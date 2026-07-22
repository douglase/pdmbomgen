#!/usr/bin/env bash
# Build the static Pages site for this vault repo: index.html + the
# downloadable .xlsx, stamped with the git commit that last touched the
# BOM export. Called by both CI configs (.github/workflows/pages.yml and
# .gitlab-ci.yml) — see SETUP.md.
#
# Usage: scripts/build_pages.sh INPUT.{csv|xml} [CONFIG.toml] [OUTDIR]
#
# Env toggles:
#   BUILD_DASHBOARD=1  also publish the spec/RFQ budget dashboard + workbook
#                      (needs a specs column in the export — see bomgen.toml)
#   BUILD_HISTORY=1    also rebuild every git tag under OUTDIR/v/<tag>/ with
#                      the CURRENT generator (yellow historical chrome, green
#                      change-highlighting vs the previous tag) and write a
#                      versions.js dropdown into every page directory.
#
# Requires full git history + tags (fetch-depth: 0 / GIT_DEPTH: 0) so
# `git log -- INPUT` finds the real last commit and tags are available.
set -euo pipefail

input=${1:?"usage: build_pages.sh INPUT.csv|INPUT.xml [CONFIG.toml] [OUTDIR]"}
config=${2:-bomgen.toml}
outdir=${3:-_site}
stem=$(basename "$input")
stem=${stem%.*}
BOMGEN=${BOMGEN:-bomgen}   # console script installed from requirements.txt

extra=()
if [ "${BUILD_DASHBOARD:-0}" = "1" ]; then
    extra=(--dashboard "$outdir/dashboard.html"
           --budget "$outdir/${stem}_Budget.xlsx")
fi

have_git=0
git rev-parse --git-dir >/dev/null 2>&1 && have_git=1

rev=""
diffargs=()
provargs=()
repo=""
src_url_base=""   # blob-URL prefix; append "<sha>/<path>" to link a file
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
src_url_for() { [ -n "$src_url_base" ] && echo "$src_url_base/$1/$input" || true; }
if [ "$have_git" = 1 ]; then
    rev=$(git log -1 --format='%h (%ad)' --date=short -- "$input" 2>/dev/null || true)
    # Current page diffs against the previous commit touching the input
    # (tag pages diff against the previous tag below).
    prev_commit=$(git log -2 --format=%H -- "$input" 2>/dev/null | sed -n 2p)
    if [ -n "$prev_commit" ] && git show "$prev_commit:$input" \
            > "$tmp/prev_input" 2>/dev/null; then
        diffargs=(--diff-against "$tmp/prev_input")
    fi

    # Build-provenance facts (repo/branch/commit + source-file link); CI env
    # vars are authoritative when present (GitHub Actions / GitLab CI).
    commit=$(git rev-parse --short HEAD 2>/dev/null || true)
    full_sha=$(git rev-parse HEAD 2>/dev/null || true)
    branch=${GITHUB_REF_NAME:-${CI_COMMIT_REF_NAME:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)}}
    [ "$branch" = "HEAD" ] && branch=""   # detached checkout
    if [ -n "${GITHUB_REPOSITORY:-}" ]; then
        repo="$GITHUB_REPOSITORY"
        src_url_base="${GITHUB_SERVER_URL:-https://github.com}/$GITHUB_REPOSITORY/blob"
    elif [ -n "${CI_PROJECT_URL:-}" ]; then
        repo="${CI_PROJECT_PATH:-$CI_PROJECT_URL}"
        src_url_base="$CI_PROJECT_URL/-/blob"
    else
        remote=$(git remote get-url origin 2>/dev/null || true)
        case "$remote" in
          *github.com*)
            repo=$(echo "$remote" | sed -E 's#(git@github\.com:|https?://[^/]*github\.com/)##; s#\.git$##')
            [ -n "$repo" ] && src_url_base="https://github.com/$repo/blob" ;;
          *) repo="$remote" ;;
        esac
    fi
    [ -n "$repo" ]   && provargs+=(--repo "$repo")
    [ -n "$branch" ] && provargs+=(--branch "$branch")
    [ -n "$commit" ] && provargs+=(--commit "$commit")
    u=$(src_url_for "$full_sha"); [ -n "$u" ] && provargs+=(--source-url "$u")
