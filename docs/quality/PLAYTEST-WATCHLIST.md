# Playtest watch list

Things the specs deliberately simplified or set to PROPOSED values, to re-check in playtests and with the balance harness (NX-031). Each entry names the decision and what would make us revisit it. Add an entry whenever a decision says "revisit if…". This list is not a spec; changing a rule still goes through the owner (AGENTS.md rule 2).

| Watch | Decision | Revisit if | Source |
|---|---|---|---|
| Single supply number | One fungible `stock` per node, no fuel/ammo/parts split | Logistics feels boring, or convoys have nothing to choose between | Q-GP-11 |
| Quiet-stream capture | `capture.quiet_floor` 0.6, `quiet_ref` 50, `min_time_s` 30, exponent 0.5 | A 5-viewer stream stalls for hours, or 50+ viewers flip bases too fast | Q-SIM-26, Q-GP-4 |
| 500 viewer units | `slots.max_viewer_units` 500, FIFO queue with milestone feedback | Overlay unreadable near the cap, or the queue wait feels too long | Q-SIM-6, Q-SIM-12 |
| Queue idle timeout | 15 real minutes without chat leaves the queue | Viewers who lurk while waiting lose their place too often | Q-SIM-12 |
| Hit-probability factors | Only track quality, range, evasion/altitude and terrain are implemented | Fights feel flat, or jammers, countermeasures and weather are missed | Q-GP-6 |
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
