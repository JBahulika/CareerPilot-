#!/bin/sh
# One-time setup: use project git hooks (strips Cursor co-author from commits).
set -e
cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
chmod +x .githooks/prepare-commit-msg scripts/gitwatch-commit-msg.sh 2>/dev/null || true
echo "Git hooks enabled (.githooks/prepare-commit-msg)"
