# SPEC: Replays & Clips

Status: Draft · Tracker: NX-233…NX-239

## 1. Replays
Each replay is stored as: the seed, the config hash, the command log, and hourly snapshots. The replay CLI re-simulates the campaign from those. A public replay viewer (on the companion site, later) is fed **redacted, pseudonymous** views (FOW-1, SEC-DATA-2). Measure storage size in P1 instead of trusting the 35 MB estimate.

## 2. Excitement score
A rolling 15 s score combines missiles in flight, kills, captures, human involvement, and objective completion. The weights are configurable. When the score crosses a threshold, a clip job is created for `[t-25 s, t+5 s]`.

## 3. Clip rendering (P3)
A headless render worker replays the window from the nearest snapshot in a browser at 1080×1920 and records it with FFmpeg (argv list, SEC-CLIP-2), together with the cached TTS audio. It runs at low priority. If the GPU is busy, it runs when the broadcast host is idle, or on another machine.

## 4. Publishing
Finished clips go to a **review queue** in the admin console. The owner approves each one and uploads it manually or via the API (P5+, after the platform audits). No templated auto-narrated Shorts at volume, because of the YouTube "inauthentic content" policy risk.
