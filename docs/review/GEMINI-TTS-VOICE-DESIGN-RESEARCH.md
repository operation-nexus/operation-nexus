# Research: Gemini TTS voice design (2026-10-17)

> Official pages were unreachable from the research environment. **Every fact below came from search summaries and is [UNVERIFIED]**; verify it on ai.google.dev before relying on it.

## What exists (reported)
- Models `gemini-3.8-flash-tts` and `gemini-3.8-flash-lite-tts`, reportedly GA in the Gemini API on 2026-09-22.
- **Voice design:** you describe a voice in text, and `POST /v1beta/voices` returns a persistent `voice_…` id (reportedly kept for about a year) plus a WAV preview.
- **Voice replication** (cloning) is separate. It requires consent audio and is region-restricted. **We won't use it** (Q-MOD-4).
- Outputs reportedly carry a SynthID watermark.

## Reported pricing (third-party)
| Model | Text input (per 1M tokens) | Audio output (per 1M tokens), until 2026-12-31 | Audio output from 2027-01-01 |
|---|---|---|---|
| Flash | $0.50 | $9 | ~$18 (reportedly doubles) |
| Flash-Lite | $0.50 | $6 | ~$12 (reportedly doubles) |

- Audio is about 25–32 tokens/s.
- The free tier has unpublished limits, and Google may use free-tier inputs.

## Cost ESTIMATE (8 s lines, audio only)
| Cadence | Flash-Lite 2026 | Flash-Lite 2027 |
|---|---|---|
| 1 line/min | ~$52–66/mo | ~$104/mo |
| 1 line/3 min ("big moments") | ~$17–22/mo | ~$35/mo |

## Implications for us
- **Doesn't fit the $20/mo cap for the whole voice cast,** especially at 2027 prices.
- A good **hybrid**:
  - Design the voices once (Gemini), then **pre-generate and cache** fixed and common lines.
  - Use local Piper/Kokoro for the dynamic everyday lines.
  - Spend live Gemini calls only on rare, high-impact moments (mastermind taunts, war start/end).
- Store the voice ids *and* the description prompts, so voices can be recreated if an id expires.
- Generate lines off the tick path, and measure first-audio latency ourselves.
- Open question: on-stream disclosure of AI voices, and Twitch policy (Q-AI-6).
