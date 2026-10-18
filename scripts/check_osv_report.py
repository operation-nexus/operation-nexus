#!/usr/bin/env python3
"""SCA gate (CICD §5): fail on osv-scanner findings that are high or critical (CVSS >= 7.0) with a fix available.

Every finding is listed; only blocking ones set the exit code. A group with no CVSS score is listed but does not block
(dependency-review and Dependabot alerts still cover it). Accepted risks go in osv-scanner.toml [[IgnoredVulns]].

Usage: python3 scripts/check_osv_report.py <osv-scanner --format json output>
"""
import json
import sys

HIGH = 7.0


def findings(report: dict) -> list[tuple[bool, str]]:
    """(blocks, description) per vulnerability group."""
    out = []
    for result in report.get("results") or []:
        for pkg in result.get("packages") or []:
            p = pkg.get("package", {})
            fixed = {v["id"] for v in pkg.get("vulnerabilities") or []
                     if any("fixed" in e for a in v.get("affected") or [] for r in a.get("ranges") or []
                            for e in r.get("events") or [])}
            for g in pkg.get("groups") or []:
                try:
                    score = float(g.get("max_severity") or "")
                except ValueError:
                    score = None
                ids = g.get("ids") or []
                has_fix = bool(fixed & set(ids))
                blocks = score is not None and score >= HIGH and has_fix
                out.append((blocks, f"{p.get('ecosystem')} {p.get('name')} {p.get('version')}: {' '.join(ids)} "
                                    f"(CVSS {'?' if score is None else score}{', fix available' if has_fix else ''})"))
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    with open(argv[1], encoding="utf-8") as f:
        found = findings(json.load(f))
    # Package names come from PR-controlled lockfiles: indent so no line starts a workflow command ("::").
    for blocks, desc in found:
        print(f"  {'BLOCK' if blocks else 'note '} {desc}")
    blocking = sum(b for b, _ in found)
    print(f"check_osv_report: {len(found)} finding(s), {blocking} blocking (CVSS >= {HIGH} with a fix)")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
