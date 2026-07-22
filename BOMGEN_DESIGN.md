# bomgen — SolidWorks PDM CSV → Human-Readable BOM Generator

**Design Document · Rev B · 2026-07-12**
Reference dataset: examples/NCC-1701_pdmout.csv (sanitized real export)

---

## 1. Purpose & Scope

Convert an indented Bill of Materials exported from **SolidWorks PDM Professional as CSV**
into two human-readable reports:

1. **Excel** (.xlsx) matching the team's NASA-style indented BOM template
   (title block, X level-marker band, Qty Assembly/Total).
2. **HTML** — a single self-contained file with a collapsible tree, filtering,
   and copy-to-clipboard, distributable with project documentation (no network
   dependencies, no server).

Non-goals (this revision): live PDM API access, BOM diff/compare reports,
cost roll-up, mass roll-up (see §10 Future Work).

### Prior art surveyed (2026-07)
- **InteractiveHtmlBom** (openscopeproject, MIT) — pattern source for
  self-contained HTML packaging and table UX; not reused directly (EDA data
  model: flat grouped rows + PCB renderer; no hierarchy support).
- **bomkit** (robsiegwart) — pattern source for quantity roll-up
  (`aggregate`/`summary`); Excel-native input format, not PDM CSV.
- Commercial PDM add-ins (Solid Solutions BoM Export, blue byte pdm2excel,
  Bommer) — confirm the niche; closed source.
- No open-source PDM-CSV-specific parser found → clean-room implementation.

---

## 2. Input Format Specification

Derived from a real PDM Professional export (48-row assembly subtree excerpt;
sanitized copy at `examples/NCC-1701_pdmout.csv`). The parser MUST tolerate deviations noted below.

### 2.1 File mechanics
| Property | Observed | Parser behavior |
|---|---|---|
| Encoding | UTF-8 **with BOM** | open with `encoding="utf-8-sig"`; fall back to `utf-16` then `cp1252` on `UnicodeDecodeError` |
| Line endings | CRLF | `csv` module handles natively (`newline=""`) |
| Quoting | RFC-4180 (embedded commas & doubled quotes observed: `"INJECTOR BASE, 1"" COIL"`) | `csv.reader` — never `str.split(",")` |
| Header row | Row 1, verbatim PDM BOM-view column names | mapped via config (§6), not hardcoded |

### 2.2 Hierarchy encoding
- `Level` column holds **dotted item numbers**: `1`, `1.1`, `1.1.2`, `3.1.12.1`.
  Depth = number of segments. Each row's parent is its path minus the last
  segment — tree reconstruction is a dict lookup, no level-stack needed.
- `Number` (filename) carries **cosmetic leading spaces, 2 per depth level**.
  Stripped on ingest; retained as a cross-check (§7 validation V3).
- **The exported file does not contain the root assembly row.** Top-level rows
  (`1`, `2`, `3`, …) are the *children* of the assembly selected in PDM.
  → bomgen **synthesizes the Level-0 root row** from config metadata
  (`assembly_number`, `assembly_name`, `assembly_description`). *(Decision
  D2, 2026-07-12.)*

### 2.3 Columns observed (24)
`Level, Qty, Number, Name, Config, Rev, Description, Found In, Checked Out By,
Material, Material Specification, Finish, Process Specification,
ExportControlClassificationNumber, Collected Volatile Condesable Materials,
Total Mass Loss, Water Vapor Regained, LowOperatingTemp, HighOperatingTemp,
LowSurvTemp, HighSurvTemp, TRL, Datasheet Link, Mass`

Population is sparse (Name 17/48, Description 33/48, Rev 6/48, Mass 10/48,
flight-hardware columns 0/48). The tool MUST NOT assume any column beyond
`Level`, `Qty`, `Number` is populated, and MUST carry unrecognized/extra
columns through untouched when listed in `passthrough_columns` (§6).

### 2.4 Semantics
- `Qty` — quantity **per parent assembly** (integer; parse leniently, warn on
  non-numeric).
- `Number` — SolidWorks filename incl. extension (`.SLDASM`/`.SLDPRT`).
  Extension distinguishes assembly vs part (also derivable from
  has-children).
