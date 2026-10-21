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
  | NodeCaptured
  | CampaignClockPaused
  | CampaignClockResumed
  | CampaignEnded
  | ObjectiveAnnounced
  | ObjectiveResolved
  | WeaponFired
  | WeaponImpact
  | UnitDamageStateChanged
  | UnitDespawned;

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
  command_kind: "JOIN" | "SYS_SET_CALLSIGN" | "STAFF_CAMPAIGN_PAUSE" | "STAFF_CAMPAIGN_RESUME" | "STAFF_CAMPAIGN_END";
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
    | "RESERVE_QUEUE_FULL"
    | "ALREADY_PAUSED"
    | "NOT_PAUSED"
    | "CAMPAIGN_NOT_RUNNING"
    | "REASON_REQUIRED";
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
 * A unit is lost (CONTRACTS §6; STATE-MACHINES §4.1 Destroyed). Produced by fuel exhaustion (NX-368) and a captured base (NX-125), both with killer null and no assists, and by combat (NX-124): killer is the shooter of the killing hit and the assists are the other shooters that hit the unit within combat.assist_window_s. Public view: a hidden killer becomes null (FOW-3); a hidden victim is dropped.
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
   * null: no killer (fuel exhaustion or loss of a captured base), or a hidden killer in the public view.
   */
  killer_id: number | null;
  /**
   * Combat: the other shooters that hit the unit within combat.assist_window_s, sorted, no duplicates (producer). Not uniqueItems: that generates a set, whose order is not deterministic (SC-14).
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
/**
 * The campaign clock stopped (CONTRACTS 6; STATE-MACHINES 4.4; NX-126). The staff note is not in the event. Public view: sub_reason omitted (Q-ALN-39).
 */
export interface CampaignClockPaused {
  kind: "CampaignClockPaused";
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
   * Q-ALN-3. STAFF = a manual pause; TECHNICAL = offline auto-pause; MAINTENANCE = weekly window; CEASEFIRE = owner Ceasefire mode.
   */
  reason: "STAFF" | "TECHNICAL" | "MAINTENANCE" | "CEASEFIRE";
  sub_reason: ("RAID" | "ABUSE" | "CONTENT" | "OTHER") | null;
}
/**
 * The campaign clock restarted (CONTRACTS 6; NX-126). reason and sub_reason are those of the pause it ends. Public view: sub_reason omitted (Q-ALN-39).
 */
export interface CampaignClockResumed {
  kind: "CampaignClockResumed";
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
   * Q-ALN-3. STAFF = a manual pause; TECHNICAL = offline auto-pause; MAINTENANCE = weekly window; CEASEFIRE = owner Ceasefire mode.
   */
  reason: "STAFF" | "TECHNICAL" | "MAINTENANCE" | "CEASEFIRE";
  sub_reason: ("RAID" | "ABUSE" | "CONTENT" | "OTHER") | null;
}
/**
 * The campaign ended (CONTRACTS 6; STATE-MACHINES 4.4, C-2; NX-126). Exactly one per campaign. score is each side's time-limit score at the end (Q-GD-29): weight x average share of strategic nodes over the campaign, plus the objective points for the coalition's completed objectives; it is filled for every result. winner is null on an exact TIME_LIMIT tie and for ABORTED. nodes_held_pct is the coalition's share of strategic nodes at the end, rounded to the nearest percent, halves up.
 */
export interface CampaignEnded {
  kind: "CampaignEnded";
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
   * Q-GD-7, Q-GP-14. Defeat waits for combat (Q-SIM-62).
   */
  result: "VICTORY" | "DEFEAT" | "TIME_LIMIT" | "ABORTED";
  /**
   * 10 Hz game time (SC-2).
   */
  end_tick: number;
  score: {
    coalition: number;
    enemy: number;
  };
  winner: ("COALITION" | "ENEMY") | null;
  nodes_held_pct: number;
}
/**
 * A timed objective was announced (CONTRACTS 6; STATE-MACHINES 4.5; NX-126). deadline_tick is on the campaign clock (running ticks, the Hud's campaign_clock.elapsed_ticks), not the tick counter: a pause delays the real tick, so the deadline is not a Tick.
 */
