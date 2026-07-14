# License Notes

Background on pdmbomgen's licensing: this project's own license, every
third-party dependency's license, the origin of the bundled example/test
data, and the automated safeguard that keeps future contributions from
silently introducing incompatibly-licensed code.

## 1. This project's license

MIT. See [LICENSE](LICENSE) for the full text. Every substantive source
file carries an `SPDX-License-Identifier: MIT` header.

## 2. Third-party dependencies

| Package | License | Role | How verified |
|---|---|---|---|
| [openpyxl](https://pypi.org/project/openpyxl/) | MIT | Runtime (declared in `pyproject.toml`) | Read the `LICENCE.rst` bundled in the installed distribution directly, not just package metadata |
| [et_xmlfile](https://pypi.org/project/et-xmlfile/) | MIT | Runtime (transitive — a dependency of openpyxl; not declared directly in `pyproject.toml` but present at install time) | Same — read its bundled `LICENCE.rst` |
| [pytest](https://pypi.org/project/pytest/) | MIT | Test-only (`[project.optional-dependencies].test`) | Read the `LICENSE` bundled in the installed distribution directly |

All runtime and test dependencies are MIT, fully compatible with this
project's own MIT license — there is no dependency-license conflict to
manage.

## 3. Original code

No third-party code has been copied or adapted into this project. A
prior-art survey was carried out during design (see `BOMGEN_DESIGN.md` §1
"Prior art surveyed") — two open-source projects, InteractiveHtmlBom and
bomkit, are cited there as sources of *pattern* inspiration (self-contained
HTML packaging, quantity roll-up conventions respectively), explicitly
"not reused directly," with bomgen described as a clean-room
implementation. See that section for the full survey; it isn't repeated
here.

## 4. Example / fixture data

`examples/NCC-1701_pdmout.csv` is a sanitized copy of a real SolidWorks
PDM Professional export. Structure, sparsity, and known defects (including
the Excel float-mangled `2.10` item exercised by the test suite) are
preserved verbatim; identifying part numbers, names, materials, and vault
paths have been replaced with fictional Star Trek–themed values throughout.

`tests/fixtures/sample_export.xml` is fully synthetic — built to match
SOLIDWORKS' documented PDM XML export schema (per its own header comment),
not derived from any real export. It reuses the same fictional part
numbers as the CSV fixture for consistency between test fixtures.

`tests/fixtures/golden_tree.json` is derived test data (a path → quantity
snapshot computed by parsing the fixtures above) with no independent
provenance of its own.

## 5. Fonts / embedded assets

None. `bomgen/template.html` — the only HTML this project ships or
generates — uses system font stacks only (no `@font-face`, no bundled or
CDN-loaded fonts) and inline Unicode glyphs (▾ ▸ ⚠ ⬇) in place of icon
fonts or images. There is nothing vendored anywhere in this repository:
no fonts, images, minified JS/CSS, or `vendor/`/`third_party/` directories.

## 6. Enforced license scanning

Every push and pull request runs a pinned [scancode-toolkit](https://github.com/aboutcode-org/scancode-toolkit)
scan over the tree (`.github/workflows/scancode.yml`). Its JSON report is
checked against an explicit allowlist in
`scripts/check_scancode_allowlist.py`; any detected license key outside
that allowlist fails the build. To accept a new license (e.g. when adding
a dependency), add its key to `ALLOWED` in that script with a one-line
rationale, and record the addition in the dependency table above.
