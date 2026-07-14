"""Minimal Qt GUI for the PyMOL plugin."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

from .constants import DEFAULT_LIGAND_CUTOFF, DEFAULT_ZMAX, DEFAULT_ZMIN
from .commands import (
    mvqc_check,
    mvqc_check_orientation,
    mvqc_color_hydropathy,
    mvqc_export,
    mvqc_ligand_shell,
    mvqc_slab,
    mvqc_slab_orientation,
)
from .qc import format_summary

_DIALOG = None
LEGACY_MODE = "Legacy global-z"
ORIENTATION_FILE_MODE = "Planar orientation file"
PLANAR_REVIEW_STATUS = "Running planar membrane review…"
PLANAR_BOUNDARIES_STATUS = "Creating planar membrane boundaries…"


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
        self.orientation_mode.addItems([LEGACY_MODE, ORIENTATION_FILE_MODE])
        self.orientation_file = QtWidgets.QLineEdit("")
        self.orientation_source = QtWidgets.QLabel("manual_global_z")
        self.zmin = QtWidgets.QLineEdit(str(DEFAULT_ZMIN))
        self.zmax = QtWidgets.QLineEdit(str(DEFAULT_ZMAX))
        self.ligand = QtWidgets.QLineEdit("organic")
        self.cutoff = QtWidgets.QLineEdit(str(DEFAULT_LIGAND_CUTOFF))
        self.export_path = QtWidgets.QLineEdit("reports/mvqc_report.json")
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
        layout.addRow("Orientation source", self.orientation_source)
        layout.addRow("zmin", self.zmin)
        layout.addRow("zmax", self.zmax)
        layout.addRow("Ligand selection", self.ligand)
        layout.addRow("Cutoff", self.cutoff)
        layout.addRow("Export path", self.export_path)

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

    def show(self):
        self.window.show()

    def raise_(self):
        self.window.raise_()

    def run_qc(self):
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
                ),
                self._render_planar_report,
            )
            return
        values = self._inputs_or_error()
        if values is None:
            return
        self.orientation_source.setText("manual_global_z")
        self._execute(
            "Running membrane review…",
            lambda: mvqc_check(
                selection=values.selection,
                zmin=values.zmin,
                zmax=values.zmax,
                ligand=values.ligand,
                cutoff=values.cutoff,
                quiet=1,
            ),
            format_summary,
        )

    def show_slab(self):
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
                "Creating membrane boundaries…",
                lambda: mvqc_slab(values.zmin, values.zmax),
                lambda _: "Membrane boundaries updated.",
            )

    def colour_hydropathy(self):
        values = self._parse_or_error(parse_selection, self.selection.text())
        if values is not None:
            self._execute(
                "Applying hydropathy colours…",
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
                "Finding ligand neighbours…",
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
            "Exporting report…",
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

    def _render_planar_report(self, report):
        self.orientation_source.setText(_orientation_source(report.get("orientation")))
        return format_summary(report)

    def _render_planar_slab(self, membrane):
        self.orientation_source.setText(_orientation_source(membrane))
        return "Planar membrane boundaries updated."

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
