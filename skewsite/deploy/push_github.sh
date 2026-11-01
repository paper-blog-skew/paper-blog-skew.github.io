#!/bin/bash
# Build the site from its bundles and publish dist/ to GitHub Pages.
#
#     deploy/push_github.sh                 # build, render check, copy dist/ into the Pages repo, commit, push
#     SKIP_RENDER_CHECK=1 deploy/push_github.sh
#
# Settings (environment): PAGES_REPO (required: the git remote of the Pages repository) and PAGES_DIR (a git checkout
# outside any synced folder, default ~/sites/skewsite). Only the built pages are published, never the sources.
set -euo pipefail
PAGES_REPO="${PAGES_REPO:?set PAGES_REPO to the git remote of the GitHub Pages repository}"
PAGES_DIR="${PAGES_DIR:-$HOME/sites/skewsite}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"; cd "$HERE"

echo "==> build"
python3 build.py
if [ "${SKIP_RENDER_CHECK:-0}" != "1" ]; then python3 tools/render_check.py || { echo "render check failed: not published (see build/render_check.json)"; exit 1; }; fi

echo "==> copy dist/ -> $PAGES_DIR"
mkdir -p "$PAGES_DIR"
if [ ! -d "$PAGES_DIR/.git" ]; then git -C "$PAGES_DIR" init -q -b main; git -C "$PAGES_DIR" remote add origin "$PAGES_REPO"; fi
rsync -a --delete --exclude '.git' --exclude '.DS_Store' dist/ "$PAGES_DIR/"
touch "$PAGES_DIR/.nojekyll"

echo "==> commit + push"
git -C "$PAGES_DIR" add -A
if git -C "$PAGES_DIR" diff --cached --quiet; then echo "    nothing changed since the last push"; else git -C "$PAGES_DIR" commit -q -m "site build $(date '+%Y-%m-%d %H:%M')"; fi
git -C "$PAGES_DIR" push -u origin main
