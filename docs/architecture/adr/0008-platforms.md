# ADR-0008: Platform support order: Twitch, then YouTube, then Kick; TikTok deferred

- Status: Proposed (Q-PROD-2)
- Date: 2026-10-17

## Context
See `docs/review/PLATFORM-REALITY-CHECK.md`. Twitch EventSub is first-class. YouTube Live chat is quota-bound: polling uses up the default quota in hours, so `streamList` is required, and each reply costs 20 units. **TikTok has no official API to read LIVE chat.** Available libraries reverse-engineer it, violate the ToS, and depend on third-party signing servers. TikTok LIVE also penalizes unattended streams and gates RTMP access.

## Decision
- P2 (closed alpha): Twitch only.
- P3: YouTube via `streamList` with a quota dashboard. Apply for a quota increase early.
- Kick is optional, if it's cheap to add (it has an official API and signed webhooks).
- TikTok is deferred. It may be revisited as a **view-only** simulcast (no chat control), or if an official API appears. Any reverse-engineered adapter needs a new ADR that accepts the ToS and ban risk explicitly, and it must run isolated with no other credentials.
- Clips are never auto-uploaded publicly. They go to a review queue, and the owner posts them (YouTube and TikTok uploads stay private until the platforms' audits pass).

## Consequences
The launch audience is smaller, but the foundation is ToS-compliant and reliable. The adapter interface keeps new platforms cheap to add.
