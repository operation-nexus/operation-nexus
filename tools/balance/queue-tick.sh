#!/usr/bin/env bash
# Hourly tick for the local harness queue (NX-381). Usage: queue-tick.sh [DEDICATED_CLONE]
# The clone (default $NEXUS_HARNESS_CLONE) is only for the queue, never the owner's working clone:
# it is reset to origin/develop each tick, so the queue code itself is always the latest develop.
# It must hold the marker file .nexus-harness-clone (create it by hand, see the README).
# Everything runs inside main(), and the file ends with `exit`, so the reset below rewriting this
# script mid-run cannot make bash read a changed file.
set -euo pipefail

main() {
  local clone="${1:-${NEXUS_HARNESS_CLONE:-}}"
  if [[ -z "$clone" ]]; then
    echo "usage: queue-tick.sh DEDICATED_CLONE (or set NEXUS_HARNESS_CLONE)" >&2
    exit 2
  fi
  clone="$(cd "$clone" && pwd -P)"
  if [[ ! -f "$clone/.nexus-harness-clone" ]] ||
    [[ "$(git -C "$clone" rev-parse --show-toplevel)" != "$clone" ]]; then
    echo "refusing: $clone is not a marked dedicated clone (.nexus-harness-clone at its top level)" >&2
    exit 2
  fi
  cd "$clone"
  git fetch origin develop
  git checkout --detach origin/develop
  git reset --hard origin/develop
  uv run --frozen --project services/sim python tools/balance/harness_queue.py run-once
}

# One line: bash parses it whole before main runs, so a reset that rewrites this file is safe.
main "$@"; exit $?
