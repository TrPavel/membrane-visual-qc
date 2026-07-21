import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys

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
from membrane_vqc.pdbtm_cache import CacheRepository
from membrane_vqc.pdbtm_report_provenance import build_pdbtm_acquisition_provenance
from membrane_vqc.report import ReportError, build_report, validate_report


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "mvqc-report-1.0.schema.json"
SCHEMA_1_1 = ROOT / "schemas" / "mvqc-report-1.1.schema.json"
SCHEMA_1_2 = ROOT / "schemas" / "mvqc-report-1.2.schema.json"
SCHEMA_1_3 = ROOT / "schemas" / "mvqc-report-1.3.schema.json"
SCHEMA_1_4 = ROOT / "schemas" / "mvqc-report-1.4.schema.json"
_SYNTHETIC = ROOT / "data" / "synthetic"


def test_example_report_validator_supports_required_direct_script_command():
    environment = dict(os.environ)
    environment["PYTHONPATH"] = ""

    completed = subprocess.run(
        [sys.executable, "scripts/validate_example_reports.py"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Validated 20 report(s)" in completed.stdout


def test_schema_has_stable_non_placeholder_identifier():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert schema["$id"] == "urn:membrane-vqc:schema:report:1.0"
    schema_1_1 = json.loads(SCHEMA_1_1.read_text(encoding="utf-8"))
    assert schema_1_1["$id"] == "urn:membrane-vqc:schema:report:1.1"
    schema_1_2 = json.loads(SCHEMA_1_2.read_text(encoding="utf-8"))
    assert schema_1_2["$id"] == "urn:membrane-vqc:schema:report:1.2-draft"
    schema_1_3 = json.loads(SCHEMA_1_3.read_text(encoding="utf-8"))
    assert schema_1_3["$id"] == "urn:membrane-vqc:schema:report:1.3-draft"
    schema_1_4 = json.loads(SCHEMA_1_4.read_text(encoding="utf-8"))
    assert schema_1_4["$id"] == "urn:membrane-vqc:schema:report:1.4-draft"


def test_released_schema_files_remain_byte_for_byte_immutable():
    assert hashlib.sha256(SCHEMA.read_bytes()).hexdigest() == (
        "5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710"
    )
    assert hashlib.sha256(SCHEMA_1_1.read_bytes()).hexdigest() == (
        "86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf"
    )
    assert hashlib.sha256(SCHEMA_1_2.read_bytes()).hexdigest() == (
        "96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430"
    )
    assert hashlib.sha256(SCHEMA_1_3.read_bytes()).hexdigest() == (
        "6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc"
    )


def test_draft_schema_1_4_file_matches_its_recorded_hash():
    """Schema 1.4 is a new draft contract (not yet released); this pins its bytes so any
    future edit is a deliberate, reviewed change rather than a silent drift."""

    assert hashlib.sha256(SCHEMA_1_4.read_bytes()).hexdigest() == (
        "7d981454cad061681dd5c3dc2a76a283295a7ed82bed2f0d58769d1716602530"
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
    assert validate_reports_by_version(reports) == {"1.1": 7, "1.2": 11, "1.3": 1, "1.4": 1}


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


def _synthetic_acquisition_report(tmp_path, record_id="9zzz"):
    """Build one real schema-1.4 report end to end through the actual Stage 4B1 cache
    and the actual Stage 4B2 conversion -- never hand-typed JSON -- so negative tests
    below mutate a genuinely valid baseline."""

    json_bytes = (
        (_SYNTHETIC / "pdbtm_api_v1_test.json")
        .read_bytes()
        .replace(b'"pdb_id":"test"', f'"pdb_id":"{record_id}"'.encode(), 1)
    )
    pdb_bytes = (
        (_SYNTHETIC / "pdbtm_transformed_test.pdb")
        .read_bytes()
        .replace(b"TEST\n", (record_id.upper() + "\n").encode(), 1)
    )

    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Evidence:
        requested_url: str
        final_url: str
        status: int
        content_type: str
        charset: str | None
        content_encoding: str | None
        etag: str | None
        last_modified: str | None
        requested_at: str
        completed_at: str
        byte_size: int
        sha256: str
        tls_verified: bool = True

    @dataclass(frozen=True)
    class _Payload:
        role: str
        body: bytes
        evidence: _Evidence

    @dataclass(frozen=True)
    class _Versions:
        resource_version: str = "1017"
        software_version: str = "3.2.134"

    @dataclass(frozen=True)
    class _Candidate:
        canonical_record_id: str
        payloads: tuple
        provider_versions: _Versions = _Versions()

    def _payload(role, body, media_type, charset, second):
        suffix = "json" if role == "pdbtm_json" else "trpdb"
        url = f"https://pdbtm.unitmp.org/api/v1/entry/{record_id}.{suffix}"
        return _Payload(
            role,
            body,
            _Evidence(
                url,
                url,
                200,
                media_type,
                charset,
                None,
                None,
                None,
                f"2026-07-21T00:00:0{second}.000000Z",
                f"2026-07-21T00:00:0{second + 1}.000000Z",
                len(body),
                hashlib.sha256(body).hexdigest(),
            ),
        )

    repository = CacheRepository(tmp_path / "cache-v1")
    candidate = _Candidate(
        record_id,
        (
            _payload("pdbtm_json", json_bytes, "application/json", None, 0),
            _payload("transformed_pdb", pdb_bytes, "text/plain", "utf-8", 2),
        ),
    )
    generation = repository.capture_record_generation(record_id)
    repository.commit_validated_pair(candidate, expected_record_generation=generation)
    snapshot = repository.read_active(record_id)
    provenance = build_pdbtm_acquisition_provenance(
        snapshot, consumption_mode="active_cache_read", cache_generation=1
    )
    return build_report(
        selection="synthetic_pdbtm_acquisition",
        zmin=-15.0,
        zmax=15.0,
        ligand_selection="",
        cutoff=5.0,
        total_residues=0,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        pdbtm_acquisition=provenance,
    )


def _validator():
    pytest.importorskip("jsonschema")
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA_1_4.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_schema_1_4_valid_minimal_and_complete_pdbtm_provenance_reports_validate(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)

    assert report["schema_version"] == "1.4"
    assert (
        "evidence" not in report["orientation"]
    )  # minimal: acquisition only, no live-object match
    validator.validate(report)

    complete = json.loads(json.dumps(report))
    complete["orientation"]["confidence"] = "coordinate_verified"
    validator.validate(complete)


def test_schema_1_4_rejects_unknown_acquisition_field(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["unexpected_field"] = "surprise"
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_invalid_provider_kind_discriminator(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["provider_kind"] = "rcsb_api_v2"
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_malformed_timestamp(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["validated_at"] = "2026-07-21 00:00:00"
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_uppercase_digest(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["pair_id"] = report["orientation"]["acquisition"][
        "pair_id"
    ].upper()
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_malformed_digest_length(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["snapshot_id"] = "abc123"
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_negative_payload_size(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["payloads"][0]["byte_size"] = -1
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_non_integer_payload_size(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["payloads"][0]["byte_size"] = 527.5
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_unbounded_string(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["object_applicability"]["statement"] = "x" * 600
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_control_character_in_bounded_text(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["payloads"][0]["etag"] = "bad\x01etag"
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_missing_payload_role(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["payloads"] = [
        report["orientation"]["acquisition"]["payloads"][0]
    ]
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_duplicate_payload_role(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    first = report["orientation"]["acquisition"]["payloads"][0]
    report["orientation"]["acquisition"]["payloads"] = [first, dict(first)]
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_wrong_payload_role_order(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    payloads = report["orientation"]["acquisition"]["payloads"]
    report["orientation"]["acquisition"]["payloads"] = [payloads[1], payloads[0]]
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_requires_acquisition_when_declared(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    del report["orientation"]["acquisition"]
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_object_applicability_is_always_not_established(tmp_path):
    """Guards the scientific-truthfulness boundary directly at the schema level: Stage 4B2
    acquisition provenance must never claim an established object match."""

    report = _synthetic_acquisition_report(tmp_path)
    applicability = report["orientation"]["acquisition"]["object_applicability"]
    assert applicability["established"] is False
    assert applicability["scope"] == "not_evaluated"


def test_existing_schema_1_3_generation_is_unaffected_by_acquisition_support(tmp_path):
    """Backward compatibility: build_report() without pdbtm_acquisition must still emit 1.3
    exactly as before, unaffected by schema 1.4 existing."""

    pytest.importorskip("jsonschema")
    report = build_report(
        selection="m",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=0,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
    )
    assert report["schema_version"] == "1.1"
    assert "acquisition" not in report["orientation"]


def _schema_1_4_report_with_evidence_and_acquisition(tmp_path):
    """A schema-1.4 report carrying BOTH orientation.evidence (copied from the frozen,
    already-valid schema-1.3 synthetic report) and orientation.acquisition -- the
    combination docs/stage4b2_implementation.md explicitly anticipates a future Stage 4B3
    report producing. Built from real, already-valid fixtures; callers corrupt a copy."""

    schema_1_3_report = json.loads(
        (ROOT / "reports" / "pdbtm_synthetic_mvqc.json").read_text(encoding="utf-8")
    )
    acquisition_report = _synthetic_acquisition_report(tmp_path)
    combined = json.loads(json.dumps(schema_1_3_report))  # deep copy
    combined["schema_version"] = "1.4"
    combined["orientation"]["acquisition"] = acquisition_report["orientation"]["acquisition"]
    return combined


def test_stage4_semantics_still_enforced_for_schema_1_4_reports_carrying_evidence(tmp_path):
    """Adversarial-review regression (confirmed independently by two review agents): the
    Stage-4 geometric semantic checks used to be gated on schema_version == "1.3" exactly,
    so an otherwise-identical schema-1.4 report carrying the same orientation.evidence block
    silently skipped them. A non-unit current_geometry.normal must now be rejected for 1.4
    exactly as it already was for 1.3."""

    valid = _schema_1_4_report_with_evidence_and_acquisition(tmp_path)
    validate_report(valid)  # sanity: the unmodified combination is valid on its own

    corrupted = json.loads(json.dumps(valid))
    corrupted["orientation"]["evidence"]["current_geometry"]["normal"] = [
        0.5,
        0.5,
        0.6,
    ]
    with pytest.raises(ReportError, match="unit length"):
        validate_report(corrupted)


def test_stage4_semantics_still_run_via_the_example_validator_script_for_schema_1_4(tmp_path):
    """Same regression as above, via scripts/validate_example_reports.py's own gate
    (independently duplicated there, and independently fixed there)."""

    from scripts.validate_example_reports import validate_stage4_report_semantics

    corrupted = _schema_1_4_report_with_evidence_and_acquisition(tmp_path)
    corrupted["orientation"]["evidence"]["current_geometry"]["normal"] = [
        0.5,
        0.5,
        0.6,
    ]
    with pytest.raises(ReportError, match="unit length"):
        validate_stage4_report_semantics(corrupted)


def test_schema_1_4_rejects_transformed_pdb_payload_with_json_url_suffix(tmp_path):
    """Adversarial-review regression: payload URL suffix was not tied to payload role, so a
    transformed_pdb-role payload with a .json URL used to validate."""

    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    payload = report["orientation"]["acquisition"]["payloads"][1]
    payload["requested_url"] = payload["requested_url"].replace(".trpdb", ".json")
    payload["final_url"] = payload["final_url"].replace(".trpdb", ".json")
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_transformed_pdb_payload_with_json_content_type(tmp_path):
    """Adversarial-review regression: content_type was not tied to payload role, so a
    transformed_pdb-role payload claiming application/json used to validate even though the
    real producer (pdbtm_cache_contract.AcquisitionPayload) can never emit that combination."""

    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    report["orientation"]["acquisition"]["payloads"][1]["content_type"] = {
        "media_type": "application/json",
        "charset": None,
    }
    with pytest.raises(Exception):
        validator.validate(report)


def test_schema_1_4_rejects_pdbtm_json_payload_with_trpdb_url_suffix(tmp_path):
    validator = _validator()
    report = _synthetic_acquisition_report(tmp_path)
    payload = report["orientation"]["acquisition"]["payloads"][0]
    payload["requested_url"] = payload["requested_url"].replace(".json", ".trpdb")
    payload["final_url"] = payload["final_url"].replace(".json", ".trpdb")
    with pytest.raises(Exception):
        validator.validate(report)
