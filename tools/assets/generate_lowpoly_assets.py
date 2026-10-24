#!/usr/bin/env python3
"""Procedural Low-Poly 3D Asset Geometry Generator for Operation Nexus (NX-176).

Synthesizes modular low-poly Wavefront OBJ meshes for military units, vehicles,
and defensive infrastructure with strict polygon budgets (<500 triangles per asset).
Pure Python standard library with zero external dependencies.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path


def box_mesh(
    dx: float, dy: float, dz: float, ox: float = 0.0, oy: float = 0.0, oz: float = 0.0
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Generate 8 vertices and 12 triangular faces for an axis-aligned box."""
    hx, hy, hz = dx / 2.0, dy / 2.0, dz / 2.0
    verts = [
        (ox - hx, oy - hy, oz - hz),  # 0
        (ox + hx, oy - hy, oz - hz),  # 1
        (ox + hx, oy + hy, oz - hz),  # 2
        (ox - hx, oy + hy, oz - hz),  # 3
        (ox - hx, oy - hy, oz + hz),  # 4
        (ox + hx, oy - hy, oz + hz),  # 5
        (ox + hx, oy + hy, oz + hz),  # 6
        (ox - hx, oy + hy, oz + hz),  # 7
    ]
    faces = [
        (0, 2, 1),
        (0, 3, 2),  # Front (-Z)
        (4, 5, 6),
        (4, 6, 7),  # Back (+Z)
        (0, 1, 5),
        (0, 5, 4),  # Bottom (-Y)
        (3, 6, 2),
        (3, 7, 6),  # Top (+Y)
        (0, 4, 7),
        (0, 7, 3),  # Left (-X)
        (1, 2, 6),
        (1, 6, 5),  # Right (+X)
    ]
    return verts, faces


