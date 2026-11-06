# SPEC: Site live map (the in-depth view)

Status: Draft — needs owner sign-off · Owner: owner · Tracker: NX-516 · Depends on: NX-176, NX-177, NX-178 · Related: Q-UX-24, Q-UX-25, Q-UX-26, Q-ARCH-7, Q-ARCH-16, Q-MOD-1, Q-MOD-6, Q-DM-3, Q-DM-4 · Related specs: PUBLIC-SITE, WIRE-PROTOCOL, CONTRACTS §7, OVERLAY §0.10, FOG-OF-WAR, IDENTITY, THREAT-MODEL (B10) · Related ADRs: ADR-0005, ADR-0010, ADR-0012

Values marked PROPOSED are lead defaults, tunable without a spec change. Facts not checked against a real host are marked [UNVERIFIED].

## 1. Purpose
The stream is the spectator view: it labels only a few units (OVERLAY OV-4) and never pans or zooms (Q-UX-10). Players want the full picture: every unit with its name, unit detail and filters. The owner decided that this in-depth view is a live map page on the public site, first; a second "ops" stream may come later (Q-UX-24, 2026-11-05). This spec defines that page and the public, unauthenticated feed it reads.

## 2. Goals / Non-goals
Goals: the same war the stream shows, with every name and detail; works on a phone; costs the sim nothing; leaks nothing the stream does not already show.

Non-goals (this item):
- Sending commands from the site. Chat stays the only command path (WIRE-PROTOCOL §1.1, SEC-API-1).
- Accounts, login, linking or anything per-viewer on the server (IDENTITY §4 is a separate P3 portal).
- Admin or moderation features. Those are the Command Center (Q-ARCH-7).
- History, replays, the post-campaign full reveal (FOW-1a, CLIPS-REPLAY) and leaderboards (Q-ARCH-16).
- The second "ops" stream (Q-UX-24, later).

## 3. Words
- **Name:** a unit's `callsign` (CONTRACTS §3.2: `^[A-Z][A-Z0-9-]{2,11}$`), or `REDACTED-<tag>` for a deleted commander (IDENTITY §5), or the `[AI]` label for AI units (CONTRACTS §7). Raw platform display names never appear in wire schemas and are never rendered (CONTRACTS §3.5 and the `display_name` row, Q-MOD-1, SEC-MOD-1). "Full name" (Q-UX-26) therefore means the full callsign, with no 16-character cap. Today no callsign is longer than 13 characters, so the stream's cap never cuts one either.
- **Public feed:** the files this spec publishes for the page (§4).
- **Publisher:** the process on the broadcast host that builds and uploads the public feed.

## 4. Data source

### 4.1 Options
| Option | How | Verdict |
|---|---|---|
| (a) Public WS relay | The publisher opens one outbound WS to a relay outside the home network, which fans the frames out to browsers | Real time (tick Deltas). Needs an always-on public server, a WS DoS surface, its own security review and a monthly cost [UNVERIFIED]. **Later**, if demand shows |
| (b) Pushed snapshots | Every few seconds the publisher uploads one public snapshot as static JSON to object storage behind a CDN; browsers poll it | No public server, the CDN absorbs load, matches the one-way export model of Q-ARCH-16. Seconds behind, not live to the tick. **Recommended first** |
| (c) The overlay's WS | Browsers connect to `/ws` | **Rejected.** The `capability_token` is a secret (WIRE-PROTOCOL §7.1); the WS binds loopback or private only (§7.2) and is capped at 8 connections (WP-12) |
| (d) Tunnel to a home relay | A tunnel (SYSTEM-DESIGN §6) to a relay on the broadcast host | **Rejected.** Every viewer would cost home upload, and Q-ARCH-16 rules out an inbound path to the home network |

