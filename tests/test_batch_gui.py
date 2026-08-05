from pathlib import Path
from types import MappingProxyType, SimpleNamespace

from membrane_vqc import qc
from membrane_vqc.batch_gui import (
    CANCELLED,
    CANCELLING,
    COMPLETED,
    FAILED,
    IDLE,
    MAX_SESSION_HISTORY,
    READY,
    RUNNING,
    BatchReviewPanel,
)
from membrane_vqc.batch_paths import BatchPathError
from membrane_vqc.batch_result_browser import VerifiedBatchResult, VerifiedJob


ROOT = Path(__file__).resolve().parents[1]


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot, *_):
        self.slots.append(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class Widget:
    def __init__(self, *args):
        self.enabled = True

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)

    def isEnabled(self):
        return self.enabled


class QWidget(Widget):
    pass


class Layout:
    def __init__(self, *args):
        self.children = []

    def addWidget(self, widget):
        self.children.append(widget)

    def addLayout(self, value):
        self.children.append(value)


class FormLayout(Layout):
    def addRow(self, *values):
        self.children.append(values)


class GroupBox(QWidget):
    pass


class LineEdit(Widget):
    def __init__(self, value=""):
        super().__init__()
        self.value = value
        self.textChanged = Signal()

    def text(self):
        return self.value

    def setText(self, value):
        self.value = str(value)
        self.textChanged.emit(self.value)


class Label(LineEdit):
    pass


class Button(Widget):
    def __init__(self, text=""):
        super().__init__()
        self.text = text
        self.clicked = Signal()

    def click(self):
        if self.enabled:
            self.clicked.emit()


class TextEdit(Widget):
    def __init__(self):
        super().__init__()
        self.value = ""

    def setReadOnly(self, *_):
        pass

    def setPlainText(self, value):
        self.value = str(value)

    def toPlainText(self):
        return self.value


class ProgressBar(Widget):
    def __init__(self):
        super().__init__()
        self.minimum = 0
        self.maximum = 0
        self.value = 0

    def setRange(self, minimum, maximum):
        self.minimum, self.maximum = minimum, maximum

    def setValue(self, value):
        self.value = value


class TableItem:
    def __init__(self, text):
        self._text = str(text)

    def text(self):
        return self._text


class Table(Widget):
    def __init__(self, rows, columns):
        super().__init__()
        self.rows = rows
        self.columns = columns
        self.items = {}
        self.selected_row = -1
        self.itemSelectionChanged = Signal()

    def setHorizontalHeaderLabels(self, values):
        self.headers = tuple(values)

    def setRowCount(self, rows):
        self.rows = rows
        self.items = {key: value for key, value in self.items.items() if key[0] < rows}
        if self.selected_row >= rows:
            self.selected_row = -1

    def setItem(self, row, column, item):
        self.items[(row, column)] = item

    def item(self, row, column):
        return self.items.get((row, column))

    def currentRow(self):
        return self.selected_row

    def selectRow(self, row):
        self.selected_row = row
        self.itemSelectionChanged.emit()


class Timer:
    def __init__(self, *args):
        self.timeout = Signal()
        self.active = False
        self.single = False

    def setSingleShot(self, value):
        self.single = bool(value)

    def start(self, *_):
        self.active = True

    def isActive(self):
        return self.active

    def stop(self):
        self.active = False

    def fire(self):
        assert self.active
        if self.single:
            self.active = False
        self.timeout.emit()


class FileDialog:
    open_name = ""
    directory = ""

    @classmethod
    def getOpenFileName(cls, *args):
        return cls.open_name, ""

    @classmethod
    def getExistingDirectory(cls, *args):
        return cls.directory


class Desktop:
    opened = []

    @classmethod
    def openUrl(cls, url):
        cls.opened.append(url)
        return True


class Url:
    @staticmethod
    def fromLocalFile(path):
        return ("local", path)


QtWidgets = SimpleNamespace(
    QWidget=QWidget,
    QVBoxLayout=Layout,
    QHBoxLayout=Layout,
    QFormLayout=FormLayout,
    QGroupBox=GroupBox,
    QLineEdit=LineEdit,
    QPushButton=Button,
    QLabel=Label,
    QProgressBar=ProgressBar,
    QTableWidget=Table,
    QTableWidgetItem=TableItem,
    QTextEdit=TextEdit,
    QFileDialog=FileDialog,
)
QtCore = SimpleNamespace(QTimer=Timer, QUrl=Url)
QtGui = SimpleNamespace(QDesktopServices=Desktop)


