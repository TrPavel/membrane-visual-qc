"""Pure-Python membrane slab and residue classification logic."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from operator import attrgetter

from .constants import CHARGED_RESIDUES, DEFAULT_INTERFACE_WIDTH, POLAR_INSPECT_RESIDUES


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

    @property
    def identifier(self) -> str:
        chain = self.chain or "_"
        return f"{self.model}/{chain}/{self.resi}/{self.resn}"

    def as_dict(self) -> dict[str, object]:
        return {
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


def classify_z(z: float, zmin: float, zmax: float, interface_width: float = 0.0) -> str:
    """Classify a z coordinate relative to a manual membrane slab."""
    zmin, zmax = sorted((float(zmin), float(zmax)))
    if zmin <= z <= zmax:
        return "core"
    if 0 < interface_width and zmax < z <= zmax + interface_width:
        return "upper_interface"
    if 0 < interface_width and zmin - interface_width <= z < zmin:
        return "lower_interface"
    return "outside"


def classify_residues(
    atoms: list[AtomRecord],
    zmin: float,
    zmax: float,
    interface_width: float = DEFAULT_INTERFACE_WIDTH,
) -> list[ResidueRecord]:
    """Classify residues using CA coordinates, falling back to residue atom averages."""
    sorted_atoms = sorted(atoms, key=_residue_key)
    residues: list[ResidueRecord] = []
    for _, group in groupby(sorted_atoms, key=_residue_key):
        residue_atoms = list(group)
        representative = _representative_atom(residue_atoms)
        classification = classify_z(representative.z, zmin, zmax, interface_width)
        residues.append(
            ResidueRecord(
                model=representative.model,
                chain=representative.chain or "_",
                resi=representative.resi,
                resn=representative.resn.upper(),
                x=representative.x,
                y=representative.y,
                z=representative.z,
                classification=classification,
            )
        )
    return residues


def flag_core_residues(residues: list[ResidueRecord]) -> list[ResidueFlag]:
    """Flag charged and polar residues inside the membrane core for inspection."""
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
                    reason="charged residue in manually defined membrane core; inspect local environment",
                    z=residue.z,
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
                    reason="polar residue in manually defined membrane core; may be functional",
                    z=residue.z,
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
        }
        for residue in residues
    ]


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
