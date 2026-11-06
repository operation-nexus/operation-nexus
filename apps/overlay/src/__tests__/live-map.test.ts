import { describe, expect, it } from "vitest";
import type { Delta } from "../contracts/wire/delta";
import type {
  BlobView,
  EntityView,
  LastKnownView,
} from "../contracts/wire/snapshot";
import { FLASH_MS, TRACER_CAP_MS } from "../fx";
import {
  DELAY_MS,
  EXTRAP_MS,
  Interpolator,
  KEEP,
  lerpHeading,
} from "../interp";
import { LiveMap } from "../live-map";
import { WireStore } from "../net/store";
import { COL, NodeLayer } from "../nodes";
import { mapFrame } from "../stage-math";
import { TerrainLayer, type Theater } from "../terrain";
import {
  BLOB_R,
  FILL,
  GARRISON_ALPHA,
  LAST_KNOWN_ALPHA,
  SHAPE,
  ageText,
  drawWorld,
  type Scene,
} from "../units";
import { expectUnderBudget } from "./perf-gate";

type Op = [string, unknown[]];
type Kind = EntityView["unit_kind"];
type Ev = Delta["events"][number];

function rec(): { canvas: HTMLCanvasElement; ops: Op[] } {
  const ops: Op[] = [];
  const ctx = new Proxy(
    {},
    {
      get: (_t, name: string) => {
        if (name === "createRadialGradient")
          return (...a: unknown[]) => {
            ops.push([name, a]);
            return { addColorStop: () => undefined };
          };
        return (...a: unknown[]) => void ops.push([name, a]);
      },
      set: (_t, name: string, v) => {
        ops.push(["=" + name, [v]]);
        return true;
      },
    },
  );
  const canvas = {
    width: 1920,
    height: 1080,
    getContext: () => ctx,
  } as unknown as HTMLCanvasElement;
  return { canvas, ops };
}
const of = (ops: Op[], n: string): Op[] => ops.filter((o) => o[0] === n);
const vals = (ops: Op[], n: string): unknown[] =>
  of(ops, "=" + n).map((o) => o[1][0]);
const arg0 = (ops: Op[], n: string): unknown => of(ops, n)[0]?.[1][0];

const ent = (id: number, over: Partial<EntityView> = {}): EntityView => ({
  entity_id: id,
  unit_kind: "STRIKE_FIGHTER",
  side: "COALITION",
  domain: "AIR",
  owner_kind: "COMMANDER",
  callsign: null,
  pos: { x_m: 100000, y_m: 100000 },
  heading_deg: 0,
  speed_mps: 0,
  hp_pct: 100,
  damage_state: "HEALTHY",
  painted: false,
  spotted: null,
  package_id: null,
  follow_entity_id: null,
  follower_count: 0,
  cosmetic: { halo: null, trail: null },
  badges: [],
  probation: false,
  auto: false,
  ...over,
});
const F = mapFrame({ w: 400000, h: 240000 });
function scene(over: Partial<Scene> & { list?: EntityView[] } = {}): Scene {
  const entities = new Map((over.list ?? []).map((e) => [e.entity_id, e]));
  return {
    entities,
    blobs: [],
    lastKnown: [],
    pose: (id) => {
      const e = entities.get(id);
      return e && { ...e.pos, heading_deg: e.heading_deg };
    },
    ageSec: () => 0,
    ...over,
  };
}
function draw(s: Scene): Op[] {
  const { canvas, ops } = rec();
  drawWorld(canvas.getContext("2d") as CanvasRenderingContext2D, F, s);
  return ops;
}
const one = (over: Partial<EntityView>): Op[] =>
  draw(scene({ list: [ent(1, over)] }));
const outline = (ops: Op[]): string =>
  JSON.stringify(
    ops.filter((o) => ["moveTo", "lineTo"].includes(o[0])).map((o) => o[1]),
  );
const verts = (o: Op[]): number =>
  of(o, "moveTo").length + of(o, "lineTo").length;

