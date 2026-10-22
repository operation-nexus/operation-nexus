"""World model, canonical encoding, `state_hash` and snapshots (SIM-CORE SC-4, SC-9, SC-14, §4, §5).

Systems reach entities only through `World` (Q-SIM-4), never its storage. `Entity` holds only the
fields the first systems need; every other SIM-CORE §4 field is added by the system that first
uses it.

One walker, `to_canonical`, turns a world into plain sorted data. Snapshots keep floats exactly
(float64), so a restored run continues bit-identically; only `state_hash` quantizes (ADR-0002):
positions, `orbit` centres and `path` waypoints to integer mm, velocities to integer mm/s, other
floats (`fuel`) to ADR-0002's 1e-6 step. Python's `round` is round-half-to-even on the
exact float value, so it is deterministic. The RNG state, `respawn_left` (per commander, GP-2),
the reserve queue (GP-3), each side's FoW contacts with their painted flag (FOW-5), discovered
facility markers (FOW-13), SIGINT blobs and the running ticks since their refresh (Tier 1, FOW-9)
are world state, so snapshots and the hash cover them. So are each entity's `hp`, `damage_state`,
`alt_band`, per-weapon `ammo` and `reload` countdowns, wreck countdown and recent-hit list, and
the pending `shots` with their id counter (NX-124): thresholds, reloads and impact ticks are
integers. So are the downed-crew markers with their id counter, and the rest of each rearm stop's
progress (`ammo_credit`, `repair_milli`, `repair_debt`; NX-124 part 2). So are each node's
defense hp with its starvation-drain carry, the defeat run and the shots at nodes (NX-124 part 3).
So are both sides' Tasking Boards with their job counter, and each entity's explicit order and
claimed job (NX-374): leases, expiries and urgencies are integers.
So are each node's `stock` and each carrier's `cargo` (integer stock units) with its
`unload_milli` progress and `delivered` count (NX-123), and each aircraft's refuel progress
(`rearm_milli`, `rearm_spent`,
`stalled`): conservation stays exact. So are each node's live owner and its capture bar (side and
integer millionths of a percent, NX-125): thresholds are exact. So are the campaign's running
ticks, hold run, per-side held-node tick sums, objective counts and the active objective (NX-126).
`World.rules` (`nexus.core.rules`) is static config, not state: neither snapshots nor the hash
include it.
"""

import hashlib
import math
import re
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field, fields
from typing import Annotated, Any, Literal, Self, cast, get_args, get_origin

import msgpack

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.common.enums import (
    AltBand,
    DamageState,
    JobKind,
    NodeOwner,
    OwnerKind,
    PauseReasonCategory,
    Side,
    StaffPauseSubReason,
    ThreatTier,
    UnitKind,
)
from nexus.contracts.gen.events.crew_downed import CrewDowned, Pos
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_released import JobReleased
from nexus.contracts.gen.events.supply_consumed import SupplyConsumed
from nexus.contracts.gen.events.supply_delivered import SupplyDelivered
from nexus.contracts.gen.events.unit_damage_state_changed import UnitDamageStateChanged
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.core.rng import RngStream, SimRng
from nexus.core.rules import CAPTURE_FULL, Rules

# 2: Entity.path and Entity.last_node (NX-121); 3: respawn_left, hp may be null; 4: reserve_queue;
# 5: Entity.state, fuel and orbit (NX-368); 6: callsigns (NX-370); 7: contacts (NX-150);
# 8: Entity.base_id, variant and emitting, markers (NX-150 part 2); 9: Contact.painted, blobs,
# sigint_age (NX-150 part 2b); 10: node stock, Entity.cargo and unload_milli (NX-123);
# 11: Entity.rearm_milli, rearm_spent and stalled (NX-123 part 2); 12: node owner and capture bars
# (NX-125); 13: the campaign clock, pause reason, end flag, score sums and the active objective
# (NX-126); 14: Entity.hp is always real, damage_state, alt_band, ammo, reload, wreck_left, and the
# pending shots (NX-124); 15: Entity.ammo_credit, repair_milli and repair_debt, the downed-crew
# markers (NX-124 part 2); 16: node defense hp and drain carry, Campaign.defeat_ticks, structure
# shots, FacilityMarker.ring_m and state (NX-124 part 3); 17: the Tasking Boards and their job
# counter, Entity.order and Entity.job_id (NX-374); 18: Entity.follow_id and fired_by, Job.entity
# (follow and escort, NX-374 part 2); 19: each side's Threat Director state (NX-155); 20: its threat
# memory, lost nodes and adaptations (NX-156), radar blinks (Q-SIM-82)
FORMAT_VERSION = 20
_MM = 1000.0  # metres -> millimetres; m/s -> mm/s
_MICRO = 1e6  # ADR-0002's 1e-6 step for other floats (fuel)
_MILLI_UNIT = 1000  # thousandths of a stock unit per unit
_MAX_ABS = 1e9  # m or m/s; keeps mm quantization well inside int64
_BLOBS = "blobs"
_BLOB_RUNS = "blob_runs"
_BOARDS = "boards"
_COOLDOWN = "cooldown"
_LOST = "lost"
_CAPTURE = "capture"
_CAMPAIGN = "campaign"
_CONTACTS = "contacts"
_CREW_MARKERS = "crew_markers"
_DEFENSE_HP = "defense_hp"
_DEFENSE_DOWN = "defense_down"
_DEFENSE_DRAIN = "defense_drain"
_DIRECTOR = "director"
_MARKERS = "markers"
_OBJECTIVE = "objective"
_ENTITIES = "entities"
_CALLSIGNS = "callsigns"
_RESPAWN_LEFT = "respawn_left"
_SHOTS = "shots"
_NEXT_JOB_ID = "next_job_id"
_NEXT_MARKER_ID = "next_marker_id"
_NEXT_SHOT_ID = "next_shot_id"
_RESERVE_QUEUE = "reserve_queue"
_OWNER = "owner"
_NEXT_ENTITY_ID = "next_entity_id"
_NEXT_EVENT_SEQ = "next_event_seq"
_RNG = "rng"
_SIGINT_AGE = "sigint_age"
_STOCK = "stock"
_V = "v"
# The dedupe-key prefix of each job kind the board generates (`nexus.core.tasking_gen`); a key with
# one must name the job's own target (`load` checks it). The Director's STAGE and CAPTURE (and its
# other jobs) use `op:` keys, which name nothing the check could verify.
JOB_KEY_PREFIX = {
    "RESUPPLY": "resupply:", "DEFEND": "defend:", "STRIKE": "strike:",
    "ASSIST_OBJECTIVE": "assist:", "SCOUT": "scout:", "ESCORT_CONVOY": "escort:",
}  # fmt: skip
_WORLD_KEYS = (
    _BLOB_RUNS,
    _BLOBS,
    _BOARDS,
    _CALLSIGNS,
    _CAMPAIGN,
    _CAPTURE,
    _CONTACTS,
    _COOLDOWN,
    _CREW_MARKERS,
    _DEFENSE_DOWN,
    _DEFENSE_DRAIN,
    _DEFENSE_HP,
    _DIRECTOR,
    _ENTITIES,
    _LOST,
    _MARKERS,
    _NEXT_ENTITY_ID,
    _NEXT_EVENT_SEQ,
    _NEXT_JOB_ID,
    _NEXT_MARKER_ID,
    _NEXT_SHOT_ID,
    _OBJECTIVE,
    _OWNER,
    _RESERVE_QUEUE,
    _RESPAWN_LEFT,
    _RNG,
    _SHOTS,
    _SIGINT_AGE,
    _STOCK,
    _V,
)
_VEC_KEYS = frozenset({"pos", "vel", "orbit"})
_PATH = "path"
_FUEL = "fuel"


def _literal_values(alias: Any) -> tuple[str, ...]:
    """The allowed strings of a generated `type X = Literal[...]` (optionally Annotated)."""
    value = alias.__value__
    if get_origin(value) is Annotated:
        value = get_args(value)[0]
    return get_args(value)


_CALLSIGN = re.compile(r"[A-Z][A-Z0-9-]{2,11}")  # ids.json Callsign
_UNIT_KINDS = _literal_values(UnitKind)
SIDES = cast(tuple[Side, ...], _literal_values(Side))
_OWNER_KINDS = _literal_values(OwnerKind)
_NODE_OWNERS = _literal_values(NodeOwner)
_PAUSE_REASONS = _literal_values(PauseReasonCategory)
_PAUSE_SUB_REASONS = _literal_values(StaffPauseSubReason)
_DAMAGE_STATES = _literal_values(DamageState)
_ALT_BANDS = _literal_values(AltBand)
_JOB_KINDS = _literal_values(JobKind)
_TIERS = cast(tuple[ThreatTier, ...], _literal_values(ThreatTier))


@dataclass(frozen=True, slots=True)
class Vec2:
    """A point or vector in metres (or m/s), float64. Ints are stored as floats."""

    x: float
    y: float

    def __post_init__(self) -> None:
        for name in ("x", "y"):
            v = getattr(self, name)
            number = isinstance(v, int | float) and not isinstance(v, bool)
            # Magnitude first: math.isfinite raises OverflowError on huge ints.
            if not (number and abs(v) <= _MAX_ABS and math.isfinite(v)):
                raise ValueError(f"Vec2.{name} must be finite with |v| <= {_MAX_ABS:g}, got {v!r}")
            object.__setattr__(self, name, float(v))


