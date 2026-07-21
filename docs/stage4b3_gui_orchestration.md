# Stage 4B3 GUI and PyMOL worker orchestration

Status: implemented; automated (fake-Qt and Qt-free) tests validated. Exact-artifact graphical and
live-provider acceptance are recorded separately in `docs/stage4b4_exact_acceptance.md`.

## Scope and boundaries

Stage 4B3 adds an explicit, GUI-driven way to fetch and use a cached PDBTM pair from inside the
existing **PDBTM offline pair** orientation mode. Cached retrieval is a subordinate source inside
that mode, not a fourth mode; the three orientation modes (**Legacy global-z**, **Planar
orientation file**, **PDBTM offline pair**) are unchanged, and **Local files** remains the default
PDBTM source. Stage 4B3 does not add OPM/RCSB retrieval, arbitrary URLs, automatic source
selection, automatic fitting/alignment, replacement or transformation of the user's loaded object,
periodic refresh, retries, redirects, proxy/PAC/CONNECT support, telemetry, cache migration/GC,
batch processing, biological-correctness verdicts, or Stage 4C source comparison.

## Architecture

```text
GUI (MembraneVQCDialog, main/Qt thread)
    |  session UUID, generation counter, per-request ID, cache/retrieval state machines
    v
pdbtm_gui_worker.PdbtmAsyncWorker (QObject, moved to its own QThread)
    |  request_inspect / request_fetch / request_use_cached / request_clear / request_cancel
    |  (Qt "Auto" connections queue automatically because the worker lives on a different thread)
    v
pdbtm_worker.PdbtmWorkerOrchestrator (Qt-free, pure Python)
    |  inspect() / fetch() / use_cached_pair() / clear()
    v
Stage 4B1 stack: PdbtmProviderClient / PdbtmHttpsTransport / PdbtmCacheRepository /
                 retrieve_validate_and_commit()
```

`membrane_vqc/pdbtm_worker.py` never imports PyMOL or Qt and is fully unit-testable with fakes; it
is the only module that may cause network access, and only via `fetch()`. It never reads or writes
a widget, never calls a PyMOL `cmd` method, and never tests applicability against a live object.

`membrane_vqc/pdbtm_gui_worker.py` imports Qt only inside `make_worker_class(QtCore)`, called
lazily by the dialog exactly like `gui.show_dialog`'s existing `from pymol.Qt import ...` pattern,
so the module stays importable without any Qt binding installed. `PdbtmAsyncWorker` exposes both
"finished" signals (`inspect_finished`, `fetch_finished`, `use_cached_finished`, `clear_finished`)
and self-connected "request" trigger signals (`request_inspect`, `request_fetch`,
`request_use_cached`, `request_clear`, `request_cancel`); the dialog only ever calls
`worker.request_*.emit(...)`, never a `_run_*`/private method directly, so the work is guaranteed
to execute on the worker's own thread once it has been `moveToThread`-ed there.

Cancellation is **not** delivered as a queued signal into the worker thread. `_run_fetch` blocks
that thread's event loop for the fetch's entire duration (it is one synchronous call into the
Qt-free orchestrator), so a cross-thread signal aimed at that thread would simply queue up behind
the blocking call and only be processed once the fetch has already finished. Instead,
`fetch_started` hands the GUI a direct reference to the shared, thread-safe `RetrievalOperation`
the moment a fetch begins; the GUI calls `operation.request_cancel()` on it directly (a plain,
lock-guarded Python method call, not a Qt dispatch), which the already-blocked fetch call observes
at its next internal cooperative checkpoint. This exact Stage 4B1 primitive is otherwise unmodified.

Every `.connect()` call for a cross-thread signal in this module and in `gui.py`'s `_ensure_worker`
explicitly passes `QtCore.Qt.QueuedConnection` rather than relying on `Qt.AutoConnection`.
Headless real-Qt smoke testing against the bundled Incentive PyMOL PyQt5 build (see
`docs/stage4b4_exact_acceptance.md`) found that `Qt.AutoConnection`'s cross-thread detection did
not reliably resolve to a queued connection for these self-connected-signal / plain-Python-slot
patterns: `emit()` blocked the calling thread for the slot's full duration instead of posting and
returning immediately, which would have frozen the entire PyMOL GUI for the duration of every
Fetch/Inspect/Use-cached-pair/Clear call -- silently defeating the whole point of the worker
thread. This was caught only by an actual headless `QThread` run, not by static review or the
synchronous fake-Qt unit tests (which cannot observe connection-type semantics at all). Being
explicit about the connection type removes the ambiguity regardless of binding/version quirks.

