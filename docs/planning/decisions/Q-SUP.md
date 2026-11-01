# Decided questions: Q-SUP

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Admin/RBAC and support redemptions (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-SUP-1 | Can **money** (Bits, Super Chat, tips) buy QoL perks such as a respawn skip or a queue jump, or only cosmetics and shoutouts? Channel points can buy capped QoL either way. | Money buys cosmetics, shoutouts and spectacle only. QoL is channel points only. That avoids "pay to win" perception. | ✅ 2026-10-17: Money buys cosmetics, shoutouts and spectacle only; QoL via channel points only |
| Q-SUP-2 | Show donor messages on stream? | Not in v1. Callsign-only shoutouts. Messages may come later behind moderation, and are never spoken by TTS. | ✅ 2026-10-17: No free-text donor messages in v1. **Owner idea:** templated "rally call" instead (Q-SUP-6) |
| Q-SUP-3 | Third-party tips (Ko-fi, Streamlabs, StreamElements)? | Later (P5), pick one. Start with platform-native support. | ✅ 2026-10-17: A, platform-native support first; one third-party tip service later (P5) |
| Q-SUP-4 | Confirm ADR-0011: no in-game currency in v1? | Yes. Direct capped redemptions; revisit later via a new ADR plus legal review. | ✅ 2026-10-17: No in-game currency in v1 (ADR-0011 accepted) |
| Q-SUP-6 | Owner idea: a "rally call" so the crowd can coordinate like a hive mind. Example: "VIPER-27 calls: ATTACK STRAIT BRIDGE" pinned on the map. | **Templated, not free text:** `!rally <node> <attack/defend/supply>` shows a map pin and a banner with the callsign. Unlocked free at Captain (O-3) with a cooldown. Channel points or donations make it more prominent (bigger banner, longer pin) but never more powerful. It only informs; it never controls other players' units. | ✅ 2026-10-17: A, templated rally call; free at Captain with cooldown; points or donations only make it more prominent |
| Q-SUP-5 | Retention of financial support records? | Keep them as long as your tax and accounting needs require. Ask an accountant; this isn't something we can define for you. | ✅ 2026-10-17: A, keep all financial support records until an accountant advises; donor messages deleted after 30 days |

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-SUP-7 | Channel-point supply drops grow with audience size, which violates TS-1 | a fixed global hourly cap, or drop the category | ✅ 2026-10-18: Fixed global cap on supply-drop redemptions per hour (support.supply_drop.max_per_hour, value PROPOSED/TBD by harness) plus a shared cooldown; reward shows 'on cooldown' when capped. Enforced in our code and mirrored in the platform's reward settings where available [UNVERIFIED exact Twitch options]. Satisfies TS-1 (no crowd-size scaling). |
