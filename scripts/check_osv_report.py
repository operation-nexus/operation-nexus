#!/usr/bin/env python3
"""SCA gate (CICD §5): fail on osv-scanner findings that are high or critical (CVSS >= 7.0) with a fix available.

Every finding is listed; only blocking ones set the exit code. A group with no CVSS score is listed but does not block
(dependency-review and Dependabot alerts still cover it). Accepted risks go in osv-scanner.toml [[IgnoredVulns]].

Usage: python3 scripts/check_osv_report.py <osv-scanner --format json output> [min CVSS, default 7.0]
"""
import json
import re
import sys

HIGH = 7.0
_NUMERIC = re.compile(r"^\d+(\.\d+)*$")
_CONTROL = {c: "?" for c in [*range(0x20), 0x7F]}  # \r \n and friends: a lockfile name must not start a log line


def _key(ecosystem: str | None, name: str | None) -> tuple[str | None, str]:
    name = name or ""
    if ecosystem == "PyPI":  # PEP 503 normalization; npm names are exact
        name = re.sub(r"[-_.]+", "-", name).lower()
    return ecosystem, name


def _fix_above(fixed: str, installed: str | None) -> bool:
    # ponytail: compares plain dotted-numeric versions only (2.10.1 > 2.10.0); anything else (pre-releases, PEP 440
    # epochs, semver build tags) counts as "fix above". Upgrade to packaging/semver parsing if that over-blocks.
    if installed and _NUMERIC.match(fixed) and _NUMERIC.match(installed):
        return tuple(map(int, fixed.split("."))) > tuple(map(int, installed.split(".")))
    return True


def fix_available(vuln: dict, package: dict) -> bool:
    """A fixed version above the installed one, in an affected entry for this exact package."""
    me = _key(package.get("ecosystem"), package.get("name"))
    return any(_fix_above(e["fixed"], package.get("version"))
               for a in vuln.get("affected") or []
               if _key((a.get("package") or {}).get("ecosystem"), (a.get("package") or {}).get("name")) == me
               for r in a.get("ranges") or [] for e in r.get("events") or [] if "fixed" in e)


def findings(report: dict, min_score: float = HIGH) -> list[tuple[bool, str]]:
    """(blocks, description) per vulnerability group."""
    out = []
    for result in report.get("results") or []:
        for pkg in result.get("packages") or []:
            p = pkg.get("package", {})
            fixed = {v["id"] for v in pkg.get("vulnerabilities") or [] if fix_available(v, p)}
            for g in pkg.get("groups") or []:
                try:
                    score = float(g.get("max_severity") or "")
                except ValueError:
                    score = None
                ids = g.get("ids") or []
                has_fix = bool(fixed & set(ids))
                blocks = score is not None and score >= min_score and has_fix
                out.append((blocks, (f"{p.get('ecosystem')} {p.get('name')} {p.get('version')}: {' '.join(ids)} "
                                     f"(CVSS {'?' if score is None else score}{', fix available' if has_fix else ''})")))
    return out


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__.strip().splitlines()[-1])
        return 2
    with open(argv[1], encoding="utf-8") as f:
        min_score = float(argv[2]) if len(argv) == 3 else HIGH
        found = findings(json.load(f), min_score)
    # Package names come from PR-controlled lockfiles: indent and strip control characters so no line starts a
    # workflow command ("::").
    for blocks, desc in found:
        print(f"  {'BLOCK' if blocks else 'note '} {desc.translate(_CONTROL)}")
    blocking = sum(b for b, _ in found)
    print(f"check_osv_report: {len(found)} finding(s), {blocking} blocking (CVSS >= {min_score} with a fix)")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
