from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from membrane_vqc.pdbtm_cache import CacheRepository
from membrane_vqc.pdbtm_report_provenance import (
    ProvenanceConversionError,
    build_pdbtm_acquisition_provenance,
)


@dataclass(frozen=True)
class FakeEvidence:
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
class FakePayload:
    role: str
    body: bytes
    evidence: FakeEvidence


@dataclass(frozen=True)
class FakeVersions:
    resource_version: str = "1017"
    software_version: str = "3.2.134"


@dataclass(frozen=True)
class FakeCandidate:
    canonical_record_id: str
    payloads: tuple[FakePayload, FakePayload]
    provider_versions: FakeVersions = FakeVersions()


_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "data" / "synthetic"
_JSON_TEMPLATE = (_FIXTURE_ROOT / "pdbtm_api_v1_test.json").read_bytes()
_PDB_TEMPLATE = (_FIXTURE_ROOT / "pdbtm_transformed_test.pdb").read_bytes()
_RECORD_ID = "9zzz"


def _valid_pdbtm_bytes(record_id: str = _RECORD_ID) -> tuple[bytes, bytes]:
    json_bytes = _JSON_TEMPLATE.replace(b'"pdb_id":"test"', f'"pdb_id":"{record_id}"'.encode(), 1)
    pdb_bytes = _PDB_TEMPLATE.replace(b"TEST\n", (record_id.upper() + "\n").encode(), 1)
    return json_bytes, pdb_bytes


def _payload(record_id: str, role: str, body: bytes, second: int, **overrides) -> FakePayload:
    suffix = "json" if role == "pdbtm_json" else "trpdb"
    url = f"https://pdbtm.unitmp.org/api/v1/entry/{record_id}.{suffix}"
    content_type = "application/json" if role == "pdbtm_json" else "text/plain"
    charset = None if role == "pdbtm_json" else "utf-8"
    digest = hashlib.sha256(body).hexdigest()
    evidence = FakeEvidence(
        overrides.pop("requested_url", url),
        overrides.pop("final_url", url),
        overrides.pop("status", 200),
        overrides.pop("content_type", content_type),
        overrides.pop("charset", charset),
        None,
        overrides.pop("etag", None),
        overrides.pop("last_modified", None),
        f"2026-07-21T00:00:0{second}.000000Z",
        f"2026-07-21T00:00:0{second + 1}.000000Z",
        overrides.pop("byte_size", len(body)),
        overrides.pop("sha256", digest),
        overrides.pop("tls_verified", True),
    )
    return FakePayload(role, body, evidence)


def _candidate(record_id: str = _RECORD_ID) -> FakeCandidate:
    json_bytes, pdb_bytes = _valid_pdbtm_bytes(record_id)
    return FakeCandidate(
        record_id,
        (
            _payload(record_id, "pdbtm_json", json_bytes, 0),
            _payload(record_id, "transformed_pdb", pdb_bytes, 2),
        ),
    )


def _repository(tmp_path: Path) -> CacheRepository:
    return CacheRepository(
        tmp_path / "cache-v1",
        utc_now=lambda: datetime(2026, 7, 21, 0, 0, 4, tzinfo=timezone.utc),
    )


def _commit_and_read_active(tmp_path: Path, record_id: str = _RECORD_ID):
    repository = _repository(tmp_path)
    generation = repository.capture_record_generation(record_id)
    repository.commit_validated_pair(_candidate(record_id), expected_record_generation=generation)
    return repository, repository.read_active(record_id)


def test_valid_active_cache_read_converts_successfully(tmp_path):
    repository, snapshot = _commit_and_read_active(tmp_path)

    provenance = build_pdbtm_acquisition_provenance(
        snapshot, consumption_mode="active_cache_read", cache_generation=1
    )

    assert provenance.canonical_record_id == _RECORD_ID
    assert provenance.consumption_mode == "active_cache_read"
    assert provenance.cache_generation == 1
    assert provenance.pair_id == snapshot.snapshot_core.pair_id
    assert provenance.snapshot_id == snapshot.snapshot_id
    assert [item.role for item in provenance.payloads] == ["pdbtm_json", "transformed_pdb"]
    assert provenance.pair_self_consistency.method == "identity"
    assert provenance.object_applicability.established is False
    assert provenance.object_applicability.scope == "not_evaluated"


