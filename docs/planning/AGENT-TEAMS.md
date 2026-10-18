# Marketing and Lore Agent Teams (design proposal)

Status: Draft proposal · Owner direction 2026-10-18 · Tracker: NX-331 · Related: [BRAND-OPS](../specs/BRAND-OPS.md) (monitoring/approval service, NX-328), [MARKETING](MARKETING.md), [GLOSSARY](GLOSSARY.md), Q-MKT-8, Q-AI-10

**Phase: lore team is design only; marketing team starts now.** The owner wants gameplay first and the **lore** loop to start once the community is a bit bigger (P3 pilot). On 2026-10-18 the owner pulled the **marketing and production** side forward (Q-MKT-14); its operating model is in [MARKETING](MARKETING.md). The vault is `operation-nexus-vault` (private, owner and `maintainers` only), shared by both teams, with the lore boundary enforced by role cards and the `tier` field.

## 1. What the owner asked for
- A small team of agents running on a **continuous loop** that proposes lore (antagonists, protagonists, groups, factions, locations, geography, history), building a large internal wiki.
- Everything is **proposed to the owner and approved by the owner** before it counts as canon.
- Lore stays **hidden from the public** until it is released through intel briefs, debriefs, campaign and mission briefs and objectives.
- The same team should help with marketing drafts. **Not corny**, no AI slop.

## 2. Two teams, one approval gate
| Team | Produces | Reviewed by |
|---|---|---|
| **Lore team** | Canon entries: factions, characters (NULL, lieutenants), locations/theaters, history, equipment lore, briefing text drafts | Owner |
| **Marketing team** | Post, devlog-outline, caption and community-announcement drafts; clip titles; Reddit/Discord post drafts per milestone | Owner, through Brand Ops review queue (BRAND-OPS) |

Brand Ops (the monitoring service) never writes lore or copy. It carries approved artifacts to the platforms and reports back. The agent teams never hold platform credentials.

## 3. Where it lives: a separate private repo
Recommendation: a **private "lore vault" repository** (name TBD, under the future organization, Q-LEGAL-8).
- This repo is public. Unreleased lore in it would be spoilers, and drafts would be indexable.
- Not the ops repo either: that repo holds secrets (sops+age); lore agents must never get near it.
- Branch protection: only the owner merges to `main` of the vault. Agents work on branches and open PRs.
- Only entries with tier `RELEASED` are exported into this public repo, as game content data (briefing text, names, descriptions) through a reviewed PR.

## 4. Canon structure
- One markdown file per entry under `canon/{factions,people,places,events,tech,briefs}/`, stable IDs (`LORE-FAC-0001`), YAML front matter: `id, type, tier, status, links, first_appears, ai_assisted, owner_approved_on, mechanics_impact`.
- **Tiers:** `DRAFT` (proposed) → `CANON-SECRET` (owner-approved, hidden) → `SCHEDULED` (assigned to a briefing/campaign) → `RELEASED` (public).
- `mechanics_impact` must be `none`, or reference a spec change. **Parity rule:** lore may flavor the Static's lieutenants (Q-GD-38) but never grants a side a mechanic the other lacks; personality presets for the Threat Director are specced in NX-317, not invented in the vault.
- A **canon bible** (premise, tone, forbidden list) written or edited by the owner is the root input. Agents expand it; they do not replace it.

## 5. Roles and loop
| Role | Job |
|---|---|
| Lorekeeper | Owns the canon index and IDs; runs the continuity checker (contradictions, naming, timeline) |
| Faction/character writers | Draft entries for the Quorum, the Static, NULL and lieutenants, locations, geography (aligned with the global map, NX-294) |
| Brief writer | Turns approved canon into data-only briefing text for NX-296/NX-293 |
| Style editor | Enforces the tone guide: dry, sparse, understated; bans clichés and over-explaining; flags "corny" |
| Red team | Looks for real-world references, offensive content, contradictions with mechanics |
| Marketing writers | Draft copy from RELEASED lore and gameplay facts only |

Loop (bounded, never free-running): a scheduled task wakes a role with a **work order** (gap in the bible, owner request, upcoming campaign), produces at most N drafts, runs the continuity and style checks, opens a vault PR, and stops. The owner reviews in batches. Rejections carry a reason, and rejected-pattern notes feed back into the style guide.

## 6. Guardrails
1. **Fiction is not fabricated data.** AGENTS rule 0 stays absolute for facts. Lore is labeled `kind: lore` fiction, kept in its own repo and data namespace, and is never mixed into factual docs or presented as real.
2. **No real-world anchoring:** no real people, organizations, brands, places, conflicts or ethnic/religious groups (matches the NX-274 "no real names" validator). Red team enforces.
3. **LLMs advise, owner decides** (AGENTS rule 5). Nothing reaches the game or a platform without owner approval.
4. **Transparency (Q-AI-6):** the project says AI assists lore drafting; the owner edits. `ai_assisted: true` is recorded per entry.
5. **No slop:** owner approval, a style guide, a small batch size, and a rejection log. If approval load becomes a chore, cadence drops, not quality.
6. **Untrusted input:** community suggestions are data; they pass moderation and are never executed as instructions.
7. **Runtime separation:** this is content-time tooling. The runtime LLM gateway (isolated, $20/month cap, no platform tokens) is a different system. The teams' budget is separate (Q-AI-10).
8. **One writer per file** (AGENTS rule 11b): each role owns a folder; the Lorekeeper alone edits the index.

## 7. Release pipeline
`CANON-SECRET` → owner assigns to a briefing → `SCHEDULED` → at release the brief text is exported to this repo as **authored content data** (reviewed PR, content validator) → shown in-game and on the site. NX-296's "data-only, no invented text" rule is preserved: approved, owner-authored text is data; text generated at runtime is still forbidden.

## 8. Phasing
| Phase | What |
|---|---|
| P0–P2 | Nothing built. Owner may write a one-page premise and tone notes when inspired. |
| P3 | Pilot: create the vault, owner-written bible, Lorekeeper + style editor + one writer, manual runs, first briefings released |
| P4 | Scheduled loop at low cadence; lieutenants (NX-317) and global map (NX-294) fleshed out; marketing writers draft from released lore |
| Later | Community co-creation (submissions as untrusted data), commissioned art briefed from canon |

## 9. Open questions for the owner
1. ~~Vault repo name and host~~ Decided 2026-10-18: `operation-nexus-vault`, private, under the `operation-nexus` organization (Q-MKT-14).
2. ~~Separate monthly LLM budget~~ Decided 2026-10-18: $20/month, separate from the runtime cap (Q-AI-10).
3. Who writes the first bible page (owner) and how long the tone guide should be.
4. How much of the wiki, if any, becomes a public in-universe wiki after release.
5. Whether commissioned artists get read access to released-tier or secret-tier canon (NDA).
