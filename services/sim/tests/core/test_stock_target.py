"""NX-501 (GAMEPLAY §5 "Stock target cap", Q-TD-133 (a)): `logistics.stock_target_mode` `fraction`
is today's target, `loadouts` is min(max(M x C, the node's live floor), node_max_stock) with C the
largest `logistics.loadout_cost`; every reader of `Supply.stock_target` follows it.

Expected numbers are worked by hand from the shipped strait-1 values: `node_max_stock` AIRBASE and
HQ 2,000, FOB 1,000, BRIDGE 0; `stock_target_frac` 0.8 (1,600 and 800); `starve_threshold` 0.25
(floors 500 and 250); C 20; floor `loadouts` N 5 (100); M 15 (300). Every config goes through
`shipped_config` overrides, so the loader's key path is the one under test. Loader refusals are in
`tests/runtime/test_config.py`.
"""

from typing import Any

from test_join import CAMPAIGN_ID
from test_staging import at_floor, fire, offensive
from test_staging import config as staging_config
from test_staging import world as staging_world

from nexus.core.bridges import enemy_held
from nexus.core.fog import side_view
from nexus.core.logistics import keeps, plan_run, stock_targets
from nexus.core.step import step
from nexus.core.tasking_gen import _resupply
from nexus.core.world import World, load, save, state_hash
from nexus.runtime.campaign_config import CampaignConfig, start_campaign
from nexus.runtime.golden import shipped_config

LOADOUTS = {"logistics.stock_target_mode": "loadouts"}
FLOOR_LOADOUTS = {"logistics.starve_floor_mode": "loadouts"}
BOTH = {**FLOOR_LOADOUTS, **LOADOUTS}
DEFAULT = shipped_config({})
BOTH_CFG = shipped_config(BOTH)
FINITE = ("west-airbase", "east-airbase", "static-hq", "fob-n-w", "fob-s-w", "cross-n", "cross-s",
          "fob-n-e", "fob-s-e")  # fmt: skip
BRIDGES = ("bridge-n", "bridge-s")
FRACTION_TARGETS = {
    "west-airbase": 1600, "east-airbase": 1600, "static-hq": 1600,
    "fob-n-w": 800, "fob-s-w": 800, "cross-n": 800, "cross-s": 800, "fob-n-e": 800, "fob-s-e": 800,
    "bridge-n": 0, "bridge-s": 0,
}  # fmt: skip


def world(c: CampaignConfig, seed: int = 1) -> World:
    return start_campaign(CAMPAIGN_ID, seed, c)


def targets(**overrides: object) -> dict[str, int]:
    return dict(shipped_config({**BOTH, **overrides}).rules.supply.stock_target)


# --- fraction is today's rule -----------------------------------------------------------------


def test_fraction_is_the_default_and_todays_target_at_every_node() -> None:
    assert dict(DEFAULT.rules.supply.stock_target) == FRACTION_TARGETS
    explicit = shipped_config({"logistics.stock_target_mode": "fraction"})
    assert dict(explicit.rules.supply.stock_target) == FRACTION_TARGETS


def test_in_fraction_mode_m_is_not_read() -> None:
    for extra in ({}, FLOOR_LOADOUTS):
        m9 = shipped_config({**extra, "logistics.stock_target_loadouts": 9})
        assert dict(m9.rules.supply.stock_target) == FRACTION_TARGETS


def test_fraction_follows_the_fraction_and_storage_as_before() -> None:
    low = shipped_config({"logistics.stock_target_frac": 0.5}).rules.supply.stock_target
    assert low["west-airbase"] == 1000 and low["fob-n-e"] == 500
    big = shipped_config({"logistics.node_max_stock.AIRBASE": 4000}).rules.supply.stock_target
    assert big["west-airbase"] == 3200  # the fraction target grows with storage


# --- loadouts: max(M x C, floor), capped at the maximum -----------------------------------------


def test_m15_c20_gives_300_at_every_base_and_0_at_a_bridge() -> None:
    t = targets()
    assert all(t[n] == 300 for n in FINITE) and all(t[b] == 0 for b in BRIDGES)
    assert set(t) == set(FRACTION_TARGETS)


def test_m_10_and_20_give_200_and_400() -> None:
    assert targets(**{"logistics.stock_target_loadouts": 10})["west-airbase"] == 200
    assert targets(**{"logistics.stock_target_loadouts": 20})["fob-n-w"] == 400


def test_with_floor_fraction_the_target_is_max_of_300_and_the_floor() -> None:
    t = dict(shipped_config(LOADOUTS).rules.supply.stock_target)
    assert all(t[n] == 500 for n in ("west-airbase", "east-airbase", "static-hq"))  # the floor
    assert all(t[n] == 300 for n in FINITE[3:])  # FOBs: 300 over their floor of 250
    assert t["bridge-n"] == 0 == t["bridge-s"]


