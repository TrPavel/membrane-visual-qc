"""Pure-Python membrane slab and residue classification logic."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from operator import attrgetter

from .constants import CHARGED_RESIDUES, DEFAULT_INTERFACE_WIDTH, POLAR_INSPECT_RESIDUES
from .orientation import (
    PlanarMembrane,
    classify_signed_distance,
    legacy_global_z,
    measure_point,
)


@dataclass(frozen=True)
class AtomRecord:
    """Minimal atom data needed by the core QC logic."""

    model: str
    chain: str
    resi: str
    resn: str
    name: str
    x: float
    y: float
    z: float
    element: str = ""
    altloc: str = ""
    occupancy: float | None = None
    formal_charge: int | None = None
    is_hetatm: bool | None = None


@dataclass(frozen=True)
class ResidueRecord:
    """Representative residue coordinate and membrane classification."""

    model: str
    chain: str
    resi: str
    resn: str
    x: float
    y: float
    z: float
    classification: str
    signed_distance: float | None = None
    absolute_center_distance: float | None = None
    nearest_boundary_distance: float | None = None
    outside_distance: float | None = None
    normalized_depth: float | None = None

    @property
    def identifier(self) -> str:
        chain = self.chain or "_"
        return f"{self.model}/{chain}/{self.resi}/{self.resn}"


@dataclass(frozen=True)
class ResidueFlag:
    """Inspection flag for a residue in the membrane core."""

    model: str
    chain: str
    resi: str
    resn: str
    classification: str
    severity: str
    reason: str
    z: float
    signed_distance: float | None = None
    absolute_center_distance: float | None = None
    nearest_boundary_distance: float | None = None
    outside_distance: float | None = None
    normalized_depth: float | None = None

    @property
    def identifier(self) -> str:
        chain = self.chain or "_"
        return f"{self.model}/{chain}/{self.resi}/{self.resn}"

    def as_dict(self) -> dict[str, object]:
        result = {
            "id": self.identifier,
            "model": self.model,
            "chain": self.chain or "_",
            "resi": self.resi,
            "resn": self.resn,
            "classification": self.classification,
            "severity": self.severity,
            "reason": self.reason,
            "z": self.z,
        }
        result.update(_depth_dict(self))
        return result


def classify_z(z: float, zmin: float, zmax: float, interface_width: float = 0.0) -> str:
    """Classify a z coordinate relative to a manual membrane slab."""
    return classify_signed_distance(float(z), legacy_global_z(zmin, zmax, interface_width))


def classify_residues(
    atoms: list[AtomRecord],
    zmin: float,
    zmax: float,
    interface_width: float = DEFAULT_INTERFACE_WIDTH,
) -> list[ResidueRecord]:
    """Classify residues using CA coordinates, falling back to residue atom averages."""
    membrane = legacy_global_z(zmin, zmax, interface_width)
    return classify_residues_for_membrane(atoms, membrane)


def aggregate_residues(atoms: list[AtomRecord]) -> list[ResidueRecord]:
    """Return one representative coordinate per residue without membrane classification."""
    sorted_atoms = sorted(atoms, key=_residue_key)
    residues: list[ResidueRecord] = []
    for _, group in groupby(sorted_atoms, key=_residue_key):
        residue_atoms = list(group)
        representative = _representative_atom(residue_atoms)
        residues.append(
            ResidueRecord(
                model=representative.model,
                chain=representative.chain or "_",
                resi=representative.resi,
                resn=representative.resn.upper(),
                x=representative.x,
                y=representative.y,
                z=representative.z,
                classification="outside",
            )
        )
    return residues


def classify_residues_for_membrane(
    atoms: list[AtomRecord], membrane: PlanarMembrane
) -> list[ResidueRecord]:
    """Classify residue representative points against an arbitrary planar membrane."""
    classified: list[ResidueRecord] = []
    for residue in aggregate_residues(atoms):
        measurement = measure_point((residue.x, residue.y, residue.z), membrane)
        classified.append(
            ResidueRecord(
                model=residue.model,
                chain=residue.chain,
                resi=residue.resi,
                resn=residue.resn,
                x=residue.x,
                y=residue.y,
                z=residue.z,
                classification=measurement.classification,
                signed_distance=measurement.signed_distance,
                absolute_center_distance=measurement.absolute_center_distance,
                nearest_boundary_distance=measurement.nearest_boundary_distance,
                outside_distance=measurement.outside_distance,
                normalized_depth=measurement.normalized_depth,
            )
        )
    return classified


def flag_core_residues(
    residues: list[ResidueRecord], orientation_source: str = "manual_global_z"
) -> list[ResidueFlag]:
    """Flag charged and polar residues inside the membrane core for inspection."""
    if orientation_source == "manual_global_z":
        core_description = "manually defined membrane core"
    elif orientation_source.startswith("manual"):
        core_description = "manually defined planar membrane core"
    else:
        core_description = "defined planar membrane core"
    flags: list[ResidueFlag] = []
    for residue in residues:
        if residue.classification != "core":
            continue
        if residue.resn in CHARGED_RESIDUES:
            flags.append(
                ResidueFlag(
                    model=residue.model,
                    chain=residue.chain,
                    resi=residue.resi,
                    resn=residue.resn,
                    classification=residue.classification,
                    severity="WARNING",
                    reason=f"charged residue in {core_description}; inspect local environment",
                    z=residue.z,
                    signed_distance=residue.signed_distance,
                    absolute_center_distance=residue.absolute_center_distance,
                    nearest_boundary_distance=residue.nearest_boundary_distance,
                    outside_distance=residue.outside_distance,
                    normalized_depth=residue.normalized_depth,
                )
            )
        elif residue.resn in POLAR_INSPECT_RESIDUES:
            flags.append(
                ResidueFlag(
                    model=residue.model,
                    chain=residue.chain,
                    resi=residue.resi,
                    resn=residue.resn,
                    classification=residue.classification,
                    severity="INSPECT",
                    reason=f"polar residue in {core_description}; may be functional",
                    z=residue.z,
                    signed_distance=residue.signed_distance,
                    absolute_center_distance=residue.absolute_center_distance,
                    nearest_boundary_distance=residue.nearest_boundary_distance,
                    outside_distance=residue.outside_distance,
                    normalized_depth=residue.normalized_depth,
                )
            )
    return flags


def residue_dicts(residues: list[ResidueRecord]) -> list[dict[str, object]]:
    """Convert residues to JSON-friendly dictionaries."""
    return [
        {
            "id": residue.identifier,
            "model": residue.model,
            "chain": residue.chain or "_",
            "resi": residue.resi,
            "resn": residue.resn,
            "x": residue.x,
            "y": residue.y,
            "z": residue.z,
            "classification": residue.classification,
            **_depth_dict(residue),
        }
        for residue in residues
    ]


def _depth_dict(residue: ResidueRecord | ResidueFlag) -> dict[str, float | None]:
    return {
        "signed_distance": residue.signed_distance,
        "absolute_center_distance": residue.absolute_center_distance,
        "nearest_boundary_distance": residue.nearest_boundary_distance,
        "outside_distance": residue.outside_distance,
        "normalized_depth": residue.normalized_depth,
    }


def _residue_key(atom: AtomRecord) -> tuple[str, str, str, str]:
    return atom.model, atom.chain or "_", atom.resi, atom.resn.upper()


def _representative_atom(atoms: list[AtomRecord]) -> AtomRecord:
    ca_atoms = [atom for atom in atoms if atom.name.strip().upper() == "CA"]
    if ca_atoms:
        return ca_atoms[0]

    count = len(atoms)
    first = atoms[0]
    return AtomRecord(
        model=first.model,
        chain=first.chain or "_",
        resi=first.resi,
        resn=first.resn.upper(),
        name="AVG",
        x=sum(map(attrgetter("x"), atoms)) / count,
        y=sum(map(attrgetter("y"), atoms)) / count,
        z=sum(map(attrgetter("z"), atoms)) / count,
    )
