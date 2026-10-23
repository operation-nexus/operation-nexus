#!/usr/bin/env python3
"""Settings registry guard and generator (NX-390, Q-CFG-15, CONFIG-AND-CONTENT CFG-5).

Reads contracts/config/balance.json. Every annotation site (a leaf key, a shared $def, or the
additionalProperties of a map) must carry x-unit, x-hot-reload, x-category, x-audience, x-edit-role, x-tune,
x-source and x-status. Exits non-zero on a missing or invalid field, otherwise writes
docs/specs/CONFIG-REFERENCE.md. `make contracts` runs it. Stdlib only.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "contracts" / "config" / "balance.json"
OUT = ROOT / "docs" / "specs" / "CONFIG-REFERENCE.md"

EXEMPT_BLOCKS = {"schema_version"}
# Blocks not yet annotated (NX-390 follow-up PRs); each leaves this list when its block is done.
PENDING_BLOCKS = ["logistics", "capture", "campaign", "combat", "tasking", "director"]
BLOCK_CATEGORY = {"sim": "WORLD", "air": "WORLD", "fow": "WORLD", "slots": "SLOTS", "logistics": "LOGISTICS",
                  "combat": "COMBAT", "capture": "CAPTURE", "campaign": "CAMPAIGN", "tasking": "TASKING",
                  "director": "DIRECTOR"}
CATEGORIES = ["WORLD", "SLOTS", "LOGISTICS", "COMBAT", "CAPTURE", "CAMPAIGN", "TASKING", "DIRECTOR"]
ENUMS = {
    "x-category": CATEGORIES,
    "x-audience": ["OPERATOR", "TUNER", "DEVELOPER"],
    "x-edit-role": ["ADMIN", "NONE"],
    "x-status": ["PROPOSED", "RULE_DEFAULT", "VALIDATED", "FIXED"],
}
REGISTRY_FIELDS = ["x-category", "x-audience", "x-edit-role", "x-tune", "x-source", "x-status"]
ALWAYS_FIELDS = ["x-unit", "x-hot-reload"]
TUNE_KEYS = {"min", "max", "step", "scale"}


def _resolve(schema, node):
    """Follow local $ref; return (node, def name or None)."""
    ref = node.get("$ref", "") if isinstance(node, dict) else ""
    if ref.startswith("#/$defs/"):
        name = ref[len("#/$defs/"):]
        return schema["$defs"][name], name
    return node, None


def sites(schema):
    """Annotation sites in schema order: [{"name", "paths", "blocks", "node"}]."""
    found = {}
    order = []

    def add(key, path, block, node):
        if key not in found:
            found[key] = {"name": key, "paths": [], "blocks": [], "node": node}
            order.append(key)
        site = found[key]
        site["paths"].append(path)
        if block not in site["blocks"]:
            site["blocks"].append(block)

    def walk(node, path, block, def_name):
        if "properties" in node:
            for name, child in node["properties"].items():
                if not path and name in EXEMPT_BLOCKS:
                    continue
                walk_child(child, f"{path}.{name}" if path else name, block or name)
        elif isinstance(node.get("additionalProperties"), dict):
            add(path + ".*", path + ".*", block, node["additionalProperties"])
        else:
            add("#/$defs/" + def_name if def_name else path, path, block, node)

    def walk_child(child, path, block):
        node, def_name = _resolve(schema, child)
        walk(node, path, block, def_name)

    walk(schema, "", None, None)
    return [found[k] for k in order]


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _tune_problems(tune, node):
    if tune is None:
        return []
    kind = node.get("type")
    if kind not in ("integer", "number"):
        return ["x-tune must be null on a non-numeric key"]
    if not isinstance(tune, dict) or set(tune) != TUNE_KEYS:
        return ["x-tune must be null or an object with min, max, step, scale"]
    out = []
    if tune["scale"] not in ("LINEAR", "LOG"):
        out.append(f"x-tune.scale {tune['scale']!r} is not LINEAR or LOG")
    if not all(_is_num(tune[k]) for k in ("min", "max", "step")):
        return out + ["x-tune min, max and step must be numbers"]
    lo, hi, step = tune["min"], tune["max"], tune["step"]
    if kind == "integer" and not all(float(v).is_integer() for v in (lo, hi, step)):
        out.append("x-tune min, max and step must be whole numbers on an integer key")
    if lo > hi:
        out.append(f"x-tune min {lo} is above max {hi}")
    if step <= 0:
        out.append(f"x-tune step {step} must be above 0")
    if tune["scale"] == "LOG" and lo <= 0:
        out.append("x-tune LOG scale needs min above 0")
    if "minimum" in node and lo < node["minimum"]:
        out.append(f"x-tune min {lo} is below the schema minimum {node['minimum']}")
    if "exclusiveMinimum" in node and lo <= node["exclusiveMinimum"]:
        out.append(f"x-tune min {lo} is not above the schema exclusiveMinimum {node['exclusiveMinimum']}")
    if "maximum" in node and hi > node["maximum"]:
        out.append(f"x-tune max {hi} is above the schema maximum {node['maximum']}")
    if "exclusiveMaximum" in node and hi >= node["exclusiveMaximum"]:
        out.append(f"x-tune max {hi} is not below the schema exclusiveMaximum {node['exclusiveMaximum']}")
    return out


def problems(schema, pending=None):
    """Every missing or invalid registry field, as readable lines. Empty list = clean."""
    pending = PENDING_BLOCKS if pending is None else pending
    out = []
    all_sites = sites(schema)
    for site in all_sites:
        node, where = site["node"], ", ".join(site["paths"])
        skip = all(b in pending for b in site["blocks"])
        for field in ALWAYS_FIELDS + ([] if skip else REGISTRY_FIELDS):
            if field not in node:
                out.append(f"{where}: missing {field}")
        for field in ALWAYS_FIELDS + REGISTRY_FIELDS:
            if field not in node:
                continue
            value = node[field]
            if field in ENUMS and value not in ENUMS[field]:
                out.append(f"{where}: {field} {value!r} is not one of {ENUMS[field]}")
            elif field in ("x-unit", "x-source") and not (isinstance(value, str) and value.strip()):
                out.append(f"{where}: {field} must be a non-empty string")
            elif field == "x-hot-reload" and not isinstance(value, bool):
                out.append(f"{where}: x-hot-reload must be true or false")
            elif field == "x-tune":
                out += [f"{where}: {p}" for p in _tune_problems(value, node)]
        want = [BLOCK_CATEGORY.get(b) for b in site["blocks"]]
        if node.get("x-category") in ENUMS["x-category"] and node["x-category"] not in want:
            out.append(f"{where}: x-category {node['x-category']} does not match its block ({want})")
    blocks = {b for s in all_sites for b in s["blocks"]}
    for name in pending:
        mine = [s for s in all_sites if name in s["blocks"]]
        if name not in blocks:
            out.append(f"PENDING_BLOCKS: {name!r} is not a block of the schema")
        elif all(all(f in s["node"] for f in REGISTRY_FIELDS) for s in mine):
            out.append(f"PENDING_BLOCKS: {name!r} is fully annotated, remove it from the list")
    return out


def _num(v):
    return str(int(v)) if float(v).is_integer() else repr(v)


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _type(schema, node):
    if "enum" in node:
        return "enum"
    if node.get("type") == "array":
        item, _ = _resolve(schema, node.get("items", {}))
        ref = node.get("items", {}).get("$ref", "")
        return "list of " + (ref.rsplit("/", 1)[-1] if ref else str(item.get("type", "?")))
    return str(node.get("type", "?"))


def _bounds(node):
    parts = []
    for key, sign in (("minimum", "≥"), ("exclusiveMinimum", ">"), ("maximum", "≤"), ("exclusiveMaximum", "<")):
        if key in node:
            parts.append(f"{sign} {_num(node[key])}")
    if "enum" in node:
        parts.append("one of " + ", ".join(str(v) for v in node["enum"]))
    if "minItems" in node:
        parts.append(f"≥ {node['minItems']} items")
    return ", ".join(parts) or "—"


def _tune(tune):
    if not isinstance(tune, dict):
        return "—"
    return f"{_num(tune['min'])} to {_num(tune['max'])}, step {_num(tune['step'])}, {tune['scale']}"


def render(schema):
    """The CONFIG-REFERENCE.md text. Same schema, same bytes."""
    lines = [
        "<!-- Generated by scripts/gen_config_reference.py — do not edit. -->",
        "",
        "# Balance settings reference",
        "",
        "Generated by scripts/gen_config_reference.py — do not edit. One row per key of "
        "`contracts/config/balance.json`, grouped by category (Q-CFG-15). Edit the schema, then run "
        "`make contracts`. A dash in a block still listed in `PENDING_BLOCKS` means the field is not annotated yet. "
        "Tune ranges are PROPOSED sweep ranges, not validation; the schema bounds are the validation. Values live "
        "in `balance/default.yaml`; the prose per key is in [CONFIG-AND-CONTENT](CONFIG-AND-CONTENT.md) §6.",
        "",
    ]
    by_cat = {}
    for site in sites(schema):
        node = site["node"]
        cat = node.get("x-category") or BLOCK_CATEGORY.get(site["blocks"][0], "UNCATEGORIZED")
        by_cat.setdefault(cat, []).append(site)
    head = ["Key", "Type", "Unit", "Schema bounds", "Hot reload", "Tune", "Audience", "Edit role", "Status",
            "Source", "Description"]
    for cat in sorted(by_cat, key=lambda c: (CATEGORIES.index(c) if c in CATEGORIES else len(CATEGORIES), c)):
        lines += [f"## {cat}", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        for site in by_cat[cat]:
            n = site["node"]
            keys = "<br>".join(f"`{p}`" for p in site["paths"])
            hot = {True: "Yes", False: "No"}.get(n.get("x-hot-reload"), "—")
            cells = [keys, _type(schema, n), n.get("x-unit", "—"), _bounds(n), hot,
                     _tune(n["x-tune"]) if "x-tune" in n else "—", n.get("x-audience", "—"),
                     n.get("x-edit-role", "—"), n.get("x-status", "—"), n.get("x-source", "—"),
                     n.get("description", "—")]
            lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
        lines.append("")
    return "\n".join(lines)


def main():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    found = problems(schema)
    for line in found:
        print(f"config registry: {line}", file=sys.stderr)
    if found:
        print(f"config registry: {len(found)} problem(s); fix contracts/config/balance.json", file=sys.stderr)
        return 1
    OUT.write_text(render(schema), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
