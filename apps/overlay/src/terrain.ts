// Static terrain layer (OVERLAY §0.2, OV-10): nodes and edges of Welcome.theater, pre-rendered and
// redrawn only when the theater or the backing-store size changes. Units are NX-177; no terrain contours yet (NX-176).
import type { Welcome } from "./contracts/wire/welcome";
import { STAGE_H, STAGE_W, safeRect } from "./stage-math";

export type Theater = Welcome["theater"];

export const PAD = 40; // stage px kept free around the outermost nodes
const NODE_R = 12;

/** Keep only well-formed nodes (finite position, string id) and edges: the feed is untrusted
 *  (WP-13), and one bad node must not drop the whole map. */
export function sanitize(t: Theater): Theater {
  const nodes = (Array.isArray(t.nodes) ? t.nodes : []).filter(
    (n) =>
      typeof n?.node_id === "string" &&
      Number.isFinite(n.pos?.x_m) &&
      Number.isFinite(n.pos?.y_m),
  );
  const edges = (Array.isArray(t.edges) ? t.edges : []).filter(
    (e) => typeof e?.a === "string" && typeof e?.b === "string",
  );
  return { ...t, nodes, edges };
}

/** Content key: a re-sent identical theater (reconnect) must not redraw. */
export function theaterKey(t: Theater): string {
  return JSON.stringify([t.nodes, t.edges]);
}

/** Fit the node bounding box into the safe area, aspect kept, centered. y_m maps to screen y unflipped
 *  ([UNVERIFIED]: the coordinate convention is not in the spec; change here when it is). */
export function projector(
  t: Theater,
): (p: { x_m: number; y_m: number }) => [number, number] {
  const xs = t.nodes.map((n) => n.pos.x_m);
  const ys = t.nodes.map((n) => n.pos.y_m);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const spanX = Math.max(Math.max(...xs) - minX, 1);
  const spanY = Math.max(Math.max(...ys) - minY, 1);
  const r = safeRect();
  const k = Math.min((r.w - 2 * PAD) / spanX, (r.h - 2 * PAD) / spanY);
  const ox = r.x + (r.w - spanX * k) / 2;
  const oy = r.y + (r.h - spanY * k) / 2;
  return (p) => [ox + (p.x_m - minX) * k, oy + (p.y_m - minY) * k];
}

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
    const ctx = this.canvas.getContext("2d");
    if (ctx === null) return;
    const t = this.theater;
    const k = this.canvas.width / STAGE_W;
    ctx.setTransform(k, 0, 0, this.canvas.height / STAGE_H, 0, 0);
    ctx.clearRect(0, 0, STAGE_W, STAGE_H);
    if (t.nodes.length === 0) {
      this.draws += 1;
      return;
    }
    const at = projector(t);
    const pos = new Map(t.nodes.map((n) => [n.node_id, at(n.pos)]));
    ctx.lineWidth = 3;
    for (const e of t.edges) {
      const a = pos.get(e.a);
      const b = pos.get(e.b);
      if (a === undefined || b === undefined) continue;
      ctx.strokeStyle = e.layer === "ROAD" ? "#64748b" : "#0e7490";
      ctx.setLineDash(e.layer === "ROAD" ? [] : [14, 10]);
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.fillStyle = "#fbbf24";
    for (const p of pos.values()) {
      ctx.fillRect(p[0] - NODE_R, p[1] - NODE_R, 2 * NODE_R, 2 * NODE_R);
    }
    this.draws += 1;
  }
}
