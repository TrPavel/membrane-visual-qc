from membrane_vqc import qc
from membrane_vqc.membrane import AtomRecord
from membrane_vqc.orientation import PlanarMembrane


def test_arbitrary_normal_analysis_classifies_and_reports_depth(monkeypatch):
    membrane = PlanarMembrane(
        center=(10, 0, 0),
        normal=(1, 0, 0),
        lower_offset=-5,
        upper_offset=10,
        interface_width=2,
        source="unit_test",
    )
    atoms = [
        AtomRecord("m", "A", "1", "LYS", "CA", 10, 50, -20),
        AtomRecord("m", "A", "2", "ALA", "CA", 20, 0, 0),
        AtomRecord("m", "A", "3", "ALA", "CA", 22, 0, 0),
    ]
    rendered = []
    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj: atoms)
    monkeypatch.setattr(qc, "ligand_atoms", lambda selection, ligand, cmd_obj: [])
    monkeypatch.setattr(qc, "create_membrane_planes", lambda *args: rendered.append(args))
    for name in ("color_hydropathy", "show_ligand_shell", "show_residue_selections"):
        monkeypatch.setattr(qc, name, lambda *args: None)
    report = qc.run_check_with_membrane(
        selection="m", membrane=membrane, ligand="", cutoff=5, cmd_obj=object()
    )
    assert report["summary"]["core_residues"] == 2
    assert report["summary"]["charged_core_residues"] == 1
    assert report["review_items"][0]["signed_distance"] == 0.0
    assert report["review_items"][0]["normalized_depth"] == 1.0
    assert "defined planar membrane core" in report["review_items"][0]["reason"]
    assert "manually" not in report["review_items"][0]["reason"]
    assert report["orientation"]["normal"] == [1.0, 0.0, 0.0]
    assert rendered[0][0] is membrane


def test_legacy_adapter_and_explicit_global_z_produce_same_summary(monkeypatch):
    atoms = [
        AtomRecord("m", "A", "1", "LYS", "CA", 0, 0, 0),
        AtomRecord("m", "A", "2", "SER", "CA", 0, 0, 16),
    ]
    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj: atoms)
    monkeypatch.setattr(qc, "ligand_atoms", lambda selection, ligand, cmd_obj: [])
    monkeypatch.setattr(qc, "create_membrane_planes", lambda *args: None)
    for name in ("color_hydropathy", "show_ligand_shell", "show_residue_selections"):
        monkeypatch.setattr(qc, name, lambda *args: None)
    legacy = qc.run_check(selection="m", zmin=-15, zmax=15, ligand="", cmd_obj=object())
    explicit = qc.run_check_with_membrane(
        selection="m",
        ligand="",
        cmd_obj=object(),
        membrane=PlanarMembrane(
            center=(0, 0, 0),
            normal=(0, 0, 1),
            lower_offset=-15,
            upper_offset=15,
            interface_width=3,
            source="manual_global_z",
        ),
    )
    assert explicit["summary"] == legacy["summary"]
