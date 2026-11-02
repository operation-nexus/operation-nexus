"""NX-495 (GAMEPLAY §5 "Absolute floor", Q-TD-123, Q-TD-132 (B)): `logistics.starve_floor_mode`
`fraction` is today's floor, `loadouts` is min(N x C, node_max_stock) with C the largest
`logistics.loadout_cost`; the Director's surplus reference stays on the fraction floor.

Expected numbers are worked by hand from the shipped strait-1 values: `node_max_stock` AIRBASE and
HQ 2,000, FOB 1,000, BRIDGE 0; `starve_threshold` 0.25 (floors 500 and 250); C 20 (STRIKE_FIGHTER,
ENEMY_FIGHTER, ENEMY_STRIKE_FIGHTER); N 5 (100). Every config goes through `shipped_config`
overrides, so the loader's key path is the one under test. Loader refusals are in
`tests/runtime/test_config.py`.
"""

from typing import Any

from test_join import CAMPAIGN_ID

from nexus.core.defense import drain
from nexus.core.director import surplus
from nexus.core.fog import side_view
from nexus.core.logistics import keeps, plan_deploy
from nexus.core.rearm import is_starved
from nexus.core.step import step
from nexus.core.tasking_gen import starving_need
from nexus.core.world import World, load, save, state_hash
from nexus.runtime.campaign_config import CampaignConfig, start_campaign
from nexus.runtime.golden import shipped_config

LOADOUTS = {"logistics.starve_floor_mode": "loadouts"}
DEFAULT = shipped_config({})
LOADOUT_CFG = shipped_config(LOADOUTS)
FINITE = ("west-airbase", "east-airbase", "static-hq", "fob-n-w", "fob-s-w", "cross-n", "cross-s",
          "fob-n-e", "fob-s-e")  # fmt: skip
BRIDGES = ("bridge-n", "bridge-s")
FRACTION_FLOORS = {
    "west-airbase": 500, "east-airbase": 500, "static-hq": 500,
    "fob-n-w": 250, "fob-s-w": 250, "cross-n": 250, "cross-s": 250, "fob-n-e": 250, "fob-s-e": 250,
    "bridge-n": 0, "bridge-s": 0,
}  # fmt: skip


def world(c: CampaignConfig, seed: int = 1) -> World:
    return start_campaign(CAMPAIGN_ID, seed, c)


def floors(**overrides: object) -> dict[str, int]:
    return dict(shipped_config({**LOADOUTS, **overrides}).rules.supply.starve_floor)


# --- fraction is today's rule -----------------------------------------------------------------


def test_fraction_is_the_default_and_todays_floor_at_every_node() -> None:
    assert dict(DEFAULT.rules.supply.starve_floor) == FRACTION_FLOORS
    explicit = shipped_config({"logistics.starve_floor_mode": "fraction"})
    assert dict(explicit.rules.supply.starve_floor) == FRACTION_FLOORS


def test_in_fraction_mode_n_is_not_read() -> None:
    n9 = shipped_config({"logistics.starve_floor_loadouts": 9})
    assert dict(n9.rules.supply.starve_floor) == FRACTION_FLOORS


def test_fraction_follows_the_threshold_and_storage_as_before() -> None:
    low = shipped_config({"logistics.starve_threshold": 0.05}).rules.supply.starve_floor
    assert low["west-airbase"] == 100 and low["fob-n-e"] == 50
    big = shipped_config({"logistics.node_max_stock.AIRBASE": 4000}).rules.supply.starve_floor
    assert big["west-airbase"] == 1000  # the fraction floor grows with storage


# --- loadouts: N x C, capped at the maximum -----------------------------------------------------


def test_loadouts_n5_c20_gives_100_at_every_base_and_0_at_a_bridge() -> None:
    f = dict(LOADOUT_CFG.rules.supply.starve_floor)
    assert all(f[n] == 100 for n in FINITE)
    assert all(f[b] == 0 for b in BRIDGES)
    assert set(f) == set(FRACTION_FLOORS)


def test_n_3_and_4_give_60_and_80() -> None:
    assert floors(**{"logistics.starve_floor_loadouts": 3})["west-airbase"] == 60
    assert floors(**{"logistics.starve_floor_loadouts": 4})["fob-n-w"] == 80


def test_a_node_whose_maximum_is_below_n_times_c_gets_its_maximum() -> None:
    # N 26 x C 20 = 520: a FOB at maximum 500 (its start stock) is capped, an airbase is not
    f = floors(**{"logistics.starve_floor_loadouts": 26, "logistics.node_max_stock.FOB": 500})
    assert f["fob-n-w"] == 500 and f["west-airbase"] == 520
    assert f["bridge-n"] == 0


def test_doubling_the_maximum_leaves_the_floor_unchanged() -> None:
    doubled = floors(**{
        "logistics.node_max_stock.AIRBASE": 4000,
        "logistics.node_max_stock.HQ": 4000,
        "logistics.node_max_stock.FOB": 2000,
    })  # fmt: skip
    assert doubled == floors() and doubled["west-airbase"] == 100 and doubled["fob-n-w"] == 100


