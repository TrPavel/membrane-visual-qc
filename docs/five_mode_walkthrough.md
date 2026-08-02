# Five-mode walkthrough

A narrated, run-it-yourself walkthrough of the retained synthetic five-mode batch plan --
[`data/synthetic/stage5a_batch_plan.json`](../data/synthetic/stage5a_batch_plan.json). It exercises
all five [batch modes](batch_plan_reference.md#6-each-supported-mode) in one plan, and is the exact
plan used as the "designated" batch example throughout this project's manual acceptance checklists.
For the field-by-field JSON contract, see [docs/batch_plan_reference.md](batch_plan_reference.md).

## What it is, and isn't

This plan exists to exercise every mode end-to-end against small, deterministic, synthetic fixture
files -- it is a software-behavior demonstration, not a scientific example. The synthetic
structures are deliberately artificial. **Nothing about this walkthrough proves anything about
membrane placement, orientation correctness, or biological validity** -- see
[docs/scientific_interpretation.md](scientific_interpretation.md).

## 1. How to run it

The plan references a synthetic PDBTM cache snapshot that is not committed to Git. Materialize it
first (no network access; purely local file generation):

```bash
python scripts/materialize_stage5a_example.py DESTINATION
```

Then either validate it without PyMOL:

```bash
python -m membrane_vqc.batch_cli validate DESTINATION/stage5a_batch_plan.json
```

or run it for real, through **Batch review** (select the materialized plan and an output
directory, press **Validate**, then **Run batch**) or headlessly:

```bash
pymol -cq tests/pymol_smoke/run_batch_plan.py -- DESTINATION/stage5a_batch_plan.json DESTINATION/output
```

## 2. What each job demonstrates

| Job `id` | Mode | Input | Orientation source | What it demonstrates |
|---|---|---|---|---|
| `legacy` | `legacy_global_z` | `pdbtm_original_test.pdb` | `zmin=-15.0, zmax=15.0` | The original, simplest slab mode against a real (if synthetic) transmembrane-shaped file. |
| `planar` | `planar_orientation` | `pdbtm_original_test.pdb` | `stage5a_orientation.json` | The general planar-membrane orientation-file mode on the same input, for direct comparison against `legacy`. |
| `pdbtm-local` | `pdbtm_local` | `pdbtm_original_test.pdb` | `record_id: "test"`, local `pdbtm_api_v1_test.json` + `pdbtm_transformed_test.pdb` pair | The offline-import path with a genuine explicit local pair, producing schema 1.3. |
| `pdbtm-cache` | `pdbtm_cache` | `pdbtm_original_1tes.pdb` | `record_id: "1tes"`, `snapshot_id` naming an exact cache entry under `cache_root` | The cache-read path (schema 1.4) with no network access at all -- requires the materialized cache from step 1; without it, this job fails closed rather than fetching. |
| `comparison` | `pdbtm_opm_comparison` | `pdbtm_original_test.pdb` | local `pdbtm_local` pair plus `opm_oriented_test.pdb` | The two-independent-source geometric comparison (schema 1.5); the only job here with `write_csv: false`, since comparison never writes CSV. |

The separate `stage5a_batch_plan_invalid.json` fixture intentionally contains a path-traversal
violation for negative testing -- it is not a usage example and running it should be rejected, not
executed.

## 3. Expected status distribution

When validated with `python -m membrane_vqc.batch_cli validate`, this plan validates cleanly: 5
jobs, contract `mvqc-batch-plan-1.0`, `"valid": true`.

When actually **executed** with the materialized cache present, the observed distribution for this
specific synthetic example is:

| Status | Jobs | Why |
|---|---|---|
| `SUCCESS` | `legacy`, `planar`, `pdbtm-local`, `pdbtm-cache` | Each mode's inputs are internally consistent and the fixture geometry produces no flagged residues. |
| `REVIEW_ITEMS` | `comparison` | The synthetic PDBTM and OPM fixtures have deliberately offset geometry, so the comparison flags a reviewable disagreement -- this is expected, not a failure. |

**This is the observed status for this specific synthetic example, not a universal guarantee for
real structures.** A real plan against your own data may produce any of the job statuses listed in
[docs/status_vocabulary.md#2-batch-job-status-jobsstatus-in-batch-resultjson](status_vocabulary.md#2-batch-job-status-jobsstatus-in-batch-resultjson)
depending entirely on your inputs. If you run this exact plan without materializing the cache
first, expect `pdbtm-cache` to fail closed with `INPUT_REJECTED` instead of `SUCCESS` -- that is
also expected, not a defect (see [docs/troubleshooting.md#plans](troubleshooting.md#plans)).

## 4. What this example does not prove

- It does not prove that any of the five modes produce a biologically correct membrane placement
  -- it only proves each mode's software path executes and produces the documented report schema.
- `comparison`'s `REVIEW_ITEMS` result is not a claim that either source is wrong, or that one
  source is more correct than the other -- see
  [docs/scientific_interpretation.md#comparison-is-not-source-ranking](scientific_interpretation.md#comparison-is-not-source-ranking).
- The `SUCCESS` results for `legacy`/`planar`/`pdbtm-local`/`pdbtm-cache` do not prove the synthetic
  input structures resemble any real protein -- they are minimal fixtures built to exercise code
  paths deterministically.

## 5. How to inspect the output

After a real run, the output directory contains `batch-result.json` (the manifest) plus each
successful job's `<id>.json` report and (where applicable) `<id>.csv` -- see
[docs/outputs_and_manifests.md](outputs_and_manifests.md) for the exact layout. Through **Batch
review**'s result browser: select the completed run, inspect the ordered queue's per-job status,
press **Open result manifest** to see the raw `batch-result.json`, and use **Reveal selected
report** / **Reveal selected CSV** on any individual job to view its report or CSV directly. Each
open re-verifies the file's identity against the manifest before showing it.
