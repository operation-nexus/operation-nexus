# Platform & Dependency Reality Check

> Verification status (2026-10-18): corrected against primary sources in [PLATFORM-POLICY-VERIFICATION-2026-10-18](PLATFORM-POLICY-VERIFICATION-2026-10-18.md) and [LICENSE-AND-MUSIC-VERIFICATION-2026-10-18](LICENSE-AND-MUSIC-VERIFICATION-2026-10-18.md). Inline [CORRECTED 2026-10-18] notes mark changed claims; [VERIFIED 2026-10-18] marks confirmed ones.

Date: 2026-10-17 · Method: web research (search-result excerpts; some official pages were unreachable from the research environment). Items marked **[UNVERIFIED]** come from secondary sources and must be re-checked before they drive a decision.

## Top risks, ranked
1. **TikTok has no official API for reading LIVE chat.** TikTok LIVE policy also works against unattended, TTS-narrated streams.
2. **YouTube quota:** polling `liveChatMessages.list` uses up the default 10,000 units/day in about 1–3 h. `streamList` is mandatory. Chat posts cost 20 units each.
3. **Auto-posting Shorts/TikToks:** TikTok Direct Post is private-only for unaudited clients, and its Intended Use excludes a utility that uploads to accounts "you or your team manages", so plan inbox drafts or manual posting only [CORRECTED 2026-10-18: was "private-only until Google's and TikTok's audits pass"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 K3]. For YouTube, the old private lock on unverified API projects conflicts with the current `videos.insert` reference, which says they are not restricted; test with a real upload [CORRECTED 2026-10-18: was an unconditional private lock; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y8].
4. **Twitch bot send limits** are 20 msgs/30 s (100 if the bot is a moderator or VIP). Verified bot status is "rarely granted"; no pause notice was found [CORRECTED 2026-10-18: was "Verified-bot reviews are paused"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T14].
5. **LiteLLM supply-chain compromise (March 2026).** Pin with hashes, or skip LiteLLM.
6. **Piper is now GPL-3.0** (piper1-gpl). Licensing review needed. [VERIFIED 2026-10-18: GPL-3.0-or-later, see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-03]
7. The 24/7 browser render + dual encode **needs a GPU**.

## 1. Twitch
- **Reading chat:** EventSub `channel.chat.message` is the recommended path and IRC is legacy. The bot needs `user:read:chat`. To send, it needs `user:write:chat` and uses the Helix Send Chat Message API. With an app token it also needs `user:bot`, plus `channel:bot` granted by the broadcaster or bot moderator status.
- **Rate limits:** 20 msgs/30 s for a normal account and 100/30 s for a mod or VIP. Exceeding them makes Twitch ignore the bot's messages for 1 hour [CORRECTED 2026-10-18: was 30–60 min; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T13].
  - **Implication:** make the bot a moderator, and aggregate acknowledgements on the overlay. Per-command chat replies are impossible at volume.
- **Whispers:** Helix whispers need a verified phone. Limits are 40 unique recipients/day and 3/s, and delivery can fail silently. The public one-time-link approach is right, but the link must not be usable by onlookers (see THREAT-MODEL).
- **24/7 streams:** reruns must be labelled. A broadcast reportedly ends after 48 h, so plan for auto-restart **[UNVERIFIED]**. No explicit rule against unattended interactive games was found. Rewards/drops abuse is banned.
- Sources: dev.twitch.tv/docs/chat/irc-migration, dev.twitch.tv/docs/chat/authenticating, dev.twitch.tv/docs/irc, dev.twitch.tv/docs/chat/whispers, discuss.dev.twitch.com/t/54596

## 2. YouTube Live
- **Quota:** the default is 10,000 units/day. `liveChatMessages.list` costs 5 units and `insert` costs 20. `streamList` (gRPC server streaming) is listed at 5 units, and whether that is per connection or per message is unconfirmed **[UNVERIFIED]**. [VERIFIED 2026-10-18: 10,000 units/day plus separate 100 `videos.insert` and 100 `search.list` buckets; list 5, insert 20, streamList 5 per call (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y1, Y3, Y4); the per-connection or per-message billing question stays UNVERIFIED (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y5).]
- **Math:** polling at the suggested interval uses up the quota in roughly 1–3 h. Polling within quota means one call per ~43 s, which is useless for live play.
  - **Implication:** use `streamList` and keep reconnects to a minimum. Treat chat replies as nearly unavailable. Apply for a quota increase, which needs a compliance audit.
- **Policy:** in July 2025 the YPP "repetitious content" policy was renamed "inauthentic content" (mass-produced or templated) [VERIFIED 2026-10-18, PLATFORM-POLICY-VERIFICATION-2026-10-18 Y13]. The interactive sim is defensible. **Templated daily LLM-voiceover Shorts are exactly what the policy targets.**
- Sources: developers.google.com/youtube/v3/determine_quota_cost, …/live/docs/liveChatMessages/streamList

