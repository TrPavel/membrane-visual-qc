"""One-click QC orchestration."""

from __future__ import annotations

import math
from typing import Any

from .constants import DEFAULT_INTERFACE_WIDTH, DEFAULT_LIGAND_CUTOFF, DEFAULT_ZMAX, DEFAULT_ZMIN
from .errors import InputValidationError
from .membrane import classify_residues_for_membrane, flag_core_residues, residue_dicts
from .neighbors import ligand_neighbor_residues
from .orientation import PlanarMembrane, legacy_global_z
from .pymol_adapter import (
    color_hydropathy,
    create_membrane_planes,
    ligand_atoms,
    protein_atoms,
    show_ligand_shell,
    show_residue_selections,
)
from .report import build_report, export_report

LAST_REPORT: dict[str, Any] | None = None


def run_check(
    selection: str = "all",
    zmin: float = DEFAULT_ZMIN,
    zmax: float = DEFAULT_ZMAX,
    ligand: str = "organic",
    cutoff: float = DEFAULT_LIGAND_CUTOFF,
    quiet: int = 1,
    export_path: str = "",
    cmd_obj: Any | None = None,
    input_path: str = "",
) -> dict[str, Any]:
    """Run the unchanged legacy global-z workflow through the planar engine."""
    selection, zmin, zmax, ligand, cutoff = validate_analysis_inputs(
        selection, zmin, zmax, ligand, cutoff
    )
    membrane = legacy_global_z(zmin, zmax, DEFAULT_INTERFACE_WIDTH)
    return run_check_with_membrane(
        selection=selection,
        membrane=membrane,
        ligand=ligand,
        cutoff=cutoff,
        quiet=quiet,
        export_path=export_path,
        cmd_obj=cmd_obj,
        input_path=input_path,
    )


def run_check_with_membrane(
    *,
    selection: str,
    membrane: PlanarMembrane,
    ligand: str = "organic",
    cutoff: float = DEFAULT_LIGAND_CUTOFF,
    quiet: int = 1,
    export_path: str = "",
    cmd_obj: Any | None = None,
    input_path: str = "",
    orientation_import: Any | None = None,
) -> dict[str, Any]:
    """Run membrane visual QC against an explicit arbitrary planar membrane."""
    global LAST_REPORT
    selection, ligand, cutoff = validate_context_inputs(selection, ligand, cutoff)
    warnings = list(membrane.warnings)
    if membrane.source.startswith("manual") or membrane.source in {"unknown", "unspecified"}:
        warnings.append(
            "Membrane orientation was manually defined or is unverified. "
            "Interpret core flags as geometric inspection only."
        )
    if not membrane.lower_offset < 0.0 < membrane.upper_offset:
        warnings.append(
            "The membrane centre plane is not between both core boundaries; "
            "normalised in-core depth is unavailable."
        )
    atoms = protein_atoms(selection, cmd_obj)
    if not atoms:
        warnings.append(f"No protein atoms found in selection: {selection}")
        residues = []
        flags = []
        neighbours = []
    else:
        residues = classify_residues_for_membrane(atoms, membrane)
        flags = flag_core_residues(residues, membrane.source)
        lig_atoms = ligand_atoms(selection, ligand, cmd_obj) if ligand else []
        if ligand and not lig_atoms:
            warnings.append(f"No atoms found for ligand selection: {ligand}")
        neighbours = ligand_neighbor_residues(atoms, lig_atoms, float(cutoff))

        create_membrane_planes(membrane, atoms, selection, cmd_obj)
        color_hydropathy(selection, residues, cmd_obj)
        if ligand:
            show_ligand_shell(selection, ligand, neighbours, cmd_obj)
        # Review highlights are deliberately applied last so base colouring cannot hide them.
        show_residue_selections(residues, flags, cmd_obj)

    report = build_report(
        selection=selection,
        zmin=membrane.lower_offset,
        zmax=membrane.upper_offset,
        ligand_selection=ligand,
        cutoff=float(cutoff),
        total_residues=len(residues),
        core_residues=sum(1 for residue in residues if residue.classification == "core"),
        flagged_residues=[flag.as_dict() for flag in flags],
        ligand_neighbours=residue_dicts(neighbours),
        warnings=list(dict.fromkeys(warnings)),
        slab_mode=membrane.source,
        input_path=input_path or None,
        pymol_version=_pymol_version(cmd_obj),
        membrane=membrane,
        orientation_import=orientation_import,
    )
    LAST_REPORT = report

    if export_path:
        export_report(report, export_path, write_csv=True)
    if not int(quiet):
        print(format_summary(report))
    return report


def validate_context_inputs(selection: str, ligand: str, cutoff: float) -> tuple[str, str, float]:
    """Validate fields shared by legacy and arbitrary-plane analysis."""
    selection = str(selection).strip()
    ligand = str(ligand).strip()
    if not selection:
        raise InputValidationError("Protein selection must not be empty.")
    try:
        cutoff = float(cutoff)
    except (TypeError, ValueError) as exc:
        raise InputValidationError("Ligand cutoff must be numeric.") from exc
    if not math.isfinite(cutoff):
        raise InputValidationError("Ligand cutoff must be finite.")
    if cutoff <= 0:
        raise InputValidationError("Ligand cutoff must be greater than zero.")
    return selection, ligand, cutoff


def _pymol_version(cmd_obj: Any | None = None) -> str:
    """Return the runtime PyMOL version when exposed by the command API."""
    cmd = cmd_obj
    if cmd is None:
        try:
            from pymol import cmd as pymol_cmd

            cmd = pymol_cmd
        except Exception:
            return ""
    try:
        version = cmd.get_version()
    except (AttributeError, RuntimeError, TypeError):
        return ""
    if isinstance(version, (tuple, list)):
        version = version[0] if version else ""
    return str(version or "")


def validate_analysis_inputs(
    selection: str,
    zmin: float,
    zmax: float,
    ligand: str,
    cutoff: float,
) -> tuple[str, float, float, str, float]:
    """Validate and normalise public analysis parameters."""
    selection = str(selection).strip()
    ligand = str(ligand).strip()
    if not selection:
        raise InputValidationError("Protein selection must not be empty.")
    try:
        zmin = float(zmin)
        zmax = float(zmax)
        cutoff = float(cutoff)
    except (TypeError, ValueError) as exc:
        raise InputValidationError("zmin, zmax, and cutoff must be numeric.") from exc
    if not all(math.isfinite(value) for value in (zmin, zmax, cutoff)):
        raise InputValidationError("zmin, zmax, and cutoff must be finite.")
    if zmin >= zmax:
        raise InputValidationError("zmin must be smaller than zmax.")
    if cutoff <= 0:
        raise InputValidationError("Ligand cutoff must be greater than zero.")
    return selection, zmin, zmax, ligand, cutoff


def format_summary(report: dict[str, Any]) -> str:
    """Return a concise human-readable summary."""
    summary = report["summary"]
    return (
        "Membrane Visual QC: "
        f"{summary['core_residues']} core residues; "
        f"{summary['charged_core_residues']} charged core residues require inspection; "
        f"{summary['polar_core_inspect_residues']} polar core residues marked INSPECT; "
        f"{summary['ligand_neighbour_residues']} ligand-neighbour residues. "
        "This is a visual QC helper, not a definitive validator."
    )
