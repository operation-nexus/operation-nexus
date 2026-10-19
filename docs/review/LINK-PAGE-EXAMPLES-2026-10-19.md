> **Status (2026-10-19): agent-compiled research, NOT verified.** Search was weak for this topic, so several areas have few or no examples and the report says so rather than filling them. Third-party notes on link previews for Bluesky, Discord and Reddit are unverified. It informs the draft [PUBLIC-SITE spec](../specs/PUBLIC-SITE.md) (NX-351).

# Link page research for hiveplex.live (accessed 2026-10-19)

Method: WebSearch plus WebFetch. Search was weak for "good small link pages", so section 1 and 3 have fewer real examples than asked. I did not invent any to fill the gap. Anything I could not open myself is marked [UNVERIFIED]. No code or images were copied.

## 1. Indie / dev-in-public pages

**dukope.com (Lucas Pope)** https://dukope.com/ , fetched 2026-10-19
- Does well: honest status per project via plain labels ("Beta 0.5.13", "Barely tested and possibly full of bugs"). Dry, self-deprecating tone, in-character mock-official blurbs. Socials (Twitter, Mastodon, Bluesky) sit in the footer as plain text links.
- Avoid: it is a long scroll, not one screen, and it has no Discord. Do not copy the length.
- Borrow: status as a plain-language label, and a dry voice that admits what is unfinished.

**itch.io creator profiles (pattern only)** e.g. https://gamesinstantiate.itch.io , https://danstarr13.itch.io , seen in search results only, not fetched [UNVERIFIED as to layout]. Search snippets show the common pattern: a short bio, "join the Discord for development updates", a dev-only Bluesky link. Snippets also show a Discord link that wrongly pointed at a Bluesky post. Lesson: click-test every link, and make the Discord invite non-expiring.

I found no clean, one-screen, honest-early-status link page by a real indie that I could verify. Do not treat that as proof none exist.

## 2. Crowd-controlled / stream-interactive projects

**Twitch Plays Pokemon** https://twitchplayspokemon.tv/ , fetched 2026-10-19
- What-is-this line: "a social experiment and gaming platform" where viewers collectively control Pokemon through Twitch chat. Simple vertical page: logo, stream link, short About, resource list, footer.
- Does well: short About paragraph. Footer states no ads or tracking, with a playful aside. Fits your privacy stance.
- Avoid: it has no Discord or socials link, and the resource list is long. The footer note asks for JavaScript. Yours should need none.

**Crowd Control** https://crowdcontrol.live/ , fetched 2026-10-19
- What-is-this line: "Crowd Control lets your viewers send jumpscares, keybinds, in-game effects, and more." One concrete sentence naming what viewers do.
- Avoid: marketing sections, revenue claims, testimonials, exclamation-heavy copy. This is the opposite of your tone.
- Borrow: lead with the verb ("viewers send / viewers type").

**Chat-controlled strategy games on itch.io** (search snippets only, pages not fetched, [UNVERIFIED]): Chat Fight https://frib.itch.io/chat-fight (viewers control armies through chat; the developer says the Twitch features are untested, which is honest early-status wording), Plan-It https://vykri.itch.io/plan-it-twitch-chat-game , Sea War on Stream https://spius.itch.io/sea-war-on-stream . Use them to see how others phrase "chat types commands to move units".

## 3. War-room / terminal styling and accessibility

