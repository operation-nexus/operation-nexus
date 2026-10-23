"""Issue sync (ERROR-PIPELINE EP-9): `python -m nexus.errors.sync`.

Reads the local fingerprint store (EP-8) and nothing else, and creates or updates `error` issues in
the private ops repo through the GitHub REST API (EP-5). Run it from a host timer; this module
only does one run. Config comes from the environment: `NEXUS_ERRORS_DB`, `NEXUS_ERRORS_REPO`,
`NEXUS_ERRORS_GH_TOKEN`. The token is read only for a real run, goes only into the Authorization
header, and is never logged, printed or put in an error message. Issue text is built from the
stored allowlisted fields (EP-2) and counts; never a message, chat line or name.
"""

import argparse
import http.client
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from nexus.errors.store import Entry, Store

LABEL = "error"
DEFAULT_MAX_NEW = 10  # PROPOSED (EP-9, errors.sync_max_new_per_run); the owner may change it
UPDATE_INTERVAL = timedelta(hours=1)  # EP-9: an issue gets a comment at most this often
FLOOD_ISSUE = "flood_issue"
FLOOD_SYNCED_AT = "flood_synced_at"
BOUND_REPO = "repo"  # the repo this store's issue numbers belong to
# owner/name; a segment of only dots (`..`) would climb the API path, so it is refused
_REPO = re.compile(r"(?!\.+(?:/|$))[A-Za-z0-9_.-]+/(?!\.+$)[A-Za-z0-9_.-]+")
_API = "https://api.github.com"
_HTTP_TIMEOUT_S = 30


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx becomes an HTTPError: the token is never re-sent to another URL."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


class SyncError(Exception):
    """A failed GitHub call. The message names the call and status only: no token, no body."""


# What a failed item can raise: our own errors, a store error, a half-read HTTP reply.
_ITEM_FAILURES = (SyncError, sqlite3.Error, http.client.HTTPException)


class IssueClient(Protocol):
    def create_issue(self, title: str, body: str) -> int: ...

    def comment(self, number: int, body: str) -> None: ...

    def reopen(self, number: int) -> None:
        """Set the issue open (a no-op on an open issue)."""
        ...

    def update_body(self, number: int, body: str) -> None: ...


class GitHubClient:
    def __init__(self, repo: str, token: str) -> None:
        self._base = f"{_API}/repos/{repo}/issues"
        self._token = token

    def _call(self, method: str, suffix: str, payload: dict[str, object]) -> object:
        request = urllib.request.Request(  # noqa: S310 - fixed https URL
            self._base + suffix,
            data=json.dumps(payload).encode(),
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "nexus-errors-sync",
            },
        )
        what = f"GitHub {method} issues{suffix}"
        try:
            with _OPENER.open(request, timeout=_HTTP_TIMEOUT_S) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as failure:
            raise SyncError(f"{what} returned HTTP {failure.code}") from None
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as failure:
            raise SyncError(f"{what} failed: {type(failure).__name__}") from None

    def create_issue(self, title: str, body: str) -> int:
        reply = self._call("POST", "", {"title": title, "body": body, "labels": [LABEL]})
        number = reply.get("number") if isinstance(reply, dict) else None
        if not isinstance(number, int):
            raise SyncError("GitHub POST issues returned no issue number")
        return number

    def comment(self, number: int, body: str) -> None:
        self._call("POST", f"/{number}/comments", {"body": body})

    def reopen(self, number: int) -> None:
        self._call("PATCH", f"/{number}", {"state": "open"})

    def update_body(self, number: int, body: str) -> None:
        self._call("PATCH", f"/{number}", {"body": body})


class DryRunClient:
    """Prints what a real run would do; touches nothing."""

    def create_issue(self, title: str, body: str) -> int:
        print(f"would create issue: {title}")
        return 0

    def comment(self, number: int, body: str) -> None:
        print(f"would comment on #{number}: {body}")

    def reopen(self, number: int) -> None:
        print(f"would reopen #{number} if closed")

    def update_body(self, number: int, body: str) -> None:
        print(f"would update the body of #{number}")


def issue_title(entry: Entry) -> str:
    return f"error: `{entry.exc_type}` in {entry.component}"


def issue_body(entry: Entry) -> str:
    sample = json.dumps(entry.sample, indent=2, sort_keys=True)
    return "\n".join(
        [
            f"Fingerprint: local:{entry.fp}",
            "",
            f"Component: {entry.component}",
            f"Exception: `{entry.exc_type}`",
            f"First seen: {entry.first_seen.isoformat()}",
            f"Last seen: {entry.last_seen.isoformat()}",
            f"Count: {entry.seen_count}",
            f"Release: {entry.release or 'none recorded'}",
            "",
            "Sample (allowlisted fields only):",
            "```json",
            sample,
            "```",
        ]
    )


def _flood_body(overflow: Sequence[Entry]) -> str:
    lines = [f"- local:{e.fp}: {e.seen_count}" for e in overflow]
    return "\n".join(
        ["Fingerprint: local:flood", "", "New-issue cap reached; fingerprint: count", *lines]
    )