describe("units (OVERLAY §0.10, OV-2)", () => {
  const kinds = Object.keys(SHAPE) as Kind[];
  it("draws one closed silhouette per unit_kind, distinct per shape family", () => {
    const coalition: Kind[] = [
      "STRIKE_FIGHTER",
      "RECON_UAV",
      "LOGI_TRUCK",
      "GARRISON_INFANTRY",
      "RADAR_SITE",
      "AIR_DEFENSE_SITE",
    ];
    const sigs = coalition.map((unit_kind) => outline(one({ unit_kind })));
    expect(new Set(sigs).size).toBe(coalition.length);
    for (const k of kinds) {
      const ops = one({ unit_kind: k });
      expect(of(ops, "closePath")).toHaveLength(1);
      expect(verts(ops)).toBe(SHAPE[k].pts.length);
    }
  });

  it("coalition is angular cyan, enemy the same shape jagged magenta", () => {
    const c = one({ unit_kind: "STRIKE_FIGHTER" });
    const e = one({ unit_kind: "ENEMY_STRIKE_FIGHTER", side: "ENEMY" });
    expect(vals(c, "strokeStyle")).toEqual([COL.COALITION]);
    expect(vals(e, "strokeStyle")).toEqual([COL.ENEMY]);
    expect(verts(e)).toBe(2 * verts(c));
  });

  it("rotates by heading_deg: 0 is north, 90 is east on the screen", () => {
    const nose = (h: number): [number, number] => {
      const ops = one({ heading_deg: h });
      const a = (arg0(ops, "rotate") as number | undefined) ?? 0;
      const [x, y] = of(ops, "moveTo")[0]?.[1] as [number, number]; // the nose
      // canvas rotate(a) is clockwise on screen
      return [
        x * Math.cos(a) - y * Math.sin(a),
        x * Math.sin(a) + y * Math.cos(a),
      ];
    };
    const [nx, ny] = nose(0);
    expect(nx).toBeCloseTo(0);
    expect(ny).toBeLessThan(0); // up
    const [ex, ey] = nose(90);
    expect(ex).toBeGreaterThan(10);
    expect(ey).toBeCloseTo(0);
    expect(nose(180)[1]).toBeGreaterThan(10); // south
  });

  it("a facility (STATIC) is not rotated", () => {
    const ops = one({
      domain: "STATIC",
      unit_kind: "RADAR_SITE",
      heading_deg: 90,
    });
    expect(of(ops, "rotate")).toHaveLength(0);
  });

  it("damage_state is a fill ladder with an outline at every rung", () => {
    const fills = (d: EntityView["damage_state"]): number[] =>
      vals(one({ damage_state: d }), "globalAlpha") as number[];
    expect(fills("HEALTHY")).toContain(FILL.HEALTHY);
    expect(fills("DAMAGED")).toContain(FILL.DAMAGED);
    expect(fills("MISSION_KILL")).toContain(FILL.MISSION_KILL);
    expect(fills("DISABLED")).toContain(0);
    expect(FILL.HEALTHY).toBeGreaterThan(FILL.DAMAGED);
    expect(FILL.DAMAGED).toBeGreaterThan(FILL.MISSION_KILL);
    expect(FILL.MISSION_KILL).toBeGreaterThan(FILL.DISABLED);
    for (const d of Object.keys(FILL) as EntityView["damage_state"][])
      expect(of(one({ damage_state: d }), "stroke")).toHaveLength(1);
    expect(arg0(one({ damage_state: "DISABLED" }), "setLineDash")).toEqual([
      5, 4,
    ]);
    expect(arg0(one({ damage_state: "HEALTHY" }), "setLineDash")).toEqual([]);
  });

  it("AI_GARRISON is drawn dimmer than a commander's unit", () => {
    const a = (o: EntityView["owner_kind"]): number =>
      Math.max(...(vals(one({ owner_kind: o }), "globalAlpha") as number[]));
    expect(a("COMMANDER")).toBe(1);
    expect(a("AI_GARRISON")).toBe(GARRISON_ALPHA);
  });

  it("draws no text (no labels in this slice)", () => {
    expect(of(one({ callsign: "X" }), "fillText")).toHaveLength(0);
  });
});

