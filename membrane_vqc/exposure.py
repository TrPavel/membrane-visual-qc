"""Deterministic pure-Python Shrake–Rupley solvent exposure."""

from __future__ import annotations

import importlib.util
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from itertools import groupby
from typing import Iterable

from .context_models import (
    AtomSASA,
    ExposureAnalysis,
    ExposureBackendMetadata,
    ExposureConfig,
    ResidueExposure,
    SurfacePartition,
)
from .membrane import AtomRecord
from .orientation import PlanarMembrane
from .spatial import CellList

BACKEND_NAME = "builtin_shrake_rupley"
BACKEND_VERSION = "1"
ALTLOC_POLICY = "highest_occupancy_blank_A_lexical_v1"
BACKBONE_ATOMS = frozenset({"N", "CA", "C", "O", "OXT"})

# Fixed element-level radii for element_vdw_v1. Values follow Bondi 1964,
# DOI 10.1021/j100785a001. Unknown elements are excluded, never mapped to carbon.
ELEMENT_VDW_RADII = {
    "H": 1.20,
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "F": 1.47,
    "P": 1.80,
    "S": 1.80,
    "CL": 1.75,
    "BR": 1.85,
    "I": 1.98,
}

# Theoretical ALLOWED-region maxima in Table 1 of Tien et al. 2013,
# DOI 10.1371/journal.pone.0080635.
TIEN_2013_THEORETICAL_MAX_ASA = {
    "ALA": 129.0,
    "ARG": 274.0,
    "ASN": 195.0,
    "ASP": 193.0,
    "CYS": 167.0,
    "GLN": 225.0,
    "GLU": 223.0,
    "GLY": 104.0,
    "HIS": 224.0,
    "ILE": 197.0,
    "LEU": 201.0,
    "LYS": 236.0,
    "MET": 224.0,
    "PHE": 240.0,
    "PRO": 159.0,
    "SER": 155.0,
    "THR": 172.0,
    "TRP": 285.0,
    "TYR": 263.0,
    "VAL": 174.0,
}

ResidueKey = tuple[str, str, str, str]
AtomKey = tuple[str, str, str, str, str]


@dataclass(frozen=True)
class PreparedAtoms:
    atoms: tuple[AtomRecord, ...]
    radii: tuple[float, ...]
    warnings: tuple[str, ...]
    alternate_atoms_seen: int
    alternate_atoms_discarded: int


def calculate_exposure(
    atoms: Iterable[AtomRecord],
    *,
    config: ExposureConfig | None = None,
    target_residues: Iterable[ResidueKey] | None = None,
    membrane: PlanarMembrane | None = None,
) -> ExposureAnalysis:
    """Calculate target-residue SASA using same-model atoms as occluders."""
    started = time.perf_counter()
    config = config or ExposureConfig()
    original = tuple(atoms)
    _validate_coordinates(original)
    collapsed, alternate_seen, alternate_discarded = collapse_alternate_locations(original)
    requested = _target_residue_keys(collapsed, config, target_residues)
    prepared = prepare_atoms(collapsed, config, alternate_seen, alternate_discarded)

    warnings = list(prepared.warnings)
    models = tuple(sorted({atom.model for atom in collapsed}))
    if len(models) > 1:
        warnings.append(
            "Exposure selection spans multiple models; each model was calculated independently "
            "without cross-model occlusion."
        )

    atom_results: dict[int, AtomSASA] = {}
    atoms_by_model: dict[str, list[int]] = defaultdict(list)
    for index, atom in enumerate(prepared.atoms):
        atoms_by_model[atom.model].append(index)

    for model in sorted(atoms_by_model):
        model_indices = atoms_by_model[model]
        target_indices = [
            index for index in model_indices if _residue_key(prepared.atoms[index]) in requested
        ]
        atom_results.update(
            _calculate_model_atoms(
                prepared.atoms,
                prepared.radii,
                model_indices,
                target_indices,
                config,
                membrane,
            )
        )

    residue_results = _aggregate_residue_results(
        prepared.atoms,
        atom_results,
        requested,
        config,
        membrane,
        warnings,
    )
    elapsed = time.perf_counter() - started
    metadata = ExposureBackendMetadata(
        backend=BACKEND_NAME,
        backend_version=BACKEND_VERSION,
        config=config,
        alternate_atoms_seen=prepared.alternate_atoms_seen,
        alternate_atoms_discarded=prepared.alternate_atoms_discarded,
        alternate_location_policy=ALTLOC_POLICY,
        models=models,
        freesasa_status=(
            "available" if importlib.util.find_spec("freesasa") is not None else "unavailable"
        ),
        warnings=tuple(dict.fromkeys(warnings)),
        elapsed_seconds=elapsed,
    )
    status = (
        "completed" if all(item.status == "completed" for item in residue_results) else "partial"
    )
    return ExposureAnalysis(status=status, residues=tuple(residue_results), metadata=metadata)


