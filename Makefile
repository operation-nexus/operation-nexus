SIM := services/sim
OVERLAY := apps/overlay

.PHONY: bootstrap check check-python check-overlay

bootstrap:
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

check-overlay:
	pnpm --dir $(OVERLAY) run typecheck
	pnpm --dir $(OVERLAY) run lint
	pnpm --dir $(OVERLAY) test
