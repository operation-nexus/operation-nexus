#!/usr/bin/env bash
# PostToolUse: run `ruff format` on a Python file an agent just wrote under services/sim or tools,
# so format misses never reach `make check` or CI (code-quality §9, NX-414). Never blocks and never
# fails the edit: a missing venv, a parse error or a ruff error just leaves the file as written.
input=$(cat)
if command -v jq >/dev/null 2>&1; then
  path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
else
  path=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path") or "")' 2>/dev/null)
fi
root="${CLAUDE_PROJECT_DIR:-}"
[ -n "$root" ] || exit 0
case "$path" in
  "$root"/*) ;;  # this repo or a worktree inside it; never another clone in a multi-repo session
  *) exit 0 ;;
esac
case "$path" in
  */services/sim/*.py|*/tools/*.py) ;;
  *) exit 0 ;;
esac
[ -f "$path" ] || exit 0
ruff="$root/services/sim/.venv/bin/ruff"
[ -x "$ruff" ] || exit 0
"$ruff" format --quiet -- "$path" >/dev/null 2>&1 || true
exit 0
