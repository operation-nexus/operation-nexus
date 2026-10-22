# Marketing Plan (living document)

Status: Draft, built with the owner by voice, 2026-10-17 (Q-MKT-1).

## Principles (owner)
- **High quality, never "AI slop."** Real gameplay footage and the owner's own voice. No mass-produced templated AI-narrated shorts (that also matches the YouTube inauthentic-content risk in PLATFORM-REALITY-CHECK).
- **Low effort for the owner.** Automation prepares material, and the owner approves or records with minimal time.
- **Transparent about AI** (Q-AI-6).

## Channels (owner direction: "C, but adapted")
| Channel | Role | Effort-saver |
|---|---|---|
| Devlogs (long-form YouTube) | Main story engine: "building a war game played by chat" | Devlog checkpoints + auto-captured footage (below) |
| Short-form (Shorts, TikTok, Reels) | Discovery | Auto-clip candidates → owner approves with one tap (CLIPS-REPLAY review queue). Owner voice or captions only. |
| Reddit / strategy communities | Launch moments, devlog shares | Post drafts prepared per milestone; owner posts. Each community's self-promo rules must be checked first. |
| Discord (existing, from the old channel) | Seed community, alpha testers | Announcements automated (War Briefing, NX-296) |

## Devlog checkpoints (owner request: "tell me when to record")
Because agents build fast, moments get missed. So:
1. Tracker items that are good devlog moments carry the label `devlog-moment`.
2. When such an item lands, the agent's completion report ends with a **DEVLOG CHECKPOINT** block: what to capture (screen recording, replay render, before/after), a 3–5 bullet talking-point outline for a voiceover, and a suggested title. The talking points are suggestions; the owner speaks in their own words.
3. **Auto-capture:** staging records short replay renders and screenshots at milestones (from deterministic replays, CLIPS-REPLAY) and stores them in a `devlog-footage` folder, so footage exists even if recording is forgotten.
4. Phase gates (ROADMAP) already require a recorded demo. That's the minimum devlog cadence.

## Operating model (owner grill, 2026-10-18; Q-MKT-14, Q-MKT-15, Q-OPS-11)
- **Where it lives:** the private `operation-nexus-vault` repo (`marketing/`, `production/`, `lore/` reserved, `assets/manifests/`). Access: owner and the `maintainers` team only. Brand-voice skills live there; generic process skills stay in this repo.
- **How it runs:** scheduled cloud sessions draft at most 5 items a week as one vault PR, holding no platform credentials. The owner reviews in one batch and posts manually from approved files until Brand Ops exists. Nothing is posted before the first-map gate (Q-MKT-3); profile polish and unpublished drafts are allowed now.
- **Voice:** an owner-written voice brief built through a short interview and hand rewrites, then reused as a ban list and examples file. A deterministic style check runs before any model review.
- **Production:** footage never goes into git. Video work (clipping, transcripts, captions) is local scripts on the owner's desktop; cloud agents work from the committed text.
- **Cost:** content-time agents have their own $20/month cap; cheaper tiers draft, the strongest tier reviews (Q-AI-10).
- **Measurement:** tagged `src` links and a weekly note of numbers the owner pastes from platform dashboards (Q-DM-4).
- **Research:** [SKILLS-AND-PLUGINS-RESEARCH](../review/SKILLS-AND-PLUGINS-RESEARCH-2026-10-18.md) (candidates only). Tracker: NX-338..NX-344.

## Open marketing questions
See OPEN-QUESTIONS (Q-MKT-*).

## Timing (Q-MKT-3, owner 2026-10-17)
- **"Done is better than perfect."** Publish early and imperfect. The devlog format *is* the work in progress.
- Free channels only for now; no paid ads.
- First public post: when the first map renders with moving units (P1/P2 boundary). Agents should flag this moment as a DEVLOG CHECKPOINT. Exception (owner, 2026-10-22): the text-only devlog 0 on Discord and Bluesky went out early; other early posts need the owner's say-so (Q-MKT-3).
- The old Discord announcement is held back at first, to measure organic traction.
- Simulated bot battles can be shown, **clearly labeled "simulated test"**.

## Research and follow-up docs (2026-10-18)
- [MARKETING-AND-PRODUCTION-RESEARCH](../review/MARKETING-AND-PRODUCTION-RESEARCH.md): gaps, comparables, pipeline, launch plan, backlog candidates (NX-337).
- [SOCIAL-CHANNEL-AUTOMATION-RESEARCH](../review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md) and the [BRAND-OPS](../specs/BRAND-OPS.md) draft: account setup, API limits, the review/approval service.
- [LEGAL-AND-NAME-SWEEP](../review/LEGAL-AND-NAME-SWEEP-2026-10-18.md): licenses, platform terms, name round 4.
- [AGENT-TEAMS](AGENT-TEAMS.md): the marketing and lore agent teams (deferred until the community grows).
- Decisions: Q-MKT-5..8, Q-LEGAL-9..10, Q-MOD-7..8, Q-DM-4 in OPEN-QUESTIONS.

