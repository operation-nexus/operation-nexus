"""Balance harness tests (NX-031 part 1, Q-SIM-91; tools/balance). Short runs only."""

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.contracts.gen.events.supply_delivered import SupplyDelivered
from nexus.contracts.gen.events.threat_tier_changed import ThreatTierChanged
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.contracts.gen.events.weapon_impact import WeaponImpact
from nexus.core.campaign import momentum
from nexus.core.world import Vec2
from nexus.runtime.campaign_config import CampaignConfig, start_campaign
from nexus.runtime.command_log import CommandLogReader, Tombstone

# The harness modules live in tools/balance, outside the package: put them on the path, as the
# other tool tests reach their scripts. mypy cannot see them from here, so they type as Any.
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "balance"))
import balance  # type: ignore[import-not-found,unused-ignore]
import metrics  # type: ignore[import-not-found,unused-ignore]
import personas  # type: ignore[import-not-found,unused-ignore]
import report  # type: ignore[import-not-found,unused-ignore]
import runner  # type: ignore[import-not-found,unused-ignore]
from profiles import ROLES, Data, load, schedule  # type: ignore[import-not-found,unused-ignore]

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
            assert e["role"] in ROLES and e["target"] is None
    assert a["commands"] == {
        k: sum(e["kind"] == k for e in entries) for k in sorted({e["kind"] for e in entries})
    }


# --- personas ---------------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(load().personas))
def test_persona_emits_only_valid_commands(name: str) -> None:
    persona = load().personas[name]
    v = personas.new_viewer(7, persona, "prime-50", 1)
    adapter: TypeAdapter[Command] = TypeAdapter(Command)
    join = personas.join_command(v, 5, 1)
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
        world, newbies, tick_hz=HZ, sample_ticks=600, a3_ticks=1000, idle_sample_ticks=600
    )


def test_newbie_time_to_first_impact(collector: metrics.Collector) -> None:
    for n in (1, 2, 3, 4, 5, 6):  # 6 is not a newbie
        collector.note_join(commander(n), 100)
    collector.note_join(commander(1), 900)  # only the first JOIN counts
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
            "newbie": {"ttfi_s": [60.0, 120.0], "no_impact_observed_s": []},
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
    assert report._a1([early], t)["seeds_in_window"] == 0  # under 24 h is a miss
    slow = fake_run(newbie={"ttfi_s": [100.0], "no_impact_observed_s": [400.0, 500.0]})
    assert report._a2([slow], t)["status"] == report.FAIL  # two of three never saw an impact
    assert report._a2([fake_run()], t)["status"] == report.PASS
    unresolved = fake_run(newbie={"ttfi_s": [], "no_impact_observed_s": [10.0]})
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

    def flaky(profile: str, seed: int, *args: Any) -> Any:
        if profile == "quiet-5":
            raise KeyError("oops")
        return real(profile, seed, *args)

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
