# Status vocabulary

Membrane Visual QC uses several distinct, non-interchangeable status vocabularies across the
single-structure report, the batch contracts, the Batch review GUI, and the PDBTM cache. The same
English word (or even the same JSON field name, `overall_status`) means different things in
different documents. This page is the one canonical table -- if a term you see in the GUI, a
report, or a manifest is not listed here, it is not a literal this project defines (see
`docs/report_schema.md`, `membrane_vqc/batch_contracts.py`, and `membrane_vqc/pdbtm_errors.py` for
the authoritative source enumerations this table is extracted from).

Every vocabulary on this page is a frozen v1.0 candidate contract, additive-only (existing values
never renamed or removed; new values may be added) -- see
`docs/v1.0_contract_freeze.md#5-batchsingle-structure-status-vocabulary-frozen` and
`docs/versioning_policy.md#4-error-code-vocabulary`.

None of these statuses are a biological verdict. "Success" means the software completed its
deterministic geometric/statistical procedure, not that the input is a biologically correct
membrane placement.

## 1. Single-structure report status (`summary.overall_status`)

Appears in every schema 1.0-1.4 `single_structure_review` report's `summary` object.

| Value | Operational meaning | Not a claim that... | Suggested action |
|---|---|---|---|
| `NO_FLAGS` | The configured heuristics found no core-region charged/polar residue to flag. | ...the structure is membrane-correct, complete, or free of issues outside what this run's rules check. | Nothing required; still review orientation/context warnings if present. |
| `REVIEW_ITEMS` | One or more residues were flagged for manual review under the configured rules. | ...any flagged residue is wrong, misplaced, or non-functional. | Inspect each `review_items` entry in structural context (active sites, ion-binding, cofactors -- see `docs/known_limitations.md#scientific-interpretation`). |
| `INSUFFICIENT_CONTEXT` | Zero residues were evaluable (e.g. an empty or non-matching selection). | ...the structure itself is invalid. | Check the selection and orientation bounds/file used for this run. |
| `ANALYSIS_ERROR` | The analysis could not complete for a typed reason (see the accompanying error/warning text). | ...silent or partial results are being shown as if complete. | Read the reported error, fix the input, and retry; do not treat a partial prior state as valid. |

## 2. Batch job status (`jobs[].status` in `batch-result.json`)

The `mvqc-batch-result-1.0` contract's per-job status; see `membrane_vqc/batch_contracts.py:STATUSES`.

| Value | Operational meaning | Not a claim that... | Suggested action |
|---|---|---|---|
| `SUCCESS` | The job's single-structure analysis completed with no flagged review items. | ...the structure is verified correct. | None required. |
| `REVIEW_ITEMS` | The job completed and produced one or more flagged residues (same meaning as report-level `REVIEW_ITEMS` above). | ...the job failed. | Open the job's report through **Batch review**'s result browser. |
| `INSUFFICIENT_CONTEXT` | The job completed but evaluated zero residues. | ...an execution failure occurred. | Check the job's `input`/selection in the plan. |
| `ANALYSIS_ERROR` | The job's analysis raised a typed, recoverable error after inputs were accepted. | ...the whole batch run is invalid. | Check `error_code` and the plan/output for that job specifically. |
| `INPUT_REJECTED` | The job's declared input, path, or cross-reference failed pre-execution validation (never reached analysis). | ...the science produced a wrong answer -- no analysis ran at all. | Fix the plan entry named by `error_code` (see `docs/troubleshooting.md#plans`). |
| `CANCELLED` | The job had not started when a cooperative cancellation was observed. | ...anything about the job's input or correctness. | Re-run the batch (or just the affected jobs) if the work is still needed. |
| `SKIPPED_DEPENDENCY` | Under `failure_policy: fail_fast`, this job was never attempted because an earlier job failed. | ...this specific job's input was itself invalid. | Fix the earlier failing job, then re-run. |

