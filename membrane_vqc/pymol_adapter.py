"""Thin wrappers around PyMOL command API."""

from __future__ import annotations

from math import isfinite
from pathlib import Path
from typing import Any

from .hydropathy import color_name_for_residue
from .context_models import LocalContextAnalysis
from .membrane import AtomRecord, ResidueFlag, ResidueRecord
from .orientation import PlanarMembrane, orthonormal_basis

MVQC_NAMES = frozenset(
    {
        "mvqc_slab_lower",
        "mvqc_slab_upper",
        "mvqc_core_residues",
        "mvqc_core_charged",
        "mvqc_core_polar_inspect",
        "mvqc_ligand",
        "mvqc_ligand_shell",
        "mvqc_context_partners",
        "mvqc_context_waters",
        "mvqc_context_ions",
        "mvqc_context_ligands",
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
MVQC_CONTEXT_NAMES = (
    "mvqc_context_partners",
    "mvqc_context_waters",
    "mvqc_context_ions",
    "mvqc_context_ligands",
)


def clear_owned(cmd_obj: Any | None = None) -> None:
    """Remove only objects and selections owned by Membrane Visual QC."""
    cmd = get_cmd(cmd_obj)
    for name in sorted(MVQC_NAMES):
        cmd.delete(name)


def clear_slab(cmd_obj: Any | None = None) -> None:
    """Remove only the membrane-boundary objects owned by the plugin."""
    cmd = get_cmd(cmd_obj)
    for name in MVQC_SLAB_NAMES:
        cmd.delete(name)


def clear_context(cmd_obj: Any | None = None) -> None:
    """Remove only local-context visual evidence owned by the plugin."""
    cmd = get_cmd(cmd_obj)
    if not hasattr(cmd, "delete"):
        return
    for name in MVQC_CONTEXT_NAMES:
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
                element=str(getattr(atom, "symbol", "") or getattr(atom, "elem", "") or ""),
                altloc=str(getattr(atom, "alt", "") or ""),
                occupancy=_optional_float(getattr(atom, "q", None)),
                formal_charge=_optional_int(getattr(atom, "formal_charge", None)),
                is_hetatm=_optional_bool(getattr(atom, "hetatm", None)),
            )
        )
    return atoms


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: object) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"0", "false", "no"}:
            return False
        if normalized in {"1", "true", "yes"}:
            return True
    return None


def protein_atoms(selection: str, cmd_obj: Any | None = None) -> list[AtomRecord]:
    """Extract polymer protein atoms for a selection."""
    return atoms_from_selection(f"({selection}) and polymer.protein", cmd_obj)


def structure_atoms(selection: str, cmd_obj: Any | None = None) -> list[AtomRecord]:
    """Extract every atom inside the user-supplied structure selection."""
    return atoms_from_selection(f"({selection})", cmd_obj)


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


def show_local_context(analysis: LocalContextAnalysis, cmd_obj: Any | None = None) -> None:
    """Create deterministic plugin-owned selections for local-context partners."""
    cmd = get_cmd(cmd_obj)
    clear_context(cmd)
    categories: dict[str, list[str]] = {name: [] for name in MVQC_CONTEXT_NAMES}
    for residue in analysis.residues:
        for contact in residue.contacts:
            partner = contact.partner_key
            chain = "" if partner[1] == "_" else f" and chain {partner[1]}"
            expression = f"(model {partner[0]}{chain} and resi {partner[2]} and resn {partner[3]})"
            if contact.contact_type == "nearby_water":
                name = "mvqc_context_waters"
            elif contact.contact_type == "nearby_ion":
                name = "mvqc_context_ions"
            elif contact.contact_type in {"ligand_proximity", "polar_ligand_proximity"}:
                name = "mvqc_context_ligands"
            else:
                name = "mvqc_context_partners"
            categories[name].append(expression)
    styles = {
        "mvqc_context_partners": ("sticks", "cyan"),
        "mvqc_context_waters": ("spheres", "blue"),
        "mvqc_context_ions": ("spheres", "violet"),
        "mvqc_context_ligands": ("sticks", "magenta"),
    }
    for name in MVQC_CONTEXT_NAMES:
        expression = " or ".join(sorted(set(categories[name]))) or "none"
        cmd.select(name, expression)
        representation, color = styles[name]
        cmd.show(representation, name)
        cmd.color(color, name)
    apply_review_style(cmd)


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def projected_coordinates(
    membrane: PlanarMembrane, atoms: list[AtomRecord]
) -> list[tuple[float, float]]:
    """Project atom coordinates onto the two axes spanning a membrane plane."""
    axis_u, axis_v = orthonormal_basis(membrane.normal)
    center = membrane.center
    return [
        (
            _dot((atom.x - center[0], atom.y - center[1], atom.z - center[2]), axis_u),
            _dot((atom.x - center[0], atom.y - center[1], atom.z - center[2]), axis_v),
        )
        for atom in atoms
    ]


