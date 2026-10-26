export type VisualEffectType =
  | "MISSILE_TRAJECTORY"
  | "KINETIC_BURST"
  | "RADAR_SWEEP"
  | "SCANLINE_GLITCH"
  | "BRIDGE_CRACK";

export interface MissileTrajectoryEffect {
  type: "MISSILE_TRAJECTORY";
  id: string;
  sourcePos: [number, number, number]; // [x, y, z] in meters
  targetPos: [number, number, number]; // [x, y, z] in meters
  progress: number; // 0.0 to 1.0
  peakAltitudeMeters: number; // e.g. 5000m
  color: string;
}

export interface KineticBurstEffect {
  type: "KINETIC_BURST";
  id: string;
  pos: [number, number, number]; // [x, y, z] in meters
  radiusMeters: number;
  progress: number; // 0.0 to 1.0
  color: string;
}

export interface RadarSweepEffect {
  type: "RADAR_SWEEP";
  angleDeg: number;
  centerPos: [number, number];
  radiusMeters: number;
}

export interface ScanlineGlitchEffect {
  type: "SCANLINE_GLITCH";
  intensity: number; // 0.0 to 1.0
  durationMs: number;
}

export interface BridgeCrackEffect {
  type: "BRIDGE_CRACK";
  bridgeId: string;
  pos: [number, number];
  integrityPct: number;
}

export type VisualEffect =
  | MissileTrajectoryEffect
  | KineticBurstEffect
  | RadarSweepEffect
  | ScanlineGlitchEffect
  | BridgeCrackEffect;
