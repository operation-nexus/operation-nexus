# MGRS Tactical Grid & Coordinate Engine Reference

This reference documents the MGRS coordinate standard used across Operation Nexus simulation, visual sandboxes, and player chat commands.

---

## 1. Coordinate Space Mapping

- **Simulation Metric Space**:
  - $X \in [0, 400\,000\text{m}]$ (West to East)
  - $Y \in [0, 240\,000\text{m}]$ (North to South in simulation; Cartography Northing increases North)
- **Grid Zone Designator (GZD)**:
  - Fictional theater default: `38S`
- **100km Square Identifiers**:
  - Columns: `MGRS_COLS = "ABCDEFGHJKLMNPQRSTUVWXYZ"` (Column offset 10 $\to$ `'L'` for Strait-1)
  - Rows: `MGRS_ROWS = "ABCDEFGHJKLMNPQRSTUV"` (Row offset 3 $\to$ `'D'` for Strait-1)
  - Column 0: `LD`, Column 1: `MD`, Column 2: `ND`, Column 3: `PD`

---

## 2. Precision Tiers

| Digits | Grid Size | Example Output | Tactical Use Case |
| :--- | :--- | :--- | :--- |
| **1 digit** | $10\text{km}$ | `38S LD 4 2` | Theater lane / sector assignment |
| **2 digits** | $1\text{km}$ | `38S LD 42 21` | Area reconnaissance, artillery barrage |
| **3 digits** | $100\text{m}$ | `38S LD 425 218` | Precision airstrike (`!strike <grid>`), point defense |
| **4 digits** | $10\text{m}$ | `38S LD 4250 2180` | Building / bunker targeting |
| **5 digits** | $1\text{m}$ | `38S LD 42503 21805` | Sensor pinpoint |

---

## 3. Python Standard Library Tool

Located at [`tools/terrain/mgrs_grid.py`](file:///Users/canthony/Documents/projects/project-hiveplex/operation-nexus/tools/terrain/mgrs_grid.py):
```bash
# Encode coordinates to MGRS:
python3 tools/terrain/mgrs_grid.py --encode 200000 60000 --precision 3
# Output: 38S ND 000 600

# Decode MGRS string to simulation meters:
python3 tools/terrain/mgrs_grid.py --decode "38S ND 000 600"
# Output: (200050.0m, 60050.0m) [Precision: 100m]
```
