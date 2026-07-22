"""Main-thread PyMOL snapshot and rendering helpers for source comparison."""

from __future__ import annotations

from dataclasses import dataclass

from .membrane import AtomRecord
from .orientation import PlanarMembrane
from .orientation_sources import StructureContext
from .opm_adapter import fingerprint_structure_context
from .pdbtm_pymol import structure_context_from_pymol
from .pymol_adapter import (
    clear_comparison,
    create_comparison_membrane_planes,
    protein_atoms,
)


@dataclass(frozen=True, slots=True)
class ComparisonObjectSnapshot:
    """Immutable current-object evidence captured before worker dispatch."""

    structure_context: StructureContext
    atoms: tuple[AtomRecord, ...]
    coordinate_fingerprint: str


def capture_comparison_snapshot(
    selection: str,
    *,
    biological_assembly: str | None = None,
    cmd_obj: object | None = None,
) -> ComparisonObjectSnapshot:
    """Capture current coordinates on the caller's (PyMOL main) thread."""
    context = structure_context_from_pymol(
        selection,
        biological_assembly=biological_assembly,
        cmd_obj=cmd_obj,
    )
    atoms = tuple(protein_atoms(selection, cmd_obj))
    return ComparisonObjectSnapshot(
        structure_context=context,
        atoms=atoms,
        coordinate_fingerprint=fingerprint_structure_context(context),
    )


def comparison_snapshot_is_current(
    snapshot: ComparisonObjectSnapshot,
    selection: str,
    *,
    biological_assembly: str | None = None,
    cmd_obj: object | None = None,
) -> bool:
    """Re-snapshot and reject a worker result if the selected object changed."""
    current = structure_context_from_pymol(
        selection,
        biological_assembly=biological_assembly,
        cmd_obj=cmd_obj,
    )
    return (
        current.model_id == snapshot.structure_context.model_id
        and current.biological_assembly == snapshot.structure_context.biological_assembly
        and current.coordinate_frame == snapshot.structure_context.coordinate_frame
        and fingerprint_structure_context(current) == snapshot.coordinate_fingerprint
    )


def show_comparison_boundaries(
    pdbtm_membrane: PlanarMembrane,
    opm_membrane: PlanarMembrane,
    snapshot: ComparisonObjectSnapshot,
    selection: str,
    *,
    cmd_obj: object | None = None,
) -> None:
    """Render four comparison-owned planes without changing molecular coordinates."""
    create_comparison_membrane_planes(
        pdbtm_membrane,
        opm_membrane,
        list(snapshot.atoms),
        selection,
        cmd_obj,
    )


def clear_comparison_boundaries(cmd_obj: object | None = None) -> None:
    """Remove comparison output while preserving standard QC and user objects."""
    clear_comparison(cmd_obj)
