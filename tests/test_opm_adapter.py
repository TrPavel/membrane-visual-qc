from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from membrane_vqc.errors import OrientationError
from membrane_vqc.comparison_worker import (
    ComparisonRequest,
    ComparisonWorkerOrchestrator,
    ComparisonWorkerResult,
)
from membrane_vqc.opm_adapter import IDENTITY_LIMIT, import_opm_orientation
from membrane_vqc.orientation_sources import StructureContext


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "synthetic" / "opm_oriented_test.pdb"


def _payload() -> bytes:
    return FIXTURE.read_bytes()


def _current(payload: bytes | None = None, *, structure_id: str = "test", model: int = 1):
    payload = payload or _payload()
    lines = [
        line
        for line in payload.splitlines()
        if not (line.startswith(b"HETATM") and line[17:20].strip() == b"DUM")
    ]
    return StructureContext(b"\n".join(lines) + b"\n", structure_id, model)


def _import(payload: bytes | None = None, context: StructureContext | None = None, record="test"):
    return import_opm_orientation(
        payload or _payload(),
        context or _current(payload),
        metadata={"expected_record_id": record},
    )


def _codes(result):
    return [message.code for message in result.messages]


def _replace_line(payload: bytes, predicate, transform) -> bytes:
    lines = payload.splitlines()
    for index, line in enumerate(lines):
        if predicate(line):
            lines[index] = transform(line)
            break
    return b"\n".join(lines) + b"\n"


def _set_xyz(line: bytes, xyz: tuple[float, float, float]) -> bytes:
    text = line.decode("ascii")
    return (text[:30] + "".join(f"{value:8.3f}" for value in xyz) + text[54:]).encode("ascii")


def test_synthetic_fixture_is_explicitly_fake_and_imports_deterministically():
    payload = _payload()
    first = _import(payload)
    second = _import(payload)

    assert b"TEST" in payload
    assert b"1PCR" not in payload.upper()
    assert first.status == "imported"
    assert first.as_dict() == second.as_dict()
    assert first.membrane.center == pytest.approx((0.0, 0.0, 0.0))
    assert first.membrane.normal == pytest.approx((0.0, 0.0, 1.0))
    assert first.membrane.lower_offset == pytest.approx(-15.0)
    assert first.membrane.upper_offset == pytest.approx(15.0)
    assert first.evidence.directional_topology_available is False
    assert first.evidence.applicability.method == "identity_no_transform"
    assert first.evidence.applicability.rmsd == 0.0
    assert first.evidence.applicability.maximum_residual == 0.0
    assert first.source.raw_payloads[0].sha256 == hashlib.sha256(payload).hexdigest()
    assert first.source.raw_payloads[0].byte_size == len(payload)


def test_direct_adapter_reports_the_enforced_five_mibibyte_limit():
    oversized = b" " * (5 * 1024 * 1024 + 1)

    result = _import(oversized, _current())

    assert result.status == "rejected"
    assert result.messages[0].code == "PAYLOAD_TOO_LARGE"
    assert "5 MiB" in result.messages[0].message


def test_result_contains_no_local_path_or_unrequested_metadata():
    result = _import()
    serialized = repr(result.as_dict())

    assert str(FIXTURE) not in serialized
    assert "source_url': None" in serialized
    assert result.evidence.raw_metadata["dum_label_semantics"].startswith("N/O distinguish")


def test_opposite_dum_label_order_is_same_undirected_geometry():
    payload = _payload()
    swapped = []
    for line in payload.splitlines():
        if line.startswith(b"HETATM") and line[17:20].strip() == b"DUM":
            atom = line[12:16].strip()
            replacement = b" O  " if atom == b"N" else b" N  "
            line = line[:12] + replacement + line[16:]
        swapped.append(line)
    swapped_payload = b"\n".join(swapped) + b"\n"

    original = _import(payload)
    reversed_labels = _import(swapped_payload, _current(payload))

    assert reversed_labels.status == "imported"
    assert reversed_labels.membrane.center == pytest.approx(original.membrane.center)
    assert reversed_labels.membrane.normal == pytest.approx(original.membrane.normal)
    assert reversed_labels.evidence.directional_topology_available is False


