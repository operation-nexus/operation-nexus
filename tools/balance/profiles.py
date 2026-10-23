"""Crowd profiles, personas and targets from profiles.yaml, and the seeded arrival schedule
(NX-031 part 1, Q-SIM-91). The schedule uses its own `random.Random`, never the sim's streams."""

import hashlib
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from nexus.core.director import TIERS

DATA = Path(__file__).resolve().parent / "profiles.yaml"
KINDS = ("auto", "striker", "hauler", "scout")  # persona kinds (Q-SIM-95)
ROLES = ("STRIKE", "RECON", "LOGI")  # the playable roles (content/roles.yaml); NAVY is P3


@dataclass(frozen=True, slots=True)
class Persona:
    name: str
    role_weights: dict[str, float]
    hold: bool
    join_prob: float
    rejoin_prob: float
    max_attempts: int
    rejoin_delay_s: tuple[float, float]
    rebase_prob: float
    rebase_after_s: tuple[float, float]


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    viewers: int
    ramp_min: float
    arrivals_per_hour: float
    mix: dict[str, float]
    kinds: dict[str, float]  # persona-kind shares, sum to 1 (Q-SIM-95)


@dataclass(frozen=True, slots=True)
class Targets:
    a1_min_h: float
    a1_pass_frac: float
    a2_min_tier: str  # A2 counts newbies who arrive at this Static tier or above (Q-SIM-93)
    a2_max_s: float
    a2_tail_s: float  # A2 tail: first impact later than this (Q-SIM-97)
    a2_tail_share: float  # ... for at most this share of newbies
    a3_hours: float
    a3_max_nodes_lost: int
    a4_max_share: float
    a4_min_kills: int
    a4_suspended: bool  # A4 is reported, not judged (Q-SIM-92)


@dataclass(frozen=True, slots=True)
class Data:
    profiles: dict[str, Profile]
    personas: dict[str, Persona]
    targets: Targets
    impact_check_s: float  # game seconds between the capture-progress and scouting checks
    idle_sample_min: float  # game minutes between idle armed viewer-unit samples (Q-SIM-92)
    momentum_sample_s: float  # game seconds between momentum and starvation samples
    kind_roles: dict[str, str]  # persona kind (not auto) -> the JOIN role it always sends
    digest: str  # blake2b of the file, in every report


def _pair(value: Any, what: str) -> tuple[float, float]:
    lo, hi = value
    if not 0 <= lo <= hi:
        raise ValueError(f"{what}: need 0 <= min <= max, got {value}")
    return float(lo), float(hi)


def load(path: Path = DATA) -> Data:
    raw = path.read_bytes()
    doc = yaml.safe_load(raw)
    personas = {
        name: Persona(
            name,
            {r: float(w) for r, w in sorted(p["role_weights"].items())},
            bool(p["hold"]),
            float(p["join_prob"]),
            float(p["rejoin_prob"]),
            int(p["max_attempts"]),
            _pair(p["rejoin_delay_s"], f"{name}.rejoin_delay_s"),
            float(p["rebase_prob"]),
            _pair(p["rebase_after_s"], f"{name}.rebase_after_s"),
        )
        for name, p in doc["personas"].items()
    }
    for p in personas.values():
        if not set(p.role_weights) <= set(ROLES) or sum(p.role_weights.values()) <= 0:
            raise ValueError(f"persona {p.name}: role_weights must name {ROLES} and not be all 0")
        if not (0 <= p.join_prob <= 1 and 0 <= p.rejoin_prob <= 1 and 0 <= p.rebase_prob <= 1):
            raise ValueError(f"persona {p.name}: probabilities must be in 0..1")
    profiles = {
        name: Profile(
            name,
            int(p["viewers"]),
            float(p["ramp_min"]),
            float(p["arrivals_per_hour"]),
            {k: float(v) for k, v in sorted(p["mix"].items())},
            {k: float(v) for k, v in sorted(p["kinds"].items())},
        )
        for name, p in doc["profiles"].items()
    }
    for pr in profiles.values():
        if (pr.viewers or pr.arrivals_per_hour) and sum(pr.mix.values()) <= 0:
            raise ValueError(f"profile {pr.name}: a crowd needs a persona mix")
        if unknown := set(pr.mix) - set(personas):
            raise ValueError(f"profile {pr.name}: unknown personas {sorted(unknown)}")
        if not set(pr.kinds) <= set(KINDS) or min(pr.kinds.values(), default=-1) < 0:
            raise ValueError(f"profile {pr.name}: kinds must be shares of {KINDS}")
        if abs(sum(pr.kinds.values()) - 1) > 1e-9:
            raise ValueError(
                f"profile {pr.name}: kinds must sum to 1, got {sum(pr.kinds.values())}"
            )
    targets = Targets(**doc["targets"])
    if targets.a2_min_tier not in TIERS:
        raise ValueError(f"targets.a2_min_tier must be one of {TIERS}")
    if not 0 < targets.a2_tail_s < math.inf or not 0 < targets.a2_tail_share <= 1:
        raise ValueError("targets.a2_tail_s must be > 0 and a2_tail_share in (0, 1]")
    check_s = float(doc["impact_check_s"])
    if check_s <= 0:
        raise ValueError("impact_check_s must be > 0")
    idle_min = float(doc["idle_sample_min"])
    if idle_min <= 0:
        raise ValueError("idle_sample_min must be > 0")
    sample_s = float(doc["momentum_sample_s"])
    if not 0 < sample_s < math.inf:
        raise ValueError("momentum_sample_s must be > 0")
    kind_roles = {str(k): str(v) for k, v in sorted(doc["kind_roles"].items())}
    if not set(kind_roles) <= set(KINDS) - {"auto"} or not set(kind_roles.values()) <= set(ROLES):
        raise ValueError(f"kind_roles: keys must be non-auto kinds of {KINDS}, values of {ROLES}")
    for pr in profiles.values():
        if missing := {k for k in pr.kinds if k != "auto"} - set(kind_roles):
            raise ValueError(f"profile {pr.name}: kinds {sorted(missing)} have no kind_roles role")
    return Data(
        profiles,
        personas,
        targets,
        check_s,
        idle_min,
        sample_s,
        kind_roles,
        hashlib.blake2b(raw, digest_size=16).hexdigest(),
    )


def schedule(profile: Profile, seed: int, ticks: int, tick_hz: int) -> list[tuple[int, str]]:
    """`(arrival_tick, persona)` for every distinct viewer, in arrival order: `viewers` uniform in
    the ramp, then Poisson arrivals at `arrivals_per_hour` until `ticks`. Ticks are 1-based: the
    first command can target tick 1."""
    rng = random.Random(f"balance/schedule/{profile.name}/{seed}")  # noqa: S311  # harness RNG
    names = list(profile.mix)
    weights = [profile.mix[n] for n in names]
    ramp = max(1, round(profile.ramp_min * 60 * tick_hz))
    times = sorted(rng.randint(1, ramp) for _ in range(profile.viewers))
    if profile.arrivals_per_hour > 0:
        mean_ticks = 3600 * tick_hz / profile.arrivals_per_hour
        t = float(ramp)
        while (t := t + rng.expovariate(1 / mean_ticks)) <= ticks:
            times.append(int(t))
    return [(t, rng.choices(names, weights)[0]) for t in times if t <= ticks]
