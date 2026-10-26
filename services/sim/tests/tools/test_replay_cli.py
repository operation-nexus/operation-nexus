"""Unit tests for the Replay CLI (tools/replay/replay.py, NX-032)."""

import sys
from pathlib import Path

import pytest

from nexus.core.world import state_hash
from nexus.runtime.campaign_config import load_campaign_config, start_campaign
from nexus.runtime.command_log import CommandLogWriter
from nexus.runtime.snapshot_file import write_snapshot

REPLAY_DIR = Path(__file__).resolve().parents[4] / "tools" / "replay"
if str(REPLAY_DIR) not in sys.path:
    sys.path.insert(0, str(REPLAY_DIR))

import replay  # type: ignore[import-not-found,unused-ignore]  # noqa: E402


@pytest.fixture
def sample_campaign(tmp_path: Path) -> tuple[Path, Path, str, object]:
    """Create a minimal real campaign with snapshot and command log for testing."""
    snaps = tmp_path / "snapshots"
    logs = tmp_path / "logs"
    snaps.mkdir()
    logs.mkdir()

    cfg = load_campaign_config()
    campaign_id = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
    world = start_campaign(campaign_id, 12345, cfg)

    write_snapshot(
        snaps,
        world,
        last_arrival_seq=0,
        sim_build="test-build",
        protocol_version="0.2",
        created_at="2026-10-21T12:00:00Z",
    )

    writer = CommandLogWriter(
        logs,
        segment=1,
        campaign_id=campaign_id,
        protocol_version="0.2",
        next_arrival_seq=1,
    )
    writer.close()

    expected = state_hash(world)
    return snaps, logs, expected, cfg


def test_replay_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Replay CLI root and subcommands must support --help and exit 0."""
    parser = replay.parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "run" in captured.out
    assert "verify" in captured.out
    assert "size" in captured.out

    for sub in ("run", "verify", "size"):
        with pytest.raises(SystemExit) as sub_exc:
            parser.parse_args([sub, "--help"])
        assert sub_exc.value.code == 0


def test_replay_cli_invalid_command() -> None:
    """Missing or invalid subcommand must exit with code 2."""
    parser = replay.parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])
    assert exc_info.value.code == 2

    with pytest.raises(SystemExit) as exc_info2:
        parser.parse_args(["unknown-cmd"])
    assert exc_info2.value.code == 2


def test_replay_cli_missing_dirs(tmp_path: Path) -> None:
    """Non-existent directories must cause main to return exit code 2."""
    bad_snaps = tmp_path / "nonexistent_snaps"
    bad_logs = tmp_path / "nonexistent_logs"
    assert replay.main(["run", str(bad_snaps), str(bad_logs)]) == 2
    assert replay.main(["verify", str(bad_snaps), str(bad_logs), "--expect", "0" * 64]) == 2
    assert replay.main(["size", str(bad_snaps), str(bad_logs)]) == 2


def test_replay_cli_hash_validation(tmp_path: Path) -> None:
    """Verify subcommand must validate that --expect is 64 hex characters."""
    snaps = tmp_path / "snaps"
    logs = tmp_path / "logs"
    snaps.mkdir()
    logs.mkdir()
    parser = replay.parser()

    # Too short
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["verify", str(snaps), str(logs), "--expect", "1234abcd"])
    assert exc.value.code == 2

    # Non-hex characters
    with pytest.raises(SystemExit) as exc2:
        parser.parse_args(["verify", str(snaps), str(logs), "--expect", "g" * 64])
    assert exc2.value.code == 2


def test_replay_cli_size(
    sample_campaign: tuple[Path, Path, str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    """Size subcommand must report snapshot and log stats and exit 0."""
    snaps, logs, _, _ = sample_campaign
    rc = replay.main(["size", str(snaps), str(logs)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "ticks covered:" in captured.out
    assert "snapshots:" in captured.out
    assert "log segments:" in captured.out


def test_replay_cli_run(
    sample_campaign: tuple[Path, Path, str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    """Run subcommand must print checkpoints and final state hash and exit 0."""
    snaps, logs, expected, _ = sample_campaign
    rc = replay.main(["run", str(snaps), str(logs)])
    assert rc == 0
    captured = capsys.readouterr()
    assert expected in captured.out
    assert "(final)" in captured.out


def test_replay_cli_verify_success(
    sample_campaign: tuple[Path, Path, str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify subcommand must print 'ok <hash>' and exit 0 when hashes match."""
    snaps, logs, expected, _ = sample_campaign
    rc = replay.main(["verify", str(snaps), str(logs), "--expect", expected])
    assert rc == 0
    captured = capsys.readouterr()
    assert f"ok {expected}" in captured.out


def test_replay_cli_verify_mismatch(
    sample_campaign: tuple[Path, Path, str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify subcommand must print MISMATCH and exit 1 when hashes differ."""
    snaps, logs, expected, _ = sample_campaign
    wrong_hash = "0" * 64
    rc = replay.main(["verify", str(snaps), str(logs), "--expect", wrong_hash])
    assert rc == 1
    captured = capsys.readouterr()
    assert f"MISMATCH: expected {wrong_hash}, got {expected}" in captured.err


def test_replay_cli_until_tick(sample_campaign: tuple[Path, Path, str, object]) -> None:
    """Until-tick option must be supported in run and verify."""
    snaps, logs, expected, _ = sample_campaign
    rc = replay.main(["run", str(snaps), str(logs), "--until-tick", "0"])
    assert rc == 0
    rc_v = replay.main(["verify", str(snaps), str(logs), "--until-tick", "0", "--expect", expected])
    assert rc_v == 0
