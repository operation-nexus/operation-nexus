# Reddit and Discord rules: primary-source read (NX-344)

Date: 2026-10-19 · Status: partial · Tracker: NX-344 · Related: [PLATFORM-POLICY-VERIFICATION-2026-10-18](PLATFORM-POLICY-VERIFICATION-2026-10-18.md), Q-MKT-15

Method: each page was fetched from this cloud environment on 2026-10-19, converted to text, and searched for the terms below; the quoted lines are copied from that text. Pages that returned HTTP 403 or no content were **not** read and are listed in §4. Nothing in this report is legal advice.

## 1. What was read

| Source | URL | Result |
|---|---|---|
| Reddit Content Policy | https://www.redditinc.com/policies/content-policy | Read (eight rules and the enforcement list) |
| Reddit Data API Terms | https://www.redditinc.com/policies/data-api-terms | Read in full (sections 2, 3, 6 and 7 used below) |
| Discord Community Guidelines | https://discord.com/guidelines | Read (rules 13 to 17 used below; page date not checked) |

## 2. Reddit

Quoted lines (Content Policy):
- Rule 2: "Abide by community rules. Participate authentically in communities where you have a personal interest, and do not spam or engage in disruptive behaviors (including content manipulation) that interfere with Reddit communities."
- Rule 5: "Be authentic. You don't have to use your real name, but do not intentionally mislead others or impersonate an individual or entity in a deceptive manner."
- Rule 6: "Ensure people have predictable experiences on Reddit by properly labeling content and communities, particularly content that is graphic, sexually-explicit, or offensive."
- Enforcement ranges from "Asking you nicely to knock it off" through removal of content to suspension of accounts and bans of communities.

Quoted lines (Data API Terms), relevant only if a tool reads Reddit through its API:
- 2.8: "You must use the Access Info we provided you (e.g., the OAuth token) when accessing the Data APIs, and you will not misrepresent or mask either the user agent or OAuth identity when using the Data APIs."
- 2.9: Reddit "may set and enforce limits on your use of the Data APIs".
- 3.1: "If you are interested in using the Data APIs for commercial purposes, research in excess of rate limits, or for any use that is not expressly permitted under the Data API Terms, then you will need to enter into a separate agreement with Reddit."
- 3.2 forbids using the APIs to train "a machine learning or AI model without the express permission of rightsholders", to "spam, incentivize, or harass users", and to keep content "beyond your approved use case", which must be deleted.
- 2.6 requires a privacy policy disclosing how data is collected, used and shared.
- Section 6 (termination): stop using the APIs and delete cached or stored User Content, including "data or models that were derived from" it.

What this means for us:
- **Posting devlogs by hand is a community-rules question, not a site-wide one.** The Content Policy only says to follow each community's rules and to participate authentically. Each subreddit's own rules (self-promotion limits, flair, required formats) were **not read** and must be read per subreddit before any post. The vault's `social-post-draft` skill already carries that note.
- **Do not disguise promotion.** Rules 2 and 5 support posting as the clearly labelled project account and joining the conversation, not dropping links.
- **Brand Ops reading Reddit through the API** (not planned today; Reddit stays manual, Q-MKT-5) would need: its own registered app and an honest user agent, a privacy policy (already on the P3 path, NX-316), no AI training on the content, and deletion when told to. Whether the project counts as "commercial" under 3.1 (supporters, Q-SUP) is a legal question for the narrow attorney consult; treat as [UNVERIFIED].
- The "10 percent self-promotion" folk rule was **not found** in what was read. Do not cite it.

## 3. Discord

Quoted lines (Community Guidelines):
- 13: "Do not send unsolicited bulk messages (or spam) to others."
- 14: "Do not use self-bots or user-bots. Each account must be associated with a human, not a bot."
- 15: "Do not engage with our service in an inauthentic way. This includes artificially inflating server membership, manipulating engagement metrics, and selling artificial engagement services."
- The guidelines point bot and app developers to the Developer Terms of Service and the Developer Policy, and to the Monetization Policy if monetizing.

What this means for us:
- **Real bots are allowed as bots** under their own application (the plan in BRAND-OPS: its own Discord app and token). Running them from a normal user account is not (14).
- **Announcements to our own server are fine; unsolicited mass DMs are not** (13). This matches the Brand Ops rule of never sending DMs automatically.
- **No fake growth** (15): no bought members, no engagement tricks.
- The requirements for bots themselves (message content access, rate limits, data handling, AI use) live in the Developer Policy and Terms, which were **not read** (HTTP 403).

## 4. Not read, and why

| Page | Why it matters | Status |
|---|---|---|
| Reddiquette and Reddit's "Rules for communities" help articles (support.reddithelp.com) | the platform's own wording on self-promotion and spam | HTTP 403 |
| Reddit "What is spam" help article | spam definition | HTTP 403 |
| Reddit wiki page on self-promotion | folk 10 percent rule | no content returned |
| Discord Developer Policy and Developer Terms of Service (discord.com/developers/docs/policies-and-agreements) | the actual bot rules | HTTP 403 |
| Discord help article on automated accounts | bot vs self-bot detail | HTTP 403 |
| Any individual subreddit's rules or Discord server's rules | the rules that actually decide a post | not applicable until a target is chosen |

To finish NX-344, either the owner reads those pages in a browser and records what they say (or sends the text), or the cloud environment's network allowlist gets those hosts (Q-PROC-3). Until then Reddit and Discord self-promotion and bot-specific rules stay [UNVERIFIED].

## 5. Recommended changes (not made here)
- Keep the `[UNVERIFIED: check community self-promotion rules before posting]` note on every Reddit and Discord draft. It stays correct even after this read, because each subreddit has its own rules.
- Add "subreddit rules read on <date>" to the Reddit draft checklist in the vault when the first Reddit post is planned.
