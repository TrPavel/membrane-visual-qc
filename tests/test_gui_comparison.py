from pathlib import Path
from types import SimpleNamespace

from membrane_vqc import gui, qc
from membrane_vqc.comparison_worker import ComparisonWorkerFailure
from membrane_vqc.orientation_comparison import ComparableOrientation
from membrane_vqc.orientation_sources import ImportMessage, PayloadDigest, SourceIdentity


class FakeText:
    def __init__(self, value=""):
        self.value = value
        self.enabled = True

    def text(self):
        return self.value

    def currentText(self):
        return self.value

    def setText(self, value):
        self.value = value

    def setPlainText(self, value):
        self.value = value

    def setEnabled(self, value):
        self.enabled = bool(value)


class Signal:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class Operation:
    def __init__(self):
        self.cancelled = 0

    def request_cancel(self):
        self.cancelled += 1


def comparison_dialog(source=gui.PDBTM_SOURCE_LOCAL):
    dialog = object.__new__(gui.MembraneVQCDialog)
    dialog.QtCore = None
    dialog.QtWidgets = SimpleNamespace()
    dialog.window = object()
    dialog._session_id = "session"
    dialog._comparison_generation = 0
    dialog._comparison_request_seq = 0
    dialog._pending_comparison_id = None
    dialog._comparison_operation = None
    dialog._comparison_worker = SimpleNamespace(request_compare=Signal())
    dialog._comparison_thread = None
    dialog._comparison_snapshot = None
    dialog._comparison_result = None
    dialog._comparison_report = None
    dialog._comparison_used_cache = False
    dialog._cached_snapshot = None
    dialog._cached_snapshot_record_id = None
    dialog._cached_snapshot_generation = None
    dialog.selection = FakeText("all")
    dialog.biological_assembly = FakeText("1")
    dialog.pdbtm_json = FakeText("pdbtm.json")
    dialog.transformed_pdb = FakeText("transformed.pdb")
    dialog.comparison_record_id = FakeText("1abc")
    dialog.comparison_pdbtm_source = FakeText(source)
    dialog.comparison_pdbtm_summary = FakeText()
    dialog.comparison_opm_path = FakeText("opm.pdb")
    dialog.comparison_status = FakeText()
    dialog.comparison_metrics = FakeText()
    dialog.comparison_export_path = FakeText("comparison.json")
    dialog.summary = FakeText()
    dialog.compare_button = FakeText()
    dialog.comparison_cancel_button = FakeText()
    dialog.show_both_button = FakeText()
    dialog.export_comparison_button = FakeText()
    dialog.clear_comparison_button = FakeText()
    return dialog


def _snapshot():
    context = SimpleNamespace(model_id=1, biological_assembly="1", coordinate_frame="current")
    atoms = (SimpleNamespace(chain="A"),)
    return SimpleNamespace(structure_context=context, atoms=atoms, coordinate_fingerprint="f" * 64)


def test_compare_is_explicit_and_dispatches_precreated_operation(monkeypatch):
    dialog = comparison_dialog()
    monkeypatch.setattr(gui, "read_local_payload", lambda path, role: role.encode())
    monkeypatch.setattr(gui, "capture_comparison_snapshot", lambda *a, **k: _snapshot())
    monkeypatch.setattr(gui, "ComparisonRequest", lambda *args: args)
    operation = Operation()
    monkeypatch.setattr(gui, "ComparisonOperation", lambda: operation)
    dialog._on_compare_clicked()
    assert len(dialog._comparison_worker.request_compare.calls) == 1
    request_id, request, emitted_operation = dialog._comparison_worker.request_compare.calls[0]
    assert request_id == dialog._pending_comparison_id
    assert request[-1] == "1abc"
    assert emitted_operation is operation


def test_local_comparison_uses_dedicated_id_not_cache_field(monkeypatch):
    dialog = comparison_dialog()
    dialog.cached_record_id = FakeText("")
    monkeypatch.setattr(gui, "read_local_payload", lambda path, role: b"x")
    monkeypatch.setattr(gui, "capture_comparison_snapshot", lambda *a, **k: _snapshot())
    monkeypatch.setattr(gui, "ComparisonRequest", lambda *args: args)
    monkeypatch.setattr(gui, "ComparisonOperation", Operation)
    dialog._on_compare_clicked()
    assert dialog._comparison_worker.request_compare.calls[0][1][-1] == "1abc"


def test_source_change_cancels_and_invalidates_late_result(monkeypatch):
    dialog = comparison_dialog()
    operation = Operation()
    dialog._pending_comparison_id = "old"
    dialog._comparison_operation = operation
    monkeypatch.setattr(gui, "clear_comparison_boundaries", lambda: None)
    dialog._on_comparison_input_changed()
    assert operation.cancelled == 1
    assert dialog._pending_comparison_id is None
    dialog._on_comparison_finished("old", object())
    assert dialog._comparison_result is None


def test_failure_preserves_qc_report_and_standard_state():
    dialog = comparison_dialog()
    dialog._pending_comparison_id = "request"
    sentinel = {"existing": "qc report"}
    previous = qc.LAST_REPORT
    qc.LAST_REPORT = sentinel
    try:
        dialog._on_comparison_finished(
            "request", ComparisonWorkerFailure("SOURCE_INVALID", "Source rejected")
        )
        assert qc.LAST_REPORT is sentinel
        assert dialog.comparison_status.value == "Source rejected"
    finally:
        qc.LAST_REPORT = previous