def collapse_alternate_locations(
    atoms: Iterable[AtomRecord],
) -> tuple[tuple[AtomRecord, ...], int, int]:
    """Collapse duplicate atom identities using the documented deterministic policy."""
    ordered = sorted(atoms, key=lambda atom: (_atom_identity(atom), _atom_stable_key(atom)))
    selected: list[AtomRecord] = []
    seen = 0
    discarded = 0
    for _, group in groupby(ordered, key=_atom_identity):
        variants = list(group)
        if len(variants) > 1:
            seen += len(variants)
            discarded += len(variants) - 1
        selected.append(min(variants, key=_altloc_priority))
    return tuple(sorted(selected, key=_atom_stable_key)), seen, discarded


def prepare_atoms(
    atoms: Iterable[AtomRecord],
    config: ExposureConfig,
    alternate_atoms_seen: int = 0,
    alternate_atoms_discarded: int = 0,
) -> PreparedAtoms:
    """Resolve elements/radii and apply hydrogen/non-protein inclusion policy."""
    prepared: list[AtomRecord] = []
    radii: list[float] = []
    warnings: list[str] = []
    for atom in sorted(atoms, key=_atom_stable_key):
        if atom.is_hetatm is True and not config.include_nonprotein_occluders:
            continue
        element = normalize_or_infer_element(atom)
        if not element:
            warnings.append(f"Unknown element for atom {_atom_label(atom)}; excluded from SASA.")
            continue
        if element == "H" and not config.include_hydrogens:
            continue
        radius = ELEMENT_VDW_RADII.get(element)
        if radius is None:
            warnings.append(
                f"No safe {config.radii_model} radius for element {element} at "
                f"{_atom_label(atom)}; excluded from SASA."
            )
            continue
        prepared.append(_with_element(atom, element))
        radii.append(radius)
    return PreparedAtoms(
        atoms=tuple(prepared),
        radii=tuple(radii),
        warnings=tuple(dict.fromkeys(warnings)),
        alternate_atoms_seen=alternate_atoms_seen,
        alternate_atoms_discarded=alternate_atoms_discarded,
    )


def normalize_or_infer_element(atom: AtomRecord) -> str:
    """Return a supported uppercase element or an empty string deterministically."""
    supplied = str(atom.element or "").strip().upper()
    if supplied:
        return supplied if supplied in ELEMENT_VDW_RADII else ""

    raw_name = str(atom.name or "").strip()
    while raw_name and raw_name[0].isdigit():
        raw_name = raw_name[1:]
    if not raw_name:
        return ""

    upper = raw_name.upper()
    two_letter = upper[:2]
    conventional_two_letter = len(raw_name) >= 2 and raw_name[0].isupper() and raw_name[1].islower()
    hetero_identity = atom.is_hetatm is True and atom.resn.strip().upper() in {two_letter, upper}
    if two_letter in {"CL", "BR"} and (conventional_two_letter or hetero_identity):
        return two_letter
    one_letter = upper[0]
    return one_letter if one_letter in ELEMENT_VDW_RADII else ""


def fibonacci_sphere_points(count: int) -> tuple[tuple[float, float, float], ...]:
    """Return deterministic unit-sphere points using a golden-angle spiral."""
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("Sphere point count must be a positive integer.")
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    points = []
    for index in range(count):
        y = 1.0 - 2.0 * ((index + 0.5) / count)
        radial = math.sqrt(max(0.0, 1.0 - y * y))
        theta = golden_angle * index
        points.append((math.cos(theta) * radial, y, math.sin(theta) * radial))
    return tuple(points)


def classify_exposure(relative_sasa: float | None, config: ExposureConfig) -> str:
    if relative_sasa is None:
        return "unknown"
    if relative_sasa < config.buried_rsa_threshold:
        return "buried"
    if relative_sasa < config.exposed_rsa_threshold:
        return "intermediate"
    return "exposed"


