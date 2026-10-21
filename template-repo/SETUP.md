# Set up a new vault-BOM repository from this template

Follow these steps once for each PDM vault or assembly you want a
published BOM for.

## 1. Copy this folder into a new repository

```bash
cp -r template-repo/ /path/to/my-vault-bom
cd /path/to/my-vault-bom
git init
```

Once this pattern has a life of its own, the recommended path is a real
GitHub template repository — click **Use this template** — instead of a
manual copy; see the note at the bottom.

## 2. Add your real PDM export

Delete the placeholder and drop in your actual export:

```bash
rm vault/PLACEHOLDER_pdmout.csv
cp /path/to/your/PDM_export.csv vault/
```

CSV (the interactive PDM export) and XML (the automation path) both work;
the main pdmbomgen README explains the difference. Don't open and re-save
the CSV in Excel before committing it — Excel rewrites two-segment item
numbers. bomgen repairs the common case with a warning, but exporting
straight from PDM avoids the problem entirely.

## 3. Edit bomgen.toml

At minimum, set:

- `[project]` — `title_line`, `system_name`, `assembly_number`,
  `assembly_name`, `assembly_description`, `contact_name`, `contact_info`
- `[columns]` — only if your PDM export uses different column headers
  than the defaults (`Level`, `Qty`, `Number`, and so on)

The full field reference is `BOMGEN_DESIGN.md` §6 in the pdmbomgen
repository.

## 4. Point CI at your file

Edit `BOM_INPUT` (and `BOM_CONFIG` if you renamed the configuration file)
in both `.github/workflows/pages.yml` and `.gitlab-ci.yml`. You only need
the one that matches your host, but both are harmless to keep:

```yaml
env:                          # GitHub
  BOM_INPUT: vault/your_export.csv
```
```yaml
variables:                    # GitLab
  BOM_INPUT: vault/your_export.csv
```

## 4.5 If pdmbomgen (the tool repository) is private

`requirements.txt` installs pdmbomgen with an anonymous `git clone`,
which only works while `douglase/pdmbomgen` is **public**. Cloning a
private repository anonymously fails in CI with `could not read Username
for 'https://github.com'`.

Pick one fix:

- **Make pdmbomgen public** (simplest; no CI configuration needed). It's
  only the tool — code, docs, and a sanitized example — not anyone's real
  vault data, which stays wherever this repository is hosted and can stay
  private independently. On github.com: **Settings → General → Danger
  Zone → Change visibility → Public**.
- **Keep it private and authenticate CI.** Both CI configurations already
  support this and do nothing when the variable is unset:
  - GitLab: create a GitHub personal access token with read-only access
    to pdmbomgen and add it as a masked, protected CI/CD variable named
    `PDMBOMGEN_TOKEN` (**Settings → CI/CD → Variables**).
  - GitHub: add the same token as a repository secret named
    `PDMBOMGEN_PAT` (**Settings → Secrets and variables → Actions**).
  - Rotate the token before it expires, or CI starts failing again with
    the same error.

## 5. Commit and push

```bash
git add -A
git commit -m "Initial vault BOM: <assembly name>"
git remote add origin <your new repository's URL>
git push -u origin main
```

## 6a. Turn on GitHub Pages

1. Push to a GitHub repository (default branch `main`; if yours differs,
   update `branches: [main]` in `.github/workflows/pages.yml`).
2. Set **Settings → Pages → Build and deployment → Source** to
   **GitHub Actions**.
3. The defaults under **Settings → Actions → General → Workflow
   permissions** work; nothing else to change.
4. Push, or run **Actions → Publish BOM to GitHub Pages → Run workflow**,
   to trigger the first build. The deploy job prints the live URL
   (`https://<user>.github.io/<repo>/`).

## 6b. Turn on GitLab Pages

1. Push to a GitLab repository. `.gitlab-ci.yml` at the root is picked up
   automatically.
2. Confirm shared or project runners are enabled (**Settings → CI/CD →
   Runners**); gitlab.com's shared runners work out of the box.
3. Push to trigger the `pages` job; **Deploy → Pages** shows the live URL
   once it succeeds.
4. Set up the weekly rebuild — GitLab schedules live outside the YAML:
   **Build → Pipeline schedules → New schedule**, for example weekly,
   targeting the default branch. The schedule is what lets upstream
   pdmbomgen fixes reach this repository's published site even when
   nobody edits the CSV. (GitHub's equivalent `schedule:` trigger is
   already in `.github/workflows/pages.yml` — no extra step there.)

## 6c. Optional features

Both CI configurations preset these environment toggles:

- `BUILD_DASHBOARD=1` (default here) publishes the budget dashboard and
  workbook. Assign specs with a committed `File,Spec` table
  (`[budget].specs_file` in `bomgen.toml` — no PDM change needed) or map
  a spec column with `[columns].specs`; otherwise every part reports as
  unassigned. Spec-level dollars come from a `Spec,WAG,ROM,Quote` table
  (`[budget].costs_file`). To keep the cost model in its own repository
  instead, see `template-budget-repo/` in the pdmbomgen repository.
- `BUILD_HISTORY=1` (default here) rebuilds every git tag into
  `v/<tag>/` with yellow historical styling and a version dropdown. Push
  a tag (`git tag v1.0 && git push origin v1.0`) to populate it; pushing
  a tag also triggers a republish on both services.

## 6d. Update the machinery later

When the pdmbomgen template gains features, refresh your copy from the
repository root with:

```bash
bash scripts/update_from_template.sh
```

It overwrites machinery only (build scripts, CI configurations,
requirements, this file) and never your payload (`vault/`,
`bomgen.toml`, `README.md`), preserving your `BOM_INPUT` and `BOM_CONFIG`
values. It refuses to run on a dirty tree or outside a vault repository,
stages the changes, and leaves the commit to you. If pdmbomgen is private
and HTTPS authentication fails:
`PDMBOMGEN_REPO=git@github.com:douglase/pdmbomgen bash scripts/update_from_template.sh`

## 6e. Trigger a budget repository on BOM pushes

If a separate budget repository builds its dashboard from this vault
(see `template-budget-repo/` in the pdmbomgen repository), set a CI/CD
variable `BUDGET_REPO_PROJECT` here to that project's full path. The
`trigger_budget_rebuild` job then fires the budget repository's pipeline
on every push to the default branch, so the cost dashboard follows the
BOM immediately instead of waiting for its weekly schedule. The comments
in `.gitlab-ci.yml` cover the requirements and the fallback for older
GitLab versions.

## 7. Verify

Open the published URL: the BOM should render, the **Download Excel**
button should serve the workbook, and the header should show a
"· rev `<hash>`" provenance stamp matching your last commit to the CSV.

## Turn this into a real GitHub template repository

Once you (or your organization) are happy with this starting point, push
it to its own repository and check **Settings → General → Template
repository** there. Future vault repositories can then click **Use this
template** on GitHub instead of copying by hand, and this file becomes
that new repository's own setup walkthrough (steps 2 onward still apply).
