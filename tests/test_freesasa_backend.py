import sys

import pytest

from membrane_vqc import commands, qc
from membrane_vqc.context_models import ExposureConfig
from membrane_vqc.exposure import calculate_exposure
from membrane_vqc.freesasa_backend import calculate_freesasa_exposure
from membrane_vqc.membrane import AtomRecord
from membrane_vqc.orientation import legacy_global_z


def atoms():
    return [
        AtomRecord("m", "A", "1", "ALA", "CA", 0, 0, 0, element="C"),
        AtomRecord("m", "A", "1", "ALA", "CB", 2.5, 0, 0, element="C"),
        AtomRecord("m", "A", "2", "GLY", "CA", 5.0, 0, 0, element="C"),
    ]


def multi_element_atoms():
    return [
        AtomRecord("m", "A", "1", "ALA", "CA", 0.0, 0.0, 0.0, element="C"),
        AtomRecord("m", "A", "1", "ALA", "CB", 2.4, 0.0, 0.0, element="C"),
        AtomRecord("m", "A", "2", "SER", "N", 4.1, 0.3, 0.0, element="N"),
        AtomRecord("m", "A", "2", "SER", "OG", 5.7, 0.5, 0.2, element="O"),
        AtomRecord("m", "A", "3", "CYS", "SG", 7.6, 0.8, 0.4, element="S"),
    ]


def assert_parity(builtin, reference):
    assert reference.metadata.freesasa_status == "used"
    assert set(builtin.by_residue()) == set(reference.by_residue())
    for key, expected in reference.by_residue().items():
        actual = builtin.by_residue()[key]
        residue_tolerance = max(2.0, 0.05 * expected.residue_sasa)
        sidechain_tolerance = max(2.0, 0.05 * expected.sidechain_sasa)
        assert actual.residue_sasa == pytest.approx(expected.residue_sasa, abs=residue_tolerance)
        assert actual.sidechain_sasa == pytest.approx(
            expected.sidechain_sasa, abs=sidechain_tolerance
        )
        builtin_atoms = {item.atom_key: item for item in actual.atom_sasa}
        reference_atoms = {item.atom_key: item for item in expected.atom_sasa}
        assert set(builtin_atoms) == set(reference_atoms)
        for atom_key, reference_atom in reference_atoms.items():
            tolerance = max(2.0, 0.05 * reference_atom.sasa)
            assert builtin_atoms[atom_key].sasa == pytest.approx(reference_atom.sasa, abs=tolerance)


def test_importing_reference_adapter_does_not_import_freesasa():
    assert "freesasa" not in sys.modules


def test_missing_freesasa_returns_explicit_unavailable_result(monkeypatch):
    import membrane_vqc.freesasa_backend as backend

    real_import = backend.importlib.import_module

    def unavailable(name):
        if name == "freesasa":
            raise ImportError("not installed")
        return real_import(name)

    monkeypatch.setattr(backend.importlib, "import_module", unavailable)
    result = calculate_freesasa_exposure(
        atoms(),
        target_residues=[("m", "A", "1", "ALA")],
    )

    assert result.status == "unavailable"
    assert result.metadata.freesasa_status == "unavailable"
    assert result.residues[0].residue_sasa is None
    assert "unavailable" in result.metadata.warnings[-1].lower()


def test_qc_orchestration_preserves_explicit_unavailable_backend_result(monkeypatch):
    import membrane_vqc.freesasa_backend as backend

    real_import = backend.importlib.import_module

    def unavailable(name):
        if name == "freesasa":
            raise ImportError("not installed")
        return real_import(name)

    monkeypatch.setattr(backend.importlib, "import_module", unavailable)
    result = qc._calculate_exposure(
        atoms(),
        config=ExposureConfig(target_scope="all_residues"),
        target_residues=None,
        membrane=legacy_global_z(-15, 15),
        backend="FreeSASA reference",
    )

    assert result.status == "unavailable"
    assert result.metadata.backend == "freesasa_reference"
    assert result.metadata.freesasa_status == "unavailable"


def test_freesasa_standard_240_point_parity_and_atom_mapping():
    pytest.importorskip("freesasa")
    config = ExposureConfig(sphere_points=240, target_scope="all_residues")
    fixture = multi_element_atoms()
    builtin = calculate_exposure(fixture, config=config)
    reference = calculate_freesasa_exposure(fixture, config=config)

    assert {atom.element for residue in reference.residues for atom in residue.atom_sasa} == {
        "C",
        "N",
        "O",
        "S",
    }
    assert_parity(builtin, reference)


@pytest.mark.parametrize("backend", ["FreeSASA reference", "Auto"])
def test_qc_orchestration_uses_installed_freesasa_without_membrane_argument(backend):
    pytest.importorskip("freesasa")
    result = qc._calculate_exposure(
        multi_element_atoms(),
        config=ExposureConfig(sphere_points=240, target_scope="all_residues"),
        target_residues=None,
        membrane=legacy_global_z(-15, 15),
        backend=backend,
    )

    assert result.status == "completed"
    assert result.metadata.backend == "freesasa_reference"
    assert result.metadata.freesasa_status == "used"
    assert all(residue.partition.core_area is None for residue in result.residues)


