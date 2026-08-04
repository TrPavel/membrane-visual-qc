"""Real PyQt5 offscreen checks for the v0.9.0 UI/UX polish additions.

Mirrors the existing test_batch_gui_real_qt.py pattern: skip entirely if PyQt5 is not
installed, run against the offscreen platform plugin otherwise. These tests check the new
*presentation* additions specifically (section headers, primary-button styling, group-title
styling, and that a COMPLETED_WITH_ERRORS batch outcome is visually distinguishable from a
FAILED_FAST one) -- not scientific behavior, which the rest of the suite already covers.
"""

from __future__ import annotations

import os
from pathlib import Path
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtCore = pytest.importorskip("PyQt5.QtCore")
QtGui = pytest.importorskip("PyQt5.QtGui")
QtWidgets = pytest.importorskip("PyQt5.QtWidgets")

from membrane_vqc import ui_theme  # noqa: E402
from membrane_vqc.batch_gui import FAILED, BatchReviewPanel  # noqa: E402
from membrane_vqc.gui import LEGACY_MODE, ORIENTATION_FILE_MODE, PDBTM_MODE  # noqa: E402
from membrane_vqc.gui import MembraneVQCDialog, _headline_for_result  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Created once, at import time, and kept alive for the whole test module: PyQt5 requires exactly
# one QApplication per process, and letting a per-test local variable go out of scope at the end
# of each test function (as a bare `QtWidgets.QApplication.instance() or QtWidgets.QApplication([])`
# call would) lets Python garbage-collect it, tearing down Qt mid-session and crashing the next
# test's widget construction.
_APPLICATION = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_real_qt_primary_actions_are_styled_and_secondary_actions_are_not():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)

    run_qc, show_slab, colour, ligand_shell, export_json = dialog.action_buttons
    assert run_qc.text() == "Run QC"
    assert export_json.text() == "Export JSON"
    assert run_qc.styleSheet() == ui_theme.PRIMARY_BUTTON_QSS
    for secondary in (show_slab, colour, ligand_shell):
        assert secondary.styleSheet() == ""
    # Export JSON starts disabled and unstyled -- it only becomes the primary action once a
    # result actually exists to export (see _sync_result_actions).
    assert export_json.styleSheet() == ""
    assert export_json.isEnabled() is False
    assert dialog.compare_button.styleSheet() == ui_theme.PRIMARY_BUTTON_QSS
    assert dialog.comparison_cancel_button.styleSheet() == ""

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_export_json_becomes_primary_once_a_result_exists():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
    export_json = dialog.action_buttons[-1]
    assert export_json.isEnabled() is False

    dialog._last_result_available = True
    dialog._sync_result_actions()
    assert export_json.isEnabled() is True
    assert export_json.styleSheet() == ui_theme.PRIMARY_BUTTON_QSS

    dialog._last_result_available = False
    dialog._sync_result_actions()
    assert export_json.isEnabled() is False
    assert export_json.styleSheet() == ""

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_single_structure_tab_has_workflow_group_titles():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)

    titles = {
        box.title()
        for box in dialog.single_page.findChildren(QtWidgets.QGroupBox)
        if box.styleSheet() == ui_theme.GROUP_TITLE_QSS
    }
    for expected in (
        "Structure & mode",
        "Orientation source",
        "Analysis options",
        "Advanced analysis (optional)",
        "Run",
        "Results",
        "Source comparison (optional)",
    ):
        assert expected in titles

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_orientation_mode_hides_irrelevant_rows():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
    dialog.window.show()
    QtWidgets.QApplication.processEvents()

    dialog.orientation_mode.setCurrentText(LEGACY_MODE)
    QtWidgets.QApplication.processEvents()
    assert dialog.zmin.isVisible() is True
    assert dialog.zmax.isVisible() is True
    assert dialog.orientation_file.isVisible() is False
    assert dialog.pdbtm_json.isVisible() is False

    dialog.orientation_mode.setCurrentText(ORIENTATION_FILE_MODE)
    QtWidgets.QApplication.processEvents()
    assert dialog.zmin.isVisible() is False
    assert dialog.orientation_file.isVisible() is True
    assert dialog.pdbtm_json.isVisible() is False

    dialog.orientation_mode.setCurrentText(PDBTM_MODE)
    QtWidgets.QApplication.processEvents()
    assert dialog.orientation_file.isVisible() is False
    assert dialog.pdbtm_json.isVisible() is True  # local source is the PDBTM-mode default
    assert dialog.pdbtm_source.isVisible() is True
    assert dialog.cache_status.isVisible() is False  # cache-only rows stay hidden for local

    dialog.pdbtm_source.setCurrentText("Validated cache")
    QtWidgets.QApplication.processEvents()
    assert dialog.pdbtm_json.isVisible() is False
    assert dialog.cache_status.isVisible() is True

    # Always visible regardless of mode.
    assert dialog.orientation_source.isVisible() is True

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def _orientation_group(dialog):
    return next(
        box
        for box in dialog.single_page.findChildren(QtWidgets.QGroupBox)
        if box.title() == "Orientation source"
    )


