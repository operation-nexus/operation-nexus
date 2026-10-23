# Sentry research note (2026-10-23)

Status: Research note, not a decision; Q-DEV-24, NX-364 · Spec: ERROR-PIPELINE (EP-1..EP-7) · ADR-0010 (N-1)

All sources were read on 2026-10-23 and are listed in §9 by id (S1..S22). "Probe" means a script run on 2026-10-23 against the `sentry-sdk` 2.73.0 wheel from PyPI, using a fake transport (no network), on the session's system Python 3.13.16 (not the repo's 3.12). Anything not confirmed from a primary source is marked **[UNVERIFIED]**.

## 1. Summary
- The free Developer plan gives 5k errors a month, 1 user and a 30-day lookback (S1). Over-quota events "will not be accepted" (S2). Whether the Developer plan can ever be billed is not stated: **[UNVERIFIED]**, but S1 shows no spend thresholds or spend notifications for it.
- `sentry-sdk` 2.73.0 (released 2026-10-22, MIT, classifiers include 3.12) fits our toolchain (S6). A 3.0.0b1 beta is out (2026-10-21), and `send_default_pii` is deprecated and "will be removed in version 3.0" (S7). Pin `<3` until we review 3.0.
- The SDK's defaults send much more than EP-2 allows: `sys.argv`, the installed package list, the hostname, local variables, source lines, absolute file paths and the exception message (probe, S7, S8). An allowlist `before_send` is required, and it works: it runs last, after serialization, and a `before_send` that raises drops the event (probe, S10).
- `before_send` and `Transport.capture_envelope` run on the calling thread. Only the default HTTP transport moves the network send to a daemon worker thread with a 100-item queue that drops when full (probe, S10). So EP-3 needs our own queue and thread in front of the SDK; the SDK alone would build and scrub the event on the sim thread.
- A `Transport` subclass instance passed as `transport=` receives every envelope synchronously. That gives a deterministic, network-free EP-2 test (probe, S10).
- 5k errors a month is small for a 10 Hz loop. A crash loop that reports every tick would use the month's quota in minutes (estimate, §6). The adapter needs its own per-fingerprint rate limit.
- An official Sentry MCP server exists (getsentry/sentry-mcp, hosted at mcp.sentry.dev, OAuth). Its stdio mode lists write scopes, and no read-only switch is documented (S16, S17). The REST API reads issues with the `event:read` scope (S14).
- GlitchTip says it is "compatible with Sentry client SDKs" (S18), so EP-7's DSN-only switch is plausible. Which SDK features it ignores is not documented on the pages read: **[UNVERIFIED]**.

## 2. Free plan, quotas and regions
- Developer plan: "5k errors", "1 User", "30-day lookback", 5GB logs, 5M spans, 50 replays; email is the only alert channel; "Spend notifications: No", "Set maximum spend threshold: No" (S1).
- Seer (AI root cause and fix) is "No" on Developer; "MCP access" is listed for Developer (S1).
- Over quota: "Events and attachments that exceed your quota will not be accepted" (S2). For paid plans, data past reserved volume and PAYG budget "will be dropped and you won't be charged for it" (S4). Developer-plan PAYG availability is not stated: **[UNVERIFIED]**.
- Spike protection drops events during a spike. It is enabled per project, and S3 does not say if it is on by default or available on Developer: **[UNVERIFIED]**. The threshold formula uses the Developer plan's minimum as a floor (S3).
- Per-project error rate limits are set under the project's Client Keys (DSN) settings (S2). Whether the Developer plan can set them: **[UNVERIFIED]**.
- Trial: new accounts get a 14-day trial, then fall back to Developer (S4).
- Data region: US (Iowa) or EU (Frankfurt), chosen when the organization is created, and it "can't be changed" later (S5). Plan availability of the choice is not stated on S5; S1 shows "Data Residency: Yes" on all plans.
- Open-source sponsorship: 5M errors and Business features for projects under "a friendly license like Apache or MIT" (S21). Whether this project qualifies (public repo, monetized stream) is not stated: **[UNVERIFIED]**.

## 3. sentry-python behavior
**Version and license.** 2.73.0, uploaded 2026-10-22; `license_expression` MIT; `requires_python >=3.6`; classifiers list 3.6 to 3.15 (S6). MIT is compatible with the project's MIT license.

