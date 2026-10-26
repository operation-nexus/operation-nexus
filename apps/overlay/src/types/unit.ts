import type {
  UnitDamageStateChanged,
  UnitSpawned,
} from "../contracts/events/event";
import type { EdgeLayer } from "./theater";

export type UnitSide = UnitSpawned["side"];

export type UnitKind = UnitSpawned["unit_kind"];

export type DamageState = UnitDamageStateChanged["to"];

export interface TrailPoint {
  x: number;
  y: number;
  alpha: number;
}

export interface VisualUnit {
  id: number;
  callsign: string;
  side: UnitSide;
  kind: UnitKind;
  x: number; // meters from theater origin (0 to bounds.w)
  y: number; // meters from theater origin (0 to bounds.h)
  z?: number | undefined; // altitude in meters (0 for ground, 30..60 for air)
  vx?: number | undefined; // velocity x in m/s
  vy?: number | undefined; // velocity y in m/s
  headingDeg: number; // 0 to 360 degrees
  speedMps?: number | undefined;
  hpPct: number; // 0 to 100
  damageState: DamageState;
  isSelected?: boolean | undefined;
  isAiControlled?: boolean | undefined;
  trailHistory?: TrailPoint[] | undefined;
  cargoCount?: number | undefined; // for logistics convoys
  isConvoyLeader?: boolean | undefined;
  convoyFollowers?: number | undefined; // badge "[TRUCK] +3"
}

export interface VisualEdge {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  layer: EdgeLayer;
  roadClass: "MSR_PRIMARY" | "CONNECTOR_SPUR" | "BRIDGE_CAUSEWAY";
  speedMult: number;
  bridgeId?: string | undefined;
  bridgeIntegrityPct?: number | undefined; // 0 to 100
  activeConvoyCount: number;
  isContested: boolean;
  waypointsMeters: Array<[number, number]>;
}
