"""NX-170 part a: the generated wire message types accept good payloads and reject bad ones
(CONTRACTS section 7). Stands alone: no frame builder, no sim."""

from typing import Any

import pytest
from pydantic import ValidationError

from nexus.contracts.gen.wire.ack import Ack
from nexus.contracts.gen.wire.control import Control
from nexus.contracts.gen.wire.delta import Delta
from nexus.contracts.gen.wire.hud import Hud
from nexus.contracts.gen.wire.snapshot import Snapshot
from nexus.contracts.gen.wire.views import EntityPatch
from nexus.contracts.gen.wire.welcome import Welcome

V = "0.65"
CAMPAIGN = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
POS = {"x_m": 10, "y_m": -4}
ENTITY: dict[str, Any] = {
    "entity_id": 3,
    "unit_kind": "STRIKE_FIGHTER",
    "side": "COALITION",
    "domain": "AIR",
    "owner_kind": "COMMANDER",
    "callsign": "VIPER-01",
    "pos": POS,
    "heading_deg": 90,
    "speed_mps": 200,
    "hp_pct": 100,
    "damage_state": "HEALTHY",
    "painted": False,
    "spotted": False,
    "package_id": None,
    "follow_entity_id": None,
    "follower_count": 0,
    "cosmetic": {"halo": None, "trail": None},
    "badges": [],
    "probation": False,
    "auto": False,
}
NODE: dict[str, Any] = {
    "node_id": "west-airbase",
    "owner": "COALITION",
    "capture": {"side": None, "progress_pct": 0},
    "stock_pct": 80,
    "starvation": "OK",
    "hp_pct": 100,
    "facilities": [
        {
            "entity_id": 9,
            "kind": "RADAR_SITE",
            "variant": None,
            "pos": POS,
            "ring_m": None,
            "state": "HEALTHY",
            "emitting": True,
            "confirmed_tick": None,
        }
    ],
}
HUD: dict[str, Any] = {
    "type": "Hud",
    "v": V,
    "momentum_pct": 41,
    "momentum_breakdown": {
        "nodes_held_pct": 38,
        "supply_pct": 49,
        "recent_events": [],
        "sectors": [],
    },
    "objective_mode": "TIMED",
    "objective": {"node_id": "east-airbase", "name": "East Airbase", "deadline_tick": 9001},
    "threat_tier": "PATTERN_OF_LIFE",
    "nodes_held": 3,
    "nodes_total": 8,
    "campaign_clock": {
        "elapsed_ticks": 5,
        "limit_ticks": 100,
        "paused": False,
        "pause_reason": None,
    },
    "ticker": [],
    "panels": {
        "campaign_status": {
            "nodes_held": {"coalition": 3, "enemy": 3, "neutral": 2},
            "result": None,
        },
        "tasking_needed": [],
        "top_commanders": [],
    },
    "active_humans": None,
    "operators": None,
}
PAYLOADS: dict[type, dict[str, Any]] = {
    Welcome: {
        "type": "Welcome",
        "v": V,
        "server_build": "abc123",
        "campaign_id": CAMPAIGN,
        "tick_rate_hz": 10,
        "theater": {
            "nodes": [
                {"node_id": "west-airbase", "name": "West Airbase", "kind": "AIRBASE", "pos": POS}
            ],
            "edges": [{"a": "a", "b": "b", "layer": "ROAD", "bridge": None}],
            "terrain_ref": None,
        },
    },
    Snapshot: {
        "type": "Snapshot",
        "v": V,
        "tick": 5,
        "entities": [ENTITY],
        "nodes": [NODE],
        "blobs": [{"blob_id": "10-4", "cell_center": POS, "size": "M"}],
        "last_known": [
            {
                "entity_id": 7,
                "unit_kind": "ENEMY_ARMOR",
                "pos": POS,
                "heading_deg": 0,
                "seen_tick": 3,
            }
        ],
        "hud": HUD,
    },
    Delta: {
        "type": "Delta",
        "v": V,
        "tick": 6,
        "base_tick": 5,
        "upserts": [{"entity_id": 3, "pos": POS}],
        "removes": [7],
        "node_patches": [{"node_id": "west-airbase", "stock_pct": 79}],
        "blobs": None,
        "last_known": None,
        "events": [],
    },
    Hud: HUD,
    Control: {"type": "Control", "v": V, "action": "RESYNC"},
    Ack: {"type": "Ack", "v": V, "applied_tick": 6},
}


@pytest.mark.parametrize("model", PAYLOADS, ids=lambda m: m.__name__)
def test_good_payload_validates_and_round_trips(model: Any) -> None:
    payload = PAYLOADS[model]
    assert model.model_validate(payload).model_dump(mode="json", exclude_unset=True) == payload


@pytest.mark.parametrize("model", PAYLOADS, ids=lambda m: m.__name__)
def test_an_unknown_field_is_rejected_when_produced(model: Any) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({**PAYLOADS[model], "display_name": "x"})


def test_control_carries_only_reload_and_resync() -> None:
    for action in ("BANNER", "KILL_SWITCH"):
        with pytest.raises(ValidationError):
            Control.model_validate({"type": "Control", "v": V, "action": action})
    assert Control.model_validate({**PAYLOADS[Control], "action": "RELOAD"}).action == "RELOAD"


@pytest.mark.parametrize("missing", ["nodes_held", "nodes_total"])
def test_hud_requires_the_node_counts(missing: str) -> None:
    with pytest.raises(ValidationError):
        Hud.model_validate({k: v for k, v in HUD.items() if k != missing})


def test_hud_limit_ticks_is_required_but_nullable() -> None:
    clock = {k: v for k, v in HUD["campaign_clock"].items() if k != "limit_ticks"}
    with pytest.raises(ValidationError):
        Hud.model_validate({**HUD, "campaign_clock": clock})
    unlimited = Hud.model_validate({**HUD, "campaign_clock": {**clock, "limit_ticks": None}})
    assert unlimited.campaign_clock.limit_ticks is None
    with pytest.raises(ValidationError):
        Hud.model_validate({**HUD, "campaign_clock": {**clock, "limit_ticks": 0}})


def test_entity_patch_takes_a_partial_field_set_but_needs_the_id() -> None:
    patch = EntityPatch.model_validate({"entity_id": 3, "hp_pct": 40, "callsign": None})
    assert patch.model_fields_set == {"entity_id", "hp_pct", "callsign"}
    with pytest.raises(ValidationError):
        EntityPatch.model_validate({"hp_pct": 40})
    with pytest.raises(ValidationError):
        EntityPatch.model_validate({"entity_id": 3, "hp_pct": 101})
