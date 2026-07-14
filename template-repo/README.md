# vault-bom-template

A minimal starting point for a repo that owns **one PDM vault's BOM
export**: the CSV/XML lives here under version control, [pdmbomgen]
compiles it to Excel + HTML on every push, and the compiled report is
published to GitHub Pages or GitLab Pages stamped with the git commit of
the export it reflects.

[pdmbomgen]: https://github.com/douglase/pdmbomgen

This repo is deliberately thin — it holds *your* data and *your* CI
config, not the conversion logic. `requirements.txt` pulls pdmbomgen
straight from its `main` branch, so bug fixes and features land here
automatically on the next build, with nothing to update by hand.

**New repo? Start with [`SETUP.md`](SETUP.md).**

## Layout

```
vault/PLACEHOLDER_pdmout.csv   the PDM export — replace with your real one
bomgen.toml                    project title block, column mapping, rules
requirements.txt                pdmbomgen @ git+.../pdmbomgen.git@main
scripts/build_pages.sh          the build step both CI configs call
.github/workflows/pages.yml     GitHub Pages CI
.gitlab-ci.yml                  GitLab Pages CI
```

## How the provenance stamp works

`scripts/build_pages.sh` runs `git log -1 -- vault/your_export.csv` in
*this* repo (not pdmbomgen's) to get the export's last commit, then passes
it to `bomgen --source-rev`. Both the HTML and Excel report show it, so
anyone looking at the published BOM can see exactly which commit — and
therefore which state of the vault — it was generated from.

## How upstream tracking works

Both CI configs reinstall pdmbomgen from `requirements.txt` on every run
— they never cache or vendor it — and a scheduled weekly rebuild (already
configured) reruns the build even if this repo's own CSV hasn't changed.
So a fix merged into pdmbomgen's `main` branch reaches this site within a
week even if nobody touches this repo. See `../BOMGEN_DESIGN.md` §8.1 in
the pdmbomgen repo for the design rationale and the tag-pinning trade-off.

## Local build

```bash
pip install -r requirements.txt
bash scripts/build_pages.sh vault/PLACEHOLDER_pdmout.csv bomgen.toml _site
```

## License

This template folder is provided by [pdmbomgen] under the MIT license (see
`LICENSE-NOTES.md` in the pdmbomgen repo) as a starting point to copy out.
It carries no license header of its own — once you copy it into your own
repo, that repo's data and CI config are yours to license however you
choose; pdmbomgen itself remains a dependency, not vendored code.
