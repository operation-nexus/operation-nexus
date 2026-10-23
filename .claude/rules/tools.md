---
paths:
  - "tools/**"
---
`make check` lints `tools/` with ruff (`tools/ruff.toml`) and runs `mypy --strict` on the maintained tools (`TOOLS_TYPED` in the Makefile, mirrored in the CI `python` job); add a new typed tool to both. `tools/balance/harness_queue.py` parses hostile GitHub issue text (AGENTS.md rule 4): run the `security-review` skill on any change to it.
