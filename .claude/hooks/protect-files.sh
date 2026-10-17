#!/usr/bin/env bash
# PreToolUse guard: block agent edits to secrets and to read-only source material.
# Exit 2 = block; stderr is shown to the agent.
set -euo pipefail
path=$(jq -r '.tool_input.file_path // empty')
[ -z "$path" ] && exit 0
case "$(basename "$path")" in
  .env|.env.*)
    [ "$(basename "$path")" = ".env.example" ] && exit 0
    echo "Blocked: agents must not write secret files ($path). See AGENTS.md rule 9." >&2; exit 2 ;;
  Raw-plans.md|Raw-conversation.md)
    echo "Blocked: $path is read-only source material. Put changes in docs/." >&2; exit 2 ;;
esac
exit 0
