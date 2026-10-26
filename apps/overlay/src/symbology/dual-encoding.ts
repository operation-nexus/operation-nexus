import type { Side } from "../types/theater";
import type { UnitKind, UnitSide, VisualUnit } from "../types/unit";

/**
 * Tactical color tokens per VISUAL-STYLE-CATALOG.md and OVERLAY.md.
 */
export const FACTION_TOKENS = {
  QUORUM_CYAN: "#00e5ff",
  QUORUM_FILL: "#0284c7",
  QUORUM_GLOW: "rgba(0, 229, 255, 0.45)",

  STATIC_MAGENTA: "#ff0055",
  STATIC_FILL: "#be123c",
  STATIC_GLOW: "rgba(255, 0, 85, 0.45)",

  NEUTRAL_SLATE: "#94a3b8",
  NEUTRAL_FILL: "#334155",
  NEUTRAL_GLOW: "rgba(148, 163, 184, 0.3)",

  SUPPLY_AMBER: "#f59e0b",
  RADAR_EMERALD: "#10b981",
  VOID_BACKGROUND: "#050b14",
} as const;

export interface SideColorTheme {
  primary: string;
  fill: string;
  glow: string;
  label: string;
}

export function getSideColors(side: Side): SideColorTheme {
  switch (side) {
    case "COALITION":
      return {
        primary: FACTION_TOKENS.QUORUM_CYAN,
        fill: FACTION_TOKENS.QUORUM_FILL,
        glow: FACTION_TOKENS.QUORUM_GLOW,
        label: "QUORUM",
      };
    case "ENEMY":
      return {
        primary: FACTION_TOKENS.STATIC_MAGENTA,
        fill: FACTION_TOKENS.STATIC_FILL,
        glow: FACTION_TOKENS.STATIC_GLOW,
        label: "STATIC",
      };
    case "NEUTRAL":
    default:
      return {
        primary: FACTION_TOKENS.NEUTRAL_SLATE,
        fill: FACTION_TOKENS.NEUTRAL_FILL,
        glow: FACTION_TOKENS.NEUTRAL_GLOW,
        label: "NEUTRAL",
      };
  }
}

/**
 * Aircraft (drawn at altitude). Exhaustive: a new contract UnitKind fails tsc
 * here until it is classified.
 */
export function isAirUnit(kind: UnitKind): boolean {
  switch (kind) {
    case "STRIKE_FIGHTER":
    case "RECON_UAV":
    case "ENEMY_FIGHTER":
    case "ENEMY_STRIKE_FIGHTER":
    case "ENEMY_RECON_UAV":
      return true;
    case "LOGI_TRUCK":
    case "GARRISON_INFANTRY":
    case "ENEMY_ARMOR":
    case "ENEMY_CONVOY":
    case "RADAR_SITE":
    case "AIR_DEFENSE_SITE":
      return false;
    default: {
      const unreachable: never = kind;
      return unreachable;
    }
  }
}

/**
 * Shape descriptor describing geometry for colorblind differentiation (OV-2/3).
 */
export interface ShapeDescriptor {
  side: UnitSide;
  geometryFamily: "SMOOTH_CHEVRON_DIAMOND" | "JAGGED_SAWTOOTH";
  vertexCount: number;
  hasSawtoothJags: boolean;
  isAngularChevron: boolean;
}

export function getUnitShapeDescriptor(unit: VisualUnit): ShapeDescriptor {
  if (unit.side === "COALITION") {
    return {
      side: "COALITION",
      geometryFamily: "SMOOTH_CHEVRON_DIAMOND",
      vertexCount:
        unit.kind === "STRIKE_FIGHTER" ? 4 : unit.kind === "RECON_UAV" ? 4 : 5,
      hasSawtoothJags: false,
      isAngularChevron: true,
    };
  }
  return {
    side: "ENEMY",
    geometryFamily: "JAGGED_SAWTOOTH",
    vertexCount: 7, // 7-point jagged sawtooth polygon
    hasSawtoothJags: true,
    isAngularChevron: false,
  };
}

/**
 * Draw dual-encoded unit shape onto a 2D canvas context.
 * Quorum units render clean smooth angular chevrons/diamonds.
 * Static units render aggressive jagged sawtooth silhouettes.
 */
export function drawUnitVectorShape(
  ctx: CanvasRenderingContext2D,
  unit: VisualUnit,
  radius: number,
): void {
  const colors = getSideColors(unit.side);
  ctx.save();
  ctx.strokeStyle = colors.primary;
  ctx.fillStyle = colors.fill;
  ctx.lineWidth = 2;
  ctx.shadowColor = colors.glow;
  ctx.shadowBlur = 6;

  ctx.beginPath();
  if (unit.side === "COALITION") {
    // NATO Smooth Angular Chevron / Delta Wing
    if (unit.kind === "STRIKE_FIGHTER") {
      ctx.moveTo(0, -radius);
      ctx.lineTo(radius * 0.85, radius);
      ctx.lineTo(0, radius * 0.45);
      ctx.lineTo(-radius * 0.85, radius);
      ctx.closePath();
    } else if (unit.kind === "RECON_UAV") {
      // Clean NATO Diamond
      ctx.moveTo(0, -radius);
      ctx.lineTo(radius * 0.7, 0);
      ctx.lineTo(0, radius);
      ctx.lineTo(-radius * 0.7, 0);
      ctx.closePath();
    } else {
      // Logistics Truck: Smooth rounded box chevron
      ctx.moveTo(-radius * 0.6, -radius * 0.8);
      ctx.lineTo(radius * 0.6, -radius * 0.8);
      ctx.lineTo(radius * 0.6, radius * 0.8);
      ctx.lineTo(-radius * 0.6, radius * 0.8);
      ctx.closePath();
    }
  } else {
    // Static: Jagged Sawtooth Shard Silhouette (OV-2 / OV-3)
    ctx.moveTo(0, -radius * 1.1);
    ctx.lineTo(radius * 0.45, -radius * 0.3);
    ctx.lineTo(radius * 0.9, -radius * 0.1);
    ctx.lineTo(radius * 0.4, radius * 0.5);
    ctx.lineTo(radius * 0.75, radius);
    ctx.lineTo(0, radius * 0.5);
    ctx.lineTo(-radius * 0.75, radius);
    ctx.lineTo(-radius * 0.4, radius * 0.5);
    ctx.lineTo(-radius * 0.9, -radius * 0.1);
    ctx.lineTo(-radius * 0.45, -radius * 0.3);
    ctx.closePath();
  }

  ctx.fill();
  ctx.stroke();

  // If unit is damaged, draw warning slash
  if (unit.damageState === "DAMAGED" || unit.damageState === "MISSION_KILL") {
    ctx.strokeStyle = "#ff3366";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(-radius * 0.5, -radius * 0.5);
    ctx.lineTo(radius * 0.5, radius * 0.5);
    ctx.stroke();
  }

  ctx.restore();
}
