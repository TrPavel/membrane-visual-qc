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


def test_freesasa_reference_parity_when_optional_package_is_installed():
    pytest.importorskip("freesasa")
    config = ExposureConfig(sphere_points=960, target_scope="all_residues")
    builtin = calculate_exposure(atoms(), config=config)
    reference = calculate_freesasa_exposure(atoms(), config=config)

    assert reference.metadata.freesasa_status == "used"
    for key, expected in builtin.by_residue().items():
        actual = reference.by_residue()[key]
        tolerance = max(2.0, 0.05 * expected.residue_sasa)
        assert actual.residue_sasa == pytest.approx(expected.residue_sasa, abs=tolerance)
