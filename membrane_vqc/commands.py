"""PyMOL command registrations for Membrane Visual QC."""

from __future__ import annotations

import math

from .constants import DEFAULT_LIGAND_CUTOFF, DEFAULT_ZMAX, DEFAULT_ZMIN
from .context_models import ExposureConfig, LocalContextConfig
from . import qc
from .membrane import aggregate_residues, residue_dicts
from .neighbors import ligand_neighbor_residues
from .orientation_io import load_orientation_file
from .pdbtm_pymol import resolve_pdbtm_from_pymol
from .pymol_adapter import (
    MVQC_NAMES,
    clear_owned,
    clear_slab,
    color_hydropathy,
    create_membrane_planes,
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
    analyze_context: int = 0,
    exposure_quality: str = "Standard",
    exposure_backend: str = "Built-in",
):
    """Run one-click membrane visual QC."""
    selection = _selection(selection)
    zmin, zmax = _slab(zmin, zmax)
    cutoff = _positive_float(cutoff, "cutoff")
    clear_owned()
    qc.LAST_REPORT = None
    try:
        exposure_config, context_config = _analysis_configs(analyze_context, exposure_quality)
        return qc.run_check(
            selection,
            zmin,
            zmax,
            str(ligand).strip(),
            cutoff,
            int(quiet),
            export_path,
            input_path=str(input_path).strip(),
            exposure_config=exposure_config,
            local_context_config=context_config,
            exposure_backend=exposure_backend,
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


def mvqc_check_orientation(
    selection: str = "all",
    orientation_file: str = "",
    ligand: str = "organic",
    cutoff: float = DEFAULT_LIGAND_CUTOFF,
    quiet: int = 1,
    export_path: str = "",
    input_path: str = "",
    analyze_context: int = 0,
    exposure_quality: str = "Standard",
    exposure_backend: str = "Built-in",
):
    """Run QC using a validated local planar-orientation JSON document."""
    clear_owned()
    qc.LAST_REPORT = None
    try:
        selection = _selection(selection)
        orientation_file = str(orientation_file).strip()
        if not orientation_file:
            raise ValueError("orientation_file must not be empty.")
        cutoff = _positive_float(cutoff, "cutoff")
        loaded = load_orientation_file(orientation_file)
        exposure_config, context_config = _analysis_configs(analyze_context, exposure_quality)
        return qc.run_check_with_membrane(
            selection=selection,
            membrane=loaded.membrane,
            ligand=str(ligand).strip(),
            cutoff=cutoff,
            quiet=int(quiet),
            export_path=str(export_path).strip(),
            input_path=str(input_path).strip(),
            orientation_import=loaded,
            exposure_config=exposure_config,
            local_context_config=context_config,
            exposure_backend=exposure_backend,
        )
    except Exception:
        clear_owned()
        qc.LAST_REPORT = None
        raise


def mvqc_slab_orientation(selection: str = "all", orientation_file: str = ""):
    """Render boundaries from a validated local planar-orientation document."""
    clear_slab()
    try:
        selection = _selection(selection)
        orientation_file = str(orientation_file).strip()
        if not orientation_file:
            raise ValueError("orientation_file must not be empty.")
        loaded = load_orientation_file(orientation_file)
        atoms = protein_atoms(selection)
        create_membrane_planes(loaded.membrane, atoms, selection)
        return loaded.membrane.as_dict()
    except Exception:
        clear_slab()
        raise


def mvqc_check_pdbtm(
    selection: str = "all",
    pdbtm_json: str = "",
    transformed_pdb: str = "",
    biological_assembly: str = "",
    ligand: str = "organic",
    cutoff: float = DEFAULT_LIGAND_CUTOFF,
    quiet: int = 1,
    export_path: str = "",
    input_path: str = "",
    analyze_context: int = 0,
    exposure_quality: str = "Standard",
    exposure_backend: str = "Built-in",
):
    """Run QC using an explicit offline PDBTM JSON/transformed-PDB pair."""

    clear_owned()
    qc.LAST_REPORT = None
    try:
        selection = _selection(selection)
        cutoff = _positive_float(cutoff, "cutoff")
        imported = resolve_pdbtm_from_pymol(
            selection=selection,
            pdbtm_json_path=str(pdbtm_json).strip(),
            transformed_pdb_path=str(transformed_pdb).strip(),
            biological_assembly=str(biological_assembly).strip() or None,
        )
        exposure_config, context_config = _analysis_configs(analyze_context, exposure_quality)
        return qc.run_check_with_membrane(
            selection=selection,
            membrane=imported.membrane,
            orientation_evidence=imported.evidence,
            ligand=str(ligand).strip(),
            cutoff=cutoff,
            quiet=int(quiet),
            export_path=str(export_path).strip(),
            input_path=str(input_path).strip(),
            exposure_config=exposure_config,
            local_context_config=context_config,
            exposure_backend=exposure_backend,
        )
    except Exception:
        clear_owned()
        qc.LAST_REPORT = None
        raise


def mvqc_slab_pdbtm(
    selection: str = "all",
    pdbtm_json: str = "",
    transformed_pdb: str = "",
    biological_assembly: str = "",
):
    """Render only the resolved current-frame slab from an offline PDBTM pair."""

    clear_slab()
    try:
        selection = _selection(selection)
        imported = resolve_pdbtm_from_pymol(
            selection=selection,
            pdbtm_json_path=str(pdbtm_json).strip(),
            transformed_pdb_path=str(transformed_pdb).strip(),
            biological_assembly=str(biological_assembly).strip() or None,
        )
        atoms = protein_atoms(selection)
        create_membrane_planes(imported.membrane, atoms, selection)
        return imported
    except Exception:
        clear_slab()
        raise


def mvqc_color_hydropathy(selection: str = "all"):
    """Colour selected protein residues by a simple hydropathy scale."""
    selection = _selection(selection)
    atoms = protein_atoms(selection)
    residues = aggregate_residues(atoms)
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


def _analysis_configs(enabled, quality) -> tuple[ExposureConfig | None, LocalContextConfig | None]:
    if isinstance(enabled, bool):
        normalized = int(enabled)
    elif isinstance(enabled, int) and enabled in {0, 1}:
        normalized = enabled
    elif isinstance(enabled, str) and enabled.strip() in {"0", "1"}:
        normalized = int(enabled.strip())
    else:
        raise ValueError("analyze_context must be 0 or 1.")
    enabled = bool(normalized)
    if not enabled:
        return None, None
    points = {"fast": 96, "standard": 240, "high": 960}.get(str(quality).strip().lower())
    if points is None:
        raise ValueError("exposure_quality must be Fast, Standard, or High.")
    return ExposureConfig(sphere_points=points), LocalContextConfig()


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
    cmd_obj.extend("mvqc_check_orientation", mvqc_check_orientation)
    cmd_obj.extend("mvqc_slab_orientation", mvqc_slab_orientation)
    cmd_obj.extend("mvqc_check_pdbtm", mvqc_check_pdbtm)
    cmd_obj.extend("mvqc_slab_pdbtm", mvqc_slab_pdbtm)
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
