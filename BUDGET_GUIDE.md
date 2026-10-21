# Build a budget by specification

This guide shows you how to group a BOM into procurement categories
("specs"), attach dollars and export-control facts to each category, and
publish the result as a dashboard and a costing workbook. For the design
rationale, see `BOMGEN_DESIGN.md` §5.4 and decision D14.

## Quick start

Describe your categories in two CSV files and pass them to bomgen:

```bash
# specs.csv : which category each CAD file belongs to
# costs.csv : what each category costs, plus anything else you track per category
bomgen vault/export.csv --dashboard --budget \
    --specs-csv specs.csv --costs-csv costs.csv
# -> <stem>_Dashboard.html + <stem>_Budget.xlsx
```

To avoid typing the flags every time, configure the paths once in
`bomgen.toml`:

```toml
[budget]
specs_file = "specs.csv"   # paths are relative to this toml file
costs_file = "costs.csv"
```

In CI, setting `BUILD_DASHBOARD=1` makes `scripts/build_pages.sh` publish
the dashboard (as `dashboard.html`) and the workbook next to the BOM page.

## Step 1: Assign specs in specs.csv

Each row maps one CAD file to a category. The PDM export itself needs no
specs column.

```csv
File,Spec,Note
NCC-FA004.SLDASM,RFQ-WELD-001,injector mount weldment — one quote covers the subtree
NCC-FP005.SLDPRT,RFQ-MACH-001,
NCC-FP006.SLDPRT,RFQ-MACH-001,
92423A461_Screw.SLDPRT,RFQ-HDWE-001,COTS fastener buy
```

How assignment works:

- **An assembly's spec covers its whole subtree.** Assign a weldment
  assembly one row and every piece part under it is covered — you don't
  list them individually. A few rows can cover hundreds of parts: start
  with the big quoted assemblies and watch the dashboard's *Unassigned
  parts* tile drop.
- **Matching is by filename** (for example `NCC-FA004.SLDASM`), ignoring
  case and extra whitespace, against the export's `Number` column.
- **Parts that nothing covers** appear in the *(unassigned)* group
  (warning V10) — a visible budget gap, never a silent one.
- **Several rows for one file** make it multi-spec; the first row listed
  is the budget category (warning V11). A spec'd item inside another
  spec'd subtree is allowed but flagged (warning V12 — a possible
  double-counted cost).
- **Rows naming files that left the BOM** warn (V13), so the table can't
  silently go stale. If the export also has a specs column, the table
  wins on any conflict (warning V14).

If you'd rather not keep a table, you can put the reference in a column
of the export itself and map it with `[columns] specs = "YourHeader"`
(several references per cell split on `[budget].spec_separator`; the
first wins). The demo site uses both at once: its `Material
Specification` column plus `examples/NCC-1701_specs.csv`.

## Step 2: Cost specs in costs.csv

Each row costs one spec. Costing is per category, not per part: a
category gets one WAG/ROM/Quote set (wild guess, rough order of
magnitude, vendor quote).

```csv
Spec,WAG,ROM,Quote,Note,Hardware,Technology,Software,Intent to Publish Research Product Design,Existing Publication,Rationale,Vendor
RFQ-WELD-001,25000,18500,,ROM from vendor letter 2026-06,EAR99,EAR99,,Yes,,structural weldment; no controlled technology,Starfleet Fabrication
RFQ-MACH-001,12000,,,WAG pending drawing release,EAR99,,,Yes,,machined from public drawings,TBD
RFQ-HDWE-001,,,1840.50,McMaster cart quote,EAR99,,,,doi:10.5555/ncc1701,catalog COTS fasteners,McMaster-Carr
```

How costing works:

- **Best = Quote, else ROM, else WAG.** Fill in whatever maturity you
  have. The weldment above reports $18,500 — its ROM beats its WAG —
  until a quote lands.
- Values like `$12,000` parse; values that don't parse (such as `TBD`)
  warn (V15) and read as blank. Duplicate spec rows warn; the first wins.