describe("fog (FOW-6a, FOW-9)", () => {
  const at = { x_m: 200000, y_m: 120000 };
  const blob = (size: BlobView["size"]): BlobView => ({
    blob_id: size,
    cell_center: at,
    size,
  });
  it("blobs are a fuzzy gradient sized by S, M, L, with no shape, heading or text", () => {
    for (const s of ["S", "M", "L"] as const) {
      const ops = draw(scene({ blobs: [blob(s)] }));
      const g = of(ops, "createRadialGradient")[0]?.[1] as number[];
      expect(g[5]).toBe(BLOB_R[s]);
      expect([g[0], g[1]]).toEqual(F.at(at));
      expect(of(ops, "closePath")).toHaveLength(0);
      expect(of(ops, "fillText")).toHaveLength(0);
    }
    expect(BLOB_R.S).toBeLessThan(BLOB_R.M);
    expect(BLOB_R.M).toBeLessThan(BLOB_R.L);
  });

  const lk = (over: Partial<LastKnownView> = {}): LastKnownView => ({
    entity_id: 9,
    unit_kind: "ENEMY_ARMOR",
    pos: { x_m: 50000, y_m: 50000 },
    heading_deg: 30,
    seen_tick: 10,
    ...over,
  });
  it("last-known is the frozen shape, dashed, faded, with its age", () => {
    const ops = draw(scene({ lastKnown: [lk()], ageSec: () => 75 }));
    expect(arg0(ops, "setLineDash")).toEqual([5, 4]);
    expect(of(ops, "fill")).toHaveLength(0); // outline only
    expect(vals(ops, "globalAlpha")[0]).toBe(LAST_KNOWN_ALPHA);
    expect(arg0(ops, "fillText")).toBe("1m");
    expect(arg0(ops, "rotate")).toBeCloseTo((30 * Math.PI) / 180);
  });
  it("a blob with a NaN or missing cell_center draws nothing", () => {
    for (const cell_center of [{ x_m: NaN, y_m: 1 }, undefined]) {
      const b = { blob_id: "x", cell_center, size: "S" } as unknown as BlobView;
      expect(
        of(draw(scene({ blobs: [b] })), "createRadialGradient"),
      ).toHaveLength(0);
    }
  });
  it("last-known is gone when the server drops it", () => {
    const ops = draw(scene({ lastKnown: [] }));
    expect(
      ops.filter((o) => ["stroke", "fillText"].includes(o[0])),
    ).toHaveLength(0);
  });
  it("formats the age", () => {
    expect([ageText(0), ageText(59.9), ageText(60), ageText(185)]).toEqual([
      "0s",
      "59s",
      "1m",
      "3m",
    ]);
  });
});

// ---- interpolation (OV-7) ----
const HZ = 10; // 100 ms per tick
function feed(
  iv: Interpolator,
  tick: number,
  now: number,
  e: EntityView[],
): void {
  iv.observe(new Map(e.map((x) => [x.entity_id, x])), tick, HZ, now);
}
const X = (x: number, extra: Partial<EntityView> = {}): EntityView =>
  ent(1, { pos: { x_m: x, y_m: 0 }, ...extra });

