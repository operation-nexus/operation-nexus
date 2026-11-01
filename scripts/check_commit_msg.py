#!/usr/bin/env python3
"""Commit-message lint (AGENTS.md rule 12): Conventional Commits subject, and no AI attribution
trailer or footer (owner, 2026-11-01, Q-DEV-36; replaces the 2026-10-23 allowance, Q-DEV-26).

Usage: python3 scripts/check_commit_msg.py <commit-msg-file>   (pre-commit `commit-msg` stage passes the file)
"""
import argparse
import re
import sys

CONVENTIONAL = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-zA-Z0-9_\-/]+\))?!?: .+$")
# A closed list of the exact addresses AI tools sign co-author trailers with (add one when a tool
# is seen using it). The whole address between < and > must match, so a human co-author, at any
# company and with any name, stays allowed. Session lines and "Generated with" footers too.
ATTRIBUTION = re.compile(
    r"^[^\w]*(co-authored-by:[^<]*<(noreply@anthropic\.com|(noreply|codex)@openai\.com|copilot@github\.com"
    r"|\d+\+(copilot|codex|codex\[bot\])@users\.noreply\.github\.com)>"
    r"|(claude|codex|copilot|gemini|cursor|chatgpt|windsurf|antigravity)-session:\s"
    r"|generated (with|by) \[?(claude|codex|copilot|gemini|cursor|chatgpt|windsurf|antigravity)\b)",
    re.IGNORECASE,
)


def problems(lines: list[str]) -> list[str]:
    lines = [ln for ln in lines if not ln.startswith("#")]  # git strips comment lines itself
    if not any(ln.strip() for ln in lines):
        return ["commit message is empty"]
    bad: list[str] = []
    subject = lines[0].strip()
    if not subject.startswith(("Merge ", "Revert \"")) and not CONVENTIONAL.match(subject):
        bad.append(f"subject is not a Conventional Commit (type(scope): description): {subject}")
    bad += [f"AI attribution is not allowed (AGENTS.md rule 12): {ln.strip()[:80]}"
            for ln in lines[1:] if ATTRIBUTION.match(ln)]  # fmt: skip
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("commit_msg_file", help="Path to commit message file")
    raw_args = argv[1:] if argv is not None else sys.argv[1:]
    try:
        args = parser.parse_args(raw_args)
    except SystemExit as e:
        return e.code

    try:
        with open(args.commit_msg_file, encoding="utf-8") as f:
            bad = problems(f.read().splitlines())
    except OSError as e:
        print(f"check_commit_msg: {e}", file=sys.stderr)
        return 2

    for b in bad:
        print(f"check_commit_msg: {b}", file=sys.stderr)
    if bad:
        print("Example: feat(sim): add supply decay to captured nodes (NX-123)", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
