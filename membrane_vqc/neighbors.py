"""Ligand/cofactor neighbourhood logic independent of PyMOL."""

from __future__ import annotations

from math import dist

from .membrane import AtomRecord, ResidueRecord, classify_residues


def ligand_neighbor_residues(
    protein_atoms: list[AtomRecord],
    ligand_atoms: list[AtomRecord],
    cutoff: float,
) -> list[ResidueRecord]:
    """Return residues with any atom within cutoff of any ligand atom."""
    if not protein_atoms or not ligand_atoms:
        return []

    cutoff = float(cutoff)
    neighbor_atoms: list[AtomRecord] = []
    seen: set[tuple[str, str, str, str]] = set()
    ligand_coords = [(atom.x, atom.y, atom.z) for atom in ligand_atoms]
    for atom in protein_atoms:
        atom_coord = (atom.x, atom.y, atom.z)
        if any(dist(atom_coord, ligand_coord) <= cutoff for ligand_coord in ligand_coords):
            key = (atom.model, atom.chain or "_", atom.resi, atom.resn.upper())
            if key not in seen:
                seen.add(key)
                neighbor_atoms.append(atom)

    return classify_residues(
        neighbor_atoms, zmin=float("-inf"), zmax=float("inf"), interface_width=0
    )
