"""Balance harness tests (NX-031 part 1, Q-SIM-91; tools/balance). Short runs only."""

import dataclasses
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
import yaml
from pydantic import TypeAdapter

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.events.bridge_destroyed import BridgeDestroyed
from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.capture_started import CaptureStarted
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.contracts.gen.events.node_defenses_down import NodeDefensesDown
from nexus.contracts.gen.events.spawn_refused import SpawnRefused
from nexus.contracts.gen.events.supply_consumed import SupplyConsumed
from nexus.contracts.gen.events.supply_delivered import SupplyDelivered
from nexus.contracts.gen.events.supply_produced import SupplyProduced
from nexus.contracts.gen.events.supply_shortfall import SupplyShortfall
from nexus.contracts.gen.events.threat_adaptation import ThreatAdaptation
from nexus.contracts.gen.events.threat_tier_changed import ThreatTierChanged
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.contracts.gen.events.unit_grounded import UnitGrounded
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.contracts.gen.events.victory_hold_started import VictoryHoldStarted
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.contracts.gen.events.weapon_impact import WeaponImpact
from nexus.core.campaign import campaign, momentum
from nexus.core.step import HANDLERS, step
from nexus.core.tasking import post_job
from nexus.core.tasking_gen import JobSpec
from nexus.core.world import CaptureBar, Claim, Contact, Job, Vec2
from nexus.runtime.campaign_config import CampaignConfig, start_campaign
from nexus.runtime.command_log import CommandLogReader, Tombstone

# The harness modules live in tools/balance, outside the package: put them on the path, as the
# other tool tests reach their scripts. mypy cannot see them from here, so they type as Any.
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "balance"))
import balance  # type: ignore[import-not-found,unused-ignore]
import metrics  # type: ignore[import-not-found,unused-ignore]
import orders  # type: ignore[import-not-found,unused-ignore]
import personas  # type: ignore[import-not-found,unused-ignore]
import report  # type: ignore[import-not-found,unused-ignore]
import runner  # type: ignore[import-not-found,unused-ignore]
import steamroll  # type: ignore[import-not-found,unused-ignore]
from profiles import (  # type: ignore[import-not-found,unused-ignore]
    DATA,
    KINDS,
    ROLES,
    Data,
    load,
    schedule,
)

HZ = 10
TICKS = 3600  # 6 game minutes


@pytest.fixture(scope="module")
def data() -> Data:
    """prime-50's mix with a fast, small crowd, so a 6 minute run has every persona in play."""
    full = load()
    crowd = dataclasses.replace(full.profiles["prime-50"], viewers=40, ramp_min=1)
    return dataclasses.replace(full, profiles={**full.profiles, "prime-50": crowd})


def run_once(tmp: Path, name: str, data: Data, config: CampaignConfig, seed: int = 1) -> Any:
    return runner.run("prime-50", seed, TICKS / HZ / 3600, tmp / name, data, config)


def strip_timing(run: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in run.items() if k != "timing"}


def log_entries(directory: Path) -> list[dict[str, Any]]:
    entries = [e for e in CommandLogReader(directory) if not isinstance(e, Tombstone)]
    return [e.model_dump(mode="json") for e in entries]


@pytest.fixture(scope="module")
def first(
    tmp_path_factory: pytest.TempPathFactory, data: Data, shipped_config: CampaignConfig
) -> Any:
    tmp = tmp_path_factory.mktemp("balance")
    return tmp, run_once(tmp, "a", data, shipped_config)


# --- the runner -------------------------------------------------------------------------------
def test_same_seed_same_report_and_log(
    first: Any, tmp_path: Path, data: Data, shipped_config: CampaignConfig
) -> None:
    tmp, a = first
    b = run_once(tmp_path, "b", data, shipped_config)
    assert strip_timing(a) == strip_timing(b)
    assert log_entries(tmp / "a") == log_entries(tmp_path / "b")
    assert a["commands"]["JOIN"] > 10  # the crowd did something
    sf = a["metrics"]["economy"]["shortfall"]  # a real run carries the NX-437 counts
    assert sf["window_ticks"] == 600 and sf["windows"] == a["ticks_run"] // 600
    other = run_once(tmp_path, "c", data, shipped_config, seed=2)
    assert other["final_state_hash"] != a["final_state_hash"]


def test_log_replays_to_the_same_state_hash(first: Any, shipped_config: CampaignConfig) -> None:
    tmp, a = first
    got = runner.replay_log(tmp / "a", a["seed"], a["profile"], a["ticks_run"], shipped_config)
    assert got == a["final_state_hash"]
    assert a["config_hash"] == shipped_config.config_hash


def test_every_logged_command_is_valid_and_existing(first: Any) -> None:
    tmp, a = first
    entries = log_entries(tmp / "a")
    adapter: TypeAdapter[Command] = TypeAdapter(Command)
    assert [e["arrival_seq"] for e in entries] == list(range(1, len(entries) + 1))
    for e in entries:
        adapter.validate_python(e)
        assert e["kind"] in ("JOIN", "REBASE")  # no other command exists for a persona
        if e["kind"] == "JOIN":
            assert e["role"] in ROLES
            assert e["target"] is None or e["role"] in ("STRIKE", "LOGI")  # striker or capturer
    assert a["commands"] == {
        k: sum(e["kind"] == k for e in entries) for k in sorted({e["kind"] for e in entries})
    }


# --- personas ---------------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(load().personas))
def test_persona_emits_only_valid_commands(name: str) -> None:
    persona = load().personas[name]
    v = personas.new_viewer(7, persona, "prime-50", 1)
    adapter: TypeAdapter[Command] = TypeAdapter(Command)
    join = personas.join_command(v, 5, 1, None, load().kind_roles)
    rebase = personas.rebase_command(v, "west-airbase", 6, 2)
    for cmd in (join, rebase):
        adapter.validate_python(cmd.model_dump(mode="json"))
    assert join.role in persona.role_weights and join.hold == persona.hold
    assert join.issuer.commander_id == personas.commander_id(7) == rebase.issuer.commander_id


def test_persona_rules() -> None:
    d = load().personas
    lurkers = [personas.new_viewer(i, d["lurker"], "p", 1) for i in range(400)]
    assert sum(personas.joins_on_arrival(v) for v in lurkers) < 400 * 0.15  # "rarely"
    assert all(
        personas.joins_on_arrival(personas.new_viewer(i, d["newbie"], "p", 1)) for i in range(50)
    )
    afk = personas.new_viewer(1, d["afk-farmer"], "p", 1)
    assert afk.persona.hold and personas.rejoin_at(afk, 100, HZ) is None  # never comes back
    vet = personas.new_viewer(2, d["veteran"], "p", 1)
    lo, hi = vet.persona.rejoin_delay_s
    times = [personas.rejoin_at(vet, 100, HZ) for _ in range(vet.persona.max_attempts)]
    assert all(t is None or 100 + lo * HZ <= t <= 100 + hi * HZ for t in times)
    assert personas.rejoin_at(vet, 100, HZ) is None  # past max_attempts it gives up
    assert all(p.rebase_prob == 0 for p in d.values())  # off until unit orders exist (NX-192)
    on = personas.new_viewer(3, dataclasses.replace(d["veteran"], rebase_prob=1.0), "p", 1)
    lo, hi = on.persona.rebase_after_s
    assert 100 + lo * HZ <= personas.rebase_at(on, 100, HZ) <= 100 + hi * HZ  # the path still works
    assert personas.rebase_at(vet, 100, HZ) is None


def test_schedule_is_seeded_sorted_and_sized() -> None:
    p = load().profiles["prime-50"]
    s = schedule(p, 3, 72 * 36000, HZ)
    assert s == schedule(p, 3, 72 * 36000, HZ) and s != schedule(p, 4, 72 * 36000, HZ)
    assert [t for t, _ in s] == sorted(t for t, _ in s) and s[0][0] >= 1
    assert sum(t <= 30 * 60 * HZ for t, _ in s) == 50  # the ramp holds exactly `viewers`
    assert 50 + 10 * 72 * 0.6 < len(s) < 50 + 10 * 72 * 1.4  # then ~10 an hour
    assert schedule(load().profiles["overnight-0"], 1, 36000, HZ) == []


# --- metrics on hand-built event streams ----------------------------------------------------------
def commander(n: int) -> str:
    return str(personas.commander_id(n))


def spawned(tick: int, entity: int, kind: str, side: str, cmdr: str | None) -> Any:
    return UnitSpawned.model_construct(
        kind="UnitSpawned",
        tick=tick,
        entity_id=entity,
        unit_kind=kind,
        side=side,
        commander_id=cmdr,
    )


def killed(tick: int, victim: int, killer: int | None, side: str = "ENEMY") -> Any:
    return UnitDestroyed.model_construct(
        kind="UnitDestroyed",
        tick=tick,
        entity_id=victim,
        killer_id=killer,
        assist_ids=[],
        side=side,
    )


@pytest.fixture
def collector(shipped_config: CampaignConfig) -> metrics.Collector:
    world = start_campaign("c", 1, shipped_config)
    newbies = frozenset(commander(n) for n in (1, 2, 3, 4, 5))
    return metrics.Collector(
        world,
        newbies,
        tick_hz=HZ,
        sample_ticks=600,
        a3_ticks=1000,
        idle_sample_ticks=600,
        impact_check_ticks=10,
        kinds={commander(n): "scout" if n == 5 else "auto" for n in range(1, 7)},
        a2_min_tier="ALPHA",
    )


def test_newbie_time_to_first_impact(collector: metrics.Collector) -> None:
    for n in (1, 2, 3, 4, 5, 6):  # 6 is not a newbie
        collector.note_join(commander(n), 100, "ALPHA")
    collector.note_join(commander(1), 900, "BRAVO")  # only the first JOIN counts
    collector.feed([spawned(110, 901, "STRIKE_FIGHTER", "COALITION", commander(1))])
    collector.feed([spawned(110, 902, "LOGI_TRUCK", "COALITION", commander(2))])
    collector.feed([spawned(110, 906, "STRIKE_FIGHTER", "COALITION", commander(6))])
    miss = WeaponImpact.model_construct(kind="WeaponImpact", tick=150, shooter_id=901, hit=False)
    hit = WeaponImpact.model_construct(kind="WeaponImpact", tick=400, shooter_id=901, hit=True)
    other = WeaponImpact.model_construct(kind="WeaponImpact", tick=120, shooter_id=906, hit=True)
    late = WeaponImpact.model_construct(kind="WeaponImpact", tick=900, shooter_id=901, hit=True)
    delivery = SupplyDelivered.model_construct(
        kind="SupplyDelivered", tick=700, commander_id=commander(2)
    )
    capture = NodeCaptured.model_construct(
        kind="NodeCaptured",
        tick=1100,
        node_id="cross-n",
        from_="NEUTRAL",
        to="COALITION",
        participant_commander_ids=[commander(3)],
    )
    collector.feed([miss, hit, other, late, delivery, capture])
    kill = killed(500, 950, 901)  # a later kill by 1 does not move its first impact
    collector.feed([kill])
    n = collector.result(2000)["newbie"]
    assert n["joined"] == 5
    assert n["ttfi_s"] == [30.0, 60.0, 100.0]  # 1: tick 400; 2: delivery at 700; 3: capture at 1100
    assert n["no_impact_observed_s"] == [190.0, 190.0]  # 4 and 5 joined at 100, run ends at 2000


