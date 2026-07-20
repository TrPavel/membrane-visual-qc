"""Pure-Python PDBTM provider orchestration and pair validation.

This module deliberately has no PyMOL, Qt, cache, or report dependency.  The
provider bytes are accepted only after the existing offline adapter proves
that the transformed companion is an identity-frame match for itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
import time
from typing import Protocol

from .orientation_sources import OrientationImportResult, StructureContext
from .pdbtm_adapter import import_pdbtm_orientation
from .pdbtm_errors import Stage4BError, Stage4BErrorCode

PDBTM_JSON_ROLE = "pdbtm_json"
TRANSFORMED_PDB_ROLE = "transformed_pdb"
PAIR_ROLES = (PDBTM_JSON_ROLE, TRANSFORMED_PDB_ROLE)
PAIR_MAX_BYTES = 10 * 1024 * 1024
PAIR_DEADLINE_SECONDS = 60.0
_RECORD_ID = re.compile(r"^[0-9][A-Za-z0-9]{3}$", flags=re.ASCII)
_IDENTITY4 = tuple(tuple(1.0 if row == column else 0.0 for column in range(4)) for row in range(4))


class CancellationView(Protocol):
    """Minimum cancellation surface shared with the transport."""

    @property
    def is_cancelled(self) -> bool: ...


class RetrievedPayload(Protocol):
    """Transport result consumed by the provider layer."""

    role: str
    body: bytes
    byte_size: int
    sha256: str


class ProviderTransport(Protocol):
    """Narrow transport boundary used by :class:`PdbtmProviderClient`."""

    def fetch(
        self,
        record_id: str,
        role: str,
        *,
        cancellation: CancellationView | None = None,
        pair_deadline: float | None = None,
    ) -> RetrievedPayload: ...


@dataclass(frozen=True, slots=True)
class ProviderVersions:
    resource_version: str
    software_version: str


@dataclass(frozen=True, slots=True)
class PairValidationSummary:
    adapter_name: str
    adapter_version: str
    mapping_method: str
    runtime_identity_rmsd: float
    runtime_identity_maximum_residual: float
    current_fingerprint: str
    transformed_fingerprint: str


@dataclass(frozen=True, slots=True)
class ValidatedPdbtmPair:
    """Validated transient candidate; cache publication is a separate step."""

    canonical_record_id: str
    payloads: tuple[RetrievedPayload, RetrievedPayload]
    orientation_result: OrientationImportResult
    provider_versions: ProviderVersions
    validation: PairValidationSummary

    @property
    def json_payload(self) -> RetrievedPayload:
        return self.payloads[0]

    @property
    def transformed_payload(self) -> RetrievedPayload:
        return self.payloads[1]


def canonicalize_record_id(value: object) -> str:
    """Validate the exact legacy PDB identifier grammar and lowercase it."""

    if not isinstance(value, str) or _RECORD_ID.fullmatch(value) is None:
        _fail(
            Stage4BErrorCode.INVALID_RECORD_ID,
            "Record ID must be exactly four ASCII PDB identifier characters.",
        )
    return value.lower()


def _fail(
    code: Stage4BErrorCode,
    message: str,
    *,
    retryable: bool = False,
    existing_cache_usable: bool = False,
) -> None:
    raise Stage4BError(
        code=code,
        user_message=message,
        retryable=retryable,
        existing_cache_usable=existing_cache_usable,
    )


def _cancelled(cancellation: CancellationView | None) -> bool:
    if cancellation is None:
        return False
    value = getattr(cancellation, "is_cancelled", False)
    return bool(value() if callable(value) else value)


def _require_not_cancelled(cancellation: CancellationView | None) -> None:
    if _cancelled(cancellation):
        _fail(
            Stage4BErrorCode.RETRIEVAL_CANCELLED,
            "PDBTM retrieval was cancelled.",
            existing_cache_usable=True,
        )


def _payload_body(payload: RetrievedPayload, expected_role: str) -> bytes:
    if getattr(payload, "role", None) != expected_role:
        _fail(
            Stage4BErrorCode.PROVIDER_RESPONSE_INVALID,
            "PDBTM response roles did not match the requested provider pair.",
            existing_cache_usable=True,
        )
    body = getattr(payload, "body", None)
    if not isinstance(body, bytes):
        _fail(
            Stage4BErrorCode.PROVIDER_RESPONSE_INVALID,
            "PDBTM returned an invalid response body.",
            existing_cache_usable=True,
        )
    if getattr(payload, "byte_size", None) != len(body):
        _fail(
            Stage4BErrorCode.PROVIDER_RESPONSE_INVALID,
            "PDBTM response size evidence did not match the response body.",
            existing_cache_usable=True,
        )
    if getattr(payload, "sha256", None) != hashlib.sha256(body).hexdigest():
        _fail(
            Stage4BErrorCode.PROVIDER_RESPONSE_INVALID,
            "PDBTM response digest evidence did not match the response body.",
            existing_cache_usable=True,
        )
    return body


def _adapter_failure(result: OrientationImportResult) -> None:
    codes = {message.code for message in result.messages}
    if codes & {"COMPANION_ID_MISMATCH", "STRUCTURE_ID_MISMATCH"}:
        _fail(
            Stage4BErrorCode.COMPANION_ID_MISMATCH,
            "PDBTM JSON and transformed companion identifiers do not agree.",
            existing_cache_usable=True,
        )
    if codes & {
        "COMPANION_COUNT",
        "DUPLICATE_JSON_KEY",
        "INVALID_ENCODING",
        "INVALID_JSON",
        "NONFINITE_JSON_NUMBER",
        "NUL_BYTE",
        "UNEXPECTED_PAYLOAD_ROLE",
    }:
        _fail(
            Stage4BErrorCode.PROVIDER_RESPONSE_INVALID,
            "PDBTM returned a malformed or unexpected provider response.",
            existing_cache_usable=True,
        )
    _fail(
        Stage4BErrorCode.PAIR_VALIDATION_FAILED,
        "PDBTM JSON and transformed companion failed scientific pair validation.",
        existing_cache_usable=True,
    )


def _as_float(mapping: object, key: str) -> float:
    if not hasattr(mapping, "get"):
        _fail(
            Stage4BErrorCode.PAIR_VALIDATION_FAILED,
            "PDBTM identity validation evidence is incomplete.",
            existing_cache_usable=True,
        )
    value = mapping.get(key)  # type: ignore[union-attr]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(
            Stage4BErrorCode.PAIR_VALIDATION_FAILED,
            "PDBTM identity validation evidence is incomplete.",
            existing_cache_usable=True,
        )
    number = float(value)
    if not math.isfinite(number):
        _fail(
            Stage4BErrorCode.PAIR_VALIDATION_FAILED,
            "PDBTM identity validation evidence is invalid.",
            existing_cache_usable=True,
        )
    return number


def validate_pdbtm_pair(
    record_id: str,
    pdbtm_json: bytes,
    transformed_pdb: bytes,
) -> tuple[OrientationImportResult, ProviderVersions, PairValidationSummary]:
    """Validate exact provider bytes in the transformed companion identity frame."""

    canonical_id = canonicalize_record_id(record_id)
    if not isinstance(pdbtm_json, bytes) or not isinstance(transformed_pdb, bytes):
        _fail(
            Stage4BErrorCode.PROVIDER_RESPONSE_INVALID,
            "PDBTM provider payloads must be exact bytes.",
        )
    context = StructureContext(
        pdb_payload=transformed_pdb,
        structure_id=canonical_id,
        model_id=1,
        biological_assembly=None,
        coordinate_frame="pdbtm_transformed_companion",
    )
    result = import_pdbtm_orientation(pdbtm_json, transformed_pdb, context)
    if result.status != "imported" or result.evidence is None or result.source is None:
        _adapter_failure(result)

    evidence = result.evidence
    source = result.source
    if source.record_id != canonical_id or evidence.source != source:
        _fail(
            Stage4BErrorCode.COMPANION_ID_MISMATCH,
            "PDBTM provider record identity did not match the requested record.",
            existing_cache_usable=True,
        )
    digests = source.raw_payloads
    if [item.role for item in digests] != [PDBTM_JSON_ROLE, TRANSFORMED_PDB_ROLE]:
        _fail(
            Stage4BErrorCode.PROVIDER_RESPONSE_INVALID,
            "PDBTM provider evidence did not contain the exact required roles.",
            existing_cache_usable=True,
        )
    expected = {
        PDBTM_JSON_ROLE: hashlib.sha256(pdbtm_json).hexdigest(),
        TRANSFORMED_PDB_ROLE: hashlib.sha256(transformed_pdb).hexdigest(),
    }
    if any(item.sha256 != expected[item.role] for item in digests):
        _fail(
            Stage4BErrorCode.PROVIDER_RESPONSE_INVALID,
            "PDBTM adapter evidence did not bind the exact provider bytes.",
            existing_cache_usable=True,
        )

    mapping = evidence.mapping
    if (
        evidence.adapter_name != "pdbtm_api_v1_offline"
        or mapping.method != "identity"
        or mapping.current_frame != "pdbtm_transformed_companion"
        or mapping.source_to_current != _IDENTITY4
    ):
        _fail(
            Stage4BErrorCode.PAIR_VALIDATION_FAILED,
            "PDBTM pair did not validate in the transformed companion identity frame.",
            existing_cache_usable=True,
        )
    runtime_identity = mapping.metrics.get("runtime_identity")
    rmsd = _as_float(runtime_identity, "rmsd")
    maximum = _as_float(runtime_identity, "maximum_residual")
    thresholds = mapping.thresholds.get("runtime_identity_match_limit")
    rmsd_limit = _as_float(thresholds, "rmsd")
    maximum_limit = _as_float(thresholds, "maximum_residual")
    if rmsd > rmsd_limit or maximum > maximum_limit:
        _fail(
            Stage4BErrorCode.PAIR_VALIDATION_FAILED,
            "PDBTM identity residuals exceeded the reviewed runtime limits.",
            existing_cache_usable=True,
        )
    fingerprints = mapping.fingerprints
    current_fingerprint = fingerprints.get("current")
    transformed_fingerprint = fingerprints.get("transformed_reference")
    if not isinstance(current_fingerprint, str) or current_fingerprint != transformed_fingerprint:
        _fail(
            Stage4BErrorCode.PAIR_VALIDATION_FAILED,
            "PDBTM identity coordinate fingerprints did not agree.",
            existing_cache_usable=True,
        )
    if source.resource_version is None or source.software_version is None:
        _fail(
            Stage4BErrorCode.PROVIDER_RESPONSE_INVALID,
            "PDBTM provider version provenance is incomplete.",
            existing_cache_usable=True,
        )
    return (
        result,
        ProviderVersions(source.resource_version, source.software_version),
        PairValidationSummary(
            evidence.adapter_name,
            evidence.adapter_version,
            mapping.method,
            rmsd,
            maximum,
            current_fingerprint,
            transformed_fingerprint,
        ),
    )


class PdbtmProviderClient:
    """Retrieve and validate one exact JSON/transformed-PDB provider pair."""

    def __init__(
        self,
        transport: ProviderTransport,
        *,
        monotonic=time.monotonic,
        pair_deadline_seconds: float = PAIR_DEADLINE_SECONDS,
    ) -> None:
        if pair_deadline_seconds <= 0:
            raise ValueError("pair_deadline_seconds must be positive")
        self._transport = transport
        self._monotonic = monotonic
        self._pair_deadline_seconds = pair_deadline_seconds

    def fetch(
        self,
        record_id: str,
        *,
        cancellation: CancellationView | None = None,
    ) -> ValidatedPdbtmPair:
        canonical_id = canonicalize_record_id(record_id)
        _require_not_cancelled(cancellation)
        deadline = self._monotonic() + self._pair_deadline_seconds
        payloads: list[RetrievedPayload] = []
        byte_total = 0
        for role in PAIR_ROLES:
            _require_not_cancelled(cancellation)
            if self._monotonic() >= deadline:
                _fail(
                    Stage4BErrorCode.NETWORK_TIMEOUT,
                    "PDBTM pair retrieval exceeded its total deadline.",
                    retryable=True,
                    existing_cache_usable=True,
                )
            payload = self._transport.fetch(
                canonical_id,
                role,
                cancellation=cancellation,
                pair_deadline=deadline,
            )
            body = _payload_body(payload, role)
            byte_total += len(body)
            if byte_total > PAIR_MAX_BYTES:
                _fail(
                    Stage4BErrorCode.RESPONSE_TOO_LARGE,
                    "PDBTM provider pair exceeded the 10 MiB limit.",
                    existing_cache_usable=True,
                )
            payloads.append(payload)
            _require_not_cancelled(cancellation)
        if self._monotonic() >= deadline:
            _fail(
                Stage4BErrorCode.NETWORK_TIMEOUT,
                "PDBTM pair retrieval exceeded its total deadline.",
                retryable=True,
                existing_cache_usable=True,
            )
        _require_not_cancelled(cancellation)
        json_body = _payload_body(payloads[0], PDBTM_JSON_ROLE)
        pdb_body = _payload_body(payloads[1], TRANSFORMED_PDB_ROLE)
        result, versions, validation = validate_pdbtm_pair(canonical_id, json_body, pdb_body)
        _require_not_cancelled(cancellation)
        return ValidatedPdbtmPair(
            canonical_id,
            (payloads[0], payloads[1]),
            result,
            versions,
            validation,
        )
