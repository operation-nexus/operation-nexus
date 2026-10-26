import { describe, expect, it } from "vitest";
import { CrtVectorEngine } from "../renderers/crt2d/crt-engine";
import { STRAIT_1_THEATER } from "../theater/strait1";
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
      translate: () => {},
      rotate: () => {},
      beginPath: () => {},
      moveTo: () => {},
      lineTo: () => {},
      closePath: () => {},
      arc: () => {},
      rect: () => {},
      fillRect: () => {},
      strokeRect: () => {},
      fillText: () => {},
      stroke: () => {},
      fill: () => {},
      createRadialGradient: () => ({ addColorStop: () => {} }),
      setLineDash: () => {},
      strokeStyle: "",
      fillStyle: "",
      lineWidth: 0,
      shadowColor: "",
      shadowBlur: 0,
      globalAlpha: 1,
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

describe("Option A: 2D CRT Vector Phosphor Engine", () => {
  it("initializes and handles canvas creation and resizing", async () => {
    const engine = new CrtVectorEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();

    await engine.initialize(container, { canvas });
    expect(engine.id).toBe("crt");
    expect(engine.name).toBe("2D CRT Vector Phosphor");

    engine.resize(1920, 1080, 2);
    expect(canvas.width).toBe(3840);
    expect(canvas.height).toBe(2160);

    engine.updateTheaterMap(STRAIT_1_THEATER);
  });

  it("renders frame state with dual-encoded units and radar sweep", async () => {
    const engine = new CrtVectorEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();

    await engine.initialize(container, { canvas });

    const units: VisualUnit[] = [
      {
        id: 101,
        callsign: "VIPER-01",
        side: "COALITION",
        kind: "STRIKE_FIGHTER",
        x: 120000,
        y: 60000,
        headingDeg: 90,
        speedMps: 250,
        hpPct: 100,
        damageState: "HEALTHY",
        isSelected: true,
      },
      {
        id: 201,
        callsign: "NULL-01",
        side: "ENEMY",
        kind: "ENEMY_ARMOR",
        x: 280000,
        y: 60000,
        headingDeg: 270,
        speedMps: 20,
        hpPct: 100,
        damageState: "HEALTHY",
      },
    ];

    const frameState: RenderFrameState = {
      tick: 42,
      simTime: 4200,
      units,
      telemetry: {
        momentum: { quorum: 55, static: 45 },
        countdownSeconds: 840,
        objectiveName: "SECURE STRAIT CROSSINGS",
        threatLevel: "NOMINAL",
        threatTier: "PATTERN_OF_LIFE",
        sitrep: [],
        ticker: [],
      },
    };

    expect(() => engine.renderFrame(frameState)).not.toThrow();

    engine.triggerEffect({
      type: "MISSILE_TRAJECTORY",
      id: "M-1",
      sourcePos: [90000, 120000, 2],
      targetPos: [290000, 40000, 2],
      progress: 0.5,
      peakAltitudeMeters: 5000,
      color: "#ff0055",
    });

    expect(() => engine.renderFrame(frameState)).not.toThrow();

    engine.dispose();
  });
});
