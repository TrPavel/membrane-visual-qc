"""Dialog-level tests for the Stage 4B3 cached-PDBTM GUI workflow.

These construct ``MembraneVQCDialog`` via ``object.__new__`` (bypassing
``__init__``, matching the existing ``test_gui_actions.py`` pattern) and
inject a ``FakeWorker`` whose ``request_*`` signals only *record* what was
requested -- they never auto-deliver a result. Each test then calls the
dialog's own ``_on_*_finished`` handler directly to simulate a worker
completion landing at a chosen, controlled moment. This lets the staleness
guard (matching against ``self._pending_request_id``), the Fetch-vs-Use
separation, and the cancellation/close invalidation contract all be tested
deterministically without any real threading or Qt.
"""

from types import SimpleNamespace

from membrane_vqc import gui


class FakeText:
    def __init__(self, value=""):
        self.value = value
        self.enabled = True

    def text(self):
        return self.value

    def setText(self, value):
        self.value = value

    def setPlainText(self, value):
        self.value = value

    def currentText(self):
        return self.value

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)


class RecordedSignal:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class FakeWorker:
    def __init__(self):
        self.request_inspect = RecordedSignal()
        self.request_fetch = RecordedSignal()
        self.request_use_cached = RecordedSignal()
        self.request_clear = RecordedSignal()


class FakeOperation:
    """Stands in for pdbtm_retrieval.RetrievalOperation in dialog-level tests."""

    def __init__(self):
        self.cancel_calls = 0

    def request_cancel(self):
        self.cancel_calls += 1

    def is_cancelled(self):
        return self.cancel_calls > 0


class FakeMessageBox:
    Yes = "yes"
    No = "no"

    def __init__(self, answer="yes"):
        self.answer = answer
        self.questions = []

    def question(self, parent, title, text):
        self.questions.append((title, text))
        return self.answer

    def warning(self, parent, title, text):
        self.warnings = getattr(self, "warnings", [])
        self.warnings.append((title, text))


def cached_dialog(*, source=gui.PDBTM_SOURCE_CACHED, record_id="1pcr"):
    dialog = object.__new__(gui.MembraneVQCDialog)
    dialog.QtWidgets = SimpleNamespace(QMessageBox=FakeMessageBox())
    dialog.QtGui = None
    dialog.QtCore = None
    dialog.window = object()
    dialog.action_buttons = []
    dialog.orientation_mode = FakeText(gui.PDBTM_MODE)
    dialog.selection = FakeText("all")
    dialog.ligand = FakeText("")
    dialog.cutoff = FakeText("5")
    dialog.summary = FakeText()
    dialog.orientation_source = FakeText("unavailable")
    dialog.orientation_file = FakeText("")
    dialog.pdbtm_json = FakeText("")
    dialog.transformed_pdb = FakeText("")
    dialog.browse_pdbtm_json = FakeText()
    dialog.browse_transformed_pdb = FakeText()
    dialog.biological_assembly = FakeText("")
    dialog.zmin = FakeText("-15")
    dialog.zmax = FakeText("15")
    dialog.pdbtm_source = FakeText(source)
    dialog.cached_record_id = FakeText(record_id)
    dialog.fetch_button = FakeText()
    dialog.cancel_button = FakeText()
    dialog.cache_status = FakeText()
    dialog.cache_metadata = FakeText()
    dialog.use_cached_button = FakeText()
    dialog.open_cache_location_button = FakeText()
    dialog.clear_cached_button = FakeText()

    dialog._session_id = "session"
    dialog._generation = 0
    dialog._request_seq = 0
    dialog._pending_request_id = None
    dialog._pending_use_cached_record_id = None
    dialog._pending_clear_record_id = None
    dialog._retrieval_state = gui.RETRIEVAL_IDLE
    dialog._selection_state = (
        gui.SELECTION_CACHED_UNSELECTED
        if source == gui.PDBTM_SOURCE_CACHED
        else gui.SELECTION_LOCAL_FILES
    )
    dialog._cached_snapshot = None
    dialog._cached_snapshot_record_id = None
    dialog._cached_snapshot_generation = None
    dialog._last_inspect = (None, None)
    dialog._fetch_operations = {}
    dialog._worker = FakeWorker()
    dialog._worker_thread = None
    return dialog


def _snapshot_stub(record_id="1pcr", pair_id="p" * 64, snapshot_id="s" * 64):
    core = SimpleNamespace(
        canonical_record_id=record_id,
        pair_id=pair_id,
        provider_versions=SimpleNamespace(resource_version="1017", software_version="3.2.134"),
        validated_at="2026-07-20T00:00:04.000000Z",
    )
    return SimpleNamespace(snapshot_id=snapshot_id, snapshot_core=core, payloads=(b"a", b"b"))


