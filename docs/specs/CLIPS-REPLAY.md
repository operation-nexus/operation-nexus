# SPEC: Replays & Clips

Status: Draft · Tracker: NX-233…NX-239

## 1. Replays
Each campaign is stored with: the seed, the config hash, the command log and the retained snapshots (DATA-MODEL §6.1). The replay CLI re-simulates the campaign from those for developers only: it reproduces a campaign on the same commit and pinned image (SIM-CORE SC-16), not an archive. **Public replays and clips come from recorded output (Q-SIM-13, Q-SIM-18):** while a campaign runs the runtime records two streams, a redacted coalition frame stream and a private full-truth frame stream. The truth stream is never served until `campaigns.ended_at` is set (RP-2, FOW-1a). A public replay viewer (on the companion site, later) is fed **pseudonymous** views (SEC-DATA-2): `commander_id` only, resolved to approved callsigns at view time, and deleted commanders show as `REDACTED-<tag>` (e.g. `REDACTED-7KQ2`), where the tag is the random 4-character value stored at deletion (Q-DM-2, Q-ALN-29, DATA-MODEL §4.2, §6.4). The tag is unique per deleted commander, so two deleted actors in one replay stay distinct; it is not derived from any identifier, so it can't be reversed. Storage was measured in the NX-345 spike: about 250 MB per stream per game hour at the worst case (indicative; docs/review/NX-345-BENCH.md). **Measured storage (NX-032):** the command log and snapshots that the replay CLI re-simulates from were measured with `tools/replay/measure.py`, which runs the real `SimRuntime` with the test stub handler (one unit spawned per JOIN) for 36,000 ticks (one game hour) at a STAND-IN rate of 120 commands per minute (one every 5 ticks; not a measured chat rate), snapshots every 300 ticks, on a 4-core Intel Xeon cloud VM (Linux 6.18, CPython 3.12). Result: the command log is 121 segments, 1,334,852 bytes (about 1.3 MB per game hour, about 185 bytes per command, zstd-compressed); after retention (SIM-CORE §5: newest 20 plus the earliest of each hour) 21 snapshots remain, 634,843 bytes, the largest 33,817 bytes. Snapshot size grows with the entity count (7,200 stub units at the end of this run), and the stub has no gameplay, so it is a floor: it covers the log and snapshot overhead only and must be re-measured once real handlers and entities land. Retained snapshots are bounded (20 plus one per hour), so their total is not a per-hour rate on a long campaign. The replay frame streams above are far larger than either. Retention limits and archiving are open (Q-SIM-29).

**Fog of war by campaign state (Q-ALN-21):**
- **RP-1** While the campaign is running, every replay view, clip and export shows only what the coalition could see (FOW-1).
- **RP-2** Once the campaign has ended (`campaigns.ended_at` is set), archives and recaps are exempt from FOW-1: the full campaign archive and the AAR "what you didn't see" view may reveal everything, including enemy positions the coalition never saw.
- **RP-3** Pseudonymity does not relax at campaign end: the full reveal shows hidden entities, never names beyond approved callsigns.
- Test: a replay view requested for a running campaign contains no entity that fails the coalition visibility predicate; the same view after `campaigns.ended_at` is set contains the hidden entities; both contain no display name or platform id.
- Test (Q-ALN-29): a fixture replay with two deleted commanders renders two different `REDACTED-<tag>` names, each equal to `REDACTED-` plus the commander's stored tag.

## 2. Excitement score
A rolling 15 s score combines missiles in flight, kills, captures, human involvement, and objective completion. The weights are configurable. When the score crosses a threshold, a clip job is created for `[t-25 s, t+5 s]`.

## 3. Clip rendering (P3)
A headless render worker plays the recorded frames for the window (Q-SIM-18) in a browser at 1080×1920 and records it with FFmpeg (argv list, SEC-CLIP-2), together with the cached TTS audio. It runs at low priority. If the GPU is busy, it runs when the broadcast host is idle, or on another machine. A clip rendered or published while its campaign is running uses the FoW-redacted view (RP-1); a full-reveal clip is possible only after the campaign has ended (RP-2).

## 4. Publishing
Finished clips go to a **review queue** in the admin console. The owner approves each one and uploads it manually or via the API (P5+, after the platform audits). No templated auto-narrated Shorts at volume, because of the YouTube "inauthentic content" policy risk.

## 5. Open questions
- Decided and folded in (2026-10-18): Q-ALN-21 (RP-1…RP-3), Q-ALN-29 and Q-DM-2 (`REDACTED-<tag>`, §1).
- None open.
