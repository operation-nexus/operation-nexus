# Entertainment review

A structured check of how entertaining the game is, run at the end of every phase and at major checkpoints (Q-DEV-22). Tests prove the sim is correct; this review asks whether anyone would want to watch or play it. It produces notes and suggestions, never rule changes: a suggestion becomes a change only through the owner (AGENTS.md rule 2).

## Who runs it
The `entertainment-reviewer` agent (`.claude/agents/`, Opus) runs the review, and the lead writes the report file. It also has a proposal mode: before the lead puts a gameplay design question to the owner, the agent says how each option plays for each audience and which one it would pick (build-loop §3).

## When
- At every phase exit, as one of the milestone gates (ROADMAP).
- At a major checkpoint: a whole subsystem lands (for example the Threat Director's three parts), a tracker item labeled `devlog-moment` is done, or the owner asks.

## Audiences
Each review scores and comments on all four. An audience whose surface doesn't exist yet is still reviewed from what the sim produces for it, and the review says so.

| Audience | Who | What they need |
|---|---|---|
| **Watcher** | A viewer on the stream who isn't playing | Something readable within 5 s; a reason to stay (a fight building, a base about to fall); a reason to join |
| **Player** | A viewer commanding units through chat | Agency they can feel: their command is acknowledged, their unit matters, the outcome traces back to their choices; clear next steps; not too much waiting |
| **Site watcher** (future, Q-ARCH-7) | Someone following on the public site only: map, replays, leaderboards, stats | A campaign story they can follow asynchronously: what changed since they last looked, who did what, the stakes now |
| **VOD and clip watcher** | Someone watching a recording, a highlight or a short clip later | Moments that make sense without context: a clear setup and payoff in under a minute; a recap of the campaign arc for long VODs |

## What to look at
Use what exists at the time of the review, and name it in the report.
- **P1 (headless):** long seeded runs from the balance harness (NX-031) at the standard crowd profiles, read as event streams and replay summaries (NX-032). Reconstruct what each audience would have seen.
- **P2 onward:** the overlay on a recorded run, the stream itself, chat feedback, and later the site and clips.

For each audience, measure where the data allows and estimate where it doesn't, labelled as an estimate (DATA-INTEGRITY):
- **Pacing:** the time between notable events (a capture, a base going down, a tier change, a big fight), and the longest stretch with nothing notable ("dead air").
- **Arc:** does the campaign have rising tension, swings and a climax, or is it flat or decided early? Count the comebacks and the lead changes.
- **Readability:** can each notable event be explained in one line from what that audience sees?
- **Agency (Player):** the share of outcomes traceable to a viewer's command; the time from joining to first meaningful effect; the time spent waiting.
- **Clip-worthiness (VOD and clip):** the count of self-contained 15–60 s moments with a setup and a payoff, and their spacing.
- **Low population:** what each audience sees at 0, 1 and 5 viewers (TS-3), including overnight Pattern of Life.

## Output
A report at `docs/review/ENTERTAINMENT-<phase or checkpoint>-<date>.md` with:
1. What was reviewed (runs, seeds, profiles, durations, builds) and what doesn't exist yet.
2. For each audience: a score from 1 (would leave) to 5 (would stay and tell a friend), the evidence behind it, and the three biggest problems.
3. Suggestions, each with the audience it serves, the expected effect, a rough cost and the spec or config it touches. Mark the ones that are pure tuning (a balance key, Q-DEV-21) separately from the ones that need a design change.
4. Watch items to add to PLAYTEST-WATCHLIST, and questions for OPEN-QUESTIONS.

The owner decides which suggestions to take. Accepted ones become tracker items or config changes like any other work.
