import { build } from "vite";
import { CSP } from "../../vite.config";
import { afterEach, describe, expect, it, vi } from "vitest";
import indexHtml from "../../index.html?raw";
import { MAP_RECT, backingSize, fitStage, safeRect } from "../stage-math";
import { mountStage, HEARTBEAT_CELLS } from "../stage";
import { TerrainLayer, frameOf, type Theater } from "../terrain";

// Vitest blanks .css imports (even ?raw), so CSS is read from a real production build, in memory.
interface Built {
  html: string;
  css: string;
  fonts: number;
  preloads: string[];
}
let cache: Promise<Built> | null = null;
function built(): Promise<Built> {
  cache ??= build({ logLevel: "silent", build: { write: false } }).then(
    (res) => {
      const out = (Array.isArray(res) ? res[0] : res) as unknown as {
        output: { fileName: string; source?: string | Uint8Array }[];
      };
      const text = (ext: string): string[] =>
        out.output
          .filter((o) => o.fileName.endsWith(ext))
          .map((o) => String(o.source));
      return {
        html: text(".html")[0] ?? "",
        css: text(".css").join("\n"),
        fonts: text(".woff2").length,
        preloads: [
          ...(text(".html")[0] ?? "").matchAll(
            /<link\s[^>]*rel="preload"[^>]*as="font"[^>]*type="font\/woff2"[^>]*crossorigin[^>]*href="([^"]+)"/g,
          ),
        ].map((m) => m[1] ?? ""),
      };
    },
  );
  return cache;
}

const theater = (x = 0): Theater => ({
  nodes: [
    { node_id: "a", name: "A", kind: "HQ", pos: { x_m: x, y_m: 0 } },
    { node_id: "b", name: "B", kind: "FOB", pos: { x_m: x + 4000, y_m: 2000 } },
  ],
  edges: [{ a: "a", b: "b", layer: "ROAD", bridge: null }],
  bounds_m: { w: 4000, h: 2000 },
  terrain_ref: null,
});

describe("stage math", () => {
  it("scales to the limiting axis and centers", () => {
    expect(fitStage(1920, 1080)).toEqual({ scale: 1, x: 0, y: 0 });
    expect(fitStage(1280, 720)).toEqual({ scale: 2 / 3, x: 0, y: 0 });
    const wide = fitStage(2560, 1080);
    expect(wide.scale).toBe(1);
    expect(wide.x).toBe(320);
    const tall = fitStage(1920, 1280);
    expect(tall.y).toBe(100);
  });

  it("backing store = CSS size x DPR, capped at 2", () => {
    expect(backingSize(1, 1)).toEqual({ w: 1920, h: 1080 });
    expect(backingSize(0.5, 2)).toEqual({ w: 1920, h: 1080 });
    expect(backingSize(1, 3)).toEqual({ w: 3840, h: 2160 });
    expect(backingSize(1000 / 1920, 1)).toEqual({ w: 1000, h: 563 }); // 562.5 rounds up
    expect(backingSize(1, Number.NaN)).toEqual({ w: 1920, h: 1080 });
  });

  it("safe area is 5% on each edge", () => {
    expect(safeRect()).toEqual({ x: 96, y: 54, w: 1728, h: 972 });
  });

  it("projects nodes inside the map rectangle, which is inside the safe area", () => {
    const at = frameOf(theater()).at;
    const r = MAP_RECT;
    expect(r.x).toBeGreaterThanOrEqual(safeRect().x);
    expect(r.y + r.h).toBeLessThanOrEqual(safeRect().y + safeRect().h);
    for (const n of theater().nodes) {
      const [x, y] = at(n.pos);
      expect(x).toBeGreaterThanOrEqual(r.x);
      expect(x).toBeLessThanOrEqual(r.x + r.w);
      expect(y).toBeGreaterThanOrEqual(r.y);
      expect(y).toBeLessThanOrEqual(r.y + r.h);
    }
  });
});

