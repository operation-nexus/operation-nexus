import type { Side } from "./theater";
import type { ThreatTierChanged } from "../contracts/events/event";

export type ThreatTier = ThreatTierChanged["to"];

export interface MomentumData {
  quorum: number; // 0 to 100
  static: number; // 0 to 100
}

export interface SitrepItem {
  id: string;
  timestamp: number;
  text: string;
  severity: "info" | "warn" | "alert";
  side?: Side | undefined;
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
  threatTier: ThreatTier;
  sitrep: SitrepItem[];
  ticker: TickerItem[];
  fps?: number | undefined;
  unitCount?: number | undefined;
}
