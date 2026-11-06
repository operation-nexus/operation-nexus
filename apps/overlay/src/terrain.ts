// Static map layer (OVERLAY §0.10, OV-10): contours (empty), roads and sea lanes of Welcome.theater, pre-rendered
// and redrawn only when the theater or the backing-store size changes. State-dependent marks live in nodes.ts.
import type { Welcome } from "./contracts/wire/welcome";
import { STAGE_H, STAGE_W, mapFrame, type MapFrame } from "./stage-math";

export type Theater = Welcome["theater"];

const finitePos = (p: { x_m?: unknown; y_m?: unknown } | null | undefined) =>
  Number.isFinite(p?.x_m) && Number.isFinite(p?.y_m);

/** Keep only well-formed nodes (finite position, string id) and edges: the feed is untrusted
 *  (WP-13), and one bad node must not drop the whole map. Unusable bounds_m leave nothing to frame. */
export function sanitize(t: Theater): Theater {
  const b = t.bounds_m;
  const ok = b !== undefined && b !== null && b.w > 0 && b.h > 0;
  const nodes = (Array.isArray(t.nodes) ? t.nodes : [])
    .filter((n) => typeof n?.node_id === "string" && finitePos(n.pos))
    .map((n) => (typeof n.name === "string" ? n : { ...n, name: "" }));
  const edges = (Array.isArray(t.edges) ? t.edges : []).filter(
    (e) => typeof e?.a === "string" && typeof e?.b === "string",
  );
  return {
    ...t,
    nodes: ok ? nodes : [],
    edges: ok ? edges : [],
    bounds_m: ok ? b : { w: 1, h: 1 },
  };
}

/** Content key: a re-sent identical theater (reconnect) must not redraw. */
export function theaterKey(t: Theater): string {
  return JSON.stringify([t.nodes, t.edges, t.bounds_m, t.terrain_ref]);
}

export const frameOf = (t: Theater): MapFrame => mapFrame(t.bounds_m);

/** Reset the canvas to stage coordinates and clear it; null when there is no 2D context. */
export function beginDraw(
  canvas: HTMLCanvasElement,
): CanvasRenderingContext2D | null {
  const ctx = canvas.getContext("2d");
  if (ctx === null) return null;
  ctx.setTransform(canvas.width / STAGE_W, 0, 0, canvas.height / STAGE_H, 0, 0);
  ctx.clearRect(0, 0, STAGE_W, STAGE_H);
  return ctx;
}

/** Contour layer (Q-UX-20): no terrain geometry is on the wire, so this draws nothing, with or without a
 *  `terrain_ref`. It reserves the slot behind the roads; no relief is invented. Returns the paths drawn. */
export function drawContours(): number {
  return 0;
}

interface LineStyle {
  color: string;
  width: number;
  dash: number[];
}
export const ROAD_STYLE: LineStyle = {
  color: "rgba(255,184,74,0.75)",
  width: 3,
  dash: [],
};
export const SEA_STYLE: LineStyle = {
  color: "#5fa3b8",
  width: 3,
  dash: [14, 10],
};

export class TerrainLayer {
  /** Number of full draws, for tests and the perf probe. */
  draws = 0;
  private theater: Theater | null = null;
  private key: string | null = null;
  private drawnW = 0;
  private drawnH = 0;

  constructor(private readonly canvas: HTMLCanvasElement) {}

  /** Returns true when the theater changed (and so a redraw was needed). */
  setTheater(raw: Theater): boolean {
    const t = sanitize(raw);
    const key = theaterKey(t);
    if (key === this.key) return false;
    this.theater = t;
    this.key = key;
    this.draw();
    return true;
  }

  /** The canvas was resized (setting either dimension clears it): redraw once. */
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
    const t = this.theater;
    this.draws += 1;
    if (t.nodes.length === 0) return;
    const f = frameOf(t);
    drawContours();
    const pos = new Map(t.nodes.map((n) => [n.node_id, f.at(n.pos)]));
    for (const e of t.edges) {
      const a = pos.get(e.a);
      const b = pos.get(e.b);
      if (a === undefined || b === undefined) continue;
      const s = e.layer === "ROAD" ? ROAD_STYLE : SEA_STYLE;
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.width;
      ctx.setLineDash(s.dash);
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }
}
