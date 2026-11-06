"""NX-511 (GAMEPLAY §1b item 253): the balance harness counts AI wingmen from the kernel's own
events (`UnitSpawned`, `SupplyConsumed{SPAWN}`, `UnitDestroyed`, `UnitDespawned`) and the world's
flights and cooldowns, per seed and summed per profile."""

import sys
from pathlib import Path
from typing import Any

import pytest

from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.core.tasking import claim, post_job
from nexus.core.tasking_gen import JobSpec
from nexus.core.world import Vec2, World
from nexus.runtime.campaign_config import CampaignConfig, start_campaign

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "balance"))
import metrics  # type: ignore[import-not-found,unused-ignore]
import report  # type: ignore[import-not-found,unused-ignore]

JET: UnitKind = "STRIKE_FIGHTER"


def _collector(world: World) -> Any:
    return metrics.Collector(
        world, frozenset(), tick_hz=10, sample_ticks=600, a3_ticks=1000, idle_sample_ticks=600,
        impact_check_ticks=10, kinds={}, a2_min_tier="ALPHA", a2_refresh_ticks=18_000,
        starve_threshold=0.25,
    )  # fmt: skip


def _flight(config: CampaignConfig) -> tuple[World, Any, list[Event], list[int]]:
    """A viewer's landed jet at the sanctuary claims a STRIKE job: the kernel spawns its flight."""
    world = start_campaign("c", 1, config)
    assert world.rules is not None
    collector = _collector(world)
    node = world.rules.sanctuary
    world.pool["COALITION"] = 100
    pos = Vec2(*world.rules.roads.pos[node])
    lead = world.spawn(JET, "COALITION", "COMMANDER", pos, commander_id="viewer-1")
    lead.last_node, lead.home_base, lead.state = node, node, "LANDED"
    lead.fuel = world.rules.fuel_s[JET]
    world.last_command["viewer-1"] = world.campaign.running_ticks
    spec = JobSpec("STRIKE", "strike:t", 2, 1000, node="east-airbase")
    out: list[Event] = []
    claim(world, lead, post_job(world, "COALITION", spec, []), out)
    collector.feed(out)
    collector.observe(world)
    return world, collector, out, world.flights[lead.id].wingmen


def _destroyed(tick: int, eid: int) -> Any:
    return UnitDestroyed.model_construct(
        kind="UnitDestroyed", tick=tick, entity_id=eid, killer_id=None, assist_ids=[],
        side="COALITION",
    )  # fmt: skip


def _despawned(tick: int, eid: int, reason: str = "RETIRED") -> Any:
    return UnitDespawned.model_construct(
        kind="UnitDespawned", tick=tick, entity_id=eid, reason=reason
    )


def test_counts_a_flight_from_the_kernels_events_and_state(shipped_config: CampaignConfig) -> None:
    world, collector, out, ids = _flight(shipped_config)
    assert len(ids) == 2
    spent = sum(e.amount for e in out if e.kind == "SupplyConsumed" and e.cause == "SPAWN")
    assert spent == 2 * world.rules.supply.loadout_cost[JET] > 0  # type: ignore[union-attr]
    collector.observe(world)  # the flight is counted once, however many ticks it flies
    collector.feed([_destroyed(50, ids[0]), _despawned(60, ids[1])])
    got = collector.result(100)
    assert got["wingmen"] == {
        "flights": 1, "spawned": 2, "destroyed": 1, "retired": 1, "despawned_other": 0,
        "cooldowns": 0, "supply_spent": spent,
    }  # fmt: skip
    collector.feed([_despawned(70, ids[0], "WRECKED")])
    assert collector.result(100)["wingmen"]["despawned_other"] == 1
    assert collector.result(100)["wingmen"]["retired"] == 1
    assert got["retirements"]["retired"] == {"COALITION": 0, "ENEMY": 0}  # wingmen are not trucks