def _sync_entry(store: Store, client: IssueClient, entry: Entry, now: datetime, dry: bool) -> None:
    if entry.issue_number is None:
        number = client.create_issue(issue_title(entry), issue_body(entry))
    else:
        if entry.synced_at is not None and now - entry.synced_at < UPDATE_INTERVAL:
            return
        number = entry.issue_number
        client.reopen(number)  # EP-5: a recurrence reopens a closed issue
        client.comment(
            number, f"Count: {entry.seen_count}\nLast seen: {entry.last_seen.isoformat()}"
        )
    if not dry:
        try:
            store.mark_synced(entry.fp, number, entry.seen_count, now)
        except sqlite3.Error as failure:
            print(
                f"issue #{number} for local:{entry.fp} was written but the store update failed"
                f" ({type(failure).__name__}); the next run may post it again",
                file=sys.stderr,
            )
            raise


def _sync_flood(
    store: Store, client: IssueClient, overflow: Sequence[Entry], now: datetime, dry: bool
) -> None:
    body = _flood_body(overflow)
    number = store.meta_get(FLOOD_ISSUE)
    if number is None:
        created = client.create_issue("error: flood", body)
        if not dry:
            store.meta_set(FLOOD_ISSUE, str(created))
            store.meta_set(FLOOD_SYNCED_AT, now.isoformat())
        return
    last = store.meta_get(FLOOD_SYNCED_AT)
    if last is not None and now - datetime.fromisoformat(last) < UPDATE_INTERVAL:
        return
    client.reopen(int(number))
    client.update_body(int(number), body)
    if not dry:
        store.meta_set(FLOOD_SYNCED_AT, now.isoformat())


def _describe(failure: Exception) -> str:
    """Our own errors are safe to print; anything else is named by type only."""
    return str(failure) if isinstance(failure, SyncError) else type(failure).__name__


def run_sync(
    store: Store, client: IssueClient, now: datetime, max_new: int, dry_run: bool = False
) -> int:
    """One sync pass. Returns the number of failed items; a failed item's store state is left
    unchanged so the next run retries it."""
    failures = 0
    budget = max_new
    overflow: list[Entry] = []
    for entry in store.pending():
        if entry.issue_number is None:
            if budget <= 0:
                overflow.append(entry)
                continue
            budget -= 1
        try:
            _sync_entry(store, client, entry, now, dry_run)
        except _ITEM_FAILURES as failure:
            failures += 1
            print(f"sync failed for local:{entry.fp}: {_describe(failure)}", file=sys.stderr)
    if overflow:
        try:
            _sync_flood(store, client, overflow, now, dry_run)
        except _ITEM_FAILURES as failure:
            failures += 1
            print(f"sync failed for the flood issue: {_describe(failure)}", file=sys.stderr)
    return failures


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    client: IssueClient | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    parser = argparse.ArgumentParser(prog="python -m nexus.errors.sync", description=__doc__)
    parser.add_argument(
        "--max-new",
        type=int,
        default=DEFAULT_MAX_NEW,
        help=(
            f"most new-issue attempts per run, then one flood issue "
            f"(default {DEFAULT_MAX_NEW}; PROPOSED)"
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan; no token needed")
    args = parser.parse_args(argv)
    if args.max_new < 0:
        parser.error("--max-new must be 0 or more")
    env = os.environ if env is None else env
    db, repo = env.get("NEXUS_ERRORS_DB"), env.get("NEXUS_ERRORS_REPO")
    if not db or not repo or not _REPO.fullmatch(repo):
        print("NEXUS_ERRORS_DB and NEXUS_ERRORS_REPO (owner/name) are required", file=sys.stderr)
        return 2
    if not Path(db).exists():
        print("no error store yet; nothing to sync")
        return 0
    if args.dry_run:
        client = DryRunClient()
    elif client is None:
        token = env.get("NEXUS_ERRORS_GH_TOKEN")
        if not token:
            print("NEXUS_ERRORS_GH_TOKEN is required", file=sys.stderr)
            return 2
        client = GitHubClient(repo, token)
    store = Store(Path(db))
    try:
        # Issue numbers in the store belong to one repo: never reuse them in another (a changed
        # NEXUS_ERRORS_REPO with an old store would reopen and comment on unrelated issues).
        bound = store.meta_get(BOUND_REPO)
        if bound is not None and bound.lower() != repo.lower():
            print(
                f"the error store belongs to {bound}, not {repo}: use a new NEXUS_ERRORS_DB",
                file=sys.stderr,
            )
            return 2
        if bound is None and not args.dry_run:
            store.meta_set(BOUND_REPO, repo)
        failures = run_sync(store, client, clock(), args.max_new, args.dry_run)
    except sqlite3.Error as failure:  # the store itself is unreadable
        print(f"sync aborted: store error {type(failure).__name__}", file=sys.stderr)
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
