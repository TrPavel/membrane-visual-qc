import json
import hashlib
from pathlib import Path

import pytest

from scripts.validate_example_reports import (
    default_report_paths,
    validate_reports,
    validate_reports_by_version,
)
from membrane_vqc.context_models import ExposureConfig
from membrane_vqc.exposure import calculate_exposure
from membrane_vqc.membrane import AtomRecord
from membrane_vqc.orientation import legacy_global_z
from membrane_vqc.report import build_report


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "mvqc-report-1.0.schema.json"
SCHEMA_1_1 = ROOT / "schemas" / "mvqc-report-1.1.schema.json"
SCHEMA_1_2 = ROOT / "schemas" / "mvqc-report-1.2.schema.json"


def test_schema_has_stable_non_placeholder_identifier():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert schema["$id"] == "urn:membrane-vqc:schema:report:1.0"
    schema_1_1 = json.loads(SCHEMA_1_1.read_text(encoding="utf-8"))
    assert schema_1_1["$id"] == "urn:membrane-vqc:schema:report:1.1"
    schema_1_2 = json.loads(SCHEMA_1_2.read_text(encoding="utf-8"))
    assert schema_1_2["$id"] == "urn:membrane-vqc:schema:report:1.2-draft"


def test_released_schema_files_remain_byte_for_byte_immutable():
    assert hashlib.sha256(SCHEMA.read_bytes()).hexdigest() == (
        "5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710"
    )
    assert hashlib.sha256(SCHEMA_1_1.read_bytes()).hexdigest() == (
        "86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf"
    )


def test_generated_example_reports_validate_against_json_schema():
    pytest.importorskip("jsonschema")
    reports = [
        path
        for path in default_report_paths(ROOT / "reports")
        if json.loads(path.read_text(encoding="utf-8"))["schema_version"] == "1.1"
    ]

    assert reports
    validate_reports(SCHEMA_1_1, reports)


def test_generated_examples_can_dispatch_by_declared_schema_version():
    pytest.importorskip("jsonschema")
    reports = default_report_paths(ROOT / "reports")
    assert validate_reports_by_version(reports) == {"1.1": 7, "1.2": 5}


def test_exposure_report_validates_against_draft_schema_1_2(tmp_path):
    pytest.importorskip("jsonschema")
    atom = AtomRecord("m", "A", "1", "LYS", "NZ", 0, 0, 0, element="N")
    exposure = calculate_exposure(
        [atom],
        config=ExposureConfig(),
        target_residues=[("m", "A", "1", "LYS")],
    )
    report = build_report(
        selection="m",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=1,
        core_residues=1,
        flagged_residues=[
            {
                "model": "m",
                "chain": "A",
                "resi": "1",
                "resn": "LYS",
                "classification": "core",
                "severity": "WARNING",
                "reason": "charged residue in membrane core",
                "z": 0.0,
            }
        ],
        ligand_neighbours=[],
        warnings=[],
        exposure_analysis=exposure,
    )
    path = tmp_path / "exposure.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    assert report["schema_version"] == "1.2"
    assert report["review_items"][0]["exposure"]["status"] == "completed"
    validate_reports(SCHEMA_1_2, [path])


def test_schema_1_2_accepts_zero_sasa_areas_with_null_fractions(tmp_path):
    target = AtomRecord("m", "A", "1", "LYS", "NZ", 0, 0, 0, element="N")
    enclosing = AtomRecord("m", "A", "2", "UNK", "I1", 0, 0, 0, element="I")
    exposure = calculate_exposure(
        [target, enclosing],
        config=ExposureConfig(),
        target_residues=[("m", "A", "1", "LYS")],
        membrane=legacy_global_z(-15, 15),
    )
    report = build_report(
        selection="m",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=2,
        core_residues=1,
        flagged_residues=[
            {
                "model": "m",
                "chain": "A",
                "resi": "1",
                "resn": "LYS",
                "classification": "core",
                "severity": "WARNING",
                "reason": "charged residue in membrane core",
                "z": 0.0,
            }
        ],
        ligand_neighbours=[],
        warnings=[],
        exposure_analysis=exposure,
    )
    evidence = report["review_items"][0]["exposure"]
    path = tmp_path / "zero-sasa.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    assert evidence["residue_sasa"] == 0.0
    assert evidence["core_region_accessible_area"] == 0.0
    assert evidence["interface_region_accessible_area"] == 0.0
    assert evidence["outside_region_accessible_area"] == 0.0
    assert evidence["core_region_accessible_fraction"] is None
    assert evidence["interface_region_accessible_fraction"] is None
    assert evidence["outside_region_accessible_fraction"] is None
    assert evidence["membrane_region_accessible_fraction"] is None
    validate_reports(SCHEMA_1_2, [path])
