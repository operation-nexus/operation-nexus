# Legal, License and Name Sweep, Round 4 (Q-LEGAL-5) — 2026-10-18

> **Research, not legal advice.** The author is not a lawyer. Nothing here is a legal opinion, a trademark clearance or a compliance sign-off. Where an attorney is needed, this document says so.
>
> **Source quality, stated up front (AGENTS.md rule 0).** In this research environment only two hosts were reachable by direct request: `pypi.org` and `registry.npmjs.org` (JSON metadata). **Every platform policy page, trademark register, store page and handle page was unreachable** (see §0). Platform and legal statements below therefore come from **web-search result excerpts** (some of them excerpts of the official page, many from third-party summaries). Each is marked **[UNVERIFIED]** unless it was read in full from the primary source. Nothing here was read in full from a platform's own policy page. "Nothing found" means only that the searches returned nothing.

Scope: Q-LEGAL-1 to Q-LEGAL-8 and Q-BRAND-4 to Q-BRAND-7 (OPEN-QUESTIONS), following [NAME-CLEARANCE.md](NAME-CLEARANCE.md) rounds 1–3 and [PLATFORM-REALITY-CHECK.md](PLATFORM-REALITY-CHECK.md). Date of all reads: **2026-10-18**.

## 0. What was and was not reachable

| Route | Result |
|---|---|
| `pypi.org/pypi/<pkg>/<ver>/json` (curl) | **Reachable.** Used for every Python license below. |
| `registry.npmjs.org/<pkg>/<ver>` (curl) | **Reachable.** Used for every npm license below. |
| `raw.githubusercontent.com` (WebFetch) | Reachable as a host (a wrong path returned 404). The paths tried for Piper's LICENSE were not found, and `gh api` for any repo other than this one was refused ("GitHub access to this repository is not enabled"). So **upstream repo LICENSE files were not read**; package-index metadata and search excerpts were used instead. |
| tmsearch.uspto.gov, tsdr.uspto.gov | **Unreachable** (curl: proxy refusal; WebFetch: DNS `ENOTFOUND`). |
| EUIPO eSearch, TMview (tmdn.org), WIPO Global Brand DB (branddb.wipo.int), gov.uk trade mark search | **Unreachable** (same). |
| Companies House (find-and-update.company-information.service.gov.uk) | **Unreachable** by fetch. The company page title and a short excerpt appeared in a search result. |
| store.steampowered.com, itch.io | **Unreachable** (same). Only search excerpts. |
| twitch.tv (legal pages and channel pages), youtube.com, reddit.com, discord.com, developers.google.com, dev.twitch.tv | **Unreachable** (same). Only search excerpts. |
| rdap.org, rdap.verisign.com (domain availability) | **Unreachable.** Domain and handle availability could not be checked at all. |
| web.archive.org, r.jina.ai (mirrors tried as alternate routes) | Blocked ("unable to fetch") or DNS failure. |
| plex.tv, epidemicsound.com, nice-classification.org, wipo.int/classifications | **Unreachable.** Nice class wording below is **[UNVERIFIED]**. |
| Web search (US index) | Worked. Result excerpts are the only source for everything outside §2's package metadata. |

## 1. Project license audit

**Facts read from the repo:** `LICENSE` is the standard MIT text, `Copyright (c) 2026 cant`. There is no `assets/` directory, no `docs/legal/` directory, no `TRADEMARKS`/`NOTICE` file and no `CONTRIBUTING`/CLA/DCO file (checked with `ls`). AUDIO-TTS.md says voice-model licenses are recorded in `docs/legal/THIRD-PARTY.md`, **but that file does not exist yet**. CONFIG-AND-CONTENT.md (lines ~461–464) specifies an asset provenance register under `assets/`.

