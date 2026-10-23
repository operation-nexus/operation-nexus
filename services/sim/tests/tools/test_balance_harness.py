"""Balance harness tests (NX-031 part 1, Q-SIM-91; tools/balance). Short runs only."""

import dataclasses
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
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
from nexus.core.step import HANDLERS, step
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
from profiles import DATA, KINDS, ROLES, Data, load, schedule  # type: ignore[import-not-found,unused-ignore]

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
    assert report._a1([early], t)["seeds_in_window"] == 0  # under 24 h is a miss
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


def test_set_rejects_a_bool_leaf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The shipped config has no bool leaf today, so feed one: True must not be coerced to 1.
    tree = yaml.safe_load(balance.ConfigPaths().balance.read_text())
    tree["debug_flag"] = True
    (shipped := tmp_path / "balance.yaml").write_text(yaml.safe_dump(tree))
    monkeypatch.setattr(balance, "ConfigPaths", lambda: SimpleNamespace(balance=shipped))
    with pytest.raises(ValueError, match="numeric"):
        balance.override_balance(["debug_flag=1"])


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