def _calculate_model_atoms(
    atoms: tuple[AtomRecord, ...],
    radii: tuple[float, ...],
    model_indices: list[int],
    target_indices: list[int],
    config: ExposureConfig,
    membrane: PlanarMembrane | None,
) -> dict[int, AtomSASA]:
    if not model_indices or not target_indices:
        return {}
    local_centers = [_point(atoms[index]) for index in model_indices]
    local_expanded = tuple(radii[index] + config.probe_radius for index in model_indices)
    max_expanded = max(local_expanded)
    grid = CellList.build(local_centers, max_expanded)
    global_to_local = {
        global_index: local_index for local_index, global_index in enumerate(model_indices)
    }
    base_sphere = fibonacci_sphere_points(config.sphere_points)
    results: dict[int, AtomSASA] = {}

    for atom_index in sorted(target_indices, key=lambda index: _atom_stable_key(atoms[index])):
        atom = atoms[atom_index]
        target_local_index = global_to_local[atom_index]
        center = local_centers[target_local_index]
        expanded_radius = local_expanded[target_local_index]
        point_area = 4.0 * math.pi * expanded_radius * expanded_radius / config.sphere_points
        sphere = _equivariant_sphere_points(atom_index, model_indices, atoms, base_sphere, membrane)
        accessible = 0
        core = interface = outside = 0
        for unit in sphere:
            sample = (
                center[0] + expanded_radius * unit[0],
                center[1] + expanded_radius * unit[1],
                center[2] + expanded_radius * unit[2],
            )
            occluded = False
            for local_index in grid.nearby_indices(sample):
                if local_index == target_local_index:
                    continue
                other = local_centers[local_index]
                dx = sample[0] - other[0]
                dy = sample[1] - other[1]
                dz = sample[2] - other[2]
                if dx * dx + dy * dy + dz * dz < local_expanded[local_index] ** 2:
                    occluded = True
                    break
            if occluded:
                continue
            accessible += 1
            if membrane is None:
                continue
            distance = (
                (sample[0] - membrane.center[0]) * membrane.normal[0]
                + (sample[1] - membrane.center[1]) * membrane.normal[1]
                + (sample[2] - membrane.center[2]) * membrane.normal[2]
            )
            if membrane.lower_offset <= distance <= membrane.upper_offset:
                core += 1
            elif (
                membrane.lower_offset - membrane.interface_width <= distance < membrane.lower_offset
                or membrane.upper_offset
                < distance
                <= membrane.upper_offset + membrane.interface_width
            ):
                interface += 1
            else:
                outside += 1

        sasa = accessible * point_area
        partition = _partition_from_counts(core, interface, outside, point_area, sasa, membrane)
        results[atom_index] = AtomSASA(
            atom_key=_atom_identity(atom),
            element=atom.element,
            radius=radii[atom_index],
            sasa=sasa,
            accessible_points=accessible,
            sphere_points=config.sphere_points,
            partition=partition,
        )
    return results