| # | Finding | Action / owner |
|---|---|---|
| 1.1 | **Copyright holder "cant" does not match the planned public identity** (saltyseraphcodes, Q-LEGAL-6/8). It is also not a legal name. The MIT notice only has force if it names the right rights holder, and it must be copied into every redistributed copy. A holder name that changes later means two holders in history. | Owner decides the holder string (an individual's legal name, a pen-name or a future LLC) **before the Q-LEGAL-8 fresh-start import commit**, so the clean repo carries the right notice from commit 1. If an LLC is planned, ask the attorney whether to assign copyright now or later. Agent can then edit one line. |
| 1.2 | **MIT + "brand and art all rights reserved" (Q-LEGAL-4) is coherent**, because the MIT text grants rights to "the Software and associated documentation files" and says nothing about trademarks, names or art. Copyright and trademark are separate rights, so MIT does not by itself license the brand. The risk is **ambiguity**: art or brand files inside an MIT repo are covered by the MIT grant unless carved out. The carve-out therefore has to be explicit and has to cover the copyright in the art, not only the trademarks. | See 1.3. |
| 1.3 | **Mechanisms commonly used** (general practice; named projects not verified in this pass **[UNVERIFIED]**): (a) a root `TRADEMARKS.md` (or "Trademark policy") that says the name/logo are not licensed, and what fair use looks like (accurate reference, no implied endorsement, no confusingly similar names for forks); (b) a separate `assets/LICENSE` ("All rights reserved", with a clause for personal/non-commercial viewing if wanted); (c) a README paragraph; (d) per-file headers or a `REUSE.toml`/`.reuse/dep5` (the REUSE spec, reuse.software, assigns an SPDX license per path, which is a clean fit for a mixed-license repo **[UNVERIFIED primary]**); (e) the asset provenance register already planned (Q-BRAND-5/NX-318). A strong option is to keep brand art **out of the public repo** entirely, in a private repo or the broadcast host only, so no license text has to do the work. | Owner chooses A (carve-out files in repo) or B (art kept private). Recommended minimum: `assets/LICENSE` + `TRADEMARKS.md` + README pointer + REUSE-style per-path mapping, reviewed by an attorney once. |
| 1.4 | **Contributors.** Under MIT, inbound contributions are by default under the same MIT terms only if the contributor says so or the repo states it. Two common mechanisms: **DCO** (Developer Certificate of Origin, a `Signed-off-by` line, lightweight, confirms the right to submit) and a **CLA** (a signed agreement that can also grant relicensing rights). With MIT in, MIT out, a CLA is mainly needed if the owner wants the freedom to **relicense later or dual-license** (for example to move the code away from MIT, or to sell a commercial license). DCO is enough if MIT stays. Either way a CONTRIBUTING note should state: code is MIT; contributions of art/brand are not accepted into `assets/` without a written grant (NX-319 already requires commission contracts to grant the needed rights). **Note:** AGENTS.md rule 12 (no co-author trailers) is about AI trailers; a DCO `Signed-off-by` line would need an explicit exception in `scripts/check_commit_msg.py` rules, so decide before outside PRs arrive. | Owner decision (Q below). |
| 1.5 | **Third-party material in a public MIT repo.** Fonts and any vendored code keep their own licenses and notices (OFL fonts need their license text shipped with them; see §4.3). A `docs/legal/THIRD-PARTY.md` is referenced by the AUDIO-TTS spec but does not exist. | Create when the first third-party asset or non-dev dependency lands (agent). |
| 1.6 | **Name in the license vs. the planned public identity:** the Q-LEGAL-8 fresh-start publication means the old history (with `cant` and personal handles) may stay cached or forked. That does not change the license of what was already published (MIT grants already given are not revocable in practice **[UNVERIFIED legal point; ask attorney]**). | Attorney question. |

## 2. Dependency license audit

### 2.1 Method

- Python: `services/sim/uv.lock` parsed (no install, no lockfile change). For each locked name+version, `https://pypi.org/pypi/<name>/<version>/json` was read (`license_expression`, `license`, classifiers).
- npm: `apps/overlay/pnpm-lock.yaml` `packages:` section parsed (no install, no change). For each `name@version`, `https://registry.npmjs.org/<name>/<version>` was read (`license`).
- `tools/` contains only `README.md` (no manifests). `services/sim` has **no runtime dependencies** (`dependencies = []`). The overlay has **no runtime dependencies** (only `devDependencies`).
- The license strings are what each package declares in its own registry metadata. They were **not** cross-checked against the upstream LICENSE files (those hosts were not reachable, see §0).

### 2.2 Direct dependencies (all dev/build-time only; none ships in the product)

| Package | Version | Declared license | In Q-LEGAL-1 allowlist? |
|---|---|---|---|
| ruff | 0.17.1 | MIT | yes |
| mypy | 2.4.0 | MIT | yes |
| pytest | 9.1.1 | MIT | yes |
| hypothesis | 6.170.1 | **MPL-2.0** | yes (MPL-2.0 is file-level copyleft; fine for an unmodified dev tool) |
| import-linter | 2.15 | BSD 2-Clause (in `license` field and classifier) | yes |
| @eslint/js 10.0.1, eslint 10.13.0, prettier 3.9.10, typescript-eslint 8.71.2, vite 8.3.4, vitest 5.0.5 | as listed | MIT | yes |
| typescript | 6.0.3 | Apache-2.0 | yes |

### 2.3 Transitive dependencies

- **Python (16 transitive, from uv.lock):** all permissive, with these notes. `typing-extensions 4.16.0` declares **PSF-2.0**, which is **not in the Q-LEGAL-1 list** (permissive, OSI-approved, but not named). `packaging 26.3` is `Apache-2.0 OR BSD-2-Clause`. `pathspec 1.1.1` is MPL-2.0 (classifier only). `ast-serialize`, `librt`, `iniconfig`, `pluggy`, `markdown-it-py`, `mdurl`, `rich`, `mypy`-family: MIT. `click`, `pygments`, `grimp`: BSD. `colorama`: BSD (classifier). `sortedcontainers`: Apache 2.0. **`mypy-extensions 1.1.0` has no license text in its PyPI metadata** (no `license` field, no license classifier; only the homepage URL `github.com/python/mypy_extensions`). It is widely known as MIT, but **that was not verified from the repo** **[UNVERIFIED]**.
- **npm (146 transitive; 153 `name@version` entries in total):** MIT 111, Apache-2.0 15, **MPL-2.0 12**, BSD-2-Clause 6, ISC 6, BSD-3-Clause 2, **BlueOak-1.0.0 1**. The 12 MPL-2.0 entries are `lightningcss` 1.33.0 and its 11 per-platform native binaries (Vite's CSS tooling). `minimatch 10.2.6` declares **BlueOak-1.0.0** (permissive, **not in the allowlist**).
- Nothing GPL/AGPL/LGPL and nothing "UNLICENSED" appeared in either lockfile.

### 2.4 Allowlist flags

| Item | Why flagged | Suggested handling |
|---|---|---|
| PSF-2.0 (`typing-extensions`) | Not in list. Permissive. | Add PSF-2.0 and BlueOak-1.0.0 to the allowlist, or record them as accepted exceptions (owner decision). |
| BlueOak-1.0.0 (`minimatch`) | Not in list. Permissive. | Same. |
| MPL-2.0 (hypothesis, pathspec, lightningcss and its binaries) | In list. File-level copyleft: if the project modified and **distributed** those files it would have to publish those files. Unmodified dev tooling is fine. | None. Keep out of any shipped bundle (lightningcss is a build tool). |
| `mypy-extensions` (no declared license) | Missing metadata. | Agent: read upstream LICENSE once GitHub access to `python/mypy_extensions` exists; until then **[UNVERIFIED]**. |

CI today has no license gate. A license-scan job (for example `pip-licenses` / `license-checker`-style, or `uv`/`pnpm` license listing) with an allowlist would turn this table into an enforced check **[tool names not verified]**. It is a decision for the owner whether to add it (Q-LEGAL-1 follow-up).

### 2.5 Planned dependencies named in specs or ADRs (not yet in the repo)

Licenses below are from **PyPI/npm metadata read today** unless marked. "Distribute" = giving copies to others (public repo, Docker images pushed publicly, downloads). "Run as a service" = operating it ourselves and letting others interact with it over a network. **GPL v3 (no network clause): running unmodified or modified GPL code privately as a service does not by itself trigger source obligations; distributing it does. AGPL v3 §13 adds a duty to offer source to remote users who interact with a modified version.** (Source: secondary summaries read via search today, **[UNVERIFIED primary]**; the GPL/AGPL texts were not read.) Because our repo is public, anything **we commit** is distributed. Because our container images may be pushed to a registry, anything **baked into a pushed image** may be too.

| Component | Where planned | License (source) | Obligation notes |
|---|---|---|---|
| **Piper TTS (piper1-gpl)** | AUDIO-TTS | `piper-tts 1.8.0`: **GPL-3.0-or-later** (PyPI). Original `rhasspy/piper` was MIT and archived Oct 2025 (search excerpt **[UNVERIFIED]**). | Spec already isolates it in a separate `nexus-tts` process. Safest: pip-install it only on the host, never vendor it into the MIT repo, never push an image containing it publicly. If the TTS image is distributed (even to the owner's other machine via a public registry), GPL source obligations arise for that image. Running it privately on the broadcast PC is the low-risk path. **Voice models have their own licenses** (per-model MODEL_CARD); not read **[UNVERIFIED]**. |
| **espeak-ng** (Piper and Kokoro phonemizer) | AUDIO-TTS | GPL-3.0-or-later per search excerpts (project README and distro metadata) **[UNVERIFIED primary]**. Python wrappers: `phonemizer 3.4.0` **GPL-3.0+**, `espeakng 1.0.5` **GPLv3** (PyPI). `espeakng-loader 0.2.4`: no license in PyPI metadata. | Same isolation. Whether dynamic linking into a differently licensed program creates obligations is a known legal question; **attorney or FSF-guidance question**, not decided here. |
| **Kokoro** | AUDIO-TTS | Python `kokoro 0.9.4`: Apache License (PyPI). Model card excerpt: weights Apache-2.0, code MIT, with a GPLv3 dependency in espeak-ng **[UNVERIFIED primary]**. `kokoro-js 1.2.1`: Apache-2.0 (npm). `kokoro-onnx 0.6.1`: no license in metadata. | Weights Apache-2.0 is fine. Training-data and voicepack provenance **not found**. The espeak-ng dependency means the same isolation applies. |
| `pedalboard` (if audio effects are added) | not named | `0.9.26`: **GPLv3** (PyPI) | Avoid or isolate in the TTS worker. Not in specs today. |
| **discord.py** | CHAT/ops notifications | `2.7.1`: MIT (PyPI) | Fine. Discord's own developer terms apply (§3.5). |
| **twitchio** | gateway | `3.3.2`: MIT (PyPI classifier) | Fine. The `@twurple/*` npm packages (8.2.0) are MIT. |
| **Pydantic / fastapi / uvicorn / websockets** | contracts, API | MIT / MIT / BSD-3 / BSD-3 (PyPI) | Fine. |
| `datamodel-code-generator` 0.85.0, `jsonschema` 4.26.0, `json-schema-to-typescript` 16.0.0 | CONTRACTS | MIT (PyPI/npm) | Fine. Generated output is committed; generator license does not infect it **[UNVERIFIED general point]**. |
| **litellm** (PLATFORM-REALITY-CHECK notes a March 2026 compromise) | LLM gateway | `1.106.0`: MIT (PyPI) | License fine; the risk is supply chain (hash-pin or skip). `instructor 1.17.0`: MIT. `anthropic 1.15.0`: MIT; `openai 3.35.1` and `google-genai 2.31.0`: Apache-2.0. Provider terms (output ownership, acceptable use) were **not** reviewed here. |
| **psycopg** (if Postgres is used) | DATA-MODEL | `3.3.6`: **LGPL-3.0-only** (PyPI) | Not on the allowlist. LGPL via dynamic import in a service is commonly accepted, but it is outside Q-LEGAL-1 as written. Alternatives from the same check: `asyncpg 0.32.0` Apache-2.0, `sqlalchemy 2.1.5` MIT. |
| `orjson 3.13.0` | possible | `MPL-2.0 AND (Apache-2.0 OR MIT)` (PyPI) | Allowed. |
| `numpy 2.5.4` | ADR-0004 | BSD-3 plus bundled MIT/0BSD/Zlib/CC0 (PyPI) | Fine. |
| `torch 2.14.1` | only if a local ML model is used | Apache-2.0/BSD/MIT/BSL-1.0 mix (PyPI) | Fine. Not in specs as a dependency. |
| **TikTokLive** (TikTok chat reading, reverse-engineered) | gateway (deferred) | `7.0.1`: "**Modified AGPL-3.0**", classifier "Other/Proprietary" (PyPI) | **Do not adopt** without legal review: AGPL-style terms plus an ToS-violating approach (PLATFORM-REALITY-CHECK §3). |
| `playwright` 1.64.0 / `@playwright/test` 1.64.1 | e2e | Apache-2.0 | Fine. |
| **milsymbol** | OVERLAY symbols | `3.0.4`: **MIT** (npm). Search excerpts agree. | Code license only; see §4.4 for the standards. |
| pixi.js 8.22.0 (optional, ADR-0005) | OVERLAY | MIT (npm) | Fine. |
| **FFmpeg** | CLIPS-REPLAY | Not read. FFmpeg is generally LGPL 2.1+ by default, with GPL when built with GPL components (e.g. libx264) **[UNVERIFIED primary; search returned nothing on it]**. | Running our own build/package on our host is "use". Distributing a binary needs license-matched compliance. Prefer not to ship FFmpeg binaries in images. |
| **OBS Studio**, **Aitum Vertical plugin** | broadcast | Not read. OBS is widely documented as GPL-2.0-or-later **[UNVERIFIED]**. | Used as an application, not linked. Plugin license **not found**. Windows host per ADR-0012. |
| **Chromium / Playwright browsers** | headless render | Not read. Chromium is largely BSD-style with many bundled third-party licenses **[UNVERIFIED]**. | Used as a tool. Bundled codecs (H.264/AAC) can carry patent-licensing questions when **distributing** a browser; not an issue when only running it **[UNVERIFIED general point]**. |
| **Docker Desktop** (Windows host, ADR-0012) | deploy | Docker's own materials (2021-era search excerpts) say Docker Desktop is free for personal use, education, non-commercial open source, and businesses with **fewer than 250 employees AND less than $10M revenue** **[UNVERIFIED, may have changed; current terms not read]**. | Likely free at this size. Re-read before monetization or an LLC. |
| **Fonts** (OFL) | OVERLAY | `@fontsource/ibm-plex-mono`, `share-tech-mono`, `jetbrains-mono`, `inter` 5.3.0: **OFL-1.1** (npm) | See §4.3. |

**GPL vs AGPL summary for this project.** (1) The only GPL items are the TTS stack (Piper, espeak-ng, phonemizer). (2) Nothing planned is AGPL except the reverse-engineered TikTok chat library, which should be avoided. (3) Because the TTS worker is only **run** on our host, a GPL (non-Affero) component creates no duty toward viewers of the stream. A duty appears the moment a binary, an image or the source containing it is **given to someone else**. (4) An AGPL component, if one were ever adopted and modified, would carry a source-offer duty to remote users of the modified service. (5) Q-LEGAL-1's "GPL only in separate server-side processes" is consistent with this, provided "separate" means a separate process and a separate, unpublished image.

## 3. Platform terms and policy sweep

> **Every row in this section is [UNVERIFIED].** No platform's own policy page could be opened (§0). The "Primary URL" is the page to read; "Seen" says what the only available route showed. All "read" dates: 2026-10-18.

### 3.1 Twitch

| Topic | What the excerpts say | Primary URL (to read) | Verification |
|---|---|---|---|
| Minimum age | Services not available under 13 (16 in Australia, or the local minimum if older); ages 13 to majority only under a parent's agreement; age by self-declaration | twitch.tv/p/en/legal/terms-of-service/ | **[UNVERIFIED]**, from aggregator pages (conductatlas.com, tostracker.app). |
| 24/7 and reruns | Reruns allowed if labelled (Rerun toggle plus "[Rerun]" in title/notification); one broadcast reportedly ends at 48 h; an "Always On" category exists; cheating drops/rewards is prohibited (2020 Valorant precedent). Music-only streams reportedly need a written exemption. No explicit ban on unattended interactive games was found. | help.twitch.tv (rerun and stream-length articles); twitch.tv/p/en/legal/community-guidelines/ | **[UNVERIFIED]**, from a streaming-host vendor blog and 2020 news. Our content is live game state, not a rerun, but replays/recaps should be labelled. |
| Bots and automation | Chat send limits (from the official docs excerpt): unverified bots 20 msgs/30 s and 1/s per channel; verified bots 7,500/30 s; exceeding means messages ignored for about an hour. Twitch sues and bans view/follow/chat-impersonation bots. A May 2026 item says new rules target tools that fake live viewer counts (unverified mirror). No rule against an open command bot was found. | dev.twitch.tv/docs/chat/; Developer Services Agreement | **[UNVERIFIED]**. |
| Developer agreement, data | Forum answers (not the agreement text) say: OAuth-authorized data may be stored beyond the 24 h figure in the agreement; users can ask for their data to be deleted; monetizing chat logs likely needs Twitch Legal approval. The "6 months" figure in the task brief **could not be confirmed**. | legal.twitch.com (Developer Services Agreement) | **[UNVERIFIED]**, community forum answers. |
| AI-content disclosure | No Twitch AI-disclosure rule found. A report says the CEO (Tokyo Game Show 2026) said none is needed yet. Separate item: in Aug 2026 Twitch added a "Training for Generative AI" channel setting, reportedly **on by default**, with an opt-out under Security and Privacy. | twitch.tv/p/en/legal/community-guidelines/ | **[UNVERIFIED]**, news sites. Owner action: check and set this toggle for the project channel. |
| Violence and mature content | Extreme violence/gore focus is banned; Twitch can ask a streamer to tone content down; game bans track ESRB Adults-Only and guideline violations. Nothing found about stylized war sims specifically. | twitch.tv/p/en/legal/community-guidelines/ | **[UNVERIFIED]**. Our sim is abstract C2-map symbology, which is the low-risk end. |
| Gambling-like | 2022 policy bans streaming unlicensed slots/roulette/dice sites and their referral links. Nothing found on channel points/predictions or loot boxes. Bits acceptable-use language (from ADR-0011): Bits are not a currency and may not be wagered. | twitch.tv (Bits Acceptable Use Policy) | **[UNVERIFIED]**. |

### 3.2 YouTube / Google

| Topic | What the excerpts say | Primary URL | Verification |
|---|---|---|---|
| API Services ToS + Developer Policies | Do not store user data indefinitely; users must have a clear deletion path; revocation via Google's security settings. The policy guide excerpt gives **30 days** to delete on user request or if authorization can't be verified. Secondary summaries say authorized data should be refreshed or deleted on a ~30-day cycle and non-authorized stats not kept longer than 30 days. | developers.google.com/youtube/terms/api-services-terms-of-service; …/developer-policies; …/developer-policies-guide | Excerpt of the official pages seen via search, partial: **[UNVERIFIED]**. |
| Quota and audit | Default 10,000 units/day; an increase needs a compliance audit; start with the "YouTube API Services Audit and Quota Extension Form"; periodic re-audits; appeals form exists. | developers.google.com/youtube/v3/guides/quota_and_compliance_audits | Excerpt of the official page: **[UNVERIFIED]** until read in full. Audit turnaround unknown. |
| Inauthentic content (YPP) | July 15, 2025: "repetitious" renamed "inauthentic" (mass-produced/templated). YouTube called it a clarification and said it does not specifically target AI. Nothing found about live streams. | support.google.com/youtube (YPP policies) | **[UNVERIFIED]**, news. Templated daily LLM-voiceover Shorts remain the exposure (PLATFORM-REALITY-CHECK). |
| Altered/synthetic disclosure | Required for realistic content a viewer could mistake for real (face/voice swap, altered real event). Generic TTS, AI scripts and thumbnails reportedly do not need a label. A 2026 "AI Use" field was reported but not confirmed. Live-stream-specific rules: **not found**. | support.google.com/youtube (altered or synthetic content) | **[UNVERIFIED]**. Our abstract map and a labelled TTS voice are unlikely to be "realistic", but add a plain on-stream "AI voice / AI Threat Director" note (already in Q-LEGAL-7/Q-BRAND-5 spirit). |
| Violence | Official page: content praising violent extremist/criminal organizations is not allowed, and modded games that glorify real violent events are listed. In-game violence ad-eligibility rules were reported updated (Nov 2022; a Nov 2025 item). Age-restriction criteria for game violence: **not found**. | support.google.com/youtube/answer/9229472 | Official page excerpt: **[UNVERIFIED]** for anything beyond the quoted part. The enemy faction must stay fictional (no real groups, flags or events). |
| Made for kids / COPPA | The setting is an audience declaration tied to COPPA "directed to children" factors (subject matter, visuals, animated characters, child-oriented activities, music, etc.), not a content rating. Made-for-kids limits live chat and live-chat donations (Dutch help page excerpt). A mislabelled channel can create COPPA exposure. | support.google.com/youtube/answer/9632097 | **[UNVERIFIED]**. A mature-toned military C2 game is plausibly "not made for kids", but the owner must make and record that setting decision. |

### 3.3 TikTok

| Topic | What the excerpts say | Primary URL | Verification |
|---|---|---|---|
| LIVE eligibility | Sources conflict: about 1,000 followers and 18+ for gifts; one says minimum age 16 to go live; LIVE Studio / stream key is gated with unpublished criteria; one blog says renewal needs recurring 25-minute streams **[treat as unverified]**. Nothing found on pre-recorded or unattended streams. | tiktok.com/live (Help Center / LIVE policies) | **[UNVERIFIED]**, marketing blogs. Consistent with PLATFORM-REALITY-CHECK: TikTok is optional/deferred. |
| Content Posting API | Official-docs excerpt: unaudited clients can only post **private**, all posting accounts must be private, up to 5 users per 24 h; an audit is required to lift it; creator caps and per-account daily caps apply for all clients. Docs show "updated Aug 4, 2026". | developers.tiktok.com/doc/content-sharing-guidelines | Excerpt of the official page: **[UNVERIFIED]** until read in full. |
| Developer ToS | **Not found** in this pass. | developers.tiktok.com/doc/tiktok-developer-terms-of-service | Gap. |
| Chat reading | No official API for LIVE chat (PLATFORM-REALITY-CHECK); `TikTokLive` is "Modified AGPL-3.0" on PyPI (§2.5). | n/a | Previously researched, **[UNVERIFIED]**. |

### 3.4 Instagram / Meta

| Topic | What the excerpts say | Primary URL | Verification |
|---|---|---|---|
| Content publishing | Official docs excerpt: 100 API-published posts per account per rolling 24 h (carousel counts as one), enforced at `media_publish`; the same docs also show "50" in one place, so check `GET /<IG_ID>/content_publishing_limit` live. | developers.facebook.com/documentation/instagram-platform/content-publishing | Excerpt: **[UNVERIFIED]**. |
| Automation | A secondary guide says Meta's Automated Data Collection Terms prohibit scrapers and bots without written permission; use official API paths with Business/Creator accounts. | facebook.com/legal/automated_data_collection_terms; developers.facebook.com/terms | **[UNVERIFIED]**. App review for Reels/publishing not covered. Instagram is a clip-distribution channel only; a human posting manually avoids the API question. |

### 3.5 Discord

| Topic | What the excerpts say | Primary URL | Verification |
|---|---|---|---|
| Verification | Bots in 100+ servers must be verified to keep joining servers; applying is possible from about 75; privileged intents (Message Content, Server Members, Presence) are self-serve below 100 servers and need approval above. Source is a **2020** Discord post, so dated. | discord.com/developers/docs/policies-and-agreements/developer-policy; support.discord.com (verification) | **[UNVERIFIED]**. Slash-command-only bots generally don't need Message Content. |
| Developer ToS / policy | Official text **not read**. Bot operators describe deletion-on-request as a Developer Policy duty. Whether AI training on Discord data is prohibited: **not confirmed**. | discord.com/developers/docs/policies-and-agreements/developer-terms-of-service | **[UNVERIFIED]**. |

### 3.6 Cross-cutting questions asked in the brief

| Question | Finding | Status |
|---|---|---|
| Unattended 24/7 | No explicit Twitch ban found; rerun labelling, the 48 h broadcast limit and drops-abuse rules exist. TikTok LIVE policy reportedly disfavors static/no-presenter streams (PLATFORM-REALITY-CHECK). YouTube has no found live-specific rule. | **[UNVERIFIED]**, owner must read the Twitch rerun/Always-On help articles. |
| Bots / automation | Open, openly-labelled command bots appear fine on Twitch within rate limits; fake-engagement bots are banned. Q-LEGAL-7 (simulator never on the public channel) is the right line. | **[UNVERIFIED]**. |
| AI-generated content disclosure | Twitch: none required found. YouTube: required for realistic synthetic media; generic TTS reportedly exempt. TikTok and Instagram: reportedly require labels for realistic AI media (one news item). Kick: strict disclosure update March 2026 (news item). | **[UNVERIFIED]**. |
| Children / age | Twitch 13+; COPPA applies to services **directed to** children or with **actual knowledge** of under-13 data. The amended FTC COPPA Rule: effective 2025-06-23, compliance date 2026-04-22; the FTC issued a Feb 25, 2026 policy statement about age-verification data for mixed-audience services (law-firm summaries, plus the Federal Register URL appeared in results). UK ICO Children's Code applies to services likely to be accessed by under-18s ("assume you are caught unless compelling evidence"). | **[UNVERIFIED]**, secondary summaries. See §5. |
| Gambling-like mechanics | ADR-0011 already forbids a stored currency. Twitch Bits wagering is banned per ADR-0011 research. Keep redemptions direct, capped, cosmetic, with no randomized paid outcomes or loot boxes. | **[UNVERIFIED]**; legal review needed before any currency (ADR-0011 already says so). |
| Military-themed / simulated violence | Nothing found that bans stylized war-sim content on Twitch/YouTube. Risk items are: real-world extremist groups, glorifying real events, gore, and ad-eligibility limits (YouTube, reported). | **[UNVERIFIED]**. |
| The word "war" in titles | **No rule found** against it. Two soft risks: auto-moderation and advertiser-suitability systems may be more cautious around war/violence keywords (**no evidence found, speculation**), and Q-BRAND-1's playful tone. Prefer titles that make clear it is a game ("co-op strategy game"). | No evidence either way. |

### 3.7 Summary: must / must not / owner decision

**Must do (all [UNVERIFIED] until the primary page is read):**
1. Label replays/recaps as reruns on Twitch and plan an automatic restart before the reported 48 h limit (OPS-ADMIN already marks this "[to verify]").
2. Keep bot sends within the 20/30 s limit (or make the bot a mod) and aggregate acknowledgements on the overlay.
3. Set the YouTube audience declaration deliberately and record the decision. Disclose AI voice and AI roles on stream.
4. Implement deletion-on-request and revocation handling for platform user data (Twitch and YouTube; YouTube's ~30-day figure is the one concrete number found).
5. For YouTube chat, apply for the audit/quota extension early; build against `streamList`.
6. Check and set Twitch's "Training for Generative AI" channel toggle.

**Must not:** use reverse-engineered chat libraries (TikTokLive); run the viewer simulator on a public channel (Q-LEGAL-7); introduce a stored in-game currency or randomized paid rewards (ADR-0011); use real extremist/terror group names or real-event imagery in the Static's lore; claim "made for kids".

**Owner decisions:** whether TikTok is in scope at all; YouTube "made for kids" answer; whether to apply for YouTube quota extension now; whether to keep "war" out of channel/stream titles; who reads the primary pages (this document cannot).

## 4. Music, asset and font licensing

### 4.1 Epidemic Sound

All points are from search excerpts and **[UNVERIFIED]** (epidemicsound.com and its help center could not be fetched; some excerpts quote help-center pages).

| Question | Finding |
|---|---|
| Live streams on Twitch/YouTube | Epidemic's pages say the catalog is licensed for live streams and VODs **while the subscription is active**, and that connecting/safelisting your channel keeps content you published during an active subscription cleared even after you cancel. Plans in the excerpts: a Creator plan (one channel per platform) and a Pro plan (three channels per platform, client work, digital ads). Names may have changed. |
| After the subscription lapses | The FAQ excerpt says content published while subscribed stays licensed, but you cannot publish **new** content with the music once it lapses, including tracks downloaded earlier. For an always-on stream, whether a continuing broadcast started during the subscription counts as "published" is **not answered** in any source found. |
| **Music-first / 24/7 radio-style use** | The help-center page "Can Epidemic Sound music be used for compilations or music listening content" (excerpt) says the music is for enhancing original productions, **not standalone listening experiences**, and use where visuals or narration are secondary is not permitted under any license; playlists and online radio are excluded. Another excerpt says Epidemic's own YouTube Content ID guidance tells creators to check the content "isn't published as a listening experience". A game stream with music underneath is *probably* not a listening experience, but a 24/7 loop where the game is a visual backdrop could be read that way (**my inference**). **Ask Epidemic support in writing.** |
| Content ID / claims | Help center (excerpt): a Content ID claim usually means the platform found the music but could not confirm the license; check the channel is safelisted and a subscription was active at publish; dispute within 5 days to keep ad revenue. Third parties report claims despite safelisting (anecdotal). A vendor blog says YouTube's Creator Music does not cover live streams in 2026 (**unverified, vendor**). |
| Channel limits | Safelisting is per channel; the project uses several (Twitch, YouTube, TikTok, Instagram), so the plan tier and channel count matter. |
| API / MCP | The Epidemic Sound MCP server (beta) exists and appeared in Claude's connector directory per a company press release dated 2026-08-31 (search excerpt). Searching is free; downloading/using needs a paid subscription. A broader "Partner API" is described as partnership-gated. Terms for AI-generated or automated selection **not found**. This answers the "does an MCP exist" half of Q-LEGAL-2. |
| Overtone Studios | Epidemic subsidiary label (round 1). Already avoids "Overtone" as an enemy name. |

**Recommended written questions to Epidemic Sound support:** (1) Is a 24/7 unattended game stream with music underneath covered on the owner's exact plan? (2) Does it count as "listening content" if the music is the only continuous element? (3) What happens to an in-progress broadcast and its VODs when the plan lapses? (4) How many channels, and does a fan-run copy (Discord screen share, clip re-uploads by viewers) trigger claims? (5) Is automated track selection through the MCP covered by the same terms?

### 4.2 Twitch music rules and Content ID risk

- Twitch uses DMCA takedowns, counter-notices and repeat-infringer termination (third-party summaries of Twitch's legal pages, **[UNVERIFIED]**). Audio recognition reportedly mutes VOD sections and may delete clips. A muted VOD is not a license.
- Live vs VOD vs clips may be treated separately, so licensed music must cover all three.
- "Soundtrack by Twitch" has been unavailable since July 2023 (excerpt).
- YouTube Content ID can claim a 24/7 stream in real time. A false claim on a live stream can mute or block it. Mitigation: only licensed or CC0 music, a **music cue sheet** (track, license, source URL, date) kept per stream, and a fallback "no-music" scene.

### 4.3 Free-use music, SFX and fonts

| Source | License | Notes | Status |
|---|---|---|---|
| Kenney.nl asset/audio packs | CC0 (excerpts: Kenney's support page says all packs are CC0; attribution optional) | Good for UI SFX. Kenney's own page was not fetched. | **[UNVERIFIED]** |
| OpenGameArt | Per item (CC0, CC-BY, CC-BY-SA, GPL…) | Check each item. | **[UNVERIFIED]** |
| Freesound | Per sound: CC0, CC-BY, CC-BY-NC | Avoid NC. CC-BY needs on-stream/site credit. | **[UNVERIFIED]** |
| Incompetech (Kevin MacLeod) | CC-BY (attribution) or a paid no-attribution license | Credit must be shown for a live stream; attribution plan needed. | **[UNVERIFIED]** |
| Free Music Archive | Per artist; some CC-BY-SA | Check per track. | **[UNVERIFIED]** |
| Pixabay Music | Not found | License terms for 24/7 or AI use **not read**. | Gap |
| Commissioned stems (Q-LEGAL-2) | Written license from the composer | Needs contract wording for streaming, VOD, clips, platforms, perpetuity, derivative edits (NX-319). | Plan |

Excerpt note: one source says major subscription libraries (Epidemic, Artlist, Soundstripe) **exclude internet radio broadcasting** from standard plans and need business tiers for 24/7 streams. It is consistent with §4.1 but is a single unreliable source.

**Fonts.** The planned fonts (IBM Plex Mono, Share Tech Mono, JetBrains Mono, Inter via Fontsource) all declare **OFL-1.1** in npm metadata (read today). From OFL FAQ mirrors (search excerpts, **[UNVERIFIED primary]**): bundling and redistribution with software are allowed, the font stays under the OFL with its license text and copyright notice, fonts may not be sold on their own, and modified versions must not reuse a Reserved Font Name. Practical rule: ship each font's license file next to it (also required by OV-9 "fonts are bundled, no remote fonts") and list it in the asset register. OBS browser sources: not covered in any result found (no reason to expect a difference, **not verified**).

### 4.4 milsymbol, MIL-STD-2525 and APP-6

- **milsymbol library:** `3.0.4`, **MIT** (npm). Draws SVG/Canvas symbols per MIL-STD-2525 B/C/D/E and APP-6 B/D/E (search excerpts). The MIT license covers the **code**.
- **MIL-STD-2525C and D:** the covers carry "Distribution A: Approved for public release; distribution is unlimited" (excerpt of the jcs.mil PDFs). DLA guidance says Distribution A documents may be made public. This suggests the standard's text is freely distributable in the US **[UNVERIFIED; the PDFs themselves were not read]**. A US government work is generally not subject to US copyright, but a standard may include third-party material; I have no source on that.
- **NATO APP-6:** a NATO publication. A *draft* edition (2015 Study Draft) says reproduction needs the publisher's prior permission except for member/partner nations and NATO bodies, and commercial sales are excluded from that exception. The final text was not read. A vendor page lists APP-6(D) as "approved for public release", which **conflicts** with the NATO draft language **[UNVERIFIED]**.
- **Interpretation (not advice):** Drawing fictional unit symbols with a library that implements the *geometry* is a different act from republishing the standard's text, tables or figures. Whether symbol shapes are themselves copyrightable is a legal question I have no source for. The safer practice: do not copy the standards' text or tables into the repo; reference them by name; keep using the library's output; and note in the legal doc that the in-world factions use fictional designations. Q-STYLE decisions about "shape-coded" generic symbols (OVERLAY) already lower the dependence on NATO-specific marks.
- **Attorney or NATO Standardization Office question:** is rendering APP-6 symbols in a monetized stream acceptable? Low priority.

## 5. Privacy and data law summary (research, not advice)

Planned data: platform user ids and display names (chat), commander/profile rows, OAuth tokens (owner/bot and, if used, viewer links), first-party analytics from own events (Q-DM-3), command logs, clips containing usernames, `!forget` deletion (SEC-DATA-3), retention (SEC-DATA-4: raw chat 7 days; command log campaign + 30 days; aggregates kept).

| Topic | Research findings | What the notice/ToS should cover |
|---|---|---|
| **GDPR / UK GDPR** | A pseudonymous username or platform id is generally still personal data ("pseudonymised data is still personal data"; secondary source, **[UNVERIFIED primary]**). The right to erasure (Art. 17) is not absolute; a community discussion argues freedom-of-expression exceptions may let messages stay while profiles must go (**not authority**). Anonymising after a period is a commonly discussed route, but what "erasure" means then is unclear (academic paper). Article 13 notice content was not retrieved; from general knowledge the notice names the controller and contact, purposes and lawful bases, recipients (platforms, hosting, LLM and TTS providers), transfers, retention, rights and complaint route **[UNVERIFIED, general]**. | Controller identity (Q-LEGAL-6: individual with a dedicated privacy address; PO box if an address is required); lawful basis per purpose (likely legitimate interest for game operation and abuse prevention, consent where Discord/OAuth linking is optional) **[attorney to decide]**; every processor; retention table matching SEC-DATA-4; how to use `!forget` and how to reach the contact; effect on leaderboards/recaps/clips already published (SEC-DATA-3 covers profiles and identities; **clips and aggregates containing names are a gap to specify**). |
| **EU/UK representative, transfers** | Not researched. A US-based individual serving EU/UK viewers may fall under GDPR's territorial scope (general knowledge, **[UNVERIFIED]**). | Attorney question. |
| **ePrivacy / cookies** | Q-DM-3 sets **no third-party trackers, cookies or analytics scripts**. Summaries of the CNIL audience-measurement exemption say strictly limited first-party analytics can be exempt from consent only under conditions (anonymous statistics, limited retention such as 25 months, no cross-site tracking); the CNIL page itself was not read and these are vendor summaries. Whether a **cookieless** first-party scheme needs any banner under the ePrivacy rules was not settled by any source found (the open question stated in the excerpt). | If the site sets **no** cookies/localStorage identifiers beyond strictly necessary ones, the notice should *say so* (Q-DM-3 already requires the statement), and a consent banner may be unnecessary; if the site stores a login/session cookie for the Discord/Twitch link, list it as strictly necessary **[attorney to confirm]**. Overlay in OBS is not a public web page. |
| **CCPA/CPRA (California)** | Thresholds (revenue, number of consumers, share of revenue from selling data) were not retrieved; a small hobby operation is likely under them **[UNVERIFIED, not researched]**. | Include a short "California" paragraph only after the attorney confirms. Never "sell" or "share" data (consistent with Q-DM-3). |
| **COPPA (US)** | The amended FTC COPPA Rule took effect 2025-06-23, with a general compliance date of 2026-04-22; the FTC reportedly signalled active enforcement; a Feb 25, 2026 policy statement limits enforcement for mixed-audience services collecting data solely for age verification under conditions (law-firm summaries and the Federal Register URL in search results). COPPA applies to operators of services **directed to children under 13** or with **actual knowledge** they collect children's data. Twitch and Discord set 13+ in their terms. A law-firm paper (search result) warns that game streamers can face COPPA exposure if a child discloses personal information on a stream with a child-directed audience. | State "13+ / not directed to children" in the ToS and notice; no collection beyond platform id/display name; a deletion path for a parent's request; do not run features that collect personal data (voice clips, free-text profiles) from unknown ages; record the YouTube audience decision (§3.2). |
| **UK Children's Code** | Applies to services *likely to be accessed* by under-18s; the ICO's stance is "assume you are caught unless compelling evidence"; ICO has game-developer guidance (2023). A live stream by itself may or may not be an "information society service" in scope; **not resolved**. | Do an age-appropriate-design check if the site or Discord adds interactive features for UK users **[attorney]**. |
| **Twitch API data** | See §3.1: store only what is needed, handle token revocation, deletion on request; do not monetize chat logs without approval (forum). | Handle `user.authorization.revoke`-style events and delete linked data on revocation (event naming from forum results, **[UNVERIFIED]**). |
| **YouTube API data** | See §3.2: ~30 days to honor a deletion request, periodic refresh of stored authorized data, users can revoke at Google's permissions page, a privacy policy is required. | Link Google's privacy policy and the revocation page in the notice (general practice for API clients **[UNVERIFIED]**). |
| **Discord data** | Developer policy text not read (§3.5). | Keep Discord ids only for the optional link flow (IDENTITY spec). |
| **Retention / `!forget`** | SEC-DATA-3 and SEC-DATA-4 exist. The brief's "30 days" for YouTube deletion matches SEC-DATA-3's 30-day window. | Document backups: how long deleted data survives in backups and replays; whether replays/clips keep names. |
| **Tokens** | OAuth tokens are credentials (SEC-SECRET rules in THREAT-MODEL); they belong in the notice only as "we store tokens you grant, encrypted, until you revoke". | n/a |

Needs an attorney: lawful-basis choices, EU/UK applicability and representative, the cookie/consent position, the COPPA/Children's Code posture, and CCPA thresholds.

## 6. Name sweep, round 4

> **Same limits as rounds 1–3.** Knockout search only. **No official trademark register could be queried** (USPTO, EUIPO/TMview, WIPO, UKIPO all unreachable, §0). Aggregators (Justia, gleanmark, trademarkdir, Trademarkia) show stale or partial data. **Handle and domain availability was not checked** (nothing reachable). All statuses are **[UNVERIFIED]**.

### 6.1 Hiveplex (deep check)

New or changed since round 3:

| Finding | Source (excerpt only) |
|---|---|
| **HIVE for downloadable game software is registered to Hive Games Limited (York, UK; a Minecraft server operator), with 4 marks on file; The Hive Limited and Hive Studios LLC also hold game-related marks; Com2uS's HIVE game-platform filings; Hive Media, Inc. has game-related marks.** The word **"Hive" at the front is therefore crowded in class 9/41 games**, independent of Plex. | [gleanmark: Hive Games Limited](https://gleanmark.com/owner/hivegameslimited), [Justia: Com2US](https://trademarks.justia.com/owners/com2us-corporation-2890425), [Justia: The Hive Limited](https://trademark.justia.com/owners/the-hive-limited-2915731), [Justia: Hive Studios LLC](https://trademarks.justia.com/owners/hive-studios-llc-5791015) |
| No HIVEPLEX record at USPTO/EUIPO/UKIPO found in aggregator results (single search; near-marks: HIVEMQ, HIVEFLOW, HIVEOPS). The registers themselves were not queried. | [gleanmark HIVEMQ](https://gleanmark.com/trademark/uspto-79197176) |
| **HIVEPLEX LTD** (UK company 13440983, incorporated 2021-06-07, registered office Godalming, active, online/mail-order retail per excerpt). Confirmed again by two search results; the Companies House page itself could not be opened. | [Companies House](https://find-and-update.company-information.service.gov.uk/company/13440983), [identeco](https://www.identeco.co.uk/search/company/13440983/HIVEPLEX_LTD) |
| hiveplex.com listed for sale at $2,495 on a broker page (as in round 3). No result for hiveplex.io/.gg/.tv or any live site. **No registrar check was possible.** | [dnbolt.com](https://dnbolt.com/hiveplex) |
| Google's "Hiveplex" (2010 beehives) still dominates search results. | [mv-voice.com](https://www.mv-voice.com/news/2010/09/23/googles-hiveplex-is-the-place-to-bee/) |
| **Plex, Inc.:** a trademark directory lists nine US filings (eight registered, one abandoned) across classes **42, 9, 41 and 38**, including PLEX, MEDIAVERSE and MASTER YOUR MEDIAVERSE; no class 28 filing shown. Plex Systems, Inc. (a different company) holds PLEX filings in class 9 enterprise software. | [trademarkdir: Plex, Inc.](https://trademarkdir.com/owner/plex-inc), [gleanmark: Plex Systems](https://gleanmark.com/owner/plexsystemsinc) |
| **Other "-plex" marks coexist in game-adjacent areas** per aggregator results: MINEPLEX (Mineplex Studios LLC, computer game software), PIXELPLEX, LEISURE PLEX, MERIPLEX (telecom/software). This weakly suggests PLEX compounds are not exclusive to Plex, Inc., but **registration is not the same as tolerated use, and no enforcement history was found either way**. | [Justia: Mineplex Studios](https://trademark.justia.com/owners/mineplex-studios-llc-5664162), [Justia: PIXELPLEX](https://trademarks.justia.com/861/36/pixelplex-86136459.html), [gleanmark: MERIPLEX](https://gleanmark.com/trademark/uspto-76355637) |
| No game, Twitch, YouTube, Discord, Reddit or GitHub hit for "Hiveplex" or "Hive Plex" (three searches today). | searches below |

Queries (2026-10-18): `"Hiveplex"` (extended); `HIVEPLEX trademark USPTO OR EUIPO OR UKIPO application`; `"Hive Plex" OR "HivePlex" game OR studio OR app OR channel OR server`; `hiveplex.com OR hiveplex.io OR hiveplex.gg OR hiveplex.tv domain registered website`; `Plex Inc trademark PLEX class 41 class 9 class 28 registrations opposition "PLEX" suffix compound marks TTAB`.

**Assessment (unchanged: medium), with one added reason.** Round 3 named the "plex" suffix as the main risk. Round 4 adds that the **"Hive-" prefix is itself crowded in games** (HIVE class 9 registered for game software). Together, "Hive"+"plex" is a composite of two marks that belong to others in related goods. That does not mean a conflict, because overall impression and the register comparison decide, but it is exactly the question for an attorney. Practical items stay: one word, lowercase handle, TTS test.

### 6.2 In-game names

| Name | Re-check result today | Round 1–3 risk | Change |
|---|---|---|---|
| **the Quorum** (players) | Searches for "the Quorum faction" found no game faction by that name. Many QUORUM software marks exist (QuorumLabs, Quorum Software Systems, others; class 9 software). | Low as in-world label; High as brand | None. Keep it out of the external brand. |
| **Quorum Marshal**, **Quorum Control** | No game, software product or mark by those exact phrases found. Results were generic QUORUM marks only. | not checked before | Low as in-game titles. "Quorum Control" reads like software/telecom product naming, so avoid it as a public product label. |
| **the Static** (enemy) | No 2026 game with a faction "The Static" found. Earlier exact-title games remain (aFonte Games, Pol Clarissou; round 1). | Low (faction) / Medium (title) | None. |
| **NULL** | No new finding (generic word). | Low legal / Medium practical (`null` literal) | None. |
| **Hum** | No search run this round beyond rounds 1–3; generic word. | Low | None. |
| **Drone / Swarm Lead / Hive Commander** | "Hive Commander" is a Factorio mod by Deablo (MIT, ~11 downloads) and "Drone Commander" appears as a rank in *Drone Armada*. No mark found. These are generic rank titles. | not checked before | Low. "Hive Commander" has a tiny namesake; fine for an in-game rank, avoid as a product name. |
| **Operation Nexus** (internal codename) | A 2026-dated search found nothing new called "Operation Nexus". Many NEXUS companies exist (NEXUS Korean blockchain/game company, which rebranded its ecosystem to "ONE" in 2026 per an excerpt; Nexus Mods; Nexus: The Jupiter Incident sequel crowdfunding). | Medium | None. Fine as an internal codename. |

### 6.3 Alternative blended names (one quick clash search each)

All searched 2026-10-18. A result of "nothing found" does **not** mean clear. TTS and spelling comments are my own judgment, not tested.

| Candidate | Quick search result | Notes |
|---|---|---|
| **Hivemesh** | No exact game/app/company/mark found. Results are all "Hive" brands (HIVE game marks again). | Easy to spell and say. Inherits the crowded "Hive" prefix. |
| **Nodehive** | No exact match. Near: Neonhive Games (Glasgow publisher), Node.Hack (2012 game), Node App Inc. | "Node-hive" reads cleanly. Neonhive is one letter set away and in games. |
| **Swarmwire** | No exact match. Near: Swarm (Foursquare), AppSwarm, Swarmio Media (CSE: SWRM; gaming/esports SaaS). | "Swarm" noise (known from round 3). Also close to "Hivewire", which the owner rejected. |
| **Meshplex** | No exact match. Near: MERIPLEX, MINEPLEX (game software mark). | Keeps the "-plex" suffix, so the Plex question stays, with no "Hive" prefix. |
| **Hivelink** | No exact match. Only "Hive" brands. | Generic-sounding, likely weak but also likely available in some classes. |
| **Hivegrid** | No exact match. Only the Hive board game and notation pages. | Smooth, but "Hive" again. |
| **Wirehive** | No exact match. Near: Hive Networks (open-source mesh project, "Hivewares"), Meshmerize "Hive" tool. | Reverse of the rejected Hivewire; likely similar impression. |
| **Crowdmesh** | No exact match. Near: **CROWD.GAME** mark (Crowd.Game LLC, online multiplayer interactive video games, filed 2016). | The Crowd.Game filing is in the same field (class 41/9 multiplayer games), so **medium**. |

Summary: none of these 8 turned up a direct hit, but the aggregators and search index are weak for coined words. Only Swarmwire and Crowdmesh avoid both "Hive-" and "-plex", and each has its own caveat above (Swarm noise and closeness to the rejected Hivewire; the CROWD.GAME mark). A fresh brainstorm that avoids `hive`, `plex`, `swarm`, `nexus` and `quorum` may be worth doing.

### 6.4 Manual check checklist for the owner

**Registers** (the official sites were not reachable from here):
- [ ] **USPTO Trademark Search** (tmsearch.uspto.gov): exact strings `HIVEPLEX`, `HIVE PLEX`, `HIVEPLEXX`, `HIVE*PLEX` (wildcard), then `PLEX` alone, then `HIVE` alone filtered to classes below. For each live record open TSDR for status, owner, goods and any 2(d) citations.
- [ ] **EUIPO eSearch plus TMview** (tmdn.org/tmview): same strings. **WIPO Global Brand Database**: same strings (includes Madrid designations). **UKIPO** (gov.uk "Search for a trade mark"): same strings, plus **Companies House** check of HIVEPLEX LTD (13440983) for status and SIC code.
- [ ] Re-check the specific records already cited: PLEX reg. 4521387; CLEARWAVE reg. 8113483 and UK00908116741 (only if Clearwave remains anywhere); HIVEMQ, and the HIVE record(s) of Hive Games Limited for game goods.
- [ ] **Nice classes to filter.** Class wording below is from general knowledge and is **[UNVERIFIED]**, to be replaced with the official class headings (WIPO/EUIPO Nice pages) when reachable: **9** (downloadable software and games), **28** (games and playthings, for any board/card spin-off), **35** (advertising, business/commercial services, relevant to merch/online store), **38** (telecommunications, relevant to streaming/chat services), **41** (education, entertainment, online non-downloadable games, streaming shows), **42** (software as a service and software design). Add **25** if apparel merch is planned.
- [ ] Search terms for owner-side common-law use: `"hiveplex"` in Google, Bing, Steam, itch.io, Epic, App Store, Google Play, Roblox, Xbox, PlayStation, Nintendo eShop.
- [ ] Attorney question list: PLEX (Plex, Inc.) and HIVE (Hive Games Limited) vs a composite HIVEPLEX in classes 9/41/42; HIVEPLEX LTD in the UK; whether coexistence consent is realistic.

**Handles and domains** (none verified; claim or visit while logged in, record result and date):
- [ ] Twitch `twitch.tv/<name>`; YouTube `@<name>`; TikTok `@<name>`; Instagram; X; Bluesky (`<name>.bsky.social`); Discord vanity URL; Reddit `r/<name>`; GitHub org (note Q-LEGAL-8: owned by saltyseraphcodes); Mastodon/Threads if desired.
- [ ] Domains: `.com`, `.gg`, `.tv`, `.live`, `.io`, `.app`, `.xyz`; note premium, parked and for-sale pages. hiveplex.com was seen listed at $2,495 (broker, unverified). Check WHOIS/RDAP at a registrar. Also check lookalikes: `hive-plex`, `hiveplexx`, `hiveplex-game`.
- [ ] Record the date, result and screenshot. Typosquat and impersonation check: reserve the obvious misspellings on the main platforms.
- [ ] TTS test: say the name through the chosen voice; have three people type it from audio.

## 7. Summary

### 7.1 Prioritized risks

| # | Severity | Risk | Evidence | Recommended action | Who acts |
|---|---|---|---|---|---|
| 1 | **High** | **Brand choice (Hiveplex) not cleared** against PLEX (classes 9/41/42) and HIVE (class 9 games), plus HIVEPLEX LTD in the UK | §6.1: Plex, Inc. filings in 42/9/41/38; HIVE registered for game software; UK company; all from aggregators | Run the manual register checks (§6.4) before any spend on domains, merch, art with the name; get an attorney opinion; keep "Operation Nexus" as codename only | Owner, then attorney |
| 2 | **High** | **24/7 music licensing**: Epidemic Sound may exclude "listening experience" use; unclear what happens on lapse; Content ID on live streams | §4.1 excerpts | Ask Epidemic support the five written questions; meanwhile prefer CC0/commissioned music and keep a cue sheet and no-music fallback scene | Owner (support request), agent (cue sheet, scene) |
| 3 | **High** | **Platform terms not read from primary sources**; every platform rule here is unverified | §0, §3 | Owner or agent with browser access reads: Twitch ToS, Community Guidelines, Developer Services Agreement, rerun/24-7 help; YouTube API ToS/Developer Policies, YPP and synthetic-content pages; Discord Developer Policy | Owner (or a session with fetch access) |
| 4 | **Medium** | **GPL TTS stack (Piper, espeak-ng, phonemizer)** could taint the repo or a pushed image | §2.5 | Keep as an unpublished host-only install in a separate process; create `docs/legal/THIRD-PARTY.md`; never commit or publish an image with it; record voice-model licenses | Agent (docs/CI), owner (confirm no public image) |
| 5 | **Medium** | **Copyright holder "cant"** mismatches the planned identity; fresh-start repo imminent | §1.1 | Decide holder string before the clean import commit; add `TRADEMARKS.md`, `assets/LICENSE`, README note | Owner decides, agent edits |
| 6 | **Medium** | **Children / COPPA / "made for kids"** posture undefined | §3.2, §5 | Record 13+ and not-directed-to-children; set YouTube audience; notice wording | Owner, attorney |
| 7 | **Medium** | **Privacy notice, cookie position and `!forget` scope** (clips and aggregates containing names) not specified | §5 | Specify clip/aggregate handling in SEC-DATA; draft notice; attorney review of lawful basis and cookie stance | Agent drafts, owner/attorney review |
| 8 | **Medium** | **Twitch "Training for Generative AI" setting on by default** (reported) | §3.1 | Check the toggle on the project channel | Owner |
| 9 | **Medium** | **YouTube chat quota and audit** needed for live play (carried from PLATFORM-REALITY-CHECK) | §3.2 | Apply for audit early; build on `streamList` | Owner/agent |
| 10 | **Low-Med** | **Allowlist gaps**: PSF-2.0, BlueOak-1.0.0, LGPL (psycopg if chosen); `mypy-extensions` license unread | §2.4 | Amend Q-LEGAL-1 or record exceptions; add a license scan to CI | Owner decides, agent implements |
| 11 | **Low-Med** | **APP-6 reproduction terms** unclear; MIL-STD-2525 appears public-release | §4.4 | Do not copy standards' text; use library output; low-priority attorney/NSO question | Owner (low) |
| 12 | **Low** | **TikTok** reverse-engineered chat libs (Modified AGPL-3.0) | §2.5 | Do not adopt; keep TikTok out of scope | Owner |
| 13 | **Low** | **DCO/CLA** undecided before outside contributors | §1.4 | Choose DCO (if MIT stays) or CLA (if relicensing is wanted); adjust commit-message checker | Owner |

### 7.2 Decisions needed from the owner

1. **Hiveplex:** proceed to manual register and handle checks now, or choose another direction? If proceeding, commit to an attorney opinion before paying for domains or art.
2. **Copyright holder name** for LICENSE (individual name, pen name, or future LLC) before the Q-LEGAL-8 fresh-start import.
3. **Brand/art carve-out method:** explicit `assets/LICENSE` + `TRADEMARKS.md` in the repo, or keep brand art out of the public repo.
4. **Contributions:** DCO or CLA (and whether commits may carry `Signed-off-by`).
5. **Allowlist:** add PSF-2.0 and BlueOak-1.0.0; stance on LGPL (psycopg) and whether to add a CI license scan.
6. **Music:** send the written questions to Epidemic Sound, or move the 24/7 stream to CC0/commissioned music only.
7. **TikTok and Instagram:** in or out of scope for the first launch.
8. **YouTube "made for kids"** answer and the on-stream AI-disclosure wording.
9. **Twitch AI-training toggle** and who reads the primary platform pages (this document could not).
10. **Attorney engagement** for: HIVEPLEX vs PLEX/HIVE, privacy notice and cookie position, COPPA/Children's Code, GPL/linking comfort for the TTS stack, and APP-6 use.

### 7.3 Gaps (honest list)

- No trademark register queried; every trademark statement is aggregator or search-excerpt based.
- No platform policy page read in full; every platform rule is [UNVERIFIED].
- No handle or domain availability verified.
- Upstream LICENSE files not read (package-index metadata only). `mypy-extensions`, `espeakng-loader`, `kokoro-onnx` have no declared license in PyPI metadata. FFmpeg, OBS, Chromium, Aitum plugin licenses were not read.
- Nice class headings not read from an official page.
- Twitch Developer Services Agreement text, TikTok Developer ToS, Discord Developer Policy and Meta Platform Terms not read.
- Piper voice-model licenses and Kokoro training-data provenance not found.
- GDPR Article 13 content, CCPA thresholds and EU/UK representative rules were not retrieved from primary text.
