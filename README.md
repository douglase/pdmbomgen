# pdmbomgen
_Converts SOLIDWORKS PDM Professional BOM exports into shareable Excel, HTML, and budget reports for UASAL projects._

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![License scan](https://github.com/douglase/pdmbomgen/actions/workflows/scancode.yml/badge.svg?branch=main)](https://github.com/douglase/pdmbomgen/actions/workflows/scancode.yml) **[Main Branch]**

> [!Important]
> This repository is the tool.
> Your vault's PDM export does **not** belong in it:
> real BOM data lives in a downstream vault repository built from [`template-repo/`](template-repo/),
> and cost models live in a budget repository built from [`template-budget-repo/`](template-budget-repo/).
> Refer to the [UASAL Development Guide](https://uasal.github.io/uasal_development_guide/) for process questions not covered here.

From one PDM export, bomgen produces:

- **An Excel workbook** (.xlsx) in the NASA-style indented BOM layout:
  title block, level-marker band, rolled-up quantities, and collapsible subassemblies.
- **A web page** — a single self-contained HTML file that works with no server and no internet:
  collapsible tree, live filtering, copy to spreadsheet, and a **Download Excel** button.
- **A budget dashboard and costing workbook** that group parts into procurement categories with dollars attached.
  See [`BUDGET_GUIDE.md`](BUDGET_GUIDE.md).

-------

## Dependencies
_What must be installed, and what pip installs for you._

- Python 3.11 or later (the standard-library `tomllib` is required).
- [openpyxl](https://openpyxl.readthedocs.io/) — the only runtime dependency; pip installs it automatically.
- [pytest](https://docs.pytest.org/) — tests only; installed by `pip install ".[test]"`.

## Installation
_How to install for use, and how to install for editing._

There is no PyPI package yet; install from GitHub.
If you intend to edit the package, add `-e` to the commands below for an editable install.

### Pip-based install

If the repository is publicly accessible:
```sh
pip install "pdmbomgen @ git+https://github.com/douglase/pdmbomgen.git@main"
```

If ssh authentication is required:
```sh
pip install "pdmbomgen @ git+ssh://git@github.com/douglase/pdmbomgen.git@main"
```

### Installed via cloning

```sh
git clone https://github.com/douglase/pdmbomgen.git   # or git@github.com:douglase/pdmbomgen.git
cd pdmbomgen
pip install .
```

To run from a clone without installing:
```sh
pip install openpyxl
python -m bomgen examples/NCC-1701_pdmout.csv --both
```

### Environment variables
_Variables the CI build script reads; none are needed for local command-line use._

- `BOM_INPUT`, `BOM_CONFIG`: which export and configuration file CI publishes.
- `BUILD_DASHBOARD=1`: also publish the budget dashboard and workbook.
- `BUILD_HISTORY=1`: rebuild every git tag into `v/<tag>/` with a version dropdown.
- `PDMBOMGEN_PAT` (GitHub) / `PDMBOMGEN_TOKEN` (GitLab): token for installing pdmbomgen when this repository is private.
- `BUDGET_REPO_PROJECT`: GitLab path of a budget repository to trigger on BOM pushes.
- `BOM_SOURCE_REV`, `BOM_SOURCE_URL`, `BOM_PREV_FILE`: provenance and diff overrides when the input lives in a cloned repository
  (set automatically by the budget-repository CI).

## Usage
_The smallest working example; the guides have the rest._

```sh
bomgen examples/NCC-1701_pdmout.csv --both
# -> NCC-1701_pdmout_BOM.xlsx, NCC-1701_pdmout_BOM.html
```

Export the BOM from PDM as CSV (interactive) or XML (export-rule automation).
Do **NOT** open and re-save the CSV in Excel before committing it:
Excel rewrites two-segment item numbers such as `2.10` as `2.1`.
bomgen detects and repairs the unambiguous cases with a warning (rule R1), but a clean export avoids the problem entirely.

**NOTE:** the XML parser follows the documented SOLIDWORKS schema
but has not been verified against a real vault export (open item O2 in the design document);
run one sanitized export through it before trusting the results.

Data-quality problems that bomgen catches
(Excel number mangling, unresolved `SW-Mass@…` property expressions, missing columns)
print to the terminal **and** appear in a yellow warning banner at the top of every report.

All configuration lives in [`bomgen.toml`](bomgen.toml):
the title block, column mapping, part-number rules, and the optional features below.
The file ships fully commented; the field reference is [`BOMGEN_DESIGN.md`](BOMGEN_DESIGN.md) §6.

### Optional features
_Each feature is off until configured; each links its own guide._

- **PDM viewer links** — set `[links].file_url_template` to make every filename a link into your PDM web viewer.
  `{found_in}` is the row's *Found In* vault folder as a URL path
  (the leading `<drive>:\<Vault>\` is stripped for any drive letter);
  `{file}` is the SOLIDWORKS filename.
  Ex.) `file_url_template = "https://your-pdm.example.edu/solidworkspdm/Vault/{found_in}"`
  turns `D:\Vault\STP\ESC\Flight` into `…/solidworkspdm/Vault/STP/ESC/Flight`.
- **Budget by specification** — group parts into procurement categories and attach WAG/ROM/Quote estimates
  and export-control facts from two version-controlled CSV tables,
  then publish the rollup with `--budget --dashboard`.
  Worked examples: [`BUDGET_GUIDE.md`](BUDGET_GUIDE.md); rollout plan: [`BUDGET_PLAN.md`](BUDGET_PLAN.md).
- **Change highlighting and history** — `--diff-against PREV.csv` highlights changed and added rows green in every output;
  `BUILD_HISTORY=1` in CI rebuilds every git tag with yellow historical styling and a version dropdown.
- **Material properties** — enrich rows with density, CTE, outgassing, and other properties
  from a committed [materials database](MATERIALS_DB_PLAN.md) export;
  local file only, never the network.
- **Build provenance** — every output carries a collapsible *Build provenance* block
  (and a linked workbook cell)
  listing the source BOM and its commit, the repository and branch, the configuration file,
  and the exact tool versions that compiled it.

### Publishing to GitHub Pages or GitLab Pages
_Both CI configurations compile and deploy the reports on every push._

- GitHub: [`.github/workflows/pages.yml`](.github/workflows/pages.yml) — set **Settings → Pages → Source** to **GitHub Actions**.
- GitLab: [`.gitlab-ci.yml`](.gitlab-ci.yml) — picked up automatically.

Both run the tests, call [`scripts/build_pages.sh`](scripts/build_pages.sh), and publish the example BOM by default;
point `BOM_INPUT` and `BOM_CONFIG` at your own export.
Step-by-step instructions: [`PAGES_SETUP.md`](PAGES_SETUP.md).

### Command-line reference

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

`python -m bomgen …` works identically from a clone.
The provenance flags are normally supplied by `scripts/build_pages.sh`, not typed by hand.
When `--both` writes both files into one directory,
the web page's **Download Excel** button links the workbook by relative filename automatically;
`--xlsx-url` overrides the target, and the button removes itself when no workbook location is known.

-------

## Contributing Overview
_How a change gets from an idea into the default branch._

### General Steps:
_Quick overview of how to add or change content in this repository._

1. Create a GitHub issue describing the change.
   1. Verify there is not a duplicate issue.
   2. Add labels and an assignee.
2. Create a branch named `username/branch-description` from the default branch,
   following the [git-flow guide](https://uasal.github.io/uasal_development_guide/git/git-flow-guide.html).
3. Make the change; run the local tests below.
   When derivation rules change, update [`BOMGEN_DESIGN.md`](BOMGEN_DESIGN.md) in place —
   it is the living design record (input-format findings, the decision log D1–D14, data-flow diagrams, open items).
4. Open a draft pull request, fill in the description, and link the issue.
5. Squash and merge once approved.

### Local Testing / Steps:
_What to run before opening a pull request._

```sh
pip install -e ".[test]"
python -m pytest tests/ -v
```

The suite covers tree reconstruction, the Excel number-mangle repair, quantity roll-up,
part numbering, XML ingest, the budget and provenance features,
and a golden snapshot ([`tests/fixtures/golden_tree.json`](tests/fixtures/golden_tree.json)).
Regenerate the snapshot deliberately — delete it and rerun — when derivation rules change.

## Key Scripts Overview
_One bullet per script, with what it does and what it depends on._

- [`scripts/build_pages.sh`](scripts/build_pages.sh):
  - Builds the complete Pages site (BOM page, workbooks, dashboard, historical tags) from one export.
  - Computes git provenance facts and passes them to bomgen; honors the environment variables above.
- [`template-repo/scripts/update_from_template.sh`](template-repo/scripts/update_from_template.sh):
  - Refreshes a vault repository's machinery (CI, build scripts) from this template without touching its data.
- [`scripts/check_scancode_allowlist.py`](scripts/check_scancode_allowlist.py):
  - CI gate that fails the license scan if anything outside the MIT allowlist appears.

-------

## License
_MIT, with the scan that keeps it that way._

MIT — see [LICENSE](LICENSE).
Third-party dependency licenses, example-data provenance, and the automated license-scan safeguard
are documented in [LICENSE-NOTES.md](LICENSE-NOTES.md).

**NOTE:** [`examples/NCC-1701_pdmout.csv`](examples/NCC-1701_pdmout.csv) is a sanitized,
Star Trek–themed copy of a real PDM export;
its structure, sparsity, and defects (including the Excel-mangled `2.10` item) are preserved verbatim.
This project was largely written with Claude Code (AI assistance disclosure).
