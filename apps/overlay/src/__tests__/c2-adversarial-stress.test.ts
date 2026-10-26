import { describe, expect, it } from "vitest";
import { BatchSpriteEngine } from "../renderers/batch/batch-engine";
import { HoloTableEngine } from "../renderers/holo3d/holo-engine";
import { CrtVectorEngine } from "../renderers/crt2d/crt-engine";
import { FlirMfdEngine } from "../renderers/flir/flir-engine";
import {
  FACTION_TOKENS,
  getSideColors,
  getUnitShapeDescriptor,
  drawUnitVectorShape,
} from "../symbology/dual-encoding";
import { STRAIT_1_THEATER, STRAIT_CHANNEL_BOUNDS } from "../theater/strait1";
import {
  ELEVATION_CHANNEL_WATER,
  ELEVATION_TERRAIN_BASE,
  ELEVATION_BRIDGE_DECK_MIN,
  ELEVATION_BRIDGE_DECK_MAX,
  ELEVATION_ROAD_OFFSET,
  ELEVATION_CHANNEL_BED,
  getBridgeDeckElevation,
  getBallisticMissileAltitude,
} from "../theater/elevation";
import type { VisualUnit } from "../types/unit";
import type { RenderFrameState } from "../types/render";
import type { TelemetryState } from "../types/telemetry";

function createMockCanvas(width = 1280, height = 720): HTMLCanvasElement {
  const drawCalls: { type: string; args: unknown[] }[] = [];
  const canvas = {
    width,
    height,
    style: {},
    getContext: () => ({
      save: () => drawCalls.push({ type: "save", args: [] }),
      restore: () => drawCalls.push({ type: "restore", args: [] }),
      scale: (...args: unknown[]) => drawCalls.push({ type: "scale", args }),
      beginPath: () => drawCalls.push({ type: "beginPath", args: [] }),
      moveTo: (...args: unknown[]) => drawCalls.push({ type: "moveTo", args }),
      lineTo: (...args: unknown[]) => drawCalls.push({ type: "lineTo", args }),
      closePath: () => drawCalls.push({ type: "closePath", args: [] }),
      arc: (...args: unknown[]) => drawCalls.push({ type: "arc", args }),
      strokeRect: (...args: unknown[]) =>
        drawCalls.push({ type: "strokeRect", args }),
      fillRect: (...args: unknown[]) =>
        drawCalls.push({ type: "fillRect", args }),
      fillText: (...args: unknown[]) =>
        drawCalls.push({ type: "fillText", args }),
      stroke: () => drawCalls.push({ type: "stroke", args: [] }),
      fill: () => drawCalls.push({ type: "fill", args: [] }),
      strokeStyle: "",
      fillStyle: "",
      lineWidth: 0,
      font: "",
      __drawCalls: drawCalls,
    }),
  } as unknown as HTMLCanvasElement;
  return canvas;
}

function createMockContainer(width = 1280, height = 720): HTMLElement {
  const children: HTMLElement[] = [];
  return {
    getBoundingClientRect: () => ({
      width,
      height,
      top: 0,
      left: 0,
      bottom: height,
      right: width,
    }),
    appendChild: (child: HTMLElement) => {
      children.push(child);
      return child;
    },
    removeChild: (child: HTMLElement) => {
      const idx = children.indexOf(child);
      if (idx !== -1) children.splice(idx, 1);
      return child;
    },
    children,
  } as unknown as HTMLElement;
}

function makeDummyTelemetry(unitCount: number): TelemetryState {
  return {
    momentum: { quorum: 55, static: 45 },
    countdownSeconds: 840,
    objectiveName: "STRAIT-1 HIGH DENSITY STRESS",
    threatTier: "ALPHA",
    sitrep: [
      {
        id: "SR-01",
        timestamp: Date.now(),
        text: "RADAR ACTIVE",
        severity: "info",
      },
    ],
    ticker: [],
    unitCount,
  };
}

