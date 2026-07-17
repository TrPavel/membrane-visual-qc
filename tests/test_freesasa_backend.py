import sys

import pytest

from membrane_vqc.context_models import ExposureConfig
from membrane_vqc.exposure import calculate_exposure
from membrane_vqc.freesasa_backend import calculate_freesasa_exposure
from membrane_vqc.membrane import AtomRecord


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
