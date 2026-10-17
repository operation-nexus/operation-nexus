# ADR-0004: Toolchain and languages

- Status: Proposed (Q-ARCH-3)
- Date: 2026-10-17

## Decision
- **Python 3.12+** for the app: `uv` (lockfile with hashes), `ruff`, `mypy --strict`, `pytest`, `hypothesis`, `import-linter`. FastAPI/Starlette for HTTP+WS (lifespan, not `on_event`). Use `numpy` for vectorized spatial queries once a profile shows they are needed.
- **TypeScript (strict)** for the overlay: Vite, pnpm, Vitest, Playwright, ESLint + Prettier.
- **Contracts**: JSON Schema in `/contracts`, with generated Pydantic (datamodel-code-generator) and TS (json-schema-to-typescript) types. CI checks for drift. Hot binary frames may use msgpack with the same schema.
- **Make** as the task runner: `make check`, `make dev`, `make sim`.

## Consequences
- Two languages, so contract generation is mandatory.
- Revisit Python if the tick budget fails at target scale after vectorization. Port hot loops to Rust via PyO3; don't rewrite the whole thing.
