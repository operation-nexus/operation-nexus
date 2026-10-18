# Trademark, Store and Company-Register Verification for Hiveplex (Q-LEGAL-5, Q-BRAND-6) — 2026-10-18

> **This is a knockout verification, not legal clearance, and not legal advice.** The author is not a lawyer. A knockout search looks for obvious blockers in a few public databases. It cannot find confusingly similar marks that a lawyer would weigh (sound, meaning, family of marks), unindexed or very recent filings, foreign filings that were not searched, or unregistered (common-law) use that search engines do not index. **Three of the four trademark registers that matter (EUIPO, WIPO, UKIPO) could not be searched** (§1). Do not spend money on domains, art, merch or a filing on the strength of this document alone; take the questions in §7 to a trademark attorney first.

Scope: the owner's public brand choice **Hiveplex** (Q-BRAND-6), the in-world names (the Quorum, Quorum Marshal, Quorum Control, the Static, NULL, Hum) and the fallback brands Swarmwire and Hivegrid. It replaces the search-excerpt evidence in [NAME-CLEARANCE.md](NAME-CLEARANCE.md) (rounds 1-3) and [LEGAL-AND-NAME-SWEEP-2026-10-18.md](LEGAL-AND-NAME-SWEEP-2026-10-18.md) §6 with primary-register evidence where it was reachable. All reads were made on **2026-10-18**.

Verdict tags: **VERIFIED** (primary source read, matches), **CORRECTED** (primary source differs; right value given), **NEW** (not claimed before; found now), **STILL UNVERIFIED** (could not be read; reason and manual step given).

## 1. Method and access log

| Route | Result |
|---|---|
| USPTO `tmsearch.uspto.gov` | **Reachable via its own search API** (the JSON endpoint behind the web UI, `POST /prod-stage-v1-0-0/tmsearch`, after loading the landing page for a session cookie). Index contains filings up to at least 2026-10-02 (e.g. serial 50141608). Searches were on the `wordmark` field unless stated. Design-only marks and phonetic equivalents are not covered. The ElasticSearch-style query is token based: a bare multi-word query is OR'd, so phrases were quoted. I did not read each record's TSDR status page (`tsdr.uspto.gov/statusview/...` returns a JS shell; the TSDR API `tsdrapi.uspto.gov` returns HTTP 401 without a key). |
| EUIPO eSearch (`euipo.europa.eu/eSearch`) | Page loads (HTTP 200) but is a JS application; the guessed JSON endpoints returned 404 / a default Apache page. **No search possible.** |
| TMview (`tmdn.org/tmview`) | Page loads, JS application; the API call returned a bot-protection script (Imperva). **No search possible.** |
| WIPO Global Brand Database (`branddb.wipo.int`) | JS application; the search API requires a verification token from a browser challenge. **No search possible.** |
| UKIPO (`search-trademark.service.gov.uk`, `trademarks.ipo.gov.uk`) | Connection failure / HTTP 403. **No search possible.** |
| Justia, Trademarkia | Justia HTTP 403; Trademarkia HTTP 200 but JS-rendered. Not used. |
| Companies House (`find-and-update.company-information.service.gov.uk`) | **Reachable** (company overview, officers, filing history, search). The API host needs a key (HTTP 401) and was not needed. |
| Verisign RDAP (`rdap.verisign.com`) for `.com`/`.net` | **Reachable.** `rdap.org` was used for other TLDs; its HTTP 404 answers are **indicative only** (not-registered, or no RDAP for that TLD). |
| Steam `api/storesearch` and `api/appdetails`, GOG `catalog.gog.com`, itch.io search, Apple `itunes.apple.com/search`, npm registry, PyPI JSON, Roblox omni-search | **Reachable.** |
| Google Play search | HTTP 200 but results render client-side; only the query echo is in the HTML. **STILL UNVERIFIED.** |
| Epic Games Store, Xbox, PlayStation, Nintendo eShop, Kickstarter, Indiegogo, Crunchbase | Not reachable by script (JS/bot challenge, or not attempted because no public API). **STILL UNVERIFIED.** Kickstarter returned a Cloudflare "Just a moment" page. |
| GitHub | GitHub MCP `search_users` / `search_repositories` worked. `api.github.com` by curl is blocked except for this repo. |
| Twitch `gql.twitch.tv` (the public web GraphQL) | **Reachable.** Twitch Help Center articles (`help.twitch.tv`) are a JS shell (every article, including 404s, returns the same 65,593-byte page). `blog.twitch.tv` is readable. |
| `courtlistener.com` API | HTTP 200 but **throttled** ("Rate limit exceeded: 125/day"). US court-record search not done. |
| `web.archive.org`, `trademarks.justia.com`, `reddit.com` | Unreachable / 403. WebFetch could not resolve several hosts (`ENOTFOUND`); curl was used instead. |
| Web search (US index) | Worked; used only to locate primary pages, never as the evidence itself. |

## 2. Verdict table

