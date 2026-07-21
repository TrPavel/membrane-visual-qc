"""Pure, immutable PDBTM cache-acquisition provenance for report schema 1.4.

This module performs no network I/O, no cache I/O, and never opens or
discovers a cache path. It only converts an already-validated Stage 4B1
:class:`~membrane_vqc.pdbtm_cache.CachedSnapshot` into a minimal, report-facing
provenance model: pair/snapshot identity, acquisition evidence for both
payload roles, and the pair's own internal self-consistency result.

Scientific-truthfulness boundary: ``validate_pdbtm_pair`` (the validator
behind every ``CachedSnapshot``) only ever checks that the acquired JSON and
transformed-PDB payloads are mutually consistent with each other; it never
sees a loaded PyMOL object's coordinates. This module therefore never claims
that a cached pair matches, or was tested against, any currently loaded
structure -- see :class:`ObjectApplicability`, which is always
"not established" here. Establishing real object applicability requires the
existing offline adapter path (Stage 4A2) with a live ``StructureContext``,
which is out of scope for this pure conversion.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from .errors import OrientationError
from .pdbtm_cache import CachedSnapshot
from .pdbtm_cache_contract import (
    CACHE_CONTRACT,
    PAYLOAD_ROLES,
    PROVIDER,
    TRANSPORT_VERIFICATION,
    PairCore,
    PayloadIdentity,
    compute_pair_id,
)

MODEL_VERSION = "1"
PROVIDER_KIND = "pdbtm_api_v1"
PROVIDER_DISPLAY_NAME = "PDBTM"
ACQUISITION_MODE = "direct_https_provider_fetch"
ADAPTER_NAME = "pdbtm_api_v1_offline"
ADAPTER_VERSION = "1"
EXPECTED_MAPPING_METHOD = "identity"
EXPECTED_COORDINATE_FRAME = "pdbtm_transformed_companion"

ConsumptionMode = Literal["active_cache_read", "snapshot_cache_read"]
_CONSUMPTION_MODES = ("active_cache_read", "snapshot_cache_read")


class ProvenanceConversionError(OrientationError):
    """Raised when a CachedSnapshot cannot be safely converted to report provenance."""


@dataclass(frozen=True, slots=True)
class AcquisitionPayloadProvenance:
    """Report-facing acquisition evidence for one payload role. Bytes are never retained."""

    role: str
    byte_size: int
    sha256: str
    media_type: str
    charset: str | None
    requested_url: str
    final_url: str
    requested_at: str
    completed_at: str
    etag: str | None
    last_modified: str | None
    transport_verification: str

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "byte_size": self.byte_size,
            "sha256": self.sha256,
            "content_type": {"media_type": self.media_type, "charset": self.charset},
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "requested_at": self.requested_at,
            "completed_at": self.completed_at,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "transport_verification": self.transport_verification,
        }


@dataclass(frozen=True, slots=True)
class PairSelfConsistency:
    """Evidence that the two acquired payloads validated against each other.

    This is a self-consistency result only: the payloads were compared
    against each other by the offline adapter, not against any loaded
    structure. See :class:`ObjectApplicability`.
    """

    adapter_name: str
    adapter_version: str
    method: str
    coordinate_frame: str
    rmsd: float
    maximum_residual: float
    fingerprint_match: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "method": self.method,
            "coordinate_frame": self.coordinate_frame,
            "rmsd": self.rmsd,
            "maximum_residual": self.maximum_residual,
            "fingerprint_match": self.fingerprint_match,
        }


@dataclass(frozen=True, slots=True)
class ObjectApplicability:
    """Explicit, always-truthful statement of what this provenance does NOT establish."""

    established: bool
    scope: str
    statement: str

    def as_dict(self) -> dict[str, object]:
        return {
            "established": self.established,
            "scope": self.scope,
            "statement": self.statement,
        }


_NOT_EVALUATED_APPLICABILITY = ObjectApplicability(
    established=False,
    scope="not_evaluated",
    statement=(
        "This provenance confirms the acquired PDBTM JSON and transformed-PDB payload pair "
        "is internally self-consistent and was validated and cached. It does not evaluate, "
        "and must not be read as confirming, that any currently loaded structure matches "
        "this pair."
    ),
)


@dataclass(frozen=True, slots=True)
class PdbtmAcquisitionProvenance:
    """Minimal, immutable, report-facing PDBTM cache-acquisition provenance (schema 1.4)."""

    model_version: str
    provider_kind: str
    provider_name: str
    provider_contract: str
    canonical_record_id: str
    acquisition_mode: str
    consumption_mode: str
    pair_id: str
    snapshot_id: str
    cache_generation: int | None
    resource_version: str
    software_version: str
    validated_at: str
    payloads: tuple[AcquisitionPayloadProvenance, AcquisitionPayloadProvenance]
    pair_self_consistency: PairSelfConsistency
    object_applicability: ObjectApplicability

    def as_dict(self) -> dict[str, object]:
        return {
            "model_version": self.model_version,
            "provider_kind": self.provider_kind,
            "provider_name": self.provider_name,
            "provider_contract": self.provider_contract,
            "canonical_record_id": self.canonical_record_id,
            "acquisition_mode": self.acquisition_mode,
            "consumption_mode": self.consumption_mode,
            "pair_id": self.pair_id,
            "snapshot_id": self.snapshot_id,
            "cache_generation": self.cache_generation,
            "provider_versions": {
                "resource_version": self.resource_version,
                "software_version": self.software_version,
            },
            "validated_at": self.validated_at,
            "payloads": [item.as_dict() for item in self.payloads],
            "pair_self_consistency": self.pair_self_consistency.as_dict(),
            "object_applicability": self.object_applicability.as_dict(),
        }


def _fail(message: str) -> None:
    raise ProvenanceConversionError(message)


def build_pdbtm_acquisition_provenance(
    snapshot: CachedSnapshot,
    *,
    consumption_mode: ConsumptionMode,
    cache_generation: int | None = None,
) -> PdbtmAcquisitionProvenance:
    """Convert an already-validated Stage 4B1 cache read result to report provenance.

    ``snapshot`` must be a :class:`CachedSnapshot` returned by
    :meth:`PdbtmCacheRepository.read_active` or ``.read_snapshot`` with the
    default semantic validator (so ``semantic_result`` is populated). This
    function performs no I/O of any kind; every fact is independently
    re-derived from ``snapshot`` and cross-checked for internal consistency
    before being trusted -- an untrusted or hand-constructed candidate is
    rejected, not passed through.
    """

    if consumption_mode not in _CONSUMPTION_MODES:
        _fail(f"Unsupported consumption mode: {consumption_mode!r}")
    if cache_generation is not None and (
        isinstance(cache_generation, bool) or cache_generation < 0
    ):
        _fail("cache_generation must be a non-negative integer or None.")

    core = snapshot.snapshot_core
    if core.cache_contract != CACHE_CONTRACT or core.provider != PROVIDER:
        _fail("Cache snapshot does not use the reviewed PDBTM cache contract.")

    roles = tuple(payload.role for payload in core.payloads)
    if roles != PAYLOAD_ROLES:
        _fail(f"Payload roles must be exactly {PAYLOAD_ROLES!r} in order; got {roles!r}.")

    raw_bodies = snapshot.payloads
    if len(raw_bodies) != 2:
        _fail("Snapshot must contain exactly two raw payload bodies.")
    for identity, body in zip(core.payloads, raw_bodies, strict=True):
        if not isinstance(body, bytes):
            _fail(f"{identity.role} payload body must be bytes.")
        if len(body) != identity.byte_size:
            _fail(f"{identity.role} byte size does not match its acquisition evidence.")
        if hashlib.sha256(body).hexdigest() != identity.sha256:
            _fail(f"{identity.role} SHA-256 does not match its acquisition evidence.")

    identities = tuple(
        PayloadIdentity(payload.role, payload.sha256, payload.byte_size)
        for payload in core.payloads
    )
    recomputed_pair_id = compute_pair_id(
        PairCore(core.canonical_record_id, identities)  # type: ignore[arg-type]
    )
    if recomputed_pair_id != core.pair_id:
        _fail("Recomputed pair ID does not match the snapshot's recorded pair ID.")

    semantic = snapshot.semantic_result
    if not (isinstance(semantic, tuple) and len(semantic) == 3):
        _fail(
            "Snapshot has no semantic validation result; read it with the default "
            "validate_pdbtm_pair validator before converting."
        )
    orientation_result, validator_versions, summary = semantic

    if getattr(orientation_result, "status", None) != "imported":
        _fail("Snapshot's pair-validation result was not an accepted 'imported' status.")
    source = getattr(orientation_result, "source", None)
    if source is None or source.record_id != core.canonical_record_id:
        _fail("Pair-validation source record ID does not match the snapshot's record ID.")

    if (
        validator_versions.resource_version != core.provider_versions.resource_version
        or validator_versions.software_version != core.provider_versions.software_version
    ):
        _fail("Provider version evidence contradicts the snapshot's recorded provider versions.")

    if summary.adapter_name != ADAPTER_NAME or summary.adapter_version != ADAPTER_VERSION:
        _fail("Unexpected adapter identity in pair-validation summary.")
    if summary.mapping_method != EXPECTED_MAPPING_METHOD:
        _fail("Pair validation did not use the expected identity-frame method.")
    if summary.current_fingerprint != summary.transformed_fingerprint:
        _fail("Pair-validation fingerprints do not agree.")

    evidence = getattr(orientation_result, "evidence", None)
    coordinate_frame = getattr(getattr(evidence, "mapping", None), "current_frame", None)
    if coordinate_frame != EXPECTED_COORDINATE_FRAME:
        _fail("Pair validation did not resolve in the expected coordinate frame.")

    payload_provenance: list[AcquisitionPayloadProvenance] = []
    for identity in core.payloads:
        if identity.transport_verification != TRANSPORT_VERIFICATION:
            _fail(f"{identity.role} does not carry verified direct-HTTPS transport evidence.")
        if identity.status != 200:
            _fail(f"{identity.role} acquisition status was not 200.")
        if identity.final_url != identity.requested_url:
            _fail(f"{identity.role} evidence implies a redirect, which is never permitted.")
        payload_provenance.append(
            AcquisitionPayloadProvenance(
                role=identity.role,
                byte_size=identity.byte_size,
                sha256=identity.sha256,
                media_type=identity.headers.content_type.media_type,
                charset=identity.headers.content_type.charset,
                requested_url=identity.requested_url,
                final_url=identity.final_url,
                requested_at=identity.requested_at,
                completed_at=identity.completed_at,
                etag=identity.headers.etag,
                last_modified=identity.headers.last_modified,
                transport_verification=identity.transport_verification,
            )
        )

    return PdbtmAcquisitionProvenance(
        model_version=MODEL_VERSION,
        provider_kind=PROVIDER_KIND,
        provider_name=PROVIDER_DISPLAY_NAME,
        provider_contract=core.cache_contract,
        canonical_record_id=core.canonical_record_id,
        acquisition_mode=ACQUISITION_MODE,
        consumption_mode=consumption_mode,
        pair_id=core.pair_id,
        snapshot_id=snapshot.snapshot_id,
        cache_generation=cache_generation,
        resource_version=core.provider_versions.resource_version,
        software_version=core.provider_versions.software_version,
        validated_at=core.validated_at,
        payloads=(payload_provenance[0], payload_provenance[1]),
        pair_self_consistency=PairSelfConsistency(
            adapter_name=summary.adapter_name,
            adapter_version=summary.adapter_version,
            method=summary.mapping_method,
            coordinate_frame=coordinate_frame,
            rmsd=summary.runtime_identity_rmsd,
            maximum_residual=summary.runtime_identity_maximum_residual,
            fingerprint_match=True,
        ),
        object_applicability=_NOT_EVALUATED_APPLICABILITY,
    )
