"""Automated tests for CLI ergonomics and safety standards (NX-021, R1).

Verifies that all repo-level maintenance scripts in scripts/ and tools/sim-determinism/check.py:
1. Provide --help and -h flags returning exit code 0.
2. Return standardized exit code 2 for invalid or missing arguments.
3. Contain zero arbitrary shell execution (no shell=True).
4. Correctly allowlist DTED theater assets without hygiene warnings.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

TARGET_SCRIPTS = [
    REPO_ROOT / "scripts" / "check_commit_msg.py",
    REPO_ROOT / "scripts" / "check_contracts_compat.py",
    REPO_ROOT / "scripts" / "check_osv_report.py",
    REPO_ROOT / "scripts" / "check_site.py",
    REPO_ROOT / "scripts" / "check_tracked_files.py",
    REPO_ROOT / "scripts" / "gen_config_reference.py",
    REPO_ROOT / "tools" / "sim-determinism" / "check.py",
]

POSITIONAL_REQUIRED_SCRIPTS = [
    REPO_ROOT / "scripts" / "check_commit_msg.py",
    REPO_ROOT / "scripts" / "check_contracts_compat.py",
    REPO_ROOT / "scripts" / "check_osv_report.py",
]


def _run_script(script_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_help_flag_returns_zero() -> None:
    """Every target script must accept --help and return exit code 0."""
    for script in TARGET_SCRIPTS:
        proc = _run_script(script, "--help")
        assert proc.returncode == 0, f"{script.name} --help failed with exit code {proc.returncode}:\n{proc.stderr}"
        assert "usage:" in proc.stdout.lower() or "options:" in proc.stdout.lower(), (
            f"{script.name} --help output did not contain usage info:\n{proc.stdout}"
        )


def test_short_help_flag_returns_zero() -> None:
    """Every target script must accept -h and return exit code 0."""
    for script in TARGET_SCRIPTS:
        proc = _run_script(script, "-h")
        assert proc.returncode == 0, f"{script.name} -h failed with exit code {proc.returncode}:\n{proc.stderr}"
        assert "usage:" in proc.stdout.lower() or "options:" in proc.stdout.lower(), (
            f"{script.name} -h output did not contain usage info:\n{proc.stdout}"
        )


def test_invalid_arguments_return_exit_code_two() -> None:
    """Every target script must reject unknown flags with standardized exit code 2."""
    for script in TARGET_SCRIPTS:
        proc = _run_script(script, "--unrecognized-option-xyz")
        assert proc.returncode == 2, (
            f"{script.name} with invalid flag returned exit code {proc.returncode} instead of 2.\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


def test_missing_required_arguments_return_exit_code_two() -> None:
    """Scripts with required positional arguments must exit with code 2 when invoked without arguments."""
    for script in POSITIONAL_REQUIRED_SCRIPTS:
        proc = _run_script(script)
        assert proc.returncode == 2, (
            f"{script.name} without args returned exit code {proc.returncode} instead of 2.\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


def test_safe_execution_no_shell_true() -> None:
    """No script in scripts/ or tools/sim-determinism may use shell=True in subprocess invocations."""
    all_scripts = list((REPO_ROOT / "scripts").glob("*.py")) + [
        REPO_ROOT / "tools" / "sim-determinism" / "check.py"
    ]
    for script in all_scripts:
        source = script.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(script))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "shell":
                        if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                            raise AssertionError(f"Forbidden shell=True found in {script} at line {node.lineno}")


def test_dted_allowlist_gate() -> None:
    """check_tracked_files.py must allowlist content/theaters/dted/ without violation."""
    proc = _run_script(REPO_ROOT / "scripts" / "check_tracked_files.py")
    assert proc.returncode == 0, (
        f"check_tracked_files.py failed with exit code {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"
    )
    assert "strait-1-dem16.bin" not in proc.stdout


if __name__ == "__main__":
    test_help_flag_returns_zero()
    test_short_help_flag_returns_zero()
    test_invalid_arguments_return_exit_code_two()
    test_missing_required_arguments_return_exit_code_two()
    test_safe_execution_no_shell_true()
    test_dted_allowlist_gate()
    print("ok")
