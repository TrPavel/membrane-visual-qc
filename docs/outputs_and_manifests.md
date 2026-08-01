# Outputs and manifests

This page documents the on-disk output contract exactly as it exists today, derived from
`membrane_vqc/batch_paths.py`, `membrane_vqc/batch_runner.py`, `membrane_vqc/batch_contracts.py`,
and a genuine batch result bundle (`tests/fixtures/v0.6.0_batch_result/`). It covers the **batch**
output layout in detail; single-structure exports (`mvqc_export`) write one report (and, from the
GUI, an accompanying CSV) directly to the path you choose, with no additional manifest.

## Output root and run directory

- **Batch output root**: the explicit directory you pass as `output_dir` (CLI) or choose in
  **Batch review** (GUI). It must already exist and be writable; this project never invents or
  discovers an output location for you.
- There is no separate per-run subdirectory created automatically -- all of a run's artifacts (the
  manifest and every job's report/CSV) are written directly into that output root, named from each
  job's `id` (see [Filenames](#filenames) below).
- **Cache root**: unrelated to the output root. Lives at a fixed location independent of both the
  plugin install directory and any batch output directory --
  `%LOCALAPPDATA%\MembraneVisualQC\Cache` by default, or `$MVQC_CACHE_DIR` if set. See
  `docs/compatibility.md#cache-format`.

## Filenames

Each job's artifacts are named directly from its `id` in the plan, validated as a single safe path
component (`membrane_vqc.batch_paths.safe_output_name`):

- report: `<job_id>.json`
- CSV (only when `output.write_csv: true` and the mode produces one -- `pdbtm_opm_comparison` never
  does): `<job_id>.csv`
- manifest: always the fixed name **`batch-result.json`** (`membrane_vqc/batch_runner.py`) --  a
  job may not be named `batch-result` for exactly this reason (`membrane_vqc/batch_contracts.py`
  rejects it as a plan/result validation error).

