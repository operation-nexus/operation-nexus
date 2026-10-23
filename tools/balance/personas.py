"""Scripted viewers (NX-031 part 1, Q-SIM-91). A viewer is a synthetic commander with a persona; it
sends only commands that exist: JOIN (a role; a striker adds a node target) and REBASE. Each
viewer has its own `random.Random`, so one viewer's luck never shifts another's. Behaviour
numbers are in profiles.yaml (PROPOSED)."""

import random
from collections.abc import Mapping
from dataclasses import dataclass

from profiles import Persona, Profile

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.commands.rebase import RebaseCommand

# Idle: nothing in flight. Pending: a JOIN is sent and not yet answered. Alive: has a unit.
# Gone: left (a viewer leaves only by losing its unit; there is no leave command, Q-SIM-91).
IDLE, PENDING, ALIVE, GONE = "idle", "pending", "alive", "gone"


@dataclass(slots=True)
class Viewer:
    index: int
    commander_id: str
    persona: Persona
    rng: random.Random
    kind: str = "auto"  # auto-tasked, striker, hauler or scout (Q-SIM-95)
    status: str = IDLE
    entity: int | None = None
    attempts: int = 0  # consecutive losses and rejections since the last spawn


def commander_id(index: int) -> str:
    """A synthetic, deterministic UUIDv7-shaped commander id (never a platform id)."""
    return f"0192f0c1-7a2b-7c3d-8e4f-{index:012d}"


def new_viewer(index: int, persona: Persona, profile: str, seed: int, kind: str = "auto") -> Viewer:
    rng = random.Random(f"balance/viewer/{profile}/{seed}/{index}")  # noqa: S311  # harness RNG
    return Viewer(index, commander_id(index), persona, rng, kind)


def draw_kind(profile: Profile, seed: int, index: int) -> str:
    """The viewer's persona kind: a seeded draw from the profile's `kinds` shares, from its own
    RNG so it never shifts the viewer's or the sim's streams."""
    rng = random.Random(f"balance/kind/{profile.name}/{seed}/{index}")  # noqa: S311  # harness RNG
    names = list(profile.kinds)
    return rng.choices(names, [profile.kinds[n] for n in names])[0]


def pick_node(v: Viewer, defended_foes: list[str]) -> str | None:
    """A striker's target: a seeded pick among the known defended foe nodes (sorted), or None."""
    return v.rng.choice(defended_foes) if v.kind == "striker" and defended_foes else None


def joins_on_arrival(v: Viewer) -> bool:
    return v.rng.random() < v.persona.join_prob


def rejoin_at(v: Viewer, now: int, tick_hz: int) -> int | None:
    """After a loss or a rejected JOIN: the tick it tries again, or None when it gives up."""
    p = v.persona
    v.attempts += 1
    if v.attempts > p.max_attempts or v.rng.random() >= p.rejoin_prob:
        return None
    return now + round(v.rng.uniform(*p.rejoin_delay_s) * tick_hz)


def rebase_at(v: Viewer, now: int, tick_hz: int) -> int | None:
    """After a spawn: the tick it sends its one REBASE, or None when it never does."""
    p = v.persona
    if v.rng.random() >= p.rebase_prob:
        return None
    return now + round(v.rng.uniform(*p.rebase_after_s) * tick_hz)


def join_command(
    v: Viewer, tick: int, seq: int, node: str | None, kind_roles: Mapping[str, str]
) -> JoinCommand:
    """The JOIN: the persona's role (auto) or the kind's (`kind_roles`, profiles.yaml); a node
    target only for a striker."""
    p = v.persona
    roles = list(p.role_weights)
    role = kind_roles.get(v.kind) or v.rng.choices(roles, [p.role_weights[r] for r in roles])[0]
    return JoinCommand.model_validate(
        {
            "kind": "JOIN",
            "source": "CHAT",
            "issuer": {"commander_id": v.commander_id},
            "target_tick": tick,
            "arrival_seq": seq,
            "correlation_id": f"v{v.index}-{seq}",
            "role": role,
            "target": None if node is None else {"node_id": node},
            "hold": p.hold and node is None,
        }
    )


def rebase_command(v: Viewer, node: str, tick: int, seq: int) -> RebaseCommand:
    return RebaseCommand.model_validate(
        {
            "kind": "REBASE",
            "source": "CHAT",
            "issuer": {"commander_id": v.commander_id},
            "target_tick": tick,
            "arrival_seq": seq,
            "correlation_id": f"v{v.index}-{seq}",
            "node_id": node,
        }
    )
