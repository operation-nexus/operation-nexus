/* Generated from contracts/ by make contracts (NX-021). Do not edit. */

/**
 * Discriminated union of all sim events on kind (CONTRACTS §6).
 */
export type Event = UnitSpawned | CommandRejected | ReserveQueueJoined | UnitDestroyed;

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
   * null for AI entities, and for COMMANDER units until identity supplies the callsign with SYS_SET_CALLSIGN (IDENTITY §2). Clients key the [AI] marker (DI-5) on owner_kind, never on a null callsign.
   */
  callsign: string | null;
  /**
   * Stable slug from the theater file.
   */
  node_id: string;
  loadout: "FULL" | "REDUCED";
}
/**
 * A command was rejected (CONTRACTS §5.3, §6; SIM-CORE SC-7). Not public: aggregated digest only. command_kind is the rejected command's kind; kind is the event discriminator.
 */
export interface CommandRejected {
  kind: "CommandRejected";
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
   * Arrival order assigned by the runtime inbox; carried as arrival_seq.
   */
  arrival_seq: number;
  /**
   * Grows one kind at a time, with each handler (AGENTS.md rule 6a).
   */
  command_kind: "JOIN";
  /**
   * CONTRACTS §5.3. Grows one value at a time, with the code that emits it (rule 6a).
   */
  reason:
    | "ROLE_UNKNOWN"
    | "UNIT_IN_SORTIE"
    | "RESPAWN_COOLDOWN"
    | "NODE_UNKNOWN"
    | "NODE_INVALID_FOR_UNIT"
    | "FOLLOW_TARGET_INVALID"
    | "CAMPAIGN_PAUSED"
    | "INVALID_PAYLOAD"
    | "INTERNAL_ERROR"
    | "RESERVE_QUEUE_FULL";
  commander_id: string | null;
}
/**
 * A JOIN went to the reserve queue (CONTRACTS §6; GAMEPLAY GP-3, RQ-1; STATE-MACHINES §4.1): the cap is reached, the queue is not empty, or the campaign is paused (Q-ALN-26). Also emitted when a queued commander's new JOIN replaces its entry. Public view: queue length only.
 */
export interface ReserveQueueJoined {
  kind: "ReserveQueueJoined";
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
   * UUIDv7, canonical lowercase (IDENTITY §1). Not a platform id.
   */
  commander_id: string;
  /**
   * 1-based place in the queue; 1 is served next.
   */
  position: number;
}
/**
 * A unit is lost (CONTRACTS §6; STATE-MACHINES §4.1 Destroyed). First producer: an aircraft out of fuel crashes, killer null and no assists (NX-368). Public view: a hidden killer becomes null (FOW-3); a hidden victim is dropped.
 */
export interface UnitDestroyed {
  kind: "UnitDestroyed";
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
   * null: no killer (fuel exhaustion), or a hidden killer in the public view.
   */
  killer_id: number | null;
  /**
   * No duplicates (producer). Not uniqueItems: that generates a set, whose order is not deterministic (SC-14).
   *
   * @maxItems 32
   *
   * Items: Sequential per campaign, never reused (SC-4).
   */
  assist_ids: number[];
  /**
   * The lost unit's side.
   */
  side: "COALITION" | "ENEMY";
}
