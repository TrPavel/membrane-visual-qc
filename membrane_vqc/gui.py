"""Minimal Qt GUI for the PyMOL plugin."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import uuid

from .constants import DEFAULT_LIGAND_CUTOFF, DEFAULT_ZMAX, DEFAULT_ZMIN
from .commands import (
    mvqc_check,
    mvqc_check_orientation,
    mvqc_check_pdbtm,
    mvqc_check_pdbtm_cached,
    mvqc_color_hydropathy,
    mvqc_export,
    mvqc_ligand_shell,
    mvqc_slab,
    mvqc_slab_orientation,
    mvqc_slab_pdbtm,
    mvqc_slab_pdbtm_cached,
)
from .pdbtm_cache import PdbtmCacheRepository
from .pdbtm_errors import Stage4BError
from .pdbtm_gui_worker import make_worker_class
from .pdbtm_provider import canonicalize_record_id
from .pdbtm_worker import WorkerFailure
from .qc import format_summary

_DIALOG = None
LEGACY_MODE = "Legacy global-z"
ORIENTATION_FILE_MODE = "Planar orientation file"
PDBTM_MODE = "PDBTM offline pair"
PLANAR_REVIEW_STATUS = "Running planar membrane review\u2026"
PLANAR_BOUNDARIES_STATUS = "Creating planar membrane boundaries\u2026"
PDBTM_REVIEW_STATUS = "Resolving offline PDBTM orientation\u2026"
PDBTM_BOUNDARIES_STATUS = "Resolving offline PDBTM boundaries\u2026"
BROWSE_LABEL = "Browse\u2026"

PDBTM_SOURCE_LOCAL = "Local files"
PDBTM_SOURCE_CACHED = "Validated cache"

RETRIEVAL_IDLE = "IDLE"
RETRIEVAL_INSPECTING_CACHE = "INSPECTING_CACHE"
RETRIEVAL_FETCHING = "FETCHING"
RETRIEVAL_CANCELLING = "CANCELLING"
RETRIEVAL_AVAILABLE = "AVAILABLE"
RETRIEVAL_FAILED = "FAILED"
RETRIEVAL_CANCELLED = "CANCELLED"

SELECTION_LOCAL_FILES = "LOCAL_FILES"
SELECTION_CACHED_UNSELECTED = "CACHED_UNSELECTED"
SELECTION_CACHED_SELECTED = "CACHED_SELECTED"
SELECTION_CACHED_SELECTION_UNAVAILABLE = "CACHED_SELECTION_UNAVAILABLE"


@dataclass(frozen=True)
class GUIInputs:
    """Validated GUI analysis inputs, independent of Qt."""

    selection: str
    zmin: float
    zmax: float
    ligand: str
    cutoff: float


@dataclass(frozen=True)
class SlabInputs:
    """Validated membrane-boundary inputs."""

    zmin: float
    zmax: float


@dataclass(frozen=True)
class LigandShellInputs:
    """Validated ligand-neighbour search inputs."""

    selection: str
    ligand: str
    cutoff: float


def parse_gui_inputs(selection, zmin, zmax, ligand, cutoff) -> GUIInputs:
    """Parse and validate GUI text without importing or opening Qt."""
    protein = parse_selection(selection)
    slab = parse_slab_inputs(zmin, zmax)
    shell = parse_ligand_shell_inputs(protein, ligand, cutoff)
    return GUIInputs(protein, slab.zmin, slab.zmax, shell.ligand, shell.cutoff)


def parse_selection(value) -> str:
    """Return a non-empty protein selection."""
    selection = str(value).strip()
    if not selection:
        raise ValueError("Protein selection must not be empty.")
    return selection


def parse_slab_inputs(zmin, zmax) -> SlabInputs:
    """Validate only the fields needed to display the membrane slab."""
    lower = _parse_finite(zmin, "zmin")
    upper = _parse_finite(zmax, "zmax")
    if lower >= upper:
        raise ValueError("zmin must be less than zmax.")
    return SlabInputs(lower, upper)


def parse_ligand_shell_inputs(selection, ligand, cutoff) -> LigandShellInputs:
    """Validate only the fields needed for a ligand-neighbour search."""
    selection = parse_selection(selection)
    distance = _parse_finite(cutoff, "Ligand cutoff")
    if distance <= 0:
        raise ValueError("Ligand cutoff must be greater than zero.")
    return LigandShellInputs(selection, str(ligand).strip(), distance)


def parse_export_path(value) -> Path:
    """Return a non-empty export path; write errors are reported by the caller."""
    text = str(value).strip()
    if not text:
        raise ValueError("Export path must not be empty.")
    return Path(text)


def _parse_finite(value, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite.")
    return number


def show_dialog():
    """Open the Membrane Visual QC dialog."""
    global _DIALOG
    try:
        from pymol.Qt import QtCore, QtGui, QtWidgets
    except Exception as exc:
        print(f"Could not open Membrane Visual QC GUI: {exc}")
        return None

    if _DIALOG is None:
        _DIALOG = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
    _DIALOG.show()
    _DIALOG.raise_()
    return _DIALOG


class MembraneVQCDialog:
    """Small wrapper class so imports stay lazy outside PyMOL."""

    def __init__(self, QtWidgets, QtGui=None, QtCore=None):
        self.QtWidgets = QtWidgets
        self.QtGui = QtGui
        self.QtCore = QtCore
        self._session_id = uuid.uuid4().hex
        self._generation = 0
        self._request_seq = 0
        self._pending_request_id = None
        self._pending_use_cached_record_id = None
        self._pending_clear_record_id = None
        self._retrieval_state = RETRIEVAL_IDLE
        self._selection_state = SELECTION_LOCAL_FILES
        self._cached_snapshot = None
        self._cached_snapshot_record_id = None
        self._cached_snapshot_generation = None
        self._last_inspect = (None, None)
        self._worker = None
        self._worker_thread = None
        self.window = QtWidgets.QDialog()
        self.window.setWindowTitle("Membrane Visual QC")
        layout = QtWidgets.QFormLayout(self.window)

        self.selection = QtWidgets.QLineEdit("all")
        self.orientation_mode = QtWidgets.QComboBox()
        self.orientation_mode.addItems([LEGACY_MODE, ORIENTATION_FILE_MODE, PDBTM_MODE])
        self.orientation_file = QtWidgets.QLineEdit("")
        self.pdbtm_json = QtWidgets.QLineEdit("")
        self.transformed_pdb = QtWidgets.QLineEdit("")
        self.biological_assembly = QtWidgets.QLineEdit("")
        self.browse_pdbtm_json = QtWidgets.QPushButton(BROWSE_LABEL)
        self.browse_transformed_pdb = QtWidgets.QPushButton(BROWSE_LABEL)
        self.pdbtm_source = QtWidgets.QComboBox()
        self.pdbtm_source.addItems([PDBTM_SOURCE_LOCAL, PDBTM_SOURCE_CACHED])
        self.cached_record_id = QtWidgets.QLineEdit("")
        self.fetch_button = QtWidgets.QPushButton("Fetch / Refresh")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cache_status = QtWidgets.QLabel("")
        self.cache_metadata = QtWidgets.QTextEdit()
        self.cache_metadata.setReadOnly(True)
        self.use_cached_button = QtWidgets.QPushButton("Use cached pair")
        self.open_cache_location_button = QtWidgets.QPushButton("Open cache location")
        self.clear_cached_button = QtWidgets.QPushButton("Clear cached record")
        self.orientation_source = QtWidgets.QLabel("manual_global_z")
        self.zmin = QtWidgets.QLineEdit(str(DEFAULT_ZMIN))
        self.zmax = QtWidgets.QLineEdit(str(DEFAULT_ZMAX))
        self.ligand = QtWidgets.QLineEdit("organic")
        self.cutoff = QtWidgets.QLineEdit(str(DEFAULT_LIGAND_CUTOFF))
        self.export_path = QtWidgets.QLineEdit("reports/mvqc_report.json")
        self.analyze_context = QtWidgets.QCheckBox("Analyze exposure and local context")
        self.exposure_quality = QtWidgets.QComboBox()
        self.exposure_quality.addItems(["Fast", "Standard", "High"])
        self.exposure_quality.setCurrentText("Standard")
        self.exposure_backend = QtWidgets.QComboBox()
        self.exposure_backend.addItems(["Built-in", "Auto", "FreeSASA reference"])
        self.summary = QtWidgets.QTextEdit()
        self.summary.setReadOnly(True)

        if QtGui is not None:
            numeric = QtGui.QDoubleValidator()
            numeric.setNotation(QtGui.QDoubleValidator.StandardNotation)
            positive = QtGui.QDoubleValidator()
            positive.setBottom(0.0)
            positive.setNotation(QtGui.QDoubleValidator.StandardNotation)
            self.zmin.setValidator(numeric)
            self.zmax.setValidator(numeric)
            self.cutoff.setValidator(positive)

        layout.addRow("Selection", self.selection)
        layout.addRow("Orientation mode", self.orientation_mode)
        layout.addRow("Orientation JSON", self.orientation_file)
        json_row = QtWidgets.QHBoxLayout()
        json_row.addWidget(self.pdbtm_json)
        json_row.addWidget(self.browse_pdbtm_json)
        layout.addRow("PDBTM JSON", json_row)
        pdb_row = QtWidgets.QHBoxLayout()
        pdb_row.addWidget(self.transformed_pdb)
        pdb_row.addWidget(self.browse_transformed_pdb)
        layout.addRow("Transformed PDB", pdb_row)
        layout.addRow("Current assembly (optional)", self.biological_assembly)
        layout.addRow("PDBTM source", self.pdbtm_source)
        layout.addRow("Canonical record ID", self.cached_record_id)
        fetch_row = QtWidgets.QHBoxLayout()
        fetch_row.addWidget(self.fetch_button)
        fetch_row.addWidget(self.cancel_button)
        layout.addRow(fetch_row)
        layout.addRow("Cache status", self.cache_status)
        layout.addRow("Cache metadata", self.cache_metadata)
        cache_actions_row = QtWidgets.QHBoxLayout()
        cache_actions_row.addWidget(self.use_cached_button)
        cache_actions_row.addWidget(self.open_cache_location_button)
        cache_actions_row.addWidget(self.clear_cached_button)
        layout.addRow(cache_actions_row)
        layout.addRow("Orientation source", self.orientation_source)
        layout.addRow("zmin", self.zmin)
        layout.addRow("zmax", self.zmax)
        layout.addRow("Ligand selection", self.ligand)
        layout.addRow("Cutoff", self.cutoff)
        layout.addRow("Export path", self.export_path)
        layout.addRow(self.analyze_context)
        layout.addRow("Exposure quality", self.exposure_quality)
        layout.addRow("Exposure backend", self.exposure_backend)

        buttons = QtWidgets.QHBoxLayout()
        self.action_buttons = []
        for label, callback in (
            ("Run QC", self.run_qc),
            ("Show Slab", self.show_slab),
            ("Colour Hydropathy", self.colour_hydropathy),
            ("Ligand Shell", self.ligand_shell),
            ("Export JSON", self.export_json),
        ):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
            self.action_buttons.append(button)
        layout.addRow(buttons)
        layout.addRow("Summary", self.summary)

        self.orientation_mode.currentTextChanged.connect(self._update_orientation_mode)
        self.browse_pdbtm_json.clicked.connect(self._browse_pdbtm_json)
        self.browse_transformed_pdb.clicked.connect(self._browse_transformed_pdb)
        self.pdbtm_source.currentTextChanged.connect(self._on_pdbtm_source_changed)
        self.cached_record_id.editingFinished.connect(self._on_cached_record_id_edited)
        self.fetch_button.clicked.connect(self._on_fetch_clicked)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.use_cached_button.clicked.connect(self._on_use_cached_clicked)
        self.open_cache_location_button.clicked.connect(self._on_open_cache_location_clicked)
        self.clear_cached_button.clicked.connect(self._on_clear_cached_clicked)
        self.window.finished.connect(self._teardown_worker)
        self._update_orientation_mode()

    def show(self):
        self.window.show()

    def raise_(self):
        self.window.raise_()

    def run_qc(self):
        if self.orientation_mode.currentText() == PDBTM_MODE:
            values = self._parse_or_error(
                parse_ligand_shell_inputs,
                self.selection.text(),
                self.ligand.text(),
                self.cutoff.text(),
            )
            if values is None:
                return
            if self._is_cached_source():
                if (
                    self._cached_snapshot is None
                    or self._selection_state != SELECTION_CACHED_SELECTED
                ):
                    self._show_error("Press Use cached pair before running QC.")
                    return
                self.orientation_source.setText("unavailable")
                self._execute(
                    PDBTM_REVIEW_STATUS,
                    lambda: mvqc_check_pdbtm_cached(
                        self._cached_snapshot,
                        selection=values.selection,
                        biological_assembly=str(self.biological_assembly.text()).strip(),
                        ligand=values.ligand,
                        cutoff=values.cutoff,
                        quiet=1,
                        cache_generation=self._cached_snapshot_generation,
                        **self._context_options(),
                    ),
                    self._render_pdbtm_report,
                )
                return
            self.orientation_source.setText("unavailable")
            self._execute(
                PDBTM_REVIEW_STATUS,
                lambda: mvqc_check_pdbtm(
                    selection=values.selection,
                    pdbtm_json=str(self.pdbtm_json.text()).strip(),
                    transformed_pdb=str(self.transformed_pdb.text()).strip(),
                    biological_assembly=str(self.biological_assembly.text()).strip(),
                    ligand=values.ligand,
                    cutoff=values.cutoff,
                    quiet=1,
                    **self._context_options(),
                ),
                self._render_pdbtm_report,
            )
            return
        if self.orientation_mode.currentText() == ORIENTATION_FILE_MODE:
            values = self._parse_or_error(
                parse_ligand_shell_inputs,
                self.selection.text(),
                self.ligand.text(),
                self.cutoff.text(),
            )
            if values is None:
                return
            orientation_path = str(self.orientation_file.text()).strip()
            self.orientation_source.setText("unavailable")
            self._execute(
                PLANAR_REVIEW_STATUS,
                lambda: mvqc_check_orientation(
                    selection=values.selection,
                    orientation_file=orientation_path,
                    ligand=values.ligand,
                    cutoff=values.cutoff,
                    quiet=1,
                    **self._context_options(),
                ),
                self._render_planar_report,
            )
            return
        values = self._inputs_or_error()
        if values is None:
            return
        self.orientation_source.setText("manual_global_z")
        self._execute(
            "Running membrane review\u2026",
            lambda: mvqc_check(
                selection=values.selection,
                zmin=values.zmin,
                zmax=values.zmax,
                ligand=values.ligand,
                cutoff=values.cutoff,
                quiet=1,
                **self._context_options(),
            ),
            format_summary,
        )

    def show_slab(self):
        if self.orientation_mode.currentText() == PDBTM_MODE:
            selection = self._parse_or_error(parse_selection, self.selection.text())
            if selection is None:
                return
            if self._is_cached_source():
                if (
                    self._cached_snapshot is None
                    or self._selection_state != SELECTION_CACHED_SELECTED
                ):
                    self._show_error("Press Use cached pair before showing the slab.")
                    return
                self.orientation_source.setText("unavailable")
                self._execute(
                    PDBTM_BOUNDARIES_STATUS,
                    lambda: mvqc_slab_pdbtm_cached(
                        self._cached_snapshot,
                        selection=selection,
                        biological_assembly=str(self.biological_assembly.text()).strip(),
                    ),
                    self._render_pdbtm_slab,
                )
                return
            self.orientation_source.setText("unavailable")
            self._execute(
                PDBTM_BOUNDARIES_STATUS,
                lambda: mvqc_slab_pdbtm(
                    selection=selection,
                    pdbtm_json=str(self.pdbtm_json.text()).strip(),
                    transformed_pdb=str(self.transformed_pdb.text()).strip(),
                    biological_assembly=str(self.biological_assembly.text()).strip(),
                ),
                self._render_pdbtm_slab,
            )
            return
        if self.orientation_mode.currentText() == ORIENTATION_FILE_MODE:
            selection = self._parse_or_error(parse_selection, self.selection.text())
            if selection is None:
                return
            orientation_path = str(self.orientation_file.text()).strip()
            self.orientation_source.setText("unavailable")
            self._execute(
                PLANAR_BOUNDARIES_STATUS,
                lambda: mvqc_slab_orientation(selection, orientation_path),
                self._render_planar_slab,
            )
            return
        values = self._parse_or_error(
            parse_slab_inputs,
            self.zmin.text(),
            self.zmax.text(),
        )
        if values is not None:
            self._execute(
                "Creating membrane boundaries\u2026",
                lambda: mvqc_slab(values.zmin, values.zmax),
                lambda _: "Membrane boundaries updated.",
            )

    def colour_hydropathy(self):
        values = self._parse_or_error(parse_selection, self.selection.text())
        if values is not None:
            self._execute(
                "Applying hydropathy colours\u2026",
                lambda: mvqc_color_hydropathy(values),
                lambda residues: f"Hydropathy coloured residues: {len(residues)}",
            )

    def ligand_shell(self):
        values = self._parse_or_error(
            parse_ligand_shell_inputs,
            self.selection.text(),
            self.ligand.text(),
            self.cutoff.text(),
        )
        if values is not None:
            self._execute(
                "Finding ligand neighbours\u2026",
                lambda: mvqc_ligand_shell(
                    protein=values.selection,
                    ligand=values.ligand,
                    cutoff=values.cutoff,
                ),
                lambda neighbours: (
                    "Ligand selection is empty; ligand context was cleared."
                    if not values.ligand
                    else f"Ligand-neighbour residues: {len(neighbours)}"
                ),
            )

    def export_json(self):
        try:
            path = parse_export_path(self.export_path.text())
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self._execute(
            "Exporting report\u2026",
            lambda: mvqc_export(str(path)),
            lambda written: "Exported: " + ", ".join(str(item) for item in written),
        )

    def _inputs_or_error(self):
        return self._parse_or_error(
            parse_gui_inputs,
            self.selection.text(),
            self.zmin.text(),
            self.zmax.text(),
            self.ligand.text(),
            self.cutoff.text(),
        )

    def _context_options(self):
        checkbox = getattr(self, "analyze_context", None)
        enabled = bool(checkbox.isChecked()) if checkbox is not None else False
        quality = getattr(self, "exposure_quality", None)
        backend = getattr(self, "exposure_backend", None)
        return {
            "analyze_context": int(enabled),
            "exposure_quality": quality.currentText() if quality is not None else "Standard",
            "exposure_backend": backend.currentText() if backend is not None else "Built-in",
        }

    def _render_planar_report(self, report):
        self.orientation_source.setText(_orientation_source(report.get("orientation")))
        return format_summary(report)

    def _render_planar_slab(self, membrane):
        self.orientation_source.setText(_orientation_source(membrane))
        return "Planar membrane boundaries updated."

    def _render_pdbtm_report(self, report):
        evidence = report.get("orientation", {}).get("evidence", {})
        status, details = _pdbtm_status_and_details(evidence)
        acquisition = report.get("orientation", {}).get("acquisition")
        if acquisition:
            details += "\n\n" + _acquisition_details(acquisition)
        self.orientation_source.setText(status)
        return format_summary(report) + "\n\n" + details

    def _render_pdbtm_slab(self, imported):
        evidence = imported.evidence.as_dict()
        status, details = _pdbtm_status_and_details(evidence)
        self.orientation_source.setText(status)
        return "PDBTM membrane boundaries updated.\n\n" + details

    def _update_orientation_mode(self, *_):
        mode = self.orientation_mode.currentText()
        legacy = mode == LEGACY_MODE
        planar = mode == ORIENTATION_FILE_MODE
        pdbtm = mode == PDBTM_MODE
        self.zmin.setEnabled(legacy)
        self.zmax.setEnabled(legacy)
        self.orientation_file.setEnabled(planar)
        self.biological_assembly.setEnabled(pdbtm)
        self.orientation_source.setText("manual_global_z" if legacy else "unavailable")
        self._sync_pdbtm_controls()

    def _is_cached_source(self) -> bool:
        return str(self.pdbtm_source.currentText()) == PDBTM_SOURCE_CACHED

    def _sync_pdbtm_controls(self):
        mode_is_pdbtm = self.orientation_mode.currentText() == PDBTM_MODE
        cached = mode_is_pdbtm and self._is_cached_source()
        local = mode_is_pdbtm and not self._is_cached_source()
        for widget in (
            self.pdbtm_json,
            self.transformed_pdb,
            self.browse_pdbtm_json,
            self.browse_transformed_pdb,
        ):
            widget.setEnabled(local)
        for widget in (self.pdbtm_source, self.cached_record_id):
            widget.setEnabled(mode_is_pdbtm)
        busy = self._pending_request_id is not None
        self.fetch_button.setEnabled(cached and not busy)
        self.cancel_button.setEnabled(cached and busy)
        self.use_cached_button.setEnabled(cached and not busy)
        self.clear_cached_button.setEnabled(cached and not busy)
        self.open_cache_location_button.setEnabled(mode_is_pdbtm)

    def _next_request_id(self) -> str:
        self._request_seq += 1
        return f"{self._session_id}:{self._generation}:{self._request_seq}"

    def _invalidate_active_request(self, *, request_cancel: bool = False):
        pending = self._pending_request_id
        self._generation += 1
        self._pending_request_id = None
        self._pending_use_cached_record_id = None
        self._pending_clear_record_id = None
        if pending is not None and request_cancel and self._worker is not None:
            self._worker.request_cancel.emit(pending)

    def _ensure_worker(self):
        if self._worker is not None:
            return self._worker
        if self.QtCore is None:
            return None
        worker_class = make_worker_class(self.QtCore)
        thread = self.QtCore.QThread()
        worker = worker_class()
        worker.moveToThread(thread)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(
            lambda finished_thread=thread: self._on_worker_thread_finished(finished_thread)
        )
        worker.inspect_finished.connect(self._on_inspect_finished)
        worker.fetch_finished.connect(self._on_fetch_finished)
        worker.use_cached_finished.connect(self._on_use_cached_finished)
        worker.clear_finished.connect(self._on_clear_finished)
        thread.start()
        self._worker = worker
        self._worker_thread = thread
        return worker

    def _on_worker_thread_finished(self, thread):
        # Only clear bookkeeping for the exact thread that just stopped; a
        # newer worker/thread pair may already have replaced it (e.g. a rapid
        # close-then-reopen). Deferring thread.deleteLater() to here (rather
        # than a bare thread.finished.connect(thread.deleteLater) alongside an
        # immediate `self._worker_thread = None` in _teardown_worker) is
        # deliberate: QThread.quit() is asynchronous, so dropping the last
        # Python reference to the QThread object immediately after calling it
        # risks Qt destroying a QThread wrapper while the underlying OS
        # thread is still running, which aborts the process.
        if self._worker_thread is thread:
            self._worker = None
            self._worker_thread = None
        thread.deleteLater()

    def _teardown_worker(self, *_):
        self._invalidate_active_request(request_cancel=True)
        if self._worker_thread is not None:
            self._worker_thread.quit()

    def _canonical_cached_record_id_or_error(self):
        text = str(self.cached_record_id.text()).strip()
        try:
            return canonicalize_record_id(text)
        except Stage4BError:
            self._show_error("Enter a four-character PDB ID such as 1pcr.")
            return None

    def _on_pdbtm_source_changed(self, *_):
        self._invalidate_active_request()
        if self._is_cached_source():
            self._selection_state = (
                SELECTION_CACHED_SELECTED
                if self._cached_snapshot is not None
                else SELECTION_CACHED_UNSELECTED
            )
            self._retrieval_state = RETRIEVAL_IDLE
            self._dispatch_inspect()
        else:
            self._selection_state = SELECTION_LOCAL_FILES
        self._sync_pdbtm_controls()

    def _on_cached_record_id_edited(self, *_):
        self._invalidate_active_request()
        self._cached_snapshot = None
        self._cached_snapshot_record_id = None
        self._cached_snapshot_generation = None
        self._selection_state = (
            SELECTION_CACHED_UNSELECTED if self._is_cached_source() else SELECTION_LOCAL_FILES
        )
        self._retrieval_state = RETRIEVAL_IDLE
        self._sync_pdbtm_controls()
        self._dispatch_inspect()

    def _dispatch_inspect(self):
        if not self._is_cached_source():
            return
        canonical = self._canonical_id_quiet()
        if canonical is None:
            self.cache_status.setText("")
            return
        worker = self._ensure_worker()
        if worker is None:
            return
        request_id = self._next_request_id()
        self._pending_request_id = request_id
        self._retrieval_state = RETRIEVAL_INSPECTING_CACHE
        self.cache_status.setText("Checking cached status\u2026")
        self._sync_pdbtm_controls()
        worker.request_inspect.emit(request_id, canonical)

    def _canonical_id_quiet(self):
        text = str(self.cached_record_id.text()).strip()
        try:
            return canonicalize_record_id(text)
        except Stage4BError:
            return None

    def _on_inspect_finished(self, request_id, result):
        if request_id != self._pending_request_id:
            return
        self._pending_request_id = None
        if isinstance(result, WorkerFailure):
            self._retrieval_state = RETRIEVAL_FAILED
            self.cache_status.setText(result.message)
            self._sync_pdbtm_controls()
            return
        self._retrieval_state = RETRIEVAL_IDLE
        self._last_inspect = (result.canonical_record_id, result.cache_generation)
        if result.record_present and result.active_snapshot_id is not None:
            self.cache_status.setText(
                f"Cached snapshot available ({result.snapshot_count} retained)."
            )
        else:
            self.cache_status.setText("No validated cached PDBTM pair is available.")
        self._sync_pdbtm_controls()

    def _on_fetch_clicked(self):
        if not self._is_cached_source():
            return
        canonical = self._canonical_cached_record_id_or_error()
        if canonical is None:
            return
        self._invalidate_active_request(request_cancel=True)
        worker = self._ensure_worker()
        if worker is None:
            self._show_error("Qt is not available for PDBTM retrieval.")
            return
        request_id = self._next_request_id()
        self._pending_request_id = request_id
        self._retrieval_state = RETRIEVAL_FETCHING
        self.cache_status.setText("Retrieving PDBTM pair\u2026")
        self._sync_pdbtm_controls()
        worker.request_fetch.emit(request_id, canonical)

    def _on_fetch_finished(self, request_id, result):
        if request_id != self._pending_request_id:
            return
        self._pending_request_id = None
        if isinstance(result, WorkerFailure):
            self._retrieval_state = RETRIEVAL_FAILED
            self.cache_status.setText(result.message)
            self._sync_pdbtm_controls()
            return
        self._retrieval_state = RETRIEVAL_AVAILABLE
        # A successful commit may have bumped the cache's index generation past
        # whatever an earlier inspect captured; discard that now-unreliable
        # value rather than let a later Use cached pair attach a stale one.
        self._last_inspect = (None, None)
        self.cache_status.setText(
            "A new validated snapshot is available. Press Use cached pair to select it."
        )
        self._sync_pdbtm_controls()

    def _on_cancel_clicked(self):
        if self._pending_request_id is None:
            return
        self._retrieval_state = RETRIEVAL_CANCELLING
        self._sync_pdbtm_controls()
        self._invalidate_active_request(request_cancel=True)
        self._retrieval_state = RETRIEVAL_CANCELLED
        self.cache_status.setText("PDBTM retrieval was cancelled.")
        self._sync_pdbtm_controls()

    def _on_use_cached_clicked(self):
        if not self._is_cached_source():
            return
        canonical = self._canonical_cached_record_id_or_error()
        if canonical is None:
            return
        self._invalidate_active_request()
        worker = self._ensure_worker()
        if worker is None:
            self._show_error("Qt is not available for PDBTM retrieval.")
            return
        request_id = self._next_request_id()
        self._pending_request_id = request_id
        self._pending_use_cached_record_id = canonical
        self.cache_status.setText("Validating cached pair\u2026")
        self._sync_pdbtm_controls()
        worker.request_use_cached.emit(request_id, canonical)

    def _on_use_cached_finished(self, request_id, result):
        if request_id != self._pending_request_id:
            return
        self._pending_request_id = None
        record_id = self._pending_use_cached_record_id
        self._pending_use_cached_record_id = None
        if isinstance(result, WorkerFailure):
            # Fail closed: a re-validation failure (corrupt/missing/conflicted)
            # must never leave a previously selected snapshot looking current,
            # since Run QC/Show Slab gate only on a snapshot being present.
            self._cached_snapshot = None
            self._cached_snapshot_record_id = None
            self._cached_snapshot_generation = None
            self._selection_state = SELECTION_CACHED_SELECTION_UNAVAILABLE
            self.cache_status.setText(result.message)
            self._sync_pdbtm_controls()
            return
        self._cached_snapshot = result
        self._cached_snapshot_record_id = record_id
        last_record_id, last_generation = self._last_inspect
        self._cached_snapshot_generation = last_generation if last_record_id == record_id else None
        self._selection_state = SELECTION_CACHED_SELECTED
        self.cache_status.setText("Validated cached pair selected.")
        self._render_cache_metadata(result)
        self._sync_pdbtm_controls()

    def _render_cache_metadata(self, snapshot):
        core = snapshot.snapshot_core
        text = (
            f"Record: {core.canonical_record_id}\n"
            f"Snapshot: {_abbreviate_id(snapshot.snapshot_id)}\n"
            f"Pair: {_abbreviate_id(core.pair_id)}\n"
            f"Provider resource/software: {core.provider_versions.resource_version} / "
            f"{core.provider_versions.software_version}\n"
            f"Validated at: {core.validated_at}\n"
            "Validation status: pair self-consistency confirmed; "
            "not evaluated against any currently loaded structure."
        )
        self.cache_metadata.setPlainText(text)

    def _on_clear_cached_clicked(self):
        if not self._is_cached_source():
            return
        canonical = self._canonical_cached_record_id_or_error()
        if canonical is None:
            return
        message_box = getattr(self.QtWidgets, "QMessageBox", None)
        if message_box is not None:
            confirmation = message_box.question(
                self.window,
                "Clear cached record",
                f"Clear the cached PDBTM record for {canonical}? This cannot be undone.",
            )
            yes = getattr(message_box, "Yes", None)
            if yes is not None and confirmation != yes:
                return
        self._invalidate_active_request()
        worker = self._ensure_worker()
        if worker is None:
            self._show_error("Qt is not available for PDBTM retrieval.")
            return
        request_id = self._next_request_id()
        self._pending_request_id = request_id
        self._pending_clear_record_id = canonical
        self.cache_status.setText("Clearing cached record\u2026")
        self._sync_pdbtm_controls()
        worker.request_clear.emit(request_id, canonical)

    def _on_clear_finished(self, request_id, result):
        if request_id != self._pending_request_id:
            return
        self._pending_request_id = None
        cleared_record_id = self._pending_clear_record_id
        self._pending_clear_record_id = None
        if isinstance(result, WorkerFailure):
            self.cache_status.setText(result.message)
            self._sync_pdbtm_controls()
            return
        if self._cached_snapshot_record_id == cleared_record_id:
            self._cached_snapshot = None
            self._cached_snapshot_record_id = None
            self._cached_snapshot_generation = None
            self._selection_state = SELECTION_CACHED_UNSELECTED
        self.cache_status.setText("Cached record cleared.")
        self.cache_metadata.setPlainText("")
        self._sync_pdbtm_controls()
        self._dispatch_inspect()

    def _on_open_cache_location_clicked(self):
        try:
            root = PdbtmCacheRepository().root
        except Exception:
            self._show_error("The PDBTM cache location is not available.")
            return
        opened = False
        desktop_services = getattr(self.QtGui, "QDesktopServices", None) if self.QtGui else None
        url_type = getattr(self.QtCore, "QUrl", None) if self.QtCore else None
        if desktop_services is not None and url_type is not None:
            opened = bool(desktop_services.openUrl(url_type.fromLocalFile(str(root))))
        if not opened:
            self._show_error("Could not open the cache location.")

    def _browse_pdbtm_json(self):
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            "Select PDBTM JSON",
            "",
            "PDBTM JSON (*.json);;All files (*)",
        )
        if path:
            self.pdbtm_json.setText(path)

    def _browse_transformed_pdb(self):
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            "Select transformed PDB",
            "",
            "Transformed PDB (*.pdb *.ent *.trpdb);;All files (*)",
        )
        if path:
            self.transformed_pdb.setText(path)

    def _parse_or_error(self, parser, *values):
        try:
            return parser(*values)
        except ValueError as exc:
            self._show_error(str(exc))
            return None

    def _execute(self, status, operation, render):
        self._set_busy(True)
        self.summary.setPlainText(status)
        try:
            application = getattr(self.QtWidgets, "QApplication", None)
            if application is not None:
                application.processEvents()
            result = operation()
            self.summary.setPlainText(render(result))
            return result
        except Exception as exc:
            self._show_error(str(exc) or exc.__class__.__name__)
            return None
        finally:
            self._set_busy(False)

    def _set_busy(self, busy):
        for button in self.action_buttons:
            button.setEnabled(not busy)

    def _show_error(self, message):
        text = f"Membrane Visual QC could not complete the action:\n{message}"
        self.summary.setPlainText(text)
        message_box = getattr(self.QtWidgets, "QMessageBox", None)
        if message_box is not None:
            message_box.warning(self.window, "Membrane Visual QC", text)


def _orientation_source(value) -> str:
    if isinstance(value, dict):
        source = str(value.get("source", "")).strip()
        if source:
            return source
    return "unavailable"


def _pdbtm_status_and_details(evidence) -> tuple[str, str]:
    if not isinstance(evidence, dict):
        return "unavailable", "PDBTM evidence is unavailable."
    source = evidence.get("source", {})
    mapping = evidence.get("coordinate_mapping", {})
    source_geometry = evidence.get("source_geometry", {})
    record_id = str(source.get("record_id", "") or "unknown")
    method = str(mapping.get("method", "") or "unknown")
    confidence = str(evidence.get("geometric_confidence", "") or "unknown").replace("_", " ")
    display_method = method.replace("_", " ")
    status = f"PDBTM {record_id} \u00b7 {display_method} \u00b7 {confidence}"
    metric_key = "runtime_identity" if method == "identity" else "runtime_inverse"
    metrics = mapping.get("metrics", {}).get(metric_key, {})
    matched = metrics.get("matched_atom_count", "unavailable")
    rmsd = metrics.get("rmsd")
    maximum = metrics.get("maximum_residual")
    upper = source_geometry.get("upper_offset")
    warnings = evidence.get("warnings", [])
    warning_text = (
        "; ".join(str(item.get("message", "")) for item in warnings if isinstance(item, dict))
        or "none"
    )
    details = (
        f"Record: {record_id}\n"
        f"Mapping: {method}\n"
        f"Matched atoms: {matched}\n"
        f"RMSD: {_format_measure(rmsd)} \u00c5\n"
        f"Maximum residual: {_format_measure(maximum)} \u00c5\n"
        f"Half-thickness: {_format_measure(upper)} \u00c5\n"
        f"Provider resource/software: {source.get('resource_version') or 'unavailable'} / "
        f"{source.get('software_version') or 'unavailable'}\n"
        f"Warnings: {warning_text}\n"
        "Geometric applicability is not a biological correctness verdict."
    )
    return status, details


def _format_measure(value) -> str:
    try:
        return f"{float(value):.6g}"
    except (TypeError, ValueError):
        return "unavailable"


def _abbreviate_id(value) -> str:
    text = str(value)
    return text[:12] + "\u2026" if len(text) > 12 else text


def _acquisition_details(acquisition) -> str:
    if not isinstance(acquisition, dict):
        return ""
    versions = acquisition.get("provider_versions", {}) or {}
    applicability = (acquisition.get("object_applicability", {}) or {}).get("statement", "")
    return (
        f"Cached pair: {_abbreviate_id(acquisition.get('pair_id', ''))} "
        f"(snapshot {_abbreviate_id(acquisition.get('snapshot_id', ''))})\n"
        f"Consumption mode: {acquisition.get('consumption_mode', 'unavailable')}\n"
        f"Cache provider resource/software: {versions.get('resource_version', 'unavailable')} / "
        f"{versions.get('software_version', 'unavailable')}\n"
        f"{applicability}"
    )
