"""Exact point-in-polygon, shared by the kernel (sectors, `nexus.core.rules`) and the theater loader
(`nexus.runtime.theater`): one implementation, so their edge behaviour cannot differ (NX-155).

Vertices are integer metres. A point may be an int or a float: a float is converted to its exact
`Fraction` first, so every comparison below is exact (no rounding, nothing to differ by platform).
"""

from collections.abc import Sequence
from fractions import Fraction

type Vertex = tuple[int, int]


def in_polygon(x: float, y: float, poly: Sequence[Vertex]) -> bool:
    """Even-odd rule; a point on an edge or a vertex counts as inside."""
    px = Fraction(x) if isinstance(x, float) else x
    py = Fraction(y) if isinstance(y, float) else y
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, (*poly[1:], poly[0]), strict=True):
        cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        if cross == 0 and min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2):
            return True
        if (y1 > py) != (y2 > py) and (cross > 0) == (y2 > y1):
            inside = not inside
    return inside