- `Config` — SolidWorks configuration; for vendor hardware this often carries
  the catalog number (e.g., McMaster `96246A088`), for custom parts usually
  `Default` or a variant name.
- `Found In` — vault path; encodes workflow area (`…\Flight`,
  `…\WIP\9000 - Piece Parts`). Surfaced as an optional "State" column
  (last one/two path segments).

### 2.5 XML input (PDM export rules — automation path)
PDM Professional can export BOMs to XML automatically on workflow transitions
(the ERP-integration channel), configured in the Administration tool with a
file-ID variable and optional alias sets. `read_xml()` normalizes this into
the same row shape as CSV, then shares `build_tree()` unchanged. *(Decision
D4, 2026-07-12: XML = automation path, CSV = interactive path.)*

Schema handled (per SOLIDWORKS PDM help "XML File Structure and Example"):
`<xml><transactions><transaction><document id=…><configuration name=…>
<attribute name=… value=…/>` — hierarchy accepted either as (a) nested
`<document>` under `<references>` (item numbers synthesized in document
order, per-reference `quantity` attribute), or (b) a dotted-level attribute
matching `columns.level`, or (c) flat (single level).

> **⚠ OPEN ITEM O2:** the published SOLIDWORKS example documents the *import*
> transaction; the exact BOM-*export* nesting must be verified against a real
> vault export (sample files ship in `SWPDMClient\Support\ERP` on any PDM
> client install). `tests/fixtures/sample_export.xml` encodes the assumed
> form; replace with a sanitized real export and re-run tests. The parser
> emits an O2 warning whenever it synthesizes hierarchy.

XML also carries the vault's unique **File ID**, the enabler for a future
BOM-compare mode keyed on identity rather than filename strings (§10).

---

## 3. Data Model

```
BomNode
  path: str            # "1.1.2" ("0" for synthesized root)
  depth: int           # segments in path; root = 0
  qty: int             # per-parent
  filename: str        # stripped Number
  raw: dict[str,str]   # full source row, post column-mapping
  children: list[BomNode]
  parent: BomNode|None
  # derived (computed once after tree build):
  qty_total: int       # product of qty along ancestor chain (root=1)
  part_number: str     # §4.1
  display_name: str    # §4.2
  is_assembly: bool    # extension == .SLDASM or has children
  cots: str            # §4.3 — verbatim from mapped column, else ""
  state: str           # from Found In (optional)
  file_url: str        # PDM viewer link from [links] template (D9), else ""
  material_props: dict # materials-database enrichment (D10), {} when off
  specs: list[str]     # spec-doc refs from columns.specs cell (§5.4, D11)
  spec: str            # primary (first) spec ref, "" when none
  diff: str            # ""|"changed"|"added" vs --diff-against (§5.5, D12)
```

Implementation: plain dataclass + dict index `{path: node}`; no external tree
library (anytree not needed at this scale; revisit >50k rows).

---

## 4. Derivation Rules

### 4.1 Abbreviated Part Number
```
stem      = filename minus extension
base      = first match of config regex `part_number_pattern` against stem,
            else whole stem
dash      = Rev, zero-padded to 2 chars if numeric; "00" if Rev empty
part_number = f"{base}-{dash}"
```
Default `part_number_pattern = "^([A-Za-z]+-[A-Za-z]{2}\\d+)"` → captures
`NCC-FA004` from `NCC-FA004.SLDASM`; non-matching stems (vendor files like
`96246A088_Helical Insert_RTX`) fall back to the full stem, no dash appended.

> **⚠ OPEN ITEM O1 (revisit):** dash number is currently sourced from `Rev`
> per decision D3 (2026-07-12). Rev is populated on only ~12% of rows in the
> sample; parts without Rev render as `-00`, which conflates "revision 0" with
> "revision unknown." Candidate future sources: PDM `Revision` variable on
> the *file* (vs. configuration), a dedicated DashNo variable, or the
> configuration name. Config key `dash_source` reserved for this.

### 4.2 Display name (template "Part Name")
Fallback chain: `Name` → `Description` → humanized stem (underscores→spaces).
Always suffixed with the filename in parentheses:
`Injector Mount Assembly Port No Coil (NCC-FA004.SLDASM)`.

