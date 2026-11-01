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
