import { build } from "vite";
import { describe, expect, it, vi } from "vitest";

const start = vi.fn(() => Promise.resolve());
const prototype = start;
vi.mock("../stage", () => ({ mountStage: vi.fn() }));

import { boot } from "../boot";

function fakeWin(hash: string): Window {
  const root = { id: "root" };
  return {
    location: { hash, pathname: "/", search: "" },
    history: { replaceState: vi.fn() },
    document: { getElementById: () => root },
  } as unknown as Window;
}

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