## 3. Batch run status (`overall_status` in `batch-result.json`, top level)

Same field name as #1 above, **different document, different value set** -- do not confuse the
two. See `docs/outputs_and_manifests.md`.

| Value | Operational meaning | Suggested action |
|---|---|---|
| `COMPLETED` | Every job reached `SUCCESS`, `REVIEW_ITEMS`, or `INSUFFICIENT_CONTEXT` -- no job failed, was rejected, or was cancelled. | Review any `REVIEW_ITEMS`/`INSUFFICIENT_CONTEXT` jobs as usual. |
| `COMPLETED_WITH_ERRORS` | The run finished under `continue_on_error`, but at least one job reached `ANALYSIS_ERROR` or `INPUT_REJECTED`. | Inspect the failing jobs' `error_code`; other jobs' outputs remain valid. |
| `FAILED_FAST` | The run stopped under `failure_policy: fail_fast` after the first operational failure; later jobs are `SKIPPED_DEPENDENCY`. | Fix the first failing job and re-run. |
| `CANCELLED` | At least one job was cancelled before starting. | Re-run if the remaining work is still needed. |

## 4. Batch review GUI run-level state (`membrane_vqc/batch_gui.py:BATCH_STATES`)

The dialog's own operational state machine -- separate from both status vocabularies above.

| Value | Meaning | Suggested action |
|---|---|---|
| `IDLE` | No plan is validated for the current path; changing the plan path always returns here. | Choose a plan and press **Validate**. |
| `VALIDATING` | Validation is in progress. | Wait; this is near-instantaneous for typical plans. |
| `READY` | The plan validated against its exact current bytes; **Run** is enabled once an output directory is chosen. | Choose an output directory and press **Run**, or re-edit the plan (which returns to `IDLE`). |
| `RUNNING` | The queue is executing, one job per main-thread event. | Wait, or press **Cancel**. |
| `CANCELLING` | Cancellation was requested; no further job will start, the current job's safe lifecycle still finishes. | Wait for the run to reach `CANCELLED`. |
| `COMPLETED` | The run finished and every job reached a non-cancelled terminal status. | Inspect results via the queue/result browser. |
| `CANCELLED` | The run stopped due to cancellation. | Re-run if needed. |
| `FAILED` | The GUI could not complete the run for an operational reason distinct from any individual job's status. | See the status text and `docs/troubleshooting.md`. |

## 5. Review item severity (`review_items[].severity`)

| Value | Meaning | Not a claim that... |
|---|---|---|
| `WARNING` | A charged core residue was flagged. | ...the residue is wrong -- it may be catalytic, ion-binding, or otherwise functional. |
| `INSPECT` | A polar core residue (or, in schema 1.2+, a context-driven item) was flagged for lower-priority review. | ...the residue requires correction. |

## 6. Result artifact availability (`membrane_vqc/batch_result_browser.py`)

Used when opening a result bundle through **Batch review**'s result browser.

| Value | Meaning | Suggested action |
|---|---|---|
| `VERIFIED` | The referenced file exists, and its size/SHA-256/inode/mtime match the manifest's recorded identity exactly. | Safe to open. |
| `MISSING` | The referenced file no longer exists at its recorded relative path. | This is expected and reported cleanly if the file was moved or deleted after the run -- not an upgrade or plugin defect (see `docs/upgrade_guide.md#7-troubleshooting`). |

An artifact whose bytes exist but no longer match the recorded identity is rejected outright
(`OUTPUT_IDENTITY_CHANGED`, see `docs/troubleshooting.md#batch-execution`), not silently reported
as a third availability state.

## 7. Cache and provider error codes (`membrane_vqc/pdbtm_errors.py:Stage4BErrorCode`)

Raised as typed `Stage4BError` codes from cache/retrieval operations (Fetch/Refresh, Use cached
pair, `pdbtm_cache` batch jobs). None of these indicate a batch job's *scientific* status; a
cache/network failure at this layer surfaces to the batch job as `INPUT_REJECTED` or
`ANALYSIS_ERROR` with this code recorded in `error_code`.

