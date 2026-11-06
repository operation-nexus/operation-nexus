// Render-time interpolation (OVERLAY §0.10, OV-7, ADR-0005): the overlay draws each unit at
// (latest server tick − 100 ms), linear between the two states that bracket that time. Past the newest
// state it extrapolates on speed and heading for at most 200 ms, and not at all while the campaign is
// paused (OV-21). Time is passed in, so it is testable without a clock.
import type { EntityView } from "./contracts/wire/snapshot";

export const DELAY_MS = 100;
export const EXTRAP_MS = 200;
export const OFFSET_WINDOW_MS = 8000; // PROPOSED
export const KEEP = 8; // samples per unit: enough to bracket the render time at any sane tick rate

export interface Pose {
  x_m: number;
  y_m: number;
  heading_deg: number;
}
interface Sample extends Pose {
  t: number;
  v: number;
}

const finite = (n: unknown): n is number =>
  typeof n === "number" && Number.isFinite(n);

/** Interpolated heading along the shortest arc, in [0, 360). */
export function lerpHeading(a: number, b: number, u: number): number {
  const d = ((((b - a) % 360) + 540) % 360) - 180;
  return (((a + d * u) % 360) + 360) % 360;
}

export class Interpolator {
  private hist = new Map<number, Sample[]>();
  private lastT = -Infinity;
  /** wall − server ms of each frame in the last OFFSET_WINDOW_MS. Their minimum (the least-delayed frame) maps
   *  server time to wall time. A sliding window, not an all-time minimum: a server that ticks slightly slow, or one
   *  early frame, ages out in a few seconds instead of pinning render time at the extrapolation cap. */
  private offsets: { wall: number; off: number }[] = [];
  private offset = Infinity;

  /** A resync or tick regress: forget everything. */
  clear(): void {
    this.hist.clear();
    this.lastT = -Infinity;
    this.offsets = [];
    this.offset = Infinity;
  }

  /** Record the store's entities as the state at `tick`, received at wall time `nowMs`. */
  observe(
    entities: ReadonlyMap<number, EntityView>,
    tick: number,
    hz: number,
    nowMs: number,
  ): void {
    if (!(hz > 0) || !finite(tick)) return;
    const t = (tick * 1000) / hz;
    if (t < this.lastT) this.clear();
    this.lastT = t;
    this.offsets.push({ wall: nowMs, off: nowMs - t });
    while (
      this.offsets.length > 1 &&
      nowMs - (this.offsets[0]?.wall ?? nowMs) > OFFSET_WINDOW_MS
    )
      this.offsets.shift();
    this.offset = Math.min(...this.offsets.map((o) => o.off));
    for (const [id, e] of entities) {
      if (!finite(e.pos?.x_m) || !finite(e.pos?.y_m)) continue;
      let s = this.hist.get(id);
      if (s === undefined) this.hist.set(id, (s = []));
      const sample = {
        t,
        x_m: e.pos.x_m,
        y_m: e.pos.y_m,
        heading_deg: finite(e.heading_deg) ? e.heading_deg : 0,
        v: finite(e.speed_mps) ? e.speed_mps : 0,
      };
      if (s.at(-1)?.t === t) s[s.length - 1] = sample;
      else s.push(sample);
      if (s.length > KEEP) s.shift();
    }
    for (const id of this.hist.keys())
      if (!entities.has(id)) this.hist.delete(id);
  }

  /** The drawn pose of every unit with history at wall time `nowMs`. */
  poses(nowMs: number, paused: boolean): Map<number, Pose> {
    const out = new Map<number, Pose>();
    const rt = nowMs - this.offset - DELAY_MS;
    for (const [id, s] of this.hist) {
      const p = at(s, rt, paused);
      if (p !== undefined) out.set(id, p);
    }
    return out;
  }
}

function at(s: Sample[], rt: number, paused: boolean): Pose | undefined {
  const last = s.at(-1);
  if (last === undefined) return undefined;
  if (rt >= last.t) {
    const dt = paused ? 0 : Math.min(rt - last.t, EXTRAP_MS) / 1000;
    const h = (last.heading_deg * Math.PI) / 180;
    return {
      x_m: last.x_m + Math.sin(h) * last.v * dt,
      y_m: last.y_m + Math.cos(h) * last.v * dt,
      heading_deg: last.heading_deg,
    };
  }
  const i = s.findIndex((x) => x.t > rt); // the first state after the render time
  const a = s[i - 1];
  const b = s[i];
  if (a === undefined || b === undefined) return s[0]; // older than the oldest state: hold it
  const u = (rt - a.t) / (b.t - a.t);
  return {
    x_m: a.x_m + (b.x_m - a.x_m) * u,
    y_m: a.y_m + (b.y_m - a.y_m) * u,
    heading_deg: lerpHeading(a.heading_deg, b.heading_deg, u),
  };
}
