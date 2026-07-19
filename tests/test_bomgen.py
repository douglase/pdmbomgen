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


def test_pdm_found_in_url_auto():
    """By default {found_in} strips the leading <drive>:\\<vault>\\ for ANY
    drive letter / vault name — no found_in_strip needed."""
    cfg = bomgen.load_config(None)
    cfg["links"]["file_url_template"] = (
        "https://pdm.example.edu/solidworkspdm/Starfleet_PDM/{found_in}")
    root, _ = parse(SAMPLE_CSV, cfg)
    idx = {n.path: n for n in bomgen.preorder(root)}
    # 1.1.1 Found In: D:\Starfleet_PDM\SFC\ENT\NCC\Flight -> drive+vault dropped
    assert idx["1.1.1"].file_url == (
        "https://pdm.example.edu/solidworkspdm/Starfleet_PDM/SFC/ENT/NCC/Flight")
    # a folder with spaces (…\WIP\9000 - Piece Parts) is percent-encoded
    assert "9000%20-%20Piece%20Parts" in idx["1.1.3"].file_url
    assert " " not in idx["1.1.3"].file_url


def test_pdm_found_in_drive_agnostic():
    """Any drive letter works; the vault root is dropped by name-position."""
    rest = bomgen._found_in_rest  # helper: (found_in, strip) -> url tail
    assert rest("D:\\Obs_PDM\\STP\\ESC\\Flight", "") == "STP/ESC/Flight"
    assert rest("E:\\Obs_PDM\\STP\\ESC\\Flight", "") == "STP/ESC/Flight"
    assert rest("Z:\\Another_Vault\\A\\B", "") == "A/B"
    # explicit override still supported (drive-tolerant)
    assert rest("C:\\V\\STP\\ESC", "C:\\V\\STP") == "ESC"
    assert rest("C:\\V\\STP\\ESC", "V\\STP") == "ESC"


def test_pdm_found_in_url():
    """Explicit found_in_strip override yields the same tail."""
    cfg = bomgen.load_config(None)
    cfg["links"]["file_url_template"] = (
        "https://pdm.example.edu/solidworkspdm/Starfleet_PDM/{found_in}")
    cfg["links"]["found_in_strip"] = "D:\\Starfleet_PDM"
    root, _ = parse(SAMPLE_CSV, cfg)
    idx = {n.path: n for n in bomgen.preorder(root)}
    assert idx["1.1.1"].file_url == (
        "https://pdm.example.edu/solidworkspdm/Starfleet_PDM/SFC/ENT/NCC/Flight")


def test_pdm_found_in_and_file():
    """Both placeholders combine: folder path + filename query."""
    cfg = bomgen.load_config(None)
    cfg["links"]["file_url_template"] = (
        "https://pdm.example.edu/vault/{found_in}?view=bom&file={file}")
    cfg["links"]["found_in_strip"] = "D:\\Starfleet_PDM"
    root, _ = parse(SAMPLE_CSV, cfg)
    node = {n.path: n for n in bomgen.preorder(root)}["1.1.1"]
    assert node.file_url == (
        "https://pdm.example.edu/vault/SFC/ENT/NCC/Flight"
        "?view=bom&file=NCC-FP005.SLDPRT")


# ------------------------------------------------------------ budget / specs

SPEC_CSV = ("Level,Qty,Number,Name,Rev,Specs,COTS\n"
            "1,1,NCC-FA010.SLDASM,Weldment,1,SPEC-WELD-001,\n"
            "1.1,4,NCC-FP020.SLDPRT,Plate,,,\n"
            "2,3,NCC-FP030.SLDPRT,Bracket,2,SPEC-MACH-002,\n"
            "3,1,NCC-FA011.SLDASM,Mount,,,\n"
            "3.1,6,92423A111_Screw.SLDPRT,,,SPEC-HDWE-003,X\n"
            "3.2,1,NCC-FP032.SLDPRT,Shim,,,\n"
            "4,2,NCC-FP030.SLDPRT,Bracket,2,SPEC-MACH-002,\n"
            "5,1,NCC-FP040.SLDPRT,MultiSpec,,SPEC-MACH-002; SPEC-WELD-001,\n")


def _spec_rollup(tmp_path, csv_text=SPEC_CSV, cfg=None):
    f = tmp_path / "spec.csv"
    f.write_text(csv_text, encoding="utf-8")
    cfg = cfg or bomgen.load_config(None)
    warnings = []
    header, rows = bomgen.read_csv(f)
    root = bomgen.build_tree(header, rows, cfg, warnings)
    bomgen.derive(root, cfg)
    rollup = bomgen.budget_rollup(root, cfg, warnings, header)
    return rollup, warnings


