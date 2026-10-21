"""Uniform spatial grid for radius queries (SIM-CORE SC-10, SC-4; NX-104).

Callers pick `cell_m` (SC-10); sensing (`nexus.core.fog`) builds one grid per sensor range class,
cell = the class's largest radius / 2 (NX-372).

The grid is derived data: references to the entities and their positions taken at `rebuild`. It is
not part of `World` state, the snapshot or `state_hash`. Queries filter on the positions taken at
`rebuild`, so once entities move, discard the grid (or `rebuild` it); never keep one across ticks.
"""

import math
from collections.abc import Iterable

from nexus.core.world import Entity, Vec2

# Widens the scanned cell range so float rounding in `center +- radius` can never drop a point
# the exact distance test accepts. Vec2 bounds coordinates to 1e9 m, where one ulp is ~1.2e-7 m.
_PAD_M = 1e-3

type _Cell = tuple[int, int]
type _Point = tuple[Entity, float, float]  # (entity, x, y) at rebuild


class UniformGrid:
    """Entities bucketed by `(floor(x / cell_m), floor(y / cell_m))`; unbounded, keyed by cell."""

    __slots__ = ("_cell_m", "_cells")

    def __init__(self, cell_m: float) -> None:
        if isinstance(cell_m, bool) or not (
            isinstance(cell_m, int | float) and math.isfinite(cell_m) and cell_m > 0
        ):
            raise ValueError(f"cell_m must be finite and > 0, got {cell_m!r}")
        self._cell_m = float(cell_m)
        self._cells: dict[_Cell, list[_Point]] = {}

    def _key(self, x: float, y: float) -> _Cell:
        return math.floor(x / self._cell_m), math.floor(y / self._cell_m)

    def rebuild(self, entities: Iterable[Entity]) -> None:
        """Clear and re-bucket every entity at its current position. Call once per tick after
        movement. Full rebuild is the simplest correct approach; incremental update is a later
        optimisation only if the NX-104 benchmark shows it is needed."""
        cells: dict[_Cell, list[_Point]] = {}
        for e in entities:
            x, y = e.pos.x, e.pos.y
            cells.setdefault(self._key(x, y), []).append((e, x, y))
        self._cells = cells

    def remove(self, entity: Entity) -> None:
        """Drop `entity` from the grid. It must be in the grid and must not have moved since
        `rebuild` (its cell is found from its current position); otherwise this raises KeyError
        or leaves it in place. Removing one entity costs one pass over its cell."""
        key = self._key(entity.pos.x, entity.pos.y)
        bucket = self._cells[key]
        bucket[:] = [p for p in bucket if p[0] is not entity]
        if not bucket:
            del self._cells[key]

    def query_radius(self, center: Vec2, radius_m: float) -> list[int]:
        """Ids within `radius_m` of `center` (inclusive, Euclidean), ascending by id (SC-4)."""
        ids = [e.id for e in self.within(center, radius_m)]
        ids.sort()
        return ids

    def within(self, center: Vec2, radius_m: float) -> list[Entity]:
        """The entities `query_radius` finds, in bucket order, not id order: only for callers that
        reduce them to a set (the order is deterministic, but not SC-4's)."""
        if not (math.isfinite(radius_m) and radius_m >= 0):
            raise ValueError(f"radius_m must be finite and >= 0, got {radius_m!r}")
        cx, cy, r2 = center.x, center.y, radius_m * radius_m
        x0, y0 = self._key(cx - radius_m - _PAD_M, cy - radius_m - _PAD_M)
        x1, y1 = self._key(cx + radius_m + _PAD_M, cy + radius_m + _PAD_M)
        if (x1 - x0 + 1) * (y1 - y0 + 1) > len(self._cells):
            # A huge radius: scanning the occupied cells is cheaper than the empty range.
            buckets = list(self._cells.values())
        else:
            buckets = [
                b
                for kx in range(x0, x1 + 1)
                for ky in range(y0, y1 + 1)
                if (b := self._cells.get((kx, ky))) is not None
            ]
        return [
            e for b in buckets for e, x, y in b if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r2
        ]
