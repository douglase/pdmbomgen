# Plan: material-property enrichment from `materials_database`

**Status: deferred / not yet implemented.** This is a design record for a
future feature, captured so the work can start from a known position rather
than a blank page. Nothing here is wired into bomgen today.

## Why

Some material metadata the BOM would benefit from — density, CTE, outgassing
(TML/CVCM/WVR), tensile/yield strength, thermal properties — is not in the
PDM export. It lives in a separate system, **`materials_database`**
(github.com/douglase/materials_database): a Node/Express + MongoDB app behind
an HTTPS NGINX reverse proxy, run by the mechanical/optical/aerospace teams.

The goal: let a generated BOM carry those properties for each part's
material, sourced from that database, without breaking bomgen's current
"reads a file, writes a file, touches no network" model.

## What the materials_database actually exposes

Read from the repo (`server/routes/*.js`, `server/models/material.js`):

- **REST API with unauthenticated read endpoints** (only writes need Google
  OAuth + admin role):
  - `GET /export/raw-json` → the whole non-deleted collection as one JSON
    document. The ideal bulk-sync source.
  - `GET /materials/` (all), `GET /materials/name/:name` (exact),
    `GET /materials/search?Material=<text>` (regex over **both** `Material`
    and `Material_Synonyms`).
- **Schema** (`server/models/material.js`): each material has a unique
  `Material` name, `Material_Synonyms: [String]`, `Specification: [String]`,
  `UNS_Designation`, `Manufacturer`, `Part_Number`, and `Properties` — a
  **Map of `{ value, unit, reference }`** objects. Real property keys
  include `Density_kg/m3`, `Elastic_Modulus_gpa`, `Poissons_ratio`,
  `CTE_u/k`, `Thermal_Conductivity_W/mK`, `Specific_Heat_J/gC`,
  `Tensile_Strength_mpa`, `Yield_Strength_mpa`, `Total_mass_loss` (TML),
  `Collected_volatile_condensed_mass` (CVCM), `Tg_deg_c`.
- **A SolidWorks material export already exists**: `GET /export/solidworks`
  emits a `.sldmat` file (`server/utils/solidworksExport.js`).

## Two complementary paths (not either/or)

### Path A — enrich at BOM generation (two-stage, keeps bomgen network-free)

bomgen must not gain a live network dependency: its CI
(`.github/workflows/pages.yml`, `.gitlab-ci.yml`, template-repo copies)
makes zero outbound calls beyond pip/git/deploy, and "no network
dependencies, no server" is a stated design goal for the HTML output (§1).
So split the work in two:

