# Publishing the BOM to GitHub Pages or GitLab Pages

The HTML report includes a **⇩ Download Excel (.xlsx)** button. It works by
convention, not magic: at compile (CI) time both outputs are generated into
the same directory —

```
_site/  (GitHub)  or  public/  (GitLab)
├── index.html                   # the interactive BOM (renamed HTML output)
└── <input-stem>_BOM.xlsx        # the Excel BOM, linked by the button
```

— and deployed together, so the button is a plain relative `href` to the
sibling file. That makes the same page work on GitHub Pages, GitLab Pages,
a file share, or `file://` with zero host-specific code. The shared build
step lives in `scripts/build_pages.sh`; both CI configs call it.

If you host the `.xlsx` somewhere else, generate the HTML with
`--xlsx-url <URL>` to point the button there instead. If bomgen writes an
HTML with no known `.xlsx` location, the button removes itself.

Both pipelines run the test suite before building, and both publish the
example BOM (`examples/NCC-1701_pdmout.csv`) by default — **edit
`BOM_INPUT`/`BOM_CONFIG` in the CI file to publish your real BOM** (the
input CSV/XML must be committed to the repo).

---

## GitHub Pages (`.github/workflows/pages.yml`)

1. **Push this repository to GitHub** (default branch `main`; if yours is
   named differently, change `branches: [main]` in
   `.github/workflows/pages.yml`).
2. **Enable Pages via Actions**: on github.com open the repo →
   **Settings → Pages → Build and deployment → Source** and select
   **GitHub Actions**. (Nothing else on that screen needs configuring — the
   workflow supplies the artifact.)
3. **Pick what gets published**: edit the `env:` block at the top of
   `.github/workflows/pages.yml`:
   ```yaml
   env:
     BOM_INPUT: path/to/your_export.csv   # or .xml
     BOM_CONFIG: path/to/your_bomgen.toml
   ```
4. **Trigger a build**: push to `main`, or run it by hand under
   **Actions → Publish BOM to GitHub Pages → Run workflow**
   (`workflow_dispatch` is enabled).
5. **Find your URL**: the deploy job prints it (also shown under
   **Settings → Pages**). It has the form
   `https://<user-or-org>.github.io/<repo>/`.
6. Verify the page loads and the **Download Excel** button serves the
   `.xlsx`.

Notes:
- Private repos need GitHub Pro/Team/Enterprise for Pages; public repos are
  free.
- The workflow uses the OIDC deploy path (`actions/deploy-pages`), so no
  token or `gh-pages` branch is involved; `permissions:` in the workflow is
  all the auth it needs.

## GitLab Pages (`.gitlab-ci.yml`)

1. **Push this repository to GitLab** (gitlab.com or self-managed with Pages
   enabled by the admin). `.gitlab-ci.yml` at the repo root is picked up
   automatically — there is no toggle to flip.
2. **Check runners**: the job uses a Docker image (`python:3.12-slim`), so
   the project needs shared or project runners with the Docker executor —
   on gitlab.com the shared runners work out of the box
   (**Settings → CI/CD → Runners** to confirm they're enabled).
3. **Pick what gets published**: edit the `variables:` block in
   `.gitlab-ci.yml` (or override without a commit under
   **Settings → CI/CD → Variables**):
   ```yaml
   variables:
     BOM_INPUT: path/to/your_export.csv   # or .xml
     BOM_CONFIG: path/to/your_bomgen.toml
   ```
4. **Trigger a build**: push to the default branch (the `rules:` clause
   restricts publishing to it). Watch the `pages` job under **Build →
   Pipelines**; GitLab auto-deploys its `public/` artifact.
5. **Find your URL**: **Deploy → Pages** shows it. Typical form:
   `https://<user-or-group>.gitlab.io/<project>/`. On that same screen you
   can toggle **Use unique domain** off if you want the short URL.
6. Verify the page loads and the **Download Excel** button serves the
   `.xlsx`.

Notes:
- If the project is private, Pages access follows project membership by
  default (**Deploy → Pages → Access control**); make the Pages site public
  there if the BOM may be shared more widely — think before you do, BOMs
  can be export-controlled.
- Self-managed GitLab: an admin must have Pages configured
  (`pages_external_url` in `gitlab.rb`); everything else is identical.

## Optional site features (env toggles)

`scripts/build_pages.sh` honors two environment toggles, set in the CI
config's `env:`/`variables:` block (both are ON for this repo's demo):

- **`BUILD_DASHBOARD=1`** — also publish the spec/RFQ budget dashboard
  (`dashboard.html`) and the budget workbook next to the BOM page. Needs a
  spec-reference column mapped via `[columns].specs` in `bomgen.toml`;
  without one, every part reports as unassigned (warning V10).
- **`BUILD_HISTORY=1`** — rebuild **every git tag** on every run with the
  current generator into `v/<tag>/`, with yellow historical chrome, per-tag
  change highlighting vs the previous tag, and a version dropdown on every
  page (written as per-directory `versions.js`). Needs full history + tags
  in the checkout (`fetch-depth: 0` / `GIT_DEPTH: "0"`, already set) and at
  least one pushed git tag — no tags, no dropdown. Pushing a tag triggers a
  republish on both services (tag trigger in each CI config).

The build also stamps every output with a **build-provenance** record
(source path linked at the build commit, repo/branch/commit, toolchain
versions) computed automatically from the CI environment — nothing to
configure.

## Publishing more than one BOM

`scripts/build_pages.sh` writes one `index.html`. For several assemblies,
call `bomgen.py` once per input inside the build step, giving each an
explicit `--html`/`--xlsx` filename in the same output directory, and add a
hand-written `index.html` linking them — the relative-href button keeps
working because each HTML/xlsx pair still shares a directory.
