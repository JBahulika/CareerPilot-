#!/bin/sh
# Auto-commit and push to GitHub when files change.
#
# Install once (macOS):
#   brew install gitwatch
#
# Usage:
#   ./scripts/start-gitwatch.sh          # commit only
#   ./scripts/start-gitwatch.sh --push   # commit + push to origin (GitHub)

set -e
cd "$(dirname "$0")/.."

if ! command -v gitwatch >/dev/null 2>&1; then
  echo "gitwatch not found. Install with: brew install gitwatch"
  exit 1
fi

# Strip Cursor co-author lines from auto-commits
git config core.hooksPath .githooks

ROOT="$(pwd)"
chmod +x "$ROOT/.githooks/prepare-commit-msg" 2>/dev/null || true
chmod +x "$ROOT/scripts/gitwatch-commit-msg.sh" 2>/dev/null || true

PUSH=0
if [ "$1" = "--push" ]; then
  PUSH=1
  echo "gitwatch: auto-commit + push to origin on every save"
else
  echo "gitwatch: auto-commit only (pass --push to also push to GitHub)"
fi

echo "Watching $ROOT (Ctrl+C to stop)"
if [ "$PUSH" = "1" ]; then
  exec gitwatch -f -r origin -m "Update" .
else
  exec gitwatch -f -m "Update" .
fi
