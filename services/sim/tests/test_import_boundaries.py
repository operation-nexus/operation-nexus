"""NX-019: the import-linter contracts in pyproject.toml actually fail on a bad import."""

import shutil
import subprocess
import sys
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
LINT_IMPORTS = Path(sys.executable).with_name("lint-imports")


def _lint(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv, our own venv binary
        [str(LINT_IMPORTS), "--config", str(root / "pyproject.toml"), "--no-cache"],
        cwd=root,
        env={"PYTHONPATH": str(root / "src")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_boundary_violation_fails(tmp_path: Path) -> None:
    root = tmp_path / "sim"
    shutil.copytree(SIM / "src", root / "src")
    shutil.copy(SIM / "pyproject.toml", root / "pyproject.toml")
    assert _lint(root).returncode == 0, "clean copy must pass"

    (root / "src/nexus/gateway/bad.py").write_text("import nexus.core\n")
    result = _lint(root)
    assert result.returncode != 0
    assert "Boundary modules never import the kernel" in result.stdout
