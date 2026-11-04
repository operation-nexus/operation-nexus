# Decided questions: Q-CT

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## From the detailed system specs (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-CT-1 | Chat over the length cap: reject or truncate? | Reject. Truncation could turn it into a different valid command. | ✅ 2026-10-17: A, reject with a "too long" note in the batched digest; never truncate |
| Q-CT-2 | Is the campaign seed public? | Hidden during the campaign, published after `CampaignEnded` | ✅ 2026-10-17: A. Hidden during the campaign. After `CampaignEnded`, publish the seed and a **"what you didn't see" recap** (summary and/or narrative) that labels every enemy decision as made by the **AI rules, the LLM advisor, or a human Game Master**. |
| Q-CT-3 | Show tracers from enemy shooters we can't see? | No for MVP. Revisit after the readability study (NX-034). | ✅ 2026-10-17: A, no tracers from hidden shooters (impact shown as "unknown contact"). **Playtest note:** revisit in the readability study (NX-034). |
| Q-CT-4 | Show an "active humans" count on stream? | Yes. Humans only; shows `—` until known. | ✅ 2026-10-17: A, "Operators active" shows humans only, and `—` when unknown. **Plus a breakdown** by role or doctrine (e.g. Strike 5 · Recon 2 · Logistics 4) and optionally by rank band. It goes in the Campaign Status rotating panel, from the PresenceSnapshot event. |
| Q-CT-5 | MVP enemy/garrison unit roster (garrison AAA and infantry; enemy SAM site, radar, fighter, armor, convoy)? | Confirm once the first theater sketch exists (NX-008) | ✅ 2026-10-17: A, small MVP set (SAM, radar, armor, convoy + garrison), confirmed at the theater sketch. New platforms come through the **hot-loadable unit content pipeline** (CONFIG-AND-CONTENT §7a). |

## Foundations grilling (2026-10-19): NX-021, NX-040, NX-019/NX-050

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-CT-6 | NX-021 scope | Pipeline plus seed schemas only (common ids and enums, ChatEnvelope, JOIN, UnitSpawned, Hello, Welcome, Snapshot); every other schema lands with the code that implements it (rule 6a). | P0 | ✅ 2026-10-19 |
| Q-CT-7 | Contract types in the kernel | `nexus.core` may import generated `nexus.contracts`; events built with `model_construct` on the hot path; validation at boundaries and in tests. | P0 | ✅ 2026-10-19 |
| Q-CT-8 | Versioning before launch | `contracts/VERSION` starts at 0.1; 0.x bumps MINOR and the compat check only reports; MAJOR enforcement from 1.0; compat diff against the PR base branch, not `main`. | P0 | ✅ 2026-10-19 |
| Q-CT-9 | Breaking-change detection | Small tested script in `scripts/` (removed properties, newly required fields, changed types, removed enum values); no new dependency. | P0 | ✅ 2026-10-19 |
| Q-CT-10 | Tools and commands | datamodel-code-generator (Python dev dep) and json-schema-to-typescript (overlay dev dep), pinned with rule-8 justification; `make contracts`; CI `contracts` job fails on drift; generated code committed at `services/sim/src/nexus/contracts/` and `apps/overlay/src/contracts/`. | P0 | ✅ 2026-10-19 |
| Q-CT-11 | What part of CONTRACTS is approved | §3 (conventions, ids, versioning, pipeline) Approved; §4–8 catalogs stay Draft and are approved piece by piece as handlers land. | P0 | ✅ 2026-10-19 |
| Q-CT-12 | NX-021 seed list after reading §7 | `Snapshot` (about 15 nested views incl. Hud) and `Welcome` (TheaterStatic) leave the seed and land with NX-170; the seed is common ids and used enums, ChatEnvelope, the command header and JOIN (`CommandKind` = JOIN only), UnitSpawned and Hello. Revises Q-CT-6. | P0 | ✅ 2026-10-19 |
| Q-CT-13 | WIRE-PROTOCOL readiness for NX-170 (2026-11-04): how does the overlay authenticate to the WS (SEC-API-2)? | A static capability secret from `.env`, carried in the OBS URL fragment `#token=` (never sent to the server or logged), sent by the page in `Hello.capability_token`, compared in constant time; loopback or private-network bind; Origin allowlist; rotate by changing `.env` and the OBS URL | P2 | ✅ 2026-11-04 (owner, in chat): as recommended. WIRE-PROTOCOL §7. |
| Q-CT-14 | Which library serves the overlay WS? | FastAPI/Starlette + uvicorn (ADR-0004) | P2 | ✅ 2026-11-04 (owner, in chat): FastAPI/Starlette + uvicorn. The rule 8 write-up goes in the NX-170 (b) PR. |
| Q-CT-15 | WIRE-PROTOCOL behavior NX-170 needs: frame build, cadence, handshake, backpressure, close codes, scope | One shared Delta per tick built on the sim thread, Snapshot on demand at most once per tick; Delta every tick, Hud as its own message at ≤ 1 Hz, Snapshot only on connect, resync or gap; Hello → Welcome → Snapshot with `last_tick` a hint only; per-client queue 3, connection cap 8, 4 KB inbound, ping 15 s / idle 45 s, Ack 20/s (all PROPOSED); close codes 1001, 1009, 4001–4006; `Control` RELOAD and RESYNC only in P2; Audio, kill-switch banners, PiP and vertical deferred (NX-225, NX-253, NX-179, NX-180b); NX-170 split into (a) schemas and frames, (b) server, (c) bench | P2 | ✅ 2026-11-04 (owner, in chat): lead defaults approved; WIRE-PROTOCOL is Approved (WP-1…WP-14, §5–§9). |