### 4.3 COTS flag
**No heuristic.** *(Decision D1, 2026-07-12.)* The value is read verbatim from
the column named by `columns.cots` in the config. The team will add a COTS
variable to the SolidWorks/PDM data card (or hand-edit the CSV). Until that
column exists, the report column renders blank. bomgen emits a one-line
warning when the configured COTS column is absent from the input.

### 4.4 Quantity roll-up
`qty_total(node) = node.qty × qty_total(parent)`; root = 1. Matches the
template's *Qty (Assembly)* vs *Qty (Total)* pair. (Same semantics as
bomkit's aggregate.)

### 4.5 Level → marker columns
Template convention (inferred from the single example row — **confirm with
team**): numeric `Level` column = depth; X placed in marker column *depth*
for depth ≥ 1; the Level-0 root row gets X in **all** marker columns (as in
the provided template example).

---

## 5. Outputs

### 5.1 Excel (`excel_out`)
Reproduces `Book.xlsx` ("TEMPLATE Example") conventions **exactly** unless
config overrides:

- Font **Aptos Narrow** throughout (title 18 bold, header 14 bold, data 11).
- Title block: B6 "Bill of Materials (BOM)"; B7 `{title_line}` (e.g.
  "NCC-1701 BOM DRAFT, …"); B9–B13 project box (project title, System Name,
  Assembly Name, Contact Name, Contact Info), each merged B:G.
- Header band row 16: "Assembly Level" merged over the marker columns;
  "Quantity Required" merged over the two Qty columns; medium bottom border.
- Header row 17: marker columns numbered 1…N, then `Level`, `Abbreviated
  Part Number`, `Part Name`, `Description`, `COTS`, `Qty (Assembly)`,
  `Qty (Total)`, then any `passthrough_columns`.
- **Marker band width N = max(5, max depth)** — grows for deep assemblies,
  never shrinks below the template's 5.
- Data from row 18; column widths copied from template (H/I ≈ 111, J = 100…).
- **Excel-native row grouping**: each row's outline level = depth, so
  subassemblies collapse with Excel's +/− controls. `SUMMARY_ABOVE = False`… 
  set `sheet_properties.outlinePr.summaryBelow = False` so the parent row
  sits above its group.
- No formulas (report is a static snapshot); therefore no recalc step needed.
- **Data-quality banner** (§7, D6): when warnings exist, a yellow wrapped
  block merged over rows 2–5 (blank in the template, so the title block and
  header rows never move) lists them.
- **Source revision** *(D8)*: when `--source-rev` is given, row 8 (a blank
  spacer between the title line and the project box — never referenced
  elsewhere) gets "Source revision: {value}" in small non-bold text.

### 5.2 HTML (`html_out`)
One self-contained file, zero external requests (CSS+JS inlined, data embedded
as a JSON `<script>` blob) — the InteractiveHtmlBom packaging pattern.

Features (all vanilla JS, ~300 lines):
- Header: title, assembly, contact, generation timestamp, source filename.
- **Collapsible treegrid**: one `<tr>` per node, indented, ▸/▾ toggles;
  clicking a parent hides/shows its subtree.
- Controls: *Expand all*, *Collapse all*, *Level 1/2/3…* depth buttons,
  live text filter (matches any visible column; ancestors of matches stay
  visible), **Copy TSV** (visible rows → clipboard, pasteable into Excel).
- **Data-quality banner** (§7, D6): yellow box between header and controls
  listing caught warnings; injected server-side (`__WARNBOX__`), absent
  when there are none. Replaces the former footer warning note.
- Columns: Level path, Part Number, Part Name, Description, COTS badge,
  Qty, Qty Total, State, + passthrough. Column set driven by the same config.
- **Download Excel button** *(Decision D5, 2026-07-13)*: an `<a download>`
  in the controls bar pointing at the report's .xlsx twin. The href is
  injected at generation time (`__XLSX_HREF__`): `--xlsx-url` if given,
  else the .xlsx **filename** when the same run writes both outputs into
  the same directory, else empty — and an empty href removes the button
  client-side. A relative href is deliberately host-agnostic: it works on
  GitHub Pages, GitLab Pages, `file://`, and plain file shares, with no
  service detection. The self-contained-file guarantee is unchanged — the
  page makes no request unless the button is clicked, and a downloaded
  HTML sans .xlsx simply drops the button.
