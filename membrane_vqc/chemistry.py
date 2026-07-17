"""Explicit conservative atom-role and non-protein category definitions."""

from __future__ import annotations

from .exposure import TIEN_2013_THEORETICAL_MAX_ASA, normalize_or_infer_element
from .membrane import AtomRecord

STANDARD_RESIDUES = frozenset(TIEN_2013_THEORETICAL_MAX_ASA)
NEGATIVE_ATOMS = {"ASP": frozenset({"OD1", "OD2"}), "GLU": frozenset({"OE1", "OE2"})}
POSITIVE_ATOMS = {
    "LYS": frozenset({"NZ"}),
    "ARG": frozenset({"NE", "NH1", "NH2"}),
}

# Heavy-atom roles only. These support distance-only evidence and do not assign protonation.
DONOR_ATOMS = {
    "ARG": frozenset({"NE", "NH1", "NH2"}),
    "ASN": frozenset({"ND2"}),
    "GLN": frozenset({"NE2"}),
    "HIS": frozenset({"ND1", "NE2"}),
    "LYS": frozenset({"NZ"}),
    "SER": frozenset({"OG"}),
    "THR": frozenset({"OG1"}),
    "TRP": frozenset({"NE1"}),
    "TYR": frozenset({"OH"}),
}
ACCEPTOR_ATOMS = {
    "ASN": frozenset({"OD1"}),
    "ASP": frozenset({"OD1", "OD2"}),
    "GLN": frozenset({"OE1"}),
    "GLU": frozenset({"OE1", "OE2"}),
    "HIS": frozenset({"ND1", "NE2"}),
    "SER": frozenset({"OG"}),
    "THR": frozenset({"OG1"}),
    "TYR": frozenset({"OH"}),
}
BACKBONE_DONORS = frozenset({"N"})
BACKBONE_ACCEPTORS = frozenset({"O", "OXT"})
WATER_RESIDUES = frozenset({"HOH", "WAT", "H2O", "DOD"})
ION_RESIDUES = frozenset(
    {"CA", "CL", "NA", "K", "MG", "ZN", "FE", "MN", "CU", "CO", "NI", "IOD", "BR"}
)
ION_ELEMENTS = frozenset(
    {"CA", "CL", "NA", "K", "MG", "ZN", "FE", "MN", "CU", "CO", "NI", "I", "BR"}
)


def atom_name(atom: AtomRecord) -> str:
    return str(atom.name).strip().upper()


def residue_name(atom: AtomRecord) -> str:
    return str(atom.resn).strip().upper()


def charged_role(atom: AtomRecord) -> str:
    """Return canonical positive/negative role; histidine is intentionally neutral here."""
    resn, name = residue_name(atom), atom_name(atom)
    if name in NEGATIVE_ATOMS.get(resn, ()):
        return "negative"
    if name in POSITIVE_ATOMS.get(resn, ()):
        return "positive"
    return ""


def donor_acceptor_roles(atom: AtomRecord) -> frozenset[str]:
    resn, name = residue_name(atom), atom_name(atom)
    roles: set[str] = set()
    if (name in BACKBONE_DONORS and resn != "PRO") or name in DONOR_ATOMS.get(resn, ()):
        roles.add("donor")
    if name in BACKBONE_ACCEPTORS or name in ACCEPTOR_ATOMS.get(resn, ()):
        roles.add("acceptor")
    return frozenset(roles)


def is_protein(atom: AtomRecord) -> bool:
    return atom.is_hetatm is False or (
        atom.is_hetatm is None and residue_name(atom) in STANDARD_RESIDUES
    )


def is_water(atom: AtomRecord) -> bool:
    return atom.is_hetatm is True and residue_name(atom) in WATER_RESIDUES


def safe_element(atom: AtomRecord) -> str:
    return normalize_or_infer_element(atom)


def is_polar_heavy_element(atom: AtomRecord) -> bool:
    return safe_element(atom) in {"N", "O", "S"}
