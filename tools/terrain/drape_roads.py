#!/usr/bin/env python3
"""Dynamic Road Spline Draping & Terrain Conforming for Operation Nexus (NX-176).

Interpolates theater road networks over the continuous DEM surface, eliminating
terrain clipping and mid-air floating. Spans bridge crossings over water channels
with elevated clearances and smooth abutment ramps.

Outputs:
  - 3D Draped Road Geometry JSON (content/theaters/dted/strait-1-roads-3d.json)
  - Wavefront OBJ 3D Road Ribbon Mesh (content/theaters/dted/strait-1-roads.obj)
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

# Ensure tools directory is on sys.path for relative tool imports
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.terrain.bake_synthetic_dted import sample_strait1_elevation  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None  # Fallback to lightweight regex parser if PyYAML is absent

# Vertical elevation budget (metres) to prevent Z-fighting with ground terrain mesh
ROAD_ELEVATION_OFFSET_M = 0.22
BRIDGE_DECK_ELEVATION_M = 14.0
DEFAULT_ROAD_WIDTH_M = 18.0


def sample_road_height(x_m: float, y_m: float, is_bridge: bool) -> float:
    """Compute draped road height at (x_m, y_m) with bridge deck elevation logic."""
    strait_center_x = 200_000.0
    strait_half_width = 20_000.0
    dist_to_center = abs(x_m - strait_center_x)

    if is_bridge and dist_to_center <= strait_half_width:
        # Elevated bridge deck spanning the water channel
        t = dist_to_center / strait_half_width  # 0 at center, 1 at abutments
        ground_elev = sample_strait1_elevation(x_m, y_m)
        bridge_base = BRIDGE_DECK_ELEVATION_M
        # Smooth cosine parabolic crown in center
        crown = math.cos(t * math.pi / 2.0) * 3.0
        deck_target = bridge_base + crown
        # Blend into ground abutments near edges
        if t > 0.8:
            blend = (t - 0.8) / 0.2
            return (1.0 - blend) * deck_target + blend * (ground_elev + ROAD_ELEVATION_OFFSET_M)
        return deck_target

    ground = sample_strait1_elevation(x_m, y_m)
    return ground + ROAD_ELEVATION_OFFSET_M


def drape_edge(
    pos_a: tuple[float, float],
    pos_b: tuple[float, float],
    is_bridge: bool,
    step_m: float = 250.0,
) -> list[tuple[float, float, float]]:
    """Subdivide a straight road edge into dense draped 3D points conforming to terrain."""
    x1, y1 = pos_a
    x2, y2 = pos_b
    total_dist = math.hypot(x2 - x1, y2 - y1)
    if total_dist <= 0:
        return [(x1, sample_road_height(x1, y1, is_bridge), y1)]

    steps = max(2, math.ceil(total_dist / step_m))
    points: list[tuple[float, float, float]] = []

    for s in range(steps + 1):
        t = s / steps
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)
        z_elev = sample_road_height(x, y, is_bridge)
        points.append((x, z_elev, y))

    return points


def parse_theater_roads(
    theater_yaml_path: Path,
) -> tuple[dict[str, tuple[float, float]], list[dict]]:
    """Parse node coordinates and road edges from theater YAML file."""
    with open(theater_yaml_path, encoding="utf-8") as f:
        text = f.read()

    if yaml is not None:
        data = yaml.safe_load(text)
        nodes = {node["id"]: tuple(node["pos"]) for node in data.get("nodes", [])}
        edges = data.get("edges", [])
        return nodes, edges

    # Ponytail fallback: parse simple inline dictionaries via regex if PyYAML absent
    nodes: dict[str, tuple[float, float]] = {}
    edges: list[dict] = []

    node_pattern = re.compile(
        r"id:\s*([a-zA-Z0-9_\-]+).*?pos:\s*\[\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\]"
    )
    for m in node_pattern.finditer(text):
        node_id, x_str, y_str = m.groups()
        nodes[node_id] = (float(x_str), float(y_str))

    edge_pattern = re.compile(r"a:\s*([a-zA-Z0-9_\-]+).*?b:\s*([a-zA-Z0-9_\-]+)")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("-") and "a:" in line and "b:" in line:
            m = edge_pattern.search(line)
            if m:
                a_id, b_id = m.groups()
                edge_dict = {"a": a_id, "b": b_id}
                if "bridge:" in line:
                    edge_dict["bridge"] = True
                edges.append(edge_dict)

    return nodes, edges


def generate_draped_roads(
    theater_yaml_path: Path,
    step_m: float = 250.0,
    road_width_m: float = DEFAULT_ROAD_WIDTH_M,
    scale: float = 1.0,
    centered: bool = False,
) -> tuple[dict, str]:
    """Parse theater YAML and produce 3D road points and Wavefront OBJ mesh content."""
    nodes, edges = parse_theater_roads(theater_yaml_path)

    center_x = 200_000.0 if centered else 0.0
    center_y = 120_000.0 if centered else 0.0

    draped_network: dict[str, list[dict]] = {"edges": []}
    obj_lines: list[str] = [
        "# Operation Nexus Draped Road Ribbon Mesh",
        f"# Source: {theater_yaml_path.name}",
        "o Roads",
    ]

    vert_offset = 1
    total_length_m = 0.0

    for edge in edges:
        id_a = edge["a"]
        id_b = edge["b"]
        if id_a not in nodes or id_b not in nodes:
            continue

        is_bridge = "bridge" in edge
        pts_3d = drape_edge(nodes[id_a], nodes[id_b], is_bridge=is_bridge, step_m=step_m)

        edge_record = {
            "from": id_a,
            "to": id_b,
            "is_bridge": is_bridge,
            "points_count": len(pts_3d),
            "points_xyz": pts_3d,
        }
        draped_network["edges"].append(edge_record)

        # Generate 3D Ribbon Quad strip in OBJ format
        half_w = road_width_m / 2.0
        edge_start_v = vert_offset

        for i, (px, py, pz) in enumerate(pts_3d):
            # Compute tangent direction
            if i < len(pts_3d) - 1:
                nx = pts_3d[i + 1][0] - px
                nz = pts_3d[i + 1][2] - pz
            else:
                nx = px - pts_3d[i - 1][0]
                nz = pz - pts_3d[i - 1][2]

            seg_len = math.hypot(nx, nz)
            if seg_len > 0:
                nx /= seg_len
                nz /= seg_len
            else:
                nx, nz = 1.0, 0.0

            # Normal vector in ground plane (perpendicular to road tangent)
            perp_x = -nz
            perp_z = nx

            # Left and right edge vertices (with optional centering and scaling)
            lx = (px - perp_x * half_w - center_x) * scale
            lz = (pz - perp_z * half_w - center_y) * scale
            ly = py * scale

            rx = (px + perp_x * half_w - center_x) * scale
            rz = (pz + perp_z * half_w - center_y) * scale
            ry = py * scale

            obj_lines.append(f"v {lx:.3f} {ly:.3f} {lz:.3f}")
            obj_lines.append(f"v {rx:.3f} {ry:.3f} {rz:.3f}")
            vert_offset += 2

            if i > 0:
                total_length_m += math.hypot(px - pts_3d[i - 1][0], pz - pts_3d[i - 1][2])

        # Faces for this edge ribbon
        for i in range(len(pts_3d) - 1):
            v0 = edge_start_v + i * 2
            v1 = v0 + 1
            v2 = v0 + 2
            v3 = v0 + 3
            obj_lines.append(f"f {v0} {v2} {v1}")
            obj_lines.append(f"f {v1} {v2} {v3}")

    draped_network["total_length_m"] = total_length_m
    return draped_network, "\n".join(obj_lines)


def run_tests() -> bool:
    """Verify road draping logic and clearance constraints."""
    print("Testing bridge elevation clearance over submarine trench...")
    # North bridge crossing at X=200,000, Y=60,000
    bridge_h = sample_road_height(200_000.0, 60_000.0, is_bridge=True)
    if bridge_h < 12.0:
        raise RuntimeError(f"Bridge deck too low over water: {bridge_h:.2f}m")

    # Non-bridge point in water channel must plunge or reflect trench
    trench_h = sample_road_height(200_000.0, 60_000.0, is_bridge=False)
    if trench_h > 0.0:
        raise RuntimeError(f"Unbridged trench should be submerged, got {trench_h:.2f}m")

    # Land point must include vertical offset to prevent Z-fighting
    land_ground = sample_strait1_elevation(50_000.0, 50_000.0)
    land_road = sample_road_height(50_000.0, 50_000.0, is_bridge=False)
    if not math.isclose(land_road - land_ground, ROAD_ELEVATION_OFFSET_M, abs_tol=1e-3):
        raise RuntimeError("Road elevation offset above terrain not maintained")

    print("All road draping self-checks PASSED (100% OK).")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Dynamic Road Spline Draping & Conforming Engine")
    parser.add_argument(
        "--theater",
        type=Path,
        default=Path("content/theaters/strait-1.yaml"),
        help="Path to theater YAML specification",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("content/theaters/dted"),
        help="Directory to save draped road JSON and OBJ meshes",
    )
    parser.add_argument("--step-m", type=float, default=250.0, help="Sampling step in metres")
    parser.add_argument("--scale", type=float, default=1.0, help="Coordinate scale factor")
    parser.add_argument("--centered", action="store_true", help="Center coordinates around (0, 0)")
    parser.add_argument("--test", action="store_true", help="Run automated self-tests")

    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    print(f"Draping road network from {args.theater} at step={args.step_m}m...")
    network_data, obj_content = generate_draped_roads(
        args.theater,
        step_m=args.step_m,
        scale=args.scale,
        centered=args.centered,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "strait-1-roads-3d.json"
    obj_path = args.output_dir / "strait-1-roads.obj"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(network_data, f, indent=2)

    with open(obj_path, "w", encoding="utf-8") as f:
        f.write(obj_content)

    total_km = network_data["total_length_m"] / 1000.0
    print(f"  [+] 3D Roads JSON: {json_path} ({len(network_data['edges'])} edges)")
    print(f"  [+] 3D Roads OBJ:  {obj_path} ({total_km:.1f} km total)")


if __name__ == "__main__":
    main()
