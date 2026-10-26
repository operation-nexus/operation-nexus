# Entertainment review: upkeep (proposal mode, 2026-10-26)

Asked by the owner in #412: is upkeep worth its cost to the show, given the direction that running short of upkeep should be rare (Q-TD-50)? The `entertainment-reviewer` agent (Opus) wrote this. The lead checked the load-bearing facts against the repo: every shipped `economy.upkeep` value is 0 (`balance/default.yaml:369-378`, Q-TD-29), and NX-426 (upkeep period) is not built. Scores are estimates.

## Short answer
Keep upkeep, but change its job. With rare shortfall it can no longer cap a big crowd's army. It works as a supply-line alarm instead: units pay a small amount, and a base runs short rarely, mostly when the enemy has cut its supply. Two measured results drive this:
- **Upkeep 1 per window is far from rare.** At raid-300 it grounded 46% of viewer unit-time.
- **A pay period fixes it.** NX-426's per-kind period, prototyped at 4 windows, cut viewer grounding to 0% at prime-50 and 0.15% at raid-300.

## Runs
Every run used a scratch harness at `ae31539`, with economy rules on and both sides limited. **Nothing here is a queued harness job.**
- **CTL:** no upkeep. Same config hash as J0.
- **U1:** upkeep 1 per window on the armed kinds.
- **P4 / P30:** an in-memory prototype of NX-426 (pay every 4 or 30 windows, staggered by entity id). It is not the real feature.
- **Samples:** prime-50 ran 3 seeds × 6 h. Raid-300 ran 1 seed × 2 h, which is weak.

These runs predate NX-428, so they used the old grounding order.

**prime-50 (3 seeds × 6 h)**

| Metric | CTL | U1 | P4 |
|---|---|---|---|
| Viewer armed unit-time grounded | 0 | 6.7% | 0% |
| Windows with any viewer unit grounded | 0 | 9.2% | 0% |
| Static AI unit-time grounded | 0 | 22.1% | 1.65% |
| Static budget per window | 46.3 | 9.1 | 32.5 |
| Offensives (3 runs) | 8 | 1 | 6 |

**raid-300 (1 seed × 2 h)**

| Metric | CTL | U1 | P4 | P30 |
|---|---|---|---|---|
| Viewer unit-time grounded | 0 | 46.4% | 0.15% | 0 |
| Static budget per window | 48.5 | 16.7 | 29.3 | 45.4 |

**What the numbers show:**
1. **Shortfall is local.** In U1 at prime, all 508 coalition groundings were at west-airbase, while the pool at haven sat near its cap. Jets landed forward, so that base became their home (EC-5). A grounded jet can't REBASE back to haven (EC-6).
2. **Static upkeep starves the Director through the EC-7 reserve term.** The reserve is `upkeep_reserve_windows` × upkeep owed, and it cut the budget by 80% at N=1.
3. **The coalition has income to spare, but little at raid.** Spare is about 1650/h at prime and about 530/h at raid (derived). At upkeep 1, raid needs a period of about 15 or more to stay inside that.

## Q1. What upkeep adds and costs
**Adds:**
- **Watcher:** a readable grounding wave after a convoy raid or a bridge drop.
- **Player:** a second hauling demand, created by idle units.
- **Counterplay:** raids on Static convoys can bench Static jets.
- **Site:** "the night the west airbase went dry" stories.
- **VOD:** a setup and payoff in under a minute (cut, RTB, resupply, relaunch).

**Costs:**
- Benched viewers (46% at raid with upkeep 1).
- TS-1: income doesn't grow with the crowd.
- "6000 stock, yet my jet is grounded" reads as a bug.
- Static upkeep suppresses Offensives.

**At upkeep about 0 (today), the game loses:** grounding waves, a cost for idle units, and Q-TD-16(1)'s economic army cap. The cap matters least today, because the open problems are Offensive effectiveness and uncontested holds.

| Option | Watcher | Player | Site | VOD |
|---|---|---|---|---|
| A. Upkeep 0 (J0) | 2 | 2 | 2 | 2 |
| B. Chronic, N=1 | 2 (raid 1) | 1-2 | 2 | 2 |
| C. Rare and caused (recommended) | 2-3 | 2 | 2-3 | 2-3 |

