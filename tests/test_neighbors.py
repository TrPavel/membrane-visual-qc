from membrane_vqc.membrane import AtomRecord
from membrane_vqc.neighbors import ligand_neighbor_residues


def test_ligand_neighbors_include_atoms_within_cutoff_only():
    protein_atoms = [
        AtomRecord(model="m", chain="A", resi="1", resn="ALA", name="CA", x=0, y=0, z=0),
        AtomRecord(model="m", chain="A", resi="2", resn="LEU", name="CA", x=10, y=0, z=0),
    ]
    ligand_atoms = [
        AtomRecord(model="m", chain="L", resi="9", resn="RET", name="C1", x=3, y=0, z=0),
    ]

    neighbors = ligand_neighbor_residues(protein_atoms, ligand_atoms, cutoff=5)

    assert [neighbor.resi for neighbor in neighbors] == ["1"]


def test_empty_ligand_selection_returns_empty_list():
    protein_atoms = [
        AtomRecord(model="m", chain="A", resi="1", resn="ALA", name="CA", x=0, y=0, z=0),
    ]

    assert ligand_neighbor_residues(protein_atoms, [], cutoff=5) == []
