import { describe, expect, it } from "vitest";
import type { VisualUnit } from "../types/unit";
import {
  FACTION_TOKENS,
  getSideColors,
  getUnitShapeDescriptor,
  drawUnitVectorShape,
} from "../symbology/dual-encoding";

describe("OV-2 / OV-3 Colorblind-Safe Dual-Encoding", () => {
  const quorumFighter: VisualUnit = {
    id: 1,
    callsign: "VIPER-01",
    side: "COALITION",
    kind: "STRIKE_FIGHTER",
    x: 100000,
    y: 60000,
    headingDeg: 90,
    hpPct: 100,
    damageState: "HEALTHY",
  };

  const quorumRecon: VisualUnit = {
    id: 2,
    callsign: "GHOST-1",
    side: "COALITION",
    kind: "RECON_UAV",
    x: 120000,
    y: 80000,
    headingDeg: 180,
    hpPct: 100,
    damageState: "HEALTHY",
  };

  const staticArmor: VisualUnit = {
    id: 3,
    callsign: "NULL-IRON-9",
    side: "ENEMY",
    kind: "ENEMY_ARMOR",
    x: 250000,
    y: 60000,
    headingDeg: 270,
    hpPct: 80,
    damageState: "DAMAGED",
  };

  it("enforces color palette tokens matching specification", () => {
    expect(FACTION_TOKENS.QUORUM_CYAN).toBe("#00e5ff");
    expect(FACTION_TOKENS.STATIC_MAGENTA).toBe("#ff0055");
    expect(FACTION_TOKENS.VOID_BACKGROUND).toBe("#050b14");

    const quorumColors = getSideColors("COALITION");
    expect(quorumColors.primary).toBe("#00e5ff");
    expect(quorumColors.label).toBe("QUORUM");

    const staticColors = getSideColors("ENEMY");
    expect(staticColors.primary).toBe("#ff0055");
    expect(staticColors.label).toBe("STATIC");
  });

  it("provides shape differentiation independent of color (colorblind safety)", () => {
    const qFighterDesc = getUnitShapeDescriptor(quorumFighter);
    const qReconDesc = getUnitShapeDescriptor(quorumRecon);
    const staticDesc = getUnitShapeDescriptor(staticArmor);

    // Quorum units MUST use smooth angular chevrons / diamonds
    expect(qFighterDesc.geometryFamily).toBe("SMOOTH_CHEVRON_DIAMOND");
    expect(qFighterDesc.hasSawtoothJags).toBe(false);
    expect(qFighterDesc.isAngularChevron).toBe(true);

    expect(qReconDesc.geometryFamily).toBe("SMOOTH_CHEVRON_DIAMOND");
    expect(qReconDesc.hasSawtoothJags).toBe(false);

    // Static enemy units MUST use jagged sawtooth silhouettes
    expect(staticDesc.geometryFamily).toBe("JAGGED_SAWTOOTH");
    expect(staticDesc.hasSawtoothJags).toBe(true);
    expect(staticDesc.isAngularChevron).toBe(false);
    expect(staticDesc.vertexCount).toBe(7);
  });

  it("executes drawUnitVectorShape on canvas context without throwing", () => {
    const mockCtx = {
      save: () => {},
      restore: () => {},
      beginPath: () => {},
      moveTo: () => {},
      lineTo: () => {},
      closePath: () => {},
      arc: () => {},
      fill: () => {},
      stroke: () => {},
      strokeStyle: "",
      fillStyle: "",
      lineWidth: 0,
      shadowColor: "",
      shadowBlur: 0,
    } as unknown as CanvasRenderingContext2D;

    expect(() => drawUnitVectorShape(mockCtx, quorumFighter, 8)).not.toThrow();
    expect(() => drawUnitVectorShape(mockCtx, staticArmor, 8)).not.toThrow();
  });
});
