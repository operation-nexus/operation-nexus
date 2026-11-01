#!/usr/bin/env python3
"""PR body lint (NX-415): the template's headings are present, a tracker ID is named, no `___` placeholder is left.

Usage: python3 scripts/check_pr_body.py <body-file>   (the NX-### regex is the one pr-hygiene.yml uses)
"""
import argparse
import re
import sys

HEADINGS = ("## Summary", "## Traceability", "## Checklist")
TRACKER = re.compile(r"NX-[0-9]{3,}")


def problems(body: str) -> list[str]:
    lines = [ln.strip() for ln in body.splitlines()]
    bad = [f"missing section heading: {h}" for h in HEADINGS if not any(ln.startswith(h) for ln in lines)]
    if not TRACKER.search(body):
        bad.append("no tracker ID (NX-###) in the body")
    # `___` inside inline code is documentation, not a leftover placeholder
    bad += [f"template placeholder left in: {ln[:80]}" for ln in lines if "___" in re.sub(r"`[^`]*`", "", ln)]
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip(), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("body_file", help="Path to the PR body (markdown)")
    args = parser.parse_args(argv)
    try:
        with open(args.body_file, encoding="utf-8") as f:
            bad = problems(f.read())
    except OSError as e:
        print(f"check_pr_body: {e}", file=sys.stderr)
        return 2
    for b in bad:
        print(f"check_pr_body: {b}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
