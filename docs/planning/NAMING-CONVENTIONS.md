# Naming Conventions

Status: Draft · Tracker: NX-315 (done), NX-323 (owner rulings) · Related: [GLOSSARY.md](GLOSSARY.md) (what words mean), CONTRACTS §3 (wire
conventions), ADR-0009 and CICD-ARCHITECTURE §2 (branches and commits)

This page records the case style each layer **already uses** in the specs and the repo (surveyed 2026-10-18). It is
descriptive: where usage is inconsistent, §3 lists the inconsistency instead of picking a winner. Settling those is an
owner call (grill pass, NX-323). New names follow the dominant style in §1 and §2.

## 1. Code, contracts and config

| Layer | Style | Examples | Source |
|---|---|---|---|
| Config keys (balance, runtime) | Dotted path of lowercase `snake_case` segments, `<area>.<name>`; durations and quantities end in a unit suffix (`_s`, `_min`, `_h`, `_days`, `_ticks`, `_m`, `_pct`, `_frac`, `_mult`, `_per_min`, `_per_hour`); variable segments in angle brackets | `presence.idle_handoff_min`, `tasking.claim_lease_s`, `season.overtime_cap_days`, `director.cp.unit_value.<unit_kind>` | CONFIG-AND-CONTENT |
| Enum values written in config or chat | lowercase `snake_case` | `campaign.objective_mode: timed`, `campaign.intermission.mode: auto_advance`, `orientation: west_to_east`, `!join strike hold` | CONFIG-AND-CONTENT §6.6; GAMEPLAY §3, §9a |
| Enum types (contracts) | `PascalCase` | `PauseReasonCategory`, `ThreatTier`, `CommandKind` | CONTRACTS §3.1, §3.3 |
| Enum values (contracts, DB `CHECK` lists) | `UPPER_SNAKE` | `CEASEFIRE`, `MISSION_KILL`, `TOTAL_DOMINATION`, `TOMBSTONE` | CONTRACTS §3.1 |
| Schema titles, wire message `type` | `PascalCase` | `ChatEnvelope`, `Hello`, `Snapshot`, `Hud` | CONTRACTS §3.1, §7 |
| Fields (wire, Python, TS, DB columns) | `snake_case` everywhere; TS does not camelCase | `arrival_seq`, `reason_category`, `taunt_opt_out` | CONTRACTS §3.1 |
| Sim events (`kind`) | `PascalCase`, usually `<Subject><PastVerb>` | `UnitSpawned`, `CampaignClockPaused`, `JobClaimed`, `NodeCaptured` | CONTRACTS §6 |
| Commands (`CommandKind`) | `UPPER_SNAKE`; staff commands start `STAFF_`, system commands `SYS_`; chat and advisor commands have no prefix | `JOIN`, `SET_CALLSIGN`, `STAFF_CAMPAIGN_PAUSE`, `SYS_SET_CALLSIGN`, `ADVISOR_CHOICE` | CONTRACTS §5 |
| Reject reasons | `UPPER_SNAKE` | `UNIT_IN_SORTIE`, `CAMPAIGN_PAUSED` | CONTRACTS §5.3 |
| Admin API routes | `/admin/<group>/…`, lowercase `kebab-case` segments, `{id}` path params | `POST /admin/kill-switch`, `POST /admin/commanders/{id}/purge-units` | CONTRACTS §8 |
| Admin roles | `UPPER_SNAKE` | `OWNER`, `ADMIN`, `GAME_MASTER` | ADMIN-RBAC §4.1 |
| Permissions | Dotted lowercase `snake_case`, same shape as config keys | `mod.ban`, `users.view_pii`, `campaign.pause` | ADMIN-RBAC §4.2 |
| DB tables, views | Plural `snake_case` tables; views start `v_` | `commanders`, `platform_identities`, `tasking_jobs`, `v_auto_assists` | DATA-MODEL |
| Python modules | `nexus.<module>`, lowercase | `nexus.commands`, `nexus.ops`, `nexus.clips` | SYSTEM-DESIGN §4 |
| RNG sub-streams | One lowercase word | `combat`, `objective`, `tasking` | SIM-CORE SC-5 |
| Ids with a fixed format | See CONTRACTS §3.2: node and sector ids are lowercase kebab slugs; callsigns are `^[A-Z][A-Z0-9-]{2,11}$` (`WORD-NN` when generated); rank ids `O-1`…`O-6` | `VIPER-27`, `O-3` | CONTRACTS §3.2, PROGRESSION §3 |
| Release tags | `<deployable>-v<semver>`, created by release-please only | `sim-v1.4.0` | CICD-ARCHITECTURE §2 |

