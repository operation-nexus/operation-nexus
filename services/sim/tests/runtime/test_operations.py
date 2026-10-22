"""NX-156: the operation catalog loader (CONFIG-AND-CONTENT §8a, THREAT-DIRECTOR §7 Q-TD-7)."""

import dataclasses
from pathlib import Path

import pytest
import yaml

from nexus.runtime.campaign_config import REPO, ConfigPaths, load_campaign_config
from nexus.runtime.config import ConfigError
from nexus.runtime.operations import operations_hash

SHIPPED = REPO / "content" / "operations.yaml"
# The canonical hash of the shipped catalog: a content change moves it (and config_hash with it).
GOLDEN_OPERATIONS_HASH = "d78874aee52c2cc36db75aeaefc133ec00e5de5925b797536cfb3081bfcad41c"


def tree() -> dict[str, object]:
    loaded: dict[str, object] = yaml.safe_load(SHIPPED.read_text(encoding="utf-8"))
    return loaded


def load(tmp_path: Path, data: object) -> object:
    path = tmp_path / "operations.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_campaign_config(dataclasses.replace(ConfigPaths(), operations=path))


def op(data: dict[str, object], op_id: str) -> dict[str, object]:
    ops: list[dict[str, object]] = data["operations"]  # type: ignore[assignment]
    return next(o for o in ops if o["id"] == op_id)


def test_shipped_catalog_is_q_sim_81_in_id_order() -> None:
    rules = load_campaign_config().rules.director
    assert rules is not None
    got = {
        o.id: (o.cost, o.priority, [(j.kind, j.at, j.slots) for j in o.jobs])
        for o in rules.operations
    }
    assert list(got) == sorted(got)
    assert set(got) == {
        "OFFENSIVE",
        "RETAKE",
        "PROBE",
        "RECON",
        "ESCORT_CONVOYS",
        "REINFORCE_IADS",
        "DECOY_BLINK",
    }
    assert got["OFFENSIVE"][0] == 60 and str(got["OFFENSIVE"][1]) == "1"
    assert [j[0] for j in got["OFFENSIVE"][2]] == ["STAGE", "STRIKE", "CAPTURE"]
    assert [j[2] for j in got["RETAKE"][2]] == [1, 3]
    assert (got["ESCORT_CONVOYS"][0], got["RECON"][0], got["DECOY_BLINK"][0]) == (
        10,
        5,
        0,
    )  # Q-SIM-82
    assert "STRIKE_BRIDGE" not in got


def test_shipped_hash_is_pinned_and_ignores_file_order(tmp_path: Path) -> None:
    config = load_campaign_config()
    director = config.rules.director
    assert director is not None
    assert operations_hash(director.operations) == GOLDEN_OPERATIONS_HASH
    data = tree()
    data["operations"] = list(reversed(data["operations"]))  # type: ignore[call-overload]
    shuffled = load(tmp_path, data)
    assert shuffled.config_hash == config.config_hash  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda d: op(d, "PROBE")["jobs"][0].update(kind="BOMB"), "kind"),  # type: ignore[index]
        (lambda d: op(d, "PROBE").update(preconditions=["target_is_nice"]), "preconditions"),
        (lambda d: op(d, "PROBE").update(cost=81), "above the largest tier budget"),
        (lambda d: op(d, "PROBE").update(cost=-1), "cost"),
        (lambda d: op(d, "PROBE").update(cost=1.5), "cost"),
        (lambda d: op(d, "PROBE")["jobs"][0].update(at="the_moon"), "at"),  # type: ignore[index]
        (lambda d: op(d, "PROBE")["jobs"][0].update(unit_kinds=["STRIKE_FIGHTER"]), "not an ENEMY"),  # type: ignore[index]
        (lambda d: op(d, "PROBE")["jobs"][0].update(unit_kinds=["ENEMY_ARMOR"]), "cannot take"),  # type: ignore[index]
        (lambda d: op(d, "PROBE")["jobs"][0].update(slots=7), "max_spawns_per_window"),  # type: ignore[index]
        (lambda d: op(d, "PROBE")["jobs"][0].update(at="each_convoy"), "ESCORT_CONVOY"),  # type: ignore[index]
        (lambda d: op(d, "PROBE").update(effect="EMISSION_BLINK"), "exactly one"),
        (lambda d: op(d, "PROBE").update(preconditions=["has_unescorted_convoy"]), "does not suit"),
        (lambda d: op(d, "DECOY_BLINK").update(cost=5), "no units, so no cost"),
        (lambda d: op(d, "PROBE").update(cost=0), "costs at least 1"),
        (
            lambda d: op(d, "PROBE").update(
                preconditions=["target_is_frontline", "target_is_frontline"]
            ),
            "duplicate in preconditions",
        ),
        (lambda d: op(d, "PROBE").update(id="PROBE2"), "op_priority"),
        (lambda d: d["operations"].append(dict(op(d, "PROBE"))), "duplicate"),
    ],
)
def test_loader_rejects(tmp_path: Path, edit: object, message: str) -> None:
    data = tree()
    edit(data)  # type: ignore[operator]
    with pytest.raises(ConfigError, match=message):
        load(tmp_path, data)
