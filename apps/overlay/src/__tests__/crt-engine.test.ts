import { describe, expect, it } from "vitest";
import { CrtVectorEngine } from "../renderers/crt2d/crt-engine";
import { STRAIT_1_THEATER } from "../simulation/mock-theater";
import type { RenderFrameState } from "../types/render";
import type { VisualUnit } from "../types/unit";

interface TextCall {
  text: string;
  x: number;
  y: number;
  align: string;
}

function createMockCanvas(textCalls: TextCall[] = []): HTMLCanvasElement {
  const ctx = {
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
    fillText(text: string, x: number, y: number) {
      textCalls.push({ text, x, y, align: ctx.textAlign });
    },
    measureText: (text: string) => ({ width: text.length * 6 }),
    textAlign: "left",
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
  };
  const canvas = {
    width: 1280,
    height: 720,
    style: {},
    getContext: () => ctx,
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

  it("moves a node label under the node when it would run off the right edge", async () => {
    const engine = new CrtVectorEngine();
    const textCalls: TextCall[] = [];
    const canvas = createMockCanvas(textCalls);
    await engine.initialize(createMockContainer(), { canvas });
    engine.resize(1920, 1080, 1); // the broadcast stage size (OVERLAY §0.7)

    engine.renderFrame({
      tick: 1,
      simTime: 100,
      units: [],
      telemetry: {
        momentum: { quorum: 50, static: 50 },
        countdownSeconds: 0,
        objectiveName: "",
        threatTier: "PATTERN_OF_LIFE",
        sitrep: [],
        ticker: [],
      },
    });

    // Static Rear sits at x = 395 km of 400 km, i.e. 1896 px of 1920.
    const rear = textCalls.find((c) => c.text === "STATIC REAR");
    expect(rear).toBeDefined();
    expect(rear?.align).toBe("right");
    expect(rear?.x).toBe(1912);
    // ...and below its row, clear of the Static HQ label on the same row.
    const hq = textCalls.find((c) => c.text === "STATIC HQ");
    expect(hq?.align).toBe("left");
    expect((rear?.y ?? 0) - (hq?.y ?? 0)).toBeGreaterThanOrEqual(12);

    // Haven is near the left edge and keeps its label on the right.
    const haven = textCalls.find((c) => c.text === "HAVEN SANCTUARY");
    expect(haven?.align).toBe("left");

    engine.dispose();
  });

  it("keeps two right-edge labels on the same row apart at 1280 px", async () => {
    const engine = new CrtVectorEngine();
    const textCalls: TextCall[] = [];
    const canvas = createMockCanvas(textCalls);
    await engine.initialize(createMockContainer(), { canvas }); // 1280 × 720

    engine.renderFrame({
      tick: 1,
      simTime: 100,
      units: [],
      telemetry: {
        momentum: { quorum: 50, static: 50 },
        countdownSeconds: 0,
        objectiveName: "",
        threatTier: "PATTERN_OF_LIFE",
        sitrep: [],
        ticker: [],
      },
    });

    // At this width neither Static HQ nor Static Rear fits to the right.
    const hq = textCalls.find((c) => c.text === "STATIC HQ");
    const rear = textCalls.find((c) => c.text === "STATIC REAR");
    expect(hq?.align).toBe("right");
    expect(rear?.align).toBe("right");
    expect(Math.abs((rear?.y ?? 0) - (hq?.y ?? 0))).toBeGreaterThanOrEqual(12);

    engine.dispose();
  });
});
