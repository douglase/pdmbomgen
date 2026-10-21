# Budget repo template — the primary cost model

This folder is the starting point for a **budget repo**: the
version-controlled home of a project's spec assignments and cost estimates,
published as a dashboard + downloadable budget workbook. It is deliberately
**separate from the vault repo** (which holds the PDM BOM export) and from
pdmbomgen (the tool):

```
pdmbomgen  (tool, pip-installed from git)      — HOW to build
vault repo (PDM export, e.g. vault/x.csv)      — WHAT the hardware is
budget repo (THIS: specs.csv + costs.csv + CI) — WHAT it costs
```

Each CI build clones the vault repo, joins the BOM to the two committed
tables here, and publishes to GitLab Pages:

- `dashboard.html` — budget by spec: Best-dollar tiles and per-spec totals,
  collapsible part groups, spec-document links, download buttons for both
  workbooks
- `index.html` — the full interactive BOM page
- `<stem>_Budget.xlsx` — the budget workbook, WAG/ROM/Quote **prefilled
  from costs.csv** with a live `Best = Quote, else ROM, else WAG` chain
- `<stem>_BOM.xlsx` — the plain BOM workbook

## The two tables you maintain

**`specs.csv`** — `File,Spec[,Note]`: which spec/RFQ category each
SolidWorks file belongs to. An assembly's spec covers its whole subtree (a
quoted weldment includes its piece parts). The PDM export never needs a
specs column; rows naming files that left the BOM warn (V13) instead of
silently rotting.

**`costs.csv`** — `Spec,WAG,ROM,Quote[,Note,...]`: spec-level dollars, any
subset filled. `$12,000`-style values parse. Uncosted specs and stale rows
warn (V16), so the dashboard's "Specs costed" tile tells you when the
budget total is incomplete. Every **other** column passes through to the
Budget sheet verbatim — this template ships the export-control review set
(Hardware / Technology / Software / Intent to Publish Research Product
Design / Existing Publication / Rationale / Vendor); add or remove columns
freely. Worked examples for both tables: `BUDGET_GUIDE.md` in the
pdmbomgen repo.

Commit a change to either table (or wait for the weekly schedule to pick up
vault/tool changes) and the site rebuilds.

## Setup

1. Copy this folder to a new GitLab repo and push.
2. In `.gitlab-ci.yml` (or Settings → CI/CD → Variables) set
   `VAULT_REPO_URL` and `VAULT_BOM_PATH`. Private vault repo on the same
   GitLab instance: use
   `https://gitlab-ci-token:${CI_JOB_TOKEN}@<host>/<group>/<vault>.git`
   and allowlist this project in the vault repo under **Settings → CI/CD →
   Job token permissions**.
3. Fill in `bomgen.toml` (`[project]`, and `spec_url_template` if your spec
   documents are linkable), then replace the placeholder rows in `specs.csv`
   and `costs.csv`.
4. Add a weekly pipeline schedule (**Build → Pipeline schedules**) so the
   site tracks vault commits and upstream pdmbomgen fixes.
5. If pdmbomgen (the tool) is private, add a `PDMBOMGEN_TOKEN` CI variable —
   same mechanism as the vault template, see its SETUP.md §4.5.

Provenance on every page/workbook shows the vault repo's commit for the BOM
(computed from the clone), this repo's commit for the cost model, and the
pdmbomgen version+commit that compiled — three repos, all pinned.

Keeping a high-level Smartsheet (or similar) alongside? Treat this repo as
the source of truth and carry over only the per-spec Best totals from the
Budget sheet's TOTAL row.