# --- No implicit network/worker creation ------------------------------------


def test_switching_orientation_modes_never_creates_a_worker():
    dialog = cached_dialog(source=gui.PDBTM_SOURCE_LOCAL)
    dialog._worker = None
    for mode in (gui.LEGACY_MODE, gui.ORIENTATION_FILE_MODE, gui.PDBTM_MODE):
        dialog.orientation_mode.value = mode
        dialog._update_orientation_mode()
    assert dialog._worker is None


def test_dispatch_inspect_is_a_noop_for_local_source():
    dialog = cached_dialog(source=gui.PDBTM_SOURCE_LOCAL)
    dialog._dispatch_inspect()
    assert dialog._worker.request_inspect.calls == []
    assert dialog._pending_request_id is None


def test_invalid_record_id_never_dispatches_inspect():
    dialog = cached_dialog(record_id="not-an-id")
    dialog._dispatch_inspect()
    assert dialog._worker.request_inspect.calls == []


# --- Inspect dispatch and staleness ------------------------------------------


def test_editing_record_id_dispatches_a_fresh_inspect_request():
    dialog = cached_dialog()
    dialog._on_cached_record_id_edited()

    assert len(dialog._worker.request_inspect.calls) == 1
    request_id, record_id = dialog._worker.request_inspect.calls[0]
    assert record_id == "1pcr"
    assert dialog._pending_request_id == request_id
    assert dialog._retrieval_state == gui.RETRIEVAL_INSPECTING_CACHE


def test_stale_inspect_result_is_ignored_after_a_newer_request_supersedes_it():
    dialog = cached_dialog()
    dialog._on_cached_record_id_edited()
    stale_request_id = dialog._pending_request_id

    dialog.cached_record_id.value = "1a0s"
    dialog._on_cached_record_id_edited()
    fresh_request_id = dialog._pending_request_id
    assert fresh_request_id != stale_request_id

    dialog.cache_status.setText("fresh-status")
    dialog._on_inspect_finished(
        stale_request_id,
        SimpleNamespace(
            canonical_record_id="1pcr",
            cache_generation=1,
            record_present=True,
            active_snapshot_id="a" * 64,
            snapshot_count=1,
        ),
    )

    assert dialog.cache_status.value == "fresh-status"
    assert dialog._pending_request_id == fresh_request_id


# --- Fetch never auto-selects -------------------------------------------------


def test_fetch_success_never_auto_selects_or_changes_selection_state():
    dialog = cached_dialog()
    dialog._on_fetch_clicked()
    request_id = dialog._pending_request_id
    assert dialog._retrieval_state == gui.RETRIEVAL_FETCHING

    dialog._on_fetch_finished(request_id, _snapshot_stub())

    assert dialog._retrieval_state == gui.RETRIEVAL_AVAILABLE
    assert dialog._cached_snapshot is None
    assert dialog._selection_state == gui.SELECTION_CACHED_UNSELECTED


def test_fetch_failure_surfaces_the_safe_message():
    dialog = cached_dialog()
    dialog._on_fetch_clicked()
    request_id = dialog._pending_request_id

    from membrane_vqc.pdbtm_worker import WorkerFailure

    dialog._on_fetch_finished(
        request_id,
        WorkerFailure(
            "NETWORK_UNAVAILABLE", "The PDBTM service is currently unreachable.", True, True
        ),
    )

    assert dialog._retrieval_state == gui.RETRIEVAL_FAILED
    assert dialog.cache_status.value == "The PDBTM service is currently unreachable."


# --- Use cached pair selects only the exact validated result ------------------


def test_use_cached_pair_selects_only_after_its_own_result_lands():
    dialog = cached_dialog()
    dialog._on_use_cached_clicked()
    request_id = dialog._pending_request_id
    snapshot = _snapshot_stub()

    dialog._on_use_cached_finished(request_id, snapshot)

    assert dialog._cached_snapshot is snapshot
    assert dialog._cached_snapshot_record_id == "1pcr"
    assert dialog._selection_state == gui.SELECTION_CACHED_SELECTED


def test_stale_use_cached_result_never_selects_a_snapshot():
    dialog = cached_dialog()
    dialog._on_use_cached_clicked()
    stale_request_id = dialog._pending_request_id

    # A newer request (e.g. the user pressed Cancel) supersedes it.
    dialog._invalidate_active_request()

    dialog._on_use_cached_finished(stale_request_id, _snapshot_stub())

    assert dialog._cached_snapshot is None
    assert dialog._selection_state == gui.SELECTION_CACHED_UNSELECTED