def test_the_dearest_kind_sets_c_whoever_holds_it() -> None:
    parity_off = {"economy.cost_parity": False}
    # raising a kind above C raises every node's floor, the Static's bases too
    up = floors(**parity_off, **{"logistics.loadout_cost.RECON_UAV": 30})
    assert all(up[n] == 150 for n in FINITE) and up["bridge-s"] == 0
    # lowering a kind that is not the dearest changes nothing
    down = floors(**parity_off, **{"logistics.loadout_cost.ENEMY_ARMOR": 10})
    assert down == floors()
    # nor does cutting the one coalition strike kind: ENEMY_FIGHTER still costs 20
    assert floors(**parity_off, **{"logistics.loadout_cost.STRIKE_FIGHTER": 10}) == floors()


# --- the readers follow -------------------------------------------------------------------------


def at(c: CampaignConfig, node: str, stock: int) -> World:
    w = world(c)
    w.stock[node] = stock
    return w


def test_a_base_at_150_is_not_starved_in_loadouts_mode() -> None:
    for c, starved in ((LOADOUT_CFG, False), (DEFAULT, True)):
        w = at(c, "west-airbase", 150)
        assert w.rules is not None
        assert is_starved(w, w.rules, "west-airbase") is starved
        sup = w.rules.supply
        need = starving_need(150, sup.starve_floor["west-airbase"], (0, 1))  # LC-2 demand share
        assert (need > 0) is starved


def test_a_base_at_150_takes_no_hp_drain_in_loadouts_mode() -> None:
    for c, loses in ((LOADOUT_CFG, False), (DEFAULT, True)):
        w = at(c, "west-airbase", 150)
        assert w.rules is not None and w.rules.defense is not None
        before = w.defense_hp["west-airbase"]
        for _ in range(w.rules.defense.ticks_per_min):  # a minute of running ticks
            drain(w, [])
        assert (w.defense_hp["west-airbase"] < before) is loses


def test_a_source_ships_down_to_100_on_a_starving_run() -> None:
    for c, kept in ((LOADOUT_CFG, 100), (DEFAULT, 250)):
        w = at(c, "west-airbase", 40)  # starving under either floor
        assert w.rules is not None
        assert keeps(w, w.rules, "COALITION", "west-airbase")["fob-n-w"] == kept


def test_a_jet_deploys_at_west_airbase_from_150() -> None:
    for c, where in ((LOADOUT_CFG, "west-airbase"), (DEFAULT, None)):
        w = at(c, "west-airbase", 150)  # 150 >= floor 100 + max(50, 20); 150 < 500 + 50
        assert w.rules is not None
        plan = plan_deploy(w, w.rules, "COALITION", "STRIKE_FIGHTER", "fob-n-w")
        assert (None if plan is None else plan[0]) == where
    w = at(LOADOUT_CFG, "west-airbase", 149)
    assert w.rules is not None
    assert plan_deploy(w, w.rules, "COALITION", "STRIKE_FIGHTER", "fob-n-w") is None


# --- the Director's surplus does not follow -----------------------------------------------------


def static_surplus(w: World) -> int:
    assert w.rules is not None
    return surplus(side_view(w, "ENEMY"), w.rules, w.stock)


def test_the_directors_reference_is_the_fraction_floor_in_loadouts_mode() -> None:
    sup = LOADOUT_CFG.rules.supply
    assert dict(sup.surplus_ref) == FRACTION_FLOORS  # not the live floor (100)
    assert sup.surplus_ref["east-airbase"] == 500 and sup.starve_floor["east-airbase"] == 100
    assert static_surplus(world(LOADOUT_CFG)) == static_surplus(world(DEFAULT)) == 1500


def test_the_reference_follows_the_threshold_and_share_not_the_mode() -> None:
    for extra, ref in (
        (
            {"logistics.starve_threshold": 0.4},
            800,
        ),  # max(500, ceil(0.4 x 2000)): the fraction floor
        ({"director.surplus_ref_frac": 0.4}, 800),  # the share
        ({"logistics.starve_threshold": 0.05}, 500),  # the share 0.25
    ):
        a = shipped_config({**LOADOUTS, **extra}).rules.supply
        b = shipped_config(extra).rules.supply
        assert dict(a.surplus_ref) == dict(b.surplus_ref)
        assert a.surplus_ref["east-airbase"] == ref


# --- determinism, snapshot ----------------------------------------------------------------------


def run(w: World, ticks: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _ in range(ticks):
        out += [e.model_dump() for e in step(w, [])]
    return out


def test_a_loadouts_run_is_deterministic() -> None:
    def once() -> tuple[str, list[dict[str, Any]]]:
        w = world(LOADOUT_CFG, seed=7)
        events = run(w, 1300)  # two director windows and a bit
        return state_hash(w), events

    first = once()
    assert first[1]
    assert once() == first


def test_save_and_load_round_trip_in_loadouts_mode() -> None:
    w = world(LOADOUT_CFG, seed=7)
    run(w, 900)
    copy = load(save(w))
    copy.rules = w.rules  # the floor is derived from config: the snapshot format is unchanged
    assert state_hash(copy) == state_hash(w)
    assert run(copy, 700) == run(w, 700)
    assert state_hash(copy) == state_hash(w)