Example, for the five-mode plan at `data/synthetic/stage5a_batch_plan.json` run to
`C:\mvqc-test\outputs\example\`:

```text
C:\mvqc-test\outputs\example\
├── batch-result.json      <- manifest (always this name)
├── legacy.json
├── legacy.csv
├── planar.json
├── planar.csv
├── pdbtm-local.json
├── pdbtm-local.csv
├── pdbtm-cache.json       <- absent if this job did not reach SUCCESS/REVIEW_ITEMS/INSUFFICIENT_CONTEXT
├── pdbtm-cache.csv
└── comparison.json        <- no comparison.csv; comparison never writes CSV
```

## `batch-result.json` (the manifest)

Validated against `mvqc-batch-result-1.0` (`schemas/mvqc-batch-result-1.0.schema.json`). Top-level
fields, taken directly from a genuine result bundle:

| Field | Meaning |
|---|---|
| `contract` | Always the literal string `mvqc-batch-result-1.0`. |
| `run_id` | A 64-hex identity for this specific run; required to authorize a `same_batch` replacement of itself later. |
| `plan_sha256` | SHA-256 of the exact plan bytes that were executed. |
| `started_at` / `completed_at` | UTC timestamps. |
| `software` | `{"commit": ..., "version": ...}` -- the plugin version/commit that produced this run. |
| `execution` | The plan's own `{"failure_policy": ..., "overwrite": ...}`, echoed back. |
| `overall_status` | The run-level aggregate status -- see `docs/status_vocabulary.md#3-batch-run-status-overall_status-in-batch-resultjson-top-level`. |
| `counts` | Per-job-status tallies plus `total`, e.g. `{"SUCCESS": 3, "REVIEW_ITEMS": 1, "INPUT_REJECTED": 1, ..., "total": 5}`. |
| `identity_core_sha256` | SHA-256 of a canonical subset of this document (see [Reproducibility](#reproducibility-and-the-identity-core) below). |
| `jobs` | Ordered array, one entry per plan job (see below). |

Each `jobs[]` entry:

| Field | Meaning |
|---|---|
| `job_id`, `mode` | Echoed from the plan. |
| `status` | Job-level status -- see `docs/status_vocabulary.md#2-batch-job-status-jobsstatus-in-batch-resultjson`. |
| `error_code` | A stable code (see `docs/status_vocabulary.md#7-cache-and-provider-error-codes` and `#8`) when `status` is `INPUT_REJECTED` or `ANALYSIS_ERROR`; otherwise `null`. |
| `report_schema` | The report schema version this job's report was written as (e.g. `"1.1"`, `"1.3"`, `"1.5"`), or `null` if no report was produced. |
| `review_items_count`, `warnings_count` | Counts extracted from the job's report, or `null`/`0` if no report exists. |
| `coordinate_preserved` | `true`/`false` if the job's coordinate-fingerprint check ran, `null` if the job never reached that stage (e.g. `INPUT_REJECTED`). See `docs/coordinate_preservation.md`. |
| `report` | `{"path": "<job_id>.json", "size": ..., "sha256": ...}` (relative to the output root), or `null`. |
| `csv` | Same shape for the CSV companion, or `null`. |

## Reproducibility and the identity core

`identity_core_sha256` is computed over a canonical subset of the manifest that **excludes**
`run_id`, `started_at`/`completed_at`, and any timestamp-bearing byte identities -- so two
independent runs of the same plan against the same inputs can be compared for operational
equivalence even though their timestamps and run IDs necessarily differ. The complete manifest
(with timestamps) is not claimed to be byte-reproducible across runs; only this identity core is
meaningful to compare directly.

## Atomic publication and collision behavior

Every artifact (each report, each CSV, and the manifest itself) is written via
`membrane_vqc.batch_paths.atomic_write_bytes`: data is written to a securely-random temporary file
in the same directory, `fsync`'d, and then published with a single `os.replace` -- there is no
window where a partially-written file is visible at its final name.

- **Collision refusal (`overwrite: refuse`, the plan default)**: if an output path already exists
  and was not written by the current run, the job is rejected with `OUTPUT_COLLISION` before any
  write is attempted.
- **`overwrite: same_batch`**: a new run may replace outputs it can prove it owns -- specifically,
  every existing output at those paths must still match the size/SHA-256 recorded by the prior
  manifest for the *same* `run_id` and plan digest. This replacement is transactional: if the
  replacement run fails or is cancelled partway, the prior verified artifact set is restored
  byte-for-byte (`SAME_BATCH_ROLLED_BACK`), never left in a partial state.
- Existing unrelated files in the output directory, duplicate job-derived names, path traversal,
  absolute/URL/UNC/device paths, reserved Windows device names, and symlink/reparse-point escapes
  are all rejected before any write.

## Cancelled and failed run layout

- Under cancellation, jobs that already completed keep their published artifacts; jobs that never
  started are recorded as `CANCELLED` in the manifest with no `report`/`csv` entries.
- Under `fail_fast`, later un-started jobs are recorded as `SKIPPED_DEPENDENCY`, also with no
  artifacts.
- The manifest itself is always the last thing published, once the run reaches a terminal state --
  so an interrupted process cannot leave a stale `batch-result.json` pointing at artifacts that
  don't correspond to what actually ran (any prior manifest at that path is only replaced according
  to the collision rules above).

## Missing or partial artifacts

If a manifest references a file that was later moved or deleted, opening that result through
**Batch review**'s result browser reports it as availability `MISSING` -- a clean, expected state,
not an error (see `docs/status_vocabulary.md#6-result-artifact-availability`). If the file exists
but its bytes no longer match the manifest's recorded size/SHA-256/identity, it is rejected outright
(`OUTPUT_IDENTITY_CHANGED`) rather than opened and trusted.

## Safe Reveal/Open behavior

**Reveal output** / **Open result manifest** / opening a report or CSV from the result browser are
always explicit, single button actions. The manifest and the specific artifact are re-resolved and
re-verified (size, SHA-256, path safety) immediately before opening -- not just once at load time.
No shell command is constructed from any path; opening uses a Qt local-file URL.

## Ownership and what not to edit

- **User-owned**: everything under the output root and the cache root is yours -- move, copy, back
  up, or delete these files as you wish; the plugin never deletes them on your behalf (including
  across an upgrade -- see `docs/upgrade_guide.md#5-existing-data`).
- **Move artifacts together**: a manifest's `report`/`csv` entries use paths relative to the output
  root, so if you relocate a result bundle, move the manifest and all of its referenced files
  together as one unit; moving only some of them will surface as `MISSING`/`OUTPUT_IDENTITY_CHANGED`
  for the rest.
- **Do not hand-edit** `batch-result.json`, a report JSON, or a CSV and expect the plugin to accept
  it afterward -- every open re-verifies size and SHA-256 against the manifest's recorded identity,
  so any manual edit is detected and rejected, not silently trusted.

## Compatibility across v0.6.0 -> 0.7.x

The output/manifest contract (`mvqc-batch-result-1.0`) and the report schemas it can reference
(1.0-1.5) are unchanged between v0.6.0 and the current `0.7.x` line -- a v0.6.0-era result bundle
remains fully inspectable under `0.7.x` with no conversion step. See
`docs/upgrade_guide.md#5-existing-data` and `docs/manual_install_upgrade_checklist.md` for the
owner-observed confirmation of this.

## What is stable vs. not yet frozen

As of the v0.8.0 contract-freeze audit (`docs/v1.0_contract_freeze.md`), both of the following are
frozen v1.0 candidate contracts -- see that page for the exact deprecation process required before
either could change:

- **The `mvqc-batch-plan-1.0` / `mvqc-batch-result-1.0` JSON shapes themselves, and report schemas
  1.0-1.5** -- exact-string contract identifiers with no version-range parsing
  (`docs/compatibility.md#supported-batch-contract-versions`,
  `docs/v1.0_contract_freeze.md#2-batch-contracts-frozen`).
- **The exact directory layout described above** (flat output root, `<job_id>.json`/`.csv` naming,
  fixed `batch-result.json` manifest name) -- previously documented here as "current convention,
  not yet a versioned promise for v1.0"; that framing is superseded by
  `docs/v1.0_contract_freeze.md#11-outputmanifest-layout-frozen-as-the-v10-candidate`. Do not build
  automation that depends on undocumented details beyond what is written on this page.
