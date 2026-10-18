# Handle and Domain Check: "hiveplex" (2026-10-18)

Tracker: NX-297, NX-336 · Decisions: Q-BRAND-6, Q-MKT-7, Q-MKT-10 · Status: point-in-time snapshot, **not a reservation**

Availability changes by the minute. Nothing here holds a name for you; claim the handles the same day you act on this.

## 1. Result summary
| Platform | Result for `hiveplex` | Confidence |
|---|---|---|
| **Twitch** | **TAKEN.** User id 82074766, display name "Hiveplex", created 2015-02-07, no description, 0 followers, not a partner or affiliate, no broadcast ever (last-broadcast fields empty) | High (the platform's own web data) |
| YouTube | `@hiveplex` returns 404: no such handle | High |
| TikTok | `@hiveplex` page says the account was not found | Medium (page text, not an API) |
| Bluesky | `hiveplex.bsky.social`: "Profile not found" | High (public API) |
| Discord | Invite code `hiveplex`: "Unknown Invite" (no such invite, so the vanity URL looks unused) | Medium (vanity availability also depends on server boosts) |
| X | Not checkable (page loads for any name; syndication endpoint rate-limited) | Manual |
| Instagram | Not checkable (rate-limited, 429/401) | Manual |
| Reddit | Not checkable (automated requests blocked, 403) | Manual |
| GitHub org/user | Not checkable (403 from the shared egress) | Manual |

Twitch variants that returned "no such login": `hiveplextv`, `hiveplexgame`, `hiveplexgames`, `hiveplexhq`, `playhiveplex`, `thehiveplex`, `hiveplex_`, `hiveplexofficial`, `hiveplexwar`, `realhiveplex`, `hiveplexlive`, `hiveplexnet`. YouTube `@hiveplexgame`, `@hiveplextv`, `@playhiveplex`, `@hiveplexhq` and TikTok `@hiveplexgame`, `@hiveplextv`, `@playhiveplex`, `@hiveplexhq` also looked free.

### 1a. Hype-prefix variants (owner asked for a workaround, 2026-10-18)
Free at check time on Twitch, YouTube, TikTok and Discord (Bluesky timed out for `playhiveplex`, `hiveplextv`, `teamhiveplex`; free for the others): `playhiveplex`, `operationhiveplex`, `projecthiveplex`, `hiveplextv`, `hiveplexgame`, `hiveplexhq`, `teamhiveplex`. `playhiveplex.com/.net/.gg/.tv` and `operationhiveplex.com`, `projecthiveplex.com` show no DNS delegation. Recommendation (Q-MKT-10): one consistent handle, `playhiveplex`, display name "Hiveplex"; use "Operation Hiveplex" style naming for campaign banners rather than the handle.

## 2. Domains
| Domain | Result |
|---|---|
| hiveplex.com | **Registered** (2017-11-22, per RDAP). DNS points to a domain-sale marketplace (nameservers `ns1/ns2.brandbucket.com`); the earlier sweep saw a listing at about $2,495 [UNVERIFIED price] |
| .net .org .tv .live .app .games .game .xyz .dev .online | RDAP: not found, and public DNS: no delegation (NXDOMAIN) → very likely unregistered |
| .io .gg .co .gaming | These endings have no RDAP service in the IANA bootstrap list; public DNS shows no delegation (NXDOMAIN) → likely unregistered, **confirm at a registrar** |

NXDOMAIN means no nameservers are delegated. A registered domain with no DNS would look the same, so a registrar search is the only authority.

## 3. Method and caveats
- Domains: RDAP via `rdap.org` (only for endings listed in the IANA RDAP bootstrap) plus public DNS (`dns.google` NS lookups). WHOIS port 43 was not reachable.
- Twitch: Twitch's public web GraphQL endpoint with the web client's public Client-ID (read-only lookup of a public profile). This is an unofficial interface and could change. The unofficial `passport.twitch.tv/usernames` endpoint returned an unusable status and was ignored.
- YouTube/TikTok/Bluesky/Discord: plain HTTP requests to public profile pages or APIs.
- No account, token or credential was used; nothing was registered.

## 4. Recommendations (see Q-MKT-10)
1. **Twitch:** the exact `hiveplex` is held by a dormant 2015 account. Ask Twitch support whether it can be released (their inactive-username policy is being read in the trademark verification pass, NX-333; do not count on it). Meanwhile register **`hiveplextv`**, the conventional fallback, which was free at check time.
2. **Everywhere else:** register `hiveplex` the same day on YouTube, TikTok, Bluesky, Discord (vanity URL when eligible) and, after you check them by hand, X, Instagram, Reddit and a GitHub organization.
3. **Consistency beats purity:** the channel display name is "Hiveplex" on every platform even where the handle differs.
4. **Domain:** register a clean ending for the public site and the contact addresses (`.gg`, `.tv`, `.live`, `.net` or `.app`, your preference and registrar price). Use WHOIS privacy. `hiveplex.com` is a broker purchase, not worth it now.
5. Re-run this check on the day you register.
