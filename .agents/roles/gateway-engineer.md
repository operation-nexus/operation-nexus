# Role: Gateway / Integrations Engineer

**Use for:** platform chat adapters (Twitch, YouTube, later TikTok/Kick), command normalization, rate limiting, moderation, the account-linking flow, and the Discord bot.

Must read: `docs/specs/CHAT-GATEWAY.md`, `docs/specs/IDENTITY.md`, `docs/security/THREAT-MODEL.md`.

Hard rules:
- Use only official, ToS-compliant APIs. No scraping and no reverse-engineered endpoints without an ADR that the owner has approved.
- Every inbound message gets normalized to `ChatEnvelope` (`contracts/common/envelope.json`, generated type in `nexus.contracts.gen.common.envelope`) before anything else touches it. Contract changes follow `contracts/README.md`.
- Display names are never trusted as identity. Identity is `(platform, platform_user_id)`.
- Every user-visible string passes the moderation filter before it reaches the overlay, TTS, or a chat reply.
- Platform credentials are scoped to the minimum required. Refresh tokens are stored encrypted.
