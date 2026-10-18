# SPEC: Support Events & Redemptions

Status: Draft · Owner: — · Tracker: NX-267…NX-272 · ADRs: 0010, 0011 · Research: [SUPPORT-AND-SCRAPING-RESEARCH](../review/SUPPORT-AND-SCRAPING-RESEARCH.md)

> All thresholds and caps below are **PROPOSED** (DATA-INTEGRITY DI-7). The owner sets the real values in the admin rules editor (ADMIN-RBAC).

## 1. Purpose
A single global ingest for all support and engagement events (Bits, channel points, subs, Super Chats/Stickers, memberships, third-party tips). The flow is: verify the event really happened, match it against owner-defined redemption rules, then run the resulting in-game action. Platform-neutral, with no in-game currency (ADR-0011).

## 2. Goals / Non-goals
- **Goals:**
  - One `SupportEvent` shape for every source.
  - Idempotent: never redeem twice.
  - Owner-configurable rules.
  - Honest acknowledgement, including refunds where the platform supports them.
  - Fair: no pay-to-win.
- **Non-goals:**
  - Stored balances or wallets.
  - Currency conversion inside the game.
  - Random or chance rewards.
  - Cash-out.
  - Auto-reading donor messages aloud.

## 3. Ingest (`SupportSource` port, ADR-0010)
| Adapter | Events | Phase |
|---|---|---|
| Twitch | channel points redemptions (rewards created by our Client-Id), `channel.bits.use` / `channel.cheer`, subs/gifts (de-duplicated), Hype Train v2 | P4 (channel points can come first) |
| YouTube | `superChatEvent`, `superStickerEvent`, `newSponsorEvent`, `memberMilestoneChatEvent` (arrive in the chat stream) | P4 |
| Ko-fi | webhook | P5 (optional; Q-SUP-3: one third-party tip service, chosen later) |
| Streamlabs / StreamElements | socket | P5 (optional; Q-SUP-3: one third-party tip service, chosen later) |

Normalized `SupportEvent` (added to CONTRACTS):
```
SupportEvent {
  support_id        # adapter source id (dedupe key), e.g. platform event id / Ko-fi message_id
  platform          # Platform enum
  platform_user_id  # nullable: anonymous tips have no id; never guessed
  kind              # BITS | CHANNEL_POINTS | SUB | GIFT_SUB | SUPER_CHAT | SUPER_STICKER | MEMBERSHIP | TIP | HYPE_TRAIN
  amount_minor      # integer in the source's unit: bits count, points count, or currency minor units; null if N/A
  currency          # ISO 4217 for money; null for bits/points/subs
  platform_tier     # e.g. YouTube Super Chat tier, sub tier; null if none
  reward_ref        # channel-points reward id (ours), else null
  message           # donor text: untrusted, moderated, never auto-spoken
  received_at       # runtime wall clock
}
```

## 4. Redemption rules (config, admin-editable)
Each rule has these parts:
- **Trigger:**
  - a channel-points reward id, or
  - `kind` + minimum `amount_minor`, **per currency**, or
  - `kind` + minimum `platform_tier`.
- **Effect:** one entry from the allowlist below.
- **Limits:** per-commander cooldown, a global cap per hour, and max active at a time.

Effect allowlist by trigger source:
| Category | Allowed effects (examples) | Money | Channel points |
|---|---|---|---|
| Cosmetic | Halo or trail color for this campaign, PiP placard flair, callsign "supporter" badge, unit nose-art | ✅ | ✅ |
| Shoutout | On-stream "Thanks, VIPER-27" banner (callsign only); a template sitrep line, e.g. "Logistics wing salutes VIPER-27"; a more prominent `!rally` banner or longer pin (Q-SUP-6: prominence only, never more power) | ✅ | ✅ |
| Spectacle (no gameplay effect) | Flare or fireworks burst over a friendly base; an AWACS flyover animation | ✅ | ✅ |
| QoL (capped) | Skip *your own* respawn delay once; one extra `!scout` ping; jump the reserve queue once (max N per hour globally) | ❌ (Q-SUP-1: money buys cosmetics, shoutouts and spectacle only) | ✅ |
| Team support (capped, small) | Request a supply drop to the starved FOB **queued through the normal logistics system** (it still has to fly in and can be intercepted) | ❌ (Q-SUP-1) | ✅ (global cap and shared cooldown, §4a, Q-SUP-7) |
| **Forbidden** | Damage or HP buffs, instant captures, killing units, changing director tiers, anything random, anything that stacks into a decisive advantage | ❌ | ❌ |

### 4a. Supply-drop cap (Q-SUP-7)
- **SR-1** Supply-drop redemptions have a **fixed global cap per hour**, `support.supply_drop.max_per_hour` (value PROPOSED / TBD by harness), plus a shared cooldown across all viewers. The cap never scales with viewer count or chat volume (GAMEPLAY TS-1).
- **SR-2** Our code enforces the cap and cooldown (§5 step 5). Where the platform's reward settings support it, the same limits are mirrored there [UNVERIFIED: exact Twitch reward options]. When capped, the reward shows "on cooldown"; a redemption that still arrives is refused through §5 step 7 (channel points CANCELED, so the points are refunded).

