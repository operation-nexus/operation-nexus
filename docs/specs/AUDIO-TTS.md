# SPEC: Audio & TTS

Status: Draft · Tracker: NX-225…NX-232 · Inputs: P99–107, C18–22, C63

## 1. Buses
1. **Music**: two ambient stems crossfaded by frontline tension. Licensed stems only (Q-LEGAL-2). Licensed music is never committed to the repo; it is loaded on the broadcast host only (Q-LEGAL-4). The music is always secondary to the visuals and there is never a music-only scene: Epidemic Sound licenses its music to enhance original productions, not for standalone listening experiences (use where visuals or narration are secondary to the music is not permitted under any plan, and playlists and online radio are named as excluded), and Twitch bans radio station-style broadcasts of recorded music without a live visual performance. Whether Epidemic Sound's licence covers a continuous 24/7 unattended stream is not answered by any of its published pages, so it needs written confirmation from Epidemic Sound support before the stream relies on it (Q-LEGAL-2). Its Pro and Business plans do not cover Video on Demand, so whether an archived livestream counts as VOD is part of that question. The `MusicSource` adapter and any automated track selection stay behind the same confirmation, because the Epidemic Sound Terms and MCP agreement text could not be read.
2. **Foley**: UI ticks, pings, distant rumbles, mixed at about −18 dB. Committed audio assets must have a license that permits redistribution and are listed in the asset provenance register (Q-LEGAL-4, NX-318).
3. **Radio**: TTS run through a 300–3000 Hz band-pass, a compressor, and a squelch tail.

## 2. Sitreps
- Triggered by events: node lost or captured, bridge destroyed, tier change, objective announced or completed, adaptive-defense INTEL.
- Text comes from **templates** filled with approved callsigns and node names. LLM embellishment is optional (P4). Every string is moderated (SEC-MOD-2).
- **AU-1** At most 1 sitrep per 20 s. A priority queue drops stale items (anything older than 60 s). Both windows run on a monotonic real-time clock, not sim time (Q-CFG-8).
- **AU-2 Night mode** (00:00–08:00 **America/New_York** by default, admin-adjustable, Q-CFG-6; `audio.night_mode.hours` stores the IANA zone so DST is handled; or triggered by low activity): softer music, no shutter or alarm sounds, sitreps limited to critical events, and lower radio volume.

## 2a. Voice cast (owner decision 2026-10-17)
The voice reads **only big moments**: node captured or lost, bridge destroyed, objective announced or completed, director tier change, and Static mastermind taunts. Max 1 line per 20 s (PROPOSED); quieter in night mode. Everything else is text only. Goal: never excessive or grating.

Lines are spoken by a small **voice cast**: named voice profiles, each with an engine voice, a radio filter preset and a pacing setting. The cast is tuned by ear through a listening session (NX-278).
| Profile (working name) | Speaks | Character |
|---|---|---|
| Quorum Control | Objectives, captures, status | Calm, clear dispatcher |
| Field Operator | Frontline events (bridge down, convoy hit) | Brisk, slightly noisier radio |
| The Static (mastermind) | Taunts, enemy offensives | Glitchy, distorted; dry, sparse, lightly smug, never theatrical (Q-BRAND-4) |
| Game Master | Lines when a human GM is active (Q-RB-7) | Distinct preset, so viewers know a human is speaking |

- **AU-6 Hum motif** (Q-BRAND-4): every Static transmission is preceded by the **Hum**, the Static's audio motif. Coalition voices refer to the mastermind by its intel codename **NULL**; the name it signs its own broadcasts with is TBD.
- **AU-7 Naming operators in taunts** (Q-AI-7): a taunt may name an operator only through a code-filled `{target}` placeholder holding that operator's approved callsign. The LLM (P4+) never sees names or chat text (SEC-LLM-4); before P4, taunts are template-only. Each operator is named at most once per `taunt.name_cooldown_min` (PROPOSED default 10), reduced to `taunt.name_cooldown_spotlight_min` (PROPOSED default 5) for spotlight operators (recent hero events or high recent action); both are admin-configurable. Both cooldowns run on a monotonic real-time clock, not sim time: they are enforced outside the sim and keep running while the sim is paused (Q-ALN-4). An operator whose `!quiet` toggle is on is never named (IDENTITY ID-PREF-1, Q-ALN-12). Tone: playful rivalry, never insults about the person.

## 3. TTS engine (Q-AI-4)

Engines implement the `TtsEngine` port (ADR-0010), so Piper, Kokoro and cloud voices can be swapped by config.

Runs as a separate `nexus-tts` worker process (crash isolation and GPL isolation). Engine choice is Piper (piper1-gpl) or Kokoro after a listening test. Voice-model licenses are recorded in `docs/legal/THIRD-PARTY.md`, from each voice's `MODEL_CARD`, before a voice enters the listening test. No voice trained on a non-commercial or research-only dataset may be shipped on a monetized stream (for example Piper's `ryan` voice is CC BY-NC-SA 4.0 and the `lessac` dataset is research-only, and many Piper voices are fine-tuned from `lessac`); a voice such as `libritts_r` (CC BY 4.0) needs its attribution. Piper's own voice documentation says it is "intended for personal use and text to speech research only", and whether a dataset licence restricts a model trained on it is a legal question that no published page answers. Piper (piper1-gpl) and its espeak-ng are GPL-3.0-or-later. Kokoro-82M weights are Apache-2.0 and its Python code is Apache-2.0 (not MIT), with CC BY training audio listed on its model card, but `kokoro-onnx` pulls GPL `phonemizer` and `espeakng-loader`; so whichever engine is chosen, TTS stays an isolated `nexus-tts` process, nothing from it is committed to the MIT repo, and no image containing it is published. Audio is cached by text hash. Gemini or premium voices come later, within the **$20/month AI cap** shared with the LLM (Q-AI-5, LLM-ADVISORS LLM-3). Gemini TTS costs $0.009 (Flash-Lite) to $0.0135 (Flash) per minute of speech through 2026-12-31 and $0.018 to $0.027 per minute from 2027-01-01 (audio only; text input is extra and also doubles on 2027-01-01). TTS budgets are tracked on a monotonic real-time clock (Q-CFG-8). User-created or cloned voices of real people are out of scope (SEC-MOD-4, Q-MOD-4); synthetic designed voices for the voice cast are a future option (research NX-287); Gemini voice design keeps a voice for 1 year with a limit of 200 voices per project, so the description prompts are stored with the voice ids.

## 3a. AI voice disclosure (Q-AI-6, decided 2026-10-17)
- **AU-3** The stream discloses that voices are AI-generated: a "Synthetic voices" note in the channel panel and on the about screen.
- **AU-4** Each platform's AI-content disclosure rules are followed, and **re-checked at every phase gate** (NX-288). Platform specifics as of 2026-10-18: YouTube asks for disclosure of realistic altered or synthetic content only (Studio field "AI use"); gameplay footage from video games and cloning one's own voice are listed as not needing it, and a generic TTS voice is on neither list, so labelling TTS there is the house rule, not a platform requirement. TikTok requires labelling AI-generated or significantly edited content that shows realistic-looking scenes or people (Community Guidelines 2026H2, effective 2026-09-24); the Direct Post field `is_aigc` sets the tag. Twitch's AI-disclosure rule and Instagram's "AI info" label rules are [UNVERIFIED] (no primary page was readable) until that check.
- **AU-5** Human voice lines (the owner, or community voice actors) need written consent and a license per contributor (SEC-MOD-4) and are labeled as human in the voice-cast config.

## 4. Failure
If TTS is down, text sitreps continue and the circuit breaker opens. There is no retry storm.
