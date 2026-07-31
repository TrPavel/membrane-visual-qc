"""Real PyQt5 offscreen lifecycle tests for the Stage 5B main-thread pump."""

from __future__ import annotations

from types import MappingProxyType
import os
from pathlib import Path
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtCore = pytest.importorskip("PyQt5.QtCore")
QtGui = pytest.importorskip("PyQt5.QtGui")
QtWidgets = pytest.importorskip("PyQt5.QtWidgets")

from membrane_vqc.batch_gui import CANCELLED, COMPLETED, READY, BatchReviewPanel  # noqa: E402
from membrane_vqc.batch_result_browser import VerifiedBatchResult, VerifiedJob  # noqa: E402
from membrane_vqc.gui import MembraneVQCDialog  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


class _Session:
    instances = []

    def __init__(self, plan, plan_bytes, output, executor, **kwargs):
        self.plan = plan
        self.root = Path(output)
        self.cancel_requested = kwargs["cancel_requested"]
        self.results = []
        self.index = 0
        self.finalized = 0
        self.overall_status = "COMPLETED"
        self.__class__.instances.append(self)

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
        assert QtCore.QThread.currentThread() is QtWidgets.QApplication.instance().thread()
        job = self.current_job
        cancelled = self.cancel_requested()
        item = {
            "job_id": job["id"],
            "mode": job["analysis"]["mode"],
            "status": "CANCELLED" if cancelled else "SUCCESS",
            "error_code": None,
            "report": None,
            "report_schema": None if cancelled else "1.1",
            "csv": None,
            "warnings_count": 0,
            "review_items_count": None if cancelled else 0,
            "coordinate_preserved": None if cancelled else True,
        }
        if cancelled:
            self.overall_status = "CANCELLED"
        self.results.append(item)
        self.index += 1
        return item

    def finalize(self):
        self.finalized += 1
        return {"overall_status": self.overall_status}

    def abort(self):
        self.overall_status = "FAILED"


def _bundle(status="COMPLETED"):
    jobs = tuple(
        VerifiedJob(
            f"job-{index}",
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
        for index in range(5)
    )
    return VerifiedBatchResult(
        Path("C:/safe/batch-result.json"),
        Path("C:/safe"),
        100,
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        status,
        "2026-07-31T00:00:00Z",
        "2026-07-31T00:00:01Z",
        "0.6.0.dev0",
        MappingProxyType({"total": 5}),
        jobs,
    )


def _drive(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline
        QtWidgets.QApplication.processEvents()


def test_real_qt_dialog_and_main_thread_batch_lifecycle(monkeypatch, tmp_path):
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    import membrane_vqc.batch_gui as module

    _Session.instances.clear()
    monkeypatch.setattr(module, "PymolBatchExecutor", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "BatchRunSession", _Session)
    monkeypatch.setattr(
        module,
        "inspect_result_bundle",
        lambda path: _bundle(_Session.instances[-1].overall_status),
    )

    for _ in range(2):
        dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
        dialog.show()
        QtWidgets.QApplication.processEvents()
        assert dialog.tabs.count() == 2
        assert dialog.tabs.tabText(1) == "Batch review"
        dialog.window.close()
        QtWidgets.QApplication.processEvents()

    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, QtWidgets.QWidget())
    panel.cmd_obj = object()
    panel.plan_path.setText(str(ROOT / "data" / "synthetic" / "stage5a_batch_plan.json"))
    panel.validate_selected_plan()
    panel.output_path.setText(str(tmp_path / "complete"))
    assert panel.state == READY

    turns = []
    panel.timer.timeout.connect(lambda: turns.append(len(_Session.instances[-1].results)))
    panel.run_batch()
    _drive(lambda: panel.session is None)
    assert panel.state == COMPLETED
    assert turns == [1, 2, 3, 4, 5, 5]
    assert _Session.instances[-1].finalized == 1

    panel.plan_path.setText(str(ROOT / "data" / "synthetic" / "stage5a_batch_plan.json"))
    panel.validate_selected_plan()
    panel.output_path.setText(str(tmp_path / "cancel"))
    panel.run_batch()
    panel.cancel_batch()
    _drive(lambda: panel.session is None)
    assert panel.state == CANCELLED
    assert all(item["status"] == "CANCELLED" for item in _Session.instances[-1].results)

    panel.plan_path.setText(str(ROOT / "data" / "synthetic" / "stage5a_batch_plan.json"))
    panel.validate_selected_plan()
    panel.output_path.setText(str(tmp_path / "close"))
    panel.run_batch()
    panel.shutdown()
    panel.reactivate()
    _drive(lambda: panel.session is None)
    assert panel.state == CANCELLED
    assert panel.run_state.text() == CANCELLED
    assert not panel.cancel_button.isEnabled()
    application.processEvents()
