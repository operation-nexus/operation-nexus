#!/usr/bin/env python3
"""Map changed files to the checks `make check-fast` runs (NX-415).

Usage: python3 scripts/changed_tests.py   (prints one line per changed .py file or "pytest <path>" / "run <cmd>" lines)
Output: first token "py" = a changed Python file under services/sim or tools, "pytest" = a sim test path (relative to services/sim),
"run" = a shell command to run from the repo root. Stdlib only.
"""
import os
import subprocess
import sys

SRC = "services/sim/src/nexus/"
TESTS = "services/sim/tests/"
REPO_TESTS = "run python3 scripts/tests/test_repo_checks.py"


def plan(changed: list[str], test_dirs: set[str]) -> list[str]:
    """Lines for the changed paths. `test_dirs` = names of the directories under services/sim/tests."""
    out: list[str] = []
    for path in sorted(set(changed)):
        if path.endswith(".py") and path.startswith(("services/sim/", "tools/")):  # the trees `make check-python` lints
            out.append(f"py {path}")
        if path.startswith(SRC):
            pkg = path[len(SRC):].split("/")[0]
            out.append(f"pytest tests/{pkg if pkg in test_dirs else 'core'}")
            if pkg == "core":
                out.append("pytest tests/golden")
        elif path.startswith(TESTS) and path.endswith(".py"):  # a changed test runs itself
            out.append(f"pytest {path[len('services/sim/'):]}")
        elif path.startswith("tools/balance/"):
            out.append("pytest tests/tools")
        elif path.startswith("scripts/"):
            out.append(REPO_TESTS)
    return sorted(set(out), key=lambda s: (not s.startswith("py "), s))


def changed_files() -> list[str]:
    def git(*args: str) -> list[str]:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.split()

    base = git("merge-base", "HEAD", "origin/develop")[0]
    return git("diff", "--name-only", "--diff-filter=d", base) + git("ls-files", "--others", "--exclude-standard")


def main() -> int:
    dirs = {e.name for e in os.scandir(TESTS) if e.is_dir() and e.name != "__pycache__"}
    for line in plan(changed_files(), dirs):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
