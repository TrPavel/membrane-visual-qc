import json

import pytest

from membrane_vqc import qc
from membrane_vqc.errors import ReportError
from membrane_vqc.orientation import PlanarMembrane
from membrane_vqc.orientation_io import load_orientation_file, write_orientation_file
from membrane_vqc.qc import _pymol_version
from membrane_vqc.report import build_report, export_report, sha256_file, validate_report


def test_build_report_contains_required_fields_and_timestamp():
    report = build_report(
        selection="all",
        zmin=-15,
        zmax=15,
        ligand_selection="organic",
        cutoff=5,
        total_residues=10,
        core_residues=4,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=["manual slab"],
    )

    assert report["plugin"] == "membrane-vqc-pymol"
    assert report["schema_version"] == "1.1"
    assert report["software"]["name"] == "membrane-vqc-pymol"
    assert report["software"]["commit_status"] == "recorded"
    assert report["runtime"]["pymol_status"] == "unavailable"
    assert report["input"]["provenance_status"] == "input_path_not_supplied"
    assert report["timestamp"]
    assert report["input"]["selection"] == "all"
    assert report["summary"]["total_residues"] == 10
    assert report["summary"]["core_residues"] == 4
    assert report["summary"]["overall_status"] == "NO_FLAGS"
    assert report["orientation"]["source"] == "manual_global_z"
    assert report["orientation"]["normal"] == [0.0, 0.0, 1.0]
    assert report["orientation"]["lower_offset"] == -15.0
    assert report["orientation"]["upper_offset"] == 15.0
    assert "This plugin is a visual QC helper" in report["limitations"][1]


def test_export_report_creates_parent_directory_and_valid_json(tmp_path):
    report = build_report(
        selection="all",
        zmin=-15,
        zmax=15,
        ligand_selection="organic",
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
                "reason": "charged residue in manually defined membrane core",
                "z": 0.0,
            }
        ],
        ligand_neighbours=[],
        warnings=[],
    )
    output = tmp_path / "nested" / "report.json"

    paths = export_report(report, output, write_csv=True)

    assert output in paths
    assert output.with_suffix(".csv") in paths
    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["summary"]["charged_core_residues"] == 1
    assert loaded["summary"]["overall_status"] == "REVIEW_ITEMS"
    assert loaded["review_items"] == loaded["flagged_residues"]


def test_empty_analysis_reports_insufficient_context():
    report = build_report(
        selection="none",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=0,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=["No protein atoms found"],
    )

    assert report["summary"]["overall_status"] == "INSUFFICIENT_CONTEXT"


def test_input_hash_uses_basename_and_sha256(tmp_path):
    source = tmp_path / "private" / "model.cif"
    source.parent.mkdir()
    source.write_bytes(b"data_test\n")
    report = build_report(
        selection="all",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=1,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        input_path=source,
        input_format="mmCIF",
    )

    assert report["input"]["path"] == "model.cif"
    assert report["input"]["sha256"] == sha256_file(source)
    assert report["input"]["provenance_status"] == "file_hashed"


def test_input_provenance_is_empty_without_explicit_source_path():
    report = build_report(
        selection="object_from_session",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=1,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
    )

    assert report["input"]["path"] == ""
    assert report["input"]["sha256"] == ""


def test_pymol_version_uses_command_api():
    class FakeCmd:
        @staticmethod
        def get_version():
            return ("3.1.8", 3.108, 3108)

    assert _pymol_version(FakeCmd()) == "3.1.8"


def test_pymol_version_is_empty_when_api_does_not_expose_it():
    assert _pymol_version(object()) == ""


def test_run_check_records_explicit_input_and_pymol_runtime(monkeypatch, tmp_path):
    source = tmp_path / "model.pdb"
    source.write_text("END\n", encoding="ascii")

    class FakeCmd:
        @staticmethod
        def get_version():
            return ("3.1.8", 3.108, 3108)

    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj: [])
    report = qc.run_check(cmd_obj=FakeCmd(), input_path=str(source))

    assert report["runtime"]["pymol"] == "3.1.8"
    assert report["input"]["path"] == "model.pdb"
    assert report["input"]["sha256"] == sha256_file(source)


def test_validate_report_rejects_legacy_biological_ok_status():
    report = build_report(
        selection="all",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=1,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
    )
    report["summary"]["overall_status"] = "OK"

    with pytest.raises(ReportError, match="Invalid biological review status"):
        validate_report(report)


def test_validate_report_requires_review_item_identity_and_interpretation_fields():
    report = build_report(
        selection="all",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=1,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
    )
    report["review_items"] = [{"model": "m"}]

    with pytest.raises(ReportError, match="missing required fields"):
        validate_report(report)


def test_explicit_commit_provenance_takes_precedence():
    report = build_report(
        selection="all",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=1,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        software_commit="f" * 40,
    )
    assert report["software"]["commit"] == "f" * 40
    assert report["software"]["commit_status"] == "recorded"


def test_planar_orientation_and_import_provenance_are_reported(tmp_path):
    membrane = PlanarMembrane(
        center=(1, 2, 3),
        normal=(1, 0, 0),
        lower_offset=-8,
        upper_offset=12,
        interface_width=4,
        source="fixture_manual",
        metadata={"fixture": "rotated"},
    )
    orientation_path = write_orientation_file(membrane, tmp_path / "plane.json")
    loaded = load_orientation_file(orientation_path)
    report = build_report(
        selection="model",
        zmin=-8,
        zmax=12,
        ligand_selection="",
        cutoff=5,
        total_residues=1,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        membrane=loaded.membrane,
        orientation_import=loaded,
    )
    assert report["orientation"]["center"] == [1.0, 2.0, 3.0]
    assert report["orientation"]["normal"] == [1.0, 0.0, 0.0]
    assert report["orientation"]["import"] == {
        "path": "plane.json",
        "sha256": loaded.sha256,
        "schema_version": "1.0",
    }