### 4b. Provocation weights (Q-AI-9)
- **SR-3** Every applied redemption adds to the director's `provocation` score (THREAT-DIRECTOR §5a) by a per-type weight, `director.provocation.weights.redemption.<type>` (admin-tunable; values PROPOSED / TBD by harness).
- **SR-4** Weight classes: offensive = full weight; support (e.g. supply drop) = small weight; cosmetic, shoutout and spectacle = **0**. An unapplied, refunded or ignored redemption adds nothing.

## 5. Flow
1. The adapter verifies authenticity: signed webhooks, OAuth-bound EventSub, and a Ko-fi token compared in constant time over HTTPS.
2. **Dedupe** on `(platform, support_id)` in `support_events` (unique). Retries are no-ops.
3. Store the event, recording the raw amount and currency exactly as received.
4. Match it against the rules (deterministic, first match by priority).
5. Run the checks: the commander is resolved (if `platform_user_id` is null, only shoutout-free cosmetic or global spectacle rules can apply), limits are OK, and the campaign is running.
6. Issue the logged command `SUPPORT_REDEEM{support_id, rule_id, commander_id?}`. The sim applies the effect and its provocation weight (§4b), which keeps replays deterministic.
7. **Acknowledge:**
   - Channel points: FULFILLED on success, **CANCELED (refunds the points) on failure**.
   - Money and Bits can't be refunded through the API. If the effect can't be applied, show "Thank you" (the shoutout still happens) and log `unapplied_reason`.
8. Show it on the overlay (recruit-strip style), and include it in the chat digest (GAMEPLAY §1a).

## 6. Currency handling (DATA-INTEGRITY)
- Thresholds are defined **per currency** in config (e.g. `USD: 500` = $5.00, `EUR: 500`). A currency with no threshold means that rule doesn't trigger. It's logged and shown in the admin console, never guessed.
- Optionally, the owner can add their own FX table (`support.fx_table`, owner-entered with a date). It's registered as a fallback (FB-5) and labeled in the admin UI. No live FX feeds in v1.
- YouTube's `tier` can be used instead of an amount, so rules work across currencies without FX.

## 7. Safety
- Donor `message` is untrusted. It's never shown or spoken unmoderated, and **never read aloud by TTS in v1**. No free-text donor messages appear on stream in v1 (Q-SUP-2); a templated rally call (Q-SUP-6) is the alternative.
- Anonymous tips give no per-user effects.
- Effects are temporary (per campaign or per sortie). Nothing permanent depends on money, so a later chargeback has nothing to claw back.
- Rewards are fully deterministic. No loot boxes, chance or wagers (Bits AUP; gambling and loot-box risk).
- **Money never buys gameplay effects** (Q-SUP-1, decided 2026-10-17): Bits, Super Chats, memberships and tips map only to cosmetics, shoutouts and spectacle. QoL and team-support effects are channel-points only. The config validator rejects a rule that binds a money trigger to a QoL or team-support effect.
- Made-for-kids content has no Super Chat. The channel is not marked made-for-kids (THREAT-MODEL COPPA note).

## 8. Data model additions
- **`support_events`**: `support_id` + `platform` (unique), all `SupportEvent` fields, `matched_rule_id`, `status` (RECEIVED | REDEEMED | UNAPPLIED | REFUNDED | IGNORED), `unapplied_reason`, `command_arrival_seq`.
- **`redemption_rules`**: versioned with the balance config, `config_hash`.
- **Retention:** keep all financial support records until an accountant advises otherwise; donor messages are deleted after 30 days (Q-SUP-5, decided 2026-10-17).

## 9. Test plan
- Conformance suite for every `SupportSource` adapter: dedupe, authenticity, malformed payloads, gift-bomb double count.
- Property tests: no event redeems twice, and caps hold.
- Golden replay including `SUPPORT_REDEEM`.
- A test that the channel-points refund path is called on failure.
- A forbidden-effect rule is rejected by the config validator.
- SR-1/SR-2: with 1 and with 300 simulated viewers, supply drops never exceed `support.supply_drop.max_per_hour`; a capped channel-points redemption is CANCELED.
- SR-4: a cosmetic, shoutout or spectacle redemption leaves `provocation` unchanged; an unapplied one adds nothing.

## 10. Open questions
Q-SUP-1 … Q-SUP-7 and Q-AI-9 are decided and folded in above. Still open:
- Q-AI-9 names an offensive class (airstrike, barrage), but §4 forbids damage and killing units from any redemption, so no allowlisted effect is offensive today. Which class the QoL effects (respawn skip, extra `!scout` ping, queue jump) belong to is not decided.
