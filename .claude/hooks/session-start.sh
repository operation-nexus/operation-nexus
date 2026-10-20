#!/usr/bin/env bash
# SessionStart (NX-025): cloud sessions start from a fresh clone, so install the toolchain deps
# to make `make check` runnable. Desktop runs `make bootstrap` once by hand. Never blocks the session.
[ "$CLAUDE_CODE_REMOTE" = "true" ] || exit 0
cd "$CLAUDE_PROJECT_DIR" || exit 0
command -v make >/dev/null || { echo "NX-025 bootstrap skipped: make is not installed in this environment."; exit 0; }
log="${TMPDIR:-/tmp}/nexus-bootstrap.log"
if make bootstrap >"$log" 2>&1; then
  echo "make bootstrap finished; make check is ready to run."
else
  echo "make bootstrap failed (full log: $log). Last lines:"
  tail -20 "$log"
fi