def _clamped_interval(
    values: list[float], margin: float, minimum_size: float, maximum_size: float
) -> tuple[float, float]:
    if values:
        lower = min(values) - margin
        upper = max(values) + margin
        midpoint = (lower + upper) / 2.0
        size = min(max(upper - lower, minimum_size), maximum_size)
    else:
        midpoint = 0.0
        size = minimum_size
    return midpoint - size / 2.0, midpoint + size / 2.0


def projected_footprint(
    membrane: PlanarMembrane,
    atoms: list[AtomRecord],
    *,
    margin: float = 6.0,
    minimum_size: float = 20.0,
    maximum_size: float = 120.0,
) -> tuple[float, float, float, float]:
    """Return clamped ``(u_min, u_max, v_min, v_max)`` display bounds."""
    dimensions = (margin, minimum_size, maximum_size)
    if not all(isfinite(float(value)) for value in dimensions):
        raise ValueError("Plane footprint dimensions must be finite.")
    if margin < 0:
        raise ValueError("Plane footprint margin must be non-negative.")
    if minimum_size <= 0 or maximum_size < minimum_size:
        raise ValueError("Plane footprint sizes must satisfy 0 < minimum <= maximum.")

    projected = projected_coordinates(membrane, atoms)
    u_min, u_max = _clamped_interval(
        [point[0] for point in projected], margin, minimum_size, maximum_size
    )
    v_min, v_max = _clamped_interval(
        [point[1] for point in projected], margin, minimum_size, maximum_size
    )
    return u_min, u_max, v_min, v_max


def _plane_vertices(
    membrane: PlanarMembrane,
    offset: float,
    footprint: tuple[float, float, float, float],
) -> tuple[tuple[float, float, float], ...]:
    axis_u, axis_v = orthonormal_basis(membrane.normal)
    origin = tuple(membrane.center[index] + offset * membrane.normal[index] for index in range(3))
    u_min, u_max, v_min, v_max = footprint

    def point(u_value: float, v_value: float) -> tuple[float, float, float]:
        return tuple(
            origin[index] + u_value * axis_u[index] + v_value * axis_v[index] for index in range(3)
        )

    lower_left = point(u_min, v_min)
    lower_right = point(u_max, v_min)
    upper_right = point(u_max, v_max)
    upper_left = point(u_min, v_max)
    return (
        lower_left,
        lower_right,
        upper_right,
        lower_left,
        upper_right,
        upper_left,
    )


def create_membrane_planes(
    membrane: PlanarMembrane,
    atoms: list[AtomRecord],
    selection: str,
    cmd_obj: Any | None = None,
    *,
    margin: float = 6.0,
    minimum_size: float = 20.0,
    maximum_size: float = 120.0,
) -> None:
    """Render arbitrary planar membrane boundaries without rotating coordinates."""
    cmd = get_cmd(cmd_obj)
    try:
        from pymol.cgo import ALPHA, BEGIN, COLOR, END, NORMAL, TRIANGLES, VERTEX
    except Exception:
        print("Could not import PyMOL CGO constants; membrane planes were not created.")
        return

    for name in MVQC_SLAB_NAMES:
        cmd.delete(name)

    footprint = projected_footprint(
        membrane,
        atoms,
        margin=margin,
        minimum_size=minimum_size,
        maximum_size=maximum_size,
    )

    def plane(offset: float, color: tuple[float, float, float], normal_sign: float) -> list[float]:
        r, g, b = color
        normal = tuple(normal_sign * value for value in membrane.normal)
        cgo = [
            ALPHA,
            0.28,
            BEGIN,
            TRIANGLES,
            COLOR,
            r,
            g,
            b,
            NORMAL,
            *normal,
        ]
        for vertex in _plane_vertices(membrane, offset, footprint):
            cgo.extend((VERTEX, *vertex))
        cgo.append(END)
        return cgo

    cmd.load_cgo(
        plane(membrane.lower_offset, (0.2, 0.5, 1.0), -1.0),
        "mvqc_slab_lower",
    )
    cmd.load_cgo(
        plane(membrane.upper_offset, (1.0, 0.5, 0.2), 1.0),
        "mvqc_slab_upper",
    )

    if selection.strip():
        try:
            cmd.center(selection)
        except (AttributeError, TypeError):
            pass
        try:
            cmd.zoom(selection)
        except (AttributeError, TypeError):
            pass


def create_slab(zmin: float, zmax: float, cmd_obj: Any | None = None) -> None:
    """Legacy global-z rendering wrapper retained for command compatibility."""
    membrane = PlanarMembrane(
        center=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        lower_offset=float(zmin),
        upper_offset=float(zmax),
        interface_width=0.0,
        source="manual_global_z",
    )

    create_membrane_planes(
        membrane,
        [],
        "",
        cmd_obj,
        margin=0.0,
        minimum_size=160.0,
        maximum_size=160.0,
    )


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
