export type ThreatLevel = "NOMINAL" | "ELEVATED" | "CRITICAL";

export type ThreatTier =
  "PATTERN_OF_LIFE" | "CONDITION_ALPHA" | "CONDITION_BRAVO";

export interface MomentumData {
  quorum: number; // 0 to 100
  static: number; // 0 to 100
}

export interface SitrepItem {
  id: string;
  timestamp: number;
  text: string;
  severity: "info" | "warn" | "alert";
  side?: "COALITION" | "ENEMY" | "NEUTRAL" | undefined;
}

export interface TickerItem {
  id: string;
  category: "RECRUITMENT" | "INTEL" | "LOGISTICS" | "THREAT";
  text: string;
}

export interface TelemetryState {
  momentum: MomentumData;
  countdownSeconds: number;
  objectiveName: string;
  threatLevel: ThreatLevel;
  threatTier: ThreatTier;
  sitrep: SitrepItem[];
  ticker: TickerItem[];
  fps?: number | undefined;
  unitCount?: number | undefined;
}
