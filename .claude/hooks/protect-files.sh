#!/usr/bin/env bash
# PreToolUse guard: block agent edits to secrets and to read-only source material.
# Exit 2 = block (stderr shown to the agent). Fails closed if the input can't be parsed.
input=$(cat)
if command -v jq >/dev/null 2>&1; then
  path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty') || { echo "Guard: could not parse hook input" >&2; exit 2; }
elif command -v python3 >/dev/null 2>&1; then
  path=$(printf '%s' "$input" | python3 -c 'import json,sys; t=json.load(sys.stdin).get("tool_input",{}); print(t.get("file_path") or t.get("notebook_path") or "")') || { echo "Guard: could not parse hook input" >&2; exit 2; }
else
  echo "Guard: neither jq nor python3 is installed; refusing edits until one is (see docs/agentic/TOOLING.md)." >&2; exit 2
fi
[ -z "$path" ] && exit 0
name=$(basename "$path")
case "$name" in
  .env.example) exit 0 ;;
  .env|.env.*)
    echo "Blocked: agents must not write secret files ($path). See AGENTS.md rule 9." >&2; exit 2 ;;
  Raw-plans.md|Raw-conversation.md)
    echo "Blocked: $path is read-only source material. Put changes in docs/." >&2; exit 2 ;;
esac
exit 0
