# Setup: bootstrapping a new vault-BOM repo from this template

Do this once per PDM vault/assembly you want a published BOM for.

## 1. Copy this folder into a new repo

```bash
cp -r template-repo/ /path/to/my-vault-bom
cd /path/to/my-vault-bom
git init
```

(Once this pattern has a life of its own, the recommended path is a real
GitHub "Template repository" — click **Use this template** — instead of a
manual copy; see the note at the bottom.)

## 2. Add your real PDM export

Delete the placeholder and drop in your actual export:

```bash
rm vault/PLACEHOLDER_pdmout.csv
cp /path/to/your/PDM_export.csv vault/
```

CSV (interactive PDM export) or XML (automation/export-rule path) both
work — see the main pdmbomgen README for the difference. **Do not**
round-trip the CSV through Excel before committing it (Excel mangles
two-segment item numbers; bomgen repairs the common case with a warning,
but exporting straight from PDM avoids it entirely).

## 3. Edit `bomgen.toml`

At minimum, set:
- `[project]` — `title_line`, `system_name`, `assembly_number`,
  `assembly_name`, `assembly_description`, `contact_name`, `contact_info`
- `[columns]` — only if your PDM export uses different column headers than
  the defaults (`Level`, `Qty`, `Number`, …)

Full field reference: `BOMGEN_DESIGN.md` §6 in the pdmbomgen repo.

## 4. Point CI at your file

Edit `BOM_INPUT` (and `BOM_CONFIG` if you renamed the config) in **both**
`.github/workflows/pages.yml` and `.gitlab-ci.yml` — you only need the one
matching your host, but both are harmless to keep:

```yaml
env:                          # GitHub
  BOM_INPUT: vault/your_export.csv
```
```yaml
variables:                    # GitLab
  BOM_INPUT: vault/your_export.csv
```

## 4.5 If pdmbomgen (the tool repo) is private

`requirements.txt` installs pdmbomgen via anonymous `git clone`. That only
works if `douglase/pdmbomgen` is **public** — an anonymous clone of a
private repo fails in CI with `could not read Username for
'https://github.com'` (no TTY to prompt for credentials).

Two ways to fix it, pick one:

- **Make pdmbomgen public** (simplest, no CI config needed): it's just the
  tool — code, docs, a sanitized example CSV — not anyone's real vault
  data, which stays wherever *this* repo is hosted and can stay private
  independently. On github.com: **Settings → General → Danger Zone →
  Change visibility → Public**.
- **Keep it private, authenticate CI**: both CI configs already support
  this, no-op if unused.
  - **GitLab**: create a GitHub PAT with read-only access to pdmbomgen,
    add it as a masked/protected CI/CD variable named `PDMBOMGEN_TOKEN`
    (**Settings → CI/CD → Variables**).
  - **GitHub**: same PAT, added as a repo secret named `PDMBOMGEN_PAT`
    (**Settings → Secrets and variables → Actions → New repository
    secret**).
  - Rotate the PAT before it expires, or CI starts failing again with the
    same error.

## 5. Commit and push

```bash
git add -A
git commit -m "Initial vault BOM: <assembly name>"
git remote add origin <your new repo's URL>
git push -u origin main
```

## 6a. Enable GitHub Pages

1. Push to a GitHub repo (default branch `main` — if different, update
   `branches: [main]` in `.github/workflows/pages.yml`).
2. Repo → **Settings → Pages → Build and deployment → Source** →
   **GitHub Actions**.
3. Repo → **Settings → Actions → General → Workflow permissions** — the
   defaults work; nothing else to change.
4. Push (or **Actions → Publish BOM to GitHub Pages → Run workflow**) to
   trigger the first build. The deploy job prints the live URL
   (`https://<user>.github.io/<repo>/`).

## 6b. Enable GitLab Pages

1. Push to a GitLab repo. `.gitlab-ci.yml` at the root is picked up
   automatically.
2. Confirm shared/project runners are enabled (**Settings → CI/CD →
   Runners**) — gitlab.com's shared runners work out of the box.
3. Push to trigger the `pages` job; **Deploy → Pages** shows the live URL
   once it succeeds.
4. **Set up the weekly rebuild** (GitLab schedules live outside the YAML):
   **Build → Pipeline schedules → New schedule** — e.g. weekly, targeting
   the default branch. This is what lets upstream pdmbomgen fixes reach
   this repo's published site even when nobody edits the CSV.
   (GitHub's equivalent `schedule:` trigger is already in
   `.github/workflows/pages.yml` — no extra step needed there.)

## 6c. Optional features (env toggles, preset in both CI configs)

- `BUILD_DASHBOARD=1` (default here) — publishes the spec/RFQ budget
  dashboard + workbook; map your spec column via `[columns].specs` in
  `bomgen.toml` or every part reports as unassigned.
- `BUILD_HISTORY=1` (default here) — rebuilds every git tag into
  `v/<tag>/` with yellow historical chrome and a version dropdown; push a
  tag (`git tag v1.0 && git push origin v1.0`) to populate it. Pushing a
  tag also triggers a republish on both services.

## 6d. Updating the machinery later

When the pdmbomgen template gains features (CI toggles, build-script
improvements), refresh your copy from the repo root with:

```bash
bash scripts/update_from_template.sh
```

It overwrites machinery only (build scripts, CI configs, requirements,
SETUP.md), never your payload (`vault/`, `bomgen.toml`, `README.md`), and
preserves your `BOM_INPUT`/`BOM_CONFIG` values. It refuses to run on a
dirty tree or outside a vault repo, stages the changes, and leaves the
commit to you. If pdmbomgen is private and https auth fails:
`PDMBOMGEN_REPO=git@github.com:douglase/pdmbomgen bash scripts/update_from_template.sh`

## 7. Verify

Open the published URL: the BOM should render, the **Download Excel**
button should serve the `.xlsx`, and the header should show a
"· rev `<hash>`" provenance stamp matching your last commit to the CSV.

## Turning this into a real GitHub template repository

Once you (or your org) are happy with this starting point, push it to its
own repo and check **Settings → General → Template repository** there.
Future vault repos can then click **Use this template** on GitHub instead
of a manual `cp -r`, and this file becomes that new repo's actual
`SETUP.md` walkthrough (steps 2 onward still apply).