def _bundle(job_count=5, status="COMPLETED"):
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
        for index in range(job_count)
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
        MappingProxyType({"total": job_count}),
        jobs,
    )


class FakeSession:
    instances = []

    def __init__(self, plan, plan_bytes, output, executor, **kwargs):
        self.plan = plan
        self.root = Path(output)
        self.cancel = kwargs["cancel_requested"]
        self.index = 0
        self.results = []
        self.executed = []
        self.finalize_count = 0
        self.aborted = False
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
        job = self.current_job
        if self.cancel():
            status = "CANCELLED"
        else:
            status = "SUCCESS"
            self.executed.append(job["id"])
        result = {
            "job_id": job["id"],
            "mode": job["analysis"]["mode"],
            "status": status,
            "error_code": None,
            "report": None,
            "report_schema": "1.1" if status == "SUCCESS" else None,
            "csv": None,
            "warnings_count": 0,
            "review_items_count": 0 if status == "SUCCESS" else None,
            "coordinate_preserved": True if status == "SUCCESS" else None,
        }
        self.results.append(result)
        self.index += 1
        return result

    def finalize(self):
        self.finalize_count += 1
        cancelled = any(item["status"] == "CANCELLED" for item in self.results)
        return {"overall_status": "CANCELLED" if cancelled else "COMPLETED"}

    def abort(self):
        self.aborted = True


def _panel(monkeypatch):
    import membrane_vqc.batch_gui as module

    FakeSession.instances.clear()
    monkeypatch.setattr(module, "PymolBatchExecutor", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "BatchRunSession", FakeSession)
    monkeypatch.setattr(module, "inspect_result_bundle", lambda path: _bundle())
    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, QWidget())
    panel.cmd_obj = object()
    return panel


def _ready_panel(panel, tmp_path):
    panel.plan_path.setText(str(ROOT / "data" / "synthetic" / "stage5a_batch_plan.json"))
    panel.validate_selected_plan()
    panel.output_path.setText(str(tmp_path / "output"))
    assert panel.state == READY


def test_batch_panel_defaults_do_not_scan_validate_or_execute(monkeypatch):
    panel = _panel(monkeypatch)
    assert panel.state == IDLE
    assert not panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()
    assert panel.queue.rows == 0
    assert list(panel.history) == []
    assert FakeSession.instances == []


def test_validation_populates_five_ordered_rows_and_edits_invalidate(monkeypatch, tmp_path):
    panel = _panel(monkeypatch)
    _ready_panel(panel, tmp_path)
    assert panel.queue.rows == 5
    assert [panel.queue.item(row, 1).text() for row in range(5)] == [
        "legacy",
        "planar",
        "pdbtm-local",
        "pdbtm-cache",
        "comparison",
    ]
    assert panel.run_button.isEnabled()
    panel.plan_path.setText("changed.json")
    assert panel.state == IDLE
    assert panel.validated_plan is None
    assert panel.queue.rows == 0


def test_run_batch_reserved_output_name_failure_is_caught_not_raised(monkeypatch, tmp_path):
    """Regression test: a job id that collides with a reserved Windows device name
    (e.g. "con") passes plan validation but makes BatchRunSession.start() raise
    BatchPathError from safe_output_name(). Before this fix, run_batch()'s except-tuple
    didn't include BatchPathError, so this exception propagated uncaught out of the
    Run button's Qt slot instead of producing a clean FAILED state."""
    panel = _panel(monkeypatch)
    _ready_panel(panel, tmp_path)

    def _raise_start(self):
        raise BatchPathError("output name contains a reserved Windows component")

    monkeypatch.setattr(FakeSession, "start", _raise_start)
    panel.run_batch()
    assert panel.state == FAILED
    assert panel.session is None


def test_open_result_reserved_output_name_failure_is_caught_not_raised(monkeypatch, tmp_path):
    """Regression test: inspect_result_bundle() can raise BatchPathError (a sibling,
    not a subclass, of BatchResultBrowserError) if a manifest references a reserved
    output name. Before this fix, open_result()'s except-tuple only caught
    BatchResultBrowserError, so this exception propagated uncaught."""
    panel = _panel(monkeypatch)
    import membrane_vqc.batch_gui as module

    def _raise_inspect(path):
        raise BatchPathError("output name contains a reserved Windows component")

    monkeypatch.setattr(module, "inspect_result_bundle", _raise_inspect)
    result = panel.open_result(str(tmp_path / "batch-result.json"))
    assert result is False
    assert panel.state == FAILED


