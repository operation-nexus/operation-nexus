# Error tracking options: alternatives to Sentry, agent access, build vs buy (2026-10-23)

Status: Research note, not a decision; Q-DEV-24, NX-364 · Spec: ERROR-PIPELINE (EP-1..EP-7) · ADR-0010 · Companion: `SENTRY-RESEARCH-2026-10-23.md` (#283)

Owner's question (2026-10-23): are there Sentry alternatives, AI-enabled skills, MCPs, connectors or direct integrations, and what is the payoff of our own simpler version? Constraints: $0 for now, data stored in the US only, public MIT repo, single-threaded 10 Hz Python 3.12 sim on WSL2, chat text never leaves the box, agents (cloud, desktop, daily routine) read errors and open `error` issues.

All sources were read on 2026-10-23 and are listed in §10 by id (A1..A38; no A12). Sentry facts are not repeated; they are cited as "Sentry note". Anything not confirmed in a primary source is marked **[UNVERIFIED]**. Line and PR counts are **estimates**.

## 1. Summary
- Every Sentry-compatible server (GlitchTip, Bugsink, Better Stack, self-hosted Sentry) takes the same `sentry-sdk` and the same allowlist `before_send`. So the Sentry skeleton adapter is not wasted work: it is the adapter for all of them (A3, A6, A11).
- GlitchTip is the best Sentry drop-in for us: backend MIT, self-host from 256-512 MB RAM with PostgreSQL only (A4), hosting offered in the US and EU (A2), and a built-in MCP server on self-hosted instances (A5). Hosted free tier is only 1,000 events a month (A2).
- Self-hosted Sentry needs 4 cores and 16 GB RAM plus 16 GB swap, and is FSL-licensed (A1). Too heavy for our Linux server's other jobs (estimate).
- Bugsink is light and Sentry-compatible but uses the PolyForm Shield licence (A8), and its hosted plan is EU only (A6). Hosted is ruled out by the US-only constraint; self-host is possible.
- Hosted free tiers with a US region and an official MCP server: PostHog (100k exceptions a month, US Cloud, read-only MCP mode; A13-A16) and Honeybadger (5k errors, 15 days; MCP with read-only grant; A20, A22). Better Stack has 100k exceptions free and an MCP, but the free-tier region is not stated (A10, A11).
- OpenTelemetry logs give a vendor-neutral path. We build the log record ourselves, so EP-2 is easy. We lose issue grouping unless the backend adds it (A26). Our planned Loki + Grafana (Q-ARCH-11) can store these, and `mcp-grafana` reads Loki with a `--disable-write` flag (A27).
- Cloud agents cannot reach anything on the owner's LAN. A push model (the host writes to GitHub issues) works for every agent; a pull model (the routine reads a tracker) needs a hosted tracker or an exposed endpoint.
- **Recommendation (lead to confirm), §8:** build the simple version now (the NX-364 part 1 log adapter + local fingerprint store + host-side issue sync), keep the Sentry-SDK adapter as a skeleton behind the same port, and choose at NX-255 between self-hosted GlitchTip and hosted Sentry with the open-source sponsorship.

## 2. Comparison
"Scrub" = can we enforce the EP-2 allowlist before data leaves the process. "Agent" = documented way for an agent to read errors.

| Option | Cost (free tier) | US region | EP-2 scrub | Agent / MCP access | AI features | Licence | Notes |
|---|---|---|---|---|---|---|---|
| **Build our own** (§7) | $0 | Host + GitHub only | Full: we write every field | `gh` issues (all agents) | None of its own | MIT (ours) | We maintain it |
| Sentry hosted | 5k errors/mo, 1 user (Sentry note) | Yes, fixed at org creation (Sentry note) | Allowlist `before_send` works (Sentry note) | Official MCP; no documented read-only mode (Sentry note) | Seer not on free plan (Sentry note) | SDK MIT | OSS sponsorship possible (Sentry note) |
| Sentry self-hosted | Server cost only | Our box | Same SDK | Same MCP **[UNVERIFIED]** for self-host | **[UNVERIFIED]** | FSL, Apache-2.0 after 2 years (A1) | 4 cores, 16 GB RAM + 16 GB swap minimum (A1) |
| GlitchTip hosted | 1,000 events/mo, 30 days (A2) | US and EU offered (A2) | Same SDK | MCP on hosted: **[UNVERIFIED]** | None found | Backend MIT (Sentry note) | $15/mo for 100k (A2) |
| GlitchTip self-hosted | Server cost only | Our box | Same SDK | Built-in MCP, `GLITCHTIP_ENABLE_MCP=True`, OAuth or API token; has write tools (A5) | None found | MIT | 256-512 MB RAM, PostgreSQL 14+, Valkey optional (A4) |
| Bugsink self-hosted | Server cost only | Our box | Same SDK (A6) | Community MCPs only (A9) **[UNVERIFIED]** quality | None found | PolyForm Shield 1.0.0 (A8) | SQLite option (A7); PyPI 2.6.2, 2026-10-22 (A28) |
| Bugsink hosted | 15k events/mo, 1 user (A6) | No: "EU (GDPR-friendly)" (A6) | Same SDK | As above | None found | As above | Ruled out (US-only) |
| Better Stack | 100k exceptions/mo; logs 3 GB, 3 days (A10) | Free tier region not stated **[UNVERIFIED]** | Takes Sentry SDK (A11) | Official MCP (A11) | "AI-native", prompts for coding agents (A11) | **[UNVERIFIED]** | Retention on free tier unclear (A10) |
| PostHog | 100k exceptions/mo (A14) | US Cloud and EU Cloud (A14) | No `before_send` on the page read **[UNVERIFIED]**; autocapture is opt-in (A15) | Hosted MCP, read-only and project-pinned modes (A16, A17) | Example prompts suggest fixes (A16) | SDK MIT (A29) | Product analytics suite; claude.ai plugin (§5) |
| Honeybadger | 5k errors/mo, 15 days, 1 user (A20) | EU region exists; US default **[UNVERIFIED]** | `before_notify` rewrites; drop unconfirmed (A21) | Official MCP, hosted, read-only grant (A22) | None found | SDK MIT (A29) | |
| Rollbar | 5k occurrences/mo, 30 days (A18) | Not stated **[UNVERIFIED]** | Payload handler can modify or drop (A19) | Official MCP, read-scope token (A30) | None on pricing page (A18) | SDK MIT (A29) | MCP "under active development" (A30) |
| Bugsnag | 7.5k events/mo (inferred), 1 user, 7 days (A23) | Not stated **[UNVERIFIED]** | **[UNVERIFIED]** | **[UNVERIFIED]** | **[UNVERIFIED]** | SDK MIT (A29) | |
| Grafana Cloud | Logs 50 GB/mo, 14 days, 3 users; Frontend Obs 50k sessions (A24) | US regions exist; free-tier choice **[UNVERIFIED]** (A25) | We build OTel/Loki records (full) | `mcp-grafana`, Apache-2.0, `--disable-write` (A27) | Grafana Assistant on free (A24) | | No error grouping UI found **[UNVERIFIED]** |
| Axiom | 30-day retention; "500 GB/mo data loading compute" (A31) | US East 1 exists; free choice **[UNVERIFIED]** (A32) | We build records (full) | "MCP server" on Personal (A31) | "SRE skill" (A31) | | Logs store, not an issue tracker |
| Datadog | Free infra: 5 hosts, 1-day metrics; no free logs seen (A33) | **[UNVERIFIED]** | **[UNVERIFIED]** | **[UNVERIFIED]** | **[UNVERIFIED]** | | Error Tracking free tier not found; skip |

Not covered: AppSignal (no source read). Highlight: `highlight.io` now redirects (308) to `launchdarkly.com` (A34); standalone status **[UNVERIFIED]**, skipped.

## 3. Sentry-compatible drop-ins
- **What carries over.** All of them accept the Sentry SDK by DSN (A3, A6, A11). The EP-2 allowlist, the own-queue EP-3 thread and the per-fingerprint rate limit from the Sentry note stay the same. EP-7's "DSN change, not code change" holds for sending.
- **What does not.** The routine's reader. Each server has its own API and MCP. GlitchTip's MCP is built in (A5); Bugsink has only community MCPs (A9). Which Sentry SDK features each server ignores is not documented on pages read: **[UNVERIFIED]**.
- **Missing vs Sentry.** None of the pages read list gaps. Seer-style AI root cause was not found on GlitchTip or Bugsink pages.
- **GlitchTip self-host** fits the Linux server (Q-ARCH-11 already runs Grafana and Loki there). Data never leaves owner hardware, so the US rule is met trivially. Cost: one more service to back up and patch.
- **Bugsink licence.** PolyForm Shield bars using it to compete with Bugsink (A8). Self-hosting for our own errors looks fine, but this is not legal advice: **[UNVERIFIED]**. It is not OSI open source, unlike GlitchTip (MIT).

## 4. Hosted alternatives
- **US region.** Confirmed US options: Sentry (Sentry note), GlitchTip (A2), PostHog (A14), Grafana Cloud paid regions (A25), Axiom US East 1 (A32). The rest are unstated on pages read.
- **Scrub control.** Sentry-SDK vendors give the strongest, tested control (Sentry note). Rollbar documents a drop-or-modify handler (A19). Honeybadger documents rewrite only (A21). PostHog and Bugsnag: not confirmed. For an unconfirmed SDK, we would build a minimal payload ourselves and never pass the raw exception: **[UNVERIFIED]** whether each SDK allows that.
- **Free tiers by volume.** PostHog and Better Stack 100k a month; Bugsink 15k (EU only); Bugsnag 7.5k; Sentry, Rollbar, Honeybadger 5k; GlitchTip 1k (sources in §2). Our rate limit (Sentry note §7) makes 1k-5k enough once the code is stable (estimate).
- **Account rule.** Each needs an account the owner creates; agents use tokens, not seats.

## 5. OpenTelemetry route
- **How.** Record exceptions as attributes on a LogRecord: `exception.type`, `exception.message`, `exception.stacktrace` (Stable) (A26). We simply omit `exception.message` (the spec itself warns it "may contain sensitive information", A26) and write a trimmed, repo-relative stack.
- **Backends.** SigNoz: MIT outside `ee/` (A35), self-host, lists exceptions as a signal (A36). HyperDX/ClickStack: MIT, ClickHouse + MongoDB + OTel collector, "at least 4GB of RAM and 2 cores for testing" (A37). Grafana Loki: already planned self-hosted (Q-ARCH-11, OPS-ADMIN).
- **Gain.** Vendor-neutral wire format (fits ADR-0010); `opentelemetry-sdk` is Apache-2.0, 1.45.1 (A38); one pipeline for logs and errors; backend swap is config.
- **Lose.** Issue grouping, first/last seen and resolve state are tracker features. Loki stores lines; it does not group. SigNoz and HyperDX grouping quality: **[UNVERIFIED]**. A new dependency for little gain over JSON lines that `nexus.obs` already writes.

## 6. AI-enabled agent access
**Official MCP servers found:**
| Vendor | Server | Read-only | Source |
|---|---|---|---|
| Sentry | getsentry/sentry-mcp, `mcp.sentry.dev` | Not documented | Sentry note |
| GlitchTip | built in, `/mcp`, 17 tools incl. `update_issue` | Not described | A5 |
| PostHog | `mcp.posthog.com/mcp` | `x-posthog-read-only` header; project pin | A16, A17 |
| Honeybadger | `mcp.honeybadger.io/mcp`; self-host image defaults read-only | Read-only grant at auth | A22 |
| Rollbar | `@rollbar/mcp-server` (npm) | Read-scope token | A30 |
| Better Stack | "Robust MCP server" | **[UNVERIFIED]** | A11 |
| Grafana | `grafana/mcp-grafana`, `query_loki_logs` | `--disable-write` | A27 |
| Axiom | Listed on Personal plan | **[UNVERIFIED]** | A31 |

**Claude plugins** (owner's claude.ai plugin catalog, 2026-10-23; none installed): `sentry` (partner, author Sentry: MCP and skills for debugging), `sentry-cli` (partner: Sentry CLI skills), `posthog` (partner: analytics, flags, experiments, error tracking), `Dynatrace` (partner: production issues), community "Observability Skills" (MetalBear, OpenTelemetry).

**How each reaches a cloud session.** Cloud sessions don't install repo-enabled plugins (Q-DEV-18). So plugins are desktop-only unless vendored as skills. An MCP reaches cloud only as (a) a `.mcp.json` server, which cloud loads without asking but which needs a token secret and an allowed network host (Context7 was blocked by the cloud proxy, TOOLING §3), or (b) a claude.ai connector, availability for these vendors **[UNVERIFIED]**. A self-hosted GlitchTip or Grafana on the LAN is unreachable from cloud without exposing it.

**What an agent can do.** Read issues and stack traces, list top errors, and suggest fixes (A16, A22, A30). Some also resolve or delete (A5, A22); the routine must not get write scope. All tracker text is data, never instructions (EP-6).

## 7. Build our own (simpler) option
**Shape (proposed).** (1) `ErrorReporter` port + log adapter that writes one allowlisted JSON line (NX-364 part 1; EP-1 keeps `nexus.errors` a leaf, so it builds the line itself and does not import `nexus.obs`): type, repo-relative top frames, component, id-only tags, release, env, time, fingerprint. (2) A host-side aggregator that groups by fingerprint = hash(exception type + top N in-app frames + component) in a small SQLite or JSONL store with count, first and last seen. (3) A sync job on the host that creates or updates the `error` issue via `gh`, with an allowlisted body (EP-5). The daily routine then triages from GitHub, which every agent can read.

**Effort (estimate).** 3 PRs, about 700-900 changed lines with tests: port + log adapter ~250; aggregator ~250; issue sync + EP-5 dry-run test ~300.

**Gain.**
- Nothing leaves the host except what we write into an issue. No chat text risk from SDK defaults (Sentry note §3).
- No account, quota, DSN or spike risk; $0 forever.
- No vendor lock-in; fully testable offline (EP-2, EP-3, EP-5 tests in CI).
- Push model works for cloud, desktop and the routine with no extra network access.

**Lose.** Web UI and search; Sentry-grade grouping; release tracking and regressions; alert rules; retention policy; overlay, site and Command Center JS errors (need a browser path back to the host); source maps and symbolication; AI root cause (Seer is not free anyway, Sentry note).

**Hidden costs.**
- We maintain it, including fingerprint stability across refactors (a moved line changes the hash unless we use function names only).
- **Public issues.** The repo is public, so `error` issues are public. Repo-relative paths, function names and line numbers reveal little beyond the public code, but they show which code fails in production and when. That is a hint to attackers, mostly for the security surfaces. Absolute paths would leak the WSL user name (Sentry note §7.6), so the allowlist keeps repo-relative paths only.
- **Private ops repo.** NX-299 plans `operation-nexus-ops` (private). Issues there hide traces, but the daily routine, `gh` token and EP-6 fix flow then span two repos. NX-299 is not done yet.
- **Spec tension.** EP-5 says the routine creates issues and EP-5's fingerprint lists "Sentry issue id". A cloud routine cannot read host logs, so the host must push issues (or a digest). This needs a small spec change.

## 8. Build vs buy
**Recommendation (lead to confirm).**
1. **Now (NX-364 part 1):** build our own: port and log adapter (part 1, in review), then a local fingerprint store, host-side issue sync with an allowlisted body. Reasons: $0, no data leaves except the issue text, works for every agent, fully testable, and it is the Q-DEV-24 (b) choice already.
2. **Early skeleton (Q-DEV-24):** keep the Sentry-SDK adapter with the allowlist `before_send`, tested against a recording transport only (no DSN). It serves Sentry, GlitchTip, Bugsink and Better Stack alike.
3. **At NX-255 (first 24/7 deploy):** pick one backend by config (ADR-0010 N-5): self-hosted GlitchTip on the Linux server (MIT, light, data on owner hardware, built-in MCP for desktop) or hosted Sentry US with the OSS sponsorship (better grouping, official plugin, reachable from cloud). Keep the local aggregator either way as the fallback and the issue writer.
4. **Skip for now:** OTel exporters (no grouping gain over our JSON lines), Bugsink (licence), self-hosted Sentry (16 GB RAM), PostHog and Honeybadger (no extra value over the above for a Python backend; revisit for browser JS errors).

**Hybrid payoff.** The hybrid costs one extra adapter (estimate ~150 lines) and keeps the buy option open with no lock-in. Building alone loses JS errors and a UI; buying alone puts the account and quota on the critical path before we need them.

## 9. Open questions for the owner
Already answered (owner, 2026-10-23):
- Data region: US only (project is US-based, English first).
- Accounts: the owner creates one only after research says it is worth it; if Sentry is chosen, the owner applies for the open-source sponsorship.
- Read-only token and spike-protection check: only if a hosted service is chosen.

Still open:
1. **Where do `error` issues live?** Public repo with allowlisted, repo-relative frames, or the private ops repo (NX-299) for all or only security-surface errors?
2. **Who writes issues?** OK to amend EP-5 so a host-side job pushes issues and the routine triages, instead of the routine pulling from a tracker?
3. **NX-255 backend.** Self-hosted GlitchTip on the Linux server, or hosted Sentry US? (Decide later; this note recommends deferring.)
4. **Browser errors.** Do overlay, site and Command Center JS errors need capture before NX-255, or can they wait?

## 10. Sources (all accessed 2026-10-23)
| Id | Source |
|---|---|
| A1 | https://develop.sentry.dev/self-hosted/ |
| A2 | https://glitchtip.com/pricing |
| A3 | https://glitchtip.com/ (via Sentry note S18) |
| A4 | https://glitchtip.com/documentation/install |
| A5 | https://glitchtip.com/documentation/mcp |
| A6 | https://www.bugsink.com/ |
| A7 | https://www.bugsink.com/docs/installation/ |
| A8 | https://raw.githubusercontent.com/bugsink/bugsink/main/LICENSE |
| A9 | https://glama.ai/mcp/servers/j-shelfwood/bugsink-mcp (community listing; not vendor) |
| A10 | https://betterstack.com/pricing |
| A11 | https://betterstack.com/docs/errors/ |
| A13 | https://posthog.com/pricing (truncated; no figures read) |
| A14 | https://posthog.com/docs/error-tracking/pricing |
| A15 | https://posthog.com/docs/error-tracking/installation/python |
| A16 | https://posthog.com/docs/model-context-protocol |
| A17 | https://posthog.com/docs/model-context-protocol/faq |
| A18 | https://rollbar.com/pricing/ |
| A19 | https://docs.rollbar.com/docs/python |
| A20 | https://www.honeybadger.io/plans/ |
| A21 | https://docs.honeybadger.io/lib/python/errors/filtering-sensitive-data/ |
| A22 | https://docs.honeybadger.io/resources/mcp/ |
| A23 | https://www.bugsnag.com/pricing/ |
| A24 | https://grafana.com/pricing/ |
| A25 | https://grafana.com/docs/grafana-cloud/security-and-account-management/regional-availability/ |
| A26 | https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs/ |
| A27 | https://github.com/grafana/mcp-grafana |
| A28 | https://pypi.org/pypi/bugsink/json |
| A29 | https://pypi.org/pypi/{posthog,rollbar,honeybadger,bugsnag}/json (licence metadata or classifiers) |
| A30 | https://docs.rollbar.com/docs/mcp-server-setup |
| A31 | https://axiom.co/pricing |
| A32 | https://axiom.co/docs/reference/regions |
| A33 | https://www.datadoghq.com/pricing/ (first 100k characters read) |
| A34 | https://www.highlight.io/ (308 redirect to launchdarkly.com) |
| A35 | https://raw.githubusercontent.com/SigNoz/signoz/main/LICENSE |
| A36 | https://github.com/SigNoz/signoz |
| A37 | https://github.com/hyperdxio/hyperdx |
| A38 | https://pypi.org/pypi/opentelemetry-sdk/json |
| — | Owner's claude.ai plugin catalog, 2026-10-23 (not a public URL; relayed by the lead) |
