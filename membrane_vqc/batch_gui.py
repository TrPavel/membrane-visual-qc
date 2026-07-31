"""Lazy Qt adapter for Stage 5B batch queue, history, and result browsing."""

from __future__ import annotations

from collections import deque
import copy
from dataclasses import dataclass
import hashlib
from pathlib import Path
import uuid

from .batch_contracts import BatchContractError, load_plan
from .batch_executor import PymolBatchExecutor, _git_commit
from .batch_result_browser import (
    BatchResultBrowserError,
    VerifiedArtifact,
    VerifiedBatchResult,
    inspect_result_bundle,
    revalidate_artifact,
)
from .batch_runner import BatchExecutionFailed, BatchInputRejected, BatchRunSession, MANIFEST_NAME
from .constants import VERSION


IDLE = "IDLE"
VALIDATING = "VALIDATING"
READY = "READY"
RUNNING = "RUNNING"
CANCELLING = "CANCELLING"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"
FAILED = "FAILED"
BATCH_STATES = (IDLE, VALIDATING, READY, RUNNING, CANCELLING, COMPLETED, CANCELLED, FAILED)
MAX_SESSION_HISTORY = 20
MAX_STATUS_TEXT = 256


@dataclass(frozen=True, slots=True)
class ValidatedPlanSnapshot:
    path: Path
    plan: dict[str, object]
    plan_bytes: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class SessionHistoryEntry:
    plan_name: str
    plan_sha256: str
    manifest_path: Path | None
    overall_status: str
    completed_at: str
    counts: tuple[tuple[str, int], ...]
    identity_core_sha256: str


class CancellationToken:
    def __init__(self) -> None:
        self._requested = False

    def request(self) -> None:
        self._requested = True

    def is_cancelled(self) -> bool:
        return self._requested


def input_summary(job: dict[str, object]) -> str:
    source = job["input"]
    if source["kind"] == "pymol":
        return f"PyMOL: {str(source['selection'])[:96]}"
    return f"File: {Path(str(source['path'])).name[:96]}"


