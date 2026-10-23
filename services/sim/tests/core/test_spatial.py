"""Uniform grid tests (NX-104, SIM-CORE SC-4, SC-10)."""

import math
import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexus.core.spatial import UniformGrid
from nexus.core.world import Campaign, Entity, Vec2, World

KM = 1000.0
# Whole-km values land exactly on the borders of the whole-km cells below, and on exact radii.
coord = st.one_of(st.floats(-250 * KM, 250 * KM), st.integers(-250, 250).map(lambda k: k * KM))
cell = st.one_of(st.sampled_from([1 * KM, 5 * KM, 20 * KM, 60 * KM]), st.floats(1.0, 100 * KM))
radius = st.one_of(st.floats(0.0, 600 * KM), st.integers(0, 600).map(lambda k: k * KM))
points = st.lists(st.tuples(coord, coord), max_size=60)


def world_with(xy: list[tuple[float, float]]) -> World:
    w = World.new(Campaign("c", 1, "cfg"))
    for x, y in xy:
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(x, y), hp=1)
    return w


def brute(entities: list[Entity], c: Vec2, r: float) -> list[int]:
    return sorted(e.id for e in entities if (e.pos.x - c.x) ** 2 + (e.pos.y - c.y) ** 2 <= r * r)


@given(points, cell, coord, coord, radius)
def test_query_matches_brute_force(
    xy: list[tuple[float, float]], cell_m: float, cx: float, cy: float, r: float
) -> None:
    entities = list(world_with(xy).entities())
    grid = UniformGrid(cell_m)
    grid.rebuild(entities)
    assert grid.query_radius(Vec2(cx, cy), r) == brute(entities, Vec2(cx, cy), r)


@given(points, cell, coord, coord, radius, st.data())
def test_within_and_remove_match_brute_force_over_the_rest(
    xy: list[tuple[float, float]],
    cell_m: float,
    cx: float,
    cy: float,
    r: float,
    data: st.DataObject,
) -> None:
    """NX-372: `within` finds the same entities as `query_radius`; removed ones are gone."""
    entities = list(world_with(xy).entities())
    gone = data.draw(
        st.sets(st.sampled_from([e.id for e in entities])) if entities else st.just(set())
    )
    grid = UniformGrid(cell_m)
    grid.rebuild(entities)
    for i in sorted(gone):
        grid.remove(entities[i - 1])
    rest = [e for e in entities if e.id not in gone]
    assert sorted(e.id for e in grid.within(Vec2(cx, cy), r)) == brute(rest, Vec2(cx, cy), r)
    assert grid.query_radius(Vec2(cx, cy), r) == brute(rest, Vec2(cx, cy), r)


def test_worked_example_inclusive_radius_borders_and_negatives() -> None:
    # 3-4-5 triangles: (3 km, 4 km) and (-3 km, -4 km) are exactly 5 km from the origin.
    w = world_with([(3 * KM, 4 * KM), (-3 * KM, -4 * KM), (5 * KM, 0.1), (0.0, 0.0), (-5 * KM, 0)])
    grid = UniformGrid(1 * KM)  # every whole-km point sits on a cell corner
    grid.rebuild(w.entities())
    assert grid.query_radius(Vec2(0, 0), 5 * KM) == [1, 2, 4, 5]
    assert grid.query_radius(Vec2(0, 0), 0) == [4]
    assert grid.query_radius(Vec2(-5 * KM, 0), 0) == [5]


@given(points, st.randoms(use_true_random=False))
def test_order_ascending_and_independent_of_input_order(
    xy: list[tuple[float, float]], rnd: random.Random
) -> None:
    entities = list(world_with(xy).entities())
    shuffled = entities[::-1]
    rnd.shuffle(shuffled)
    a, b = UniformGrid(20 * KM), UniformGrid(20 * KM)
    a.rebuild(entities)
    b.rebuild(shuffled)
    for c in (Vec2(0, 0), Vec2(-100 * KM, 50 * KM)):
        got = a.query_radius(c, 150 * KM)
        assert got == sorted(got)
        assert got == b.query_radius(c, 150 * KM)


def test_rebuild_replaces_previous_contents() -> None:
    w = world_with([(0.0, 0.0)])
    grid = UniformGrid(KM)
    grid.rebuild(w.entities())
    w.get(1).pos = Vec2(100 * KM, 0)
    grid.rebuild(w.entities())
    assert grid.query_radius(Vec2(0, 0), KM) == []
    assert grid.query_radius(Vec2(100 * KM, 0), 0) == [1]


@pytest.mark.parametrize("bad", [0.0, -1.0, math.inf, math.nan])
def test_invalid_cell_size_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="cell_m"):
        UniformGrid(bad)


@pytest.mark.parametrize("bad", [-1.0, math.inf, math.nan])
def test_invalid_radius_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="radius_m"):
        UniformGrid(KM).query_radius(Vec2(0, 0), bad)


def test_smoke_benchmark_1000_entities() -> None:
    # CI smoke only (SIM-CORE SC-10 test plan): asserts completion and correctness, never a timing.
    # 40 km query radius and 20 km cells are STAND-INS until the unit catalog (NX-106).
    w = World.new(Campaign("c", 104, "cfg"))
    for i in range(1000):  # a deterministic spread over the 400 x 240 km theater
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(i * 397 % 400_000, i * 241), hp=1)
    grid, r = UniformGrid(20 * KM), 40 * KM
    for tick in range(20):
        for e in w.entities():
            e.pos = Vec2((e.pos.x + 150.0) % 400_000, (e.pos.y + 15.0 * (tick % 3)) % 240_000)
        grid.rebuild(w.entities())
        results = [grid.query_radius(e.pos, r) for e in w.entities()]
        entities = list(w.entities())
        for e in entities[tick::97]:
            assert results[e.id - 1] == brute(entities, e.pos, r)


def test_bounding_box_prune_keeps_borders_and_empty_grids() -> None:
    grid = UniformGrid(KM)
    assert grid.within(Vec2(0, 0), 10 * KM) == []  # never rebuilt
    grid.rebuild([])
    assert grid.within(Vec2(0, 0), 10 * KM) == []  # rebuilt empty
    w = world_with([(10 * KM, 10 * KM), (20 * KM, 10 * KM)])
    grid.rebuild(w.entities())
    # Exactly 3 km west of the box edge (x 10 km): a 3 km reach touches it, 3 km less one metre not.
    assert grid.query_radius(Vec2(7 * KM, 10 * KM), 3 * KM) == [1]
    assert grid.query_radius(Vec2(7 * KM, 10 * KM), 3 * KM - 1) == []
    # Diagonal off the box corner (10 km, 10 km): a 3-4-5 triangle.
    assert grid.query_radius(Vec2(7 * KM, 6 * KM), 5 * KM) == [1]
    assert grid.query_radius(Vec2(7 * KM, 6 * KM), 5 * KM - 1) == []
    assert grid.query_radius(Vec2(15 * KM, 10 * KM), 5 * KM) == [1, 2]  # inside the box
