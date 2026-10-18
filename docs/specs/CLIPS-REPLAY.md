# SPEC: Replays & Clips

Status: Draft · Tracker: NX-233…NX-239

## 1. Replays
Each replay is stored as: the seed, the config hash, the command log, and hourly snapshots (one per game-time hour, DATA-MODEL §6.1). The replay CLI re-simulates the campaign from those. A public replay viewer (on the companion site, later) is fed **pseudonymous** views (SEC-DATA-2): `commander_id` only, resolved to approved callsigns at view time, and deleted commanders show as `REDACTED-<tag>` (e.g. `REDACTED-7KQ2`), where the tag is the random 4-character value stored at deletion (Q-DM-2, Q-ALN-29, DATA-MODEL §4.2, §6.4). The tag is unique per deleted commander, so two deleted actors in one replay stay distinct; it is not derived from any identifier, so it can't be reversed. Measure storage size in P1 instead of trusting the 35 MB estimate.

**Fog of war by campaign state (Q-ALN-21):**
- **RP-1** While the campaign is running, every replay view, clip and export shows only what the coalition could see (FOW-1).
- **RP-2** Once the campaign has ended (`campaigns.ended_at` is set), archives and recaps are exempt from FOW-1: the full campaign archive and the AAR "what you didn't see" view may reveal everything, including enemy positions the coalition never saw.
- **RP-3** Pseudonymity does not relax at campaign end: the full reveal shows hidden entities, never names beyond approved callsigns.
- Test: a replay view requested for a running campaign contains no entity that fails the coalition visibility predicate; the same view after `campaigns.ended_at` is set contains the hidden entities; both contain no display name or platform id.
- Test (Q-ALN-29): a fixture replay with two deleted commanders renders two different `REDACTED-<tag>` names, each equal to `REDACTED-` plus the commander's stored tag.

## 2. Excitement score
A rolling 15 s score combines missiles in flight, kills, captures, human involvement, and objective completion. The weights are configurable. When the score crosses a threshold, a clip job is created for `[t-25 s, t+5 s]`.

## 3. Clip rendering (P3)
A headless render worker replays the window from the nearest snapshot in a browser at 1080×1920 and records it with FFmpeg (argv list, SEC-CLIP-2), together with the cached TTS audio. It runs at low priority. If the GPU is busy, it runs when the broadcast host is idle, or on another machine. A clip rendered or published while its campaign is running uses the FoW-redacted view (RP-1); a full-reveal clip is possible only after the campaign has ended (RP-2).

## 4. Publishing
Finished clips go to a **review queue** in the admin console. The owner approves each one and uploads it manually or via the API (P5+, after the platform audits). No templated auto-narrated Shorts at volume, because of the YouTube "inauthentic content" policy risk.

## 5. Open questions
- Decided and folded in (2026-10-18): Q-ALN-21 (RP-1…RP-3), Q-ALN-29 and Q-DM-2 (`REDACTED-<tag>`, §1).
- None open.
