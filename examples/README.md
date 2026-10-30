# Examples
_Sanitized example data used by the demo site, the tests, and the documentation._

- [`NCC-1701_pdmout.csv`](NCC-1701_pdmout.csv):
  a sanitized, Star Trek–themed copy of a real PDM Professional export.
  Structure, sparsity, and defects (including the Excel-mangled `2.10` item number)
  are preserved verbatim from the original so the repair and warning paths stay exercised.
- [`NCC-1701_specs.csv`](NCC-1701_specs.csv):
  demo spec-assignment table (`File,Spec,Note`) for the budget dashboard;
  includes one deliberately stale row to demonstrate warning V13.
- [`NCC-1701_costs.csv`](NCC-1701_costs.csv):
  demo spec-level cost table with the export-control passthrough columns.

Do **NOT** put real vault data here;
real exports belong in a downstream vault repository (see [`../template-repo/`](../template-repo/)).
