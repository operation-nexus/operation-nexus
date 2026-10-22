# Playtest watch list

Things the specs deliberately simplified or set to PROPOSED values, to re-check in playtests and with the balance harness (NX-031). Each entry names the decision and what would make us revisit it. Add an entry whenever a decision says "revisit if…". This list is not a spec; changing a rule still goes through the owner (AGENTS.md rule 2).

| Watch | Decision | Revisit if | Source |
|---|---|---|---|
| Single supply number | One fungible `stock` per node, no fuel/ammo/parts split | Logistics feels boring, or convoys have nothing to choose between | Q-GP-11 |
| Quiet-stream capture | `capture.quiet_floor` 0.6, `quiet_ref` 50, `min_time_s` 30, exponent 0.5 | A 5-viewer stream stalls for hours, or 50+ viewers flip bases too fast | Q-SIM-26, Q-GP-4 |
| 500 viewer units | `slots.max_viewer_units` 500, FIFO queue with milestone feedback | Overlay unreadable near the cap, or the queue wait feels too long | Q-SIM-6, Q-SIM-12 |
| Queue idle timeout | 15 real minutes without chat leaves the queue | Viewers who lurk while waiting lose their place too often | Q-SIM-12 |
| Hit-probability factors | Only track quality, range, evasion and terrain are implemented; the rest are 1.0 (FB-6) | Fights feel flat, or jammers, countermeasures and weather are missed | Q-GP-6, Q-CBT-10 |
| Pk cap and range falloff | Cap 0.95; full Pk to 50% of range, 0.5 at max range | Long shots feel pointless, or close shots feel automatic | Q-CBT-10 |
| Terrain masking and evasion | Masking 0.5 for NOE/LOW/ground; evasion 0.6–1.0 per kind | Low flying is always or never worth it; fighters are unkillable or paper | Q-CBT-11, Q-CBT-12 |
| Wreck timeout | Disabled units removed after 600 s game time, no field repair | Commanders wait too long to rejoin, or wrecks clutter the map | Q-CBT-14 |
| Campaign time limit | 72 h default, owner/Admin extensions capped at 48 h total, no unlimited mode | Wars routinely hit the limit, or viewers ask for endless campaigns | Q-TEST-6, Q-TEST-7 |
| Balance thresholds | Max 40% kill share per kind; adversarial shift < 20%; overnight-0 loses ≤ 1 node in 12 h | The first harness runs show these are trivially met or impossible | Q-TEST-8 |
| Static threat score | Fixed per-kind `threat` drives target priority | Units ignore the obvious danger (an attacker, an emitting SAM) | Q-CBT-16, Q-CBT-17 |
| Shot flight time | Impact after range/speed, Pk rolled at impact, no projectile entity | Viewers can't follow what hit what, or SAM intercepts are wanted | Q-GP-7, Q-GP-12 |
| Damage-state thresholds | Damaged < 70%, Mission-kill < 35%, Disabled < 10% of hp | Units spend too long or too little time in a state | Q-GP-8 |
| No Stalemate | Time limit gives a score winner; only an exact tie is a draw | Wars end in meaningless narrow wins | Q-GP-10 |
| Plain FIFO queue | No first-timer boost, no queued `!scout` | First-time viewers bounce from long queues | Q-GP-9 |
| AI resupply cadence | Trucks only; the AI garrison runs resupply jobs at 0 viewers | The idle war starves to a halt, or AI convoys make humans unnecessary | Q-GP-16 |
| Job priority | Flat table per job type × urgency (supply, danger, objective) + aging | NEEDED list looks wrong to viewers, or units pile onto one job | Q-GP-20 |
| Auto-tasking on `!join` | No parameters = take a job at once; a node = go there; `hold` = wait | New viewers don't realise they can choose a target | Q-GP-23 |
| Facilities as separate units | Radars, air defense and factories are STATIC units attached to a base, not part of the base | It feels fiddly on stream, or bases and facilities should merge (owner is not fully settled) | Q-GP-25, Q-GP-27 |
| Idle drift | At 0 viewers the Static slowly gains ground but cannot take the last forward airbase | The morning crowd finds too much lost, or the drift is invisible | Q-GP-28 |
| Spawn location | Free sanctuary spawn; forward deploy only from surplus | Players feel stuck far from the front, or forward bases never qualify | Q-GP-41 |
| Single supply source | Stock only from the sanctuary by truck; factories parked | Convoys from one source can't keep the front alive | Q-GP-41 |
| Follower credit | Capped share of the leader's outcome merit | Follow chains become merit farms, or followers feel unrewarded | Q-GP-42 |
