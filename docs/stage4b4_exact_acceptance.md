# Stage 4B4 exact-artifact acceptance

Status: partially complete. Every item achievable without interactive desktop GUI automation was
run against the exact final PR head's CI artifact and passed. Literal mouse-driven Plugin Manager
installation, a full interactive GUI restart, and on-screen screenshot confirmation could not be
performed by this session (see "Capability boundary" below) and are recorded as not performed
rather than fabricated.

## Accepted environment and artifact

- OS: Windows 10 build 26200
- PyMOL: Incentive PyMOL 3.1.8, installed at `%LOCALAPPDATA%\Schrodinger\PyMOL2`; bundled CPython
  3.10.20 (`python.exe` at the install root)
- Final PR head: `9ae38be6b6e5ffe89c40981b6a4cc277d3ad13bf`
- CI artifact (push workflow run [29853518696](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29853518696)):
  artifact ID `8504333680`, outer archive digest
  `sha256:1f62a0be998475d9a0612e1c8329e9c26bd661a215a7a6fc90a959ae03ed1f75`, 428,758 bytes
- CI artifact (pull_request workflow run [29853522061](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29853522061)):
  artifact ID `8504336725`, outer archive digest
  `sha256:998ef17c4835578148ba9e4838baaa5d6d45d6c791e0bafed2bbf5fd304f8e2e`, 428,773 bytes
- Both outer artifacts were downloaded directly via the GitHub API (not `gh run download`'s
  auto-extraction) and their SHA-256 independently recomputed to match the API-reported digest
  exactly, for both runs.
- Inner Plugin ZIP, extracted from **both** independent CI runs: `MembraneVisualQC-0.5.0.dev0.zip`,
  **110,358 bytes**, SHA-256 **`5ad626ef12e72be4807ad15ef34f39595ca76b1addc1c19c6c2f8e5487c400c1`**
  -- byte-identical across the two independently-built CI artifacts, confirming genuine
  cross-run determinism of the exact artifact tested below (not merely a local rebuild).

## Capability boundary

This session has no desktop GUI automation tool (no mouse/keyboard/screenshot driver for native
Windows applications) -- only a web browser pane and a shell are available. This means the
literal, mouse-driven steps of the acceptance checklist below (installing the exact ZIP through
the PyMOL **Plugin Manager** dialog, performing a full PyMOL GUI restart, and taking genuine
on-screen screenshots) cannot be performed by this session. Those items are marked **NOT PERFORMED
(tool capability)** below rather than fabricated.

Where the *underlying production code path* can be genuinely exercised without mouse/screenshot
interaction -- by running the bundled PyMOL interpreter's real Python headlessly, including with
`QT_QPA_PLATFORM=offscreen` for a real (non-fake) `QApplication`/`QThread`/signal stack -- that was
done directly against the exact extracted CI artifact (not the mutable local checkout) and is
recorded as a genuine, non-mouse-driven PASS/FAIL below.

## GUI acceptance (regression)

| Item | Result |
|---|---|
| Plugin installed via Plugin Manager, full restart | NOT PERFORMED (tool capability) |
| Dialog opens, correct Unicode rendering | NOT PERFORMED (tool capability) |
| All 3 orientation modes selectable | NOT PERFORMED (tool capability) |
| Legacy global-z regression | NOT PERFORMED (tool capability) |
| Planar orientation file regression | NOT PERFORMED (tool capability) |
| Local PDBTM offline mode regression | NOT PERFORMED (tool capability) |
| Run QC / Show Slab / Colour Hydropathy / Ligand Shell / Export JSON | NOT PERFORMED (tool capability) |
| Wrong-pair and coordinate-frame-mismatch cleanup | NOT PERFORMED (tool capability) |
| Input coordinates preserved | NOT PERFORMED (tool capability) |