def test_real_qt_hidden_orientation_rows_do_not_reserve_height():
    """Regression test for the real bug this refinement pass fixed: hiding QFormLayout rows
    via setVisible() alone leaves each hidden row's inter-row spacing reserved on this exact
    PyQt5 5.15.11/Qt 5.15.15 build (confirmed empirically: ~6px per hidden row, invisible with
    one hidden row but a large, clearly visible gap with the ~10 this group can hide at once).
    The fix groups each mode's fields into its own QWidget container and toggles whole
    containers, which collapses with zero residual height -- this test pins that fact."""
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
    dialog.window.show()
    QtWidgets.QApplication.processEvents()
    group = _orientation_group(dialog)

    dialog.orientation_mode.setCurrentText(LEGACY_MODE)
    QtWidgets.QApplication.processEvents()
    legacy_height = group.sizeHint().height()

    # Build a from-scratch reference group containing only what Legacy mode actually shows
    # (helper text, Resolved orientation, zmin, zmax) to establish the true minimal height.
    reference = QtWidgets.QGroupBox("Orientation source")
    reference_layout = QtWidgets.QFormLayout(reference)
    helper = QtWidgets.QLabel("The fields below adapt to the selected orientation mode.")
    helper.setWordWrap(True)
    reference_layout.addRow(helper)
    reference_layout.addRow("Resolved orientation", QtWidgets.QLabel("manual_global_z"))
    reference_layout.addRow("zmin", QtWidgets.QLineEdit("-15.0"))
    reference_layout.addRow("zmax", QtWidgets.QLineEdit("15.0"))
    reference.show()
    QtWidgets.QApplication.processEvents()
    reference_height = reference.sizeHint().height()

    # Allow a small margin for styling/font differences, but the ~60px of residual spacing the
    # old row-hiding approach left behind must not reappear.
    assert legacy_height <= reference_height + 20, (
        f"Legacy-mode group height ({legacy_height}) is far larger than a from-scratch group "
        f"with only its visible fields ({reference_height}) -- hidden rows are reserving space "
        "again."
    )

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_orientation_group_height_changes_with_visible_content():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
    dialog.window.show()
    QtWidgets.QApplication.processEvents()
    group = _orientation_group(dialog)

    heights = {}
    for mode in (LEGACY_MODE, ORIENTATION_FILE_MODE, PDBTM_MODE):
        dialog.orientation_mode.setCurrentText(mode)
        QtWidgets.QApplication.processEvents()
        heights[mode] = group.sizeHint().height()

    # Planar shows only one field (Orientation JSON) -- strictly the smallest.
    assert heights[ORIENTATION_FILE_MODE] < heights[LEGACY_MODE]
    # PDBTM (local, the mode's default source) shows more fields than Legacy's zmin/zmax pair.
    assert heights[PDBTM_MODE] > heights[LEGACY_MODE]

    dialog.pdbtm_source.setCurrentText("Validated cache")
    QtWidgets.QApplication.processEvents()
    cached_height = group.sizeHint().height()
    # Switching from local to cache trades two fields (PDBTM JSON, Transformed PDB) for more
    # (fetch/cancel, cache status, cache metadata, cache actions) -- strictly taller.
    assert cached_height > heights[PDBTM_MODE]

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_advanced_and_comparison_groups_start_collapsed():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
    dialog.window.show()
    QtWidgets.QApplication.processEvents()

    assert dialog.comparison_group.isCheckable() is True
    assert dialog.comparison_group.isChecked() is False
    assert dialog.comparison_pdbtm_source.isVisible() is False

    dialog.comparison_group.setChecked(True)
    QtWidgets.QApplication.processEvents()
    assert dialog.comparison_pdbtm_source.isVisible() is True

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