function fakeCanvas(): HTMLCanvasElement {
  const ctx = new Proxy({}, { get: () => () => undefined });
  return { width: 1920, height: 1080, getContext: () => ctx } as never;
}

describe("terrain layer", () => {
  it("redraws only when the theater changes", () => {
    const t = new TerrainLayer(fakeCanvas());
    expect(t.setTheater(theater())).toBe(true);
    expect(t.setTheater(theater())).toBe(false); // identical re-send (reconnect)
    expect(t.draws).toBe(1);
    expect(t.setTheater(theater(10))).toBe(true);
    expect(t.draws).toBe(2);
  });

  it("redraws on a backing-store resize, not otherwise", () => {
    const c = fakeCanvas();
    const t = new TerrainLayer(c);
    t.setTheater(theater());
    t.onResize();
    expect(t.draws).toBe(1);
    c.width = 1280;
    t.onResize();
    expect(t.draws).toBe(2);
  });
});

class FakeEl {
  children: FakeEl[] = [];
  parentElement: FakeEl | null = null;
  className = "";
  width = 0;
  height = 0;
  style: Record<string, string> = {};
  attrs: Record<string, string> = {};
  on = new Set<string>();
  constructor(readonly tag: string) {}
  appendChild(c: FakeEl): FakeEl {
    c.parentElement = this;
    this.children.push(c);
    return c;
  }
  replaceChildren(): void {
    this.children = [];
  }
  setAttribute(k: string, v: string): void {
    this.attrs[k] = v;
  }
  getContext(): unknown {
    return new Proxy({}, { get: () => () => undefined });
  }
  classList = {
    toggle: (c: string, force: boolean) => {
      if (force) this.on.add(c);
      else this.on.delete(c);
    },
  };
}

function fakeWin(w: number, h: number, dpr: number) {
  const win = {
    innerWidth: w,
    innerHeight: h,
    devicePixelRatio: dpr,
    document: { createElement: (t: string) => new FakeEl(t) },
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    setInterval: (f: () => void, ms: number) => setInterval(f, ms),
    clearInterval: (id: number) => clearInterval(id),
  };
  return win as unknown as Window;
}