describe("interpolation (OV-7, OV-21)", () => {
  // tick 10 arrives at wall 5000, tick 11 at 5100: wall - server offset is 4000, so wall w renders server w - 4100.
  const two = (): Interpolator => {
    const iv = new Interpolator();
    feed(iv, 10, 5000, [X(0)]);
    feed(iv, 11, 5100, [X(1000, { speed_mps: 100, heading_deg: 90 })]);
    return iv;
  };
  it("renders 100 ms behind the latest tick, linear between the bracketing states", () => {
    expect(DELAY_MS).toBe(100);
    const iv = two();
    expect(iv.poses(5100, false).get(1)?.x_m).toBeCloseTo(0); // render time = tick 10
    expect(iv.poses(5150, false).get(1)?.x_m).toBeCloseTo(500);
    expect(iv.poses(5200, false).get(1)?.x_m).toBeCloseTo(1000);
  });
  it("holds the oldest state before the history starts", () => {
    expect(two().poses(4000, false).get(1)?.x_m).toBe(0);
  });
  it("extrapolates on speed and heading, at most 200 ms", () => {
    expect(EXTRAP_MS).toBe(200);
    const iv = two();
    // 150 ms past tick 11 at 100 m/s east: +15 m on x, none on y (heading 90 = east)
    const p = iv.poses(5350, false).get(1);
    expect(p?.x_m).toBeCloseTo(1015);
    expect(p?.y_m).toBeCloseTo(0);
    expect(iv.poses(5800, false).get(1)?.x_m).toBeCloseTo(1020); // capped at 200 ms = 20 m
    expect(iv.poses(60000, false).get(1)?.x_m).toBeCloseTo(1020);
  });
  it("extrapolates north for heading 0", () => {
    const iv = new Interpolator();
    feed(iv, 10, 5000, [X(0, { speed_mps: 50 })]);
    expect(iv.poses(5300, false).get(1)?.y_m).toBeCloseTo(50 * 0.2);
  });
  it("does not extrapolate while paused: positions frozen at the latest state", () => {
    const iv = two();
    expect(iv.poses(5350, true).get(1)?.x_m).toBe(1000);
    expect(iv.poses(60000, true).get(1)?.x_m).toBe(1000);
  });
  it("turns by the shortest arc", () => {
    expect(lerpHeading(350, 10, 0.5)).toBeCloseTo(0);
    expect(lerpHeading(10, 350, 0.25)).toBeCloseTo(5);
    expect(lerpHeading(0, 90, 0.5)).toBeCloseTo(45);
    const iv = new Interpolator();
    feed(iv, 10, 5000, [X(0, { heading_deg: 350 })]);
    feed(iv, 11, 5100, [X(0, { heading_deg: 10 })]);
    const h = iv.poses(5150, false).get(1)?.heading_deg ?? -1;
    expect(h < 1 || h > 359).toBe(true);
  });
  it("a tick regress drops the history", () => {
    const iv = two();
    feed(iv, 3, 9000, [X(77)]);
    // one state left: that one, whatever the time
    expect(iv.poses(9000, false).get(1)?.x_m).toBe(77);
    expect(iv.poses(1, false).get(1)?.x_m).toBe(77);
  });
  it("keeps the clock mapping when the server ticks slightly slow (100.1 ms per tick)", () => {
    const iv = new Interpolator();
    let wall = 0;
    for (let k = 0; k <= 6000; k++) {
      feed(iv, k, wall, [X(k * 10)]);
      wall += 100.1;
    }
    const last = wall - 100.1;
    // 50 ms after the last frame the unit is still moving between states, not pinned at the cap
    const a = iv.poses(last + 20, false).get(1)?.x_m ?? 0;
    const b = iv.poses(last + 70, false).get(1)?.x_m ?? 0;
    expect(b).toBeGreaterThan(a);
    expect(iv.poses(last + 70, false).get(1)?.x_m).toBeLessThan(6000 * 10 + 1);
  });
  it("keeps a bounded history per unit", () => {
    const iv = new Interpolator();
    for (let k = 0; k < 20; k++) feed(iv, k, k * 100, [X(k)]);
    const h = (iv as unknown as { hist: Map<number, unknown[]> }).hist;
    expect(h.get(1)).toHaveLength(KEEP);
  });
  it("forgets a unit the store dropped, and clear() forgets all", () => {
    const iv = two();
    feed(iv, 12, 5200, []);
    expect(iv.poses(5200, false).size).toBe(0);
    feed(iv, 13, 5300, [X(5)]);
    iv.clear();
    expect(iv.poses(5300, false).size).toBe(0);
  });
});

// ---- the loop ----
const theater = (): Theater =>
  ({
    nodes: [
      {
        node_id: "hq",
        name: "HQ",
        kind: "HQ",
        pos: { x_m: 300000, y_m: 50000 },
      },
    ],
    edges: [],
    bounds_m: { w: 400000, h: 240000 },
    terrain_ref: null,
  }) as unknown as Theater;
function rig() {
  const u = rec();
  const f = rec();
  const store = new WireStore();
  store.theater = theater();
  store.tickRateHz = HZ;
  const clock = { t: 5000 };
  const live = new LiveMap(u.canvas, f.canvas, () => store, {
    now: () => clock.t,
    raf: () => 1,
    caf: () => undefined,
  });
  const recv = (tick: number, e: EntityView[], events: Ev[] = []): void => {
    store.entities = new Map(e.map((x) => [x.entity_id, x]));
    store.tick = tick;
    live.onFrame({ type: "Delta", events } as Delta);
  };
  return { live, store, units: u.ops, fx: f.ops, clock, recv };
}
const fired = (s: number, t: number | null, node: string | null = null) =>
  ({
    kind: "WeaponFired",
    shooter_id: s,
    target_id: t,
    target_node_id: node,
    weapon: "w",
    tick: 1,
    event_seq: 1,
    campaign_id: "c",
    impact_tick: 2,
  }) as unknown as Ev;
