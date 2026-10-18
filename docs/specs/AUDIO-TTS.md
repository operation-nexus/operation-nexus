# SPEC: Audio & TTS

Status: Draft · Tracker: NX-225…NX-232 · Inputs: P99–107, C18–22, C63

## 1. Buses
1. **Music**: two ambient stems crossfaded by frontline tension. Licensed stems only (Q-LEGAL-2).
2. **Foley**: UI ticks, pings, distant rumbles, mixed at about −18 dB.
3. **Radio**: TTS run through a 300–3000 Hz band-pass, a compressor, and a squelch tail.

## 2. Sitreps
- Triggered by events: node lost or captured, bridge destroyed, tier change, objective announced or completed, adaptive-defense INTEL.
- Text comes from **templates** filled with approved callsigns and node names. LLM embellishment is optional (P4). Every string is moderated (SEC-MOD-2).
- **AU-1** At most 1 sitrep per 20 s. A priority queue drops stale items (anything older than 60 s).
- **AU-2 Night mode** (00:00–08:00 **America/New_York** by default, admin-adjustable, Q-CFG-6; `audio.night_mode.hours` stores the IANA zone so DST is handled; or triggered by low activity): softer music, no shutter or alarm sounds, sitreps limited to critical events, and lower radio volume.

## 2a. Voice cast (owner decision 2026-10-17)
The voice reads **only big moments**: node captured or lost, bridge destroyed, objective announced or completed, director tier change, and Static mastermind taunts. Max 1 line per 20 s (PROPOSED); quieter in night mode. Everything else is text only. Goal: never excessive or grating.

Lines are spoken by a small **voice cast**: named voice profiles, each with an engine voice, a radio filter preset and a pacing setting. The cast is tuned by ear through a listening session (NX-278).
| Profile (working name) | Speaks | Character |
|---|---|---|
| Clearwave Control | Objectives, captures, status | Calm, clear dispatcher |
| Field Operator | Frontline events (bridge down, convoy hit) | Brisk, slightly noisier radio |
| The Static (mastermind) | Taunts, enemy offensives | Glitchy, distorted, playful villain |
| Game Master | Lines when a human GM is active (Q-RB-7) | Distinct preset, so viewers know a human is speaking |

## 3. TTS engine (Q-AI-4)

Engines implement the `TtsEngine` port (ADR-0010), so Piper, Kokoro and cloud voices can be swapped by config.

Runs as a separate `nexus-tts` worker process (crash isolation and GPL isolation). Engine choice is Piper (piper1-gpl) or Kokoro after a listening test. Voice-model licenses are recorded in `docs/legal/THIRD-PARTY.md`. Audio is cached by text hash. Gemini or premium voices come later, within the **$20/month AI cap** shared with the LLM (Q-AI-5, LLM-ADVISORS LLM-3). User-created or cloned voices of real people are out of scope (SEC-MOD-4, Q-MOD-4); synthetic designed voices for the voice cast are a future option (research NX-287).

## 3a. AI voice disclosure (Q-AI-6, decided 2026-10-17)
- **AU-3** The stream discloses that voices are AI-generated: a "Synthetic voices" note in the channel panel and on the about screen.
- **AU-4** Each platform's AI-content disclosure rules are followed, and **re-checked at every phase gate** (NX-288). Platform specifics are [UNVERIFIED] until that check.
- **AU-5** Human voice lines (the owner, or community voice actors) need written consent and a license per contributor (SEC-MOD-4) and are labeled as human in the voice-cast config.

## 4. Failure
If TTS is down, text sitreps continue and the circuit breaker opens. There is no retry storm.