| Code | Meaning |
|---|---|
| `INVALID_RECORD_ID` | The supplied PDBTM record ID does not match the required 4-character format. |
| `CACHE_MISS` | No cached snapshot exists yet for this record. |
| `CACHE_CORRUPT` | An existing cache entry's on-disk bytes do not match its recorded identity. |
| `CACHE_WRITE_FAILED` | A cache write could not be committed (see `docs/troubleshooting.md#networkingcache`). |
| `CACHE_DURABILITY_UNCERTAIN` | A write may or may not have been durably committed; the cache is left in its last known-safe state. |
| `CACHE_CONFLICT` | A concurrent modification was detected (index generation mismatch). |
| `CACHE_FORMAT_UNSUPPORTED` | The on-disk cache format does not match what this plugin version expects -- fails closed, never silently misread (see `docs/upgrade_guide.md#7-troubleshooting`). |
| `CACHE_CLEAR_FAILED` | **Clear cached record** could not remove the entry. |
| `CACHE_OPEN_FAILED` | The cache root could not be opened/initialized. |
| `NETWORK_TIMEOUT` / `NETWORK_UNAVAILABLE` | The bounded direct HTTPS request to the PDBTM API timed out or could not connect. |
| `PROXY_UNSUPPORTED` | A configured system proxy was detected; direct connection only is supported (see `docs/offline_guarantees.md`). |
| `TLS_ERROR` | The TLS handshake or certificate validation failed. |
| `REDIRECT_DISALLOWED` | The server attempted to redirect; this transport follows no redirects. |
| `RESPONSE_TOO_LARGE` | The response exceeded the bounded size limit. |
| `PROVIDER_NOT_FOUND` | The PDBTM API returned "not found" for the requested record. |
| `PROVIDER_RATE_LIMITED` / `PROVIDER_SERVER_ERROR` | The provider returned a rate-limit or server-error response. |
| `PROVIDER_RESPONSE_INVALID` | The response body did not parse as the expected contract. |
| `COMPANION_ID_MISMATCH` | The fetched JSON and transformed-PDB companion do not share the same record identity. |
| `PAIR_VALIDATION_FAILED` | The fetched pair failed the same semantic validation applied to an offline local pair. |
| `RETRIEVAL_CANCELLED` | A Fetch/Refresh operation was cancelled before completing. |

## 8. Batch/result-bundle integrity error codes

Distinct from job-level `error_code` values above -- these are raised as exceptions (not recorded
in a manifest) when a plan, result bundle, or output path itself is structurally unsafe.

| Code | Where it appears | Meaning |
|---|---|---|
| `RESULT_MANIFEST_INVALID` | Opening a result bundle | The selected `batch-result.json` failed contract/JSON validation. |
| `REPORT_INVALID` | Opening a result bundle, or during a batch run's own report write-back | A referenced report file failed schema/semantic validation. |
| `OUTPUT_COLLISION` | Batch execution | An output path already exists and is not owned by the current run under the active `overwrite` policy. |
| `OUTPUT_SIZE_INVALID` / `OUTPUT_UNAVAILABLE` / `OUTPUT_IDENTITY_CHANGED` / `OUTPUT_PATH_UNSAFE` | Opening a result bundle | The referenced artifact's size, readability, byte identity, or path safety failed re-verification at open time. |
| `SAME_BATCH_ROLLED_BACK` | Batch execution under `overwrite: same_batch` | A replacement run failed partway and the prior verified output set was restored byte-for-byte; nothing partial was published. |

## What these vocabularies never express

No status value in this table is, or is derived from, a biological-correctness verdict, a
membrane-insertion claim, a "best" or "preferred" source designation, or a claim of automatic
validation. See `docs/known_limitations.md#scientific-interpretation` and
`docs/coordinate_preservation.md`.