export interface ObjectiveAnnounced {
  kind: "ObjectiveAnnounced";
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
   * Sequential per campaign, never reused (STATE-MACHINES 4.5).
   */
  objective_id: number;
  /**
   * Stable slug from the theater file.
   */
  node_id: string;
  deadline_tick: number;
}
/**
 * A timed objective was completed or expired (CONTRACTS 6; STATE-MACHINES 4.5; NX-126). participant_commander_ids: for a capture, the NodeCaptured participants; for a hold, the coalition commanders with units within capture.radius_m of the node at the deadline; ascending, no duplicates (producer); empty on EXPIRED.
 */
export interface ObjectiveResolved {
  kind: "ObjectiveResolved";
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
   * Sequential per campaign, never reused (STATE-MACHINES 4.5).
   */
  objective_id: number;
  outcome: "COMPLETED" | "EXPIRED";
  /**
   * Items: UUIDv7, canonical lowercase (IDENTITY §1). Not a platform id.
   */
  participant_commander_ids: string[];
}
/**
 * A unit fired a weapon at a target (CONTRACTS §6; COMBAT CB-2). The shot is not an entity; the outcome is not known yet (Q-GP-12). impact_tick is on the campaign clock (running ticks), not the tick counter: a pause delays the real tick, so it is not a Tick; a gun's equals the clock value of the tick it fired in. Public view: a hidden shooter shows no tracer (Q-CT-3).
 */
export interface WeaponFired {
  kind: "WeaponFired";
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
  shooter_id: number;
  /**
   * Sequential per campaign, never reused (SC-4).
   */
  target_id: number;
  /**
   * Weapon profile id from content/weapons.yaml (CONFIG-AND-CONTENT §7.2).
   */
  weapon: string;
  /**
   * The campaign-clock tick the shot lands on.
   */
  impact_tick: number;
}
/**
 * A shot landed (CONTRACTS §6; COMBAT CB-3, CB-4), on its impact tick after the Pk roll. A fizzle (the shooter's side no longer tracks the target, the target is out of the weapon's range or bands, or the target or shooter is gone) is a miss with no roll (Q-FOW-16). Public view: a hidden shooter shows as an unknown contact.
 */
export interface WeaponImpact {
  kind: "WeaponImpact";
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
  shooter_id: number;
  /**
   * Sequential per campaign, never reused (SC-4).
   */
  target_id: number;
  /**
   * Weapon profile id from content/weapons.yaml (CONFIG-AND-CONTENT §7.2).
   */
  weapon: string;
  hit: boolean;
}
/**
 * A hit moved a unit to a worse damage state (CONTRACTS §6; COMBAT CB-6). One event per hit, from the state before to the state after; none when the hit destroys the unit (UnitDestroyed). Public view: dropped for a victim the viewer side does not currently observe (FOW-13).
 */
export interface UnitDamageStateChanged {
  kind: "UnitDamageStateChanged";
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
   * Q-CBT-1. Destroyed is a lifecycle event (UnitDestroyed), not a damage state.
   */
  from: "HEALTHY" | "DAMAGED" | "MISSION_KILL" | "DISABLED";
  /**
   * Q-CBT-1. Destroyed is a lifecycle event (UnitDestroyed), not a damage state.
   */
  to: "HEALTHY" | "DAMAGED" | "MISSION_KILL" | "DISABLED";
}
/**
 * A unit was removed without being destroyed (CONTRACTS §6). WRECKED is the first producer: a Disabled unit removed after combat.disabled_timeout_s, its cargo lost (COMBAT CB-7, Q-CBT-14). Other reasons join with their producers (rule 6a). Public view: a hidden ENEMY unit is dropped.
 */
export interface UnitDespawned {
  kind: "UnitDespawned";
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
  reason: "WRECKED";
}
