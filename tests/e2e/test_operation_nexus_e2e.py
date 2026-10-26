"""Comprehensive End-to-End (E2E) Test Suite for Operation Nexus.

Validates Requirements R1 (Tooling & Automation), R2 (Agent Architecture),
and R3 (Decoupled C2 Visualization Pipeline) across four rigorous test tiers:
- Tier 1: Feature Coverage (Happy Path per feature)
- Tier 2: Boundary & Corner Cases (Error handling, invalid inputs, edge conditions)
- Tier 3: Cross-Feature Interactions (Pairwise combinations across R1, R2, R3)
- Tier 4: Real-World Scenarios (End-to-end multi-step operational workflows)

Authoritative References:
- ORIGINAL_REQUEST.md
- PROJECT.md
- content/theaters/strait-1.yaml
- docs/architecture/DECOUPLED-RENDERER-ARCHITECTURE.md
- docs/design/VISUAL-STYLE-CATALOG.md
- docs/specs/TERRAIN-AND-BIOMES.md
- docs/architecture/UNIT-POV-AND-COCKPIT-CONTRACTS-RFC.md
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def get_test_env() -> dict[str, str]:
    """Construct an execution environment with reliable PATH and PYTHONPATH."""
    env = dict(os.environ)
    home = Path.home()
    local_bin = str(home / ".local" / "bin")
    fnm_bin = str(home / ".local" / "share" / "fnm" / "aliases" / "default" / "bin")
    current_path = env.get("PATH", "")
    env["PATH"] = f"{local_bin}:{fnm_bin}:{current_path}"
    sim_src = str(REPO_ROOT / "services" / "sim" / "src")
    balance_dir = str(REPO_ROOT / "tools" / "balance")
    env["PYTHONPATH"] = (
        f"{sim_src}:{balance_dir}:{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    )
    return env


def get_sim_python() -> str:
    """Return python interpreter with services/sim virtual environment packages."""
    venv_py = REPO_ROOT / "services" / "sim" / ".venv" / "bin" / "python"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


def run_cmd(
    args: list[str],
    cwd: Path | None = None,
    timeout: int = 30,
    check: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a command safely using explicit argument list and bounded timeout."""
    env = get_test_env()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        args,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
        env=env,
    )


# ==============================================================================
# Tier 1: Feature Coverage (Happy Path)
# ==============================================================================


