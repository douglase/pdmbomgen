#!/usr/bin/env bash
# Build the static Pages site for this vault repo: index.html + the
# downloadable .xlsx, stamped with the git commit that last touched the
# BOM export. Called by both CI configs (.github/workflows/pages.yml and
# .gitlab-ci.yml) — see SETUP.md.
#
# Usage: scripts/build_pages.sh INPUT.{csv|xml} [CONFIG.toml] [OUTDIR]
#
# Requires full git history (not a shallow clone) so `git log -1 -- INPUT`
# finds the real last commit touching INPUT, not just HEAD. Both CI configs
# set this up (fetch-depth: 0 / GIT_DEPTH: 0).
set -euo pipefail

input=${1:?"usage: build_pages.sh INPUT.csv|INPUT.xml [CONFIG.toml] [OUTDIR]"}
config=${2:-bomgen.toml}
outdir=${3:-_site}
stem=$(basename "$input")
stem=${stem%.*}

rev=$(git log -1 --format='%h (%ad)' --date=short -- "$input" 2>/dev/null || true)
if [ -z "$rev" ]; then
    rev="uncommitted"
    echo "warning: '$input' has no commit history yet (staged/new file?) — " \
         "reports will be stamped 'uncommitted'" >&2
fi
echo "source revision: $rev"

mkdir -p "$outdir"
# `bomgen` is the console-script entry point installed from requirements.txt
bomgen "$input" -c "$config" \
    --html "$outdir/index.html" \
    --xlsx "$outdir/${stem}_BOM.xlsx" \
    --source-rev "$rev"

echo "site built in $outdir/:"
ls -l "$outdir"