def test_command_level_context_run_with_freesasa_emits_schema_12(monkeypatch):
    pytest.importorskip("freesasa")
    target = AtomRecord("m", "A", "1", "LYS", "NZ", 0, 0, 0, element="N")
    target_carbon = AtomRecord("m", "A", "1", "LYS", "CE", 1.3, 0, 0, element="C")
    partner = AtomRecord("m", "B", "2", "ASP", "OD1", 3.5, 0, 0, element="O")
    selected = [target, target_carbon, partner]
    monkeypatch.setattr(commands, "clear_owned", lambda: None)
    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj: [target, target_carbon])
    monkeypatch.setattr(qc, "structure_atoms", lambda selection, cmd_obj: selected)
    monkeypatch.setattr(qc, "create_membrane_planes", lambda *args: None)
    for name in (
        "color_hydropathy",
        "show_ligand_shell",
        "show_residue_selections",
        "show_local_context",
        "clear_context",
    ):
        monkeypatch.setattr(qc, name, lambda *args: None)

    report = commands.mvqc_check(
        selection="m",
        ligand="",
        analyze_context=1,
        exposure_backend="FreeSASA reference",
    )

    assert report["schema_version"] == "1.2"
    metadata = report["context_analysis"]["exposure"]
    assert metadata["backend"] == "freesasa_reference"
    assert metadata["freesasa_status"] == "used"
    assert report["review_items"][0]["exposure"]["core_region_accessible_area"] is None


def test_freesasa_singleton_model_is_guarded_without_native_call(monkeypatch):
    freesasa = pytest.importorskip("freesasa")

    def forbidden_calc_coord(*args, **kwargs):
        raise AssertionError("calcCoord must not be called for a singleton model")

    monkeypatch.setattr(freesasa, "calcCoord", forbidden_calc_coord)
    singleton = [AtomRecord("single", "A", "1", "ALA", "CB", 0, 0, 0, element="C")]
    result = calculate_freesasa_exposure(
        singleton,
        config=ExposureConfig(sphere_points=240, target_scope="all_residues"),
    )

    residue = result.by_residue()[("single", "A", "1", "ALA")]
    assert result.status == "unavailable"
    assert result.metadata.freesasa_status == "available"
    assert residue.status == "unavailable"
    assert residue.residue_sasa is None
    assert any("fewer than two supported atoms" in warning for warning in result.metadata.warnings)
    assert any("fewer than two supported atoms" in warning for warning in residue.warnings)


def test_freesasa_mixed_models_complete_valid_model_and_skip_singleton(monkeypatch):
    freesasa = pytest.importorskip("freesasa")
    real_calc_coord = freesasa.calcCoord
    native_model_sizes = []

    def recording_calc_coord(coordinates, radii, parameters):
        native_model_sizes.append(len(radii))
        return real_calc_coord(coordinates, radii, parameters)

    monkeypatch.setattr(freesasa, "calcCoord", recording_calc_coord)
    fixture = [
        AtomRecord("single", "A", "1", "ALA", "CB", 0, 0, 0, element="C"),
        AtomRecord("valid", "A", "1", "ALA", "CB", 0, 0, 0, element="C"),
        AtomRecord("valid", "A", "2", "SER", "OG", 2.4, 0, 0, element="O"),
    ]
    result = calculate_freesasa_exposure(
        fixture,
        config=ExposureConfig(sphere_points=240, target_scope="all_residues"),
    )

    by_residue = result.by_residue()
    assert native_model_sizes == [2]
    assert result.status == "partial"
    assert result.metadata.freesasa_status == "used"
    assert by_residue[("single", "A", "1", "ALA")].status == "unavailable"
    assert by_residue[("valid", "A", "1", "ALA")].status == "completed"
    assert by_residue[("valid", "A", "2", "SER")].status == "completed"


def test_freesasa_target_only_matches_all_residue_mapping():
    pytest.importorskip("freesasa")
    fixture = multi_element_atoms()
    all_config = ExposureConfig(sphere_points=240, target_scope="all_residues")
    target_config = ExposureConfig(sphere_points=240, target_scope="explicit")
    target = ("m", "A", "2", "SER")
    builtin_all = calculate_exposure(fixture, config=all_config)
    reference_all = calculate_freesasa_exposure(fixture, config=all_config)
    builtin_target = calculate_exposure(fixture, config=target_config, target_residues=[target])
    reference_target = calculate_freesasa_exposure(
        fixture, config=target_config, target_residues=[target]
    )

    assert (
        builtin_target.by_residue()[target].as_report_dict()
        == builtin_all.by_residue()[target].as_report_dict()
    )
    assert (
        reference_target.by_residue()[target].as_report_dict()
        == reference_all.by_residue()[target].as_report_dict()
    )
    assert_parity(builtin_target, reference_target)


def test_freesasa_model_isolation_matches_builtin():
    pytest.importorskip("freesasa")
    fixture = [
        AtomRecord("A", "A", "1", "ALA", "CB", 0, 0, 0, element="C"),
        AtomRecord("A", "A", "2", "SER", "OG", 2.4, 0, 0, element="O"),
        AtomRecord("B", "A", "1", "ALA", "CB", 0, 0, 0, element="C"),
        AtomRecord("B", "A", "2", "SER", "OG", 2.4, 0, 0, element="O"),
    ]
    config = ExposureConfig(sphere_points=240, target_scope="all_residues")
    builtin = calculate_exposure(fixture, config=config)
    reference = calculate_freesasa_exposure(fixture, config=config)

    for result in (builtin, reference):
        by_residue = result.by_residue()
        assert by_residue[("A", "A", "1", "ALA")].residue_sasa == pytest.approx(
            by_residue[("B", "A", "1", "ALA")].residue_sasa, abs=1e-12
        )
        assert by_residue[("A", "A", "2", "SER")].residue_sasa == pytest.approx(
            by_residue[("B", "A", "2", "SER")].residue_sasa, abs=1e-12
        )
    assert_parity(builtin, reference)
