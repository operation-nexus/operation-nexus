# Marketing and Production Research

> Verification status (2026-10-18): corrected against primary sources in [PLATFORM-POLICY-VERIFICATION-2026-10-18](PLATFORM-POLICY-VERIFICATION-2026-10-18.md) and [LICENSE-AND-MUSIC-VERIFICATION-2026-10-18](LICENSE-AND-MUSIC-VERIFICATION-2026-10-18.md). Inline [CORRECTED 2026-10-18] notes mark changed claims; [VERIFIED 2026-10-18] marks confirmed ones.

Date: 2026-10-18 · Author: research agent · Status: Draft for owner review · Inputs: MARKETING.md, VISION.md, ROADMAP.md, PLATFORM-REALITY-CHECK.md, EPIDEMIC-SOUND-RESEARCH.md, GEMINI-TTS-VOICE-DESIGN-RESEARCH.md, CLIPS-REPLAY, AUDIO-TTS, OVERLAY, OPEN-QUESTIONS (Q-MKT-*, Q-BRAND-*, Q-TEST-3, Q-LEGAL-7, Q-AI-6, Q-DM-3).

## 0. How to read this document (evidence rules)

- **Research limit, stated up front:** in this research environment `WebFetch` and direct `curl` could not reach any external host (DNS failure and proxy 403). Everything below therefore comes from **web-search result summaries**, not from reading full pages. No page was read end to end. That includes official platform pages.
- Evidence tags used in this file:
  - **[EXCERPT-OFFICIAL]** the search summary quoted or described an official platform or developer page. Re-read the live page before it drives a decision.
  - **[UNVERIFIED]** secondary source only (news, vendor blog, creator blog). Do not treat as fact.
  - **[NO DATA]** no credible number was found. We do not invent one.
  - **[OWNER DECISION]** already decided in OPEN-QUESTIONS.
  - **[ESTIMATE]** my own planning estimate, not a measurement.
- Rule 0 (AGENTS.md) applies: no viewer counts, conversion rates or benchmarks are given unless a source is cited. Several sources below conflict with each other; conflicts are shown, not smoothed over.
- Rule 11b (one writer per file): this is a new file with one writer. No other file was edited. TRACKER and OPEN-QUESTIONS changes in section 7 are **proposals** for the owner.

---

## 1. Gap analysis: current marketing plan vs what a live-service stream-game launch needs

### 1.1 What MARKETING.md already covers (do not redo)
| Area | Where | State |
|---|---|---|
| Principles: high quality, low owner effort, AI transparency | MARKETING Principles, Q-AI-6 | Decided |
| Four channels: devlogs, short-form, Reddit/strategy communities, Discord | MARKETING Channels, Q-MKT-1 | Decided |
| Devlog checkpoint mechanism and `devlog-footage` auto-capture | MARKETING, AGENTS 11a | Decided, not yet built |
| Timing: start early and imperfect, free only, hold the old-Discord announcement, label simulated battles | Q-MKT-3 | Decided |
| Cadence target: devlog every 2-4 weeks, 2-3 shorts/week, scheduled post queue | Q-MKT-4 | Decided as a flexible target |
| Clean-break accounts (Twitch, YouTube, TikTok, Instagram) | Q-MKT-2 | Decided |
| Clip pipeline with human review queue, no templated auto-narrated Shorts | CLIPS-REPLAY §4 | Spec Draft |
| Cold-tester recruitment (5-10 private invites) | Q-TEST-3 | Decided |
| First-party-only analytics | Q-DM-3 | Decided |
| No viewer simulator on the public channel | Q-LEGAL-7 | Decided |
| Placeholder-art disclosure and release gate | Q-BRAND-5 | Decided |

### 1.2 What a live-service stream-game launch needs that is missing or thin
Each item is marked **Missing** (nothing in docs), **Thin** (a mention but no plan), or **Blocked** (depends on an open decision).

1. **Positioning and one-line pitch. Thin / Blocked.** VISION has a one-sentence description. The taglines are known from Q-BRAND-6 ('Many minds. One front.', 'The crowd is the commander.', 'Join the Quorum.'), but:
   - 'Join the Quorum.' is **reserved for community-engagement copy**, and 'Quorum' is **never the external brand** (Q-BRAND-7; name research rated it high risk). So the pitch for strangers must lead with another line.
   - The public name itself is still a working title (Q-BRAND-6). MARKETING says "grab handles now" (Q-MKT-3). Handles claimed before the name settles may be wasted. **Decision needed** (see §7.2).
   - Missing: a written 1-line, 3-line and 30-second pitch; a "what is this?" answer that a stranger understands in 5 seconds (matches Vision pillar 1).
2. **Audience segments. Thin.** VISION lists mil-sim/strategy fans, casual lurkers and the devlog audience. Missing: what each segment wants, where they are (platform/community), and what they see first. Suggested segments are in §6.1. All are hypotheses, no audience data exists.
3. **Community guidelines and moderation policy. Thin.** The conduct system exists in ADMIN-RBAC §6.8 (decaying score, escalation ladder, appeals, `!rules`), and NX-276/NX-314 track "community rules". Missing: the human-readable Code of Conduct, the Discord rules, the on-stream chat rules, who moderates, and how Discord/Twitch rules map to the in-game ladder. See §5.
4. **Press and creator kit. Missing.** No fact sheet, screenshot set, logo files, brand colors, short description, content notes, contact address, or "how to feature us on stream" page. Generic indie press-kit guidance converges on: fact sheet, descriptions, screenshots, trailer, logos, team info, contact **[UNVERIFIED, vendor blogs, e.g. presskit.gg, wayline.io, gtstu.com]**. A creator kit should also include the colour hex codes and font names so thumbnail makers can match the brand **[UNVERIFIED, same sources]**. The kit should exist before the first Reddit post **[UNVERIFIED, presskit.gg]**.
5. **Trailer and key art. Missing, and constrained.** Q-BRAND-5 forbids AI-generated art at release and allows it only as marked PLACEHOLDER in alpha. A trailer or key art made before real art exists must carry the placeholder disclosure and cannot be reused at release without replacement. Indie-marketing advice says a trailer should show real gameplay from the first seconds, not CGI **[UNVERIFIED, secondhand summary of Chris Zukowski via Unity and Game World Observer]**. Our natural trailer is a replay render (CLIPS-REPLAY), which is real footage.
6. **Stream scheduling and art for an "always on" channel. Missing.** A 24/7 channel has no "going live" moment. Needs: a weekly "event slot" schedule (see Q-MKT-4 reconciliation in §3.6), channel-page schedule, offline/intermission screens (the War Briefing card exists, NX-296), channel panels (including the "Synthetic voices" note, Q-AI-6), title/category/tag conventions, emotes and badges.
7. **Discoverability on Twitch and YouTube for 24/7 games. Missing.** See §3.
8. **Collaboration with small streamers and raids. Missing.** Q-TEST-3 mentions "small streamers" as a tester source, but there is no outreach plan, no "how to host Nexus on your stream" page, no raid etiquette. See §5.6 and §6.
9. **Playtest recruitment. Decided but not operational.** Q-TEST-3 gives the mix, not the sourcing channels, message templates, consent forms for recording the first 5 minutes, or the survey (max 3 questions). Marked "playtesting community after checking its rules [UNVERIFIED]".
10. **Analytics and KPIs from own events only. Decided, KPIs undefined.** Q-DM-3 says D7, session length etc. come from sim/gateway events keyed by `commander_id`. VISION gives beta targets (median session >= 12 min, >= 20% issue a command, D7 >= 15%). Missing: **marketing** KPIs that are measurable without third-party trackers (e.g. `!join` rate per stream session, first-command rate by referral source). Referral attribution is hard without trackers; proposal in §6.6 uses a self-declared "how did you find us" `!join` prompt or a launch-week code, never cookies. Platform dashboards may be viewed but not imported (Q-DM-3).
11. **Crisis plan if something offensive slips through. Missing.** VISION has "zero moderation incidents on stream", and the ingestion pipeline moderates everything, but there is no playbook for the day it fails: who pulls the stream, how to clip-and-delete, what to say publicly, how to report to the platform. Skeleton in §5.7.
12. **Press/community cadence tied to ROADMAP gates. Thin.** ROADMAP gate 1 requires a recorded demo, which is the minimum devlog. Missing: a calendar mapping each gate to concrete posts. See §4.5 and §6.
13. **AI-transparency copy bank. Thin.** Q-AI-6 and Q-BRAND-5 decide the policy. Missing: exact wording for the channel panel, video descriptions, Discord, README, and the "artists wanted" notice. See §4.8.
14. **Accessibility and captions in published content. Missing.** See §4.7.
15. **Budget/opportunity register. Missing.** Free-only is decided; there is no "if we ever spend, spend on X" list. §6.7 gives a sourced-only version.

