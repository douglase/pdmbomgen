#!/usr/bin/env bash
# Refresh this vault repo's machinery from the latest pdmbomgen template.
#
#   bash scripts/update_from_template.sh
#
# Overwrites MACHINERY only:
#   scripts/build_pages.sh, scripts/update_from_template.sh (self),
#   .github/workflows/pages.yml, .gitlab-ci.yml, requirements.txt,
#   .gitignore, SETUP.md
# Never touches PAYLOAD:
#   vault/ (your data), bomgen.toml (your project config), README.md
# Preserves your BOM_INPUT / BOM_CONFIG values in both CI files.
#
# Options (env vars):
#   PDMBOMGEN_REPO  clone source (default https://github.com/douglase/pdmbomgen;
#                   use an SSH URL or a local path if https auth fails)
#   PDMBOMGEN_REF   branch/tag to pull the template from (default main)
#
# Portable: BSD (macOS) and GNU userlands — in-place edits use perl, never
# `sed -i`. Nothing is committed; review `git diff --cached` afterwards.
set -euo pipefail

tmp=""
trap '[ -z "$tmp" ] || rm -rf "$tmp"' EXIT

main() {
    local src=${PDMBOMGEN_REPO:-https://github.com/douglase/pdmbomgen}
    local ref=${PDMBOMGEN_REF:-main}

    # --- locate the vault repo root, wherever we were invoked from
    local root
    root=$(git rev-parse --show-toplevel 2>/dev/null) \
        || die "not inside a git repository — cd into your vault repo first"
    cd "$root"
    [ -d vault ] || [ -f bomgen.toml ] \
        || die "this doesn't look like a vault repo (no vault/ or bomgen.toml) — refusing to overwrite files in $root"
    [ -z "$(git status --porcelain)" ] \
        || die "working tree not clean — commit or stash first so this update is reviewable (and revertible) on its own"

    # --- fetch the template
    tmp=$(mktemp -d)
    echo "fetching template from $src @ $ref ..."
    git clone --quiet --depth 1 --branch "$ref" "$src" "$tmp/pdmbomgen" \
        || die "clone failed — if pdmbomgen is private, retry with:
  PDMBOMGEN_REPO=git@github.com:douglase/pdmbomgen bash scripts/update_from_template.sh"
    local T="$tmp/pdmbomgen/template-repo"
    [ -d "$T" ] || die "no template-repo/ found in the clone (ref '$ref' predates it?)"

    # --- capture your CI settings BEFORE overwriting anything
    local gh_input gh_conf gl_input gl_conf
    gh_input=$(setting 'BOM_INPUT:'  .github/workflows/pages.yml)
    gh_conf=$(setting  'BOM_CONFIG:' .github/workflows/pages.yml)
    gl_input=$(setting 'BOM_INPUT:'  .gitlab-ci.yml)
    gl_conf=$(setting  'BOM_CONFIG:' .gitlab-ci.yml)

    # --- copy machinery (each file only if the template ships it)
    put "$T/scripts/build_pages.sh"                scripts/build_pages.sh
    put "$T/scripts/update_from_template.sh"       scripts/update_from_template.sh
    put "$T/.github/workflows/pages.yml"           .github/workflows/pages.yml
    put "$T/.gitlab-ci.yml"                        .gitlab-ci.yml
    put "$T/requirements.txt"                      requirements.txt
    put "$T/.gitignore"                            .gitignore
    put "$T/SETUP.md"                              SETUP.md

    # --- restore your CI settings (portable in-place edit via perl)
    restore 'BOM_INPUT'  "$gh_input" .github/workflows/pages.yml
    restore 'BOM_CONFIG' "$gh_conf"  .github/workflows/pages.yml
    restore 'BOM_INPUT'  "$gl_input" .gitlab-ci.yml
    restore 'BOM_CONFIG' "$gl_conf"  .gitlab-ci.yml

    # --- stage and report; committing is yours to do after review
    git add -A
    echo ""
    echo "updated files:"
    git diff --cached --stat
    echo ""
    grep -Hn 'BOM_INPUT\|BOM_CONFIG' .github/workflows/pages.yml .gitlab-ci.yml 2>/dev/null \
        || true
    echo ""
    echo "review:  git diff --cached"
    echo "commit:  git commit -m 'Refresh template machinery from pdmbomgen' && git push"
    echo "undo:    git reset --hard HEAD"
}

die() { echo "error: $*" >&2; exit 1; }

# first value of "KEY: value" in a file ("" if file/key missing)
setting() {
    [ -f "$2" ] || { echo ""; return; }
    grep -m1 "$1" "$2" 2>/dev/null | sed 's/.*: *//' || true
}

# copy template file over local one; quietly skip files the template lacks
put() {
    [ -f "$1" ] || { echo "  (template has no $(basename "$2"); skipped)"; return; }
    mkdir -p "$(dirname "$2")"
    cp "$1" "$2"
    echo "  updated $2"
}

# rewrite "KEY: ..." line with the preserved value, keeping indentation
restore() {
    local key=$1 val=$2 file=$3
    [ -n "$val" ] || return 0
    [ -f "$file" ] || return 0
    KEY="$key" VAL="$val" perl -pi -e \
        's/^(\s*)\Q$ENV{KEY}\E:.*/$1$ENV{KEY}: $ENV{VAL}/' "$file"
    echo "  restored $key in $file -> $val"
}

# Everything runs from main() so bash parses this whole file before executing
# — required because the script overwrites ITSELF during the update.
main "$@"