These regressions are covered instead by the retained automated suite (`tests/test_pymol_lifecycle.py`,
`tests/test_pymol_orientation.py`, `tests/test_gui_actions.py`, `tests/test_pdbtm_pymol.py`, and this
stage's own `tests/test_gui_pdbtm_cached.py`/`tests/test_commands_pdbtm_cached.py`), which exercise
the identical production code paths (including the bundled Incentive PyMOL Python interpreter for
non-Qt logic, in CI) without requiring mouse-driven interaction, and by the headless real-Qt runs
below for the parts genuine Qt threading behavior could actually be exercised.

## Live fetch acceptance -- PASS

Run directly against the exact extracted CI artifact (`.local/stage4b4-extracted/membrane_vqc`,
not the local checkout) using the bundled PyMOL interpreter, via `PdbtmWorkerOrchestrator.fetch()`
(the same call the GUI's Fetch/Refresh button makes) with `http.client.HTTPSConnection.request`
instrumented to count and record every outbound call, for canonical record `1pcr`:

- Exactly **2** GET requests, in order: `pdbtm.unitmp.org` `/api/v1/entry/1pcr.json`, then
  `pdbtm.unitmp.org` `/api/v1/entry/1pcr.trpdb`. Zero retries, zero redirects, no proxy/CONNECT.
- `pdbtm_json` payload: 283,537 bytes, SHA-256
  `38b2f724c4271a00bf2b83aa16015783610178f18d8954a88cb932b9152f36e0` -- exact match to the expected
  identity.
- `transformed_pdb` payload: 628,434 bytes, SHA-256
  `7e52525ff397e4bfa5900e602f39753628e3b1408d513a3d0d76928c0fd10698` -- exact match.
- Provider versions recorded: `resource_version=1017`, `software_version=3.2.134`.
- Adapter validation, cache commit, and pair/snapshot identity all succeeded
  (`pair_id=99b69dbd1b6c813dafb045747af410baade7001dfea9af905705728fa8e82c52`).
- No local path or unsafe transport detail is present in any of the recorded evidence (the
  instrumentation only records host/method/path, matching what the production transport itself
  is allowed to log).
- A second live refresh was deliberately not performed (refresh-replacement semantics are already
  covered by deterministic fake/loopback tests in the retained suite, per policy).

## Cached offline acceptance -- PASS

Continuing in the same process, immediately after the live fetch: `socket.socket` was replaced
with a function that raises on any call, then, entirely offline:

- `PdbtmWorkerOrchestrator.use_cached_pair("1pcr")` (the exact call behind the GUI's `Use cached
  pair` button) succeeded, returning payloads byte-identical to the just-fetched live pair.
- Current-object applicability was established fully offline via `import_pdbtm_orientation` against
  the exact cached bytes (using the fetched transformed-PDB bytes as the loaded "object" so the
  identity-frame match is deterministic without needing a separately obtained structure file --
  this exercises the real production `resolve_pdbtm_from_payloads`/`import_pdbtm_orientation`
  chain, not a mock).
- A schema-1.4 report was built fully offline via the real `qc.run_check_with_membrane(...,
  pdbtm_acquisition=...)`, containing **both** `orientation.evidence` and `orientation.acquisition`;
  `object_applicability` is `{"established": false, "scope": "not_evaluated", ...}`, correctly never
  claiming the cache-side self-consistency check establishes object applicability.
- The report was exported (`export_report`) and re-validated (`validate_report`) fully offline:
  13,955-byte JSON, SHA-256 `767f0699190fedb289df03a8177770632d71544367cfd82c647da751deebb688`
  (plus its CSV sibling), matching schema 1.4.
- `PdbtmWorkerOrchestrator.clear("1pcr")` (the exact call behind `Clear cached record`) succeeded,
  tombstone generation 2.
- A subsequent `use_cached_pair("1pcr")` correctly raised `Stage4BError` `CACHE_MISS` -- fully
  offline, no silent fallback, no network access attempted to detect the miss.
- No socket was ever opened during this entire phase (enforced by the raising stub, not merely
  unobserved).

Local-file PDBTM workflows continuing to emit schema 1.3 (unaffected by any of this) is verified by
the retained automated suite, not re-run manually here.

## Graphical cancellation/lifecycle acceptance -- PASS, with one finding fixed and one documented

Run headlessly with `QT_QPA_PLATFORM=offscreen` against the exact extracted CI artifact, using a
real `QApplication`/`QThread`/`PdbtmAsyncWorker` (not the synchronous fake-Qt used by ordinary unit
tests) and a controlled fake/slow orchestrator (never the live provider, per policy):

**Finding, fixed on this branch before this acceptance run:** the first headless run (against an
earlier commit on this same PR) revealed that `Qt.AutoConnection`'s cross-thread detection did not
reliably resolve to a queued connection for `PdbtmAsyncWorker`'s self-connected-signal patterns
against the bundled PyQt5 build -- `worker.request_fetch.emit(...)` blocked the calling (GUI) thread
for the full duration of the fetch instead of posting and returning immediately, which would have
frozen the entire PyMOL GUI on every Fetch/Inspect/Use-cached-pair/Clear action. It also revealed
that routing Cancel through a queued signal into the worker thread was structurally unable to
interrupt an in-flight fetch, since that thread's event loop is blocked for the fetch's entire
duration. Both were fixed (explicit `QtCore.Qt.QueuedConnection` on every cross-thread connection;
`fetch_started(request_id, operation)` hands the GUI a direct, thread-safe operation reference so
Cancel calls `operation.request_cancel()` directly rather than via Qt dispatch) and are described in
`docs/stage4b3_gui_orchestration.md`. This exact re-run, against the final artifact identified
above, confirms the fix:

- `worker.request_fetch.emit(...)` now returns in ~16ms regardless of the fetch's duration (measured
  directly: emit-to-return elapsed time is independent of a 0.5s fake fetch delay) -- the GUI thread
  is never frozen.
- Cancel-while-fetching: the worker thread stops cleanly after `thread.quit()`/no `wait()`-blocking
  teardown; exactly one `fetch_finished` delivery is received; no crash, no
  "QThread: Destroyed while thread is still running" abort (the exact failure mode an earlier,
  already-fixed version of `_teardown_worker` was vulnerable to).
- Dialog-close-during-retrieval: cancelling the operation directly and calling `thread.quit()`
  without a blocking `wait()`, then cooperatively pumping the main thread's event loop, allows the
  worker thread to stop within the bounded observation window every time -- no hang.

**Remaining documented nuance, not a regression:** cancellation reliably makes the GUI ignore
whatever the fetch eventually returns (the state-machine/staleness guarantee holds), but it does
not reliably shorten the fetch's own wall-clock duration in this headless harness -- consistent
with Stage 4B1's own accepted design statement that "the worker may exit only at the bounded
network deadline." Whether this is exactly reproduced during real interactive use (as opposed to a
bare-script `QEventLoop`) could not be more precisely characterized without genuine interactive
PyMOL GUI access, which this session does not have.

## Network failure diagnostic policy

Not invoked: outbound HTTPS to `pdbtm.unitmp.org` was reachable throughout testing; no production
code was weakened, no retry/proxy/insecure-TLS logic was added, and no code was modified merely to
compensate for a connectivity concern.

## Summary

| Acceptance area | Result |
|---|---|
| Outer CI artifact digest (2 independent runs) | PASS -- verified byte-identical |
| Inner Plugin ZIP identity (2 independent runs) | PASS -- verified byte-identical |
| GUI regression (mouse-driven) | NOT PERFORMED (tool capability) |
| Live fetch (bounded, `1pcr`) | PASS |
| Cached offline use/QC/export/clear | PASS |
| Graphical cancellation/lifecycle (headless real Qt) | PASS (after fixing 2 real defects found by this exact testing) |
