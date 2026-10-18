# SPEC: Command Center (Admin Console) & Role-Based Access Control (RBAC)

Status: Draft · Owner: — · Tracker: NX-253 (P2 minimal console), NX-258…NX-266 (P3/P4, proposed) · Related: OPS-ADMIN, CONTRACTS §5.2 and §8, THREAT-MODEL, DATA-MODEL, CONFIG-AND-CONTENT, ADR-0002, ADR-0010

## 1. Purpose
The owner and their team need to run, moderate, and shape the war without touching code or config files. That means:
- managing users, the AI, and campaigns
- editing the rules
- scheduling events
- creating or generating maps (environments)
- stepping in and taking over the AI ("Game Master" mode)

All of this has to work from a phone browser or Discord, with least privilege and a complete audit trail.

## 2. Goals / Non-goals
**Goals**
- Role-based permissions that are fine-grained, scopeable, and auditable.
- Two admin channels (web console and Discord slash commands) behind one neutral `AdminChannel` port (ADR-0010).
- Every sim-affecting action is a logged `STAFF_*` command, so replays stay deterministic (ADR-0002).
- Rule changes are schema-validated, diffed, dry-run in the balance harness, and reversible.

**Non-goals**
- Public player-facing features. Per Q-ARCH-7 there are **two apps in one codebase**: the **public site** (replays, leaderboards, stats, Field Manual, later player login and account linking; read-mostly, **no admin features**) and this private **Command Center**. They share a design system and contracts but use separate APIs, logins and deployments, so a public-site bug can't reach admin powers. The public site has its own spec (to be written).
- Arbitrary code or script execution from the console.
- Editing values the sim computes. Staff can't hand-edit XP, unit HP, or node stock directly.

**XP adjustments are the exception:** staff can make one, but only as an audited, typed `ADMIN_ADJUST` ledger entry (DATA-MODEL §4.10). Viewers never see an invented number presented as earned (DATA-INTEGRITY).

## 3. Requirements
| ID | Requirement |
|---|---|
| RB-1 | Every admin request MUST be authenticated, then authorized against the RBAC matrix (§4) **on the server**. The UI hiding buttons is not security. |
| RB-2 | Deny by default. A permission absent from a role's grant list is denied. |
| RB-3 | Every admin action (allowed or rejected) MUST write one immutable `admin_audit` row (CONTRACTS §8 record + §9 additions). |
| RB-4 | Every action that changes sim state MUST be issued as a `STAFF_*` command with `source = STAFF` and an `issuer {staff_id}`, applied at a tick boundary and recorded in the command log. |
| RB-5 | Discord-originated admin actions MUST map to a staff identity through a **verified** Discord OAuth link (IDENTITY §4), never via Discord display names or unverified role names. |
| RB-6 | Destructive or high-impact permissions (§4.3) MUST support an optional two-person rule, configured per permission. |
| RB-7 | Service and agent accounts (bots, AI agents, CI) MUST use scoped tokens with the minimum permission set. They can never hold OWNER or ADMIN, and can never approve their own requests. |
| RB-8 | The kill switch (SEC-MOD-3) MUST be reachable in ≤ 2 taps from the console home screen and via one Discord slash command. It MUST work while every other admin feature is degraded. |
| RB-9 | Game Master takeover MUST be visible on stream (an `[GM]` label on director-originated actions and the threat panel), and MUST respect the same director budget and fog-of-war rules unless the OWNER explicitly lifts them for that session. |
| RB-10 | Rule/balance changes MUST be validated against the balance schema (CONFIG-AND-CONTENT §6) before any command is emitted. Non-hot-reloadable keys can only be applied to a future campaign. |
| RB-11 | Admin sessions MUST expire (idle and absolute timeouts), be revocable, and be rate-limited per staff member and per IP. |
| RB-12 | Personal data shown in the console is limited to what the staff member's permissions need. Raw platform ids are visible only with `users.view_pii`. |
| RB-13 | **While the campaign is paused (Q-ALN-24, Q-ALN-36):** safety actions MUST always work: ban (`STAFF_BAN`), forget (`FORGET`), the kill switch (`STAFF_KILL_SWITCH`), and pause, resume and end (`STAFF_CAMPAIGN_PAUSE`/`RESUME`/`END`). A config reload (`rules.apply_hot`, including applying a rank/XP preset) is validated and registered but deferred: `STAFF_CONFIG_RELOAD` applies at the first tick after resume (CONFIG-AND-CONTENT §5). A director override (`STAFF_DIRECTOR_OVERRIDE`) MUST be rejected with `CAMPAIGN_PAUSED` and audited (RB-3). Unban (`STAFF_UNBAN`), purge units (`STAFF_PURGE_UNITS`) and approved callsign changes (`SYS_SET_CALLSIGN`) apply while paused (Q-ALN-36). GM commands MUST be rejected with `CAMPAIGN_PAUSED` and audited, except a GM release (`STAFF_GM_RELEASE`, manual or automatic), which always applies (Q-ALN-36). |

## 4. Roles & permissions