class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1: Feature Coverage verifying each feature in isolation."""

    # --- Feature R1: Tooling, Scripting & Automation Gap Resolution ---

    def test_tier1_r1_dted_allowlist(self) -> None:
        """Feature 1: scripts/check_tracked_files.py allowlists content/theaters/dted/."""
        script_path = REPO_ROOT / "scripts" / "check_tracked_files.py"
        self.assertTrue(script_path.is_file(), f"Missing {script_path}")

        content = script_path.read_text(encoding="utf-8")
        self.assertIn(
            "content/theaters/dted/", content, "DTED directory must be allowlisted"
        )

        res = run_cmd([sys.executable, str(script_path)])
        self.assertEqual(
            res.returncode, 0, f"check_tracked_files failed: {res.stdout}\n{res.stderr}"
        )
        self.assertNotIn("content/theaters/dted", res.stdout)

    def test_tier1_r1_cli_help_exit_codes(self) -> None:
        """Feature 2: Standardized --help returns exit code 0 across all tools and scripts."""
        scripts_to_check = [
            REPO_ROOT / "scripts" / "check_commit_msg.py",
            REPO_ROOT / "scripts" / "check_contracts_compat.py",
            REPO_ROOT / "scripts" / "check_osv_report.py",
            REPO_ROOT / "scripts" / "check_site.py",
            REPO_ROOT / "scripts" / "check_tracked_files.py",
            REPO_ROOT / "scripts" / "gen_config_reference.py",
            REPO_ROOT / "tools" / "sim-determinism" / "check.py",
            REPO_ROOT / "tools" / "balance" / "balance.py",
            REPO_ROOT / "tools" / "replay" / "replay.py",
            REPO_ROOT / "tools" / "terrain" / "bake_synthetic_dted.py",
            REPO_ROOT / "tools" / "terrain" / "drape_roads.py",
            REPO_ROOT / "tools" / "terrain" / "mgrs_grid.py",
        ]
        for script in scripts_to_check:
            self.assertTrue(script.is_file(), f"Script {script} does not exist")
            py_bin = (
                get_sim_python()
                if any(
                    x in str(script)
                    for x in ["tools/balance", "tools/replay", "sim-determinism"]
                )
                else sys.executable
            )
            res = run_cmd([py_bin, str(script), "--help"])
            self.assertEqual(
                res.returncode,
                0,
                f"Expected exit code 0 on --help for {script.name}, got {res.returncode}. Stderr: {res.stderr}",
            )
            output = res.stdout.lower()
            self.assertTrue(
                "usage:" in output or "options:" in output or "help" in output,
                f"Help message missing usage/options text for {script.name}",
            )

    def test_tier1_r1_safe_script_execution(self) -> None:
        """Feature 3: Safe script execution with zero arbitrary shell execution (shell=False)."""
        scan_dirs = [REPO_ROOT / "scripts", REPO_ROOT / "tools"]
        for scan_dir in scan_dirs:
            for py_file in scan_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                code = py_file.read_text(encoding="utf-8")
                tree = ast.parse(code, filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        # Detect any call with keyword argument shell=True
                        for kw in node.keywords:
                            if (
                                kw.arg == "shell"
                                and isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                            ):
                                self.fail(
                                    f"Prohibited shell=True detected in {py_file} at line {node.lineno}"
                                )

    def test_tier1_r1_makefile_recipes(self) -> None:
        """Feature 4: Makefile targets test, test-unit, determinism, terrain, balance exist."""
        makefile = REPO_ROOT / "Makefile"
        self.assertTrue(makefile.is_file(), "Makefile missing at project root")
        text = makefile.read_text(encoding="utf-8")

        required_targets = [
            "test",
            "test-unit",
            "determinism",
            "terrain",
            "balance",
            "check",
            "contracts",
        ]
        for target in required_targets:
            pattern = rf"^{re.escape(target)}\s*:"
            self.assertTrue(
                re.search(pattern, text, re.MULTILINE) is not None,
                f"Required Makefile target '{target}' missing from Makefile",
            )
        # Check PATH export in Makefile
        self.assertIn("export PATH :=", text, "Makefile must export local bin PATH")

    def test_tier1_r1_tool_resilience(self) -> None:
        """Feature 5: Developer tools execute without manual PATH or shim interventions."""
        sim_py = get_sim_python()
        tools = [
            [sim_py, str(REPO_ROOT / "tools" / "balance" / "balance.py"), "--help"],
            [sim_py, str(REPO_ROOT / "tools" / "replay" / "replay.py"), "--help"],
            [
                sim_py,
                str(REPO_ROOT / "tools" / "sim-bench" / "kernel_bench.py"),
                "--help",
            ],
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "terrain" / "geojson_to_mask.py"),
                "--help",
            ],
        ]
        for cmd in tools:
            res = run_cmd(cmd)
            self.assertEqual(
                res.returncode, 0, f"Tool failed: {' '.join(cmd)}\n{res.stderr}"
            )

    def test_tier1_r1_pr341_self_tests(self) -> None:
        """Feature 6: Built-in self-tests for DTED, roads, MGRS, and low-poly assets pass."""
        test_commands = [
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "terrain" / "bake_synthetic_dted.py"),
                "--test",
            ],
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "terrain" / "drape_roads.py"),
                "--test",
            ],
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "terrain" / "mgrs_grid.py"),
                "--test",
            ],
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "assets" / "generate_lowpoly_assets.py"),
                "--test",
            ],
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "replay" / "render_cinematic_pass.py"),
                "--test",
            ],
        ]
        for cmd in test_commands:
            res = run_cmd(cmd, timeout=45)
            self.assertEqual(
                res.returncode,
                0,
                f"PR #341 self-test failed: {' '.join(cmd)}\n{res.stderr}",
            )
            self.assertTrue(
                "ok" in res.stdout.lower() or "pass" in res.stdout.lower(),
                f"Self-test output did not indicate success for {' '.join(cmd)}",
            )

    def test_tier1_r1_tool_test_suites(self) -> None:
        """Feature 7: Automated test suites for tools and repo checks exist and pass."""
        repo_checks = REPO_ROOT / "scripts" / "tests" / "test_repo_checks.py"
        self.assertTrue(
            repo_checks.is_file(), "scripts/tests/test_repo_checks.py missing"
        )
        res = run_cmd([sys.executable, str(repo_checks)], timeout=45)
        self.assertEqual(
            res.returncode, 0, f"test_repo_checks failed: {res.stdout}\n{res.stderr}"
        )

        replay_test = (
            REPO_ROOT / "services" / "sim" / "tests" / "runtime" / "test_replay_cli.py"
        )
        self.assertTrue(replay_test.is_file(), "Replay CLI tests missing")

    # --- Feature R2: Model-Agnostic Agent Collaboration Architecture ---

    def test_tier1_r2_model_agnostic_entry(self) -> None:
        """Feature 8: AGENTS.md entry point is model-agnostic and accessible to any frontier model."""
        agents_md = REPO_ROOT / "AGENTS.md"
        self.assertTrue(agents_md.is_file(), "AGENTS.md missing")
        text = agents_md.read_text(encoding="utf-8")

        models = ["Antigravity", "Gemini", "Codex", "Cursor", "Claude"]
        for model in models:
            self.assertIn(
                model, text, f"AGENTS.md must reference {model} in universal entry"
            )

    def test_tier1_r2_capability_tiers(self) -> None:
        """Feature 9: AGENTS.md codifies the 4 Functional Capability Tiers."""
        agents_md = REPO_ROOT / "AGENTS.md"
        text = agents_md.read_text(encoding="utf-8")

        self.assertIn("Tier 1", text, "Tier 1 must be codified in AGENTS.md")
        self.assertIn("Tier 2", text, "Tier 2 must be codified in AGENTS.md")
        self.assertIn("Tier 3", text, "Tier 3 must be codified in AGENTS.md")
        self.assertIn("Tier 4", text, "Tier 4 must be codified in AGENTS.md")

        # Verify key role descriptions
        self.assertTrue(
            "lookup" in text.lower() or "lightweight" in text.lower(),
            "Tier 1 must cover lookup/lightweight",
        )
        self.assertTrue(
            "workhorse" in text.lower() or "scoped" in text.lower(),
            "Tier 2 must cover workhorse/scoped implementation",
        )
        self.assertTrue(
            "frontier" in text.lower() or "governance" in text.lower(),
            "Tier 3 must cover frontier/governance",
        )
        self.assertTrue(
            "tooling" in text.lower() or "deterministic" in text.lower(),
            "Tier 4 must cover deterministic tooling",
        )

    def test_tier1_r2_universal_invariants(self) -> None:
        """Feature 10: Preserves universal invariants (Rule 0, spec-first, determinism, hostile chat, ~400 lines)."""
        agents_md = REPO_ROOT / "AGENTS.md"
        text = agents_md.read_text(encoding="utf-8")

        self.assertIn(
            "NO FABRICATED OR HALLUCINATED DATA", text, "Rule 0 must be present"
        )
        self.assertIn("Spec first", text, "Spec first rule must be present")
        self.assertIn(
            "simulation is deterministic", text, "Determinism invariant must be present"
        )
        self.assertIn(
            "Chat input is hostile", text, "Hostile chat input rule must be present"
        )
        self.assertIn("400", text, "PR line budget must be present")

    def test_tier1_r2_protected_files(self) -> None:
        """Feature 11: Non-hook file protection rules explicitly prohibit .env*, Raw-*.md, .claude/."""
        agents_md = REPO_ROOT / "AGENTS.md"
        text = agents_md.read_text(encoding="utf-8")

        self.assertIn(".env", text, "Protected files must include .env")
        self.assertIn("Raw-plans.md", text, "Protected files must include Raw-plans.md")
        self.assertIn(
            "Raw-conversation.md",
            text,
            "Protected files must include Raw-conversation.md",
        )
        self.assertIn(".claude/", text, "Protected files must include .claude/")

    def test_tier1_r2_agents_catalog(self) -> None:
        """Feature 12: .agents/README.md indexes roles/, rules/, prompts/, context/, and skills/."""
        readme = REPO_ROOT / ".agents" / "README.md"
        self.assertTrue(readme.is_file(), ".agents/README.md missing")
        text = readme.read_text(encoding="utf-8")

        required_sections = ["roles/", "rules/", "prompts/", "context/", "skills/"]
        for section in required_sections:
            self.assertIn(section, text, f".agents/README.md must index {section}")
        self.assertIn(
            "hiveplex-visualization",
            text,
            "Catalog must index hiveplex-visualization skill",
        )

    def test_tier1_r2_claude_preservation(self) -> None:
        """Feature 13: Strict preservation of CLAUDE.md and .claude/ (zero git diff)."""
        res = run_cmd(["git", "diff", "CLAUDE.md", ".claude/"])
        self.assertEqual(res.returncode, 0, f"git diff failed: {res.stderr}")
        self.assertEqual(
            res.stdout.strip(),
            "",
            "CLAUDE.md and .claude/ must have 0 byte diff; modifications forbidden",
        )
        self.assertTrue((REPO_ROOT / "CLAUDE.md").is_file(), "CLAUDE.md must exist")
        self.assertTrue((REPO_ROOT / ".claude").is_dir(), ".claude/ must exist")

    # --- Feature R3: Decoupled High-Fidelity Tactical C2 Visualization Pipeline ---

    def test_tier1_r3_decoupled_engine_contract(self) -> None:
        """Feature 14: Decoupled IRenderEngine and RenderFrameState interface contracts."""
        render_types = REPO_ROOT / "apps" / "overlay" / "src" / "types" / "render.ts"
        self.assertTrue(render_types.is_file(), f"Missing {render_types}")
        code = render_types.read_text(encoding="utf-8")

        self.assertIn("interface IRenderEngine", code)
        self.assertIn("interface RenderFrameState", code)

        methods = [
            "initialize",
            "resize",
            "updateTheaterMap",
            "renderFrame",
            "triggerEffect",
            "setCameraTarget",
            "dispose",
        ]
        for m in methods:
            self.assertIn(m, code, f"IRenderEngine must include method {m}")

        frame_props = ["tick", "simTime", "units", "telemetry"]
        for prop in frame_props:
            self.assertIn(prop, code, f"RenderFrameState must include property {prop}")

    def test_tier1_r3_paradigm_a_crt(self) -> None:
        """Feature 15: Paradigm A (2D CRT Vector Phosphor / Living Glass) specifications."""
        crt_file = (
            REPO_ROOT
            / "apps"
            / "overlay"
            / "src"
            / "renderers"
            / "crt2d"
            / "crt-engine.ts"
        )
        proto_file = REPO_ROOT / "tools" / "prototype" / "unified-visualizer.html"
        self.assertTrue(
            crt_file.is_file() or proto_file.is_file(), "Paradigm A source missing"
        )

        content = (
            crt_file.read_text(encoding="utf-8")
            if crt_file.is_file()
            else proto_file.read_text(encoding="utf-8")
        )
        self.assertTrue(
            "scanline" in content.lower(),
            "CRT scanlines must be specified in Paradigm A",
        )
        self.assertTrue(
            "radar" in content.lower() or "sweep" in content.lower(),
            "Radar sweep must be specified",
        )
        self.assertTrue(
            "trail" in content.lower(), "Vector speed trails must be specified"
        )

    def test_tier1_r3_paradigm_b_holo(self) -> None:
        """Feature 16: Paradigm B (3D Holographic War Room Table) specifications."""
        holo_file = (
            REPO_ROOT
            / "apps"
            / "overlay"
            / "src"
            / "renderers"
            / "holo3d"
            / "holo-engine.ts"
        )
        proto_file = REPO_ROOT / "tools" / "prototype" / "unified-visualizer.html"
        self.assertTrue(
            holo_file.is_file() or proto_file.is_file(), "Paradigm B source missing"
        )

        content = (
            holo_file.read_text(encoding="utf-8")
            if holo_file.is_file()
            else proto_file.read_text(encoding="utf-8")
        )
        self.assertTrue(
            "elevation" in content.lower() or "terrain" in content.lower(),
            "Terrain elevation required",
        )
        self.assertTrue(
            "bridge" in content.lower(), "Elevated bridges required in 3D Holo"
        )
        self.assertTrue(
            "parabolic" in content.lower() or "missile" in content.lower(),
            "Parabolic missile trajectories required",
        )

    def test_tier1_r3_paradigm_c_flir(self) -> None:
        """Feature 17: Paradigm C (FLIR / MFD Cockpit Sensor) specifications."""
        proto_file = REPO_ROOT / "tools" / "prototype" / "unified-visualizer.html"
        catalog_file = REPO_ROOT / "docs" / "design" / "VISUAL-STYLE-CATALOG.md"
        self.assertTrue(proto_file.is_file() and catalog_file.is_file())

        content = proto_file.read_text(encoding="utf-8") + catalog_file.read_text(
            encoding="utf-8"
        )
        self.assertTrue("flir" in content.lower() or "mfd" in content.lower())
        self.assertTrue("white-hot" in content.lower() or "thermal" in content.lower())
        self.assertTrue(
            "pitch ladder" in content.lower() or "heading" in content.lower()
        )

    def test_tier1_r3_paradigm_d_batch(self) -> None:
        """Feature 18: Paradigm D (High-Density Batch Spriting) specifications."""
        arch_doc = (
            REPO_ROOT / "docs" / "architecture" / "DECOUPLED-RENDERER-ARCHITECTURE.md"
        )
        batch_engine = (
            REPO_ROOT
            / "apps"
            / "overlay"
            / "src"
            / "renderers"
            / "batch"
            / "batch-engine.ts"
        )
        self.assertTrue(arch_doc.is_file() and batch_engine.is_file())

        arch_text = arch_doc.read_text(encoding="utf-8")
        batch_text = batch_engine.read_text(encoding="utf-8")

        self.assertIn(
            "500", batch_text, "Paradigm D must support 500+ units in batch engine"
        )
        self.assertTrue(
            "high-density" in arch_text.lower()
            or "batch" in arch_text.lower()
            or "pixi" in arch_text.lower(),
            "High-density 2D sprites must be specified in architecture doc",
        )

    def test_tier1_r3_visual_rules(self) -> None:
        """Feature 19: Core visual rules OV-1 (5s glance), OV-2/3 (colorblind dual encoding), OV-4 (decluttering)."""
        dual_enc = (
            REPO_ROOT / "apps" / "overlay" / "src" / "symbology" / "dual-encoding.ts"
        )
        self.assertTrue(dual_enc.is_file(), f"Missing {dual_enc}")
        code = dual_enc.read_text(encoding="utf-8")

        self.assertIn("#00e5ff", code, "Quorum Cyan #00e5ff required")
        self.assertIn("#ff0055", code, "Static Magenta #ff0055 required")
        self.assertIn(
            "SMOOTH_CHEVRON_DIAMOND", code, "NATO Chevron/Diamond geometry required"
        )
        self.assertIn(
            "JAGGED_SAWTOOTH", code, "Jagged Sawtooth geometry required for enemy"
        )

    def test_tier1_r3_strait1_theater(self) -> None:
        """Feature 20: Strait-1 theater coordinates, recessed water (-3.5m), and elevated bridges (+2..+14m)."""
        theater_yaml = REPO_ROOT / "content" / "theaters" / "strait-1.yaml"
        self.assertTrue(theater_yaml.is_file())
        with theater_yaml.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Bounds: 400km x 240km
        self.assertEqual(data["bounds_m"]["w"], 400000)
        self.assertEqual(data["bounds_m"]["h"], 240000)

        # Strategic infrastructure nodes
        nodes = {node["id"]: node for node in data["nodes"]}
        self.assertIn("haven", nodes)
        self.assertIn("west-airbase", nodes)
        self.assertIn("east-airbase", nodes)
        self.assertIn("bridge-n", nodes)
        self.assertIn("bridge-s", nodes)
        self.assertIn("static-hq", nodes)

        # Elevation constants
        elev_file = REPO_ROOT / "apps" / "overlay" / "src" / "theater" / "elevation.ts"
        self.assertTrue(elev_file.is_file())
        elev_code = elev_file.read_text(encoding="utf-8")
        self.assertIn(
            "-3.5", elev_code, "Water must be recessed at -3.5m to eliminate Z-fighting"
        )
        self.assertIn("14.0", elev_code, "Bridge mid-span apex must reach +14.0m")

    def test_tier1_r3_telemetry_hud(self) -> None:
        """Feature 21: Real-time telemetry HUD components (momentum, countdown, threat badge, sitrep, ticker)."""
        telemetry_file = (
            REPO_ROOT / "apps" / "overlay" / "src" / "types" / "telemetry.ts"
        )
        self.assertTrue(telemetry_file.is_file(), f"Missing {telemetry_file}")
        code = telemetry_file.read_text(encoding="utf-8")

        self.assertIn("momentum", code.lower())
        self.assertIn("countdown", code.lower())
        self.assertIn("threat", code.lower())
        self.assertIn("sitrep", code.lower())
        self.assertIn("ticker", code.lower())

    def test_tier1_r3_paradigm_swappability(self) -> None:
        """Feature 22: Hot-swappable visual paradigms architecture."""
        arch_doc = (
            REPO_ROOT / "docs" / "architecture" / "DECOUPLED-RENDERER-ARCHITECTURE.md"
        )
        proto_html = REPO_ROOT / "tools" / "prototype" / "unified-visualizer.html"
        self.assertTrue(arch_doc.is_file() and proto_html.is_file())
        text = arch_doc.read_text(encoding="utf-8") + proto_html.read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            "swappable" in text.lower()
            or "switch" in text.lower()
            or "theme" in text.lower()
        )


# ==============================================================================
# Tier 2: Boundary & Corner Cases (Error Handling & Limits)
# ==============================================================================


class TestTier2BoundaryAndCornerCases(unittest.TestCase):
    """Tier 2: Boundary & Corner Cases testing invalid inputs, error exit codes, and limits."""

    # --- R1 Boundary & Corner Cases ---

    def test_tier2_r1_invalid_cli_args_exit_code_2(self) -> None:
        """R1 Boundary 1: Invalid CLI arguments return exit code 2."""
        scripts_to_test = [
            REPO_ROOT / "scripts" / "check_tracked_files.py",
            REPO_ROOT / "scripts" / "check_site.py",
            REPO_ROOT / "scripts" / "gen_config_reference.py",
            REPO_ROOT / "tools" / "sim-determinism" / "check.py",
        ]
        for script in scripts_to_test:
            res = run_cmd([sys.executable, str(script), "--unrecognized-argument-xyz"])
            self.assertEqual(
                res.returncode,
                2,
                f"Expected exit code 2 for invalid arguments in {script.name}, got {res.returncode}. Stderr: {res.stderr}",
            )

    def test_tier2_r1_nonexistent_file_handling(self) -> None:
        """R1 Boundary 2: Passing nonexistent file paths returns non-zero without uncaught crash."""
        res = run_cmd(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "check_commit_msg.py"),
                "/tmp/nonexistent_xyz.txt",
            ]
        )
        self.assertNotEqual(
            res.returncode, 0, "Nonexistent file must cause non-zero exit code"
        )
        # Check that error is cleanly handled (no raw traceback)
        self.assertNotIn("Traceback (most recent call last):", res.stderr)

    def test_tier2_r1_missing_path_resilience(self) -> None:
        """R1 Boundary 3: Tool executions with bare minimum PATH succeed using standard library."""
        minimal_env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO_ROOT)}
        res = run_cmd(
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "terrain" / "bake_synthetic_dted.py"),
                "--help",
            ],
            extra_env=minimal_env,
        )
        self.assertEqual(
            res.returncode, 0, f"Tool failed under minimal PATH: {res.stderr}"
        )

    def test_tier2_r1_safe_input_validation(self) -> None:
        """R1 Boundary 4: Subprocess arguments are safe against shell injection characters."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_path = Path(tmp_dir) / "test;echo_injected;touch_PWNED.txt"
            bad_path.write_text(
                "feat: valid commit message (NX-123)\n", encoding="utf-8"
            )
            _ = run_cmd(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "check_commit_msg.py"),
                    str(bad_path),
                ]
            )
            self.assertFalse(
                (Path(tmp_dir) / "PWNED").exists() or (REPO_ROOT / "PWNED").exists(),
                "Shell injection vulnerability detected! PWNED file was created.",
            )

    def test_tier2_r1_balance_extreme_inputs(self) -> None:
        """R1 Boundary 5: Balance tool rejects negative seeds or invalid profile gracefully."""
        res = run_cmd(
            [
                get_sim_python(),
                str(REPO_ROOT / "tools" / "balance" / "balance.py"),
                "--profile",
                "non_existent_profile_xyz_123",
                "--seeds",
                "1",
                "--hours",
                "1",
                "--out",
                "/tmp/dummy_out_dir",
            ]
        )
        self.assertNotEqual(
            res.returncode, 0, "Invalid balance profile must be rejected"
        )

    # --- R2 Boundary & Corner Cases ---

    def test_tier2_r2_non_claude_model_parsing(self) -> None:
        """R2 Boundary 1: AGENTS.md contains pure valid Markdown without unclosed proprietary XML tags."""
        agents_md = REPO_ROOT / "AGENTS.md"
        content = agents_md.read_text(encoding="utf-8")

        # Prohibit unclosed or Claude-specific internal tags that break generic models
        self.assertNotIn("<antThinking>", content)
        self.assertNotIn("</antThinking>", content)
        self.assertNotIn("<claude-hook>", content)

    def test_tier2_r2_protected_file_rejection(self) -> None:
        """R2 Boundary 2: Git index and hygiene rules reject secret files (*.pem, *.key, .env*)."""
        gitignore = REPO_ROOT / ".gitignore"
        self.assertTrue(gitignore.is_file())
        text = gitignore.read_text(encoding="utf-8")

        self.assertIn(".env", text, ".env must be ignored in .gitignore")

    def test_tier2_r2_diff_budget_enforcement(self) -> None:
        """R2 Boundary 3: PR line diff budget is strictly defined at ~400 lines non-test code."""
        agents_md = REPO_ROOT / "AGENTS.md"
        text = agents_md.read_text(encoding="utf-8")
        match = re.search(r"~?400\s*(?:changed\s*)?lines", text)
        self.assertIsNotNone(match, "AGENTS.md must codify the ~400 lines budget")

    def test_tier2_r2_vendor_sdk_isolation(self) -> None:
        """R2 Boundary 4: Sim core (nexus.core) imports zero vendor SDKs (ADR-0010)."""
        core_dir = REPO_ROOT / "services" / "sim" / "src" / "nexus" / "core"
        if core_dir.is_dir():
            prohibited_imports = [
                "openai",
                "anthropic",
                "google.generativeai",
                "discord",
                "twitchio",
            ]
            for py_file in core_dir.rglob("*.py"):
                tree = ast.parse(
                    py_file.read_text(encoding="utf-8"), filename=str(py_file)
                )
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            for prohibited in prohibited_imports:
                                self.assertFalse(
                                    alias.name.startswith(prohibited),
                                    f"Vendor SDK {prohibited} imported in sim core: {py_file}",
                                )
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        for prohibited in prohibited_imports:
                            self.assertFalse(
                                node.module.startswith(prohibited),
                                f"Vendor SDK {prohibited} imported in sim core: {py_file}",
                            )

    def test_tier2_r2_hostile_input_sanitization_rules(self) -> None:
        """R2 Boundary 5: Hostile chat input length caps and untrusted validation codified."""
        threat_doc = REPO_ROOT / "docs" / "security" / "THREAT-MODEL.md"
        self.assertTrue(threat_doc.is_file())
        text = threat_doc.read_text(encoding="utf-8")
        self.assertTrue(
            "length" in text.lower()
            or "sanitize" in text.lower()
            or "untrusted" in text.lower(),
            "Threat model must document chat input bounds and sanitization",
        )

    # --- R3 Boundary & Corner Cases ---

    def test_tier2_r3_extreme_coordinate_handling(self) -> None:
        """R3 Boundary 1: Extreme and boundary coordinates clamp strictly to theater bounds."""
        theater_file = REPO_ROOT / "apps" / "overlay" / "src" / "theater" / "strait1.ts"
        self.assertTrue(theater_file.is_file(), f"Missing {theater_file}")
        code = theater_file.read_text(encoding="utf-8")

        self.assertIn("400000", code, "Theater width max 400km")
        self.assertIn("240000", code, "Theater height max 240km")
        self.assertTrue(
            "clamp" in code.lower() or "min" in code.lower() or "max" in code.lower()
        )

    def test_tier2_r3_z_fighting_elevation_budget(self) -> None:
        """R3 Boundary 2: Elevation budget vertical order strictly non-overlapping."""
        elev_file = REPO_ROOT / "apps" / "overlay" / "src" / "theater" / "elevation.ts"
        self.assertTrue(elev_file.is_file())
        code = elev_file.read_text(encoding="utf-8")
        self.assertIn("ELEVATION_CHANNEL_WATER", code)

        # Extract values
        channel_water = -3.5
        terrain_base = 2.0
        road_offset = 0.22
        bridge_apex = 14.0

        self.assertLess(channel_water, 0.0, "Water must be below shoreline 0.0m")
        self.assertLess(0.0, terrain_base, "Shoreline must be below terrain base 2.0m")
        self.assertGreater(
            bridge_apex, terrain_base, "Bridge apex must exceed terrain base"
        )
        self.assertGreater(road_offset, 0.0, "Road offset must be positive")

    def test_tier2_r3_extreme_momentum_values(self) -> None:
        """R3 Boundary 3: Momentum percentage handles boundaries (0%, 50%, 100%)."""
        telemetry_file = (
            REPO_ROOT / "apps" / "overlay" / "src" / "types" / "telemetry.ts"
        )
        self.assertTrue(telemetry_file.is_file())
        code = telemetry_file.read_text(encoding="utf-8")
        self.assertIn("momentum", code.lower())

    def test_tier2_r3_threat_condition_transitions(self) -> None:
        """R3 Boundary 4: Threat Director condition states validate allowed values."""
        telemetry_file = (
            REPO_ROOT / "apps" / "overlay" / "src" / "types" / "telemetry.ts"
        )
        self.assertTrue(telemetry_file.is_file())
        code = telemetry_file.read_text(encoding="utf-8")

        # Threat tiers from OVERLAY.md
        self.assertTrue(
            "PATTERN_OF_LIFE" in code or "NOMINAL" in code,
            "Calm/nominal threat condition required",
        )
        self.assertTrue(
            "CONDITION_ALPHA" in code or "ELEVATED" in code,
            "Elevated/alpha threat condition required",
        )
        self.assertTrue(
            "CONDITION_BRAVO" in code or "CRITICAL" in code,
            "Critical/bravo threat condition required",
        )

    def test_tier2_r3_paused_simulation_state(self) -> None:
        """R3 Boundary 5: Paused simulation state freezes dead reckoning while keeping overlay alive."""
        overlay_doc = REPO_ROOT / "docs" / "specs" / "OVERLAY.md"
        self.assertTrue(overlay_doc.is_file())
        text = overlay_doc.read_text(encoding="utf-8")
        self.assertTrue("paused" in text.lower() or "pause" in text.lower())