def test_use_cached_pair_failure_marks_selection_unavailable():
    dialog = cached_dialog()
    dialog._on_use_cached_clicked()
    request_id = dialog._pending_request_id

    from membrane_vqc.pdbtm_worker import WorkerFailure

    dialog._on_use_cached_finished(
        request_id,
        WorkerFailure("CACHE_MISS", "No validated cached PDBTM pair is available.", True, False),
    )

    assert dialog._selection_state == gui.SELECTION_CACHED_SELECTION_UNAVAILABLE
    assert dialog._cached_snapshot is None


def test_use_cached_pair_failure_clears_a_previously_valid_selection():
    """A re-validation failure must never leave a stale selection usable by Run QC."""
    dialog = cached_dialog()
    dialog._on_use_cached_clicked()
    dialog._on_use_cached_finished(dialog._pending_request_id, _snapshot_stub())
    assert dialog._cached_snapshot is not None

    dialog._on_use_cached_clicked()
    request_id = dialog._pending_request_id

    from membrane_vqc.pdbtm_worker import WorkerFailure

    dialog._on_use_cached_finished(
        request_id,
        WorkerFailure("CACHE_CORRUPT", "Cached pair failed integrity validation.", True, False),
    )

    assert dialog._cached_snapshot is None
    assert dialog._cached_snapshot_record_id is None
    assert dialog._cached_snapshot_generation is None
    assert dialog._selection_state == gui.SELECTION_CACHED_SELECTION_UNAVAILABLE


def test_run_qc_refuses_a_snapshot_left_over_from_a_failed_revalidation(monkeypatch):
    """Defense in depth: Run QC must gate on selection state, not snapshot presence alone."""
    dialog = cached_dialog()
    dialog._cached_snapshot = _snapshot_stub()
    dialog._selection_state = gui.SELECTION_CACHED_SELECTION_UNAVAILABLE
    called = []
    monkeypatch.setattr(gui, "mvqc_check_pdbtm_cached", lambda *a, **k: called.append(1))

    dialog.run_qc()

    assert called == []


def test_fetch_success_discards_a_stale_prior_inspect_generation():
    """A committed Fetch must not let a later Use cached pair attach a pre-fetch generation."""
    dialog = cached_dialog()
    dialog._last_inspect = ("1pcr", 3)

    dialog._on_fetch_clicked()
    dialog._on_fetch_finished(dialog._pending_request_id, _snapshot_stub())

    assert dialog._last_inspect == (None, None)

    dialog._on_use_cached_clicked()
    dialog._on_use_cached_finished(dialog._pending_request_id, _snapshot_stub())

    assert dialog._cached_snapshot_generation is None


def test_changing_record_id_invalidates_the_selected_cached_snapshot():
    dialog = cached_dialog()
    dialog._on_use_cached_clicked()
    dialog._on_use_cached_finished(dialog._pending_request_id, _snapshot_stub())
    assert dialog._cached_snapshot is not None

    dialog.cached_record_id.value = "1a0s"
    dialog._on_cached_record_id_edited()

    assert dialog._cached_snapshot is None
    assert dialog._selection_state == gui.SELECTION_CACHED_UNSELECTED


# --- Cancellation and committed-but-ignored results ---------------------------


def test_cancel_with_no_pending_request_is_a_noop():
    dialog = cached_dialog()
    dialog._on_cancel_clicked()
    assert dialog._fetch_operations == {}


def test_cancel_requests_cooperative_cancellation_and_invalidates_delivery():
    dialog = cached_dialog()
    dialog._on_fetch_clicked()
    request_id = dialog._pending_request_id
    operation = FakeOperation()
    dialog._on_fetch_started(request_id, operation)

    dialog._on_cancel_clicked()

    assert operation.cancel_calls == 1
    assert dialog._pending_request_id is None
    assert dialog._retrieval_state == gui.RETRIEVAL_CANCELLED


def test_committed_result_after_cancel_is_ignored_not_misreported():
    dialog = cached_dialog()
    dialog._on_fetch_clicked()
    request_id = dialog._pending_request_id
    dialog._on_fetch_started(request_id, FakeOperation())
    dialog._on_cancel_clicked()
    assert dialog._retrieval_state == gui.RETRIEVAL_CANCELLED

    # The worker had already committed the cache write before honoring cancel.
    dialog._on_fetch_finished(request_id, _snapshot_stub())

    # A stale delivery must never flip the state back to AVAILABLE nor select.
    assert dialog._retrieval_state == gui.RETRIEVAL_CANCELLED
    assert dialog._cached_snapshot is None


# --- Clear requires confirmation and preserves unrelated state ----------------