---

## 2. Comparable projects and what they teach

**Caveat for the whole section:** only search-result summaries were read. No official post-mortems for the commercial examples were found. Viewer numbers are given **only** where a source states them, with the source and its conflicts.

### 2.1 Twitch Plays Pokemon (2014): the origin of the format
- **What it is:** an anonymous developer built a bot that let Twitch chat control a Pokemon Red game via typed commands. Reported by Nintendo Life as an experiment to test how people interact with an input system and with each other **[UNVERIFIED, secondary]**.
- **Numbers (conflicting, all secondary):**
  - Game Informer, reporting Twitch's own figures, gave a total of more than nine million viewers and a peak of 121,000 concurrent viewers, about 30 viewers on day 1 and about 4,000 by mid-day 2 **[UNVERIFIED]**. Same page: "36 million total views" appears in Game Informer and PCR, while another source says "26 million+" **[conflict]**.
  - Wikipedia (via search summary): average over 80,000 concurrent viewers, peak 121,000 simultaneous participants, an estimate of 1.16 million participants; another outlet cites about 658,000 participants **[conflict, UNVERIFIED]**.
  - Completion reported after about 16 days **[UNVERIFIED]**.
- **What worked:**
  - Participation as the hook: anyone's typed command moves the game, and "interactivity, plus memes, drove its spread" **[UNVERIFIED, Game Informer summary]**.
  - Community self-organisation: players used Reddit to share strategies that others largely followed **[UNVERIFIED, search summary of press/academic coverage]**.
  - Tension between helpers and trolls is credited as an engagement driver **[UNVERIFIED, one journalistic piece]**.
  - Forgiving game rules: a commentator argued that Pokemon's fainting rules (return to checkpoint with XP intact) made crowd play survivable **[UNVERIFIED, PC Gamer coverage as summarised]**.
- **What failed or was costly:**
  - Pure anarchy stalled on precision sections; "Democracy" mode (vote tally) was added. Reported vote windows differ by source (roughly 5 s to 30 s) **[conflict]**. Switching between modes needed a 75% majority to go to democracy and 50% to return, so the default stuck; most of the run happened in anarchy **[UNVERIFIED, BioMed Central / press summaries]**.
  - The mode vote split the crowd into two communities and some members stopped voting rather than change publicly **[UNVERIFIED, BioMed Central blog summary of an academic study]**.
  - Democracy was slower than anarchy **[UNVERIFIED]**.
  - The scale strained Twitch chat; Twitch moved it to a dedicated chat server (MCV, summarised) **[UNVERIFIED]**.
- **How it grew:** within days via Reddit and press, on a novelty that needed no explanation. It then spawned many "Twitch Plays" channels and a dedicated "Twitch Plays" directory on Twitch (GameSpot, summarised) **[UNVERIFIED]**.
- **Lesson for Nexus:** novelty alone was enough in 2014 because the format was new. It is not new now. Our differentiators are persistence, roles, logistics and readable war-room visuals. Note the design lesson: mode and rule changes that split the community are costly; Nexus avoids the anarchy/democracy dilemma by giving each viewer their own unit and the Tasking Board.

### 2.2 Choice Chamber (2015): chat vs streamer, built for Twitch
- **What it is:** a roguelike where Twitch chat votes to help or hinder the streamer (Studio Bean). Coverage from the 2015 Kickstarter and launch (Tubefilter, GamesBeat, Austin Chronicle, PC Gamer) **[UNVERIFIED]**.
- **What worked:** developer streamed work in progress to learn what worked; Twitch helped with funding visibility; chaos as a feature **[UNVERIFIED]**.
- **Design lesson:** chat count is not player count; the game polls participants to learn how many are active, and was planned to scale difficulty with crowd size ("if you have, say, a thousand people, you might have a special boss") **[UNVERIFIED]**. This mirrors our crowd-profile balance runs (0/5/50/150/300 simulated viewers, ROADMAP P1).
- **Gap:** no retention numbers or post-mortem found **[NO DATA]**.

### 2.3 Stream Raiders (Captain.tv): viewers as an army on a streamer's channel
- **What it is:** a browser game linked to Twitch where the streamer is the "Captain" and viewers place units on a battlefield; progression through campaign maps, rewards and unit unlocks **[UNVERIFIED, Chrome Web Store listing and co-op.gg]**.
- **Facts that conflict:** unit-placement cooldown is five minutes per battle in one listing, battles every 30 minutes in another **[conflict, UNVERIFIED]**. It was not established that it is an official Twitch extension **[UNVERIFIED]**.
- **Relevance:** closest mechanical cousin (viewer-placed units, persistence of unlocks). Its fan ecosystem includes unofficial reminder tools for when a viewer can act again, evidence that **cooldown-driven return loops generate fan-made tooling**. No growth numbers found **[NO DATA]**.

### 2.4 Marbles on Stream: minimal-friction participation
- **What it is:** a free Steam game where viewers type a chat command to get a named marble in a race; viewers do not control marbles, outcomes are random; Twitch only at the time of the sources; camera controls only **[UNVERIFIED, Steam community threads and MLH guide; the join command differs between sources: `!play` vs `!join`]**.
- **Lesson:** extremely low participation cost (one word) and no skill gate. Nexus's `!join strike` follows the same principle but promises more depth. No numbers found **[NO DATA]**.

### 2.5 Neuro-sama: 24/7-style AI stream, channel growth from a long-running character
- **What it is:** an AI VTuber run by one developer; origin as an osu! bot in 2018; now streams almost daily and responds to chat **[UNVERIFIED, Tubefilter]**.
- **Numbers (conflicting):** Tubefilter reports Hype Train records and about 160,000 active subscriptions on 2026-01-05; a French outlet reports over 300,000 for the same event **[conflict]**. Revenue estimates (about $200,000 for a single train) are outlet estimates **[UNVERIFIED]**.
- **Relevance (limited):** shows a solo developer plus an AI character can build a large audience over years; **the growth came from a personality and recurring events (annual subathon), not from a game ruleset**. Not directly comparable: Neuro-sama is a performer, Nexus is a system. Also shows audience tolerance for AI when clearly presented as AI. Time to scale was years, not weeks **[UNVERIFIED]**.

### 2.6 AI-plays-game streams (Claude Plays Pokemon, February 2025)
- Tubefilter reports an Anthropic-run channel where a model plays Pokemon Red **[UNVERIFIED]**. No audience or growth numbers found **[NO DATA]**. Relevance: shows interest in watching an autonomous agent progress through a game; our "AI Threat Director adapts visibly" pillar has a similar hook. (Full disclosure: the same vendor as the agents building this repo; this is a context note, not an endorsement.)

### 2.7 Foxhole (Siege Camp): persistent, community-driven war
- **What it is:** a persistent multiplayer war game where players run the entire war effort, no NPC economy; 1.0 launch on 2022-09-28 after 5 years of Early Access; the official Discord server reached almost 100,000 members by June 2021 **[UNVERIFIED, Wikipedia/press-release summaries]**.
- **Relevance:** proof that a war that lasts days or weeks, with logistics as a core job, supports a community and lore of its own. One report says developers once stepped in to end a war that ran 70 days **[UNVERIFIED, single outlet of unclear quality; Indian Defence Review]**. Treat the "70 days / 9 million deaths" figure as unverified. Lesson for our campaign length decisions and for community events around war ends. Also: a rule change to help new players join long wars drew mixed reactions **[UNVERIFIED]**; announce balance and new-player changes with reasoning.