**Options that matter for EP-2 (defaults from S7, confirmed in `consts.py`, S10).**
| Option | Default | Note |
|---|---|---|
| `send_default_pii` | `None` | Deprecated; removed in 3.0. Replaced by `data_collection` (dict, default `None`). Setting `data_collection` opts into "permissive defaults" and disables `event_scrubber` (S7). Do not set `data_collection`. |
| `include_local_variables` | `True` | Adds `vars` to every frame (probe). Must be `False`. |
| `include_source_context` | `True` | Adds `pre_context`, `context_line`, `post_context` (probe). Set `False`. |
| `max_request_body_size` | `"medium"` | Only used by web-framework integrations; values `always`, `never`, `small`, `medium` (S10). Set `"never"`. |
| `before_send` | `None` | Runs after event processors and serialization; returning `None` drops (S7, S10). |
| `before_breadcrumb` | `None` | Returning nothing drops the breadcrumb (S7). |
| `max_breadcrumbs` | `100` | Set `0` as a second guard. |
| `server_name` | `None` -> `socket.gethostname()` (S10) | Leaks the host name. Set a constant. |
| `release` | `None` -> `SENTRY_RELEASE`, else `git rev-parse HEAD` in a subprocess, else CI env vars (S10) | Set it explicitly. |
| `environment` | `SENTRY_ENVIRONMENT` or `"production"` (S7, S10) | EP-7 sets it from `NEXUS_ENV`. |
| `default_integrations` | `True` | `False` disables all default integrations and the auto-enabling ones unless added explicitly (S7, S8). |
| `auto_enabling_integrations` | `True` | Set `False` too. |
| `send_client_reports` | `True` | Sends counts of dropped events (S7); no event content. |
| `enable_logs` | `False` | Sentry Logs product (S10). Keep off. |
| `shutdown_timeout` | `2` s | Used by `flush()` when no timeout is given (S7, S10). |

**Default integrations in 2.73.0** (`integrations/__init__.py`, S10): argv, atexit, dedupe, excepthook, logging, modules, stdlib, threading. Asyncio is not a default.
- Argv "Adds `sys.argv` as an `extra` attribute"; Modules "Sends a list of installed Python packages"; Excepthook reports unhandled exceptions; Threading reports crashing threads; Stdlib adds breadcrumbs for outgoing `httplib` requests and `subprocess` spawns (S8).
- Logging: records at INFO and above become breadcrumbs, ERROR and above become events, and "each record's message text appears in the event" (S9). Any log line with chat text would leave the box.
- Auto-enabling integrations turn on when their library is installed. The 2.73.0 list includes anthropic, openai, google_genai, httpx, fastapi, starlette, mcp and others (S10). In the probe, httpx2, mcp and starlette switched on with no config because those packages were installed.

**What a default event carries** (probe, `capture_exception` with defaults): `contexts.runtime`, `contexts.trace`, `extra.sys.argv`, `modules` (82 packages), `server_name`, `breadcrumbs`, `sdk.integrations`, and frames with `abs_path`, `vars` and source lines. The exception `value` holds the message, so a chat line or token in `str(exc)` is sent. With integrations off and `include_local_variables=False`, `contexts.trace`, `server_name`, `sdk` and `abs_path` remain. The envelope header carried `trace: {environment, trace_id}`; with an allowlist `before_send` that drops `contexts`, the header had only `event_id` and `sent_at`.

**Threads and flush.** `HttpTransport.capture_envelope` submits to a `BackgroundWorker`: a daemon `threading.Thread`, `Queue(100)`, `put_nowait`, and the event is dropped when the queue is full (S10). `flush(timeout)` waits on that queue and logs "flush timed out, dropped N events" (S10). Event building, scrubbing and `before_send` run on the caller's thread (probe: `before_send` thread = MainThread). Because the worker is a daemon and our config turns off atexit, shutdown must call `flush` explicitly.

**Testing without network.** `make_transport` uses a `Transport` instance passed as `transport=` as-is (S10). A subclass that only implements `capture_envelope` records envelopes synchronously; no flush or sleep is needed (probe). Calling `sentry_sdk.init` again replaces the client, which isolated the probe's cases.

## 4. Fingerprinting and grouping (EP-5)
- "Events with the same fingerprint are grouped together into an issue." Set `event['fingerprint']` in `before_send` or `scope.fingerprint`. Including `{{ default }}` keeps Sentry's hash and adds to it; leaving it out replaces grouping (S12).
- EP-5 keys on the Sentry issue id. Whether an issue id survives a merge in the UI: **[UNVERIFIED]**.
- Dropping the exception message changes the inputs to default grouping. How much Sentry weighs the message when a stack trace is present: **[UNVERIFIED]**. A fingerprint of `["{{ default }}", component]` keeps grouping stable and under our control.