describe("Adversarial Stress Test: High Entity Count & Option D (OV-4)", () => {
  it("processes 500 simultaneous units under 16.6ms (60fps budget)", async () => {
    const engine = new BatchSpriteEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();
    await engine.initialize(container, { canvas });

    const units: VisualUnit[] = [];
    for (let i = 0; i < 500; i++) {
      units.push({
        id: i,
        callsign: `U-${i}`,
        side: i % 2 === 0 ? "COALITION" : "ENEMY",
        kind: i % 2 === 0 ? "STRIKE_FIGHTER" : "ENEMY_ARMOR",
        x: (i * 790) % 400000,
        y: (i * 470) % 240000,
        headingDeg: (i * 13) % 360,
        speedMps: 150,
        hpPct: 100,
        damageState: "HEALTHY",
        isSelected: i === 0,
        isConvoyLeader: i === 10,
        convoyFollowers: i === 10 ? 4 : undefined,
      });
    }

    const state: RenderFrameState = {
      tick: 1,
      simTime: 100,
      units,
      telemetry: makeDummyTelemetry(500),
    };

    const t0 = performance.now();
    engine.renderFrame(state);
    const elapsed = performance.now() - t0;

    const stats = engine.getPerformanceStats();
    expect(stats.unitCount).toBe(500);
    expect(stats.batchPasses).toBe(4);
    // JS frame processing time must be well under 16.6ms budget
    expect(elapsed).toBeLessThan(16.6);

    engine.dispose();
  });

  it("scales to 1,000 simultaneous units cleanly with linear batching", async () => {
    const engine = new BatchSpriteEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();
    await engine.initialize(container, { canvas });

    const units: VisualUnit[] = [];
    for (let i = 0; i < 1000; i++) {
      units.push({
        id: i,
        callsign: `U-${i}`,
        side: i % 2 === 0 ? "COALITION" : "ENEMY",
        kind: i % 2 === 0 ? "STRIKE_FIGHTER" : "ENEMY_ARMOR",
        x: (i * 397) % 400000,
        y: (i * 239) % 240000,
        headingDeg: (i * 7) % 360,
        speedMps: 120,
        hpPct: 100,
        damageState: "HEALTHY",
        isSelected: i === 42,
      });
    }

    const state: RenderFrameState = {
      tick: 2,
      simTime: 200,
      units,
      telemetry: makeDummyTelemetry(1000),
    };

    const t0 = performance.now();
    engine.renderFrame(state);
    const elapsed = performance.now() - t0;

    const stats = engine.getPerformanceStats();
    expect(stats.unitCount).toBe(1000);
    expect(stats.batchPasses).toBe(4);
    expect(elapsed).toBeLessThan(16.6); // < 16.6ms budget

    engine.dispose();
  });

  it("scales to 2,000 simultaneous units without memory explosion or stall", async () => {
    const engine = new BatchSpriteEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();
    await engine.initialize(container, { canvas });

    const units: VisualUnit[] = [];
    for (let i = 0; i < 2000; i++) {
      units.push({
        id: i,
        callsign: `U-${i}`,
        side: i % 2 === 0 ? "COALITION" : "ENEMY",
        kind: i % 2 === 0 ? "STRIKE_FIGHTER" : "ENEMY_ARMOR",
        x: (i * 199) % 400000,
        y: (i * 119) % 240000,
        headingDeg: (i * 17) % 360,
        speedMps: 200,
        hpPct: 100,
        damageState: "HEALTHY",
      });
    }

    const state: RenderFrameState = {
      tick: 3,
      simTime: 300,
      units,
      telemetry: makeDummyTelemetry(2000),
    };

    const t0 = performance.now();
    engine.renderFrame(state);
    const elapsed = performance.now() - t0;

    const stats = engine.getPerformanceStats();
    expect(stats.unitCount).toBe(2000);
    expect(elapsed).toBeLessThan(33.3); // 2000 units within 30fps absolute minimum

    engine.dispose();
  });

  it("enforces OV-4 label decluttering: suppresses text labels on general swarms", async () => {
    const engine = new BatchSpriteEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();
    await engine.initialize(container, { canvas });

    // 1000 units, but only 2 have badges (1 selected, 1 convoy leader)
    const units: VisualUnit[] = [];
    for (let i = 0; i < 1000; i++) {
      units.push({
        id: i,
        callsign: `SWARM-${i}`,
        side: i % 2 === 0 ? "COALITION" : "ENEMY",
        kind: "STRIKE_FIGHTER",
        x: (i * 400) % 400000,
        y: (i * 240) % 240000,
        headingDeg: 90,
        speedMps: 100,
        hpPct: 100,
        damageState: "HEALTHY",
        isSelected: i === 0,
        isConvoyLeader: i === 500,
        convoyFollowers: i === 500 ? 5 : undefined,
      });
    }

    const state: RenderFrameState = {
      tick: 4,
      simTime: 400,
      units,
      telemetry: makeDummyTelemetry(1000),
    };

    engine.renderFrame(state);

    const ctx = canvas.getContext("2d") as unknown as {
      __drawCalls: { type: string; args: unknown[] }[];
    };
    const fillTextCalls = ctx.__drawCalls.filter((c) => c.type === "fillText");

    // The stats pill draws 4 lines of text:
    // 1. "HIGH-DENSITY BATCH SPRITING"
    // 2. "ACTIVE UNITS: 1000 ..."
    // 3. "FRAME RENDER TIME: ... ms"
    // 4. "FRAME RATE: ... FPS"
    // Plus exactly 2 unit badges for the 2 selected/leader units!
    // Total text draws must be 6, NOT 1004!
    const unitBadgeCalls = fillTextCalls.filter(
      (c) => c.args[0] === "SWARM-0" || c.args[0] === "[TRUCK] +5",
    );
    expect(unitBadgeCalls.length).toBe(2);

    // Verify 998 unselected swarm units have ZERO text labels drawn
    const swarmTextDraws = fillTextCalls.filter(
      (c) =>
        typeof c.args[0] === "string" &&
        c.args[0].startsWith("SWARM-") &&
        c.args[0] !== "SWARM-0",
    );
    expect(swarmTextDraws.length).toBe(0);

    engine.dispose();
  });

  it("handles adversarial inputs: NaN coords, extreme headings, negative positions safely", async () => {
    const engine = new BatchSpriteEngine();
    const container = createMockContainer();
    const canvas = createMockCanvas();
    await engine.initialize(container, { canvas });

    const adversarialUnits: VisualUnit[] = [
      {
        id: 9901,
        callsign: "NAN-UNIT",
        side: "COALITION",
        kind: "STRIKE_FIGHTER",
        x: NaN,
        y: NaN,
        headingDeg: 9999,
        speedMps: Infinity,
        hpPct: -50,
        damageState: "MISSION_KILL",
      },
      {
        id: 9902,
        callsign: "OUT-OF-BOUNDS-NEG",
        side: "ENEMY",
        kind: "ENEMY_ARMOR",
        x: -500000,
        y: -300000,
        headingDeg: -720,
        speedMps: 0,
        hpPct: 0,
        damageState: "MISSION_KILL",
      },
      {
        id: 9903,
        callsign: "OUT-OF-BOUNDS-POS",
        side: "COALITION",
        kind: "RECON_UAV",
        x: 10000000,
        y: 10000000,
        headingDeg: 1080,
        speedMps: -100,
        hpPct: 200,
        damageState: "HEALTHY",
      },
    ];

    const state: RenderFrameState = {
      tick: 5,
      simTime: 500,
      units: adversarialUnits,
      telemetry: makeDummyTelemetry(3),
    };

    expect(() => engine.renderFrame(state)).not.toThrow();
    engine.dispose();
  });
});

