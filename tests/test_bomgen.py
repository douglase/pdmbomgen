# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 E Douglas, University of Arizona and contributors
"""Tests for bomgen. Run: python -m pytest tests/ -v"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import bomgen  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
SAMPLE_CSV = REPO / "examples" / "NCC-1701_pdmout.csv"


def parse(path, cfg=None):
    cfg = cfg or bomgen.load_config(None)
    warnings = []
    if path.suffix == ".xml":
        header, rows = bomgen.read_xml(path, cfg, warnings)
    else:
        header, rows = bomgen.read_csv(path)
    root = bomgen.build_tree(header, rows, cfg, warnings)
    bomgen.derive(root, cfg)
    bomgen.enrich_materials(root, cfg, warnings)
    return root, warnings


# ------------------------------------------------------------------ CSV path

def test_csv_tree_shape():
    root, _ = parse(SAMPLE_CSV)
    nodes = bomgen.preorder(root)
    assert len(nodes) == 49  # 48 rows + synthesized root
    assert max(n.depth for n in nodes) == 4
    idx = {n.path: n for n in nodes}
    assert idx["0"].part_number  # synthesized root populated from config


def test_excel_float_mangle_repair():
    root, warnings = parse(SAMPLE_CSV)
    idx = {n.path: n for n in bomgen.preorder(root)}
    assert "2.10" in idx, "duplicate '2.1' should be repaired to '2.10'"
    assert any(w.startswith("R1") for w in warnings)


def test_qty_rollup_multiplies_ancestors():
    root, _ = parse(SAMPLE_CSV)
    idx = {n.path: n for n in bomgen.preorder(root)}
    n = idx["3.1.12.2"]
    assert n.qty == 1 and idx["3.1.12"].qty == 6 and n.qty_total == 6


def test_rollup_invariant_leaf_sums():
    root, _ = parse(SAMPLE_CSV)
    total = sum(n.qty_total for n in bomgen.preorder(root) if not n.children)
    root2, _ = parse(SAMPLE_CSV)
    total2 = sum(n.qty_total for n in bomgen.preorder(root2) if not n.children)
    assert total == total2 > 0


def test_part_number_rev_dash():
    root, _ = parse(SAMPLE_CSV)
    idx = {n.path: n for n in bomgen.preorder(root)}
    assert idx["1.1.1"].part_number == "NCC-FP005-02"  # Rev 2 -> -02 (D3/O1)


def test_golden_paths(tmp_path):
    """Snapshot of (path, qty_total) pairs; update deliberately if rules change."""
    golden_file = FIX / "golden_tree.json"
    root, _ = parse(SAMPLE_CSV)
    actual = {n.path: n.qty_total for n in bomgen.preorder(root)}
    if not golden_file.exists():  # first run generates it
        golden_file.write_text(json.dumps(actual, indent=1, sort_keys=True))
        pytest.skip("golden file created; re-run")
    assert actual == json.loads(golden_file.read_text())


# ------------------------------------------------------------------ XML path

def test_xml_nested_references():
    root, warnings = parse(FIX / "sample_export.xml")
    idx = {n.path: n for n in bomgen.preorder(root)}
    # top doc -> "1"; its two references -> 1.1, 1.2; grandchildren -> 1.1.x
    assert idx["1"].filename == "NCC-FA014.SLDASM"
    assert idx["1.1.2"].qty == 2
    assert idx["1.1.2"].qty_total == 2
    assert idx["1.2"].qty == 4
    assert idx["1.1.2"].cots == "X"          # COTS attr flows through (D1)
    assert idx["1.1.1"].part_number == "NCC-FP005-02"
    assert any("O2" in w for w in warnings)  # verification flag surfaces


# ------------------------------------------------------------------ outputs

def test_outputs_write(tmp_path):
    cfg = bomgen.load_config(None)
    root, warnings = parse(SAMPLE_CSV, cfg)
    x, h = tmp_path / "o.xlsx", tmp_path / "o.html"
    bomgen.write_excel(root, cfg, x)
    bomgen.write_html(root, cfg, "src.csv", h, warnings)
    assert x.stat().st_size > 4000
    page = h.read_text(encoding="utf-8")
    assert "__TITLE__" not in page and '"2.10"' in page

    import openpyxl
    ws = openpyxl.load_workbook(x).active
    assert ws["B16"].value == "Assembly Level"
    row17 = [c.value for c in ws[17] if c.value is not None]
    assert "Qty (Total)" in row17


def test_unresolved_swprop_warning():
    """V7: SW-Mass@.SLDPRT-style cells are flagged, grouped per column."""
    _, warnings = parse(SAMPLE_CSV)
    v7 = [w for w in warnings if w.startswith("V7")]
    assert len(v7) == 1 and "'Mass'" in v7[0] and "SW-Mass@" in v7[0]
    assert "4 row(s)" in v7[0]


def test_warning_banner_in_both_outputs(tmp_path):
    """D6: caught gotchas render in a yellow banner atop Excel and HTML."""
    cfg = bomgen.load_config(None)
    root, warnings = parse(SAMPLE_CSV, cfg)
    assert any(w.startswith("R1") for w in warnings)  # float-mangle caught
    x, h = tmp_path / "o.xlsx", tmp_path / "o.html"
    bomgen.write_excel(root, cfg, x, warnings)
    bomgen.write_html(root, cfg, "src.csv", h, warnings)

    page = h.read_text(encoding="utf-8")
    assert 'id="warnbox"' in page
    assert "SW-Mass@" in page and "R1" in page  # both gotchas surfaced

    import openpyxl
    ws = openpyxl.load_workbook(x).active
    banner = ws["B2"].value
    assert banner and "DATA QUALITY" in banner
    assert "SW-Mass@" in banner and "R1" in banner
    assert ws["B6"].value == "Bill of Materials (BOM)"  # template rows intact


def test_no_banner_on_clean_input(tmp_path):
    """No warnings -> no banner in either output."""
    clean = tmp_path / "clean.csv"
    clean.write_text("Level,Qty,Number,COTS\n"
                     "1,1,NCC-FA002.SLDASM,\n"
                     "1.1,2,NCC-FP001.SLDPRT,X\n", encoding="utf-8")
    cfg = bomgen.load_config(None)
    root, warnings = parse(clean, cfg)
    assert warnings == []
    x, h = tmp_path / "o.xlsx", tmp_path / "o.html"
    bomgen.write_excel(root, cfg, x, warnings)
    bomgen.write_html(root, cfg, "clean.csv", h, warnings)
    assert 'id="warnbox"' not in h.read_text(encoding="utf-8")
    import openpyxl
    assert openpyxl.load_workbook(x).active["B2"].value is None


def test_html_xlsx_download_link(tmp_path):
    """D5: explicit xlsx_href lands in the download button, escaped."""
    cfg = bomgen.load_config(None)
    root, warnings = parse(SAMPLE_CSV, cfg)
    h = tmp_path / "o.html"
    bomgen.write_html(root, cfg, "src.csv", h, warnings, xlsx_href="o.xlsx")
    page = h.read_text(encoding="utf-8")
    assert 'id="dl"' in page and 'href="o.xlsx"' in page
    # no href known -> empty attribute (button removes itself client-side)
    bomgen.write_html(root, cfg, "src.csv", h, warnings)
    assert 'href=""' in h.read_text(encoding="utf-8")


def test_cli_both_links_sibling_xlsx(tmp_path):
    """--both into one directory -> button links the .xlsx by filename,
    the layout scripts/build_pages.sh deploys to GitHub/GitLab Pages."""
    rc = bomgen.main([str(SAMPLE_CSV), "--both", "-o", str(tmp_path), "--quiet"])
    assert rc == 0
    page = (tmp_path / "NCC-1701_pdmout_BOM.html").read_text(encoding="utf-8")
    assert 'href="NCC-1701_pdmout_BOM.xlsx"' in page
    assert (tmp_path / "NCC-1701_pdmout_BOM.xlsx").exists()


def test_cli_xlsx_url_override(tmp_path):
    rc = bomgen.main([str(SAMPLE_CSV), "--html", str(tmp_path / "o.html"),
                      "--xlsx-url", "https://example.com/bom.xlsx", "--quiet"])
    assert rc == 0
    page = (tmp_path / "o.html").read_text(encoding="utf-8")
    assert 'href="https://example.com/bom.xlsx"' in page


def test_source_rev_in_both_outputs(tmp_path):
    """D8: --source-rev (e.g. the vault repo's git hash for the CSV) is
    embedded in both outputs for provenance; omitted -> no trace of it."""
    cfg = bomgen.load_config(None)
    root, warnings = parse(SAMPLE_CSV, cfg)
    x, h = tmp_path / "o.xlsx", tmp_path / "o.html"
    bomgen.write_excel(root, cfg, x, warnings, source_rev="a1b2c3d")
    bomgen.write_html(root, cfg, "src.csv", h, warnings, source_rev="a1b2c3d")

    page = h.read_text(encoding="utf-8")
    assert "a1b2c3d" in page and "rev" in page

    import openpyxl
    ws = openpyxl.load_workbook(x).active
    assert "a1b2c3d" in (ws["B8"].value or "")
    assert ws["B6"].value == "Bill of Materials (BOM)"  # template rows intact

    # omitted -> row 8 stays blank, no stray placeholder text in the HTML
    h2 = tmp_path / "o2.html"
    bomgen.write_html(root, cfg, "src.csv", h2, warnings)
    assert "__SOURCE_REV__" not in h2.read_text(encoding="utf-8")
    x2 = tmp_path / "o2.xlsx"
    bomgen.write_excel(root, cfg, x2, warnings)
    assert openpyxl.load_workbook(x2).active["B8"].value is None


def test_cli_source_rev_flag(tmp_path):
    rc = bomgen.main([str(SAMPLE_CSV), "--html", str(tmp_path / "o.html"),
                      "--source-rev", "deadbee", "--quiet"])
    assert rc == 0
    assert "deadbee" in (tmp_path / "o.html").read_text(encoding="utf-8")


def test_pdm_file_url_links(tmp_path):
    """Configurable file_url_template turns filenames into PDM-viewer links
    in both outputs; {file} is substituted with the URL-encoded filename."""
    cfg = bomgen.load_config(None)
    cfg["links"]["file_url_template"] = (
        "https://pdm.example.edu/vault/PROJ?view=bom&file={file}")
    root, warnings = parse(SAMPLE_CSV, cfg)
    idx = {n.path: n for n in bomgen.preorder(root)}
    # a known part row: NCC-FP005.SLDPRT
    node = idx["1.1.1"]
    assert node.file_url == (
        "https://pdm.example.edu/vault/PROJ?view=bom&file=NCC-FP005.SLDPRT")
    # a filename with spaces is URL-encoded
    shim = idx["1.1.5"]  # "Custom Injector Shim_WRP.SLDPRT"
    assert "%20" in shim.file_url and " " not in shim.file_url

    x, h = tmp_path / "o.xlsx", tmp_path / "o.html"
    bomgen.write_excel(root, cfg, x, warnings)
    bomgen.write_html(root, cfg, "src.csv", h, warnings)

    page = h.read_text(encoding="utf-8")
    # the per-row fileUrl lands in the embedded JSON data blob
    assert '"fileUrl": "https://pdm.example.edu' in page
    assert "file=NCC-FP005.SLDPRT" in page

    import openpyxl
    ws = openpyxl.load_workbook(x).active
    # find the Part Name cell for the NCC-FP005 row and check its hyperlink
    links = [c.hyperlink.target for row in ws.iter_rows() for c in row
             if c.hyperlink]
    assert any("NCC-FP005.SLDPRT" in t for t in links)


def test_pdm_file_url_default_off(tmp_path):
    """Default config (empty template) -> no file_url, no links; unchanged."""
    cfg = bomgen.load_config(None)
    assert cfg["links"]["file_url_template"] == ""
    root, warnings = parse(SAMPLE_CSV, cfg)
    assert all(n.file_url == "" for n in bomgen.preorder(root))
    h = tmp_path / "o.html"
    bomgen.write_html(root, cfg, "src.csv", h, warnings)
    page = h.read_text(encoding="utf-8")
    # fileUrl field is emitted but empty for every row; no populated links
    assert '"fileUrl": ""' in page and '"fileUrl": "http' not in page


# ------------------------------------------------------------ materials (Stage B)

MATERIALS_JSON = FIX / "materials_raw.json"


def _materials_cfg(**over):
    cfg = bomgen.load_config(None)
    cfg["materials"].update({
        "enabled": True, "cache_file": str(MATERIALS_JSON),
        "properties": ["Density_kg/m3", "Tensile_Strength_mpa"],
    })
    cfg["materials"].update(over)
    return cfg


def test_materials_key_normalization():
    k = bomgen.material_cache_key
    assert k("  Tritanium   18-8 ") == k("tritanium 18-8")
    assert k("") == "" and k(None) == ""


def test_materials_enrichment_match():
    """A raw /export/raw-json dump enriches rows whose Material matches."""
    root, warnings = parse(SAMPLE_CSV, _materials_cfg())
    idx = {n.path: n for n in bomgen.preorder(root)}
    # 1.1.3 is a "Tritanium 18-8" washer in the example CSV
    assert idx["1.1.3"].material_props["Density_kg/m3"] == "8000 kg/m3"
    assert idx["1.1.3"].material_props["Tensile_Strength_mpa"] == "620 MPa"
    # 1.1.4 is "Duranium A286 Alloy" — has density, no tensile in the DB
    assert idx["1.1.4"].material_props["Density_kg/m3"] == "7920 kg/m3"
    assert idx["1.1.4"].material_props["Tensile_Strength_mpa"] == ""
    # unmatched materials in the example produce a grouped V9 warning
    assert any(w.startswith("V9") for w in warnings)


def test_materials_show_units_false():
    root, _ = parse(SAMPLE_CSV, _materials_cfg(show_units=False))
    idx = {n.path: n for n in bomgen.preorder(root)}
    assert idx["1.1.3"].material_props["Density_kg/m3"] == "8000"


def test_materials_synonym_match(tmp_path):
    """A Material that matches a DB synonym still resolves."""
    csv = tmp_path / "syn.csv"
    csv.write_text("Level,Qty,Number,Material,COTS\n"
                   "1,1,NCC-FA002.SLDASM,,\n"
                   "1.1,1,NCC-FP001.SLDPRT,18-8,\n", encoding="utf-8")
    root, _ = parse(csv, _materials_cfg())
    idx = {n.path: n for n in bomgen.preorder(root)}
    assert idx["1.1"].material_props["Density_kg/m3"] == "8000 kg/m3"


def test_materials_cache_missing_warns():
    cfg = _materials_cfg(cache_file="/no/such/materials.json")
    root, warnings = parse(SAMPLE_CSV, cfg)
    assert any(w.startswith("V8") for w in warnings)
    assert all(n.material_props.get("Density_kg/m3", "") == ""
               for n in bomgen.preorder(root) if n.parent)


def test_materials_disabled_is_noop():
    """Default config -> no enrichment, no material columns, no warnings."""
    cfg = bomgen.load_config(None)
    assert cfg["materials"]["enabled"] is False
    root, warnings = parse(SAMPLE_CSV, cfg)
    assert all(n.material_props == {} for n in bomgen.preorder(root))
    assert not any(w.startswith(("V8", "V9")) for w in warnings)


def test_materials_render_both_outputs(tmp_path):
    cfg = _materials_cfg(labels={"Density_kg/m3": "Density"})
    root, warnings = parse(SAMPLE_CSV, cfg)
    x, h = tmp_path / "o.xlsx", tmp_path / "o.html"
    bomgen.write_excel(root, cfg, x, warnings)
    bomgen.write_html(root, cfg, "src.csv", h, warnings)

    page = h.read_text(encoding="utf-8")
    assert '"Density"' in page and "8000 kg/m3" in page

    import openpyxl
    ws = openpyxl.load_workbook(x).active
    row17 = [c.value for c in ws[17] if c.value is not None]
    assert "Density" in row17            # labeled header
    assert "Tensile Strength mpa" in row17  # default underscore->space label