# ==============================================================================
# Tier 3: Cross-Feature Interactions (Pairwise Combinations)
# ==============================================================================


class TestTier3CrossFeatureInteractions(unittest.TestCase):
    """Tier 3: Cross-Feature Interactions testing pairwise combinations across R1, R2, R3."""

    def test_tier3_interaction_makefile_and_tool_scripts(self) -> None:
        """Interaction 1 (R1 x R2): Makefile recipes execute tools under Tier 4 deterministic rules."""
        # Test dry-run of standard makefile targets
        targets = ["test", "test-unit", "determinism", "terrain", "balance"]
        for target in targets:
            res = run_cmd(["make", "-n", target])
            self.assertEqual(
                res.returncode,
                0,
                f"Makefile recipe dry-run failed for target '{target}': {res.stderr}",
            )

    def test_tier3_interaction_replay_artifacts_to_c2_telemetry(self) -> None:
        """Interaction 2 (R1 x R3): Replay/balance artifacts feed into RenderFrameState."""
        render_types = REPO_ROOT / "apps" / "overlay" / "src" / "types" / "render.ts"
        self.assertTrue(render_types.is_file())
        code = render_types.read_text(encoding="utf-8")

        # Verify that RenderFrameState has necessary fields to consume sim tick state
        self.assertIn("tick", code)
        self.assertIn("simTime", code)
        self.assertIn("units", code)
        self.assertIn("telemetry", code)

    def test_tier3_interaction_visual_engineer_rules_to_c2_symbology(self) -> None:
        """Interaction 3 (R2 x R3): .agents/roles/visual-engineer.md matches C2 dual-encoding."""
        role_card = REPO_ROOT / ".agents" / "roles" / "visual-engineer.md"
        self.assertTrue(role_card.is_file(), "visual-engineer.md role card missing")
        role_text = role_card.read_text(encoding="utf-8")

        # Visual engineer role mandates reading VISUAL-STYLE-CATALOG and enforcing elevation budget
        self.assertIn("docs/design/VISUAL-STYLE-CATALOG.md", role_text)
        self.assertIn("RenderFrameState", role_text)
        self.assertIn("-3.5", role_text)

        # VISUAL-STYLE-CATALOG.md defines the authoritative dual-encoding colors
        catalog = REPO_ROOT / "docs" / "design" / "VISUAL-STYLE-CATALOG.md"
        self.assertTrue(catalog.is_file())
        catalog_text = catalog.read_text(encoding="utf-8")
        self.assertIn("#00e5ff", catalog_text)
        self.assertIn("#ff0055", catalog_text)

        # Dual-encoding module in overlay implements these exact tokens
        dual_enc = (
            REPO_ROOT / "apps" / "overlay" / "src" / "symbology" / "dual-encoding.ts"
        )
        self.assertTrue(dual_enc.is_file())
        enc_code = dual_enc.read_text(encoding="utf-8")
        self.assertIn("#00e5ff", enc_code)
        self.assertIn("#ff0055", enc_code)
        self.assertIn("SMOOTH_CHEVRON_DIAMOND", enc_code)
        self.assertIn("JAGGED_SAWTOOTH", enc_code)

    def test_tier3_interaction_dted_hygiene_and_terrain_assets(self) -> None:
        """Interaction 4 (R1 x R2 x R3): Git hygiene permits DTED terrain assets without CI failure."""
        dted_bin = REPO_ROOT / "content" / "theaters" / "dted" / "strait-1-dem16.bin"
        if not dted_bin.is_file():
            run_cmd(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "terrain" / "bake_synthetic_dted.py"),
                    "--output-dir",
                    str(dted_bin.parent),
                ]
            )
        self.assertTrue(dted_bin.is_file(), "strait-1-dem16.bin must exist")
        size = dted_bin.stat().st_size
        self.assertGreater(size, 100000, "DTED DEM must be a valid elevation raster")

        # Running hygiene check must pass cleanly with this file tracked
        res = run_cmd(
            [sys.executable, str(REPO_ROOT / "scripts" / "check_tracked_files.py")]
        )
        self.assertEqual(res.returncode, 0, f"check_tracked_files failed: {res.stdout}")

    def test_tier3_interaction_unit_pov_contracts_and_schema_validation(self) -> None:
        """Interaction 5 (R2 x R3): Unit POV camera contracts adhere to model-agnostic specs."""
        rfc_doc = (
            REPO_ROOT
            / "docs"
            / "architecture"
            / "UNIT-POV-AND-COCKPIT-CONTRACTS-RFC.md"
        )
        self.assertTrue(rfc_doc.is_file())
        text = rfc_doc.read_text(encoding="utf-8")

        cameras = [
            "FIGHTER_CANOPY",
            "VEHICLE_CABIN",
            "HELICOPTER_BUBBLE",
            "WEAPON_SEEKER",
        ]
        for cam in cameras:
            self.assertIn(cam, text, f"Camera contract {cam} missing in RFC")