## 3. TikTok LIVE (biggest hole)
- **There is no official API for reading LIVE comments.** Libraries like TikTokLive and tiktok-live-connector are reverse-engineered, often rely on third-party signing services, break regularly, and violate the ToS.
- **Eligibility:** 18+ is official; the follower number is not published ("required number of followers, which may vary by region") [CORRECTED 2026-10-18: was "about 1,000 followers"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 K8]. Access to an RTMP key or LIVE Studio is gated with unpublished criteria. Keys reportedly rotate every session, which conflicts with unattended 24/7 operation **[UNVERIFIED]**.
- **Policy:** static screens, no presenter, or long stretches without interaction can make a LIVE "not eligible for recommendation".
- **Implication:** TikTok is optional and best-effort, or deferred. The game must not depend on it.

## 4. Kick
A public API exists: OAuth 2.1 with PKCE, a `chat:write` scope, and Ed25519-signed webhooks (at-least-once delivery, dedupe on message id) **[UNVERIFIED — docs unreachable]**. It's a possible third platform with an official API, unlike TikTok.

## 5. Auto-upload of clips
- **YouTube:** `videos.insert` has its own bucket of 100 calls/day at 1 unit per call (quota calculator, revision history 2025-12-04 and 2026-06-01; read 2026-10-18) [CORRECTED 2026-10-18: was "historically costs 1,600 units, about 6 uploads/day [a newer cost is UNVERIFIED]"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y2]. The 2020 rule that uploads from unverified API projects are locked to private conflicts with the current `videos.insert` reference, which says they are not restricted; test with a real upload [CORRECTED 2026-10-18: was a flat statement that uploads from unverified projects created after 2020-07-28 are locked to private until a compliance audit passes; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y8].
- **TikTok:** an unaudited Content Posting API client can post private-only [VERIFIED 2026-10-18, PLATFORM-POLICY-VERIFICATION-2026-10-18 K1]. Direct Post's Intended Use excludes a single-owner publisher, so use inbox drafts or manual posting [CORRECTED 2026-10-18: Intended Use was not mentioned before; see PLATFORM-POLICY-VERIFICATION-2026-10-18 K3].
- **Implication:** Phase 1 clipping writes to a review folder, and a human posts manually.

## 6. TTS
- Piper moved from rhasspy/piper (MIT, archived Oct 2025) to OHF-Voice/piper1-gpl (**GPL-3.0-or-later**, because it embeds espeak-ng). Running it server-side without distributing it is generally fine. Each voice model has its own dataset license; check every MODEL_CARD [VERIFIED 2026-10-18, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-04]. Dataset licenses seen: `en_US/ryan/medium` CC BY-NC-SA 4.0, `en_US/libritts_r/medium` CC BY 4.0, and the `lessac` dataset (basis of many fine-tuned voices) is under a research-only licence that excludes commercial voice synthesis; Piper's docs say it is "intended for personal use and text to speech research only" (LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-05, V-06). The "archived Oct 2025" flag of rhasspy/piper is UNVERIFIED (GitHub API refused, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-02); its README move notice is verified (LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-01).
- Kokoro-82M weights are Apache-2.0 (Hugging Face model card, read) [CORRECTED 2026-10-18: was "reported as Apache-2.0 [UNVERIFIED primary]"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-11]. The Python `kokoro` code is Apache-2.0, not MIT (LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-12). `kokoro-onnx` pulls GPL `phonemizer` and `espeakng-loader`, so TTS stays an isolated process (LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-14).
- Gemini TTS costs $0.009 (Flash-Lite) to $0.0135 (Flash) per minute of speech through 2026-12-31 and $0.018 to $0.027 from 2027-01-01 (official pricing page, audio only; text input is extra) [CORRECTED 2026-10-18: was "roughly $0.015 per minute [UNVERIFIED — pricing page unreachable]"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-112 to V-114].

## 7. LLM tooling
- **LiteLLM:** malicious PyPI releases 1.82.7 and 1.82.8 (2026-03-24) only 1.82.8 contained the `.pth` credential stealer (`litellm_init.pth`); 1.82.7 carried a payload in `proxy_server.py`. LiteLLM says it "believe[s]" the origin was the Trivy dependency in its CI/CD security scanning; the packages were live about 40 minutes on 2026-03-24, and a clean 1.83.0 followed (PyPI upload 2026-03-31 UTC) [CORRECTED 2026-10-18: was "dropped a `.pth` credential stealer, reportedly via a compromised scanner in LiteLLM's CI" for both versions; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-117].
  - **Implication:** use hash-pinned lockfiles, run the LLM gateway in an isolated container with no platform tokens, or call provider SDKs directly.
- **Instructor** (567-labs) is active, v1.17.0 as of 2026-10-18 [CORRECTED 2026-10-18: was v1.15.x as of mid-2026; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-31].

## 8. Broadcast host
- **Option A:** Xvfb + Chromium (headed, for WebGL) + PipeWire + FFmpeg → RTMP.
- **Option B:** OBS on Linux under Xvfb, or a real desktop session. The Aitum Vertical (9:16) plugin needs real OBS.
- Without a GPU, Chromium falls back to SwiftShader and encoding falls back to x264. Dual 60 fps outputs need NVENC (or equivalent) and a GPU.
- Supervise every process with systemd. A watchdog restarts the stream when it dies.

## 9. Discord
discord.py is maintained (v2.7.1, March 2026) [VERIFIED 2026-10-18: MIT; 2.7.1 uploaded 2026-03-03 and still the latest on 2026-10-18; LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-20].
