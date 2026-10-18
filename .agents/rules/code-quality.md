# Code Quality Rules

Rules for every new or touched file. They carry lessons from an earlier project's static-analysis and security
findings, adapted to this repo's stack (ADR-0004). Where a rule here and a spec, ADR or `AGENTS.md` disagree, the spec
side wins; stop and ask. Related: `docs/quality/DATA-INTEGRITY.md`, `REVIEW-CHECKLIST.md`, `TESTING-STRATEGY.md`,
`DEFINITION-OF-DONE.md`.

## 0. Build less

- Build what the tracker item and spec ask for, nothing speculative: no option, field, config key, endpoint or
  abstraction "for later".
- Reuse before writing: grep for a helper, schema, module or test fixture that already does it.
- Fix at the shared root: one guard in the shared function, not one per caller.
- Deletion beats addition; the shortest correct diff wins. Stdlib and installed dependencies before new code; no new
  dependency for what a few lines do (AGENTS.md rule 8).
- A deliberate shortcut with a known ceiling gets a comment naming the limit and when to upgrade. If it is worth
  tracking, it cites a tracker ID (`NX-###`), like any TODO (DEFINITION-OF-DONE).
- Never cut: input validation at trust boundaries, data-loss handling, security, accessibility, honest provenance.

## 1. Security (never acceptable)

- **TLS is verified.** No `verify=False`, `ssl._create_unverified_context()`, `CERT_NONE` or `check_hostname=False`.
  For a private CA, pass a CA bundle (`ssl.create_default_context(cafile=...)`, httpx `verify=<path>`). An owner
  opt-out is an explicit env flag that defaults to verifying and logs a warning.
- **No credentials in code, including fallbacks.** `os.environ.get("X", "some-password")` is banned: read the value,
  fail loudly when it is missing. This is the DATA-INTEGRITY §3 rule applied to secrets.
- **Bind to all interfaces** (`0.0.0.0`) only for in-container servers, via an env var, with the reason in a comment.
  Host services bind to localhost or the tailnet (ADR-0006).

## 2. Python async correctness

- **Never swallow cancellation.** In `except asyncio.CancelledError:` clean up, then `raise`; better, put cleanup in
  `finally`. To stop a background task: `task.cancel(); await asyncio.gather(task, return_exceptions=True)`, never
  `try: await task except CancelledError: pass`.
- **Keep a reference to every fire-and-forget task** (a set of tasks, discarded in a done-callback, or a
  `TaskGroup`). A bare `asyncio.create_task(...)` whose result is dropped can be garbage-collected mid-run.
- **No blocking I/O in `async def`.** File and SQLite work goes through `asyncio.to_thread` or the persistence module.
- **Time outside `sim-core` is timezone-aware:** `datetime.now(timezone.utc)`, never `datetime.utcnow()`. Inside
  `sim-core` there is no wall clock at all (AGENTS.md rule 3).
- **A service never crash-loops because a dependency is still starting.** Connect at startup with bounded retries and
  backoff, then fail with a clear error.

## 3. HTTP / WebSocket (FastAPI, ADR-0004)

- **Parameters use `Annotated`:** `limit: Annotated[int, Query(ge=1, le=500)] = 100`. Never `limit: int = Query(...)`.
- Pydantic optional fields have an explicit default: `callsign: str | None = None`.
- Wire models come from `contracts/` (AGENTS.md rule 6); do not hand-write a request or frame type.

## 4. TypeScript (overlay, site, command center)

- **Always pass a comparator to `.sort()`.** A bare `.sort()` sorts numbers as strings, and any ordering that reaches
  the screen or a hash must be deterministic.
- `Number.parseInt` / `Number.parseFloat` with an explicit radix, not the globals. `Math.trunc(x)`, not `x | 0`, unless
  you need the int32 wrap (hashing), which gets a comment saying so.
- No async work in constructors: construct, then call `init()`.
- Interactive DOM elements are real `<button>` / `<input>` (or have role, tabIndex and a keyboard handler), and form
  labels are associated with their controls (Command Center, site).
- Text from chat or an LLM never goes through `innerHTML` (OVERLAY OV-9, frontend role card).

## 5. Hygiene (every touched file)

- No unused imports, variables or assignments; no commented-out code; no duplicate imports.
- Keep functions small and shallow (aim for a cognitive complexity of 15 or less): extract helpers rather than
  nesting. When touching a function over the limit, leave it smaller than you found it.
- No string literal repeated 3+ times in a module: make it a constant.
- No emojis in code, comments or commit messages. Docs use them sparingly; the tracker's status glyphs are its legend
  and stay.

## 6. Suppressions

`# noqa: <code>`, `# type: ignore[<code>]` and `// eslint-disable-next-line <rule>` always name the specific rule and
give the reason on the same line, and only where the code is deliberately correct. A rule we do not follow at all is
switched off in the tool's config (`pyproject.toml`, ESLint config), not suppressed line by line.

## 7. Tests that prove something

A test exists to fail when the behaviour breaks. A test that passes whatever the code does is worse than none.
TESTING-STRATEGY says *what* to test per risk; these rules say how to make each test honest.

- **Fails without the change.** Write the test first, or revert the fix, and watch it fail for the reason the change
  addresses; say so in the PR. A bug fix gets a test that reproduces the bug.
- **Real code, real shapes.** Drive the real function, sim system or component. Mock only the boundary (platform API,
  LLM, clock, network, browser APIs), and shape mocked data from recorded fixtures (TESTING-STRATEGY §3.4, §3.8),
  never from what the caller happens to expect. Do not mock the module under test.
- **Assert outcomes, not calls.** Check the state, event, rendered text or frame a viewer or caller would see. "Was
  called" or "did not throw" alone proves nothing; golden or snapshot updates need a reason (`golden-update` label).
- **Edges, not just the happy path.** Empty, missing and malformed input; zero, one and many; exact limits and off by
  one; failures (HTTP error, timeout, malformed LLM reply); concurrency (double command, a reply for an old request).
- **No test that only restates the code** (expected values computed with the same expression, or constants copied from
  the implementation). Use independent expected values: a worked example, a recorded fixture.
- **Deterministic.** Fake clocks and seeded randomness; no real timers or network. A flaky test is a bug.
- A non-trivial fix without such a test is not done. Trivial one-line changes (text, a colour token) need none.

## 8. Before every commit

1. `make check` (or the subset for the package you touched) passes. Run tests before committing, never after.
2. Commit specific paths (`git add <paths>`), never `git add -A` across unrelated work.
3. `python3 scripts/check_tracked_files.py` passes: no tracked file that is gitignored, a recording/capture
   (clips, audio, `.db`) or over 5 MB.
4. The message passes `python3 scripts/check_commit_msg.py`: Conventional Commits, no AI attribution trailer
   (AGENTS.md rule 12).

## 9. Lessons learned here

Add a line when a review, incident or bug in this repo teaches something a rule above does not cover:
`- YYYY-MM-DD (NX-###): what happened -> the rule`. Promote a lesson into a section above once it has bitten twice.

- _(none yet)_
