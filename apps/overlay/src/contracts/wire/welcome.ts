/* Generated from contracts/ by make contracts (NX-021). Do not edit. */

/**
 * Server to client, after a valid Hello (CONTRACTS section 7, WIRE-PROTOCOL WP-7).
 */
export interface Welcome {
  type: "Welcome";
  /**
   * PROTOCOL_VERSION (contracts/VERSION).
   */
  v: string;
  server_build: string;
  campaign_id: string | null;
  tick_rate_hz: number;
  theater: TheaterStatic;
}
/**
 * Sent once, in Welcome.
 */
export interface TheaterStatic {
  nodes: {
    /**
     * Stable slug from the theater file.
     */
    node_id: string;
    name: string;
    /**
     * SIM-CORE §4. Facilities are UnitKinds, not nodes (Q-GP-21, Q-GP-25).
     */
    kind: "AIRBASE" | "FOB" | "PORT" | "BRIDGE" | "HQ" | "SANCTUARY";
    pos: Pos;
  }[];
  edges: {
    /**
     * Stable slug from the theater file.
     */
    a: string;
    /**
     * Stable slug from the theater file.
     */
    b: string;
    layer: "ROAD" | "SEA_LANE";
    bridge: string | null;
  }[];
  /**
   * The playable area, unit m: x in [0, w], y in [0, h], origin south-west, +y north (Q-UX-18, Q-UX-19). The overlay frames on it.
   */
  bounds_m: {
    w: number;
    h: number;
  };
  terrain_ref: string | null;
}
export interface Pos {
  /**
   * metres, quantized to 1 m (WP-4)
   */
  x_m: number;
  /**
   * metres, quantized to 1 m (WP-4)
   */
  y_m: number;
}
