# bomgen

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![License scan](https://github.com/douglase/pdmbomgen/actions/workflows/scancode.yml/badge.svg)](https://github.com/douglase/pdmbomgen/actions/workflows/scancode.yml)

bomgen turns the bill of materials (BOM) that SOLIDWORKS PDM Professional
exports into reports your whole team can read, share, and publish:

- **An Excel workbook** (.xlsx) in the familiar NASA-style indented
  layout: title block, level-marker band, rolled-up quantities, and
  collapsible subassemblies.
- **A web page** — a single self-contained HTML file that works with no
  server and no internet: collapsible tree, live filtering, copy to
  spreadsheet, and a **Download Excel** button.
- **A budget dashboard and costing workbook** that group parts into
  procurement categories with dollars attached. See
  [`BUDGET_GUIDE.md`](BUDGET_GUIDE.md).

You can run bomgen by hand, or let the included CI configurations publish
the reports to GitHub Pages or GitLab Pages on every change. Everything is
configured for your vault in one file, `bomgen.toml`.

## Quick start

Install from GitHub (there's no PyPI package yet) and convert the included
example export:

```bash
pip install "pdmbomgen @ git+https://github.com/douglase/pdmbomgen.git@main"
bomgen examples/NCC-1701_pdmout.csv --both
# -> NCC-1701_pdmout_BOM.xlsx, NCC-1701_pdmout_BOM.html
```

To run from a clone without installing:

```bash
pip install openpyxl
python -m bomgen examples/NCC-1701_pdmout.csv --both
```

bomgen requires Python 3.11 or later. openpyxl is the only runtime
dependency.

## Get a BOM out of PDM

- **CSV (recommended to start)** — in PDM, open the assembly's BOM tab
  and export. Don't open and re-save the file in Excel before committing
  it: Excel rewrites two-segment item numbers such as `2.10` as `2.1`.
  bomgen detects and repairs the unambiguous cases and warns (rule R1),
  but a clean export avoids the problem entirely.
- **XML (automation path)** — a PDM export rule can emit XML on a workflow
  transition, such as a release, for bomgen to consume. The XML parser
  follows the documented SOLIDWORKS schema but hasn't been verified
  against a real vault export yet (open item O2 in the design doc) — run
  one sanitized export through it before trusting the results.

Whatever the input, data-quality problems that bomgen catches (Excel
number mangling, unresolved `SW-Mass@…` property expressions, missing
columns, and so on) print to the terminal **and** appear in a yellow
warning banner at the top of every report, so readers of the published
BOM see them too.

## Configure it for your vault

All configuration lives in `bomgen.toml`: the title block, which export
columns map to which report columns, part-number rules, and the optional
features below. The file ships fully commented; the field reference is in
`BOMGEN_DESIGN.md` §6.

### Link filenames to your PDM web viewer

Set `[links].file_url_template` to make every filename in the reports a
clickable link into your PDM web viewer. The template takes `{found_in}`
(the row's *Found In* vault folder, converted to a URL path — the leading
`<drive>:\<Vault>\` is stripped for any drive letter) and `{file}` (the
SOLIDWORKS filename). For example:

```toml
[links]
file_url_template = "https://your-pdm.example.edu/solidworkspdm/Vault/{found_in}"
```

turns a *Found In* of `D:\Vault\STP\ESC\Flight` into
`…/solidworkspdm/Vault/STP/ESC/Flight`. Leave the template empty (the
default) to keep filenames as plain text.

### Build a budget by specification

Group parts into procurement categories ("specs"), attach
WAG/ROM/Quote estimates and export-control facts to each category, and
publish the rollup as a dashboard plus a costing workbook:

```bash
bomgen INPUT.csv --budget --dashboard
```

Spec assignments and dollars live in two version-controlled CSV tables
(`specs.csv` and `costs.csv`), so the PDM export never has to change.
**Start with [`BUDGET_GUIDE.md`](BUDGET_GUIDE.md)** for worked examples;
[`BUDGET_PLAN.md`](BUDGET_PLAN.md) tracks the rollout plan, and
[`template-budget-repo/`](template-budget-repo/) is the starting point
for keeping the cost model in its own repository.

### Highlight changes and keep historical versions

`--diff-against PREV.csv` highlights rows changed or added since a
previous export in **green**, in every output; removed parts are
summarized in the banner. Only report columns are compared, so PDM churn
such as *Checked Out By* never flags a row (`[diff].ignore_columns`
excludes more). In CI, `BUILD_HISTORY=1` rebuilds every git tag into
`v/<tag>/` with yellow historical styling, a version dropdown on every
page, and per-tag change highlighting.

### Add material properties

Enrich rows with density, CTE, outgassing, and other properties from a
[materials database](MATERIALS_DB_PLAN.md) export. Commit the database's
raw `/export/raw-json` dump next to your BOM and configure `[materials]`
in `bomgen.toml`. Matching is by material name or synonym; bomgen reads
the file from disk only and never touches the network. Unmatched
materials warn — they never fail the build.

## Publish to GitHub Pages or GitLab Pages

The repository ships CI configurations for both services. Each compiles
the BOM on every push to the default branch and deploys the web page and
the Excel files together, so the download buttons work on the published
site:

- GitHub: `.github/workflows/pages.yml` (set **Settings → Pages →
  Source** to **GitHub Actions**)
- GitLab: `.gitlab-ci.yml` (picked up automatically)

Both call `scripts/build_pages.sh` and publish the example BOM by
default; point `BOM_INPUT` and `BOM_CONFIG` in the CI file at your own
export. **Step-by-step instructions: [`PAGES_SETUP.md`](PAGES_SETUP.md).**

## Set up a repository for your own vault data

This repository is the tool — your PDM export doesn't belong in it. To
version-control your own vault's export, publish it to Pages, and pick up
bomgen fixes automatically on every build, copy
[`template-repo/`](template-repo/) into a new repository and follow
[`template-repo/SETUP.md`](template-repo/SETUP.md).

The template installs pdmbomgen with a plain `git clone` of this
repository, which works anonymously only while this repository is
**public**. If it's private, either make it public (recommended — it's
only the tool; no vault data lives here) or give the downstream CI a
token. `template-repo/SETUP.md` §4.5 covers both.

## Command-line reference

```
bomgen INPUT.{csv|xml} [-c bomgen.toml] [--xlsx [OUT]] [--html [OUT]] [--both]
                       [--budget [OUT]] [--dashboard [OUT]]
                       [--specs-csv PATH] [--costs-csv PATH]
                       [--xlsx-url URL] [--materials-cache PATH]
                       [--diff-against PREV] [--historical LABEL]
                       [--source-rev REV] [--repo NAME] [--branch NAME]
                       [--commit SHA] [--source-url URL] [--source-path PATH]
                       [-o OUTDIR] [--quiet] [--version]
```

`python -m bomgen …` works identically from a clone. The provenance flags
(`--source-rev`, `--repo`, `--branch`, `--commit`, `--source-url`,
`--source-path`) are normally supplied by `scripts/build_pages.sh`, not
typed by hand — every output records a collapsible *Build provenance*
block (and a linked workbook cell) listing the source BOM, its commit,
the repository and branch, the configuration file, and the exact tool
versions that compiled it.

When `--both` writes both files into one directory, the web page's
**Download Excel** button links the workbook by relative filename
automatically. `--xlsx-url` overrides the link target, and the button
removes itself when no workbook location is known.

## For developers

- **Design document** — `BOMGEN_DESIGN.md` is the living design record:
  input-format findings from real exports, derivation rules, the data-flow
  diagrams, the decision log (D1–D14), and open items. Update it in place
  when rules change.
- **Tests** — `python -m pytest tests/ -v` covers tree reconstruction,
  the Excel number-mangle repair, quantity roll-up, part numbering, XML
  ingest, the budget and provenance features, and a golden snapshot
  (`tests/fixtures/golden_tree.json`). Regenerate the snapshot
  deliberately — delete it and rerun — when derivation rules change.
- **Repository notes** — `examples/NCC-1701_pdmout.csv` is a sanitized,
  Star Trek-themed copy of a real PDM export; its structure, sparsity,
  and defects (including the Excel-mangled `2.10` item) are preserved
  verbatim. `bomgen/` is the installable package; the HTML templates ship
  as package data. This project was largely written with Claude Code.

## License

MIT — see [LICENSE](LICENSE). Third-party dependency licenses,
example-data provenance, and the automated license-scan safeguard are
documented in [LICENSE-NOTES.md](LICENSE-NOTES.md).
