"""World model, canonical encoding, `state_hash` and snapshots (SIM-CORE SC-4, SC-9, SC-14, §4, §5).

Systems reach entities only through `World` (Q-SIM-4), never its storage. `Entity` holds only the
fields the first systems need; every other SIM-CORE §4 field is added by the system that first
uses it.

One walker, `to_canonical`, turns a world into plain sorted data. Snapshots keep floats exactly
(float64), so a restored run continues bit-identically; only `state_hash` quantizes (ADR-0002):
positions, `orbit` centres and `path` waypoints to integer mm, velocities to integer mm/s, other
floats (`fuel`) to ADR-0002's 1e-6 step. Python's `round` is round-half-to-even on the
exact float value, so it is deterministic. The RNG state, `respawn_left` (per commander, GP-2),
the reserve queue (GP-3) and each side's FoW contacts (FOW-5) are world state, so snapshots and
the hash cover them. `World.rules`
(`nexus.core.rules`) is static config, not state: neither snapshots nor the hash include it.
"""

import hashlib
import math
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, fields
from typing import Annotated, Any, Literal, Self, cast, get_args, get_origin

import msgpack

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.common.enums import OwnerKind, Side, UnitKind
from nexus.core.rng import SimRng
from nexus.core.rules import Rules

# 2: Entity.path and Entity.last_node (NX-121); 3: respawn_left, hp may be null; 4: reserve_queue;
# 5: Entity.state, fuel and orbit (NX-368); 6: callsigns (NX-370); 7: contacts (NX-150)
FORMAT_VERSION = 7
_MM = 1000.0  # metres -> millimetres; m/s -> mm/s
_MICRO = 1e6  # ADR-0002's 1e-6 step for other floats (fuel)
_MAX_ABS = 1e9  # m or m/s; keeps mm quantization well inside int64
_CAMPAIGN = "campaign"
_CONTACTS = "contacts"
_ENTITIES = "entities"
_CALLSIGNS = "callsigns"
_RESPAWN_LEFT = "respawn_left"
_RESERVE_QUEUE = "reserve_queue"
_NEXT_ENTITY_ID = "next_entity_id"
_NEXT_EVENT_SEQ = "next_event_seq"
_RNG = "rng"
_V = "v"
_WORLD_KEYS = (
    _CALLSIGNS,
    _CAMPAIGN,
    _CONTACTS,
    _ENTITIES,
    _NEXT_ENTITY_ID,
    _NEXT_EVENT_SEQ,
    _RESERVE_QUEUE,
    _RESPAWN_LEFT,
    _RNG,
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
_SIDES = cast(tuple[Side, ...], _literal_values(Side))
_OWNER_KINDS = _literal_values(OwnerKind)


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
    hp: int | None  # None: not modeled yet (no catalog hp until combat, NX-124; Q-CFG-10)
    # Remaining waypoints (SIM-CORE §4): node ids, or Vec2 for AIR. A GROUND unit is on the road
    # edge from `last_node` (the node it last reached or spawned at) to `path[0]` (NX-121).
    path: list[str | Vec2] = field(default_factory=list)
    last_node: str | None = None
    # STATE-MACHINES §4.1 state; only aircraft have one yet (NX-368), None for other domains.
    state: UnitState | None = None
    fuel: float | None = None  # aircraft: world seconds of flight left (NX-368)
    orbit: Vec2 | None = None  # the centre an idle ON_STATION aircraft circles (NX-368)


@dataclass(slots=True)
class Contact:
    """One enemy entity a side knows of (FOG-OF-WAR Tier 2, FOW-6a): kind, position and velocity
    (its heading) as of the last pass that tracked it. `age` is None while tracked; once lost it is
    a last-known track and `age` counts the running ticks since (FOW-9)."""

    kind: UnitKind
    pos: Vec2
    vel: Vec2
    age: int | None = None


@dataclass(slots=True)
class Campaign:
    id: str  # CampaignId
    seed: int
    config_hash: str
    tick: int = 0
    clock_paused: bool = False


_ENTITY_KEYS = tuple(f.name for f in fields(Entity))
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
        "callsigns",
        "campaign",
        "contacts",
        "reserve_queue",
        "respawn_left",
        "rng",
        "rules",
    )

    def __init__(self, campaign: Campaign, rng: SimRng, rules: Rules | None = None) -> None:
        self.campaign = campaign
        self.rng = rng
        self.rules = rules  # None: no unit may have a path (movement raises)
        self._entities: dict[int, Entity] = {}
        self._next_entity_id = 1
        self._next_event_seq = 1
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
        self.contacts: dict[Side, dict[int, Contact]] = {side: {} for side in _SIDES}

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
        hp: int | None,
    ) -> Entity:
        entity = Entity(
            self._next_entity_id, kind, side, owner_kind, commander_id, callsign, pos, vel, hp
        )
        self._entities[entity.id] = entity
        self._next_entity_id += 1
        return entity

    def get(self, entity_id: int) -> Entity:
        return self._entities[entity_id]

    def remove(self, entity_id: int) -> None:
        del self._entities[entity_id]

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
            {"age": c.age, "id": i, "kind": c.kind, "pos": _xy(c.pos, quantize),
             "vel": _xy(c.vel, quantize)}
            for i, c in sorted(world.contacts[side].items())
        ]
        for side in _SIDES
    }  # fmt: skip