- **Source revision** *(D8)*: when `--source-rev` is given, the header's
  generation line gets a " · rev `{value}`" suffix; empty when omitted.
  bomgen treats the value as opaque text — no git dependency in bomgen
  itself — so it works with any VCS or provenance scheme a caller wants.
- **PDM viewer links** *(D9)*: when `[links].file_url_template` is set, the
  filename inside each Part Name becomes a link to the PDM web viewer. The
  template takes `{found_in}` (the Found In vault folder mapped to a URL
  path — the leading `<drive>:\<Vault>\` stripped automatically for any
  drive letter, backslashes → "/") and/or `{file}` (the filename), each
  URL-encoded. `found_in_strip` overrides the auto strip for non-standard
  layouts. In Excel the Part Name cell is a hyperlink instead (xlsx can't
  link a substring). Off by default.
- **Material properties** *(D10)*: when `[materials].enabled`, each row's
  `Material` is matched (by name/synonym, whitespace/case-insensitive)
  against a committed materials-database export — the raw `/export/raw-json`
  dump read from local disk (never the network) — and the configured
  `properties` are appended as columns in both outputs via the same dynamic
  passthrough mechanism (no `template.html` change). Cache-file trouble → V8;
  unmatched materials → grouped V9. Full design in `MATERIALS_DB_PLAN.md`.
- Print stylesheet: tree fully expanded, controls hidden.

### 5.3 Pages publishing (compile-time .xlsx)
The .xlsx cannot be generated in the browser (openpyxl is Python), so the
published site is compiled in CI and the two artifacts are deployed side by
side:

```
site root: index.html (HTML report) + <stem>_BOM.xlsx  ← button target
```

- `scripts/build_pages.sh INPUT [CONFIG] [OUTDIR]` — the single build step,
  shared verbatim by both CI configs so GitHub/GitLab can't drift.
- `.github/workflows/pages.yml` — GitHub Actions: test → build `_site/` →
  `upload-pages-artifact` → `deploy-pages` (OIDC; Settings → Pages source
  must be "GitHub Actions").
- `.gitlab-ci.yml` — GitLab CI: `pages` job publishing `public/`
  (auto-deployed by job-name convention), default branch only.
- Published input selected by `BOM_INPUT` / `BOM_CONFIG` variables in each
  CI file (defaults: the NCC-1701 example).

Step-by-step service setup: `PAGES_SETUP.md`.

### 5.4 Spec/RFQ budget outputs (`--budget`, `--dashboard`) *(D11)*

Parts are flagged into procurement categories by a **spec-document
reference** carried in a column of the export (mapped via `columns.specs`,
default header `Specs` — adjustable like every column; a cell may list
several refs separated by `[budget].spec_separator`, and the **first** is
the category used for cost rollup, V11 warning on the rest).

**Coverage semantics** (`budget_rollup()`): a node carrying a spec is a
budget **line item**, and its whole subtree is covered by that line — a
quoted weldment includes its piece parts. Identical parts (same filename)
under the same spec merge into one line with summed `qty_total` and a use
count. Leaf parts under no spec'd ancestor land in **(unassigned)** so
budget gaps are visible, never silent (V10). A spec'd item nested inside
another spec'd subtree is allowed but flagged (V12 — possible double-count).

Two outputs, both optional and off unless requested:

- **Budget workbook** (`write_budget_xlsx`): sheet *Budget* = one row per
  spec, `COUNTIF`/`SUMIF`-linked to sheet *Parts* — the costing template
  where unit **WAG / ROM / Quote** are typed into shaded input columns.
  `Unit Best = Quote, else ROM, else WAG`; extended costs are
  `qty × unit` formulas, so the workbook keeps rolling up as estimates
  mature. **Deliberate exception to the no-formulas rule** of the BOM
  report (§5.1) — this is a working costing sheet, not a static snapshot.
  Spec-document hyperlinks via `[links].spec_url_template` (`{spec}`).
- **Dashboard** (`bomgen/dashboard.html`, same self-contained packaging as
  the BOM page): stat tiles (specs / line items / total qty / unassigned),
  one collapsible group per spec with a single-hue quantity bar, live
  filter, the shared yellow warning banner, and relative sibling links to
  the budget workbook and the BOM page (same rule as the Excel download
  button, D5). Costs are *not* on the dashboard — they live in the
  workbook; the page shows the structural rollup the costs hang off.

CI: `scripts/build_pages.sh` publishes both when `BUILD_DASHBOARD=1`
(opt-in so spec-less repos don't get a permanent V10 warning).

### 5.5 Change highlighting & historical tagged views *(D12)*

**Change highlighting** (`--diff-against PREV`): rows whose content changed
or that were added since a previous version of the export are highlighted
**green** in every output — BOM HTML, BOM xlsx, dashboard line items, and
the budget workbook's Parts sheet (owner choice: everywhere). Removed parts
can't be highlighted (no row), so they're summarized in the warning banner
(`DIFF:` line). Semantics:

- **Row identity is never the Level path** (renumbering isn't change):
  match by filename within the same parent, falling back to
  filename-anywhere for moved parts — a **move with identical content is
  not a change**.
- **Only report columns are compared** (mapped + passthrough), so PDM
  churn in unmapped metadata (e.g. `Checked Out By`) never lights a row;
  `[diff].ignore_columns` can exclude report columns too.
- bomgen stays VCS-agnostic (same pattern as `--source-rev`): the caller
  extracts the previous file (`git show`); an unreadable previous file is
  a warning, never an abort.

**Historical tagged views** (`BUILD_HISTORY=1` in `build_pages.sh`): every
git tag is rebuilt on every run **with the current generator** — dashboard
improvements retroactively apply to all historical source data, and no
compiled branch exists. Each tag's pages land in `OUTDIR/v/<tag>/`, built
from that tag's own CSV + config. Failed/incomplete tags are skipped with
a warning, never blocking current publishing.

- **Diff baselines are hybrid** (owner decision): the current page diffs
  against the previous commit touching the input; each tag page diffs
  against the **previous tag** ("what changed in this release").
- **Yellow historical chrome** (`--historical LABEL`): tag pages tint the
  background yellow and pin an alert bar linking back to current; the
  xlsx outputs get a yellow "HISTORICAL VERSION" cell.
- **Version dropdown**: the build writes a `versions.js` (relative hrefs
  only — works at any hosting root and on `file://`) into every page
  directory; pages load it as an *optional* sibling script. A single
  copied-out HTML file simply has no dropdown and is otherwise fully
  functional — the self-contained guarantee is preserved.

---

## 6. Configuration (`bomgen.toml`)

```toml
[project]
title_line   = "NCC-1701 BOM DRAFT, …"
project_box  = "PROJECT NAME AND TITLE BOX"
system_name  = "USS Enterprise Deflector Subsystem"
assembly_number      = "NCC-FA001-00"   # synthesized Level-0 root (D2)
assembly_name        = "Enterprise Deflector Final Assy (NCC-FA001.SLDASM)"
assembly_description = "Final Deflector Top Level Assembly"
contact_name = ""
contact_info = ""

[columns]                 # map logical field -> CSV header
level       = "Level"
qty         = "Qty"
number      = "Number"
name        = "Name"
config      = "Config"
rev         = "Rev"
description = "Description"
found_in    = "Found In"
cots        = "COTS"      # D1: read verbatim; absent -> blank + warning
passthrough = ["Material", "Mass"]   # appended verbatim to both outputs

[rules]
part_number_pattern = '^([A-Za-z]+-[A-Za-z]{2}\d+)'
dash_source = "rev"       # reserved: rev | config | variable:<Name>  (O1)
min_marker_columns = 5
state_from_found_in = true   # derive State column from vault path tail

[output]
excel_font = "Aptos Narrow"
```

Config lookup order: `--config PATH` → `./bomgen.toml` → built-in defaults.

---

## 7. Validation (fail loudly, report all findings at once)

| ID | Check | Severity |
|---|---|---|
| V1 | every non-root path's parent exists | error |
| V2 | duplicate paths | error |
| V3 | leading-space indent ÷ 2 == depth − 1 (when spaces present) | warning |
| V4 | Qty parses as positive int | warning (defaults 1) |
| V5 | required mapped columns present in header | error (except `cots`: warning) |
| V6 | depth jumps >1 relative to previous row | warning (dotted paths make this legal but it usually signals a truncated export) |
| V7 | cell holds an unresolved SolidWorks property expression (`SW-*@…`, e.g. `SW-Mass@.SLDPRT`) instead of an evaluated value — the file was never rebuilt/saved after the property was linked | warning, grouped per column with a count (fix in CAD, not in bomgen) |
| V8 | materials enrichment enabled but the configured cache file is missing/unreadable | warning (properties left blank; feature otherwise off) |
| V9 | a row's Material is not found in the materials-database export | warning, grouped with a count + examples (re-export the JSON or fix the name) |
| V10 | budget requested but the specs column is missing, or leaf parts are covered by no spec | warning (parts land in "(unassigned)" — budget gaps visible, not silent) |
| V11 | a row lists multiple spec references | warning (only the first is used for cost rollup) |
| V12 | a spec'd item nested inside another spec'd subtree | warning (possible double-counted cost) |
| R1 | duplicate dotted path repaired by re-appending zeros ("2.1"→"2.10") iff result equals next expected sibling — recovers Excel float-mangling of two-segment item numbers | warning (export direct from PDM to avoid entirely) |

Errors abort before writing outputs. Warnings print to stderr **and render
as a yellow data-quality banner at the top of both outputs** *(Decision D6,
2026-07-13)* — first 8 warnings, then a "+N more" line — so a reader of the
published report sees caught gotchas (R1 float-mangling, V7 unresolved
SW properties, missing COTS column, O2 XML caveats, …) without access to
the generator's stderr. No warnings → no banner.

---

## 8. CLI

```
bomgen INPUT.{csv|xml} [-c bomgen.toml] [--xlsx [OUT]] [--html [OUT]] [--both]
                       [--budget [OUT]] [--dashboard [OUT]]
                       [--xlsx-url URL] [--materials-cache PATH]
                       [--diff-against PREV] [--historical LABEL]
                       [--source-rev REV] [--repo NAME] [--branch NAME]
                       [--commit SHA] [--source-url URL] [--source-path PATH]
                       [-o OUTDIR] [--quiet]
```
- `--xlsx-url` overrides the HTML download-button target (§5.2, D5).
- `--budget` / `--dashboard` write the spec/RFQ budget outputs (§5.4, D11).
- `--materials-cache` overrides `[materials].cache_file` and implies
  `enabled=true` for the run (D10).
- `--diff-against` / `--historical` drive change highlighting and the
  yellow historical chrome (§5.5, D12).
- `--source-rev` plus `--repo/--branch/--commit/--source-url/--source-path`
  feed the build-provenance record (D8, D13) — all opaque strings computed
  by the caller (normally `scripts/build_pages.sh`); bomgen has no VCS
  dependency itself.

Single-module implementation (`bomgen/__init__.py`, matching the original
single-file philosophy — one file of logic, no internal package split);
stdlib + `openpyxl` only (`tomllib` is stdlib ≥3.11). Packaged for
installation via `pyproject.toml` at the repo root (D7) — `pip install
bomgen` gives a `bomgen` console script and `python -m bomgen` both; a
clone still works dependency-free by running `python -m bomgen` from the
repo root without installing. Exit 0 clean, 1 validation error, 2 usage
error.

## 8.1 Packaging & downstream vault repos (D7, D8)

bomgen's own repo holds no real BOM data — the CSV/XML export belongs to
whoever owns the vault, in their own repo. That repo needs three things
this repo doesn't provide by itself:

1. **pdmbomgen installed as a dependency, not vendored** — so a fix merged
   upstream reaches every downstream repo without anyone copy-pasting a
   new script version.
2. **The exported CSV/XML under version control**, so changes to the BOM
   are auditable.
3. **A compiled report that says which commit of the CSV it came from** —
   the "is this report current?" question answered by the report itself.

`template-repo/` in this repo is a copy-out starting point for that
pattern:
- `requirements.txt` pins `pdmbomgen @ git+https://github.com/douglase/
  pdmbomgen.git@main` — **not** a tagged release. CI reinstalls it fresh
  on every build, so a push to pdmbomgen's `main` is picked up by every
  downstream repo's *next* build with zero action from that repo's owner.
  (Trade-off: an upstream breaking change also reaches everyone
  immediately; pin to a tag instead if that's a bigger risk than staleness
  for your team.)
- `scripts/build_pages.sh` computes `git log -1 --format=%h -- "$BOM_INPUT"`
  **in the downstream repo's own history** (not pdmbomgen's) and passes it
  as `--source-rev`, so the compiled report is stamped with the commit
  that last touched the actual vault export.
