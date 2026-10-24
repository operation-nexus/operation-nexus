#!/usr/bin/env python3
"""Synthetic DTED & Analytical Hillshade Baker for Operation Nexus (NX-176).

Zero-dependency standard-library utility synthesizing 100% fictional DEM matrices,
computing analytical hillshade relief, and baking offline GIS tiles and heightmaps.
Uses pure Python standard library (struct, zlib, math) without external dependencies.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import tempfile
import zlib
from pathlib import Path


def write_png(width: int, height: int, rgb_bytes: bytes, out_path: Path) -> None:
    """Encode raw 24-bit RGB pixel buffer to valid PNG format using standard library."""
    # PNG Signature
    png_magic = b"\x89PNG\r\n\x1a\n"

    # IHDR Chunk: Width (4), Height (4), Bit depth 8, Color RGB, Deflate, Filter 0, Interlace 0
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc

    # IDAT Chunk (Scanlines prepended with filter type byte 0 = None)
    scanlines = bytearray()
    row_bytes = width * 3
    for y in range(height):
        scanlines.append(0)  # Filter type: None
        start = y * row_bytes
        scanlines.extend(rgb_bytes[start : start + row_bytes])

    compressed = zlib.compress(bytes(scanlines), level=6)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    idat_chunk = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc

    # IEND Chunk
    iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    iend_chunk = struct.pack(">I", 0) + b"IEND" + iend_crc

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(png_magic + ihdr_chunk + idat_chunk + iend_chunk)


def sample_strait1_elevation(x_m: float, y_m: float) -> float:
    """Evaluate synthetic continuous elevation for Strait-1 theater in meters.

    Theater span: 400,000m East (X) x 240,000m South (Y).
    """
    strait_center_x = 200_000.0
    dist_to_strait = abs(x_m - strait_center_x)

    # 1. Strait trench and shoreline bevel
    if dist_to_strait < 18_000.0:
        # Submarine trench: -60m to -90m
        return -80.0 + math.sin(y_m * 0.00008) * 12.0
    elif dist_to_strait < 24_000.0:
        # Coastal shoreline bevel transitioning to surface
        t = (dist_to_strait - 18_000.0) / 6_000.0
        return -80.0 + t * 85.0  # Rises to +5m

    # 2. Landmass harmonic undulation
    macro = math.sin(x_m * 0.00002) * math.cos(y_m * 0.00003) * 120.0
    micro = math.sin(x_m * 0.00007 + 1.2) * math.cos(y_m * 0.00008 + 0.8) * 45.0
    base_elev = 25.0 + macro + micro

    # 3. Northern Mountain Ridge (Y ~ 40,000m)
    north_mountain = 0.0
    if y_m < 80_000.0:
        ridge_dist = abs(y_m - 40_000.0)
        peak_profile = max(0.0, 750.0 - ridge_dist * 0.015)
        north_mountain = peak_profile * (0.85 + 0.25 * math.sin(x_m * 0.00004))

    # 4. Southern Valley Sneak Corridor (Y ~ 220,000m, X > 220,000m)
    south_valley = 0.0
    if y_m > 190_000.0 and x_m > 220_000.0:
        valley_t = (y_m - 190_000.0) / 50_000.0
        south_valley = -60.0 * valley_t + math.sin(x_m * 0.00005) * 30.0

    elev = base_elev + north_mountain + south_valley
    return max(4.0, elev)


def compute_hillshade_and_dem(
    cols: int = 400,
    rows: int = 240,
    width_m: float = 400_000.0,
    height_m: float = 240_000.0,
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
    z_factor: float = 2.5,
) -> tuple[list[float], bytearray]:
    """Calculate DEM elevation grid and Horn analytical hillshade RGB buffer."""
    dx = width_m / (cols - 1)
    dy = height_m / (rows - 1)

    # Precalculate lighting angles (in radians)
    zenith_rad = math.radians(90.0 - altitude_deg)
    # Azimuth clockwise from north converted to mathematical direction
    azimuth_math = 360.0 - azimuth_deg + 90.0
    if azimuth_math >= 360.0:
        azimuth_math -= 360.0
    azimuth_rad = math.radians(azimuth_math)

    # 1. Synthesize Elevation Matrix
    dem: list[float] = [0.0] * (cols * rows)
    for r in range(rows):
        y_m = r * dy
        for c in range(cols):
            x_m = c * dx
            dem[r * cols + c] = sample_strait1_elevation(x_m, y_m)

    # 2. Compute Analytical Hillshade (Horn 3x3 Window)
    rgb = bytearray(cols * rows * 3)

    for r in range(rows):
        r_top = max(0, r - 1)
        r_bot = min(rows - 1, r + 1)

        for c in range(cols):
            c_left = max(0, c - 1)
            c_right = min(cols - 1, c + 1)

            # 3x3 neighborhood heights
            a = dem[r_top * cols + c_left]
            b = dem[r_top * cols + c]
            c_ne = dem[r_top * cols + c_right]
            d = dem[r * cols + c_left]
            cur_z = dem[r * cols + c]
            f = dem[r * cols + c_right]
            g = dem[r_bot * cols + c_left]
            h = dem[r_bot * cols + c]
            i = dem[r_bot * cols + c_right]

            # Horn's gradient approximations
            dz_dx = ((c_ne + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * dx)
            dz_dy = ((g + 2.0 * h + i) - (a + 2.0 * b + c_ne)) / (8.0 * dy)

            slope_rad = math.atan(z_factor * math.hypot(dz_dx, dz_dy))

            if dz_dx != 0.0:
                aspect_rad = math.atan2(dz_dy, -dz_dx)
                if aspect_rad < 0.0:
                    aspect_rad += 2.0 * math.pi
            elif dz_dy > 0:
                aspect_rad = math.pi / 2.0
            elif dz_dy < 0:
                aspect_rad = 1.5 * math.pi
            else:
                aspect_rad = 0.0

            shade = math.cos(zenith_rad) * math.cos(slope_rad) + math.sin(zenith_rad) * math.sin(
                slope_rad
            ) * math.cos(azimuth_rad - aspect_rad)
            shade_val = max(0.0, min(1.0, shade))

            # Hypsometric Tinting & Styling
            idx = (r * cols + c) * 3
            if cur_z < 0.0:
                # Submarine water channel: navy blue with depth darkening
                water_shade = 0.4 + 0.6 * shade_val
                rgb[idx] = int(14 * water_shade)
                rgb[idx + 1] = int(28 * water_shade)
                rgb[idx + 2] = int(48 * water_shade)
            elif cur_z < 15.0:
                # Coastal sand / low beach
                tint = 0.5 + 0.5 * shade_val
                rgb[idx] = int(110 * tint)
                rgb[idx + 1] = int(115 * tint)
                rgb[idx + 2] = int(95 * tint)
            elif cur_z < 250.0:
                # Grassland / scrub terrain
                tint = 0.4 + 0.6 * shade_val
                rgb[idx] = int(42 * tint)
                rgb[idx + 1] = int(58 * tint)
                rgb[idx + 2] = int(44 * tint)
            elif cur_z < 550.0:
                # Foothills / exposed rock
                tint = 0.4 + 0.6 * shade_val
                rgb[idx] = int(85 * tint)
                rgb[idx + 1] = int(82 * tint)
                rgb[idx + 2] = int(76 * tint)
            else:
                # High mountain peaks / snowcap
                tint = 0.35 + 0.65 * shade_val
                rgb[idx] = int(175 * tint)
                rgb[idx + 1] = int(175 * tint)
                rgb[idx + 2] = int(185 * tint)

    return dem, rgb


def export_dted_bundle(
    output_dir: Path,
    cols: int = 400,
    rows: int = 240,
) -> tuple[Path, Path, Path]:
    """Generate and write full DEM dataset: Hillshade PNG, 16-bit Raw DEM, and Metadata JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dem, hillshade_rgb = compute_hillshade_and_dem(cols=cols, rows=rows)

    png_path = output_dir / "strait-1-hillshade.png"
    raw_path = output_dir / "strait-1-dem16.bin"
    meta_path = output_dir / "strait-1-terrain-meta.json"

    # 1. Write Hillshade PNG
    write_png(cols, rows, bytes(hillshade_rgb), png_path)

    # 2. Write 16-bit Signed Integer Binary DEM (metres)
    # ponytail: pure struct.pack, short and portable without numpy
    raw_bytes = bytearray()
    for elev in dem:
        raw_bytes.extend(struct.pack("<h", round(elev)))
    with open(raw_path, "wb") as f:
        f.write(raw_bytes)

    # 3. Write Metadata JSON
    metadata = {
        "theater": "strait-1",
        "bounds_m": {"width": 400000.0, "height": 240000.0},
        "resolution": {
            "cols": cols,
            "rows": rows,
            "dx_m": 400000.0 / cols,
            "dy_m": 240000.0 / rows,
        },
        "elevation_stats": {
            "min_m": min(dem),
            "max_m": max(dem),
            "trench_depth_m": min(dem),
            "peak_height_m": max(dem),
        },
        "artifacts": {
            "hillshade_png": png_path.name,
            "raw_dem16": raw_path.name,
        },
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return png_path, raw_path, meta_path


def run_tests() -> bool:
    """Verify PNG encoding and DEM baker calculations."""
    print("Testing PNG header and chunk integrity...")
    test_rgb = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])  # 2x2 RGB image
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_path = Path(tmp_dir) / "test_integrity.png"
        write_png(2, 2, test_rgb, test_path)

        with open(test_path, "rb") as f:
            header = f.read(8)
            if header != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError(f"Invalid PNG magic: {header!r}")
            ihdr_len = struct.unpack(">I", f.read(4))[0]
            ihdr_type = f.read(4)
            if ihdr_type != b"IHDR" or ihdr_len != 13:
                raise RuntimeError(f"Invalid IHDR header: type={ihdr_type!r}, len={ihdr_len}")

    print("Testing DEM elevation range and trench depths...")
    dem, rgb = compute_hillshade_and_dem(cols=20, rows=12)
    min_elev = min(dem)
    max_elev = max(dem)
    if min_elev > -50.0:
        raise RuntimeError(f"Expected submarine trench depth < -50m, got {min_elev:.1f}m")
    if max_elev < 400.0:
        raise RuntimeError(f"Expected mountain peaks > 400m, got {max_elev:.1f}m")
    if len(rgb) != 20 * 12 * 3:
        raise RuntimeError("RGB buffer length mismatch")

    print("All DTED baker self-checks PASSED (100% OK).")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic DTED & Analytical Hillshade Baker")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("content/theaters/dted"),
        help="Directory to output DEM tiles and hillshades",
    )
    parser.add_argument("--cols", type=int, default=400, help="Grid columns (default 400)")
    parser.add_argument("--rows", type=int, default=240, help="Grid rows (default 240)")
    parser.add_argument("--test", action="store_true", help="Run automated self-tests")

    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    print(f"Baking synthetic DTED grid ({args.cols}x{args.rows}) to {args.output_dir}...")
    png, raw, meta = export_dted_bundle(args.output_dir, cols=args.cols, rows=args.rows)
    print(f"  [+] Hillshade PNG: {png}")
    print(f"  [+] Raw DEM (16b): {raw}")
    print(f"  [+] Metadata:      {meta}")


if __name__ == "__main__":
    main()
