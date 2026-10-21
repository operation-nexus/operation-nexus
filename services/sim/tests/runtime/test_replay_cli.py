"""Replay CLI tests (NX-032; tools/replay/replay.py, CLIPS-REPLAY §1)."""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from nexus.core.world import Campaign, World, state_hash
from nexus.runtime.campaign_config import CampaignConfig
from nexus.runtime.command_log import CommandLogWriter
from nexus.runtime.recovery import restore
from nexus.runtime.snapshot_file import list_snapshots

from .conftest import CAMPAIGN_ID
from .test_recovery import STUB, Rig

REPO = Path(__file__).resolve().parents[4]
CLI = REPO / "tools" / "replay" / "replay.py"


@pytest.fixture
def rig(
    tmp_path: Path, log_writer: Callable[..., CommandLogWriter], shipped_config: CampaignConfig
) -> Rig:
    campaign = Campaign(CAMPAIGN_ID, 12345, shipped_config.config_hash)
    return Rig(log_writer, tmp_path, world=World.new(campaign, shipped_config.rules))


def cli(*args: str | Path) -> subprocess.CompletedProcess[str]:
    # fixed argv: this interpreter + the repo's own script
    return subprocess.run(  # noqa: S603
        [sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True
    )


def test_run_prints_the_restore_hashes(tmp_path: Path, rig: Rig) -> None:
    rig.run_to(650)
    # The CLI uses the real, empty HANDLERS, which do not replay the stub's JOINs; compare on
    # the snapshot tick itself (nothing to replay) and check the final line names the same hash.
    out = cli("run", rig.snaps, rig.logs, "--until-tick", "600", "--every", "300")
    assert out.returncode == 0, out.stderr
    expected = state_hash(
        restore(rig.snaps, rig.logs, handlers=STUB, rules=None, until_tick=600).world
    )
    assert out.stdout.splitlines()[-1] == f"tick 600 {expected} (final)"
    h300 = state_hash(restore(rig.snaps, rig.logs, handlers=STUB, rules=None, until_tick=300).world)
    assert f"tick 300 {h300}" in out.stdout
    assert out.stderr == ""


def test_verify_exit_codes(tmp_path: Path, rig: Rig) -> None:
    rig.run_to(650)
    good = state_hash(restore(rig.snaps, rig.logs, handlers=STUB, rules=None, until_tick=600).world)
    assert (
        cli("verify", rig.snaps, rig.logs, "--expect", good, "--until-tick", "600").returncode == 0
    )
    bad = cli("verify", rig.snaps, rig.logs, "--expect", "0" * 64, "--until-tick", "600")
    assert bad.returncode == 1
    assert "MISMATCH" in bad.stderr


def test_size_counts_the_files(tmp_path: Path, rig: Rig) -> None:
    rig.run_to(650)
    snaps = list_snapshots(rig.snaps)
    segs = sorted(rig.logs.glob("*.nxl.zst"))
    out = cli("size", rig.snaps, rig.logs)
    assert out.returncode == 0, out.stderr
    snap_bytes = sum(p.stat().st_size for p in snaps)
    seg_bytes = sum(p.stat().st_size for p in segs)
    assert f"snapshots: {len(snaps)} files, {snap_bytes} bytes" in out.stdout
    assert f"log segments: {len(segs)} files, {seg_bytes} bytes" in out.stdout
    assert "ticks covered: 650" in out.stdout


def test_a_corrupt_snapshot_dir_exits_with_a_clear_error(tmp_path: Path, rig: Rig) -> None:
    rig.run_to(100)
    for p in list_snapshots(rig.snaps):
        p.write_bytes(b"garbage")
    out = cli("run", rig.snaps, rig.logs)
    assert out.returncode == 2
    assert out.stderr.startswith("error: ")
    assert len(out.stderr.strip().splitlines()) == 1


def test_bad_directories_exit_with_not_a_directory(tmp_path: Path, rig: Rig) -> None:
    for cmd in ("run", "size"):
        out = cli(cmd, tmp_path / "typo", rig.logs)
        assert out.returncode == 2
        assert out.stderr.strip() == f"error: {tmp_path / 'typo'}: not a directory"
    out = cli("verify", rig.snaps, tmp_path / "typo", "--expect", "0" * 64)
    assert (out.returncode, out.stderr.strip()) == (
        2,
        f"error: {tmp_path / 'typo'}: not a directory",
    )


def test_bad_options_are_argparse_errors(rig: Rig) -> None:
    for flags in (["--every", "0"], ["--every", "-3"], ["--until-tick", "-1"]):
        out = cli("run", rig.snaps, rig.logs, *flags)
        assert out.returncode == 2
        assert "Traceback" not in out.stderr
    out = cli("verify", rig.snaps, rig.logs, "--expect", "xyz")
    assert out.returncode == 2
    assert "64 lowercase hex" in out.stderr


def test_replay_across_logged_ticks_warns_about_missing_handlers(rig: Rig) -> None:
    rig.run_to(450)  # logged JOINs between the snapshot at 300 and tick 450
    out = cli("run", rig.snaps, rig.logs, "--until-tick", "450", "--every", "150")
    assert out.returncode == 0, out.stderr
    assert "warning: the log holds JOIN commands with no handler yet" in out.stdout
    assert out.stdout.splitlines()[-1].startswith("tick 450 ")
    assert "(final)" in out.stdout


def test_a_tombstoned_tick_replays(rig: Rig) -> None:
    rig.run_to(350)
    rig.rt.log.append_tombstone(320)
    rig.rt.log.flush()
    out = cli("run", rig.snaps, rig.logs, "--until-tick", "350")
    assert out.returncode == 0, out.stderr


def test_a_corrupt_log_exits_2(rig: Rig) -> None:
    rig.run_to(350)
    for p in rig.logs.glob("*.nxl.zst"):
        p.write_bytes(b"garbage")
    out = cli("run", rig.snaps, rig.logs)
    assert (out.returncode, out.stderr.startswith("error: ")) == (2, True)


def test_pruned_history_and_early_until_tick(rig: Rig) -> None:
    rig.run_to(100)
    out = cli("run", rig.snaps, rig.logs, "--until-tick", "0", "--every", "50")
    assert out.returncode == 0, out.stderr
    list_snapshots(rig.snaps)[0].rename(rig.snaps / "000000000200.nxs")  # first snapshot is now 200
    out = cli("run", rig.snaps, rig.logs, "--until-tick", "250", "--every", "100")
    assert "checkpoints before tick 200 skipped" in out.stderr
    assert "tick 100 " not in out.stdout
    out = cli("run", rig.snaps, rig.logs, "--until-tick", "150")
    assert (out.returncode, out.stderr.strip()) == (2, "error: no snapshot at or before tick 150")


def test_a_snapshot_of_another_config_is_refused(tmp_path: Path, rig: Rig) -> None:
    rig.run_to(100)
    out = cli("run", rig.snaps, rig.logs, "--theater", tmp_path / "missing.yaml")
    assert out.returncode == 2
    assert "missing.yaml" in out.stderr  # a bad config path names the file
    text = (REPO / "balance" / "default.yaml").read_text(encoding="utf-8")
    other = tmp_path / "balance.yaml"
    patched = text.replace("snapshot_every_ticks: 300", "snapshot_every_ticks: 301")
    assert patched != text  # the config really differs
    other.write_text(patched, encoding="utf-8")
    out = cli("verify", rig.snaps, rig.logs, "--expect", "0" * 64, "--balance", other)
    assert out.returncode == 2
    assert "differs from the loaded config" in out.stderr
