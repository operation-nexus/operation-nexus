"""Golden replays (SIM-CORE SC-3, §5, §7; TESTING-STRATEGY §3.2; NX-105).

A case is a directory: `case.json` (campaign and run parameters), `log/` (a command log in the
NX-103 format, read with `CommandLogReader`) and `expected.json` (the pinned outputs). `run_golden`
builds the world from the seed, steps every tick from 1 to `ticks`, takes `state_hash` every
`checkpoints_every` ticks and hashes the event stream (blake2b-256 over one canonical JSON line
per event). Commands of a tombstoned tick are dropped, as in restore (SC-8). This module ships no
handlers: the caller passes the registries that a case's `handlers` name picks from. A case with
`"rules": "shipped"` starts from `start_campaign` with the shipped config (its rules and the
theater's facilities), and its `config_hash` must equal that config's, so a config change fails
loudly instead of drifting; any other case starts from an empty world with no rules.
"""

import hashlib
import json
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.events.event import Event
from nexus.core.step import Handler, step
from nexus.core.world import Campaign, World, state_hash
from nexus.runtime.campaign_config import (
    CampaignConfig,
    ConfigPaths,
    load_campaign_config,
    start_campaign,
)
from nexus.runtime.command_log import CommandLogReader, Tombstone

CASE_FILE = "case.json"
EXPECTED_FILE = "expected.json"
LOG_DIR = "log"
_CASE_KEYS = {
    "campaign_id": str,
    "seed": int,
    "config_hash": str,
    "ticks": int,
    "checkpoints_every": int,
    "handlers": str,
    "description": str,
}
_RULES = "rules"
_SHIPPED = "shipped"
_OVERRIDES = "overrides"


@dataclass(frozen=True, slots=True)
class GoldenResult:
    checkpoints: dict[str, str]  # tick as a decimal string (a JSON key) -> state_hash
    event_count: int
    events_hash: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def load_case(case_dir: Path) -> dict[str, Any]:
    case = json.loads((case_dir / CASE_FILE).read_text())
    if not isinstance(case, dict) or set(case) - {_RULES, _OVERRIDES} != set(_CASE_KEYS):
        raise ValueError(
            f"{case_dir.name}: {CASE_FILE} must have exactly {sorted(_CASE_KEYS)} "
            f"and optionally {_RULES!r} and {_OVERRIDES!r}"
        )
    if case.get(_OVERRIDES) and _RULES not in case:
        raise ValueError(f"{case_dir.name}: {_OVERRIDES} need {_RULES}: {_SHIPPED!r}")
    if case.get(_RULES, _SHIPPED) != _SHIPPED:
        raise ValueError(f"{case_dir.name}: {_RULES} must be {_SHIPPED!r}")
    for key, kind in _CASE_KEYS.items():
        if type(case[key]) is not kind:
            raise ValueError(f"{case_dir.name}: {key} must be {kind.__name__}")
    if case["ticks"] < 1 or case["checkpoints_every"] < 1:
        raise ValueError(f"{case_dir.name}: ticks and checkpoints_every must be >= 1")
    return case


def run_golden(case_dir: Path, registries: Mapping[str, Mapping[str, Handler]]) -> GoldenResult:
    case = load_case(case_dir)
    world = _world(case_dir.name, case)
    if case["handlers"] not in registries:
        raise ValueError(f"{case_dir.name}: unknown handler registry {case['handlers']!r}")
    handlers = registries[case["handlers"]]
    by_tick, tombstones = _read_log(case_dir, case["ticks"])
    digest = hashlib.blake2b(digest_size=32)
    count = 0
    checkpoints: dict[str, str] = {}
    for tick in range(1, case["ticks"] + 1):
        commands = by_tick.get(tick, [])
        if tick in tombstones:
            events = step(world, [], handlers, dropped=commands)
        else:
            events = step(world, commands, handlers)
        for event in events:
            digest.update(_event_line(event))
        count += len(events)
        if tick % case["checkpoints_every"] == 0:
            checkpoints[str(tick)] = state_hash(world)
    return GoldenResult(checkpoints, count, digest.hexdigest())


def _world(name: str, case: dict[str, Any]) -> World:
    if _RULES not in case:
        return World.new(Campaign(case["campaign_id"], case["seed"], case["config_hash"]))
    config = shipped_config(case.get(_OVERRIDES, {}))
    if case["config_hash"] != config.config_hash:
        raise ValueError(
            f"{name}: config_hash {case['config_hash']} is not the shipped config's "
            f"{config.config_hash}; rewrite the case (README) and update its expected.json"
        )
    return start_campaign(case["campaign_id"], case["seed"], config)


def shipped_config(overrides: Mapping[str, float]) -> CampaignConfig:
    """The shipped config, with `overrides` (a dotted balance key -> number, e.g.
    `director.pol.offensive_period_s`) applied to the balance profile: a golden case that needs a
    long period shortened says so in its `case.json`, and its `config_hash` covers the change."""
    if not overrides:
        return load_campaign_config()
    profile = yaml.safe_load(ConfigPaths().balance.read_text(encoding="utf-8"))
    for dotted, value in sorted(overrides.items()):
        *path, last = dotted.split(".")
        node = profile
        for part in path:
            node = node[part]
        if last not in node:
            raise ValueError(f"override {dotted}: no such balance key")
        node[last] = value
    with tempfile.TemporaryDirectory() as tmp:
        balance = Path(tmp) / "balance.yaml"
        balance.write_text(yaml.safe_dump(profile), encoding="utf-8")
        return load_campaign_config(replace(ConfigPaths(), balance=balance))


def write_expected(case_dir: Path, result: GoldenResult) -> None:
    """Rewrite `expected.json` (the golden update; see tests/golden/README.md for the policy)."""
    text = json.dumps(result.to_json(), indent=2) + "\n"  # checkpoints stay in tick order
    (case_dir / EXPECTED_FILE).write_text(text)


def _read_log(case_dir: Path, ticks: int) -> tuple[dict[int, list[Command]], set[int]]:
    log_dir = case_dir / LOG_DIR
    if not log_dir.is_dir():
        raise ValueError(f"{case_dir.name}: no {LOG_DIR}/ directory")
    by_tick: defaultdict[int, list[Command]] = defaultdict(list)
    tombstones: set[int] = set()
    reader = CommandLogReader(log_dir)
    for entry in reader:
        tick = entry.tick if isinstance(entry, Tombstone) else entry.target_tick
        if not 1 <= tick <= ticks:
            raise ValueError(f"{case_dir.name}: log names tick {tick}, outside 1..{ticks}")
        if isinstance(entry, Tombstone):
            tombstones.add(entry.tick)
        else:
            by_tick[entry.target_tick].append(entry)
    if reader.truncated_tail:
        raise ValueError(f"{case_dir.name}: the log's last frame is torn")
    return by_tick, tombstones


def _event_line(event: Event) -> bytes:
    data = event.model_dump(mode="json", by_alias=True)  # the contract's keys (`NodeCaptured.from`)
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode() + b"\n"
