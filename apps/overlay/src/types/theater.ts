import type { NodeCaptured } from "../contracts/events/event";

// Node owner: the contract NodeCaptured.to (COALITION | ENEMY | NEUTRAL).
export type Side = NodeCaptured["to"];

export const NODE_KINDS = [
  "AIRBASE",
  "FOB",
  "PORT",
  "BRIDGE",
  "HQ",
  "SANCTUARY",
] as const;
export type NodeKind = (typeof NODE_KINDS)[number];

export const EDGE_LAYERS = ["ROAD", "SEA_LANE"] as const;
export type EdgeLayer = (typeof EDGE_LAYERS)[number];

export interface TheaterBounds {
  w: number; // width in meters (e.g. 400000)
  h: number; // height in meters (e.g. 240000)
}

export interface MaskingRegion {
  id: string;
  polygon: Array<[number, number]>;
}

export interface Sector {
  id: string;
  name: string;
  polygon: Array<[number, number]>;
}

export interface TheaterNode {
  id: string;
  name: string;
  kind: NodeKind;
  pos: [number, number]; // [x, y] in meters
  startOwner: Side;
  startStock?: number | null | undefined;
  sector: string;
  garrisonQuota?: number | undefined;
}

export interface TheaterEdge {
  a: string;
  b: string;
  layer: EdgeLayer;
  speedMult: number;
  bridge?: string | undefined;
}

export interface TheaterDefinition {
  schemaVersion: number;
  slug: string;
  name: string;
  version: string;
  boundsM: TheaterBounds;
  sectors: Sector[];
  maskingRegions: MaskingRegion[];
  nodes: TheaterNode[];
  edges: TheaterEdge[];
  sanctuary: string;
  enemyRearSource: string;
  enemyHq: string;
  forwardAirbase: string;
}
