> **Status (2026-10-18): agent-compiled research, NOT verified.** Read from READMEs, commit lists and Anthropic docs, not from skill or script source. Licenses, star counts and dates are as displayed on the pages at the access date and may be wrong. Every tool here is a **candidate**: nothing is adopted until the PR that adds it passes the AGENTS rule 8 check (why, license, maintenance, alternatives) and, for skills, reads the source. Decisions that use this report: Q-MKT-15 in [OPEN-QUESTIONS](../planning/OPEN-QUESTIONS.md). Not yet read from primary sources: Reddit and Discord self-promotion rules [UNVERIFIED].

# Skills, plugins and tools for the Nexus vault workflows

Access date for every claim: 2026-10-18. Method: WebSearch plus WebFetch of GitHub pages and Anthropic docs. `gh` API was blocked in this session ("GitHub access not enabled"), so star counts, licences and commit dates come from rendered GitHub pages. I did not install or run anything, and I read READMEs and commit lists, not SKILL.md bodies or script sources. Treat every "install surface / security" line as README-level, not code-reviewed. Where a field is "not shown" the page did not display it; I did not guess.

Registry searches: SearchSkills (voice/style keywords) returned nothing. SearchPlugins returned only Anthropic's Marketing plugin and unrelated community ad-tech plugins (listed under B). SearchMcpRegistry was not available in this session.

Key constraint found: the scheduled sessions run in the cloud, so they cannot see footage on the owner's disk. Anything touching ffmpeg/whisper on real footage is a local desktop job; the cloud job can only produce text artefacts (outlines, shot lists, briefs, SRT proofreading).

---

## A. Official guidance (area 8 and 9): authoritative, use directly

**A1. Skill authoring best practices** (Anthropic) - https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices (read in full 2026-10-18)
- `name` max 64 chars, lowercase/digits/hyphens, cannot contain reserved words "anthropic" or "claude". `description` max 1,024 chars, third person, what + when.
- Only name+description preload; SKILL.md loads when relevant; other files load on demand. Body under 500 lines. References one level deep from SKILL.md; files over 100 lines get a table of contents.
- Scripts: "more reliable than generated code, save tokens, ensure consistency"; the script's code is not loaded, only its output. Say whether Claude should execute or read it. Prefer scripts for deterministic operations. Scripts must handle errors, not defer to Claude; no unexplained constants.
- Degrees of freedom: low freedom (exact script) for fragile steps, high freedom for judgment steps.
- Validate-then-act: plan file, validate with script, execute. Build 3 evaluations before extensive docs; test on Haiku, Sonnet and Opus.
- Verdict: ADOPT as the house standard for every vault skill.

**A2. Claude Code skills reference** - https://code.claude.com/docs/en/skills (first ~100k chars read)
- Frontmatter fields confirmed: `model`, `context: fork`, `agent`, `disable-model-invocation`, `allowed-tools`, `paths`.
- `description` plus `when_to_use` are truncated at 1,536 chars in the listing. Put the key use case first.
- Body loads only on use; stays in context after. After compaction only the most recent invocation of each skill is re-attached, first 5,000 tokens each, 25,000 tokens combined.
- `` !`cmd` `` runs a shell command before the skill reaches Claude and substitutes its output: a deterministic step that costs no model turn. A failed command aborts the invocation. Disable via `disableSkillShellExecution`.
- Skill `model` override lasts only for the current turn.
- Verdict: ADOPT. Design implication: put deterministic steps (lint, git log, validators) in `!` blocks or scripts.

