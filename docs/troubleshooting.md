# Troubleshooting

Organized by symptom. Each entry states the likely cause, the recovery step, and links to the
detailed doc that governs that behavior. Terms in `code font` are the exact user-visible literals
this project uses -- see `docs/status_vocabulary.md` for the canonical table they come from.

Before retrying after a failure during batch execution or PDBTM retrieval, **preserve the current
output directory, the manifest, and the PyMOL console log** if you plan to report the issue --
retrying in place can overwrite the evidence needed to diagnose it (collision rules permitting; see
`docs/outputs_and_manifests.md#atomic-publication-and-collision-behavior`).

## Installation

**Plugin does not appear in the menu after installing.**
PyMOL was not fully restarted (closing just the Plugin Manager dialog is not enough), or Python's
own module cache still holds an old/no state from before the install. Fully quit and relaunch
PyMOL. See `docs/upgrade_guide.md#7-troubleshooting`.

**Duplicate plugin menu entry.**
Usually means old and new plugin files are both present under different install-directory names
after an overlay install. Follow the clean-replacement method in
`docs/upgrade_guide.md#3-recommended-installation-method`.

**Old version is still displayed after installing a new ZIP.**
Same root cause as "does not appear" above -- PyMOL was not fully restarted, or files were
overlaid rather than cleanly replaced. See `docs/upgrade_guide.md#7-troubleshooting`.

**Plugin Manager install failure.**
Capture the exact error text. A permission error usually means you lack write access to PyMOL's
plugin directory -- consult your PyMOL distribution's own documentation for that location. See
`docs/upgrade_guide.md#7-troubleshooting`.

**Stale files after an overlay install.**
Compare your installed `membrane_vqc/` directory's files against its own
`membrane_vqc/PLUGIN_MANIFEST.json`; anything present but not listed is a leftover from a prior
install. Delete it, or perform a clean reinstall per `docs/upgrade_guide.md#3-recommended-installation-method`.

## GUI

**Dialog is too tall or clipped.**
Report your display scaling percentage and PyMOL/Windows build if filing an issue -- this is
tracked as a manual-verification item (`docs/compatibility.md#what-ci-cannot-prove`). Try resizing
the dialog window directly.

**Vertical scrolling does not work.**
Confirm you are scrolling inside the dialog's own scroll area, not the outer PyMOL window. If it
genuinely does not scroll, this is a real defect -- report it with your PyMOL version.

**UI appears frozen.**
Batch execution and PDBTM Fetch/Refresh run on the main PyMOL/Qt thread by design
(`docs/stage5b_gui_batch.md#main-thread-pump-and-cancellation`) -- brief unresponsiveness during a
single job/request is expected, not a hang. If it does not recover within a reasonable time for the
size of the job, note how long you waited and whether **Cancel** was available and worked.

**`QThread: Destroyed while thread is still running` warning in the PyMOL console.**
This should never occur under normal use -- close/reopen and cancellation are both designed to
avoid it (`docs/stage5b_gui_batch.md`). If you see it, note the exact action that preceded it
(close, cancel, or a specific tab) and report it.

**Close/reopen behavior.**
Closing the dialog while a batch run or PDBTM Fetch is active requests the same cooperative
cancellation as pressing **Cancel**; it never blocks or force-terminates a thread.

**History resets after restart.**
This is expected, not a bug. Batch review history (at most 20 entries) lives only in the dialog's
in-memory state for as long as PyMOL stays open -- it is never written to disk by any version. Keep
the manifest/report files a run wrote to your output directory if you need a permanent record. See
`docs/upgrade_guide.md#2-before-upgrading`.

## Plans

**Missing plan file.**
`python -m membrane_vqc.batch_cli validate PLAN.json` and the GUI's **Validate** both print/show a
concise error and exit non-zero / stay in `IDLE` rather than raising a traceback.

**Malformed JSON.**
Validation rejects it with a parse error before any execution is attempted -- plan validation never
partially trusts a malformed document.

**Unsafe path (traversal / drive-relative / UNC / device / pipe / reparse).**
Rejected intentionally by the batch path contract -- see
`docs/known_limitations.md#windows-paths`. This is not a bug; it is the documented safe-path
boundary. Use an ordinary relative or absolute path instead.

**Relative path not found.**
File-input paths in a plan are resolved relative to the plan file's own directory, not your current
working directory (`docs/batch_plan.md#4-path-resolution-rules`). Double-check the plan sits where
its relative paths expect it to.

**Unicode and spaces in paths.**
Fully supported for plan, input, and output paths (`docs/known_limitations.md#windows-paths`) -- if
one of these is rejected, that is a genuine bug, not expected behavior.

**Windows path-length issue.**
Paths are bounded (512 characters per path segment in the batch contract;
`docs/stage5a_batch_review.md#reviewed-limits`), and extended-length `\\?\`-prefixed paths are
intentionally not accepted (`docs/known_limitations.md#windows-paths`). Keep your plan/input/output
paths short -- a short root like `C:\mvqc-test\` avoids this entirely.

## Batch execution

**Output collision (`OUTPUT_COLLISION`).**
An output path already exists and is not owned by the current run under the active `overwrite`
policy (`refuse` by default). Either choose a fresh output directory, or explicitly opt into
`overwrite: same_batch` with the correct prior `run_id` -- see
`docs/outputs_and_manifests.md#atomic-publication-and-collision-behavior`.

