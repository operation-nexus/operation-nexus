// Tracers and impact flashes (OVERLAY §0.10, NX-177), on the FX canvas. A WeaponFired draws a line from shooter
// to target until the matching WeaponImpact (or 3 s of real time), which leaves a short hit or miss flash.
// A shooter or target that is not on the map draws nothing. Lengths and looks are PROPOSED (NX-274).
import type { PublicEvent } from "./contracts/wire/delta";
import { COL } from "./nodes";
import type { MapFrame } from "./stage-math";
import type { Scene } from "./units";

export const TRACER_CAP_MS = 3000;
export const FLASH_MS = 250;
type Pos = { x_m: number; y_m: number };
type Ev = Extract<PublicEvent, { kind: "WeaponFired" | "WeaponImpact" }>;
interface Flight {
  key: string;
  shooter: number;
  target: number | null;
  node: string | null;
  at: number;
}
interface Flash {
  pos: Pos;
  hit: boolean;
  at: number;
}

const keyOf = (e: Ev): string =>
  `${e.shooter_id}|${e.target_id ?? e.target_node_id}|${e.weapon}`;

export class TracerLayer {
  flights: Flight[] = [];
  flashes: Flash[] = [];

  /** Feed the events of an applied Delta (other kinds are ignored). `where` resolves a target now. */
  events(
    evs: readonly PublicEvent[],
    nowMs: number,
    where: (target: number | null, node: string | null) => Pos | null,
  ): void {
    // Expire here too: a hidden tab pauses rAF (and so draw()) while Deltas keep arriving.
    this.flights = this.flights.filter((t) => nowMs - t.at < TRACER_CAP_MS);
    this.flashes = this.flashes.filter((h) => nowMs - h.at < FLASH_MS);
    for (const e of evs) {
      if (e.kind === "WeaponFired") {
        this.flights.push({
          key: keyOf(e),
          shooter: e.shooter_id,
          target: e.target_id,
          node: e.target_node_id,
          at: nowMs,
        });
      } else if (e.kind === "WeaponImpact") {
        const i = this.flights.findIndex((f) => f.key === keyOf(e));
        if (i >= 0) this.flights.splice(i, 1);
        const pos = where(e.target_id, e.target_node_id);
        if (pos !== null) this.flashes.push({ pos, hit: e.hit, at: nowMs });
      }
    }
  }

  clear(): void {
    this.flights = [];
    this.flashes = [];
  }

  draw(
    ctx: CanvasRenderingContext2D,
    f: MapFrame,
    s: Scene,
    where: (target: number | null, node: string | null) => Pos | null,
    nowMs: number,
  ): void {
    this.flights = this.flights.filter((t) => nowMs - t.at < TRACER_CAP_MS);
    this.flashes = this.flashes.filter((h) => nowMs - h.at < FLASH_MS);
    ctx.lineWidth = 2.5;
    ctx.setLineDash([10, 8]);
    ctx.lineDashOffset = -(nowMs / 25) % 18;
    for (const t of this.flights) {
      const from = s.pose(t.shooter);
      const to = where(t.target, t.node);
      const side = s.entities.get(t.shooter)?.side;
      if (from === undefined || to === null || side === undefined) continue;
      const [x0, y0] = f.at(from);
      const [x1, y1] = f.at(to);
      ctx.strokeStyle = COL[side];
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    for (const h of this.flashes) {
      const u = (nowMs - h.at) / FLASH_MS;
      const [x, y] = f.at(h.pos);
      ctx.globalAlpha = 1 - u;
      ctx.beginPath();
      if (h.hit) {
        ctx.arc(x, y, 6 + 18 * u, 0, Math.PI * 2);
        ctx.fillStyle = "#f8fafc";
        ctx.fill();
      } else {
        ctx.arc(x, y, 8 + 12 * u, 0, Math.PI * 2);
        ctx.strokeStyle = COL.dim;
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }
}