@pytest.mark.parametrize(
    ("result", "expected_category", "expected_text"),
    [
        ({"summary": {"overall_status": "NO_FLAGS"}}, ui_theme.CATEGORY_SUCCESS, "NO_FLAGS"),
        (
            {"summary": {"overall_status": "REVIEW_ITEMS"}, "review_items": [1, 2]},
            ui_theme.CATEGORY_REVIEW,
            "REVIEW_ITEMS (2)",
        ),
        (
            {"summary": {"overall_status": "INSUFFICIENT_CONTEXT"}},
            ui_theme.CATEGORY_REVIEW,
            "INSUFFICIENT_CONTEXT",
        ),
        (
            {"summary": {"overall_status": "ANALYSIS_ERROR"}},
            ui_theme.CATEGORY_ERROR,
            "ANALYSIS_ERROR",
        ),
        (["not", "a", "report"], ui_theme.CATEGORY_SUCCESS, "Completed"),
    ],
)
def test_headline_for_result_never_confuses_review_with_failure(
    result, expected_category, expected_text
):
    category, text = _headline_for_result(result)
    assert category == expected_category
    assert text == expected_text
    if expected_category == ui_theme.CATEGORY_REVIEW:
        assert category != ui_theme.CATEGORY_ERROR


def test_real_qt_run_qc_updates_result_headline_and_enables_export():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
    export_json = dialog.action_buttons[-1]
    assert export_json.isEnabled() is False
    assert ui_theme.glyph_for_category(ui_theme.CATEGORY_NEUTRAL) in dialog.result_headline.text()

    dialog._execute(
        "Running…",
        lambda: {"summary": {"overall_status": "REVIEW_ITEMS"}, "review_items": [1]},
        lambda result: "rendered",
    )
    QtWidgets.QApplication.processEvents()

    assert export_json.isEnabled() is True
    assert ui_theme.glyph_for_category(ui_theme.CATEGORY_REVIEW) in dialog.result_headline.text()
    assert "REVIEW_ITEMS" in dialog.result_headline.text()
    assert ui_theme.glyph_for_category(ui_theme.CATEGORY_ERROR) not in dialog.result_headline.text()

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_single_structure_results_area_is_compact_until_populated():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)

    assert dialog.summary.maximumHeight() == ui_theme.COMPACT_RESULT_HEIGHT

    dialog._execute(
        "Running…",
        lambda: {"summary": {"overall_status": "NO_FLAGS"}},
        lambda result: "rendered",
    )
    QtWidgets.QApplication.processEvents()
    assert dialog.summary.maximumHeight() == ui_theme.EXPANDED_RESULT_HEIGHT

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_comparison_metrics_area_is_compact_until_a_comparison_completes():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
    assert dialog.comparison_metrics.maximumHeight() == ui_theme.COMPACT_RESULT_HEIGHT

    # _sync_comparison_controls reads self._comparison_result/_comparison_report directly;
    # simulate "a comparison just completed" the same way _on_comparison_finished does.
    dialog._comparison_result = object()
    dialog._comparison_report = object()
    dialog._sync_comparison_controls()

    assert dialog.comparison_metrics.maximumHeight() == ui_theme.EXPANDED_RESULT_HEIGHT

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_batch_panel_primary_button_and_group_titles():
    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, QtWidgets.QWidget())

    assert panel.validate_button.styleSheet() == ui_theme.PRIMARY_BUTTON_QSS
    assert panel.run_button.styleSheet() == ui_theme.PRIMARY_BUTTON_QSS
    assert panel.cancel_button.styleSheet() == ""

    group_titles = {
        box.title()
        for box in panel.widget.findChildren(QtWidgets.QGroupBox)
        if box.styleSheet() == ui_theme.GROUP_TITLE_QSS
    }
    assert group_titles == {"Plan", "Output", "Execution", "Results", "Current-session history"}


