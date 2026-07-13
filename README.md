# bomgen

Convert SolidWorks **PDM Professional** BOM exports (CSV or XML) into
human-readable, shareable reports:

- **Excel** (.xlsx) — NASA-style indented BOM: title block, X level-marker
  band, numeric Level, Qty (Assembly) / Qty (Total) roll-up, native Excel
  row grouping for collapsible subassemblies.
- **HTML** — a single self-contained file (no server, no internet): 
  collapsible tree, live filtering, expand-to-level buttons, copy-as-TSV,
  and a **Download Excel** button linking the sibling .xlsx.

Configurable for any PDM vault via `bomgen.toml`.

## Quick start

```bash
pip install openpyxl pytest      # openpyxl is the only runtime dependency
python bomgen.py examples/NCC-1701_pdmout.csv --both
# -> NCC-1701_pdmout_BOM.xlsx, NCC-1701_pdmout_BOM.html
```

Requires Python ≥ 3.11 (stdlib `tomllib`).

## Usage

```
python bomgen.py INPUT.{csv|xml} [-c bomgen.toml] [--xlsx [OUT]] [--html [OUT]]
                                 [--both] [--xlsx-url URL] [-o OUTDIR] [--quiet]
```

- **CSV** — the interactive path: PDM BOM tab → export. Tip: do **not**
  round-trip the file through Excel; Excel float-mangles two-segment item
  numbers ("2.10" → "2.1"). bomgen detects and repairs the unambiguous
  cases with a warning (rule R1).
- **Data-quality banner** — caught gotchas (Excel float-mangle repairs,
  unresolved `SW-Mass@…` property expressions, missing COTS column, …)
  print to stderr *and* render in a yellow warning box at the top of both
  reports, so readers of the published BOM see them too.
- **XML** — the automation path: a PDM export rule fires on a workflow
  transition (e.g., release) and drops an XML for bomgen to consume.
  ⚠ The XML parser is written against SOLIDWORKS' documented schema family
  but has **not yet been verified against a real vault export** (open item
  O2 in the design doc) — send one sanitized export through
  `tests/fixtures/` before trusting it. XML files are parsed with stdlib
  ElementTree; treat inputs as trusted (they come from your own vault).

Configuration (project title block, column-name mapping, part-number
regex, passthrough columns) lives in `bomgen.toml` — see the comments
there and design doc §6.

When `--both` (or `--xlsx` and `--html` together) writes both files into
the same directory, the HTML's **Download Excel** button links the .xlsx by
relative filename automatically; `--xlsx-url` overrides the link target,
and the button removes itself when no .xlsx location is known.

## Publishing to GitHub / GitLab Pages

The repo ships CI configs for both services that compile the BOM on every
push to the default branch and deploy `index.html` + the `.xlsx` together,
so the download button works on the published page:

- GitHub: `.github/workflows/pages.yml` (Settings → Pages → Source =
  GitHub Actions)
- GitLab: `.gitlab-ci.yml` (picked up automatically)

Both call `scripts/build_pages.sh` and publish the example BOM by default —
point `BOM_INPUT`/`BOM_CONFIG` in the CI file at your own export.
**Step-by-step setup for both services: [`PAGES_SETUP.md`](PAGES_SETUP.md).**

## Design & decisions

`BOMGEN_DESIGN.md` is the living design document: input format findings
(from real exports), derivation rules, the decision log (D1–D4), and open
items (O1 dash-number source, O2 XML schema verification). Update it in
place when rules change.

## Tests

```bash
python -m pytest tests/ -v
```

Covers: tree reconstruction, Excel float-mangle repair, quantity roll-up,
Rev→dash part numbers, XML nested-references ingest, and output smoke
tests, plus a golden snapshot (`tests/fixtures/golden_tree.json`) —
regenerate it deliberately (delete and re-run) when derivation rules
change.

## Repository notes

- `examples/NCC-1701_pdmout.csv` is a sanitized (Star Trek-themed) copy of a
  real PDM export — structure, sparsity, and defects (including the Excel
  float-mangled `2.10` item) are preserved verbatim from the original.
- `template.html` must sit next to `bomgen.py` (it's read at runtime).
