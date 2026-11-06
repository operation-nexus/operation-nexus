// Node layer (OVERLAY §0.10, NX-176): everything on the map that depends on NodeView state, drawn on its own
// canvas above the static one. Redrawn on a theater change, a backing-size change or a change in the
// node state it shows, never per frame (OV-10). Palette and shapes are PROPOSED until NX-274 (Q-UX-26).
import type { NodeView } from "./contracts/wire/snapshot";
import {
  beginDraw,
  frameOf,
  sanitize,
  theaterKey,
  type Theater,
} from "./terrain";
import type { MapFrame } from "./stage-math";

type Kind = Theater["nodes"][number]["kind"];
type Owner = NodeView["owner"];
type Pt = [number, number];

export const COL = {
  COALITION: "#43dcff",
  ENEMY: "#ff4f7b",
  NEUTRAL: "#d8dde2",
  dim: "#64748b",
  alert: "#fbbf24",
  ink: "rgba(6,12,16,0.9)",
} as const;
export const FONT = '700 17px "JetBrains Mono", monospace';
/** Glyph frame radius in stage px, by kind (prototype style 3; PORT is the FOB size). */
export const NODE_R: Record<Kind, number> = {
  SANCTUARY: 25,
  AIRBASE: 27,
  FOB: 21,
  PORT: 21,
  BRIDGE: 15,
  HQ: 31,
};
/** Kinds that get a name label: campaign.strategic_node_kinds (balance/default.yaml:153). */
export const LABELLED: ReadonlySet<Kind> = new Set(["AIRBASE", "FOB", "PORT"]);
/** Capture arc radius, and the outer edge of its 5 px stroke. */
const ARC_R = (r: number): number => r * 1.4 + 6;
const ARC_OUT = (r: number): number => ARC_R(r) + 2.5;
const TINT_R = 176; // stage px, PROPOSED
const TINT_ALPHA = "26"; // hex, about 15%

const isOwner = (o: unknown): o is Owner =>
  o === "COALITION" || o === "ENEMY" || o === "NEUTRAL";
const pct = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v)
    ? Math.min(100, Math.max(0, v))
    : null;

/** Frame shape by owner, so colour is never the only cue: chamfered octagon, spiked, dashed circle. */
function framePath(ctx: CanvasRenderingContext2D, o: Owner, r: number): void {
  ctx.beginPath();
  if (o === "COALITION") {
    for (let i = 0; i < 8; i++) {
      const a = Math.PI / 8 + (i * Math.PI) / 4;
      ctx.lineTo(Math.cos(a) * r * 1.08, Math.sin(a) * r * 1.08);
    }
  } else if (o === "ENEMY") {
    for (let i = 0; i < 16; i++) {
      const a = (i * Math.PI) / 8;
      const rad = i % 2 ? r * 0.86 : r * 1.28;
      ctx.lineTo(Math.cos(a) * rad, Math.sin(a) * rad);
    }
  } else ctx.arc(0, 0, r, 0, Math.PI * 2);
  ctx.closePath();
}