def test_kill_share_by_unit_kind(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    collector.feed(
        [
            spawned(1, 901, "STRIKE_FIGHTER", "COALITION", commander(9)),
            spawned(1, 902, "RECON_UAV", "COALITION", commander(10)),
            spawned(1, 903, "ENEMY_FIGHTER", "ENEMY", None),
            spawned(1, 904, "AIR_DEFENSE_SITE", "COALITION", None),  # an AI facility
        ]
    )
    collector.feed([killed(5, 100, 901), killed(6, 101, 901), killed(7, 102, 901)])
    collector.feed([killed(8, 103, 902), killed(9, 104, None), killed(10, 105, 12345)])
    collector.feed([killed(12, 106, 904)])
    collector.feed([killed(11, 901, 903, side="COALITION")])  # the enemy's kill is not counted
    k = collector.result(100)["kills"]
    assert k == {
        "by_kind": {"AIR_DEFENSE_SITE": 1, "RECON_UAV": 1, "STRIKE_FIGHTER": 3},
        "player_by_kind": {"RECON_UAV": 1, "STRIKE_FIGHTER": 3},
        "total": 5,
        "unattributed": 2,
    }
    live = dataclasses.replace(load().targets, a4_suspended=False)
    few = dataclasses.replace(live, a4_min_kills=1)
    pooled = report._a4([{"metrics": {"kills": k}}], few)
    assert pooled["status"] == report.FAIL  # the target uses the all-coalition share
    assert pooled["top"] == {"kind": "STRIKE_FIGHTER", "share": 0.6}
    assert pooled["player_share"] == {"RECON_UAV": 0.25, "STRIKE_FIGHTER": 0.75}
    assert pooled["player_kills"] == 4 and pooled["coalition_kills"] == 5
    assert report._a4([{"metrics": {"kills": k}}], live)["status"] == report.NO_DATA


def test_nodes_lost_tier_dwell_and_outcome(collector: metrics.Collector) -> None:
    def captured(tick: int, node: str, frm: str, to: str) -> Any:
        return NodeCaptured.model_construct(
            kind="NodeCaptured",
            tick=tick,
            node_id=node,
            from_=frm,
            to=to,
            participant_commander_ids=[],
        )

    collector.feed(
        [
            captured(500, "west-airbase", "COALITION", "ENEMY"),  # strategic, inside the window
            captured(600, "bridge-n", "COALITION", "ENEMY"),  # a bridge is not strategic
            captured(700, "cross-n", "NEUTRAL", "COALITION"),  # a gain
            captured(1500, "fob-n-w", "COALITION", "ENEMY"),  # strategic, after the window
        ]
    )
    for tick, a, b in ((100, "PATTERN_OF_LIFE", "ALPHA"), (400, "ALPHA", "BRAVO")):
        collector.feed(
            [
                ThreatTierChanged.model_construct(
                    kind="ThreatTierChanged", tick=tick, side="ENEMY", from_=a, to=b
                )
            ]
        )
    collector.feed(
        [
            ThreatTierChanged.model_construct(
                kind="ThreatTierChanged", tick=450, side="COALITION", from_="BRAVO", to="ALPHA"
            )
        ]
    )  # only the Static's Director is measured
    collector.feed(
        [
            CampaignEnded.model_construct(
                kind="CampaignEnded",
                tick=1000,
                result="VICTORY",
                winner="COALITION",
                end_tick=1000,
                nodes_held_pct=75,
            )
        ]
    )
    r = collector.result(1000)
    assert r["nodes_lost"] == [
        {"tick": 500, "node": "west-airbase"},
        {"tick": 1500, "node": "fob-n-w"},
    ]
    assert r["nodes_lost_in_a3_window"] == 1
    assert r["director"] == {
        "tier_dwell_s": {"ALPHA": 30.0, "BRAVO": 60.0, "PATTERN_OF_LIFE": 10.0},
        "tier_changes": 2,
    }
    assert r["outcome"]["result"] == "VICTORY" and r["outcome"]["length_h"] == 1000 / 36000


def test_samples_and_sanctuary_hp(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    world = start_campaign("c", 1, shipped_config)
    world.campaign.tick = 500
    collector.sample(world)
    base = collector.result(500)
    assert base["starvation"] == {"any_node_minutes": 0.0, "node_minutes": 0.0}
    world.stock["west-airbase"] = 0  # below its starvation floor, coalition-held
    world.stock["fob-n-w"] = 0
    world.defense_hp["haven"] = 0
    collector.sample(world)
    collector.observe(world)
    world.campaign.tick = 1500  # outside the A3 window
    world.defense_hp["haven"] = 7
    collector.observe(world)
    r = collector.result(1500)
    assert r["starvation"] == {"any_node_minutes": 1.0, "node_minutes": 2.0}  # 600 ticks = 1 min
    assert r["sanctuary_hp"] == {"min": 0, "min_in_a3_window": 0}
    first, second = r["momentum"]["samples"]
    assert second < first == momentum(start_campaign("c", 1, shipped_config)).momentum_pct


# --- report and CLI -----------------------------------------------------------------------------
def newbie(ttfi: list[float], never: list[float]) -> dict[str, Any]:
    return {
        "joined_below_tier": 0,
        "below_tier_ttfi_s": [],
        "ttfi_s": ttfi,
        "no_impact_observed_s": never,
        "first_impact_kinds": {},
        "by_kind": {},
    }


def fake_run(hours: float = 72, **over: Any) -> dict[str, Any]:
    outcome = {"ended": True, "result": "VICTORY", "length_h": 40.0}
    run: dict[str, Any] = {
        "seed": 1,
        "crash": None,
        "harness_error": None,
        "hours": hours,
        "ticks_run": round(hours * 36000),
        "a3_ticks": 12 * 36000,
        "time_limit_h": 72.0,
        "metrics": {
            "outcome": outcome,
            "newbie": newbie([60.0, 120.0], []),
            "nodes_lost_in_a3_window": 0,
            "sanctuary_hp": {"min_in_a3_window": 500},
        },
    }
    run["metrics"].update(over)
    return run


def test_target_rules() -> None:
    t = load().targets
    runs = [fake_run() for _ in range(6)] + [
        fake_run(outcome={"ended": True, "result": "TIME_LIMIT", "length_h": 72.0})
    ]
    assert report._a1(runs, t)["status"] == report.PASS  # 6/7 = 86%
    runs[5] = runs[6]
    assert report._a1(runs, t)["status"] == report.FAIL  # 5/7
    assert report._a1([fake_run(hours=2)], t)["status"].startswith("not evaluable")
    early = fake_run(outcome={"ended": True, "result": "DEFEAT", "length_h": 3.0})
    assert report._a1([early], t)["seeds_in_window"] == 1  # no 24 h floor (Q-TEST-6, 2026-10-24)
    slow = fake_run(newbie=newbie([100.0], [400.0, 500.0]))
    assert report._a2([slow], t)["status"] == report.FAIL  # two of three never saw an impact
    assert report._a2([fake_run()], t)["status"] == report.PASS
    two = report._a2([fake_run(newbie=newbie([100.0, 700.0], []))], t)
    assert two["status"] == report.PASS and "median 400 s time to first impact" in two["detail"]
    assert report._a2([fake_run(newbie=newbie([100.0, 900.0], []))], t)["status"] == report.FAIL
    unresolved = fake_run(newbie=newbie([], [10.0]))
    assert report._a2([unresolved], t)["status"] == report.NO_DATA
    assert report._a3([fake_run()], t, "overnight-0")["status"] == report.PASS
    assert (
        report._a3([fake_run(nodes_lost_in_a3_window=2)], t, "overnight-0")["status"] == report.FAIL
    )
    dead = fake_run(sanctuary_hp={"min_in_a3_window": 0})
    assert report._a3([dead], t, "overnight-0")["status"] == report.FAIL
    assert report._a3([fake_run(hours=2)], t, "overnight-0")["status"].startswith("not evaluable")
    # a crash inside the window is a fail, even with clean numbers; one after it is not
    crashed = fake_run(hours=12) | {"crash": {"tick": 30, "error": "x"}, "ticks_run": 29}
    assert report._a3([crashed], t, "overnight-0")["status"] == report.FAIL
    late = fake_run(hours=13) | {"crash": {"tick": 13 * 36000, "error": "x"}}
    assert report._a3([late], t, "overnight-0")["status"] == report.PASS
    ended = fake_run(hours=12) | {"ticks_run": 100}  # stopped short, no crash
    assert report._a3([fake_run(), ended], t, "overnight-0")["status"].startswith("not evaluable")
    broken = fake_run() | {"harness_error": "KeyError: x"}
    assert report._a3([broken], t, "overnight-0")["status"].startswith("not evaluable")
    assert report._a3([fake_run()], t, "prime-50")["status"] == "n/a"


def test_a4_is_suspended_but_still_reports_the_top_kind() -> None:
    t = load().targets
    assert t.a4_suspended  # Q-SIM-92
    a4 = report._a4([fake_run(kills={"by_kind": {"A": 40, "B": 1}})], t)
    assert a4["status"] == report.SUSPENDED and a4["top"]["kind"] == "A"
    assert report._a4([fake_run(kills={"by_kind": {"A": 1}})], t)["status"] == report.SUSPENDED


def test_a4_needs_a_minimum_sample() -> None:
    t = dataclasses.replace(load().targets, a4_suspended=False)
    enough = t.a4_min_kills
    top = round(t.a4_max_share * enough)  # exactly at the limit passes
    rest = enough - top
    even = fake_run(kills={"by_kind": {"A": top, "B": rest // 2, "C": rest - rest // 2}})
    assert report._a4([even], t)["status"] == report.PASS
    skew = fake_run(kills={"by_kind": {"A": enough, "B": 1}})
    assert report._a4([skew], t)["status"] == report.FAIL
    thin = fake_run(kills={"by_kind": {"A": enough - 1}})  # all one kind, but too few to say
    assert report._a4([thin], t)["status"] == report.NO_DATA
    assert report._a4([thin, thin], t)["status"] == report.FAIL  # pooled over seeds


def test_a_harness_error_is_recorded_and_the_batch_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = runner.run

    def flaky(profile: str, seed: int, *args: Any, **kw: Any) -> Any:
        if profile == "quiet-5":
            raise KeyError("oops")
        return real(profile, seed, *args, **kw)

    monkeypatch.setattr(runner, "run", flaky)
    out = tmp_path / "o"
    argv = ["balance.py", "--profile", "overnight-0,quiet-5", "--hours", "0.02", "--out", str(out)]
    monkeypatch.setattr(sys, "argv", argv)
    assert balance.main() == 0
    doc = json.loads((out / "report.json").read_text())
    outcomes = {r["profile"]: r["outcome"] for r in doc["runs"]}
    assert outcomes["quiet-5"] == "HARNESS ERROR: KeyError: 'oops'"
    assert outcomes["overnight-0"] == "not ended"
    assert doc["profiles"]["quiet-5"]["A1"]["outcomes"] == {"HARNESS_ERROR": 1}
    assert doc["profiles"]["quiet-5"]["A1"]["status"] == report.NO_DATA
    assert (out / "report.md").is_file()


class _FakePool:
    """An executor that only records the order items were submitted in."""

    log: ClassVar[list[Any]] = []

    def __init__(self, max_workers: int) -> None:
        pass

    def submit(self, fn: Any, job: Any) -> Any:
        _FakePool.log.append(job[:2])
        return SimpleNamespace(result=lambda: fn(job))

    def __enter__(self) -> "_FakePool":
        return self

    def __exit__(self, *a: Any) -> None:
        pass


def _jobs() -> list[Any]:
    return [
        (n, s, 1.0, Path("."), None) for n in ("quiet-5", "raid-300", "prime-50") for s in (1, 2)
    ]


def test_jobs_start_longest_first_and_ties_keep_job_order() -> None:
    data = load()
    _FakePool.log = []
    jobs = _jobs()
    balance.run_jobs(
        jobs, lambda j: data.profiles[j[0]].viewers, 2, _FakePool, lambda j: {"id": (j[0], j[1])}
    )
    assert _FakePool.log == [
        ("raid-300", 1), ("raid-300", 2), ("prime-50", 1), ("prime-50", 2),
        ("quiet-5", 1), ("quiet-5", 2),
    ]  # fmt: skip


def test_a_freed_worker_takes_the_next_waiting_item() -> None:
    """Backfill rests on submitting every run on its own before waiting on any (no fixed chunks):
    the executor then hands the next waiting run to whichever worker frees up. Checked with a pool
    that logs each submit and each result wait, so no thread timing or wall-clock limit is used."""
    events: list[str] = []

    class Pool(_FakePool):
        def submit(self, fn: Any, job: Any) -> Any:
            events.append(f"submit {job[1]}")

            def result() -> Any:
                events.append(f"wait {job[1]}")
                return fn(job)

            return SimpleNamespace(result=result)

    jobs = [("p", s, 1.0, Path("."), None) for s in range(1, 7)]
    runs = balance.run_jobs(jobs, lambda j: 1, 2, Pool, lambda j: {"seed": j[1]})
    assert [r["seed"] for r in runs] == [1, 2, 3, 4, 5, 6]
    assert events[:6] == [f"submit {s}" for s in range(1, 7)]  # each run alone, all before a wait
    assert events[6:] == [f"wait {s}" for s in range(1, 7)]


def test_results_come_back_in_job_order_whatever_finishes_first() -> None:
    from concurrent.futures import ThreadPoolExecutor

    jobs = _jobs()
    cost = {"quiet-5": 5, "raid-300": 300, "prime-50": 50}
    runs = balance.run_jobs(
        jobs, lambda j: cost[j[0]], 3, ThreadPoolExecutor, lambda j: {"id": (j[0], j[1])}
    )
    assert [r["id"] for r in runs] == [j[:2] for j in jobs]


def test_cli_report_is_the_same_with_any_worker_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shipped_config: CampaignConfig
) -> None:
    outs = []
    for workers in (1, 2):
        out = tmp_path / f"w{workers}"
        argv = [
            "balance.py",
            "--profile",
            "overnight-0,quiet-5",
            "--seeds",
            "1,2",
            "--hours",
            "0.02",
            "--workers",
            str(workers),
            "--out",
            str(out),
        ]
        monkeypatch.setattr(sys, "argv", argv)
        assert balance.main() == 0
        doc = json.loads((out / "report.json").read_text())
        doc.pop("timing"), doc.pop("workers")
        for r in doc["runs"]:
            r.pop("wall_s"), r.pop("ticks_per_s")
        outs.append(doc)
        assert len(list((out / "runs").glob("*.json"))) == 4 and (out / "report.md").is_file()
    assert outs[0] == outs[1]
    assert outs[0]["config"]["config_hash"] == shipped_config.config_hash
    assert outs[0]["seeds"] == [1, 2]
    assert all(r["ticks_run"] == 720 for r in outs[0]["runs"])
    rows = {(r["target"], r["profile"]): r["status"] for r in outs[0]["targets"]}
    assert (
        rows[("A5 adversarial bound", "all")]
        == rows[("A6 conduct", "all")]
        == report.NOT_MEASURABLE
    )
    assert rows[("A1", "quiet-5")].startswith("not evaluable")  # 0.02 h is far short of 72 h
    assert rows[("orders", "quiet-5")] == report.PASS  # no stuck order, no stale claim


def _cli(monkeypatch: pytest.MonkeyPatch, out: Path, *extra: str) -> int:
    argv = ["balance.py", "--profile", "quiet-5", "--seeds", "1,2,3", "--hours", "0.02"]
    monkeypatch.setattr(sys, "argv", [*argv, "--out", str(out), *extra])
    return int(balance.main())


def _comparable(out: Path) -> dict[str, Any]:
    doc = json.loads((out / "report.json").read_text())
    doc.pop("timing"), doc.pop("workers")
    for r in doc["runs"]:
        r.pop("wall_s"), r.pop("ticks_per_s")
    return dict(doc)


def test_resume_reruns_only_missing_or_bad_runs_and_matches_a_clean_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shipped_config: CampaignConfig
) -> None:
    """NX-433: a kill leaves run files missing or half-written. The resumed report equals an
    uninterrupted job's apart from wall-clock fields (`timing`, `workers`, each run's wall_s and
    ticks_per_s)."""
    clean, cut = tmp_path / "clean", tmp_path / "cut"
    assert _cli(monkeypatch, clean) == 0 and _cli(monkeypatch, cut) == 0
    kept = (cut / "runs" / "quiet-5-s1.json").read_bytes()
    (cut / "runs" / "quiet-5-s2.json").unlink()  # killed before it was written
    (cut / "runs" / "quiet-5-s3.json").write_text('{"profile": "quiet-5", "se')  # half a file
    (cut / "report.json").unlink()
    (cut / "report.md").unlink()
    ran: list[int] = []
    real = runner.run

    def spy(profile: str, seed: int, *a: Any, **kw: Any) -> Any:
        ran.append(seed)
        return real(profile, seed, *a, **kw)

    monkeypatch.setattr(runner, "run", spy)
    assert _cli(monkeypatch, cut) == 2  # without --resume an existing --out is still refused
    assert _cli(monkeypatch, cut, "--resume") == 0
    assert sorted(ran) == [2, 3]  # seed 1 was kept
    assert (cut / "runs" / "quiet-5-s1.json").read_bytes() == kept
    assert _comparable(cut) == _comparable(clean)
    assert not list((cut / "runs").glob("*.tmp"))


def test_load_done_trusts_only_a_matching_complete_file(tmp_path: Path) -> None:
    (tmp_path / "runs").mkdir()
    job = ("quiet-5", 1, 1.0, tmp_path, None)
    path = tmp_path / "runs" / "quiet-5-s1.json"
    good = {
        "profile": "quiet-5", "seed": 1, "hours": 1.0, "config_hash": "h", "ticks_run": 5,
        "metrics": {}, "timing": {}, "crash": None, "harness_error": None,
        "final_state_hash": "x",
    }  # fmt: skip
    assert balance.load_done(job, "h") is None  # missing
    path.write_text(json.dumps(good))
    assert balance.load_done(job, "h") == good
    assert balance.load_done(job, "other") is None  # another config
    for bad in ({"seed": 2}, {"hours": 2.0}, {"profile": "x"}, {"config_hash": None}):
        path.write_text(json.dumps(good | bad))
        assert balance.load_done(job, "h") is None
    path.write_text(json.dumps({k: v for k, v in good.items() if k != "timing"}))
    assert balance.load_done(job, "h") is None  # a key the report reads is missing
    path.write_text("[1]")
    assert balance.load_done(job, "h") is None


def test_a_sim_crash_is_recorded_not_raised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    data: Data,
    shipped_config: CampaignConfig,
) -> None:
    real = runner.step

    def flaky(world: Any, cmds: Any, handlers: Any) -> Any:
        if world.campaign.tick == 99:
            raise ValueError("boom")
        return real(world, cmds, handlers)

    monkeypatch.setattr(runner, "step", flaky)
    run = runner.run("prime-50", 1, 0.1, tmp_path / "x", data, shipped_config)
    assert run["crash"] == {"tick": 100, "error": "ValueError: boom"}
    assert run["ticks_run"] == 99 and run["final_state_hash"] is None
    a1 = report._a1([run], load().targets)
    assert a1["outcomes"] == {"CRASHED": 1} and a1["seeds_in_window"] == 0


def test_idle_sampling_counts_idle_armed_viewer_units_and_why(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    world = start_campaign("c", 1, shipped_config)
    collector.sample_idle(world)  # no viewer unit yet: no sample
    assert collector.idle_shares == []
    node = Vec2(*shipped_config.rules.roads.pos["west-airbase"])
    jet = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", node, commander_id=commander(1))
    held = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", node, commander_id=commander(2))
    held.order = "HOLD"
    jet.state = held.state = "LANDED"
    collector.sample_idle(world)
    assert collector.idle_shares == [0.5] and dict(collector.idle_reasons) == {"no_job": 1}
    idle = collector.result(100)["idle"]
    assert (idle["samples"], idle["share_max"], idle["reasons"]) == (1, 0.5, {"no_job": 1})
    agg = report._idle([{"metrics": {"idle": idle}}, {"metrics": {"idle": idle}}])
    assert (agg["samples"], agg["share_mean"], agg["reasons"]) == (2, 0.5, {"no_job": 2})


# --- A2 at ALPHA or above, impact kinds, persona kinds (NX-383, Q-SIM-93, Q-SIM-95) ---------
def test_a2_counts_only_arrivals_at_alpha_or_above(collector: metrics.Collector) -> None:
    collector.note_join(commander(1), 100, "PATTERN_OF_LIFE")
    collector.note_join(commander(2), 100, "ALPHA")
    collector.note_join(commander(3), 100, "BRAVO")
    collector.feed([spawned(110, 902, "STRIKE_FIGHTER", "COALITION", commander(2))])
    collector.feed([spawned(110, 901, "STRIKE_FIGHTER", "COALITION", commander(1))])
    for shooter, tick in ((901, 200), (902, 400)):
        collector.feed(
            [
                WeaponImpact.model_construct(
                    kind="WeaponImpact", tick=tick, shooter_id=shooter, hit=True
                )
            ]
        )
    n = collector.result(2000)["newbie"]
    assert (n["joined"], n["joined_below_tier"], n["joined_counted"]) == (3, 1, 2)
    assert n["ttfi_s"] == [30.0] and n["no_impact_observed_s"] == [190.0]  # 2 and 3 only
    assert n["below_tier_ttfi_s"] == [10.0]  # 1: reported, not judged
    a2 = report._a2([{"metrics": {"newbie": n}}], load().targets)
    assert (a2["newbies"], a2["below_tier"]["newbies"]) == (2, 1)


def test_each_impact_kind_is_detected(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    for n in (1, 2, 3, 4, 5):
        collector.note_join(commander(n), 100, "ALPHA")
    collector.feed(
        [spawned(110, 900 + n, "STRIKE_FIGHTER", "COALITION", commander(n)) for n in (1, 2)]
    )
    collector.feed(
        [WeaponImpact.model_construct(kind="WeaponImpact", tick=200, shooter_id=901, hit=True)]
    )
    collector.feed([killed(300, 950, 902)])
    collector.feed(
        [
            SupplyDelivered.model_construct(
                kind="SupplyDelivered", tick=400, commander_id=commander(3)
            )
        ]
    )
    # derived from world state: 4 stands in a coalition capture bar, 5 (a scout) sees a new track
    world = start_campaign("c", 1, shipped_config)
    rules = shipped_config.rules
    node = next(n for n, o in sorted(world.owner.items()) if o == "ENEMY")
    x, y = rules.roads.pos[node]
    ground = next(k for k, d in sorted(rules.domain.items()) if d == "GROUND")
    world.spawn(ground, "COALITION", "COMMANDER", Vec2(x, y), commander_id=commander(4))
    world.capture[node] = CaptureBar("COALITION", 1)
    recon = next(k for k in sorted(rules.painters))
    enemy = next(e for e in world.entities() if e.side == "ENEMY" and rules.stealth[e.kind] > 0)
    world.spawn(
        recon, "COALITION", "COMMANDER", Vec2(enemy.pos.x, enemy.pos.y), commander_id=commander(5)
    )
    world.contacts["COALITION"][enemy.id] = Contact(
        enemy.kind, Vec2(enemy.pos.x, enemy.pos.y), Vec2(0, 0)
    )
    collector.check_impact(world)
    kinds = {c: k for c, (_, k) in collector.impact.items()}
    assert kinds == {
        commander(1): "hit",
        commander(2): "kill",
        commander(3): "delivery",
        commander(4): "capture",
        commander(5): "scout",
    }
    assert collector.result(2000)["newbie"]["first_impact_kinds"] == {
        "capture": 1,
        "delivery": 1,
        "hit": 1,
        "kill": 1,
        "scout": 1,
    }
    collector.check_impact(world)  # the track is no longer new: nothing changes
    assert len(collector.impact) == 5


def test_persona_kinds_are_seeded_validated_and_a_striker_names_a_defended_foe(
    shipped_config: CampaignConfig, tmp_path: Path
) -> None:
    d = load()
    p = d.profiles["prime-50"]
    kinds = [personas.draw_kind(p, 1, i) for i in range(400)]
    assert kinds == [personas.draw_kind(p, 1, i) for i in range(400)]
    assert kinds != [personas.draw_kind(p, 2, i) for i in range(400)]
    assert {k: round(kinds.count(k) / 400, 1) for k in p.kinds} == {
        k: round(v, 1) for k, v in p.kinds.items()
    }
    for bad in ({"auto": 0.5, "striker": 0.4}, {"auto": 1.0, "boss": 0.0}):
        doc = tmp_path / "bad.yaml"
        raw = yaml.safe_load(DATA.read_text())
        raw["profiles"]["prime-50"]["kinds"] = bad
        doc.write_text(yaml.safe_dump(raw))
        with pytest.raises(ValueError, match="kinds"):
            load(doc)
    world = start_campaign("c", 1, shipped_config)
    foes = runner.defended_foes(world)
    assert foes and all(world.owner[n] == "ENEMY" and world.defense_hp[n] for n in foes)
    v = personas.new_viewer(3, d.personas["newbie"], "prime-50", 1, "striker")
    node = personas.pick_node(v, foes)
    join = personas.join_command(v, 5, 1, node, d.kind_roles)
    assert (join.role, join.hold, join.target.node_id) == ("STRIKE", False, node)
    assert node == personas.pick_node(
        personas.new_viewer(3, d.personas["newbie"], "prime-50", 1, "striker"), foes
    )
    for kind, role in (("hauler", "LOGI"), ("scout", "RECON")):
        other = personas.new_viewer(4, d.personas["newbie"], "prime-50", 1, kind)
        j = personas.join_command(other, 5, 1, personas.pick_node(other, foes), d.kind_roles)
        assert (j.role, j.target) == (role, None)


def test_a_run_has_strikers_with_valid_targets_and_reports_per_kind(
    first: Any, shipped_config: CampaignConfig
) -> None:
    tmp, a = first
    assert set(a["viewers"]["by_kind"]) <= set(KINDS) and a["viewers"]["by_kind"]["striker"] > 0
    targets = [e["target"] for e in log_entries(tmp / "a") if e["kind"] == "JOIN" and e["target"]]
    assert targets and all(t["node_id"] in shipped_config.rules.roads.pos for t in targets)
    assert set(a["metrics"]["newbie"]["by_kind"]) <= set(KINDS)


def test_capturer_picks_only_a_zero_defense_capturable_foe_node(
    shipped_config: CampaignConfig,
) -> None:
    world = start_campaign("c", 1, shipped_config)
    rules = world.rules
    assert rules is not None
    foes = sorted(n for n, o in world.owner.items() if o == "ENEMY")
    assert runner.capturable_foes(world) == []  # every foe base starts defended
    rear = rules.supply.rear["ENEMY"]
    assert rear in foes and rules.node_kind[rear] in rules.uncapturable
    for n in foes:
        world.defense_hp[n] = 0  # all stripped, the rear and any uncapturable kind included
    open_ = runner.capturable_foes(world)
    assert len(open_) > 2 and rear not in open_
    assert all(rules.node_kind[n] not in rules.uncapturable for n in open_)
    world.defense_hp[open_[0]] = 5  # a defended node is not capturable yet
    assert open_[0] not in runner.capturable_foes(world)
    world.owner[open_[1]] = "COALITION"  # a coalition node is no target
    assert open_[1] not in runner.capturable_foes(world)

    d = load()
    cands = runner.capturable_foes(world)
    picks = []
    for i in range(40):
        v = personas.new_viewer(i, d.personas["newbie"], "prime-50", 1, "capturer")
        node = personas.pick_node(v, cands)
        assert node in cands
        j = personas.join_command(v, 5, 1, node, d.kind_roles)
        assert (j.role, j.target.node_id, j.hold) == ("LOGI", node, False)
        again = personas.new_viewer(i, d.personas["newbie"], "prime-50", 1, "capturer")
        assert personas.pick_node(again, cands) == node  # seeded: same seed, same pick
        picks.append(node)
    assert len(set(picks)) > 1
    hauler = personas.new_viewer(1, d.personas["newbie"], "prime-50", 1, "hauler")
    assert personas.pick_node(hauler, cands) is None  # only striker and capturer name a node


def test_capturer_falls_back_to_a_bare_logi_join_and_counts_it(
    shipped_config: CampaignConfig,
) -> None:
    d = load()
    world = start_campaign("c", 1, shipped_config)
    crowd = runner._Crowd([(1, "newbie")], d, "prime-50", 1)
    (a,) = crowd.viewers
    a.kind = "capturer"
    ja = crowd._join(world, a, "join", 1)
    assert ja is not None and (ja.role, ja.target) == ("LOGI", None)
    assert (crowd.capturer_fallbacks, crowd.striker_fallbacks) == (1, 0)  # no foe is open yet
    for n in [n for n, o in world.owner.items() if o == "ENEMY"]:
        world.defense_hp[n] = 0
    a.status = personas.IDLE
    ja = crowd._join(world, a, "join", 2)
    assert ja is not None and ja.target is not None
    assert (crowd.capturer_fallbacks, crowd.striker_fallbacks) == (1, 0)
    assert runner.failed_run("p", 1, 1, "x")["viewers"]["capturer_fallbacks"] == 0


KEY = "tasking.strike_idle_targets_max"


def cli(monkeypatch: pytest.MonkeyPatch, out: Path, *extra: str) -> int:
    argv = ["balance.py", "--profile", "overnight-0", "--hours", "0.01", "--out", str(out), *extra]
    monkeypatch.setattr(sys, "argv", argv)
    return int(balance.main())


def test_set_changes_the_config_and_reaches_every_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shipped_config: CampaignConfig
) -> None:
    out = tmp_path / "o"
    assert cli(monkeypatch, out, "--seeds", "1,2", "--workers", "2", "--set", f"{KEY}=0") == 0
    doc = json.loads((out / "report.json").read_text())
    assert doc["config"]["overrides"] == [f"{KEY}=0"]
    assert doc["config"]["config_hash"] != shipped_config.config_hash
    hashes = {json.loads(f.read_text())["config_hash"] for f in (out / "runs").glob("*.json")}
    assert hashes == {doc["config"]["config_hash"]}
    assert f"balance overrides: `{KEY}=0`" in (out / "report.md").read_text()
    loaded = balance.load_campaign_config(balance.ConfigPaths(balance=out / "balance.yaml"))
    assert loaded.balance.tasking.strike_idle_targets_max == 0
    assert shipped_config.balance.tasking.strike_idle_targets_max != 0


@pytest.mark.parametrize(
    "pair",
    [
        "tasking.nope=1",  # unknown key
        "nope.strike_idle_targets_max=1",  # unknown section
        "tasking=1",  # not a leaf
        "sim.tick_hz=x",  # not a number
        f"{KEY}=1.5",  # float for an int key
        f"{KEY}=-1",  # schema minimum
        f"{KEY}=nan",
    ],
)
def test_set_rejections_exit_2_before_any_run(
    pair: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "o"
    assert cli(monkeypatch, out, "--set", pair) == 2
    assert capsys.readouterr().err.startswith("error:") and not out.exists()


def test_set_takes_true_and_false_on_a_bool_key(tmp_path: Path) -> None:
    # NX-412 part 5a: the shipped switches go off through --set, and the loader takes the result
    text = balance.override_balance(["economy.legacy_rules=false", "economy.unlimited.ENEMY=false"])
    tree = yaml.safe_load(text)
    assert tree["economy"]["legacy_rules"] is False
    assert tree["economy"]["unlimited"] == {"COALITION": True, "ENEMY": False}
    (path := tmp_path / "balance.yaml").write_text(text)
    assert balance.load_campaign_config(balance.ConfigPaths(balance=path)).rules.economy is not None
    on = yaml.safe_load(balance.override_balance(["economy.unlimited.COALITION=true"]))
    assert on["economy"]["unlimited"]["COALITION"] is True


@pytest.mark.parametrize(
    ("pair", "match"),
    [
        ("economy.legacy_rules=1", "not true or false"),  # a number on a bool key: never coerced
        ("economy.legacy_rules=0", "not true or false"),
        ("economy.legacy_rules=True", "not true or false"),
        ("economy.legacy_rules=yes", "not true or false"),
        (f"{KEY}=true", "not a valid int"),  # a bool on a numeric key
        ("economy.window_s=false", "not a valid"),
        ("economy.unlimited=false", "numeric or boolean"),  # a section, not a leaf
    ],
)
def test_set_checks_the_value_against_the_key_type(pair: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        balance.override_balance([pair])


def test_set_rejects_a_repeated_key() -> None:
    with pytest.raises(ValueError, match="twice"):
        balance.override_balance(
            ["tasking.strike_idle_targets_max=1", "tasking.strike_idle_targets_max=2"]
        )


# --- --theater and board density (NX-031) ----------------------------------------------------
def variant_theater(tmp: Path) -> Path:
    """A copy of strait-1 under another name plus one extra node (a sea-side outpost on a road)."""
    tree = yaml.safe_load(balance.ConfigPaths().theater.read_text())
    tree["name"] = "Strait Variant"
    tree["nodes"].append(
        {"id": "outpost", "name": "Outpost", "kind": "FOB", "pos": [130000, 120000],
         "start_owner": "COALITION", "start_stock": 100, "sector": "centre"}
    )  # fmt: skip
    tree["edges"].append({"a": "west-airbase", "b": "outpost", "layer": "ROAD", "speed_mult": 1.0})
    (path := tmp / "strait-1.yaml").write_text(yaml.safe_dump(tree, sort_keys=False))
    return path


def test_theater_runs_on_the_file_in_every_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shipped_config: CampaignConfig
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    theater = variant_theater(src)
    out = tmp_path / "o"
    assert cli(monkeypatch, out, "--seeds", "1,2", "--workers", "2", "--theater", str(theater)) == 0
    doc = json.loads((out / "report.json").read_text())
    shipped_nodes = len(shipped_config.theater.nodes)
    assert doc["config"]["theater"]["nodes"] == shipped_nodes + 1
    assert doc["config"]["theater"]["name"] == "Strait Variant"
    assert f"{shipped_nodes + 1} nodes" in (out / "report.md").read_text()
    # the hash covers the theater, and every worker ran on it
    assert doc["config"]["config_hash"] != shipped_config.config_hash
    hashes = {json.loads(f.read_text())["config_hash"] for f in (out / "runs").glob("*.json")}
    assert len(list((out / "runs").glob("*.json"))) == 2
    assert hashes == {doc["config"]["config_hash"]}
    assert (out / "theater" / "strait-1.yaml").read_text() == theater.read_text()
    # the density denominator is the variant's node count, not strait-1's
    run = runner.run(
        "overnight-0",
        1,
        0.01,
        tmp_path / "l",
        config=balance.load_campaign_config(
            balance.ConfigPaths(theater=out / "theater" / "strait-1.yaml")
        ),
    )
    assert run["config_hash"] == doc["config"]["config_hash"]
    world = start_campaign(
        "c", 1, balance.load_campaign_config(balance.ConfigPaths(theater=theater))
    )
    world.boards["COALITION"][1] = Job(1, "STRIKE", "a", 1, 1000, 0)
    col = metrics.Collector(world, frozenset(), tick_hz=HZ, sample_ticks=1, a3_ticks=1,
        idle_sample_ticks=1, impact_check_ticks=1, kinds={}, a2_min_tier="ALPHA")  # fmt: skip
    col.sample_density(world)
    assert col.jobs_per_node == [1 / (shipped_nodes + 1)]


def test_theater_named_balance_yaml_does_not_clobber_the_set_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = yaml.safe_load(balance.ConfigPaths().theater.read_text())
    tree["slug"] = "balance"
    src = tmp_path / "src"
    src.mkdir()
    (src / "balance.yaml").write_text(yaml.safe_dump(tree, sort_keys=False))
    out = tmp_path / "o"
    assert cli(monkeypatch, out, "--set", f"{KEY}=0", "--theater", str(src / "balance.yaml")) == 0
    run = json.loads(next((out / "runs").glob("*.json")).read_text())
    assert run["harness_error"] is None
    loaded = balance.load_campaign_config(balance.ConfigPaths(balance=out / "balance.yaml"))
    assert loaded.balance.tasking.strike_idle_targets_max == 0
    assert (out / "theater" / "balance.yaml").exists()


def test_a_bad_theater_exits_2_before_out_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("slug: bad\nnodes: 3\n")
    out = tmp_path / "o"
    assert cli(monkeypatch, out, "--theater", str(bad)) == 2
    err = capsys.readouterr().err
    assert err.startswith("error:") and err.count("\n") == 1 and not out.exists()
    assert cli(monkeypatch, out, "--theater", str(tmp_path / "missing.yaml")) == 2
    assert not out.exists()


def test_board_density_on_a_hand_built_sample(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    nodes = len(yaml.safe_load(balance.ConfigPaths().theater.read_text())["nodes"])
    assert nodes == 13  # strait-1 today; the expected values below are written for 13
    world = start_campaign("c", 1, shipped_config)
    node = Vec2(*shipped_config.rules.roads.pos["west-airbase"])
    for n in (1, 2):
        world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", node, commander_id=commander(n))
    world.spawn("STRIKE_FIGHTER", "COALITION", "AI_GARRISON", node)  # not a viewer unit
    board = world.boards["COALITION"]
    board[1] = Job(1, "STRIKE", "a", 3, 1000, 0)  # 3 unfilled
    board[2] = Job(2, "STRIKE", "b", 2, 1000, 0, claims={7: Claim(0)})  # 1 unfilled
    board[3] = Job(3, "STRIKE", "c", 1, 1000, 0, claims={8: Claim(0)})  # full: not open
    gone = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", node, commander_id=commander(3))
    gone.damage_state = "DISABLED"  # not live: out of the denominator
    world.boards["ENEMY"][4] = Job(4, "STRIKE", "d", 5, 1000, 0)  # the other side's: ignored
    collector.sample_density(world)
    # (3 + 1) unfilled slots / 2 viewer units; 2 open jobs / 13 nodes
    assert collector.slots_per_unit == [2.0]
    assert collector.jobs_per_node == [2 / 13]
    empty = start_campaign("c", 1, shipped_config)  # no viewer unit: slots sample skipped
    empty.boards["COALITION"][1] = Job(1, "STRIKE", "a", 3, 1000, 0)
    collector.sample_density(empty)
    assert collector.slots_per_unit == [2.0] and collector.jobs_per_node == [2 / 13, 1 / 13]
    d = collector.result(100)["density"]
    assert (d["slots_per_unit_samples"], d["jobs_per_node_samples"]) == (1, 2)
    agg = report._density([{"metrics": {"density": d}}, {"metrics": {"density": d}}])
    assert agg["slots_per_unit"] == 2.0 and agg["jobs_per_node"] == pytest.approx(1.5 / 13)
    assert report._density([{"metrics": {}}]) == {"slots_per_unit": None, "jobs_per_node": None}


# --- A2 target 480 s median + 15 min tail, hauler departure (Q-SIM-97) ---------------------------
def a2(ttfi: list[float], never: list[float]) -> dict[str, Any]:
    out: dict[str, Any] = report._a2([fake_run(newbie=newbie(ttfi, never))], load().targets)
    return out


def test_a2_median_boundary_is_480_s() -> None:
    assert load().targets.a2_max_s == 480
    assert [a2([m], [])["status"] for m in (479.0, 480.0, 481.0)] == ["pass", "pass", "fail"]


def test_a2_tail_share_boundary_is_10_percent() -> None:
    fast, slow = [60.0] * 9, [901.0]  # 1 of 10 later than 900 s: exactly 10%
    ok = a2(fast + slow, [])
    assert ok["status"] == report.PASS and ok["tail"]["share"] == 0.1
    assert "10.0% over 900 s (1/10), needs <= 10%" in ok["detail"]
    assert a2([60.0] * 8 + [901.0] * 2, [])["status"] == report.FAIL  # 20%
    just_over = a2([60.0] * 26 + [901.0] * 3, [])  # 3/29 = 10.3%: fails and must not read as 10%
    assert just_over["status"] == report.FAIL and "10.3% over 900 s (3/29)" in just_over["detail"]
    assert a2([60.0] * 8 + [901.0, 900.0], [])["status"] == report.PASS  # 900 s is not over 900 s
    # watched past 900 s with no impact is in the tail (and a miss for the median, once 480 s)
    assert a2([60.0] * 8, [901.0, 901.0])["status"] == report.FAIL


def test_a2_tail_leaves_unresolved_newbies_out() -> None:
    # 1 of 10 over the tail; 5 more are still inside their first 900 s with no impact: left out
    r = a2([60.0] * 9 + [901.0], [500.0, 600.0, 700.0, 800.0, 900.0])
    assert r["tail"] == {"limit_s": 900.0, "over": 1, "judged": 10, "share": 0.1}
    assert r["unresolved_run_ended"] == 0 and r["no_impact_within_window"] == 5
    # the median still counts the 500..900 s ones as misses: 15 newbies, 5 inf; median is 60 s
    assert r["status"] == report.PASS
    only = a2([], [100.0])  # nothing resolved at all
    assert only["status"] == report.NO_DATA and only["tail"]["share"] is None


def test_a2_detail_names_the_tail() -> None:
    r = a2([60.0, 1000.0], [])
    assert r["tail"]["over"] == 1 and r["status"] == report.FAIL  # median 530 s too
    assert "50.0% over 900 s (1/2), needs <= 10%" in r["detail"]
    assert a2([60.0, 100.0, 1000.0], [])["status"] == report.FAIL  # median 100 s: the tail alone


def test_profiles_reject_a_bad_tail(tmp_path: Path) -> None:
    bads = (
        ("a2_tail_s", 0),
        ("a2_tail_s", float("inf")),
        ("a2_tail_share", 0),
        ("a2_tail_share", 1.5),
    )
    for key, bad in bads:
        raw = yaml.safe_load(DATA.read_text())
        raw["targets"][key] = bad
        doc = tmp_path / "bad.yaml"
        doc.write_text(yaml.safe_dump(raw))
        with pytest.raises(ValueError, match="a2_tail"):
            load(doc)


def join_hauler(
    config: CampaignConfig, node: str | None
) -> tuple[Any, metrics.Collector, list[Any]]:
    """A newbie hauler's JOIN LOGI at tick 5 (to `node`, or bare), stepped for 60 ticks."""
    world = start_campaign("c", 1, config)
    cmdr = commander(1)
    collector = metrics.Collector(
        world, frozenset([cmdr]), tick_hz=HZ, sample_ticks=600, a3_ticks=1000,
        idle_sample_ticks=600, impact_check_ticks=10, kinds={cmdr: "hauler"}, a2_min_tier="ALPHA",
    )  # fmt: skip
    collector.note_join(cmdr, 5, "ALPHA")
    v = personas.new_viewer(1, load().personas["newbie"], "prime-50", 1, "hauler")
    spawns: list[Any] = []
    for tick in range(1, 61):
        cmds = [personas.join_command(v, tick, 1, node, load().kind_roles)] if tick == 5 else []
        events = step(world, cmds, HANDLERS)
        spawns += [e for e in events if e.kind == "UnitSpawned" and e.commander_id == cmdr]
        collector.feed(events)
        collector.observe(world)
    return world, collector, spawns


def test_a_hauler_leaving_its_source_loaded_is_a_departure(shipped_config: CampaignConfig) -> None:
    rules = shipped_config.rules
    world = start_campaign("c", 1, shipped_config)
    dest = next(  # a coalition base that takes stock, not the rear: the truck loads at another one
        n for n, o in sorted(world.owner.items())
        if o == "COALITION" and rules.supply.max_stock.get(n, 0) > 0 and n != rules.sanctuary
    )  # fmt: skip
    world, collector, spawns = join_hauler(shipped_config, dest)
    assert len(spawns) == 1
    truck = world.find(spawns[0].entity_id)
    assert truck is not None and truck.cargo and truck.cargo > 0 and truck.path
    assert collector.impact[commander(1)] == (spawns[0].tick, "departure")
    assert collector.result(60)["newbie"]["first_impact_kinds"] == {"departure": 1}


def test_a_truck_leaving_empty_is_no_departure(shipped_config: CampaignConfig) -> None:
    world = start_campaign("c", 1, shipped_config)
    foe = next(n for n, o in sorted(world.owner.items()) if o == "ENEMY")  # a capture run: no load
    world, collector, spawns = join_hauler(shipped_config, foe)
    truck = world.find(spawns[0].entity_id)
    assert truck is not None and truck.path and not truck.cargo
    assert collector.impact == {}


# --- harness keys in config: momentum_sample_s, kind_roles, --hours default ------------------


@pytest.mark.parametrize(
    ("key", "value", "match"),
    [
        ("momentum_sample_s", 0, "momentum_sample_s"),
        ("momentum_sample_s", -5, "momentum_sample_s"),
        ("kind_roles", {"striker": "STRIKE", "hauler": "LOGI", "scout": "NAVY"}, "kind_roles"),
        ("kind_roles", {"auto": "STRIKE", "striker": "STRIKE"}, "kind_roles"),
        ("kind_roles", {"striker": "STRIKE", "hauler": "LOGI"}, "scout"),  # scout is used
    ],
)
def test_new_profile_keys_are_validated(key: str, value: Any, match: str, tmp_path: Path) -> None:
    raw = yaml.safe_load(DATA.read_text())
    raw[key] = value
    doc = tmp_path / "bad.yaml"
    doc.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match=match):
        load(doc)


def test_sampling_interval_and_kind_roles_come_from_the_config(
    tmp_path: Path, data: Data, shipped_config: CampaignConfig
) -> None:
    assert load().momentum_sample_s == 60
    fast = dataclasses.replace(data, momentum_sample_s=30)
    run = run_once(tmp_path, "fast", fast, shipped_config)
    assert run["metrics"]["momentum"]["sample_every_s"] == 30
    std = run_once(tmp_path, "std", data, shipped_config)
    assert std["metrics"]["momentum"]["sample_every_s"] == 60
    n_fast, n_std = (len(r["metrics"]["momentum"]["samples"]) for r in (run, std))
    assert n_fast > n_std + 3
    swapped = {"striker": "STRIKE", "hauler": "RECON", "scout": "LOGI"}
    v = personas.new_viewer(4, load().personas["newbie"], "prime-50", 1, "hauler")
    assert personas.join_command(v, 5, 1, None, swapped).role == "RECON"


def test_hours_default_follows_the_balance_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[float] = []

    def spy(profile: str, seed: int, hours: float, *args: Any, **kw: Any) -> Any:
        seen.append(hours)
        return runner.failed_run(profile, seed, hours, "spy")

    monkeypatch.setattr(runner, "run", spy)

    def go(out: str, *extra: str) -> None:
        argv = ["balance.py", "--profile", "overnight-0", "--out", str(tmp_path / out), *extra]
        monkeypatch.setattr(sys, "argv", argv)
        assert balance.main() == 0

    go("a")
    go("b", "--set", "campaign.time_limit_h=36")
    go("c", "--hours", "1", "--set", "campaign.time_limit_h=36")
    assert seen == [72.0, 36.0, 1.0]


# --- direct orders (NX-398, Q-SIM-110) ---------------------------------------------------------
def test_freelancers_send_any_node_and_no_direct_order_breaks_or_sticks(
    tmp_path: Path, shipped_config: CampaignConfig
) -> None:
    """freelance-50 with a fast, small crowd: random direct orders to every node (the rear,
    bridges, the sanctuary) crash nothing, leave no GOTO stuck and no claim past its lease."""
    full = load()
    crowd = dataclasses.replace(full.profiles["freelance-50"], viewers=40, ramp_min=1)
    d = dataclasses.replace(full, profiles={**full.profiles, "freelance-50": crowd})
    r = runner.run("freelance-50", 1, 2 * TICKS / HZ / 3600, tmp_path / "f", d, shipped_config)
    assert (r["crash"], r["harness_error"]) == (None, None)
    assert r["viewers"]["by_kind"]["freelancer"] > 0
    targets = {
        e["target"]["node_id"]
        for e in log_entries(tmp_path / "f")
        if e["kind"] == "JOIN" and e["target"]
    }
    assert {"static-rear", "haven"} & targets  # the rear or the sanctuary was ordered
    o = r["orders"]
    assert (o["stuck_goto"], o["stale_claims"]) == (0, 0)
    assert o["direct_orders_ended"] > 0 and 0 <= o["no_effect"] <= o["direct_orders_ended"]


def test_only_freelance_50_has_freelancers() -> None:
    for name, p in load().profiles.items():
        assert ("freelancer" in p.kinds) == (name == "freelance-50")


def test_the_order_checks_flag_a_stuck_goto_a_held_too_long_and_a_stale_claim(
    shipped_config: CampaignConfig,
) -> None:
    from nexus.core.tasking import post_job
    from nexus.core.tasking_gen import JobSpec

    world = start_campaign("c", 1, shipped_config)
    tr = shipped_config.rules.tasking
    assert tr is not None
    o = orders.Orders(world, frozenset())
    x, y = shipped_config.rules.roads.pos["fob-n-w"]
    stuck = world.spawn("LOGI_TRUCK", "COALITION", "COMMANDER", Vec2(x, y), commander_id="a")
    held = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(x, y), commander_id="b")
    stuck.order = held.order = "GOTO"
    every = tr.reeval_every_ticks
    held.order_node, held.held_since = "fob-n-w", every  # began holding at a pass
    job = post_job(world, "COALITION", JobSpec("DEFEND", "op:x", 1, 1000, node="fob-n-w"), [])
    job.claims[held.id] = Claim(every)
    world.campaign.running_ticks = every  # a pass: the truck idle once, nothing else yet
    o.observe(world)
    assert (o.result()["stuck_goto"], o.result()["stale_claims"]) == (0, 0)
    world.campaign.running_ticks = every + tr.order_dwell_ticks - every  # the last pass before
    o.observe(world)  # the truck idle at two passes; the jet's hold is one pass short of the dwell
    assert (o.result()["stuck_goto"], o.result()["stale_claims"]) == (1, 1)
    world.campaign.running_ticks = every + tr.order_dwell_ticks  # exactly the dwell: should be over
    o.observe(world)
    assert o.result()["stuck_goto"] == 2


def test_a_freelancer_order_without_a_shot_delivery_or_capture_counts_as_no_effect(
    shipped_config: CampaignConfig,
) -> None:
    world = start_campaign("c", 1, shipped_config)
    o = orders.Orders(world, frozenset({"a", "b", "c", "d"}))
    units = {}
    for c in "abcd":
        units[c] = world.spawn(
            "STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0), commander_id=c
        )
        units[c].order = "GOTO"
        o.feed([SimpleNamespace(kind="UnitSpawned", commander_id=c, entity_id=units[c].id)])
    o.feed(
        [
            SimpleNamespace(kind="WeaponFired", shooter_id=units["a"].id),
            SimpleNamespace(kind="SupplyDelivered", commander_id="b"),
            SimpleNamespace(kind="NodeCaptured", participant_commander_ids=["c"]),
        ]
    )
    o.observe(world)
    assert o.result()["direct_orders_ended"] == 0  # every order still on
    for e in units.values():
        e.order = None
    o.observe(world)
    assert o.result() | {"stuck_goto": 0, "stale_claims": 0} == {
        "direct_orders_ended": 4,
        "no_effect": 1,
        "no_effect_share": 0.25,
        "stuck_goto": 0,
        "stale_claims": 0,
    }


def test_profile_all_is_the_standard_profiles_and_a_check_profile_is_named_only() -> None:
    d = load()
    assert balance.resolve("all", d) == [n for n in d.profiles if n != "freelance-50"]
    assert balance.resolve("all", d) == [
        "overnight-0", "quiet-5", "prime-50", "evening-150", "raid-300", "surge-500"
    ]  # fmt: skip
    assert balance.resolve("freelance-50", d) == ["freelance-50"]
    assert balance.resolve("prime-50,freelance-50", d) == ["prime-50", "freelance-50"]
    with pytest.raises(ValueError, match="unknown profiles"):
        balance.resolve("prime-50,nope", d)


def test_the_report_fails_a_profile_with_a_stuck_order_or_a_stale_claim() -> None:
    clean = {"stuck_goto": 0, "stale_claims": 0, "direct_orders_ended": 8, "no_effect": 2}
    ok = report._orders([{"orders": clean}, {"orders": clean}])
    got = (ok["status"], ok["direct_orders_ended"], ok["no_effect_share"])
    assert got == (report.PASS, 16, 0.25)
    skip = {k: {"status": "n/a"} for k in ("A1", "A2", "A3", "A4")}
    for bad in ({"stuck_goto": 1}, {"stale_claims": 3}):
        agg = report._orders([{"orders": clean}, {"orders": clean | bad}])
        assert agg["status"] == report.FAIL
        rows = report.target_table({"freelance-50": skip | {"orders": agg}})
        (row,) = [r for r in rows if r["target"] == "orders"]
        assert row["status"] == report.FAIL and "stuck GOTO orders" in row["detail"]
    assert report._orders([{"orders": None}])["status"] == report.NO_DATA  # a failed run


# --- steamroll signals S1 to S4 (NX-411, Q-TEST-11) ---------------------------------------------
LATE = (
    240  # one-minute samples of a 4 h campaign (sample_ticks 600 at 10 Hz); the last third is 160+
)


def sr_metrics(**over: Any) -> dict[str, Any]:
    """A won, hard-fought 4 h campaign: no signal fires. `over` replaces keys of the steamroll
    block (`static` keys merge), `result` / `momentum` replace those parts."""
    raw: dict[str, Any] = {
        "pressure_ticks": [1000, 20000, 60000, 90000, 130000],  # 5 in 4 h; the hold began at 100000
        "hold_start": 100000,
        "holds_broken": 1,
        "sample_ticks": 600,
        "static": {"units": [40] * 120 + [30] * 120, "stock": [900] * LATE, "start_stock": 1000},
    }
    raw["static"] |= over.pop("static", {})
    result = over.pop("result", "VICTORY")
    swing = over.pop("momentum", [30, 55, 70, 50, 65] + [60] * (LATE - 5))
    raw |= over
    return {
        "outcome": {"result": result, "length_h": 4.0, "end_tick": 144000},
        "momentum": {"sample_every_s": 60.0, "samples": swing},
        "steamroll": raw,
    }


def judge(**over: Any) -> dict[str, Any]:
    got: dict[str, Any] = steamroll.judge(sr_metrics(**over), load().targets)
    return got


def test_a_hard_fought_win_fires_nothing() -> None:
    got = judge()
    assert got["judged"] and got["fired"] == 0 and got["steamroll"] is False
    assert got["signals"]["S1"]["value"] == 5.0  # 5 events * 4 / 4 h
    assert got["signals"]["S2"]["value"] == {"pressure": 1, "broken": 1}  # the 130000 event
    assert got["signals"]["S3"]["value"] == {"max_drop": 20, "lead_changes": 1}


def test_s1_fires_under_two_pressure_events_per_4_hours() -> None:
    assert judge(pressure_ticks=[5])["signals"]["S1"]["fired"]  # 1 per 4 h
    assert not judge(pressure_ticks=[5, 6])["signals"]["S1"]["fired"]  # exactly 2: not under
    # normalised by the campaign length: 2 events in a 2 h win are 4 per 4 h
    m = sr_metrics(pressure_ticks=[5, 6])
    m["outcome"] |= {"length_h": 2.0, "end_tick": 72000}
    assert not steamroll.judge(m, load().targets)["signals"]["S1"]["fired"]


def test_s2_fires_when_the_last_hold_was_uncontested_and_never_broken() -> None:
    assert judge(pressure_ticks=[1000], holds_broken=0)["signals"]["S2"]["fired"]
    assert not judge(pressure_ticks=[1000], holds_broken=1)["signals"]["S2"]["fired"]
    assert not judge(pressure_ticks=[100000], holds_broken=0)["signals"]["S2"]["fired"]


def test_s2_is_not_measurable_without_a_running_hold() -> None:
    s2 = judge(hold_start=None)["signals"]["S2"]  # won by HQ capture below the hold fraction
    assert s2["value"] is None and not s2["fired"] and "not measurable" in s2["note"]


def test_s3_fires_on_a_small_swing_with_at_most_one_lead_change() -> None:
    flat = [30, 55, 60, 52, 58] + [60] * (LATE - 5)
    assert judge(momentum=flat)["signals"]["S3"]["fired"]  # drop 8, one change
    big = [30, 55, 70, 58] + [60] * (LATE - 4)
    assert not judge(momentum=big)["signals"]["S3"]["fired"]  # drop 12
    wobble = [30, 55, 45, 55] + [60] * (LATE - 4)
    got = judge(momentum=wobble)["signals"]["S3"]
    assert got["value"]["lead_changes"] == 3 and not got["fired"]
    never = judge(momentum=[30] * LATE)["signals"]["S3"]
    assert never["value"] is None and not never["fired"]


def test_s3_boundaries_fire_strictly_under_the_drop_and_at_most_the_changes() -> None:
    tail = [60] * (LATE - 4)
    at_ten = judge(momentum=[30, 55, 65, 55, *tail])["signals"]["S3"]  # drop 65 -> 55
    assert at_ten["value"]["max_drop"] == 10 and not at_ten["fired"]  # 10 is not under 10
    nine = judge(momentum=[30, 55, 65, 56, *tail])["signals"]["S3"]
    assert nine["value"]["max_drop"] == 9 and nine["fired"]
    one = judge(momentum=[30, 55, 58, 56, *tail])["signals"]["S3"]
    assert one["value"]["lead_changes"] == 1 and one["fired"]  # at most 1: 1 fires
    two = judge(momentum=[55, 49, 55, 56, *tail])["signals"]["S3"]  # C, then E, then C again
    assert two["value"] == {"max_drop": 6, "lead_changes": 2} and not two["fired"]
    # exactly 50 keeps the previous leader: no flip, and no lead while the Static leads
    held = judge(momentum=[30, 55, 50, 56, *tail])["signals"]["S3"]
    assert held["value"] == {"max_drop": 5, "lead_changes": 1} and held["fired"]
    still = judge(momentum=[30, 50, 55, 56, *tail])["signals"]["S3"]
    assert still["value"]["lead_changes"] == 1 and still["value"]["max_drop"] == 0


def test_s4_boundaries_fire_strictly_under_the_fractions() -> None:
    def s4(**static: Any) -> dict[str, Any]:
        got: dict[str, Any] = judge(static=static)["signals"]["S4"]
        return got

    # peak 40, late mean 10 = exactly 25%: not under; 9 fires
    assert not s4(units=[40] * 160 + [10] * 80)["fired"]
    assert s4(units=[40] * 160 + [9] * 80)["fired"]
    # start stock 1000, late mean 100 = exactly 10%: not under; 99 fires
    assert not s4(stock=[900] * 160 + [100] * 80)["fired"]
    assert s4(stock=[900] * 160 + [99] * 80)["fired"]


def test_s4_fires_on_a_collapsed_late_static_force() -> None:
    gone = {"units": [40] * 160 + [5] * 80}
    assert judge(static=gone)["signals"]["S4"]["fired"]  # 5/40 = 12.5% < 25%
    broke = {"stock": [900] * 160 + [50] * 80}
    s4 = judge(static=broke)["signals"]["S4"]
    assert s4["fired"] and s4["value"]["stock_of_start"] == 0.05
    assert not judge(static={"units": [40] * 160 + [11] * 80})["signals"]["S4"]["fired"]
    assert judge(static={"units": [0] * LATE})["signals"]["S4"]["value"] is None


def test_the_rule_is_s1_and_s2_or_three_of_four() -> None:
    both = judge(pressure_ticks=[1000], holds_broken=0)  # S1 + S2 only
    assert both["fired"] == 2 and both["steamroll"] is True
    s1_only = judge(pressure_ticks=[1000], holds_broken=1)
    assert s1_only["fired"] == 1 and s1_only["steamroll"] is False
    flat = [30, 55, 60, 52, 58] + [60] * (LATE - 5)
    three = judge(pressure_ticks=[1000, 20000], holds_broken=0, momentum=flat,
        static={"units": [40] * 160 + [5] * 80})  # fmt: skip
    assert [k for k, v in three["signals"].items() if v["fired"]] == ["S2", "S3", "S4"]
    assert three["steamroll"] is True
    two = judge(momentum=flat, static={"units": [40] * 160 + [5] * 80})  # S3 + S4
    assert two["fired"] == 2 and two["steamroll"] is False


def test_only_won_campaigns_are_judged() -> None:
    for result in ("DEFEAT", "TIME_LIMIT", None):
        got = judge(result=result)
        assert not got["judged"] and got["steamroll"] is None
    lost = fake_run(outcome={"ended": True, "result": "TIME_LIMIT", "length_h": 72.0})
    lost["metrics"]["steamroll"] = sr_metrics()["steamroll"]
    won = fake_run()
    won["metrics"] |= sr_metrics(pressure_ticks=[], holds_broken=0)
    won["metrics"]["outcome"] = {
        "ended": True,
        "result": "VICTORY",
        "length_h": 4.0,
        "end_tick": 144000,
    }
    a1 = report._a1([lost, won], load().targets)
    assert (a1["steamroll"]["judged"], a1["steamroll"]["flagged"], a1["steamroll"]["share"]) == (
        1,
        1,
        1.0,
    )
    assert a1["seeds_in_window"] == 1 and "1/1 won seeds flagged" in a1["detail"]  # fmt: skip


def test_collector_derives_pressure_and_the_hold_from_events(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    # The hold now comes from the sim's VictoryHoldStarted / Broken (NX-412 part 5a): each tick's
    # captures go through a real world and `nexus.core.campaign.campaign`, and the hold events it
    # emits are fed with them, so the S2 inputs must match the old capture-derived expectations.
    world = start_campaign("c", 1, shipped_config)

    def cap(tick: int, node: str, frm: str, to: str) -> Any:
        return NodeCaptured.model_construct(
            kind="NodeCaptured", tick=tick, node_id=node, from_=frm, to=to,
            participant_commander_ids=[],
        )  # fmt: skip

    def feed_tick(*caps: Any) -> None:
        out: list[Any] = []
        for c in caps:
            world.owner[c.node_id] = c.to
        world.campaign.tick = caps[0].tick - 1
        campaign(world, out)
        collector.feed([*caps, *(e for e in out if e.kind.startswith("VictoryHold"))])

    def start(tick: int, node: str, side: str) -> Any:
        return CaptureStarted.model_construct(
            kind="CaptureStarted", tick=tick, node_id=node, side=side
        )

    def down(tick: int, node: str, owner: str) -> Any:
        return NodeDefensesDown.model_construct(
            kind="NodeDefensesDown", tick=tick, node_id=node, owner=owner
        )

    assert (
        collector.hold_start is None
    )  # the setup holds 3 of 8 strategic nodes; the hold needs 4/5
    collector.feed([
        start(10, "cross-n", "ENEMY"),  # neutral ground: not pressure
        start(11, "fob-n-e", "COALITION"),  # the coalition's own capture: not pressure
        start(12, "fob-n-w", "ENEMY"),  # on a coalition node: pressure
        down(13, "fob-n-w", "COALITION"),  # pressure
        down(14, "east-airbase", "ENEMY"),  # the Static's own: not pressure
    ])  # fmt: skip
    assert collector.pressure_ticks == [12, 13]
    for tick, node, frm in (
        (100, "cross-n", "NEUTRAL"), (110, "cross-s", "NEUTRAL"), (120, "fob-n-e", "ENEMY"),
        (130, "fob-s-e", "ENEMY"),
    ):  # fmt: skip
        feed_tick(cap(tick, node, frm, "COALITION"))
    assert collector.hold_start == 130 and collector.holds_broken == 0  # 7 of 8 >= 4/5
    collector.feed([start(150, "fob-n-e", "ENEMY")])
    feed_tick(cap(160, "fob-n-e", "COALITION", "ENEMY"))
    assert collector.pressure_ticks == [12, 13, 150, 160]  # a capture start, then the node lost
    assert collector.hold_start is None and collector.holds_broken == 1  # 6 of 8 < 4/5: broken
    feed_tick(cap(170, "fob-n-e", "ENEMY", "COALITION"))
    assert collector.hold_start == 170
    raw = collector.result(1000)["steamroll"]
    assert (raw["hold_start"], raw["holds_broken"], raw["pressure_ticks"]) == (
        170,
        1,
        [12, 13, 150, 160],
    )
    # a loss and a regain in one tick: the hold is judged on the tick's final ownership
    feed_tick(cap(180, "fob-n-e", "COALITION", "ENEMY"), cap(180, "fob-n-e", "ENEMY", "COALITION"))
    assert collector.hold_start == 170 and collector.holds_broken == 1
    holds = collector.result(1000)["economy"]["holds"]
    assert holds == [
        {"start": 130, "end": 160, "broken": True, "ops": 0, "pressure": 2},  # 150, 160
        {"start": 170, "end": None, "broken": False, "ops": 0, "pressure": 1},  # the loss at 180
    ]


# --- economy metrics (NX-412 part 5a, ECONOMY §4 "Harness report") ------------------------------
HOUR = 3600 * HZ


def test_collector_counts_the_economy_per_side_per_hour(collector: metrics.Collector) -> None:
    def produced(tick: int, side: str, amount: int) -> Any:
        return SupplyProduced.model_construct(kind="SupplyProduced", tick=tick, side=side,
                                              amount=amount)  # fmt: skip

    def consumed(tick: int, node: str, amount: int, cause: str) -> Any:
        return SupplyConsumed.model_construct(kind="SupplyConsumed", tick=tick, node_id=node,
                                              amount=amount, cause=cause)  # fmt: skip

    def refused(tick: int, reason: str, ops: int, units: int) -> Any:
        return SpawnRefused.model_construct(kind="SpawnRefused", tick=tick, side="ENEMY",
                                            reason=reason, operations=ops, units=units)  # fmt: skip

    collector.feed([
        produced(5, "COALITION", 20), produced(10, "ENEMY", 40), produced(HOUR + 1, "ENEMY", 30),
        consumed(20, "fob-n-w", 3, "UPKEEP"),  # a coalition base pays upkeep
        consumed(21, "static-rear", 2, "UPKEEP"),  # the Static's source (no owner entry needed)
        consumed(30, "static-rear", 60, "SPAWN"),  # the Static's source account
        consumed(30, "east-airbase", 15, "SPAWN"),  # a Static base account
        consumed(31, "haven", 20, "SPAWN"),  # a coalition spawn: not the Director's spend
        consumed(32, "east-airbase", 9, "REARM"),  # neither upkeep nor a spawn
        spawned(35, 901, "STRIKE_FIGHTER", "COALITION", commander(1)),
        UnitGrounded.model_construct(kind="UnitGrounded", tick=40, entity_id=901, node_id="haven"),
        refused(50, "GUARD", 2, 7), refused(HOUR + 5, "TIER_CAP", 1, 0),
    ])  # fmt: skip
    eco = collector.result(2 * HOUR)["economy"]
    assert eco["sides"] == {
        "COALITION": {"income": [20], "upkeep": [3], "groundings": [1]},
        "ENEMY": {"income": [40, 30], "upkeep": [2], "groundings": []},
    }
    assert eco["budget"]["spent"] == {"base": [15], "source": [60]}
    assert eco["refused"] == {
        "operations_per_hour": {"GUARD": [2], "TIER_CAP": [0, 1]},
        "units": {"GUARD": 7, "TIER_CAP": 0},
    }


def test_collector_counts_the_statics_adaptations_by_category(collector: metrics.Collector) -> None:
    def adapted(tick: int, side: str, category: str) -> Any:
        return ThreatAdaptation.model_construct(kind="ThreatAdaptation", tick=tick, side=side,
                                                category=category)  # fmt: skip

    collector.feed([
        adapted(5, "ENEMY", "STAGING"), adapted(HOUR + 1, "ENEMY", "STAGING"),
        adapted(HOUR + 2, "ENEMY", "HOLD_AT_RISK"), adapted(9, "COALITION", "STAGING"),
    ])  # fmt: skip
    assert collector.result(2 * HOUR)["economy"]["adapted"] == {
        "HOLD_AT_RISK": [0, 1], "STAGING": [1, 1],
    }  # fmt: skip


def test_collector_counts_static_operations_holds_and_budgets(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    world = start_campaign("c", 1, shipped_config)

    def tick_with(tick: int, *jobs: tuple[str, str, str]) -> None:
        out: list[Any] = []
        world.campaign.tick = tick - 1
        for kind, key, node in jobs:
            post_job(world, "ENEMY", JobSpec(kind, key, 1, 500, node=node), out)  # type: ignore[arg-type]
        world.campaign.tick = tick
        collector.feed(out)
        collector.observe(world)

    # an OFFENSIVE posts its STAGE (job 0) and CAPTURE (job 1) on one tick: one launch
    tick_with(100, ("STAGE", "op:OFFENSIVE:fob-n-w:0", "fob-n-w"),
              ("CAPTURE", "op:OFFENSIVE:fob-n-w:1", "fob-n-w"))  # fmt: skip
    tick_with(200, ("PATROL", "op:POL_PATROL:east-airbase:0", "east-airbase"))  # routine
    hold = VictoryHoldStarted.model_construct(
        kind="VictoryHoldStarted", tick=300, node_ids=[], ends_at_tick=18300
    )
    collector.feed([hold])
    tick_with(400, ("CAPTURE", "op:OFFENSIVE:cross-n:0", "cross-n"))  # neutral, in the hold
    tick_with(500, ("STRIKE", "op:PROBE:fob-s-w:1", "fob-s-w"))  # not a first job: no launch
    state = world.director["ENEMY"]
    state.windows, state.budget = state.windows + 1, 70  # a decision window ran
    collector.observe(world)
    collector.observe(world)  # the same window: counted once
    eco = collector.result(2 * HOUR)["economy"]
    assert eco["ops"] == [
        [100, "OFFENSIVE", "fob-n-w", True],
        [200, "POL_PATROL", "east-airbase", False],
        [400, "OFFENSIVE", "cross-n", False],
    ]
    assert eco["holds"] == [{"start": 300, "end": None, "broken": False, "ops": 1, "pressure": 0}]
    assert eco["budget"]["sum"] == [70] and eco["budget"]["windows"] == [1]
    run = {"metrics": {"economy": eco}, "ticks_run": 2 * HOUR, "tick_hz": HZ, "seed": 1,
           "viewers": {"peak_concurrent": 5}}  # fmt: skip
    agg = report._economy([run])
    assert agg["ops_per_hour"] == 1.0  # 2 catalog launches over 2 game hours; patrols left out
    assert agg["ops_by_id"] == {"OFFENSIVE": 2, "POL_PATROL": 1}
    assert (agg["offensives"], agg["offensives_on_coalition"]) == (2, 1)
    assert agg["offensive_gap_min"] == {"median": 0.5, "max": 0.5}  # 300 ticks at 10 Hz
    assert agg["budget_per_window"] == 70 and agg["ops_per_hold"] == [1]
    assert agg["army_vs_viewers"] == [[0, 5]]


def test_collector_samples_pools_grounded_units_and_grounding_by_state(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    world = start_campaign("c", 1, shipped_config)
    busy = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    idle = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    busy.job_id = 77  # holds a job at the first sample
    collector.sample_idle(world)
    busy.grounded, busy.job_id = True, None  # upkeep grounded it before the next sample
    collector.sample_idle(world)
    eco = collector.result(HOUR)["economy"]
    seen_idle = metrics.idle_reason(world, idle)
    assert eco["grounded_from"] == {"job": 1}
    assert eco["exposure"] == {"job": 1, seen_idle: 1}  # the idle one stayed ungrounded
    world.campaign.tick = HOUR - 1
    collector.sample(world)  # not yet a full hour
    world.campaign.tick = HOUR
    collector.sample(world)
    collector.sample(world)  # the same hour: one snapshot
    assert collector.result(HOUR)["economy"]["hourly"] == [
        {"COALITION": {"pool": None, "grounded": 1}, "ENEMY": {"pool": None, "grounded": 0}}
    ]  # shipped: both sides unlimited, so no pool
    assert collector.result(HOUR)["economy"]["army_peak"] >= 2


def test_the_report_header_labels_the_economy_mode() -> None:
    # EC-15: a legacy or unlimited run is labelled, never passed off as a normal balance result
    on, off = {"COALITION": True, "ENEMY": True}, {"COALITION": False, "ENEMY": False}
    shipped = report._economy_mode({"legacy_rules": True, "unlimited": on})
    assert shipped == [
        "- **economy: legacy_rules ON; unlimited COALITION, ENEMY** (ECONOMY EC-15: not a normal "
        "balance result)"
    ]
    sweep = report._economy_mode({"legacy_rules": False, "unlimited": off})
    assert sweep == ["- **economy: legacy_rules off; unlimited none**"]
    one = report._economy_mode({"legacy_rules": False, "unlimited": {**off, "COALITION": True}})
    assert "unlimited COALITION**" in one[0] and "EC-15" in one[0]
    assert report._economy_mode(None) == []  # an old report.json without the field


def test_travel_table_on_strait_1(shipped_config: CampaignConfig) -> None:
    rows = {r["node"]: r for r in metrics.travel_table(shipped_config.rules, HZ)}
    assert set(rows) == set(shipped_config.rules.campaign.strategic)  # type: ignore[union-attr]
    east = rows["east-airbase"]
    # by hand: static-rear (395 km, 120 km) -> static-hq (380, 120) -> east-airbase (310, 120),
    # 85 km at speed_mult 1; ENEMY_ARMOR 20 m/s world = 4,250 world s, 7,084 ticks of 0.6 s
    # (time_scale 6 at 10 Hz) = 708.4 game s
    assert east["kind"] == "ENEMY_ARMOR" and east["road_km"] == 85.0
    assert east["minutes"] == pytest.approx(708.4 / 60) and east["hold_min"] == 30.0
    assert east["within_hold"] is True
    assert rows["west-airbase"]["within_hold"] is False  # the far bank is out of reach


def test_collector_samples_the_static_force_and_stock(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    world = start_campaign("c", 1, shipped_config)
    collector.sample(world)
    assert collector.static_start_stock > 0 and collector.static_stock == [
        collector.static_start_stock
    ]
    assert world.rules is not None
    armed = world.rules.armed
    assert collector.static_units[0] == sum(
        e.side == "ENEMY" and e.kind in armed for e in world.entities()
    )


def _ev(model: Any, kind: str, tick: int, **fields: Any) -> Any:
    return model.model_construct(kind=kind, tick=tick, **fields)


def _launch_tick(world: Any, collector: metrics.Collector, tick: int, *keys: tuple[str, str],
                 debit: int = 0) -> None:  # fmt: skip
    """Post `(kind, key)` Static jobs on `tick` (the node is in the key), feed their JobCreated and
    an optional Static SPAWN debit, then observe."""
    out: list[Any] = []
    world.campaign.tick = tick - 1
    for kind, key in keys:
        post_job(world, "ENEMY", JobSpec(kind, key, 1, 500, node=key.split(":")[2]), out)  # type: ignore[arg-type]
    world.campaign.tick = tick
    if debit:
        out.append(_ev(SupplyConsumed, "SupplyConsumed", tick, node_id="east-airbase",
                       amount=debit, cause="SPAWN"))  # fmt: skip
    collector.feed(out)
    collector.observe(world)


def test_collector_follows_a_capture_operation_down_its_funnel(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    world = start_campaign("c", 1, shipped_config)
    collector.feed([spawned(1, 900, "ENEMY_STRIKE_FIGHTER", "ENEMY", None)])
    for node in ("fob-n-w", "cross-n", "fob-s-w"):
        world.owner[node] = "COALITION"
        collector._owner[node] = "COALITION"
    _launch_tick(world, collector, 100, ("STRIKE", "op:OFFENSIVE:fob-n-w:0"))
    _launch_tick(world, collector, 110, ("STRIKE", "op:RETAKE:cross-n:0"))
    _launch_tick(world, collector, 120, ("STRIKE", "op:PROBE:fob-s-w:0"))  # not a capture op
    f = _ev(WeaponFired, "WeaponFired", 130, shooter_id=900, target_id=None,
            target_node_id="fob-n-w")  # fmt: skip
    friendly = _ev(WeaponFired, "WeaponFired", 131, shooter_id=901, target_id=None,
                   target_node_id="cross-n")  # fmt: skip
    collector.feed([spawned(1, 901, "STRIKE_FIGHTER", "COALITION", None), f, friendly])
    down = NodeDefensesDown
    collector.feed([_ev(down, "NodeDefensesDown", 140, node_id="fob-n-w", owner="COALITION"),
                    _ev(down, "NodeDefensesDown", 141, node_id="cross-n", owner="ENEMY"),
                    _ev(CaptureStarted, "CaptureStarted", 150, node_id="fob-n-w", side="ENEMY"),
                    _ev(CaptureStarted, "CaptureStarted", 151, node_id="cross-n", side="COALITION"),
                    _ev(NodeCaptured, "NodeCaptured", 160, node_id="fob-n-w", from_="COALITION",
                        to="ENEMY", participant_commander_ids=[])])  # fmt: skip
    collector.feed([_ev(NodeCaptured, "NodeCaptured", 165, node_id="cross-n", from_="ENEMY",
                        to="COALITION", participant_commander_ids=[])])  # fmt: skip
    # a later Static strike on the captured node belongs to no launch any more, and neither
    # does a Static capture start on the node the coalition took back
    collector.feed([_ev(WeaponFired, "WeaponFired", 170, shooter_id=900, target_id=None,
                        target_node_id="fob-n-w"),
                    _ev(CaptureStarted, "CaptureStarted", 175, node_id="cross-n",
                        side="ENEMY")])  # fmt: skip
    funnel = collector.result(1000)["economy"]["funnel"]
    keys = ("strike_fired", "defenses_down", "capture_started", "captured")
    assert [(x["op"], x["target"], *(x[k] for k in keys)) for x in funnel] == [
        ("OFFENSIVE", "fob-n-w", True, True, True, True),
        ("RETAKE", "cross-n", False, False, False, False),  # wrong shooter / owner / side
    ]
    agg = report._funnel([collector.result(1000)["economy"]])
    assert agg["OFFENSIVE"] == {"launched": 1, "strike_fired": 1, "defenses_down": 1,
                                "capture_started": 1, "captured": 1}  # fmt: skip
    assert agg["RETAKE"]["launched"] == 1 and agg["RETAKE"]["captured"] == 0


def test_offensive_gaps_per_seed_with_lead_in_tail_and_tier() -> None:
    hz = HZ
    minute = 60 * hz
    eco = {
        "ops": [[10 * minute, "OFFENSIVE", "a", True], [15 * minute, "PROBE", "a", True],
                [30 * minute, "OFFENSIVE", "b", True], [60 * minute, "OFFENSIVE", "c", True]],
        "tiers": {"start": "PATROL", "changes": [[5 * minute, "ALPHA"], [30 * minute, "BRAVO"]]},
    }  # fmt: skip
    quiet = {"ops": [], "tiers": {"start": "PATROL", "changes": []}}
    runs = [{"seed": 1, "tick_hz": hz, "ticks_run": 100 * minute},
            {"seed": 2, "tick_hz": hz, "ticks_run": 50 * minute}]  # fmt: skip
    g = report._gaps(runs, [eco, quiet])
    assert g["per_seed"] == [
        {
            "seed": 1,
            "offensives": 3,
            "lead_in_min": 10.0,
            "gaps_min": [20.0, 30.0],
            "tail_min": 40.0,
            "longest_dry_min": 40.0,
        },
        {
            "seed": 2,
            "offensives": 0,
            "lead_in_min": 50.0,
            "gaps_min": [],
            "tail_min": None,
            "longest_dry_min": 50.0,
        },
    ]
    # gap 1 starts at 10 min (ALPHA since 5), gap 2 at 30 min, the tick BRAVO began (it counts)
    assert g["by_tier"] == {"ALPHA": {"n": 1, "median": 20.0, "max": 20.0},
                            "BRAVO": {"n": 1, "median": 30.0, "max": 30.0}}  # fmt: skip


def _dry(offensive_min: list[int], run_min: int) -> float:
    minute = 60 * HZ
    eco = {"ops": [[m * minute, "OFFENSIVE", "a", True] for m in offensive_min],
           "tiers": {"start": "PATROL", "changes": []}}  # fmt: skip
    run = {"seed": 1, "tick_hz": HZ, "ticks_run": run_min * minute}
    return float(report._gaps([run], [eco])["per_seed"][0]["longest_dry_min"])


def test_longest_dry_stretch_counts_lead_in_gaps_and_tail() -> None:
    assert _dry([], 90) == 90.0  # no Offensive: the whole run
    assert _dry([50, 60, 70], 80) == 50.0  # lead-in longest
    assert _dry([10, 60, 70], 80) == 50.0  # middle gap longest
    assert _dry([10, 20, 30], 80) == 50.0  # tail longest
    assert _dry([30], 100) == 70.0  # one Offensive: lead-in 30, tail 70
    assert _dry([60], 100) == 60.0  # one Offensive: lead-in longest


def _d5_eco(per_seed: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "funnel": {},
        "staging": {"sitreps": 0, "capture_launches": 0, "launched": 0, "dispersed": 0,
                    "open": 0, "strike_downed": 0},
        "gaps": {"per_seed": per_seed, "by_tier": {}},
        "pressure_per_hold": [],
        "spawn_by_op": {"ops": {}, "shared": 0, "unattributed": 0},
        "adaptations_per_hour": {},
    }  # fmt: skip


def test_the_markdown_gives_the_longest_dry_stretch_per_seed_with_max_and_median() -> None:
    seeds: list[dict[str, Any]] = [{"seed": s, "lead_in_min": 1.0, "gaps_min": [], "tail_min": None,
              "longest_dry_min": v} for s, v in ((1, 10.0), (2, 30.0), (3, 20.0))]  # fmt: skip
    line = next(x for x in report._d5_lines("p", _d5_eco(seeds)) if "without an Offensive" in x)
    assert "lead-in and tail included" in line
    assert "s1 10.0, s2 30.0, s3 20.0; max 30.0, median 20.0" in line


def test_an_old_report_json_without_the_dry_stretch_renders() -> None:
    old = [{"seed": 1, "lead_in_min": 1.0, "gaps_min": [], "tail_min": None}]
    line = next(x for x in report._d5_lines("p", _d5_eco(old)) if "without an Offensive" in x)
    assert "s1 -; max -, median -" in line


def test_the_markdown_keeps_fractional_offensive_gaps() -> None:
    e = {
        "funnel": {},
        "staging": {"sitreps": 0, "capture_launches": 0, "launched": 0, "dispersed": 0,
                    "open": 0, "strike_downed": 0},
        "gaps": {
            "per_seed": [{"seed": 1, "lead_in_min": 0.4, "gaps_min": [0.6, 12.25],
                          "tail_min": None}],
            "by_tier": {},
        },
        "pressure_per_hold": [],
        "spawn_by_op": {"ops": {}, "shared": 0, "unattributed": 0},
        "adaptations_per_hour": {},
    }  # fmt: skip
    seeds = next(line for line in report._d5_lines("p", e) if "per seed" in line)
    assert "s1: lead-in 0.4, gaps [0.6, 12.2], tail -" in seeds


def test_collector_logs_the_tier_timeline(collector: metrics.Collector) -> None:
    start = collector.tier
    collector.feed([_ev(ThreatTierChanged, "ThreatTierChanged", 500, side="ENEMY", to="BRAVO")])
    assert collector.result(1000)["economy"]["tiers"] == {
        "start": start,
        "changes": [[500, "BRAVO"]],
    }


def test_pressure_is_counted_per_victory_hold(collector: metrics.Collector) -> None:
    collector.pressure_ticks = [50, 100, 120, 200, 250, 260, 400]
    collector.holds = [
        {"start": 100, "end": 250, "broken": True, "ops": 0},
        {"start": 300, "end": None, "broken": False, "ops": 0},
    ]
    holds = collector.result(500)["economy"]["holds"]
    # the start (100) and break (250) ticks count; 50 is before, 260 is between
    assert [h["pressure"] for h in holds] == [4, 1]
    eco = collector.result(500)["economy"]
    run = {"metrics": {"economy": eco}, "ticks_run": 500, "tick_hz": HZ,
           "seed": 1, "viewers": {"peak_concurrent": 1}}  # fmt: skip
    assert report._economy([run])["pressure_per_hold"] == [4, 1]


def test_spawn_debits_go_to_the_single_operation_launched_that_tick(
    collector: metrics.Collector, shipped_config: CampaignConfig
) -> None:
    world = start_campaign("c", 1, shipped_config)
    _launch_tick(world, collector, 100, ("STRIKE", "op:PROBE:fob-s-w:0"), debit=15)
    _launch_tick(world, collector, 200, ("STRIKE", "op:PROBE:cross-n:0"), debit=15)
    _launch_tick(world, collector, 300, ("STRIKE", "op:PROBE:east-airbase:0"),
                 ("STRIKE", "op:OFFENSIVE:fob-n-w:0"), debit=60)  # fmt: skip
    collector.feed([_ev(SupplyConsumed, "SupplyConsumed", 400, node_id="east-airbase",
                        amount=7, cause="SPAWN")])  # fmt: skip
    _launch_tick(world, collector, 410)  # no launch: the 7 is unattributed
    assert collector.result(500)["economy"]["spawn_by_op"] == {
        "ops": {"PROBE": 30}, "shared": 60, "unattributed": 7}  # fmt: skip


def test_sitreps_per_run_hour_by_category_and_staging_count() -> None:
    eco = {
        "adapted": {"STAGING": [2, 1], "CONVOY_ESCORT": [4]},
        "funnel": [], "ops": [], "tiers": {"start": "PATROL", "changes": []},
        "spawn_by_op": {"ops": {}, "shared": 0, "unattributed": 0},
        "sides": {}, "hourly": [], "refused": {"operations_per_hour": {}, "units": {}},
        "grounded_from": {}, "exposure": {}, "budget": {"sum": [], "windows": [],
                                                       "spent": {"base": [], "source": []}},
        "ops_unseen": 0, "holds": [], "army_peak": 0,
    }  # fmt: skip
    run = {"metrics": {"economy": eco}, "ticks_run": 2 * HOUR, "tick_hz": HZ, "seed": 1,
           "viewers": {"peak_concurrent": 0}}  # fmt: skip
    agg = report._economy([run])
    assert agg["adaptations_per_hour"] == {"CONVOY_ESCORT": 2.0, "STAGING": 1.5}
    assert agg["staging"] == {"sitreps": 3, "capture_launches": 0, "launched": 0, "dispersed": 0,
                              "open": 3, "strike_downed": 0}  # fmt: skip


def test_the_report_counts_how_each_massing_closed_and_the_downed_packages() -> None:
    """NX-431 (Q-TD-47, Q-TD-56): 5 massings, 1 launched from staging and 2 dispersed, so 2 still
    open at the end; 3 strike packages downed, over two runs."""

    def run(adapted: dict[str, list[int]]) -> dict[str, Any]:
        eco = {
            "adapted": adapted, "funnel": [], "ops": [],
            "tiers": {"start": "PATROL", "changes": []},
            "spawn_by_op": {"ops": {}, "shared": 0, "unattributed": 0},
            "sides": {}, "hourly": [], "refused": {"operations_per_hour": {}, "units": {}},
            "grounded_from": {}, "exposure": {}, "budget": {"sum": [], "windows": [],
                                                           "spent": {"base": [], "source": []}},
            "ops_unseen": 0, "holds": [], "army_peak": 0,
        }  # fmt: skip
        return {"metrics": {"economy": eco}, "ticks_run": HOUR, "tick_hz": HZ, "seed": 1,
                "viewers": {"peak_concurrent": 0}}  # fmt: skip

    agg = report._economy([
        run({"STAGING": [3], "STAGING_LAUNCHED": [1], "STAGING_DISPERSED": [1],
             "STRIKE_DOWNED": [2]}),
        run({"STAGING": [2], "STAGING_DISPERSED": [1],
             "STRIKE_DOWNED": [1]}),
    ])  # fmt: skip
    assert agg["staging"] == {"sitreps": 5, "capture_launches": 0, "launched": 1, "dispersed": 2,
                              "open": 2, "strike_downed": 3}  # fmt: skip
    line = next(x for x in report._d5_lines("p", agg | {"pressure_per_hold": []}) if "STAGING" in x)
    assert "closed by a launch 1, dispersed 2, open at the end 2" in line
    assert "strike packages downed 3" in line


# --- rare-shortfall metrics (NX-437; ENTERTAINMENT-upkeep Q2 R1-R4, R8, R10, R11) ----------------
WINDOW = 600  # economy.window_ticks of the shipped config at 10 Hz (60 game s)
HALF_HOUR = 30 * 60 * HZ  # 30 game minutes in ticks


def rig(shipped_config: CampaignConfig) -> tuple[metrics.Collector, Any]:
    world = start_campaign("c", 1, shipped_config)
    assert world.rules is not None and world.rules.economy is not None
    assert world.rules.economy.window_ticks == WINDOW
    col = metrics.Collector(
        world, frozenset(), tick_hz=HZ, sample_ticks=600, a3_ticks=1000, idle_sample_ticks=600,
        impact_check_ticks=10, kinds={}, a2_min_tier="ALPHA",
    )  # fmt: skip
    return col, world


def run_windows(col: metrics.Collector, world: Any, upto: int, each: Any = None) -> None:
    """Step the economy window counter from the current one to window `upto`, calling
    `each(window_number)` to set the world's state first."""
    for k in range(world.campaign.running_ticks // WINDOW + 1, upto + 1):
        if each:
            each(k)
        world.campaign.running_ticks = world.campaign.tick = k * WINDOW
        col.observe(world)


def shortfall(col: metrics.Collector) -> dict[str, Any]:
    out: dict[str, Any] = col.result(0)["economy"]["shortfall"]
    return out


def test_r1_r2_r8_unit_time_and_windows_with_a_grounded_viewer(
    shipped_config: CampaignConfig,
) -> None:
    col, world = rig(shipped_config)
    a = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    off = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    off.damage_state = "DISABLED"  # not counted
    ai = world.spawn("STRIKE_FIGHTER", "COALITION", "AI_GARRISON", Vec2(0, 0))
    ai.grounded = True  # a coalition AI unit is neither R1 nor R2
    foe = world.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(0, 0))
    base = sum(
        e.side == "ENEMY" and e.kind in world.rules.armed and e.owner_kind != "COMMANDER"
        for e in world.entities()
    )
    foe.grounded = True
    run_windows(col, world, 1, lambda k: setattr(a, "grounded", True))
    run_windows(col, world, 2, lambda k: setattr(a, "grounded", False))
    s = shortfall(col)
    assert s["windows"] == 2 and s["windows_viewer_grounded"] == 1  # R2: 1 of 2 windows
    assert s["unit_windows"]["COALITION"] == {"units": 4, "grounded": 1}  # R1: a and b, twice
    assert s["unit_windows"]["ENEMY"] == {"units": 2 * base, "grounded": 2}  # R8
    pooled = report._shortfall([col.result(0)["economy"]], 1)
    assert pooled["r1_viewer_grounded_share"] == 0.25
    assert pooled["r2_windows_with_viewer_grounded_share"] == 0.5
    assert pooled["r8_static_grounded_share"] == 2 / (2 * base)


def test_r3_episodes_are_runs_of_windows_with_a_grounded_unit_at_a_home(
    shipped_config: CampaignConfig,
) -> None:
    col, world = rig(shipped_config)
    u = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    v = world.spawn("STRIKE_FIGHTER", "COALITION", "AI_GARRISON", Vec2(0, 0))
    u.home_base, v.home_base = "fob-n-w", "west-airbase"
    plan = {1: (1, 0), 2: (1, 1), 3: (0, 1), 4: (0, 0), 5: (1, 0)}  # window -> (u, v) grounded

    def ground(k: int) -> None:
        u.grounded, v.grounded = (bool(x) for x in plan[k])

    run_windows(col, world, 5, ground)
    eps = [(x["home"], x["start"] // WINDOW, x["windows"]) for x in shortfall(col)["episodes"]]
    # u: windows 1-2 (2 long), then clear at 3-4, then 5 (still open, 1); v: windows 2-3 (2)
    assert eps == [("fob-n-w", 1, 2), ("west-airbase", 2, 2), ("fob-n-w", 5, 1)]
    pooled = report._shortfall([col.result(0)["economy"]], 2)
    assert pooled["r3_episodes"] == 3 and pooled["r3_episodes_per_hour"] == 1.5
    assert pooled["r3_median_episode_windows"] == 2
    assert pooled["r3_episodes_by_home"] == {"fob-n-w": 2, "west-airbase": 1}


def test_r3_a_second_unit_grounding_inside_a_running_episode_is_not_a_new_one(
    shipped_config: CampaignConfig,
) -> None:
    col, world = rig(shipped_config)
    us = [world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0)) for _ in range(2)]
    for u in us:
        u.home_base = "fob-n-w"
    run_windows(col, world, 3, lambda k: setattr(us[0 if k < 3 else 1], "grounded", True))
    us[0].grounded = False
    assert [(x["windows"]) for x in shortfall(col)["episodes"]] == [3]


def test_r4_counts_distinct_viewers_ever_grounded_and_keeps_no_ids(
    shipped_config: CampaignConfig,
) -> None:
    col, _ = rig(shipped_config)
    col.feed([spawned(1, 901 + n, "STRIKE_FIGHTER", "COALITION", commander(n)) for n in (1, 2, 3)])
    col.feed([spawned(1, 950, "STRIKE_FIGHTER", "COALITION", commander(1))])  # one viewer, 2 units
    col.feed([spawned(1, 960, "STRIKE_FIGHTER", "COALITION", None)])  # AI: not a viewer
    for tick, entity in ((5, 902), (6, 902), (7, 903), (8, 950), (9, 960)):
        col.feed([UnitGrounded.model_construct(kind="UnitGrounded", tick=tick, entity_id=entity,
                                               node_id="haven")])  # fmt: skip
    s = shortfall(col)
    assert (s["viewers"], s["viewers_grounded"]) == (3, 2)  # viewers 1 (3 groundings) and 2
    assert commander(1) not in json.dumps(col.result(10))  # counts only (ECONOMY §4 privacy)


@pytest.mark.parametrize(
    ("low_windows", "stretches", "minutes"),
    [(30, 0, 0.0), (31, 1, 31.0)],  # exactly 30 min is not "more than 30"
)
def test_r10_pool_low_stretch_boundary_at_30_minutes(
    shipped_config: CampaignConfig, low_windows: int, stretches: int, minutes: float
) -> None:
    col, world = rig(shipped_config)
    world.storage["COALITION"] = 100

    def pool(k: int) -> None:
        world.pool["COALITION"] = 9 if k <= low_windows else 10  # 10 is not below 10% of 100

    run_windows(col, world, low_windows + 1, pool)
    assert shortfall(col)["pool_low"] == {"stretches": stretches, "minutes": minutes}


def test_r10_an_open_stretch_counts_and_a_gap_splits_two(shipped_config: CampaignConfig) -> None:
    col, world = rig(shipped_config)
    world.storage["COALITION"] = 100
    low = {k for k in range(1, 61) if k <= 20 or k >= 22}  # 20 low, 1 ok, 39 low (still open)
    run_windows(
        col, world, 60, lambda k: world.pool.__setitem__("COALITION", 1 if k in low else 50)
    )
    assert shortfall(col)["pool_low"] == {"stretches": 1, "minutes": 39.0}  # the 20 is too short


def episode_after(shipped_config: CampaignConfig, home: str, events: list[Any]) -> bool:
    """Feed `events`, ground a unit at `home` in window 61 only; return the episode's R11 flag."""
    col, world = rig(shipped_config)
    u = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    u.home_base = home
    col.feed(events)
    run_windows(col, world, 61, lambda k: setattr(u, "grounded", k == 61))
    (ep,) = shortfall(col)["episodes"]
    assert ep["start"] == START
    return bool(ep["after_action"])


START = 61 * WINDOW


def capture(tick: int, node: str, side: str = "ENEMY") -> Any:
    return CaptureStarted.model_construct(kind="CaptureStarted", tick=tick, node_id=node, side=side)


def bridge(tick: int, node: str) -> Any:
    return BridgeDestroyed.model_construct(kind="BridgeDestroyed", tick=tick, node_id=node)


def test_r11_attribution_window_edge_is_30_minutes_inclusive(
    shipped_config: CampaignConfig,
) -> None:
    cfg = shipped_config
    assert episode_after(cfg, "fob-n-w", [capture(START - HALF_HOUR, "fob-n-w")])
    assert not episode_after(cfg, "fob-n-w", [capture(START - HALF_HOUR - 1, "fob-n-w")])
    assert not episode_after(cfg, "fob-n-w", [capture(START - 5, "west-airbase")])  # elsewhere
    assert not episode_after(cfg, "fob-n-w", [capture(START - 5, "fob-n-w", "COALITION")])


def test_r11_counts_a_cut_bridge_on_the_homes_road_only(shipped_config: CampaignConfig) -> None:
    cfg = shipped_config  # fob-n-e is reached from haven over bridge-n; fob-n-w has no bridge
    assert episode_after(cfg, "fob-n-e", [bridge(START - 100, "bridge-n")])
    assert not episode_after(cfg, "fob-n-e", [bridge(START - 100, "bridge-s")])
    assert not episode_after(cfg, "fob-n-w", [bridge(START - 100, "bridge-n")])
    assert not episode_after(cfg, "fob-n-e", [bridge(START - HALF_HOUR - 1, "bridge-n")])


def test_r11_a_truck_that_unloaded_is_no_longer_a_convoy(shipped_config: CampaignConfig) -> None:
    col, world = rig(shipped_config)
    truck = world.spawn("LOGI_TRUCK", "COALITION", "COMMANDER", Vec2(0, 0))
    truck.cargo, truck.path = 5, ["fob-n-w"]
    u = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    u.home_base = "fob-n-w"
    col.feed([
        spawned(1, 700, "ENEMY_ARMOR", "ENEMY", None),
        spawned(1, truck.id, "LOGI_TRUCK", "COALITION", None),
    ])  # fmt: skip
    run_windows(col, world, 1)  # seen loaded and bound for fob-n-w
    truck.cargo, truck.path = 0, []  # delivered; the truck stays in the world
    run_windows(col, world, 2)
    col.feed([killed(START - 100, truck.id, 700, side="COALITION")])
    run_windows(col, world, 61, lambda k: setattr(u, "grounded", k == 61))
    (ep,) = shortfall(col)["episodes"]
    assert ep["after_action"] is False


@pytest.mark.parametrize(
    ("cargo", "killer", "after"),
    [(5, 700, True), (5, None, False), (5, 701, False), (None, 700, False)],
)
def test_r11_counts_a_loaded_convoy_killed_by_the_static_on_its_way_home(
    shipped_config: CampaignConfig, cargo: int | None, killer: int | None, after: bool
) -> None:
    col, world = rig(shipped_config)
    truck = world.spawn("LOGI_TRUCK", "COALITION", "COMMANDER", Vec2(0, 0))
    truck.cargo, truck.path = cargo, ["fob-n-w"]
    u = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    u.home_base = "fob-n-w"
    col.feed([
        spawned(1, 700, "ENEMY_ARMOR", "ENEMY", None),  # the Static's unit
        spawned(1, 701, "STRIKE_FIGHTER", "COALITION", None),  # a friendly one
        spawned(1, truck.id, "LOGI_TRUCK", "COALITION", None),
    ])  # fmt: skip
    run_windows(col, world, 1)  # observe records where the loaded truck is bound
    world.remove(truck.id)
    col.feed([killed(START - 100, truck.id, killer, side="COALITION")])
    run_windows(col, world, 61, lambda k: setattr(u, "grounded", k == 61))
    (ep,) = shortfall(col)["episodes"]
    assert ep["after_action"] is after


def test_shortfall_keys_reach_report_json_and_markdown(shipped_config: CampaignConfig) -> None:
    col, world = rig(shipped_config)
    u = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    u.home_base = "fob-n-w"
    col.feed([capture(START - 10, "fob-n-w")])
    run_windows(col, world, 61, lambda k: setattr(u, "grounded", k >= 60))
    f = report._shortfall([col.result(START)["economy"]], 1)
    assert set(f) == {
        "windows", "r1_viewer_grounded_share", "r8_static_grounded_share",
        "r2_windows_with_viewer_grounded_share", "r3_episodes", "r3_episodes_per_hour",
        "r3_episodes_by_home", "r3_median_episode_windows", "r4_viewers_grounded", "r4_viewers",
        "r4_viewers_grounded_share", "r10_pool_low_stretches", "r10_pool_low_minutes",
        "r11_episodes_after_enemy_action", "r11_share", "sitreps",
    }  # fmt: skip
    assert (f["r3_episodes"], f["r11_share"], f["r1_viewer_grounded_share"]) == (1, 1.0, 2 / 61)
    lines = "\n".join(report._shortfall_lines("p", f))
    assert "R1 viewer unit-time grounded 3.3%" in lines
    assert "R3 1 (1.00 per run-hour, median 2.0 windows, by home {'fob-n-w': 1})" in lines
    assert "R11 after enemy action within 30 min 100.0% (1 of 1)" in lines
    assert "R10 coalition pool under 10% of cap for over 30 min: 0 stretches, 0.0 min" in lines
    empty = report._shortfall([{"shortfall": None}], 0)  # an old report.json without the data
    assert empty["r3_episodes"] == 0 and empty["r11_share"] is None
    assert "R1 viewer unit-time grounded -" in report._shortfall_lines("p", empty)[0]


def test_shortfall_sitreps_are_counted_by_side_and_status(shipped_config: CampaignConfig) -> None:
    """NX-436: the SupplyShortfall lines per side and status, pooled into the report."""
    col, _ = rig(shipped_config)

    def sitrep(side: str, status: str) -> Any:
        return SupplyShortfall.model_construct(kind="SupplyShortfall", tick=10, side=side,
                                               status=status, node_id="fob-n-w")  # fmt: skip

    col.feed([sitrep("COALITION", "STARTED"), sitrep("COALITION", "ENDED"),
              sitrep("COALITION", "STARTED"), sitrep("ENEMY", "STARTED")])  # fmt: skip
    f = report._shortfall([col.result(0)["economy"]] * 2, 1)  # two seeds pool
    assert f["sitreps"] == {"COALITION ENDED": 2, "COALITION STARTED": 4, "ENEMY STARTED": 2}
    line = report._shortfall_lines("p", f)[1]
    assert line.endswith("sitreps (NX-436) COALITION ENDED 2, COALITION STARTED 4, ENEMY STARTED 2")
    assert report._shortfall_lines("p", report._shortfall([{"shortfall": None}], 0))[1].endswith(
        "sitreps (NX-436) none"
    )
    assert report._shortfall([{"shortfall": None}], 0)["sitreps"] == {}