### 2.8 What was NOT found
- No credible source on **always-on, chat-controlled strategy streams** besides the above, and no sourced growth curve for a **new** crowd-played game in 2026 **[NO DATA]**.
- No official post-mortems for Choice Chamber, Stream Raiders or Marbles on Stream were found.
- No sourced data for Twitch Integrated/Extension game retention.

### 2.9 Cross-cutting lessons (marked as inference, not sourced fact)
1. **Instant participation beats explanation.** Every cited example had a one-step entry. Keep `!join` the first thing on screen (matches Vision pillar 2).
2. **A novelty hook needs a retention loop.** TPP's hook was novelty; Stream Raiders' loop is progression/unlocks; Foxhole's is the war. Ours is persistent ranks and campaigns. Marketing should show the loop, not only the novelty.
3. **Rule changes split communities.** Announce balance and rule changes with reasons and a feedback path (see §5).
4. **Streamers built these games alongside the audience.** Choice Chamber's developer streamed development. This supports the devlog-as-story-engine direction **[UNVERIFIED, inference from one source]**.
5. **Clear AI labelling is not a growth blocker in the one AI example found** (Neuro-sama) **[UNVERIFIED]**; it is still our own principle regardless.

---

## 3. Platform discoverability realities

All platform facts are from search summaries; the official page is named where the summary pointed to one. Re-verify at each phase gate (NX-288).

### 3.1 Twitch directory and small-channel discovery
- **Directory/tags:** up to 10 tags per stream, set in the Creator Dashboard / Stream Manager > Edit Stream Info; some tags are category-linked **[UNVERIFIED, Fiverr and other guides; Twitch's own page not read]**.
- **Reality for small channels:** the distribution is heavily skewed. StreamScheme estimates ~95% of streamers average 0-5 concurrent viewers (about 6,350 of 127,000 active streamers, circa 2021) **[UNVERIFIED, old]**; StreamHatchet reports 61% of channels under 10 viewers **[UNVERIFIED, undated]**. Treat as direction, not data. **No current, credible number found [NO DATA].**
- **Category choice advice** (find games with a good viewers-to-channels ratio, check with TwitchTracker/SullyGnome) **[UNVERIFIED, creator blogs]**. For Nexus a custom category does not exist; it must pick an existing category. **Open question (§7.2):** which category (a specific "Software and Game Development"-type, a strategy category, or "Always On").
- **Discovery Feed:** Twitch launched a vertical, algorithmic clips feed in the mobile apps (tests from August 2023, launch 2024); creators can mark **featured clips**; Twitch states clips are meant to drive traffic to live streams, and it is "not our goal for viewers to spend hours in a Clips feed" **[UNVERIFIED, TechCrunch and esports.gg summaries]**. Relevance: our 9:16 clips (CLIPS-REPLAY §3) and the 9:16 variant (OV-11) can feed this surface. No numbers on its effect for small channels **[NO DATA]**.
- **Raids and schedule (Twitch Creator Camp, official domain, content dated from 2018 launch):** stream on a set schedule "even if only a few hours a week" and post it; raids can send your viewers to another live channel **[EXCERPT-OFFICIAL, twitch.tv/creatorcamp; may be dated]**.

### 3.2 24/7 channels on Twitch: rules and labelling
- **Rerun label:** prerecorded video should carry Twitch's Rerun label (checkbox in Edit Stream Info; title and notification prefixed "[Rerun]") **[UNVERIFIED, vendor guides; Twitch's help page not read]**. [Still UNVERIFIED on 2026-10-18: help.twitch.tv could not be read, PLATFORM-POLICY-VERIFICATION-2026-10-18 T24.]
- **48-hour broadcast limit:** a broadcast reportedly ends at 48 h and must reconnect **[UNVERIFIED, several vendor sources; already flagged in PLATFORM-REALITY-CHECK]**. [Still UNVERIFIED on 2026-10-18: no 48-hour figure appears on any page read, PLATFORM-POLICY-VERIFICATION-2026-10-18 T24.]
- **Always On category:** exists; a vendor snapshot dated 2026-10-10 reports about 16.9K viewers and 617K followers, with about two thirds of the first 30 channels replaying past streams **[UNVERIFIED, single vendor blog (upstream.so)]**.
- **Rerun hours and Affiliate/Partner eligibility:** a vendor claims reruns do not count toward eligibility baselines **[UNVERIFIED]**.
- **Drops/rewards abuse is banned** **[UNVERIFIED, consistent with PLATFORM-REALITY-CHECK]**.
- **Implication for Nexus:** our broadcast is a **live, interactive** render, not a prerecorded rerun, so the Rerun label should not apply to the main feed. **But** any segment that is a pre-recorded replay or devlog loop shown during intermissions should be assessed. **Open question (§7.2):** does the War Briefing / replay-loop intermission need the Rerun label, and does labelling a channel Rerun hurt discovery? Verify with Twitch support before P2.
- **AI disclosure on Twitch:** per a GamesBeat interview (Tokyo Game Show 2026), Twitch's CEO said Twitch does not currently need AI-disclosure rules; Kick updated its guidelines in March 2026 to require disclosure **[UNVERIFIED, single interview + single report]**. Separately, a report dated 2026-08-12 says Twitch content trains Amazon's generative AI models by default with a toggle **[UNVERIFIED, one outlet]**. We disclose anyway (Q-AI-6); no change. [Still UNVERIFIED on 2026-10-18: no Twitch policy page on AI disclosure and no primary source for the training toggle were retrievable, PLATFORM-POLICY-VERIFICATION-2026-10-18 T25, T26.]

### 3.3 YouTube: Live vs Shorts vs long-form
- **Shorts vs long-form use different recommendation systems** (Shorts are discovered in a swipe feed) per a YouTube Shorts product lead on Creator Insider, as reported by news coverage **[UNVERIFIED, second-hand]**.
- **Overlap of audiences:** a blog claims overlap as low as 10% between dedicated Shorts and long-form viewers, no methodology **[UNVERIFIED, weak]**. Conversion rates of Shorts viewers to long-form: the "15 to 25%" figure in one blog has no checkable source **[NO DATA]**.
- **Shorts view counting:** from 2025-03-31, a Shorts view counts when it starts or replays, with no minimum watch time; the previous measure is shown as "Engaged views" and monetisation is tied to engaged views **[VERIFIED 2026-10-18]** on support.google.com/youtube/answer/10059070: from 3/31/2025 a Shorts view counts when it "starts to play or replay, with no minimum watch time"; the old metric is "Engaged views" and YPP uses engaged views [CORRECTED 2026-10-18: was `[EXCERPT-OFFICIAL via a search summary pointing at YouTube Help; threshold undisclosed]`; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y18]. Implication: raw Shorts view counts are not comparable to older benchmarks; use engaged views and subscribers gained from our own analytics screen.
- **Thumbnail/title testing:** YouTube Studio lets a creator test up to three titles and thumbnails per video; the winner is chosen by watch time; desktop only; not available for Shorts, scheduled lives or premieres; live archives are supported **[EXCERPT-OFFICIAL, support.google.com/youtube/answer/16391400]**. Useful for devlogs.
- **YouTube Live for 24/7:** no official source on discovery for 24/7 streams was found **[NO DATA]**.
- **Inauthentic content (YPP, effective 2025-07-15):** targets mass-produced and repetitious content; not a ban on AI or reused content if there is original value (commentary, editing, narration) **[VERIFIED 2026-10-18]** on support.google.com/youtube/answer/1311392: the policy was renamed from "repetitious content" to "inauthentic content"; it concerns YPP monetization and says nothing about live streams (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y13) [CORRECTED 2026-10-18: was `[UNVERIFIED, news summaries; official wording not read]`]. Our "owner voice, real footage, human approval" direction fits; the policy is the reason not to automate Shorts.
- **Altered/synthetic content disclosure:** creators must disclose realistic altered/synthetic content at upload; unrealistic content, animation and routine AI productivity uses (scripts, captions) are exempt; YouTube may label it automatically, and said in 2026 it would use detection to add labels to "significant photorealistic AI" content **[UNVERIFIED, NBC and ppc.land summaries]**. [VERIFIED 2026-10-18 on support.google.com/youtube/answer/14328491: disclosure is for realistic content only; the no-disclosure list includes "Gameplay footage from video games" and "Cloning one's own voice to create voice overs"; a generic TTS voice is on neither list; the Studio field is Attributes, "AI use"; automatic labels apply to YouTube GenAI tools, C2PA metadata or internal detection and cannot be adjusted, and the page gives no 2026 date for detection labels (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y14, Y15).] Our footage is rendered simulation, not photorealistic; AI voices are likely a "disclose to be safe" case, to be confirmed in NX-288.