I found no specific tasteful war-room page I could verify. I will not name one. Verified guidance only:
- Contrast (WCAG 2.2 SC 1.4.3): 4.5:1 normal text, 3:1 large text (18pt or 14pt bold). Non-text UI such as link borders and focus rings: 3:1 (SC 1.4.11, threshold inferred from the page's example). https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- Motion: write the effect, then override in `@media (prefers-reduced-motion: reduce)`. Prefer replacing motion with opacity changes over removing all feedback. Baseline widely available since 2020. https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- Retro guidance (secondary source): period-accurate low-contrast neon and tiny pixel fonts fail WCAG, so keep the look and fix legibility. https://www.superdesign.dev/styles/retro
- CRT overlay pattern (secondary source, one open-source project): drop flicker and scanlines under reduced motion, mark the decorative overlay `aria-hidden`, keep scanlines subtle. https://mintlify.wiki/apursley2012/retrowin/components/crt-overlay
- Tasteful approach (my recommendation, not sourced): monospace system font stack (no webfonts), one accent colour, thin borders, a status line like a header bar, and no animation beyond an optional blinking cursor that stops under reduced motion.

## 4. No-JS static page, meta tags, verification

Sources read:
- Open Graph spec (primary): https://ogp.me/ . Required: og:title, og:type, og:image, og:url. Optional: og:description, og:site_name, og:locale. Image extras: og:image:alt (spec says include whenever og:image is set), og:image:width, og:image:height. Example uses `<html prefix="og: https://ogp.me/ns#">`.
- Facebook (primary): https://developers.facebook.com/docs/sharing/webmasters/ . Lists og:url, og:title, og:description, og:image; advises setting image width and height; supports JPEG, GIF, PNG. Sharing Debugger at developers.facebook.com/tools/debug shows what the crawler reads and forces a re-scrape.
- Bluesky (secondary vendor guides only; the official docs page https://bsky.network/docs/advanced-guides/posts came back empty): https://htmlcsstoimage.com/features/og-images-for-bluesky , https://app.unilink.us/blog/bluesky-website-card . Claims: card built from og:title, og:description, og:image; title falls back to `<title>`; absolute HTTPS image URL; about 1.91:1 (1200x630); thumbnail cap about 1,000,000 bytes in the app.bsky.embed.external lexicon; card is stored in the post when created, so fixing tags later does not change old posts; tags must be in server HTML, not JS-injected. [UNVERIFIED against Bluesky's lexicon.]
- Discord (secondary, vendor and a code comment): https://htmlcsstoimage.com/features/og-images-for-discord ; `theme-color` meta tag sets the embed sidebar colour; Discordbot user agent must not be blocked; previews cached. No official Discord doc found. [UNVERIFIED]
- Reddit (secondary, forum and vendor): https://forum.level1techs.com/t/reddit-sharing/76617 , https://htmlcsstoimage.com/features/og-images-for-reddit . Reported order: direct image, then og tag, then largest page image. Cached. No official spec found. [UNVERIFIED]
- GitHub Pages custom domain (primary): https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site . Apex A records 185.199.108.153, .109.153, .110.153, .111.153 (AAAA optional); CNAME www to `<org>.github.io`; CNAME file only when publishing from a branch (not from an Actions workflow); Enforce HTTPS can take up to 24 hours to appear; verify the domain first and avoid wildcard DNS (takeover risk).

Free verification: Facebook Sharing Debugger (above); posting the URL in a private Discord channel or a test Bluesky draft to see the real card; Bluesky checker https://opentweet.io/tools/bluesky-link-preview-checker (third-party, not tested, [UNVERIFIED]); `curl -s https://hiveplex.live/ | grep -i 'og:'` to confirm tags are in raw HTML. X's validator URL returned HTTP 402 and I could not use it; skip X (not in your platform list anyway).

## 5. Credits / thanks sections

I could not find a verifiable small-studio link page with a credits section; none of the fetched pages had one. dukope.com has only a footer of profile links. No example to cite. Recommendation (mine): one line, plain text, at the foot, naming only things that are true and checkable (for example "Built with plain HTML. No tracking."). No credits for people or assets that do not yet exist.

## Recommended outline (single screen on desktop, short scroll on phone)

1. Status bar: "HIVEPLEX // OPERATION NEXUS // STATUS: IN PLANNING". Purpose: honest status first.
2. Name + one-line description: e.g. a verb-first sentence (stream chat commands an army against an adaptive AI enemy). Purpose: say what it is.
3. Status note: "In planning. Nothing to play yet." plus one dry line. Purpose: set expectations.
4. Links block: Discord first (the only place to talk), then the seven socials as a plain list with visible text labels and handles. Purpose: where to follow.
5. Footer: "No analytics, no cookies, no third-party scripts." and an optional one-line thanks. Purpose: privacy and honesty, trust.

## Meta tags to ship (sources: ogp.me, Facebook webmasters doc, GitHub docs; Bluesky/Discord notes are secondary)

- `<meta charset="utf-8">`, `<meta name="viewport" content="width=device-width, initial-scale=1">`
- `<title>` and `<meta name="description">` (Bluesky falls back to `<title>`)
- `<link rel="canonical" href="https://hiveplex.live/">`
- `og:title`, `og:type` (website), `og:url`, `og:image` (absolute HTTPS, ~1200x630, PNG or JPEG, well under 1 MB), `og:image:alt`, `og:image:width`, `og:image:height`, `og:description`, `og:site_name`
- `<meta name="color-scheme" content="dark">` and `<meta name="theme-color" content="...">` (Discord sidebar colour, [UNVERIFIED])
- Optional `twitter:card` = `summary_large_image` only if you care about X; I did not verify X's current behaviour.
- Inline `<style>` only; `@media (prefers-reduced-motion: reduce)` and `:focus-visible` outlines; no JS.
- Put a `CNAME` file in the published branch root if publishing from a branch.

## Gaps

No verified war-room-styled example, no verified credits example, no official Bluesky/Discord/Reddit preview documentation. Test the real cards after deploy.