**A3. Subagent model selection** (area 9) - https://code.claude.com/docs/en/sub-agents (first ~100k chars read)
- `model` accepts `sonnet`, `opus`, `haiku`, `fable`, a full model ID, or `inherit`.
- Resolution order (docs): per-invocation `model` param, then definition frontmatter, then `CLAUDE_CODE_SUBAGENT_MODEL`, then the main conversation model. Before v2.1.251 the env var came first. A third-party blog I searched claimed the env var wins; the official doc contradicts that for current versions. Trust the doc and pin the CLI version.
- `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` plus `CLAUDE_CODE_SUBAGENT_MODEL` forces one model on all subagents (needs v2.1.257+).
- Built-in Explore does not use the env var alone; override by defining your own subagent named `Explore` with `model: haiku`.
- `.claude/agents/*.md` frontmatter has `tools:` for least privilege and a `skills:` field that preloads full skill text into the subagent (up to 32 names). Combined non-built-in subagent descriptions should stay under 15,000 tokens.
- Docs say routing work to a cheaper model such as Haiku is a documented cost control.
- Proposed pattern (my recommendation, not tested): deterministic scripts do mechanical work with no model; a `haiku` subagent for mechanical text chores (SRT cleanup, link/claim extraction, formatting); `sonnet` main thread drafts from the owner's notes; a separate fresh-context reviewer subagent (different `model` or at least separate context, `tools: Read, Grep, Glob` only) checks the draft against the voice file and the Vale report. Whether Haiku can hold the owner's voice is unmeasured; test it per A1's "test on all models" rule before relying on it. Our repo already has `reviewer` and `fact-checker` subagents; reuse the pattern.

---

## B. Writing in the owner's voice and anti-slop (area 1)

**B1. Vale** - https://github.com/vale-cli/vale (earlier URL errata-ai/vale redirects here)
- What: prose linter, single Go binary, offline linting, Markdown/AsciiDoc/rST/HTML, also commit messages and code comments.
- Licence: MIT. Stars 6.3k. Last commit shown 2026-10-16 (jdkato). Latest release version not shown.
- Install surface: CLI binary. `vale sync` downloads style packages (the only network step; pin versions).
- Security: local, no telemetry stated on the page ("Nothing leaves your machine"). Supply chain: the binary plus any style packages you sync; pin by release zip URL.
- Fit: exactly the "script for deterministic step, zero tokens" slot. Runs in a `!` block or CI, returns a short report.
- Verdict: ADOPT (CLI). Reason: free, deterministic, and it lets a cheap model draft while code, not a model, flags the tells.

**B2. tbhb/vale-ai-tells** - https://github.com/tbhb/vale-ai-tells
- What: Vale style package. 137 rule files in prose style `ai-tells`, 15 in `ai-tells-commits`, separate experimental structural package (count not shown). Flags overused vocabulary ("leverage", "seamlessly"), rhetorical formulas, filler, em-dash use.
- Licence: MIT. 119 stars, 290 commits. Last commit 2026-10-11 (page); latest release not confirmed, README example pins v1.37.0.
- Install: `.vale.ini` Packages entry, `vale sync`.
- Security: data files only (YAML rules). Authored commits include an "agent" account (tbhb-agent), so review diffs on updates.
- Fit caveats (from README): all rules default to `error`; some rules are broad and the README says to suppress noisy ones; it "targets technical documentation rather than creative or marketing writing", so false positives on devlog/lore voice are expected. No false-positive rate is claimed.
- Verdict: VENDOR-AND-ADAPT. Pin a release, copy the rule files, downgrade most to warning, delete rules that hit the owner's genuine habits, add owner-specific bans. Reason: best-evidenced maintained tell-list, but needs tuning to a voice.

**B3. thrash-d/slop-linter** - https://github.com/thrash-d/slop-linter
- What: Vale rules plus a Claude Code PostToolUse hook that lints after Write/Edit and exits 2 to send hits back to Claude.
- Licence: MIT. 1 star, 42 commits, last commit date not shown. Hook is PowerShell 5.1, "not tested under PowerShell 7 on macOS or Linux", so it will not run in the Linux cloud sessions as-is.
- Verdict: STEAL-IDEAS-ONLY. Reason: the "block until lint is clean" hook idea is good; the code is Windows-only and unproven. Write a small bash hook.

**B4. blader/humanizer** - https://github.com/blader/humanizer
- What: skill that rewrites text to remove AI-writing patterns, based on Wikipedia's field guide. README: 26 patterns in six categories (search snippets said 29/33 in other versions; counts differ by version). Supports calibrating to 2-3 paragraphs of your own writing.
- Licence MIT. Stars about 58.1k (page). Last commit 2026-10-16 (README edits only in the latest four; last non-README merge 2026-09-28). 1 open issue, 5 open PRs.
- Install: plugin (needs Claude Code 2.1.142+) or `npx skills add`. Has `scripts/` and `agents/` folders whose contents I did not see; `npx` fetches from the network.
- Fit: it is a rewriter. Rewriting by an LLM to "sound human" is the opposite of our rule that the owner speaks in their own words, and a rewrite pass can launder slop rather than remove it.
- Verdict: STEAL-IDEAS-ONLY. Reason: use its pattern list and voice-sample idea as a checklist feeding Vale rules and the reviewer; do not run it as an auto-rewriter.

