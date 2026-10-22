# Plan: spec-level financial budget — decoupled cost model
_The decided architecture, the rollout checklist, and the deferred follow-ups._

**Status: implemented in pdmbomgen** (decision D14; §5.4 and the §1.1
data-flow diagrams in `BOMGEN_DESIGN.md`). What remains is the rollout —
standing up the budget repo and migrating real data — which is tracked
here.

## The architecture (decided 2026-10-20)

Three repos, three responsibilities:

```
pdmbomgen   (tool, pip-installed @main by CI)   — HOW to build
vault repo  (PDM export, for example vault/x.csv) — WHAT the hardware is
budget repo (specs.csv + costs.csv + CI)        — WHAT it costs
```

- **Spec-level costing** (owner decision): `costs.csv` holds
  `Spec,WAG,ROM,Quote[,Note]` per RFQ category, not per part.
  `Best = Quote, else ROM, else WAG`.
- **Spec assignment decoupled from PDM** (owner decision): `specs.csv`
  (`File,Spec[,Note]`) assigns categories by filename, so each PDM
  re-export never touches specs or costs; the table wins over any specs
  column in the export (V14), stale rows warn (V13).
- **The budget repo is the primary cost model** (owner decision; a
  high-level Smartsheet persists, carrying only per-spec Best totals from
  the Budget sheet's TOTAL row).
- Rollups happen in Python at build time: dashboard gets Budget (Best) /
  Specs costed tiles and a per-spec Cost (Best) column; the downloadable
  budget workbook's Budget sheet is prefilled from `costs.csv` with a live
  Best chain. Uncosted specs warn (V16) so totals are never quietly
  incomplete.

## Rollout checklist (user side)

1. Create the budget repo on GitLab from `template-budget-repo/`
   (copy the folder, push, enable Pages — its README walks through it).
2. Set `VAULT_REPO_URL` + `VAULT_BOM_PATH` in its `.gitlab-ci.yml` (or as
   CI/CD variables). Same-instance private vault: the
   `gitlab-ci-token:${CI_JOB_TOKEN}@` URL plus allowlisting the budget
   project under the vault repo's **Settings → CI/CD → Job token
   permissions**.
3. Populate `specs.csv` from the current assembly (start with the big
   quoted weldments/assemblies — a spec'd assembly covers its subtree,
   so a few rows cover many parts; the V10 unassigned count on the
   dashboard shows what's left).
4. Fill `costs.csv` with the current WAG/ROM/Quote state; the V16 warnings
   and the "Specs costed" tile track coverage.
5. Add a weekly pipeline schedule (**Build → Pipeline schedules**) so the
   site follows vault commits and upstream pdmbomgen fixes.
6. In the **vault repo**, set CI/CD variable `BUDGET_REPO_PROJECT` to the
   budget project's path so every BOM push triggers a budget rebuild
   immediately (vault CI's `trigger_budget_rebuild` job; the weekly
   schedule then only backstops tool updates).
7. Retire per-part costing habits: numbers typed into a downloaded
   workbook persist only when copied back into `costs.csv`.

## Follow-ups (not yet built)

- **`--extract-costs filled.xlsx`** — read a hand-edited budget workbook
  and write the numbers back into `costs.csv`, closing the round trip if
  editing CSVs by hand proves tedious.
- **History for the budget repo** — `BUILD_HISTORY` is off there because a
  tag of the budget repo pins the cost model but not the vault clone;
  pinning the vault revision per tag (for example, a committed `vault.lock` with
  the SHA to clone) would make tagged budget snapshots fully reproducible.
- **Smartsheet handoff** — if copying Best totals by hand gets old, a tiny
  exporter (per-spec `Spec,Best` CSV already derivable from the rollup)
  could feed whatever import Smartsheet offers. Deliberately out of scope
  until the manual step actually hurts.
