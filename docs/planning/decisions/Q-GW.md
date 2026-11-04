# Decided questions: Q-GW

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Admin/RBAC and support redemptions (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-GW-1 | Command rate limits | Stricter, per command class, admin-adjustable live, slow-mode toggle, cooldown ring + batched replies (CHAT-GATEWAY §5) | P2 | ✅ 2026-10-17: A. Per-class limits as in CHAT-GATEWAY §5, admin-adjustable live; slow-mode toggle; cooldown ring + batched replies |

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-GW-2 | Accept commands from Twitch Shared Chat or raid-origin viewers? (API specifics [UNVERIFIED]) | own channel only | ✅ 2026-10-18: Raid-origin viewers are normal viewers in our chat and are accepted (normal rate limits apply; a raid may trigger a small 'reinforcements arriving' world event). Twitch Shared Chat messages originating from other channels are ignored by default; config switch gateway.shared_chat.accept_foreign (default false) can enable them after the source-channel API fields are verified [UNVERIFIED]. |
| Q-GW-3 | CHAT-GATEWAY readiness (2026-11-04): the gateway as a separate service (AGENTS.md layout) or in-process (ADR-0001, SYSTEM-DESIGN)? | In-process `nexus.gateway` in the app; the adapter runs on its own asyncio thread and calls the thread-safe `Inbox.submit` | P2 | ✅ 2026-11-04 (owner, in chat): in-process. CHAT-GATEWAY §1; AGENTS.md layout fixed in its own PR. |
| Q-GW-4 | Approve CHAT-GATEWAY for NX-190/192/041 with the lead defaults? | Yes: ChatSource/ChatSink ports, IdentityResolver fake until NX-200, per-tick NameDirectory snapshot, normalizer in `nexus.moderation`, fixed pipeline order, token-bucket limits, DigestBuilder for always-answer, LocalSim conformance before any Twitch credentials, JOIN/REBASE first then one PR per command (GW-1…GW-22); tunable values PROPOSED (global cap 50/tick, spam threshold 10 rejects in 60 s, digest 30 s) | P2 | ✅ 2026-11-04 (owner, in chat): approved with lead defaults. YouTube (§3) stays Draft. |
| Q-GW-5 | Raw chat retention: SEC-DATA-4's 7 days vs the Twitch developer agreement's 24 h cache limit (PLATFORM-POLICY-VERIFICATION T19) | Keep raw envelopes at most 24 h; only the resolved command log longer | P2 | ✅ 2026-11-04 (owner, in chat): 24 h. GW-16; SEC-DATA-4 and DATA-MODEL updated in their own PR. |
| Q-GW-6 | May bot replies @-mention the viewer's platform login? | Yes, in that platform's chat only; never on the overlay, TTS or logs (Q-MOD-1) | P2 | ✅ 2026-11-04 (owner, in chat): yes. GW-15. |