## GUI controls

Inside the existing PDBTM panel: `PDBTM source` (`Local files` / `Validated cache`), `Canonical
record ID`, `Fetch / Refresh`, `Cancel`, `Cache status`, `Cache metadata` (record ID; abbreviated
active snapshot ID; abbreviated pair ID; provider resource/software versions; validated-at time;
a fixed self-consistency-only validation statement -- never an age-derived "fresh" label), `Use
cached pair`, `Open cache location`, and `Clear cached record` (the current task's wording for the
design document's "Clear selected record" -- same control, aligned to the accepted final naming).
None of these ever display an absolute filesystem path, username, IP address, proxy detail,
credential, or raw exception text; `Open cache location` reveals the cache directory only as a
direct explicit action (via `QDesktopServices.openUrl`) and never logs, persists, or reports the
path.

## Network authorization

Only `Fetch / Refresh` ever causes network access. Package import, command registration, plugin
startup, opening/closing the dialog, changing orientation mode, editing the record ID, inspecting
cache status, `Use cached pair`, Run QC, Show Slab, Export JSON, local-file workflows, `Clear
cached record`, and `Open cache location` perform zero network requests -- verified by
`tests/test_stage4b3_package_safety.py` (import-time) and the GUI dialog tests (action-time, via a
`FakeWorker` that only ever records what was requested). Automatic, non-network cache-status
inspection is dispatched on record-ID edits and PDBTM-source changes (still never on dialog open,
since the default source is `Local files`); it never authorizes a fetch.

## Session/request/stale-result model

Each dialog owns a session UUID (`uuid.uuid4().hex`), a monotonically increasing generation
counter, and a per-request ID formed as `f"{session}:{generation}:{seq}"`. A worker completion
(`_on_*_finished`) is applied only when its request ID still equals `self._pending_request_id`;
editing the record ID, changing the PDBTM source, pressing Cancel, or closing the dialog all bump
the generation and clear the pending request ID first, so a result that arrives afterward is
compared against a value it can never match and is silently dropped -- it never selects a cached
source, runs QC, renders a slab, changes a PyMOL object, sets `qc.LAST_REPORT`, exports a report, or
overwrites a newer status message. This preserves Stage 4B1's own commit-vs-delivery distinction
exactly: a fetch that wins the cache commit after the GUI already invalidated its delivery is not
retroactively rolled back, but the GUI also never claims it was applied.

## GUI state machines

Retrieval state: `IDLE` / `INSPECTING_CACHE` / `FETCHING` / `CANCELLING` / `AVAILABLE` / `FAILED` /
`CANCELLED`. Selection state (independent): `LOCAL_FILES` / `CACHED_UNSELECTED` /
`CACHED_SELECTED` / `CACHED_SELECTION_UNAVAILABLE`.

Fetch success transitions retrieval state to `AVAILABLE` and displays that a new snapshot exists,
but never touches selection state, never selects the snapshot, and never runs QC or renders a
slab. `Use cached pair` performs an integrity read plus semantic revalidation in the worker
(`PdbtmCacheRepository.read_active`, the same call Stage 4B1 already exposes) and, only once its
own non-stale result lands, selects that exact validated in-memory `CachedSnapshot` -- never
running QC or Show Slab automatically. Changing the record ID invalidates any selected cached
snapshot (`CACHED_UNSELECTED`); clearing the selected record invalidates the cached selection but
never clears a PyMOL object or an already-generated report.

Pressing `Cancel` requests cooperative cancellation and immediately invalidates delivery; because a
truly synchronous "did cancellation win against the commit" confirmation would require blocking the
GUI thread (explicitly disallowed), the GUI shows `CANCELLED` as soon as cancellation is requested
-- an intentional simplification of the design document's "may show Cancelling... until the worker
confirms" language, never fatal to correctness because the underlying invalidation guard (above)
makes a late commit's result unobservable regardless of which label is shown.

Consistent with Stage 4B1's own documented limitation ("DNS resolution cannot be guaranteed to
stop immediately in CPython 3.10... the worker may exit only at the bounded network deadline; this
limitation must be displayed honestly rather than using unsafe thread termination"), pressing
Cancel does not guarantee the in-flight network call itself returns early -- only that the GUI
immediately treats the request as cancelled and ignores whatever the fetch eventually returns.
Headless smoke testing observed that, because `fetch_started` cannot be delivered to the GUI until
the worker thread's single blocking `_run_fetch` call returns some measure of control to Qt's
dispatch machinery, `operation.request_cancel()` may not reach the shared `RetrievalOperation`
until close to when the fetch would have finished naturally anyway -- i.e. cancellation is
reliably correct at the GUI/state-machine level (a stale result is always ignored) but is not a
reliable way to shorten an in-flight fetch's wall-clock duration. This is a pre-existing, accepted
Stage 4B1 property, not a Stage 4B3 regression; see `docs/stage4b4_exact_acceptance.md` for the
exact headless observation and why it could not be more precisely characterized without genuine
interactive PyMOL access.

## Cached Run QC / Show Slab

Once `Validated cache` is selected and `Use cached pair` has produced a validated snapshot, `Run
QC`/`Show Slab` call `commands.mvqc_check_pdbtm_cached()` / `mvqc_slab_pdbtm_cached()` directly
(internal helpers -- deliberately not new registered PyMOL commands, since they exist only to give
the GUI's existing buttons a cached-source code path, not for command-line symmetry). Both:

- perform no network access and no hidden cache fallback (they operate only on the exact validated
  `CachedSnapshot` object already held in memory by the dialog, from a controlled prior `Use cached
  pair` call);
- call `pdbtm_pymol.resolve_pdbtm_from_payloads()` -- the in-memory-bytes sibling of the existing
  `resolve_pdbtm_from_pymol()` -- to establish current-object applicability against the live PyMOL
  object on the main thread, reusing `structure_context_from_pymol()` and `import_pdbtm_orientation()`
  unchanged;
- preserve the user's input coordinates and perform no fit/align/transform/replacement;
- retain the existing full stale-plugin-output cleanup (`clear_owned()` before and, on failure,
  after; `qc.LAST_REPORT` reset before the attempt).

`mvqc_check_pdbtm_cached()` additionally calls `pdbtm_report_provenance.build_pdbtm_acquisition_provenance()`
on the same snapshot and passes it to `qc.run_check_with_membrane(pdbtm_acquisition=...)`
(`qc.run_check_with_membrane` gained this one pass-through parameter; `report.build_report()` and
its schema-selection ladder were already added, unused, by Stage 4B2). The resulting report
therefore contains both `orientation.evidence` (current-object applicability, Stage 4A2) and
`orientation.acquisition` (cache provenance, Stage 4B2) and is schema 1.4 -- the first time both
blocks appear together in a real, non-synthetic call path. `object_applicability.established` is
always `false` in the acquisition block: the acquisition and evidence facts are independently true
but never conflated. Local PDBTM file workflows (`mvqc_check_pdbtm`/`mvqc_slab_pdbtm`) are entirely
unchanged and continue to emit schema 1.3.

## Tests

`tests/test_pdbtm_worker.py` (Qt-free orchestrator, fakes for the cache repository/provider),
`tests/test_pdbtm_gui_worker.py` (fake-Qt request routing, failure conversion, cancellation),
`tests/test_gui_pdbtm_cached.py` (dialog state machine, staleness guard, Fetch-vs-Use separation,
Cancel/committed-result-ignored, Clear confirmation, control enable/disable), and
`tests/test_commands_pdbtm_cached.py` (end-to-end schema-1.4 report through a real Stage 4B1 cache
and Stage 4B2 conversion) cover this stage without any real Qt, PyMOL, or network dependency.
`tests/test_stage4b3_package_safety.py` proves `pdbtm_worker.py`/`pdbtm_gui_worker.py`/`gui.py`
import without opening a socket or requiring PyQt5/PySide/pymol.

## Deferred work

Stage 4B4 (exact-artifact graphical and live-provider acceptance) and Stage 4C have not started as
functionality; see `docs/stage4b4_exact_acceptance.md` and `docs/development_state.md` for their
current status.
