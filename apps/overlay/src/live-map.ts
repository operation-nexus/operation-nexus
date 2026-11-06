// The real-time map loop (OVERLAY §0.10, NX-177): one requestAnimationFrame callback that draws the units and
// FX canvases from the wire store. The static and node canvases are never given to it (OV-10).
import type { Delta } from "./contracts/wire/delta";
import type { EntityView, Hud, Snapshot } from "./contracts/wire/snapshot";
import { TracerLayer } from "./fx";
import { Interpolator, type Pose } from "./interp";
import type { WireStore } from "./net/store";
import type { MapFrame } from "./stage-math";
import { beginDraw, frameOf, sanitize } from "./terrain";
import { drawWorld, type Scene } from "./units";

export interface LoopEnv {
  now: () => number;
  raf: (cb: () => void) => number;
  caf: (id: number) => void;
}
type Pos = { x_m: number; y_m: number };

const rawPose = (e: EntityView | undefined): Pose | undefined =>
  e !== undefined && Number.isFinite(e.pos?.x_m) && Number.isFinite(e.pos?.y_m)
    ? {
        x_m: e.pos.x_m,
        y_m: e.pos.y_m,
        heading_deg: Number.isFinite(e.heading_deg) ? e.heading_deg : 0,
      }
    : undefined;

export class LiveMap {
  /** Milliseconds the last frame spent per stage, for the perf probe. */
  timing = { interp: 0, units: 0, fx: 0 };
  private interp = new Interpolator();
  private tracers = new TracerLayer();
  private rafId: number | null = null;
  private seen: unknown = null;
  private frameOfTheater: MapFrame | null = null;
  private nodePos = new Map<string, Pos>();

  constructor(
    private readonly units: HTMLCanvasElement,
    private readonly fxCanvas: HTMLCanvasElement,
    private readonly store: () => WireStore,
    private readonly env: LoopEnv,
  ) {}

  /** Call from the wire client's onFrame, after the store applied the frame. */
  onFrame(f: Snapshot | Hud | Delta): void {
    if (f.type === "Hud") return;
    const s = this.store();
    if (s.tick === null || s.tickRateHz === null) return;
    const now = this.env.now();
    this.interp.observe(s.entities, s.tick, s.tickRateHz, now);
    if (f.type === "Delta")
      this.tracers.events(f.events, now, (t, n) => this.where(t, n));
  }

  /** A Welcome (reconnect or restart): the history and any flight in the air no longer mean anything. */
  reset(): void {
    this.interp.clear();
    this.tracers.clear();
  }

  start(): void {
    const loop = (): void => {
      try {
        this.frame();
      } finally {
        this.rafId = this.env.raf(loop); // one bad frame must not freeze the map
      }
    };
    this.rafId = this.env.raf(loop);
  }

  stop(): void {
    if (this.rafId !== null) this.env.caf(this.rafId);
    this.rafId = null;
  }

  private poses = new Map<number, Pose>();
  private where(target: number | null, node: string | null): Pos | null {
    if (target !== null)
      return (
        this.poses.get(target) ?? this.store().entities.get(target)?.pos ?? null
      );
    return node === null ? null : (this.nodePos.get(node) ?? null);
  }

  frame(): void {
    const s = this.store();
    const t0 = this.env.now();
    const ctx = beginDraw(this.units);
    const fctx = beginDraw(this.fxCanvas);
    const th = s.theater;
    if (th === null || ctx === null || fctx === null) return;
    if (th !== this.seen) {
      const t = sanitize(th);
      this.seen = th;
      this.frameOfTheater = frameOf(t);
      this.nodePos = new Map(t.nodes.map((n) => [n.node_id, n.pos]));
    }
    const f = this.frameOfTheater;
    if (f === null) return;
    const hz = s.tickRateHz ?? 0;
    const paused = s.hud?.campaign_clock?.paused === true;
    // Unsynced (resync, gap): the history is dropped; the last store state is drawn still until the Snapshot.
    if (s.tick === null) this.interp.clear();
    this.poses = this.interp.poses(t0, paused);
    const t1 = this.env.now();
    const tick = s.tick ?? 0;
    const scene: Scene = {
      entities: s.entities,
      blobs: s.blobs,
      lastKnown: s.lastKnown,
      pose: (id) => this.poses.get(id) ?? rawPose(s.entities.get(id)),
      ageSec: (seen) => (hz > 0 ? Math.max(0, (tick - seen) / hz) : 0),
    };
    drawWorld(ctx, f, scene);
    const t2 = this.env.now();
    this.tracers.draw(fctx, f, scene, (a, b) => this.where(a, b), t0);
    const t3 = this.env.now();
    this.timing = { interp: t1 - t0, units: t2 - t1, fx: t3 - t2 };
  }
}
