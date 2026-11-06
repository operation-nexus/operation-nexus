import { describe, expect, it } from "vitest";
import {
  STRAIT_1_THEATER,
  STRAIT_CHANNEL_BOUNDS,
} from "../simulation/mock-theater";
import {
  ELEVATION_CHANNEL_WATER,
  ELEVATION_TERRAIN_BASE,
  ELEVATION_BRIDGE_DECK_MIN,
  ELEVATION_BRIDGE_DECK_MAX,
  getBridgeDeckElevation,
  getBallisticMissileAltitude,
} from "../theater/elevation";

describe("Strait-1 mock Theater & Physical Elevation Budget", () => {
  it("conforms to authoritative Strait-1 theater dimensions (400km x 240km)", () => {
    expect(STRAIT_1_THEATER.slug).toBe("strait-1");
    expect(STRAIT_1_THEATER.boundsM.w).toBe(400000);
    expect(STRAIT_1_THEATER.boundsM.h).toBe(240000);
  });

  it("partitions theater into North, Centre, and South sectors", () => {
    expect(STRAIT_1_THEATER.sectors.length).toBe(3);
    const sectorIds = STRAIT_1_THEATER.sectors.map((s) => s.id);
    expect(sectorIds).toContain("north");
    expect(sectorIds).toContain("centre");
    expect(sectorIds).toContain("south");

    const northSector = STRAIT_1_THEATER.sectors.find((s) => s.id === "north");
    expect(northSector?.polygon[2]?.[1]).toBe(160000); // +y is north: 160 to 240 km
  });

  it("defines radar masking regions in northern hills and southern valley", () => {
    expect(STRAIT_1_THEATER.maskingRegions.length).toBe(2);
    const regionIds = STRAIT_1_THEATER.maskingRegions.map((m) => m.id);
    expect(regionIds).toContain("northern-hills");
    expect(regionIds).toContain("southern-valley");
  });

  it("enforces recessed water channel elevation to eliminate Z-fighting", () => {
    expect(ELEVATION_CHANNEL_WATER).toBe(-3.5);
    expect(ELEVATION_TERRAIN_BASE).toBe(2.0);
    expect(STRAIT_CHANNEL_BOUNDS.elevationWaterMeters).toBe(-3.5);
    expect(STRAIT_CHANNEL_BOUNDS.westBankX).toBe(185000);
    expect(STRAIT_CHANNEL_BOUNDS.eastBankX).toBe(215000);
    expect(STRAIT_CHANNEL_BOUNDS.widthMeters).toBe(30000);
  });

  it("models elevated highway bridges rising +2m to +14m over water", () => {
    expect(ELEVATION_BRIDGE_DECK_MIN).toBe(2.0);
    expect(ELEVATION_BRIDGE_DECK_MAX).toBe(14.0);

    // Abutment ends (progress = 0 and 1) should be at base height +2.0m
    expect(getBridgeDeckElevation(0.0)).toBe(2.0);
    expect(getBridgeDeckElevation(1.0)).toBe(2.0);

    // Mid-span apex (progress = 0.5) should reach maximum clearance +14.0m
    expect(getBridgeDeckElevation(0.5)).toBe(14.0);

    // Quarter-span should be between +2m and +14m
    const quarter = getBridgeDeckElevation(0.25);
    expect(quarter).toBeGreaterThan(2.0);
    expect(quarter).toBeLessThan(14.0);
  });

  it("calculates 3D parabolic ballistic missile trajectories accurately", () => {
    const startY = 2;
    const targetY = 2;
    const peak = 50;

    // At launch (progress 0)
    expect(getBallisticMissileAltitude(startY, targetY, 0, peak)).toBe(2);

    // At apex (progress 0.5): baseline 2 + peak 50 = 52
    expect(getBallisticMissileAltitude(startY, targetY, 0.5, peak)).toBeCloseTo(
      52,
    );

    // At impact (progress 1.0)
    expect(getBallisticMissileAltitude(startY, targetY, 1.0, peak)).toBeCloseTo(
      2,
    );
  });

  it("contains all authoritative bases, bridges, and sanctuary nodes", () => {
    const nodeMap = new Map(STRAIT_1_THEATER.nodes.map((n) => [n.id, n]));

    expect(nodeMap.get("haven")?.pos).toEqual([20000, 120000]);
    expect(nodeMap.get("west-airbase")?.pos).toEqual([90000, 120000]);
    expect(nodeMap.get("bridge-n")?.pos).toEqual([200000, 180000]);
    expect(nodeMap.get("bridge-s")?.pos).toEqual([200000, 60000]);
    expect(nodeMap.get("cross-n")?.pos).toEqual([230000, 180000]);
    expect(nodeMap.get("cross-s")?.pos).toEqual([230000, 60000]);
    expect(nodeMap.get("east-airbase")?.pos).toEqual([310000, 120000]);
    expect(nodeMap.get("static-hq")?.pos).toEqual([380000, 120000]);
    expect(nodeMap.get("static-rear")?.pos).toEqual([395000, 120000]);
  });
});

describe("retired y-south strait1.ts", () => {
  it("no source file imports it, and the file is gone", () => {
    const files = import.meta.glob("../**/*.ts", {
      query: "?raw",
      import: "default",
      eager: true,
    }) as Record<string, string>;
    expect(Object.keys(files).some((f) => f.endsWith("/strait1.ts"))).toBe(
      false,
    );
    const needle = ["theater", "strait1"].join("/");
    const hits = Object.entries(files)
      .filter(
        ([f, src]) =>
          !f.endsWith("mock-theater.test.ts") && src.includes(needle),
      )
      .map(([f]) => f);
    expect(hits).toEqual([]);
  });
});
