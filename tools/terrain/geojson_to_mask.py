#!/usr/bin/env python3
"""Convert GeoJSON terrain and biome vector layers to spatial masking grids.

Provides deterministic conversion from authored GeoJSON vector polygons
(biomes, masking regions, water bodies) into simulation spatial grid cells
and optional raster preview maps, preserving the decoupled architecture.

Usage:
    python3 tools/terrain/geojson_to_mask.py --input content/theaters/strait-1-biomes.geojson
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("geojson_to_mask")

# Standard Biome Taxonomy (0x00 to 0x07)
BIOMES = {
    "OCEAN_DEEP": {"code": 0, "name": "Deep Ocean", "speed_mult": 0.0, "masking": False},
    "WATER_INLAND": {"code": 1, "name": "Inland Water", "speed_mult": 0.0, "masking": False},
    "BEACH_SHORE": {"code": 2, "name": "Beach / Shoreline", "speed_mult": 0.6, "masking": False},
    "PLAINS_LOWLAND": {"code": 3, "name": "Plains Lowland", "speed_mult": 1.0, "masking": False},
    "FOREST_WOODLAND": {"code": 4, "name": "Forest Woodland", "speed_mult": 0.7, "masking": True},
    "DESERT_ARID": {"code": 5, "name": "Desert Arid", "speed_mult": 0.85, "masking": False},
    "HIGHLANDS_ROCK": {"code": 6, "name": "Highlands Rock", "speed_mult": 0.0, "masking": True},
    "URBAN_METRO": {"code": 7, "name": "Urban Metro", "speed_mult": 0.9, "masking": True},
}


def point_in_polygon(px: float, py: float, poly: list[list[float]]) -> bool:
    """Ray-casting point in polygon test."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1 + 1e-12) + x1):
            inside = not inside
    return inside


def parse_geojson_features(path: Path) -> list[dict[str, Any]]:
    """Load and validate GeoJSON polygon features."""
    if not path.exists():
        logger.warning("Input file %s does not exist; generating sample schema.", path)
        return []

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    features = []
    for feat in data.get("features", []):
        geom = feat.get("geometry", {})
        props = feat.get("properties", {})
        biome_kind = props.get("kind", "PLAINS_LOWLAND")
        if biome_kind not in BIOMES:
            logger.warning("Unknown biome kind '%s', defaulting to PLAINS_LOWLAND", biome_kind)
            biome_kind = "PLAINS_LOWLAND"

        coords = geom.get("coordinates", [])
        if geom.get("type") == "Polygon" and coords:
            features.append(
                {
                    "kind": biome_kind,
                    "code": BIOMES[biome_kind]["code"],
                    "polygon": coords[0],
                    "properties": props,
                }
            )
    return features


def rasterize_grid(
    features: list[dict[str, Any]],
    bounds_m: tuple[float, float, float, float],
    cell_size_m: float = 1000.0,
) -> dict[str, Any]:
    """Bake vector features into simulation spatial cells."""
    min_x, min_y, max_x, max_y = bounds_m
    cols = math.ceil((max_x - min_x) / cell_size_m)
    rows = math.ceil((max_y - min_y) / cell_size_m)

    logger.info("Rasterizing %d x %d spatial grid (cell: %dm)", cols, rows, cell_size_m)
    grid_cells: dict[str, int] = {}

    for r in range(rows):
        cy = min_y + (r + 0.5) * cell_size_m
        for c in range(cols):
            cx = min_x + (c + 0.5) * cell_size_m
            biome_code = BIOMES["PLAINS_LOWLAND"]["code"]
            for feat in features:
                if point_in_polygon(cx, cy, feat["polygon"]):
                    biome_code = feat["code"]
                    break
            if biome_code != BIOMES["PLAINS_LOWLAND"]["code"]:
                grid_cells[f"{c}:{r}"] = biome_code

    return {
        "bounds_m": list(bounds_m),
        "cell_size_m": cell_size_m,
        "cols": cols,
        "rows": rows,
        "overrides": grid_cells,
        "biomes": BIOMES,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert GeoJSON biomes to spatial grid cache.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("content/theaters/strait-1-biomes.geojson"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("content/theaters/strait-1-grid.json"),
    )
    parser.add_argument("--cell-size", type=float, default=1000.0, help="Grid cell size in meters")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    features = parse_geojson_features(args.input)

    # Theater bounds: 400km x 240km centered
    bounds = (-200000.0, -120000.0, 200000.0, 120000.0)
    grid = rasterize_grid(features, bounds, args.cell_size)

    if not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(grid, fh, indent=2)
        logger.info(
            "Saved grid cache with %d modified cells to %s",
            len(grid["overrides"]),
            args.output,
        )


if __name__ == "__main__":
    main()
