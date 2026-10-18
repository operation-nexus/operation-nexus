# Research: Gemini TTS voice design (2026-10-17)

> Verification status (2026-10-18): corrected against primary sources in [LICENSE-AND-MUSIC-VERIFICATION-2026-10-18](LICENSE-AND-MUSIC-VERIFICATION-2026-10-18.md). Inline [CORRECTED 2026-10-18] notes mark changed claims; [VERIFIED 2026-10-18] marks confirmed ones.

> Official pages were unreachable from the research environment. **Every fact below came from search summaries and is [UNVERIFIED]**; verify it on ai.google.dev before relying on it. [CORRECTED 2026-10-18: the ai.google.dev changelog, voice-design, voice-replication and pricing pages were later read; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-110 to V-116. SynthID and the replication region restriction remain UNVERIFIED.]

## What exists (reported)
- Models `gemini-3.8-flash-tts` and `gemini-3.8-flash-lite-tts`, GA in the Gemini API on 2026-09-22 [VERIFIED 2026-10-18, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-110].
- **Voice design:** you describe a voice in text, and `POST /v1beta/voices` returns a persistent `voice_…` id (1-year TTL and a limit of 200 voices per project) [CORRECTED 2026-10-18: was "reportedly kept for about a year"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-111] plus a WAV preview.
- **Voice replication** (cloning) is separate. It requires consent audio [VERIFIED 2026-10-18, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-116] and is reportedly region-restricted [UNVERIFIED: the "Available regions" text was not in the page text obtained]. **We won't use it** (Q-MOD-4).
- Outputs reportedly carry a SynthID watermark [UNVERIFIED on 2026-10-18: not in the page text obtained, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-116].

## Pricing (official pricing page, read 2026-10-18)

[CORRECTED 2026-10-18: this section was first written from third-party reports; the text-input column was "$0.50" with no 2027 change, and the 2027 audio prices were "~$18 (reportedly doubles)" and "~$12 (reportedly doubles)". Text input also doubles on 2027-01-01; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-112, V-113.]

| Model | Text input (per 1M tokens) | Audio output (per 1M tokens), until 2026-12-31 | Audio output from 2027-01-01 |
|---|---|---|---|
| Flash | $0.50 through 2026-12-31, $1.00 from 2027-01-01 | $9.00 | $18.00 |
| Flash-Lite | $0.50 through 2026-12-31, $1.00 from 2027-01-01 (same as Flash) | $6.00 | $12.00 |

- Audio is about 25–32 tokens/s.
- The free tier has unpublished limits, and Google uses free-tier inputs to improve its products (paid tier: no) [VERIFIED 2026-10-18, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-113]. The batch tier is half price.
- Per minute of speech (audio only): Flash $0.0135 and Flash-Lite $0.009 through 2026-12-31; $0.027 and $0.018 from 2027-01-01 [VERIFIED 2026-10-18, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-114].

## Cost ESTIMATE (8 s lines, audio only)
| Cadence | Flash-Lite 2026 | Flash-Lite 2027 |
|---|---|---|
| 1 line/min | ~$52–66/mo | ~$104/mo |
| 1 line/3 min ("big moments") | ~$17–22/mo | ~$35/mo |

The lower 1 line/min bounds (about $52 in 2026 and about $104 in 2027) were re-derived from the official per-10-second prices [VERIFIED 2026-10-18, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-115]; the upper bounds were not re-derived.

## Implications for us
- **Doesn't fit the $20/mo cap for the whole voice cast,** especially at 2027 prices.
- A good **hybrid**:
  - Design the voices once (Gemini), then **pre-generate and cache** fixed and common lines.
  - Use local Piper/Kokoro for the dynamic everyday lines.
  - Spend live Gemini calls only on rare, high-impact moments (mastermind taunts, war start/end).
- Store the voice ids *and* the description prompts, so voices can be recreated if an id expires (the 1-year TTL is verified, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-111).
- Generate lines off the tick path, and measure first-audio latency ourselves.
- Open question: on-stream disclosure of AI voices, and Twitch policy (Q-AI-6).
