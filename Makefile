SIM := services/sim
OVERLAY := apps/overlay

# Prepend local user binary locations (uv in ~/.local/bin) and fallback fnm default alias
export PATH := $(HOME)/.local/bin:$(PATH):$(HOME)/.local/share/fnm/aliases/default/bin

.PHONY: bootstrap check check-python check-overlay node-version contracts perf test test-unit determinism terrain balance test-tools

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

# Maintained tools under mypy --strict. Not typed: tools/sim-bench/bench.py and grid_bench.py
# (spikes) and tools/discord-setup/tests (108 errors, untyped test script).
TOOLS_TYPED := ../../tools/balance ../../tools/replay ../../tools/sim-determinism \
  ../../tools/sim-bench/kernel_bench.py ../../tools/discord-setup/setup.py \
  ../../tools/soak/soak.py

check-python:
	cd $(SIM) && uv run --frozen ruff check . ../../tools
	cd $(SIM) && uv run --frozen ruff format --check . ../../tools
	cd $(SIM) && uv run --frozen mypy src tests
	cd $(SIM) && MYPYPATH=src:tests:../../tools/balance uv run --frozen mypy $(TOOLS_TYPED)
	cd $(SIM) && uv run --frozen lint-imports
	cd $(SIM) && uv run --frozen pytest -m "not perf"  # wall-clock budgets run in `make perf` and CI (#358)
	python3 scripts/tests/test_repo_checks.py
	python3 scripts/tests/test_cli_ergonomics.py
	python3 tools/discord-setup/tests/test_setup.py
	$(MAKE) test-tools

check-overlay: node-version
	pnpm --dir $(OVERLAY) run typecheck
	pnpm --dir $(OVERLAY) run lint
	pnpm --dir $(OVERLAY) test

# Regenerate contract types from contracts/ (NX-021, CONTRACTS §3.1). CI runs
# this and fails on any diff. Python: every schema; TS: wire messages and the
# event union (what the overlay consumes). json2ts resolves $ref against --cwd,
# so each file runs with its own directory. --use-type-alias is marked experimental
# by datamodel-code-generator: bump that dependency only together with a
# `make contracts` run and the regenerated output in the same PR.
CONTRACT_GROUPS := common commands events wire config
# Tests that assert wall-clock budgets (pytest marker `perf`); CI's plain `pytest` runs them too.
perf:
	cd $(SIM) && uv run --frozen pytest -m perf

contracts:
	python3 scripts/gen_config_reference.py
	rm -rf $(SIM)/src/nexus/contracts/gen $(OVERLAY)/src/contracts
	tmp="$$(mktemp -d)"; mkdir "$$tmp/contracts" && cp -R $(addprefix contracts/,$(CONTRACT_GROUPS)) "$$tmp/contracts"/ && \
	  cd $(SIM) && uv run --frozen datamodel-codegen --input "$$tmp/contracts" --input-file-type jsonschema \
	    --output src/nexus/contracts/gen --output-model-type pydantic_v2.BaseModel \
	    --target-python-version 3.12 --use-annotated --field-constraints \
	    --enum-field-as-literal all --use-type-alias --use-unique-items-as-set --disable-timestamp --formatters ruff-format ruff-check; \
	  status=$$?; rm -rf "$$tmp"; exit $$status
	for f in contracts/wire/*.json contracts/events/event.json; do \
	  rel="$${f#contracts/}"; mkdir -p "$(OVERLAY)/src/contracts/$$(dirname "$$rel")"; \
	  pnpm --dir $(OVERLAY) exec json2ts -i "../../$$f" -o "src/contracts/$${rel%.json}.ts" \
	    --cwd "../../$$(dirname "$$f")" --additionalProperties false \
	    --bannerComment "/* Generated from contracts/ by make contracts (NX-021). Do not edit. */" || exit 1; \
	done

test:
	cd $(SIM) && uv run --frozen pytest
	$(MAKE) test-tools

test-unit:
	cd $(SIM) && uv run --frozen pytest -k "not golden"

determinism:
	cd $(SIM) && uv run --frozen python ../../tools/sim-determinism/check.py

terrain:
	python3 tools/terrain/bake_synthetic_dted.py --test
	python3 tools/terrain/drape_roads.py --test

balance:
	@if [ -z "$(ARGS)" ]; then \
	  echo "Running balance smoke test (overnight-0, 1 seed, 1 hour)..."; \
	  tmp="$$(mktemp -d)"; \
	  cd $(SIM) && uv run --frozen python ../../tools/balance/balance.py --profile overnight-0 --seeds 1 --hours 1 --workers 1 --out "$$tmp/report"; \
	  status=$$?; rm -rf "$$tmp"; exit $$status; \
	else \
	  cd $(SIM) && uv run --frozen python ../../tools/balance/balance.py $(ARGS); \
	fi

test-tools:
	python3 tools/terrain/bake_synthetic_dted.py --test
	python3 tools/terrain/drape_roads.py --test
	python3 tools/terrain/mgrs_grid.py --test
	python3 tools/assets/generate_lowpoly_assets.py --test
	python3 tools/replay/render_cinematic_pass.py --test
