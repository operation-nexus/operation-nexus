# Specs

| Spec | Scope | Phase |
|---|---|---|
| [SIM-CORE](SIM-CORE.md) | Tick loop, world model, determinism, budgets | P1 |
| [GAMEPLAY](GAMEPLAY.md) | Roles, commands, logistics, capture, win/loss, campaign | P1 |
| [COMBAT](COMBAT.md) | Targeting, hit probability, damage, wrecks, stance, who can shoot whom | P1 |
| [GAMEPLAY-LATER](GAMEPLAY-LATER.md) | Parked later-phase gameplay rules split from GAMEPLAY (Q-GP-1) | P3-P4 |
| [FOG-OF-WAR](FOG-OF-WAR.md) | Sensor tiers, redaction, director fairness | P1 |
| [THREAT-DIRECTOR](THREAT-DIRECTOR.md) | Enemy AI tiers, budget, threat memory, advisor | P1 / P4 |
| [WIRE-PROTOCOL](WIRE-PROTOCOL.md) | Server→overlay WS protocol, versioning | P2 |
| [OVERLAY](OVERLAY.md) | Broadcast layout, readability, accessibility, PiP | P2 |
| [CHAT-GATEWAY](CHAT-GATEWAY.md) | Platform adapters, normalization, rate limits, replies | P2 |
| [IDENTITY](IDENTITY.md) | Commanders, callsigns, OAuth linking | P2 / P3 |
| [PROGRESSION](PROGRESSION.md) | XP, ranks, merit, doctrines, cosmetics, anti-farming | P3 / P4 |
| [AUDIO-TTS](AUDIO-TTS.md) | Audio buses, sitreps, TTS, night mode | P2 / P3 |
| [CLIPS-REPLAY](CLIPS-REPLAY.md) | Replays, excitement scoring, clip review queue | P3 |
| [LLM-ADVISORS](LLM-ADVISORS.md) | Advisor, narrator, `!order` parser, budgets | P4 |
| [CONTRACTS](CONTRACTS.md) | Enums, commands, events, wire messages, internal and admin API | P0–P2 |
| [DATA-MODEL](DATA-MODEL.md) | SQLite schema, ledgers, snapshot and log formats, retention, backups | P1–P3 |
| [CONFIG-AND-CONTENT](CONFIG-AND-CONTENT.md) | Config layers, balance key reference, unit catalog, theater format | P1 |
| [STATE-MACHINES-AND-FLOWS](STATE-MACHINES-AND-FLOWS.md) | Lifecycles, transition tables, end-to-end sequences | P1–P2 |
| [ADMIN-RBAC](ADMIN-RBAC.md) | Roles and permissions, moderation, GM takeover, scheduling, rules editor, theater generation | P2–P4 |
| [SUPPORT-REDEMPTIONS](SUPPORT-REDEMPTIONS.md) | Bits, channel points, Super Chats, tips → capped redemptions | P4–P5 |
| [OPS-ADMIN](OPS-ADMIN.md) | Watchdog, observability, alerting, admin console, kill switch, runbooks | P2 |
| [DISCORD-SERVER-SETUP](DISCORD-SERVER-SETUP.md) | Owner-run setup of the community Discord server: layout, roles, permissions, script rules | P0 |
| [PUBLIC-SITE](PUBLIC-SITE.md) | The public site, starting with the one-page link page at hiveplex.live | P0 (link page), P3 (replays and stats) |

Specs start as **Draft**. They move to **Approved** only after the owner signs off and every linked open question that blocks the phase is answered.
