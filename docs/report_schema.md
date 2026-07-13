# Report schema

Membrane Visual QC writes UTF-8 JSON reports using schema version `1.0`. The
machine-readable schema is stored in `schemas/mvqc-report-1.0.schema.json`.

The canonical v1 fields are:

- `software` and `runtime`: software and execution provenance;
- `input`: portable input identity and SHA-256 when a local file is available;
- `orientation`: orientation source, geometry, parameters, and warnings;
- `parameters`: analysis parameters;
- `summary.overall_status`: `NO_FLAGS`, `REVIEW_ITEMS`,
  `INSUFFICIENT_CONTEXT`, or `ANALYSIS_ERROR`;
- `review_items`: explainable residue-level items requiring review;
- `ligand_neighbours`, `warnings`, and `limitations`.

Manual orientation is always recorded and does not imply that the coordinates
are biologically membrane-aligned. `NO_FLAGS` means only that the configured
heuristics emitted no review items.

`input.provenance_status` is `file_hashed` only when a real local path is explicitly supplied
through `mvqc_check input_path=...` or the core API. Normal PyMOL selection analysis reports
`input_path_not_supplied`; it does not guess a source file. `runtime.pymol_status` and
`software.commit_status` similarly distinguish recorded metadata from unavailable metadata.

## Compatibility policy

The v0.1 development fields `plugin`, `version`, `timestamp`,
`flagged_residues`, and the legacy analysis keys inside `input` are retained as
aliases throughout schema v1. New consumers should use the canonical fields.
They may be deprecated only in a future major schema version with a migration
guide and compatibility tests.

## CSV contract

The companion CSV contains review items in deterministic residue order with
these columns:

```text
model,chain,resi,resn,classification,severity,reason,z
```

JSON and CSV are written through a temporary file followed by an atomic
replacement on the same filesystem.