Why home upload matters: measured upload is about 36 Mbps (HARDWARE.md:11), the stream uses about 9–10 Mbps (HARDWARE.md:53), and total outbound must stay ≤ 70% of upload (HARDWARE.md:55). One viewer of the full Delta stream at the WP-4 size (16 KB × 10 Hz) is about 1.3 Mbps, so (c) or (d) would fit only about ten viewers.

### 4.2 Recommendation
Option (b) now. The snapshot format is a public projection of the overlay's `Snapshot` (§5), so moving to (a) later changes the transport, not the content.

### 4.3 Requirements
- **SLM-1** Site viewers MUST NOT touch the sim's hot path. The publisher is a client of the existing broadcast endpoint on loopback (WIRE-PROTOCOL §2, WP-7), holding one of the WP-12 slots; it rebuilds state from `Delta`s off the sim thread. It adds no sim code, and its effect on the tick is the WP-11 bound for one client. Its `client_kind` is a build-PR choice (open question 6).
- **SLM-2** The publisher MUST run in its own container with no stream keys, platform tokens or admin API access (SYSTEM-DESIGN §6). Its only secret is a write key scoped to the feed's storage prefix, kept in sops (Q-ARCH-10). The storage SDK sits behind a `PublicFeedTarget` port, like `BackupTarget` (ADR-0010).
- **SLM-3** Every PROPOSED 5 s the publisher uploads `state.json`. It uploads `theater.json` (the `Welcome.theater` projection) on start and when the theater changes, under a content-hash name that `state.json` names. Upload is outbound HTTPS only; nothing on the home network listens.
- **SLM-4** `state.json` MUST be served with a short cache life (PROPOSED `max-age=2`), so the CDN takes the viewer load and the storage origin sees few reads. `theater.json` is immutable (long cache).
- **SLM-5** Latency target: the page shows a state at most PROPOSED 10 s older than the sim, p95. The page interpolates unit motion between two snapshots from `speed_mps` and `heading_deg` (as OVERLAY OV-7 does between ticks) and never extrapolates past the next expected snapshot.
- **SLM-6** Upload budget: a gzipped `state.json` at 1,000 entities SHOULD be ≤ PROPOSED 256 KB, about 0.4 Mbps at 5 s. The real size is not measured yet; the build PR measures it, as NX-171 did for WP-4.
- **SLM-7** Storage object versioning MUST be off and the publisher MUST NOT keep past snapshots: the feed is "now" only, so a ban or deletion is not undone by an old copy (§6).

## 5. What a public client may receive
- **SLM-8 Fog.** The feed MUST carry exactly the coalition view the overlay gets (WP-9, FOW-1): tracked entities, `LastKnownView`s, `BlobView`s, nodes and discovered facilities. It MUST NOT carry anything the overlay frames do not carry. The publisher only removes and renames fields; it never adds a source.
- **SLM-9 Field allowlist.** The publisher builds each file from an explicit allowlist. It drops `Welcome.server_build` (no version banner for attackers). Shapes reuse the CONTRACTS §7 view types. The feed's own schema lives in `contracts/` (rule 6) as `contracts/public/` [path PROPOSED].
- **SLM-10 No identity-linked ids.** The feed MUST contain no `commander_id`, platform id or display name (a schema check, as CONTRACTS §10 does for `wire/`).
- **SLM-11 Opaque entity ids.** `EntityId` is sequential per campaign (CONTRACTS §3.2). On a public feed, gaps between enemy ids could reveal how many hidden enemy units were made. The publisher MUST replace every entity id (`entity_id`, `follow_entity_id`, facility and last-known ids) with a feed-local id, numbered in the order the feed first shows each entity, kept for the campaign. Open question 3.
- **SLM-12 Names.** Shown names are the wire's `callsign` values only (§3). The page MUST also honor:
  - the staff kill switch: while `hide_user_text` is set (CONTRACTS `STAFF_KILL_SWITCH`), the publisher blanks every callsign and every user-derived ticker line, as the stream does. The wire has no kill-switch state until NX-253 (CONTRACTS §7 `Snapshot`), so this rule ships with NX-253 or the feed stays off until then;
  - banned and forgotten commanders: their units leave the world (CONTRACTS §5.2 `FORGET` despawn, `UnitOrphaned`), so they leave the next snapshot; a deleted commander shows as `REDACTED-<tag>` (IDENTITY §5);
  - no new opt-out is added here; a callsign is a pseudonym (open question 4).
