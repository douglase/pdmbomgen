# Budget repository template — the primary cost model

This folder is the starting point for a **budget repository**: the
version-controlled home of a project's spec assignments and cost
estimates, published as a dashboard and a downloadable budget workbook.
It's deliberately separate from the vault repository (which holds the PDM
BOM export) and from pdmbomgen (the tool):

```
pdmbomgen   (tool, pip-installed from git)       — HOW to build
vault repo  (PDM export, for example vault/x.csv) — WHAT the hardware is
budget repo (THIS: specs.csv + costs.csv + CI)    — WHAT it costs
```

Each CI build clones the vault repository, joins the BOM to the two
tables committed here, and publishes to GitLab Pages:

- `dashboard.html` — the budget by spec: Best-dollar tiles, per-spec
  totals with export-control details in the tooltips, collapsible part
  groups, spec-document links, and download buttons for both workbooks
- `index.html` — the full interactive BOM page
- `<stem>_Budget.xlsx` — the budget workbook, WAG/ROM/Quote prefilled
  from `costs.csv` with a live `Best = Quote, else ROM, else WAG` chain
- `<stem>_BOM.xlsx` — the plain BOM workbook

## The two tables you maintain

**`specs.csv`** (`File,Spec[,Note]`) — which spec or RFQ category each
SOLIDWORKS file belongs to. An assembly's spec covers its whole subtree,
so a quoted weldment includes its piece parts, and the PDM export never
needs a specs column. Rows naming files that left the BOM warn (V13)
instead of silently rotting.

**`costs.csv`** (`Spec,WAG,ROM,Quote[,Note,…]`) — spec-level dollars,
any subset filled; values like `$12,000` parse. Uncosted specs and stale
rows warn (V16), so the dashboard's *Specs costed* tile tells you when
the budget total is incomplete. Every other column passes through to the
workbook's Budget sheet verbatim — this template ships the
export-control review set (*Hardware*, *Technology*, *Software*, *Intent
to Publish Research Product Design*, *Existing Publication*,
*Rationale*, *Vendor*); add or remove columns freely. Worked examples
for both tables are in `BUDGET_GUIDE.md` in the pdmbomgen repository.

Commit a change to either table (or wait for the weekly schedule to pick
up vault and tool changes) and the site rebuilds.

## Set it up

1. Copy this folder to a new GitLab repository and push.
2. In `.gitlab-ci.yml` (or under **Settings → CI/CD → Variables**), set
   `VAULT_REPO_URL` and `VAULT_BOM_PATH`. For a private vault repository
   on the same GitLab instance, use
   `https://gitlab-ci-token:${CI_JOB_TOKEN}@<host>/<group>/<vault>.git`
   and allowlist this project in the vault repository under
   **Settings → CI/CD → Job token permissions**.
3. Fill in `bomgen.toml` (`[project]`, and `spec_url_template` if your
   spec documents are linkable), then replace the placeholder rows in
   `specs.csv` and `costs.csv`.
4. Add a weekly pipeline schedule (**Build → Pipeline schedules**) so the
   site tracks vault commits and upstream pdmbomgen fixes.
5. **Rebuild on vault pushes (recommended):** in the *vault* repository,
   set a CI/CD variable `BUDGET_REPO_PROJECT` to this project's full
   path. Its `trigger_budget_rebuild` job then fires this repository's
   pipeline on every BOM push, so the dashboard follows the BOM
   immediately instead of waiting for the weekly schedule. This needs
   GitLab 15.3 or later and the pusher to have Developer access here;
   the vault CI file's comments describe the pipeline-trigger-token
   fallback for older instances.
6. If pdmbomgen (the tool) is private, add a `PDMBOMGEN_TOKEN` CI
   variable — the same mechanism as the vault template; see its
   SETUP.md §4.5.

Provenance on every page and workbook shows the vault repository's
commit for the BOM (computed from the clone), this repository's commit
for the cost model, and the pdmbomgen version and commit that compiled —
three repositories, all pinned.

Keeping a high-level Smartsheet (or similar) alongside? Treat this
repository as the source of truth and carry over only the per-spec Best
totals from the Budget sheet's TOTAL row.
