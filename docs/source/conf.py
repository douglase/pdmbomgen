# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 E Douglas, University of Arizona and contributors
# Configuration file for the Sphinx documentation builder.
# Essentials practiced by the UASAL Development Guide
# (https://uasal.github.io/uasal_development_guide/); see
# https://www.sphinx-doc.org/en/master/usage/configuration.html for the rest.

import re
import shutil
from pathlib import Path

# -- Project information -----------------------------------------------------

project = 'pdmbomgen'
copyright = '2026, E Douglas, University of Arizona and contributors'
author = 'E Douglas and contributors'

# -- Single-source Markdown --------------------------------------------------
# This repository's documentation is Markdown at the repo root (the UASAL
# style keeps repository-level docs in Markdown; rst is for guide pages).
# Rather than forking the content into rst, the build copies the canonical
# .md files into source/_docs/ and renders them with MyST. Each copy gets a
# github_url front-matter key so the theme's "Edit on GitHub" button points
# at the TRUE source file at the repo root, not at the build-time copy.

_REPO = Path(__file__).resolve().parents[2]
_DOCS = [
    'README.md',
    'BUDGET_GUIDE.md',
    'PAGES_SETUP.md',
    'BUDGET_PLAN.md',
    'MATERIALS_DB_PLAN.md',
    'BOMGEN_DESIGN.md',
]
_GITHUB = 'https://github.com/douglase/pdmbomgen'
_LINK = re.compile(r'(\]\()([^)\s]+)(\))')


def _github_link(match):
    # Links between rendered guides stay local; any other repo-relative
    # target (LICENSE, bomgen.toml, examples/..., template-repo/...) is not
    # published in _docs/, so point it at the file or folder on GitHub.
    target = match.group(2)
    path = target.split('#', 1)[0]
    if not path or '://' in path or path.startswith('mailto:') or path in _DOCS:
        return match.group(0)
    kind = 'tree' if (_REPO / path).is_dir() else 'blob'
    return f'{match.group(1)}{_GITHUB}/{kind}/main/{target}{match.group(3)}'


_dest = Path(__file__).resolve().parent / '_docs'
shutil.rmtree(_dest, ignore_errors=True)
_dest.mkdir()
for _name in _DOCS:
    _text = _LINK.sub(_github_link, (_REPO / _name).read_text(encoding='utf-8'))
    _url = f'{_GITHUB}/blob/main/{_name}'
    (_dest / _name).write_text(f'---\ngithub_url: {_url}\n---\n\n' + _text,
                               encoding='utf-8')

# -- General configuration ---------------------------------------------------

extensions = ['myst_parser']  # renders the copied Markdown; index stays rst
myst_heading_anchors = 3      # GitHub-style #section links keep working

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_static_path = []  # images are referenced by path from the source files
html_theme_options = {
    'vcs_pageview_mode': 'blob',  # 'blob' shows the file view, 'edit' the edit view
}

_source_suffix = locals().get('source_suffix', '.rst')

# --- Settings for the "Edit on GitHub" link ---------------------------------

github_user = "douglase"      # GitHub organization or user
github_repo = "pdmbomgen"     # repository name
github_version = "main"       # default branch
conf_py_path = "/docs/source/"  # path from repo root to the directory holding conf.py

html_context = {
    'display_github': True,
    'github_user': github_user,
    'github_repo': github_repo,
    'github_version': github_version,
    'conf_py_path': conf_py_path,
    'source_suffix': _source_suffix,
}

# -- Link checking -----------------------------------------------------------
# Every entry gets a comment saying why it is listed.

linkcheck_allowed_redirects = {
    # Login redirects count as working.
    r'https://github.com/settings/.*': r'https://github.com/login.*',
    # Read the Docs redirects bare project URLs to /en/stable/.
    r'https://openpyxl\.readthedocs\.io/': r'https://openpyxl\.readthedocs\.io/en/stable/',
}

linkcheck_ignore = [
    r'https?://[^/]*example\.edu/.*',   # placeholder hosts in config examples
    r'https?://<.*',                    # <user-or-org>-style URL shapes in prose
    r'https?://escpdm\.as\.arizona\.edu/.*',  # VPN-only PDM web viewer
    r'https?://doi\.org/10\.5555/.*',   # demo DOI in the example costs table
    r'https://img\.shields\.io/.*',     # badge image service rate-limits checkers
    r'https://github\.com/douglase/pdmbomgen/actions.*',  # 403 to unauthenticated link checkers
]

# Sites where anchor checking fails (often a redirect issue).
linkcheck_anchors_ignore_for_url = [r'https://github.com/.*']
