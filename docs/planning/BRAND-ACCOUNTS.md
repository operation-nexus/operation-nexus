# Brand accounts and organization registry

Single list of the project's public identities, so every session and agent starts from the same facts. Public handles and identifiers only. No passwords, tokens, recovery codes or keys go here or anywhere in this repo (AGENTS.md rule 9); those live in the private `operation-nexus-ops` repo once it exists (Q-OPS-10, NX-299).

Source: owner message, 2026-10-18. Everything below is owner-reported; the sessions have not logged in to verify it. [UNVERIFIED] until a check is recorded.

## GitHub

| Item | Value |
|---|---|
| Organization | `operation-nexus` (https://github.com/operation-nexus), owned by `saltyseraphcodes` |
| Public repo | `operation-nexus` (transferred into the organization 2026-10-18) |
| Private repo: secrets | `operation-nexus/operation-nexus-ops` (created, empty; encrypted secrets only, Q-OPS-10) |
| Private repo: lore, drafts, licensed art | `operation-nexus/operation-nexus-vault` (created, empty; Q-OPS-10) |

## Brand mailbox (Q-MKT-11)

`projecthiveplex@gmail.com` is the login and recovery email for the brand accounts below. The developer mailbox stays separate and is never published.

## Platform handles (Q-MKT-10)

`hiveplex` alone was taken on several platforms, so the owner took the `project_hiveplex` family. The names are not identical across platforms. The display name is "Hiveplex" wherever the platform allows it. Aim for one consistent handle later (Twitch rename is possible in about two months).

| Platform | Handle / URL |
|---|---|
| YouTube | `@hiveplex` (https://www.youtube.com/@hiveplex) |
| Twitch | `hiveplextv` (https://www.twitch.tv/hiveplextv); rename to a `project_hiveplex` form when Twitch allows |
| Instagram | `project_hiveplex` |
| TikTok | `@project_hiveplex` |
| Bluesky | `hiveplex.bsky.social` (https://bsky.app/profile/hiveplex.bsky.social) |
| Reddit | `u/hiveplex` |
| GitHub | `hiveplex` (personal account, defensive hold; not used for project work) |
| Discord | `project_hiveplex` |
| Discord developer application | `hiveplex`, application id 1561428278521372792 |
| Discord developer team | `operation-nexus`, team id 1561428590095114301 |

Not created: X (decided to wait, Q-MKT-12).

Twitch `hiveplex` (a dormant 2015 account) belongs to someone else; the owner confirmed it is not theirs. It is not a fallback to rely on.

## Domains (Q-MKT-12)

Bought by the owner on 2026-10-18: `hiveplex.live` (public brand) and `operationnexus.dev` (codename: docs, API, developer pages). Checked in the public registry (RDAP) on 2026-10-19: both are registered at Porkbun LLC with Porkbun nameservers, registered 2026-10-18 and expiring 2027-10-18 (the first renewal date). Not bought: `hiveplex.io` (renewal quoted at 51 a year). Renewal prices are the owner's quotes, not verified; set a calendar reminder for the first renewal.

## Secrets key

The age public key is in `operation-nexus-ops/.sops.yaml`. The private key is held only by the owner (password manager, with an offline backup).
