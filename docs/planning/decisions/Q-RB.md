# Decided questions: Q-RB

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Admin/RBAC and support redemptions (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-RB-1 | Can moderators pause campaigns? | Yes, they can pause. Resuming needs a GM or admin. | ✅ 2026-10-17: A, moderators can pause, but only with a **required reason** (category + short note). Resume: GM/admin/owner. Every pause **immediately alerts the owner** (who, when, why). Optional AI assessment ("situation report: should we stay paused?") is attached. One-tap resume from phone/Discord, voice later (ADMIN-RBAC §pause flow, NX-286). |
| Q-RB-2 | Does a platform-scoped moderator's ban cascade across the commander's linked platforms? | Yes. Unbanning needs an admin. | ✅ 2026-10-17: A, bans cascade across all linked platforms; unban requires an admin |
| Q-RB-3 | Two-person rule with a single owner? | Allow self-approval with an audit flag, plus a delay (PROPOSED 10 min) on campaign end and rules publish | ✅ 2026-10-17: A, self-approval allowed while solo, audit-flagged, with a cancellable safety delay (~10 min, PROPOSED) on campaign end and rules publish. Second-person approval once more admins exist. |
| Q-RB-4 | Is the admin console exposed publicly? | No. Tailnet + Discord only through P3. A DAST pass is required before any public exposure. | ✅ 2026-10-17: Implied by Q-ARCH-7: the Command Center is private (tailnet + Discord); DAST before any public exposure |
| Q-RB-5 | Is a harness dry-run mandatory before publishing rules? | Mandatory for next-campaign publishes. Optional for hot keys, and a skip is flagged in the audit log. | ✅ 2026-10-17: A, harness dry-run mandatory for next-campaign publishes; optional for hot keys, and a skip is audit-flagged |
| Q-RB-6 | Does threat memory keep learning during a GM FULL takeover? | Yes | ✅ 2026-10-17: A, threat memory keeps learning during GM FULL takeover |
| Q-RB-7 | Do GM sitreps get a distinct TTS voice? | Yes, a different preset with the same radio filter | ✅ 2026-10-17: Implied by the voice cast (AUDIO-TTS §2a): Game Master has its own voice profile |
