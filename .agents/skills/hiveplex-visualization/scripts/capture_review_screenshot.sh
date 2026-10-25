#!/usr/bin/env bash
# Headless visual verification script for Hiveplex HTML sandboxes and overlays.
# Usage: ./capture_review_screenshot.sh <url-or-html-path> <output-png-path> [window-size] [time-budget-ms]

set -euo pipefail

TARGET="${1:-}"
OUTPUT="${2:-}"
SIZE="${3:-1600,1050}"
BUDGET="${4:-2500}"

if [ -z "$TARGET" ] || [ -z "$OUTPUT" ]; then
  echo "Usage: $0 <url-or-html-path> <output-png-path> [window-size: 1600,1050] [time-budget-ms: 2500]"
  exit 1
fi

# Detect absolute file path vs URL
if [[ "$TARGET" != http* ]] && [[ "$TARGET" != file://* ]]; then
  TARGET="file://$(cd "$(dirname "$TARGET")" && pwd)/$(basename "$TARGET")"
fi

CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ ! -f "$CHROME_BIN" ]; then
  CHROME_BIN="$(command -v google-chrome || command -v chromium || true)"
fi

if [ -z "$CHROME_BIN" ] || [ ! -x "$CHROME_BIN" ]; then
  echo "Error: Google Chrome binary not found." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

echo "Capturing visual review snapshot: $TARGET -> $OUTPUT ($SIZE)"
"$CHROME_BIN" \
  --headless=new \
  --screenshot="$OUTPUT" \
  --window-size="$SIZE" \
  --virtual-time-budget="$BUDGET" \
  --hide-scrollbars \
  --disable-gpu-shader-disk-cache \
  "$TARGET" >/dev/null 2>&1

if [ -f "$OUTPUT" ]; then
  FILE_SIZE=$(wc -c < "$OUTPUT" | tr -d ' ')
  echo "Captured successfully: $OUTPUT ($FILE_SIZE bytes)"
else
  echo "Error: Screenshot failed to generate." >&2
  exit 1
fi
