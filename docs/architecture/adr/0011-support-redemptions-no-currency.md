# ADR-0011: Support events trigger capped redemptions; no in-game currency (for now)

- Status: Accepted (owner, 2026-10-17)
- Date: 2026-10-17
- Related: ADR-0010 (ports), SUPPORT-REDEMPTIONS spec, research in docs/review/SUPPORT-AND-SCRAPING-RESEARCH.md

## Context
The owner wants donations, Super Chats, Bits and channel points to trigger in-game actions. Mostly cosmetic, with possibly a few QoL perks such as a reduced cooldown. They asked whether an in-game currency is worth adding, without scope creep. Research found:
- Twitch's Bits Acceptable Use Policy prohibits wagering and says Bits "do not serve as a currency".
- Channel points can be refunded programmatically (CANCELED), but only for rewards our app created.
- Amounts arrive in the original currency only, with no normalized USD value.
- Chargebacks can't be seen through these APIs.

## Options
1. **Direct redemptions:** each support event maps straight to one capped effect.
2. **In-game currency:** support converts into a stored balance that players spend.
3. Both.

## Decision
Option 1, direct redemptions. **No stored in-game currency in v1.** Reasons:
- **Less scope:** no wallet, balance UI, ledger reconciliation, or refund and chargeback clawback.
- **Lower policy risk:** a stored balance bought with Bits looks like a currency.
- **Better fairness on stream.**

Twitch channel points already act as a free, platform-managed "currency" for QoL redemptions.

Rules:
- Paid support (Bits, Super Chat, memberships, tips) unlocks **cosmetics, shoutouts and spectacle only** (Q-SUP-1, owner decision 2026-10-17). QoL perks (respawn skip, queue jump) and team-support effects come **only from channel points**, from a capped allowlist (SUPPORT-REDEMPTIONS §4). **Nothing** that decides battles is available from any source.
- **No randomness** in paid rewards: no loot boxes or chance.
- No conversion between currencies inside the game. Thresholds are set per currency or per platform tier.

## Consequences
- Revisit an in-game currency only if redemptions prove popular *and* the owner accepts the added scope. That would be a new ADR, preceded by a legal review.

## Amendment (2026-10-17): money buys no QoL (Q-SUP-1)
The original text allowed paid support to unlock QoL effects from a capped allowlist. The owner decided (Q-SUP-1) that money buys cosmetics, shoutouts and spectacle only, to avoid any "pay to win" perception. The Rules above are updated to match; channel points remain the only source of capped QoL.