### 3.4 TikTok / Reels / Shorts for gameplay clips
- **TikTok AI labels:** creators are required to label AI-generated or significantly edited content that shows realistic-looking scenes or people (Community Guidelines 2026H2 update, released 2026-08-25, effective 2026-09-24), and the Direct Post field `is_aigc` adds the tag [CORRECTED 2026-10-18: was "creators are asked to disclose realistic AI content"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 K9]; C2PA-based automatic labels were announced in May 2024 **[UNVERIFIED, news summaries, 2024; recheck for 2026]** (the C2PA announcement; the 2026 label rule above is `[VERIFIED 2026-10-18]`).
- **TikTok LIVE:** unchanged from PLATFORM-REALITY-CHECK (no chat API; best-effort). Short-form clips on TikTok/Reels do not need LIVE.
- **One 2026 guide argues the most reliable growth pipeline for small streamers runs through TikTok and YouTube Shorts rather than Twitch** **[UNVERIFIED, nerdbot.com]**. Treat as opinion.
- **No credible, platform-neutral benchmark for gameplay clips was found [NO DATA].**

### 3.5 Posting cadence evidence (weak)
- vidIQ (July 2026, 10.2 million channels): median monthly view growth rose from 0.53% (uploading less than once a month) to 2.18% (12 or more uploads/month); subscriber growth from about flat to 0.91%/month. vidIQ itself says correlation, not causation **[UNVERIFIED, vendor study, search summary]**.
- OverseerOS (189 breakout channels): median 2.7 uploads/week, but 23.3% published less than about weekly **[UNVERIFIED, vendor, small sample]**.
- "Predictable spacing beats irregular posting at the same volume" (18,000 channels, cited second-hand) **[UNVERIFIED, weak]**.
- **Reading:** evidence supports "regular" more than any magic number, and is all confounded. **Flag: weak.**

### 3.6 Reconciling with Q-MKT-4
Q-MKT-4: devlog every 2-4 weeks at milestones, 2-3 shorts/week from one-tap approvals, Reddit at big milestones, flexible, breaks allowed, scheduled post queue.
- The evidence does not contradict the target, but it is weak, and says **predictability matters**. The owner travels, so the scheduled post queue is the right tool (post on fixed weekdays regardless of travel).
- Suggest wording: **"floor and ceiling"**: floor = 1 short/week + 1 devlog/month on fixed weekdays; ceiling = 3 shorts/week. The floor protects against burn-out; the ceiling is not a goal.
- The 24/7 stream is itself continuous content; the schedule that matters on Twitch is a **weekly "event slot"** (e.g. campaign start, war end, lieutenant reveal), per Creator Camp's "set schedule" advice **[EXCERPT-OFFICIAL, dated]**.
- Raw Shorts view counts changed meaning in 2025 (§3.3), so do not set targets on raw views.

---

## 4. Production pipeline for a solo developer

### 4.1 Devlog workflow (capture, outline, record, edit, publish)
| Step | What happens | Owner effort [ESTIMATE] | Automation |
|---|---|---|---|
| 1. Capture | `devlog-moment` item lands; agent writes DEVLOG CHECKPOINT (AGENTS 11a); staging writes replay renders/screenshots to `devlog-footage` (MARKETING) | 0 min | Existing mechanism |
| 2. Outline | Owner picks 1 moment per devlog; agent drafts a 5-bullet talking-point outline and shot list from the checkpoint blocks | 10 min | Agent drafts, owner edits |
| 3. Record | Owner records voiceover (own voice, MARKETING principle) over footage | 20-40 min | None; script is bullets, not prose |
| 4. Edit | Cut to length, add lower thirds and captions from templates (§4.4) | 1-3 h | Template project, auto-subtitle draft reviewed by the owner |
| 5. Publish | Thumbnail from template, title, description with AI-disclosure line (§4.8), chapters, link to Discord; schedule | 30 min | Description template |
| 6. Repurpose | Cut 2-3 vertical clips from the devlog for the short-form queue | 30 min | CLIPS-REPLAY review queue |
Total per devlog [ESTIMATE]: 3-5 h of owner time. This is my planning estimate, not a measurement; track actual time for the first three and replace it.