def _aggregate_residue_results(
    atoms: tuple[AtomRecord, ...],
    atom_results: dict[int, AtomSASA],
    requested: set[ResidueKey],
    config: ExposureConfig,
    membrane: PlanarMembrane | None,
    global_warnings: list[str],
) -> list[ResidueExposure]:
    indices_by_residue: dict[ResidueKey, list[int]] = defaultdict(list)
    for index in atom_results:
        indices_by_residue[_residue_key(atoms[index])].append(index)

    results: list[ResidueExposure] = []
    for residue_key in sorted(requested):
        indices = sorted(
            indices_by_residue.get(residue_key, []), key=lambda i: _atom_stable_key(atoms[i])
        )
        if not indices:
            message = f"No supported atoms were available for target residue {_residue_label(residue_key)}."
            global_warnings.append(message)
            unavailable = _unavailable_partition()
            results.append(
                ResidueExposure(
                    *residue_key,
                    status="unavailable",
                    residue_sasa=None,
                    sidechain_sasa=None,
                    relative_sasa=None,
                    reference_max_sasa=TIEN_2013_THEORETICAL_MAX_ASA.get(residue_key[3]),
                    reference_status=(
                        "available"
                        if residue_key[3] in TIEN_2013_THEORETICAL_MAX_ASA
                        else "unavailable"
                    ),
                    classification="unknown",
                    partition=unavailable,
                    sidechain_partition=unavailable,
                    warnings=(message,),
                )
            )
            continue

        atom_sasa = tuple(atom_results[index] for index in indices)
        total = sum(item.sasa for item in atom_sasa)
        sidechain_items = tuple(
            atom_results[index]
            for index in indices
            if atoms[index].name.strip().upper() not in BACKBONE_ATOMS
        )
        sidechain = sum(item.sasa for item in sidechain_items)
        reference = TIEN_2013_THEORETICAL_MAX_ASA.get(residue_key[3])
        relative = total / reference if reference is not None else None
        warnings: tuple[str, ...] = ()
        if reference is None:
            warnings = (
                f"No {config.rsa_reference} maximum ASA is available for residue "
                f"{_residue_label(residue_key)}; RSA is unavailable.",
            )
            global_warnings.extend(warnings)
        results.append(
            ResidueExposure(
                *residue_key,
                status="completed",
                residue_sasa=total,
                sidechain_sasa=sidechain,
                relative_sasa=relative,
                reference_max_sasa=reference,
                reference_status="available" if reference is not None else "unavailable",
                classification=classify_exposure(relative, config),
                partition=_sum_partitions(atom_sasa, total, membrane),
                sidechain_partition=_sum_partitions(sidechain_items, sidechain, membrane),
                atom_sasa=atom_sasa,
                warnings=warnings,
            )
        )
    return results


def _target_residue_keys(
    atoms: tuple[AtomRecord, ...],
    config: ExposureConfig,
    target_residues: Iterable[ResidueKey] | None,
) -> set[ResidueKey]:
    if target_residues is None:
        if config.target_scope == "all_residues":
            return {_residue_key(atom) for atom in atoms}
        raise ValueError(
            f"target_residues must be supplied when target_scope is {config.target_scope!r}."
        )
    normalized = {
        (str(model or "_"), str(chain or "_"), str(resi), str(resn).upper())
        for model, chain, resi, resn in target_residues
    }
    return normalized


def _partition_from_counts(
    core: int,
    interface: int,
    outside: int,
    point_area: float,
    total_sasa: float,
    membrane: PlanarMembrane | None,
) -> SurfacePartition:
    if membrane is None:
        return _unavailable_partition()
    core_area = core * point_area
    interface_area = interface * point_area
    outside_area = outside * point_area
    denominator = total_sasa if total_sasa > 0.0 else None
    core_fraction = _bounded_fraction(core_area, denominator)
    interface_fraction = _bounded_fraction(interface_area, denominator)
    outside_fraction = _bounded_fraction(outside_area, denominator)
    membrane_fraction = _bounded_fraction(core_area + interface_area, denominator)
    return SurfacePartition(
        core_area,
        interface_area,
        outside_area,
        core_fraction,
        interface_fraction,
        outside_fraction,
        membrane_fraction,
    )


def _sum_partitions(
    atom_items: tuple[AtomSASA, ...], total_sasa: float, membrane: PlanarMembrane | None
) -> SurfacePartition:
    if membrane is None:
        return _unavailable_partition()
    core = sum(item.partition.core_area or 0.0 for item in atom_items)
    interface = sum(item.partition.interface_area or 0.0 for item in atom_items)
    outside = sum(item.partition.outside_area or 0.0 for item in atom_items)
    denominator = total_sasa if total_sasa > 0.0 else None
    core_fraction = _bounded_fraction(core, denominator)
    interface_fraction = _bounded_fraction(interface, denominator)
    outside_fraction = _bounded_fraction(outside, denominator)
    return SurfacePartition(
        core,
        interface,
        outside,
        core_fraction,
        interface_fraction,
        outside_fraction,
        _bounded_fraction(core + interface, denominator),
    )


def _unavailable_partition() -> SurfacePartition:
    return SurfacePartition(None, None, None, None, None, None, None)


def _bounded_fraction(numerator: float, denominator: float | None) -> float | None:
    if denominator is None or denominator <= 0.0:
        return None
    return min(1.0, max(0.0, numerator / denominator))


def _validate_coordinates(atoms: tuple[AtomRecord, ...]) -> None:
    for atom in atoms:
        if not all(math.isfinite(float(value)) for value in (atom.x, atom.y, atom.z)):
            raise ValueError(f"Atom {_atom_label(atom)} has non-finite coordinates.")
        if atom.occupancy is not None and not math.isfinite(float(atom.occupancy)):
            raise ValueError(f"Atom {_atom_label(atom)} has non-finite occupancy.")


