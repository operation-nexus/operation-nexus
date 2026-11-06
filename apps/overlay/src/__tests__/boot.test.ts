import { build } from "vite";
import { describe, expect, it, vi } from "vitest";

const start = vi.fn(() => Promise.resolve());
const prototype = start;
const mountStage = vi.hoisted(() => vi.fn());
vi.mock("../stage", () => ({ mountStage }));
// The real startFeed opens a WebSocket; this stand-in keeps its contract: with `#token=` it mounts the stage and
// returns a client, without one it returns null.
vi.mock("../net/start", () => ({
  startFeed: vi.fn((win: Window, mount: () => unknown) => {
    if (!win.location.hash.includes("token=")) return null;
    mount();
    return {};
  }),
}));

import { boot } from "../boot";

function fakeWin(hash: string): Window {
  const root = { id: "root" };
  return {
    location: { hash, pathname: "/", search: "" },
    history: { replaceState: vi.fn() },
    document: { getElementById: () => root },
  } as unknown as Window;
}

describe("boot with a token", () => {
  it("mounts the live stage and never starts the prototype", async () => {
    start.mockClear();
    mountStage.mockClear();
    await boot(fakeWin("#token=abc"), prototype);
    expect(mountStage).toHaveBeenCalledTimes(1);
    expect(start).not.toHaveBeenCalled();
  });
});

describe("boot without a token", () => {
  it("production: renders nothing and never starts the mock feed", async () => {
    start.mockClear();
    await boot(fakeWin(""), null);
    expect(start).not.toHaveBeenCalled();
  });

  it("dev: the prototype mock feed is still available", async () => {
    start.mockClear();
    await boot(fakeWin(""), prototype);
    expect(start).toHaveBeenCalledTimes(1);
  });

  it("the production bundle contains no mock feed", async () => {
    // Vite derives DEV from NODE_ENV, which vitest sets to "test"; a real `vite build` runs as "production".
    vi.stubEnv("NODE_ENV", "production");
    const res = await build({
      logLevel: "silent",
      mode: "production",
      build: { write: false },
    });
    vi.unstubAllEnvs();
    const out = (Array.isArray(res) ? res[0] : res) as unknown as {
      output: { type: string; code?: string }[];
    };
    const js = out.output
      .filter((o) => o.type === "chunk")
      .map((o) => o.code ?? "")
      .join("\n");
    expect(js.length).toBeGreaterThan(0);
    expect(js).not.toContain("SimulationFeedGenerator");
    expect(js).not.toContain("VIPER-01");
  }, 60_000);
});