def test_invalid_plan_never_leaves_prior_plan_current(monkeypatch, tmp_path):
    panel = _panel(monkeypatch)
    _ready_panel(panel, tmp_path)
    panel.plan_path.setText(str(ROOT / "data" / "synthetic" / "stage5a_batch_plan_invalid.json"))
    panel.validate_selected_plan()
    assert panel.state == FAILED
    assert panel.validated_plan is None
    assert not panel.run_button.isEnabled()


def test_main_thread_pump_runs_one_job_per_timer_turn(monkeypatch, tmp_path):
    panel = _panel(monkeypatch)
    _ready_panel(panel, tmp_path)
    panel.run_batch()
    session = FakeSession.instances[-1]
    assert panel.state == RUNNING
    assert session.executed == []
    for expected in range(1, 6):
        panel.timer.fire()
        assert len(session.executed) == expected
        assert session.finalize_count == 0
    panel.timer.fire()
    assert session.finalize_count == 1
    assert panel.state == COMPLETED
    assert len(panel.history) == 1


def test_cancel_before_first_job_starts_no_scientific_job(monkeypatch, tmp_path):
    panel = _panel(monkeypatch)
    _ready_panel(panel, tmp_path)
    panel.run_batch()
    session = FakeSession.instances[-1]
    panel.cancel_batch()
    assert panel.state == CANCELLING
    while panel.timer.isActive():
        panel.timer.fire()
    assert session.executed == []
    assert panel.state == CANCELLED


def test_close_invalidates_ui_delivery_but_finishes_cancellation(monkeypatch, tmp_path):
    panel = _panel(monkeypatch)
    _ready_panel(panel, tmp_path)
    panel.run_batch()
    session = FakeSession.instances[-1]
    panel.timer.fire()
    panel.shutdown()
    panel.reactivate()
    while panel.timer.isActive():
        panel.timer.fire()
    assert session.executed == ["legacy"]
    assert session.finalize_count == 1
    assert panel._ui_active is True
    assert panel.state == CANCELLED
    assert panel.run_state.text() == CANCELLED
    assert panel.plan_path.isEnabled()
    assert not panel.cancel_button.isEnabled()
    # Reopening before hidden cancellation finishes does not reactivate the old run's delivery.
    assert panel.queue.item(1, 4).text() == "QUEUED"


def test_result_browsing_cannot_strand_an_active_run(monkeypatch, tmp_path):
    panel = _panel(monkeypatch)
    _ready_panel(panel, tmp_path)
    panel.run_batch()
    session = FakeSession.instances[-1]
    assert panel.open_result("explicit-result.json") is False
    assert panel.state == RUNNING
    assert panel.session is session
    assert not panel.open_existing_button.isEnabled()
    while panel.timer.isActive():
        panel.timer.fire()
    assert session.finalize_count == 1
    assert panel.state == COMPLETED


def test_history_is_bounded_and_clear_deletes_no_files(monkeypatch, tmp_path):
    panel = _panel(monkeypatch)
    sentinel = tmp_path / "must-remain.txt"
    sentinel.write_text("owned by output", encoding="utf-8")
    for index in range(MAX_SESSION_HISTORY + 3):
        bundle = _bundle(1)
        panel._add_history(f"plan-{index}.json", bundle)
    assert len(panel.history) == MAX_SESSION_HISTORY
    assert panel.history[0].plan_name == "plan-3.json"
    panel.clear_history()
    assert list(panel.history) == []
    assert sentinel.read_text("utf-8") == "owned by output"


def test_browsing_result_does_not_touch_last_report_or_pymol(monkeypatch):
    panel = _panel(monkeypatch)
    sentinel = {"single": "report"}
    previous = qc.LAST_REPORT
    qc.LAST_REPORT = sentinel
    try:
        assert panel.open_result("explicit-result.json") is True
        assert qc.LAST_REPORT is sentinel
        assert FakeSession.instances == []
    finally:
        qc.LAST_REPORT = previous


def test_active_single_operation_blocks_batch_start(monkeypatch, tmp_path):
    panel = BatchReviewPanel(QtWidgets, QtGui, QtCore, QWidget(), execution_allowed=lambda: False)
    panel.cmd_obj = object()
    _ready_panel(panel, tmp_path)
    panel.run_batch()
    assert panel.state == READY
    assert "single-structure" in panel.status_message.text()