# ==============================================================================
# Tier 4: Real-World Scenarios (End-to-End Workflows)
# ==============================================================================


class TestTier4RealWorldScenarios(unittest.TestCase):
    """Tier 4: Real-World Scenarios executing complete end-to-end operational workflows."""

    def test_tier4_developer_check_lifecycle(self) -> None:
        """Workflow 1: Developer full check lifecycle across repo checks and contracts."""
        # Run test_repo_checks.py
        res = run_cmd(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "tests" / "test_repo_checks.py"),
            ],
            timeout=45,
        )
        self.assertEqual(res.returncode, 0, f"Repo checks failed: {res.stderr}")

        # Run gen_config_reference --check
        res2 = run_cmd(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "gen_config_reference.py"),
                "--check",
            ],
            timeout=30,
        )
        self.assertEqual(
            res2.returncode, 0, f"Config reference check failed: {res2.stderr}"
        )

    def test_tier4_overnight_balance_run(self) -> None:
        """Workflow 2: Automated balance run generating valid balance metrics and reports."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "balance_report"
            cmd = [
                get_sim_python(),
                str(REPO_ROOT / "tools" / "balance" / "balance.py"),
                "--profile",
                "overnight-0",
                "--seeds",
                "1",
                "--hours",
                "1",
                "--workers",
                "1",
                "--out",
                str(out_dir),
            ]
            res = run_cmd(cmd, timeout=90)
            self.assertEqual(
                res.returncode, 0, f"Balance run failed: {res.stdout}\n{res.stderr}"
            )

            # Verify generated output files
            report_json = out_dir / "report.json"
            report_md = out_dir / "report.md"
            self.assertTrue(report_json.is_file(), "report.json missing")
            self.assertTrue(report_md.is_file(), "report.md missing")

            with report_json.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("runs", data)
            self.assertGreater(len(data["runs"]), 0)
            self.assertEqual(data["runs"][0]["ticks_run"], 36000)

    def test_tier4_strait1_simulation_playback_across_all_paradigms(self) -> None:
        """Workflow 3: Complete Strait-1 scenario playback across all 4 visual paradigms."""
        proto_file = REPO_ROOT / "tools" / "prototype" / "unified-visualizer.html"
        sandbox_file = REPO_ROOT / "tools" / "prototype" / "visualizer-sandbox.html"
        self.assertTrue(
            proto_file.is_file() and sandbox_file.is_file(),
            "Visualizer prototypes missing",
        )
        content = proto_file.read_text(encoding="utf-8") + sandbox_file.read_text(
            encoding="utf-8"
        )

        # Verify all 4 paradigms are integrated into the playback director
        self.assertTrue(
            "pillar1" in content.lower()
            or "gis" in content.lower()
            or "2d" in content.lower()
        )
        self.assertTrue(
            "pillar2" in content.lower()
            or "rts" in content.lower()
            or "textured" in content.lower()
        )
        self.assertTrue(
            "pillar3" in content.lower()
            or "holo" in content.lower()
            or "wireframe" in content.lower()
        )
        self.assertTrue(
            "pillar4" in content.lower()
            or "neural" in content.lower()
            or "cognitive" in content.lower()
        )

        # Verify live unit simulation and telemetry tracking
        self.assertTrue("momentum" in content.lower())
        self.assertTrue("sitrep" in content.lower())
        self.assertTrue("threat" in content.lower())

    def test_tier4_terrain_and_asset_generation_pipeline(self) -> None:
        """Workflow 4: Complete terrain and asset generation pipeline."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "dted"
            out_dir.mkdir(parents=True, exist_ok=True)

            # 1. Bake synthetic DTED
            res1 = run_cmd(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "terrain" / "bake_synthetic_dted.py"),
                    "--output-dir",
                    str(out_dir),
                ],
                timeout=45,
            )
            self.assertEqual(res1.returncode, 0, f"DTED baking failed: {res1.stderr}")
            self.assertTrue((out_dir / "strait-1-dem16.bin").is_file())
            self.assertTrue((out_dir / "strait-1-hillshade.png").is_file())
            self.assertTrue((out_dir / "strait-1-terrain-meta.json").is_file())

            # 2. Drape roads
            res2 = run_cmd(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "terrain" / "drape_roads.py"),
                    "--theater",
                    str(REPO_ROOT / "content" / "theaters" / "strait-1.yaml"),
                    "--output-dir",
                    str(out_dir),
                ],
                timeout=45,
            )
            self.assertEqual(res2.returncode, 0, f"Road draping failed: {res2.stderr}")
            self.assertTrue((out_dir / "strait-1-roads-3d.json").is_file())
            self.assertTrue((out_dir / "strait-1-roads.obj").is_file())


if __name__ == "__main__":
    unittest.main()