class BatchReviewPanel:
    """Own one dialog's main-thread batch pump and bounded session history."""

    def __init__(
        self,
        QtWidgets,
        QtGui,
        QtCore,
        parent,
        *,
        set_single_run_busy=None,
        execution_allowed=None,
    ):
        self.QtWidgets = QtWidgets
        self.QtGui = QtGui
        self.QtCore = QtCore
        self.parent = parent
        self.set_single_run_busy = set_single_run_busy or (lambda _: None)
        self.execution_allowed = execution_allowed or (lambda: True)
        self.session_uuid = uuid.uuid4().hex
        self.generation = 0
        self.request_sequence = 0
        self.current_request_id: str | None = None
        self.run_generation: int | None = None
        self.delivery_generation = 0
        self.run_delivery_generation: int | None = None
        self.state = IDLE
        self.validated_plan: ValidatedPlanSnapshot | None = None
        self.completed_result: VerifiedBatchResult | None = None
        self.session: BatchRunSession | None = None
        self.cancellation: CancellationToken | None = None
        self.history: deque[SessionHistoryEntry] = deque(maxlen=MAX_SESSION_HISTORY)
        self._ui_active = True
        self._selected_bundle: VerifiedBatchResult | None = None
        self.cmd_obj = None
        self.widget = QtWidgets.QWidget(parent)
        self._build()
        self.timer = QtCore.QTimer(self.widget)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._pump)
        self._sync_controls()

    def _build(self) -> None:
        layout = self.QtWidgets.QVBoxLayout(self.widget)
        plan_group = self.QtWidgets.QGroupBox("Plan")
        plan_layout = self.QtWidgets.QFormLayout(plan_group)
        self.plan_path = self.QtWidgets.QLineEdit("")
        self.browse_plan_button = self.QtWidgets.QPushButton("Browse plan…")
        self.validate_button = self.QtWidgets.QPushButton("Validate")
        plan_row = self.QtWidgets.QHBoxLayout()
        plan_row.addWidget(self.plan_path)
        plan_row.addWidget(self.browse_plan_button)
        plan_row.addWidget(self.validate_button)
        self.plan_contract_status = self.QtWidgets.QLabel("Not validated")
        self.plan_sha = self.QtWidgets.QLabel("")
        self.plan_job_count = self.QtWidgets.QLabel("0")
        self.failure_policy = self.QtWidgets.QLabel("")
        self.overwrite_policy = self.QtWidgets.QLabel("")
        plan_layout.addRow("Plan file", plan_row)
        plan_layout.addRow("Contract", self.plan_contract_status)
        plan_layout.addRow("Plan SHA-256", self.plan_sha)
        plan_layout.addRow("Jobs", self.plan_job_count)
        plan_layout.addRow("Failure policy", self.failure_policy)
        plan_layout.addRow("Overwrite policy", self.overwrite_policy)
        layout.addWidget(plan_group)

        output_group = self.QtWidgets.QGroupBox("Output")
        output_layout = self.QtWidgets.QFormLayout(output_group)
        self.output_path = self.QtWidgets.QLineEdit("")
        self.browse_output_button = self.QtWidgets.QPushButton("Browse output directory…")
        output_row = self.QtWidgets.QHBoxLayout()
        output_row.addWidget(self.output_path)
        output_row.addWidget(self.browse_output_button)
        output_layout.addRow("Output directory", output_row)
        layout.addWidget(output_group)

        execution_group = self.QtWidgets.QGroupBox("Execution")
        execution_layout = self.QtWidgets.QFormLayout(execution_group)
        self.run_button = self.QtWidgets.QPushButton("Run batch")
        self.cancel_button = self.QtWidgets.QPushButton("Cancel")
        action_row = self.QtWidgets.QHBoxLayout()
        action_row.addWidget(self.run_button)
        action_row.addWidget(self.cancel_button)
        self.progress = self.QtWidgets.QProgressBar()
        self.progress_label = self.QtWidgets.QLabel("0 / 0")
        self.current_job = self.QtWidgets.QLabel("")
        self.current_mode = self.QtWidgets.QLabel("")
        self.run_state = self.QtWidgets.QLabel(IDLE)
        self.status_message = self.QtWidgets.QLabel("Select and validate a plan explicitly.")
        execution_layout.addRow(action_row)
        execution_layout.addRow("Progress", self.progress)
        execution_layout.addRow("Completed / total", self.progress_label)
        execution_layout.addRow("Current job", self.current_job)
        execution_layout.addRow("Current mode", self.current_mode)
        execution_layout.addRow("Run state", self.run_state)
        execution_layout.addRow("Status", self.status_message)
        layout.addWidget(execution_group)

        self.queue = self.QtWidgets.QTableWidget(0, 8)
        self.queue.setHorizontalHeaderLabels(
            [
                "Order",
                "Job ID",
                "Mode",
                "Input summary",
                "Status",
                "Report schema",
                "Review items",
                "Error code",
            ]
        )
        layout.addWidget(self.queue)

        results_group = self.QtWidgets.QGroupBox("Results")
        results_layout = self.QtWidgets.QFormLayout(results_group)
        self.result_summary = self.QtWidgets.QTextEdit()
        self.result_summary.setReadOnly(True)
        self.selected_job_details = self.QtWidgets.QTextEdit()
        self.selected_job_details.setReadOnly(True)
        self.open_manifest_button = self.QtWidgets.QPushButton("Open result manifest")
        self.open_output_button = self.QtWidgets.QPushButton("Open output directory")
        self.reveal_report_button = self.QtWidgets.QPushButton("Reveal selected report")
        self.reveal_csv_button = self.QtWidgets.QPushButton("Reveal selected CSV")
        result_actions = self.QtWidgets.QHBoxLayout()
        for button in (
            self.open_manifest_button,
            self.open_output_button,
            self.reveal_report_button,
            self.reveal_csv_button,
        ):
            result_actions.addWidget(button)
        results_layout.addRow("Run summary", self.result_summary)
        results_layout.addRow("Selected job", self.selected_job_details)
        results_layout.addRow(result_actions)
        layout.addWidget(results_group)

        history_group = self.QtWidgets.QGroupBox("Current-session history")
        history_layout = self.QtWidgets.QVBoxLayout(history_group)
        self.history_table = self.QtWidgets.QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(
            ["Plan", "Status", "Completed", "Jobs", "Identity core"]
        )
        history_layout.addWidget(self.history_table)
        history_actions = self.QtWidgets.QHBoxLayout()
        self.open_existing_button = self.QtWidgets.QPushButton("Open existing result manifest…")
        self.open_history_button = self.QtWidgets.QPushButton("Open selected history")
        self.clear_history_button = self.QtWidgets.QPushButton("Clear session history")
        for button in (
            self.open_existing_button,
            self.open_history_button,
            self.clear_history_button,
        ):
            history_actions.addWidget(button)
        history_layout.addLayout(history_actions)
        layout.addWidget(history_group)

        self.plan_path.textChanged.connect(self._on_plan_edited)
        self.output_path.textChanged.connect(self._sync_controls)
        self.browse_plan_button.clicked.connect(self._browse_plan)
        self.browse_output_button.clicked.connect(self._browse_output)
        self.validate_button.clicked.connect(self.validate_selected_plan)
        self.run_button.clicked.connect(self.run_batch)
        self.cancel_button.clicked.connect(self.cancel_batch)
        self.queue.itemSelectionChanged.connect(self._render_selected_job)
        self.open_manifest_button.clicked.connect(self._open_manifest)
        self.open_output_button.clicked.connect(self._open_output)
        self.reveal_report_button.clicked.connect(lambda: self._reveal_selected("report"))
        self.reveal_csv_button.clicked.connect(lambda: self._reveal_selected("csv"))
        self.open_existing_button.clicked.connect(self._open_existing)
        self.open_history_button.clicked.connect(self._open_selected_history)
        self.clear_history_button.clicked.connect(self.clear_history)

    def _set_state(self, state: str, message: str) -> None:
        if state not in BATCH_STATES:
            raise ValueError("invalid batch GUI state")
        self.state = state
        if self._ui_active:
            self.run_state.setText(state)
            self.status_message.setText(str(message)[:MAX_STATUS_TEXT])
            self._sync_controls()

    def _on_plan_edited(self, *_):
        if self.state in {RUNNING, CANCELLING}:
            return
        self.generation += 1
        self.validated_plan = None
        self.completed_result = None
        self._selected_bundle = None
        self._clear_queue()
        self.plan_contract_status.setText("Not validated")
        self.plan_sha.setText("")
        self.plan_job_count.setText("0")
        self.failure_policy.setText("")
        self.overwrite_policy.setText("")
        self._set_state(IDLE, "Plan path changed; validate explicitly.")

    def _browse_plan(self):
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.parent, "Select batch plan", "", "Batch plan (*.json);;All files (*)"
        )
        if path:
            self.plan_path.setText(path)

    def _browse_output(self):
        path = self.QtWidgets.QFileDialog.getExistingDirectory(
            self.parent, "Select explicit batch output directory", ""
        )
        if path:
            self.output_path.setText(path)

    def validate_selected_plan(self):
        if self.state in {RUNNING, CANCELLING}:
            return
        self.generation += 1
        generation = self.generation
        self.validated_plan = None
        self._clear_queue()
        self._set_state(VALIDATING, "Validating the selected local plan…")
        try:
            path = Path(str(self.plan_path.text()).strip()).absolute()
            plan, plan_bytes = load_plan(path)
            snapshot = ValidatedPlanSnapshot(
                path,
                copy.deepcopy(plan),
                bytes(plan_bytes),
                hashlib.sha256(plan_bytes).hexdigest(),
            )
        except (BatchContractError, OSError):
            if generation == self.generation:
                self.plan_contract_status.setText("Invalid")
                self._set_state(FAILED, "PLAN_INVALID")
            return
        if generation != self.generation:
            return
        self.validated_plan = snapshot
        self.plan_contract_status.setText(str(plan["contract"]))
        self.plan_sha.setText(snapshot.sha256)
        self.plan_job_count.setText(str(len(plan["jobs"])))
        self.failure_policy.setText(str(plan["execution"]["failure_policy"]))
        self.overwrite_policy.setText(str(plan["execution"]["overwrite"]))
        self._populate_queue(plan)
        self._set_state(READY, "Plan validated; choose an explicit output directory.")

    def _populate_queue(self, plan):
        jobs = plan["jobs"]
        self.queue.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            values = (
                str(row + 1),
                str(job["id"]),
                str(job["analysis"]["mode"]),
                input_summary(job),
                "QUEUED",
                "",
                "",
                "",
            )
            for column, value in enumerate(values):
                self.queue.setItem(row, column, self.QtWidgets.QTableWidgetItem(value))
        self.progress.setRange(0, len(jobs))
        self.progress.setValue(0)
        self.progress_label.setText(f"0 / {len(jobs)}")

    def _clear_queue(self):
        self.queue.setRowCount(0)
        self.progress.setRange(0, 0)
        self.progress.setValue(0)
        self.progress_label.setText("0 / 0")

    def _next_request_id(self) -> str:
        self.request_sequence += 1
        return f"{self.session_uuid}:{self.generation}:{self.request_sequence}"

    def run_batch(self):
        if self.state != READY or self.validated_plan is None:
            return
        if not self.execution_allowed():
            self._set_state(READY, "Finish or cancel the active single-structure operation first.")
            return
        output = str(self.output_path.text()).strip()
        if not output:
            self._set_state(READY, "Choose an explicit output directory.")
            return
        self.generation += 1
        generation = self.generation
        self.run_generation = generation
        self.run_delivery_generation = self.delivery_generation
        self.current_request_id = self._next_request_id()
        self.cancellation = CancellationToken()
        snapshot = self.validated_plan
        plan = copy.deepcopy(snapshot.plan)
        try:
            cmd_obj = self.cmd_obj
            if cmd_obj is None:
                from pymol import cmd as cmd_obj

            executor = PymolBatchExecutor(
                plan,
                snapshot.path.parent,
                cmd_obj,
                quiet=1,
                cancel_requested=self.cancellation.is_cancelled,
            )
            self.session = BatchRunSession(
                plan,
                snapshot.plan_bytes,
                output,
                executor,
                software_version=VERSION,
                software_commit=_git_commit(),
                cancel_requested=self.cancellation.is_cancelled,
            )
            self.session.start()
        except (BatchContractError, BatchInputRejected, BatchExecutionFailed, OSError):
            self.session = None
            self.current_request_id = None
            self.cancellation = None
            self._set_state(FAILED, "BATCH_START_FAILED")
            return
        if generation != self.generation:
            self.session.abort()
            self.session = None
            return
        self.completed_result = None
        self._selected_bundle = None
        self.set_single_run_busy(True)
        self._set_state(RUNNING, "Batch queue started on the PyMOL main thread.")
        self.timer.start(0)

    def _pump(self):
        session = self.session
        generation = self.run_generation
        if session is None or self.state not in {RUNNING, CANCELLING}:
            return
        if generation is None or generation != self.generation:
            return
        if session.done:
            self._finalize_session(generation)
            return
        job = session.current_job
        if self._run_delivery_current() and job is not None:
            self.current_job.setText(str(job["id"]))
            self.current_mode.setText(str(job["analysis"]["mode"]))
        try:
            item = session.execute_next()
        except Exception:
            session.abort()
            self.session = None
            self._finish_failed("BATCH_EXECUTION_FAILED")
            return
        if generation != self.generation:
            return
        if self._run_delivery_current():
            row = len(session.results) - 1
            for column, value in (
                (4, item["status"]),
                (5, item["report_schema"] or ""),
                (6, "" if item["review_items_count"] is None else item["review_items_count"]),
                (7, item["error_code"] or ""),
            ):
                self.queue.setItem(row, column, self.QtWidgets.QTableWidgetItem(str(value)))
            completed = len(session.results)
            self.progress.setValue(completed)
            self.progress_label.setText(f"{completed} / {session.total_jobs}")
        self.timer.start(0)

    def _finalize_session(self, generation: int):
        session = self.session
        snapshot = self.validated_plan
        if session is None or snapshot is None:
            return
        try:
            result = session.finalize()
            bundle = inspect_result_bundle(session.root / MANIFEST_NAME)
        except Exception:
            self.session = None
            self._finish_failed("BATCH_FINALIZE_FAILED")
            return
        deliver = self._run_delivery_current()
        self.session = None
        self.cancellation = None
        self.current_request_id = None
        self.run_generation = None
        self.run_delivery_generation = None
        if generation != self.generation:
            return
        self.completed_result = bundle
        self._selected_bundle = bundle
        self._add_history(snapshot.path.name, bundle)
        if result["overall_status"] == "CANCELLED":
            state = CANCELLED
        elif result["overall_status"] in {"FAILED_FAST", "COMPLETED_WITH_ERRORS"}:
            state = FAILED
        else:
            state = COMPLETED
        if deliver:
            self._render_bundle(bundle)
            self._set_state(state, "Batch result finalized and verified.")
        else:
            self.state = state
            if self._ui_active:
                self.run_state.setText(state)
                self.status_message.setText("Prior batch finalized after dialog close.")
                self._sync_controls()
        self.set_single_run_busy(False)

    def _finish_failed(self, code: str):
        deliver = self._run_delivery_current()
        self.cancellation = None
        self.current_request_id = None
        self.run_generation = None
        self.run_delivery_generation = None
        if self.validated_plan is not None:
            self.history.append(
                SessionHistoryEntry(
                    self.validated_plan.path.name,
                    self.validated_plan.sha256,
                    None,
                    FAILED,
                    "",
                    tuple(),
                    "",
                )
            )
            if deliver:
                self._render_history()
        if deliver:
            self._set_state(FAILED, code)
        else:
            self.state = FAILED
            if self._ui_active:
                self.run_state.setText(FAILED)
                self.status_message.setText("Prior batch failed after dialog close.")
                self._sync_controls()
        self.set_single_run_busy(False)

    def cancel_batch(self):
        if self.state not in {RUNNING, CANCELLING} or self.cancellation is None:
            return
        self.cancellation.request()
        self._set_state(CANCELLING, "Cancellation requested; no later job will begin.")
        if not self.timer.isActive():
            self.timer.start(0)

    def shutdown(self):
        self._ui_active = False
        self.delivery_generation += 1
        if self.state in {RUNNING, CANCELLING} and self.cancellation is not None:
            self.cancellation.request()
            self.state = CANCELLING
            if not self.timer.isActive():
                self.timer.start(0)
        else:
            self.generation += 1

    def reactivate(self):
        self._ui_active = True
        self.run_state.setText(self.state)
        if self.completed_result is not None and self.session is None:
            self._render_bundle(self.completed_result)
        self._render_history()
        self._sync_controls()

    def _run_delivery_current(self) -> bool:
        return (
            self._ui_active
            and self.run_delivery_generation is not None
            and self.run_delivery_generation == self.delivery_generation
        )

    def _add_history(self, plan_name: str, bundle: VerifiedBatchResult):
        self.history.append(
            SessionHistoryEntry(
                plan_name,
                bundle.plan_sha256,
                bundle.manifest_path,
                bundle.overall_status,
                bundle.completed_at,
                tuple(sorted(bundle.counts.items())),
                bundle.identity_core_sha256,
            )
        )
        if self._ui_active:
            self._render_history()

    def clear_history(self):
        if self.state in {RUNNING, CANCELLING}:
            return
        self.history.clear()
        self._render_history()

    def _render_history(self):
        self.history_table.setRowCount(len(self.history))
        for row, entry in enumerate(self.history):
            total = dict(entry.counts).get("total", 0)
            values = (
                entry.plan_name,
                entry.overall_status,
                entry.completed_at,
                str(total),
                entry.identity_core_sha256,
            )
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, self.QtWidgets.QTableWidgetItem(str(value)))

    def _open_existing(self):
        if self.state in {RUNNING, CANCELLING}:
            return
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.parent,
            "Open existing batch result manifest",
            "",
            "Batch result (*.json);;All files (*)",
        )
        if path:
            self.open_result(path)

    def _open_selected_history(self):
        if self.state in {RUNNING, CANCELLING}:
            return
        row = self.history_table.currentRow()
        entries = list(self.history)
        if 0 <= row < len(entries) and entries[row].manifest_path is not None:
            self.open_result(entries[row].manifest_path)

    def open_result(self, path: str | Path) -> bool:
        if self.state in {RUNNING, CANCELLING}:
            return False
        try:
            bundle = inspect_result_bundle(path)
        except BatchResultBrowserError:
            self._set_state(FAILED, "RESULT_BUNDLE_INVALID")
            return False
        self.completed_result = bundle
        self._selected_bundle = bundle
        self._render_bundle(bundle)
        self._add_history(Path(path).name, bundle)
        self._set_state(COMPLETED, "Existing result manifest verified.")
        return True

    def _render_bundle(self, bundle: VerifiedBatchResult):
        counts = ", ".join(f"{key}={value}" for key, value in bundle.counts.items())
        self.result_summary.setPlainText(
            "\n".join(
                (
                    f"Operational status: {bundle.overall_status}",
                    f"Counts: {counts}",
                    f"Plan digest: {bundle.plan_sha256}",
                    f"Identity core: {bundle.identity_core_sha256}",
                    f"Software: {bundle.software_version}",
                    f"Started: {bundle.started_at}",
                    f"Completed: {bundle.completed_at}",
                    f"Manifest: {bundle.manifest_sha256} ({bundle.manifest_size} bytes)",
                    "Operational index only; not a biological verdict.",
                )
            )
        )
        self.queue.setRowCount(len(bundle.jobs))
        for row, job in enumerate(bundle.jobs):
            values = (
                str(row + 1),
                job.job_id,
                job.mode,
                "Explicit plan input",
                job.status,
                job.report_schema or "",
                "" if job.review_items_count is None else str(job.review_items_count),
                job.error_code or "",
            )
            for column, value in enumerate(values):
                self.queue.setItem(row, column, self.QtWidgets.QTableWidgetItem(value))
        self._render_selected_job()

    def _selected_job(self):
        bundle = self._selected_bundle
        row = self.queue.currentRow()
        if bundle is None or not (0 <= row < len(bundle.jobs)):
            return None
        return bundle.jobs[row]

    def _render_selected_job(self):
        job = self._selected_job()
        if job is None:
            self.selected_job_details.setPlainText("")
            self._sync_controls()
            return
        lines = [
            f"Job: {job.job_id}",
            f"Mode: {job.mode}",
            f"Status: {job.status}",
            f"Report schema: {job.report_schema or 'none'}",
            f"Warnings: {job.warnings_count}",
            f"Review items: {job.review_items_count if job.review_items_count is not None else 'n/a'}",
            f"Coordinate preserved: {job.coordinate_preserved}",
        ]
        for key, value in job.summary.items():
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
        self.selected_job_details.setPlainText("\n".join(lines))
        self._sync_controls()

    def _open_local(self, path: Path) -> bool:
        desktop = getattr(self.QtGui, "QDesktopServices", None)
        url = getattr(self.QtCore, "QUrl", None)
        if desktop is None or url is None:
            return False
        return bool(desktop.openUrl(url.fromLocalFile(str(path))))

    def _open_manifest(self):
        if self.state in {RUNNING, CANCELLING}:
            return
        bundle = self._selected_bundle
        if bundle is None:
            return
        try:
            current = inspect_result_bundle(bundle.manifest_path)
            if current.manifest_sha256 != bundle.manifest_sha256:
                raise BatchResultBrowserError("RESULT_MANIFEST_CHANGED")
            opened = self._open_local(bundle.manifest_path)
        except BatchResultBrowserError:
            opened = False
        if not opened:
            self._set_state(self.state, "RESULT_MANIFEST_UNAVAILABLE")

    def _open_output(self):
        if self.state in {RUNNING, CANCELLING}:
            return
        bundle = self._selected_bundle
        if bundle is None:
            return
        try:
            current = inspect_result_bundle(bundle.manifest_path)
            opened = current.output_root == bundle.output_root and self._open_local(
                bundle.output_root
            )
        except BatchResultBrowserError:
            opened = False
        if not opened:
            self._set_state(self.state, "OUTPUT_DIRECTORY_UNAVAILABLE")

    def _reveal_selected(self, role: str):
        if self.state in {RUNNING, CANCELLING}:
            return
        bundle = self._selected_bundle
        job = self._selected_job()
        artifact: VerifiedArtifact | None = None if job is None else getattr(job, role)
        if bundle is None or artifact is None:
            return
        try:
            opened = self._open_local(revalidate_artifact(bundle, artifact))
        except BatchResultBrowserError:
            opened = False
        if not opened:
            self._set_state(self.state, "OUTPUT_UNAVAILABLE")

    def _sync_controls(self, *_):
        active = self.state in {RUNNING, CANCELLING}
        ready = self.state == READY and self.validated_plan is not None
        output_ready = bool(str(self.output_path.text()).strip())
        self.run_button.setEnabled(ready and output_ready)
        self.cancel_button.setEnabled(active)
        for widget in (
            self.plan_path,
            self.output_path,
            self.browse_plan_button,
            self.browse_output_button,
            self.validate_button,
        ):
            widget.setEnabled(not active)
        bundle = self._selected_bundle
        job = self._selected_job() if bundle is not None else None
        self.open_manifest_button.setEnabled(not active and bundle is not None)
        self.open_output_button.setEnabled(not active and bundle is not None)
        self.reveal_report_button.setEnabled(
            not active
            and job is not None
            and job.report is not None
            and job.report.availability == "VERIFIED"
        )
        self.reveal_csv_button.setEnabled(
            not active
            and job is not None
            and job.csv is not None
            and job.csv.availability == "VERIFIED"
        )
        self.open_existing_button.setEnabled(not active)
        self.open_history_button.setEnabled(not active and bool(self.history))
        self.clear_history_button.setEnabled(not active and bool(self.history))