def _with_element(atom: AtomRecord, element: str) -> AtomRecord:
    return AtomRecord(
        model=atom.model,
        chain=atom.chain,
        resi=atom.resi,
        resn=atom.resn,
        name=atom.name,
        x=atom.x,
        y=atom.y,
        z=atom.z,
        element=element,
        altloc=atom.altloc,
        occupancy=atom.occupancy,
        formal_charge=atom.formal_charge,
        is_hetatm=atom.is_hetatm,
    )


def _altloc_priority(atom: AtomRecord) -> tuple[float, int, str, tuple[object, ...]]:
    occupancy = float(atom.occupancy) if atom.occupancy is not None else -math.inf
    altloc = str(atom.altloc or "").strip()
    rank = 0 if not altloc else 1 if altloc.upper() == "A" else 2
    return -occupancy, rank, altloc, _atom_stable_key(atom)


def _atom_identity(atom: AtomRecord) -> AtomKey:
    return (
        atom.model or "_",
        atom.chain or "_",
        str(atom.resi),
        atom.resn.upper(),
        atom.name.strip().upper(),
    )


def _residue_key(atom: AtomRecord) -> ResidueKey:
    identity = _atom_identity(atom)
    return identity[0], identity[1], identity[2], identity[3]


def _atom_stable_key(atom: AtomRecord) -> tuple[object, ...]:
    return (
        *_atom_identity(atom),
        str(atom.altloc or ""),
        -(float(atom.occupancy) if atom.occupancy is not None else -math.inf),
        float(atom.x),
        float(atom.y),
        float(atom.z),
        str(atom.element or ""),
    )


def _point(atom: AtomRecord) -> tuple[float, float, float]:
    return float(atom.x), float(atom.y), float(atom.z)


def _equivariant_sphere_points(
    target_index: int,
    model_indices: list[int],
    atoms: tuple[AtomRecord, ...],
    base: tuple[tuple[float, float, float], ...],
    membrane: PlanarMembrane | None = None,
) -> tuple[tuple[float, float, float], ...]:
    """Orient points by membrane/structure geometry so joint transforms are equivariant."""
    origin = _point(atoms[target_index])
    z_axis = membrane.normal if membrane is not None else None
    x_axis = None
    for index in model_indices:
        if index == target_index:
            continue
        point = _point(atoms[index])
        vector = (point[0] - origin[0], point[1] - origin[1], point[2] - origin[2])
        if _dot(vector, vector) <= 1e-24:
            continue
        if z_axis is None:
            z_axis = _normalize(vector)
            continue
        projected = _subtract(vector, _scale(z_axis, _dot(vector, z_axis)))
        if _dot(projected, projected) > 1e-20:
            x_axis = _normalize(projected)
            break

    if z_axis is None:
        return base

    if x_axis is None:
        # With no non-parallel structural vector, occlusion/partition geometry is axially
        # symmetric about z_axis, so this deterministic phase cannot change classified counts.
        x_axis = _stable_perpendicular(z_axis)
    y_axis = _cross(z_axis, x_axis)
    return tuple(
        (
            x_axis[0] * point[0] + y_axis[0] * point[1] + z_axis[0] * point[2],
            x_axis[1] * point[0] + y_axis[1] * point[1] + z_axis[1] * point[2],
            x_axis[2] * point[0] + y_axis[2] * point[1] + z_axis[2] * point[2],
        )
        for point in base
    )


def _stable_perpendicular(axis: tuple[float, float, float]) -> tuple[float, float, float]:
    """Return a deterministic phase axis for axially symmetric geometry."""
    trial = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
    return _normalize(_subtract(trial, _scale(axis, _dot(trial, axis))))


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _subtract(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _scale(a: tuple[float, float, float], factor: float) -> tuple[float, float, float]:
    return a[0] * factor, a[1] * factor, a[2] * factor


def _cross(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(a: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(_dot(a, a))
    return a[0] / length, a[1] / length, a[2] / length


def _atom_label(atom: AtomRecord) -> str:
    return "/".join(_atom_identity(atom))


def _residue_label(key: ResidueKey) -> str:
    return "/".join(key)
