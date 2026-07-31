# Stage 5A reproducible batch review

Stage 5A runs an ordered list of explicit review jobs using the existing accepted single-job
scientific paths. The planner and contract validator import without PyMOL. Execution occurs only
inside PyMOL, sequentially on the calling main thread; no worker invokes a PyMOL command.

## Supported modes

The closed plan union accepts exactly `legacy_global_z`, `planar_orientation`, `pdbtm_local`,
`pdbtm_cache`, and `pdbtm_opm_comparison`. The first four produce the existing report schemas
1.1/1.2, 1.3, or 1.4 as appropriate; comparison produces schema 1.5. Stage 5A does not duplicate
or change scientific algorithms or schemas 1.0–1.5.

File inputs are relative to the plan directory. Loaded PyMOL inputs require an explicit selection.
Temporary file-backed objects use deterministic plugin-owned names. PyMOL loads the exact
preflighted bytes from a private temporary copy, that copy is re-hashed after loading, and both
copy and object are deleted after their job. User-owned objects are never deleted, and a full-precision
coordinate fingerprint must match before and after every successful job.

Cached jobs name a canonical record ID and exact snapshot SHA-256. All file inputs and cache
snapshots are resolved before the first job. Batch execution never calls retrieval, never falls
back to the active snapshot, and never fetches OPM.

## Execution and failure

`continue_on_error` is the default example policy: independent later jobs continue after
`INPUT_REJECTED` or `ANALYSIS_ERROR`. `fail_fast` stops after the first operational failure and
marks later jobs `SKIPPED_DEPENDENCY`. `REVIEW_ITEMS` and `INSUFFICIENT_CONTEXT` are scientific
review states, not execution failures. Cooperative cancellation is checked between jobs; under
`refuse`, completed reports remain and unstarted jobs become `CANCELLED`.

The output root is explicit. Job IDs produce stable single-component `.json` and optional `.csv`
names. Existing unrelated files, duplicate names, traversal, absolute/URL/UNC/device paths,
reserved Windows names, and symlink/reparse escapes are rejected. Each artifact and the final
manifest are staged on the output filesystem and published with an atomic no-overwrite link.
`refuse` is the default overwrite policy; `same_batch` accepts only identities already recorded by
the same explicit run ID. A `same_batch` replacement is transactional: cancellation or any
operational error restores the verified prior artifacts and manifest instead of publishing a
partial replacement.

The result manifest is an operational index, not a biological certificate. It contains no absolute
path, username, hostname, proxy, credential, provider body, or raw exception. A canonical identity
core excludes run ID, timestamps, and timestamp-bearing report byte identities so its operational
SHA-256 can be compared; the manifest retains the exact report/CSV sizes and SHA-256 values outside
that core. Complete timestamp-bearing manifest bytes are not claimed reproducible.

## Interfaces

Validate without importing PyMOL:

```bash
python -m membrane_vqc.batch_cli validate data/synthetic/stage5a_batch_plan.json
```

Run from an initialized PyMOL session:

```pml
mvqc_batch_run plan=data/synthetic/stage5a_batch_plan.json, output_dir=reports/stage5a, fail_fast=0, quiet=1
```

Or run headlessly from the checkout root:

```bash
pymol -cq tests/pymol_smoke/run_batch_plan.py -- PLAN.json OUTPUT_DIR
```

The retained five-mode plan names an exact deterministic synthetic snapshot. Materialize the
untracked cache and a self-contained copy of the fixtures before executing it:

```bash
python scripts/materialize_stage5a_example.py .test-tmp-stage5a-example
pymol -cq tests/pymol_smoke/run_batch_plan.py -- .test-tmp-stage5a-example/stage5a_batch_plan.json .test-tmp-stage5a-example/output
```

No cache content or official provider payload is committed.

## Reviewed limits

- plan bytes: 1,048,576;
- jobs per plan: 100;
- job ID: 64 characters;
- each path: 512 characters;
- each local input file: 67,108,864 bytes;
- aggregate preflighted local/cache payload bytes: 268,435,456;
- selection and ordinary bounded text: 256 characters;
- ligand cutoff: greater than 0 and at most 100 Å;
- total enforceable job-output bytes per run: 536,870,912;
- stable error codes: 64 characters; diagnostic text is never serialized and internal bounded
  warning/error text is limited to 512 characters.

For `overwrite: same_batch`, pass the prior 64-hex run identity explicitly as the optional PyMOL
command argument `run_id=...`. Replacement is permitted only when both run ID and exact plan digest
match and every existing output still matches the size/SHA recorded by the prior manifest.
Successful replacement publishes the complete new set; an unsuccessful replacement raises the
stable `SAME_BATCH_ROLLED_BACK` code and leaves the prior set byte-for-byte intact.

See [batch_plan.md](batch_plan.md) for the contract shape and multi-job example.
