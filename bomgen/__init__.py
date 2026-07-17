#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 E Douglas, University of Arizona and contributors
"""bomgen — SolidWorks PDM Professional CSV BOM -> human-readable Excel + HTML.

See BOMGEN_DESIGN.md. Single-module by design; deps: openpyxl (+ stdlib
tomllib). Installable (pyproject.toml at repo root) so downstream "vault"
repos can `pip install` it straight from this repo instead of vendoring
the file — see template-repo/ for the pattern (design decision D7).
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover (py<3.11)
    tomllib = None

__version__ = "0.1.0"

# --------------------------------------------------------------------------- config

DEFAULT_CONFIG = {
    "project": {
        "title_line": "BOM DRAFT",
        "project_box": "PROJECT NAME AND TITLE BOX",
        "system_name": "",
        "assembly_number": "TOP-LEVEL-00",
        "assembly_name": "Top Level Assembly",
        "assembly_description": "",
        "contact_name": "",
        "contact_info": "",
    },
    "columns": {
        "level": "Level",
        "qty": "Qty",
        "number": "Number",
        "name": "Name",
        "config": "Config",
        "rev": "Rev",
        "description": "Description",
        "found_in": "Found In",
        "cots": "COTS",
        "material": "Material",
        "passthrough": [],
    },
    "rules": {
        "part_number_pattern": r"^([A-Za-z]+-[A-Za-z]{2}\d+)",
        "dash_source": "rev",  # reserved for O1
        "min_marker_columns": 5,
        "state_from_found_in": True,
    },
    "output": {"excel_font": "Aptos Narrow"},
    "links": {
        # URL template for linking each filename to a PDM web viewer.
        # "{file}" is replaced with the (URL-encoded) SolidWorks filename,
        # e.g. NCC-FA001.SLDASM. Empty -> filenames are not linked.
        "file_url_template": "",
    },
    "materials": {
        # Enrich rows with properties from a committed materials-database
        # export (the raw /export/raw-json dump: a JSON array of material
        # documents). Local file only — bomgen never touches the network.
        "enabled": False,
        "cache_file": "",              # path to the raw-json dump
        "properties": [],              # DB property keys to show as columns
        "show_units": True,            # "2700 kg/m3" vs bare "2700"
        "labels": {},                  # property_key -> column header override
    },
}


def load_config(path: Path | None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    candidate = path or Path("bomgen.toml")
    if candidate.exists():
        if tomllib is None:
            sys.exit("bomgen: python >=3.11 required for TOML config")
        with open(candidate, "rb") as f:
            user = tomllib.load(f)
        for section, vals in user.items():
            cfg.setdefault(section, {}).update(vals)
        cfg["_config_path"] = str(candidate)
    elif path is not None:
        sys.exit(f"bomgen: config not found: {path}")
    return cfg


# --------------------------------------------------------------------------- model

@dataclass
class BomNode:
    path: str
    depth: int
    qty: int
    filename: str
    raw: dict
    parent: "BomNode | None" = None
    children: list = field(default_factory=list)
    qty_total: int = 1
    part_number: str = ""
    display_name: str = ""
    is_assembly: bool = False
    cots: str = ""
    state: str = ""
    file_url: str = ""
    material_props: dict = field(default_factory=dict)


class ValidationError(Exception):
    pass


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    last_err = None
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            with open(path, encoding=enc, newline="") as f:
                rows = list(csv.DictReader(f))
            if not rows:
                sys.exit(f"bomgen: no data rows in {path}")
            return list(rows[0].keys()), rows
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
    sys.exit(f"bomgen: cannot decode {path}: {last_err}")


def read_xml(path: Path, cfg: dict, warnings: list[str]) -> tuple[list[str], list[dict]]:
    """Ingest a PDM Professional XML export (export-rule / ERP channel).

    Schema-tolerant (see design §2.5 / open item O2): PDM XML wraps data in
    <transactions><transaction><document><configuration><attribute name=.. value=../>.
    Hierarchy may arrive as (a) nested <document> elements under <references>,
    or (b) a dotted-level attribute matching columns.level. Output is
    normalized to CSV-shaped row dicts so build_tree() is shared unchanged.
    """
    import xml.etree.ElementTree as ET  # trusted-vault input; see README note
    col = cfg["columns"]
    try:
        xroot = ET.parse(path).getroot()
    except ET.ParseError as e:
        sys.exit(f"bomgen: XML parse error in {path}: {e}")

    def attrs_of(doc) -> dict:
        d = {}
        for conf in doc.findall("configuration"):
            if conf.get("name") and col["config"] not in d:
                d[col["config"]] = conf.get("name")
            for a in conf.findall("attribute"):
                d[a.get("name", "")] = a.get("value", "")
        # document-level id doubles as filename/number when no explicit attr
        d.setdefault(col["number"], doc.get("id", ""))
        return d

    rows: list[dict] = []
    transactions = xroot.findall(".//transaction") or [xroot]
    top_docs = [d for t in transactions for d in t.findall("document")]
    nested = any(d.find(".//references/document") is not None for d in top_docs)

    if nested:
        counters: dict[str, int] = {}

        def walk(doc, parent_path: str):
            counters[parent_path] = counters.get(parent_path, 0) + 1
            p = (f"{parent_path}.{counters[parent_path]}"
                 if parent_path else str(counters[parent_path]))
            row = attrs_of(doc)
            row[col["level"]] = p
            row.setdefault(col["qty"], doc.get("quantity", "1"))
            rows.append(row)
            refs = doc.find("references")
            if refs is not None:
                for child in refs.findall("document"):
                    # per-reference quantity may sit on the child element
                    walk(child, p)

        for d in top_docs:
            walk(d, "")
        warnings.append("XML: hierarchy from nested <references>; item numbers "
                        "synthesized in document order (O2: verify vs vault export)")
    else:
        for d in top_docs:
            row = attrs_of(d)
            row.setdefault(col["qty"], d.get("quantity", "1"))
            rows.append(row)
        if rows and col["level"] not in rows[0]:
            for i, r in enumerate(rows, 1):
                r[col["level"]] = str(i)
            warnings.append("XML: no level attribute found; treating as flat "
                            "single-level BOM (O2)")

    if not rows:
        sys.exit(f"bomgen: no <document> elements found in {path}")
    header = sorted({k for r in rows for k in r})
    return header, rows


# unresolved SolidWorks property expression, e.g. 'SW-Mass@.SLDPRT': the
# data-card variable is linked to a model property but the evaluated value
# was never cached (file not rebuilt/saved) — the cell is not a number.
SW_PROP_RE = re.compile(r"^SW-\w+@")


def scan_unresolved_props(rows: list[dict], warnings: list[str]) -> None:
    """V7: flag cells that export the raw SW property expression instead of
    its evaluated value. Grouped per column so the banner stays short."""
    hits: dict[str, tuple[int, str]] = {}
    for r in rows:
        for k, v in r.items():
            v = (v or "").strip() if isinstance(v, str) else ""
            if SW_PROP_RE.match(v):
                n, ex = hits.get(k, (0, v))
                hits[k] = (n + 1, ex)
    for k, (n, ex) in sorted(hits.items()):
        warnings.append(
            f"V7: column '{k}': {n} row(s) hold an unresolved SolidWorks "
            f"property expression (e.g. '{ex}'), not a value — rebuild and "
            "save those files in CAD so PDM exports the evaluated number")


def build_tree(header: list[str], rows: list[dict], cfg: dict,
               warnings: list[str]) -> BomNode:
    col = cfg["columns"]
    errors: list[str] = []
    scan_unresolved_props(rows, warnings)

    # V5 required columns
    for key in ("level", "qty", "number"):
        if col[key] not in header:
            errors.append(f"V5: required column '{col[key]}' missing from input")
    if col["cots"] not in header:
        warnings.append(
            f"V5: COTS column '{col['cots']}' not in input; COTS will be blank "
            "(per design D1 — add the variable in PDM or edit the CSV)")
    if errors:
        raise ValidationError("\n".join(errors))

    p = cfg["project"]
    root = BomNode(path="0", depth=0, qty=1, filename="", raw={},
                   is_assembly=True)
    root.part_number = p["assembly_number"]
    root.display_name = p["assembly_name"]
    root.raw = {"Description": p["assembly_description"]}
    index: dict[str, BomNode] = {"0": root}

    prev_depth = 0
    for i, row in enumerate(rows, start=2):  # 1-based incl. header
        path = (row.get(col["level"]) or "").strip()
        if not path:
            warnings.append(f"row {i}: empty Level; row skipped")
            continue
        if path in index:
            # V2/R1: Excel round-trips float-mangle dotted levels ("2.10"->"2.1").
            # Repair iff appending zeros to the last segment yields exactly the
            # next expected sibling number under the same parent.
            repaired = None
            head, _, last = path.rpartition(".")
            pp = head or "0"
            if head and pp in index and last.isdigit():
                expected = len(index[pp].children) + 1
                cand = last
                while len(cand) < 6:
                    cand += "0"
                    if int(cand) == expected:
                        repaired = f"{head}.{cand}"
                        break
                    if int(cand) > expected:
                        break
            if repaired and repaired not in index:
                warnings.append(
                    f"R1: row {i}: duplicate path '{path}' reinterpreted as "
                    f"'{repaired}' (Excel float-mangling; export direct from PDM to avoid)")
                path = repaired
            else:
                errors.append(f"V2: duplicate path '{path}' at row {i}")
                continue
        depth = path.count(".") + 1
        raw_number = row.get(col["number"]) or ""
        filename = raw_number.strip()

        # V3 indent cross-check
        lead = len(raw_number) - len(raw_number.lstrip(" "))
        if raw_number and lead and lead // 2 != depth - 1:
            warnings.append(
                f"V3: row {i} ('{path}'): indent {lead} spaces disagrees with depth {depth}")
        # V6 depth jump
        if depth > prev_depth + 1:
            warnings.append(f"V6: row {i} ('{path}'): depth jumps {prev_depth}->{depth}")
        prev_depth = depth

        # V4 qty
        qty_raw = (row.get(col["qty"]) or "").strip()
        try:
            qty = int(float(qty_raw))
            if qty <= 0:
                raise ValueError
        except ValueError:
            warnings.append(f"V4: row {i} ('{path}'): qty '{qty_raw}' invalid; using 1")
            qty = 1

        parent_path = path.rsplit(".", 1)[0] if "." in path else "0"
        parent = index.get(parent_path)
        if parent is None:
            errors.append(f"V1: row {i} ('{path}'): parent '{parent_path}' not found")
            continue

        node = BomNode(path=path, depth=depth, qty=qty, filename=filename,
                       raw=row, parent=parent)
        parent.children.append(node)
        index[path] = node

    if errors:
        raise ValidationError("\n".join(errors))
    return root


def derive(root: BomNode, cfg: dict) -> None:
    col, rules, proj = cfg["columns"], cfg["rules"], cfg["project"]
    pn_re = re.compile(rules["part_number_pattern"])
    url_tmpl = cfg.get("links", {}).get("file_url_template", "")

    def visit(n: BomNode):
        if n.parent is not None:
            n.qty_total = n.qty * n.parent.qty_total
            stem = re.sub(r"\.(sldasm|sldprt|slddrw)$", "", n.filename, flags=re.I)
            n.is_assembly = bool(n.children) or n.filename.lower().endswith(".sldasm")
            m = pn_re.match(stem)
            if m:
                rev = (n.raw.get(col["rev"]) or "").strip()
                dash = rev.zfill(2) if rev.isdigit() else (rev or "00")  # O1
                n.part_number = f"{m.group(1)}-{dash}"
            else:
                n.part_number = stem
            name = (n.raw.get(col["name"]) or "").strip()
            desc = (n.raw.get(col["description"]) or "").strip()
            base = name or desc or stem.replace("_", " ")
            n.display_name = f"{base} ({n.filename})" if n.filename else base
            # PDM viewer link: substitute the (URL-encoded) filename into the
            # configured template; filename already carries .SLDASM/.SLDPRT.
            if url_tmpl and n.filename:
                n.file_url = url_tmpl.replace("{file}", quote(n.filename, safe=""))
            n.cots = (n.raw.get(col["cots"]) or "").strip()
            if rules["state_from_found_in"]:
                fi = (n.raw.get(col["found_in"]) or "").replace("/", "\\")
                parts = [s for s in fi.split("\\") if s]
                n.state = "\\".join(parts[-2:]) if parts else ""
        for c in n.children:
            visit(c)

    visit(root)


def preorder(root: BomNode) -> list[BomNode]:
    out: list[BomNode] = []

    def walk(n: BomNode):
        out.append(n)
        for c in n.children:
            walk(c)

    walk(root)
    return out


# --------------------------------------------------------------------------- materials

def material_cache_key(name: str) -> str:
    """Normalize a material name for matching (whitespace-collapsed, casefold).

    The shared contract between a materials-database export and this reader:
    a BOM row's Material text matches a DB record iff their keys are equal.
    """
    return re.sub(r"\s+", " ", (name or "").strip()).casefold()


def _material_index(docs: list) -> dict[str, dict]:
    """Index a raw materials-database export (the /export/raw-json dump: a
    list of material documents) by normalized name, each synonym aliased to
    the same Properties map. Later duplicates lose to earlier ones."""
    index: dict[str, dict] = {}
    for d in docs:
        if not isinstance(d, dict) or d.get("is_deleted"):
            continue
        name = d.get("Material")
        if not name:
            continue
        props = d.get("Properties") if isinstance(d.get("Properties"), dict) else {}
        for alias in [name, *(d.get("Material_Synonyms") or [])]:
            key = material_cache_key(alias)
            if key and key not in index:
                index[key] = props
    return index


def enrich_materials(root: BomNode, cfg: dict, warnings: list[str]) -> None:
    """Populate each node's material_props from a committed materials-database
    export (config `[materials]`). Local-file only; no network. Purely
    additive and a no-op unless `[materials].enabled`. Cache miss = blank
    properties + a grouped warning, never an abort (cf. COTS / D1)."""
    mat = cfg.get("materials", {})
    if not mat.get("enabled"):
        return
    wanted = list(mat.get("properties", []))
    show_units = mat.get("show_units", True)
    col = cfg["columns"]
    cache_file = mat.get("cache_file", "")
    path = Path(cache_file) if cache_file else None

    index: dict[str, dict] = {}
    if path is None or not path.exists():
        warnings.append(
            f"V8: materials enrichment enabled but cache file "
            f"'{cache_file}' not found; material properties left blank")
    else:
        try:
            docs = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(docs, dict):  # tolerate {"materials": [...]} wrappers
                docs = docs.get("materials") or docs.get("data") or [docs]
            index = _material_index(docs)
        except (json.JSONDecodeError, OSError) as e:
            warnings.append(
                f"V8: materials cache '{path}' unreadable ({e}); "
                "material properties left blank")

    misses: dict[str, int] = {}
    for n in preorder(root):
        if n.parent is None:
            continue
        raw_name = (n.raw.get(col["material"]) or "").strip()
        if not raw_name:
            continue
        entry = index.get(material_cache_key(raw_name)) if index else None
        if entry is None:
            n.material_props = {p: "" for p in wanted}
            if index:  # only a "miss" if we actually have a database to miss in
                misses[raw_name] = misses.get(raw_name, 0) + 1
            continue
        rendered = {}
        for p in wanted:
            prop = entry.get(p)
            if isinstance(prop, dict) and prop.get("value") is not None:
                unit = prop.get("unit") or ""
                rendered[p] = (f"{prop['value']} {unit}".strip()
                               if show_units and unit else str(prop["value"]))
            else:
                rendered[p] = ""
        n.material_props = rendered

    if misses:
        total = sum(misses.values())
        examples = ", ".join(sorted(misses)[:3])
        warnings.append(
            f"V9: {total} row(s) reference {len(misses)} material(s) not found "
            f"in the materials database (e.g. {examples}); properties left blank "
            "— re-export the materials JSON or check the Material names")


# --------------------------------------------------------------------------- excel

BANNER_MAX = 8  # warnings shown in the data-quality banner before "+N more"


def banner_lines(warnings: list[str]) -> list[str]:
    shown = warnings[:BANNER_MAX]
    if len(warnings) > BANNER_MAX:
        shown.append(f"…and {len(warnings) - BANNER_MAX} more (see generator stderr)")
    return shown


def write_excel(root: BomNode, cfg: dict, out: Path,
                warnings: list[str] | None = None, source_rev: str = "") -> None:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    proj, colcfg, rules = cfg["project"], cfg["columns"], cfg["rules"]
    fontname = cfg["output"]["excel_font"]
    nodes = preorder(root)
    max_depth = max(n.depth for n in nodes)
    n_mark = max(rules["min_marker_columns"], max_depth)
    passthrough = list(colcfg.get("passthrough", []))
    matcfg = cfg.get("materials", {})
    mat_props = list(matcfg.get("properties", [])) if matcfg.get("enabled") else []
    mat_headers = [matcfg.get("labels", {}).get(p, p.replace("_", " "))
                   for p in mat_props]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOM"
    ws.sheet_properties.outlinePr.summaryBelow = False

    F = lambda size, bold=False: Font(name=fontname, size=size, bold=bold)
    medium_bottom = Border(bottom=Side(style="medium"))

    first = 2  # column B, matching template
    def L(idx):  # 0-based logical index -> letter
        return get_column_letter(first + idx)

    headers = ["Level", "Abbreviated Part Number", "Part Name", "Description",
               "COTS", "Qty (Assembly)", "Qty (Total)"] + passthrough + mat_headers
    total_cols = n_mark + len(headers)

    # ---- data-quality banner (rows 2-5 are blank in the template, so the
    # banner never shifts the title block / header rows the team knows)
    if warnings:
        lines = ["⚠ DATA QUALITY WARNINGS — verify before use:"] + [
            f"• {w}" for w in banner_lines(warnings)]
        yellow = PatternFill("solid", fgColor="FFF3C4")
        edge = Side(style="thin", color="B98900")
        box = Border(left=edge, right=edge, top=edge, bottom=edge)
        for row in range(2, 6):
            for i in range(total_cols):
                cell = ws[f"{L(i)}{row}"]
                cell.fill, cell.border = yellow, box
        c = ws["B2"]
        c.value = "\n".join(lines)
        c.font = Font(name=fontname, size=11, bold=False, color="7A4E00")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(f"B2:{L(total_cols - 1)}5")
        est = sum(len(l) // 160 + 1 for l in lines)  # rough wrap estimate
        for row in range(2, 6):
            ws.row_dimensions[row].height = max(15, est * 15 / 4 + 2)

    # ---- title block
    def put(row, text, size=14, bold=True):
        c = ws[f"B{row}"]
        c.value, c.font = text, F(size, bold)
        ws.merge_cells(f"B{row}:{L(n_mark)}{row}")

    put(6, "Bill of Materials (BOM)", 18)
    put(7, proj["title_line"])
    if source_rev:
        # row 8 is a blank spacer in the template; safe to use for
        # provenance without disturbing the documented title-block rows
        put(8, f"Source revision: {source_rev}", size=10, bold=False)
    put(9, proj["project_box"])
    put(10, f"System Name: {proj['system_name']}")
    put(11, f"Assembly Name {proj['assembly_number']}")
    put(12, proj["contact_name"] or "Contact Name")
    put(13, proj["contact_info"] or "Contact Info")

    # ---- header band (row 16) + header row (17)
    b = ws["B16"]
    b.value, b.font, b.border = "Assembly Level", F(18, True), medium_bottom
    ws.merge_cells(f"B16:{L(n_mark - 1)}16")
    qa_idx, qt_idx = n_mark + 5, n_mark + 6
    q = ws[f"{L(qa_idx)}16"]
    q.value, q.font, q.border = "Quantity Required", F(14, True), medium_bottom
    ws.merge_cells(f"{L(qa_idx)}16:{L(qt_idx)}16")
    for i in range(total_cols):
        ws[f"{L(i)}16"].border = medium_bottom

    for i in range(n_mark):
        c = ws[f"{L(i)}17"]
        c.value, c.font, c.border = str(i + 1), F(14, True), medium_bottom
        c.alignment = Alignment(horizontal="center")
    for j, h in enumerate(headers):
        c = ws[f"{L(n_mark + j)}17"]
        c.value, c.font, c.border = h, F(14, True), medium_bottom

    # ---- data rows
    r = 18
    for n in nodes:
        desc = (n.raw.get(colcfg["description"]) or "").strip()
        if n.depth == 0:
            for i in range(n_mark):  # root: X across the band (per template example)
                ws[f"{L(i)}{r}"] = "X"
        else:
            ws[f"{L(n.depth - 1)}{r}"] = "X"
        vals = [n.depth, n.part_number, n.display_name, desc, n.cots,
                n.qty, n.qty_total] + [
                    (n.raw.get(p) or "").strip() for p in passthrough] + [
                    n.material_props.get(p, "") for p in mat_props]
        for j, v in enumerate(vals):
            c = ws[f"{L(n_mark + j)}{r}"]
            c.value = v
            c.font = F(14 if n.depth == 0 else 11, n.is_assembly)
        if n.file_url:
            # Part Name is logical column index 2; make the whole cell a
            # hyperlink to the PDM viewer (xlsx can't link a substring).
            c = ws[f"{L(n_mark + 2)}{r}"]
            c.hyperlink = n.file_url
            c.font = Font(name=fontname, size=(14 if n.depth == 0 else 11),
                          bold=n.is_assembly, color="0563C1", underline="single")
        for i in range(n_mark):
            ws[f"{L(i)}{r}"].font = F(14 if n.depth == 0 else 11, True)
            ws[f"{L(i)}{r}"].alignment = Alignment(horizontal="center")
        if n.depth > 0:
            ws.row_dimensions[r].outline_level = min(n.depth, 7)
        r += 1

    # ---- widths, freeze, autofilter
    for i in range(n_mark):
        ws.column_dimensions[L(i)].width = 5.3
    for j, w in enumerate([9, 26, 62, 55, 8, 15, 12]
                          + [14] * len(passthrough) + [14] * len(mat_props)):
        ws.column_dimensions[L(n_mark + j)].width = w
    ws.freeze_panes = f"B18"
    ws.auto_filter.ref = f"{L(n_mark)}17:{L(total_cols - 1)}{r - 1}"

    wb.save(out)


# --------------------------------------------------------------------------- html

def write_html(root: BomNode, cfg: dict, src_name: str, out: Path,
               warnings: list[str], xlsx_href: str = "",
               source_rev: str = "") -> None:
    """xlsx_href: URL/relative path to the sibling .xlsx (empty -> the
    download button is removed client-side). When publishing to GitHub or
    GitLab Pages the .xlsx is deployed next to the HTML, so a bare filename
    works on both (see PAGES_SETUP.md).

    source_rev: opaque provenance string (e.g. the input CSV's last git
    commit hash in the repo that owns it) rendered next to the source
    filename. bomgen itself has no git dependency — callers compute this
    (see template-repo/scripts/build_pages.sh) and pass it in verbatim."""
    proj = cfg["project"]
    passthrough = list(cfg["columns"].get("passthrough", []))
    matcfg = cfg.get("materials", {})
    mat_props = list(matcfg.get("properties", [])) if matcfg.get("enabled") else []
    mat_headers = [matcfg.get("labels", {}).get(p, p.replace("_", " "))
                   for p in mat_props]
    extra_cols = passthrough + mat_headers
    nodes = preorder(root)
    data = [{
        "path": n.path, "depth": n.depth, "pn": n.part_number,
        "name": n.display_name,
        "desc": (n.raw.get(cfg["columns"]["description"]) or "").strip(),
        "cots": n.cots, "qty": n.qty, "qtyTotal": n.qty_total,
        "state": n.state, "asm": n.is_assembly,
        "file": n.filename, "fileUrl": n.file_url,
        "extra": [(n.raw.get(p) or "").strip() for p in passthrough]
                 + [n.material_props.get(p, "") for p in mat_props],
    } for n in nodes]

    if warnings:
        items = "".join(f"<li>{html.escape(w)}</li>"
                        for w in banner_lines(warnings))
        warnbox = ('<div id="warnbox"><strong>&#9888; Data quality warnings '
                   f"— verify before use:</strong><ul>{items}</ul></div>")
    else:
        warnbox = ""

    tmpl = Path(__file__).with_name("template.html").read_text(encoding="utf-8")
    page = (tmpl
            .replace("/*__DATA__*/", json.dumps(
                {"rows": data, "extraCols": extra_cols}, ensure_ascii=False))
            .replace("__TITLE__", html.escape(proj["title_line"]))
            .replace("__SYSTEM__", html.escape(proj["system_name"]))
            .replace("__ASSY__", html.escape(proj["assembly_number"]))
            .replace("__CONTACT__", html.escape(
                " · ".join(x for x in (proj["contact_name"], proj["contact_info"]) if x)))
            .replace("__GENERATED__", datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__SOURCE__", html.escape(src_name))
            .replace("__SOURCE_REV__",
                     f" · rev <code>{html.escape(source_rev)}</code>" if source_rev else "")
            .replace("__XLSX_HREF__", html.escape(xlsx_href, quote=True))
            .replace("__WARNBOX__", warnbox))
    out.write_text(page, encoding="utf-8")


# --------------------------------------------------------------------------- cli

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bomgen", description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("-c", "--config", type=Path)
    ap.add_argument("--xlsx", type=Path, nargs="?", const=True, default=None)
    ap.add_argument("--html", type=Path, nargs="?", const=True, default=None)
    ap.add_argument("--both", action="store_true")
    ap.add_argument("--xlsx-url", default=None, metavar="URL",
                    help="href for the HTML download button (default: the "
                         ".xlsx filename when both outputs land in the same "
                         "directory, as on a Pages deploy; omitted otherwise)")
    ap.add_argument("--source-rev", default="", metavar="REV",
                    help="opaque provenance string embedded in both reports "
                         "(e.g. the input file's last git commit hash: "
                         "$(git log -1 --format=%%h -- INPUT)); blank if omitted")
    ap.add_argument("--materials-cache", type=Path, default=None, metavar="PATH",
                    help="raw materials-database export (/export/raw-json) to "
                         "enrich rows from; overrides [materials].cache_file and "
                         "implies enabled=true for this run")
    ap.add_argument("-o", "--outdir", type=Path, default=Path("."))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    cfg = load_config(a.config)
    warnings: list[str] = []
    if a.input.suffix.lower() == ".xml":
        header, rows = read_xml(a.input, cfg, warnings)
    else:
        header, rows = read_csv(a.input)
    try:
        root = build_tree(header, rows, cfg, warnings)
    except ValidationError as e:
        print(f"bomgen: validation errors:\n{e}", file=sys.stderr)
        return 1
    derive(root, cfg)
    if a.materials_cache is not None:
        cfg["materials"]["enabled"] = True
        cfg["materials"]["cache_file"] = str(a.materials_cache)
    enrich_materials(root, cfg, warnings)

    if not a.quiet:
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)

    a.outdir.mkdir(parents=True, exist_ok=True)
    stem = a.input.stem
    did = False
    xlsx_out: Path | None = None
    if a.xlsx or a.both:
        xlsx_out = a.xlsx if isinstance(a.xlsx, Path) else a.outdir / f"{stem}_BOM.xlsx"
        write_excel(root, cfg, xlsx_out, warnings, source_rev=a.source_rev)
        did = True
        if not a.quiet:
            print(f"wrote {xlsx_out}")
    if a.html or a.both:
        p = a.html if isinstance(a.html, Path) else a.outdir / f"{stem}_BOM.html"
        href = a.xlsx_url
        if href is None:
            # sibling .xlsx from the same run -> relative link survives any
            # hosting root (GitHub Pages, GitLab Pages, file://, S3, ...)
            same_dir = (xlsx_out is not None
                        and xlsx_out.resolve().parent == p.resolve().parent)
            href = xlsx_out.name if same_dir else ""
        write_html(root, cfg, a.input.name, p, warnings, xlsx_href=href,
                  source_rev=a.source_rev)
        did = True
        if not a.quiet:
            print(f"wrote {p}")
    if not did:
        print("bomgen: nothing to do (use --xlsx, --html, or --both)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
