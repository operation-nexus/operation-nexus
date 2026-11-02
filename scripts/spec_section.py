#!/usr/bin/env python3
"""Print one section of a Markdown spec, so an agent reads only the part its task needs (NX-415, W6).

  python3 scripts/spec_section.py docs/specs/SIM-CORE.md 3
  python3 scripts/spec_section.py docs/specs/SIM-CORE.md SC-8
  python3 scripts/spec_section.py docs/specs/SIM-CORE.md "Logistics"

SECTION matches a heading's leading number or id ("3", "3.2", "SC-8"; a trailing "." is ignored), else its whole
title, with or without a trailing parenthetical citation, case-insensitively. Prints that heading and its body up
to the next heading of the same or a higher level.
Exit 1 when the section is not found, 2 on bad arguments or an unreadable file.
"""
import argparse
import re
import sys

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
# A trailing citation, "Budgets (Q-SIM-4, Q-SIM-6)" -> "Budgets": only parentheticals naming a Q-row, ADR, NX id or §,
# so "Logistics (air)" stays a different title from "Logistics".
TRAILING_CITE = re.compile(r"\s*\((?=[^()]*(?:\bQ-[A-Z]+-\d|\bADR-\d|\bNX-\d|§))[^()]*\)$", re.IGNORECASE)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")  # CommonMark fence: up to 3 spaces, then ``` or ~~~


def _fence_close(line: str, opener: str) -> bool:
    """True when `line` closes a fence opened with `opener`: same character, at least as long, nothing after it."""
    m = FENCE.match(line)
    return bool(m) and m.group(1)[0] == opener[0] and len(m.group(1)) >= len(opener) and not m.group(2).strip()


def section(lines: list[str], wanted: str) -> list[str] | None:
    """The heading line matching `wanted` and its body, or None."""
    key = wanted.strip().rstrip(".").lower()
    start = level = -1
    opener = ""  # the open fence's marker, "" when outside a fence
    for i, line in enumerate(lines):
        if opener:
            if _fence_close(line, opener):
                opener = ""
            continue
        fence = FENCE.match(line)
        if fence and not (fence.group(1)[0] == "`" and "`" in fence.group(2)):  # a backtick info string has no "`"
            opener = fence.group(1)
            continue
        m = HEADING.match(line)
        if not m:
            continue
        depth = len(m.group(1))
        if start >= 0:
            if depth <= level:
                return lines[start:i]
            continue
        text = m.group(2)
        first, _, rest = text.partition(" ")
        names = {text.lower(), TRAILING_CITE.sub("", text).lower()}
        if any(c.isdigit() for c in first):  # "3. Requirements", "SC-10 Budgets (Q-SIM-4)"
            title = rest.strip().lower()
            names |= {first.rstrip(".").lower(), title, TRAILING_CITE.sub("", title)}
        if key in names:
            start, level = i, depth
    return lines[start:] if start >= 0 else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Print one section of a Markdown spec.")
    ap.add_argument("spec", help="path to the Markdown file")
    ap.add_argument("section", help='heading number, id or title, e.g. 3, SC-8 or "Logistics"')
    args = ap.parse_args(argv)
    try:
        with open(args.spec, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except (OSError, UnicodeDecodeError) as e:
        print(f"spec_section: cannot read {args.spec}: {e}", file=sys.stderr)
        return 2
    found = section(lines, args.section)
    if found is None:
        print(f"spec_section: no section {args.section!r} in {args.spec}", file=sys.stderr)
        return 1
    print("\n".join(found).rstrip("\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