def test_real_qt_batch_panel_history_group_starts_collapsed():
    parent = QtWidgets.QWidget()
    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, parent)
    parent.show()
    QtWidgets.QApplication.processEvents()

    history_group = next(
        box
        for box in panel.widget.findChildren(QtWidgets.QGroupBox)
        if box.title() == "Current-session history"
    )
    assert history_group.isCheckable() is True
    assert history_group.isChecked() is False
    assert panel.history_table.isVisible() is False

    history_group.setChecked(True)
    QtWidgets.QApplication.processEvents()
    assert panel.history_table.isVisible() is True

    parent.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_batch_panel_empty_states_toggle_with_content(monkeypatch, tmp_path):
    parent = QtWidgets.QWidget()
    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, parent)
    panel.cmd_obj = object()
    parent.show()
    QtWidgets.QApplication.processEvents()

    # The history group starts collapsed (see the dedicated collapsed-by-default test), so its
    # empty-state label is only meaningfully visible once expanded.
    history_group = next(
        box
        for box in panel.widget.findChildren(QtWidgets.QGroupBox)
        if box.title() == "Current-session history"
    )
    history_group.setChecked(True)
    QtWidgets.QApplication.processEvents()

    assert panel.queue_empty_label.isVisible() is True
    assert panel.history_empty_label.isVisible() is True

    panel.plan_path.setText(str(ROOT / "data" / "synthetic" / "stage5a_batch_plan.json"))
    panel.validate_selected_plan()
    QtWidgets.QApplication.processEvents()
    assert panel.queue.rowCount() == 5
    assert panel.queue_empty_label.isVisible() is False

    panel.plan_path.setText("")
    QtWidgets.QApplication.processEvents()
    assert panel.queue.rowCount() == 0
    assert panel.queue_empty_label.isVisible() is True

    parent.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_batch_plan_metadata_grid_is_populated_after_validation(tmp_path):
    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, QtWidgets.QWidget())
    panel.cmd_obj = object()
    panel.plan_path.setText(str(ROOT / "data" / "synthetic" / "stage5a_batch_plan.json"))
    panel.validate_selected_plan()

    assert panel.plan_job_count.text() == "5"
    assert panel.plan_sha.text() != ""
    assert panel.plan_contract_status.text() != "Not validated"


def test_real_qt_batch_metadata_shows_em_dash_before_validation_not_blank_or_zero():
    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, QtWidgets.QWidget())

    assert panel.plan_sha.text() == ui_theme.EMPTY_VALUE
    assert panel.plan_job_count.text() == ui_theme.EMPTY_VALUE
    assert panel.failure_policy.text() == ui_theme.EMPTY_VALUE
    assert panel.overwrite_policy.text() == ui_theme.EMPTY_VALUE
    assert panel.current_job.text() == ui_theme.EMPTY_VALUE
    assert panel.current_mode.text() == ui_theme.EMPTY_VALUE
    for text in (
        panel.plan_sha.text(),
        panel.plan_job_count.text(),
        panel.failure_policy.text(),
        panel.overwrite_policy.text(),
    ):
        assert text != ""
        assert text != "0"


def test_real_qt_batch_result_and_selected_job_areas_are_compact_until_populated(tmp_path):
    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, QtWidgets.QWidget())
    panel.cmd_obj = object()

    assert panel.result_summary.maximumHeight() == ui_theme.COMPACT_RESULT_HEIGHT
    assert panel.selected_job_details.maximumHeight() == ui_theme.COMPACT_RESULT_HEIGHT

    panel.plan_path.setText(str(ROOT / "data" / "synthetic" / "stage5a_batch_plan.json"))
    panel.validate_selected_plan()
    panel.output_path.setText(str(tmp_path / "output"))

    # Selecting a job before any bundle exists must not crash and must stay compact.
    assert panel.selected_job_details.maximumHeight() == ui_theme.COMPACT_RESULT_HEIGHT


def test_real_qt_batch_result_and_selected_job_areas_expand_once_populated():
    from types import MappingProxyType

    from membrane_vqc.batch_result_browser import VerifiedBatchResult, VerifiedJob

    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, QtWidgets.QWidget())
    jobs = tuple(
        VerifiedJob(
            f"job-{i}",
            "legacy_global_z",
            "SUCCESS",
            "1.1",
            0,
            0,
            None,
            True,
            None,
            None,
            MappingProxyType({}),
        )
        for i in range(3)
    )
    bundle = VerifiedBatchResult(
        Path("C:/safe/batch-result.json"),
        Path("C:/safe"),
        100,
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "COMPLETED",
        "2026-08-03T00:00:00Z",
        "2026-08-03T00:00:01Z",
        "0.9.0.dev0",
        MappingProxyType({"total": 3}),
        jobs,
    )

    panel._selected_bundle = bundle
    panel._render_bundle(bundle)
    assert panel.result_summary.maximumHeight() == ui_theme.EXPANDED_RESULT_HEIGHT
    # No row selected yet -- detail area stays compact even though a bundle now exists.
    assert panel.selected_job_details.maximumHeight() == ui_theme.COMPACT_RESULT_HEIGHT

    panel.queue.selectRow(0)
    panel._render_selected_job()
    assert panel.selected_job_details.maximumHeight() == ui_theme.EXPANDED_RESULT_HEIGHT
    assert "job-0" in panel.selected_job_details.toPlainText()


