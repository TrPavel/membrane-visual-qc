import pytest

from membrane_vqc import qc
from membrane_vqc.context_models import ExposureConfig
from membrane_vqc.exposure import calculate_exposure as calculate_exposure_core
from membrane_vqc.membrane import AtomRecord
from membrane_vqc.orientation import legacy_global_z


def _disable_rendering(monkeypatch):
    monkeypatch.setattr(qc, "create_membrane_planes", lambda *args: None)
    for name in ("color_hydropathy", "show_ligand_shell", "show_residue_selections"):
        monkeypatch.setattr(qc, name, lambda *args: None)


def _protein_target():
    return AtomRecord(
        "scope",
        "A",
        "1",
        "LYS",
        "NZ",
        0,
        0,
        0,
        element="N",
        is_hetatm=False,
    )


def _nearby_heteroatom():
    return AtomRecord(
        "scope",
        "_",
        "900",
        "IOD",
        "I1",
        0,
        0,
        0,
        element="I",
        is_hetatm=True,
    )


def test_nonprotein_occluder_flag_controls_actual_qc_exposure(monkeypatch):
    protein = _protein_target()
    heteroatom = _nearby_heteroatom()
    structure_calls = []
    captured_targets = []
    real_calculate = calculate_exposure_core

    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj: [protein])

    def selected_structure(selection, cmd_obj):
        structure_calls.append(selection)
        return [protein, heteroatom]

    def recording_calculate(atoms, *, config, target_residues, membrane):
        captured_targets.append(set(target_residues))
        return real_calculate(
            atoms, config=config, target_residues=target_residues, membrane=membrane
        )

    monkeypatch.setattr(qc, "structure_atoms", selected_structure)
    monkeypatch.setattr(qc, "calculate_exposure", recording_calculate)
    _disable_rendering(monkeypatch)

    without_hetero = qc.run_check_with_membrane(
        selection="scope",
        membrane=legacy_global_z(-15, 15),
        ligand="",
        cmd_obj=object(),
        exposure_config=ExposureConfig(
            target_scope="all_residues", include_nonprotein_occluders=False
        ),
    )
    with_hetero = qc.run_check_with_membrane(
        selection="scope",
        membrane=legacy_global_z(-15, 15),
        ligand="",
        cmd_obj=object(),
        exposure_config=ExposureConfig(
            target_scope="all_residues", include_nonprotein_occluders=True
        ),
    )

    target_key = ("scope", "A", "1", "LYS")
    assert structure_calls == ["scope"]
    assert captured_targets == [{target_key}, {target_key}]
    assert without_hetero["review_items"][0]["exposure"]["residue_sasa"] > 0.0
    assert with_hetero["review_items"][0]["exposure"]["residue_sasa"] == 0.0
    assert without_hetero["context_analysis"]["exposure"]["include_nonprotein_occluders"] is False
    assert with_hetero["context_analysis"]["exposure"]["include_nonprotein_occluders"] is True
    assert len(with_hetero["review_items"]) == 1
    assert with_hetero["review_items"][0]["resn"] == "LYS"


def test_context_disabled_does_not_extract_full_structure(monkeypatch):
    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj: [_protein_target()])
    monkeypatch.setattr(
        qc,
        "structure_atoms",
        lambda *args: pytest.fail("full structure extraction must remain exposure-only"),
    )
    _disable_rendering(monkeypatch)

    report = qc.run_check_with_membrane(
        selection="scope",
        membrane=legacy_global_z(-15, 15),
        ligand="",
        cmd_obj=object(),
    )

    assert report["schema_version"] == "1.1"
    assert "context_analysis" not in report