fi
if [ -z "$rev" ]; then
    rev="uncommitted"
    echo "warning: '$input' has no commit history yet (staged/new file?) — " \
         "reports will be stamped 'uncommitted'" >&2
fi
echo "source revision: $rev"

mkdir -p "$outdir"
$BOMGEN "$input" -c "$config" \
    --html "$outdir/index.html" \
    --xlsx "$outdir/${stem}_BOM.xlsx" \
    --source-rev "$rev" \
    "${extra[@]}" "${diffargs[@]}" "${provargs[@]}"

# ---- historical tag builds -------------------------------------------------
if [ "${BUILD_HISTORY:-0}" = "1" ] && [ "$have_git" = 1 ]; then
    tags=$(git tag --sort=creatordate)
    prev_tag=""
    built_tags=()
    for tag in $tags; do
        workdir="$tmp/tag-$tag"
        mkdir -p "$workdir"
        if ! git archive "$tag" 2>/dev/null | tar -x -C "$workdir"; then
            echo "warning: could not extract tag '$tag'; skipped" >&2
            prev_tag=$tag; continue
        fi
        tin="$workdir/$input"
        tcfg="$workdir/$config"
        [ -f "$tcfg" ] || tcfg="$config"   # tag predates the config file
        if [ ! -f "$tin" ]; then
            echo "warning: '$input' absent at tag '$tag'; skipped" >&2
            prev_tag=$tag; continue
        fi
        tdiff=()
        if [ -n "$prev_tag" ] && git show "$prev_tag:$input" \
                > "$workdir/prev_input" 2>/dev/null; then
            tdiff=(--diff-against "$workdir/prev_input")
        fi
        tagdate=$(git log -1 --format=%ad --date=short "$tag" 2>/dev/null || true)
        label="$tag${tagdate:+ ($tagdate)}"
        outv="$outdir/v/$tag"
        mkdir -p "$outv"
        textra=()
        if [ "${BUILD_DASHBOARD:-0}" = "1" ]; then
            textra=(--dashboard "$outv/dashboard.html"
                    --budget "$outv/${stem}_Budget.xlsx")
        fi
        tprov=(--source-path "$input")
        [ -n "$repo" ] && tprov+=(--repo "$repo")
        tsha=$(git rev-parse "$tag^{commit}" 2>/dev/null || true)
        if [ -n "$tsha" ]; then
            tprov+=(--commit "$(git rev-parse --short "$tag^{commit}")")
            u=$(src_url_for "$tsha"); [ -n "$u" ] && tprov+=(--source-url "$u")
        fi
        if $BOMGEN "$tin" -c "$tcfg" \
                --html "$outv/index.html" --xlsx "$outv/${stem}_BOM.xlsx" \
                --source-rev "$label" --historical "$label" \
                "${textra[@]}" "${tdiff[@]}" "${tprov[@]}"; then
            built_tags+=("$tag")
        else
            echo "warning: build failed for tag '$tag'; skipped" >&2
            rm -rf "$outv"
        fi
        prev_tag=$tag
    done

    # versions.js dropdown data, baked per directory (relative hrefs only,
    # so it works at any hosting root and on file://)
    write_versions() {  # $1 out-file, $2 prefix-to-site-root, $3 current-label
        {
            echo "window.BOMGEN_VERSIONS = {current: \"$3\", versions: ["
            echo "  {label: \"current\", href: \"$2index.html\"},"
            for t in "${built_tags[@]}"; do
                echo "  {label: \"$t\", href: \"$2v/$t/index.html\"},"
            done
            echo "]};"
        } > "$1"
    }
    if [ "${#built_tags[@]}" -gt 0 ]; then
        write_versions "$outdir/versions.js" "" "current"
        for t in "${built_tags[@]}"; do
            depth=$(echo "v/$t" | tr -cd '/' | wc -c)
            prefix=$(printf '../%.0s' $(seq 0 "$depth"))
            write_versions "$outdir/v/$t/versions.js" "$prefix" "$t"
        done
    fi
fi

echo "site built in $outdir/:"
ls -lR "$outdir" | head -40
