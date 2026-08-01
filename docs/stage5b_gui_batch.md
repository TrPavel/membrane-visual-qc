# Stage 5B GUI batch review

> **Technical reference.** This document remains the detailed reference for the **Batch review**
> dialog's controls and state machine, linked from [docs/index.md](index.md) -- for a task-oriented
> introduction, start with [docs/tutorial.md](tutorial.md#running-many-jobs-at-once-batch-review)
> or [docs/five_mode_walkthrough.md](five_mode_walkthrough.md).

Stage 5B adds a dedicated **Batch review** tab to the existing dialog. It consumes the unchanged
`mvqc-batch-plan-1.0` and `mvqc-batch-result-1.0` contracts. It is a safe loader, validator, queue
runner, and result viewer; it is not a visual plan editor and its operational states are not a
biological verdict.

## Controls and state

The Plan group contains an explicit plan path, Browse, Validate, contract status, SHA-256, job
count, failure policy, and overwrite policy. Output requires an explicit local directory. Execution
shows Run, Cancel, progress, completed/total, current job, current mode, overall state, and a
bounded status. The eight queue columns are Order, Job ID, Mode, Input summary, Status, Report
schema, Review items, and Error code.

The state model is `IDLE`, `VALIDATING`, `READY`, `RUNNING`, `CANCELLING`, `COMPLETED`,
`CANCELLED`, and `FAILED`. Run is enabled only for the current immutable validated-plan snapshot
and an explicit output. Editing the plan invalidates that snapshot. Validate never executes.
Per-dialog session, generation, request, and delivery identities prevent an older or closed run
from updating a newer visible queue.

## Main-thread pump and cancellation

`BatchRunSession` is shared by the synchronous Stage 5A runner and the GUI. The GUI starts the
session, executes at most one job for each single-shot zero-delay Qt timer delivery, and schedules
the next delivery only after that job returns. All PyMOL operations therefore stay serial and on
the PyMOL/Qt main thread. No scientific work runs in a thread, subprocess, nested event loop, or
`QApplication.processEvents()` product loop.

Cancel enters `CANCELLING` immediately and sets a cooperative token. The current operation follows
its existing safe lifecycle; no later job begins once cancellation is observed. Remaining jobs are
finalized with the Stage 5A status, and the manifest is published atomically. Closing requests the
same cancellation, invalidates GUI delivery immediately, and never blocks or forcibly terminates a
thread. The accepted Stage 5A command behavior for plugin-owned state and `LAST_REPORT` remains
unchanged; batch results are presented only in the Batch tab and are not copied into single-run
summary widgets.

## History and verified results

History contains at most 20 current-session entries: display plan name and digest, manifest path in
memory, operational status, completion time, counts, and identity-core digest. Startup performs no
scan or discovery. Clearing or eviction changes GUI memory only and never deletes an output.

Opening an explicit result manifest applies bounded UTF-8/JSON and contract validation, aggregate
and identity-core checks, safe relative-path and Windows device/reparse checks, size/SHA-256 checks,
and the existing structural and semantic report validators. Missing outputs are shown unavailable;
changed or unsafe outputs reject the bundle. Browsing never loads a structure, calls PyMOL, or sets
`qc.LAST_REPORT`, and raw unbounded JSON is not rendered.

Manifest, output-directory, report, and CSV opening is always an explicit button action through a
Qt local-file URL. The manifest or artifact is re-resolved and revalidated immediately before it
is opened. Shell command construction is not used.

## Boundaries

Dialog construction, validation, execution, cancellation, history, browsing, and reveal are
network-free. Cached jobs consume only the plan's exact predeclared snapshot; a missing snapshot
fails closed. There is no hidden provider fallback, OPM retrieval, persistent path database, cache
inventory, garbage collection, new provider, automatic source choice, ranking, consensus, or
biological verdict. Stage 5C has not started.