function glyph(ctx: CanvasRenderingContext2D, kind: Kind, r: number): void {
  const k = r / 25;
  ctx.beginPath();
  switch (kind) {
    case "SANCTUARY":
      ctx.arc(0, 0, r * 0.5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(0, 0, 3.5, 0, Math.PI * 2);
      ctx.fill();
      return;
    case "AIRBASE": // runway cross
      ctx.moveTo(0, -15 * k);
      ctx.lineTo(0, 13 * k);
      ctx.moveTo(-12 * k, -k);
      ctx.lineTo(12 * k, -k);
      ctx.moveTo(-6 * k, 11 * k);
      ctx.lineTo(6 * k, 11 * k);
      break;
    case "FOB":
      ctx.fillRect(-7, -7, 14, 14);
      return;
    case "PORT": // anchor
      ctx.moveTo(0, -9);
      ctx.lineTo(0, 8);
      ctx.moveTo(-6, -4);
      ctx.lineTo(6, -4);
      ctx.moveTo(8, 3);
      ctx.arc(0, 2, 8, 0, Math.PI);
      break;
    case "BRIDGE": // bars
      ctx.moveTo(-9, -4);
      ctx.lineTo(9, -4);
      ctx.moveTo(-9, 4);
      ctx.lineTo(9, 4);
      break;
    case "HQ": // star
      for (let i = 0; i < 10; i++) {
        const a = -Math.PI / 2 + (i * Math.PI) / 5;
        const rad = i % 2 ? 8 : 17;
        ctx.lineTo(Math.cos(a) * rad, Math.sin(a) * rad);
      }
      ctx.closePath();
      ctx.fill();
      return;
  }
  ctx.stroke();
}

/** Crossbar across an edge at its bridge node; broken (two offset, dashed stubs) while the bridge is down. */
function crossbar(
  ctx: CanvasRenderingContext2D,
  at: Pt,
  from: Pt,
  to: Pt,
  down: boolean,
): void {
  const len = Math.hypot(to[0] - from[0], to[1] - from[1]) || 1;
  const ux = (to[0] - from[0]) / len;
  const uy = (to[1] - from[1]) / len;
  const [nx, ny] = [-uy, ux];
  const h = 30;
  ctx.lineWidth = 5;
  ctx.lineCap = "butt";
  ctx.strokeStyle = down ? COL.alert : COL.NEUTRAL;
  ctx.setLineDash(down ? [6, 5] : []);
  ctx.beginPath();
  if (down) {
    const s = 8; // each stub is shoved along the road, away from the other
    ctx.moveTo(at[0] + nx * h + ux * s, at[1] + ny * h + uy * s);
    ctx.lineTo(at[0] + ux * s + nx * 4, at[1] + uy * s + ny * 4);
    ctx.moveTo(at[0] - nx * h - ux * s, at[1] - ny * h - uy * s);
    ctx.lineTo(at[0] - ux * s - nx * 4, at[1] - uy * s - ny * 4);
  } else {
    ctx.moveTo(at[0] + nx * h, at[1] + ny * h);
    ctx.lineTo(at[0] - nx * h, at[1] - ny * h);
  }
  ctx.stroke();
  ctx.setLineDash([]);
}

export class NodeLayer {
  /** Number of full draws, for tests and the perf probe. */
  draws = 0;
  private theater: Theater | null = null;
  private tKey: string | null = null;
  private views: ReadonlyMap<string, NodeView> = new Map();
  private sKey = "";
  private drawnW = 0;
  private drawnH = 0;

  constructor(private readonly canvas: HTMLCanvasElement) {}

  setTheater(raw: Theater): void {
    const t = sanitize(raw);
    const key = theaterKey(t);
    if (key === this.tKey) return;
    this.theater = t;
    this.tKey = key;
    this.draw();
  }

  /** Called after every applied frame with the store's nodes; redraws only when what is drawn changed. */
  setNodes(views: ReadonlyMap<string, NodeView>): void {
    this.views = views;
    const t = this.theater;
    if (t === null) return;
    const key = JSON.stringify(
      [...views.values()]
        .sort((a, b) => (a.node_id < b.node_id ? -1 : 1))
        .map((v) => [
          v.node_id,
          v.owner,
          v.capture,
          v.stock_pct,
          v.starvation,
          v.intact,
          v.facilities,
        ]),
    );
    if (key === this.sKey) return;
    this.sKey = key;
    this.draw();
  }

  onResize(): void {
    if (this.drawnW !== this.canvas.width || this.drawnH !== this.canvas.height)
      this.draw();
  }

  private draw(): void {
    this.drawnW = this.canvas.width;
    this.drawnH = this.canvas.height;
    if (this.theater === null) return;
    const ctx = beginDraw(this.canvas);
    if (ctx === null) return;
    this.draws += 1;
    const t = this.theater;
    if (t.nodes.length === 0) return;
    const f = frameOf(t);
    const pos = new Map(t.nodes.map((n) => [n.node_id, f.at(n.pos)]));
    const ownerOf = (id: string): Owner | null => {
      const o = this.views.get(id)?.owner;
      return isOwner(o) ? o : null;
    };
    this.tint(ctx, t, pos, ownerOf);
    this.rings(ctx, f, ownerOf);
    for (const n of t.nodes) {
      this.node(ctx, n, pos.get(n.node_id) as Pt, this.views.get(n.node_id));
    }
    // Over the bridge node frame, so the bar (and its broken state) reads.
    for (const e of t.edges) {
      const at = e.bridge === null ? undefined : pos.get(e.bridge);
      const a = pos.get(e.a);
      const b = pos.get(e.b);
      if (at && a && b) {
        const down = this.views.get(e.bridge as string)?.intact === false;
        crossbar(ctx, at, a, b, down);
      }
    }
    ctx.textAlign = "center";
    ctx.font = FONT;
    ctx.lineJoin = "round";
    for (const n of t.nodes) {
      if (!LABELLED.has(n.kind) || n.name === "") continue;
      const [x, y] = pos.get(n.node_id) as Pt;
      const ty = y - ARC_OUT(NODE_R[n.kind]) - 6; // baseline clears the capture arc
      ctx.lineWidth = 5;
      ctx.strokeStyle = "rgba(4,9,12,0.95)";
      ctx.strokeText(n.name, x, ty, 240);
      ctx.fillStyle = "#f2f8fa";
      ctx.fillText(n.name, x, ty, 240);
    }
  }

  /** Territory tint (Q-UX-26 (4)): a soft pool around each owned node; NEUTRAL and unknown stay untinted. */
  private tint(
    ctx: CanvasRenderingContext2D,
    t: Theater,
    pos: Map<string, Pt>,
    ownerOf: (id: string) => Owner | null,
  ): void {
    for (const n of t.nodes) {
      const o = ownerOf(n.node_id);
      if (o !== "COALITION" && o !== "ENEMY") continue;
      const [x, y] = pos.get(n.node_id) as Pt;
      const g = ctx.createRadialGradient(x, y, 0, x, y, TINT_R);
      g.addColorStop(0, COL[o] + TINT_ALPHA);
      g.addColorStop(1, COL[o] + "00");
      ctx.fillStyle = g;
      ctx.fillRect(x - TINT_R, y - TINT_R, 2 * TINT_R, 2 * TINT_R);
    }
  }

  /** Facility ring_m as a thin dashed circle at the facility; null draws nothing. */
  private rings(
    ctx: CanvasRenderingContext2D,
    f: MapFrame,
    ownerOf: (id: string) => Owner | null,
  ): void {
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 6]);
    ctx.globalAlpha = 0.6;
    for (const [id, v] of this.views) {
      if (!Array.isArray(v.facilities)) continue;
      ctx.strokeStyle = COL[ownerOf(id) ?? "NEUTRAL"];
      for (const fa of v.facilities) {
        const r = fa?.ring_m;
        if (typeof r !== "number" || !(r > 0) || !fa.pos) continue;
        if (!Number.isFinite(fa.pos.x_m) || !Number.isFinite(fa.pos.y_m))
          continue;
        const [x, y] = f.at(fa.pos);
        ctx.beginPath();
        ctx.arc(x, y, r * f.k, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    ctx.setLineDash([]);
  }

  private node(
    ctx: CanvasRenderingContext2D,
    n: Theater["nodes"][number],
    [x, y]: Pt,
    v: NodeView | undefined,
  ): void {
    const r = NODE_R[n.kind] ?? NODE_R.FOB;
    // No NodeView yet (cold start): the kind glyph in a dim colour, no owner frame (DI-1).
    const o = v !== undefined && isOwner(v.owner) ? v.owner : null;
    const col = o === null ? COL.dim : COL[o];
    ctx.save();
    ctx.translate(x, y);
    if (o !== null) {
      framePath(ctx, o, r);
      ctx.fillStyle = COL.ink;
      ctx.fill();
      ctx.lineWidth = 3.5;
      ctx.strokeStyle = col;
      ctx.setLineDash(o === "NEUTRAL" ? [6, 5] : []);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.strokeStyle = col;
    ctx.fillStyle = col;
    ctx.lineWidth = 2.6;
    ctx.lineCap = "round";
    glyph(ctx, n.kind, r);
    const cap = v?.capture;
    const p = pct(cap?.progress_pct);
    if (
      p !== null &&
      p > 0 &&
      (cap?.side === "COALITION" || cap?.side === "ENEMY")
    ) {
      ctx.strokeStyle = COL[cap.side];
      ctx.lineWidth = 5;
      ctx.beginPath();
      const a0 = -Math.PI / 2;
      ctx.arc(0, 0, ARC_R(r), a0, a0 + (p / 100) * Math.PI * 2);
      ctx.stroke();
    }
    const s = pct(v?.stock_pct);
    if (o === "COALITION" && s !== null) {
      const w = 44;
      const by = ARC_OUT(r) + 4; // clears the capture arc
      ctx.lineWidth = 2;
      ctx.strokeStyle = COL.dim;
      ctx.strokeRect(-w / 2, by, w, 8);
      ctx.fillStyle = v?.starvation === "OK" ? COL.COALITION : COL.alert;
      ctx.fillRect(-w / 2, by, (w * s) / 100, 8);
      if (v?.starvation === "LOW" || v?.starvation === "EMPTY") {
        ctx.font = FONT; // not smaller than the labels
        ctx.textAlign = "center";
        ctx.fillStyle = COL.alert;
        ctx.fillText(v.starvation, 0, by + 28);
      }
    }
    ctx.restore();
  }
}
