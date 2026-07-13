from membrane_vqc.membrane import AtomRecord, classify_residues, flag_core_residues


def test_classifies_core_outside_and_interfaces():
    atoms = [
        AtomRecord(model="m", chain="A", resi="1", resn="ALA", name="CA", x=0, y=0, z=0),
        AtomRecord(model="m", chain="A", resi="2", resn="VAL", name="CA", x=0, y=0, z=20),
        AtomRecord(model="m", chain="A", resi="3", resn="SER", name="CA", x=0, y=0, z=16),
        AtomRecord(model="m", chain="A", resi="4", resn="THR", name="CA", x=0, y=0, z=-16),
    ]

    residues = classify_residues(atoms, zmin=-15, zmax=15, interface_width=3)
    by_resi = {res.resi: res.classification for res in residues}

    assert by_resi["1"] == "core"
    assert by_resi["2"] == "outside"
    assert by_resi["3"] == "upper_interface"
    assert by_resi["4"] == "lower_interface"


def test_ca_coordinate_preferred_over_average_fallback():
    atoms = [
        AtomRecord(model="m", chain="A", resi="1", resn="LYS", name="N", x=0, y=0, z=30),
        AtomRecord(model="m", chain="A", resi="1", resn="LYS", name="CA", x=0, y=0, z=0),
        AtomRecord(model="m", chain="A", resi="1", resn="LYS", name="C", x=0, y=0, z=30),
        AtomRecord(model="m", chain="A", resi="2", resn="ASP", name="N", x=0, y=0, z=10),
        AtomRecord(model="m", chain="A", resi="2", resn="ASP", name="C", x=0, y=0, z=20),
    ]

    residues = classify_residues(atoms, zmin=-15, zmax=15)
    by_resi = {res.resi: res for res in residues}

    assert by_resi["1"].z == 0
    assert by_resi["1"].classification == "core"
    assert by_resi["2"].z == 15
    assert by_resi["2"].classification == "core"


def test_charged_and_polar_core_residues_are_flagged_for_inspection():
    atoms = [
        AtomRecord(model="m", chain="A", resi="1", resn="LYS", name="CA", x=0, y=0, z=0),
        AtomRecord(model="m", chain="A", resi="2", resn="HIS", name="CA", x=0, y=0, z=0),
        AtomRecord(model="m", chain="A", resi="3", resn="LEU", name="CA", x=0, y=0, z=0),
    ]

    residues = classify_residues(atoms, zmin=-15, zmax=15)
    flags = flag_core_residues(residues)
    by_resi = {flag.resi: flag for flag in flags}

    assert by_resi["1"].severity == "WARNING"
    assert by_resi["2"].severity == "INSPECT"
    assert "3" not in by_resi
