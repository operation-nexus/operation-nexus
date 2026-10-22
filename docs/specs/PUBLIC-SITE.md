# SPEC: Public site (phase 0: the link page)

Status: Approved (owner, 2026-10-19) · Owner: owner · Tracker: NX-351 · Related: Q-MKT-18, Q-ARCH-7, Q-ARCH-16, Q-LEGAL-6, Q-DM-4, NX-316, NX-330 · Related ADRs: ADR-0012

## 1. Purpose
A single static page at `hiveplex.live` that says what the project is, honestly says where it stands, and sends people to the Discord server and the social profiles. It is the first slice of the public site (Q-ARCH-7). Replays, leaderboards and stats come later (Q-ARCH-16, P3) and are out of scope here.

## 2. Goals / Non-goals
Goals: honest, fast, readable on a phone, no tracking, easy for the owner to change by pull request.
Non-goals: analytics (NX-330), accounts or login, a contact form, comments, a blog, any admin feature (the Command Center is a separate private app, Q-ARCH-7), anything that talks to the sim or the home network.

## 3. Requirements
- **PS-1** The page MUST be static HTML and CSS served from a free static host. It MUST NOT need a server, a database or a build step that fetches from the network at run time.
- **PS-2** The page MUST NOT set cookies, use local storage, or load anything from another origin: no third-party scripts, fonts, images, embeds or analytics (Q-DM-4). Outbound links are plain links.
- **PS-3** The page MUST NOT use JavaScript. (If this changes it needs a spec change.)
- **PS-4** Content MUST come from the owner-approved copy: name, one-line description, an honest status line, the seven profile links and the Discord invite `https://discord.gg/mSaAD3GGHh`. The status line MUST match the repo's actual state (today: in planning, nothing to play yet) and MUST NOT claim uptime, dates, players or numbers. The 24/7 claim stays off the page (owner, 2026-10-18).
- **PS-5** A contact address MAY be shown only if it is an address on the project domain that forwards to the brand mailbox. The brand mailbox itself MUST NOT be published (it is the login and recovery address for the brand accounts, Q-MKT-11). Until such an address exists, the page shows no email, and the Discord server is the contact channel.
- **PS-6** The page MUST be usable without a mouse and on a phone: semantic HTML, a visible keyboard focus, text contrast of at least 4.5:1 for body text, no content hidden behind hover, and no motion that cannot be turned off.
- **PS-7** The page MUST carry the Open Graph and title/description meta tags needed for a good link preview on Bluesky, Discord and Reddit. The exact tags are chosen from the research in the PR that builds the page.
- **PS-8** If the page contains an AI-generated image (the placeholder logo, NX-352), the page or credits MUST say so, and the image's provenance record MUST exist (NX-318).
- **PS-9** The page MUST show a short plain privacy note: the page itself collects nothing; the host may keep ordinary server logs [UNVERIFIED: depends on the host]. Full legal pages come with NX-316.
- **PS-10** Deployment MUST be one GitHub Actions workflow with least-privilege permissions, actions pinned by commit SHA, and no secrets. It is a CI workflow, so it needs the `security-review` before merge (AGENTS CLAUDE rule).
- **PS-11** The custom domain MUST serve HTTPS only. DNS records are set by the owner at the registrar (Porkbun); the spec author provides the exact record values after the host is confirmed.

## 4. Interfaces
None. The page reads nothing and exposes nothing. Source lives in `apps/site/`. The deployment workflow is `.github/workflows/pages.yml` (to be written in the build PR).

## 5. Behavior
- One screen: name, one line, status, then the Discord button, then the profile links, then the privacy note and the credits line.
- Changing the page is a pull request that goes through `ci-gate`.
- Dead links are fixed by pull request; there is no redirect layer.

## 6. Failure modes
| Failure | Effect | Handling |
|---|---|---|
| A handle changes or an account is lost | A dead link | Update the page by pull request; BRAND-ACCOUNTS is the registry |
| The Discord invite is revoked | Joining breaks | The invite was checked on 2026-10-19 and does not expire; if revoked, replace it; a check in the build PR looks for the invite code only, never fetches it at run time |
| DNS is wrong or expires | Site is down | Domain expires 2027-10-18; renewal reminder (BRAND-ACCOUNTS) |
| Host outage or policy change | Site is down | No data is lost; move to another static host (ADR-0010 neutrality) |
| Free-tier terms differ from assumed | Surprise limits | Read the host's terms before the build PR [UNVERIFIED today] |

## 7. Test plan
| Req | Test |
|---|---|
| PS-1, PS-3 | A repo check fails on any `<script>` tag or build-time network call in `apps/site/` |
| PS-2 | A repo check fails on any `http://` or `https://` URL that is not on an allowlist of outbound links, and on any `src=` or `href=` for a stylesheet, font or script from another origin |
| PS-4 | A check compares the page's links to the registry in BRAND-ACCOUNTS and fails on a mismatch |
| PS-5 | A check fails if an `@` address other than one on `hiveplex.live` appears |
| PS-6 | HTML validation plus a contrast check on the final colours; manual keyboard walk-through |
| PS-7 | A free preview tool is run on the live URL after deploy (recorded in the PR) |
| PS-8, PS-9 | Review checklist item |
| PS-10 | `zizmor` and the existing security workflow pass |
| PS-11 | Manual: HTTPS certificate valid, HTTP redirects |

## 8. Decisions and open questions
Decided by the owner on 2026-10-19: host is GitHub Pages; the placeholder C3 logo is on the page with an AI-made credit (PS-8, `apps/site/ASSETS.md`); search engines may index it; look and feel is concept B ("operations panel", chosen from three mockups).
PS-7 tags used: `description`, `canonical`, Open Graph `type`, `site_name`, `title`, `description`, `url`, `image` (+ alt) and `twitter:card=summary`. The share image is the 1024 px avatar; a wide 1200 by 630 card is a later improvement.
- Q-MKT-18 L3: the public contact address stays off the page until `contact@hiveplex.live` exists.
- GitHub Pages free terms and custom-domain DNS values: [UNVERIFIED] until the owner enables Pages and the domain (see the PR for the steps).
- The Reddit, Instagram and TikTok link URLs are the standard profile URL forms built from the registered handles; the registry stores handles only [UNVERIFIED for Reddit and Instagram, which block automated requests].
- Brand style guide (NX-274) may later change the look.