def _sorted(value: Any) -> Any:
    """Plain JSON data with every dict's keys sorted, at any depth."""
    if isinstance(value, dict):
        return {k: _sorted(value[k]) for k in sorted(value)}
    return [_sorted(v) for v in value] if isinstance(value, list) else value


def to_canonical(world: World, *, quantize: bool) -> dict[str, Any]:
    """Plain data with sorted keys and entities in id order; quantized for the hash only."""
    data = {
        _CALLSIGNS: dict(sorted(world.callsigns.items())),
        _CAMPAIGN: {k: getattr(world.campaign, k) for k in sorted(_CAMPAIGN_KEYS)},
        _CONTACTS: _contacts_data(world, quantize),
        _ENTITIES: [_entity_data(e, quantize) for e in world.entities()],
        _RESPAWN_LEFT: dict(sorted(world.respawn_left.items())),
        _RESERVE_QUEUE: [_sorted(c.model_dump(mode="json")) for c in world.reserve_queue],
        _NEXT_ENTITY_ID: world._next_entity_id,
        _NEXT_EVENT_SEQ: world._next_event_seq,
        _RNG: {name: dict(sorted(s.items())) for name, s in world.rng.to_state().items()},
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


def _bool(value: object, what: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{what} must be a bool, got {value!r}")
    return value


# One check per field, labelled by the field name; keys match `fields(Entity)` / `fields(Campaign)`.
_ENTITY_CHECKS: dict[str, Callable[[object, str], Any]] = {
    "id": lambda v, k: _int(v, k, 1),
    "kind": lambda v, k: _str(v, k, _UNIT_KINDS),
    "side": lambda v, k: _str(v, k, _SIDES),
    "owner_kind": lambda v, k: _str(v, k, _OWNER_KINDS),
    "commander_id": lambda v, k: _str(v, k, optional=True),
    "callsign": lambda v, k: _str(v, k, optional=True),
    "pos": _vec,
    "vel": _vec,
    "hp": lambda v, k: None if v is None else _int(v, k),
    _PATH: _path,
    "last_node": lambda v, k: _str(v, k, optional=True),
    "state": lambda v, k: _str(v, k, _UNIT_STATES, optional=True),
    _FUEL: _fuel,
    "orbit": lambda v, k: None if v is None else _vec(v, k),
}
_CAMPAIGN_CHECKS: dict[str, Callable[[object, str], Any]] = {
    "id": _str,
    "seed": _int,
    "config_hash": _str,
    "tick": _int,
    "clock_paused": _bool,
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


_CONTACT_KEYS = ("age", "id", "kind", "pos", "vel")


def _contacts(value: object, next_id: int) -> dict[Side, dict[int, Contact]]:
    """Both sides, each a list of contacts ascending by id below `next_id`."""
    sides = _fields(value, _SIDES, _CONTACTS)
    out: dict[Side, dict[int, Contact]] = {}
    for side in _SIDES:
        if not isinstance(sides[side], list):
            raise ValueError(f"{_CONTACTS}.{side} must be a list")
        out[side], last = {}, 0
        for raw in sides[side]:
            d = _fields(raw, _CONTACT_KEYS, "contact")
            i = _int(d["id"], "contact id", 1)
            if not last < i < next_id:
                raise ValueError("contact ids must ascend and stay below next_entity_id")
            age = None if d["age"] is None else _int(d["age"], "contact age")
            kind = _str(d["kind"], "contact kind", _UNIT_KINDS)
            out[side][i], last = Contact(kind, _vec(d["pos"], "pos"), _vec(d["vel"], "vel"), age), i
    return out


def _load_entity(value: object) -> Entity:
    d = _fields(value, _ENTITY_KEYS, "entity")
    e = Entity(**{k: check(d[k], k) for k, check in _ENTITY_CHECKS.items()})
    # An aircraft has a state and fuel, anything else neither; only ON_STATION has an orbit
    # (NX-368). Whether the kind is AIR needs the rules; `movement` checks that.
    if (e.state is None) != (e.fuel is None) or (e.orbit is not None and e.state != "ON_STATION"):
        raise ValueError(f"entity {e.id}: inconsistent state, fuel and orbit")
    return e


def _load_campaign(value: object) -> Campaign:
    d = _fields(value, _CAMPAIGN_KEYS, _CAMPAIGN)
    return Campaign(**{k: check(d[k], k) for k, check in _CAMPAIGN_CHECKS.items()})


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
    world.callsigns = _callsigns(d[_CALLSIGNS])
    world.respawn_left = _respawn_left(d[_RESPAWN_LEFT])
    world.reserve_queue = _reserve_queue(d[_RESERVE_QUEUE])
    world.contacts = _contacts(d[_CONTACTS], world._next_entity_id)
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
    _check_contacts(world)
    return world


def _check_contacts(world: World) -> None:
    """A contact of a live entity names an enemy of its side, of the entity's kind. A removed
    entity's contact stays valid (FOW-6a); the fade bound needs the rules, which load lacks."""
    for side, known in world.contacts.items():
        for i, c in known.items():
            e = world._entities.get(i)
            if e is not None and (e.side == side or e.kind != c.kind):
                raise ValueError(f"{_CONTACTS}.{side}: contact {i} does not match its entity")