**Permission-denied output.**
Fails promptly and cleanly with no partial or leftover output
(`docs/known_limitations.md#windows-paths`). Check write access to the chosen output directory.

**Cancelled run.**
Jobs that had not started when cancellation was observed are recorded as `CANCELLED`; jobs already
completed keep their published artifacts. This is expected, cooperative behavior, not a crash --
see `docs/status_vocabulary.md#2-batch-job-status-jobsstatus-in-batch-resultjson`.

**Partial outputs / missing report for a job.**
Check that job's `status` in the manifest first. `INPUT_REJECTED` and `SKIPPED_DEPENDENCY` jobs
never produce a report by design (they never reached analysis) -- this is not a missing-output bug.
See `docs/outputs_and_manifests.md`.

**`RESULT_MANIFEST_INVALID`.**
The selected `batch-result.json` failed contract/JSON validation when opened through the result
browser -- it may be corrupted, hand-edited, or from an incompatible/unsupported contract version.
Do not hand-edit manifest files (`docs/outputs_and_manifests.md#ownership-and-what-not-to-edit`).

**`REPORT_INVALID`.**
A referenced report file failed schema/semantic validation. Check its `schema_version` against
`docs/report_schema.md` before assuming an install/upgrade problem
(`docs/upgrade_guide.md#7-troubleshooting`).

**Cache miss (`CACHE_MISS`).**
No cached snapshot exists yet for the requested record. Use **Fetch**/**Refresh** to populate it
(this is the one action that contacts the network -- see `docs/offline_guarantees.md`), or supply a
local PDBTM pair via `pdbtm_local` instead.

**Cache corruption (`CACHE_CORRUPT`, `CACHE_FORMAT_UNSUPPORTED`).**
The cache fails closed with a clear, typed error rather than silently misreading bad data --
`docs/upgrade_guide.md#7-troubleshooting`. Recovery: use **Clear cached record** for the affected
entry, or delete the cache directory (`%LOCALAPPDATA%\MembraneVisualQC\Cache` or `$MVQC_CACHE_DIR`)
and re-fetch. No automatic cache migration ever occurs (`docs/offline_guarantees.md`).

**Input rejected vs. execution failure.**
These are different job statuses with different implications -- see
`docs/status_vocabulary.md#2-batch-job-status-jobsstatus-in-batch-resultjson`. `INPUT_REJECTED`
means the job's declared input/path/cross-reference failed pre-execution validation and no analysis
ran at all; `ANALYSIS_ERROR` means analysis started and raised a typed, recoverable error. Neither
is a scientific verdict on the underlying structure.

## Reports/results

**Unsupported schema.**
`validate_report()` dispatches by the report's own declared `schema_version` and supports 1.0-1.4
for `single_structure_review` reports; schema 1.5 (`orientation_source_comparison`) is validated
separately. See `docs/report_schema.md` and `docs/compatibility.md#supported-report-schema-versions`.
A report declaring anything else is rejected with a clear, typed error, not a crash.

**Historical schema 1.0.**
Still readable by the current plugin -- schema-1.0 read support was intentionally restored (see
`docs/adr/0001-report-schema-versioning.md` and `tests/fixtures/README.md` for the genuine
historical fixture used to test this).

**Comparison schema 1.5.**
Structurally distinct from schemas 1.0-1.4 (`report_type: orientation_source_comparison`, not
`single_structure_review`) and validated only by
`membrane_vqc.comparison_report.validate_comparison_report`, not the ordinary report validator.

**Missing artifact when browsing a result.**
Reported as availability `MISSING` -- expected if the file was moved or deleted after the run, not
an error. See `docs/status_vocabulary.md#6-result-artifact-availability`.

**Reveal/Open failure.**
The artifact is re-resolved and re-verified immediately before opening; a failure here means its
current bytes no longer match the manifest's recorded identity (`OUTPUT_IDENTITY_CHANGED`) or it
is genuinely missing/unsafe -- see `docs/outputs_and_manifests.md#safe-revealopen-behavior`.

## Networking/cache

See `docs/offline_guarantees.md` for the full, grounded statement of what does and does not touch
the network. In short: only **Fetch**/**Refresh** for PDBTM contacts the network; everything else
(validation, all five batch/single-structure modes when inputs are already local, report/result
inspection) is offline. No automatic cache migration exists between versions
(`docs/compatibility.md#cache-format`) -- a format mismatch fails closed
(`CACHE_FORMAT_UNSUPPORTED`) rather than being silently upgraded or misread.

## Scientific interpretation

- **`REVIEW_ITEMS` is not a biological failure.** It means the configured heuristics flagged
  residues for manual inspection -- not that they are wrong. See
  `docs/status_vocabulary.md#1-single-structure-report-status-summaryoverall_status` and
  `docs/known_limitations.md#scientific-interpretation`.
- **`INPUT_REJECTED` is not a scientific verdict.** It means the job's input/path/cross-reference
  failed pre-execution safety/contract validation; no analysis of the structure occurred at all.
- **Comparison is not source ranking.** `pdbtm_opm_comparison` never selects a preferred source,
  builds a consensus, or produces a biological verdict -- see
  `docs/stage4c_source_comparison.md#scientific-boundary`.
- **Coordinates are never intentionally modified.** Every analysis mode is read-only with respect
  to your structure's atomic coordinates -- see `docs/coordinate_preservation.md`.