| # | Claim | Source doc + section | Primary URL | Read | Verdict | Verified value |
|---|---|---|---|---|---|---|
| 1 | "No HIVEPLEX mark found" | NAME-CLEARANCE R3.1; SWEEP §6.1 | tmsearch.uspto.gov (API) | 2026-10-18 | **VERIFIED (US only)** | 0 hits for `HIVEPLEX`, `HIVEPLEX*`, `*HIVEPLEX*`, `"HIVE PLEX"`, `HIVEPLEXX`, `HYVEPLEX`, the same token in `goodsAndServices`, `ownerName` and `wordmarkPseudoText`. Fuzzy (edit distance 1) found only LIVEPLEX (serials 88834332, 98050371; both abandoned) and DIVEPLEX (75852568, abandoned 1999). |
| 2 | "HIVE registered for game software by Hive Games Limited" | NAME-CLEARANCE R2; SWEEP §6 | tmsearch.uspto.gov | 2026-10-18 | **VERIFIED, scope CORRECTED** | Two live US registrations, both **class 9 only**: Reg. 7204225 (standard character, serial 88613286) and Reg. 7204224 (design plus words, serial 88613170); filed 2019-09-11, registered 2023-10-31. Goods start "Downloadable computer game software ...". Owner: HIVE GAMES LIMITED, York, UK. Its other US marks: TREASURE WARS (Reg. 6122204, class 9), CHUNKER (Reg. 7438836, class 42). **No class 41 (online games) HIVE registration for Hive Games Limited.** |
| 3 | "PLEX marks of Plex, Inc. in classes 9/41/42" | NAME-CLEARANCE R3.1 | tmsearch.uspto.gov | 2026-10-18 | **VERIFIED, CORRECTED (add class 38)** | Plex, Inc. live PLEX registrations: 4521387 (cl 9), 4521345 (cl 9), 6309924 (cl 9, 42), 5704452 (cl 41, 42), 7130759 (cl 9, 41, 42), **7401242 (cl 38, "Streaming of video material on the internet")**. Also MEDIAVERSE 6229649 and MASTER YOUR MEDIAVERSE 6229650 (cl 41, 42). See §4. |
| 4 | "Re-check PLEX reg. 4521387" | NAME-CLEARANCE checklist | tmsearch.uspto.gov | 2026-10-18 | **VERIFIED** | Reg. 4521387, "REGISTERED AND RENEWED", filed 2013-09-16, registered 2014-04-29, class 9, "Downloadable computer software in the field of digital media management ...". |
| 5 | Plex, Inc.'s class 41 filings cover games/streaming entertainment | NAME-CLEARANCE R3.1 ("class 41 filings") | tmsearch.uspto.gov | 2026-10-18 | **CORRECTED** | Plex's class 41 goods are "Entertainment services in the nature of news syndication reporting ... " and "Providing a web site featuring entertainment information about television programs, movies, music ...". **No live PLEX registration of any owner covers online games, video games or gameplay streaming in class 41, and none in class 28.** Plex's class 9/42 goods are media-server and video-streaming software. |
| 6 | "HIVEPLEX LTD, UK company 13440983, incorporated 2021-06-07, Godalming, mail-order/internet retail" | NAME-CLEARANCE R3.1; SWEEP §6.1 | find-and-update.company-information.service.gov.uk/company/13440983 | 2026-10-18 | **VERIFIED, status ADDED** | "Company status Active", private limited, "Incorporated on 7 June 2021", registered office 10 Perry Close, Godalming, GU7 1UX, SIC 47910 "Retail sale via mail order houses or via Internet". Micro-entity accounts filed on time every year (latest 9 Jul 2026, to 30 Jun 2026); confirmation statement filed 19 Jun 2026; two active directors (second appointed 15 Oct 2023). It is a living, compliant company, not a dormant shell. Trading name / website: **not shown on Companies House.** |
| 7 | "hiveplex.com registered 2017-11-22" | SWEEP §6.1 | rdap.verisign.com/com/v1/domain/hiveplex.com | 2026-10-18 | **VERIFIED, expiry NEW** | RDAP events: registration 2017-11-22, **expiration 2026-11-22** (35 days from today), last changed 2025-11-28; status `client transfer prohibited`; registrar handle 3862 (Spaceship, per RDAP link). Nameservers `NS1.BRANDBUCKET.COM` / `NS2.BRANDBUCKET.COM`. `https://hiveplex.com` answers **HTTP 301 to `https://www.brandbucket.com/names/hiveplex`** (a for-sale brand-name marketplace). |
| 8 | "hiveplex.com listed for sale at $2,495 (dnbolt.com)" | NAME-CLEARANCE R3.1; SWEEP §6.1 | dnbolt.com/hiveplex; brandbucket.com/names/hiveplex | 2026-10-18 | **STILL UNVERIFIED** (price) / **CORRECTED** (venue) | The domain is parked on BrandBucket per the redirect and nameservers. Both dnbolt.com and brandbucket.com return Cloudflare/403 challenges to scripts, so **no price was read.** |
| 9 | "Google's campus beehives were called the Hiveplex (2010)" | NAME-CLEARANCE R3.1 | mv-voice.com, sunset.com | not re-read | **STILL UNVERIFIED** (not in scope of this pass; low impact) | n/a |
| 10 | Plex "went to court over ZeePlex ... lost the interim round in India" | NAME-CLEARANCE R3.1 | scconline.com Bombay HC brief; torrentfreak.com/?p=194747; conventuslaw.com | 2026-10-18 | **VERIFIED (interim stage only)** | Bombay High Court, G.S. Patel J., refused the ad-interim injunction (suit filed 1 Oct 2020, launch 2 Oct 2020). SCC Times: Plex had international registrations "but not India". Court found "no prima facie case" and noted delay. **Final outcome is not in any source I read.** See §4. |
| 11 | "Plex ran a game-streaming service in 2021-22" | NAME-CLEARANCE R3.1 | plex.tv/blog/game-on-a-plex-blog-story/ | 2026-10-18 | **VERIFIED** | Blog dated 26 Jan 2021 (Plex Arcade); update: "We've made the difficult decision to close the doors on Plex Arcade on March 31, 2022." |
| 12 | Existing Twitch account `hiveplex` (holder UNKNOWN; the research brief wrongly called it the owner's, corrected 2026-10-18) | found by the coordinator through Twitch's public web GraphQL | gql.twitch.tv | 2026-10-18 | **VERIFIED** | `user(login:"hiveplex")`: id 82074766, displayName "Hiveplex", createdAt 2015-02-07T20:40:53Z, followers 0, `lastBroadcast.startedAt` null, no live stream. `swarmwire` and `hivegrid` return `user: null` (names not taken as Twitch logins). |
| 13 | Twitch recycles inactive names after 12 months of no login/view/broadcast | none (new) | blog.twitch.tv/en/2017/01/06/... | 2026-10-18 | **VERIFIED (2017 blog); current Help text STILL UNVERIFIED** | "An inactive account is defined as an account that has had no login, viewing, or broadcasting activity for at least twelve months." See §6. |
| 14 | "No Steam/itch/store game named Hiveplex" | NAME-CLEARANCE R3.1 | Steam `storesearch`, itch search, GOG catalog, App Store search | 2026-10-18 | **VERIFIED for Steam, itch.io, GOG, Apple App Store, Roblox, npm, PyPI, GitHub; STILL UNVERIFIED for Google Play, Epic, Xbox, PlayStation, Nintendo, Kickstarter** | See §3. One GitHub user named `hiveplex` exists (id 4049119); ownership unknown (§3). |

Counts by row (14 rows): **VERIFIED 8** (rows 1, 4, 6, 7, 10, 11, 12, 13); **CORRECTED 3** (rows 2, 3, 5); **CONTRADICTED 0**; **STILL UNVERIFIED 3** (rows 8, 9, and row 14, which is verified for the stores listed and unverified for the rest). Row 8 also corrects the venue (BrandBucket, not only dnbolt).

## 3. Findings: Hiveplex

### 3.1 Trademark registers

**USPTO (searched).** No application or registration, live or dead, for HIVEPLEX, HIVE PLEX, HIVEPLEXX or HYVEPLEX in any class (row 1). That is genuinely better than the earlier excerpt-level view, which could not exclude it.

The marks that matter are the two halves:

- **HIVE.** 1,153 US records match the token HIVE (any class, live and dead). Among exact `HIVE` word marks that are live and touch classes 9, 28, 35, 38, 41 or 42, the relevant ones are: Hive Games Limited (7204225, 7204224; class 9 downloadable game software); **Hive Studios LLC, serial 50065411, application filed 2026-08-21, status "NEW APPLICATION - RECORD INITIAL", class 41 "providing on-line computer games; providing online video games"** (and a TEAM HIVE application, 50065417, same filer, same day); Yianni John, Reg. 3695775, class 28 "Board games" (renewed); Bumble Holding Limited (class 9, 41, 42 and others; not games-related goods in the HIVE word mark); and many non-game owners (hardware, software, services). Compound HIVE marks for games are plentiful: TREASURE HIVE (Aristocrat, gambling software), HOPPIN' HIVE (Playtika, classes 9 and 41), HIVESWAP (What Pumpkin Games, class 9), RHYTHM HIVE (HYBE IM, class 9), BUMBLE HIVE (class 9 "Downloadable computer games"), FOR THE HIVE (application, class 9 video games). **HIVE as a leading word in games is a crowded field, which weakens any single owner's claim to it but does not remove Hive Games Limited's class 9 rights.**
- **PLEX.** 710 records match the token; the live exact `PLEX` marks include Plex, Inc.'s six registrations and several unrelated owners (furniture, adhesive tape, amplifiers, a software-for-travel mark, an ERP vendor). Plex, Inc.'s portfolio is in §4.

**Not covered:** EUIPO, WIPO (Madrid), UKIPO. This is the largest gap, because (a) HIVEPLEX LTD is a UK company, (b) Plex, Inc. holds "international trademark registrations in several jurisdictions" per the Bombay court brief (row 10), and (c) the project's audience is global. **STILL UNVERIFIED; manual step in §8.**

### 3.2 Company register

HIVEPLEX LTD (13440983) is **Active**, files micro-entity accounts, and has two directors (row 6). Its SIC code (47910, online retail) is a different field from a live-stream co-op wargame, but an online retailer that trades as "Hiveplex" has at least common-law (UK passing-off) goodwill in that name for retail. Whether it trades, under what name, and whether it holds any UK/EU trade mark are not answerable from Companies House. A UK limited company name registration also does not by itself give trade mark rights, but the Companies House "same as" rules and the passing-off exposure make it relevant to a UK-facing brand. **Needs the attorney and a manual web search of its likely trading name.**

### 3.3 Domain

hiveplex.com has been registered since 2017-11-22 by a party that parked it with BrandBucket (row 7, 8). **It expires on 2026-11-22.** That could mean it lapses and drops, is renewed by the broker, or is bought. Do not assume it will free up; treat it as "buyable at a broker's price (unverified)". Other TLDs: Verisign RDAP returns 404 for `hiveplex.net` (so not registered per the .net registry); `rdap.org` returned 404 for `.org`, `.tv`, `.gg`, `.io`, `.co.uk` (indicative only, not a registrar-confirmed availability). Confirm at a registrar.

### 3.4 Stores, package registries, social (common law)

| Place | Result for "hiveplex" |
|---|---|
| Steam (`storesearch`, cc=us) | total 0 |
| GOG catalog | 0 products |
| itch.io search | "0 projects match" |
| Apple App Store (`itunes.apple.com/search`, US) | 7 fuzzy results, none named Hiveplex (e.g. "Hive Game", "Swarm Simulator: Evolution") |
| Roblox omni-search | no game named Hiveplex in the first page read ("Mega Hive" is the closest title) |
| npm registry | `hiveplex` not found; search total 0 |
| PyPI | `/pypi/hiveplex/json` HTTP 404 |
| GitHub (MCP search) | **one user named `hiveplex` (id 4049119)**; 0 repositories match. Not investigated further (profile not read). **Check whether this is the owner's.** |
| Twitch | an existing account whose holder is unknown (row 12); the owner must say whether it is theirs |
| Discord (`/invites/hiveplex`) | "Unknown Invite" (no vanity invite by that code; not a proof the name is free) |
| Google Play, Epic, Xbox, PlayStation, Nintendo eShop, Kickstarter, Indiegogo, Crunchbase, YouTube/TikTok/X/Instagram/Bluesky/Reddit handles | **STILL UNVERIFIED** (JS-only, bot-challenged or 403; YouTube `@hiveplex` returned HTTP 404 and TikTok `@hiveplex` HTTP 200 as a JS shell, neither conclusive) |

A web search for "Hiveplex" with game/studio/app terms and one for `"hiveplex.com" OR "HIVEPLEX LTD"` returned nothing named Hiveplex (results were Hive Games, Hive Studios, HIVE the board game, and unrelated Hive retailers).

### 3.5 Evidence for and against, and the rating

**For (supports low risk):**
- Zero HIVEPLEX / HIVE PLEX filings in the US register, including near-spellings and goods text.
- No live PLEX registration of any owner covers video games or game streaming (class 41) or class 28 games. Plex, Inc.'s class 41 goods are news syndication and entertainment information.
- Hive Games Limited's US HIVE rights are class 9 game software only; "HIVE" in game names is common (a dozen+ live compounds), so a compound with a distinctive second element is a different overall impression from the bare word.
- Plex, Inc.'s only recorded enforcement against a "-plex" name that I could find (ZeePlex) lost at the interim stage (row 10), and Plex Arcade shut in 2022 (row 11). I found no TTAB or US federal case involving Plex, Inc. (search tool did not cover it; see §4).
- No Hiveplex game, app, store page or package on Steam, itch.io, GOG, App Store, Roblox, npm or PyPI.

**Against (keeps risk at medium):**
- **PLEX is a strong, well-known mark** in media streaming software, with six live US registrations and at least one enforcement attempt against a "-plex" name (ZeePlex); our product is a *streamed entertainment* product that viewers watch on Twitch/YouTube and that streams video from OBS. A brand ending in "-plex" in the same overall field (entertainment, software, streaming) invites a likelihood-of-confusion argument at the opposition stage or in a demand letter, even if it would not necessarily succeed.
- **HIVE** is registered by a game company in class 9 (downloadable games). If the project ever ships downloadable software (a client, a launcher, a mobile companion), class 9 is in play. Hive Studios LLC's 2026 HIVE application in class 41 online games is pending (not yet examined) and could become a cited prior-pending mark against a future HIVEPLEX class 41 application. These are cited by examiners on the lead word "HIVE" alone more often than the suffix.
- **HIVEPLEX LTD** is an active UK company with an identical name; UK passing-off and a UK/EU application risk are unquantified.
- **EUIPO, WIPO and UKIPO were not searched.** Any of them may hold a HIVEPLEX, HIVE PLEX or PLEX filing that the US search cannot show.
- The brand is designed to be one word; the visual/phonetic split "hive"+"plex" is exactly how a clearance examiner will break it into two known marks.

**Rating for "Hiveplex": MEDIUM (unchanged), with the US picture better than before and the EU/UK/WIPO picture unknown.** I would not lower it until (a) EUIPO, WIPO and UKIPO are searched and (b) an attorney has given a view on PLEX and HIVE. I would not raise it to High on the evidence: nothing found blocks use today. Expressed as an action: **proceed with the working brand for pre-launch work that costs little (handles, a Twitch page, a Discord), but make no purchase or filing commitment (domain at broker prices, merch, logo commissions, a trademark application) until the attorney review is done.**

## 4. Findings: Plex, Inc. and Hive Games Limited

### 4.1 Plex, Inc. US registrations (USPTO, live)

| Reg. | Mark | Class | Filed / registered | Goods (shortened) |
|---|---|---|---|---|
| 4521345 | PLEX | 9 | 2013-09-13 / 2014-04-29 | Downloadable software for digital media management (playing, organizing, transcoding video/audio/images) |
| 4521387 | PLEX | 9 | 2013-09-16 / 2014-04-29 | same wording; "REGISTERED AND RENEWED" |
| 5704452 | PLEX | 41, 42 | 2017-12-06 / 2019-03-19 | News syndication; non-downloadable media-management software for streaming; "SECTION 8 & 15-ACCEPTED AND ACKNOWLEDGED" (so incontestable status claimed) |
| 6309924 | PLEX | 9, 42 | 2019-09-09 / 2021-03-30 | Streaming software for ad-supported, subscription and transactional video on demand, music, podcasts |
| 7130759 | PLEX | 9, 41, 42 | 2022-06-03 / 2023-08-08 | Streaming and media-management software; news syndication; website with entertainment information |
| 7401242 | PLEX | 38 | 2023-05-15 / 2024-05-28 | "Streaming of video material on the internet." |
| 6229649 / 6229650 | MEDIAVERSE / MASTER YOUR MEDIAVERSE | 41, 42 | 2019-11-22 / 2020-12-22 | Entertainment-information database and website |

Plex, Inc.'s `MYPLEX` application (86064565, class 42) is abandoned. No `PLEX ARCADE` or other PLEX-formative game mark by Plex, Inc. appears among its US records. (The owner-name search also returned Tekni-Plex, Inc. records; they are an unrelated company and were excluded.)

### 4.2 Enforcement history ("-plex" names)

- **ZeePlex (India), verified at the interim stage only.** Bombay High Court (G.S. Patel J.) refused Plex, Inc. an ad-interim injunction against Zee Entertainment's "ZEEPLEX" pay-per-view film service. SCC Online's brief says Plex "obtained international trademark registrations in several jurisdictions, but not India", and that the court found "no prima facie case" and criticised the last-day filing; the suit was filed 1 Oct 2020, the launch was 2 Oct 2020. TorrentFreak and Conventus Law report the same outcome. **What happened after the interim order is not in any source I read.** The case turned on missing Indian registration, lack of shown Indian reputation and timing. Those facts do not carry over to the US, UK or EU, where Plex, Inc. holds registrations.
- **Other matters:** a web search for Plex, Inc. as opposer or petitioner at the TTAB found nothing relevant (the search tool did not index TTABVUE, so this is a gap in the tool, not evidence of absence). CourtListener was rate limited (§1). **US federal litigation by Plex, Inc. against "-plex" names is therefore STILL UNVERIFIED.**
- Plex Arcade (a game-related Plex service) existed 2021 to 2022-03-31 (row 11). It shows Plex was willing to enter games; it is closed.

### 4.3 Hive Games Limited

Registrations and scope: row 2 (class 9 game software, two registrations, 2023). It runs a Minecraft Bedrock server called The Hive (per search results; its own site was not fetched). **No enforcement action, cease-and-desist, litigation or TTAB filing by Hive Games Limited was found** (search tool and USPTO `proceedings` field not conclusive). Its UK/EU registrations (it is a York, UK company) were **not searched.**

## 5. Findings: in-world names and fallback brands

USPTO searches below are by wordmark. "Game classes" means 9, 28 or 41 unless said otherwise. Stores: Steam `storesearch`, itch.io search, GOG catalog, Apple search, npm, PyPI.

| Name | USPTO | Stores / registries | Read |
|---|---|---|---|
| **the Quorum** | 166 token matches. Live exact `QUORUM` marks in cls 9/41: Consensys Software (cl 9, Reg. 6365037, blockchain software), QuorumLabs (cl 9, 42), Themis Computer (cl 9), Quality Assist (cl 41, early-childhood education), Quorum Business Solutions (cl 9, 35, 36, 42). Compounds: THE QUORUM INITIATIVE (cl 41, social club services), ROSS QUORUM (cl 9/35/41, video production software), QUORUM CYBER, CAREQUORUM, OUTQUORUM, WE HAVE QUORUM (cl 41, blogs; registered 2026-10-06). **None is for games or live-stream entertainment.** No cancelled-or-live QUORUM game-class mark except dead ones (Swede Industries cl 28, Musselwhite cl 41). | Steam: a game "Quorum" by rileyb3d, "Coming soon", Adventure/Indie (app 4299350). itch.io: 12 matches including "Quorum", "Space Quorum", "QUÓRUM". GOG: none exact. | As an **in-fiction faction name**, low risk. As a **brand** (channel, Discord, merch), Medium: a common English word with many unrelated registrants and at least one same-name indie game coming to Steam. Search was filtered to classes 9/28/41 for the cross-class view; classes 35/38/42 were not listed. |
| **Quorum Marshal / Quorum Control** | No mark combining QUORUM with MARSHAL or CONTROL (AND query: 0 hits). | itch.io and Steam: no title with those exact words (itch matches are the single word "Quorum"). | Low. Nothing found for the compounds. |
| **the Static** | Exact `STATIC` live in game classes: Variflex (cl 28 skateboards, Reg. 2012653), Balaji Trading (cl 9, phone cases). `"THE STATIC"` as a phrase: 6 records, none live in games. STATIC-formative live cl 41 marks exist (STATIC SHOCK, DC Comics; STATIC NIGHTMARE, Play'n GO, **online games and gambling**, Reg. 8092782, registered 2026-01-06). | **Steam: a game titled "The Static" by aFonte Games LLC, released 16 Dec 2024, Early Access, Action/Adventure/Casual/Indie** (app 1937930); also "Static Dread" and "the static speaks my name". itch.io: "The Static", "The Static Road", "THE STATIC HOURS" and others. | **As a game or brand name: Medium to High** (an existing PC game with the exact title; a very common word). As an in-world enemy faction label that is never the product name: Low to Medium. Do not use "the Static" as a store or channel name. |
| **NULL** | Exact `NULL` in cls 9/28/41: one live application, Null Solutions Limited (UK), serial 79460689, filed 2026-06-11, classes 42/9/36 (blockchain/crypto software). Mattel's NULL marks (cl 28) are dead. | Steam: no exact-title game (matches are compounds such as "Null Drifter", "Sig.NULL", "Null Vector"). itch.io: at least two projects titled "NULL". | Low as a **character** name. Poor as a **brand**: a programming keyword with unsearchable results. |
| **Hum** | Live exact `HUM`: Solid Space Inc. (cl 9, Regs. 7516806, 7516807, landlord/tenant software), Real World Holdings Limited (UK; cl 9 and 41 retained, Reg. 5958983, partial Section 8), 8177 Holdings (cl 9, 38 etc.), Hum Life (cl 28, yoga bolsters). **Class 41 pending: HUM, Sombra Project LLC, serial 99937846, filed 2026-07-13, "NON-FINAL ACTION - MAILED", events, meditation.** THE HUM, Lifecourage LLC (cl 41, Reg. 7516145, mental-health videos). | Steam: "HUM" by NO JOY, "Coming soon" (app 1872520). | Low to Medium as a character. Crowded and several class 9/41 owners. |
| **Swarmwire** | **0 records** (`SWARMWIRE*`, any class). | Steam: 0. GOG: 0. itch.io: 8 fuzzy matches, all different "Swarm..." titles. App Store: none named Swarmwire. **npm: a package named `swarmwire` exists** ("TypeScript multi-agent orchestration library", created 2026-03-27, latest 1.0.3, one maintainer). PyPI: 404. Twitch login: free. GitHub user: 0. `swarmwire.com` registered since 2015-08-04, expires 2027-08-04 (owner unknown, RDAP only). | **Low-Medium.** Clean on the USPTO and game stores, but a same-name npm package in the AI/agent space, an older registered .com, and "swarm"-formative marks are a crowded field. The npm package is software, not a game, but it is in the field this project's tooling uses (agents). |
| **Hivegrid** | **0 records** (`HIVEGRID*`, any class). | Steam: 0. GOG: 0. itch.io: 1 fuzzy ("HiveGrind"). App Store: none. npm/PyPI: not found. Twitch login: free. `hivegrid.com` registered since 2010-12-18, expires 2027-12-18. | **Low-Medium.** Clean on the USPTO and stores; the .com is taken by someone else for 16 years; "HIVE" (§3) applies equally. EU/UK/WIPO not searched. |

## 6. Findings: the existing Twitch account `hiveplex` (holder unknown)

Facts read (row 12): login `hiveplex`, user id 82074766, created 2015-02-07, 0 followers, never broadcast.

**What the policy says (primary, 2017):** Twitch's own blog (6 Jan 2017) defines an inactive account as one with "no login, viewing, or broadcasting activity for at least twelve months", says reclaimed accounts have their profile data deleted, and says the fix is to log in ("All you need to do is log into it!"). Partnered accounts are never reclaimed. On acquiring someone else's dormant name it says: "We do not accept vanity name change requests or requests to claim specific names at this time." Its 24 Feb 2017 post says you can change your own username "once every 60 days" from Profile Settings and that the abandoned name is held "for a minimum of six months".

**What I could not read:** the current Help Center article "Username Rename & Recycling Policies" (`help.twitch.tv/s/article/username-rename-and-recycling-policies`), which is a JS-only page. A search excerpt of it quotes a 180-day hold and a 60-day rename interval, which is consistent with the 2017 posts; treat as **[EXCERPT-OFFICIAL], STILL UNVERIFIED** against the live article.

**What this means for the decision:**
1. **Ownership is unknown.** The research brief wrongly described this account as the owner's; nothing established that. **Case (a), it is the owner's:** the risk is losing it if it counts as inactive. The account has no broadcasts and 0 followers; whether it has had logins or viewing in the last 12 months is unknown to me. **Log in now** (and at least yearly) per the blog guidance. **Case (b), it belongs to someone else:** Twitch states it accepts no requests to claim specific names, so the name cannot be obtained on request; the only documented route is trademark-based and needs a registered mark. Use a fallback handle (e.g. `playhiveplex`, free at check time).
2. In case (a), if the owner later changes the brand, renaming the account is self-service (60-day interval) and no request path is needed. Twitch holds the vacated name, so renaming away from `hiveplex` surrenders it for at least the hold period.
3. If a different name is wanted that is held by a dormant account (not applicable to `swarmwire`/`hivegrid`, which are free), Twitch states it does not process claim requests; the only documented route is trademark-based (Twitch can reclaim names for trademark infringement per the help-center excerpt) and that requires a registered mark.
4. A Twitch handle gives no trademark rights, and the Twitch Terms/trademark policy can cut both ways: a stronger mark owner (Plex, Hive Games) could in theory complain about the handle. Low probability, but another reason to keep the attorney review ahead of heavy brand investment.

## 7. Questions for a trademark attorney

Ask these exactly; bring this document and the table in §4.

1. **PLEX versus HIVEPLEX.** Plex, Inc. owns PLEX in classes 9, 38, 41, 42 (§4.1) and is known for media streaming. We are a free, viewer-controlled game streamed on Twitch/YouTube, with possible later merch, a companion web app and, maybe, downloadable software. Is HIVEPLEX likely to be refused or opposed, or to draw a demand letter, in the US, UK and EU? Would different spelling, presentation or a descriptor change the answer?
2. **HIVE versus HIVEPLEX.** Hive Games Limited owns HIVE in class 9 game software (US Regs. 7204224, 7204225) and presumably in the UK/EU; Hive Studios LLC has a pending HIVE application in class 41 online games (serial 50065411). Does a prior HIVE registration in class 9 and a pending HIVE in class 41 create a realistic examiner refusal on HIVEPLEX for classes 9, 41 and 42? Should we file in 41 only?
3. **HIVEPLEX LTD (UK 13440983).** Does an active UK online-retail company of the same name create passing-off or opposition exposure for a UK/EU brand, and for a US brand sold to UK users? Should we contact them, wait, or avoid UK filings?
4. **Which searches to commission.** A full search (not a knockout) in US, UK, EU and WIPO with phonetic and design coverage, plus common law, for HIVEPLEX/HIVE PLEX/HIVE-PLEX, in classes 9, 28, 35, 38, 41, 42? Cost and turnaround.
5. **Class strategy and timing.** Which classes to file first for a live-stream game (41 for online games and entertainment, 9 for downloadable software, 35, 38 or 42 as needed)? Intent-to-use (Section 1(b)) versus waiting for use? Does filing before the public announcement reduce risk?
6. **Name vs brand split.** Is it safer to use HIVEPLEX only as a studio/channel brand and a different mark for the game, or the reverse?
7. **Fallbacks.** Given §5, are SWARMWIRE or HIVEGRID better starting points, given the npm package `swarmwire` and the old domains? What residual SWARM/HIVE issues remain?
8. **In-world names.** Is it safe to use "the Static" (existing Steam game of that exact title, aFonte Games LLC) and "the Quorum" (a coming Steam game "Quorum", many QUORUM registrations in other fields) as in-fiction names in marketing, key art and store copy, provided they are never the product name?
9. **Domain.** Should we buy hiveplex.com from the broker, or does owning it create a record of knowledge of the PLEX/HIVE marks? (The domain expires 2026-11-22.)
10. **Enforcement history.** Can the attorney check TTABVUE and federal dockets for Plex, Inc. and Hive Games Limited as oppose/petitioner/plaintiff, which I could not (§4.2)?

## 8. Manual steps still needed from the owner

1. **Search EUIPO, WIPO, UKIPO in a browser** (or give them to the attorney): eSearch `euipo.europa.eu/eSearch`, TMview `tmdn.org/tmview`, WIPO Global Brand Database `branddb.wipo.int`, UKIPO `search-trademark.service.gov.uk`. Terms: HIVEPLEX, HIVE PLEX, PLEX, HIVE, SWARMWIRE, HIVEGRID; classes 9, 28, 35, 38, 41, 42. Record owner, status and goods for anything live. These were the three registers I could not reach.
2. **Log in to the Twitch `hiveplex` account now** and set a reminder to log in yearly. Confirm the current rule in the Help Center article "Username Rename & Recycling Policies" (open it in a browser; it is a JS page).
3. **Check the GitHub user `hiveplex` (id 4049119)**: is it yours? If not, decide on an alternative GitHub org name.
4. **Domain:** note hiveplex.com expires 2026-11-22; open `brandbucket.com/names/hiveplex` to read the asking price. Check availability of `.gg`, `.tv`, `.io`, `.live`, `.app` at a registrar (RDAP results here were indicative only).
5. **Google Play, Epic Games Store, Xbox, PlayStation Store, Nintendo eShop, Kickstarter, Indiegogo, Crunchbase, YouTube, TikTok, X, Instagram, Bluesky, Reddit**: search "Hiveplex", "Hive Plex", "Swarmwire", "Hivegrid" in a browser (all JS or bot-gated for scripts).
6. **HIVEPLEX LTD:** search the web for its trading name and site (Companies House shows none). Do not contact it before the attorney advises.
7. **Hive Studios LLC serial 50065411** and **Hive Games Limited**: ask the attorney to watch both (the pending application may be examined within months).
8. **CourtListener / TTABVUE:** search "Plex, Inc." as party (the CourtListener quota resets; TTABVUE is a browser UI).
9. **TTS test:** unaffected by this pass; already listed in NAME-CLEARANCE.

## 9. Corrections to existing docs

| File | Section | Old text | New text |
|---|---|---|---|
| `docs/review/NAME-CLEARANCE.md` | R3.1 table row "HIVEPLEX LTD ..." | "HIVEPLEX LTD, UK company 13440983, incorporated 2021-06-07 in Godalming, mail-order/internet retail (per excerpt)" | "... Active, private limited, SIC 47910, files micro-entity accounts annually (last to 30 Jun 2026), two directors (read at Companies House 2026-10-18)" |
| `docs/review/NAME-CLEARANCE.md` | R3.1 and §Why medium | "Plex ... has PLEX marks in classes 9/41/42" | "Plex, Inc. has live PLEX registrations in classes 9, 38, 41 and 42; its class 41 goods are news syndication and entertainment information, not games. No PLEX registration of any owner covers video games (USPTO, 2026-10-18)." |
| `docs/review/NAME-CLEARANCE.md` | R3.1 "HIVE (Hive Games Limited)" | "HIVE registered for game software" | "HIVE: US Regs. 7204224 and 7204225 (class 9 downloadable game software only), registered 2023-10-31. No class 41 HIVE registration for Hive Games Limited. A separate HIVE application in class 41 online games (Hive Studios LLC, serial 50065411, filed 2026-08-21) is pending." |
| `docs/review/NAME-CLEARANCE.md` | R3.1 "No HIVEPLEX record in aggregator results" | aggregator-level statement | "USPTO register search 2026-10-18: no HIVEPLEX, HIVE PLEX, HIVEPLEXX or HYVEPLEX record in any class. EUIPO, WIPO, UKIPO not searched." |
| `docs/review/NAME-CLEARANCE.md` | R3.1 domain row | "hiveplex.com listed for sale at $2,495 on a domain-broker page (per excerpt; not checked at a registrar)" | "hiveplex.com: registered 2017-11-22, expires 2026-11-22 (Verisign RDAP). It redirects to brandbucket.com/names/hiveplex and uses BrandBucket nameservers. Price not read (script blocked); the $2,495 figure is from a search excerpt of dnbolt.com." |
| `docs/review/NAME-CLEARANCE.md` | R3.1 "went to court over ZeePlex" | "has gone after a '-plex' compound before (and lost the interim round in India)" | Keep, add: "Bombay HC refused interim relief in Oct 2020 because Plex had no Indian registration or shown Indian reputation and sued the day before launch; final outcome not found." |
| `docs/review/NAME-CLEARANCE.md` | checklist, "Look up HIVEPLEX LTD" | open item | Mark done for status and SIC; leave trading name open. |
| `docs/review/NAME-CLEARANCE.md` | checklist, USPTO register search | open item | Mark USPTO done (see this document); EUIPO/TMview/WIPO/UKIPO remain open. |
| `docs/review/LEGAL-AND-NAME-SWEEP-2026-10-18.md` | §0 access table | "tmsearch.uspto.gov, tsdr.uspto.gov: Unreachable; Companies House: Unreachable; store pages unreachable; rdap unreachable" | Update to this document's §1: USPTO search API, Companies House, Verisign RDAP, Steam, itch.io, GOG, Apple search, Roblox, npm, PyPI, Twitch GraphQL and blog are reachable. |
| `docs/review/LEGAL-AND-NAME-SWEEP-2026-10-18.md` | §6.1 | "hiveplex.com listed for sale at $2,495 on a broker page (as in round 3). ... No registrar check was possible." | Registrar/registry check done: see correction above (expiry 2026-11-22). |
| `docs/review/LEGAL-AND-NAME-SWEEP-2026-10-18.md` | §6.1 / risk row 1 ("Plex, Inc. filings in 42/9/41/38; all from aggregators") | aggregator-level | "Verified on the USPTO register: Plex, Inc. 6 live PLEX registrations (§4.1 of TRADEMARK-AND-NAME-VERIFICATION-2026-10-18.md)." |
| `docs/planning/OPEN-QUESTIONS.md` | Q-LEGAL-5 / Q-BRAND-6 | basic clearance pending | Add: "USPTO knockout done 2026-10-18 (no HIVEPLEX filing; see TRADEMARK-AND-NAME-VERIFICATION-2026-10-18.md); EUIPO/WIPO/UKIPO and attorney review still open; hiveplex.com expires 2026-11-22." |
| Any doc that lists the Twitch handle for Hiveplex | n/a | "`twitch.tv/hiveplex` to be checked" | "Exists (user id 82074766, created 2015-02-07, holder unknown). If it is the owner's: log in at least yearly to avoid the 12-month inactivity reclaim (Twitch blog 2017-01-06). If not: Twitch accepts no requests to claim specific names; use a fallback handle." |

## 10. STILL UNVERIFIED

| Item | Reason | Manual step |
|---|---|---|
| EUIPO, TMview, WIPO Global Brand DB, UKIPO search results | JS apps / bot protection / 403; no public key-free API found | §8 step 1 |
| Current Twitch Help Center text for username recycling and renaming | JS-only page; only a search excerpt | §8 step 2 |
| hiveplex.com asking price, and the $2,495 figure | dnbolt.com and brandbucket.com block scripts | §8 step 4 |
| Final outcome of Plex v. Zee (India) and any US court or TTAB history for Plex, Inc. / Hive Games Limited | CourtListener throttled; TTABVUE is UI-only; sources found stop at the interim order | §8 step 8; attorney Q10 |
| Google Play, Epic, Xbox, PlayStation, Nintendo eShop, Kickstarter, Indiegogo, Crunchbase, YouTube, TikTok, X, Instagram, Bluesky, Reddit handles | JS-only or bot-gated | §8 step 5 |
| Whether HIVEPLEX LTD trades under that name; what the GitHub user `hiveplex` is | not on the register; profile not read | §8 steps 3, 6 |
| Google's 2010 "Hiveplex" beehives (NAME-CLEARANCE R3.1) | out of scope for this pass | none needed |
| Nice class wording for classes 9/28/35/38/41/42 | earlier tag [UNVERIFIED] stays; class numbers here come from the USPTO records' own "IC" field | attorney Q5 |