def test_valid_snapshot_cache_read_converts_successfully(tmp_path):
    repository, active = _commit_and_read_active(tmp_path)
    snapshot = repository.read_snapshot(_RECORD_ID, active.snapshot_id)

    provenance = build_pdbtm_acquisition_provenance(
        snapshot, consumption_mode="snapshot_cache_read"
    )

    assert provenance.consumption_mode == "snapshot_cache_read"
    assert provenance.cache_generation is None


def test_no_raw_bytes_or_cache_path_reach_the_provenance_model(tmp_path):
    _, snapshot = _commit_and_read_active(tmp_path)
    provenance = build_pdbtm_acquisition_provenance(snapshot, consumption_mode="active_cache_read")

    encoded = repr(provenance.as_dict())
    for body in snapshot.payloads:
        assert body not in encoded.encode("utf-8", errors="ignore")
    assert str(tmp_path) not in encoded


def test_unsupported_consumption_mode_rejected(tmp_path):
    _, snapshot = _commit_and_read_active(tmp_path)
    with pytest.raises(ProvenanceConversionError, match="consumption mode"):
        build_pdbtm_acquisition_provenance(snapshot, consumption_mode="fetched_live")  # type: ignore[arg-type]


def test_missing_semantic_result_rejected(tmp_path):
    _, snapshot = _commit_and_read_active(tmp_path)
    bare = replace(snapshot, semantic_result=None)
    with pytest.raises(ProvenanceConversionError, match="semantic validation"):
        build_pdbtm_acquisition_provenance(bare, consumption_mode="active_cache_read")


def test_tampered_payload_byte_size_rejected(tmp_path):
    """pdbtm_cache_contract.SnapshotCore/AcquisitionPayload already re-validate on every
    dataclasses.replace(), so the only place a byte_size/sha256 contradiction can still be
    smuggled through is the raw-bytes side of CachedSnapshot (a plain tuple[bytes, bytes]
    that the contract layer never cross-checks against snapshot_core) -- exactly the
    untrusted boundary this conversion function exists to close."""

    _, snapshot = _commit_and_read_active(tmp_path)
    tampered = replace(snapshot, payloads=(snapshot.payloads[0] + b"corrupt", snapshot.payloads[1]))
    with pytest.raises(ProvenanceConversionError, match="byte size"):
        build_pdbtm_acquisition_provenance(tampered, consumption_mode="active_cache_read")


def test_tampered_payload_sha256_rejected(tmp_path):
    _, snapshot = _commit_and_read_active(tmp_path)
    original = snapshot.payloads[0]
    mutated = bytes([original[0] ^ 0xFF]) + original[1:]  # same length, different content
    tampered = replace(snapshot, payloads=(mutated, snapshot.payloads[1]))
    with pytest.raises(ProvenanceConversionError, match="SHA-256"):
        build_pdbtm_acquisition_provenance(tampered, consumption_mode="active_cache_read")


def test_record_id_contradiction_rejected(tmp_path):
    """canonical_record_id lives on snapshot_core (contract-protected, cross-checked against
    pair_id at construction) while the pair-validation source record_id lives independently
    inside semantic_result -- the contract layer never cross-checks those two against each
    other, so a genuine contradiction between them can only be caught by this conversion."""

    _, snapshot = _commit_and_read_active(tmp_path)
    orientation_result, versions, summary = snapshot.semantic_result
    tampered_source = replace(orientation_result.source, record_id="9zzy")
    tampered_evidence = replace(orientation_result.evidence, source=tampered_source)
    tampered_result = replace(
        orientation_result, source=tampered_source, evidence=tampered_evidence
    )
    tampered = replace(snapshot, semantic_result=(tampered_result, versions, summary))
    with pytest.raises(ProvenanceConversionError, match="record ID"):
        build_pdbtm_acquisition_provenance(tampered, consumption_mode="active_cache_read")


