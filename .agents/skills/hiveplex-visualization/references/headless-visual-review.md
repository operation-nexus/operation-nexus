# Headless Visual Review & Iteration Runbook

## 1. Capturing Visual Verification Snapshots

When modifying or testing visual components, HTML sandboxes, or overlays, agents must visually verify their changes:

```bash
# Execute headless capture with virtual time budget to allow WebGL/RAF to render:
./scripts/capture_review_screenshot.sh path/to/sandbox.html output.png 1600,1050 2500
```

## 2. Verification Checklist

1. **Pixel Density Check:**
   Verify that non-background bytes are present and the render is not blank or stuck on black screen.
2. **Context Separation:**
   Ensure 2D thermal canvases and WebGL 3D contexts do NOT share the same canvas element (calling `getContext('2d')` on a WebGL canvas returns `null`).
3. **Multi-Camera Director Verification:**
   Verify camera angles for Wide Overview, 45° Combat Perspective, Top-Down Tactical Replay, and FLIR MFD.
4. **Responsive Formats:**
   Test desktop 16:9 ($1600\times 1050$ or $1280\times 720$) AND mobile vertical 9:16 ($600\times 1050$).
