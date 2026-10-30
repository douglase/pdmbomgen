# Docs
_The Sphinx build that renders this repository's Markdown documentation as a website._

All documentation content lives in the Markdown files at the repository root
(`README.md`, `BUDGET_GUIDE.md`, `PAGES_SETUP.md`, the plans, and `BOMGEN_DESIGN.md`);
this directory only holds the Sphinx machinery that renders them
in the same theme and configuration as the
[UASAL Development Guide](https://uasal.github.io/uasal_development_guide/),
including the "Edit on GitHub" button.
CI builds the site with `--fail-on-warning` plus a link check
and publishes it under `/docs/` on the project's Pages site.

Build locally:

```sh
pip install -r docs/requirements.txt
sphinx-build -M html docs/source docs/build --fail-on-warning
# open docs/build/html/index.html
```
