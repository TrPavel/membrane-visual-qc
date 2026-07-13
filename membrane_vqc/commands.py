"""PyMOL command registrations for Membrane Visual QC."""

from __future__ import annotations

import math

from .constants import DEFAULT_LIGAND_CUTOFF, DEFAULT_ZMAX, DEFAULT_ZMIN
from . import qc
from .membrane import classify_residues, residue_dicts
from .neighbors import ligand_neighbor_residues
from .pymol_adapter import (
    MVQC_NAMES,
    clear_owned,
    color_hydropathy,
    create_slab,
    ligand_atoms,
    protein_atoms,
    show_ligand_shell,
)
from .report import export_report


def mvqc_check(
    selection: str = "all",
    zmin: float = DEFAULT_ZMIN,
    zmax: float = DEFAULT_ZMAX,
    ligand: str = "organic",
    cutoff: float = DEFAULT_LIGAND_CUTOFF,
    quiet: int = 1,
    export_path: str = "",
    input_path: str = "",
):
    """Run one-click membrane visual QC."""
    selection = _selection(selection)
    zmin, zmax = _slab(zmin, zmax)
    cutoff = _positive_float(cutoff, "cutoff")
    clear_owned()
    qc.LAST_REPORT = None
    try:
        return qc.run_check(
            selection,
            zmin,
            zmax,
            str(ligand).strip(),
            cutoff,
            int(quiet),
            export_path,
            input_path=str(input_path).strip(),
        )
    except Exception:
        # A failed run must not leave partial output looking current.
        clear_owned()
        qc.LAST_REPORT = None
        raise


def mvqc_slab(zmin: float = DEFAULT_ZMIN, zmax: float = DEFAULT_ZMAX):
    """Create membrane slab visual boundary objects."""
    zmin, zmax = _slab(zmin, zmax)
    create_slab(zmin, zmax)


def mvqc_color_hydropathy(selection: str = "all"):
    """Colour selected protein residues by a simple hydropathy scale."""
    selection = _selection(selection)
    atoms = protein_atoms(selection)
    residues = classify_residues(atoms, float("-inf"), float("inf"), interface_width=0)
    color_hydropathy(selection, residues)
    return residue_dicts(residues)


def mvqc_ligand_shell(
    protein: str = "all",
    ligand: str = "organic",
    cutoff: float = DEFAULT_LIGAND_CUTOFF,
):
    """Show residues near a ligand/cofactor selection."""
    protein = _selection(protein)
    ligand = str(ligand).strip()
    cutoff = _positive_float(cutoff, "cutoff")
    if not ligand:
        show_ligand_shell(protein, "", [])
        return []
    p_atoms = protein_atoms(protein)
    l_atoms = ligand_atoms(protein, ligand)
    neighbours = ligand_neighbor_residues(p_atoms, l_atoms, cutoff)
    show_ligand_shell(protein, ligand, neighbours)
    return [residue.identifier for residue in neighbours]


def mvqc_clear():
    """Remove Membrane Visual QC objects/selections and reset temporary report state."""
    clear_owned()
    qc.LAST_REPORT = None
    return sorted(MVQC_NAMES)


def _finite_float(value, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite.")
    return number


def _positive_float(value, label: str) -> float:
    number = _finite_float(value, label)
    if number <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return number


def _selection(value) -> str:
    selection = str(value).strip()
    if not selection:
        raise ValueError("selection must not be empty.")
    return selection


def _slab(zmin, zmax) -> tuple[float, float]:
    lower = _finite_float(zmin, "zmin")
    upper = _finite_float(zmax, "zmax")
    if lower >= upper:
        raise ValueError("zmin must be less than zmax.")
    return lower, upper


def mvqc_export(path: str = "reports/mvqc_report.json"):
    """Export the last QC summary as JSON and CSV."""
    if qc.LAST_REPORT is None:
        raise RuntimeError("No QC report is available yet. Run mvqc_check first.")
    written = export_report(qc.LAST_REPORT, path, write_csv=True)
    print("Exported Membrane Visual QC report: " + ", ".join(str(item) for item in written))
    return written


def register_commands(cmd_obj=None) -> None:
    """Register all PyMOL commands with cmd.extend."""
    if cmd_obj is None:
        from pymol import cmd as cmd_obj

    cmd_obj.extend("mvqc_check", mvqc_check)
    cmd_obj.extend("mvqc_slab", mvqc_slab)
    cmd_obj.extend("mvqc_color_hydropathy", mvqc_color_hydropathy)
    cmd_obj.extend("mvqc_ligand_shell", mvqc_ligand_shell)
    cmd_obj.extend("mvqc_export", mvqc_export)
    cmd_obj.extend("mvqc_clear", mvqc_clear)


try:
    register_commands()
except ModuleNotFoundError as exc:
    if exc.name != "pymol":
        raise
