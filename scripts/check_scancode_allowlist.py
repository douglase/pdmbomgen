#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Ed Douglas, University of Arizona and contributors
"""Fail CI if scancode-toolkit detects any license outside our allowlist.

Reads a scancode JSON output file (the `--json-pp` artifact) and walks every
file's `license_detections`. Each detection's `license_expression` is split
into its underlying license keys (SPDX-ish identifiers with AND/OR/WITH
operators removed) and every key is checked against ALLOWED below. Any
unrecognized key fails the script with a non-zero exit code and a report.

This project and every one of its dependencies is MIT (see LICENSE-NOTES.md
for the audit) — this allowlist is intentionally tiny. Any hit outside it
means a new dependency or vendored file needs a license review before merge.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ScanCode license keys we accept in this repository, with rationale.
# Add new entries here (with a comment) when a legitimate detection
# triggers a failure — see LICENSE-NOTES.md for the audit trail.
ALLOWED: dict[str, str] = {
    "mit": "MIT — this project's own code, plus openpyxl, et_xmlfile, and "
           "pytest (all MIT; see LICENSE-NOTES.md).",
}

OPERATORS = {"and", "or", "with"}
_TOKEN_RE = re.compile(r"[\s()]+")


def license_keys(expression: str) -> set[str]:
    return {
        t for t in _TOKEN_RE.split(expression.lower())
        if t and t not in OPERATORS
    }


def find_json(path: Path) -> Path:
    if path.is_file():
        return path
    if path.is_dir():
        for p in path.rglob("*.json"):
            try:
                if json.loads(p.read_text()).get("headers") is not None:
                    return p
            except (json.JSONDecodeError, OSError):
                continue
        raise SystemExit(f"No scancode JSON output found under {path}")
    raise SystemExit(f"Not found: {path}")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_scancode_allowlist.py <path-to-scancode.json-or-dir>",
              file=sys.stderr)
        return 2
    src = find_json(Path(sys.argv[1]))
    data = json.loads(src.read_text())
    bad: list[tuple[str, str, str]] = []
    scanned = 0
    for f in data.get("files", []):
        if f.get("type") != "file":
            continue
        scanned += 1
        for det in (f.get("license_detections") or []):
            expr = det.get("license_expression") or ""
            for key in license_keys(expr):
                if key not in ALLOWED:
                    bad.append((f["path"], expr, key))
    if not bad:
        print(f"OK: scanned {scanned} files; all detected licenses are in "
              f"the allowlist ({len(ALLOWED)} keys).")
        return 0
    print(f"FAIL: {len(bad)} detection(s) outside the allowlist:")
    for path, expr, key in bad:
        print(f"  {path}\n    expression: {expr}\n    unrecognized key: {key!r}")
    print()
    print("If a finding is legitimate, add the key to ALLOWED in "
          "scripts/check_scancode_allowlist.py with a one-line rationale, "
          "and record it in LICENSE-NOTES.md.")
    print("If a finding is from generated / vendored content that shouldn't"
          " be scanned, add an --ignore pattern to .github/workflows/scancode.yml.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