- A scheduled CI trigger (weekly, in addition to on-push) so repos whose
  CSV rarely changes still periodically rebuild and pick up upstream
  pdmbomgen fixes even without a commit of their own.

See `template-repo/SETUP.md` for the bootstrap steps.

## 9. Testing
- Golden-file test: sample CSV → compare parsed tree (paths, qty_total) to a
  checked-in JSON snapshot.
- Round-trip sanity: Σ(leaf qty_total) invariant under tree rebuild.
- Encoding fixtures: utf-8-sig, utf-16, embedded commas/quotes.

## 10. Future Work
- **O1** dash-number source (see §4.1).
- **O2** verify XML export schema against a real vault export (see §2.5).
- Confirm X-marker convention for the root row (§4.5).
- BOM **compare** mode (PDM exports comparison views too) → HTML diff.
- Mass / cost roll-up columns (Mass column already passes through).
- Optional live PDM access via SolidWrap instead of CSV.
- Flight-hardware columns (TRL, CVCM/TML/WVR, temps, ECCN) promoted from
  passthrough to first-class once the team populates them. The
  material-derived subset (density, CTE, outgassing TML/CVCM, tensile/yield,
  thermal props) is separately addressed by the **materials_database
  enrichment** plan below.
- **Material-property enrichment from `materials_database`** (deferred; full
  design in [`MATERIALS_DB_PLAN.md`](MATERIALS_DB_PLAN.md)). A two-stage
  design keeps bomgen network-free: an out-of-runtime sync script pulls the
  database's unauthenticated `/export/raw-json` into a local JSON cache, and
  bomgen (config-gated, `[materials].enabled`) merges matched properties from
  that cache into each BOM row at generation time — additive, a no-op when
  the cache is absent. A complementary path already exists on the database
  side (`/export/solidworks` → `.sldmat` imported into the CAD material
  library → properties flow through PDM as ordinary columns, needing no
  bomgen change).