const impact = (s: number, t: number | null, hit: boolean) =>
  ({
    kind: "WeaponImpact",
    shooter_id: s,
    target_id: t,
    target_node_id: null,
    weapon: "w",
    hit,
    tick: 2,
    event_seq: 2,
    campaign_id: "c",
  }) as unknown as Ev;
const A = (id: number, x: number, side: EntityView["side"] = "COALITION") =>
  ent(id, { side, pos: { x_m: x, y_m: 100000 } });
const two = (): EntityView[] => [A(1, 100000), A(2, 200000, "ENEMY")];

describe("tracers (FX canvas)", () => {
  it("fire draws shooter to target until the impact, then a flash, then nothing", () => {
    const r = rig();
    r.recv(10, two(), [fired(1, 2)]);
    r.live.frame();
    expect(of(r.fx, "lineTo")).toHaveLength(1);
    expect(vals(r.fx, "strokeStyle")).toEqual([COL.COALITION]);
    r.fx.length = 0;
    r.clock.t += 40;
    r.recv(11, two(), [impact(1, 2, true)]);
    r.live.frame();
    expect(of(r.fx, "lineTo")).toHaveLength(0);
    expect(of(r.fx, "arc")).toHaveLength(1);
    expect(of(r.fx, "fill")).toHaveLength(1); // hit: filled
    r.fx.length = 0;
    r.clock.t += FLASH_MS + 1;
    r.live.frame();
    expect(of(r.fx, "arc")).toHaveLength(0);
    expect(of(r.fx, "lineTo")).toHaveLength(0);
  });
  it("two weapons from one shooter at one target: each impact ends its own flight", () => {
    const r = rig();
    const w = (weapon: string, ev: Ev): Ev => ({ ...ev, weapon }) as Ev;
    r.recv(10, two(), [w("a", fired(1, 2))]);
    r.clock.t += 2000;
    r.recv(11, two(), [w("b", fired(1, 2)), w("b", impact(1, 2, true))]);
    // b's impact must end b, not the older a: a then times out at 3 s after its own fire
    r.clock.t += 1500;
    r.live.frame();
    expect(of(r.fx, "lineTo")).toHaveLength(0);
  });
  it("a miss flashes as a ring, not a fill", () => {
    const r = rig();
    r.recv(10, two(), [fired(1, 2), impact(1, 2, false)]);
    r.live.frame();
    expect(of(r.fx, "arc")).toHaveLength(1);
    expect(of(r.fx, "fill")).toHaveLength(0);
    expect(of(r.fx, "stroke")).toHaveLength(1);
  });
  it("a tracer with no impact stops at 3 s of real time", () => {
    const r = rig();
    r.recv(10, two(), [fired(1, 2)]);
    r.clock.t += TRACER_CAP_MS - 1;
    r.live.frame();
    expect(of(r.fx, "lineTo")).toHaveLength(1);
    r.fx.length = 0;
    r.clock.t += 2;
    r.live.frame();
    expect(of(r.fx, "lineTo")).toHaveLength(0);
  });
  it("draws nothing for a shooter or a target that is not in the store", () => {
    const r = rig();
    r.recv(10, [A(2, 200000, "ENEMY")], [fired(1, 2)]); // no shooter
    r.live.frame();
    expect(of(r.fx, "lineTo")).toHaveLength(0);
    const q = rig();
    q.recv(10, [A(1, 100000)], [fired(1, 2)]); // no target
    q.live.frame();
    expect(of(q.fx, "lineTo")).toHaveLength(0);
    q.recv(11, [A(1, 100000)], [impact(1, 2, true)]); // no flash either
    q.live.frame();
    expect(of(q.fx, "arc")).toHaveLength(0);
  });
  it("a node target resolves from the theater", () => {
    const r = rig();
    r.recv(10, [A(1, 100000)], [fired(1, null, "hq")]);
    r.live.frame();
    expect(of(r.fx, "lineTo")[0]?.[1]).toEqual(
      F.at({ x_m: 300000, y_m: 50000 }),
    );
  });
  it("a Welcome drops flights in the air", () => {
    const r = rig();
    r.recv(10, two(), [fired(1, 2)]);
    r.live.reset();
    r.live.frame();
    expect(of(r.fx, "lineTo")).toHaveLength(0);
  });
});

