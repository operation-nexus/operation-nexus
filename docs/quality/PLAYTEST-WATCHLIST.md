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
