import pytest

from membrane_vqc import qc
from membrane_vqc.context_models import ExposureConfig, LocalContextConfig
from membrane_vqc.exposure import calculate_exposure as calculate_exposure_core
from membrane_vqc.membrane import AtomRecord
from membrane_vqc.orientation import legacy_global_z


def _disable_rendering(monkeypatch):
    monkeypatch.setattr(qc, "create_membrane_planes", lambda *args: None)
    for name in (
        "color_hydropathy",
        "show_ligand_shell",
        "show_residue_selections",
        "show_local_context",
        "clear_context",
    ):
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


def test_context_enabled_extracts_exact_selection_once_and_preserves_severity(monkeypatch):
    target = _protein_target()
    partner = AtomRecord("scope", "B", "2", "ASP", "OD1", 3, 0, 0, element="O", is_hetatm=False)
    calls = []
    rendered = []
    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj: [target])

    def selected(selection, cmd_obj):
        calls.append(selection)
        return [target, partner]

    monkeypatch.setattr(qc, "structure_atoms", selected)
    _disable_rendering(monkeypatch)
    monkeypatch.setattr(qc, "show_local_context", lambda analysis, cmd: rendered.append(analysis))

    report = qc.run_check_with_membrane(
        selection="scope",
        membrane=legacy_global_z(-15, 15),
        ligand="",
        cmd_obj=object(),
        exposure_config=ExposureConfig(target_scope="review_items"),
        local_context_config=LocalContextConfig(),
    )

    assert calls == ["scope"]
    assert len(rendered) == 1
    assert report["schema_version"] == "1.2"
    assert report["review_items"][0]["severity"] == "WARNING"
    assert report["review_items"][0]["local_context"]["contact_support"] == "detected"
    assert report["context_analysis"]["local_context"]["atom_role_policy"] == (
        "standard_residue_roles_v1"
    )


def test_local_context_requires_exposure_configuration():
    with pytest.raises(ValueError, match="requires exposure_config"):
        qc.run_check_with_membrane(
            selection="scope",
            membrane=legacy_global_z(-15, 15),
            cmd_obj=object(),
            local_context_config=LocalContextConfig(),
        )


def test_gui_freesasa_reference_backend_label_is_accepted(monkeypatch):
    marker = object()

    def reference_backend(atoms, *, config, target_residues):
        assert atoms == []
        assert isinstance(config, ExposureConfig)
        assert target_residues == set()
        return marker

    monkeypatch.setattr(qc, "calculate_freesasa_exposure", reference_backend)
    result = qc._calculate_exposure(
        [],
        config=ExposureConfig(),
        target_residues=set(),
        membrane=legacy_global_z(-15, 15),
        backend="FreeSASA reference",
    )
    assert result is marker


def test_builtin_backend_receives_membrane_partition_input(monkeypatch):
    marker = object()
    membrane = legacy_global_z(-15, 15)

    def builtin_backend(atoms, *, config, target_residues, membrane):
        assert atoms == []
        assert isinstance(config, ExposureConfig)
        assert target_residues == set()
        assert membrane is legacy_membrane
        return marker

    legacy_membrane = membrane
    monkeypatch.setattr(qc, "calculate_exposure", builtin_backend)
    result = qc._calculate_exposure(
        [],
        config=ExposureConfig(),
        target_residues=set(),
        membrane=membrane,
        backend="Built-in",
    )
    assert result is marker


def test_builtin_orchestration_produces_membrane_partition_evidence():
    atoms = [
        AtomRecord("m", "A", "1", "LYS", "NZ", 0, 0, 0, element="N"),
        AtomRecord("m", "A", "1", "LYS", "CE", 1.3, 0, 0, element="C"),
    ]
    result = qc._calculate_exposure(
        atoms,
        config=ExposureConfig(target_scope="all_residues"),
        target_residues=None,
        membrane=legacy_global_z(-15, 15),
        backend="Built-in",
    )

    residue = result.residues[0]
    assert result.metadata.backend == "builtin_shrake_rupley"
    assert residue.partition.core_area is not None
    assert residue.partition.core_fraction is not None


def test_auto_falls_back_to_builtin_when_freesasa_is_absent(monkeypatch):
    marker = object()
    membrane = legacy_global_z(-15, 15)
    monkeypatch.setattr(qc.importlib.util, "find_spec", lambda name: None)

    def builtin_backend(atoms, *, config, target_residues, membrane):
        return marker

    monkeypatch.setattr(qc, "calculate_exposure", builtin_backend)
    result = qc._calculate_exposure(
        [],
        config=ExposureConfig(),
        target_residues=set(),
        membrane=membrane,
        backend="Auto",
    )
    assert result is marker
