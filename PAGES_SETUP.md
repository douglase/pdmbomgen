# Publish the BOM to GitHub Pages or GitLab Pages
_Step-by-step setup so your team always has the current BOM — and its Download Excel button — one link away._

> [!Important]
> Both pipelines publish the example BOM until you point `BOM_INPUT` and `BOM_CONFIG`
> at your own committed export.

## How publishing works
_All outputs build into one directory and deploy together._

At build time, CI generates all the outputs into one directory and
deploys them together:

```
_site/  (GitHub)  or  public/  (GitLab)
├── index.html                   # the interactive BOM page
└── <input-stem>_BOM.xlsx        # the Excel BOM, linked by the button
```

The download button is a plain relative link to the file next to the
page, so the same page works on GitHub Pages, GitLab Pages, a file share,
or opened straight from disk, with no host-specific code. The shared
build step is `scripts/build_pages.sh`; both CI configurations call it.

If you host the workbook somewhere else, generate the page with
`--xlsx-url <URL>` to point the button there. If bomgen writes a page
with no known workbook location, the button removes itself.

Both pipelines run the test suite before building, and both publish the
example BOM (`examples/NCC-1701_pdmout.csv`) by default. **Edit
`BOM_INPUT` and `BOM_CONFIG` in the CI file to publish your real BOM.**
The input CSV or XML must be committed to the repository.

## Set up GitHub Pages
_From push to live URL with the included workflow._

The workflow is `.github/workflows/pages.yml`.

1. Push this repository to GitHub. The workflow runs on the `main`
   branch; if your default branch is named differently, change
   `branches: [main]` in the workflow.
2. Turn on Pages: open the repository on github.com and set
   **Settings → Pages → Build and deployment → Source** to
   **GitHub Actions**. Nothing else on that screen needs configuring —
   the workflow supplies the artifact.
3. Choose what gets published by editing the `env:` block at the top of
   the workflow:
   ```yaml
   env:
     BOM_INPUT: path/to/your_export.csv   # or .xml
     BOM_CONFIG: path/to/your_bomgen.toml
   ```
4. Trigger a build: push to `main`, or run it by hand under
   **Actions → Publish BOM to GitHub Pages → Run workflow**.
5. Find your URL: the deploy job prints it, and it also appears under
   **Settings → Pages**. It has the form
   `https://<user-or-org>.github.io/<repo>/`.
6. Verify that the page loads and the **Download Excel** button serves
   the workbook.

Notes:

- Private repositories need GitHub Pro, Team, or Enterprise for Pages;
  public repositories publish for free.
- The workflow deploys with `actions/deploy-pages` over OIDC, so there's
  no token to create and no `gh-pages` branch; the `permissions:` block
  in the workflow is all the authorization it needs.

## Set up GitLab Pages
_The same build, deployed by GitLab's pages job._

The configuration is `.gitlab-ci.yml`.

1. Push this repository to GitLab — gitlab.com, or a self-managed
   instance where an administrator has enabled Pages. GitLab picks up
   `.gitlab-ci.yml` at the repository root automatically.
2. Check runners: the job uses a Docker image (`python:3.12-slim`), so
   the project needs shared or project runners with the Docker executor.
   On gitlab.com the shared runners work out of the box; confirm they're
   enabled under **Settings → CI/CD → Runners**.
3. Choose what gets published by editing the `variables:` block in
   `.gitlab-ci.yml`, or override it without a commit under
   **Settings → CI/CD → Variables**:
   ```yaml
   variables:
     BOM_INPUT: path/to/your_export.csv   # or .xml
     BOM_CONFIG: path/to/your_bomgen.toml
   ```
4. Trigger a build: push to the default branch (the `rules:` clause
   restricts publishing to it). Watch the `pages` job under
   **Build → Pipelines**; GitLab deploys the `public/` artifact
   automatically.
5. Find your URL under **Deploy → Pages**. It typically has the form
   `https://<user-or-group>.gitlab.io/<project>/`. On the same screen you
   can turn off **Use unique domain** if you prefer the short URL.
6. Verify that the page loads and the **Download Excel** button serves
   the workbook.

Notes:

- If the project is private, Pages access follows project membership by
  default (**Deploy → Pages → Access control**). Think before making the
  site public — BOMs can be export-controlled.
- On self-managed GitLab, an administrator must have configured Pages
  (`pages_external_url` in `gitlab.rb`); everything else is identical.

## Optional site features
_Environment toggles for the dashboard and historical versions._

`scripts/build_pages.sh` honors two environment toggles, set in the CI
configuration's `env:` or `variables:` block. Both are on for this
repository's demo.

- **`BUILD_DASHBOARD=1`** also publishes the budget dashboard
  (`dashboard.html`) and the budget workbook next to the BOM page. Spec
  assignments come from a committed specs table (`[budget].specs_file`)
  or a spec-reference column mapped with `[columns].specs`; dollars come
  from a committed costs table (`[budget].costs_file`). Without either
  specs source, every part reports as unassigned (warning V10). See
  [`BUDGET_GUIDE.md`](BUDGET_GUIDE.md) for the workflow, and
  `template-budget-repo/README.md` for keeping the cost model in its own
  repository.
- **`BUILD_HISTORY=1`** rebuilds every git tag on every run with the
  current generator into `v/<tag>/`, with yellow historical styling,
  per-tag change highlighting against the previous tag, and a version
  dropdown on every page. It needs full history and tags in the checkout
  (`fetch-depth: 0` / `GIT_DEPTH: "0"`, already set) and at least one
  pushed git tag — no tags, no dropdown. Pushing a tag also triggers a
  republish on both services.

The build also stamps every output with a build-provenance record — the
source path linked at the build commit, the repository, branch, and
commit, and the tool versions — computed automatically from the CI
environment. There's nothing to configure.

## Publish more than one BOM
_One call to bomgen per assembly, plus a hand-written index page._

`scripts/build_pages.sh` writes one `index.html`. For several assemblies,
call bomgen once per input inside the build step, give each an explicit
`--html` and `--xlsx` filename in the same output directory, and add a
hand-written `index.html` that links them. The download buttons keep
working because each page still sits next to its own workbook.
