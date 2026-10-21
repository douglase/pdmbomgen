# Using the spec & budget features — a worked guide

How to group a BOM into RFQ/procurement categories ("specs"), attach
dollars and export-control facts to them, and publish the result as a
dashboard + budget workbook. Design rationale lives in `BOMGEN_DESIGN.md`
§5.4/D14; this is the how-to.

## The 60-second version

```bash
# specs.csv : which category each CAD file belongs to
# costs.csv : what each category costs (and anything else per category)
bomgen vault/export.csv --dashboard --budget \
    --specs-csv specs.csv --costs-csv costs.csv
# -> <stem>_Dashboard.html + <stem>_Budget.xlsx
```

Or configure once in `bomgen.toml` and drop the flags:

```toml
[budget]
specs_file = "specs.csv"   # paths relative to this toml file
costs_file = "costs.csv"
```

In CI, `BUILD_DASHBOARD=1` makes `scripts/build_pages.sh` publish both
next to the BOM page (as `dashboard.html`).

## 1. Assigning specs — `specs.csv`

One row per CAD file → category. The PDM export needs **no** specs column.

```csv
File,Spec,Note
NCC-FA004.SLDASM,RFQ-WELD-001,injector mount weldment — one quote covers the subtree
NCC-FP005.SLDPRT,RFQ-MACH-001,
NCC-FP006.SLDPRT,RFQ-MACH-001,
92423A461_Screw.SLDPRT,RFQ-HDWE-001,COTS fastener buy
```

Rules that matter:

- **A spec'd assembly covers its whole subtree.** Assign the weldment
  assembly one row and every piece part under it is covered — you do not
  list them. This is why a few rows can cover hundreds of parts: start
  with the big quoted assemblies and watch the dashboard's *Unassigned
  parts* tile drop.
- **Matching is by filename**, whitespace/case-insensitive, against the
  export's `Number` column (e.g. `NCC-FA004.SLDASM`).
- **Leaf parts covered by nothing** land in the *(unassigned)* group
  (warning V10) — a visible budget gap, never a silent one.
- **Several rows for one file** = multi-spec; the first listed is the
  budget category (V11). A spec'd item *inside* another spec'd subtree is
  allowed but flagged (V12 — possible double-counted cost).
- **Rows naming files that left the BOM** warn (V13) so the table can't
  silently rot. If the export *also* has a specs column, the table wins on
  any conflict (V14).

Alternative without a table: put the reference in a column of the export
itself and map it with `[columns] specs = "YourHeader"` (several refs per
cell split on `[budget].spec_separator`, first wins). The demo site uses
both at once: its `Material Specification` column plus
`examples/NCC-1701_specs.csv`.

## 2. Costing specs — `costs.csv`

One row per spec. Spec-level, not per-part: a category gets one
WAG/ROM/Quote set.

```csv
Spec,WAG,ROM,Quote,Note,Hardware,Technology,Software,Intent to Publish Research Product Design,Existing Publication,Rationale,Vendor
RFQ-WELD-001,25000,18500,,ROM from vendor letter 2026-06,EAR99,EAR99,,Yes,,structural weldment; no controlled technology,Starfleet Fabrication
RFQ-MACH-001,12000,,,WAG pending drawing release,EAR99,,,Yes,,machined from public drawings,TBD
RFQ-HDWE-001,,,1840.50,McMaster cart quote,EAR99,,,,doi:10.5555/ncc1701,catalog COTS fasteners,McMaster-Carr
```

- **Best = Quote, else ROM, else WAG** — fill whatever maturity you have;
  the weldment above reports $18,500 (its ROM beats its WAG) until a
  quote lands.
- `$12,000`-style values parse; unparseable ones (e.g. `TBD`) warn (V15)
  and read as blank. Duplicate spec rows warn; first wins.
- A spec with **no row** here warns (V16) and shows "uncosted" on the
  dashboard, so the *Budget (Best)* total is never quietly incomplete.
  A row naming a spec with no parts also warns (V16 — stale).
- **Every column beyond `Spec,WAG,ROM,Quote,Note` passes through** to the
  Budget sheet verbatim, in file order. The templates ship the
  export-control review set — *Hardware / Technology / Software / Intent
  to Publish Research Product Design / Existing Publication / Rationale /
  Vendor* — but any column works (add `Lead Time`, get a Lead Time
  column). No config, no code change.

## 3. What comes out

**Dashboard** (`--dashboard`, published as `dashboard.html`):
- Tiles: Specs · **Budget (Best)** · **Specs costed n/m** · RFQ line
  items · Total part qty · Unassigned parts (+ Changed vs previous on
  diffed builds).
- One collapsible group per spec: Cost (Best) on the row, with
  WAG/ROM/Quote, the note, and the passthrough fields (export control,
  vendor, …) in the hover tooltip; "spec doc ↗" link when
  `[links].spec_url_template` is set (`{spec}` is URL-encoded), e.g.
  `spec_url_template = "https://docs.example.edu/{spec}"`.
- Download buttons for the budget workbook and the BOM page.

**Budget workbook** (`--budget`, `<stem>_Budget.xlsx`):
- *Budget* sheet — the cost model: one row per spec with `Spec | Line
  Items | Total Qty | WAG | ROM | Quote | Best | Note | <your passthrough
  columns> | Spec Document`. WAG/ROM/Quote are shaded cells prefilled
  from `costs.csv`; Best and the TOTAL row are live formulas, so what-ifs
  typed in Excel roll up immediately. **Edits persist only when copied
  back into `costs.csv`** — every build regenerates the workbook.
- *Parts* sheet — what each spec covers (spec, part number, name, config,
  COTS, rolled-up qty, use count), green-highlighted on rows changed
  since the previous version.

## 4. Warnings cheat-sheet (yellow banner on every output)

| ID | Meaning | Fix |
|---|---|---|
| V10 | parts covered by no spec / specs column missing | add specs.csv rows (or the column) |
| V11 | a file lists several specs | fine; first one is the budget category |
| V12 | spec'd item inside another spec'd subtree | check for double-counted cost |
| V13 | specs.csv row matches no BOM file (or file missing) | delete the stale row / fix the path |
| V14 | specs.csv overrides the export's specs column | expected; the table is authoritative |
| V15 | duplicate or unparseable costs.csv row | fix the row |
| V16 | spec uncosted, stale cost row, or costs file missing | add/prune costs.csv rows |

The build log also prints `info:` lines stating the effective
`spec_url_template`, how many groups got linked, and the costed totals —
read those first when something doesn't show up.

## 5. Where the files live

Two supported layouts:

- **Everything in the vault repo** — commit `specs.csv`/`costs.csv` next
  to the export, point `[budget]` at them. Simplest; costs are visible to
  everyone with vault access.
- **Separate budget repo** (the primary-cost-model pattern): tables +
  `bomgen.toml` + CI live in their own GitLab repo, whose CI clones the
  vault repo for the BOM. Start from `template-budget-repo/` — its README
  walks through `VAULT_REPO_URL`, private-repo tokens, and the weekly
  schedule. Set `BUDGET_REPO_PROJECT` in the vault repo so every BOM push
  triggers a budget rebuild (the vault CI's `trigger_budget_rebuild`
  job); otherwise the budget site follows the BOM only weekly. Rollout
  checklist: `BUDGET_PLAN.md`.