def test_budget_rollup_semantics(tmp_path):
    """Spec'd node covers its subtree; same part under one spec merges with
    summed qty; leafs with no coverage land in unassigned; multi-spec uses
    the first listed spec."""
    rollup, warnings = _spec_rollup(tmp_path)
    by_name = {s["name"]: s for s in rollup["specs"]}
    assert set(by_name) == {"SPEC-WELD-001", "SPEC-MACH-002", "SPEC-HDWE-003"}
    # weldment is one line; its Plate child is covered, NOT unassigned
    weld = by_name["SPEC-WELD-001"]["lines"]
    assert len(weld) == 1 and weld[0]["file"] == "NCC-FA010.SLDASM"
    # bracket appears twice in the tree (qty 3 + 2) -> one merged line
    mach = {l["file"]: l for l in by_name["SPEC-MACH-002"]["lines"]}
    assert mach["NCC-FP030.SLDPRT"]["qty"] == 5
    assert mach["NCC-FP030.SLDPRT"]["occ"] == 2
    # multi-spec part landed under its FIRST spec
    assert "NCC-FP040.SLDPRT" in mach
    # shim is the only unassigned part
    ufiles = [l["file"] for l in rollup["unassigned"]["lines"]]
    assert ufiles == ["NCC-FP032.SLDPRT"]
    assert rollup["counts"]["specs"] == 3
    assert any(w.startswith("V10") for w in warnings)   # unassigned shim
    assert any(w.startswith("V11") for w in warnings)   # multi-spec row


def test_budget_specs_column_missing_warns(tmp_path):
    csv = "Level,Qty,Number\n1,1,NCC-FA001.SLDASM\n1.1,2,NCC-FP001.SLDPRT\n"
    rollup, warnings = _spec_rollup(tmp_path, csv_text=csv)
    assert rollup["counts"]["specs"] == 0
    assert any(w.startswith("V10") and "not in input" in w for w in warnings)


def test_budget_nested_spec_warns(tmp_path):
    csv = ("Level,Qty,Number,Specs\n"
           "1,1,NCC-FA010.SLDASM,SPEC-WELD-001\n"
           "1.1,2,NCC-FP099.SLDPRT,SPEC-HDWE-003\n")
    rollup, warnings = _spec_rollup(tmp_path, csv_text=csv)
    assert any(w.startswith("V12") for w in warnings)
    # nested item still gets its own line under its own spec
    names = {s["name"] for s in rollup["specs"]}
    assert names == {"SPEC-WELD-001", "SPEC-HDWE-003"}


def test_budget_spec_url_template(tmp_path):
    cfg = bomgen.load_config(None)
    cfg["links"]["spec_url_template"] = "https://docs.example.edu/{spec}"
    rollup, _ = _spec_rollup(tmp_path, cfg=cfg)
    urls = {s["name"]: s["url"] for s in rollup["specs"]}
    assert urls["SPEC-MACH-002"] == "https://docs.example.edu/SPEC-MACH-002"


def test_budget_workbook_structure(tmp_path):
    rollup, warnings = _spec_rollup(tmp_path)
    cfg = bomgen.load_config(None)
    out = tmp_path / "budget.xlsx"
    bomgen.write_budget_xlsx(rollup, cfg, "spec.csv", out, warnings,
                             source_rev="abc1234")
    import openpyxl
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Budget", "Parts"]
    ps = wb["Parts"]
    rows = [r for r in ps.iter_rows(min_row=2, max_col=6, values_only=True)
            if r[0]]
    # merged bracket line: qty 5 under SPEC-MACH-002
    bracket = [r for r in rows if r[1] == "NCC-FP030-02"]
    assert bracket and bracket[0][0] == "SPEC-MACH-002" and bracket[0][5] == 5
    # unit-best + ext formulas present, and Budget sheet SUMIF-links Parts
    assert ps["J2"].value.startswith("=IF(I2")
    assert ps["N2"].value.startswith("=IF(J2")
    bs = wb["Budget"]
    cells = [c.value for row in bs.iter_rows() for c in row
             if isinstance(c.value, str)]
    assert any("SUMIF(Parts!$A:$A" in v for v in cells)
    assert any(v == "TOTAL" for v in cells)
    assert any("abc1234" in v for v in cells)           # provenance stamp


def test_cli_budget_dashboard_outputs(tmp_path):
    f = tmp_path / "spec.csv"
    f.write_text(SPEC_CSV, encoding="utf-8")
    rc = bomgen.main([str(f), "--both", "--budget", "--dashboard",
                      "-o", str(tmp_path), "--quiet"])
    assert rc == 0
    dash = (tmp_path / "spec_Dashboard.html").read_text(encoding="utf-8")
    assert (tmp_path / "spec_Budget.xlsx").exists()
    # dashboard links its xlsx twin and the BOM page (relative siblings)
    assert 'href="spec_Budget.xlsx"' in dash
    assert 'href="spec_BOM.html"' in dash
    # rollup data embedded; warnings banner present
    assert "SPEC-MACH-002" in dash and 'id="warnbox"' in dash


def test_pdm_found_in_missing_skips_link(tmp_path):
    """A {found_in} template + a row with no Found In -> no dead link."""
    csv = tmp_path / "nofoundin.csv"
    csv.write_text("Level,Qty,Number,Found In\n"
                   "1,1,NCC-FA002.SLDASM,\n"
                   "1.1,1,NCC-FP001.SLDPRT,\n", encoding="utf-8")
    cfg = bomgen.load_config(None)
    cfg["links"]["file_url_template"] = "https://pdm.example.edu/v/{found_in}"
    root, _ = parse(csv, cfg)
    assert all(n.file_url == "" for n in bomgen.preorder(root))


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
