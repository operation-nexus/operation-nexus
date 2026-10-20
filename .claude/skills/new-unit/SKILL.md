---
name: new-unit
description: Add a new unit, weapon or facility kind (radar, air-defense site, missile-interception site, a new jet or truck), or change one's combat stats, to Operation Nexus as a unit-catalog entry through the content pipeline, with no kernel code. Use when someone asks for a new unit, platform, facility or site kind, or a variant of one.
---

# Author a catalog entry

A new unit or facility kind is **data, not code** (CONFIG-AND-CONTENT §7a, GAMEPLAY §5b, SIM-CORE §4). This skill
walks you from a plain description to a proposed catalog entry that matches the specs exactly. Read first:
CONFIG-AND-CONTENT §5 (hot-reload), §7, §7.2, §7.3, §7a, §11.2; CONTRACTS §3.3 (`UnitKind`); GAMEPLAY §0, §5b;
COMBAT (all of it, especially §5.1, §5.7); FOG-OF-WAR; AGENTS.md rules 0, 6, 6a; `docs/quality/DATA-INTEGRITY.md`.

**Planning phase.** `content/units/`, `tools/config_lint` and the balance harness (NX-031) don't exist yet. Until
their tracker items start, the entry lands as a row in the CONFIG-AND-CONTENT §7.3 table plus the `UnitKind` value in
CONTRACTS §3.3, and the YAML draft goes in the PR description. Don't create `content/` early (AGENTS.md §3). Once the
tools exist, run them and paste the commands and output (DOC-4). Never say a check passed that you didn't run.

## 1. Can data do it?

The catalog composes existing capability blocks only: domain, speed, altitude bands (`alt_bands`, `default_alt_band`),
hp, armor, evasion, crew, threat, sensor, weapons (§7.2: `targets` are domains plus `STRUCTURE`, `bands` is altitude
reach, `damage`), cargo, capture, stealth, costs. Map every behavior in the request to a field. If one doesn't
map (it needs a new targeting rule, a new entity type, a new damage rule), that part is a **new capability**: it needs
a spec change approved by the owner and a code PR (AGENTS.md rules 1–2). Say so, split it out, and author only what
data can express. Don't stretch a field to fake a capability.

## 2. Unit or facility?

| | Unit | Facility |
|---|---|---|
| Domain | AIR, GROUND (SEA is P3) | always `STATIC` |
| Placement | spawned at a base | pre-placed by the theater file with a `base_id` (CONFIG-AND-CONTENT §9) |
| Side | fixed `side` in the catalog | follows its base's owner; switches side, keeping damage, when the base flips (Q-GP-25) |
| Capture | per `can_capture` | never captured on its own; `can_capture: false` |
| Run by | `playable_by` | the base owner's AI |

A facility has hp and damage states and is struck, disabled and repaired like any unit (GAMEPLAY §5b, §6a).

## 3. Fill every field

Use the §7.1 schema field for field, plus §7a `category` (and optional sanitized `icon`), plus each new weapon in
§7.2. Rules:

- **No invented stats.** Every number is `TBD` and carries `# PROPOSED – unvalidated` (DI-7, DOC-2) until the harness
  validates it. Relative intent ("longer range than the SAM variant") is fine as a comment; a made-up number is not.
  Values that follow from the kind itself are not guesses: `domain: STATIC`, `alt_bands` only for AIR, `fuel_s: null`
  for STATIC, `can_capture: false` for a facility. Say why for each.
- **Stat envelope.** Each value must sit inside the configured min/max bands (§7a). The band keys are not defined in
  §6 yet; say so in the PR rather than inventing them.
- **Names.** `kind` is plain UPPER_SNAKE (GAMEPLAY TS-4). No real-world names (Q-PROD-5); display names come from
  `display.label_key` and the brand guide (Q-NAME-2). `display.symbol` must exist in the overlay symbol manifest, so
  write `TBD` until it does.
- **Roles.** If viewers can `!join` it, it needs a `Role` and a `roles:` mapping, which is a new command value:
  contract, parser and handler in one PR (rule 6a). Otherwise leave `roles:` alone.

## 4. Edits that land in the same PR

1. CONFIG-AND-CONTENT §7.3 row (and §7.2 weapon entries if new).
2. CONTRACTS §3.3 `UnitKind`: add the value to the spec table **and** to `contracts/common/enums.json`, bump
   `contracts/VERSION`, run `make contracts` and commit the regenerated types (contracts/README.md checklist).
   Catalog kinds must equal the enum exactly; `config_lint` checks it (§11.2). Removing a kind removes both, together.
3. Any spec section whose rule mentions the kind (e.g. GAMEPLAY §5b for a facility, FOG-OF-WAR for a sensor).
4. `docs/quality/PLAYTEST-WATCHLIST.md` row if it introduces a new mechanic or a simplification to revisit (step 7).
5. COMBAT §5.1 who-can-shoot-whom table: add or change the kind's row so it matches its weapons' `targets:`. The
   matrix test fails CI when the table and the content disagree (Q-CBT-15).
