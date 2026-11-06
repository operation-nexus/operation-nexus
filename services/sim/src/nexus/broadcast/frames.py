"""Wire frame builders: the redacted coalition view of the world as Welcome, Snapshot, Delta and Hud
(WIRE-PROTOCOL WP-4, WP-8, WP-9, WP-10; CONTRACTS section 7; NX-170 part a).

Read-only: this reads the world and its `SideView`, and never writes the world, draws RNG or reads a
clock, so attaching it changes no `state_hash`. Redaction happens here, before serialization
(FOW-1): an enemy entity appears only while the coalition tracks it (its position is the track's,
Q-FOW-6), a discovered enemy facility only as a `NodeView` facility (FOW-13), and the events
`_public` lets through are those whose CONTRACTS section 6 rule allows them, with the hidden ids
and the staff sub-reason removed. Every other event kind is dropped until its rule is built.

`FrameBuilder.delta` is called once per tick right after `step`; it diffs against the views of the
previous call (the base), so one shared Delta serves every client (WP-8). `snapshot` reads the
current world and leaves the base alone. Frames are built with `model_construct` (Q-CT-7) and
`encode` turns one into msgpack bytes; tests validate the decoded dict against the schema.

An enemy's position and velocity are its track's, up to `fow.track_every_ticks` stale (Q-FOW-6),
while its `hp_pct` and `damage_state` are live; FOG-OF-WAR allows that. `last_known[].seen_tick`
is on the campaign clock (running ticks, like `Hud.campaign_clock.elapsed_ticks`), so a pause
leaves it, and the list, unchanged.

The first `delta` of a builder is self-contained: `base_tick == tick`, with every entity and node
as a full upsert and `blobs` and `last_known` as lists, so it needs no earlier frame. Builder-local
state: `Hud.momentum_breakdown.recent_events` is the last 5 public events this builder saw, and
`panels.campaign_status.result` is the result of the last `CampaignEnded` it saw. The world does not
record a result (`Campaign.ended` is a flag), so a builder created after a restart sends
`result: null` and no recent events for an ended campaign.

Defaults where the sim has no source yet: heading is 0 for a still unit, the Hud's ticker,
operators, active_humans, top commanders and sectors are empty or null, and cosmetic, badge,
package, probation and AUTO fields are null, empty or false.
"""

import math
from collections import Counter, deque
from collections.abc import Sequence
from fractions import Fraction
from typing import Any, Literal

import msgpack
from pydantic import BaseModel

from nexus.contracts.gen.common.enums import CampaignResult, Side
from nexus.contracts.gen.config.theater import TheaterConfig
from nexus.contracts.gen.events.campaign_clock_paused import CampaignClockPaused
from nexus.contracts.gen.events.campaign_clock_resumed import CampaignClockResumed
from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.capture_started import CaptureStarted
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.contracts.gen.events.node_defenses_down import NodeDefensesDown
from nexus.contracts.gen.events.node_defenses_restored import NodeDefensesRestored
from nexus.contracts.gen.events.objective_announced import ObjectiveAnnounced
from nexus.contracts.gen.events.objective_resolved import ObjectiveResolved
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.contracts.gen.events.victory_hold_broken import VictoryHoldBroken
from nexus.contracts.gen.events.victory_hold_paused import VictoryHoldPaused
from nexus.contracts.gen.events.victory_hold_reset import VictoryHoldReset
from nexus.contracts.gen.events.victory_hold_resumed import VictoryHoldResumed
from nexus.contracts.gen.events.victory_hold_started import VictoryHoldStarted
from nexus.contracts.gen.wire import hud as h
from nexus.contracts.gen.wire import views as v
from nexus.contracts.gen.wire.ack import Ack
from nexus.contracts.gen.wire.control import Control
from nexus.contracts.gen.wire.delta import Delta
from nexus.contracts.gen.wire.snapshot import Snapshot
from nexus.contracts.gen.wire.welcome import Welcome
from nexus.core.campaign import momentum, scores
from nexus.core.fog import SideView, _marker, side_view, spotted, tracked_by, visible
from nexus.core.rearm import is_starved
from nexus.core.rules import CAPTURE_FULL, Rules
from nexus.core.step import TICK_DT
from nexus.core.world import World

