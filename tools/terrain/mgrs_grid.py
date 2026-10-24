#!/usr/bin/env python3
"""MGRS Tactical Grid & Coordinate Engine for Operation Nexus (NX-176).

Zero-dependency standard-library utility translating simulation meter coordinates
to military MGRS-style coordinate strings and vice versa.

Supported precisions:
  - 1 digit (10km tactical sector): "38S LD 4 2"
  - 2 digits (1km target grid):     "38S LD 42 21"
  - 3 digits (100m strike cell):    "38S LD 425 218"
  - 4 digits (10m precision point): "38S LD 4250 2180"
  - 5 digits (1m pinpoint):         "38S LD 42503 21805"
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import NamedTuple

# Standard 100km square column and row letter sequences (NATO MGRS, omitting I and O)
MGRS_COLS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # 24 letters
MGRS_ROWS = "ABCDEFGHJKLMNPQRSTUV"  # 20 letters

# Fictional theater default grid zone and origin offset
DEFAULT_GZD = "38S"
DEFAULT_COL_OFFSET = 10  # Starts at 'L' for Strait-1
DEFAULT_ROW_OFFSET = 3  # Starts at 'D' for Strait-1


class MGRSCoord(NamedTuple):
    gzd: str
    square: str
    easting: str
    northing: str
    precision_m: int
    x: float
    y: float

    def formatted(self, spaces: bool = True) -> str:
        """Render standard MGRS string."""
        if spaces:
            return f"{self.gzd} {self.square} {self.easting} {self.northing}"
        return f"{self.gzd}{self.square}{self.easting}{self.northing}"


def coords_to_mgrs(
    x: float,
    y: float,
    precision: int = 3,
    gzd: str = DEFAULT_GZD,
    col_offset: int = DEFAULT_COL_OFFSET,
    row_offset: int = DEFAULT_ROW_OFFSET,
) -> MGRSCoord:
    """Convert meter coordinates (x, y) to MGRS string representation.

    Args:
        x: Easting in meters (>= 0).
        y: Northing in meters (>= 0).
        precision: Number of digits per axis (1=10km, 2=1km, 3=100m, 4=10m, 5=1m).
        gzd: Grid Zone Designator string.
        col_offset: Base column letter index for 100km square.
        row_offset: Base row letter index for 100km square.

    Returns:
        MGRSCoord tuple with formatted components and calculated cell center.
    """
    if precision < 1 or precision > 5:
        raise ValueError(f"Precision must be between 1 and 5 digits, got {precision}")

    x_clamped = max(0.0, float(x))
    y_clamped = max(0.0, float(y))

    # 100km grid square indices
    col_idx = (int(x_clamped // 100_000) + col_offset) % len(MGRS_COLS)
    row_idx = (int(y_clamped // 100_000) + row_offset) % len(MGRS_ROWS)
    sq = f"{MGRS_COLS[col_idx]}{MGRS_ROWS[row_idx]}"

    # Offset within 100km square
    east_rem = x_clamped % 100_000
    north_rem = y_clamped % 100_000

    # Scale factor for requested precision (e.g., prec=3 -> 10^(5-3) = 100m step)
    step = 10 ** (5 - precision)
    east_val = int(east_rem // step)
    north_val = int(north_rem // step)

    # Format zero-padded digits
    fmt = f"{{:0{precision}d}}"
    east_str = fmt.format(east_val)
    north_str = fmt.format(north_val)

    # Center of the cell in meter coordinates
    center_x = (int(x_clamped // 100_000) * 100_000) + (east_val * step) + (step / 2.0)
    center_y = (int(y_clamped // 100_000) * 100_000) + (north_val * step) + (step / 2.0)

    return MGRSCoord(
        gzd=gzd,
        square=sq,
        easting=east_str,
        northing=north_str,
        precision_m=step,
        x=center_x,
        y=center_y,
    )


def mgrs_to_coords(
    mgrs_str: str,
    col_offset: int = DEFAULT_COL_OFFSET,
    row_offset: int = DEFAULT_ROW_OFFSET,
) -> MGRSCoord:
    """Parse an MGRS coordinate string into meter coordinates (cell center).

    Accepts formats:
      - "38S LD 425 218"
      - "38SLD425218"
      - "LD 42 21" (assumes default GZD)
    """
    clean = re.sub(r"\s+", "", mgrs_str.strip().upper())
    # Regex: optional GZD (e.g. 38S), 2-letter square, even number of digits (2 to 10)
    match = re.match(r"^(?:(\d{1,2}[A-Z]))?([A-Z]{2})(\d{2,10})$", clean)
    if not match:
        raise ValueError(f"Invalid MGRS coordinate string format: '{mgrs_str}'")

    gzd_val, sq_val, digits = match.groups()
    gzd = gzd_val or DEFAULT_GZD

    if len(digits) % 2 != 0:
        raise ValueError(f"Odd number of numerical digits in MGRS: '{digits}'")

    precision = len(digits) // 2
    if precision < 1 or precision > 5:
        raise ValueError(f"Precision must be 1 to 5 digits per axis, got {precision}")

    east_str = digits[:precision]
    north_str = digits[precision:]

    # Decode 100km square indices
    col_char = sq_val[0]
    row_char = sq_val[1]
    if col_char not in MGRS_COLS or row_char not in MGRS_ROWS:
        raise ValueError(f"Unknown 100km square letters: '{sq_val}'")

    col_idx = (MGRS_COLS.index(col_char) - col_offset) % len(MGRS_COLS)
    row_idx = (MGRS_ROWS.index(row_char) - row_offset) % len(MGRS_ROWS)

    step = 10 ** (5 - precision)
    east_val = int(east_str)
    north_val = int(north_str)

    center_x = (col_idx * 100_000) + (east_val * step) + (step / 2.0)
    center_y = (row_idx * 100_000) + (north_val * step) + (step / 2.0)

    return MGRSCoord(
        gzd=gzd,
        square=sq_val,
        easting=east_str,
        northing=north_str,
        precision_m=step,
        x=center_x,
        y=center_y,
    )


def run_tests() -> bool:
    """Self-check test suite enforcing bidirectional correctness."""
    print("Running MGRS Tactical Grid self-check suite...")
    test_cases = [
        (0.0, 0.0, 3, "38S", "LD", "000", "000", 100),
        (60000.0, 55000.0, 3, "38S", "LD", "600", "550", 100),
        (200000.0, 60000.0, 2, "38S", "ND", "00", "60", 1000),  # North bridge
        (380000.0, 120000.0, 3, "38S", "PE", "800", "200", 100),  # Static HQ
        (12345.0, 67890.0, 5, "38S", "LD", "12345", "67890", 1),
    ]

    for x, y, prec, exp_gzd, exp_sq, exp_e, exp_n, exp_step in test_cases:
        coord = coords_to_mgrs(x, y, precision=prec)
        if coord.gzd != exp_gzd:
            raise RuntimeError(f"GZD mismatch: {coord.gzd} != {exp_gzd}")
        if coord.square != exp_sq:
            raise RuntimeError(f"Square mismatch: {coord.square} != {exp_sq}")
        if coord.easting != exp_e:
            raise RuntimeError(f"Easting mismatch: {coord.easting} != {exp_e}")
        if coord.northing != exp_n:
            raise RuntimeError(f"Northing mismatch: {coord.northing} != {exp_n}")
        if coord.precision_m != exp_step:
            raise RuntimeError(f"Step mismatch: {coord.precision_m} != {exp_step}")

        # Roundtrip test
        formatted = coord.formatted()
        decoded = mgrs_to_coords(formatted)
        if decoded.square != exp_sq or decoded.easting != exp_e or decoded.northing != exp_n:
            raise RuntimeError(f"Roundtrip failed for {formatted}")
        # Decoded coordinate should match cell center (within half step)
        if not math.isclose(decoded.x, coord.x, abs_tol=1.0) or not math.isclose(
            decoded.y, coord.y, abs_tol=1.0
        ):
            raise RuntimeError(f"Center position deviation: {decoded} vs {coord}")

    # Verify whitespace and formatting tolerance
    loose_str = "  38s  ld   425   218 "
    parsed = mgrs_to_coords(loose_str)
    if parsed.square != "LD" or parsed.easting != "425" or parsed.northing != "218":
        raise RuntimeError(f"Whitespace parsing failed: {parsed}")
    if parsed.x != 42550.0 or parsed.y != 21850.0:
        raise RuntimeError(f"Whitespace coordinate error: {parsed}")

    print("All MGRS coordinate self-checks PASSED (100% OK).")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="MGRS Tactical Grid & Coordinate Engine")
    parser.add_argument(
        "--encode", nargs=2, type=float, metavar=("X", "Y"), help="Encode (X, Y) meters to MGRS"
    )
    parser.add_argument(
        "--decode", type=str, metavar="MGRS", help="Decode MGRS string to (X, Y) center coordinates"
    )
    parser.add_argument(
        "--precision",
        type=int,
        default=3,
        choices=[1, 2, 3, 4, 5],
        help="Precision digits (1=10km..5=1m)",
    )
    parser.add_argument("--test", action="store_true", help="Run automated self-tests")

    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    if args.encode:
        x, y = args.encode
        coord = coords_to_mgrs(x, y, precision=args.precision)
        print(f"MGRS Grid:   {coord.formatted()}")
        print(f"Cell Center: ({coord.x:.1f}m, {coord.y:.1f}m) ±{coord.precision_m / 2.0:.1f}m")
    elif args.decode:
        coord = mgrs_to_coords(args.decode)
        print(f"Parsed MGRS: {coord.formatted()}")
        print(f"Cell Center: ({coord.x:.1f}m, {coord.y:.1f}m) [Precision: {coord.precision_m}m]")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
