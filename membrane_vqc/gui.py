"""Minimal Qt GUI for the PyMOL plugin."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

from .constants import DEFAULT_LIGAND_CUTOFF, DEFAULT_ZMAX, DEFAULT_ZMIN
from .commands import (
    mvqc_check,
    mvqc_check_orientation,
    mvqc_check_pdbtm,
    mvqc_color_hydropathy,
    mvqc_export,
    mvqc_ligand_shell,
    mvqc_slab,
    mvqc_slab_orientation,
    mvqc_slab_pdbtm,
)
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
        from pymol.Qt import QtGui, QtWidgets
    except Exception as exc:
        print(f"Could not open Membrane Visual QC GUI: {exc}")
        return None

    if _DIALOG is None:
        _DIALOG = MembraneVQCDialog(QtWidgets, QtGui)
    _DIALOG.show()
    _DIALOG.raise_()
    return _DIALOG


class MembraneVQCDialog:
    """Small wrapper class so imports stay lazy outside PyMOL."""

    def __init__(self, QtWidgets, QtGui=None):
        self.QtWidgets = QtWidgets
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
        for widget in (
            self.pdbtm_json,
            self.transformed_pdb,
            self.biological_assembly,
            self.browse_pdbtm_json,
            self.browse_transformed_pdb,
        ):
            widget.setEnabled(pdbtm)
        self.orientation_source.setText("manual_global_z" if legacy else "unavailable")

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