def test_provider_version_contradiction_rejected(tmp_path):
    _, snapshot = _commit_and_read_active(tmp_path)
    tampered_core = replace(
        snapshot.snapshot_core,
        provider_versions=replace(
            snapshot.snapshot_core.provider_versions, resource_version="9999"
        ),
    )
    tampered = replace(snapshot, snapshot_core=tampered_core)
    with pytest.raises(ProvenanceConversionError, match="[Pp]rovider version"):
        build_pdbtm_acquisition_provenance(tampered, consumption_mode="active_cache_read")


def test_pair_id_contradiction_is_already_impossible_via_the_validated_contract(tmp_path):
    """SnapshotCore.__post_init__ already cross-validates pair_id against its own payload
    identities on every construction, so a self-inconsistent pair_id can never reach the
    conversion function -- build_pdbtm_acquisition_provenance's own pair_id recomputation
    is redundant defense in depth for this specific field, not the only guard."""

    _, snapshot = _commit_and_read_active(tmp_path)
    from membrane_vqc.pdbtm_cache_contract import CacheContractError

    with pytest.raises(CacheContractError, match="pair_id"):
        replace(snapshot.snapshot_core, pair_id="1" * 64)


def test_wrong_role_order_is_already_impossible_via_the_validated_contract(tmp_path):
    """SnapshotCore itself refuses a non-canonical payload order (pdbtm_cache_contract's
    own __post_init__ re-validates on every dataclasses.replace()), so a CachedSnapshot
    with reversed roles can never reach the conversion function in the first place --
    this is enforced one layer below build_pdbtm_acquisition_provenance, which still
    carries its own redundant role-order check as defense in depth."""

    _, snapshot = _commit_and_read_active(tmp_path)
    from membrane_vqc.pdbtm_cache_contract import CacheContractError

    with pytest.raises(CacheContractError):
        replace(
            snapshot.snapshot_core,
            payloads=(snapshot.snapshot_core.payloads[1], snapshot.snapshot_core.payloads[0]),
        )


def test_unverified_transport_evidence_is_already_impossible_via_the_validated_contract(tmp_path):
    """AcquisitionPayload.__post_init__ already requires the exact literal
    'direct_https_tls_verified' for transport_verification, so unvalidated/forged TLS
    evidence can never reach the conversion function either."""

    _, snapshot = _commit_and_read_active(tmp_path)
    from membrane_vqc.pdbtm_cache_contract import CacheContractError

    with pytest.raises(CacheContractError, match="transport_verification"):
        replace(snapshot.snapshot_core.payloads[0], transport_verification="unverified")


def test_negative_cache_generation_rejected(tmp_path):
    _, snapshot = _commit_and_read_active(tmp_path)
    with pytest.raises(ProvenanceConversionError, match="cache_generation"):
        build_pdbtm_acquisition_provenance(
            snapshot, consumption_mode="active_cache_read", cache_generation=-1
        )


def test_repeated_conversion_of_the_same_snapshot_is_deterministic(tmp_path):
    _, snapshot = _commit_and_read_active(tmp_path)
    first = build_pdbtm_acquisition_provenance(
        snapshot, consumption_mode="active_cache_read", cache_generation=1
    )
    second = build_pdbtm_acquisition_provenance(
        snapshot, consumption_mode="active_cache_read", cache_generation=1
    )
    assert first.as_dict() == second.as_dict()


def test_conversion_performs_no_network_calls(tmp_path, monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("network access attempted during provenance conversion")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    _, snapshot = _commit_and_read_active(tmp_path)
    build_pdbtm_acquisition_provenance(snapshot, consumption_mode="active_cache_read")
