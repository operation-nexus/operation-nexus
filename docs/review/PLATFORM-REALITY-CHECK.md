# Platform & Dependency Reality Check

Date: 2026-10-17 · Method: web research (search-result excerpts; some official pages were unreachable from the research environment). Items marked **[UNVERIFIED]** come from secondary sources and must be re-checked before they drive a decision.

## Top risks, ranked
1. **TikTok has no official API for reading LIVE chat.** TikTok LIVE policy also works against unattended, TTS-narrated streams.
2. **YouTube quota:** polling `liveChatMessages.list` uses up the default 10,000 units/day in about 1–3 h. `streamList` is mandatory. Chat posts cost 20 units each.
3. **Auto-posting Shorts/TikToks is private-only** until Google's and TikTok's audits pass.
4. **Twitch bot send limits** are 20 msgs/30 s (100 if the bot is a moderator or VIP). Verified-bot reviews are paused.
5. **LiteLLM supply-chain compromise (March 2026).** Pin with hashes, or skip LiteLLM.
6. **Piper is now GPL-3.0** (piper1-gpl). Licensing review needed.
7. The 24/7 browser render + dual encode **needs a GPU**.

## 1. Twitch
- **Reading chat:** EventSub `channel.chat.message` is the recommended path and IRC is legacy. The bot needs `user:read:chat`. To send, it needs `user:write:chat` and uses the Helix Send Chat Message API. With an app token it also needs `user:bot`, plus `channel:bot` granted by the broadcaster or bot moderator status.
- **Rate limits:** 20 msgs/30 s for a normal account and 100/30 s for a mod or VIP. Exceeding them makes Twitch ignore the bot for 30–60 min.
  - **Implication:** make the bot a moderator, and aggregate acknowledgements on the overlay. Per-command chat replies are impossible at volume.
- **Whispers:** Helix whispers need a verified phone. Limits are 40 unique recipients/day and 3/s, and delivery can fail silently. The public one-time-link approach is right, but the link must not be usable by onlookers (see THREAT-MODEL).
- **24/7 streams:** reruns must be labelled. A broadcast reportedly ends after 48 h, so plan for auto-restart **[UNVERIFIED]**. No explicit rule against unattended interactive games was found. Rewards/drops abuse is banned.
- Sources: dev.twitch.tv/docs/chat/irc-migration, dev.twitch.tv/docs/chat/authenticating, dev.twitch.tv/docs/irc, dev.twitch.tv/docs/chat/whispers, discuss.dev.twitch.com/t/54596

## 2. YouTube Live
- **Quota:** the default is 10,000 units/day. `liveChatMessages.list` costs 5 units and `insert` costs 20. `streamList` (gRPC server streaming) is listed at 5 units, and whether that is per connection or per message is unconfirmed **[UNVERIFIED]**.
- **Math:** polling at the suggested interval uses up the quota in roughly 1–3 h. Polling within quota means one call per ~43 s, which is useless for live play.
  - **Implication:** use `streamList` and keep reconnects to a minimum. Treat chat replies as nearly unavailable. Apply for a quota increase, which needs a compliance audit.
- **Policy:** in July 2025 the YPP "repetitious content" policy was renamed "inauthentic content" (mass-produced or templated). The interactive sim is defensible. **Templated daily LLM-voiceover Shorts are exactly what the policy targets.**
- Sources: developers.google.com/youtube/v3/determine_quota_cost, …/live/docs/liveChatMessages/streamList

## 3. TikTok LIVE (biggest hole)
- **There is no official API for reading LIVE comments.** Libraries like TikTokLive and tiktok-live-connector are reverse-engineered, often rely on third-party signing services, break regularly, and violate the ToS.
- **Eligibility:** 18+ and about 1,000 followers. Access to an RTMP key or LIVE Studio is gated with unpublished criteria. Keys reportedly rotate every session, which conflicts with unattended 24/7 operation **[UNVERIFIED]**.
- **Policy:** static screens, no presenter, or long stretches without interaction can make a LIVE "not eligible for recommendation".
- **Implication:** TikTok is optional and best-effort, or deferred. The game must not depend on it.

## 4. Kick
A public API exists: OAuth 2.1 with PKCE, a `chat:write` scope, and Ed25519-signed webhooks (at-least-once delivery, dedupe on message id) **[UNVERIFIED — docs unreachable]**. It's a possible third platform with an official API, unlike TikTok.

## 5. Auto-upload of clips
- **YouTube:** uploads from unverified API projects created after 2020-07-28 are locked to private until a compliance audit passes. `videos.insert` historically costs 1,600 units, about 6 uploads/day **[a newer cost is UNVERIFIED]**.
- **TikTok:** an unaudited Content Posting API client can post private-only.
- **Implication:** Phase 1 clipping writes to a review folder, and a human posts manually.

## 6. TTS
- Piper moved from rhasspy/piper (MIT, archived Oct 2025) to OHF-Voice/piper1-gpl (**GPL-3.0-or-later**, because it embeds espeak-ng). Running it server-side without distributing it is generally fine. Each voice model has its own dataset license; check every MODEL_CARD.
- Kokoro-82M is reported as Apache-2.0 **[UNVERIFIED primary]**. It uses espeak-ng for some phonemization, so check that too.
- Gemini TTS costs roughly $0.015 per minute of speech **[UNVERIFIED — pricing page unreachable]**.

## 7. LLM tooling
- **LiteLLM:** malicious PyPI releases 1.82.7 and 1.82.8 (2026-03-24) dropped a `.pth` credential stealer, reportedly via a compromised scanner in LiteLLM's CI.
  - **Implication:** use hash-pinned lockfiles, run the LLM gateway in an isolated container with no platform tokens, or call provider SDKs directly.
- **Instructor** (567-labs) is active, v1.15.x as of mid-2026.

## 8. Broadcast host
- **Option A:** Xvfb + Chromium (headed, for WebGL) + PipeWire + FFmpeg → RTMP.
- **Option B:** OBS on Linux under Xvfb, or a real desktop session. The Aitum Vertical (9:16) plugin needs real OBS.
- Without a GPU, Chromium falls back to SwiftShader and encoding falls back to x264. Dual 60 fps outputs need NVENC (or equivalent) and a GPU.
- Supervise every process with systemd. A watchdog restarts the stream when it dies.

## 9. Discord
discord.py is maintained (v2.7.1, March 2026).
