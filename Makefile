SIM := services/sim
OVERLAY := apps/overlay

.PHONY: bootstrap check check-python check-overlay node-version

# Node major comes from .node-version (CI reads the same file). A wrong major
# fails here with a clear message instead of breaking vitest later.
NODE_MAJOR := $(shell cat .node-version)

node-version:
	@found="$$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null)"; \
	if [ "$$found" != "$(NODE_MAJOR)" ]; then \
	  echo "error: Node $(NODE_MAJOR) required (.node-version); found $${found:-none} at $$(command -v node || echo 'no node on PATH')." >&2; \
	  echo "  Install Node $(NODE_MAJOR) and put it first on PATH (see docs/agentic/TOOLING.md §5)." >&2; \
	  exit 1; \
	fi

bootstrap: node-version
	cd $(SIM) && uv sync --frozen
	pnpm --dir $(OVERLAY) install --frozen-lockfile
	@command -v pre-commit >/dev/null && pre-commit install || echo "pre-commit not installed; skip hooks (see docs/agentic/TOOLING.md)"

check: check-python check-overlay

check-python:
	cd $(SIM) && uv run --frozen ruff check .
	cd $(SIM) && uv run --frozen ruff format --check .
	cd $(SIM) && uv run --frozen mypy src tests
	cd $(SIM) && uv run --frozen lint-imports
	cd $(SIM) && uv run --frozen pytest
	python3 scripts/tests/test_repo_checks.py
	python3 tools/discord-setup/tests/test_setup.py

check-overlay: node-version
	pnpm --dir $(OVERLAY) run typecheck
	pnpm --dir $(OVERLAY) run lint
	pnpm --dir $(OVERLAY) test