**B5. Wikipedia: Signs of AI writing** - https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing (first 100k of 254k chars read)
- Source list behind B2/B4. Sections: Content, Language and grammar, Style, Markup, Citations, Signs of human writing, Ineffective indicators, Historical indicators.
- Quotes: "Do not solely rely on artificial intelligence content detection tools." "Not all text featuring these indicators is AI-generated." Indicators are "only potential signs of a problem".
- Verdict: STEAL-IDEAS-ONLY (reference, not a tool). Reason: gives the honest framing: tells are prompts for a human edit, not a pass/fail detector. Footer licence not seen; Wikipedia text is generally CC BY-SA [UNVERIFIED for this page], so paraphrase, do not copy.

**B6. Voice profile builders**
- `anthropic-skills:setup-writing-style` is in this account's skill list ("learns how the user writes from their own sent messages and docs ... saved as the my-writing-style skill"). I only know its listed description; contents unverified. Risk: the profile is an account-level skill, so a scheduled cloud session may not have it. Verdict: STEAL-IDEAS-ONLY, or run it once on the owner's desktop and copy the resulting text into the vault as `voice/VOICE.md` (owner reviews), so cloud sessions read a committed file.
- Jakeschincariol/youtube-agent-skill uses `templates/voice.md` copied to `~/.claude/youtube/voice.md` (home dir, so not in a repo). Same lesson: keep the voice file in the repo.
- Anthropic Marketing plugin `brand-voice` skill: see D1.

Where I found nothing good: no tool I could verify that measures "sounds like this specific person". Vale catches generic tells only. We need our own voice file with real owner excerpts as few-shot examples (A1 says examples beat descriptions), plus owner review as the actual gate.

---

## C. Video and devlog production (areas 2, 3)

Local-only caveat above applies to all of C.

**C1. whisper.cpp** - https://github.com/ggml-org/whisper.cpp
- Transcription CLI. MIT. 54.5k stars. Last commit 2026-10-12 (examples fixes). Release tag not shown.
- Install: build from source or package; model download script fetches from Hugging Face (only network use found). Runs offline afterwards.
- SRT output: the README as fetched did not mention SRT/VTT, only timestamped console output. I believe an `-osrt` flag exists [UNVERIFIED]; check `--help` before scripting.
- Verdict: ADOPT (CLI, owner desktop). Reason: local, MIT, active; keeps footage and voice off third-party services. (Not compared against faster-whisper; I did not verify that project.)

**C2. vincentventalon/claude-code-video-editing-skill** - https://github.com/vincentventalon/claude-code-video-editing-skill
- Rough cut for talking-head video: join clips, remove silences and false starts, keep last take, whisper.cpp per sound island, outputs edited.mp4/.txt/.srt/.takes.tsv, local review page (Python+HTML), optional Remotion captions.
- MIT. 5 stars, 5 commits, last commit 2026-09-25. Very new, one author, co-authored with Claude.
- Security: ffmpeg, whisper.cpp, Python, optional Node; README says "nothing is uploaded" and that "Claude installs missing tools when needed" (auto-install by an agent is a risk; install nothing that way). Model 0.49-1.6 GB downloaded on first use. Speed claim (9 min to 1:58 in about two minutes) is the author's, unverified.
- Fit: our footage is rendered sim plus owner voice-over. Voice-over take cleanup fits; gameplay clips do not.
- Verdict: STEAL-IDEAS-ONLY. Reason: "sound decides the cut, last take wins, review page before render" is a good design; 5 commits is too thin to depend on.