- **Historical / tagged views** — ~~future~~ **implemented 2026-07-19**
  (D12, §5.5). Original owner-specified design, kept for the record:
  1. **Change highlighting**: when a row's content differs between the
     current CSV and the same file at the *previous git commit*, highlight
     that row **green** in the generated pages, so evolution is visible at
     a glance. (Needs the caller to supply the prior CSV — same
     VCS-agnostic pattern as `--source-rev`; bomgen diffs two files, git
     stays in the build script.)
  2. **Tagged-version pages**: CI rebuilds the site for **every git tag**
     on each run (tags recompiled with the *current* generator, so
     dashboard improvements retroactively apply to all historical source
     data — no compiled branch needed). Each tag's pages land in a
     subdirectory; a **dropdown menu** on every page lists the tags.
  3. **Historical alert**: pages generated from a non-current tag switch
     the page chrome to **yellow** so the reader knows they're looking at
     a historical version.

## Decision log
| ID | Date | Decision |
|---|---|---|
| D1 | 2026-07-12 | COTS: no heuristic; explicit PDM/CSV column only (team to add variable). |
| D2 | 2026-07-12 | Root row absent from export; synthesize Level-0 from config metadata. |
| D3 | 2026-07-12 | Dash number from `Rev` for now; flagged as open item O1. |
| D4 | 2026-07-12 | XML export-rule ingest added (`read_xml`); XML = automation path (fires on workflow transition), CSV = interactive path. Schema verification = O2. |
| D5 | 2026-07-13 | HTML gets a Download Excel button; .xlsx compiled in CI and deployed **next to** index.html on GitHub/GitLab Pages, so the button is a relative href (host-agnostic, both services, no runtime detection). `--xlsx-url` overrides; button self-removes when no target is known. |
| D6 | 2026-07-13 | Warnings promoted from HTML footer note to a yellow data-quality banner at the top of **both** outputs (Excel rows 2–5, HTML below header); new V7 check flags unresolved `SW-*@` property expressions (e.g. `SW-Mass@.SLDPRT`). |
| D7 | 2026-07-13 | Packaged as an installable module: `bomgen.py` moved to `bomgen/__init__.py` + `bomgen/template.html` (package data) + `bomgen/__main__.py`, with `pyproject.toml` at repo root providing a `bomgen` console-script entry point. Still one file of logic (`__init__.py`); the split is packaging-only, not an architecture change. Lets downstream vault repos `pip install` straight from this repo instead of vendoring the script (§8.1). |
| D8 | 2026-07-13 | `--source-rev` CLI flag: opaque provenance string (typically a git commit hash, computed by the caller — bomgen stays VCS-agnostic) embedded in both outputs, so a compiled report says which commit of the source CSV/XML it reflects. Backs the `template-repo/` vault-repo pattern (§8.1). |
| D9 | 2026-07-15 | Filenames link to a PDM web viewer. `[links].file_url_template` takes `{found_in}` (the Found In vault path → URL tail; the leading `<drive>:\<Vault>\` is auto-stripped for any drive letter, backslashes → "/", `found_in_strip` overrides) and/or `{file}` (the SolidWorks filename), each URL-encoded. HTML linkifies the filename inside the Part Name; Excel makes the Part Name cell a hyperlink (xlsx can't link a substring). Empty template (default) = no links, unchanged output. Host/vault base is project-configured, never hardcoded. |
| D10 | 2026-07-17 | Material-property enrichment (Stage B of `MATERIALS_DB_PLAN.md`). New `[materials]` config reads a committed materials-database `/export/raw-json` dump from **local disk** (never the network — keeps CI/HTML network-free) and appends chosen properties as columns, matched by Material name/synonym. `enrich_materials()` runs after `derive()`; `material_cache_key()` is the shared match contract. Off by default; missing file → V8, unmatched material → grouped V9; never aborts. The out-of-repo sync (Stage A) is unneeded when the dump is committed directly. |
| D11 | 2026-07-19 | Spec/RFQ budget outputs (§5.4): parts categorized by a spec-document reference column (`columns.specs`, adjustable; multi-ref cells split on `[budget].spec_separator`, first wins). A spec'd node covers its subtree; uncovered leaf parts land in "(unassigned)" (V10), multi-spec V11, nested-spec V12. Budget workbook = SUMIF-linked rollup + WAG/ROM/Quote costing template (**deliberate formulas exception** to §5.1's no-formulas rule); dashboard = self-contained rollup page. CI publishing opt-in via BUILD_DASHBOARD=1. |
| D12 | 2026-07-19 | Historical phase (§5.5): `--diff-against` green change-highlighting in **all** outputs (row identity by filename-within-parent, never Level path; report-columns-only comparison + `[diff].ignore_columns`; moves are not changes; removed parts summarized in banner). Hybrid baselines: current page vs previous commit, tag pages vs previous tag. `BUILD_HISTORY=1` rebuilds every git tag with the current generator into `v/<tag>/` (skip-on-fail), `--historical` yellow chrome, and a per-directory `versions.js` dropdown loaded as an optional sibling script so single-file copies stay fully functional. |
| D13 | 2026-07-20 | Build-provenance block in every output: collapsible `<details>` in both page headers, a linked cell in both workbooks (BOM xlsx row 14, Budget sheet below TOTAL). Records source BOM path (hyperlinked to its blob URL at the build commit), source data rev, repo/branch/build-commit, config file, and toolchain versions (bomgen, Python, openpyxl). Git facts arrive via `--repo/--branch/--commit/--source-url/--source-path` computed by build_pages.sh from CI env vars (GitHub/GitLab) or the git remote — bomgen stays VCS-agnostic; toolchain versions are self-determined. |