describe("mountStage", () => {
  afterEach(() => vi.useRealTimers());

  it("lays out the layers back to front (OVERLAY §0.6)", async () => {
    const root = new FakeEl("div");
    const s = mountStage(root as never, fakeWin(1280, 720, 2));
    s.dispose();
    const stage = root.children[0] as FakeEl;
    expect(stage.children.map((c) => c.className)).toEqual([
      "nx-world",
      "nx-toast",
      "nx-banners",
      "nx-heartbeat",
    ]);
    const world = stage.children[0] as FakeEl;
    expect(world.children.map((c) => c.className)).toEqual([
      "nx-map",
      "nx-safe",
    ]);
    expect(world.children[0]?.children.map((c) => c.className)).toEqual([
      "nx-terrain",
      "nx-nodes",
      "nx-units",
      "nx-fx",
    ]);
    expect(world.children[1]?.children.map((c) => c.className)).toEqual([
      "nx-panels",
      "nx-sitrep",
    ]);
    const css = (await built()).css;
    const z = (cls: string): number =>
      Number(
        new RegExp(`\\.${cls}\\s*\\{[^}]*z-index:\\s*(\\d+)`).exec(css)?.[1],
      );
    const order = ["nx-world", "nx-toast", "nx-banners"].map(z);
    expect(order[0]).toBeLessThan(order[1] as number);
    expect(order[1]).toBeLessThan(order[2] as number);
    expect([z("nx-panels"), z("nx-sitrep")]).toEqual(
      [z("nx-panels"), z("nx-sitrep")].sort((a, b) => a - b),
    );
    expect(z("nx-banners")).toBeGreaterThan(z("nx-heartbeat"));
  });

  it("scales the stage and sizes the canvases by DPR (cap 2)", () => {
    const root = new FakeEl("div");
    const s = mountStage(root as never, fakeWin(1280, 720, 3));
    s.dispose();
    expect((root.children[0] as FakeEl).style["transform"]).toBe(
      `translate(0px, 0px) scale(${2 / 3})`,
    );
    expect([s.units.width, s.units.height]).toEqual([2560, 1440]);
  });

  it("the node layer redraws on a resize that changes the backing size (NX-176)", () => {
    const root = new FakeEl("div");
    const win = fakeWin(1920, 1080, 1) as unknown as {
      innerWidth: number;
      innerHeight: number;
    };
    const s = mountStage(root as never, win as unknown as Window);
    s.showTheater(theater());
    const [n0, t0] = [s.nodes.draws, s.terrain.draws];
    win.innerWidth = 960;
    win.innerHeight = 540;
    s.layout();
    expect([s.nodes.draws, s.terrain.draws]).toEqual([n0 + 1, t0 + 1]);
    s.dispose();
  });

  it("the heartbeat steps every second", () => {
    vi.useFakeTimers();
    const root = new FakeEl("div");
    const s = mountStage(root as never, fakeWin(1920, 1080, 1));
    const beat = (root.children[0] as FakeEl).children[3] as FakeEl;
    expect(HEARTBEAT_CELLS).toBe(4);
    expect(beat.children).toHaveLength(4);
    vi.advanceTimersByTime(1000);
    expect(beat.attrs["data-beat"]).toBe("1");
    expect([...(beat.children[0] as FakeEl).on]).toEqual(["on"]);
    vi.advanceTimersByTime(1000);
    expect(beat.attrs["data-beat"]).toBe("2");
    vi.advanceTimersByTime(14000); // step 16 wraps to 0
    expect(beat.attrs["data-beat"]).toBe("0");
    expect((beat.children as FakeEl[]).every((c) => c.on.size === 0)).toBe(
      true,
    );
    s.dispose();
    vi.advanceTimersByTime(5000);
    expect(beat.attrs["data-beat"]).toBe("0");
  });
});

describe("CSP and no inline styles (SEC-OV-2)", () => {
  const BAD = /\sstyle\s*=|<style|setAttribute\(\s*["']style|https?:\/\//;

  it("source has no style= / <style / remote URLs (CSS is checked in the build)", () => {
    const files = import.meta.glob<string>(
      ["../**/*.ts", "!../**/__tests__/**", "!../contracts/**"],
      { query: "?raw", import: "default", eager: true },
    );
    expect(Object.keys(files).length).toBeGreaterThan(10);
    for (const [f, txt] of Object.entries(files)) {
      expect(txt, f).not.toMatch(BAD);
    }
    expect(indexHtml).not.toMatch(BAD);
  });

  it("the built page carries the CSP and loads only local assets", async () => {
    const { html, css, fonts, preloads } = await built();
    expect(html).toContain('http-equiv="Content-Security-Policy"');
    const meta = /http-equiv="Content-Security-Policy" content="([^"]*)"/.exec(
      html,
    );
    expect(meta?.[1]).toBe(CSP);
    expect(CSP).not.toContain("unsafe");
    expect(html).not.toMatch(BAD);
    expect(css).toContain("@font-face");
    expect(css).not.toMatch(/https?:\/\/|url\(\s*["']?data:/);
    expect(fonts).toBe(2);
    // block + preload: no fallback flash on stream (OVERLAY §0.4); both hashed files are the bundled ones.
    expect(preloads).toHaveLength(2);
    expect(preloads.some((u) => u.includes("Regular"))).toBe(true);
    expect(preloads.some((u) => u.includes("Bold"))).toBe(true);
    for (const u of preloads) expect(u).toMatch(/^\/assets\/.+\.woff2$/);
  }, 30000);
});
