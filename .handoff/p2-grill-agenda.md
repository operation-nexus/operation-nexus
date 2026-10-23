# P2 grilling agenda (prepared 2026-10-23)

This was read from `origin/develop` and cites tracker and Q-rows. **[OWNER]** marks a real design choice. **[LEAD]** means the lead can decide it under Q-DEV-21 and lists it for veto. NX-376 has improved since this was drafted: container p99 at 1,000 entities is now 11–15 ms (#273).

## Block A: P1 decisions waiting on the owner
1. **[OWNER] Approve or veto about 30 "Decided by lead" rows** (10-20 to 10-23): Q-DEV-15, Q-SIM-29 (2nd), 32, 33, 35, Q-DEV-20, Q-SIM-36, Q-CFG-13, 14, Q-SIM-37, 40, 41, 43, 44, 45–47, 52, 55, 58, 62, 63, 67, 70, 72, 75, 80, 83, 91, 98, Q-SIM-89 values, Q-SIM-92. Recommend: approve all.
2. **[OWNER] The 50-seed P1 acceptance run** (about 500 CPU-hours).
   - (a) PC queue over several nights
   - (b) cloud VM
   - (c) fewer seeds for the big profiles
   - (d) exit on a reduced run and finish during P2

   Recommend (a) + (d).
3. **[OWNER] Which §3.5a targets gate P1?** A5 needs NX-321 (P4), A6 needs NX-291 (P4), A7 needs P2. Recommend gating on A1–A4 only.
4. **[OWNER] NX-376.** The p99 is now under budget in the container. Is the i7 re-run a P1 gate, or done in P2? Recommend: gate on the i7 run (it's cheap).
5. **[OWNER] NX-373 bridge numbers.** Recommend: the lead proposes PROPOSED values next to FOB defense HP 300, and the harness tunes them.
6. **[OWNER] NX-364 errors.** Q-DEV-7 already chose Sentry's free plan.
   - (a) Sentry now
   - (b) ship the `ErrorReporter` port with a log and issue adapter now; add Sentry with the first deploy (NX-255)
   - (c) self-hosted GlitchTip

   Recommend (b).
7. **[OWNER] NX-033 soak.**
   - (a) nightly 6 h on GitHub Actions (job limit [UNVERIFIED])
   - (b) PC queue only
   - (c) 30–60 min nightly on CI plus a weekly 6 h+ on the PC

   Recommend (c).
8. **[LEAD] Move NX-301 out of P1** (later phase, Q-ALN-20, Q-PROD-8). In a docs PR tonight.
9. **[LEAD] Move NX-387 into P2,** next to NX-190. In a docs PR tonight.
10. **[OWNER] NX-378 entertainment review.**
    - (a) after the full acceptance runs
    - (b) a partial review now on 12–24 h runs, again at the first P2 overlay checkpoint
    - (c) skip

    Recommend (b).
11. **[LEAD] NX-385 and NX-386 stay in P3.** The lead can build a scaled test variant of strait-1 unless you want to design the benchmark map.

## Block B: hosting (blocks NX-013/014/254/255, monitoring, burn-in)
12. **[OWNER] Accept ADR-0012** (Proposed).
13. **[OWNER] Linux server.** It's 32-bit Ubuntu 18.04 and can't run Docker.
    - (a) amd64 Ubuntu 24.04 reinstall now (you're doing this)
    - (b) a VPS
    - (c) no server for the alpha

    Recommend (a).
14. **[OWNER] Q-OPS-1.** Broadcast box: recommend the shared gaming PC with Ceasefire mode. Also run three upload speed tests before NX-254.
15. **[OWNER] Alpha Twitch channel.** "Unlisted" streams on Twitch are [UNVERIFIED]. The simulator must not run on the production channel (CG-1).
    - (a) a separate test channel
    - (b) the public channel, unadvertised

    Recommend (a).
16. **[OWNER] Deploy pipeline depth.**
    - (a) full NX-013 chain (signed images) plus NX-014
    - (b) local compose build and a script

    Recommend (a)-lite: `build.yml` without cosign first.

## Block C: chat gateway (NX-190/191/192/193/041)
17. **[OWNER] Approve COMMAND-CATALOG (Review) and CHAT-GATEWAY** after lead fixes: §8 and §9 are out of order, and CONTRACTS §11 has a stale Q-GW-2 note.
18. **[OWNER] Twitch bot identity.**
    - (a) a separate bot account with mod rights
    - (b) the broadcaster account

    Recommend (a).
19. **[OWNER] Token and secret storage in P2.**
    - (a) pull sops+age (NX-299) into P2
    - (b) age file plus a key in DPAPI
    - (c) `.env` only

    Recommend (a).
20. **[LEAD] EventSub over WebSocket,** with a thin own client on `websockets` + `httpx`. New dependencies listed for veto.
21. **[OWNER] Callsign word list** (IDENTITY §2). Recommend: the lead drafts about 200 themed words, checked against the validator and the denylist, for your sign-off.
22. **[LEAD] Alpha moderation scope.** No user-authored text reaches the stream in P2. NX-041 ships the normalizer and a denylist; you approve the list's license.
23. **[LEAD] Viewer simulator spec** (NX-193): reuse the harness personas through `LocalSim`.

## Block D: WebSocket server and overlay (NX-170/171/175+)
24. **[LEAD] One ASGI stack** (Starlette + uvicorn) for the overlay WS, the admin API and `/metrics`, plus `@msgpack/msgpack` in the overlay. New dependencies listed for veto.
25. **[LEAD] Approve WIRE-PROTOCOL and CONTRACTS §7 piece by piece**, and fix the drift (`tick_rate` / `tick_rate_hz`, `protocol_version` / `v`, the bind rule vs SEC-API-2). Partly in a docs PR tonight.
26. **[OWNER] Overlay styling before the brand guide.**
    - (a) placeholder styling, you review screenshots, NX-274 later
    - (b) brand guide first

    Recommend (a).
27. **[LEAD] Overlay TBDs as PROPOSED keys:** toast duration, maintenance notice lead time, which layers are "heavy", resume countdown, broadcast time zone. Duplicate OV ids are fixed tonight.

## Block E: identity and data
28. **[OWNER] Approve IDENTITY §1–2 and §5, and DATA-MODEL §4.1–4.6 and §5.** Lead parts listed for veto:
    - hand-rolled `schema_migrations`;
    - P2 backups local plus to the Linux server;
    - off-site backups wait for P4.
29. **[OWNER] Q-SIM-29 frame-stream retention** (about 12 GB/day worst case).
    - (a) full truth until the campaign ends + 7 days, then keyframes only
    - (b) redacted stream only
    - (c) cold archive

    Recommend (a).

## Block F: ops and admin
30. **[OWNER] Ops and admin scope in P2:**
    - Prometheus + Grafana + Loki in P2: pull NX-300 forward if the Linux server is ready.
    - L3 dead-man's-switch provider: the lead researches, you create the account.
    - Discord admin slash commands in P3, not P2.
    - Confirm the maintenance slot (Tuesday morning, PROPOSED).
    - Smart plug after the burn-in.
    - Audio: P2 ships sound effects (plus music only if NX-332 has a written OK); TTS moves to P3.

## Specs
**Approve before P2 code:**
- CHAT-GATEWAY
- COMMAND-CATALOG
- WIRE-PROTOCOL
- CONTRACTS §4–8
- OVERLAY
- IDENTITY
- DATA-MODEL §4–5, §7
- STATE-MACHINES §4.7–4.10 and §5
- OPS-ADMIN
- ADMIN-RBAC §10
- AUDIO-TTS (if it stays in P2)
- MONITORING-WATCHDOG
- HARDWARE
- ADR-0012

**Write:**
- viewer-simulator spec
- brand/style guide (NX-274)
- overlay layout v2
- alpha playtest plan
- sitrep templates (only if TTS stays in P2)
- moderation/denylist section
- architecture doc (NX-366)
- callsign word list

## Contradictions found
- **P1 gates:** the ROADMAP P1 gate needs targets that can't be measured in P1. Fixed in #274.
- **Phase placement:**
  - Observability (Q-ARCH-11 says P2, NX-300 says P4).
  - Secrets (CHAT-GATEWAY needs them in P2, sops+age is P4).
  - Discord admin (ADMIN-RBAC says P2, NX-261 says P3).
  - TTS (NX-226 says P2, ROADMAP says P3).
  - Q-GP-48 (P4) vs NX-386 (P3 table).
- **Alpha and testing:**
  - "Twitch unlisted" is [UNVERIFIED].
  - Tester count: "a few" vs 5–10.
- **Tidy-ups:** in the docs PR tonight:
  - stale tracker counts;
  - duplicate ids (Q-SIM-29; OV-17 to OV-19);
  - stale notes (CONTRACTS §11 Q-GW-2, DATA-MODEL §11 job events).