@pytest.mark.parametrize(
    ("payload", "context", "expected", "code"),
    [
        (
            lambda: _payload().replace(b"TEST", b"8ZZZ", 1),
            lambda: _current(),
            "test",
            "RECORD_ID_MISMATCH",
        ),
        (lambda: _payload(), lambda: _current(structure_id="8zzz"), "test", "CURRENT_ID_MISMATCH"),
        (
            lambda: (
                b"\n".join(line for line in _payload().splitlines() if b" O   DUM" not in line)
                + b"\n"
            ),
            lambda: _current(),
            "test",
            "MISSING_DUMMY_BOUNDARY",
        ),
    ],
)
def test_identity_and_required_boundary_failures(payload, context, expected, code):
    result = _import(payload(), context(), expected)
    assert result.status == "rejected"
    assert _codes(result) == [code]
    assert result.membrane is None
    assert result.evidence is None


def test_placeholder_header_is_allowed_but_explicitly_warned():
    payload = _payload().replace(b"TEST", b"XXXX", 1)
    result = _import(payload, _current())

    assert result.status == "imported"
    assert [warning.code for warning in result.evidence.warnings] == ["HEADER_ID_UNAVAILABLE"]
    assert result.source.record_id == "test"


def test_multimodel_opm_is_unsupported():
    payload = _payload()
    lines = payload.splitlines()
    atoms = [line for line in lines if line.startswith(b"ATOM")]
    payload = (
        b"\n".join(
            [
                lines[0],
                lines[1],
                b"MODEL        1",
                *atoms,
                b"ENDMDL",
                b"MODEL        2",
                *atoms,
                b"ENDMDL",
                *lines[-9:],
            ]
        )
        + b"\n"
    )
    result = _import(payload, _current())

    assert result.status == "unsupported"
    assert _codes(result) == ["MULTIPLE_MODELS"]


def test_nonplanar_boundary_is_unsupported():
    payload = _replace_line(
        _payload(),
        lambda line: line.startswith(b"HETATM   16"),
        lambda line: _set_xyz(line, (10.0, 10.0, -14.0)),
    )
    result = _import(payload, _current())

    assert result.status == "unsupported"
    assert _codes(result) == ["NON_PLANAR_MEMBRANE"]


def test_collinear_boundary_is_unsupported():
    payload = _payload()
    changes = {
        b"HETATM   13": (-10.0, 0.0, -15.0),
        b"HETATM   14": (-5.0, 0.0, -15.0),
        b"HETATM   15": (5.0, 0.0, -15.0),
        b"HETATM   16": (10.0, 0.0, -15.0),
    }
    for prefix, xyz in changes.items():
        payload = _replace_line(
            payload,
            lambda line, p=prefix: line.startswith(p),
            lambda line, q=xyz: _set_xyz(line, q),
        )
    result = _import(payload, _current())

    assert result.status == "unsupported"
    assert _codes(result) == ["DEGENERATE_DUMMY_PLANE"]


def test_nonparallel_boundary_is_unsupported():
    payload = _payload()
    changes = {
        b"HETATM   17": (-10.0, -10.0, 14.0),
        b"HETATM   18": (10.0, -10.0, 16.0),
        b"HETATM   19": (-10.0, 10.0, 14.0),
        b"HETATM   20": (10.0, 10.0, 16.0),
    }
    for prefix, xyz in changes.items():
        payload = _replace_line(
            payload,
            lambda line, p=prefix: line.startswith(p),
            lambda line, q=xyz: _set_xyz(line, q),
        )
    result = _import(payload, _current())

    assert result.status == "unsupported"
    assert _codes(result) == ["NON_PARALLEL_BOUNDARIES"]


def test_thickness_comes_from_dum_and_remark_mismatch_is_warning_only():
    payload = _payload().replace(b"15.000", b"14.000", 1)
    result = _import(payload, _current())

    assert result.status == "imported"
    assert result.membrane.lower_offset == pytest.approx(-15.0)
    assert [warning.code for warning in result.evidence.warnings] == ["THICKNESS_REMARK_MISMATCH"]