### 4.1 Roles
| Role | Who | Intended for |
|---|---|---|
| `OWNER` | You (exactly one, plus a sealed break-glass recovery) | Everything, including granting roles and lifting GM limits |
| `ADMIN` | Trusted co-runner | Everything except role grants to OWNER/ADMIN, deleting audit, ownership transfer |
| `GAME_MASTER` | Event runner / storyteller | During play, runs only the Static (director control, GM takeover, jobs on the Static's Tasking Board) and world events (Q-ALN-10, Q-ALN-11, Q-AI-8). No campaign setup, no user moderation. |
| `MODERATOR` | Chat mods (Twitch, YouTube, Discord) | Bans, purges, callsign queue, kill switch. No rules or AI control. |
| `CONTENT_EDITOR` | Map/rules designer | Draft and test balance profiles, theaters, text content. Publish needs ADMIN+. |
| `VIEWER` | Observers, analysts | Read-only dashboards. No PII. |
| `SVC_PLATFORM_BOT` | Chat and Discord bot processes | Relay platform moderation events (ban sync), post digests |
| `SVC_AGENT` | AI coding or ops agents (Claude Code, others) | Read-only by default. Optionally create **drafts** (balance and theater proposals) for human approval. Never publish or apply. |
| `SVC_CI` | CI/CD | Read health and deploy status, upload harness reports. Nothing sim-affecting. |
| `SVC_ADVISOR` | The LLM advisor process | No admin permissions at all. It speaks only via `ADVISOR` commands (LLM-ADVISORS). |

### 4.2 Permissions (grouped)
| Group | Permission | Effect |
|---|---|---|
| Moderation | `mod.kill_switch` | `STAFF_KILL_SWITCH` |
| | `mod.ban` / `mod.unban` | `STAFF_BAN` / `STAFF_UNBAN` (cascades to linked platform identities) |
| | `mod.purge_units` | `STAFF_PURGE_UNITS` |
| | `mod.callsign_review` | Approve/reject queue → `SYS_SET_CALLSIGN` |
| | `mod.clip_review` | Approve/reject clips (SEC-CLIP-1) |
| Users | `users.view` | Commander list, stats, ban state (no PII) |
| | `users.view_pii` | Platform ids, link history |
| | `users.link_audit` | Link/merge audit trail |
| | `users.deletion_process` | View and expedite deletion requests (cannot cancel a user's request) |
| | `users.xp_adjust` | `ADMIN_ADJUST` ledger entry with mandatory reason |
| AI / director | `ai.view` | Director state, tier, budget, threat memory, advisor log |
| | `ai.override` | `STAFF_DIRECTOR_OVERRIDE` |
| | `ai.gm_takeover` | `STAFF_GM_TAKEOVER` / `STAFF_GM_RELEASE` |
| | `ai.gm_issue` | `STAFF_GM_OPERATION` while holding takeover |
| | `ai.gm_lift_limits` | Lift budget/fog-of-war limits for a GM session (OWNER only) |
| | `ai.advisor_toggle` | Enable/disable the LLM advisor and narrator (config flag, audited) |
| Campaign | `campaign.view` | Calendar, current campaign |
| | `campaign.pause` / `campaign.resume` | `STAFF_CAMPAIGN_PAUSE` / `STAFF_CAMPAIGN_RESUME` |
| | `campaign.end` | `STAFF_CAMPAIGN_END` |
| | `campaign.schedule` | Create/edit/cancel scheduled campaigns and events |
| Rules | `rules.view` | Balance profiles, diffs, history |
| | `rules.draft` | Edit drafts, run dry-runs |
| | `rules.apply_hot` | Hot-reload validated keys → `STAFF_CONFIG_RELOAD` |
| | `rules.publish` | Publish a profile for future campaigns |
| | `rules.rollback` | Re-apply a previous published version |
| Content | `content.view` | Theater library, unit catalog, text content |
| | `content.draft` | Upload/edit theater YAML, start generation jobs |
| | `content.publish` | Publish a theater/content version |
| Ops | `ops.view` | Health, alerts, deploy status (read-only; deploys stay in CI with Environment approval) |
| | `ops.alerts_ack` | Acknowledge/mute alerts |
| Audit | `audit.view` | Read audit log |
| | `audit.export` | Export audit log (OWNER/ADMIN) |
| Access | `access.grant_roles` | Assign roles below own level |
| | `access.manage_tokens` | Issue/revoke service tokens |

### 4.3 Matrix
✅ = granted · ⚠ = granted, two-person rule eligible (RB-6) · — = denied. Scope defaults in §4.4.

| Permission | OWNER | ADMIN | GM | MOD | EDITOR | VIEWER | SVC_PLATFORM_BOT | SVC_AGENT | SVC_CI |
|---|---|---|---|---|---|---|---|---|---|
| mod.kill_switch | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — |
| mod.ban / unban | ✅ | ✅ | — | ✅ | — | — | ✅ (relay only) | — | — |
| mod.purge_units | ✅ | ✅ | — | ✅ | — | — | — | — | — |
| mod.callsign_review | ✅ | ✅ | — | ✅ | — | — | — | — | — |
| mod.clip_review | ✅ | ✅ | — | ✅ | — | — | — | — | — |
| users.view | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | — | — |
| users.view_pii | ✅ | ✅ | — | — | — | — | — | — | — |
| users.link_audit | ✅ | ✅ | — | ✅ | — | — | — | — | — |
| users.deletion_process | ✅ | ✅ | — | — | — | — | — | — | — |
| users.xp_adjust | ⚠ | ⚠ | — | — | — | — | — | — | — |
| ai.view | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — |
| ai.override | ✅ | ✅ | ✅ | — | — | — | — | — | — |
| ai.gm_takeover / gm_issue | ✅ | ✅ | ✅ | — | — | — | — | — | — |
| ai.gm_lift_limits | ✅ | — | — | — | — | — | — | — | — |
| ai.advisor_toggle | ✅ | ✅ | — | — | — | — | — | — | — |
| campaign.view | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — |
| campaign.pause | ✅ | ✅ | ✅ | ✅ (note required) | — | — | — | — | — |
| campaign.resume | ✅ | ✅ | ✅ | — | — | — | — | — | — |
| campaign.end | ⚠ | ⚠ | — | — | — | — | — | — | — |
| campaign.schedule | ✅ | ✅ | world events only (Q-ALN-10) | — | — | — | — | — | — |
| rules.view | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | ✅ | — |
| rules.draft | ✅ | ✅ | rank/XP preset drafts only (Q-ALN-22) | — | ✅ (drafts only) | — | — | ✅ (drafts only) | — |
| rules.apply_hot | ⚠ | ⚠ | — (Q-ALN-10, Q-ALN-22) | — | — | — | — | — | — |
| rules.publish / rollback | ⚠ | ⚠ | — (Q-ALN-10) | — | — | — | — | — | — |
| content.view | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | ✅ | — |
| content.draft | ✅ | ✅ | — (Q-ALN-10) | — | ✅ (drafts only) | — | — | ✅ (drafts only) | — |
| content.publish | ✅ | ✅ | — (Q-ALN-10) | — | — | — | — | — | — |
| ops.view | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| ops.alerts_ack | ✅ | ✅ | — | ✅ | — | — | — | — | — |
| audit.view | ✅ | ✅ | own actions | own actions | own actions | — | — | — | — |
| audit.export | ✅ | ✅ | — | — | — | — | — | — | — |
| access.grant_roles | ✅ | ✅ (≤ GM/MOD/EDITOR/VIEWER) | — | — | — | — | — | — | — |
| access.manage_tokens | ✅ | ✅ | — | — | — | — | — | — | — |

This matrix folds in the owner decisions of 2026-10-17: moderators may **pause** (with a required reason) but not resume (Q-RB-1); **game rules, balance, campaign options and content are edited only by Owner and Admin** ("Who edits game rules" addendum, as narrowed by Q-ALN-10 on 2026-10-18: campaign setup is Owner/Admin only, and a Game Master runs only the Static and world events). `CONTENT_EDITOR` and `SVC_AGENT` produce **drafts only**; a Game Master may draft or propose **rank/XP presets** only (Q-ALN-22). A draft takes effect only when an Owner or Admin approves and applies or publishes it. Moderators never edit rules. Exact grants remain adjustable by the owner.

### 4.4 Scoping
- Each role grant has a scope: `GLOBAL`, or `CAMPAIGN:<campaign_id>` (e.g., a guest GM for one weekend event), with an optional `expires_at`.
- Platform-scoped moderators (`PLATFORM:<platform>`) may ban only identities whose triggering message came from that platform. The ban still cascades to the commander, per STAFF_BAN semantics (Q-RB-2).

### 4.5 Separation of duties
- `CONTENT_EDITOR` drafts. Publishing needs `ADMIN`/`OWNER` (different person when the two-person rule is on).
- `SVC_AGENT` can draft but never apply, publish, ban, or take over. An agent's drafts appear in an approval queue with the agent's token id as author.
- No one can approve their own two-person request. While the owner is the only eligible staff member, self-approval is allowed, audit-flagged `SELF_APPROVED_SOLE_OWNER`, and `campaign.end` and `rules.publish` run after a **cancellable safety delay** (`admin.solo_approval_delay_s`, PROPOSED ~10 min) (Q-RB-3). Second-person approval applies once more admins exist.
- Audit rows can't be edited or deleted by anyone, including OWNER (append-only, DM-3).

## 5. Authentication
| Topic | Rule |
|---|---|
| Owner login | Passkey (WebAuthn) primary (Q-ARCH-12). OAuth (Twitch, Discord, Google) as a second factor or recovery, checked against a staff allowlist. |
| Other staff | Passkeys for admins (Q-ARCH-12); a passkey is also required for GAME_MASTER. Moderators sign in later via Discord OAuth with a verified role mapping (Q-ARCH-12), plus allowlist entry + role grant. |
| MFA | Required for OWNER and ADMIN (passkey counts). Step-up re-auth for ⚠ actions. |
| Sessions | HttpOnly, Secure, SameSite=strict cookies. Idle timeout and absolute lifetime are config keys (`admin.session_idle_s`, `admin.session_max_s`, PROPOSED values TBD). Revocable from the console. |
| CSRF | Token on every state-changing request (SEC-ID-5 pattern). |
| Exposure | Private: reachable only via Tailscale (tailnet) and the Discord `AdminChannel` (Q-RB-4, Q-ARCH-12). A DAST pass is required before any public exposure. |
| Discord | Slash commands are handled by the Discord adapter. The bot resolves `discord_user_id` → verified staff link → role. Discord server roles are **not** trusted on their own (RB-5). A Discord role can only be a *hint* that a staff link exists. |
| Service tokens | Opaque, ≥128-bit, stored hashed, scoped to explicit permissions, with expiry. Revocable, rotated by runbook. |
| Rate limits | Per staff member and per IP. ⚠ actions get a separate stricter bucket. Values are config keys (PROPOSED, TBD). |
| Break-glass | A sealed offline recovery code for the OWNER, which re-enables passkey enrollment. Using it raises an alert. |

## 6. Feature areas

### 6.1 Moderation console
Kill switch (big, top of every page), bans with a cross-platform cascade view, purge units, the callsign approval queue (moderation verdict shown, generated alternative suggested), the clip review queue, and a "recent chat commands" feed. The feed shows normalized commands and approved callsigns only, never raw display names unless `users.view_pii`.

### 6.2 User management
Commander search (by callsign or id), stats from ledgers, ban history, link/merge audit (`identity_events`), deletion requests (SEC-DATA-3) with status, XP adjustment (⚠, reason required, writes `ADMIN_ADJUST`).

### 6.3 AI management & Game Master takeover
- **Dashboard:** current tier, CP, budget remaining, threat-memory counters, last N director operations with rationale, advisor on/off and fallback count (FB-2).
- **Tier override:** `STAFF_DIRECTOR_OVERRIDE` (existing command).
- **GM takeover mode:**
  1. `STAFF_GM_TAKEOVER{mode}` hands the director's decision loop to the GM. Modes:
     - `ASSIST`: the director still proposes, and the GM approves or vetoes each operation.
     - `FULL`: the director proposes nothing, and only GM-issued operations run.
  2. While held, `STAFF_GM_OPERATION{operation, target, params}` issues operations from the same doctrine library. Each is validated against preconditions, **tier budget**, and the **enemy fog-of-war view** (FOW-4), unless an OWNER has lifted limits with `STAFF_GM_LIMITS{budget: bool, fow: bool}`.
  3. `STAFF_GM_RELEASE` returns control to the director.
  4. Takeover auto-releases after `admin.gm_max_session_s` (config, PROPOSED TBD), or when the GM's session ends, so the AI is never left stuck. These are **real-time** (monotonic) timers enforced outside the sim, which issue a `SYSTEM` `STAFF_GM_RELEASE` when they fire; they keep running while the campaign is paused (Q-ALN-4, CONFIG-AND-CONTENT CFG-9).
  5. On stream: the threat panel shows `GAME MASTER ACTIVE`, and sitreps for GM operations are tagged `[GM]` and spoken with the distinct Game Master voice profile (DATA-INTEGRITY DI-5; Q-RB-7, AUDIO-TTS §2a).
  5a. Threat memory keeps learning during a FULL takeover (Q-RB-6).
  6. Every GM operation is a logged command, so replays reproduce it.
- **GM scope (Q-ALN-10, Q-AI-8):** during play a GM drives only the Static and world events. World events may help the coalition (supply drop, weather clearing, friendly convoy) but must be visible and in-fiction; a GM never grants units, ammo or XP to specific players. A GM cannot change objectives or campaign options (§6.4).
- **Tasking Board injection (Q-ALN-11, GAMEPLAY TB-11):** a GM may inject jobs into the **Static's** board only. An injection aimed at the coalition board is rejected and audited (RB-3). Injection is a logged `STAFF_*` command (RB-4); its contract is not written yet (§13).

### 6.4 Campaign planning & scheduling
- **Calendar:** past, current, and future campaigns. Each scheduled campaign: `mode` (CampaignMode), `theater_id@version`, `balance_profile@version`, objective mode (`timed`/`off`, Q-GD-19), campaign options (unlimited ammo, weather; Q-CBT-5/7), start time, optional target length (Q-GD-5). **Campaign setup (objectives, objective mode and every campaign option) is Owner/Admin only (Q-ALN-10).** A GM may schedule world events and GM operations, not campaigns.
- **Times and time zones (Q-CFG-6):** times are stored as wall-clock time **with an explicit IANA time zone** (default `America/New_York`, the owner's zone), not as UTC offsets, so DST is handled. The scheduler resolves each item to a UTC instant when it computes the next run; audit timestamps stay RFC 3339 UTC.
- **Scheduled events:** timed operations ("Operation Red Tempest at Saturday 20:00"), maintenance windows (auto-pause with reason `MAINTENANCE` and an on-stream banner, Q-ALN-3, Q-OPS-9), and announcement text.
- **Execution:** at the scheduled time, the scheduler emits the corresponding command (`SYS_CAMPAIGN_START`, `STAFF_CAMPAIGN_PAUSE`, `STAFF_GM_OPERATION` as `SYSTEM` on behalf of the scheduling staff member, recorded in `scheduled_items.created_by`).
- **Conflicts:** overlapping campaigns, or a theater/profile version that isn't published, are rejected at scheduling time.

### 6.5 Rules / balance editor
1. Forms are generated from the balance JSON Schema (CONFIG-AND-CONTENT §6). Each key shows type, unit, source spec, hot-reloadable flag, and PROPOSED/validated status.
2. **Diff preview** against the active profile, with non-hot-reloadable keys highlighted.
3. **Dry-run:** queue a balance-harness run (TESTING-STRATEGY §3.5) on standard scenarios. The report is attached to the draft. **Mandatory for next-campaign publishes; optional for hot keys, and a skipped dry-run is audit-flagged** (Q-RB-5).
4. **Apply:** hot keys go through `STAFF_CONFIG_RELOAD` (existing). Everything else is **publish** for future campaigns. While the campaign is paused, a hot apply is registered and applied at the first tick after resume (RB-13, Q-ALN-24).
4a. **Rank/XP presets (Q-ALN-22, CONFIG-AND-CONTENT §5a):** a GM's preset draft appears in the approval queue with the GM as author. Only an Owner or Admin can approve and apply it, through step 4; the audit row names both the drafting and the applying staff member.
5. **Versioning:** every publish creates an immutable version (`config_versions` manifest). Rollback re-applies a previous version through the same path.

### 6.6 Environment (theater) management & generation
- **Library:** theaters with versions, status (`DRAFT`/`VALIDATED`/`PUBLISHED`/`RETIRED`), preview image, node/edge counts.
- **Upload/edit:** theater YAML (CONFIG-AND-CONTENT §4), validated on save: connectivity, unique names, moderation check on names, hyphen-only ids.
- **Generation job:** parameters:
  - `seed`, `archetype`: `STRAIT`, `ARCHIPELAGO`, `LARGE_ISLANDS`, `MOUNTAIN_PASS`, `URBAN`, `MIXED`
  - `water_fraction`, `node_count`, `front_axis` (default `WEST_TO_EAST`: coalition on the left; owner decision 2026-10-17, GAMEPLAY §9a; vertical layout Q-GD-13)
  - `size`

  The job outputs a draft theater + preview render + validation report. The generator is deterministic for a given seed and parameter set. It's a `tools/` job, not part of the sim kernel.
- **Publish:** `content.publish` makes the version selectable in scheduling. Published versions are immutable.

### 6.7 Ops (read-only)
Health of each component, alert list, current deploy versions (digests), adapter status and quota. Deploys themselves stay in GitHub Environments (CICD §6), never in the console.

### 6.8 Conduct system (owner decisions Q-MOD-5, Q-MOD-6, Q-CBT-9; full spec NX-291)
- **Separate from skill.** Losing, dying or being new never lowers conduct (Q-CBT-9). Only clear disruptive patterns are flagged: suicide spam (repeated deaths in a short window with no objective progress), command spam / throttle abuse, rapid role-flipping, repeated blocked-callsign attempts, deliberately draining a starved base.
- **Decaying conduct score** with a slow, reversible **escalation ladder**: (1) a gentle warning in the digest → (2) reduced capabilities (longer cooldowns, no rally calls) → (3) temporary in-game timeout → (4) XP/merit penalty (typed, audited ledger entry) → (5) flagged to moderators for a ban decision. **Bans always need a human.** Conduct recovers with good play over time. Thresholds are PROPOSED and admin-tunable.
- **Transparency:** the rules are published (public site + `!rules`). Each operator sees their own standing and any active restriction via `!me` (later the public site); other players' scores are never shown. Moderators and admins see conduct, merit, stats and rankings in the Command Center.
- **Indicator to others (Q-MOD-6):** only a neutral **probation** tag on the unit while a restriction is active; no score, no shaming text (OVERLAY OV-2a, CONTRACTS `EntityView.probation`).
- **Audit and appeal:** every flag and step is logged, visible to moderators, and reversible on appeal. Which permissions in §4.2 cover viewing, overriding and reversing conduct actions is to be added with the conduct spec (NX-291); until then no new permission is assumed.
- Contract impact: see CONTRACTS "Contract additions pending merge" (conduct note).

## 7. Interfaces

### 7.1 AdminChannel port (ADR-0010)
```python
class AdminChannel(Protocol):
    channel: AdminChannelKind   # WEB_CONSOLE | DISCORD
    async def run(self, handler: AdminRequestHandler) -> None: ...
```
Both channels produce the same `AdminRequest{staff_id, permission, action, params, channel, request_id}`, go through one authorization function, and share the audit path. The Discord adapter can't reach anything the web console can't.

### 7.2 Discord slash-command parity (key actions)
| Action | Web console | Discord | Permission |
|---|---|---|---|
| Kill switch | Big button | `/nexus killswitch on\|off [flags]` | mod.kill_switch |
| Pause / resume | Campaign page | `/nexus pause <note> [RAID\|ABUSE\|CONTENT\|OTHER]` (category `STAFF`, optional sub-reason, Q-ALN-31), `/nexus resume` (also the one-tap link in the pause alert) | campaign.pause / campaign.resume |
| Ban / unban | User page | `/nexus ban <callsign> <reason>`, `/nexus unban <callsign>` | mod.ban/unban |
| Purge units | User page | `/nexus purge <callsign>` | mod.purge_units |
| Callsign queue | Queue page | `/nexus callsigns` (list), buttons approve/reject | mod.callsign_review |
| Director tier | AI page | `/nexus tier <ALPHA\|BRAVO\|CHARLIE> <minutes>` | ai.override |
| GM takeover | AI page | `/nexus gm take <ASSIST\|FULL>`, `/nexus gm release` | ai.gm_takeover |
| GM operation | AI page (operation picker) | `/nexus gm op <operation> <target>` | ai.gm_issue |
| Status | Home | `/nexus status` | ops.view |
| Two-person approve | Approvals page | `/nexus approve <request_id>` | the requested permission |

Rule editing, theater editing, generation, and scheduling are **web only**. Forms and diffs don't fit chat commands.

### 7.3 UI notes (phone-first)
- Single-column layout and large touch targets. The kill switch and pause are always visible.
- Confirm dialogs for ⚠ actions show the exact effect ("Ends campaign #14 as ABORTED").
- Long-running jobs (dry-run, generation) report progress and notify via the AlertSink when done.
- Text from users is rendered with `textContent` only (SEC-OV-1 applies to the console too).

## 8. Contract additions (merge into CONTRACTS)
| Command | Fields | Issuer | Reject reasons |
|---|---|---|---|
| `STAFF_GM_TAKEOVER` | `mode: ASSIST\|FULL` | STAFF | `GM_ALREADY_ACTIVE`, `CAMPAIGN_NOT_RUNNING`, `CAMPAIGN_PAUSED` (Q-ALN-36) |
| `STAFF_GM_RELEASE` | — | STAFF, or SYSTEM on timeout | `GM_NOT_ACTIVE` |
| `STAFF_GM_OPERATION` | `operation: string` (doctrine library), `target: NodeId\|SectorId\|null`, `params: object` (schema per operation) | STAFF (holder), or SYSTEM for scheduled events | `GM_NOT_ACTIVE`, `NOT_GM_HOLDER`, `UNKNOWN_OPERATION`, `PRECONDITION_FAILED`, `OVER_BUDGET`, `NOT_VISIBLE_TO_ENEMY`, `CAMPAIGN_PAUSED` (Q-ALN-36) |
| `STAFF_GM_VERDICT` | `proposal_id`, `verdict: APPROVE\|VETO` (ASSIST mode) | STAFF (holder) | `GM_NOT_ACTIVE`, `UNKNOWN_PROPOSAL`, `CAMPAIGN_PAUSED` (Q-ALN-36) |
| `STAFF_GM_LIMITS` | `budget: bool`, `fow: bool` (true = enforced) | STAFF (OWNER only) | `GM_NOT_ACTIVE`, `CAMPAIGN_PAUSED` (Q-ALN-36) |
| `STAFF_CAMPAIGN_PAUSE` (amended, Q-ALN-31) | adds `sub_reason: StaffPauseSubReason\|null` next to `reason_category` and `note`; non-null only when `reason_category = STAFF` | as in CONTRACTS | adds `INVALID_PAYLOAD` for a `sub_reason` with any other category |
| `STAFF_DIRECTOR_OVERRIDE` (amended, Q-ALN-24) | unchanged | STAFF | adds `CAMPAIGN_PAUSED` while the campaign is paused |

| Event | Fields | FoW | Consumers |
|---|---|---|---|
| `GmTakeoverChanged` | `active: bool`, `mode`, `limits{budget,fow}` | none | broadcast (panel label), audio, ops |
| `GmOperationLaunched` | as `DirectorOperationLaunched` + `by_gm: true` | same as director op | broadcast (`[GM]` tag), audio, clips |
| `DirectorProposal` | `proposal_id`, `operation`, `target` (ASSIST mode, staff-only channel) | not broadcast | admin console only |

Admin API additions: `/admin/gm/*`, `/admin/schedule/*`, `/admin/rules/drafts/*` (+ `/dry-run`, `/publish`, `/rollback`), `/admin/theaters/*` (+ `/generate`, `/validate`, `/publish`), `/admin/access/*` (roles, grants, tokens), `/admin/approvals/*`. Every route maps to exactly one permission in §4.2.

New enums: `AdminRole`, `Permission`, `GrantScopeKind` (`GLOBAL`, `CAMPAIGN`, `PLATFORM`), `TheaterArchetype`, `ContentStatus`, `ScheduledItemKind` (`CAMPAIGN`, `EVENT`, `MAINTENANCE`), `ApprovalStatus`, `StaffPauseSubReason` (`RAID`, `ABUSE`, `CONTENT`, `OTHER`; Q-ALN-31).

## 9. Data model additions (merge into DATA-MODEL)
```sql
CREATE TABLE staff (
  staff_id       TEXT PRIMARY KEY,                 -- UUIDv7
  commander_id   TEXT REFERENCES commanders(commander_id), -- nullable: service accounts have none
  kind           TEXT NOT NULL CHECK (kind IN ('HUMAN','SERVICE')),
  display_label  TEXT NOT NULL,                    -- admin-chosen label, moderated
  created_at     TEXT NOT NULL,
  disabled_at    TEXT
) STRICT;

CREATE TABLE role_grants (
  grant_id     TEXT PRIMARY KEY,
  staff_id     TEXT NOT NULL REFERENCES staff(staff_id),
  role         TEXT NOT NULL,                       -- AdminRole enum (generated CHECK)
  scope_kind   TEXT NOT NULL CHECK (scope_kind IN ('GLOBAL','CAMPAIGN','PLATFORM')),
  scope_value  TEXT,                                -- campaign_id / platform; NULL iff GLOBAL
  granted_by   TEXT NOT NULL REFERENCES staff(staff_id),
  granted_at   TEXT NOT NULL,
  expires_at   TEXT,
  revoked_at   TEXT,
  CHECK ((scope_kind = 'GLOBAL') = (scope_value IS NULL))
) STRICT;

CREATE TABLE staff_credentials (               -- passkeys / OAuth links / service tokens
  credential_id  TEXT PRIMARY KEY,
  staff_id       TEXT NOT NULL REFERENCES staff(staff_id),
  kind           TEXT NOT NULL CHECK (kind IN ('PASSKEY','OAUTH','SERVICE_TOKEN')),
  provider       TEXT,                           -- Platform enum for OAUTH, NULL otherwise
  public_ref     TEXT NOT NULL,                  -- passkey credential id / provider user id / token id
  secret_hash    TEXT,                           -- hashed token for SERVICE_TOKEN; NULL otherwise
  permissions    TEXT,                           -- JSON array, SERVICE_TOKEN only
  created_at     TEXT NOT NULL,
  expires_at     TEXT,
  revoked_at     TEXT
) STRICT;

CREATE TABLE admin_sessions (
  session_id_hash TEXT PRIMARY KEY,
  staff_id        TEXT NOT NULL REFERENCES staff(staff_id),
  channel         TEXT NOT NULL CHECK (channel IN ('WEB_CONSOLE','DISCORD')),
  created_at      TEXT NOT NULL,
  last_seen_at    TEXT NOT NULL,
  expires_at      TEXT NOT NULL,
  revoked_at      TEXT
) STRICT;

CREATE TABLE approval_requests (               -- two-person rule
  request_id     TEXT PRIMARY KEY,
  permission     TEXT NOT NULL,
  params_digest  TEXT NOT NULL,                -- sha256 of canonical params
  params_json    TEXT NOT NULL,
  requested_by   TEXT NOT NULL REFERENCES staff(staff_id),
  requested_at   TEXT NOT NULL,
  status         TEXT NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED','EXECUTED')),
  decided_by     TEXT REFERENCES staff(staff_id),
  decided_at     TEXT,
  CHECK (decided_by IS NULL OR decided_by <> requested_by OR status = 'REJECTED')
) STRICT;

CREATE TABLE scheduled_items (
  item_id        TEXT PRIMARY KEY,
  kind           TEXT NOT NULL CHECK (kind IN ('CAMPAIGN','EVENT','MAINTENANCE')),
  starts_at      TEXT NOT NULL,                -- local wall-clock time in `tz` (Q-CFG-6)
  tz             TEXT NOT NULL,                -- IANA zone, e.g. America/New_York
  ends_at        TEXT,                         -- local wall-clock time in `tz`
  payload_json   TEXT NOT NULL,                -- schema per kind (contracts/admin)
  created_by     TEXT NOT NULL REFERENCES staff(staff_id),
  created_at     TEXT NOT NULL,
  status         TEXT NOT NULL CHECK (status IN ('SCHEDULED','RUNNING','DONE','CANCELLED','FAILED')),
  last_error     TEXT
) STRICT;

CREATE TABLE content_versions (                -- theaters, balance profiles, text packs
  content_id     TEXT NOT NULL,                -- e.g. theater slug
  version        INTEGER NOT NULL,
  kind           TEXT NOT NULL CHECK (kind IN ('THEATER','BALANCE_PROFILE','TEXT_PACK','UNIT_CATALOG')),
  status         TEXT NOT NULL CHECK (status IN ('DRAFT','VALIDATED','PUBLISHED','RETIRED')),
  sha256         TEXT NOT NULL,
  source_path    TEXT NOT NULL,
  created_by     TEXT NOT NULL REFERENCES staff(staff_id),
  created_at     TEXT NOT NULL,
  validation_report_path TEXT,
  harness_report_path    TEXT,
  generation_params_json TEXT,                 -- NULL unless generated
  published_by   TEXT REFERENCES staff(staff_id),
  published_at   TEXT,
  PRIMARY KEY (content_id, version)
) STRICT;
```
`admin_audit` gains these columns: `channel` (`WEB_CONSOLE`/`DISCORD`/`SCHEDULER`/`API_TOKEN`), `permission`, `approval_request_id` (nullable), and `flags` (e.g., `SELF_APPROVED_SOLE_OWNER`).

## 10. Phasing
| Phase | Ships |
|---|---|
| **P2 (alpha)** | A single staff member, the OWNER (passkey + allowlist, tailnet only). Web console: kill switch, pause/resume, end, ban/unban, purge, callsign queue, director tier override, health view. Discord: `/nexus killswitch`, `pause`, `resume`, `ban`, `status`. Audit for everything. No two-person rule. |
| **P3 (beta)** | Full RBAC roles and scopes, staff invites, service tokens, MODERATOR role with Twitch/Discord link, clip queue, user management, deletion requests, rules editor with diff + hot-apply + versioning, scheduling for campaigns and maintenance windows. |
| **P4 (depth)** | GM takeover (ASSIST/FULL), scheduled GM events, dry-run harness integration in the editor, two-person rule, theater upload/validation/publish, procedural generation jobs with preview, SVC_AGENT draft workflow. |

## 11. Failure modes
| Failure | Behavior |
|---|---|
| Console down | Discord kill switch and pause still work (separate adapter path). The reverse holds too. |
| Discord down | Web console unaffected. Moderation events from Twitch still sync bans via SVC_PLATFORM_BOT. |
| DB unavailable | Read-only console banner. Sim-affecting actions still go to the command path (kill switch must work, RB-8). Audit rows are queued in memory (bounded) and flushed, with an alert. |
| GM disconnects mid-takeover | Auto-release after the session timeout. The director resumes, and a `[GM]` → normal banner shows. |
| Scheduled item fails (e.g., theater unpublished) | Status `FAILED` with reason, alert, nothing silently substituted (DATA-INTEGRITY DI-2). |

## 12. Test plan
| Req | Tests |
|---|---|
| RB-1, RB-2 | Generated **authz matrix test**: for every (role, permission) pair, call the route and assert allowed or denied exactly per §4.3. Unknown permission → denied. |
| RB-3 | Every route test asserts exactly one audit row, including for rejected requests. Audit rows can't be updated or deleted (DB trigger + test). |
| RB-4 | Sim-affecting routes emit the expected `STAFF_*` command. A replay of a log containing admin commands produces an identical state hash. |
| RB-5 | Discord request from an unlinked or unverified user → denied. A Discord role alone grants nothing. |
| RB-6 | ⚠ action with the two-person rule on: approval by the same staff member rejected, approval by a second staff member executes once (idempotent). |
| RB-7 | SVC_AGENT token cannot publish, apply, ban, or take over (matrix test). Expired or revoked tokens are denied. |
| RB-8 | Kill switch works with the DB down and with the console process stopped (Discord path) in an integration test. |
| RB-9 | GM operations over budget or not visible to the enemy are rejected unless limits are lifted by OWNER. A takeover emits `GmTakeoverChanged` and the overlay shows the label. Auto-release on timeout. |
| RB-10 | Invalid balance draft → no command emitted. Non-hot key in a hot-apply → rejected before the command. |
| RB-11 | Session idle and absolute expiry, revocation, rate-limit tests. |
| RB-12 | `users.view` responses contain no platform ids (schema test). |
| §6.3, §6.4 (Q-ALN-10, Q-ALN-11) | Matrix test: a GM setting unlimited ammo, the objective mode or an objective is denied; a GM scheduling a world event is allowed and a GM scheduling a campaign is denied. A GM job injection into the Static's board is accepted; one into the coalition board is rejected with an audit row. |
| §6.3 (Q-ALN-4) | With a fake monotonic clock: a takeover reaches `admin.gm_max_session_s` while the campaign is paused and still auto-releases. |
| RB-13 (Q-ALN-24) | With the campaign paused: ban, forget, kill switch, resume and end each apply; a second pause rejects `ALREADY_PAUSED`; a hot config reload is registered, not applied until the first tick after resume; a director override rejects `CAMPAIGN_PAUSED` with an audit row; unban, purge units and an approved callsign change apply (Q-ALN-36); GM takeover, operation, verdict, limits and job injection reject `CAMPAIGN_PAUSED` with an audit row, and a GM release (manual or on timeout) applies (Q-ALN-36). |
| §6.5 step 4a (Q-ALN-22) | Matrix test: a GM can save a rank/XP preset draft and cannot save any other rules draft; a GM applying a preset is denied; an Admin applying the GM's draft emits one `STAFF_CONFIG_RELOAD` and an audit row naming both staff members. |
| Pause flow (Q-ALN-31) | A form pause sends `reason_category = STAFF` with the chosen `sub_reason` (or `null`); a `sub_reason` with `TECHNICAL`, `MAINTENANCE` or `CEASEFIRE` rejects `INVALID_PAYLOAD`; a pause without a note from staff rejects `REASON_REQUIRED`. |

## 13. Resolved questions (owner decisions 2026-10-17)
All questions raised by this spec are decided and folded in above:
- **Q-RB-1:** moderators can pause, only with a required reason (a note, plus the Q-ALN-31 category and optional sub-reason); resume needs GM/admin/owner; every pause alerts the owner immediately (§4.3, pause-flow addendum).
- **Q-RB-2:** bans cascade across all linked platforms; unban requires an admin (§4.4).
- **Q-RB-3:** self-approval allowed while solo, audit-flagged, with a cancellable ~10 min (PROPOSED) safety delay on campaign end and rules publish (§4.5).
- **Q-RB-4:** the Command Center is private (tailnet + Discord); DAST before any public exposure (§5).
- **Q-RB-5:** harness dry-run mandatory for next-campaign publishes; optional for hot keys, skip audit-flagged (§6.5).
- **Q-RB-6:** threat memory keeps learning during GM FULL takeover (§6.3).
- **Q-RB-7:** the Game Master has its own voice profile (§6.3, AUDIO-TTS §2a).

Decided 2026-10-18: Q-OPS-8 (offline auto-pause, reason `TECHNICAL`) and Q-OPS-9 (weekly maintenance window, reason `MAINTENANCE`; Ceasefire mode), see OPS-ADMIN. Spec-alignment batch: Q-ALN-3 (pause reasons), Q-ALN-4 (GM auto-release on real time), Q-ALN-10 (campaign setup Owner/Admin only; GM scope = Static + world events), Q-ALN-11 (GM injects jobs into the Static's board only), Q-ALN-22 (GMs draft rank/XP presets; Owner/Admin approve and apply; §4.3, §6.5), Q-ALN-24 (actions while paused, RB-13), Q-ALN-31 (pause category plus optional `STAFF` sub-reason, pause flow), Q-ALN-32 (staff-pause banner, pause flow). Spec-alignment batch 3: Q-ALN-36 (unban, purge and callsign changes apply while paused; GM commands other than a release are rejected, RB-13, §8), Q-ALN-39 (the sub-reason never reaches the stream, pause flow).

Still open:
- The command contract for GM Tasking Board injection (§6.3).

## Addendum: Pause flow (owner decision 2026-10-17, Q-RB-1)
1. **Pause form (Q-ALN-31):** a pause carries two fields. `reason_category` is the `PauseReasonCategory` (`STAFF`, `TECHNICAL`, `MAINTENANCE`, `CEASEFIRE`, Q-ALN-3); a pause from this form is always `STAFF`. `sub_reason` is optional, one of `RAID`, `ABUSE`, `CONTENT`, `OTHER`, and is allowed only when the category is `STAFF` (automatic and Ceasefire pauses send `null`). A moderator, GM or admin must also give a short note; a form pause without a note is rejected (`STAFF_CAMPAIGN_PAUSE{reason_category, sub_reason, note}`, §8). Every pause, whatever its reason, freezes world and game time (CONFIG-AND-CONTENT CFG-9). Safety actions keep working while paused (RB-13).
1a. **On-stream banner (Q-ALN-32):** while a `STAFF` pause is active the HUD shows a simple **"PAUSED — stand by"** banner. The note and sub-reason are never shown on stream; the overlay receives only the pause category (Q-ALN-39, OVERLAY).
2. **Immediate owner alert** through every enabled `AlertSink` (ntfy, Discord, email; voice line later). It says who paused, when, why (category, sub-reason and note), and the current state: momentum, active operators, recent incidents.
3. **AI assessment (optional, advisory only):** the LLM advisor writes a short summary of the situation and a recommendation to resume or stay paused, using only logged data. It's labeled as AI-generated and never acts on its own (ADR-0007).
4. **One-tap resume:** an action link in the alert (authenticated), a Discord slash command (`/nexus resume`), or the Command Center. Voice resume comes with the voice ops line. Resume needs GM/admin/owner; the owner's action is audited like any other.
5. **Auto-escalation:** if the pause lasts longer than a configurable time with no response, re-alert (PROPOSED interval).

## Addendum: Who edits game rules (owner decision 2026-10-17)
Game rules, balance, campaign options (e.g. unlimited ammo, weather) and content: **Owner and Admin** only. The 2026-10-17 decision included the Game Master; Q-ALN-10 (2026-10-18) narrowed it: campaign setup is Owner/Admin only, and a GM runs only the Static and world events during play. A GM may draft or propose rank/XP presets, which an Owner or Admin approves and applies (Q-ALN-22, §6.5). **Moderators do not edit rules.** They moderate users and can pause (with a reason, Q-RB-1).