- **Stage A — sync (out of bomgen's runtime).** A small companion script
  (`scripts/sync_materials.py`) run wherever the materials server is
  reachable — a trusted/VPN'd machine or an internal scheduled job, **not**
  the public Pages CI. It does `GET /export/raw-json`, then writes a local
  JSON cache keyed by normalized material name (canonical entry per material
  + one alias entry per synonym). Uses `requests`/stdlib `urllib`; no Mongo
  driver, no credentials (reads are open).

- **Stage B — enrich (in bomgen, local-disk only).** bomgen reads that cache
  file from disk at generation time and merges matched properties into each
  BOM node. Purely additive and config-gated (`[materials].enabled`): if the
  file is absent or the feature is off, behavior is exactly as today.

The **cache file is the seam** between the two stages, so Stage B can be
built and tested with a hand-written fake cache before Stage A or the server
URL exist.

### Path B — populate in CAD/PDM up front (largely already built)

The database's existing `/export/solidworks` `.sldmat` output can be
imported into the SolidWorks material library, assigning real materials
(with properties) to parts in CAD. Those then flow through PDM as ordinary
`Material`-family columns in the export — needing **zero bomgen changes**
for whatever PDM ends up carrying. This is a CAD/PDM-admin workflow choice,
complementary to Path A.

## Stage B design (bomgen side — the buildable part)

### Cache file format
JSON at `cfg["materials"]["cache_file"]`, keyed by normalized material name;
property values keep the DB's `{value, unit}` shape:
```json
{
  "_meta": {"generated_at": "...", "source": "https://<server>/export/raw-json"},
  "materials": {
    "aluminum 6061-t6": {
      "canonical": "Aluminum 6061-T6",
      "specification": ["AMS 4027"],
      "properties": {
        "Density_kg/m3":        {"value": 2700, "unit": "kg/m3"},
        "CTE_u/k":              {"value": 23.6, "unit": "u/k"},
        "Tensile_Strength_mpa": {"value": 310,  "unit": "MPa"},
        "Total_mass_loss":                    {"value": 0.01, "unit": "%"},
        "Collected_volatile_condensed_mass":  {"value": 0.0,  "unit": "%"}
      }
    },
    "al 6061": {"alias_of": "aluminum 6061-t6"}
  }
}
```
Shared normalization function in `bomgen/__init__.py` (the contract both
stages must agree on):
```python
def material_cache_key(material: str) -> str:
    return re.sub(r"\s+", " ", (material or "").strip()).casefold()
```

### Config
`DEFAULT_CONFIG["columns"]` gains `material = "Material"` (the PDM column
holding the material name). New section (mirrored in `DEFAULT_CONFIG`):
```toml
[materials]
enabled    = false     # explicit opt-in; default = today's behavior
cache_file = ""        # path to Stage A's JSON cache
properties = ["Density_kg/m3", "CTE_u/k", "Tensile_Strength_mpa",
               "Total_mass_loss", "Collected_volatile_condensed_mass"]
show_units = true      # "2700 kg/m3" vs bare "2700"
labels     = {}        # optional key -> header override, e.g.
                       # {"Total_mass_loss" = "TML",
                       #  "Collected_volatile_condensed_mass" = "CVCM"}
```
Property keys stay config-driven (never hardcoded), so the DB can add fields
without a bomgen code change. Defaults above are real DB keys.

### Code changes (all in `bomgen/__init__.py` unless noted)
- New `BomNode.material_props: dict = field(default_factory=dict)` — a
  first-class derived field, mirroring how `cots` is first-class rather than
  generic passthrough.
- `derive()` gains a `warnings` param (2 call sites: `main()` and the test
  `parse()` helper). It loads the cache once (a new `_load_materials_cache`
  helper), then in the existing `visit()` walk — beside `n.cots = ...` —
  looks up `material_cache_key(n.raw.get(col["material"]))`, resolves one
  `alias_of` hop, and fills `n.material_props` with rendered value (or
  `value unit`) per configured property, or blanks on a miss.
- Rendering reuses the existing dynamic-column mechanism: append the
  material columns onto the same `passthrough` lists in `write_excel()`
  (`headers`/`vals`/widths) and `write_html()` (`extraCols`/`extra`).
  **`bomgen/template.html` needs no change** — it already renders an
  arbitrary `extraCols`/`extra` set.
- Warnings reuse the existing yellow-banner infrastructure (D6):
  - **V8** — enrichment enabled but cache file missing/unreadable (one-shot).
  - **V9** — grouped count of rows whose material wasn't found in the cache
    (same grouped style as V7's `scan_unresolved_props`). Cache miss is
    always blank + warning, never an abort (same precedent as COTS/D1).
- CLI: add `--materials-cache PATH` to override the configured path (parity
  with `--xlsx-url`/`--source-rev`); implies `enabled=true` for that run.
  `scripts/build_pages.sh` needs no change.

### Tests (`tests/test_bomgen.py`, using `tmp_path`, no mocking)
Match success populates `material_props`; cache miss → blank + V9; missing
cache file → V8 + blanks, other outputs still written; **regression guard**:
`enabled=false` (default) → `material_props == {}`, no new warnings, existing
tests unaffected; a unit test of `material_cache_key()` normalization; and an
Excel+HTML render test asserting the labeled column + value appear in both.

## Open items before implementing
- **Materials server URL + reachability** — the one real unknown. Reads need
  no auth, so once the hostname is known and the sync host can reach it,
  Stage A works. (IT / infra question.)
- **Whether to pursue Path B in parallel** — importing the `.sldmat` into the
  CAD material library is a CAD/PDM-admin decision; it could reduce or remove
  the need for Path A depending on how much ends up in PDM directly.
- **Cache staleness** — the schema captures `_meta.generated_at`; a "cache is
  N days old" warning is a cheap later addition once sync cadence is decided.
- **Structured vs. rendered values** — Stage B renders `value`/`value unit`
  as a display string. If a future mass/CTE roll-up needs machine-readable
  numbers, revisit whether `material_props` should hold `{value, unit}`
  instead of a pre-rendered string.
