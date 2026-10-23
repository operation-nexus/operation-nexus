# Data Integrity Policy — No Fabricated Data

Status: **MANDATORY** (owner rule, 2026-10-17) · Applies to: all code, docs, tests, agents, and humans

> **Never fabricate, invent, or hallucinate data.** If a value doesn't exist, say so or leave it empty. A default or fallback is allowed only when it is required and there's an obvious, honest choice. Every one must be listed in the registry (§4).

## 1. Why this matters here
This project is an always-on broadcast. A made-up number shown to viewers (a fake leaderboard entry, an invented kill count, a placeholder "Commander" name, a guessed quota value) is a visible lie, and it hides real bugs. Silent fallbacks turn crashes into wrong-but-plausible output that nobody notices for days.

## 2. Rules for runtime code (backend and frontend)

| ID | Rule | Example (wrong → right) |
|---|---|---|
| DI-1 | **Missing data is shown as missing.** Represent it explicitly as `None`/`null`, or as a typed `Unknown`/`Unavailable` state. The UI renders an honest empty state such as `—`, "NO DATA", or "UPLINK LOST". | `rank = row.get("rank", "O-1")` → `rank: Rank \| None`; overlay shows `—` |
| DI-2 | **No silent fallbacks.** A failed lookup, parse, or call raises a typed error or returns a typed failure result, and logs it. It never substitutes a plausible value. | `except Exception: return []` → `except ParseError as e: log.warn(...); return Rejected(reason=...)` |
| DI-3 | **No placeholder, mock, sample, or seed data in production paths.** Fixtures live only under `tests/` or `tools/fixtures/` and are named as fixtures. Production code that imports them fails CI. | No `DEMO_COMMANDERS = [...]` in `nexus/` |
| DI-4 | **No synthetic padding of displays.** Leaderboards, panels, and tickers show only real entries. Three real commanders means three rows, not ten with filler. | — |
| DI-5 | **NPC/AI actors are labeled as AI.** The AI garrison, NPC wingmen, and the director carry a visible AI marker and never pose as human viewers. Viewer counts, "active commanders" and similar metrics count humans only. | NPC wingman shows `[AI] GHOST` |
| DI-6 | **Derived numbers come from real inputs.** Momentum, CP, XP, and stats are computed from sim state and events, never estimated or smoothed into existence when the inputs are missing. If an input is missing, the derived value is `Unknown`. | — |
| DI-7 | **Config values are explicit.** Required config has no code default. Startup fails loudly when it's missing (fail fast). Balance values live in `balance/*.yaml` and are marked `# PROPOSED – unvalidated` until the balance harness validates them. | `TICK_RATE = os.getenv("TICK_RATE", 10)` → required key in validated config |
| DI-8 | **External data is never guessed.** Platform user ids, display names, quotas, and prices come from the platform API response, or are absent. They're never inferred. | — |
| DI-9 | **LLM output isn't data until validated.** It passes the schema and range checks and is labeled as generated (narration). It never becomes a fact such as a stat, a name, or a count. | — |

## 3. Allowed defaults and fallbacks (only these kinds)
A default or fallback is allowed when **all** of these hold:
1. The system needs a value to operate (not just to look nicer).
2. The value is obviously correct or neutral, and isn't a guess about the world.
3. It's visible: logged when used, and shown on the overlay if it affects what viewers see.
4. It's listed in the registry below, with the reason.

Examples that qualify:
- Generated callsign `VIPER-27` instead of a raw display name. This is a safety requirement, and the callsign is clearly a callsign, not a claim about the user.
- The rule-based director choice when the LLM advisor times out. Gameplay requires a decision, and the rules are the source of truth anyway (ADR-0007).
- Empty list or zero for "no events yet" when it's truly zero, not unknown.