## 5. Reading issues for the daily routine
- REST API: Bearer token in `Authorization`; token types are internal-integration tokens, personal (user) tokens and OAuth tokens (S13). Reading issues and events needs `event:read`; `project:read` and `org:read` for project and org lookups (S14). A token with only these three scopes is read-only.
- API rate limits are per caller and endpoint, fixed-window plus concurrency, reported in `X-Sentry-Rate-Limit-*` headers. No numbers and no status code are given (S15): **[UNVERIFIED]**. A once-a-day digest is unlikely to hit them (estimate).
- MCP: getsentry/sentry-mcp; hosted at `https://mcp.sentry.dev/mcp` (scopable to an org or project), "All connections use OAuth" (S16). Stdio mode takes a user token; listed scopes include `project:write`, `team:write`, `event:write`. Tools can be narrowed with `--skills` / `--disable-skills` (inspect, triage, seer, project-management). Its AI search tools need an LLM provider key (S17). No read-only mode is documented: **[UNVERIFIED]**. The claude.ai Sentry plugin's OAuth scopes: **[UNVERIFIED]**.
- Recommendation: the routine reads with a read-only REST token (`event:read`, `project:read`, `org:read`) via a small script; the MCP is for the owner's interactive use. Issue titles and frames stay data, never instructions (EP-6).

## 6. GlitchTip as a drop-in (EP-7)
- "compatible with Sentry client SDKs"; works with "Sentry's open source client SDKs" (S18). Setup is "give it your DSN" (S22). Backend license: MIT (S20).
- Hosted free tier: 1,000 events a month, 30-day retention; over the limit it drops about 10% and blocks fully at twice the limit (S19). That is a fifth of Sentry's free errors.
- Unsupported SDK features, fingerprint support and API compatibility for the routine's reader are not stated on the pages read: **[UNVERIFIED]**. Treat "DSN change, not code change" as true for sending only; the reader script would need a GlitchTip check.

