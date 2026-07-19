#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 E Douglas, University of Arizona and contributors
# Build the static Pages site: index.html + the downloadable .xlsx, side by
# side in one output directory. Called by both CI configs
# (.github/workflows/pages.yml and .gitlab-ci.yml) so the build stays
# identical across GitHub and GitLab — see PAGES_SETUP.md.
#
# Usage: scripts/build_pages.sh INPUT.{csv|xml} [CONFIG.toml] [OUTDIR]
# Set BUILD_DASHBOARD=1 to also publish the spec/RFQ budget dashboard +
# budget workbook (needs a specs column in the export — see bomgen.toml).
set -euo pipefail

input=${1:?"usage: build_pages.sh INPUT.csv|INPUT.xml [CONFIG.toml] [OUTDIR]"}
config=${2:-bomgen.toml}
outdir=${3:-_site}
stem=$(basename "$input")
stem=${stem%.*}

extra=()
if [ "${BUILD_DASHBOARD:-0}" = "1" ]; then
    extra=(--dashboard "$outdir/dashboard.html"
           --budget "$outdir/${stem}_Budget.xlsx")
fi

mkdir -p "$outdir"
# Same directory + same run => bomgen links the .xlsx from the HTML's
# download button automatically (relative href, works on any host).
python -m bomgen "$input" -c "$config" \
    --html "$outdir/index.html" \
    --xlsx "$outdir/${stem}_BOM.xlsx" \
    "${extra[@]}"

echo "site built in $outdir/:"
ls -l "$outdir"