### 4.2 Tools (free or low cost)
Licenses and prices are **[UNVERIFIED]** unless stated; confirm on the vendor pages before relying on them. [CORRECTED 2026-10-18: the licences and prices of the tools below were read from upstream files and vendor pages (LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-50 to V-57); Canva Pro stays UNVERIFIED (V-58).]
| Task | Tool | License/price (as found) |
|---|---|---|
| Stream/capture | OBS Studio | GPL v2 or any later version (README; COPYING is the GPLv2 text) **[VERIFIED 2026-10-18]**, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-50 [CORRECTED 2026-10-18: was "Open source (GPL) from general knowledge [UNVERIFIED]"] |
| Video editing | DaVinci Resolve (free) | Free version: "works with virtually all 8-bit video formats at up to 60fps in resolutions as high as Ultra HD 3840 x 2160" and "includes multi-user collaboration and HDR grading" [CORRECTED 2026-10-18: was "single-user collaboration"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-57]; "no watermark" and "no time limit" are not stated on the Blackmagic page **[UNVERIFIED]**. Studio is a one-time purchase at $295 [CORRECTED 2026-10-18: was "around $295-299 USD"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-56] **[VERIFIED 2026-10-18]** (blackmagicdesign.com/products/davinciresolve). Studio-only: noise reduction, some AI tools, GPU features, scripting API. Free tier is enough for 1080p devlogs. |
| Video editing (open source) | Kdenlive | GPLv3 (COPYING is the GPLv3 text; "or later" wording not checked) **[VERIFIED 2026-10-18]**, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-51 |
| Audio | Audacity, Reaper | Audacity: GPLv3 (LICENSE.txt; individual files may differ). Reaper: commercial, $60 discounted license (personal use, or yearly gross revenue up to USD $20,000, or educational/non-profit) or $225 commercial license, with 60 days of free evaluation (reaper.fm purchase page and EULA) **[VERIFIED 2026-10-18]**, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-54, V-55 |
| Raster art | Krita | GPLv3 (COPYING is the GPLv3 text; per-file headers not checked) **[VERIFIED 2026-10-18]**, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-52 |
| Vector art | Inkscape | Most source GPL v2 or later; complete binaries GPL v3 or later **[VERIFIED 2026-10-18]**, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-53 |
| Quick graphics | Canva | Free plan available; Pro reported around $18/month or $144/year, other sources $15/month or $180/year; free tier limits brand kits, collaboration and most AI tools **[UNVERIFIED, vendor/review sites, price conflicts]** |
| Music | Epidemic Sound | See EPIDEMIC-SOUND-RESEARCH; Creator plan is described as non-commercial yet allows monetizing one channel per platform (Epidemic's own pages contradict each other) **[VERIFIED 2026-10-18]**, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-80, V-85 [CORRECTED 2026-10-18: was `[UNVERIFIED]`]; devlogs on a monetised channel may need a higher plan; confirm in writing (NX-297) |
Compatibility note: prefer tools whose project files are open formats (Kdenlive, Krita, Inkscape) for long-term access; DaVinci Resolve is proprietary but free. All of this is a recommendation for the owner to decide.

### 4.3 Hardware reality
The broadcast host needs a GPU for the 24/7 render plus encode (PLATFORM-REALITY-CHECK §8). Cinematic replay renders (§4.6) compete with it. CLIPS-REPLAY §3 already says render at low priority, when the GPU is idle or on another machine.

### 4.4 Template kits in the Quorum/Static visual language
Visual language already decided: Signal radar look, green and amber on black, radio static, callsigns, friendly tone (Q-BRAND-1), Hum motif for the Static (Q-BRAND-4). Brand guide is NX-274 (not written yet), so templates must wait for it. Proposed kit (all tracker candidates in §7):
- **Thumbnail templates** (3): "map + one big callsign/stat", "before/after", "AAR headline". Constraint: no real names, no AI art at release (Q-BRAND-5); placeholder art labelled in alpha.
- **Lower thirds:** callsign + node name style (reuse overlay type).
- **Intro/outro (under 5 s):** radar sweep + the Hum; the outro carries the `!join` instruction and the Discord link.
- **Subtitle style:** monospace, high contrast, at least the same size rule as OV-1 (28 px at 1080p), burned-in for short-form since viewers watch muted.
- **Static vs Quorum colour cues:** coalition = green, Static = amber/red or per the brand guide; do not invent new colours outside NX-274.
- Keep generated assets in the asset provenance register (Q-BRAND-5, NX-318), including music, fonts and sound effects.

### 4.5 Content calendar tied to ROADMAP gates and DEVLOG CHECKPOINT
| Gate / moment | Content (devlog = D, short = S, community post = R) | Timing note |
|---|---|---|
| P0 exit (CI green, ADRs) | D0: "Why I'm building a war game that chat plays" (a story post, not a feature demo) | Optional; builds the origin story. Q-MKT-3 says start early |
| P1: first map renders with moving units (the MARKETING first-public-post trigger) | D1 + 3 S (labelled "simulated test") + R at r/gamedevscreens-type community **[UNVERIFIED sub names, check rules]** | First public post |
| P1 exit (golden replay, campaign ends in 24-72 h simulated) | D2: "A whole war in 90 seconds" replay render | Strong visual |
| P2 alpha running (unlisted) | D3: alpha log; S from live alpha clips; Discord private channel | Testers may share (Q-TEST-3) |
| P2 exit (multi-day unattended run) | D4: "7 days without me" (or however many days actually ran) | Report real number only (DI rules) |
| P3 public beta open | D5 launch devlog; R launch posts; old-Discord announcement released (after Q-MKT-3 organic test) | Biggest moment |
| P3 YouTube chat live; 9:16 output live | S weekly | |
| P4 depth: lieutenant reveals, world events, seasons | D every milestone; lore drops | |
Each `devlog-moment` item produces a DEVLOG CHECKPOINT; the calendar only schedules the post, the checkpoint supplies the material.

### 4.6 Auto-captured footage and replay renders (CLIPS-REPLAY)
- Replays are deterministic (seed + config hash + command log + hourly snapshots), so a "cinematic" render can re-run the same war with a different camera, speed, or annotations. Constraints that matter for marketing:
  - **RP-1:** while a campaign is running, every clip/export shows only what the coalition could see. A "cinematic" render of a live campaign cannot reveal enemy positions. Full-reveal renders only after `campaigns.ended_at` (RP-2). So **big reveal videos wait for a war to end** (good fit for an AAR devlog: "what you didn't see").
  - **Pseudonymity:** replays show approved callsigns only; deleted commanders appear as `REDACTED-<tag>`. Clips must never show display names or platform ids.
  - **Simulated footage** (viewer simulator, Q-LEGAL-7) is allowed in marketing only if labelled "simulated test" (Q-MKT-3, DI-5).
- Vertical render: 1080x1920 via headless browser + FFmpeg (CLIPS-REPLAY §3) exists as spec; OV-11 defines the 9:16 layout (full map scaled, PiP below). 9:16 is P3. Before P3, a manual crop is the only path; flag that a manual crop breaks the "never crop" rule for the live layout, so before OV-11 exists use only 16:9 devlogs plus screen-recorded phone-friendly captions, or accept a clearly separate editing crop for marketing only (decision for owner, §7.2).
- Stored footage (`devlog-footage` folder) should follow the 35 MB estimate caution in CLIPS-REPLAY §1: measure real size in P1.

### 4.7 Highlight detection and clip scoring (from our own sim events)
CLIPS-REPLAY §2 already defines a rolling 15 s excitement score from missiles in flight, kills, captures, human involvement, objective completion, with configurable weights; threshold triggers a `[t-25 s, t+5 s]` clip job. Additional own-data signals that fit the same mechanism (proposals, none sourced externally):
- Node captured/lost, bridge destroyed, tier change, objective completed (the same events as big-moment sitreps, AUDIO-TTS §2a).
- Rescue event, convoy survival, first command by a new operator, rank-up of a human, a long-held defence, a last-stand ending.
- Negative filters: skip clips with moderation flags, with an operator on `!quiet`, or in the first minutes after a restart. Skip any clip that includes unmoderated text.
- **Clip quality gate for the one-tap queue:** show owner the score components, the 3 s thumbnail, and the redaction status. Never auto-publish (CLIPS-REPLAY §4, YouTube inauthentic-content risk).
- **No benchmark** for "good" excitement-score thresholds exists externally **[NO DATA]**; calibrate on the first 20 reviewed clips and record acceptance rate as the metric.

### 4.8 Captions, subtitles, accessibility, AI-transparency labelling
- **Captions:** burn in captions on every short-form clip (owner voice or text only, per MARKETING). For devlogs, upload SRT files; auto-captions are a draft only and must be proofread.
- **Colour and contrast:** red/green is the coalition/enemy palette risk for colour-blind viewers; use shape/icon plus colour (cross-reference OVERLAY accessibility rules in the spec; I did not re-audit it here).
- **Audio:** the Hum and radio filter must not mask the owner's voice; keep sitrep/TTS lines out of devlog voice-over mixes.
- **AI-transparency copy bank** (to put in a single source file; wording is a proposal):
  - Channel panel / about (Q-AI-6, AU-3): "Synthetic voices: radio lines on this stream are AI-generated."
  - Placeholder art note (Q-BRAND-5): "Art in this build is placeholder. We are looking for human artists." State on-stream during alpha and in README/site/Discord.
  - AI Threat Director: "The Static is an AI opponent. Its choices are made by rules and an advisor model that can be rejected by code." (Keep matched to LLM-ADVISORS.)
  - Simulated footage: "SIMULATED TEST: scripted bot operators, no real players" on-screen for the whole clip, not only in the description.
  - Human voice lines: labelled human in the voice-cast config (AU-5).
  - Music: licensed track credits per platform requirement (provenance register).
  - Each platform's synthetic-content toggle at upload: decide per platform at the phase gate (NX-288). Do not assume it is optional.

---

## 5. Community and moderation operations

Keep within what specs decide; anything new is an open question (§7.2).

### 5.1 Discord server structure (alpha/beta proposal)
Per a Discord-help-style setup guide: Community features include Rules/Onboarding, Welcome Screen (now superseded by Community Onboarding), Raid Protection, Server Insights; guidance suggests mentions-only default notifications and disabling risky permissions for @everyone **[UNVERIFIED, third-party summaries of Discord support articles; check support.discord.com]**.

| Category | Channels | Notes |
|---|---|---|
| START HERE | #rules, #welcome, #how-to-play, #ai-and-art-disclosure | Read-only. Copy from the §4.8 bank |
| ANNOUNCEMENTS | #war-briefing (bot, NX-296), #devlog, #patch-notes | Bot posts; no chat |
| COMMS | #general, #strategy, #clips-and-screens, #off-topic | Moderated, slow mode on busy channels |
| ALPHA/BETA | #testers-private (invite-only), #bug-reports, #feedback | Alpha: private (Q-TEST-3) |
| LORE | #the-quorum, #the-static-intercepts | Lore drops; read-mostly |
| HELP | #support, #appeals (private ticket-style) | Appeals per ADMIN-RBAC §6.8 |
| STAFF | #mod-chat, #mod-log, #escalations | Staff only |
Roles tied to ranks: the game ranks (O-1 to O-6, PROGRESSION) could map to Discord roles via the OAuth link portal (P3). Rank names are pending NAMING-CONVENTIONS §3 / NX-323, so do not build role names yet. Staff roles: Owner, Admin, Moderator, Trial Moderator, Bot. Mapping to ADMIN-RBAC roles is not defined; **open question**. Link portal and account linking touch identity, so a `security-review` is required (CLAUDE.md).

### 5.2 Community guidelines and conduct outline
Proposed structure (an outline, not final rules; final copy belongs to NX-276/NX-314 and the conduct spec NX-291):
1. Be welcoming (Q-BRAND-1: friendly, playful, non-toxic).
2. No harassment, hate, doxxing; no real-world military glorification beyond the fiction (Q-PROD-5: no real names).
3. No spam, no command spam or suicide spam (ADMIN-RBAC §6.8: skill is not conduct).
4. No self-promotion outside the designated channel.
5. No exploiting, no account farming (NX-277).
6. Chat is hostile input: staff may remove content and the pipeline filters it.
7. How in-game conduct (decaying score, escalation ladder, appeals) relates to Discord/Twitch bans. **Not decided**; the ladder is in-game only today.
8. AI transparency statement.
Rules are published on site and via `!rules` (ADMIN-RBAC §6.8).

### 5.3 Moderator recruitment, training, escalation, appeals
- **Recruitment:** from alpha testers (Q-TEST-3), people with good standing; trial period before full moderation. Source for typical Twitch tooling: AutoMod holds risky messages for a human to approve/deny; Shield Mode bundles safety settings and adds "no first-time chatters" and bulk ban **[UNVERIFIED, esports.gg / xda-developers / brandbastion summaries of Twitch's Dec 2022 announcement]**.
- **Training:** one short written doc: tools (Twitch AutoMod/Shield Mode, Discord Raid Protection, our admin console), the escalation ladder, the "never argue in public" rule, the privacy rules (SEC-DATA-2 pseudonymity).
- **Escalation:** moderator (warn, timeout) to admin (ban, in-game restriction) to owner (policy exceptions, legal). Define response-time expectations as a decision, not as a promise.
- **Appeals:** private channel or form; every action logged and reversible (ADMIN-RBAC §6.8). Public statement that appeals exist.
- **Not covered by specs:** who reviews Discord appeals, how long, transparency reports. Open question.

### 5.4 Bot roles
- **War Briefing (NX-296):** auto-publishes the AAR/briefing card to site and Discord via `CommunityBot`/`ChatSink` ports; data-only content (no invented text).
- Suggested additional bot jobs (proposals): welcome message from the onboarding copy; role assignment on account link; scheduled event reminders; link filter in new-member channels. Vendor SDK use stays in adapters (rule 10a); discord.py is maintained (PLATFORM-REALITY-CHECK §9).
- Bots that post must be clearly labelled as bots (consistent with DI-5).

### 5.5 Event ideas (all consistent with existing specs)
- **War start / war end broadcasts** with the AAR "what you didn't see" reveal (GAMEPLAY end-of-campaign, NX-279). Natural weekly community moment.
- **Season launches** (P4); **world events** (NX-310, labelled on stream).
- **Lieutenant reveals and Static intercepts** as lore drops (NX-275, NX-326). The mastermind's self-chosen name (Crosstalk/Dead Air candidates, Q-BRAND-4) is a planned reveal beat ("NULL is <self-name>"); keep it out of marketing until the owner schedules it.
- **Naming votes** (Q-BRAND-3) are P5+/future.
- **Community art/clip/callsign showcases** (opt-in only; callsigns are pseudonyms).
- **Weekly "Debrief" thread** on Discord after each war end.

### 5.6 Creator and partner ideas (no budget)
- **"Host a war" kit** for small streamers: a page explaining how to point their chat to the Nexus channel or to run the operator view; raid etiquette; credits.
- **Raid-friendly mechanics:** a raid arriving should land in a clear "how to join" overlay moment (OV how-to strip). Raids are described by Twitch Creator Camp as sending your viewers to another live channel **[EXCERPT-OFFICIAL, dated]**.
- **Small-streamer outreach** for playtests, only to communities whose rules allow it (Q-TEST-3 flags the check as UNVERIFIED).
- **Artist call:** Q-BRAND-5 says the owner is searching for artists publicly; combine with a showcase for human artists.
- **Voice actor auditions** are allowed by Q-AI-6 with written consent and licence (AU-5).
- **Not recommended yet:** paid influencer deals (free only), affiliate codes, sponsored posts.

### 5.7 Crisis plan skeleton (if something offensive slips through)
1. **Detect:** viewer report, moderator catch, or alert (NX-300).
2. **Contain (minutes):** owner kill switch / Ceasefire (NX-325), pause overlay text layer, freeze TTS (circuit breaker, AUDIO-TTS §4), switch to the intermission scene.
3. **Remove:** delete offending VOD/clip segment on each platform; hide chat messages; remove from replay store (REDACTED pipeline).
4. **Report:** if the content violated platform rules, report it ourselves before they do, if appropriate (decision for owner).
5. **Communicate:** one short public statement in Discord and the channel panel: what happened, what was fixed, what changes. No blame on viewers; no deletion of the discussion without a reason.
6. **Post-mortem:** within a week, add the case to the moderation test corpus (SECURITY/THREAT-MODEL) and update filters.
7. **Clip-publication gate:** every clip passes the review queue, so a flagged moment should not reach short-form; if it did, delete and say so.
Roles and the "who does what at 3 a.m." decisions are open questions.

---

## 6. Launch plan by phase

All hour figures are **[ESTIMATE]** planning guesses for one part-time owner using agents; they are not measurements. Track real hours and revise at each gate. All KPIs use first-party data only (Q-DM-3).

### 6.1 Audience segment hypotheses (no data yet)
| Segment | What they want | Where to reach | First thing they should see |
|---|---|---|---|
| Mil-sim and strategy fans (DEFCON, Foxhole, HighFleet, Wargame, per VISION) | Depth, logistics, fog of war, an AI that adapts | Strategy subreddits/communities (check each sub's self-promo rules), YouTube devlogs | A replay render with fog of war and a logistics story |
| Casual lurkers who want to take part | Instant participation, a personal unit, calm ambient stream | Twitch directory, Shorts | The map with moving units and the `!join` strip |
| Devlog/indie-dev audience | How a solo dev builds a thing with agents, honest process | YouTube, r/gamedev-type communities (self-promo needs value, per sub rules **[UNVERIFIED]**) | A devlog with real numbers and mistakes |
| Small streamers / hosts | A game their chat can play | Discord outreach, raids | The "host a war" kit |
| Lore readers (later) | The Quorum/Static story | Discord lore channels | Lore drops |

### 6.2 P1: first map with moving units
- **Goal:** prove the story and create the first public artifact. Not growth.
- **Assets:** 1 devlog (D1), 3 clips labelled "simulated test", handle set (if name decided), README with AI/placeholder disclosure, 1-line pitch, screenshot set.
- **Effort [ESTIMATE]:** 3-5 h/week average, spiking in the week of the first public post.
- **KPIs (own data):** none about viewers yet. Output KPIs only: devlog published, footage folder populated, pitch tested on 3 people who answer "what is this?" in one sentence (Vision pillar 1).
- **No-budget plan:** all free tools (§4.2).

### 6.3 P2: closed alpha (Twitch, unlisted)
- **Goal:** 5-10 cold testers per Q-TEST-3, plus a multi-day unattended run.
- **Assets:** tester invite message, 3-question survey, consent form for the 5-minute recording, private Discord channel, alpha-disclosure note (AI placeholder art + artists wanted), D3/D4 devlogs, viewer-simulator content labelled "simulated" (never on the public channel, Q-LEGAL-7).
- **Effort [ESTIMATE]:** 4-6 h/week.
- **KPIs (own data):** testers read the stream in 5 s and spawn within 30 s (ROADMAP P2); survey completion; uptime days; zero unmoderated text; tester share-rate if measurable.
- **Do not** invite via the old Discord yet (Q-MKT-3 hold).

### 6.4 P3: public beta
- **Goal:** reach the VISION beta metrics: median session >= 12 min, >= 20% of viewers issue a command, D7 returning commanders >= 15% (second-command rate is X%, FB-UX-6, still TBD).
- **Assets:** launch devlog, trailer built from real replay render (placeholder art disclosed or replaced), press/creator kit, 9:16 clips, Discord public launch, Reddit posts per milestone, old-Discord announcement, raid/host kit.
- **Effort [ESTIMATE]:** 8-12 h/week at launch, then 5-8 h/week.
- **KPIs (own data):** `!join` per stream session; first-command rate; second-command rate; median session; D7 returning commanders; Discord joins from the link portal; clip approval rate. **Referral attribution without trackers:** optional "how did you find us?" one-time answer at link time or a launch-week code; never cookies or trackers (Q-DM-3, NX-204, NX-314, NX-316).
- **There is no credible external benchmark** for any of those rates **[NO DATA]**; the VISION targets are the owner's own.

### 6.5 P4: depth
- **Goal:** retention and lore. Season launches, world events, lieutenant reveals, rank-ups.
- **Assets:** season key art (human-made by release, Q-BRAND-5), lore drops, event calendar, partner kits.
- **Effort [ESTIMATE]:** 5-8 h/week.
- **KPIs:** D30 returning commanders (to be defined in analytics definitions, NX-314), event participation, Discord activity.

### 6.6 First 30 days of the public channel (when P3 opens)
| Days | Actions |
|---|---|
| Before day 0 (T-14 to T-1) | Press/creator kit published; Discord rules and onboarding tested; moderators briefed; crisis checklist rehearsed; Twitch tags/title/category settled; Rerun-label question answered |
| Day 0 | Launch devlog; Reddit post(s) per each sub's rules; Discord opens; old-Discord announcement (if organic test done); pinned "how to join" |
| Days 1-7 | Daily check-ins (15 min); first war-end AAR as a community moment; 3 shorts from the queue; fix the top 3 friction points from chat and survey |
| Days 8-14 | Weekly "debrief" post; outreach to 5 small streamers (rules checked); first KPI review from own data |
| Days 15-30 | Second devlog (what the data showed, including bad numbers); decide cadence for the next phase; retro in PHASE-P3 decision doc |

### 6.7 Budget plans
- **No-budget plan (default, owner-decided):** everything in §4.2 with free tiers; Epidemic Sound is the only known subscription (NX-297; confirm plan scope). All marketing is owned channels and community posts.
- **Optional modest-budget plan:** only items with sourced prices are listed; ranges are not offered for anything else.
  - Canva Pro, if template work in Canva proves worth it: reported $15-18/month or $144-180/year depending on source **[UNVERIFIED, conflicting]**.
  - DaVinci Resolve Studio: one-time, $295 **[VERIFIED 2026-10-18]** [CORRECTED 2026-10-18: was about $295-299; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-56] (not needed for 1080p devlogs).
  - Human art commissions: **[NO DATA]**; no credible price range was found in this research. Do not budget from this file.
  - Paid ads, sponsored creators: **[NO DATA]**; excluded by Q-MKT-3 anyway.
  - One sourced advice point: if spending anywhere, a professional-looking capsule/key image is the one item that indie-marketing advice consistently says is worth paying for **[UNVERIFIED, Zukowski via Unity/Game World Observer summaries]**. This matches Q-BRAND-5's "real human-made art at release".

---

## 7. Prioritized backlog and open questions

I did not edit TRACKER or OPEN-QUESTIONS. Sizes: S (under ~half a day), M (1-2 days), L (several days). IDs below are **placeholders** ("MKT-n") to avoid colliding with existing NX numbers; the owner assigns real IDs.

### 7.1 Tracker candidates
| # | Item | Size | Phase | Depends on | Priority |
|---|---|---|---|---|---|
| MKT-1 | One-line pitch, 3-line and 30-s pitch, tagline usage rules (which line for strangers vs community), 5-second "what is this" test | S | P1 | Q-BRAND-6 | High |
| MKT-2 | Brand-safe handle plan: which handles to claim now, which wait for the name decision | S | P1 | Q-BRAND-6 | High |
| MKT-3 | Devlog template pack: outline template, thumbnail templates (3), lower thirds, intro/outro, subtitle style | M | P1-P2 | NX-274 brand guide | High |
| MKT-4 | AI-transparency copy bank (panel, descriptions, Discord, README, on-stream placeholder note, simulated-test overlay text) | S | P1 | Q-AI-6, Q-BRAND-5, NX-288 | High |
| MKT-5 | Platform policy check (Twitch Rerun label for intermission loops; AI-disclosure toggles on Twitch/YouTube/TikTok; category choice; 48 h restart) with primary pages read | M | P1 (before P2) | NX-288 | High |
| MKT-6 | Community Code of Conduct v1 (human-readable) + Discord rules + on-stream chat rules, mapped to ADMIN-RBAC §6.8 | M | P2 | NX-276, NX-291 | High |
| MKT-7 | Discord server structure spec + onboarding copy + bot role list (War Briefing and welcome) | M | P2 | NX-296, MKT-6 | Med |
| MKT-8 | Moderator handbook (tools, ladder, escalation, appeals) + recruitment form | M | P2 | MKT-6, ADMIN-RBAC | Med |
| MKT-9 | Crisis playbook (§5.7) with kill switch/pause steps and statement templates | S | P2 | NX-325, NX-300 | High |
| MKT-10 | Tester recruitment kit: invite text, 3-question survey, consent form for 5-min recording, tester disclosure sheet | S | P2 | Q-TEST-3 | High |
| MKT-11 | Press/creator kit: fact sheet, screenshots (from replay renders), logos, colour/font tokens, content notes, contact, "host a war" page | M | P3 | NX-274, Q-BRAND-5 | Med |
| MKT-12 | Trailer from a deterministic replay render (cinematic camera, captions, disclosure) | M | P3 | CLIPS-REPLAY, OV-11 | Med |
| MKT-13 | Clip-scoring extension: extra event signals, negative filters, accept-rate metric, review-queue fields (score components, redaction status) | M | P3 | CLIPS-REPLAY §2, NX-233..239 | Med |
| MKT-14 | Marketing KPI definitions from own data (join rate per session, first/second-command rate, referral self-report) | S | P2 | Q-DM-3, NX-314 | Med |
| MKT-15 | Content calendar document tied to ROADMAP gates and DEVLOG CHECKPOINT; scheduled post queue process for travel weeks | S | P1 | Q-MKT-4 | High |
| MKT-16 | Auto-subtitle draft + proofread workflow for devlogs and shorts | S | P2 | tools choice | Low |
| MKT-17 | Community event calendar (war start/end, AAR debrief, lore drops) | S | P3 | NX-296, NX-310, NX-275 | Low |
| MKT-18 | Playtest-community and Reddit rule checklist (per community: self-promo rules, allowed content) | S | P1 | Q-TEST-3, Q-MKT-1 | Med |
| MKT-19 | Marketing-time log (record real hours) to replace the estimates in §6 | S | P1 | none | Med |

### 7.2 Open questions for the owner
1. **Handles vs name (Q-BRAND-6):** claim handles now under the working title, or wait? If a rename happens, the clean-break accounts must be renamed or recreated.
2. **Twitch category and tags:** which category will the 24/7 channel use? Is "Always On" acceptable, or a strategy category?
3. **Rerun label:** does the War Briefing / replay loop in intermissions count as prerecorded content that needs the label? Ask Twitch support before P2.
4. **Marketing crop before OV-11:** until the 9:16 layout exists (P3), may marketing clips use a separate 9:16 edit crop, or must short-form wait for OV-11?
5. **Cadence wording for Q-MKT-4:** adopt the "floor and ceiling" wording (1 short/week + 1 devlog/month floor)?
6. **Referral measurement:** is a one-time "how did you find us" self-report at link time acceptable under Q-DM-3 and the privacy notice?
7. **Conduct vs platform bans:** do in-game conduct steps ever trigger Discord/Twitch actions, or stay separate?
8. **Moderation staffing:** who are the first moderators, and what are the 3 a.m. response expectations? (Crisis plan.)
9. **Discord roles vs ranks:** map O-1..O-6 to Discord roles at P3, or keep roles as staff and "Operator" only?
10. **Press: contact email and public contact policy.** Which address, and does the owner appear by name or alias?
11. **Epidemic Sound scope** for monetised devlogs and the new brand (Q-MKT-2, NX-297): outstanding.
12. **Old-Discord announcement:** what organic-traction threshold counts as "tested" (Q-MKT-3)? Suggest naming a threshold before P3.
13. **Neutrality of lore teasers:** may marketing reveal the mastermind's existence/codename NULL before the self-name reveal beat (Q-BRAND-4)?

---

## 8. Sources and access log

**Date read: 2026-10-18.** All entries were reached **only as web-search result summaries**. No page was fetched in full. Direct `WebFetch` and `curl` to every host tried failed (DNS failure and proxy 403).

### 8.1 Sources used (summary level)
Comparables:
- https://en.wikipedia.org/wiki/Twitch_Plays_Pok%C3%A9mon (search summary only)
- https://www.npr.org/sections/alltechconsidered/2014/02/19/279682262/heres-what-happens-when-thousdands-play-pokemon-together (listing only)
- https://blogs.biomedcentral.com/on-society/2019/06/25/what-twitch-plays-pokemon-tells-us-about-crowd-behavior/
- https://arxiv.org/pdf/1408.4925.pdf
- https://psmag.com/environment/chaos-democracy-religion-world-twitch-plays-pokemon-75839
- https://diplomaticourier.com/posts/anarchy-vs-democracy-the-politics-of-twitch-plays-pokemon
- https://www.gameinformer.com/b/news/archive/2014/03/01/twitch-shares-twitch-plays-pok-233-mon-viewership-stats.aspx
- https://www.mcvuk.com/twitch-plays-pokemon-causes-system-wide-chat-problems/
- https://www.gamespot.com/articles/twitch-plays-gets-its-own-directory-on-twitch/1100-6433795/
- https://gamedeveloper.com/design/twitch-plays-everything-designing-for-a-new-frontier (opening only)
- https://www.nintendolife.com/news/2014/03/success_of_twitch_plays_pokemon_raises_possibility_of_gaming_platform
- https://gamesbeat.com/choice-chamber-has-twitch-viewers-help-or-torture-a-streamer/
- https://tubefilter.com/2015/07/17/choice-chamber-twitch-chat-video-game/
- https://www.co-op.gg/web/game/stream-raiders ; https://chromewebstore.google.com/detail/bjcggclomjkmcofpmnncenbgkbpjkpcl
- https://steamcommunity.com/app/1170970/discussions/0/1743386132101466701 ; https://guide.mlh.com/overview/event-types/digital-events/additional-mini-events/marble-races
- https://www.tubefilter.com/2026/01/05/neuro-sama-vedal987-most-subscribed-hype-train-record/amp/ ; https://gensdinternet.fr/?p=42512
- https://www.tubefilter.com/2025/02/26/anthropic-claude-ai-twitch-plays-pokemon/
- https://en.wikipedia.org/wiki/Foxhole_(video_game) ; https://indiandefencereview.com/70-days-and-over-9-million-deaths-developers-had-to-step-in-to-end-an-unstoppable-war/

Platform:
- https://www.twitch.tv/creatorcamp/en/learn-the-basics/the-basics/ ; https://www.twitch.tv/creatorcamp/en/level1/growing-your-community/collaborating ; https://www.twitch.tv/creatorcamp/en/level1/establish-your-brand/engaging-viewers
- https://upstream.so/blog/24-7-twitch-stream/ ; https://ireplay.tv/blog/24-7-always-on-streaming-twitch-grow-audience-with-existing-content/ ; https://streamhouse.co/blog/does-twitch-allow-pre-recorded-streams ; https://pulsecast.tv/en/twitch-48-hour-limit (all vendors)
- https://dotesports.com/valorant/news/twitch-puts-a-stop-to-24-7-valorant-rerun-streaming (old)
- https://blog.twitch.tv/2023/06/20/introducing-content-classification-labels
- https://techcrunch.com/2023/07/10/twitch-discovery-feed-stories-tiktok-youtube-twitchcon-paris-new-features ; https://esports.gg/news/streaming/twitch-announces-its-first-discovery-feed-experiment-for-creators
- https://gamesbeat.com/twitch-ceo-dan-clancy-says-platform-doesnt-need-ai-disclosure-rules-for-now/ ; https://godisageek.com/2026/08/twitch-amazon-ai-training/
- https://www.streamscheme.com/twitch-statistics/ ; https://www.streamhatchet.com/?p=18982
- https://support.google.com/youtube/answer/16391400 (A/B test titles & thumbnails)
- https://support.google.com/youtube/answer/10059070 (Shorts, listing) ; https://ppc.land/youtube-changes-how-shorts-views-are-counted-from-march-31/
- https://gulfnews.com/technology/youtube-updates-monetisation-policies-ai-and-repetitive-content-ban-begins-july-15-1.500192660 ; https://www.plagiarismtoday.com/2025/07/08/youtube-targets-inauthentic-content/
- https://www.nbcnews.com/tech/tech-news/youtube-says-will-require-creators-label-ai-content-rcna143937 ; https://ppc.land/youtube-shifts-generative-ai-labels-to-spots-viewers-will-actually-see/
- https://newsroom.tiktok.com/new-labels-for-disclosing-ai-generated-content?lang=en ; https://tubefilter.com/2024/05/09/tiktok-transparency-labels-for-generative-ai-content/
- https://vidiq.com/research/youtube-upload-frequency-study/ ; https://www.overseeros.com/blog/how-often-should-you-post-on-youtube
- https://www.netinfluencer.com/youtube-debunks-common-myths-about-shorts-as-format-gains-traction/ ; https://blog.eklipse.gg/basic-knowledge/youtube-shorts-vs-long-form-gaming-which-grows-faster.html (vendor)
- https://nerdbot.com/2026/06/11/how-to-get-more-viewers-on-twitch-what-actually-works/

Community, tools, marketing:
- https://support.discord.com/hc/en-us/articles/33023827550359-Discord-Server-Setup-Guide (listing only)
- https://www.xda-developers.com/twitch-shield-mode-one-click-enhanced-protection ; https://esports.gg/news/streamers/what-is-twitchs-new-shield-mode ; https://blog.brandbastion.com/how-to-set-up-twitch-moderation-and-keep-chat-safe
- https://gameworldobserver.com/2025/03/11/steam-page-launch-guide-wishlists-zukowski ; https://unity.com/blog/tips-strategies-for-marketing-indie-games
- https://presskit.gg/blog/indie-game-press-kit-guide ; https://www.wayline.io/blog/game-developer-press-kit-guide-tips ; https://gtstu.com/indie-game-press-kit/
- https://www.steampageanalyzer.com/blog/reddit-indie-game-marketing ; https://gtstu.com/?p=5080 ; r/gamedev wiki mirror text via search result
- https://tvtechnology.com/equipment/blackmagics-davinci-resolve-vs-davinci-resolve-studio-which-is-right-for-you ; https://motionarray.com/learn/davinci-resolve/davinci-resolve-price-free-vs-studio/
- https://www.capterra.com/p/168956/Canva/pricing/ ; https://stylefactoryproductions.com/blog/canva-pricing

### 8.2 Pages unreachable or not read
- **All** pages: no full-page fetch succeeded (DNS and proxy errors for en.wikipedia.org, www.npr.org, help.twitch.tv, support.google.com, www.tubefilter.com). Every claim above is therefore summary-level.
- Specifically **not read at primary level**: Twitch help (Rerun, 24/7, Community Guidelines, AI), YouTube Help (inauthentic content, altered/synthetic), TikTok Community Guidelines (2026), Discord support articles, Blackmagic pricing page, Epidemic Sound terms, vendor licence pages for OBS, Kdenlive, Audacity, Reaper, Krita, Inkscape. Licences listed for those tools in §4.2 are from general knowledge and marked **[UNVERIFIED]**.
- **Not found at all:** any official post-mortem for Choice Chamber/Stream Raiders/Marbles on Stream; any credible viewer or retention numbers for 2026 crowd-played games; any sourced benchmark for clip performance, shorts-to-stream conversion, or press-kit response rates; any credible price range for commissioned game art.
- A Q-MKT-3 note and a PLATFORM-REALITY-CHECK note already flag many of these as unreachable; this file does not resolve them.