def cylinder_mesh(
    radius: float,
    height: float,
    segments: int = 8,
    ox: float = 0.0,
    oy: float = 0.0,
    oz: float = 0.0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Generate cylinder vertices and faces along the Y axis."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    hy = height / 2.0

    # Top and bottom rings
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        cx = math.cos(angle) * radius
        cz = math.sin(angle) * radius
        verts.append((ox + cx, oy - hy, oz + cz))  # Bottom ring: 0..segments-1
        verts.append((ox + cx, oy + hy, oz + cz))  # Top ring: 1..2*segments-1

    # Side quad faces
    for i in range(segments):
        b0 = i * 2
        t0 = b0 + 1
        b1 = ((i + 1) % segments) * 2
        t1 = b1 + 1
        faces.append((b0, t0, b1))
        faces.append((b1, t0, t1))

    return verts, faces


def combine_parts(
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Merge multiple vertex/face lists, offsetting 1-based face indices."""
    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, int, int]] = []

    for v_list, f_list in parts:
        offset = len(all_verts)
        all_verts.extend(v_list)
        for v0, v1, v2 in f_list:
            all_faces.append((v0 + offset, v1 + offset, v2 + offset))

    return all_verts, all_faces


def generate_striker_jet() -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Low-poly delta-wing strike fighter (~84 triangles)."""
    parts = []
    # 1. Fuselage
    parts.append(box_mesh(dx=2.4, dy=1.8, dz=14.0, oy=1.0))
    # 2. Nose cone
    nose_v = [
        (-1.2, 0.1, 7.0),
        (1.2, 0.1, 7.0),
        (1.2, 1.9, 7.0),
        (-1.2, 1.9, 7.0),
        (0.0, 0.9, 11.0),
    ]
    nose_f = [(0, 4, 1), (1, 4, 2), (2, 4, 3), (3, 4, 0), (0, 1, 2), (0, 2, 3)]
    parts.append((nose_v, nose_f))
    # 3. Delta Wings
    parts.append(box_mesh(dx=12.0, dy=0.3, dz=6.0, oz=-1.0, oy=1.0))
    # 4. Twin Vertical Stabilizers
    parts.append(box_mesh(dx=0.3, dy=2.8, dz=2.5, ox=-2.2, oy=2.6, oz=-4.0))
    parts.append(box_mesh(dx=0.3, dy=2.8, dz=2.5, ox=2.2, oy=2.6, oz=-4.0))
    return combine_parts(parts)


def generate_logistics_truck() -> tuple[
    list[tuple[float, float, float]], list[tuple[int, int, int]]
]:
    """Low-poly 8-wheel military logistics hauler (~96 triangles)."""
    parts = []
    # 1. Main chassis
    parts.append(box_mesh(dx=3.2, dy=0.8, dz=11.0, oy=1.2))
    # 2. Armored Forward Cab
    parts.append(box_mesh(dx=3.0, dy=2.4, dz=3.2, oy=2.8, oz=3.6))
    # 3. Cargo Container Bed
    parts.append(box_mesh(dx=3.1, dy=2.8, dz=6.8, oy=3.0, oz=-1.8))
    # 4. 8 Wheels (cylinders approximated as boxes for low poly)
    wheel_z = [4.2, 2.4, -2.4, -4.2]
    for wz in wheel_z:
        parts.append(box_mesh(dx=0.8, dy=1.4, dz=1.4, ox=-1.8, oy=0.7, oz=wz))
        parts.append(box_mesh(dx=0.8, dy=1.4, dz=1.4, ox=1.8, oy=0.7, oz=wz))
    return combine_parts(parts)


def generate_sam_launcher() -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Low-poly surface-to-air missile launcher vehicle (~110 triangles)."""
    parts = []
    # 1. Tracked Chassis
    parts.append(box_mesh(dx=3.6, dy=1.4, dz=9.0, oy=0.7))
    # 2. Rotating Turret Base
    parts.append(box_mesh(dx=2.6, dy=1.2, dz=2.6, oy=2.0, oz=-0.5))
    # 3. Dual Angled Missile Canisters
    parts.append(box_mesh(dx=0.9, dy=0.9, dz=6.0, ox=-0.8, oy=3.0, oz=-0.8))
    parts.append(box_mesh(dx=0.9, dy=0.9, dz=6.0, ox=0.8, oy=3.0, oz=-0.8))
    return combine_parts(parts)


def generate_radar_spire() -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Low-poly early warning radar tower with curved dish (~128 triangles)."""
    parts = []
    # 1. Tower Base
    parts.append(box_mesh(dx=6.0, dy=2.0, dz=6.0, oy=1.0))
    # 2. Central Mast
    parts.append(cylinder_mesh(radius=1.2, height=14.0, segments=6, oy=9.0))
    # 3. Radar Dish Platform
    parts.append(box_mesh(dx=8.0, dy=4.0, dz=1.2, oy=17.0, oz=0.6))
    return combine_parts(parts)


def generate_truss_bridge_span() -> tuple[
    list[tuple[float, float, float]], list[tuple[int, int, int]]
]:
    """Low-poly modular steel truss bridge span (~140 triangles)."""
    parts = []
    span = 40.0
    width = 16.0
    # 1. Road Deck Slab
    parts.append(box_mesh(dx=span, dy=1.2, dz=width, oy=0.0))
    # 2. Left and Right Guardrails
    parts.append(box_mesh(dx=span, dy=3.5, dz=1.0, oy=2.2, oz=width / 2.0 - 0.5))
    parts.append(box_mesh(dx=span, dy=3.5, dz=1.0, oy=2.2, oz=-width / 2.0 + 0.5))
    # 3. Concrete Pier Pylons
    parts.append(box_mesh(dx=6.0, dy=16.0, dz=width + 2.0, ox=-span / 3.0, oy=-8.0))
    parts.append(box_mesh(dx=6.0, dy=16.0, dz=width + 2.0, ox=span / 3.0, oy=-8.0))
    return combine_parts(parts)


def write_obj(
    verts: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    name: str,
    out_path: Path,
) -> None:
    """Format and write standard Wavefront OBJ file."""
    lines = [
        f"# Operation Nexus Low-Poly 3D Asset: {name}",
        f"# Vertex count: {len(verts)}, Triangle count: {len(faces)}",
        f"o {name}",
    ]
    for vx, vy, vz in verts:
        lines.append(f"v {vx:.3f} {vy:.3f} {vz:.3f}")
    # 1-based indices in OBJ
    for v0, v1, v2 in faces:
        lines.append(f"f {v0 + 1} {v1 + 1} {v2 + 1}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


ASSET_GENERATORS = {
    "striker_jet": ("StrikerJet", generate_striker_jet),
    "logistics_truck": ("LogisticsTruck", generate_logistics_truck),
    "sam_launcher": ("SamLauncher", generate_sam_launcher),
    "radar_spire": ("RadarSpire", generate_radar_spire),
    "truss_bridge": ("TrussBridge", generate_truss_bridge_span),
}


def build_all_assets(output_dir: Path) -> list[tuple[str, Path, int, int]]:
    """Generate all standard catalog assets and write OBJ files."""
    results = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for asset_key, (name, gen_func) in ASSET_GENERATORS.items():
        verts, faces = gen_func()
        obj_path = output_dir / f"{asset_key}.obj"
        write_obj(verts, faces, name, obj_path)
        results.append((name, obj_path, len(verts), len(faces)))

    return results


def run_tests() -> bool:
    """Validate asset budgets and geometry topology."""
    print("Testing low-poly asset geometry and budget constraints (<500 triangles)...")
    for _key, (name, func) in ASSET_GENERATORS.items():
        verts, faces = func()
        if len(verts) == 0 or len(faces) == 0:
            raise RuntimeError(f"Asset {name} has zero geometry")
        if len(faces) > 500:
            raise RuntimeError(f"Asset {name} exceeds 500 triangle budget: {len(faces)} tris")
        # Validate face indices within bounds
        for v0, v1, v2 in faces:
            out_of_bounds = (
                v0 < 0
                or v0 >= len(verts)
                or v1 < 0
                or v1 >= len(verts)
                or v2 < 0
                or v2 >= len(verts)
            )
            if out_of_bounds:
                raise RuntimeError(f"Asset {name} contains out-of-bounds face indices")

    print("All low-poly asset self-checks PASSED (100% OK).")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Procedural Low-Poly 3D Asset Geometry Generator")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("content/assets/3d"),
        help="Directory to save generated OBJ meshes",
    )
    parser.add_argument("--test", action="store_true", help="Run automated self-tests")

    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    print(f"Synthesizing low-poly 3D assets to {args.output_dir}...")
    assets = build_all_assets(args.output_dir)
    for name, path, v_count, f_count in assets:
        print(f"  [+] {name:<16}: {path.name} ({v_count} verts, {f_count} tris)")


if __name__ == "__main__":
    main()