def test_clear_cached_record_is_not_dispatched_without_confirmation():
    dialog = cached_dialog()
    dialog.QtWidgets.QMessageBox = FakeMessageBox(answer="no")

    dialog._on_clear_cached_clicked()

    assert dialog._worker.request_clear.calls == []


def test_clear_cached_record_dispatches_after_confirmation():
    dialog = cached_dialog()
    dialog.QtWidgets.QMessageBox = FakeMessageBox(answer="yes")

    dialog._on_clear_cached_clicked()

    assert len(dialog._worker.request_clear.calls) == 1


def test_clear_finished_invalidates_only_the_matching_selected_record():
    dialog = cached_dialog()
    dialog._on_use_cached_clicked()
    dialog._on_use_cached_finished(dialog._pending_request_id, _snapshot_stub(record_id="1pcr"))
    assert dialog._cached_snapshot is not None

    dialog.QtWidgets.QMessageBox = FakeMessageBox(answer="yes")
    dialog._on_clear_cached_clicked()
    request_id = dialog._pending_request_id

    from membrane_vqc.pdbtm_worker import ClearResult

    dialog._on_clear_finished(request_id, ClearResult("1pcr", 1))

    assert dialog._cached_snapshot is None
    assert dialog._selection_state == gui.SELECTION_CACHED_UNSELECTED


# --- Run QC / Show Slab require an explicit Use cached pair selection --------


def test_run_qc_refuses_without_a_selected_cached_snapshot(monkeypatch):
    dialog = cached_dialog()
    called = []
    monkeypatch.setattr(gui, "mvqc_check_pdbtm_cached", lambda *a, **k: called.append(1))

    dialog.run_qc()

    assert called == []
    assert "Use cached pair" in dialog.summary.value


def test_run_qc_uses_the_selected_snapshot_once_available(monkeypatch):
    dialog = cached_dialog()
    snapshot = _snapshot_stub()
    dialog._cached_snapshot = snapshot
    dialog._cached_snapshot_generation = 3
    dialog._selection_state = gui.SELECTION_CACHED_SELECTED
    calls = []

    def fake_check(snap, **kwargs):
        calls.append((snap, kwargs))
        return {"orientation": {"evidence": {}}, "summary": {}}

    monkeypatch.setattr(gui, "mvqc_check_pdbtm_cached", fake_check)
    monkeypatch.setattr(gui, "format_summary", lambda report: "ok")

    dialog.run_qc()

    assert calls[0][0] is snapshot
    assert calls[0][1]["cache_generation"] == 3


def test_show_slab_refuses_without_a_selected_cached_snapshot(monkeypatch):
    dialog = cached_dialog()
    called = []
    monkeypatch.setattr(gui, "mvqc_slab_pdbtm_cached", lambda *a, **k: called.append(1))

    dialog.show_slab()

    assert called == []
    assert "Use cached pair" in dialog.summary.value


def test_show_slab_uses_the_selected_snapshot_once_available(monkeypatch):
    dialog = cached_dialog()
    snapshot = _snapshot_stub()
    dialog._cached_snapshot = snapshot
    dialog._selection_state = gui.SELECTION_CACHED_SELECTED
    calls = []

    def fake_slab(snap, **kwargs):
        calls.append(snap)
        evidence = SimpleNamespace(as_dict=lambda: {"source": {"record_id": "1pcr"}})
        return SimpleNamespace(evidence=evidence)

    monkeypatch.setattr(gui, "mvqc_slab_pdbtm_cached", fake_slab)

    dialog.show_slab()

    assert calls == [snapshot]


# --- Control enable/disable sync ---------------------------------------------


def test_sync_controls_disables_local_widgets_for_cached_source():
    dialog = cached_dialog(source=gui.PDBTM_SOURCE_CACHED)
    dialog._sync_pdbtm_controls()

    assert dialog.pdbtm_json.enabled is False
    assert dialog.transformed_pdb.enabled is False
    assert dialog.fetch_button.enabled is True
    assert dialog.use_cached_button.enabled is True


def test_sync_controls_disables_cached_widgets_for_local_source():
    dialog = cached_dialog(source=gui.PDBTM_SOURCE_LOCAL)
    dialog._sync_pdbtm_controls()

    assert dialog.fetch_button.enabled is False
    assert dialog.cancel_button.enabled is False
    assert dialog.use_cached_button.enabled is False
    assert dialog.clear_cached_button.enabled is False


def test_sync_controls_disables_actions_while_a_request_is_pending():
    dialog = cached_dialog()
    dialog._on_fetch_clicked()

    assert dialog.fetch_button.enabled is False
    assert dialog.cancel_button.enabled is True
    assert dialog.use_cached_button.enabled is False
    assert dialog.clear_cached_button.enabled is False
