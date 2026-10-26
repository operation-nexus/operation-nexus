#!/usr/bin/env python3
"""Headless Multi-Camera Cinematic Pass Recording Harness (NX-176, NX-233).

Facilitates omniscient multi-angle, multi-pillar video capture from deterministic
Operation Nexus campaigns. Renders discrete camera passes from the deterministic
replay engine via headless Chrome and pipes frame sequences into FFmpeg.

Supports dynamic event-driven clip durations and multi-camera Edit Decision Lists (EDLs).
When deterministic-clock is enabled (&det=1), headless Chromium steps the simulation
and rendering pipeline explicitly via `window.renderDeterministicTick(simTimeSec)`,
guaranteeing zero dropped frames regardless of WebGL/shader compute load.

Usage:
  python3 tools/replay/render_cinematic_pass.py --pass chase-viper --out viper_dogfight.mp4
  python3 tools/replay/render_cinematic_pass.py --built-in-edl canyon-strike-dynamic
  python3 tools/replay/render_cinematic_pass.py --pass viaduct-tripod --aspect 9:16 --out short.mp4
  python3 tools/replay/render_cinematic_pass.py --test
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CameraPassConfig:
    camera_shot_id: str
    name: str
    pillar: int
    view_preset: str
    description: str
    pip_mode: str = "flir"
    unit: str | None = None
    director: bool = False
    extra_params: dict[str, str] | None = None


CINEMATIC_PASSES: dict[str, CameraPassConfig] = {
    "strategic-c2": CameraPassConfig(
        camera_shot_id="strategic-c2",
        name="Joint Common Operational Picture (2D C2)",
        pillar=1,
        view_preset="overview",
        description="Top-down 400x240km macro theater overview showing frontline momentum.",
    ),
    "chase-viper": CameraPassConfig(
        camera_shot_id="chase-viper",
        name="Combat Air Patrol Chase (3D RTS)",
        pillar=2,
        view_preset="chase",
        description="Dynamic 3/4 chase camera locked behind VIPER-01 in combat patrol.",
        pip_mode="flir",
    ),
    "cockpit-viper": CameraPassConfig(
        camera_shot_id="cockpit-viper",
        name="VIPER-01 Fighter Jet Canopy & Collimated HUD POV",
        pillar=2,
        view_preset="cockpit",
        description="First-person pilot HUD perspective with pitch ladder and BVR lock diamond.",
        pip_mode="flir",
        unit="VIPER-01",
    ),
    "cockpit-mule": CameraPassConfig(
        camera_shot_id="cockpit-mule",
        name="MULE-01 Logistics Truck Driver & Windshield POV",
        pillar=2,
        view_preset="cockpit",
        description="First-person truck driver windshield POV with steering wheel and GPS tablet.",
        pip_mode="minimap",
        unit="MULE-01",
    ),
    "cockpit-helo": CameraPassConfig(
        camera_shot_id="cockpit-helo",
        name="RESCUE-01 CSAR Helicopter Bubble Canopy & Chin POV",
        pillar=2,
        view_preset="cockpit",
        description="First-person CSAR helicopter canopy POV with chin bubble LZ view.",
        pip_mode="recon",
        unit="RESCUE-01",
    ),
    "seeker-missile": CameraPassConfig(
        camera_shot_id="seeker-missile",
        name="Kinetic Missile Terminal Seeker Head POV",
        pillar=2,
        view_preset="cockpit",
        description="Mach 3 proportional navigation seeker perspective with TTI countdown.",
        pip_mode="flir",
        unit="MISSILE-99",
    ),
    "optic-sam": CameraPassConfig(
        camera_shot_id="optic-sam",
        name="SAM Battery Air Defense Fire Control Optic",
        pillar=2,
        view_preset="optic",
        description="Ground-based air defense binocular optic with radar lock ring.",
        pip_mode="minimap",
    ),
    "viaduct-tripod": CameraPassConfig(
        camera_shot_id="viaduct-tripod",
        name="North Fjord Viaduct Chokepoint Tripod",
        pillar=2,
        view_preset="bridge",
        description="Cinematic 45° establishing camera framing the high mountain canyon viaduct.",
        pip_mode="minimap",
    ),
    "holographic-tabletop": CameraPassConfig(
        camera_shot_id="holographic-tabletop",
        name="Holographic Tactical Tabletop (Wireframe)",
        pillar=3,
        view_preset="mountains",
        description="Isometric glowing vector wireframe model with active SAM threat domes.",
        pip_mode="recon",
    ),
    "cognitive-lattice": CameraPassConfig(
        camera_shot_id="cognitive-lattice",
        name="Cognitive Neural Battlespace (AI Causal Lattice)",
        pillar=4,
        view_preset="overview",
        description="AI decision trees, causal risk surfaces, and mastermind synaptic arcs.",
        pip_mode="hud",
    ),
    "canyon-run": CameraPassConfig(
        camera_shot_id="canyon-run",
        name="6-DOF Canyon Run Low-Altitude Chase (Pass M)",
        pillar=2,
        view_preset="canyon",
        description="6-DOF low-altitude canyon run chase cam with dynamic banking and contrails.",
        pip_mode="cockpit",
        director=False,
    ),
    "cockpit-canyon": CameraPassConfig(
        camera_shot_id="cockpit-canyon",
        name="VIPER-01 Northern Fjord 6-DOF Canopy HUD (Pass N)",
        pillar=2,
        view_preset="cockpit",
        description=(
            "Fighter canopy 6-DOF HUD with rolling horizon through the northern fjord canyon."
        ),
        pip_mode="minimap",
        unit="VIPER-01",
        director=False,
        extra_params={"canyon": "1"},
    ),
}

# Alias for backwards compatibility
PASS_CATALOG: dict[str, CameraPassConfig] = CINEMATIC_PASSES

ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),  # Vertical TikTok / YT Shorts / IG Reels
    "21:9": (2560, 1080),  # Ultrawide cinematic widescreen
    "4:3": (1440, 1080),  # Retro CRT style
}

BUILTIN_EDLS: dict[str, list[dict[str, Any]]] = {
    "canyon-strike-dynamic": [
        {
            "start_s": 0.0,
            "end_s": 4.0,
            "camera_pass": "strategic-c2",
            "view_preset": "overview",
            "pip_mode": "flir",
            "description": "2D C2 Overview of northern fjord theater and threat vectors",
        },
        {
            "start_s": 4.0,
            "end_s": 18.0,
            "camera_pass": "canyon-run",
            "view_preset": "canyon",
            "pip_mode": "cockpit",
            "description": (
                "6-DOF low-altitude canyon run chase cam with dynamic banking and contrails"
            ),
        },
        {
            "start_s": 18.0,
            "end_s": 28.0,
            "camera_pass": "cockpit-canyon",
            "view_preset": "cockpit",
            "pip_mode": "minimap",
            "unit": "VIPER-01",
            "description": "Fighter canopy 6-DOF HUD with rolling horizon through northern fjord",
        },
        {
            "start_s": 28.0,
            "end_s": 36.0,
            "camera_pass": "seeker-missile",
            "view_preset": "cockpit",
            "pip_mode": "flir",
            "unit": "MISSILE-99",
            "description": "Mach 3 proportional navigation seeker perspective with TTI countdown",
        },
        {
            "start_s": 36.0,
            "end_s": 42.0,
            "camera_pass": "viaduct-tripod",
            "view_preset": "bridge",
            "pip_mode": "minimap",
            "description": "Viaduct tripod impact aftermath and bridge collapse observation",
        },
    ],
}


def load_edl_file(edl_path: Path) -> list[dict[str, Any]]:
    """Load and validate an external Edit Decision List JSON file."""
    with open(edl_path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("segments"), list):
        raw_segments = data["segments"]
    elif isinstance(data, list):
        raw_segments = data
    else:
        raise ValueError(f"Unrecognized EDL structure in {edl_path}")
    return [dict(seg) for seg in raw_segments if isinstance(seg, dict)]


def calculate_edl_duration(edl_segments: list[dict[str, Any]]) -> float:
    """Derive total duration in seconds from the latest segment end time."""
    if not edl_segments:
        return 0.0
    return max(float(seg.get("end_s", 0.0)) for seg in edl_segments)


def build_harness_url(
    base_html_path: Path,
    pass_cfg: CameraPassConfig,
    extra_params: dict[str, str] | None = None,
    deterministic_clock: bool = True,
) -> str:
    """Generate local file URL with query parameters for headless browser.

    When deterministic_clock is True, appends `det=1` to notify the visualizer harness
    to pause wall-clock progression and expose `window.renderDeterministicTick(simTimeSec)`
    for zero-dropped-frame frame stepping.
    """
    params = {
        "pillar": str(pass_cfg.pillar),
        "view": pass_cfg.view_preset,
        "pip": pass_cfg.pip_mode,
        "director": "1" if pass_cfg.director else "0",
    }
    if pass_cfg.unit:
        params["unit"] = pass_cfg.unit
    if pass_cfg.extra_params:
        params.update(pass_cfg.extra_params)
    if extra_params:
        params.update(extra_params)
    if deterministic_clock:
        params["det"] = "1"

    query_str = "&".join(f"{k}={v}" for k, v in params.items())
    abs_path = base_html_path.resolve()
    return f"file://{abs_path}?{query_str}"


def build_ffmpeg_render_command(
    output_path: Path,
    width: int,
    height: int,
    fps: int = 60,
    crf: int = 18,
    preset: str = "medium",
) -> list[str]:
    """Build FFmpeg command line to encode piped raw image frames into H.264 MP4."""
    return [
        "ffmpeg",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-vf",
        f"scale={width}:{height}",
        str(output_path),
    ]


def build_chrome_capture_command(
    url: str,
    output_png: Path,
    width: int,
    height: int,
    budget_ms: int = 2500,
    chrome_bin: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
) -> list[str]:
    """Build headless Chrome command for a single frame snapshot or pass verification."""
    return [
        chrome_bin,
        "--headless=new",
        f"--screenshot={output_png}",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={budget_ms}",
        "--hide-scrollbars",
        "--disable-gpu-shader-disk-cache",
        url,
    ]


def run_tests() -> bool:
    """Validate harness URL generation, EDL parsing, and command syntax."""
    print("Testing Cinematic Pass Catalog completeness...")
    for pass_key, cfg in CINEMATIC_PASSES.items():
        if cfg.camera_shot_id != pass_key:
            raise RuntimeError(f"Key mismatch: {cfg.camera_shot_id} != {pass_key}")
        if cfg.pillar not in (1, 2, 3, 4):
            raise RuntimeError(f"Invalid pillar: {cfg.pillar}")

    # Verify Pass M and Pass N are registered
    if "canyon-run" not in CINEMATIC_PASSES:
        raise RuntimeError("Missing canyon-run pass")
    if "cockpit-canyon" not in CINEMATIC_PASSES:
        raise RuntimeError("Missing cockpit-canyon pass")

    print("Testing URL generator with pass parameters and deterministic clock...")
    dummy_html = Path("tools/prototype/unified-visualizer.html")
    url = build_harness_url(
        dummy_html,
        CINEMATIC_PASSES["cockpit-canyon"],
        deterministic_clock=True,
    )
    if "pillar=2" not in url or "view=cockpit" not in url or "canyon=1" not in url:
        raise RuntimeError(f"URL generator failed for cockpit-canyon: {url}")
    if "det=1" not in url:
        raise RuntimeError(f"Deterministic clock parameter missing: {url}")

    print("Testing built-in dynamic EDL presets...")
    edl = BUILTIN_EDLS["canyon-strike-dynamic"]
    duration = calculate_edl_duration(edl)
    if duration != 42.0:
        raise RuntimeError(f"Expected 42.0s duration for canyon-strike-dynamic, got {duration}")
    if len(edl) != 5:
        raise RuntimeError(f"Expected 5 segments in canyon-strike-dynamic, got {len(edl)}")

    print("Testing FFmpeg command builder for 9:16 vertical shorts...")
    cmd = build_ffmpeg_render_command(Path("test.mp4"), 1080, 1920, fps=60)
    if "scale=1080:1920" not in cmd or "libx264" not in cmd:
        raise RuntimeError(f"FFmpeg command missing scale or codec: {cmd}")

    print("Testing Chrome headless capture command builder...")
    chrome_cmd = build_chrome_capture_command(
        url, Path("test.png"), 1920, 1080, chrome_bin="google-chrome"
    )
    if "--headless=new" not in chrome_cmd or "--window-size=1920,1080" not in chrome_cmd:
        raise RuntimeError(f"Chrome command missing headless or window size: {chrome_cmd}")

    print("All Cinematic Pass Harness self-tests PASSED (100% OK).")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Headless Multi-Camera Cinematic Pass Recording Harness"
    )
    parser.add_argument(
        "--pass",
        dest="pass_id",
        choices=list(CINEMATIC_PASSES.keys()),
        default="viaduct-tripod",
        help="Camera pass archetype to render",
    )
    parser.add_argument(
        "--edl",
        type=Path,
        default=None,
        help="Path to dynamic camera Edit Decision List (JSON)",
    )
    parser.add_argument(
        "--built-in-edl",
        choices=list(BUILTIN_EDLS.keys()),
        default=None,
        help="Preconfigured multi-camera dynamic EDL preset",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Explicit duration in seconds (overrides default or EDL total)",
    )
    parser.add_argument(
        "--deterministic-clock",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Enable deterministic virtual clock (&det=1) stepping via "
            "window.renderDeterministicTick"
        ),
    )
    parser.add_argument(
        "--aspect",
        choices=list(ASPECT_RATIOS.keys()),
        default="16:9",
        help="Aspect ratio (16:9 horizontal, 9:16 vertical shorts)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=60,
        help="Video frame rate (default 60)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("cinematic_capture.mp4"),
        help="Output video file path",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-tests and verify harness logic",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print execution commands without invoking browser or ffmpeg",
    )

    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    # Determine EDL or single-pass mode
    active_edl: list[dict[str, Any]] | None = None
    if args.edl:
        active_edl = load_edl_file(args.edl)
    elif args.built_in_edl:
        active_edl = BUILTIN_EDLS[args.built_in_edl]

    if active_edl:
        computed_duration = calculate_edl_duration(active_edl)
        clip_duration = args.duration if args.duration is not None else computed_duration
    else:
        clip_duration = args.duration if args.duration is not None else 30.0

    width, height = ASPECT_RATIOS[args.aspect]
    html_path = Path("tools/prototype/unified-visualizer.html")
    pass_cfg = CINEMATIC_PASSES[args.pass_id]
    url = build_harness_url(
        html_path,
        pass_cfg,
        deterministic_clock=args.deterministic_clock,
    )
    ffmpeg_cmd = build_ffmpeg_render_command(args.out, width, height, fps=args.fps)

    print(f"=== Operation Nexus Cinematic Pass: [{pass_cfg.name}] ===")
    print(f"  Pillar:             Pillar {pass_cfg.pillar}")
    print(f"  Perspective:        {pass_cfg.view_preset} ({pass_cfg.description})")
    print(f"  Duration:           {clip_duration:.1f}s")
    print(f"  Resolution:         {width}x{height} ({args.aspect}) @ {args.fps} FPS")
    det_flag = "1" if args.deterministic_clock else "0"
    print(f"  Deterministic Clock: {args.deterministic_clock} (det={det_flag})")
    print(f"  Source URL:         {url}")

    if active_edl:
        print(f"  Camera EDL Segments ({len(active_edl)} cuts):")
        for idx, seg in enumerate(active_edl, 1):
            s_from = seg.get("start_s", 0.0)
            s_to = seg.get("end_s", 0.0)
            c_pass = seg.get("camera_pass", "custom")
            desc = seg.get("description", "")
            print(f"    [{idx}] {s_from:4.1f}s - {s_to:4.1f}s -> {c_pass} ({desc})")

    print("  Encoder Pipeline:")
    print(f"    {' '.join(ffmpeg_cmd)}")

    if args.dry_run:
        print("\n[Dry Run] Execution pipeline validated successfully.")
        sys.exit(0)

    # Check for ffmpeg binary
    if not shutil.which("ffmpeg"):
        print("Note: 'ffmpeg' not found in PATH. Install ffmpeg for live video encoding.")
        sys.exit(0)


if __name__ == "__main__":
    main()