- A spec with no row here warns (V16) and shows **uncosted** on the
  dashboard, so the *Budget (Best)* total is never quietly incomplete. A
  row naming a spec that no longer has parts also warns (V16).
- **Every column beyond `Spec,WAG,ROM,Quote,Note` passes through** to the
  workbook's Budget sheet, in file order. The templates ship the
  export-control review set — *Hardware*, *Technology*, *Software*,
  *Intent to Publish Research Product Design*, *Existing Publication*,
  *Rationale*, *Vendor* — but any column works: add `Lead Time` to the
  CSV and a Lead Time column appears, with no configuration change.

## What bomgen produces

**Dashboard** (`--dashboard`, published as `dashboard.html`):

- Summary tiles: Specs, **Budget (Best)**, **Specs costed n/m**, RFQ line
  items, total part quantity, unassigned parts, and — on diffed builds —
  changed vs previous.
- One collapsible group per spec, with Cost (Best) on the row.
  WAG/ROM/Quote, the note, and the passthrough fields (export control,
  vendor, and so on) appear in the hover tooltip. When
  `[links].spec_url_template` is set, each group links its controlled
  document ("spec doc ↗"); `{spec}` in the template is URL-encoded, for
  example `spec_url_template = "https://docs.example.edu/{spec}"`.
- Download buttons for the budget workbook and the BOM page.

**Budget workbook** (`--budget`, `<stem>_Budget.xlsx`):

- The *Budget* sheet is the cost model: one row per spec with `Spec |
  Line Items | Total Qty | WAG | ROM | Quote | Best | Note | <your
  passthrough columns> | Spec Document`. The WAG/ROM/Quote cells are
  shaded and prefilled from `costs.csv`; Best and the TOTAL row are live
  formulas, so what-if numbers typed in Excel roll up immediately.
  **Edits persist only when you copy them back into `costs.csv`** — every
  build regenerates the workbook.
- The *Parts* sheet lists what each spec covers (spec, part number, name,
  configuration, COTS flag, rolled-up quantity, use count). Rows changed
  since the previous version are highlighted green.

## Read the warnings

Warnings appear in the yellow banner at the top of every output and in
the build log.

| ID | Meaning | What to do |
|---|---|---|
| V10 | Parts covered by no spec, or the specs column is missing | Add specs.csv rows (or map the column) |
| V11 | A file lists several specs | Nothing — the first listed is the budget category |
| V12 | A spec'd item sits inside another spec'd subtree | Check for double-counted cost |
| V13 | A specs.csv row matches no BOM file, or the file is missing | Delete the stale row or fix the path |
| V14 | specs.csv overrides the export's specs column | Nothing — the table is authoritative |
| V15 | A costs.csv row is a duplicate or holds an unparseable value | Fix the row |
| V16 | A spec is uncosted, a cost row is stale, or the costs file is missing | Add or prune costs.csv rows |

The build log also prints `info:` lines with the effective
`spec_url_template`, how many groups got linked, and the costed totals.
When something doesn't show up on the dashboard, read those lines first.

## Choose where the files live

Two supported layouts:

- **Everything in the vault repository.** Commit `specs.csv` and
  `costs.csv` next to the export and point `[budget]` at them. This is
  the simplest layout; costs are visible to everyone with vault access.
- **A separate budget repository** (the primary-cost-model pattern). The
  tables, `bomgen.toml`, and CI live in their own GitLab repository,
  whose CI clones the vault repository for the BOM. Start from
  `template-budget-repo/` — its README walks through `VAULT_REPO_URL`,
  private-repository tokens, and the weekly schedule. Set
  `BUDGET_REPO_PROJECT` in the vault repository so every BOM push
  triggers a budget rebuild (the vault CI's `trigger_budget_rebuild`
  job); without it, the budget site follows the BOM only weekly. The
  rollout checklist is in `BUDGET_PLAN.md`.
