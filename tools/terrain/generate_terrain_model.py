#!/usr/bin/env python3
"""Procedural 3D Terrain Model Generator for Hiveplex Theater 1 (Strait-1).

Generates a deterministic Wavefront OBJ 3D terrain mesh with multi-octave elevation,
recessed submarine trench, mountain ridge lines, graded roadbeds, and bridge alignments.

Usage:
    python3 tools/terrain/generate_terrain_model.py --output content/theaters/strait-1-terrain.obj
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_terrain_model")


def dist_to_road_segments(
    px: float, pz: float, segments: list[tuple[tuple[float, float], tuple[float, float]]]
) -> float:
    """Calculate shortest 2D distance from (px, pz) to any road centerline segment."""
    min_d = 9999.0
    for (x1, z1), (x2, z2) in segments:
        seg_dx = x2 - x1
        seg_dz = z2 - z1
        l2 = seg_dx * seg_dx + seg_dz * seg_dz
        if l2 == 0:
            d = math.hypot(px - x1, pz - z1)
        else:
            t = max(0.0, min(1.0, ((px - x1) * seg_dx + (pz - z1) * seg_dz) / l2))
            proj_x = x1 + t * seg_dx
            proj_z = z1 + t * seg_dz
            d = math.hypot(px - proj_x, pz - proj_z)
        if d < min_d:
            min_d = d
    return min_d


def generate_terrain(
    output_obj_path: Path,
    nx: int = 80,
    nz: int = 48,
    width_m: float = 400.0,
    depth_m: float = 240.0,
) -> None:
    """Synthesize 3D vertex and face data for Strait-1 theater."""
    dx = width_m / nx
    dz = depth_m / nz

    vertices: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    faces: list[tuple[int, int, int]] = []

    # Road Network Segments matching content/theaters/strait-1.yaml
    road_segments: list[tuple[tuple[float, float], tuple[float, float]]] = [
        ((-180.0, 0.0), (-150.0, 0.0)),
        ((-150.0, 0.0), (-70.0, -55.0)),
        ((-150.0, 0.0), (-70.0, 55.0)),
        ((-70.0, -55.0), (-18.0, -55.0)),
        ((-70.0, 55.0), (-18.0, 55.0)),
        ((18.0, -55.0), (30.0, -55.0)),
        ((18.0, 55.0), (30.0, 55.0)),
        ((30.0, -55.0), (90.0, -75.0)),
        ((30.0, 55.0), (90.0, 75.0)),
        ((30.0, -55.0), (110.0, 0.0)),
        ((30.0, 55.0), (110.0, 0.0)),
        ((90.0, -75.0), (180.0, 0.0)),
        ((90.0, 75.0), (180.0, 0.0)),
        ((110.0, 0.0), (180.0, 0.0)),
    ]

    logger.info("Generating %d x %d vertex grid (span: %.0fm x %.0fm)", nx, nz, width_m, depth_m)

    # 1. Synthesize Vertices
    for j in range(nz + 1):
        z = -depth_m / 2.0 + j * dz
        for i in range(nx + 1):
            x = -width_m / 2.0 + i * dx

            strait_dist = abs(x)
            if strait_dist < 18.0:
                # Recessed Submarine Trench
                y = -4.0 + math.sin(z * 0.08) * 0.5
            elif strait_dist < 24.0:
                # Shoreline Bevel
                t = (strait_dist - 18.0) / 6.0
                y = -4.0 + t * 4.2
            else:
                # Landmass multi-octave harmonic noise
                macro_noise = math.sin(x * 0.02) * math.cos(z * 0.03) * 5.0
                micro_noise = math.sin(x * 0.07 + 1.2) * math.cos(z * 0.08 + 0.8) * 2.5

                # Northern Mountain Ridge (Radar LoS barrier)
                north_mountain = 0.0
                if z < -20.0:
                    ridge_dist = abs(z - (-70.0))
                    peak_profile = max(0.0, 22.0 - ridge_dist * 0.4)
                    north_mountain = peak_profile * (0.8 + 0.3 * math.sin(x * 0.04))

                # Southern Valley Corridor
                south_valley = 0.0
                if z > 30.0 and x > 20.0:
                    south_valley = math.sin(x * 0.05) * 4.0

                base_elev = max(0.2, macro_noise + micro_noise + north_mountain + south_valley)

                # Road grading: flatten terrain along road corridors
                r_dist = dist_to_road_segments(x, z, road_segments)
                if r_dist < 4.0:
                    base_elev = 0.25  # perfectly leveled roadbed
                elif r_dist < 8.0:
                    blend = (r_dist - 4.0) / 4.0
                    base_elev = 0.25 * (1.0 - blend) + base_elev * blend

                y = base_elev

            vertices.append((x, y, z))
            uvs.append((i / nx, j / nz))

    # 2. Synthesize Polygonal Faces (Two Triangles per Quad)
    for j in range(nz):
        for i in range(nx):
            v1 = j * (nx + 1) + i + 1
            v2 = j * (nx + 1) + (i + 1) + 1
            v3 = (j + 1) * (nx + 1) + (i + 1) + 1
            v4 = (j + 1) * (nx + 1) + i + 1

            faces.append((v1, v2, v3))
            faces.append((v1, v3, v4))

    # 3. Output Wavefront OBJ File
    output_obj_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_obj_path, "w", encoding="utf-8") as fh:
        fh.write("# Hiveplex Strait-1 3D Procedural Terrain Model\n")
        fh.write(f"# Vertices: {len(vertices)}, Faces: {len(faces)}\n\n")

        for x, y, z in vertices:
            fh.write(f"v {x:.3f} {y:.3f} {z:.3f}\n")

        for u, v in uvs:
            fh.write(f"vt {u:.4f} {v:.4f}\n")

        for v1, v2, v3 in faces:
            fh.write(f"f {v1}/{v1} {v2}/{v2} {v3}/{v3}\n")

    logger.info(
        "Saved 3D Terrain Model to %s (%d vertices, %d faces)",
        output_obj_path,
        len(vertices),
        len(faces),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Procedural 3D Terrain Model Generator.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("content/theaters/strait-1-terrain.obj"),
        help="Target .obj file output path",
    )
    parser.add_argument("--nx", type=int, default=80, help="Horizontal grid resolution")
    parser.add_argument("--nz", type=int, default=48, help="Depth grid resolution")
    args = parser.parse_args()

    generate_terrain(args.output, nx=args.nx, nz=args.nz)


if __name__ == "__main__":
    main()