**C3. 6missedcalls/video-editing-skill** - https://github.com/6missedcalls/video-editing-skill
- Bash+ffmpeg+openai-whisper scripts: trim (codec copy), jump cuts, burned captions (hormozi/standard/minimal), text overlay, speed, `edit.sh` pipeline.
- MIT. 46 stars, 3 commits, last commit 2026-02-27 (stale vs. today, about 8 months). `pip install openai-whisper`. README: no cloud calls.
- Verdict: STEAL-IDEAS-ONLY. Reason: "hormozi" caption style is the templated short-form look the marketing doc warns against; trim/caption shell scripts are short enough to write ourselves.

**C4. Kinocut (KyaniteLabs/mcp-video)** - https://github.com/KyaniteLabs/mcp-video
- Guardrailed ffmpeg MCP: 203 MCP tools, 177 CLI commands, preflight checks, per-step "video receipts". Apache-2.0. 210 stars, 1,611 commits, release 1.16.1 dated 2026-10-05, last commit 2026-10-17.
- Install: `pip install kinocut` or `uvx --from kinocut kino --mcp`; an unsigned staged MCPB package exists. README itself says local execution does not prove zero data egress; some features are opt-in (Anthropic keyframe review, model downloads). Telemetry not shown.
- Fit: 203 tool schemas is a large standing token cost; far more than a devlog needs. Rule 8 also needs a justification for a large dependency.
- Verdict: REJECT (as MCP). Reason: token cost and surface area; revisit only the CLI if plain ffmpeg scripts prove insufficient.

**C5. kevinwatt/ffmpeg-mcp-lite** - https://github.com/kevinwatt/ffmpeg-mcp-lite
- 8 tools (info, convert, compress, trim, merge, extract audio/frames, add subtitles). MIT. 28 stars, 9 commits, last commit 2026-05-08. `uvx ffmpeg-mcp-lite`.
- Verdict: REJECT. Reason: a skill with two or three tested ffmpeg commands in `scripts/` is cheaper than a standing MCP server and is reviewable.

**C6. auto-editor** - https://github.com/WyattBlue/auto-editor - Unlicense, 5.6k stars; silence/motion cutting, exports to Premiere/Resolve/FCP/Kdenlive. Last commit date, release not shown. Verdict: STEAL-IDEAS-ONLY / optional owner-side CLI; not needed for the vault itself.

**C7. Jakeschincariol/youtube-agent-skill** - https://github.com/Jakeschincariol/youtube-agent-skill
- 11 skills, six stdlib-Python scripts: `chapters.py` (chapters from SRT validated to YouTube rules), `deadair.py` (edit decision list from SRT), `title.py` (title+thumbnail lint), `hookscore.py`, `retention.py`, `swipe.py`; `hooks.json` with 21 formulas.
- MIT. 1.7k stars, 535 forks, 38 open issues; one visible commit, 2026-09-16 (made with Claude). No API key, publishes nothing.
- Honest caveats from its README: `hookscore.py` was calibrated on 74 hooks and "barely separates a creator's hits from their misses". `/yt-viral` and "virality engine" framing is the engagement-chasing pattern we want to avoid.
- Verdict: VENDOR-AND-ADAPT, selectively: `chapters.py`, `deadair.py` (EDL from SRT), and the title+thumbnail pairing lint idea. Skip viral, hookscore as a gate. Reason: deterministic stdlib scripts that save tokens; review each script first (not read in this session).

