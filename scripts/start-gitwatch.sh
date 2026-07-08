#!/bin/sh
# Auto-commit (and optionally push) on file changes.
#
# Install gitwatch once (macOS):
#   brew install gitwatch
#
# Usage:
#   ./scripts/start-gitwatch.sh          # commit only
#   ./scripts/start-gitwatch.sh --push   # commit + push to origin

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

if [ "$1" = "--push" ]; then
  echo "gitwatch: will push to origin after each commit"
fi

echo "Watching $ROOT (Ctrl+C to stop)"
if [ "$1" = "--push" ]; then
  exec gitwatch -f -r origin -m "Update" .
else
  exec gitwatch -f -m "Update" .
fi
