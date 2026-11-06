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
KINDS = ("auto", "striker", "hauler", "scout", "capturer", "freelancer")  # persona kinds (Q-SIM-95)
# check profiles (NX-398, NX-321): named only, never in `--profile all`
CHECKS = ("freelance-50", "raid-300-agency")
OWN_ROLE = ("auto", "freelancer")  # kinds that join with the persona's own role, not kind_roles
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
    agency_share: float = 0.0  # share of striker and capturer viewers who are tacticians (NX-321)
    agency_threat_window_s: float = 300.0  # a tactician's "recent" CaptureStarted, game seconds
    rng_profile: str = ""  # the profile whose name keys every harness RNG and the campaign id

    @property
    def rng_name(self) -> str:
        """The name in every RNG key and the campaign id: `rng_profile`, else the profile's own."""
        return self.rng_profile or self.name


@dataclass(frozen=True, slots=True)
class Targets:
    a1_pass_frac: float
    a1_victory_min_viewers: int  # A1 judges victory-or-defeat only at this crowd size and up
    # Q-TEST-11 steamroll signals (all PROPOSED, recalibrated once a hard-fought run exists)
    steamroll_pressure_per_4h: float  # S1 fires under this many pressure events per 4 campaign h
    steamroll_swing_pts: int  # S3 fires under this momentum drop (points) ...
    steamroll_max_lead_changes: int  # ... and at most this many lead changes
    steamroll_lead_line: int  # the coalition leads above this momentum, the Static below
    steamroll_late_units_frac: float  # S4 fires under this share of the Static's peak units ...
    steamroll_late_stock_frac: float  # ... or under this share of its start stock
    steamroll_min_signals: int  # a steamroll also when this many of S1 to S4 fire
    a2_min_tier: str  # A2 counts newbies who arrive at this Static tier or above (Q-SIM-93)
    a2_refresh_unseen_game_min: float  # a re-found enemy untracked this long is a scout impact
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
            float(p.get("agency", {}).get("share", 0.0)),  # absent = 0 = no tacticians (NX-321)
            float(p.get("agency", {}).get("threat_window_s", 300.0)),
            str(p.get("rng_profile", "")),  # absent = the profile's own name
        )
        for name, p in doc["profiles"].items()
    }
    for pr in profiles.values():
        if pr.rng_profile and pr.rng_profile not in profiles:
            raise ValueError(f"profile {pr.name}: rng_profile names no profile")
        if not 0 <= pr.agency_share <= 1 or not 0 <= pr.agency_threat_window_s < math.inf:
            raise ValueError(f"profile {pr.name}: agency.share in 0..1 and threat_window_s >= 0")
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
    if not 0 < targets.a2_refresh_unseen_game_min < math.inf:
        raise ValueError("targets.a2_refresh_unseen_game_min must be > 0")
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
    keyed = set(KINDS) - set(OWN_ROLE)
    if not set(kind_roles) <= keyed or not set(kind_roles.values()) <= set(ROLES):
        raise ValueError(f"kind_roles: keys must be kinds of {sorted(keyed)}, values of {ROLES}")
    for pr in profiles.values():
        if missing := set(pr.kinds) - set(OWN_ROLE) - set(kind_roles):
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
    rng = random.Random(f"balance/schedule/{profile.rng_name}/{seed}")  # noqa: S311  # harness RNG
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