_VIEWER: Side = "COALITION"
_STATIC = "STATIC"
_PUBLIC_AS_IS = (
    CampaignEnded,
    CaptureStarted,
    NodeDefensesDown,
    NodeDefensesRestored,
    ObjectiveAnnounced,
    ObjectiveResolved,
    VictoryHoldBroken,
    VictoryHoldPaused,
    VictoryHoldReset,
    VictoryHoldResumed,
    VictoryHoldStarted,
)
_RECENT = 5  # momentum_breakdown.recent_events at most (CONTRACTS section 7)
type Frame = Welcome | Snapshot | Delta | h.Hud | Control | Ack


def encode(frame: Frame) -> bytes:
    """The frame as msgpack (WIRE-PROTOCOL section 2). `exclude_unset` keeps a patch to its changed
    fields; `by_alias` writes `from` for `NodeCaptured.from_`."""
    return bytes(msgpack.packb(frame.model_dump(mode="json", by_alias=True, exclude_unset=True)))


def control(version: str, action: Literal["RELOAD", "RESYNC"]) -> Control:
    return Control.model_construct(type="Control", v=version, action=action)


def _pct(part: int, whole: int) -> int:
    return min(100, max(0, (part * 100 + whole // 2) // whole)) if whole else 0  # 100: a percent


def _pos(x: float, y: float) -> v.Pos:
    return v.Pos.model_construct(x_m=round(x), y_m=round(y))  # WP-4: 1 m


def _motion(vx: float, vy: float) -> tuple[int, int]:
    """Heading (0 = north = +y, clockwise) and speed in whole degrees and m/s; 0 when still."""
    return round(math.degrees(math.atan2(vx, vy))) % 360, round(math.hypot(vx, vy))  # 360: a circle


class FrameBuilder:
    def __init__(
        self,
        theater: TheaterConfig,
        *,
        protocol_version: str,
        server_build: str,
        terrain_ref: str | None = None,
    ) -> None:
        self._theater, self._v, self._build, self._terrain = (
            theater,
            protocol_version,
            server_build,
            terrain_ref,
        )
        self._names = {n.id: n.name for n in theater.nodes}
        self._base_tick: int | None = None
        self._ents: dict[int, v.EntityView] = {}
        self._nodes: dict[str, v.NodeView] = {}
        self._blobs: list[v.BlobView] = []
        self._last_known: list[v.LastKnownView] = []
        self._recent: deque[Event] = deque(maxlen=_RECENT)
        self._result: CampaignResult | None = None

    def welcome(self, world: World, tick_rate_hz: int | None = None) -> Welcome:
        t = self._theater
        nodes = [
            v.Node.model_construct(node_id=n.id, name=n.name, kind=n.kind, pos=_pos(*n.pos))
            for n in sorted(t.nodes, key=lambda n: n.id)
        ]
        edges = [
            v.Edge.model_construct(a=e.a, b=e.b, layer=e.layer, bridge=e.bridge)
            for e in sorted(t.edges, key=lambda e: (e.a, e.b, e.layer))
        ]
        static = v.TheaterStatic.model_construct(
            nodes=nodes,
            edges=edges,
            bounds_m=v.BoundsM.model_construct(w=t.bounds_m.w, h=t.bounds_m.h),
            terrain_ref=self._terrain,
        )
        return Welcome.model_construct(
            type="Welcome",
            v=self._v,
            server_build=self._build,
            campaign_id=world.campaign.id,
            tick_rate_hz=tick_rate_hz or round(1 / TICK_DT),
            theater=static,
        )

    def snapshot(self, world: World) -> Snapshot:
        ents, nodes, blobs, last_known = self._views(world)
        return Snapshot.model_construct(
            type="Snapshot",
            v=self._v,
            tick=world.campaign.tick,
            entities=list(ents.values()),
            nodes=list(nodes.values()),
            blobs=blobs,
            last_known=last_known,
            hud=self.hud(world),
        )

    def delta(self, world: World, events: Sequence[Event]) -> Delta:
        """The changes since the previous call (the base), then makes this tick the base."""
        tick = world.campaign.tick
        first = self._base_tick is None
        ents, nodes, blobs, last_known = self._views(world)
        upserts = [
            _patch(v.EntityPatch, "entity_id", old, new)
            for i, new in ents.items()
            if (old := self._ents.get(i)) != new
        ]
        node_patches = [
            _patch(v.NodePatch, "node_id", old_node, new)
            for i, new in nodes.items()
            if (old_node := self._nodes.get(i)) != new
        ]
        public = [p for e in events if (p := _public(world, e)) is not None]
        for e in public:
            self._recent.append(e)
            if isinstance(e, CampaignEnded):
                self._result = e.result
        out = Delta.model_construct(
            type="Delta",
            v=self._v,
            tick=tick,
            base_tick=tick if first else self._base_tick,
            upserts=upserts,
            removes=[i for i in self._ents if i not in ents],
            node_patches=node_patches,
            blobs=None if not first and blobs == self._blobs else blobs,
            last_known=None if not first and last_known == self._last_known else last_known,
            events=public,
        )
        self._base_tick, self._ents, self._nodes = tick, ents, nodes
        self._blobs, self._last_known = blobs, last_known
        return out

    def hud(self, world: World) -> h.Hud:
        c, rules = world.campaign, world.rules
        rc = rules.campaign if rules else None
        held = [world.owner.get(n) for n in rc.strategic] if rc else []
        m = momentum(world) if rc else None
        points = scores(world, rc) if rc else None  # exact; shown rounded half up (OVERLAY 0.11)
        enemy = world.director["ENEMY"].tier
        obj = world.objective
        breakdown = (
            h.MomentumBreakdown.model_construct(
                nodes_held_pct=m.nodes_held_pct,
                supply_pct=m.supply_pct,
                recent_events=list(self._recent),
                sectors=[],
            )
            if m
            else None
        )
        status = h.CampaignStatus.model_construct(
            nodes_held=h.NodesHeld.model_construct(
                coalition=held.count("COALITION"),
                enemy=held.count("ENEMY"),
                neutral=held.count("NEUTRAL"),
            ),
            result=self._result,
        )
        return h.Hud.model_construct(
            type="Hud",
            v=self._v,
            momentum_pct=m.momentum_pct if m else None,
            momentum_breakdown=breakdown,
            objective_mode="TIMED" if rc and rc.objectives_on else "OFF",
            objective=None
            if obj is None
            else h.Objective.model_construct(
                node_id=obj.node_id, name=self._names[obj.node_id], deadline_tick=obj.deadline
            ),
            threat_tier=enemy,
            nodes_held=held.count("COALITION"),
            nodes_total=len(held),
            campaign_clock=h.CampaignClock.model_construct(
                elapsed_ticks=c.running_ticks,
                limit_ticks=rc.time_limit_ticks if rc else None,
                paused=c.clock_paused,
                pause_reason=c.pause_reason,
            ),
            time_limit_score=None
            if points is None
            else h.TimeLimitScore.model_construct(
                coalition=math.floor(points["COALITION"] + Fraction(1, 2)),
                enemy=math.floor(points["ENEMY"] + Fraction(1, 2)),
            ),
            ticker=[],
            panels=h.Panels.model_construct(
                campaign_status=status, tasking_needed=[], top_commanders=[]
            ),
            active_humans=None,
            operators=None,
        )

    def _views(
        self, world: World
    ) -> tuple[
        dict[int, v.EntityView], dict[str, v.NodeView], list[v.BlobView], list[v.LastKnownView]
    ]:
        if world.rules is None:
            raise ValueError("frames need the world's rules")
        view = side_view(world, _VIEWER)
        rules = world.rules
        followers = Counter(
            e.follow_id for e in world.entities() if e.side == _VIEWER and e.follow_id
        )
        ents: dict[int, v.EntityView] = {}
        for e in world.entities():
            if rules.domain[e.kind] == _STATIC or not visible(world, _VIEWER, e):
                continue
            own = e.side == _VIEWER
            c = None if own else view.tracks[e.id]
            pos, vel = (e.pos, e.vel) if c is None else (c.pos, c.vel)
            heading, speed = _motion(vel.x, vel.y)
            stats = rules.combat.units.get(e.kind) if rules.combat else None
            unit = stats.hp if stats else 0  # no combat row: hp_pct reads 100
            ents[e.id] = v.EntityView.model_construct(
                entity_id=e.id,
                unit_kind=e.kind,
                side=e.side,
                domain=rules.domain[e.kind],
                owner_kind=e.owner_kind,
                callsign=e.callsign if own else None,
                pos=_pos(pos.x, pos.y),
                heading_deg=heading,
                speed_mps=speed,
                hp_pct=_pct(e.hp, unit) if unit else 100,
                damage_state=e.damage_state,
                painted=bool(c and c.painted),
                spotted=spotted(world, e) if own else None,
                package_id=None,
                follow_entity_id=e.follow_id if own else None,
                follower_count=followers[e.id],
                cosmetic=v.Cosmetic.model_construct(halo=None, trail=None),
                badges=[],
                probation=False,
                auto=False,
            )
        blobs = [
            v.BlobView.model_construct(
                blob_id=b.id, cell_center=_pos(b.pos.x, b.pos.y), size=b.size
            )
            for b in view.blobs
        ]
        last_known = [
            v.LastKnownView.model_construct(
                entity_id=i,
                unit_kind=c.kind,
                pos=_pos(c.pos.x, c.pos.y),
                heading_deg=_motion(c.vel.x, c.vel.y)[0],
                seen_tick=max(0, world.campaign.running_ticks - (c.age or 0)),
            )
            for i, c in view.last_known.items()
        ]
        return ents, self._node_views(world, view, rules), blobs, last_known

    def _node_views(self, world: World, view: SideView, rules: Rules) -> dict[str, v.NodeView]:
        facilities: dict[str, list[v.FacilityView]] = {n: [] for n in view.nodes}
        for e in world.entities():
            if e.base_id in facilities and e.side == _VIEWER and rules.domain[e.kind] == _STATIC:
                facilities[e.base_id].append(_facility(e.id, _marker(rules, e, 0), None))
        for i, m in view.markers.items():
            f = world.find(i)
            if f is not None and f.base_id in facilities:
                facilities[f.base_id].append(_facility(i, m, m.confirmed_tick))
        out: dict[str, v.NodeView] = {}
        for n in sorted(view.nodes):
            bar, owner = world.capture.get(n), view.owners[n]
            top = rules.supply.max_stock.get(n)
            public = owner != "ENEMY" and top is not None  # DI-1: an enemy base's stock is hidden
            stock = world.stock.get(n, 0)
            defense = rules.defense.max_hp.get(n) if rules.defense else None
            bridge = rules.supply.bridge_hp.get(n)  # a BRIDGE's own hp, public (FOW-10, CB-10)
            out[n] = v.NodeView.model_construct(
                node_id=n,
                owner=owner,
                capture=v.Capture.model_construct(
                    side=bar.side if bar else None,
                    progress_pct=bar.progress * 100 // CAPTURE_FULL if bar else 0,
                ),
                stock_pct=_pct(stock, top) if public and top else None,
                starvation=None
                if not public
                else "EMPTY"
                if stock == 0
                else "LOW"
                if is_starved(world, rules, n)
                else "OK",
                hp_pct=_pct(view.defense_hp[n], defense)
                if defense and n in view.defense_hp
                else _pct(world.bridge_hp[n], bridge)
                if bridge and n in world.bridge_hp
                else None,
                intact=n not in view.bridge_down if bridge else None,
                facilities=sorted(facilities[n], key=lambda f: f.entity_id),
            )
        return out


def _facility(entity_id: int, m: Any, confirmed: int | None) -> v.FacilityView:
    return v.FacilityView.model_construct(
        entity_id=entity_id,
        kind=m.kind,
        variant=m.variant,
        pos=_pos(m.pos.x, m.pos.y),
        ring_m=m.ring_m,
        state=m.state,
        emitting=m.emitting,
        confirmed_tick=confirmed,
    )


def _patch[P: BaseModel](cls: type[P], key: str, old: Any, new: Any) -> P:
    """`key` plus the fields of `new` that differ from `old` (all of them when `old` is None)."""
    fields = {
        f: getattr(new, f)
        for f in type(new).model_fields
        if f == key or old is None or getattr(old, f) != getattr(new, f)
    }
    return cls.model_construct(**fields)


def _seen(world: World, entity_id: int | None) -> bool:
    if entity_id is None:
        return False
    e = world.find(entity_id)
    return visible(world, _VIEWER, e) if e is not None else tracked_by(world, _VIEWER, entity_id)


def _public(world: World, e: Event) -> Event | None:
    """The coalition's view of `e` (CONTRACTS section 6, redaction column), or None to drop it."""
    if isinstance(e, _PUBLIC_AS_IS):
        return e
    if isinstance(e, CampaignClockPaused | CampaignClockResumed):
        return e.model_copy(update={"sub_reason": None})  # Q-ALN-39: the category only
    if isinstance(e, NodeCaptured):
        return e if e.to == _VIEWER else e.model_copy(update={"participant_commander_ids": []})
    if isinstance(e, UnitSpawned):
        return e if _seen(world, e.entity_id) else None
    if isinstance(e, UnitDestroyed) and (e.side == _VIEWER or _seen(world, e.entity_id)):
        return e.model_copy(
            update={
                "killer_id": e.killer_id if _seen(world, e.killer_id) else None,
                "assist_ids": [i for i in e.assist_ids if _seen(world, i)],
            }
        )
    return None