- **SLM-13 Probation and other tags.** The page shows only what the overlay may show for the same field: the neutral probation tag with no score (Q-MOD-6), AUTO (`auto`) and `[AI]`. `badges` and `cosmetic` are shown only once their producers exist (null today, CONTRACTS §7).
- **SLM-14 Sitreps.** The sitrep log is `Hud.ticker` (ModeratedText) plus the `PublicEvent`s from `Delta.events` and `Hud.momentum_breakdown.recent_events`, last PROPOSED 50, as the overlay words them (OVERLAY §0.9). `CommandRejected` and other never-public kinds cannot pass the `public_event.json` schema (CONTRACTS §7).

## 6. The page

### 6.1 Features
- **SLM-15 Map.** The full theater with the overlay's look: the `bounds_m` projector, nodes, roads, sea lanes, bridges, rings, territory tint (OVERLAY §0.10, Q-UX-26), and units, blobs and last-known tracks as in NX-177. The drawing code is shared with the overlay, not copied (a shared module; its place in the repo is decided in the build PR). Unlike the stream, the page may pan and zoom (Q-UX-10 binds the stream only).
- **SLM-16 Labels.** Every unit with a callsign gets a full-name label. Where labels would overlap at the current zoom, some are hidden; zooming in shows more, and the selected unit's label is never hidden. AI units show `[AI]` in the detail panel only, to keep the map readable.
- **SLM-17 Search and find my unit.** A callsign search (case-insensitive, prefix match). Choosing a result centres and highlights the unit. The URL fragment `#cs=<CALLSIGN>` does the same, so a viewer can bookmark it. Nothing is stored in the browser (PS-2).
- **SLM-18 Filters.** Side, `domain`, `unit_kind`, `owner_kind` (human or AI), and "has a name". A role filter needs a published `unit_kind`→role map and a sector filter needs sector shapes in `TheaterStatic`; neither is on the wire today (CONTRACTS §7), so both wait (open question 5).
- **SLM-19 Unit detail.** Fields from `EntityView` only: name, `unit_kind`, side, `domain`, `owner_kind`, `hp_pct` and `damage_state`, `speed_mps`, `heading_deg`, `painted`, `spotted` (own units only, FOW-12), `auto`, the probation tag, `follower_count` and the followed unit's name. A last-known track shows its kind and age from `seen_tick` against `Hud.campaign_clock.elapsed_ticks`. A blob shows its size only (FOW-2).
- **SLM-20 Summary.** Momentum, objective and deadline, threat tier, strategic nodes held, the campaign clock and pause state, active humans and operators by role, from `Hud` (CONTRACTS §7).
- **SLM-21 Freshness.** The page always shows the age of the data and a "FEED PAUSED" or "NO DATA" state (§7). It never shows stale data as live.

### 6.2 Phone and accessibility
- **SLM-22** On a narrow screen the map fills the view; the summary is a top strip; search, filters, detail and sitreps are a bottom sheet. Touch pan and pinch zoom; tap a unit for detail.
- **SLM-23** A text list of units (name, kind, side, health) mirrors the map and is keyboard and screen-reader usable, since a canvas is not. Visible focus, body text contrast ≥ 4.5:1, no colour-only meaning (OV-3), and motion that `prefers-reduced-motion` turns off (PS-6).

