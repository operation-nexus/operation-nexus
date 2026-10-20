#!/usr/bin/env python3
"""Report breaking changes between two contracts/ trees (NX-021, CONTRACTS §3.6, Q-CT-8, Q-CT-9).

Usage: check_contracts_compat.py <base_contracts_dir> <head_contracts_dir>
Breaking: a removed schema file, a removed property, a newly required property, a changed "type" or "const",
or a removed enum value. Before PROTOCOL_VERSION 1.0 this only reports (exit 0). From 1.0, breaking changes
fail unless the head MAJOR is above the base MAJOR.
"""
import json
import os
import sys


def _load(root):
    out = {}
    for dirpath, _, files in os.walk(root):
        for name in files:
            if name.endswith(".json"):
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as f:
                    out[os.path.relpath(path, root)] = json.load(f)
    return out


def _walk(old, new, where, out):
    if not isinstance(old, dict) or not isinstance(new, dict):
        return
    for key in ("type", "const"):
        if key in old and old.get(key) != new.get(key):
            out.append(f"{where}: {key} changed {old[key]!r} -> {new.get(key)!r}")
    if "enum" in old:
        gone = [v for v in old["enum"] if v not in new.get("enum", [])]
        if gone:
            out.append(f"{where}: enum values removed {gone}")
    old_props, new_props = old.get("properties", {}), new.get("properties", {})
    for name in old_props:
        if name not in new_props:
            out.append(f"{where}.{name}: property removed")
    for name in sorted(set(new.get("required", [])) - set(old.get("required", []))):
        out.append(f"{where}.{name}: newly required")
    for section in ("properties", "$defs"):
        for name, sub in old.get(section, {}).items():
            if name in new.get(section, {}):
                _walk(sub, new[section][name], f"{where}.{name}", out)
    for key in ("items",):
        if key in old and key in new:
            _walk(old[key], new[key], f"{where}[]", out)
    for key in ("anyOf", "oneOf"):
        for i, (o, n) in enumerate(zip(old.get(key, []), new.get(key, []))):
            _walk(o, n, f"{where}|{i}", out)


def breaking_changes(base, head):
    out = []
    for path, schema in sorted(base.items()):
        if path not in head:
            out.append(f"{path}: schema removed")
        else:
            _walk(schema, head[path], path, out)
    return out


def _major(root):
    path = os.path.join(root, "VERSION")
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return int(f.read().strip().split(".")[0])


def main(argv):
    base_dir, head_dir = argv[1], argv[2]
    changes = breaking_changes(_load(base_dir), _load(head_dir))
    for line in changes:
        print(f"breaking: {line}")
    head_major, base_major = _major(head_dir), _major(base_dir)
    if not changes or head_major == 0 or head_major > base_major:
        if changes and head_major == 0:
            print("report only: PROTOCOL_VERSION is 0.x (Q-CT-8)")
        return 0
    print(f"error: breaking changes need a MAJOR bump (base {base_major}, head {head_major})")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
