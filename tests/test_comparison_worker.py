from __future__ import annotations

from pathlib import Path

from membrane_vqc.comparison_worker import (
    MAX_OPM_PAYLOAD_BYTES,
    ComparisonOperation,
    ComparisonRequest,
    ComparisonWorkerFailure,
    ComparisonWorkerOrchestrator,
    comparable_orientation,
)
from membrane_vqc.opm_adapter import fingerprint_structure_context
from membrane_vqc.orientation_sources import StructureContext
from membrane_vqc.orientation_sources import OrientationImportResult


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"


def _request(path: Path) -> ComparisonRequest:
    return ComparisonRequest(
        StructureContext(b"ATOM\n", "test", 1, coordinate_frame="pymol_current_object"),
        b"pdbtm-json",
        b"pdbtm-pdb",
        path,
        "TEST",
    )


def test_worker_reads_explicit_local_opm_and_passes_immutable_context(tmp_path):
    path = tmp_path / "synthetic-opm.pdb"
    path.write_bytes(b"opm-payload")
    calls = []

    def pdbtm_loader(json_payload, pdb_payload, context, metadata):
        calls.append(("pdbtm", json_payload, pdb_payload, context, metadata))
        return OrientationImportResult("rejected")

    def opm_loader(payload, structure_context, *, expected_record_id):
        calls.append(("opm", payload, structure_context, expected_record_id))
        return OrientationImportResult("unsupported")

    worker = ComparisonWorkerOrchestrator(
        pdbtm_loader=pdbtm_loader,
        opm_loader=opm_loader,
        comparer=lambda left, right: (left, right),
    )

    result = worker.compare(_request(path))

    assert not isinstance(result, ComparisonWorkerFailure)
    assert result.comparison[0].source_key == "pdbtm"
    assert result.comparison[0].applicable is False
    assert result.comparison[1].source_key == "opm"
    assert result.comparison[1].applicable is False
    assert result.opm_byte_size == len(b"opm-payload")
    assert len(result.opm_sha256) == 64
    assert calls[0][4] == {"expected_record_id": "test"}
    assert calls[1][3] == "test"
    assert calls[0][3] is calls[1][2]


def test_pre_cancelled_request_never_reads_or_calls_adapters(tmp_path):
    path = tmp_path / "opm.pdb"
    path.write_bytes(b"payload")
    operation = ComparisonOperation()
    operation.request_cancel()
    calls = []
    worker = ComparisonWorkerOrchestrator(
        pdbtm_loader=lambda *a, **k: calls.append("pdbtm"),
        opm_loader=lambda *a, **k: calls.append("opm"),
        comparer=lambda *a: calls.append("compare"),
    )

    result = worker.compare(_request(path), operation)

    assert result == ComparisonWorkerFailure(
        "CANCELLED", "The comparison was cancelled.", retryable=True
    )
    assert calls == []


def test_missing_file_failure_never_discloses_local_path(tmp_path):
    path = tmp_path / "private-owner-name" / "missing.pdb"
    result = ComparisonWorkerOrchestrator().compare(_request(path))

    assert isinstance(result, ComparisonWorkerFailure)
    assert result.code == "OPM_FILE_NOT_FOUND"
    assert str(path) not in result.message
    assert "private-owner-name" not in result.message


def test_oversized_opm_file_is_rejected_before_adapter_calls(tmp_path):
    path = tmp_path / "large.pdb"
    with path.open("wb") as stream:
        stream.truncate(MAX_OPM_PAYLOAD_BYTES + 1)
    calls = []
    worker = ComparisonWorkerOrchestrator(
        pdbtm_loader=lambda *a, **k: calls.append(1),
        opm_loader=lambda *a, **k: calls.append(2),
        comparer=lambda *a: calls.append(3),
    )

    result = worker.compare(_request(path))

    assert isinstance(result, ComparisonWorkerFailure)
    assert result.code == "OPM_PAYLOAD_TOO_LARGE"
    assert calls == []


def test_unexpected_adapter_diagnostic_is_replaced_by_safe_failure(tmp_path):
    path = tmp_path / "opm.pdb"
    path.write_bytes(b"payload")
    worker = ComparisonWorkerOrchestrator(
        pdbtm_loader=lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("C:\\Users\\private\\secret.txt")
        ),
        opm_loader=lambda *a, **k: None,
        comparer=lambda *a: None,
    )

    result = worker.compare(_request(path))

    assert isinstance(result, ComparisonWorkerFailure)
    assert result.code == "COMPARISON_FAILED"
    assert "private" not in result.message


def test_request_rejects_invalid_identifier_and_non_bytes(tmp_path):
    context = StructureContext(b"ATOM\n", None, 1)
    import pytest

    with pytest.raises(ValueError, match="four-character"):
        ComparisonRequest(context, b"json", b"pdb", tmp_path / "x", "too-long")
    with pytest.raises(ValueError, match="exact bytes"):
        ComparisonRequest(context, "json", b"pdb", tmp_path / "x", "test")  # type: ignore[arg-type]


def test_real_worker_integrates_pdbtm_and_opm_synthetic_fixtures(tmp_path):
    record_id = "test"
    opm_payload = (SYNTHETIC / "opm_oriented_test.pdb").read_bytes()
    opm_payload = opm_payload.replace(b"9XYZ", b"TEST", 1)
    opm_payload = opm_payload.replace(b"GLY A   2", b"ALA A   2")
    opm_payload = opm_payload.replace(b"SER A   3", b"ALA A   3")
    opm_path = tmp_path / "opm_oriented_test.pdb"
    opm_path.write_bytes(opm_payload)
    current = (
        b"\n".join(line for line in opm_payload.splitlines() if not line.startswith(b"HETATM"))
        + b"\n"
    )
    transformed = (SYNTHETIC / "pdbtm_transformed_test.pdb").read_bytes()
    pdbtm_json = (SYNTHETIC / "pdbtm_api_v1_test.json").read_bytes()
    request = ComparisonRequest(
        StructureContext(
            current,
            record_id,
            1,
            biological_assembly=None,
            coordinate_frame="pymol_current_object",
        ),
        pdbtm_json,
        transformed,
        opm_path,
        record_id,
    )

    result = ComparisonWorkerOrchestrator().compare(request)

    assert not isinstance(result, ComparisonWorkerFailure)
    assert result.pdbtm.status == "imported", result.pdbtm.messages
    assert result.opm.status == "imported", result.opm.messages
    assert result.comparison.first_source == "pdbtm"
    assert result.comparison.second_source == "opm"
    assert result.comparison.comparable is True
    projected_opm = comparable_orientation(result.opm, "opm")
    assert projected_opm.applicability_method == "identity_no_transform"
    assert projected_opm.matched_atom_count == 12
    assert projected_opm.matched_residue_count == 3
    assert result.pdbtm.evidence.current_scope.coordinate_fingerprint == (
        result.opm.evidence.current_scope.coordinate_fingerprint
    )
    assert result.opm.evidence.current_scope.coordinate_fingerprint == (
        fingerprint_structure_context(request.structure_context)
    )