def test_a_node_whose_maximum_is_below_m_times_c_gets_its_maximum() -> None:
    # M 26 x C 20 = 520: a FOB at maximum 500 (its start stock) is capped, an airbase is not
    t = targets(**{"logistics.stock_target_loadouts": 26, "logistics.node_max_stock.FOB": 500})
    assert t["fob-n-w"] == 500 and t["west-airbase"] == 520 and t["bridge-n"] == 0


def test_doubling_the_maximum_leaves_the_target_unchanged() -> None:
    doubled = targets(**{
        "logistics.node_max_stock.AIRBASE": 4000,
        "logistics.node_max_stock.HQ": 4000,
        "logistics.node_max_stock.FOB": 2000,
    })  # fmt: skip
    assert doubled == targets() and doubled["west-airbase"] == 300 and doubled["fob-n-w"] == 300


def test_raising_the_dearest_kind_raises_every_target_whoever_holds_it() -> None:
    parity_off = {"economy.cost_parity": False}
    up = targets(**parity_off, **{"logistics.loadout_cost.RECON_UAV": 30})  # C 30: M x C 450
    assert all(up[n] == 450 for n in FINITE) and up["bridge-s"] == 0
    # lowering a kind that is not the dearest changes nothing
    assert targets(**parity_off, **{"logistics.loadout_cost.ENEMY_ARMOR": 10}) == targets()


# --- the readers follow -------------------------------------------------------------------------


def posted(w: World, node: str) -> bool:
    assert w.rules is not None and w.rules.tasking is not None
    view = side_view(w, "COALITION")
    held = enemy_held(w, w.rules, "COALITION")
    jobs = _resupply(w, w.rules, w.rules.tasking, "COALITION", view, held)
    return f"resupply:{node}" in [j.key for j in jobs]


def test_a_fob_at_290_posts_a_stocking_job_and_one_at_300_does_not() -> None:
    for stock, job in ((290, True), (300, False)):
        w = world(BOTH_CFG)
        w.stock["fob-n-w"] = stock  # 100 <= stock: not starved, no damage
        assert posted(w, "fob-n-w") is job, stock
    w = world(DEFAULT)  # fraction: the target is 800, so 300 posts
    w.stock["fob-n-w"] = 300
    assert posted(w, "fob-n-w")


def test_a_stocking_run_loads_only_up_to_300() -> None:
    w = world(BOTH_CFG)
    assert w.rules is not None
    w.stock.update({"fob-n-w": 290, "west-airbase": 300, "fob-s-w": 350})
    assert keeps(w, w.rules, "COALITION", "fob-n-w")["fob-s-w"] == 300  # its own target
    run = plan_run(w, w.rules, "COALITION", "fob-n-w")
    assert run and (run.source, run.cargo) == ("fob-s-w", 50)  # only what is above 300


def test_a_staging_base_still_gets_the_fs3_raise_above_its_target() -> None:
    # floor `loadouts` 100 and M 5 give a target of 100, the floor: staging adds the armor's 40
    c = staging_config({**BOTH, "logistics.stock_target_loadouts": 5})
    w = staging_world(c)
    assert w.rules is not None
    at_floor(w)
    assert stock_targets(w, w.rules)["fob-n-e"] == 100
    fire(w, offensive(w, "fob-n-w"))
    assert stock_targets(w, w.rules)["fob-n-e"] == 100 + 40  # FS-3, unchanged by the mode
    assert stock_targets(w, w.rules)["fob-s-e"] == 100  # elsewhere unchanged


# --- determinism, snapshot ----------------------------------------------------------------------


def run(w: World, ticks: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _ in range(ticks):
        out += [e.model_dump() for e in step(w, [])]
    return out


def test_a_loadouts_run_is_deterministic() -> None:
    def once() -> tuple[str, list[dict[str, Any]]]:
        w = world(BOTH_CFG, seed=7)
        events = run(w, 1300)  # two director windows and a bit
        return state_hash(w), events

    first = once()
    assert first[1]
    assert once() == first


def test_save_and_load_round_trip_in_loadouts_mode() -> None:
    w = world(BOTH_CFG, seed=7)
    run(w, 900)
    copy = load(save(w))
    copy.rules = w.rules  # the target is derived from config: the snapshot format is unchanged
    assert state_hash(copy) == state_hash(w)
    assert run(copy, 700) == run(w, 700)
    assert state_hash(copy) == state_hash(w)