## 2. Chat, docs and process

| Layer | Style | Examples | Source |
|---|---|---|---|
| Chat commands | `!` plus one lowercase word; required args `<arg>`, optional `[arg]`, choices `a\|b`; aliases are config | `!join <role> [hold]`, `!me` (alias `!status`), `!quiet` | GAMEPLAY §3 |
| On-stream names | Title Case display names over plain internal ids (TS-4); fixed HUD labels in capitals | Striker, Quorum Marshal; "NEEDED: supply to WEST FOB", "SIGNAL SOURCE: NULL" | GAMEPLAY §2, §3; OVERLAY |
| Lore names in prose | "the Quorum", "the Static" (lowercase "the" mid-sentence); possessive "the Quorum's board"; adjective "Quorum forces", "Quorum intel" | | GLOSSARY lore table |
| Spec requirement IDs | `<PREFIX>-<n>`, one prefix per spec, bold at the definition; an inserted requirement takes a letter suffix (`OA-10a`); security requirements are `SEC-<AREA>-<n>` | `GP-4`, `TB-1`, `FB-UX-3`, `OV-2b`, `SEC-LLM-4` | each spec |
| Owner questions | `Q-<AREA>-<n>`; area is a short capitalised code, numbered per area, never reused | `Q-BRAND-7`, `Q-ALN-31`, `Q-CI-6` | OPEN-QUESTIONS |
| Tracker items | `NX-###` (three digits), stable, never reused; GitHub issue title `NX-###: …` | `NX-315` | TRACKER, ISSUE-WORKFLOW |
| ADR files | `NNNN-kebab-title.md`; referenced as `ADR-NNNN` | `0009-branching-strategy.md` | adr/README |
| Doc files | `UPPER-KEBAB.md`; owner context drops `YYYY-MM-DD-short-topic.ext` | `NAME-CLEARANCE.md` | docs/README, `.agents/README.md` |
| Branches | `<type>/<slug>`, type one of `feat`, `fix`, `docs`, `chore` (from `develop`) or `hotfix` (from `main`); feature branches carry the tracker id | `feat/NX-123-short`, `docs/naming-pass`, `hotfix/…` | ADR-0009, CICD-ARCHITECTURE §2 |
| Commits and PR titles | Conventional Commits; types `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`; optional scope; tracker id in the subject; the merge commit subject is the PR title ending `(#N)` | `docs(spec): align GAMEPLAY with 2026-10-18 decisions (NX-311)` | `scripts/check_commit_msg.py`, ADR-0009 amendment |
| GitHub labels | `<group>:<value>`, lowercase groups | `area:sim`, `type:decision`, `prio:p0`, `phase:P0`, `status:needs-owner` | `.github/labels.yml` |

## 3. Inconsistencies found (not changed; owner or follow-up item decides)

