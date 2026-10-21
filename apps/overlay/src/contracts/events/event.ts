/* Generated from contracts/ by make contracts (NX-021). Do not edit. */

/**
 * Discriminated union of all sim events on kind (CONTRACTS §6).
 */
export type Event =
  | UnitSpawned
  | CommandRejected
  | ReserveQueueJoined
  | UnitDestroyed
  | CallsignChanged
  | SupplyDelivered
  | SupplyConsumed
  | RearmStalled
  | CaptureStarted
  | NodeCaptured;

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
  command_kind: "JOIN" | "SYS_SET_CALLSIGN";
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
/**
 * A commander's callsign was set by SYS_SET_CALLSIGN (CONTRACTS §6). Broadcast-only, already approved. TOMBSTONE renders as REDACTED- plus the tag after X- (Q-DM-2, Q-ALN-29).
 */
export interface CallsignChanged {
  kind: "CallsignChanged";
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
   * Generated WORD-NN or approved custom (IDENTITY §2-3).
   */
  callsign: string;
  /**
   * IDENTITY §2, DATA-MODEL §4.2.
   */
  callsign_kind: "GENERATED" | "CUSTOM" | "TOMBSTONE";
}
/**
 * A truck's unloading stop at a node ended (CONTRACTS §6; NX-123): its cargo ran out, the node reached its maximum, or it drove off. One event per stop, amount = the whole stock units delivered at that node during the stop; none when 0 were delivered. Public view: none for coalition, ENEMY deliveries are dropped.
 */
export interface SupplyDelivered {
  kind: "SupplyDelivered";
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
   * Stable slug from the theater file.
   */
  node_id: string;
  amount: number;
  /**
   * Sequential per campaign, never reused (SC-4).
   */
  carrier_id: number;
  commander_id: string | null;
}
/**
 * Stock a node paid out for units (CONTRACTS §6; NX-123): SPAWN once per forward-deployed unit, REARM once per refuel stop when it ends (filled, stalled or taken off). amount = whole stock units; none when 0. Public view: ENEMY nodes are dropped.
 */
export interface SupplyConsumed {
  kind: "SupplyConsumed";
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
   * Stable slug from the theater file.
   */
  node_id: string;
  amount: number;
  cause: "SPAWN" | "REARM";
}
/**
 * A landed aircraft needs fuel and its base has none (CONTRACTS §6; NX-123, STATE-MACHINES §4.1 Rearming): emitted once when the stall starts, not every tick; a resupply and a new stall emit again. ENEMY: dropped from public views.
 */
export interface RearmStalled {
  kind: "RearmStalled";
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
   * Stable slug from the theater file.
   */
  node_id: string;
}
/**
 * A side's capture bar on a node began to fill (CONTRACTS §6; STATE-MACHINES §4.2; NX-125): its eligible ground units are in radius and no opposing combat-capable unit blocks them, and the node had no progress. Emitted again when a bar that decayed to 0 starts afresh. Public view: none (nodes are always visible).
 */
export interface CaptureStarted {
  kind: "CaptureStarted";
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
   * Stable slug from the theater file.
   */
  node_id: string;
  /**
   * The capturing side.
   */
  side: "COALITION" | "ENEMY";
}
/**
 * A node's owner flipped (CONTRACTS §6; STATE-MACHINES §4.2; NX-125). `to` is the capturing side, `from` the previous owner (NEUTRAL for an unowned node). participant_commander_ids: the commanders of the capturing side's units in radius at the flip, ascending, no duplicates (producer). Not uniqueItems: that generates a set, whose order is not deterministic (SC-14). Public view: ENEMY participants are omitted.
 */
export interface NodeCaptured {
  kind: "NodeCaptured";
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
   * Stable slug from the theater file.
   */
  node_id: string;
  from: "COALITION" | "ENEMY" | "NEUTRAL";
  to: "COALITION" | "ENEMY" | "NEUTRAL";
  /**
   * Items: UUIDv7, canonical lowercase (IDENTITY §1). Not a platform id.
   */
  participant_commander_ids: string[];
}