## 7. Security and privacy
- **SLM-24 CSP.** No inline script or style; `default-src 'none'`; `script-src`, `style-src`, `font-src` and `img-src` `'self'`; `connect-src` the exact feed origin, never a scheme or wildcard (as OVERLAY §0.4). Fonts and assets bundled.
- **SLM-25 Text.** All feed text is rendered with `textContent` or canvas `fillText`, never as HTML (SEC-OV-1). The page validates each file against the feed schema and its length caps and drops a file that fails; it treats the CDN as untrusted (B10).
- **SLM-26 No tracking.** No cookies, browser storage, analytics or third-party requests (Q-DM-3, Q-DM-4). The privacy note says what the host may log [UNVERIFIED: host-dependent] and that we keep no viewer data.
- **SLM-27 Abuse and cost.** There is no origin server to rate-limit: the CDN serves static files. The storage key can write only the feed prefix. The host MUST have a spending cap or free egress, plus an alert, so a traffic flood cannot become a bill [UNVERIFIED until a host is chosen].
- **SLM-28 Off switch.** Staff can stop publishing (publisher config, or a Command Center action later). The publisher then uploads a "paused" `state.json` with no units or names. A stopped feed MUST NOT stop or slow the stream.
- **SLM-29 Logs.** The publisher logs upload results and sizes, never feed content or keys.
- **SLM-30 Security review.** The publisher, its deploy workflow and the page get the `security-review` skill before merge: a new public surface and a new credential, and a deploy workflow is a CI change (CLAUDE.md).

## 8. Failure modes
| Failure | Effect | Handling |
|---|---|---|
| Publisher down or its WS dropped | Feed stops updating | It reconnects per WP-5 and gets a fresh `Snapshot`; the page shows the age, then "NO DATA" after PROPOSED 30 s |
| Upload fails | Same | Retry with backoff; stream unaffected; metric and alert after PROPOSED 2 min |
| Sim restart or tick regress | State jumps back | The publisher drops its state on a new `Welcome` (WIRE-PROTOCOL §6); the page accepts a lower tick after a theater or campaign change |
| Campaign ends | Fog would still apply | The feed stays fogged; the full reveal is the archive's job (FOW-1a), not this feed |
| Flood of viewers | CDN load | Static files; cap and alert (SLM-27) |
| CDN serves a tampered file | Hostile text or shapes | Schema and length checks, `textContent` only (SLM-25) |
| Kill switch or ban | Names must vanish | Next snapshot, at most PROPOSED 5 s + `max-age` (SLM-4, SLM-12) |
| Major contract version change | Old page cannot read | The file carries `v`; on a major mismatch the page shows "UPDATE REQUIRED" and reloads (as WP-1) |

## 9. Test plan
| Req | Test |
|---|---|
| SLM-1 | Tick bench with the publisher attached stays within WP-11's 5 ms; state hash unchanged with and without it (WIRE-PROTOCOL §8) |
| SLM-2, SLM-29 | Container config check: no stream or platform secrets in its environment; logs grepped for the key |
| SLM-3, SLM-4, SLM-7 | Integration test against a fake `PublicFeedTarget`: cadence, theater hash, cache headers, no history kept |
| SLM-5, SLM-21 | Page unit tests: interpolation stops at the next expected snapshot; age shown; "NO DATA" after the timeout |
| SLM-6 | Size bench at 1,000 entities, gzipped (build PR) |
| SLM-8 | Property test over random sim runs: every feed entity is in the coalition view (FOW-1 test, applied to the feed) |
| SLM-9, SLM-10 | Schema check: no `display_name`, `commander_id`, platform id or `server_build` in `contracts/public/` |
| SLM-11 | Property test: feed ids run 1, 2, 3… in first-shown order with no gaps; an entity keeps its id for the campaign; no kernel id appears in any file |
| SLM-12 | Kill switch on: no callsign or user ticker text in the next file; a forgotten commander's unit is absent next snapshot |
| SLM-13, SLM-19 | Detail panel renders only allowlisted fields; probation shows the tag only |
| SLM-14 | A `CommandRejected` cannot enter the sitrep list (schema) |
| SLM-15 | Shared projector tests run for both the overlay and the page |
| SLM-16, SLM-17, SLM-18 | Page unit tests: label culling, prefix search, `#cs=` focus, filters |
| SLM-22, SLM-23 | Playwright at phone and desktop sizes; keyboard walk-through; contrast and colourblind checks (NX-180 script) |
| SLM-24, SLM-25 | CSP present in the build; the callsign-shaped string `<img src=x onerror=alert(1)>` in a fixture renders literally (SEC-OV-1); a file over a length cap is dropped |
| SLM-26 | Repo check: no cookie, storage or third-party URL in the page source |
| SLM-28 | Off switch: the next file is "paused" with no units; tick unaffected |

