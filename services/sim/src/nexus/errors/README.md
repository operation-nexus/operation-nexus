# nexus.errors: local error store and issue sync

Spec: `docs/specs/ERROR-PIPELINE.md` (EP-8, EP-9). Tracker: NX-392.

## Turn the store on

Set `NEXUS_ERRORS_DB` to a file path in the runtime data dir (no default: unset means no store).
Optional: `NEXUS_RELEASE` (a short id-shaped build label; otherwise recorded as none, with one startup warning), `NEXUS_ENV`.
`make_reporter()` then records every capture there and still writes the log line.

## Sync to GitHub issues

A host timer runs one pass; this repo ships no timer unit.

```
NEXUS_ERRORS_DB=/path/errors.db \
NEXUS_ERRORS_REPO=<owner>/<ops-repo> \
NEXUS_ERRORS_GH_TOKEN=<fine-grained token, issues write on that repo only> \
python -m nexus.errors.sync [--max-new N] [--dry-run]
```

- `NEXUS_ERRORS_REPO` and `NEXUS_ERRORS_GH_TOKEN` are required (no defaults). The token is read from
  the environment only, never logged or printed. Keep it with sops+age in the ops repo.
- `--dry-run` prints what it would do, needs no token, calls nothing and marks nothing.
- `--max-new` (default 10, PROPOSED) caps new issues per run; the rest go into one flood issue.
- Exit 0: done (or no store yet). 1: at least one GitHub call failed; those fingerprints stay
  unsynced and the next run retries. 2: bad or missing configuration.
- Run it at least hourly; an issue is commented at most once an hour.
- A human-closed issue is reopened (at most hourly) while its error keeps recurring (EP-5).
- Tags are typed per key (`TAG_PATTERNS` in `adapters/log.py`): `tick`, `campaign_id`; any other
  key is dropped. Add new keys there with a typed pattern.
- Issues carry only allowlisted fields (type, short-path frames, component, id tags), counts and
  times. Never read: chat, logs, or any file besides the store.
