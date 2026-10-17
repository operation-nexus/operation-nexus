# Security Review of the Raw Plans' Sample Code

Date: 2026-10-17 · Scope: `Raw-plans.md` (RP) and `Raw-conversation.md` (RC). Line numbers refer to those files at commit `f0c7624`.

**Verdict:** the sample code must not be used as a starting point. It has an account-takeover flaw in linking, stored XSS into the OBS browser source, and an unauthenticated command path. The requirements that fix these are in [`THREAT-MODEL.md`](../security/THREAT-MODEL.md).

| ID | Severity | Location | Finding | Fix (requirement) |
|---|---|---|---|---|
| V1 | Critical | RP:1105–1121 | `confirm_linking` lets the clicker type **any** `platform_user_id`; ownership is never proven. Then `INSERT OR REPLACE` silently re-points an existing identity to the attacker's commander. That is account takeover, and it works on the streamer's or a mod's account too. | SEC-ID-1, SEC-ID-2 |
| V2 | Critical | RP:748–749, 937–963, 979 | Link tokens are posted in **public chat**, where any onlooker, chat archive, or VOD replay can claim them first. `!claim` re-points the claimer's identity onto the token owner's profile, and tokens aren't bound to who requested them. | SEC-ID-3, SEC-ID-4 |
| V3 | High | RP:931, 933 | Tokens come from `random.randint(100000,999999)`: about 20 bits, from Mersenne Twister (predictable), with no rate limit. `INSERT OR REPLACE` on a collision reassigns another user's token. This contradicts the "cryptographically signed" claim (RC:146). | SEC-ID-3 |
| V4 | High | RP:605, 361, 383 | `innerHTML` built from kill-feed strings that contain raw usernames gives **stored XSS on the live broadcast**. If OBS page permissions are on, it also reaches `window.obsstudio` (scene switch / stop stream). | SEC-OV-1, SEC-OV-2 |
| V5 | High | RP:286, 404–412, 531 | `/api/command` is unauthenticated, CORS is `*`, and the `username` field is caller-supplied, so anyone can impersonate anyone. `/ws` has no Origin check or auth. | SEC-API-1, SEC-API-2 |
| V6 | High | RP:1106 | The confirm handler reads POST fields from the query string, so the HTML form gets a 422 and the obvious "fix" leaks the token into URLs and logs. There's no CSRF protection, and the token check isn't atomic with consumption (TOCTOU). | SEC-ID-4, SEC-ID-5 |
| V7 | Medium | RP:947–963 | `sec` can be `None` (crash). There's no transaction isolation, so concurrent claims race. **XP is summed on merge, which enables Sybil farming.** Foreign keys are never enabled. | SEC-ID-6, PROG-3 |
| V8 | Medium | RP:819–935 | SQLite has no WAL or `busy_timeout`. `award_xp` does a read-modify-write (lost updates). A default-callsign `randint(10,99)` collision raises an unhandled IntegrityError, after which that viewer can never play. Default patterns can be squatted. | ADR-0003 (single SQLite writer, WAL, atomic updates; Postgres once there are multiple writers), IDENTITY §callsigns |
| V9 | Medium | RP:517–523, 327, 529 | One slow WS client stalls the tick. The client list is unbounded, and the full state goes to every client 10×/s. `viewer_slots` grows forever. The sim task has no exception guard (a silent freeze). `--reload` is used in run instructions. | SEC-API-3, SIM-CORE §I/O |
| V10 | Medium | RP:501–503 | The SIGINT blob id contains the real entity id, and the jitter is a deterministic sin/cos, so exact enemy positions can be recovered from the WS. | FOW-2 |
| V11 | Medium | RP:1153 | The LLM chooses `callsign_target` from free text, so it can command other users' units. Waypoints are unbounded and `target_node` is a free string. | SEC-LLM-3 |
| V12 | Low | RP:753, 915–928 | The slur filter is promised but missing. The regex allows leetspeak, and raw usernames reach the HUD unfiltered. | SEC-MOD-1 |

## LLM-specific (OWASP LLM Top 10, 2025)
- **LLM01 Prompt injection:** comes in directly through `!order` and **indirectly through usernames, callsigns, and chat** that end up in the Threat Director's context and in sitrep/clip narration.
- **LLM05 Improper output handling:** model output becomes TTS, on-screen text, and uploaded video.
- **LLM06 Excessive agency:** auto-upload without a human. The model picks which unit to command.
- **LLM10 Unbounded consumption:** RP:1129–1131 sends *every unmatched message* to the LLM, which allows cost DoS and contradicts RP:139.
- **TTS abuse:** phonetic slurs evade text filters. Custom voices (RC:22) carry voice-cloning consent and deepfake liability.

## Platform and compliance
- Scraping TikTok chat is against the ToS and needs third-party signing servers.
- Every viewer-controlled string is broadcast, clipped, and uploaded, so hateful content means channel strikes on every platform.
- **GDPR:** platform IDs and usernames are personal data. Event-sourced replays keep usernames forever. Replays should use pseudonymous ids with a deletable mapping (crypto-shredding).
- **COPPA / UK Children's Code:** minors are present on TikTok and YouTube. Don't profile under-13s, and mark the channel not made for kids.

## CI/CD corrections
"pip-audit / npm audit" is SCA, not SAST. The full layered toolset is in [`CICD-ARCHITECTURE.md §5`](../cicd/CICD-ARCHITECTURE.md).