## 10. Performance budget (PROPOSED)
- Page JS ≤ 200 KB gzipped; first useful map ≤ 3 s on a mid-range phone on 4G.
- Pan and zoom at ≥ 30 fps with 1,000 entities on a mid-range phone; ≥ 60 fps on desktop.
- Home upload ≤ 0.5 Mbps for the feed (SLM-6; HARDWARE.md:55 rule).

## 11. Rollout
1. Spec sign-off (this item), then the feed schema in `contracts/` and the publisher (needs NX-170, built).
2. The page, after NX-176 (built), NX-177 (units and FX) and NX-178 (HUD) so the drawing and wording code can be shared.
3. A host for the feed and page (open question 2), and NX-253 before names go public (SLM-12).
4. NX-516 sits in the P2 section of the tracker, but P2 is a closed, unlisted alpha (ROADMAP P2). A public page would advertise it. Recommended: build in P2 and test on an unlisted URL; link it from the public site with the public beta (open question 1).
5. Option (a), the real-time relay, only if viewers ask for it, with its own spec change and security review.

## 12. Open questions for the owner
Each has a recommendation; none is decided yet.
1. **When does the page go public?** Recommended: build in P2, unlisted URL for testers only; public link at the public beta. Alternative: public from P2.
2. **Where are the feed and page hosted?** GitHub Pages (the link page, PUBLIC-SITE §8) redeploys on each push, which does not suit a file that changes every 5 s [UNVERIFIED]. Recommended: object storage with a CDN, a spending cap and free or capped egress, on a subdomain of `hiveplex.live` (name PROPOSED); the link page stays on Pages. The host is chosen in the build PR from researched free-tier terms. Alternative: a small cloud VM, which also makes option (a) possible later.
3. **Opaque entity ids on the public feed (SLM-11)?** Recommended: yes, feed-local ids, to close the hidden-spawn-count leak. Alternative: publish kernel ids as the overlay gets them.
4. **"Every viewer's name": callsigns only?** Recommended: yes. Platform display names stay off every screen (Q-MOD-1, CONTRACTS §3.5); the full callsign is the "full name" of Q-UX-26. No site-only opt-out, since a callsign is a pseudonym and `!forget` already removes it. Alternative: add a "hide me on the site" preference (an IDENTITY change and a new command, rule 6a).
5. **Role and sector filters.** Recommended: ship side, domain, kind and owner filters first; add sector once sector shapes are on the wire (NX-182), and role only if a published kind→role map exists. Alternative: add both to the contracts in this item.
6. **Publisher `client_kind`.** Recommended: reuse `OVERLAY` in the first build (no contract change; it holds one of the 8 slots). Alternative: add a `PUBLISHER` value to `Hello.client_kind` (a contract change in the same PR, rule 6).
7. **Snapshot cadence.** Recommended: 5 s (PROPOSED), tunable. Faster costs more uploads and storage write operations [UNVERIFIED cost per host].
8. **PUBLIC-SITE PS-3 (no JavaScript).** The live page needs JavaScript. Recommended: PS-3 keeps applying to the link page only; this page has its own rules here. Needs the owner's sign-off as a PUBLIC-SITE change.
