import { describe, expect, it } from "vitest";
import { FlirMfdEngine } from "../renderers/flir/flir-engine";
import type { RenderFrameState } from "../types/render";
import type { VisualUnit } from "../types/unit";

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
      createRadialGradient: () => ({ addColorStop: () => {} }),
      strokeStyle: "",
      fillStyle: "",
      lineWidth: 0,
      font: "",
      textAlign: "",
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

describe("Option C: FLIR / MFD Cockpit Sensor Engine", () => {
  it("initializes and allows toggling thermal polarity", async () => {
    const engine = new FlirMfdEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();

    await engine.initialize(container, { canvas });
    expect(engine.id).toBe("flir");
    expect(engine.name).toBe("FLIR / MFD Cockpit Sensor");

    expect(engine.getPolarity()).toBe("WHITE_HOT");
    engine.setPolarity("BLACK_HOT");
    expect(engine.getPolarity()).toBe("BLACK_HOT");
  });

  it("renders collimated pitch ladder, compass ribbon, and thermal PiP", async () => {
    const engine = new FlirMfdEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();
    await engine.initialize(container, { canvas });

    const units: VisualUnit[] = [
      {
        id: 101,
        callsign: "VIPER-01",
        side: "COALITION",
        kind: "STRIKE_FIGHTER",
        x: 100000,
        y: 60000,
        headingDeg: 135,
        speedMps: 260,
        hpPct: 100,
        damageState: "HEALTHY",
      },
      {
        id: 201,
        callsign: "NULL-01",
        side: "ENEMY",
        kind: "ENEMY_ARMOR",
        x: 200000,
        y: 60000,
        headingDeg: 270,
        speedMps: 20,
        hpPct: 100,
        damageState: "HEALTHY",
      },
    ];

    const frameState: RenderFrameState = {
      tick: 10,
      simTime: 1000,
      units,
      telemetry: {
        momentum: { quorum: 55, static: 45 },
        countdownSeconds: 850,
        objectiveName: "TEST",
        threatLevel: "ELEVATED",
        threatTier: "CONDITION_ALPHA",
        sitrep: [],
        ticker: [],
      },
    };

    engine.setCameraTarget({ mode: "UNIT", unitId: 201 });
    expect(() => engine.renderFrame(frameState)).not.toThrow();

    engine.triggerEffect({
      type: "SCANLINE_GLITCH",
      intensity: 0.5,
      durationMs: 200,
    });

    engine.dispose();
  });
});