6. Any change to a combat stat (`hp`, `armor`, `evasion`, `threat`, a weapon's `base_pk`, `damage`, `range_m`) attaches
   the balance-diff report (CONFIG-AND-CONTENT §11.4) once the harness exists; until then say it wasn't run.

`TRACKER.md` and `OPEN-QUESTIONS.md` are shared files: if you are a parallel session, list the edits you need in the
PR description instead (AGENTS.md rule 11b).

## 5. Parity (GAMEPLAY §0)

State in one or two sentences how the kind works for both the Quorum (COALITION) and the Static (ENEMY). A facility
gets parity for free (its side follows the base). A unit with `side: COALITION` or `ENEMY` only must name its
counterpart or justify the asymmetry in the spec.

## 6. Fog-of-war note

Write down: what its `sensor` reveals and to which side (a radar extends its side's view, FOW-4); whether the other
side knows its position by default or only by detection (FOW-10 covers nodes, not facilities, so don't assume);
whether it emits (SEAD homes on emitters, COMBAT §5.3a) or can go dark; and that the director only sees it through
the enemy-side view (FOW-4). Any rule the specs don't already state is an open question, not a choice you make.

## 7. Config keys and rollout

- List every `balance/` key the kind reads (e.g. `logistics.repair_rate.<node_kind>` for a facility) with its HR status (§5). A new
  key goes in the §6 table and the schema together (§11.2 drift check).
- Unit stats and the catalog are **not** hot-reloadable. Mid-campaign a new kind can only be added through a logged
  `STAFF_CONTENT_LOAD{content_hash}`, additive only (§7a). A facility also needs a theater file to place it, so in
  practice it arrives with a new campaign or theater. Say which applies.
- New mechanic or a deliberate simplification → add a PLAYTEST-WATCHLIST row: Watch, Decision, Revisit if, Source.

## 8. Gaps to raise, not fill

These are open in the specs today. Hit one → add a question to OPEN-QUESTIONS (or list it in the PR) and leave the
field `<OPEN: Q-…>`:

- §7.1 `side` is `COALITION | ENEMY | ANY` and `playable_by` is `VIEWER | AI_GARRISON | DIRECTOR`; neither expresses
  "follows the base" or "base owner's AI" for facilities.
- §7.1 has one row per unique `kind`, but CONTRACTS §3.3 says `AIR_DEFENSE_SITE` has catalog *variants* (AAA, SAM).
  How a variant is expressed is undefined.
- `loadout_cost` for a pre-placed facility (rearm cost?) is undefined.
- Stat-envelope band keys (step 3).

## 9. Done means

The §7.3 row, the `UnitKind` value, the YAML draft (or `content/units/<kind>.yaml` once it exists), parity
statement, FoW note, key list with HR status, watch-list row if needed, gaps raised, every stat `TBD`/PROPOSED, and
any validator or harness output you actually ran. The PR targets `develop`; balance values stay PROPOSED until the
harness runs (CONFIG-AND-CONTENT §11.4). Owner or admin approval is a §7a gate: never publish content yourself.

## Worked example: missile-interception air-defense site

Request: "a defense site that shoots down incoming missiles, as an AIR_DEFENSE_SITE variant".

**Step 1.** Shooting down missiles needs missiles to be targets. Shots are not entities: a fired shot is a pending
impact, and intercepting projectiles "come later" (COMBAT CB-2, Q-GP-7, Q-GP-12). §7.2 `targets` lists domains only.
So interception is a **new capability**: spec change + code PR, raised with the owner. What data can express today is
the site itself (STATIC, attached to a base, sensor, an anti-air weapon against `AIR`).

**Step 2.** Facility. **Step 8 gaps hit:** variant mechanism, facility `side`/`playable_by`, `loadout_cost`, envelope
bands. The draft below writes it as its own row with a working name only to show the fields; replace with whatever
the owner decides for variants.

```yaml
- kind: <OPEN: variant of AIR_DEFENSE_SITE or own kind; working name only>
  side: <OPEN: facility side follows base, §7.1 can't express it>
  domain: STATIC                      # facilities are always STATIC (Q-GP-25)
  playable_by: <OPEN: base owner's AI, §7.1 can't express it>
  display: { symbol: TBD, label_key: TBD }   # symbol must exist in the overlay manifest
  category: SITE                      # §7a category
  speed_mps: 0                        # never moves (STATIC facility), not a balance value
  hp: TBD                             # PROPOSED – unvalidated
  fuel_s: null                        # not modeled for STATIC (§7.1)
  sensor: { radius_m: TBD, masking: TBD }   # PROPOSED – unvalidated
  weapons: [<new weapon id, TBD>]     # anti-air against AIR only until interception exists
  cargo: null
  can_capture: false                  # facilities are never captured on their own (GAMEPLAY §5b)
  stealth: TBD                        # PROPOSED – unvalidated
  loadout_cost: <OPEN: meaning for pre-placed facilities>
  cp_value: TBD                       # PROPOSED – unvalidated
```

Weapon (§7.2): `targets: [AIR]`, every other field `TBD` and PROPOSED; `homes_on_emitters: false`.

- **Same PR:** §7.3 row, `UnitKind` value (once the variant question is answered; if it's a variant there may be no
  new enum value), §7.2 weapon.
- **Parity:** follows its base's owner, so either side holds it on the same rules.
- **FoW:** its sensor feeds its owner's view; whether it emits and can blink like the SAM variant, and whether the
  other side knows its position before detecting it, are open questions.
- **Keys:** none new for the data part; the interception capability will add its own keys with its spec.
- **Watch list:** the data part adds no new mechanic. The interception capability, when specified, revisits the
  existing "Shot flight time" row (Q-GP-7, Q-GP-12) rather than adding a duplicate.
- **Rollout:** not hot-reloadable; arrives with a theater that places it, at a new campaign.
