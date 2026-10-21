"""Uniform spatial grid for radius queries (SIM-CORE SC-10, SC-4; NX-104).

Callers pass `cell_m` = max sensor radius / 2 (SC-10). The sensor radius config does not exist yet
(NX-106, unit catalog), so the cell size is a constructor argument.

The grid is derived data: a snapshot of entity ids and positions taken at `rebuild`. It is not
part of `World` state, the snapshot or `state_hash`, and is rebuilt from the world after movement.
"""

import math
from collections.abc import Iterable

from nexus.core.world import Entity, Vec2

# Widens the scanned cell range so float rounding in `center +- radius` can never drop a point
# the exact distance test accepts. Vec2 bounds coordinates to 1e9 m, where one ulp is ~1.2e-7 m.
_PAD_M = 1e-3

type _Cell = tuple[int, int]
type _Point = tuple[int, float, float]  # (id, x, y)


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
            cells.setdefault(self._key(x, y), []).append((e.id, x, y))
        self._cells = cells

    def query_radius(self, center: Vec2, radius_m: float) -> list[int]:
        """Ids within `radius_m` of `center` (inclusive, Euclidean), ascending by id (SC-4)."""
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
        ids = [
            i for b in buckets for i, x, y in b if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r2
        ]
        ids.sort()
        return ids
