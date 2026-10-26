export type Side = "COALITION" | "ENEMY" | "NEUTRAL";

export type NodeKind =
  "SANCTUARY" | "AIRBASE" | "FOB" | "BRIDGE" | "HQ" | "CROSSING";

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
  layer: "ROAD" | "SEA_LANE";
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
