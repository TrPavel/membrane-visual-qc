# Machine-readable public-contract inventory

Every `.json` file in this directory is **generated**, not hand-authored -- run
`python scripts/export_contract_inventory.py` from the repository root to regenerate it. Each
value inside is imported directly from the module that owns it (see each file's `"source"` field),
so this inventory cannot silently drift from the code it describes without the generator itself
being changed. `tests/test_contract_inventory.py` re-runs the generator and diffs the result against
these committed files on every CI run -- if they disagree, the test fails.

This is the machine-readable counterpart to the prose contract-freeze audit in
[docs/v1.0_contract_freeze.md](../v1.0_contract_freeze.md) and the compatibility commitment in
[docs/versioning_policy.md](../versioning_policy.md#2-the-1x-compatibility-commitment). Read those
two documents for *why* each item here is frozen and what changing it would require; this directory
exists only to give an external tool (or a future audit) something to diff against without parsing
Markdown.

| File | Covers |
|---|---|
| `public_api.json` | The 5-name importable Python API surface (`membrane_vqc.__all__`). |
| `commands.json` | The 11 public PyMOL commands and their exact parameter/default sets. |
| `batch_plan_contract.json` | `mvqc-batch-plan-1.0`/`mvqc-batch-result-1.0`, the 5 modes, job statuses, run-level outcomes, size/count limits. |
| `report_schemas.json` | Report schema versions 1.0-1.5, current/legacy/context/adapter/acquisition version constants, and the schema filenames on disk. |
| `status_vocabulary.json` | Every status/outcome/error-code literal this project defines, across all 6 distinct vocabularies (report, batch job, batch run, GUI state, cache/provider error, result-bundle availability) -- these are genuinely different vocabularies; see [docs/status_vocabulary.md](../status_vocabulary.md). |
| `comparison.json` | The PDBTM-OPM comparison method identifier, its 3 result bands, and the 3 review thresholds (5°/2Å/2Å) -- **not** part of the 1.x freeze commitment, included here for completeness. |
| `csv_columns.json` | The single-structure flags CSV's exact column order. |
| `output_paths.json` | The batch manifest filename and per-job artifact naming pattern. |
| `cache_format.json` | The PDBTM validated-cache contract identifier (`cache-v1`). |

Do not hand-edit these files. If a value needs to change, change it in the source module the
`"source"` field names, then regenerate.
