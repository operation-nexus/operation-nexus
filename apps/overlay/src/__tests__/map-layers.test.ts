import { describe, expect, it } from "vitest";
import type { NodeView } from "../contracts/wire/snapshot";
import { LABELLED, NODE_R, NodeLayer } from "../nodes";
import { MAP_RECT, mapFrame } from "../stage-math";
import { TerrainLayer, drawContours, frameOf, type Theater } from "../terrain";

type Op = [string, unknown[]];

/** A canvas whose 2D context records every call and property assignment, in order. */
function rec(): { canvas: HTMLCanvasElement; ops: Op[] } {
  const ops: Op[] = [];
  const ctx = new Proxy(
    {},
    {
      get: (_t, name: string) => {
        if (name === "createRadialGradient")
          return () => ({ addColorStop: () => undefined });
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
const names = (ops: Op[], n: string): Op[] => ops.filter((o) => o[0] === n);

const nd = (id: string, kind: string, x: number, y: number, name = id) => ({
  node_id: id,
  name,
  kind: kind as Theater["nodes"][number]["kind"],
  pos: { x_m: x, y_m: y },
});
const theater = (over: Partial<Theater> = {}): Theater =>
  ({
    nodes: [
      nd("w", "FOB", 100000, 60000, "West"),
      nd("br", "BRIDGE", 200000, 60000),
      nd("e", "FOB", 300000, 60000, "East"),
    ],
    edges: [
      { a: "w", b: "e", layer: "ROAD", bridge: "br" },
      { a: "w", b: "e", layer: "SEA_LANE", bridge: null },
    ],
    bounds_m: { w: 400000, h: 240000 },
    terrain_ref: null,
    ...over,
  }) as Theater;
const view = (id: string, over: Partial<NodeView> = {}): NodeView => ({
  node_id: id,
  owner: "NEUTRAL",
  capture: { side: null, progress_pct: 0 },
  stock_pct: null,
  starvation: null,
  hp_pct: null,
  intact: null,
  facilities: [],
  ...over,
});
const nodesOf = (...v: NodeView[]): Map<string, NodeView> =>
  new Map(v.map((x) => [x.node_id, x]));
function drawNodes(t: Theater, v: NodeView[]): Op[] {
  const { canvas, ops } = rec();
  const layer = new NodeLayer(canvas);
  layer.setTheater(t);
  ops.length = 0;
  layer.setNodes(nodesOf(...v));
  return ops;
}
const one = (): Theater =>
  theater({ nodes: [nd("n", "FOB", 1000, 1000)], edges: [] });

describe("map projector (Q-UX-18, Q-UX-19)", () => {
  const f = mapFrame({ w: 400000, h: 240000 });
  it("puts the origin bottom-left and +y north of it", () => {
    expect(f.at({ x_m: 0, y_m: 0 })).toEqual([96, 120 + 240000 * f.k]);
    expect(f.at({ x_m: 0, y_m: 240000 })).toEqual([96, 120]);
    const [x, y] = f.at({ x_m: 400000, y_m: 240000 });
    expect(x).toBeCloseTo(96 + 400000 * f.k);
    expect(y).toBe(120);
    expect(f.at({ x_m: 5, y_m: 180000 })[1]).toBeLessThan(
      f.at({ x_m: 5, y_m: 60000 })[1],
    );
  });
  it("contains a 16:9 theater and never crops, anchored top-left", () => {
    const g = mapFrame({ w: 16000, h: 9000 });
    const [x1, y1] = g.at({ x_m: 16000, y_m: 0 });
    expect(x1).toBeLessThanOrEqual(MAP_RECT.x + MAP_RECT.w + 1e-9);
    expect(y1).toBeLessThanOrEqual(MAP_RECT.y + MAP_RECT.h + 1e-9);
    expect(g.at({ x_m: 0, y_m: 9000 })).toEqual([MAP_RECT.x, MAP_RECT.y]);
    expect(g.k).toBe(Math.min(MAP_RECT.w / 16000, MAP_RECT.h / 9000));
    const wide = mapFrame({ w: 4000, h: 100 }); // width-limited: touches the right edge
    expect(wide.at({ x_m: 4000, y_m: 0 })[0]).toBeCloseTo(
      MAP_RECT.x + MAP_RECT.w,
    );
  });
  it("strait-1 bounds fit with FOB North-West above FOB South-West", () => {
    expect(f.at({ x_m: 130000, y_m: 180000 })[1]).toBeLessThan(
      f.at({ x_m: 130000, y_m: 60000 })[1],
    );
  });
});

describe("static layer", () => {
  it("draws roads solid and sea lanes dashed, once", () => {
    const { canvas, ops } = rec();
    const l = new TerrainLayer(canvas);
    l.setTheater(theater());
    expect(names(ops, "setLineDash").map((o) => o[1][0])).toEqual([
      [],
      [14, 10],
      [],
    ]);
    expect(names(ops, "stroke")).toHaveLength(2);
    ops.length = 0;
    l.setTheater(theater()); // reconnect
    l.onResize();
    expect(ops).toHaveLength(0);
    expect(l.draws).toBe(1);
  });
  it("the contour layer is empty while terrain_ref is null, and invents no relief otherwise", () => {
    const calls = (ref: string | null): Op[] => {
      const { canvas, ops } = rec();
      new TerrainLayer(canvas).setTheater(theater({ terrain_ref: ref }));
      return ops;
    };
    expect(drawContours()).toBe(0);
    expect(calls("ref")).toEqual(calls(null)); // same marks: roads only
  });
});

describe("node layer", () => {
  it("redraws only when drawn node state, the theater or the size changes", () => {
    const { canvas } = rec();
    const l = new NodeLayer(canvas);
    l.setTheater(theater());
    l.setNodes(nodesOf(view("w", { owner: "COALITION" })));
    expect(l.draws).toBe(2);
    l.setNodes(nodesOf(view("w", { owner: "COALITION" }))); // same state, new map
    l.setNodes(nodesOf(view("w", { owner: "COALITION", hp_pct: 5 }))); // not drawn
    expect(l.draws).toBe(2);
    l.setNodes(nodesOf(view("w", { owner: "ENEMY" })));
    expect(l.draws).toBe(3);
    l.setTheater(theater());
    expect(l.draws).toBe(3);
    (canvas as { width: number }).width = 1280;
    l.onResize();
    expect(l.draws).toBe(4);
  });

  it("draws a distinct glyph per node kind", () => {
    const sig = new Set<string>();
    for (const kind of Object.keys(NODE_R)) {
      const t = theater({ nodes: [nd("n", kind, 1000, 1000)], edges: [] });
      const ops = drawNodes(t, [view("n", { owner: "COALITION" })]);
      sig.add(JSON.stringify(ops.map((o) => o[0])));
    }
    expect(sig.size).toBe(6);
  });

  it("frame shape and colour follow the owner", () => {
    const t = one();
    const lineTos = (o: NodeView["owner"]): number =>
      names(drawNodes(t, [view("n", { owner: o })]), "lineTo").length;
    expect(lineTos("COALITION")).toBe(8); // chamfered octagon
    expect(lineTos("ENEMY")).toBe(16); // spiked
    expect(lineTos("NEUTRAL")).toBe(0); // dashed circle
    const neutral = drawNodes(t, [view("n", { owner: "NEUTRAL" })]);
    expect(names(neutral, "setLineDash").map((o) => o[1][0])).toContainEqual([
      6, 5,
    ]);
    const cols = (o: NodeView["owner"]): unknown[] =>
      names(drawNodes(t, [view("n", { owner: o })]), "=strokeStyle").map(
        (x) => x[1][0],
      );
    expect(cols("COALITION")).toContain("#43dcff");
    expect(cols("ENEMY")).toContain("#ff4f7b");
    expect(cols("NEUTRAL")).toContain("#d8dde2");
  });

  it("a node without a NodeView gets no owner frame", () => {
    const { canvas, ops } = rec();
    new NodeLayer(canvas).setTheater(one());
    expect(names(ops, "fill")).toHaveLength(0);
    expect(names(ops, "=strokeStyle")[0]?.[1][0]).toBe("#64748b");
  });

  it("draws the capture arc from progress in the capturing side's colour", () => {
    const cap = (side: "COALITION" | "ENEMY" | null, p: number): Op[] =>
      drawNodes(one(), [view("n", { capture: { side, progress_pct: p } })]);
    const ops = cap("ENEMY", 25);
    const arc = names(ops, "arc").at(-1) as Op; // after the frame circle
    expect((arc[1][4] as number) - (arc[1][3] as number)).toBeCloseTo(
      Math.PI / 2,
    );
    expect(names(ops, "=strokeStyle").map((o) => o[1][0])).toContain("#ff4f7b");
    const frameOnly = names(cap(null, 40), "arc").length; // the neutral frame circle
    expect(frameOnly).toBe(1);
    expect(names(cap("COALITION", 0), "arc")).toHaveLength(frameOnly);
    expect(names(cap("COALITION", 50), "arc")).toHaveLength(frameOnly + 1);
  });

  it("shows the stock bar on coalition nodes only, nothing for null", () => {
    const bar = (o: NodeView["owner"], stock: number | null): number =>
      names(
        drawNodes(one(), [
          view("n", { owner: o, stock_pct: stock, starvation: "OK" }),
        ]),
        "strokeRect",
      ).length;
    expect(bar("COALITION", 60)).toBe(1);
    expect(bar("COALITION", null)).toBe(0);
    expect(bar("ENEMY", 60)).toBe(0);
    expect(bar("NEUTRAL", 60)).toBe(0);
    const low = drawNodes(one(), [
      view("n", { owner: "COALITION", stock_pct: 10, starvation: "LOW" }),
    ]);
    expect(names(low, "fillText").map((o) => o[1][0])).toContain("LOW");
  });

  it("labels strategic kinds only, as text, hostile names included", () => {
    expect([...LABELLED].sort()).toEqual(["AIRBASE", "FOB", "PORT"]);
    const evil = "<img src=x onerror=alert(1)>";
    const t = theater({
      nodes: [
        nd("a", "FOB", 1000, 1000, evil),
        nd("h", "HQ", 5000, 1000, "HQ"),
      ],
      edges: [],
    });
    expect(names(drawNodes(t, []), "fillText").map((o) => o[1][0])).toEqual([
      evil,
    ]);
  });

  it("draws a crossbar at the bridge node, broken when the bridge is down", () => {
    const up = drawNodes(theater(), [view("br", { intact: true })]);
    const unknown = drawNodes(theater(), [view("br", { intact: null })]);
    const down = drawNodes(theater(), [view("br", { intact: false })]);
    // the crossbar is drawn last, after the node glyphs, and is the only butt-capped path
    const bar = (ops: Op[]): Op[] =>
      ops.slice(
        ops.findIndex((o) => o[0] === "=lineCap" && o[1][0] === "butt"),
      );
    expect(names(bar(up), "moveTo")).toHaveLength(1); // one solid bar
    expect(names(bar(down), "moveTo")).toHaveLength(2); // two broken stubs
    expect(bar(unknown)).toEqual(bar(up)); // null draws the normal crossbar
    expect(names(bar(down), "setLineDash")[0]?.[1][0]).toEqual([6, 5]);
    expect(names(bar(up), "setLineDash")[0]?.[1][0]).toEqual([]);
    // the bar is centred on the bridge, across the (horizontal) road
    const [bx, by] = frameOf(theater()).at({ x_m: 200000, y_m: 60000 });
    const a = names(bar(up), "moveTo")[0] as Op;
    expect(a[1][0]).toBeCloseTo(bx);
    expect(a[1][1]).toBeCloseTo(by + 30);
  });

  it("draws facility rings dashed at ring_m, null draws nothing", () => {
    const fac = (ring: number | null): NodeView["facilities"][number] => ({
      entity_id: 1,
      kind: "AIR_DEFENSE_SITE",
      variant: null,
      pos: { x_m: 100000, y_m: 60000 },
      ring_m: ring,
      state: null,
      emitting: null,
      confirmed_tick: null,
    });
    const t = theater({ nodes: [nd("w", "FOB", 100000, 60000)], edges: [] });
    const ring = drawNodes(t, [view("w", { facilities: [fac(30000)] })]);
    const arc = names(ring, "arc")[0] as Op;
    expect(arc[1][2]).toBeCloseTo(30000 * frameOf(t).k);
    expect(names(ring, "setLineDash")[0]?.[1][0]).toEqual([5, 6]);
    const none = drawNodes(t, [view("w", { facilities: [fac(null)] })]);
    const bare = drawNodes(t, [view("w")]);
    expect(names(none, "arc")).toHaveLength(names(bare, "arc").length);
    expect(names(ring, "arc")).toHaveLength(names(bare, "arc").length + 1);
  });

  it("tints owned nodes only", () => {
    const tints = (o: NodeView["owner"]): number =>
      names(drawNodes(one(), [view("n", { owner: o })]), "fillRect").length;
    expect(tints("COALITION")).toBe(2); // tint + FOB glyph
    expect(tints("NEUTRAL")).toBe(1);
  });
});
