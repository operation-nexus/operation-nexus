import { describe, expect, it } from "vitest";
import { TerrainLayer, type Theater } from "../terrain";
import { NodeLayer } from "../nodes";

const node = (id: string, x: number, y: number): Theater["nodes"][number] => ({
  node_id: id,
  name: id,
  kind: "FOB",
  pos: { x_m: x, y_m: y },
});
const edge = (a: string, b: string): Theater["edges"][number] => ({
  a,
  b,
  layer: "ROAD",
  bridge: null,
});

/** A canvas whose 2D context records the calls it receives. */
function recCanvas(): { canvas: HTMLCanvasElement; calls: string[] } {
  const calls: string[] = [];
  const ctx = new Proxy(
    {},
    {
      get: (_t, name: string) => () => void calls.push(name),
      set: () => true,
    },
  );
  const canvas = {
    width: 1920,
    height: 1080,
    getContext: () => ctx,
  } as unknown as HTMLCanvasElement;
  return { canvas, calls };
}

const base = (): Theater => ({
  nodes: [node("a", 0, 0), node("b", 1000, 500), node("c", 2000, 0)],
  edges: [edge("a", "b"), edge("b", "c")],
  bounds_m: { w: 4000, h: 2000 },
  terrain_ref: null,
});

describe("terrain hostile and edge inputs", () => {
  it("a height-only backing-store change redraws", () => {
    const { canvas } = recCanvas();
    const layer = new TerrainLayer(canvas);
    layer.setTheater(base());
    layer.onResize();
    expect(layer.draws).toBe(1); // nothing changed
    (canvas as { height: number }).height = 1079;
    layer.onResize();
    expect(layer.draws).toBe(2);
  });

  it("bad nodes are skipped and the rest of the map still draws", () => {
    const { canvas, calls } = recCanvas();
    const t = base();
    const bad = [
      { node_id: "n1", name: "x", kind: "FOB", pos: null },
      {
        node_id: "n2",
        name: "x",
        kind: "FOB",
        pos: { x_m: Number.NaN, y_m: 0 },
      },
      { node_id: "n3", name: "x", kind: "FOB", pos: { x_m: Infinity, y_m: 0 } },
      null,
    ] as unknown as Theater["nodes"];
    t.nodes = [...t.nodes, ...bad];
    expect(() => new TerrainLayer(canvas).setTheater(t)).not.toThrow();
    expect(calls.filter((c) => c === "stroke")).toHaveLength(2);
    const nodes = recCanvas();
    new NodeLayer(nodes.canvas).setTheater(t);
    expect(nodes.calls.filter((c) => c === "fillRect")).toHaveLength(3);
  });

  it("a theater with no node or edge arrays does not throw", () => {
    const layer = new TerrainLayer(recCanvas().canvas);
    expect(() => layer.setTheater({} as unknown as Theater)).not.toThrow();
    expect(layer.draws).toBe(1);
  });

  it("a dangling edge id does not throw and the other edges still draw", () => {
    const { canvas, calls } = recCanvas();
    const t = base();
    t.edges = [edge("a", "ghost"), edge("a", "b"), edge("b", "c")];
    expect(() => new TerrainLayer(canvas).setTheater(t)).not.toThrow();
    expect(calls.filter((c) => c === "stroke")).toHaveLength(2);
  });

  it("an edges-only change redraws", () => {
    const layer = new TerrainLayer(recCanvas().canvas);
    layer.setTheater(base());
    const t = base();
    t.edges = [edge("a", "c")];
    expect(layer.setTheater(t)).toBe(true);
    expect(layer.draws).toBe(2);
  });

  it("an empty theater does not throw", () => {
    const layer = new TerrainLayer(recCanvas().canvas);
    expect(() =>
      layer.setTheater({
        nodes: [],
        edges: [],
        bounds_m: { w: 4000, h: 2000 },
        terrain_ref: null,
      }),
    ).not.toThrow();
  });
});