## Q2. "Rare" as harness targets (all PROPOSED)
Targets apply at prime-50, evening-150, raid-300 and surge-500 unless noted.

| # | Metric | Target | Reported today? |
|---|---|---|---|
| R1 | Share of armed viewer unit-time grounded | ≤ 1%; 0 at quiet-5 | No |
| R2 | Share of economy windows with any viewer unit grounded | ≤ 5% | No |
| R3 | Shortfall episodes per home | ≤ 1 per 4 run-hours at prime, ≤ 1 per 2 at raid; median ≤ 10 windows | No |
| R4 | Distinct viewers ever grounded | ≤ 10% (side-level only) | No |
| R5 | Churn: groundings/h ÷ mean grounded | ≤ 3 | Derivable |
| R6 | Grounded share coming from busy units | ≤ 1% | Yes |
| R7 | Static budget and Offensives/h | ≥ 85% of a same-sha control | Yes |
| R8 | Static AI unit-time grounded | Information only, or ≤ 10% | No |
| R9 | Peak armed units ÷ peak viewers (TS-1) | Within 5% of control | Yes |
| R10 | Coalition pool below 10% of storage for > 30 min | Never | Partly |
| R11 | Episodes that follow enemy action on that supply line within 30 min | ≥ 50% | No |

## Q3. NX-426 structure and starting values
**Structure:**
- Payment is staggered across windows by entity id.
- A grounded unit retries every window.
- `owed()` returns the per-window average (cost ÷ N), or the EC-7 reserve over-reserves N times.
- The EC-11 load check uses the per-window rate.

**Starting values (PROPOSED):**
- Armed kinds: upkeep 1 with period 20 (RECON 30).
- Mirrored Static kinds get the same values (EC-3).
- Trucks and convoys: 0.
- `director.upkeep_reserve_windows`: keep 2, or use 1 if any period drops below 10.
- Surge-500 may need period 30-40.

**Next runs:** each against a new control at the NX-426 sha (prime-50 and raid-300, 6 seeds, 24 h, 12 workers). A run needs 15 overrides, within the limit of 16.

| Job | Overrides | Question |
|---|---|---|
| K0 | The 3 economy switches only (control) | Baseline at the new sha |
| K1 | The values above | Do R1-R11 pass? |
| K2 | Period 10 | Where is the knee? |
| K3 | Period 5 | The "felt" end of the range |

## Q4. Visibility
Every shortfall is a story beat, because it is rare:
1. **One base-level sitrep per episode** ("WEST AIRBASE OUT OF SUPPLY: 12 flights grounded. Haul to West Airbase").
2. **A payoff line** that credits the delivering haulers.
3. **The grounded reason** shows the base's stock, not the pool.
4. **Static shortfall** appears only when coalition sensors see the base, at sector level (FOW-13).
5. **Rate-limit** the sitreps if shortfall turns chronic.

## Suggestions
- **T1:** the Q3 values.
- **T2:** `upkeep_reserve_windows` 1 if any period is below 10.
- **D1:** the NX-426 spec readings above.
- **D2:** harness metrics R1-R4, R10 and R11, plus gross versus clipped income.
- **D3:** episode sitreps with hauler credit, and Static shortfall gated by fog of war.
- **D4:** a grounded unit may REBASE to a friendly base that can pay it.
- **D5:** a grace of G windows before grounding, with a warning.

## Risks
- Any period below about 10 makes raid shortfall chronic (est.).
- Static upkeep plus the reserve suppresses Offensives.
- Grounding at a dry forward base while the pool is full reads as a bug.
- Hauler personas are broken at raid, so harness rates may differ from real chat.

## Questions for the owner (#412)
1. With rare shortfall, upkeep is no longer the coalition's army cap (Q-TD-16(1)), and EC-8's guard becomes the only cap. Confirm?
2. Does "rare" apply to the Static too, or may coalition raids run it short more often as counterplay?
3. D4 (REBASE while grounded)?
4. D5 (grace before grounding)?