## 7. Caveats and gaps for this project
1. **Sim thread (EP-3).** The SDK scrubs on the calling thread. At 10 Hz a tick has 100 ms (SIM-CORE SC-2). The adapter must hand off `(exc, component, tags)` to its own bounded queue and do all SDK work on its own thread. A full queue drops and counts; it never blocks.
2. **Quota at 10 Hz.** One report per tick is 36,000 an hour (estimate), against 5,000 a month. Dedupe only drops consecutive duplicates (S8). The adapter needs a per-fingerprint limit (proposed: first report, then at most one a minute with a count tag). EP-5 still gets one ticket.
3. **Hostile chat text.** It reaches Sentry through the exception message, logging records, breadcrumbs, `extra` and locals. The allowlist removes all of them. Exceptions raised in the gateway must still not put chat text in `str(exc)`, because local logs keep it (THREAT-MODEL).
4. **Implicit capture.** With defaults, excepthook, threading and logging report without going through `ErrorReporter`, so EP-1 and EP-2 would be bypassed. `default_integrations=False` and `auto_enabling_integrations=False` close that. Unhandled thread exceptions then need our own hook into the port.
5. **LLM integrations.** anthropic, openai and google_genai auto-enable when installed (S10). With `data_collection` set they may send prompts (S7 mentions "generative AI content"). Turning off auto-enabling avoids this.
6. **Host identity on WSL2.** `server_name` is the hostname and `abs_path` holds the full path, which can include the Windows or WSL user name (probe, S10). Keep only repo-relative `filename`.
7. **Public MIT repo.** The DSN goes in `.env` per EP-7. Anyone who gets a DSN can send events and burn the quota (inference from S2's per-key limits; **[UNVERIFIED]** as a documented risk).
8. **One user.** The Developer plan has 1 user (S1). Agents need a token, not a seat.
9. **SDK 3.0.** `send_default_pii` goes away and Unraisablehook is listed as "SDK 3.0+" (S7, S8). Pin `sentry-sdk>=2.73,<3` and review 3.0 separately.
10. **Cost.** $0 holds on Developer if no paid add-ons are enabled. Spike protection and per-key limits on Developer are unconfirmed.

## 8. Proposed skeleton (proposal only, no code in the repo)
`nexus.errors` (leaf, no `sentry_sdk`): `ErrorReporter` protocol (`capture(exc, *, component, tags)`, `flush(timeout_s)`), `NoopReporter`, `LogReporter`, and a factory that returns `NoopReporter` (logging "error reporting off") when `SENTRY_DSN` is unset.

`nexus.errors.adapters.sentry.SentryReporter(dsn, environment, release, *, transport=None)`:
- `sentry_sdk.init(dsn=..., environment=NEXUS_ENV, release=<explicit>, server_name="nexus", default_integrations=False, auto_enabling_integrations=False, send_default_pii=False, include_local_variables=False, include_source_context=False, max_breadcrumbs=0, max_request_body_size="never", before_breadcrumb=drop_all, before_send=allowlist, transport=transport)`. No `data_collection`. `NEXUS_ENV` and the release are required config (DI-7); no defaults.
- `capture`: check tags against NX-026 rules (drop bad tags, never the report), build the fingerprint key, apply the rate limit, `put_nowait` to a `queue.Queue(maxsize=N)`. Full queue or any error: count it in a metric and return. Never raises.
- One daemon reporter thread: takes items and calls `capture_exception` inside an isolated scope with `component` and tags set. Catches everything.
- `allowlist(event, hint)` builds a new dict: `event_id`, `timestamp`, `level`, `platform`, `release`, `environment`, `tags`, `fingerprint`, and `exception.values[]` with only `type`, `module`, `mechanism.type` and frames of `filename` (repo-relative), `lineno`, `function`, `in_app`. No `value`, `abs_path`, `vars`, context lines, `contexts`, `extra`, `user`, `request`, `modules`, `breadcrumbs`, `server_name`, `sdk`. Any exception inside it returns `None` (the SDK also drops on raise, probe).
- `flush(timeout_s)`: `sentry_sdk.flush(timeout=timeout_s)` after draining our queue; called from the shutdown path.
- Import-linter: the N-1 contract allows `sentry_sdk` only in `nexus.errors.adapters.*`; EP-4 contract: `nexus.core` never imports `nexus.errors`.
- New dependency: `sentry-sdk` (MIT, S6), justified in the PR per AGENTS rule 8.

**EP-2 test (proposed).** A `RecordingTransport(Transport)` with `capture_envelope` appending to a list, passed as `transport=`. Put a token, a chat line and a username in the exception message, a local variable, `add_breadcrumb`, `set_extra`, `set_user`, `set_context` and a `logging.error` record. Call `capture` and the reporter thread's handler directly (no thread in the test). Serialize every envelope item to JSON and assert none of the three strings appears, and that `server_name`, `modules`, `sys.argv` and `abs_path` are absent. Second test: a `before_send` that raises sends nothing. Third: a tag that breaks NX-026 never reaches the transport. EP-3 test: a reporter whose queue is full or whose transport blocks leaves `capture` returning within budget.

## 9. Open questions for the owner
1. **Account.** Create the Sentry org yourself (1 user on Developer), or apply for the open-source sponsorship (S21)? Either way, a person has to create it; agents can't.
2. **Data region.** US or EU? It is fixed at org creation (S5).
3. **Token for the routine.** OK to create a read-only token (`event:read`, `project:read`, `org:read`) stored as a secret for the daily routine, separate from the MCP's OAuth?
4. **Spike protection.** After the org exists, please confirm in Settings whether spike protection and per-key rate limits are available on Developer, so §2's unverified items close.

## 10. Sources (all accessed 2026-10-23)
| Id | Source |
|---|---|
| S1 | https://sentry.io/pricing/ |
| S2 | https://docs.sentry.io/pricing/quotas/ |
| S3 | https://docs.sentry.io/pricing/quotas/spike-protection/ |
| S4 | https://docs.sentry.io/pricing/ |
| S5 | https://docs.sentry.io/organization/data-storage-location/ |
| S6 | https://pypi.org/pypi/sentry-sdk/json (2.73.0 metadata; 3.0.0b1 upload 2026-10-21) |
| S7 | https://docs.sentry.io/platforms/python/configuration/options/ |
| S8 | https://docs.sentry.io/platforms/python/integrations/default-integrations/ |
| S9 | https://docs.sentry.io/platforms/python/integrations/logging/ |
| S10 | `sentry_sdk-2.73.0-py3-none-any.whl` from PyPI (S6): `integrations/__init__.py`, `client.py`, `transport.py`, `worker.py`, `consts.py`, `serializer.py`, `api.py` |
| S11 | Probe scripts run on the S10 wheel, fake transport, Python 3.13.16 (results quoted as "probe") |
| S12 | https://docs.sentry.io/platforms/python/usage/sdk-fingerprinting/ |
| S13 | https://docs.sentry.io/api/auth/ |
| S14 | https://docs.sentry.io/api/permissions/ |
| S15 | https://docs.sentry.io/api/ratelimits/ |
| S16 | https://mcp.sentry.dev/ (redirect from https://docs.sentry.io/product/sentry-mcp/) |
| S17 | https://github.com/getsentry/sentry-mcp |
| S18 | https://glitchtip.com/ |
| S19 | https://glitchtip.com/pricing |
| S20 | https://gitlab.com/glitchtip/glitchtip-backend |
| S21 | https://sentry.io/for/open-source/ |
| S22 | https://glitchtip.com/sdkdocs |