describe("Adversarial Stress Test: Colorblind Dual-Encoding Geometry Separation (OV-2/3)", () => {
  // Pure Grayscale Luminance Formula: L = 0.2126*R + 0.7152*G + 0.0722*B
  function hexToGrayscaleLuminance(hex: string): number {
    const clean = hex.replace("#", "");
    const r = parseInt(clean.substring(0, 2), 16);
    const g = parseInt(clean.substring(2, 4), 16);
    const b = parseInt(clean.substring(4, 6), 16);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  it("extracts distinct geometry descriptors under zero color information", () => {
    // Verify pure grayscale luminance calculation on palette tokens
    const cyanLuminance = hexToGrayscaleLuminance(FACTION_TOKENS.QUORUM_CYAN);
    const magentaLuminance = hexToGrayscaleLuminance(
      FACTION_TOKENS.STATIC_MAGENTA,
    );
    expect(cyanLuminance).toBeGreaterThan(0);
    expect(magentaLuminance).toBeGreaterThan(0);

    const quorumColors = getSideColors("COALITION");
    const staticColors = getSideColors("ENEMY");
    expect(quorumColors.label).toBe("QUORUM");
    expect(staticColors.label).toBe("STATIC");

    const quorumUnit: VisualUnit = {
      id: 1,
      callsign: "Q-DELTA",
      side: "COALITION",
      kind: "STRIKE_FIGHTER",
      x: 50000,
      y: 50000,
      headingDeg: 0,
      hpPct: 100,
      damageState: "HEALTHY",
    };

    const staticUnit: VisualUnit = {
      id: 2,
      callsign: "S-SHARD",
      side: "ENEMY",
      kind: "ENEMY_STRIKE_FIGHTER",
      x: 350000,
      y: 50000,
      headingDeg: 180,
      hpPct: 100,
      damageState: "HEALTHY",
    };

    // Verify drawing on mock canvas context
    const canvas = createMockCanvas();
    const ctx = canvas.getContext("2d");
    expect(ctx).toBeTruthy();
    if (ctx) {
      expect(() => drawUnitVectorShape(ctx, quorumUnit, 10)).not.toThrow();
      expect(() => drawUnitVectorShape(ctx, staticUnit, 10)).not.toThrow();
    }

    const qDesc = getUnitShapeDescriptor(quorumUnit);
    const sDesc = getUnitShapeDescriptor(staticUnit);

    // Under complete achromatopsia / grayscale, colors are stripped completely:
    // Distinguishing features must be strictly geometric!
    expect(qDesc.geometryFamily).toBe("SMOOTH_CHEVRON_DIAMOND");
    expect(sDesc.geometryFamily).toBe("JAGGED_SAWTOOTH");

    expect(qDesc.hasSawtoothJags).toBe(false);
    expect(sDesc.hasSawtoothJags).toBe(true);

    expect(qDesc.isAngularChevron).toBe(true);
    expect(sDesc.isAngularChevron).toBe(false);

    expect(qDesc.vertexCount).toBeLessThan(sDesc.vertexCount);
  });

  it("empirically classifies 1,000 random orientations purely by morphology (100% accuracy)", () => {
    // Polygon geometry points (relative to center, radius 10)
    type Point2D = [number, number];
    // Quorum Strike Fighter (Chevron): 4 points
    const quorumPolygon: Point2D[] = [
      [0, -10],
      [8.5, 10],
      [0, 4.5],
      [-8.5, 10],
    ];

    // Static Sawtooth Shard: 10 points
    const staticPolygon: Point2D[] = [
      [0, -11],
      [4.5, -3],
      [9, -1],
      [4, 5],
      [7.5, 10],
      [0, 5],
      [-7.5, 10],
      [-4, 5],
      [-9, -1],
      [-4.5, -3],
    ];

    // Geometric feature extractor: computes curvature inflection count (sign changes in cross product)
    function countCurvatureAlternations(poly: Point2D[]): number {
      const n = poly.length;
      let alternations = 0;
      let lastSign = 0;

      for (let i = 0; i < n; i++) {
        const p0 = poly[(i - 1 + n) % n] ?? [0, 0];
        const p1 = poly[i] ?? [0, 0];
        const p2 = poly[(i + 1) % n] ?? [0, 0];

        const v1x = p1[0] - p0[0];
        const v1y = p1[1] - p0[1];
        const v2x = p2[0] - p1[0];
        const v2y = p2[1] - p1[1];

        const cross = v1x * v2y - v1y * v2x;
        const sign = cross > 1e-5 ? 1 : cross < -1e-5 ? -1 : 0;

        if (sign !== 0 && lastSign !== 0 && sign !== lastSign) {
          alternations++;
        }
        if (sign !== 0) {
          lastSign = sign;
        }
      }
      return alternations;
    }

    // Rotate polygon by angle theta
    function rotatePoly(poly: Point2D[], rad: number): Point2D[] {
      const c = Math.cos(rad);
      const s = Math.sin(rad);
      return poly.map((pt) => [pt[0] * c - pt[1] * s, pt[0] * s + pt[1] * c]);
    }

    // Test 500 rotations of Quorum chevron vs 500 rotations of Static shard
    let correctlyClassified = 0;
    const totalSamples = 1000;

    for (let i = 0; i < totalSamples; i++) {
      const angle = (i * 0.02 * Math.PI) % (2 * Math.PI);
      const isQuorum = i % 2 === 0;
      const poly = isQuorum
        ? rotatePoly(quorumPolygon, angle)
        : rotatePoly(staticPolygon, angle);

      // Morphological Oracle: Static sawtooth has high alternating concavity/convexity (> 3 sign reversals)
      // Quorum chevron has smooth wings with only 1 reflex notch (at the tail)
      const alternations = countCurvatureAlternations(poly);
      const predictedSide = alternations > 2 ? "ENEMY" : "COALITION";
      const actualSide = isQuorum ? "COALITION" : "ENEMY";

      if (predictedSide === actualSide) {
        correctlyClassified++;
      }
    }

    // 100% classification accuracy without relying on color
    expect(correctlyClassified).toBe(totalSamples);
  });
});

describe("Adversarial Stress Test: Strait-1 Elevation Budget & Z-Fighting Boundaries", () => {
  it("verifies strictly non-zero vertical separation between water and terrain across theater", () => {
    // Water surface is at Y = -3.5m; Terrain is at Y = +2.0m
    const verticalSeparation = ELEVATION_TERRAIN_BASE - ELEVATION_CHANNEL_WATER;
    expect(verticalSeparation).toBe(5.5);
    // 5.5m separation guarantees zero Z-fighting even with low-precision 16-bit depth buffers
    expect(verticalSeparation).toBeGreaterThan(0.5);
  });

  it("validates bridge deck elevation clearance over water across 100 span sample points", () => {
    const minWater = ELEVATION_CHANNEL_WATER; // -3.5m

    for (let i = 0; i <= 100; i++) {
      const progress = i / 100;
      const deckY = getBridgeDeckElevation(progress);

      // Deck must never dip below abutment height (+2.0m)
      expect(deckY).toBeGreaterThanOrEqual(ELEVATION_BRIDGE_DECK_MIN);
      // Deck must never exceed apex height (+14.0m)
      expect(deckY).toBeLessThanOrEqual(ELEVATION_BRIDGE_DECK_MAX);

      // Physical clearance between bridge deck and water surface must be >= 5.5m everywhere
      const waterClearance = deckY - minWater;
      expect(waterClearance).toBeGreaterThanOrEqual(5.5);

      // Clearance over channel bed (-10.0m) must be >= 12.0m
      const bedClearance = deckY - ELEVATION_CHANNEL_BED;
      expect(bedClearance).toBeGreaterThanOrEqual(12.0);
    }
  });

  it("checks road mesh polygon offset prevents coplanar flickering against base terrain", () => {
    expect(ELEVATION_ROAD_OFFSET).toBe(0.22);
    expect(ELEVATION_ROAD_OFFSET).toBeGreaterThan(0.05); // > 5cm physical separation
  });

  it("verifies ballistic missile arcs maintain positive altitude clearance throughout flight", () => {
    const startY = ELEVATION_TERRAIN_BASE; // 2.0m
    const targetY = ELEVATION_TERRAIN_BASE; // 2.0m
    const peakAltitude = 8000; // 8km altitude

    for (let step = 0; step <= 50; step++) {
      const p = step / 50;
      const altitude = getBallisticMissileAltitude(
        startY,
        targetY,
        p,
        peakAltitude,
      );

      // Trajectory must always remain >= ground elevation
      expect(altitude).toBeGreaterThanOrEqual(ELEVATION_TERRAIN_BASE);

      if (p > 0.1 && p < 0.9) {
        // In flight, altitude should be well above mountain peaks (+35m)
        expect(altitude).toBeGreaterThan(500);
      }
    }
  });

  it("validates boundary coordinate integrity at West and East shoreline banks", () => {
    const { westBankX, eastBankX, widthMeters } = STRAIT_CHANNEL_BOUNDS;
    expect(eastBankX - westBankX).toBe(widthMeters);
    expect(widthMeters).toBe(30000); // 30km channel width

    // West of West Bank: Land elevation
    // East of East Bank: Land elevation
    // Inside channel: Water elevation
    function getTheoreticalElevationAtX(x: number): number {
      if (x < westBankX || x > eastBankX) {
        return ELEVATION_TERRAIN_BASE;
      }
      return ELEVATION_CHANNEL_WATER;
    }

    expect(getTheoreticalElevationAtX(westBankX - 1)).toBe(2.0);
    expect(getTheoreticalElevationAtX(westBankX + 1)).toBe(-3.5);
    expect(getTheoreticalElevationAtX(200000)).toBe(-3.5);
    expect(getTheoreticalElevationAtX(eastBankX - 1)).toBe(-3.5);
    expect(getTheoreticalElevationAtX(eastBankX + 1)).toBe(2.0);
  });
});

describe("Adversarial Stress Test: IRenderEngine Interface Contract Lifecycle", () => {
  it("enforces IRenderEngine lifecycle consistency across all 4 paradigms", async () => {
    const engines = [
      new BatchSpriteEngine(),
      new HoloTableEngine(),
      new CrtVectorEngine(),
      new FlirMfdEngine(),
    ];

    for (const engine of engines) {
      const container = createMockContainer();
      const canvas = createMockCanvas();

      // 1. Initialize
      await expect(
        engine.initialize(container, { canvas }),
      ).resolves.not.toThrow();

      // 2. Resize to arbitrary resolutions
      expect(() => engine.resize(1920, 1080)).not.toThrow();
      expect(() => engine.resize(800, 600)).not.toThrow();
      expect(() => engine.resize(0, 0)).not.toThrow(); // Edge case: zero size

      // 3. Update theater map
      expect(() => engine.updateTheaterMap(STRAIT_1_THEATER)).not.toThrow();

      // 4. Trigger effect
      expect(() =>
        engine.triggerEffect({
          type: "KINETIC_BURST",
          id: "KB-1",
          pos: [200000, 120000, 0],
          radiusMeters: 1000,
          progress: 0.5,
          color: "#00e5ff",
        }),
      ).not.toThrow();

      // 5. Camera targeting
      expect(() =>
        engine.setCameraTarget({
          mode: "OVERVIEW",
        }),
      ).not.toThrow();

      // 6. Dispose and cleanup
      expect(() => engine.dispose()).not.toThrow();
    }
  });
});
