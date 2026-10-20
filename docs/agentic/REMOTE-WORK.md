# Working Remotely (owner travels often)

Goal: plan, review, approve and even code from a phone, while the home desktop runs 24/7.

| Need | How | Status |
|---|---|---|
| Plan/spec/code from phone | Claude Code cloud sessions (like the one that produced these docs) on this repo | Working today |
| Control the home desktop session from phone | Run `claude remote-control` (or the desktop app) on the home PC in the repo folder, then continue it from the Claude app | Owner to set up (NX-044) |
| Reach home services (Command Center, staging, logs) | Tailscale on the phone + home PC + Linux server (private, no open ports) | Planned (ADR-0006) |
| Approve clips and posts on the go | Command Center review queue (phone-friendly) + a scheduled post queue | Planned (NX-234, NX-298) |
| Alerts and one-tap actions | ntfy + Discord (Q-OPS-4), pause/resume from alerts (NX-286) | Planned |
| Cloud sessions can run checks | SessionStart hook runs `make bootstrap` (NX-025) | Done; first cloud run pending |
| Review PRs/issues | GitHub mobile app | Working today |

Travel mode: the posting cadence is a flexible target (Q-MKT-4). The queue keeps scheduled posts flowing while the owner is away.