Terms:
1. **"Operator" had three meanings (resolved 2026-10-18, Q-ALN-40).** Operator now means a player only. Command Center people (owner, admins, moderators, GMs) are staff: `staff_id`, `STAFF_*` commands, `CommandSource.STAFF`, `PauseReasonCategory.STAFF` with `StaffPauseSubReason`, "staff pause". The O-2 rank is now Drone (Q-ALN-41). Unit control `OPERATOR` / `AUTO` (`UnitControlChanged`) keeps its name because it means player control.
2. **Commander vs Operator for players.** Data and mechanics say commander (`commander_id`), stream copy says Operator; specs mix the two in mechanics prose ("only active human operator", PROG-10).
3. **Lore names in mechanics docs.** GAMEPLAY TS-4 says mechanics docs keep plain names (coalition, enemy), yet specs use "the Static" throughout and, after this pass, "the Quorum" where they used "Clearwave". Contracts stay plain (`Side`: `COALITION`, `ENEMY`).
4. **Two "decision windows".** The Tasking Board hold after `!join` (`tasking.decision_window_s`, GAMEPLAY §1b) and the director's planning cycle (`director.window_s`, THREAT-DIRECTOR §4, TD-1) share the name.
5. **Held the Line vs Hold the Line.** A cosmetic badge (PROG-10) and a P4 campaign mode (`HOLD_THE_LINE`) differ by one word.
6. **Rank names after the faction rename (resolved 2026-10-18, Q-ALN-41).** The ladder now follows a hive theme: Recruit, Drone, Specialist, Swarm Lead, Hive Commander, Quorum Marshal, replacing Operator, Signal Lead and Wave Commander. The voice profile "Quorum Control" (AUDIO-TTS §2a) is confirmed. All remain working names for the brand guide (NX-274).
7. **Sortie vs mission.** GLOSSARY defines sortie; specs also say "mission" ("first completed mission", Q-PROG-3; Survivor reward) without a definition of what completes one.
8. **Command Center vs admin console.** Q-ARCH-7 named it Command Center; about a dozen spec lines still say "admin console".

Case and id style:
9. **Event naming.** THREAT-DIRECTOR §6a writes `GM_RELEASED{reason}` (UPPER_SNAKE), while CONTRACTS lists GM events as `GmTakeoverChanged`. Acronyms are cased both ways: `AARStarted` vs `GmTakeoverChanged`. Some events are nouns, not `<Subject><PastVerb>`: `CaptureProgress`, `ThreatAdaptation`, `PresenceSnapshot`, `StateHash`, `ScoutPing`, `DirectorProposal`.
10. **Same enum, two cases.** Stance and objective mode are lowercase in chat and config (`press`, `timed`) and `UPPER_SNAKE` in contracts (`PRESS`, `TIMED`); the mapping is implied, not written down. Identity history kinds in DATA-MODEL (`CALLSIGN_CHANGED`) mirror the sim event `CallsignChanged` in another case.
11. **Command prefixes.** `SUPPORT_REDEEM`, `ADVISOR_CHOICE` and `ORDER_PARSED` have no source prefix while staff and system commands do (`STAFF_`, `SYS_`).
12. **Duration units for similar timers.** `presence.idle_handoff_min` and `taunt.name_cooldown_min` use minutes; `tasking.claim_lease_s`, `director.window_s` and `slots.respawn_delay_s` use seconds; `campaign.target_duration_h` uses hours. Each is suffixed, so this is readable, but there is no rule for which unit to choose.
13. **Permissions look like config keys.** Both are dotted lowercase, and some share a first segment (`campaign.pause` permission vs `campaign.*` config keys).
14. **Requirement-id prefixes collide.** STATE-MACHINES invariants use `ID-n`, `PA-n`, `OC-n`, `OPS-n` per section, next to IDENTITY's `ID-PREF-1` and OPS-ADMIN's `OA-n`; DATA-INTEGRITY's fallback ids `FB-n` sit next to GAMEPLAY's `FB-UX-n`. TESTING-STRATEGY §3.6 cites `Q-NFR-*`, an area that has no rows in OPEN-QUESTIONS.
15. **Branch names.** ADR-0009 shows `feat/NX-###-…`; merged docs and fix branches mostly omit the id (`docs/align-gameplay`, `fix/tracked-files-clips-module`), and pre-ADR-0009 branches used `planning/*`.
16. **Label case.** `phase:P0` keeps a capital P while `prio:p0` is lowercase.
