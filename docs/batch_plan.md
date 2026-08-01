# Batch plan guide

A first-time-user guide to `mvqc-batch-plan-1.0`, the JSON contract that drives **Batch review**
and `mvqc_batch_run`. For the run-level output contract (manifest, filenames, atomic publication),
see `docs/outputs_and_manifests.md`. For the exact status literals a run can produce, see
`docs/status_vocabulary.md`.

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
count/size limits -- entirely offline (`docs/offline_guarantees.md`). It never executes a job. In
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

## 11. Five-mode narrated example

[`data/synthetic/stage5a_batch_plan.json`](../data/synthetic/stage5a_batch_plan.json) is the
retained, complete synthetic example exercising all five modes in one plan, with
`execution: {"failure_policy": "continue_on_error", "overwrite": "refuse"}`. The separate
`stage5a_batch_plan_invalid.json` fixture intentionally contains a path-traversal violation for
negative testing -- it is not a usage example. The valid plan references a synthetic cache under
`stage5a-synthetic-cache/`, which is not committed to Git; materialize it first with:

```bash
python scripts/materialize_stage5a_example.py DESTINATION
```

(no network access; purely local file generation). This is also the exact plan used as the
"designated" batch example throughout this project's manual acceptance checklists.

| Job `id` | Mode | Input | Orientation source | Why it's included |
|---|---|---|---|---|
| `legacy` | `legacy_global_z` | `pdbtm_original_test.pdb` | `zmin=-15.0, zmax=15.0` | Exercises the original, simplest slab mode with a real (if synthetic) transmembrane-shaped file. |
| `planar` | `planar_orientation` | `pdbtm_original_test.pdb` | `stage5a_orientation.json` | Exercises the general planar-membrane orientation-file mode on the same input, for direct comparison against `legacy`. |
| `pdbtm-local` | `pdbtm_local` | `pdbtm_original_test.pdb` | `record_id: "test"`, local `pdbtm_api_v1_test.json` + `pdbtm_transformed_test.pdb` pair | Exercises the offline-import path with a genuine explicit local pair, producing schema 1.3. |
| `pdbtm-cache` | `pdbtm_cache` | `pdbtm_original_1tes.pdb` | `record_id: "1tes"`, `snapshot_id` naming an exact cache entry under `cache_root` | Exercises the cache-read path (schema 1.4) with no network access at all -- requires the materialized synthetic cache above to be present; without it, this job fails closed rather than fetching. |
| `comparison` | `pdbtm_opm_comparison` | `pdbtm_original_test.pdb` | local `pdbtm_local` pair plus `opm_oriented_test.pdb` | Exercises the two-independent-source geometric comparison (schema 1.5); the only job here with `write_csv: false`, since comparison never writes CSV. |

When run through `python -m membrane_vqc.batch_cli validate`, this plan validates cleanly (5 jobs,
`mvqc-batch-plan-1.0`). When actually executed with the materialized cache present, expect
`legacy`, `planar`, `pdbtm-local`, and `pdbtm-cache` to reach `SUCCESS` and `comparison` to
typically reach `REVIEW_ITEMS` given the synthetic fixtures' deliberately-offset geometry -- **this
is the observed status for this specific synthetic example, not a universal guarantee for real
structures.** A real plan against your own data may see any of the job statuses in
`docs/status_vocabulary.md#2-batch-job-status-jobsstatus-in-batch-resultjson` depending entirely on
your inputs.

## Result contract

`mvqc-batch-result-1.0` records the exact plan-byte digest, run/software identity, timestamps,
ordered statuses, aggregate counts, safe output identities, coordinate preservation, and the
canonical identity-core digest -- see `docs/outputs_and_manifests.md` for the complete field
reference. It never converts review state into proof of correctness or successful membrane
insertion.