_ZERO = Vec2(0.0, 0.0)
# The STATE-MACHINES §4.1 states in code (NX-368, aircraft only). Kernel-internal until a frame or
# event carries a unit state; then it moves to contracts/common/enums.json.
type UnitState = Literal["LANDED", "EN_ROUTE", "ON_STATION", "RTB"]
_UNIT_STATES = get_args(UnitState.__value__)
# An explicit order (GAMEPLAY §1b, Q-GP-19, Q-GP-23) suspends auto-tasking: HOLD from a JOIN with
# `hold` (never completes), GOTO from a JOIN with a node target (completes on arrival), FOLLOW from
# a JOIN with a follow target (ends when `follow_id` does, Q-GP-31).
type Order = Literal["HOLD", "GOTO", "FOLLOW"]
_ORDERS = get_args(Order.__value__)
# A SIGINT blob's size bucket (FOG-OF-WAR Tier 1); kernel-internal until BlobView is a contract.
type BlobSize = Literal["S", "M", "L"]
_BLOB_SIZES = get_args(BlobSize.__value__)
_BLOB_ID = re.compile(r"(0|[1-9][0-9]*)-(0|[1-9][0-9]*)")  # <refresh_tick>-<cell_index> (FOW-2)


@dataclass(slots=True)
class Entity:
    """A unit or facility. `id` is allocated by `World.spawn` and must not change."""

    id: int
    kind: UnitKind
    side: Side
    owner_kind: OwnerKind
    commander_id: str | None
    callsign: str | None
    pos: Vec2
    vel: Vec2  # m/s
    hp: int  # >= 1: an entity at 0 is destroyed and removed (NX-124)
    # Remaining waypoints (SIM-CORE §4): node ids, or Vec2 for AIR. A GROUND unit is on the road
    # edge from `last_node` (the node it last reached or spawned at) to `path[0]` (NX-121).
    path: list[str | Vec2] = field(default_factory=list)
    last_node: str | None = None
    # STATE-MACHINES §4.1 state; only aircraft have one yet (NX-368), None for other domains.
    state: UnitState | None = None
    fuel: float | None = None  # aircraft: world seconds of flight left (NX-368)
    orbit: Vec2 | None = None  # the centre an idle ON_STATION aircraft circles (NX-368)
    base_id: str | None = None  # facilities: the node they belong to (Q-GP-25)
    variant: str | None = None  # facilities: the theater's catalog variant, e.g. SAM
    # FOW-11: None for a kind that never emits; True emitting, False dark (DecoyBlink, later).
    emitting: bool | None = None
    # Tasking (NX-374): the explicit order that keeps the board off this unit, and the job whose
    # claim it holds. A claim and `job_id` always match while the unit lives.
    order: Order | None = None
    job_id: int | None = None
    # Follow (NX-374 part 2, Q-GP-31): the direct leader's entity id. Set with order FOLLOW, or by
    # the claim of an escort job; kept off any Disabled leader and re-attached when one leaves.
    follow_id: int | None = None
    pickup: str | None = (
        None  # an empty truck on a resupply job: the source it drives to and loads at
    )
    # Carriers (LOGI_TRUCK, ENEMY_CONVOY; NX-123): stock units aboard, else None. `unload_milli` is
    # the thousandths of a unit unloaded so far toward the next whole one, 0 to 999.
    cargo: int | None = None
    unload_milli: int = 0
    delivered: int = 0  # units unloaded in this stop; SupplyDelivered reports it when it ends
    # Of `delivered`, the units spent on the node's defenses because its stock was full (Q-SIM-71);
    # the stop's end reports them as `SupplyConsumed{REPAIR}`.
    defended: int = 0
    # Aircraft refuelling at a base (NX-123 part 2): `rearm_milli` the thousandths of a stock unit
    # bought toward the next whole one, 0 to 999; `rearm_spent` the whole units debited in this
    # stop (SupplyConsumed reports it when it ends); `stalled` that RearmStalled was emitted.
    rearm_milli: int = 0
    rearm_spent: int = 0
    stalled: bool = False
    # The rest of a rearm stop's progress (NX-124 part 2, `nexus.core.rearm`), all exact integers:
    # `ammo_credit` the stock bought for rounds not yet whole, in 1/(1000 x the loadout's rounds)
    # stock; `repair_milli` the thousandths of an hp repaired toward the next whole one, 0 to 999;
    # `repair_debt` the repaired hp not yet paid for, in 1/(the kind's price denominator) stock.
    ammo_credit: int = 0
    repair_owed: int = 0  # thousandths of a stock unit bought for repair, 0 to 999
    repair_spent: int = 0  # whole units debited for repair in this stop (SupplyConsumed REPAIR)
    repair_milli: int = 0
    repair_debt: int = 0
    # Combat (NX-124, COMBAT). `damage_state` follows `hp` (CB-6). `alt_band`: an aircraft's band
    # (its default; no command changes it). `ammo` and `reload` are per weapon, in the unit's
    # loadout order (`CombatRules.loadout`): rounds left, and running ticks until it may fire again.
    # `wreck_left`: running ticks until a Disabled non-facility is removed (CB-7), else None.
    damage_state: DamageState = "HEALTHY"
    alt_band: AltBand | None = None
    ammo: list[int] = field(default_factory=list)
    reload: list[int] = field(default_factory=list)
    wreck_left: int | None = None
    # Recent hits on this unit, oldest first: [shooter id, running tick] pairs, kept for
    # `combat.assist_window_s` (assists, CB-5a). Facilities never die, so they keep none.
    hits: list[list[int]] = field(default_factory=list)
    # Who fired at this unit lately: [shooter id, running tick] pairs, oldest first, kept for
    # `tasking.escort_threat_memory_s` and pruned when the next shot at the unit is recorded.
    fired_by: list[list[int]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Shot:
    """A fired shot in flight (COMBAT CB-2): not an entity. `impact_tick` is on the campaign clock
    (`Campaign.running_ticks` of the tick it lands in), so a pause delays it with the world."""

    id: int
    shooter: int
    target: int | None  # an entity id; None for a shot at `node`'s defenses (CB-10)
    weapon_id: str
    impact_tick: int
    node: str | None = None


@dataclass(slots=True)
class CrewMarker:
    """A downed crew on the map (COMBAT CB-8, GAMEPLAY §6a): `entity_id` the unit it belonged to,
    `pos` where the unit was lost. `expires` is the campaign-clock tick (running ticks) it is
    removed on, `combat.crew_marker_min` after the loss."""

    id: int
    entity_id: int
    side: Side
    pos: Vec2
    expires: int


@dataclass(slots=True)
class Contact:
    """One enemy entity a side knows of (FOG-OF-WAR Tier 2, FOW-6a): kind, position and velocity
    (its heading) as of the last pass that tracked it. `age` is None while tracked; once lost it is
    a last-known track and `age` counts the running ticks since (FOW-9). `painted`: a recon unit
    of the side painted it on that pass (Q-FOW-6); always False on a last-known track."""

    kind: UnitKind
    pos: Vec2
    vel: Vec2
    age: int | None = None
    painted: bool = False


@dataclass(slots=True)
class FacilityMarker:
    """An enemy facility a side has discovered (FOW-13): permanent; its details are as of
    `confirmed_tick`, the last pass that observed the site. `ring_m` is the site's longest AIR
    weapon range, m, or None; `state` its damage state then (NX-124 part 3)."""

    kind: UnitKind
    variant: str | None
    pos: Vec2
    emitting: bool | None
    confirmed_tick: int
    ring_m: int | None
    state: DamageState


@dataclass(frozen=True, slots=True)
class Blob:
    """A SIGINT blob (FOG-OF-WAR Tier 1, FOW-2): `id` is `<refresh_tick>-<cell_index>`, `pos` the
    cell's centre and `size` a bucket of how many units it holds; never an entity id, an exact
    count or an exact position."""

    id: str
    pos: Vec2
    size: BlobSize


@dataclass(slots=True)
class CaptureBar:
    """A node's capture bar (STATE-MACHINES §4.2): `side` is the side filling it and `progress` the
    millionths of a percent filled, 1 to `CAPTURE_FULL - 1`; a node with no progress has no bar."""

    side: Side
    progress: int


@dataclass(slots=True)
class Claim:
    """One unit's claim on a job slot (TB-1). `at` is the running tick of its last progress (the
    lease clock, `tasking.claim_lease_s`); `active` once progress was seen (CLAIMED -> ACTIVE)."""

    at: int
    active: bool = False


@dataclass(slots=True)
class Job:
    """A Tasking Board job (GAMEPLAY §1b, TB-1..TB-9). The target is a node, or
    a SIGINT blob with its cell centre `pos` (a scout job). `urgency` is thousandths, 1000 to the
    configured maximum. `created` and `expires` are on the campaign clock (running ticks);
    `expires` None for an objective's job (`objective` is that objective's id). `depends_on`: the
    job that must be DONE before this one can be claimed (TB-8). Terminal jobs leave the board."""

    id: int
    kind: JobKind
    key: str
    slots: int
    urgency: int
    created: int
    node: str | None = None
    blob: str | None = None
    pos: Vec2 | None = None
    expires: int | None = None
    depends_on: int | None = None
    objective: int | None = None
    entity: int | None = None  # an escort job: the truck it covers
    restarts: int = 0  # a CAPTURE job's fresh expiries while its claimants drove (Q-SIM-84)
    claims: dict[int, Claim] = field(default_factory=dict)  # entity id -> claim, claim order

    @property
    def state(self) -> Literal["OPEN", "CLAIMED", "ACTIVE"]:
        if not self.claims:
            return "OPEN"
        return "ACTIVE" if any(c.active for c in self.claims.values()) else "CLAIMED"


@dataclass(slots=True)
class Campaign:
    """`tick` counts every tick; `running_ticks` only the unpaused ones: the campaign clock
    (STATE-MACHINES C-1, NX-126). `hold_ticks` is the current run of running ticks the coalition
    has held the victory share of strategic nodes; `held_ticks_*` sum each side's held strategic
    node count over the running ticks (the time-limit score keeps them exact)."""

    id: str  # CampaignId
    seed: int
    config_hash: str
    tick: int = 0
    clock_paused: bool = False
    running_ticks: int = 0
    pause_reason: PauseReasonCategory | None = None  # set exactly while clock_paused
    pause_sub_reason: StaffPauseSubReason | None = None  # only with reason STAFF
    ended: bool = False  # CampaignEnded was emitted (C-2): the world is frozen, no command applies
    hold_ticks: int = 0
    held_ticks_coalition: int = 0
    held_ticks_enemy: int = 0
    objectives_issued: int = 0
    objectives_done: int = 0
    defeat_ticks: int = 0  # the run of running ticks the coalition sanctuary's defense hp is 0


@dataclass(slots=True)
class Objective:
    """The active timed objective (STATE-MACHINES §4.5): `hold` when the coalition owned the node
    when it was announced (it must still hold it at the deadline), else a capture. `deadline` is
    on the campaign clock (`Campaign.running_ticks`)."""

    id: int
    node_id: str
    deadline: int
    hold: bool


@dataclass(slots=True)
class DirectorState:
    """One side's Threat Director (THREAT-DIRECTOR §2-§5a, NX-155; `nexus.core.director`). Coalition
    power `cp` (an EMA) and `provocation` are whole millionths of a point, `pending` the provocation
    noted since the last decision window (`nexus.core.provocation`). `prov_level` and `ceiling`
    (0 PATTERN_OF_LIFE, 1 ALPHA, 2 BRAVO) hold the hysteresis; `dwell` is the running ticks in
    `tier`, added a window at a time and held at `min_dwell_s`; `windows` the decision windows run;
    `budget` this window's. The sector of the most recent noted provocation is
    `last_provocation_sector`, at running tick `last_provocation_tick`.

    Threat memory (THREAT-DIRECTOR §2, NX-156): decaying counters in millionths of an event,
    `convoy_attacks` and `radar_strikes` whole, `node_losses` and `recon_losses` by sector id (a
    sector with 0 has no entry). `lost` maps a node the side lost to the running tick it fell, kept
    for the Retake window; `adapted` maps an adaptation category to the sector announced up. `dark`
    maps a base whose radar blinked to the running tick it comes back on, `blink_ready` to the tick
    its radar may blink again (Q-SIM-82). `idle` maps a Director unit with no job (its id as text)
    to the running tick it was first seen so, for `director.idle_retire_s` (Q-SIM-84)."""

    cp: int = 0
    provocation: int = 0
    pending: int = 0
    tier: ThreatTier = "PATTERN_OF_LIFE"
    prov_level: int = 0
    ceiling: int = 1
    dwell: int = 0
    windows: int = 0
    budget: int = 0
    last_provocation_sector: str | None = None
    last_provocation_tick: int = 0
    convoy_attacks: int = 0
    radar_strikes: int = 0
    node_losses: dict[str, int] = field(default_factory=dict)
    recon_losses: dict[str, int] = field(default_factory=dict)
    lost: dict[str, int] = field(default_factory=dict)
    adapted: dict[str, str] = field(default_factory=dict)
    dark: dict[str, int] = field(default_factory=dict)
    blink_ready: dict[str, int] = field(default_factory=dict)
    idle: dict[str, int] = field(default_factory=dict)  # entity id (as text, msgpack) -> tick


_DIRECTOR_KEYS = tuple(f.name for f in fields(DirectorState))


_ENTITY_KEYS = tuple(f.name for f in fields(Entity))
_JOB_KEYS = tuple(f.name for f in fields(Job))
_CAMPAIGN_KEYS = tuple(f.name for f in fields(Campaign))


class World:
    """The whole sim state. Entity ids start at 1 and are never reused (SC-4).

    `_entities` is insertion-ordered by id: ids are allocated monotonically and only ever removed,
    so iterating the dict is id order without sorting (`load` checks the same for snapshots).
    """

    __slots__ = (
        "_entities",
        "_next_entity_id",
        "_next_event_seq",
        "_next_job_id",
        "_next_marker_id",
        "_next_shot_id",
        "blob_runs",
        "blobs",
        "boards",
        "callsigns",
        "campaign",
        "capture",
        "contacts",
        "cooldown",
        "crew_markers",
        "defense_down",
        "defense_drain",
        "defense_hp",
        "director",
        "group_threat",
        "lost",
        "markers",
        "objective",
        "owner",
        "reserve_queue",
        "respawn_left",
        "rng",
        "rules",
        "shots",
        "sigint_age",
        "speed_cap",
        "stock",
    )

    def __init__(self, campaign: Campaign, rng: SimRng, rules: Rules | None = None) -> None:
        self.campaign = campaign
        self.rng = rng
        self.rules = rules  # None: no unit may have a path (movement raises)
        self._entities: dict[int, Entity] = {}
        self._next_entity_id = 1
        self._next_event_seq = 1
        self._next_shot_id = 1
        self._next_marker_id = 1
        self._next_job_id = 1
        # Side -> its Tasking Board: live jobs by id, ascending (= posting order); only
        # `nexus.core.tasking` changes it (NX-374). One id counter for both sides.
        self.boards: dict[Side, dict[int, Job]] = {side: {} for side in SIDES}
        # Node -> the running tick it was lost to the other side (capture sets it; the board prunes
        # it after `tasking.counterattack_window_min`, Q-GD-31), and per side the scouted cells not
        # posted again until a running tick (`tasking.scout_cooldown_min`, Q-SIM-75).
        self.lost: dict[str, int] = {}
        self.cooldown: dict[Side, dict[str, int]] = {side: {} for side in SIDES}
        # Downed-crew markers by id, ascending (= creation order); `combat` removes the expired.
        self.crew_markers: dict[int, CrewMarker] = {}
        # commander_id -> running ticks left of its respawn delay, always >= 1 (GP-2, SC-11).
        # `record_loss` sets it; the `lifecycle` system counts it down and deletes it at 0.
        self.respawn_left: dict[str, int] = {}
        # The reserve queue (GP-3, STATE-MACHINES §4.1): queued JOINs, head first, one per
        # commander (U-4). The JOIN handler appends; `lifecycle` serves from the head.
        self.reserve_queue: list[JoinCommand] = []
        # commander_id -> callsign set by SYS_SET_CALLSIGN (Q-SIM-39); JOIN copies it onto the
        # unit. Grows per commander; FORGET (later) removes the entry.
        self.callsigns: dict[str, str] = {}
        # Side -> enemy entity id -> what that side knows of it, in id order (FOW-5, FOW-6a).
        # Only the `sensing` system writes it; `nexus.core.fog` reads it.
        self.contacts: dict[Side, dict[int, Contact]] = {side: {} for side in SIDES}
        # Side -> enemy facility id -> its discovered marker, in id order (FOW-13); never removed.
        self.markers: dict[Side, dict[int, FacilityMarker]] = {side: {} for side in SIDES}
        # Side -> its SIGINT blobs from the last refresh, by cell index (Tier 1); replaced whole.
        self.blobs: dict[Side, tuple[Blob, ...]] = {side: () for side in SIDES}
        # Side -> blob cell index -> the consecutive SIGINT refreshes a blob was in that cell (the
        # sensing system rebuilds it with the blobs); the board posts a scout only from 2 (NX-374).
        self.blob_runs: dict[Side, dict[str, int]] = {side: {} for side in SIDES}
        self.sigint_age = 0  # running ticks since the last SIGINT refresh (FOW-9)
        # Node id -> whole stock units, for the nodes with finite stock (SANCTUARY nodes are
        # infinite by rule and absent). `start_campaign` fills it from the theater (NX-123).
        self.stock: dict[str, int] = {}
        # Node id -> its live owner, in id order (NX-125): the theater's start owners, then only
        # the `capture` system changes it. A SANCTUARY never does (N-4).
        self.owner: dict[str, NodeOwner] = dict(rules.supply.start_owner) if rules else {}
        # Node id -> its capture bar, only for nodes with progress, in id order.
        self.capture: dict[str, CaptureBar] = {}
        # Node id -> defense hp, and the starvation drain's carry (hp x ticks, below one game minute
        # of ticks), for the nodes with defenses, in id order (NX-124 part 3, Q-SIM-71): an owned
        # node starts full, a NEUTRAL one at 0.
        defense = rules.defense if rules else None
        self.defense_hp: dict[str, int] = (
            {n: 0 if self.owner[n] == "NEUTRAL" else m for n, m in defense.max_hp.items()}
            if defense else {}
        )  # fmt: skip
        self.defense_drain: dict[str, int] = dict.fromkeys(self.defense_hp, 0)
        # Nodes whose defense hp reached 0 and has not been rebuilt to full since: they announced
        # `NodeDefensesDown` and will announce `NodeDefensesRestored` once (no per-hit spam).
        self.defense_down: set[str] = set()
        # Side -> its Threat Director (NX-155); only the ENEMY's runs until NX-375, the other stays
        # at its start values.
        self.director: dict[Side, DirectorState] = {side: DirectorState() for side in SIDES}
        self.objective: Objective | None = None  # NX-126; at most one (O-1)
        # Pending shots in `(impact_tick, id)` order (CB-2); only the `combat` system changes it.
        self.shots: list[Shot] = []
        # Derived afresh every running tick by `nexus.core.follow.steer` before `movement` and
        # `combat` read it, so neither is state (no snapshot, no hash): entity id -> the base speed
        # cap (m/s, before the road's `speed_mult`) of a follower or a formation member, and
        # armed follower id -> the entity ids of the threats to its group (Q-SIM-76).
        self.speed_cap: dict[int, float] = {}
        self.group_threat: dict[int, tuple[int, ...]] = {}

    @classmethod
    def new(cls, campaign: Campaign, rules: Rules | None = None) -> Self:
        return cls(campaign, SimRng(campaign.seed), rules)

    def spawn(
        self,
        kind: UnitKind,
        side: Side,
        owner_kind: OwnerKind,
        pos: Vec2,
        *,
        commander_id: str | None = None,
        callsign: str | None = None,
        vel: Vec2 = _ZERO,
        hp: int | None = None,
        variant: str | None = None,
    ) -> Entity:
        """A new entity at full health and a full load (NX-124): hp, aircraft altitude band and
        ammo come from the world's combat rules; `hp` overrides the catalog's (tests). Without
        combat rules `hp` is required and the entity carries no weapons."""
        combat = self.rules.combat if self.rules else None
        if combat is None and hp is None:
            raise ValueError("spawn needs hp when the world has no combat rules")
        entity = Entity(
            self._next_entity_id, kind, side, owner_kind, commander_id, callsign, pos, vel,
            hp if hp is not None else 0, variant=variant,
        )  # fmt: skip
        if combat is not None:
            stats = combat.units[kind]
            entity.hp = stats.hp if hp is None else hp
            entity.alt_band = stats.alt_band
            entity.ammo = [w.ammo for w in combat.loadout(kind, variant)]
            entity.reload = [0] * len(entity.ammo)
        self._entities[entity.id] = entity
        self._next_entity_id += 1
        return entity

    def get(self, entity_id: int) -> Entity:
        return self._entities[entity_id]

    def find(self, entity_id: int) -> Entity | None:
        """The entity, or None once it is gone (destroyed or despawned)."""
        return self._entities.get(entity_id)

    def next_job_id(self) -> int:
        """The next Tasking Board job id, starting at 1."""
        job_id = self._next_job_id
        self._next_job_id += 1
        return job_id

    def next_shot_id(self) -> int:
        """The next shot id, starting at 1 (CB-2)."""
        shot_id = self._next_shot_id
        self._next_shot_id += 1
        return shot_id

    def remove(self, entity_id: int) -> None:
        """Remove an entity. Its followers take its own leader (Q-GP-33), or drop their order and
        fall back to the board; an escort-job follower just drops (its job ends with the truck).
        shortcut: a scan of every entity per removal; index followers if removals get hot."""
        gone = self._entities.pop(entity_id)
        for f in self._entities.values():
            if f.follow_id == entity_id:
                f.follow_id = gone.follow_id if f.order == "FOLLOW" else None
                if f.follow_id is None and f.order == "FOLLOW":
                    f.order = None

    def record_loss(self, commander_id: str) -> None:
        """A commander's unit was lost this tick: its respawn delay starts (GP-2).

        The hook for the systems that destroy or wreck units (NX-124, STATE-MACHINES §4.1). Call it
        before `lifecycle` counts down in the same tick (a loss inside `lifecycle` comes before its
        countdown): then a loss on tick L with a delay of D ticks allows a JOIN on tick L + D.
        """
        if self.rules is None:
            raise ValueError("record_loss needs the world's rules")
        if self.rules.respawn_delay_ticks > 0:
            self.respawn_left[commander_id] = self.rules.respawn_delay_ticks

    @property
    def frozen(self) -> bool:
        """The world's clock is stopped: paused (C-1), or the campaign ended (C-2). Every
        time-driven system returns early while this holds (SC-11)."""
        return self.campaign.clock_paused or self.campaign.ended

    def viewer_units(self) -> int:
        """Live COMMANDER-owned units; AUTO units are COMMANDER-owned too, so they count (Q-ALN-9).
        The idle-floor checks (capture, defense, campaign) read "nobody plays" from this: once the
        AUTO state exists they need a predicate that leaves AUTO units out (Q-ALN-8/9, Q-SIM-72).
        shortcut: a scan of every entity; keep a count if the SC-10 benchmark shows it in budget."""
        return sum(e.owner_kind == "COMMANDER" for e in self._entities.values())

    def landing_bases(self, side: Side) -> tuple[str, ...]:
        """The AIRBASE and SANCTUARY nodes `side` owns now, by id: where its aircraft may land."""
        if self.rules is None:
            return ()
        return tuple(n for n in self.rules.landing_nodes if self.owner.get(n) == side)

    def entities(self) -> Iterator[Entity]:
        """All entities in ascending id order (SC-4). Do not spawn or remove while iterating."""
        return iter(self._entities.values())

    def next_event_seq(self) -> int:
        """The next campaign-wide `event_seq` (SC-14), starting at 1."""
        seq = self._next_event_seq
        self._next_event_seq += 1
        return seq

    def __len__(self) -> int:
        return len(self._entities)


def release_claim(world: World, job: Job, entity_id: int, out: list[Event]) -> None:
    """Free `entity_id`'s slot of `job` with `JobReleased` (lease, preemption, eviction, or the
    unit's removal): the unit, if it lives, holds no job and no pickup."""
    del job.claims[entity_id]
    e = world.find(entity_id)
    if e is not None:
        e.job_id = e.pickup = None
        if e.order != "FOLLOW":
            e.follow_id = None  # an escort claim ends with its follow order
    out.append(
        JobReleased.model_construct(
            kind="JobReleased",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            job_id=job.id,
            entity_id=entity_id,
        )
    )


def drop_claim(world: World, e: Entity, out: list[Event]) -> None:
    """Call before removing `e`: its claim, if any, is released now, so the slot is right before the
    next board pass."""
    job = None if e.job_id is None else world.boards[e.side].get(e.job_id)
    if job is not None and e.id in job.claims:
        release_claim(world, job, e.id, out)


def lose_unit(
    world: World,
    e: Entity,
    out: list[Event],
    killer_id: int | None = None,
    assist_ids: list[int] | None = None,
) -> None:
    """A unit lost: it is removed, its commander's respawn delay starts and `UnitDestroyed` is
    emitted. `killer_id` is the shooter of a killing hit; None for fuel exhaustion or a captured
    base. `assist_ids`: the other shooters that hit it recently (sorted, at most 32). A unit that
    was never Disabled rolls its crew now (CB-8); a wreck rolled when it became Disabled."""
    if e.delivered and e.last_node is not None:
        end_stop(world, e, e.last_node, out)  # an open unloading stop reports its units first
    end_rearm(world, e, out)  # a unit lost mid-stop still reports what its stop cost
    drop_claim(world, e, out)
    world.remove(e.id)
    if e.commander_id is not None:
        world.record_loss(e.commander_id)
    out.append(
        UnitDestroyed.model_construct(
            kind="UnitDestroyed",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            entity_id=e.id,
            killer_id=killer_id,
            assist_ids=assist_ids or [],
            side=e.side,
        )
    )
    if e.damage_state != "DISABLED":
        roll_crew(world, e, out)


def consumed(
    world: World, node: str, amount: int, cause: Literal["SPAWN", "REARM", "REPAIR"]
) -> SupplyConsumed:
    return SupplyConsumed.model_construct(
        kind="SupplyConsumed",
        tick=world.campaign.tick + 1,
        event_seq=world.next_event_seq(),
        campaign_id=world.campaign.id,
        node_id=node,
        amount=amount,
        cause=cause,
    )


def end_stop(world: World, e: Entity, node: str, out: list[Event]) -> None:
    """Report the stop's delivery (none for 0 units) and reset its count; unload_milli carries.
    Units that went straight into the node's defenses (its stock was full) are also reported as
    one `SupplyConsumed{REPAIR}`, so stock + cargo + consumed stays exact."""
    if e.delivered:
        out.append(
            SupplyDelivered.model_construct(
                kind="SupplyDelivered",
                tick=world.campaign.tick + 1,
                event_seq=world.next_event_seq(),
                campaign_id=world.campaign.id,
                node_id=node,
                amount=e.delivered,
                carrier_id=e.id,
                commander_id=e.commander_id,
            )
        )
    if e.defended:
        out.append(consumed(world, node, e.defended, "REPAIR"))
    e.delivered = e.defended = 0


def end_rearm(world: World, e: Entity, out: list[Event]) -> None:
    """Report a rearm stop's spend (`REARM` for fuel and ammo, `REPAIR` for hp; none for 0 units)
    and reset the stop; the carries stay. Also called when the entity is removed mid-stop."""
    node = e.base_id or e.last_node
    if node is not None:
        if e.rearm_spent:
            out.append(consumed(world, node, e.rearm_spent, "REARM"))
        if e.repair_spent:
            out.append(consumed(world, node, e.repair_spent, "REPAIR"))
    e.rearm_spent = e.repair_spent = 0
    e.stalled = False


def set_damage_state(world: World, e: Entity, state: DamageState, out: list[Event]) -> None:
    """Move `e` to `state` with its `UnitDamageStateChanged`: a hit worsens, repair improves."""
    out.append(
        UnitDamageStateChanged.model_construct(
            kind="UnitDamageStateChanged",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            entity_id=e.id,
            from_=e.damage_state,
            to=state,
        )
    )
    e.damage_state = state


def roll_crew(world: World, e: Entity, out: list[Event]) -> None:
    """The unit's one crew-survival roll (COMBAT CB-8, Q-SIM-68), at the first of Disabled or
    Destroyed. A unit with `crew` 0 (a facility, a UAV) draws nothing. Otherwise exactly one draw
    on the `combat` stream: below the kind's `combat.crew_survival` the crew is DOWNED, a marker
    at the unit's position for `combat.crew_marker_min` plus a `CrewDowned`; else LOST, nothing."""
    cr = world.rules.combat if world.rules else None
    stats = cr.units.get(e.kind) if cr else None
    if cr is None or stats is None or not stats.crew:
        return
    if world.rng.stream(RngStream.COMBAT).random() >= stats.crew_survival:
        return
    marker = CrewMarker(
        world._next_marker_id, e.id, e.side, e.pos,
        world.campaign.running_ticks + 1 + cr.crew_marker_ticks,
    )  # fmt: skip
    world._next_marker_id += 1
    world.crew_markers[marker.id] = marker
    out.append(
        CrewDowned.model_construct(
            kind="CrewDowned",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            marker_id=marker.id,
            entity_id=e.id,
            side=e.side,
            pos=Pos.model_construct(x_m=round(e.pos.x), y_m=round(e.pos.y)),
        )
    )


def _xy(v: Vec2, quantize: bool) -> list[Any]:
    return [round(v.x * _MM), round(v.y * _MM)] if quantize else [v.x, v.y]


def _value(e: Entity, key: str, quantize: bool) -> Any:
    value = getattr(e, key)
    if value is None:
        return None
    if key in _VEC_KEYS:
        return _xy(value, quantize)
    if key == _PATH:
        return [p if isinstance(p, str) else _xy(p, quantize) for p in e.path]
    if key == _FUEL and quantize:
        return round(value * _MICRO)
    return value


def _entity_data(e: Entity, quantize: bool) -> dict[str, Any]:
    return {k: _value(e, k, quantize) for k in sorted(_ENTITY_KEYS)}


def _contacts_data(world: World, quantize: bool) -> dict[str, Any]:
    return {
        side: [
            {"age": c.age, "id": i, "kind": c.kind, "painted": c.painted,
             "pos": _xy(c.pos, quantize), "vel": _xy(c.vel, quantize)}
            for i, c in sorted(world.contacts[side].items())
        ]
        for side in SIDES
    }  # fmt: skip


def _markers_data(world: World, quantize: bool) -> dict[str, Any]:
    return {
        side: [
            {"confirmed_tick": m.confirmed_tick, "emitting": m.emitting, "id": i, "kind": m.kind,
             "pos": _xy(m.pos, quantize), "ring_m": m.ring_m, "state": m.state,
             "variant": m.variant}
            for i, m in sorted(world.markers[side].items())
        ]
        for side in SIDES
    }  # fmt: skip


def _capture_data(world: World) -> dict[str, Any]:
    return {n: {"progress": b.progress, "side": b.side} for n, b in sorted(world.capture.items())}


def _crew_markers_data(world: World, quantize: bool) -> list[Any]:
    return [
        {"entity_id": m.entity_id, "expires": m.expires, "id": i, "pos": _xy(m.pos, quantize),
         "side": m.side}
        for i, m in world.crew_markers.items()
    ]  # fmt: skip


def _blobs_data(world: World, quantize: bool) -> dict[str, Any]:
    return {
        side: [{"id": b.id, "pos": _xy(b.pos, quantize), "size": b.size} for b in world.blobs[side]]
        for side in SIDES
    }


def _job_data(j: Job, quantize: bool) -> dict[str, Any]:
    data = {k: getattr(j, k) for k in _JOB_KEYS}
    data["claims"] = [[i, c.at, c.active] for i, c in sorted(j.claims.items())]
    data["pos"] = None if j.pos is None else _xy(j.pos, quantize)
    return dict(sorted(data.items()))


def _boards_data(world: World, quantize: bool) -> dict[str, Any]:
    return {side: [_job_data(j, quantize) for j in world.boards[side].values()] for side in SIDES}


def _sorted(value: Any) -> Any:
    """Plain JSON data with every dict's keys sorted, at any depth."""
    if isinstance(value, dict):
        return {k: _sorted(value[k]) for k in sorted(value)}
    return [_sorted(v) for v in value] if isinstance(value, list) else value


def to_canonical(world: World, *, quantize: bool) -> dict[str, Any]:
    """Plain data with sorted keys and entities in id order; quantized for the hash only."""
    data = {
        _BLOB_RUNS: {s: dict(sorted(r.items())) for s, r in world.blob_runs.items()},
        _BLOBS: _blobs_data(world, quantize),
        _BOARDS: _boards_data(world, quantize),
        _CALLSIGNS: dict(sorted(world.callsigns.items())),
        _COOLDOWN: {s: dict(sorted(c.items())) for s, c in world.cooldown.items()},
        _LOST: dict(sorted(world.lost.items())),
        _CAMPAIGN: {k: getattr(world.campaign, k) for k in sorted(_CAMPAIGN_KEYS)},
        _CAPTURE: _capture_data(world),
        _CONTACTS: _contacts_data(world, quantize),
        _CREW_MARKERS: _crew_markers_data(world, quantize),
        _DEFENSE_DOWN: sorted(world.defense_down),
        _DEFENSE_DRAIN: dict(sorted(world.defense_drain.items())),
        _DEFENSE_HP: dict(sorted(world.defense_hp.items())),
        _DIRECTOR: {s: _sorted(asdict(d)) for s, d in world.director.items()},
        _ENTITIES: [_entity_data(e, quantize) for e in world.entities()],
        _MARKERS: _markers_data(world, quantize),
        _OBJECTIVE: None if world.objective is None else asdict(world.objective),
        _OWNER: dict(sorted(world.owner.items())),
        _RESPAWN_LEFT: dict(sorted(world.respawn_left.items())),
        _RESERVE_QUEUE: [_sorted(c.model_dump(mode="json")) for c in world.reserve_queue],
        _NEXT_ENTITY_ID: world._next_entity_id,
        _NEXT_EVENT_SEQ: world._next_event_seq,
        _NEXT_JOB_ID: world._next_job_id,
        _NEXT_MARKER_ID: world._next_marker_id,
        _NEXT_SHOT_ID: world._next_shot_id,
        _RNG: {name: dict(sorted(s.items())) for name, s in world.rng.to_state().items()},
        _SHOTS: [asdict(s) for s in world.shots],
        _SIGINT_AGE: world.sigint_age,
        _STOCK: dict(sorted(world.stock.items())),
        _V: FORMAT_VERSION,
    }
    return dict(sorted(data.items()))


def state_hash(world: World) -> str:
    """Hex blake2b-256 of the quantized canonical msgpack (SIM-CORE §5)."""
    packed = msgpack.packb(to_canonical(world, quantize=True), use_bin_type=True)
    return hashlib.blake2b(packed, digest_size=32).hexdigest()


def save(world: World) -> bytes:
    """Lossless snapshot bytes (SC-9); the file format is `nexus.runtime.snapshot_file`."""
    return cast(bytes, msgpack.packb(to_canonical(world, quantize=False), use_bin_type=True))


# --- load: every value is checked; anything unexpected is a ValueError. ---


def _fields(value: object, keys: tuple[str, ...], what: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{what} must have exactly the keys {list(keys)}")
    return value


def _int(value: object, what: str, lo: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lo:
        raise ValueError(f"{what} must be an int >= {lo}, got {value!r}")
    return value


def _str(value: object, what: str, allowed: tuple[str, ...] = (), *, optional: bool = False) -> Any:
    """A string (one of `allowed` when given), or None when `optional`."""
    if (optional and value is None) or (isinstance(value, str) and value in (allowed or (value,))):
        return value
    raise ValueError(f"bad {what}: {value!r}")


def _vec(value: object, what: str) -> Vec2:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{what} must be [x, y]")
    return Vec2(value[0], value[1])


def _path(value: object, what: str) -> list[str | Vec2]:
    if not isinstance(value, list):
        raise ValueError(f"{what} must be a list")
    return [p if isinstance(p, str) else _vec(p, what) for p in value]


def _fuel(value: object, what: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, float) or not 0.0 <= value <= _MAX_ABS:
        raise ValueError(f"{what} must be a float in [0, {_MAX_ABS:g}], got {value!r}")
    return value


def _milli(value: object, what: str) -> int:
    n = _int(value, what)
    if n >= _MILLI_UNIT:
        raise ValueError(f"{what} must be below {_MILLI_UNIT}, got {value!r}")
    return n


def _int_list(value: object, what: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"{what} must be a list")
    return [_int(n, what) for n in value]


def _hits(value: object, what: str) -> list[list[int]]:
    if not isinstance(value, list):
        raise ValueError(f"{what} must be a list")
    pairs = []
    for pair in value:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(f"{what} entries must be [shooter, tick]")
        pairs.append([_int(pair[0], what, 1), _int(pair[1], what, 1)])
    if [p[1] for p in pairs] != sorted(p[1] for p in pairs):
        raise ValueError(f"{what} must be oldest first")
    return pairs


def _stock(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{_STOCK} must be a map")
    return {_str(k, "node id"): _int(v, _STOCK) for k, v in value.items()}


def _defense(value: object, what: str, owner: dict[str, NodeOwner]) -> dict[str, int]:
    """Whole numbers on nodes that exist; the upper bounds need the rules (`defense.validate`)."""
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be a map")
    out = {_str(k, "node id"): _int(v, what) for k, v in value.items()}
    if not set(out) <= set(owner):
        raise ValueError(f"{what}: a node that does not exist")
    return out


def _owner(value: object) -> dict[str, NodeOwner]:
    if not isinstance(value, dict):
        raise ValueError(f"{_OWNER} must be a map")
    return {_str(k, "node id"): _str(v, _OWNER, _NODE_OWNERS) for k, v in value.items()}


def _capture(value: object, owner: dict[str, NodeOwner]) -> dict[str, CaptureBar]:
    """A bar sits on a node with an owner that is not its own side, and has progress to show."""
    if not isinstance(value, dict):
        raise ValueError(f"{_CAPTURE} must be a map")
    bars: dict[str, CaptureBar] = {}
    for node, raw in value.items():
        d = _fields(raw, ("progress", "side"), _CAPTURE)
        bar = CaptureBar(_str(d["side"], "capture side", SIDES), _int(d["progress"], _CAPTURE, 1))
        if node not in owner or bar.progress >= CAPTURE_FULL or owner[node] == bar.side:
            raise ValueError(f"{_CAPTURE}.{node}: not a bar of a node it can capture")
        bars[_str(node, "node id")] = bar
    return bars


def _bool(value: object, what: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{what} must be a bool, got {value!r}")
    return value


# One check per field, labelled by the field name; keys match `fields(Entity)` / `fields(Campaign)`.
_ENTITY_CHECKS: dict[str, Callable[[object, str], Any]] = {
    "id": lambda v, k: _int(v, k, 1),
    "kind": lambda v, k: _str(v, k, _UNIT_KINDS),
    "side": lambda v, k: _str(v, k, SIDES),
    "owner_kind": lambda v, k: _str(v, k, _OWNER_KINDS),
    "commander_id": lambda v, k: _str(v, k, optional=True),
    "callsign": lambda v, k: _str(v, k, optional=True),
    "pos": _vec,
    "vel": _vec,
    "hp": lambda v, k: _int(v, k, 1),
    _PATH: _path,
    "last_node": lambda v, k: _str(v, k, optional=True),
    "state": lambda v, k: _str(v, k, _UNIT_STATES, optional=True),
    _FUEL: _fuel,
    "orbit": lambda v, k: None if v is None else _vec(v, k),
    "base_id": lambda v, k: _str(v, k, optional=True),
    "variant": lambda v, k: _str(v, k, optional=True),
    "emitting": lambda v, k: None if v is None else _bool(v, k),
    "order": lambda v, k: _str(v, k, _ORDERS, optional=True),
    "job_id": lambda v, k: None if v is None else _int(v, k, 1),
    "follow_id": lambda v, k: None if v is None else _int(v, k, 1),
    "pickup": lambda v, k: _str(v, k, optional=True),
    "cargo": lambda v, k: None if v is None else _int(v, k),
    "unload_milli": _milli,
    "delivered": lambda v, k: _int(v, k),
    "defended": lambda v, k: _int(v, k),
    "rearm_milli": _milli,
    "rearm_spent": lambda v, k: _int(v, k),
    "stalled": _bool,
    "ammo_credit": lambda v, k: _int(v, k),
    "repair_owed": _milli,
    "repair_spent": lambda v, k: _int(v, k),
    "repair_milli": _milli,
    "repair_debt": lambda v, k: _int(v, k),
    "damage_state": lambda v, k: _str(v, k, _DAMAGE_STATES),
    "alt_band": lambda v, k: _str(v, k, _ALT_BANDS, optional=True),
    "ammo": lambda v, k: _int_list(v, k),
    "reload": lambda v, k: _int_list(v, k),
    "wreck_left": lambda v, k: None if v is None else _int(v, k, 1),
    "hits": lambda v, k: _hits(v, k),
    "fired_by": lambda v, k: _hits(v, k),
}
_CAMPAIGN_CHECKS: dict[str, Callable[[object, str], Any]] = {
    "id": _str,
    "seed": _int,
    "config_hash": _str,
    "tick": _int,
    "clock_paused": _bool,
    "running_ticks": _int,
    "pause_reason": lambda v, k: _str(v, k, _PAUSE_REASONS, optional=True),
    "pause_sub_reason": lambda v, k: _str(v, k, _PAUSE_SUB_REASONS, optional=True),
    "ended": _bool,
    "hold_ticks": _int,
    "held_ticks_coalition": _int,
    "held_ticks_enemy": _int,
    "objectives_issued": _int,
    "objectives_done": _int,
    "defeat_ticks": _int,
}


def _respawn_left(value: object) -> dict[str, int]:
    """Entries are >= 1: `lifecycle` deletes one at 0. The upper bound is the rules' delay, which
    a snapshot does not carry."""
    if not isinstance(value, dict):
        raise ValueError(f"{_RESPAWN_LEFT} must be a map")
    return {_str(k, "commander_id"): _int(v, _RESPAWN_LEFT, 1) for k, v in value.items()}


def _callsigns(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{_CALLSIGNS} must be a map")
    for callsign in value.values():
        if not (isinstance(callsign, str) and _CALLSIGN.fullmatch(callsign)):
            raise ValueError(f"bad callsign: {callsign!r}")
    return {_str(k, "commander_id"): v for k, v in value.items()}


def _reserve_queue(value: object) -> list[JoinCommand]:
    """Validated JOINs (pydantic's ValidationError is a ValueError), one per commander (U-4)."""
    if not isinstance(value, list):
        raise ValueError(f"{_RESERVE_QUEUE} must be a list")
    queue = [JoinCommand.model_validate(c, strict=True) for c in value]  # no "9" for 9
    if len({c.issuer.commander_id for c in queue}) != len(queue):
        raise ValueError(f"{_RESERVE_QUEUE} holds a commander twice")
    return queue


_CONTACT_KEYS = ("age", "id", "kind", "painted", "pos", "vel")


_MARKER_KEYS = ("confirmed_tick", "emitting", "id", "kind", "pos", "ring_m", "state", "variant")


def _per_side[T](
    value: object,
    key: str,
    keys: tuple[str, ...],
    next_id: int,
    item: Callable[[dict[str, Any]], T],
) -> dict[Side, dict[int, T]]:
    """Both sides, each a list of `keys` records ascending by id below `next_id`."""
    sides = _fields(value, SIDES, key)
    out: dict[Side, dict[int, T]] = {}
    for side in SIDES:
        if not isinstance(sides[side], list):
            raise ValueError(f"{key}.{side} must be a list")
        out[side], last = {}, 0
        for raw in sides[side]:
            d = _fields(raw, keys, key)
            i = _int(d["id"], f"{key} id", 1)
            if not last < i < next_id:
                raise ValueError(f"{key} ids must ascend and stay below next_entity_id")
            out[side][i], last = item(d), i
    return out


def _contact(d: dict[str, Any]) -> Contact:
    age = None if d["age"] is None else _int(d["age"], "contact age")
    kind = _str(d["kind"], "contact kind", _UNIT_KINDS)
    painted = _bool(d["painted"], "contact painted")
    if painted and age is not None:
        raise ValueError("a last-known track cannot be painted")
    return Contact(kind, _vec(d["pos"], "pos"), _vec(d["vel"], "vel"), age, painted)


_BLOB_KEYS = ("id", "pos", "size")


def _blobs(value: object, tick: int) -> dict[Side, tuple[Blob, ...]]:
    """Each side's blobs share one refresh tick, at most the snapshot's, ascending by cell."""
    sides = _fields(value, SIDES, _BLOBS)
    out: dict[Side, tuple[Blob, ...]] = {}
    for side in SIDES:
        if not isinstance(sides[side], list):
            raise ValueError(f"{_BLOBS}.{side} must be a list")
        out[side] = tuple(_blob(_fields(b, _BLOB_KEYS, _BLOBS)) for b in sides[side])
        keys = [tuple(int(n) for n in b.id.split("-")) for b in out[side]]
        ticks = {k[0] for k in keys}
        if len(ticks) > 1 or max(ticks, default=0) > tick or keys != sorted(set(keys)):
            raise ValueError(f"{_BLOBS}.{side}: ids must share one refresh tick and ascend")
    return out


def _blob(d: dict[str, Any]) -> Blob:
    if not (isinstance(d["id"], str) and _BLOB_ID.fullmatch(d["id"])):
        raise ValueError(f"bad blob id: {d['id']!r}")
    return Blob(d["id"], _vec(d["pos"], "pos"), _str(d["size"], "blob size", _BLOB_SIZES))


def _marker(d: dict[str, Any]) -> FacilityMarker:
    return FacilityMarker(
        _str(d["kind"], "marker kind", _UNIT_KINDS),
        _str(d["variant"], "marker variant", optional=True),
        _vec(d["pos"], "pos"),
        None if d["emitting"] is None else _bool(d["emitting"], "marker emitting"),
        _int(d["confirmed_tick"], "marker confirmed_tick"),
        None if d["ring_m"] is None else _int(d["ring_m"], "marker ring_m", 1),
        _str(d["state"], "marker state", _DAMAGE_STATES),
    )


def _load_entity(value: object) -> Entity:
    d = _fields(value, _ENTITY_KEYS, "entity")
    e = Entity(**{k: check(d[k], k) for k, check in _ENTITY_CHECKS.items()})
    # An aircraft has a state and fuel, anything else neither; only ON_STATION has an orbit
    # (NX-368). Whether the kind is AIR needs the rules; `movement` checks that.
    if (e.state is None) != (e.fuel is None) or (e.orbit is not None and e.state != "ON_STATION"):
        raise ValueError(f"entity {e.id}: inconsistent state, fuel and orbit")
    if e.cargo is None and (e.unload_milli or e.delivered):
        raise ValueError(f"entity {e.id}: unload progress without cargo")
    if e.defended > e.delivered:
        raise ValueError(f"entity {e.id}: more units spent on defenses than delivered")
    if len(e.ammo) != len(e.reload) or (e.wreck_left is not None and e.damage_state != "DISABLED"):
        raise ValueError(f"entity {e.id}: inconsistent ammo, reload or wreck timer")
    return e


_CREW_MARKER_KEYS = ("entity_id", "expires", "id", "pos", "side")


def _crew_markers(value: object, next_marker_id: int, next_entity_id: int) -> dict[int, CrewMarker]:
    """Markers ascending by id below the counter; the unit they belonged to is gone by now."""
    if not isinstance(value, list):
        raise ValueError(f"{_CREW_MARKERS} must be a list")
    markers: dict[int, CrewMarker] = {}
    for raw in value:
        d = _fields(raw, _CREW_MARKER_KEYS, "crew marker")
        i = _int(d["id"], "crew marker id", 1)
        if i <= max(markers, default=0) or i >= next_marker_id:
            raise ValueError(f"{_CREW_MARKERS}: ids must ascend and stay below the counter")
        entity_id = _int(d["entity_id"], "crew marker entity_id", 1)
        if entity_id >= next_entity_id:
            raise ValueError(f"{_CREW_MARKERS}: entity id out of range")
        markers[i] = CrewMarker(
            i, entity_id, _str(d["side"], "crew marker side", SIDES), _vec(d["pos"], "pos"),
            _int(d["expires"], "crew marker expires", 1),
        )  # fmt: skip
    return markers


def _load_campaign(value: object) -> Campaign:
    d = _fields(value, _CAMPAIGN_KEYS, _CAMPAIGN)
    c = Campaign(**{k: check(d[k], k) for k, check in _CAMPAIGN_CHECKS.items()})
    if (
        (c.pause_reason is None) == c.clock_paused
        or (c.pause_sub_reason is not None and c.pause_reason != "STAFF")
        or c.running_ticks > c.tick
        or max(c.hold_ticks, c.defeat_ticks) > c.running_ticks
        or c.objectives_done > c.objectives_issued
    ):
        raise ValueError("campaign: inconsistent clock, pause reason or objective counts")
    return c


_SHOT_KEYS = tuple(f.name for f in fields(Shot))


def _shots(value: object, next_shot_id: int, next_entity_id: int) -> list[Shot]:
    """Pending shots ascending by `(impact_tick, id)`, ids unique and below the counter; the
    shooter and target may be gone by now."""
    if not isinstance(value, list):
        raise ValueError(f"{_SHOTS} must be a list")
    shots = []
    for raw in value:
        d = _fields(raw, _SHOT_KEYS, "shot")
        shots.append(
            Shot(
                _int(d["id"], "shot id", 1),
                _int(d["shooter"], "shot shooter", 1),
                None if d["target"] is None else _int(d["target"], "shot target", 1),
                _str(d["weapon_id"], "shot weapon"),
                _int(d["impact_tick"], "shot impact_tick", 1),
                _str(d["node"], "shot node", optional=True),
            )
        )
        if (shots[-1].target is None) == (shots[-1].node is None):
            raise ValueError(f"{_SHOTS}: a shot has an entity or a node target, not both or none")
    order = [(s.impact_tick, s.id) for s in shots]
    ids = [s.id for s in shots]
    if (
        order != sorted(order)
        or len(set(ids)) != len(ids)
        or any(
            s.id >= next_shot_id or max(s.shooter, s.target or 0) >= next_entity_id for s in shots
        )
    ):
        raise ValueError(f"{_SHOTS}: not in (impact_tick, id) order, or an id out of range")
    return shots


def _load_objective(value: object, campaign: Campaign) -> Objective | None:
    """The active objective is the latest one issued and still has time left."""
    if value is None:
        return None
    d = _fields(value, tuple(f.name for f in fields(Objective)), _OBJECTIVE)
    o = Objective(
        _int(d["id"], "objective id", 1),
        _str(d["node_id"], "objective node"),
        _int(d["deadline"], "objective deadline"),
        _bool(d["hold"], "objective hold"),
    )
    if o.id != campaign.objectives_issued or o.deadline <= campaign.running_ticks:
        raise ValueError("objective: not the latest issued, or already past its deadline")
    return o


def _job(d: dict[str, Any], next_entity_id: int, running_ticks: int, nodes: set[str]) -> Job:
    claims = d["claims"]
    if not isinstance(claims, list):
        raise ValueError(f"{_BOARDS}: claims must be a list")
    job = Job(
        _int(d["id"], "job id", 1), _str(d["kind"], "job kind", _JOB_KINDS),
        _str(d["key"], "job key"), _int(d["slots"], "job slots", 1),
        _int(d["urgency"], "job urgency", 1000), _int(d["created"], "job created"),
        _str(d["node"], "job node", optional=True), _str(d["blob"], "job blob", optional=True),
        None if d["pos"] is None else _vec(d["pos"], "job pos"),
        None if d["expires"] is None else _int(d["expires"], "job expires", 1),
        None if d["depends_on"] is None else _int(d["depends_on"], "job depends_on", 1),
        None if d["objective"] is None else _int(d["objective"], "job objective", 1),
        None if d["entity"] is None else _int(d["entity"], "job entity", 1),
        _int(d["restarts"], "job restarts"),
    )  # fmt: skip
    for raw in claims:
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError(f"{_BOARDS}: a claim is [entity id, tick, active]")
        i = _int(raw[0], "claim entity id", 1)
        if i >= next_entity_id or i in job.claims or i < max(job.claims, default=0):
            raise ValueError(f"{_BOARDS}: claims must ascend by entity id below the counter")
        job.claims[i] = Claim(_int(raw[1], "claim tick"), _bool(raw[2], "claim active"))
    if job.created > running_ticks or any(c.at > running_ticks for c in job.claims.values()):
        raise ValueError(f"{_BOARDS}: a job or claim from after the snapshot's clock")
    escort = job.kind == "ESCORT_CONVOY"  # targets a truck, not a place
    if escort != (job.entity is not None) or (job.entity or 0) >= next_entity_id:
        raise ValueError(f"{_BOARDS}: only an escort job names an entity, below the counter")
    if escort != (job.node is None and job.blob is None and job.pos is None) or (
        not escort
        and ((job.node is None) == (job.blob is None) or (job.blob is None) != (job.pos is None))
    ):
        raise ValueError(f"{_BOARDS}: a job targets a node or a blob with its position")
    scout_node = job.kind == "SCOUT" and job.blob is None and job.key.startswith("op:")
    if (job.kind == "SCOUT") != (job.blob is not None or scout_node) or (
        job.node or ""
    ) not in nodes | {""}:
        raise ValueError(f"{_BOARDS}: a scout job targets a blob, any other a node of the theater")
    target = (
        str(job.entity) if escort else job.node if job.blob is None else job.blob.split("-")[-1]
    )
    prefix = JOB_KEY_PREFIX.get(job.kind, "-")
    others = [p for p in JOB_KEY_PREFIX.values() if p != prefix and job.key.startswith(p)]
    if others or (job.key.startswith(prefix) and job.key != f"{prefix}{target}"):
        raise ValueError(f"{_BOARDS}: job key {job.key!r} does not name its kind and target")
    return job


def _boards(value: object, world: World) -> dict[Side, dict[int, Job]]:
    """Both sides' jobs ascending by id below the counter; a dependency names a job on its board,
    and a claim matches its unit's `job_id` while the unit lives (the unit may be gone)."""
    sides = _fields(value, SIDES, _BOARDS)
    boards: dict[Side, dict[int, Job]] = {}
    seen: set[int] = set()
    for side in SIDES:
        if not isinstance(sides[side], list):
            raise ValueError(f"{_BOARDS}.{side} must be a list")
        jobs = [
            _job(
                _fields(raw, _JOB_KEYS, _BOARDS),
                world._next_entity_id,
                world.campaign.running_ticks,
                set(world.owner),
            )
            for raw in sides[side]
        ]
        ids = [j.id for j in jobs]
        if ids != sorted(set(ids)) or seen & set(ids) or (ids and ids[-1] >= world._next_job_id):
            raise ValueError(
                f"{_BOARDS}.{side}: ids must be unique, ascend and stay below the counter"
            )
        if len({j.key for j in jobs}) != len(jobs) or any(
            j.depends_on is not None and not (j.depends_on in ids and j.depends_on < j.id)
            for j in jobs
        ):  # a job waits for an earlier one: no self or circular wait
            raise ValueError(
                f"{_BOARDS}.{side}: duplicate dedupe key, or a dependency off the board "
                "or not on an earlier job"
            )
        seen.update(ids)
        boards[side] = {j.id: j for j in jobs}
    return boards


def _tick_map(value: object, nodes: dict[str, NodeOwner], limit: int, what: str) -> dict[str, int]:
    """Node -> a running tick, for nodes that exist, not after the snapshot's clock."""
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be a map")
    out = {_str(k, "node id"): _int(v, what) for k, v in value.items()}
    if not set(out) <= set(nodes) or any(v > limit for v in out.values()):
        raise ValueError(f"{what}: a node that does not exist, or a tick after the snapshot")
    return out


def _runs(value: object, blobs: tuple[Blob, ...]) -> dict[str, int]:
    """Runs of at least 1, exactly for the cells the side's current blobs are in."""
    if not isinstance(value, dict):
        raise ValueError(f"{_BLOB_RUNS} must be a map")
    out = {_str(k, "cell"): _int(v, _BLOB_RUNS, 1) for k, v in value.items()}
    if set(out) != {b.id.split("-")[1] for b in blobs}:
        raise ValueError(f"{_BLOB_RUNS} must name the cells of the current blobs")
    return out


def _cells(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{_COOLDOWN} must map cells to ticks")
    return {_str(k, "cell"): _int(v, _COOLDOWN) for k, v in value.items()}


def _counts(value: object, what: str) -> dict[str, int]:
    """A map from an id to a count above 0 (a sector's memory counter, a node's tick lost)."""
    if not isinstance(value, dict):
        raise ValueError(f"{_DIRECTOR}.{what} must be a map")
    return {_str(k, what): _int(v, what, 1) for k, v in value.items()}


def _idle(value: object, running_ticks: int) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{_DIRECTOR}.idle must be a map")
    out = {_str(k, "idle entity"): _int(v, "idle tick", 1) for k, v in value.items()}
    if not all(k.isdigit() and int(k) >= 1 for k in out):
        raise ValueError(f"{_DIRECTOR}.idle: keys are entity ids")
    if any(v > running_ticks for v in out.values()):
        raise ValueError(f"{_DIRECTOR}.idle: a tick after the snapshot's running ticks")
    return out


def _labels(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{_DIRECTOR}.adapted must be a map")
    return {_str(k, "adapted"): _str(v, "adapted") for k, v in value.items()}


def _director(value: object, running_ticks: int) -> dict[Side, DirectorState]:
    sides = _fields(value, SIDES, _DIRECTOR)
    out: dict[Side, DirectorState] = {}
    for side in SIDES:
        d = _fields(sides[side], _DIRECTOR_KEYS, f"{_DIRECTOR}.{side}")
        sector = _str(d["last_provocation_sector"], "last_provocation_sector", optional=True)
        state = DirectorState(
            cp=_int(d["cp"], "cp"),
            provocation=_int(d["provocation"], "provocation"),
            pending=_int(d["pending"], "pending"),
            tier=_str(d["tier"], "tier", _TIERS),
            prov_level=_int(d["prov_level"], "prov_level"),
            ceiling=_int(d["ceiling"], "ceiling"),
            dwell=_int(d["dwell"], "dwell"),
            windows=_int(d["windows"], "windows"),
            budget=_int(d["budget"], "budget"),
            last_provocation_sector=sector,
            last_provocation_tick=_int(d["last_provocation_tick"], "last_provocation_tick"),
            convoy_attacks=_int(d["convoy_attacks"], "convoy_attacks"),
            radar_strikes=_int(d["radar_strikes"], "radar_strikes"),
            node_losses=_counts(d["node_losses"], "node_losses"),
            recon_losses=_counts(d["recon_losses"], "recon_losses"),
            lost=_counts(d["lost"], "lost"),
            adapted=_labels(d["adapted"]),
            dark=_counts(d["dark"], "dark"),
            blink_ready=_counts(d["blink_ready"], "blink_ready"),
            idle=_idle(d["idle"], running_ticks),
        )
        if max(state.prov_level, state.ceiling) > 2 or state.ceiling < 1:
            raise ValueError(f"{_DIRECTOR}.{side}: a level must be 0..2 and the ceiling at least 1")
        if state.windows > running_ticks or state.last_provocation_tick > running_ticks:
            raise ValueError(f"{_DIRECTOR}.{side}: a count after the snapshot's running ticks")
        if (sector is None) != (state.last_provocation_tick == 0):
            raise ValueError(f"{_DIRECTOR}.{side}: the provocation sector and tick go together")
        out[side] = state
    return out


def _check_claims(world: World) -> None:
    """A unit holds at most one claim, on its own side's board, and a live unit's `job_id` is it."""
    claimed: dict[int, tuple[Side, int]] = {}
    for side, board in world.boards.items():
        for job in board.values():
            for i in job.claims:
                if i in claimed:
                    raise ValueError(f"{_BOARDS}: entity {i} holds two claims")
                claimed[i] = (side, job.id)
    for e in world.entities():
        side_job = claimed.get(e.id)
        if (side_job[1] if side_job else None) != e.job_id or (side_job and side_job[0] != e.side):
            raise ValueError(f"entity {e.id}: job_id does not match a claim on its side's board")


def load(data: bytes) -> World:
    """Rebuild a world from `save` output; the run continues exactly as before."""
    raw = msgpack.unpackb(data, raw=False)
    # The version first: an older snapshot has other keys, and this error says why.
    version = raw.get(_V) if isinstance(raw, dict) else None
    if version != FORMAT_VERSION or type(version) is not int:
        raise ValueError(f"unsupported snapshot format version {version!r}")
    d = _fields(raw, _WORLD_KEYS, "snapshot")
    world = World(_load_campaign(d[_CAMPAIGN]), SimRng.from_state(d[_RNG]))
    world._next_entity_id = _int(d[_NEXT_ENTITY_ID], _NEXT_ENTITY_ID, 1)
    world._next_event_seq = _int(d[_NEXT_EVENT_SEQ], _NEXT_EVENT_SEQ, 1)
    world._next_shot_id = _int(d[_NEXT_SHOT_ID], _NEXT_SHOT_ID, 1)
    world._next_marker_id = _int(d[_NEXT_MARKER_ID], _NEXT_MARKER_ID, 1)
    world._next_job_id = _int(d[_NEXT_JOB_ID], _NEXT_JOB_ID, 1)
    world.crew_markers = _crew_markers(
        d[_CREW_MARKERS], world._next_marker_id, world._next_entity_id
    )
    world.shots = _shots(d[_SHOTS], world._next_shot_id, world._next_entity_id)
    world.callsigns = _callsigns(d[_CALLSIGNS])
    world.respawn_left = _respawn_left(d[_RESPAWN_LEFT])
    world.reserve_queue = _reserve_queue(d[_RESERVE_QUEUE])
    world.contacts = _per_side(
        d[_CONTACTS], _CONTACTS, _CONTACT_KEYS, world._next_entity_id, _contact
    )
    world.markers = _per_side(d[_MARKERS], _MARKERS, _MARKER_KEYS, world._next_entity_id, _marker)
    world.blobs = _blobs(d[_BLOBS], world.campaign.tick)
    runs = _fields(d[_BLOB_RUNS], SIDES, _BLOB_RUNS)
    world.blob_runs = {s: _runs(runs[s], world.blobs[s]) for s in SIDES}
    world.sigint_age = _int(d[_SIGINT_AGE], _SIGINT_AGE)
    world.stock = _stock(d[_STOCK])
    world.owner = _owner(d[_OWNER])
    world.capture = _capture(d[_CAPTURE], world.owner)
    world.defense_hp = _defense(d[_DEFENSE_HP], _DEFENSE_HP, world.owner)
    world.defense_drain = _defense(d[_DEFENSE_DRAIN], _DEFENSE_DRAIN, world.owner)
    if set(world.defense_drain) != set(world.defense_hp):
        raise ValueError(f"{_DEFENSE_DRAIN} must name the same nodes as {_DEFENSE_HP}")
    down = d[_DEFENSE_DOWN]
    if not isinstance(down, list):
        raise ValueError(f"{_DEFENSE_DOWN} must be a list")
    world.defense_down = {_str(n, "node id") for n in down}
    if not world.defense_down <= set(world.defense_hp):
        raise ValueError(f"{_DEFENSE_DOWN} must list defended nodes")
    world.objective = _load_objective(d[_OBJECTIVE], world.campaign)
    c = world.campaign
    world.director = _director(d[_DIRECTOR], c.running_ticks)
    # A side holds at most every node each running tick; the strategic count needs the rules.
    if max(c.held_ticks_coalition, c.held_ticks_enemy) > len(world.owner) * c.running_ticks:
        raise ValueError("campaign: held-node tick sum above nodes x running ticks")
    if any(m.expires <= c.running_ticks for m in world.crew_markers.values()):
        raise ValueError(f"{_CREW_MARKERS}: a marker past its expiry")
    if c.ended and world.objective is not None:
        raise ValueError("objective: active in an ended campaign")
    # The age counts running ticks since the refresh, so it cannot exceed the ticks since then.
    if any(b and world.campaign.tick - int(b[0].id.split("-")[0]) < world.sigint_age
           for b in world.blobs.values()):  # fmt: skip
        raise ValueError(f"{_SIGINT_AGE} is older than the blobs' refresh tick")
    entities = d[_ENTITIES]
    if not isinstance(entities, list):
        raise ValueError("entities must be a list")
    last_id = 0
    for raw in entities:
        entity = _load_entity(raw)
        if not last_id < entity.id < world._next_entity_id:
            raise ValueError("entity ids must ascend and stay below next_entity_id")
        last_id = entity.id
        world._entities[entity.id] = entity
    _check_views(world)
    world.boards = _boards(d[_BOARDS], world)
    world.lost = _tick_map(d[_LOST], world.owner, world.campaign.running_ticks, _LOST)
    cooldown = _fields(d[_COOLDOWN], SIDES, _COOLDOWN)
    world.cooldown = {s: _cells(cooldown[s]) for s in SIDES}
    _check_claims(world)
    _check_follow(world)
    return world


def _check_follow(world: World) -> None:
    """A follower names a live unit of its side, no loop; FOLLOW needs a leader, and a leader
    without the order means the unit holds the claim of that unit's escort job."""
    for e in world.entities():
        leader = None if e.follow_id is None else world.find(e.follow_id)
        if e.follow_id is not None and (leader is None or leader.side != e.side):
            raise ValueError(f"entity {e.id}: follows a unit that is gone or of the other side")
        if leader is not None and (e.base_id is not None or leader.base_id is not None):
            raise ValueError(f"entity {e.id}: a facility cannot follow or be followed")
        if (e.order == "FOLLOW") != (e.follow_id is not None and e.job_id is None):
            raise ValueError(f"entity {e.id}: follow_id and order FOLLOW do not match")
        job = None if e.job_id is None else world.boards[e.side].get(e.job_id)
        if e.follow_id is not None and e.order != "FOLLOW":
            if job is None or job.kind != "ESCORT_CONVOY" or job.entity != e.follow_id:
                raise ValueError(f"entity {e.id}: follows a unit without an escort claim on it")
        chain, at = {e.id}, leader
        while at is not None:
            if at.id in chain:
                raise ValueError(f"entity {e.id}: a follow loop")
            chain.add(at.id)
            at = None if at.follow_id is None else world.find(at.follow_id)


def _check_views(world: World) -> None:
    """A contact or marker of a live entity names an enemy of its side, of the entity's kind. A
    removed entity's stays valid (FOW-6a, FOW-13); the fade bound needs the rules, which load
    lacks. A marker cannot be confirmed after the snapshot's tick."""
    for key, per_side in ((_CONTACTS, world.contacts), (_MARKERS, world.markers)):
        for side, known in per_side.items():
            for i, c in known.items():
                e = world._entities.get(i)
                if e is not None and (e.side == side or e.kind != c.kind):
                    raise ValueError(f"{key}.{side}: {i} does not match its entity")
    if any(
        m.confirmed_tick > world.campaign.tick for ms in world.markers.values() for m in ms.values()
    ):
        raise ValueError(f"{_MARKERS}: confirmed_tick after the snapshot's tick")