class _ConfigurableSession:
    """Minimal fake BatchRunSession reporting a caller-chosen overall_status."""

    def __init__(self, plan, plan_bytes, output, executor, **kwargs):
        self.plan = plan
        self.root = Path(output)
        self.cancel_requested = kwargs["cancel_requested"]
        self.results = []
        self.index = 0
        self.overall_status = "COMPLETED"

    @property
    def total_jobs(self):
        return len(self.plan["jobs"])

    @property
    def done(self):
        return self.index >= self.total_jobs

    @property
    def current_job(self):
        return None if self.done else self.plan["jobs"][self.index]

    def start(self):
        return self

    def execute_next(self):
        job = self.current_job
        item = {
            "job_id": job["id"],
            "mode": job["analysis"]["mode"],
            "status": "SUCCESS",
            "error_code": None,
            "report": None,
            "report_schema": "1.1",
            "csv": None,
            "warnings_count": 0,
            "review_items_count": 0,
            "coordinate_preserved": True,
        }
        self.results.append(item)
        self.index += 1
        return item

    def finalize(self):
        return {"overall_status": self.overall_status}

    def abort(self):
        pass


def _drive(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline
        QtWidgets.QApplication.processEvents()


@pytest.mark.parametrize(
    ("overall_status", "expected_category", "unexpected_category"),
    [
        ("COMPLETED_WITH_ERRORS", ui_theme.CATEGORY_REVIEW, ui_theme.CATEGORY_ERROR),
        ("FAILED_FAST", ui_theme.CATEGORY_ERROR, ui_theme.CATEGORY_REVIEW),
    ],
)
def test_real_qt_completed_with_errors_is_visually_distinct_from_failed_fast(
    monkeypatch, tmp_path, overall_status, expected_category, unexpected_category
):
    import membrane_vqc.batch_gui as module

    fixed_status = overall_status
    session_holder = {}

    def _make_session(plan, plan_bytes, output, executor, **kwargs):
        session = _ConfigurableSession(plan, plan_bytes, output, executor, **kwargs)
        session.overall_status = fixed_status
        session_holder["session"] = session
        return session

    monkeypatch.setattr(module, "PymolBatchExecutor", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "BatchRunSession", _make_session)

    def _bundle_for(path):
        from types import MappingProxyType

        from membrane_vqc.batch_result_browser import VerifiedBatchResult, VerifiedJob

        jobs = tuple(
            VerifiedJob(
                f"job-{i}",
                "legacy_global_z",
                "SUCCESS",
                "1.1",
                0,
                0,
                None,
                True,
                None,
                None,
                MappingProxyType({}),
            )
            for i in range(5)
        )
        return VerifiedBatchResult(
            Path("C:/safe/batch-result.json"),
            Path("C:/safe"),
            100,
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "d" * 64,
            fixed_status,
            "2026-08-02T00:00:00Z",
            "2026-08-02T00:00:01Z",
            "0.9.0.dev0",
            MappingProxyType({"total": 5}),
            jobs,
        )

    monkeypatch.setattr(module, "inspect_result_bundle", _bundle_for)

    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, QtWidgets.QWidget())
    panel.cmd_obj = object()
    panel.plan_path.setText(str(ROOT / "data" / "synthetic" / "stage5a_batch_plan.json"))
    panel.validate_selected_plan()
    panel.output_path.setText(str(tmp_path / "output"))
    panel.run_batch()
    _drive(lambda: panel.session is None)

    assert panel.state == FAILED  # unchanged GUI-state literal for both outcomes
    assert ui_theme.glyph_for_category(expected_category) in panel.status_message.text()
    assert ui_theme.glyph_for_category(unexpected_category) not in panel.status_message.text()
