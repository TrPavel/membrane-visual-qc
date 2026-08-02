# Batch plan reference

A field-by-field reference for `mvqc-batch-plan-1.0`, the JSON contract that drives **Batch
review** and `mvqc_batch_run`. This page covers structure, fields, path rules, and every
supported mode; for a narrated, run-it-yourself example see
[docs/five_mode_walkthrough.md](five_mode_walkthrough.md). For the run-level output contract
(manifest, filenames, atomic publication), see [docs/outputs_and_manifests.md](outputs_and_manifests.md).
For the exact status literals a run can produce, see [docs/status_vocabulary.md](status_vocabulary.md).
This contract is frozen ahead of v1.0 -- see
[docs/v1.0_contract_freeze.md#2-batch-contracts-frozen](v1.0_contract_freeze.md#2-batch-contracts-frozen).

## 1. Purpose of a batch plan

A batch plan is an explicit, ordered list of review jobs -- each job runs one of the five existing
single-structure analysis modes against one input, using the same scientific paths as running that
mode by hand. A plan does not introduce new science, a new report schema, or a new algorithm; it
only sequences and records existing, already-accepted single-job behavior
(`docs/stage5a_batch_review.md`). It is a reproducibility and convenience tool, not a scientific
verdict generator.

## 2. Basic structure

```json
{
  "contract": "mvqc-batch-plan-1.0",
  "jobs": [
    {
      "id": "legacy",
      "input": {"kind": "pymol", "selection": "protein"},
      "analysis": {"mode": "legacy_global_z", "zmin": -15.0, "zmax": 15.0},
      "output": {"write_csv": true}
    }
  ],
  "execution": {"failure_policy": "continue_on_error", "overwrite": "refuse"}
}
```

Every plan needs a `contract` string, an ordered `jobs` array, and an `execution` policy. A job
needs a unique `id`, an `input`, an `analysis` block naming its `mode`, and an `output` block.
`mvqc-batch-plan-1.0` is a strict, closed contract: unknown fields, duplicate JSON keys,
non-finite numbers, ambiguous mode inputs, duplicate job IDs, unsafe paths, and more than 100 jobs
are all rejected before execution.

## 3. Field-by-field reference

| Field | Required | Meaning |
|---|---|---|
| `contract` | yes | Must be exactly `"mvqc-batch-plan-1.0"`. Any other string is rejected -- there is no version-range parsing or silent reinterpretation. |
| `cache_root` | only if any job uses `pdbtm_cache` | Path (relative to the plan file) to the root under which cached PDBTM snapshots are looked up. |
| `jobs` | yes | Ordered array, at most 100 entries (`docs/stage5a_batch_review.md#reviewed-limits`). Jobs run in the listed order. |
| `jobs[].id` | yes | Unique, single-component, safe identifier; also used to derive `<id>.json`/`<id>.csv` output filenames (max 64 characters). May not be `batch-result` (that name is reserved for the manifest). |
| `jobs[].input` | yes | Either `{"kind": "pymol", "selection": "..."}` (an already-loaded PyMOL selection) or `{"kind": "file", "path": "..."}` (a local file, resolved relative to the plan -- see [Path resolution](#4-path-resolution-rules)). |
| `jobs[].analysis` | yes | Mode-specific parameters -- see [Supported modes](#6-each-supported-mode). |
| `jobs[].context` | no | Optional exposure/local-context settings (`{"enabled": true, "quality": "Standard", "backend": "Built-in"}`), same as the single-structure GUI. |
| `jobs[].ligand` | no | Optional `{"selection": "...", "cutoff": 5.0}` ligand-shell parameters. |
| `jobs[].output` | yes | `{"write_csv": true|false}`. `pdbtm_opm_comparison` never writes a CSV regardless of this flag (schema 1.5 has no CSV form). |
| `execution.failure_policy` | yes | `"continue_on_error"` or `"fail_fast"` -- see [Validation and execution](#7-validation-before-execution). |
| `execution.overwrite` | yes | `"refuse"` or `"same_batch"` -- see [Collision behavior](#9-collision-behavior). |

## 4. Path resolution rules

Every file-input path (`input.path`, `orientation_json`, `pdbtm_json`, `transformed_pdb`,
`opm_pdb`, and `cache_root`) is resolved **relative to the plan file's own directory**, not your
current working directory and not the output directory. If you move a plan file, its relative
inputs move with it only if you move the whole directory together.

## 5. Output-root rules

The output root is passed separately from the plan (as `output_dir` on the CLI/command, or chosen
explicitly in the GUI) -- it is never embedded in the plan itself. It must already exist and be
writable. See `docs/outputs_and_manifests.md#output-root-and-run-directory` for the exact layout
written into it.

## 6. Each supported mode

The closed set is exactly these five (`membrane_vqc.batch_contracts.MODES`); no other string is
accepted for `analysis.mode`:

| Mode | Produces | What it needs |
|---|---|---|
| `legacy_global_z` | schema 1.1 (or 1.2 with context) | `zmin`, `zmax` (finite, `zmin < zmax`) -- the original global-z slab. |
| `planar_orientation` | schema 1.1 (or 1.2 with context) | `orientation_json`, a local orientation file. |
| `pdbtm_local` | schema 1.3 | `record_id`, `pdbtm_json`, `transformed_pdb` -- an explicit local, matching PDBTM API-v1 pair. |
| `pdbtm_cache` | schema 1.4 | `record_id`, `snapshot_id` -- an exact, already-validated cache snapshot (requires plan-level `cache_root`; never fetches, never falls back to an "active" snapshot). |
| `pdbtm_opm_comparison` | schema 1.5 | a `pdbtm` source (`local` pair or `cache` snapshot) plus `opm_pdb`, an explicit local OPM-oriented PDB file. |

See `docs/tutorial.md` for a walkthrough of each mode outside of batch, including scientific
boundaries and failure interpretation.

## 7. Validation before execution

Validate without touching PyMOL or the network:

```bash
python -m membrane_vqc.batch_cli validate PLAN.json
```

This checks contract shape, field types, closed enums, duplicate job IDs, unsafe paths, and job
count/size limits -- entirely offline (`docs/offline_and_safety.md`). It never executes a job. In
the GUI, pressing **Validate** does the same thing and never runs anything either
(`docs/stage5b_gui_batch.md`).

Execution policy (`execution.failure_policy`) then governs what happens to *later* jobs if one
fails:

- `continue_on_error` (used by the five-mode example): independent later jobs still run after a
  job reaches `INPUT_REJECTED` or `ANALYSIS_ERROR`.
- `fail_fast`: execution stops after the first such failure; every remaining un-started job is
  recorded as `SKIPPED_DEPENDENCY`.

`REVIEW_ITEMS` and `INSUFFICIENT_CONTEXT` are scientific review states, not execution failures --
they never stop a `continue_on_error` or `fail_fast` run early. See `docs/status_vocabulary.md`.

## 8. Cancellation

Cancellation is cooperative and checked between jobs (not mid-job): the currently running job
finishes its existing safe lifecycle, no later job begins once cancellation is observed, and
already-completed jobs' outputs are kept. Remaining un-started jobs are recorded as `CANCELLED` in
the manifest, which is still published atomically. See `docs/stage5b_gui_batch.md#main-thread-pump-and-cancellation`.

## 9. Collision behavior

`execution.overwrite: "refuse"` (the example plan's setting, and the safer default) rejects a job
outright with `OUTPUT_COLLISION` if its output path already exists and was not written by the
current run. `"same_batch"` allows a run to replace outputs it can prove it owns (matching prior
`run_id` and plan digest, verified byte-for-byte) -- and rolls back to the prior verified set
byte-for-byte if the replacement itself fails partway. See
`docs/outputs_and_manifests.md#atomic-publication-and-collision-behavior` for the full mechanism.

## 10. Safe path restrictions

Rejected everywhere the batch path contract applies: path traversal (`..`), drive-relative
(`C:foo`), UNC (`\\server\share`), device (`\\.\`), pipe, reserved Windows device names (`CON`,
`PRN`, `NUL`, ...), and symlink/reparse-point paths. Ordinary paths containing spaces or Unicode
(Cyrillic, CJK, accented) characters are fully supported. Extended-length `\\?\`-prefixed paths are
intentionally not accepted -- keep paths within practical Windows length limits. See
`docs/known_limitations.md#windows-paths` and `docs/troubleshooting.md#plans`.

## 11. Minimal valid examples

The smallest valid single-job plan (legacy global-z, no context/ligand):

```json
{
  "contract": "mvqc-batch-plan-1.0",
  "jobs": [
    {
      "id": "legacy",
      "input": {"kind": "pymol", "selection": "protein"},
      "analysis": {"mode": "legacy_global_z", "zmin": -15.0, "zmax": 15.0},
      "output": {"write_csv": true}
    }
  ],
  "execution": {"failure_policy": "continue_on_error", "overwrite": "refuse"}
}
```

For a complete, runnable example exercising all five modes together -- with a full narrated
walkthrough of what each job demonstrates, its expected status, and how to inspect the result --
see [docs/five_mode_walkthrough.md](five_mode_walkthrough.md).

## Result contract

`mvqc-batch-result-1.0` records the exact plan-byte digest, run/software identity, timestamps,
ordered statuses, aggregate counts, safe output identities, coordinate preservation, and the
canonical identity-core digest -- see `docs/outputs_and_manifests.md` for the complete field
reference. It never converts review state into proof of correctness or successful membrane
insertion.
