"""Thin wrappers around PyMOL command API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .hydropathy import color_name_for_residue
from .membrane import AtomRecord, ResidueFlag, ResidueRecord

MVQC_NAMES = frozenset(
    {
        "mvqc_slab_lower",
        "mvqc_slab_upper",
        "mvqc_core_residues",
        "mvqc_core_charged",
        "mvqc_core_polar_inspect",
        "mvqc_ligand",
        "mvqc_ligand_shell",
    }
)

# Stable subsets keep object ownership and visual precedence in one place.
MVQC_SLAB_NAMES = ("mvqc_slab_lower", "mvqc_slab_upper")
MVQC_REVIEW_NAMES = (
    "mvqc_core_residues",
    "mvqc_core_charged",
    "mvqc_core_polar_inspect",
)
MVQC_LIGAND_NAMES = ("mvqc_ligand", "mvqc_ligand_shell")


def clear_owned(cmd_obj: Any | None = None) -> None:
    """Remove only objects and selections owned by Membrane Visual QC."""
    cmd = get_cmd(cmd_obj)
    for name in sorted(MVQC_NAMES):
        cmd.delete(name)


def apply_review_style(cmd_obj: Any | None = None) -> None:
    """Re-apply high-priority review styling above base and context colours."""
    cmd = get_cmd(cmd_obj)
    try:
        available = set(cmd.get_names("all"))
    except (AttributeError, TypeError):
        available = set(MVQC_REVIEW_NAMES)
    active = [name for name in MVQC_REVIEW_NAMES[1:] if name in available]
    if not active:
        return
    cmd.show("sticks", " or ".join(active))
    if "mvqc_core_charged" in active:
        cmd.color("orange", "mvqc_core_charged")
    if "mvqc_core_polar_inspect" in active:
        cmd.color("yellow", "mvqc_core_polar_inspect")


def get_cmd(cmd_obj: Any | None = None) -> Any:
    """Return a PyMOL cmd-like object or raise a helpful error."""
    if cmd_obj is not None:
        return cmd_obj
    try:
        from pymol import cmd
    except Exception as exc:
        raise RuntimeError("PyMOL cmd API is unavailable in this Python environment.") from exc
    return cmd


def atoms_from_selection(selection: str, cmd_obj: Any | None = None) -> list[AtomRecord]:
    """Extract atom records from a PyMOL selection."""
    cmd = get_cmd(cmd_obj)
    model = cmd.get_model(selection)
    atoms: list[AtomRecord] = []
    for atom in getattr(model, "atom", []):
        coord = getattr(atom, "coord", (0.0, 0.0, 0.0))
        atoms.append(
            AtomRecord(
                model=str(getattr(atom, "model", "") or "_"),
                chain=str(getattr(atom, "chain", "") or "_"),
                resi=str(getattr(atom, "resi", "")),
                resn=str(getattr(atom, "resn", "")).upper(),
                name=str(getattr(atom, "name", "")).upper(),
                x=float(coord[0]),
                y=float(coord[1]),
                z=float(coord[2]),
            )
        )
    return atoms


def protein_atoms(selection: str, cmd_obj: Any | None = None) -> list[AtomRecord]:
    """Extract polymer protein atoms for a selection."""
    return atoms_from_selection(f"({selection}) and polymer.protein", cmd_obj)


def ligand_atoms(selection: str, ligand: str, cmd_obj: Any | None = None) -> list[AtomRecord]:
    """Extract ligand atoms constrained to the selected object/structure."""
    return atoms_from_selection(f"({selection}) and ({ligand})", cmd_obj)


def residue_selection(residues: list[ResidueRecord] | list[ResidueFlag]) -> str:
    """Build a PyMOL selection expression from residue records."""
    parts = []
    for residue in residues:
        chain = "" if residue.chain == "_" else f" and chain {residue.chain}"
        parts.append(
            f"(model {residue.model}{chain} and resi {residue.resi} and resn {residue.resn})"
        )
    return " or ".join(parts) if parts else "none"


def create_slab(zmin: float, zmax: float, cmd_obj: Any | None = None) -> None:
    """Create simple CGO plane markers for the membrane slab boundaries."""
    cmd = get_cmd(cmd_obj)
    try:
        from pymol.cgo import ALPHA, BEGIN, COLOR, END, TRIANGLES, VERTEX
    except Exception:
        print("Could not import PyMOL CGO constants; slab objects were not created.")
        return

    for name in MVQC_SLAB_NAMES:
        cmd.delete(name)
    size = 80.0

    def plane(z: float, color: tuple[float, float, float]) -> list[float]:
        r, g, b = color
        return [
            ALPHA,
            0.28,
            BEGIN,
            TRIANGLES,
            COLOR,
            r,
            g,
            b,
            VERTEX,
            -size,
            -size,
            z,
            VERTEX,
            size,
            -size,
            z,
            VERTEX,
            size,
            size,
            z,
            VERTEX,
            -size,
            -size,
            z,
            VERTEX,
            size,
            size,
            z,
            VERTEX,
            -size,
            size,
            z,
            END,
        ]

    cmd.load_cgo(plane(float(zmin), (0.2, 0.5, 1.0)), "mvqc_slab_lower")
    cmd.load_cgo(plane(float(zmax), (1.0, 0.5, 0.2)), "mvqc_slab_upper")


def show_residue_selections(
    residues: list[ResidueRecord],
    flags: list[ResidueFlag],
    cmd_obj: Any | None = None,
) -> None:
    """Create predictable MVQC selections for classified and flagged residues."""
    cmd = get_cmd(cmd_obj)
    for name in MVQC_REVIEW_NAMES:
        cmd.delete(name)

    core = [residue for residue in residues if residue.classification == "core"]
    charged = [flag for flag in flags if flag.severity == "WARNING"]
    polar = [flag for flag in flags if flag.severity == "INSPECT"]
    cmd.select("mvqc_core_residues", residue_selection(core))
    cmd.select("mvqc_core_charged", residue_selection(charged))
    cmd.select("mvqc_core_polar_inspect", residue_selection(polar))
    apply_review_style(cmd)


def show_ligand_shell(
    selection: str,
    ligand: str,
    neighbours: list[ResidueRecord],
    cmd_obj: Any | None = None,
) -> None:
    """Create ligand and ligand-shell selections."""
    cmd = get_cmd(cmd_obj)
    for name in MVQC_LIGAND_NAMES:
        cmd.delete(name)
    if not ligand.strip():
        return
    cmd.select("mvqc_ligand", f"({selection}) and ({ligand})")
    cmd.select("mvqc_ligand_shell", residue_selection(neighbours))
    cmd.show("sticks", "mvqc_ligand or mvqc_ligand_shell")
    cmd.color("magenta", "mvqc_ligand")
    cmd.color("cyan", "mvqc_ligand_shell")
    apply_review_style(cmd)


def color_hydropathy(
    selection: str, residues: list[ResidueRecord], cmd_obj: Any | None = None
) -> None:
    """Apply coarse hydropathy coloring to residue selections."""
    cmd = get_cmd(cmd_obj)
    for residue in residues:
        chain = "" if residue.chain == "_" else f" and chain {residue.chain}"
        expr = f"({selection}) and model {residue.model}{chain} and resi {residue.resi} and resn {residue.resn}"
        cmd.color(color_name_for_residue(residue.resn), expr)
    apply_review_style(cmd)


def ensure_parent(path: str | Path) -> None:
    """Create a parent directory for a PyMOL-facing output path."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
