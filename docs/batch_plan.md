# Batch plan contract 1.0

`mvqc-batch-plan-1.0` is a strict, closed JSON contract. Unknown fields, duplicate JSON keys,
non-finite numbers, ambiguous mode inputs, duplicate job IDs, unsafe paths, and more than 100 jobs
are rejected before execution. `cache_root` is required whenever a job uses an exact cached PDBTM
snapshot.

This shortened multi-job plan shows the ordered shape:

```json
{
  "contract": "mvqc-batch-plan-1.0",
  "jobs": [
    {
      "id": "legacy",
      "input": {"kind": "pymol", "selection": "protein"},
      "analysis": {"mode": "legacy_global_z", "zmin": -15.0, "zmax": 15.0},
      "output": {"write_csv": true}
    },
    {
      "id": "planar",
      "input": {"kind": "file", "path": "structure.pdb"},
      "analysis": {"mode": "planar_orientation", "orientation_json": "orientation.json"},
      "context": {"enabled": true, "quality": "Standard", "backend": "Built-in"},
      "ligand": {"selection": "organic", "cutoff": 5.0},
      "output": {"write_csv": true}
    }
  ],
  "execution": {"failure_policy": "continue_on_error", "overwrite": "refuse"}
}
```

The complete synthetic five-mode example is
[`data/synthetic/stage5a_batch_plan.json`](../data/synthetic/stage5a_batch_plan.json); the separate
negative fixture intentionally contains traversal. Local PDBTM jobs require `record_id`,
`pdbtm_json`, and `transformed_pdb`. Cached jobs require `record_id`, `snapshot_id`, and the plan's
relative `cache_root`. Comparison requires an explicit local or exact-cache PDBTM source plus a
local `opm_pdb`; CSV is unavailable for schema-1.5 comparison reports.

Run `python scripts/materialize_stage5a_example.py DESTINATION` to generate the plan's exact
synthetic cache under an untracked destination; the materializer performs no network I/O.

`mvqc-batch-result-1.0` records the exact plan-byte digest, run/software identity, timestamps,
ordered statuses, aggregate counts, safe output identities, coordinate preservation, and the
canonical identity-core digest. The core omits run fields and volatile timestamp-bearing artifact
byte identities while the complete manifest retains those exact identities. It never converts review state into proof of correctness or
successful membrane insertion.