## 4. Registry of approved defaults and fallbacks
| ID | Where | Default / fallback | Why it's necessary and honest | Visible how |
|---|---|---|---|---|
| FB-1 | Identity | Generated callsign | Raw names are unsafe to broadcast (SEC-MOD-1) | It is the callsign |
| FB-2 | Director | Rule pick when advisor late/invalid | A decision is required every window | `advisor_fallback` metric + log |
| FB-3 | Narration | Template line when LLM unavailable | The sitrep content is real (from events). Only the wording falls back | Log |
| FB-5 | Support redemptions | Owner-entered FX table (`support.fx_table`, dated) to compare currencies, **only if the owner enables it** | Lets one rule cover several currencies without a live FX feed. The values are owner-entered and dated, never guessed. | Admin UI labels "owner-set FX, as of <date>"; every use is logged |
| FB-4 | Overlay | Last good frame + "COMMS RESYNC" banner on WS loss | The stream must not show broken UI | Banner text says so |
| FB-6 | Combat | Pk multiplier 1.0 for factors not built yet: radar lock, jamming, countermeasures, weather and night (COMBAT §5.2) | The factor is real design but has no unit or phase producing it yet; 1.0 means "no effect", not a guessed value. Owner-approved 2026-10-20 (Q-GP-6, Q-CBT-10). Each entry is removed when its factor is built (Q-CBT-20). | Listed in COMBAT §5.2; the PiP Pk shows only built factors |
| FB-7 | Error reporting | The log adapter when `SENTRY_DSN` is set but the Sentry adapter is not built yet (NX-364 part 1, Q-DEV-24) | Reports must not be dropped silently; the structured log line (allowlisted fields only) is the honest local record | A startup warning "SENTRY_DSN is set but the Sentry adapter is not built yet; using the log adapter" (the DSN itself is never logged); removed when the Sentry adapter lands |
| FB-8 | Error store (NX-392) | A capture of a **new** fingerprint is dropped once the local error store holds 1000 fingerprints (known fingerprints keep counting); a failed store write is dropped the same way | Bounds the store file and the flood issue body; a crash path must never block or raise (ERROR-PIPELINE EP-3, EP-8) | A warning "error store full, capture lost (N fingerprints)" (or the write failure's type) in the log |
| FB-9 | Error store and issues (NX-392) | `release` is null when `NEXUS_RELEASE` is unset or not id-shaped | A release id is never invented (DI-8); the issue says so instead | The issue body shows "none recorded"; a startup warning (without the value) when it is set but invalid |

New entries need owner approval in the PR that introduces them.

## 5. Rules for documentation and agents
- **DOC-1** Every factual claim about an external system (APIs, quotas, prices, licenses, hardware limits) cites a source URL and an access date, or is marked **[UNVERIFIED]**.
- **DOC-2** Numbers we made up (targets, budgets, balance values, estimates) are labeled as **proposed**, **target**, or **estimate**. They're never stated as facts.
- **DOC-3** Agents must not invent file paths, APIs, function names, library versions, CLI flags, or config keys. Check them in the repo or the official docs (use Context7 or the docs) before using them. If you can't verify something, say so.
- **DOC-4** Agents report what they actually ran and saw. "Tests pass" requires the command and its output. A skipped step must be stated as skipped.
- **DOC-5** Commit messages, PR descriptions, and tracker updates describe only work that was actually done.

## 6. Enforcement
- **Semgrep rules** (`.semgrep/data-integrity.yml`, NX-046):
  - Flag `except …: pass` and bare `except Exception` that returns a value.
  - Flag `.get(key, <non-None literal>)` and `os.getenv(…, <default>)` in `nexus/`. These require an `# FB-n` registry comment to be allowed.
  - Flag imports from `tests/` or `fixtures` in production packages.
  - Flag the literal names `lorem`, `dummy`, `placeholder`, `sample_`, `fake_`, and `mock_` outside `tests/`.
- **Type system:** `mypy --strict` means no implicit `Any`. Optional values must be handled explicitly.
- **Review checklist:** a data-integrity section (REVIEW-CHECKLIST).
- **Tests:** each FB-n has a test proving the fallback is logged and visible.
