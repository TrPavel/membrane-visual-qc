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
from membrane_vqc.gui import MembraneVQCDialog  # noqa: E402

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
    assert export_json.styleSheet() == ui_theme.PRIMARY_BUTTON_QSS
    for secondary in (show_slab, colour, ligand_shell):
        assert secondary.styleSheet() == ""
    assert dialog.compare_button.styleSheet() == ui_theme.PRIMARY_BUTTON_QSS
    assert dialog.comparison_cancel_button.styleSheet() == ""

    dialog.window.close()
    QtWidgets.QApplication.processEvents()


def test_real_qt_single_structure_tab_has_scannable_section_headers():
    dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)

    labels = {
        label.text()
        for label in dialog.single_page.findChildren(QtWidgets.QLabel)
        if label.styleSheet() == ui_theme.SECTION_TITLE_QSS
    }
    for expected in (
        "Structure & orientation source",
        "PDBTM source & cache",
        "Resolved orientation & membrane boundaries",
        "Ligand context & export",
        "Run",
    ):
        assert expected in labels

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