def test_late_fingerprint_change_discards_result(monkeypatch):
    dialog = comparison_dialog()
    dialog._pending_comparison_id = "request"
    dialog._comparison_snapshot = _snapshot()
    monkeypatch.setattr(gui, "comparison_snapshot_is_current", lambda *a, **k: False)
    monkeypatch.setattr(gui, "clear_comparison_boundaries", lambda: None)
    dialog._on_comparison_finished("request", object())
    assert dialog._comparison_report is None
    assert "coordinates changed" in dialog.comparison_status.value


def test_noncomparable_report_can_export_but_cannot_render():
    dialog = comparison_dialog()
    dialog._comparison_report = {"schema_version": "1.5"}
    dialog._comparison_result = SimpleNamespace(
        pdbtm=SimpleNamespace(status="rejected", membrane=None),
        opm=SimpleNamespace(status="imported", membrane=object()),
    )
    dialog._sync_comparison_controls()
    assert dialog.export_comparison_button.enabled
    assert not dialog.show_both_button.enabled


def test_render_and_clear_touch_only_comparison_ownership(monkeypatch):
    dialog = comparison_dialog()
    dialog._comparison_snapshot = _snapshot()
    dialog._comparison_report = {"schema_version": "1.5"}
    dialog._comparison_result = SimpleNamespace(
        pdbtm=SimpleNamespace(status="imported", membrane="pdbtm"),
        opm=SimpleNamespace(status="imported", membrane="opm"),
    )
    calls = []
    monkeypatch.setattr(gui, "comparison_snapshot_is_current", lambda *a, **k: True)
    monkeypatch.setattr(gui, "show_comparison_boundaries", lambda *a, **k: calls.append("show"))
    monkeypatch.setattr(gui, "clear_comparison_boundaries", lambda: calls.append("clear"))
    dialog._on_show_both_clicked()
    dialog._on_clear_comparison_clicked()
    assert calls == ["show", "clear"]


def test_export_uses_independent_comparison_report(monkeypatch, tmp_path):
    dialog = comparison_dialog()
    dialog._comparison_report = {"schema_version": "1.5"}
    dialog.comparison_export_path.value = str(tmp_path / "comparison.json")
    captured = []
    monkeypatch.setattr(
        gui, "export_comparison_report", lambda report, path: captured.append((report, path))
    )
    dialog._on_export_comparison_clicked()
    assert captured == [(dialog._comparison_report, Path(dialog.comparison_export_path.value))]


def test_close_quits_asynchronously_without_wait_or_terminate():
    dialog = comparison_dialog()

    class Thread:
        def __init__(self):
            self.quit_calls = 0

        def quit(self):
            self.quit_calls += 1

        def wait(self):
            raise AssertionError("wait must not be called")

        def terminate(self):
            raise AssertionError("terminate must not be called")

    thread = Thread()
    dialog._comparison_thread = thread
    dialog._teardown_comparison_worker()
    assert thread.quit_calls == 1


def test_selected_object_identity_uses_full_snapshot_atom_records():
    payload = (
        b"ATOM      1  CA  ALA A   1      0.000   0.000   0.000  1.00 10.00           C\n"
        b"ATOM      2  CA  GLY B   2      1.000   0.000   0.000  1.00 10.00           C\n"
        b"HETATM    3  O   HOH C   3      2.000   0.000   0.000  1.00 10.00           O\n"
    )
    assert gui._snapshot_identity_counts(payload) == (("A", "B"), 2)


def test_rejected_source_still_builds_path_free_report_provenance():
    source = SourceIdentity(
        "OPM",
        "1abc",
        None,
        None,
        None,
        None,
        None,
        (PayloadDigest("opm_pdb", "a" * 64, 12, media_type="chemical/x-pdb"),),
    )
    imported = SimpleNamespace(
        status="rejected",
        evidence=None,
        source=source,
        messages=(ImportMessage("COORDINATE_FRAME_MISMATCH", "No identity match."),),
    )

    result = gui._comparison_report_source(
        "opm", imported, ComparableOrientation("opm", False), None
    )

    assert result.adapter_name == "opm_pdb_offline"
    assert result.record_id == "1abc"
    assert result.comparison_input.applicable is False


def test_early_rejected_pdbtm_source_uses_request_level_identity():
    imported = SimpleNamespace(
        status="rejected",
        evidence=None,
        source=None,
        messages=(ImportMessage("INVALID_JSON", "PDBTM JSON is malformed."),),
    )
    fallback = (
        gui.ComparisonPayloadDigest("pdbtm_json", "a" * 64, 8, "application/json"),
        gui.ComparisonPayloadDigest("transformed_pdb", "b" * 64, 12, "chemical/x-pdb"),
    )

    result = gui._comparison_report_source(
        "pdbtm",
        imported,
        ComparableOrientation("pdbtm", False),
        None,
        fallback_record_id="1abc",
        fallback_payloads=fallback,
    )

    assert result.provider_name == "PDBTM"
    assert result.record_id == "1abc"
    assert result.payloads == fallback
