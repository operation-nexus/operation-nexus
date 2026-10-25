# Road Network, Bridge & Waypoint Taxonomy

**Specification ID**: `SPEC-ROAD-BRIDGE-01`  
**Context**: Operation Nexus / Hiveplex Theater Cartography (NX-176)

---

## 1. Physical Bridge Definition & Boundary Rules

### 1.1 The Bridge vs Approach Dilemma
In high-level scenario graphs, an edge between two bases may be labeled `bridge: bridge-n` (e.g. `fob-n-w` at $X=130\text{km}$ to `cross-n` at $X=230\text{km}$, spanning $100\text{km}$ total).
However, a physical bridge structure must **never** be rendered across dry land.

```
[ FOB North-West (130km) ]
         │ (52km Land Approach Road, Ground Tarmac at +0.22m)
[ West Abutment (182km) ] <─── Shoreline Abutment / Pier Foundation
         │ (36km Physical Bridge Structure: Deck + Truss + Pylons at +14m over Water)
[ East Abutment (218km) ] <─── Shoreline Abutment / Pier Foundation
         │ (12km Land Departure Road, Ground Tarmac at +0.22m)
[ North Crossing (230km) ]
```

### 1.2 Boundary Standards
1. **Bridge Crossing Span**:
   - Strictly active where the terrain crosses open water ($|X - 200\text{km}| \le 18\text{km}$).
   - Elevated deck clearance: $+14.0\text{m}$ above sea level (allowing naval passage below).
   - Concrete pier pylons extending into the trench floor ($-8.0\text{m}$).
   - Heavy structural steel trusses along the road deck margins.
2. **Land Approach / Departure Highways**:
   - Draped directly over the continuous digital elevation model ($+0.22\text{m}$ tarmac offset).
   - Conforms to natural ground undulations, hill slopes, and valley corridors.
   - Smooth transition ramp ($200\text{m}$ grade) connecting the $+0.22\text{m}$ ground highway to the $+14.0\text{m}$ bridge deck at each abutment.

---

## 2. Road Node Taxonomy

Theater road networks are composed of two distinct classes of nodes:

### 2.1 Class A: Facilities & Strategic POIs
- **SANCTUARY**: Indestructible rear source (e.g. `haven`, `static-rear`).
- **AIRBASE**: Primary fixed-wing flight operations and logistics node (e.g. `west-ab`, `east-ab`).
- **FOB**: Forward operating base, supply depot, and ground respawn point (e.g. `fob-nw`, `fob-se`).
- **HQ**: Central theater command center (e.g. `static-hq`).

### 2.2 Class B: Highway Waypoints & Junctions (Non-Facility Nodes)
Pure navigation nodes with zero garrison quota, zero production capacity, and neutral ownership. Used to shape realistic highway geometry:
1. **JUNCTION (`kind: JUNCTION`)**:
   - Highway forks and intersections allowing convoys and patrols to branch between lanes, switchback over mountain passes, or take low-visibility valley bypasses.
   - Examples: `jct-w-pass` (foothill pass), `jct-e-hub` (central supply distribution interchange), `jct-sneak` (southern sneak valley bypass).
2. **ABUTMENT (`kind: ABUTMENT`)**:
   - Exact physical threshold where a surface road terminates at the water's edge and transitions to an elevated bridge span.
   - Examples: `abut-n-w` ($X=182\text{km}, Y=60\text{km}$), `abut-n-e` ($X=218\text{km}, Y=60\text{km}$).
