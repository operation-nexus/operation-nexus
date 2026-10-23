#!/usr/bin/env python3
"""Commit-message lint (AGENTS.md rule 12): Conventional Commits subject. Attribution trailers are allowed (owner, 2026-10-23).

Usage: python3 scripts/check_commit_msg.py <commit-msg-file>   (pre-commit `commit-msg` stage passes the file)
"""
import re
import sys

CONVENTIONAL = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-zA-Z0-9_\-/]+\))?!?: .+$")


def problems(lines: list[str]) -> list[str]:
    lines = [ln for ln in lines if not ln.startswith("#")]  # git strips comment lines itself
    if not any(ln.strip() for ln in lines):
        return ["commit message is empty"]
    bad: list[str] = []
    subject = lines[0].strip()
    if not subject.startswith(("Merge ", "Revert \"")) and not CONVENTIONAL.match(subject):
        bad.append(f"subject is not a Conventional Commit (type(scope): description): {subject}")
    return bad


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    with open(argv[1], encoding="utf-8") as f:
        bad = problems(f.read().splitlines())
    for b in bad:
        print(f"check_commit_msg: {b}", file=sys.stderr)
    if bad:
        print("Example: feat(sim): add supply decay to captured nodes (NX-123)", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
