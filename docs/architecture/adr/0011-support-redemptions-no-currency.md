# ADR-0011: Support events trigger capped redemptions; no in-game currency (for now)

- Status: Proposed (owner to confirm, Q-SUP-4)
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
- Paid support (Bits, Super Chat, memberships, tips) unlocks **cosmetics and shoutouts by default**. QoL effects are allowed only from a capped allowlist (SUPPORT-REDEMPTIONS §4), and **never** anything that decides battles.
- **No randomness** in paid rewards: no loot boxes or chance.
- No conversion between currencies inside the game. Thresholds are set per currency or per platform tier.

## Consequences
- Revisit an in-game currency only if redemptions prove popular *and* the owner accepts the added scope. That would be a new ADR, preceded by a legal review.
