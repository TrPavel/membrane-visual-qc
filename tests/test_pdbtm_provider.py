from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import pytest

from membrane_vqc.pdbtm_errors import Stage4BError, Stage4BErrorCode
from membrane_vqc.pdbtm_provider import (
    PAIR_ROLES,
    PdbtmProviderClient,
    canonicalize_record_id,
    validate_pdbtm_pair,
)

ROOT = Path(__file__).resolve().parents[1]
JSON_BYTES = (
    (ROOT / "data" / "synthetic" / "pdbtm_api_v1_test.json")
    .read_bytes()
    .replace(b'"pdb_id":"test"', b'"pdb_id":"1abc"', 1)
)
PDB_BYTES = (
    (ROOT / "data" / "synthetic" / "pdbtm_transformed_test.pdb")
    .read_bytes()
    .replace(b"TEST\n", b"1ABC\n", 1)
)


@dataclass(frozen=True)
class FakePayload:
    role: str
    body: bytes

    @property
    def byte_size(self):
        return len(self.body)

    @property
    def sha256(self):
        return hashlib.sha256(self.body).hexdigest()


class FakeTransport:
    def __init__(self, bodies=None):
        self.bodies = bodies or {
            "pdbtm_json": JSON_BYTES,
            "transformed_pdb": PDB_BYTES,
        }
        self.calls = []

    def fetch(self, record_id, role, *, cancellation=None, pair_deadline=None):
        self.calls.append((record_id, role, cancellation, pair_deadline))
        return FakePayload(role, self.bodies[role])


@pytest.mark.parametrize("value", [" test", "test ", "../x", "1%aa", "1aa?", "١abc", "ABC"])
def test_canonical_record_id_rejects_non_contract_input(value):
    with pytest.raises(Stage4BError) as caught:
        canonicalize_record_id(value)
    assert caught.value.code is Stage4BErrorCode.INVALID_RECORD_ID


def test_provider_fetches_exact_roles_sequentially_and_validates_identity_pair():
    transport = FakeTransport()
    candidate = PdbtmProviderClient(transport).fetch("1AbC")

    assert candidate.canonical_record_id == "1abc"
    assert [(call[0], call[1]) for call in transport.calls] == [
        ("1abc", "pdbtm_json"),
        ("1abc", "transformed_pdb"),
    ]
    assert tuple(payload.role for payload in candidate.payloads) == PAIR_ROLES
    assert candidate.orientation_result.status == "imported"
    assert candidate.validation.mapping_method == "identity"
    assert candidate.validation.runtime_identity_rmsd == 0
    assert candidate.validation.runtime_identity_maximum_residual == 0
    assert candidate.validation.current_fingerprint == candidate.validation.transformed_fingerprint
    assert candidate.provider_versions.resource_version == "1017"
    assert candidate.provider_versions.software_version == "3.2.134"


def test_pair_validation_rejects_companion_identifier_mismatch():
    wrong = PDB_BYTES.replace(b"1ABC\n", b"2DEF\n", 1)
    with pytest.raises(Stage4BError) as caught:
        validate_pdbtm_pair("1abc", JSON_BYTES, wrong)
    assert caught.value.code is Stage4BErrorCode.COMPANION_ID_MISMATCH


def test_pair_validation_rejects_malformed_matrix():
    malformed = JSON_BYTES.replace(b'"rowx"', b'"wrong"', 1)
    with pytest.raises(Stage4BError) as caught:
        validate_pdbtm_pair("1abc", malformed, PDB_BYTES)
    assert caught.value.code is Stage4BErrorCode.PAIR_VALIDATION_FAILED


def test_pair_validation_rejects_unreviewed_precision():
    unsupported = JSON_BYTES.replace(b"-1.00000000", b"-1.000000", 1)
    with pytest.raises(Stage4BError) as caught:
        validate_pdbtm_pair("1abc", unsupported, PDB_BYTES)
    assert caught.value.code is Stage4BErrorCode.PAIR_VALIDATION_FAILED


def test_provider_rejects_transport_role_or_digest_evidence_mismatch():
    class BadTransport(FakeTransport):
        def fetch(self, record_id, role, **kwargs):
            payload = super().fetch(record_id, role, **kwargs)
            if role == "pdbtm_json":
                return FakePayload("transformed_pdb", payload.body)
            return payload

    with pytest.raises(Stage4BError) as caught:
        PdbtmProviderClient(BadTransport()).fetch("1abc")
    assert caught.value.code is Stage4BErrorCode.PROVIDER_RESPONSE_INVALID


def test_provider_checks_cancellation_before_network_and_between_roles():
    class Cancellation:
        is_cancelled = True

    transport = FakeTransport()
    with pytest.raises(Stage4BError) as caught:
        PdbtmProviderClient(transport).fetch("1abc", cancellation=Cancellation())
    assert caught.value.code is Stage4BErrorCode.RETRIEVAL_CANCELLED
    assert transport.calls == []

    class CancellingTransport(FakeTransport):
        def fetch(self, record_id, role, *, cancellation=None, pair_deadline=None):
            result = super().fetch(
                record_id, role, cancellation=cancellation, pair_deadline=pair_deadline
            )
            cancellation.is_cancelled = True
            return result

    cancellation = type("Cancellation", (), {"is_cancelled": False})()
    transport = CancellingTransport()
    with pytest.raises(Stage4BError) as caught:
        PdbtmProviderClient(transport).fetch("1abc", cancellation=cancellation)
    assert caught.value.code is Stage4BErrorCode.RETRIEVAL_CANCELLED
    assert len(transport.calls) == 1


def test_provider_enforces_pair_deadline_without_retry():
    moments = iter((0.0, 0.0, 0.0, 61.0))
    transport = FakeTransport()
    with pytest.raises(Stage4BError) as caught:
        PdbtmProviderClient(transport, monotonic=lambda: next(moments)).fetch("1abc")
    assert caught.value.code is Stage4BErrorCode.NETWORK_TIMEOUT
    assert len(transport.calls) == 2


def test_provider_enforces_pair_deadline_after_scientific_validation():
    moments = iter((0.0, 0.0, 0.0, 0.0, 61.0))
    transport = FakeTransport()
    with pytest.raises(Stage4BError) as caught:
        PdbtmProviderClient(transport, monotonic=lambda: next(moments)).fetch("1abc")
    assert caught.value.code is Stage4BErrorCode.NETWORK_TIMEOUT
    assert len(transport.calls) == 2


def test_provider_rejects_pair_size_evidence_without_parsing():
    huge = b"x" * (5 * 1024 * 1024 + 1)
    transport = FakeTransport({"pdbtm_json": huge, "transformed_pdb": huge})
    with pytest.raises(Stage4BError) as caught:
        PdbtmProviderClient(transport).fetch("1abc")
    assert caught.value.code is Stage4BErrorCode.RESPONSE_TOO_LARGE
    assert len(transport.calls) == 2
