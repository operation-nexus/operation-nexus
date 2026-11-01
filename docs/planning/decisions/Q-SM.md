# Decided questions: Q-SM

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## From the detailed system specs (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-SM-1 | Give objective selection its own `objective` RNG sub-stream? | Yes. Then changing objective logic doesn't shift director randomness. | ✅ 2026-10-17: A, separate `objective` RNG stream. Owner principle: **never share dice between subsystems.** |
| Q-SM-2 | How long does an idle landed unit linger before despawning? | Balance key `slots.idle_despawn_s`, tuned by the harness | ✅ 2026-10-17: A, `slots.idle_despawn_s` starts at about 5 min (PROPOSED), tuned by the harness and adjustable in admin. Owner prefers as long as practical. |
| Q-SM-3 | Custom callsigns: manual owner approval or automated moderation? | Automated moderation + review queue. Manual approval during alpha. | ✅ 2026-10-17: A, automated moderation approves most; borderline → review queue; owner manually approves all during alpha |
| Q-SM-4 | After the AAR, same theater with a new seed or rotate theaters? | Same hand-authored theater with a new seed until a second theater exists | ✅ 2026-10-17: A, rotate theater archetypes with no back-to-back repeats; reuse the first theater with a new seed until more exist. Admins can override via scheduling (ADMIN-RBAC). |
| Q-SM-5 | How long with no active humans before the campaign clock pauses? | Balance key `campaign.pause_after_no_humans_s`, tuned by the harness | ✅ 2026-10-17: Superseded. There's no automatic clock pause (Q-GD-4 amended). `campaign.pause_after_no_humans_s` is removed; Pattern-of-Life keys replace it (THREAT-DIRECTOR §5a). |
| Q-SM-6 | Approve STATE-MACHINES-AND-FLOWS? | Approve the sim-side machines (§4.1–4.6) now; grill the runtime side (§4.7–4.10, §5) when P2 starts on it. | ✅ 2026-10-21: yes. |
| Q-SM-7 | How slow is capture by logistics units ("yes (slow)", CONFIG §7.3)? | A logistics unit counts as half a capturer in the capture formula (`capture.logi_weight` PROPOSED 0.5). | ✅ 2026-10-21: yes. |
| Q-SM-8 | Garrison and empty-base capture multipliers (Q-GD-32) | Capture-time multipliers `capture.garrison_mult` 3.0 (a defender that cannot contest is present) and `capture.empty_base_mult` 0.5 (none), PROPOSED; a combat-capable defender still freezes capture. | ✅ 2026-10-21: yes. |
| Q-SM-9 | Time-limit score weights (Q-GD-29) | Score = 100 × average share of nodes held + 5 per completed objective (`campaign.score.*`, PROPOSED). | ✅ 2026-10-21: yes. |
| Q-SM-10 | Units at a captured base: who escapes (Q-GD-32)? | A ground unit escapes when a road route to a friendly base exists; an aircraft when its fuel reaches one of its landing bases; others are destroyed. | ✅ 2026-10-21: yes. |
| Q-SM-11 | How is a timed objective picked? | Uniformly among frontline nodes (road edge to an other-side or unowned node) with the `objective` stream; never the sanctuary or the Static's HQ; capture if enemy-held, hold for the period if own. | ✅ 2026-10-21: yes. |
| Q-SM-12 | Operator-driven objectives and a free-for-all mode | Keep `campaign.objective_mode: off` as it is; record objective voting / higher-rank suggestions and a self-directed mode that also hides the NEEDED list as GAMEPLAY-LATER future candidates. | ✅ 2026-10-21: yes (owner idea). |
