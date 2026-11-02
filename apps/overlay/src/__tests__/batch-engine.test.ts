import { describe, expect, it } from "vitest";
import { BatchSpriteEngine } from "../renderers/batch/batch-engine";
import { SimulationFeedGenerator } from "../simulation/mock-feed";
import type { RenderFrameState } from "../types/render";
import { expectFpsAtLeast } from "./perf-gate";

function createMockCanvas(): HTMLCanvasElement {
  const canvas = {
    width: 1280,
    height: 720,
    style: {},
    getContext: () => ({
      save: () => {},
      restore: () => {},
      scale: () => {},
      beginPath: () => {},
      moveTo: () => {},
      lineTo: () => {},
      closePath: () => {},
      arc: () => {},
      strokeRect: () => {},
      fillRect: () => {},
      fillText: () => {},
      stroke: () => {},
      fill: () => {},
      strokeStyle: "",
      fillStyle: "",
      lineWidth: 0,
      font: "",
    }),
  } as unknown as HTMLCanvasElement;
  return canvas;
}

function createMockContainer(): HTMLElement {
  const children: HTMLElement[] = [];
  return {
    getBoundingClientRect: () => ({
      width: 1280,
      height: 720,
      top: 0,
      left: 0,
      bottom: 720,
      right: 1280,
    }),
    appendChild: (child: HTMLElement) => {
      children.push(child);
      Object.assign(child, {
        parentElement: {
          removeChild: (c: HTMLElement) => {
            const idx = children.indexOf(c);
            if (idx !== -1) children.splice(idx, 1);
          },
        },
      });
      return child;
    },
    children,
  } as unknown as HTMLElement;
}

describe("Option D: High-Density Batch Spriting Engine", () => {
  it("initializes and renders 500+ simultaneous units at high frame budget", async () => {
    const engine = new BatchSpriteEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();
    await engine.initialize(container, { canvas });

    expect(engine.id).toBe("batch");
    expect(engine.name).toBe("High-Density Batch Spriting");

    const feed = new SimulationFeedGenerator();
    const frameState: RenderFrameState = feed.generateFrameState(true); // 500+ units mode

    const unitsList = Array.isArray(frameState.units)
      ? frameState.units
      : Array.from(frameState.units.values());
    expect(unitsList.length).toBeGreaterThanOrEqual(500);

    engine.renderFrame(frameState);

    const stats = engine.getPerformanceStats();
    expect(stats.unitCount).toBeGreaterThanOrEqual(500);
    expect(stats.batchPasses).toBeGreaterThanOrEqual(4);
    expect(stats.frameTimeMs).toBeGreaterThan(0);
    expectFpsAtLeast(stats.estimatedFps, 30);

    engine.dispose();
  });
});
