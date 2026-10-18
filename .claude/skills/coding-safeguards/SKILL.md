---
name: coding-safeguards
description: Guardrails that stop an agent from deleting, duplicating or mis-pathing code while editing. Use before refactoring, renaming or moving code across files, and before any multi-file edit.
---

# Coding safeguards

Tool-agnostic: "read", "search" and "edit" mean whatever your agent calls them. With Serena connected, prefer its
symbol tools (find symbol, find references, replace symbol body) over whole-file reads and text replacement.

1. **Read before you edit.** Read the target file (or symbol) first to confirm it exists and what it holds now. A
   file that does not exist is created, not "replaced". Re-read after a large edit to confirm nothing around it was
   lost.
2. **Keep imports intact.** Add or remove single import lines; do not rewrite the whole import block unless the whole
   file is being rewritten. After the edit, check that every name the file uses is still imported (`make check` runs
   ruff and mypy, ESLint and `tsc` do the same for TypeScript).
3. **Clean up after a move.** When logic moves to a shared place (a sim system, a store, a contract), search for every
   old copy, caller and test of the moved logic and remove the leftovers in the same change. List them first.
4. **Never guess a path.** List or search the directory before creating a file. New directories follow the target
   layout in `AGENTS.md` §3; a directory that is not there is created only when its tracker item starts.
5. **Stay in scope.** Edit only files the tracker item needs. Never edit `Raw-plans.md`, `Raw-conversation.md`,
   `.env*` or `.agents/context/` (the guard hook blocks some of these; the rule covers all of them).
6. **No emojis** in code, comments or commit messages; fix any you find in a file you are already changing. The
   tracker's status glyphs are its legend and stay.
7. **Test before commit.** Tests live next to the package they cover (`services/<svc>/tests/`, `apps/<app>/src/**/*.test.ts`)
   and `make check` passes before the commit, not after.
8. **Code quality:** follow `.agents/rules/code-quality.md` in every new or touched file.