describe("the frame loop", () => {
  it("moves a unit between server states and holds the last store state on a resync", () => {
    const r = rig();
    r.recv(10, [A(1, 0)]);
    r.clock.t = 5100;
    r.recv(11, [A(1, 100000)]);
    r.clock.t = 5150;
    r.live.frame();
    expect(arg0(r.units, "translate")).toBe(
      F.at({ x_m: 50000, y_m: 100000 })[0],
    );
    r.units.length = 0;
    r.store.resync(); // tick null: history dropped, last state stays on screen
    r.live.frame();
    expect(arg0(r.units, "translate")).toBe(
      F.at({ x_m: 100000, y_m: 100000 })[0],
    );
  });
  it("never touches the static or node canvases", () => {
    const t = rec();
    const n = rec();
    new TerrainLayer(t.canvas).setTheater(theater());
    new NodeLayer(n.canvas).setTheater(theater());
    const [tn, nn] = [t.ops.length, n.ops.length];
    const r = rig();
    r.recv(10, [A(1, 0)], [fired(1, null, "hq")]);
    for (let i = 0; i < 30; i++) {
      r.clock.t += 16;
      r.live.frame();
    }
    expect([t.ops.length, n.ops.length]).toEqual([tn, nn]);
    expect(r.units.length).toBeGreaterThan(0);
    expect(r.fx.length).toBeGreaterThan(0);
  });
  it("starts and stops the rAF loop", () => {
    const calls: string[] = [];
    const u = rec();
    const live = new LiveMap(u.canvas, u.canvas, () => new WireStore(), {
      now: () => 0,
      raf: () => (calls.push("raf"), 7),
      caf: (id) => void calls.push(`caf${id}`),
    });
    live.start();
    live.stop();
    expect(calls).toEqual(["raf", "caf7"]);
  });
});

describe("perf at 1,000 entities (OV-10; proposed split: interp 2 ms, units 6 ms, FX 3 ms)", () => {
  it("stays inside the split (JS side, against a no-op 2D context)", () => {
    const noop = new Proxy(
      {},
      { get: () => () => ({ addColorStop: () => undefined }), set: () => true },
    );
    const canvas = {
      width: 1920,
      height: 1080,
      getContext: () => noop,
    } as unknown as HTMLCanvasElement;
    const store = new WireStore();
    store.theater = theater();
    store.tickRateHz = HZ;
    const live = new LiveMap(canvas, canvas, () => store, {
      now: () => performance.now(),
      raf: () => 1,
      caf: () => undefined,
    });
    const kinds = Object.keys(SHAPE) as Kind[];
    const mk = (tick: number): EntityView[] =>
      Array.from({ length: 1000 }, (_, i) =>
        ent(i + 1, {
          unit_kind: kinds[i % kinds.length] ?? "STRIKE_FIGHTER",
          side: i % 3 === 0 ? "ENEMY" : "COALITION",
          pos: { x_m: (i * 397 + tick * 50) % 400000, y_m: (i * 211) % 240000 },
          heading_deg: i % 360,
          speed_mps: 100,
        }),
      );
    const events = Array.from({ length: 100 }, (_, i) => fired(i + 1, i + 2));
    const ms = {
      interp: [] as number[],
      units: [] as number[],
      fx: [] as number[],
    };
    for (let k = 0; k < 120; k++) {
      store.entities = new Map(mk(k).map((e) => [e.entity_id, e]));
      store.tick = k;
      live.onFrame({ type: "Delta", events: k === 0 ? events : [] } as Delta);
      live.frame();
      if (k >= 20)
        for (const s of ["interp", "units", "fx"] as const)
          ms[s].push(live.timing[s]);
    }
    const p95 = (a: number[]): number =>
      [...a].sort((x, y) => x - y)[Math.floor(a.length * 0.95)] ?? 0;
    expectUnderBudget(p95(ms.interp), 2);
    expectUnderBudget(p95(ms.units), 6);
    expectUnderBudget(p95(ms.fx), 3);
    expect(live.timing.units).toBeGreaterThan(0);
  });
});
