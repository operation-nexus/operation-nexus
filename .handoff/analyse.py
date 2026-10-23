import json, statistics, sys
from pathlib import Path
S = Path(sys.argv[1])
for label in ("before", "after"):
    rep = json.loads((S / label / "report.json").read_text())
    print(f"== {label}: config {rep['config'].get('config_hash','?')[:12]} overrides {rep['config'].get('overrides')}")
    for prof in ("evening-150", "raid-300"):
        a2 = rep["profiles"][prof]["A2"]
        print(f" {prof} A2 all: median {a2['median_s']} tail {a2['tail']} status {a2['status']}")
        for kind, g in sorted(a2["by_persona_kind"].items()):
            print(f"   {kind}: median {g['median_s']} tail {g['tail']} newbies {g.get('newbies')} with_impact {g.get('with_impact')} kinds {g.get('first_impact_kinds')}")
        flows = {}
        for s in rep["seeds"]:
            run = json.loads((S / label / "runs" / f"{prof}-s{s}.json").read_text())
            x = run["metrics"]["nx389"]
            for side in ("COALITION", "ENEMY"):
                f = flows.setdefault(side, {k: [] for k in ("rear", "lateral", "delivered", "consumed", "dstock", "carriers")})
                f["rear"].append(x["rear_loaded"].get(side, 0))
                f["lateral"].append(x["lateral_loaded"].get(side, 0))
                f["delivered"].append(x["delivered"].get(side, 0))
                f["consumed"].append(x["consumed"].get(side, 0))
                f["dstock"].append(x["stock_end"][side] - x["stock_start"][side])
                f["carriers"].append(x["carriers_spawned"].get(side, 0))
        for side, f in flows.items():
            print(f"   {side}: " + ", ".join(f"{k} {v}" for k, v in f.items()))
