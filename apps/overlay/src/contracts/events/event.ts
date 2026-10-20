/* Generated from contracts/ by make contracts (NX-021). Do not edit. */

/**
 * Discriminated union of all sim events on kind (CONTRACTS §6).
 */
export type Event = UnitSpawned;

/**
 * A unit appears (CONTRACTS §6). Public view: an ENEMY spawn only if its spawn point is tracked; otherwise dropped.
 */
export interface UnitSpawned {
  kind: "UnitSpawned";
  /**
   * 10 Hz game time (SC-2).
   */
  tick: number;
  /**
   * Campaign-wide, monotonic, deterministic (SC-14).
   */
  event_seq: number;
  /**
   * UUIDv7, canonical lowercase.
   */
  campaign_id: string;
  /**
   * Sequential per campaign, never reused (SC-4).
   */
  entity_id: number;
  /**
   * MVP list; FACTORY is parked (Q-GP-41).
   */
  unit_kind:
    | "STRIKE_FIGHTER"
    | "RECON_UAV"
    | "LOGI_TRUCK"
    | "GARRISON_INFANTRY"
    | "ENEMY_FIGHTER"
    | "ENEMY_STRIKE_FIGHTER"
    | "ENEMY_RECON_UAV"
    | "ENEMY_ARMOR"
    | "ENEMY_CONVOY"
    | "RADAR_SITE"
    | "AIR_DEFENSE_SITE";
  side: "COALITION" | "ENEMY";
  owner_kind: "COMMANDER" | "AI_GARRISON" | "ENEMY_DIRECTOR";
  commander_id: string | null;
  /**
   * null for AI entities, which render [AI] (DI-5).
   */
  callsign: string | null;
  /**
   * Stable slug from the theater file.
   */
  node_id: string;
  loadout: "FULL" | "REDUCED";
}