def test_only_wingmen_count(shipped_config: CampaignConfig) -> None:
    _, collector, out, _ = _flight(shipped_config)
    spawn = next(e for e in out if e.kind == "UnitSpawned")
    other = {"entity_id": 9001, "tick": spawn.tick}
    collector.feed([
        spawn.model_copy(update={**other, "side": "ENEMY"}),  # the Static's jet
        spawn.model_copy(update={**other, "unit_kind": "LOGI_TRUCK"}),  # an AI truck
        spawn.model_copy(update={**other, "unit_kind": "RECON_UAV"}),  # an unarmed aircraft
        spawn.model_copy(update={**other, "owner_kind": "COMMANDER"}),  # a viewer's jet
        _destroyed(70, 9001),
        _despawned(70, 9001),
    ])  # fmt: skip
    got = collector.result(100)
    assert (got["wingmen"]["spawned"], got["wingmen"]["destroyed"]) == (2, 0)
    assert got["wingmen"]["retired"] == 0
    assert got["retirements"]["retired"]["COALITION"] == 1  # id 9001 was last seen as the truck


def test_a_spawn_cost_is_the_one_paid_just_before_at_the_same_node(
    shipped_config: CampaignConfig,
) -> None:
    _, collector, out, _ = _flight(shipped_config)
    spawn = next(e for e in out if e.kind == "UnitSpawned")
    paid = next(e for e in out if e.kind == "SupplyConsumed")
    before = collector.result(100)["wingmen"]["supply_spent"]
    collector.feed([paid.model_copy(update={"node_id": "fob-n-w"})])  # another node's spawn
    collector.feed([spawn.model_copy(update={"entity_id": 9002})])
    collector.feed([paid.model_copy(update={"tick": spawn.tick - 1})])  # an earlier tick's
    collector.feed([spawn.model_copy(update={"entity_id": 9003})])
    collector.feed([spawn.model_copy(update={"entity_id": 9004})])  # no cost before it
    got = collector.result(100)["wingmen"]
    assert got["spawned"] == 5 and got["supply_spent"] == before


def test_cooldowns_count_each_start_once_and_a_restart_again(
    shipped_config: CampaignConfig,
) -> None:
    world = start_campaign("c", 1, shipped_config)
    collector = _collector(world)

    def seen() -> int:
        collector.observe(world)
        return int(collector.result(1)["wingmen"]["cooldowns"])

    assert seen() == 0
    world.wingmen_cooldown["viewer-1"] = 500
    assert seen() == 1 and seen() == 1  # one start, however many ticks it lasts
    world.wingmen_cooldown["viewer-2"] = 500
    assert seen() == 2
    world.wingmen_cooldown["viewer-1"] = 900  # a later flight's loss restarts it
    assert seen() == 3
    world.wingmen_cooldown.pop("viewer-1")  # ended and pruned
    assert seen() == 3
    world.wingmen_cooldown["viewer-1"] = 900  # the same end tick again: a new cooldown
    assert seen() == 4


def test_report_sums_seeds_shows_a_table_and_old_runs_are_zeros() -> None:
    one = {"flights": 1, "spawned": 2, "destroyed": 1, "retired": 1, "despawned_other": 0,
           "cooldowns": 1, "supply_spent": 40}  # fmt: skip
    runs: list[dict[str, Any]] = [
        {"seed": 1, "metrics": {"wingmen": one}},
        {"seed": 2, "metrics": {"wingmen": one}},
        {"seed": 3, "metrics": {}},  # from before NX-511, or a failed run
    ]
    assert report._wingmen_sum(runs) == {k: 2 * v for k, v in one.items()}
    assert report._wingmen(runs[2]) == dict.fromkeys(metrics.WINGMEN_KEYS, 0)
    prof = {"per_seed": [{"seed": r["seed"], "wingmen": report._wingmen(r)} for r in runs]}
    lines = report._wingmen_lines({"quiet-5": prof})
    assert "| quiet-5 | 1 | 1 | 2 | 1 | 1 | 0 | 1 | 40 |" in lines
    assert "| quiet-5 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |" in lines


@pytest.mark.parametrize("key", metrics.WINGMEN_KEYS)
def test_every_counter_is_in_the_result(key: str, shipped_config: CampaignConfig) -> None:
    world = start_campaign("c", 1, shipped_config)
    assert _collector(world).result(1)["wingmen"][key] == 0
