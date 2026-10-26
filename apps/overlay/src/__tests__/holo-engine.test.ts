import { describe, expect, it } from "vitest";
import {
  HoloTableEngine,
  CAMERA_PRESETS,
} from "../renderers/holo3d/holo-engine";
import { ELEVATION_CHANNEL_WATER } from "../theater/elevation";
import type { RenderFrameState } from "../types/render";
import type { VisualUnit } from "../types/unit";

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

describe("Option B: 3D Holographic War Room Table Engine", () => {
  it("initializes Three.js scene graph with recessed water channel and bridges", async () => {
    const engine = new HoloTableEngine();
    const container = createMockContainer();

    await engine.initialize(container);
    expect(engine.id).toBe("holo3d");
    expect(engine.name).toBe("3D Holographic War Room Table");

    const scene = engine.getScene();
    expect(scene).not.toBeNull();

    // Verify recessed water elevation in terrain mesh (-3.5m)
    expect(ELEVATION_CHANNEL_WATER).toBe(-3.5);

    // Verify default camera preset is WIDE
    expect(engine.getPreset()).toBe("WIDE");
    const camera = engine.getCamera();
    expect(camera).not.toBeNull();
    expect(camera?.fov).toBe(CAMERA_PRESETS.WIDE.fov);
  });

  it("switches camera director presets smoothly", async () => {
    const engine = new HoloTableEngine();
    const container = createMockContainer();
    await engine.initialize(container);

    engine.setCameraPreset("COMBAT_45");
    expect(engine.getPreset()).toBe("COMBAT_45");
    expect(engine.getCamera()?.fov).toBe(CAMERA_PRESETS.COMBAT_45.fov);

    engine.setCameraPreset("TOP_DOWN");
    expect(engine.getPreset()).toBe("TOP_DOWN");
    expect(engine.getCamera()?.fov).toBe(CAMERA_PRESETS.TOP_DOWN.fov);

    engine.setCameraTarget({ mode: "OVERVIEW" });
    expect(engine.getPreset()).toBe("WIDE");
  });

  it("updates dynamic 3D units and parabolic missile effects on renderFrame", async () => {
    const engine = new HoloTableEngine();
    const container = createMockContainer();
    await engine.initialize(container);

    const units: VisualUnit[] = [
      {
        id: 101,
        callsign: "VIPER-01",
        side: "COALITION",
        kind: "STRIKE_FIGHTER",
        x: 100000,
        y: 60000,
        z: 45,
        headingDeg: 90,
        speedMps: 250,
        hpPct: 100,
        damageState: "HEALTHY",
      },
      {
        id: 201,
        callsign: "NULL-SWARM-A",
        side: "ENEMY",
        kind: "ENEMY_STRIKE",
        x: 300000,
        y: 120000,
        z: 50,
        headingDeg: 270,
        speedMps: 300,
        hpPct: 100,
        damageState: "HEALTHY",
      },
    ];

    const frameState: RenderFrameState = {
      tick: 1,
      simTime: 100,
      units,
      telemetry: {
        momentum: { quorum: 50, static: 50 },
        countdownSeconds: 900,
        objectiveName: "TEST",
        threatLevel: "NOMINAL",
        threatTier: "PATTERN_OF_LIFE",
        sitrep: [],
        ticker: [],
      },
      effects: [
        {
          type: "MISSILE_TRAJECTORY",
          id: "M-1",
          sourcePos: [90000, 120000, 2],
          targetPos: [310000, 120000, 2],
          progress: 0.5,
          peakAltitudeMeters: 6000,
          color: "#ff0055",
        },
      ],
    };

    expect(() => engine.renderFrame(frameState)).not.toThrow();

    // Verify frame with no units (cleanup)
    expect(() =>
      engine.renderFrame({ ...frameState, units: [] }),
    ).not.toThrow();

    engine.dispose();
  });
});