def test_identity_tolerance_accepts_small_rounding_residual():
    current = _current().pdb_payload
    current = _replace_line(
        current,
        lambda line: line.startswith(b"ATOM      1"),
        lambda line: _set_xyz(line, (0.002, 0.0, 0.0)),
    )
    result = _import(context=StructureContext(current, "test", 1))

    assert result.status == "imported"
    assert result.evidence.applicability.maximum_residual == pytest.approx(0.002)
    assert result.evidence.applicability.maximum_residual <= IDENTITY_LIMIT


def test_shifted_coordinates_are_rejected_without_fit_or_transform():
    current = _current().pdb_payload
    shifted = []
    for line in current.splitlines():
        if line.startswith(b"ATOM"):
            text = line.decode("ascii")
            xyz = tuple(
                float(text[start:end]) + delta
                for (start, end), delta in zip(((30, 38), (38, 46), (46, 54)), (1.0, -2.0, 3.0))
            )
            line = _set_xyz(line, xyz)
        shifted.append(line)
    result = _import(context=StructureContext(b"\n".join(shifted) + b"\n", "test", 1))

    assert result.status == "rejected"
    assert _codes(result) == ["COORDINATE_FRAME_MISMATCH"]
    assert "fitting is not allowed" in result.messages[0].message


def test_atom_or_chain_scope_ambiguity_is_rejected():
    current = _current().pdb_payload
    removed_atom = (
        b"\n".join(line for line in current.splitlines() if not line.startswith(b"ATOM     12"))
        + b"\n"
    )
    atom_result = _import(context=StructureContext(removed_atom, "test", 1))
    changed_chain = current.replace(b"ALA A   1", b"ALA B   1", 1)
    chain_result = _import(context=StructureContext(changed_chain, "test", 1))

    assert _codes(atom_result) == ["ATOM_SCOPE_MISMATCH"]
    assert _codes(chain_result) == ["ATOM_SCOPE_MISMATCH"]


def test_metadata_contract_and_exact_byte_input_are_fail_closed():
    with pytest.raises(OrientationError, match="unsupported fields"):
        import_opm_orientation(
            _payload(), _current(), metadata={"expected_record_id": "test", "path": "secret"}
        )
    with pytest.raises(OrientationError, match="exactly four"):
        import_opm_orientation(_payload(), _current(), metadata={"expected_record_id": "bad"})
    with pytest.raises(OrientationError, match="exact bytes"):
        import_opm_orientation("not bytes", _current(), metadata={"expected_record_id": "test"})  # type: ignore[arg-type]


def test_digest_binds_exact_bytes_even_when_geometry_is_unchanged():
    first = _import()
    changed = _payload().replace(b"REMARK", b"REMARK", 1) + b"REMARK   synthetic trailing note\n"
    second = _import(changed, _current())

    assert second.status == "imported"
    assert first.membrane.center == second.membrane.center
    assert first.membrane.normal == second.membrane.normal
    assert first.membrane.lower_offset == second.membrane.lower_offset
    assert first.membrane.upper_offset == second.membrane.upper_offset
    assert first.source.raw_payloads[0].sha256 != second.source.raw_payloads[0].sha256


def test_real_comparison_worker_path_uses_offline_opm_adapter(tmp_path):
    opm_path = tmp_path / "synthetic-opm.pdb"
    opm_path.write_bytes(_payload())
    current = (ROOT / "data" / "synthetic" / "pdbtm_original_test.pdb").read_bytes()
    request = ComparisonRequest(
        structure_context=StructureContext(current, "test", 1),
        pdbtm_json_payload=(ROOT / "data" / "synthetic" / "pdbtm_api_v1_test.json").read_bytes(),
        pdbtm_transformed_pdb_payload=(
            ROOT / "data" / "synthetic" / "pdbtm_transformed_test.pdb"
        ).read_bytes(),
        opm_path=opm_path,
        expected_record_id="test",
    )

    result = ComparisonWorkerOrchestrator().compare(request)

    assert isinstance(result, ComparisonWorkerResult)
    assert result.pdbtm.status == "imported"
    assert result.opm.status == "imported"
    assert result.opm.evidence.applicability.method == "identity_no_transform"
    assert result.opm_sha256 == hashlib.sha256(_payload()).hexdigest()
