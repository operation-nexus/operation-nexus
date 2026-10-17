# Research: Epidemic Sound for a 24/7 game stream (2026-10-17)

> Everything below came from search excerpts of official pages. Those pages weren't reachable from the research environment, so **treat all of it as [UNVERIFIED] until the live terms or support confirm it.**

| Topic | Finding | Source |
|---|---|---|
| Creator plan scope | **Non-commercial** creators on YouTube, Facebook, Instagram, TikTok*, Twitch and podcasts. Content published during the subscription stays covered after cancelling. | help.epidemicsound.com/hc/en-us/articles/26247405706386; epidemicsound.com/our-plans |
| Channels | You must connect ("safelist") channels. Creator = **one channel per platform**. More channels need Pro or another subscription. | support.epidemicsound.com (connected channels articles) |
| Twitch | "With an active subscription you are free to play our music on the stream channel connected to your subscription" (page is about 4.5 years old) | epidemicsound.com/twitch |
| 24/7 / unattended streams | **No explicit official rule found.** A secondhand report quotes support saying music must accompany your own productions. | quora.com (secondhand) |
| Apps/games | Not covered by Creator. A third-party review says Business Plus. | photutorial.com (third-party) |
| **MCP server** | **Official MCP server exists (beta).** Needs an active subscription and a personal API key. | epidemicsound.com/tools/mcp; developers.epidemicsound.com/docs/mcp |
| Partner API | Separate, gated by a partnership agreement | apievangelist (third-party) |
| Automation | Terms forbid automated systems *except* official connectors/APIs | epidemicsound.com/policy/general-terms-and-conditions |

## Implications
1. **Before relying on it, get written confirmation from Epidemic Sound support** that a continuous, unattended, *monetized* 24/7 game stream is covered. The Creator plan is described as non-commercial, so a monetized channel may need **Pro or Business**.
2. Connect exactly one Twitch and one YouTube channel.
3. If the subscription lapses, the live stream stops being covered. Whether VODs and clips stay covered is [UNVERIFIED].
4. Music agent: use the **official MCP server** with a personal key, kept in the secret store. Put it behind a `MusicSource` adapter (ADR-0010), and keep it **off the hot path**: an agent curates playlists ahead of time, and playback stays deterministic.