**C8. Thumbnail and shot-list skills** - AgriciDaniel/claude-youtube (https://github.com/AgriciDaniel/claude-youtube): MIT, 486 stars, 14 commits, Beta, last commit date not shown; needs optional YouTube Data API key / OAuth / Gemini key. REJECT: it brings credential surface we forbid. aabrole/claude-video-thumbnail-skill generates images via Gemini (REJECT: an image API and its key; also AI thumbnails risk slop). sergebulaev/youtube-skills (MIT per search snippet) and adityaarsharma/youtube-marketing-skills (has a live-channel MCP, so credentials: REJECT on that ground) were not opened; unverified. I found no verified tool for shot lists or devlog outlines; that is a gap (section K).

**C9. Registry plugins seen** (SearchPlugins): "video-shotcraft" (Remotion product videos, community) and "Video Cleanup" (audio/picture cleanup, local ffmpeg+Python, community). Neither evaluated beyond their directory descriptions. Verdict: not assessed; no fit evidence.

---

## D. Social post drafting and platform rules (area 4)

**D1. anthropics/knowledge-work-plugins `marketing`** - https://github.com/anthropics/knowledge-work-plugins/tree/main/marketing (also in the Anthropic plugin directory as "Marketing", authored by Anthropic, v1.2.0)
- Skills: content-creation, campaign-planning, brand-voice, competitive-analysis, performance-analytics; commands /draft-content, /campaign-plan, /brand-review, /competitive-brief, /performance-report, /seo-audit, /email-sequence.
- Apache-2.0. 30.1k stars, repo last commit 2026-10-16 (bot bumps for other plugins). Connectors: Slack, Canva, Figma, HubSpot, Amplitude, Notion, Ahrefs, Similarweb, Klaviyo, Supermetrics (plus Gmail, Google Calendar in the directory entry).
- Security: the MCP connectors are credentialed third-party services; installing the plugin wholesale conflicts with "agents never hold platform credentials". I did not read the skill bodies.
- Verdict: STEAL-IDEAS-ONLY. Reason: brand-voice documentation structure and campaign-plan template are useful references; it is built for B2B marketing teams, not a solo game dev, and ships connectors we must not enable.

**D2. nickspiz/social-post-skills** - https://github.com/nickspiz/social-post-skills
- Skills: post-basics (shared rules: facts, "invented-claims guard", topic mix, variety, final checklist), plus linkedin/x/bluesky/threads/instagram/telegram/reddit-post. Plain text only: README says no scripts, hooks, files read, or network.
- MIT. 0 stars, 0 forks, 4 commits, last commit 2026-10-12 ("check limits against official docs"). Unknown author; brand-new.
- Claims limits were checked against official docs; I did not verify those numbers. Reddit skill covers "rare links" and "community rules"; Bluesky covers alt text and links.
- Verdict: VENDOR-AND-ADAPT (post-basics, bluesky-post, reddit-post only, after reading the bodies). Reason: zero-execution plain markdown is the lowest-risk kind of dependency; the invented-claims guard matches AGENTS rule 0. Re-verify every platform number we keep.

**D3. Posting tools - all REJECT on the credentials rule:** publora/skills, STGime/posta-skill, guyaga/claude-code-social-media-skill, OpenClaudia/openclaudia-skills (multiple API keys). Seen via search only; not opened. They exist to post on the owner's behalf, which we have decided against.

**Platform rules (verified vs not)**
- Bluesky Community Guidelines, https://bsky.social/about/support/community-guidelines (read 2026-10-18): no standalone bot policy; bans spam or "repeatedly post content in ways that disrupt normal conversations"; bans "artificially manipulate features or social signals to gain unearned reach"; impersonation banned except clearly labelled parody/fan accounts; nothing general on AI-generated content. The Bluesky developer guidelines page redirected to https://bsky.network/docs/support/developer-guidelines and returned empty; not verified.
- Reddit: official spam policy and Reddit Rules pages returned HTTP 403 / blocked. Official Reddit text is UNVERIFIED. Third-party blogs call "9:1" an unofficial guideline and say per-subreddit rules decide; one rules index (threadfox.vip, "rules read 2026-09-26") said r/IndieDev's rules do not mention promotion, other blogs conflicted. Treat all as [UNVERIFIED]; each draft must carry "check the subreddit's current sidebar" as an owner step.
- Discord: not researched. [UNVERIFIED]. Server-by-server rules plus Discord's developer/community policies need a primary-source pass.

Where I found nothing good: no source-cited, maintained rule set for Reddit/Discord promotion. The vault needs `platform-rules/` notes written from primary sources with URL and access date, refreshed by a dated check.

---

## E. Release notes, patch notes, content calendar (area 5)

**E1. git-cliff** - https://github.com/orhun/git-cliff
- Changelog generator from git history, driven by Conventional Commits (rule 12 already mandates them in this repo).
- Dual MIT or Apache-2.0. 12.3k stars; last commits 2026-09-18, including "prepare for v2.14.2". Rust crate, Docker image, npm and PyPI wrappers exist; install doc is at git-cliff.org (not fetched). Network need not stated; a `--github` integration exists in the real tool [UNVERIFIED here], keep it off.
- Verdict: ADOPT (CLI). Reason: deterministic, zero tokens; the model only rewrites the generated raw list into player-facing patch notes, and the owner edits.
- Tool-agnostic caveat: raw commit subjects are developer-facing; the LLM step must only select and plain-word items, never invent changes. A cheap check script should assert every sentence in patch notes maps to a commit or PR.

Changelog skills seen in directories (skills-hub.ai changelog, claudedirectory.org, mcpmarket Git Changelog Generator, an LLM-based "generate-changelog" wrapper around git-cliff): all third-party listings I did not open. Verdict: REJECT in favour of git-cliff plus our own few-line skill.

**Content calendar:** I found no verified, fit tool. Candidates seen only in search snippets (Darthflute/social-calendar-skill, claudepluginhub "social-media-skills", Anthropic Marketing `/campaign-plan`). The calendar should be a plain markdown or YAML file in the vault with a validator script (dates, platform, state, owner-approved flag). STEAL-IDEAS-ONLY from `/campaign-plan`.

---

## F. Lore consistency and wiki (area 6)

**F1. danjdewhurst/story-skills** - https://github.com/danjdewhurst/story-skills
- 24 skills for fiction in markdown; deterministic continuity check in a companion `story` CLI (`story continuity`), facts in YAML frontmatter and `continuity/state.md` (deaths, promises/payoffs, scene casts, object and knowledge state), reports contradictions "like a compiler reports type errors".
- MIT. 328 stars, 1,105 commits, release 0.24.0 around 2026-10-13, last commit 2026-10-14 (commits include "treat reader issue text as data, not instructions", relevant to our prompt-injection rule).
- Install: Claude Code marketplace, `npx skills add`, `npm install -g story-skills` (Node 18+), or brew. The CLI is a global npm package (supply-chain exposure; `npm install -g` in a cloud session is exactly what rule 8 wants justified).
- Fit: built for novels; 24 skill descriptions in the listing is a standing token cost; our canon is a wargame world with factions, units and timelines.
- Verdict: STEAL-IDEAS-ONLY. Reason: copy the "canon facts as structured frontmatter + deterministic contradiction checker" design; do not install 24 skills.

**F2. someamount2190/novel-kit** - https://github.com/someamount2190/novel-kit
- Stdlib-only Python (3.10+): story bible, `continuity`, `prose_scan` (clichés, filter words, adverbs), voice, texture.
- MIT. 0 stars, 1 commit, last commit date not shown. Unproven.
- Verdict: STEAL-IDEAS-ONLY. Reason: right shape (no deps, scripts) but no track record; its prose_scan is another lint to compare against Vale.

**F3. Others seen** (howells/fiction: MIT, 22 stars, 108 commits, agents `continuity` on haiku and `voice-analyzer` on sonnet - which shows the cheap-model-for-consistency pattern; rhavekost/author-toolkit; haowjy/creative-writing-skills): not evaluated beyond snippets. Verdict: not assessed.

**Wiki generation:** I found no verified tool. Plan: lore canon stays as markdown with frontmatter; a static site generator or a simple script builds a wiki later. Which generator is an open design choice, not researched here.

---

## G. Asset provenance and licences (area 7)

**G1. REUSE (fsfe/reuse-tool)** - https://github.com/fsfe/reuse-tool
- `reuse lint`, `annotate`, `download` (license texts into LICENSES/), `spdx`, `supported-licenses`, `convert-dep5` to `REUSE.toml`. Targets REUSE spec 3.3. Python 3.10+.
- Licence of the tool itself: GPL-3.0-or-later for source (docs CC-BY-SA-4.0, some files CC0, some Apache-2.0). Fine as an external CLI invoked on the vault; flag it under rule 8 because it is GPL. Stars 594. Last commit 2026-10-13 (translation sync); code-activity date unconfirmed. Latest release not shown (README shows `v6.2.0` only as a pre-commit example).
- The page did not explain handling of binary assets. Whether `REUSE.toml` annotations or `.license` sidecars cover binaries is from my background knowledge [UNVERIFIED]; confirm in the REUSE docs before committing to it.
- Limits: REUSE records SPDX licence and copyright per file. It does not record purchase receipts, seat or platform restrictions, credit lines, source URLs, or expiry. Epidemic Sound, for example, has terms beyond an SPDX id (see the existing EPIDEMIC-SOUND-RESEARCH).
- Verdict: VENDOR-AND-ADAPT (use as a CLI check in CI/pre-commit, vault side). Reason: standard, machine-checkable, active; pair it with our own `assets/REGISTER.yaml` (id, file hash, source URL, licence text/receipt ref, allowed uses, credit line, expiry, access date) and a validator.

No Claude skill or MCP for asset provenance turned up. This is a gap.

---

## H. Not recommended or not re-recommended

- Ponytail, grill-*, domain-modeling, finecomb, review-council, Context7, Serena, graph-memory servers: already in TOOLING.md/VENDORED.md.
- mattpocock `writing-for-agents`: listed in TOOLING.md as not yet vendored but useful; it is the closest in-hand match to A1 for writing the vault's own skills. Not re-researched here.
- Registry ad-tech plugins (Hyper Marketing, Windsor.ai, AdWhispr): ad platforms, API credentials, wrong job. REJECT.
- Any "AI humanizer" detector-evasion product: contrary to the transparency goal.

---

## I. Ranked shortlist (max 8)

1. Official skill-authoring rules (A1, A2): ADOPT as the house standard; zero cost.
2. Vale + vale-ai-tells (B1, B2): ADOPT / VENDOR-AND-ADAPT, pinned and tuned; the deterministic anti-slop gate.
3. git-cliff (E1): ADOPT; patch notes from Conventional Commits.
4. Subagent model routing + separate reviewer (A3): ADOPT as a pattern; test Haiku/Sonnet on a voice sample first.
5. whisper.cpp (C1): ADOPT on the owner's desktop; confirm SRT flag.
6. REUSE lint + own asset register (G1): VENDOR-AND-ADAPT.
7. nickspiz/social-post-skills (D2): VENDOR-AND-ADAPT after reading; bluesky/reddit/post-basics only.
8. youtube-agent-skill scripts (C7): VENDOR-AND-ADAPT chapters.py/deadair.py after code review.

Honorable mention (STEAL-IDEAS-ONLY): story-skills continuity design (F1), humanizer pattern list as a checklist (B4), Wikipedia's "tells are prompts, not proof" framing (B5), vincentventalon last-take review-page design (C2).

## J. Security and process notes for adoption

- Pin by commit SHA or release, copy into the vault (as done with mattpocock/skills), and review scripts and any hooks line by line before copying. None were read in this session beyond README summaries.
- No plugin that bundles credentialed connectors (Anthropic Marketing, YouTube suites with API keys, posting tools) should be enabled in a scheduled session. `.mcp.json` servers load without asking in cloud sessions (TOOLING.md), so keep it empty for the vault.
- Skill names must not contain "claude" or "anthropic" (A1).
- Check the network policy of the cloud environment before assuming `vale sync`, `uvx` or `npm` work there; TOOLING.md records Context7 being blocked by the proxy in cloud sessions.

## K. Gaps: we must write our own

1. Owner voice file and few-shot excerpt bank (real owner text, committed), plus a `voice-review` skill: Vale report + checklist + diff-against-excerpts, run by a separate reviewer subagent.
2. Devlog outline / shot-list / talking-points skill keyed to the DEVLOG CHECKPOINT block (nothing verified found; owner speaks the words).
3. Short-form clip packaging and thumbnail brief (text-only, no image API): title, caption lines, hook options, thumbnail brief, AI-disclosure line, checked by a `title.py`-style lint.
4. Platform-rules notes for Reddit, Discord (and refresh of Bluesky) from primary sources with URL and access date, plus a pre-post checklist skill.
5. Content calendar file format and validator script.
6. Patch-notes skill: git-cliff raw output in, plain-language draft out, with a script asserting every line maps to a commit/PR.
7. Lore canon schema (YAML frontmatter), contradiction checker script, wiki build script.
8. Asset register schema and validator (sources, receipts, allowed uses, credits, expiry), alongside REUSE lint.
9. AI-use disclosure checker: confirm each outgoing draft states what was AI-assisted, matching the existing Q-AI-6 / YouTube disclosure notes.
10. Eval set per skill (3 scenarios each, per A1) and a Haiku/Sonnet/Opus test log.
