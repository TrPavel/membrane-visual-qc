"""Canonical identity contract for the PDBTM API-v1 cache.

This module is deliberately independent of the filesystem and transport.  It
defines the closed JSON shapes that may cross the cache boundary and rejects
stored bytes unless they are already the exact ``mvqc-canonical-json-v1``
representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping, Sequence

CACHE_CONTRACT = "pdbtm-api-v1/cache-v1"
PROVIDER = "pdbtm_api_v1"
CANONICAL_JSON = "mvqc-canonical-json-v1"
DIGEST_ALGORITHM = "sha256"
VALIDATION_PROFILE = "pdbtm-api-v1-format-precision-envelope-v1"
TRANSPORT_VERIFICATION = "direct_https_tls_verified"

PDBTM_JSON_ROLE = "pdbtm_json"
TRANSFORMED_PDB_ROLE = "transformed_pdb"
PAYLOAD_ROLES = (PDBTM_JSON_ROLE, TRANSFORMED_PDB_ROLE)

PAIR_DOMAIN = b"mvqc-pdbtm-pair-v1\0"
SNAPSHOT_DOMAIN = b"mvqc-pdbtm-snapshot-v1\0"
INDEX_DOMAIN = b"mvqc-pdbtm-index-v1\0"
FORMAT_DOMAIN = b"mvqc-pdbtm-format-v1\0"

_RECORD_ID = re.compile(r"[0-9][a-z0-9]{3}\Z", re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z\Z",
    re.ASCII,
)


class CacheContractError(ValueError):
    """A value or stored document violates the frozen cache contract."""


def _fail(message: str) -> None:
    raise CacheContractError(message)


def _require_exact_type(value: object, expected: type, field: str) -> None:
    if type(value) is not expected:
        _fail(f"{field} must have exact type {expected.__name__}")


def _require_unicode_scalar(value: object, field: str) -> str:
    _require_exact_type(value, str, field)
    assert isinstance(value, str)
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        _fail(f"{field} must contain only Unicode scalar values")
    return value


def _require_literal(value: object, expected: str, field: str) -> str:
    text = _require_unicode_scalar(value, field)
    if text != expected:
        _fail(f"{field} must be {expected!r}")
    return text


def _require_nonnegative_int(value: object, field: str) -> int:
    _require_exact_type(value, int, field)
    assert isinstance(value, int)
    if value < 0:
        _fail(f"{field} must be non-negative")
    return value


def _require_record_id(value: object, field: str = "canonical_record_id") -> str:
    text = _require_unicode_scalar(value, field)
    if _RECORD_ID.fullmatch(text) is None:
        _fail(f"{field} must be one canonical lowercase legacy PDB ID")
    return text


def _require_sha256(value: object, field: str) -> str:
    text = _require_unicode_scalar(value, field)
    if _SHA256.fullmatch(text) is None:
        _fail(f"{field} must be one lowercase SHA-256 digest")
    return text


def _require_timestamp(value: object, field: str) -> str:
    text = _require_unicode_scalar(value, field)
    if _TIMESTAMP.fullmatch(text) is None:
        _fail(f"{field} must be UTC RFC 3339 with six fractional digits")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise CacheContractError(f"{field} is not a valid UTC timestamp") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != text:
        _fail(f"{field} is not a canonical UTC timestamp")
    return text


def _timestamp_value(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def _require_closed_mapping(
    value: object, expected_keys: set[str], field: str
) -> Mapping[str, object]:
    _require_exact_type(value, dict, field)
    assert isinstance(value, dict)
    for key in value:
        _require_unicode_scalar(key, f"{field} key")
    actual = set(value)
    if actual != expected_keys:
        missing = sorted(expected_keys - actual)
        extra = sorted(actual - expected_keys)
        _fail(f"{field} has an invalid closed shape (missing={missing}, extra={extra})")
    return value


def _require_exact_list(value: object, field: str) -> list[object]:
    _require_exact_type(value, list, field)
    assert isinstance(value, list)
    return value


def _validate_json_value(value: object, path: str = "$") -> None:
    if value is None or type(value) in (bool, int):
        return
    if type(value) is str:
        _require_unicode_scalar(value, path)
        return
    if type(value) is list:
        assert isinstance(value, list)
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if type(value) is dict:
        assert isinstance(value, dict)
        for key, item in value.items():
            _require_unicode_scalar(key, f"{path} key")
            _validate_json_value(item, f"{path}.{key}")
        return
    _fail(f"{path} contains a value outside the canonical JSON domain")


def canonical_json_bytes(value: object) -> bytes:
    """Serialize an already-shaped value using mvqc-canonical-json-v1."""

    _validate_json_value(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise CacheContractError("value is not canonical JSON") from error


def _identity(domain: bytes, core: Mapping[str, object]) -> str:
    return hashlib.sha256(domain + canonical_json_bytes(dict(core))).hexdigest()


def _pairs_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_float(_: str) -> object:
    _fail("floating-point JSON numbers are outside the canonical contract")


def _reject_constant(_: str) -> object:
    _fail("non-finite JSON numbers are outside the canonical contract")


def _parse_canonical_document(data: bytes) -> dict[str, object]:
    _require_exact_type(data, bytes, "stored document")
    assert isinstance(data, bytes)
    if data.startswith(b"\xef\xbb\xbf"):
        _fail("stored canonical JSON must not have a BOM")
    try:
        text = data.decode("utf-8", errors="strict")
        parsed = json.loads(
            text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except CacheContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CacheContractError("stored document is not strict UTF-8 JSON") from error
    _require_exact_type(parsed, dict, "stored document")
    assert isinstance(parsed, dict)
    if canonical_json_bytes(parsed) != data:
        _fail("stored document is not the exact canonical JSON representation")
    return parsed


def _approved_url(record_id: str, role: str) -> str:
    suffix = "json" if role == PDBTM_JSON_ROLE else "trpdb"
    return f"https://pdbtm.unitmp.org/api/v1/entry/{record_id}.{suffix}"


@dataclass(frozen=True, slots=True)
class PayloadIdentity:
    role: str
    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        if self.role not in PAYLOAD_ROLES or type(self.role) is not str:
            _fail("payload role is unsupported")
        _require_sha256(self.sha256, "payload sha256")
        _require_nonnegative_int(self.byte_size, "payload byte_size")

    def to_dict(self) -> dict[str, object]:
        return {"role": self.role, "sha256": self.sha256, "byte_size": self.byte_size}

    @classmethod
    def from_dict(cls, value: object, field: str = "payload") -> PayloadIdentity:
        mapping = _require_closed_mapping(value, {"role", "sha256", "byte_size"}, field)
        return cls(
            role=mapping["role"],  # type: ignore[arg-type]
            sha256=mapping["sha256"],  # type: ignore[arg-type]
            byte_size=mapping["byte_size"],  # type: ignore[arg-type]
        )


def _require_payload_order(
    payloads: Sequence[PayloadIdentity | AcquisitionPayload], field: str
) -> None:
    _require_exact_type(payloads, tuple, field)
    if any(type(item) not in {PayloadIdentity, AcquisitionPayload} for item in payloads):
        _fail(f"{field} contains an invalid payload type")
    if len(payloads) != 2 or tuple(item.role for item in payloads) != PAYLOAD_ROLES:
        _fail(f"{field} must contain exactly pdbtm_json then transformed_pdb")


@dataclass(frozen=True, slots=True)
class PairCore:
    canonical_record_id: str
    payloads: tuple[PayloadIdentity, PayloadIdentity]
    cache_contract: str = CACHE_CONTRACT
    provider: str = PROVIDER

    def __post_init__(self) -> None:
        _require_record_id(self.canonical_record_id)
        _require_payload_order(self.payloads, "pair payloads")
        if any(type(item) is not PayloadIdentity for item in self.payloads):
            _fail("pair payloads must be exact PayloadIdentity values")
        _require_literal(self.cache_contract, CACHE_CONTRACT, "cache_contract")
        _require_literal(self.provider, PROVIDER, "provider")

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_contract": self.cache_contract,
            "provider": self.provider,
            "canonical_record_id": self.canonical_record_id,
            "payloads": [item.to_dict() for item in self.payloads],
        }

    @classmethod
    def from_dict(cls, value: object) -> PairCore:
        mapping = _require_closed_mapping(
            value,
            {"cache_contract", "provider", "canonical_record_id", "payloads"},
            "pair_core",
        )
        payloads = _require_exact_list(mapping["payloads"], "pair_core.payloads")
        return cls(
            canonical_record_id=mapping["canonical_record_id"],  # type: ignore[arg-type]
            payloads=tuple(
                PayloadIdentity.from_dict(item, f"pair_core.payloads[{index}]")
                for index, item in enumerate(payloads)
            ),  # type: ignore[arg-type]
            cache_contract=mapping["cache_contract"],  # type: ignore[arg-type]
            provider=mapping["provider"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class ContentTypeEvidence:
    media_type: str
    charset: str | None

    def __post_init__(self) -> None:
        media_type = _require_unicode_scalar(self.media_type, "content type media_type")
        if media_type not in {"text/plain", "application/json"}:
            _fail("content type media_type is not approved")
        if self.charset is not None:
            _require_literal(self.charset, "utf-8", "content type charset")

    def to_dict(self) -> dict[str, object]:
        return {"media_type": self.media_type, "charset": self.charset}

    @classmethod
    def from_dict(cls, value: object) -> ContentTypeEvidence:
        mapping = _require_closed_mapping(value, {"media_type", "charset"}, "headers.content_type")
        return cls(
            media_type=mapping["media_type"],  # type: ignore[arg-type]
            charset=mapping["charset"],  # type: ignore[arg-type]
        )


def _require_optional_header(value: object, field: str) -> str | None:
    if value is None:
        return None
    text = _require_unicode_scalar(value, field)
    if not text or len(text) > 1024:
        _fail(f"{field} must be 1..1024 characters when present")
    if any(ord(character) < 0x20 or ord(character) > 0x7E for character in text):
        _fail(f"{field} must contain safe printable ASCII only")
    return text


_MAX_PROVIDER_VERSION_BYTES = 256


def _require_bounded_provider_field(value: object, field: str) -> str:
    text = _require_unicode_scalar(value, field)
    if not text:
        _fail(f"{field} must not be empty")
    if any(ord(character) < 0x20 or ord(character) > 0x7E for character in text):
        _fail(f"{field} must contain safe printable ASCII only")
    if len(text.encode("utf-8")) > _MAX_PROVIDER_VERSION_BYTES:
        _fail(f"{field} must be at most {_MAX_PROVIDER_VERSION_BYTES} bytes")
    return text


@dataclass(frozen=True, slots=True)
class ResponseHeaders:
    content_type: ContentTypeEvidence
    content_encoding: str | None = None
    etag: str | None = None
    last_modified: str | None = None

    def __post_init__(self) -> None:
        if type(self.content_type) is not ContentTypeEvidence:
            _fail("content_type must be exact ContentTypeEvidence")
        if self.content_encoding is not None:
            _require_literal(self.content_encoding, "identity", "content_encoding")
        _require_optional_header(self.etag, "etag")
        _require_optional_header(self.last_modified, "last_modified")

    def to_dict(self) -> dict[str, object]:
        return {
            "content_type": self.content_type.to_dict(),
            "content_encoding": self.content_encoding,
            "etag": self.etag,
            "last_modified": self.last_modified,
        }

    @classmethod
    def from_dict(cls, value: object) -> ResponseHeaders:
        mapping = _require_closed_mapping(
            value,
            {"content_type", "content_encoding", "etag", "last_modified"},
            "headers",
        )
        return cls(
            content_type=ContentTypeEvidence.from_dict(mapping["content_type"]),
            content_encoding=mapping["content_encoding"],  # type: ignore[arg-type]
            etag=mapping["etag"],  # type: ignore[arg-type]
            last_modified=mapping["last_modified"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class AcquisitionPayload:
    role: str
    sha256: str
    byte_size: int
    requested_url: str
    final_url: str
    requested_at: str
    completed_at: str
    status: int
    headers: ResponseHeaders
    transport_verification: str = TRANSPORT_VERIFICATION

    def __post_init__(self) -> None:
        if self.role not in PAYLOAD_ROLES or type(self.role) is not str:
            _fail("acquisition payload role is unsupported")
        _require_sha256(self.sha256, "acquisition payload sha256")
        _require_nonnegative_int(self.byte_size, "acquisition payload byte_size")
        record_id = _record_id_from_url(self.requested_url, self.role, "requested_url")
        if self.final_url != self.requested_url:
            _fail("final_url must exactly equal requested_url because redirects are forbidden")
        _record_id_from_url(self.final_url, self.role, "final_url")
        requested_at = _require_timestamp(self.requested_at, "requested_at")
        completed_at = _require_timestamp(self.completed_at, "completed_at")
        if _timestamp_value(completed_at) < _timestamp_value(requested_at):
            _fail("completed_at must not precede requested_at")
        _require_exact_type(self.status, int, "status")
        if self.status != 200:
            _fail("cached payload status must be exactly 200")
        if type(self.headers) is not ResponseHeaders:
            _fail("headers must be exact ResponseHeaders")
        if self.role == TRANSFORMED_PDB_ROLE and (
            self.headers.content_type.media_type != "text/plain"
            or self.headers.content_type.charset != "utf-8"
        ):
            _fail("transformed_pdb requires text/plain; charset=utf-8")
        if self.role == PDBTM_JSON_ROLE:
            content_type = self.headers.content_type
            valid_json_type = (
                content_type.media_type == "text/plain" and content_type.charset == "utf-8"
            ) or (
                content_type.media_type == "application/json"
                and content_type.charset in (None, "utf-8")
            )
            if not valid_json_type:
                _fail("pdbtm_json content type is not approved")
        _require_literal(
            self.transport_verification,
            TRANSPORT_VERIFICATION,
            "transport_verification",
        )
        # Make the URL-derived identifier observable to static analysis and ensure
        # both URL checks used the same exact approved form.
        _require_record_id(record_id)

    def to_identity(self) -> PayloadIdentity:
        return PayloadIdentity(self.role, self.sha256, self.byte_size)

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "requested_at": self.requested_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "headers": self.headers.to_dict(),
            "transport_verification": self.transport_verification,
        }

    @classmethod
    def from_dict(cls, value: object) -> AcquisitionPayload:
        mapping = _require_closed_mapping(
            value,
            {
                "role",
                "sha256",
                "byte_size",
                "requested_url",
                "final_url",
                "requested_at",
                "completed_at",
                "status",
                "headers",
                "transport_verification",
            },
            "acquisition payload",
        )
        return cls(
            role=mapping["role"],  # type: ignore[arg-type]
            sha256=mapping["sha256"],  # type: ignore[arg-type]
            byte_size=mapping["byte_size"],  # type: ignore[arg-type]
            requested_url=mapping["requested_url"],  # type: ignore[arg-type]
            final_url=mapping["final_url"],  # type: ignore[arg-type]
            requested_at=mapping["requested_at"],  # type: ignore[arg-type]
            completed_at=mapping["completed_at"],  # type: ignore[arg-type]
            status=mapping["status"],  # type: ignore[arg-type]
            headers=ResponseHeaders.from_dict(mapping["headers"]),
            transport_verification=mapping["transport_verification"],  # type: ignore[arg-type]
        )


def _record_id_from_url(value: object, role: str, field: str) -> str:
    url = _require_unicode_scalar(value, field)
    prefix = "https://pdbtm.unitmp.org/api/v1/entry/"
    suffix = ".json" if role == PDBTM_JSON_ROLE else ".trpdb"
    if not url.startswith(prefix) or not url.endswith(suffix):
        _fail(f"{field} is not an approved PDBTM URL")
    record_id = url[len(prefix) : -len(suffix)]
    _require_record_id(record_id, f"{field} record ID")
    if url != _approved_url(record_id, role):
        _fail(f"{field} is not the exact approved URL")
    return record_id


@dataclass(frozen=True, slots=True)
class ProviderVersions:
    resource_version: str
    software_version: str

    def __post_init__(self) -> None:
        for field, value in (
            ("resource_version", self.resource_version),
            ("software_version", self.software_version),
        ):
            _require_bounded_provider_field(value, field)

    def to_dict(self) -> dict[str, object]:
        return {
            "resource_version": self.resource_version,
            "software_version": self.software_version,
        }

    @classmethod
    def from_dict(cls, value: object) -> ProviderVersions:
        mapping = _require_closed_mapping(
            value, {"resource_version", "software_version"}, "provider_versions"
        )
        return cls(
            resource_version=mapping["resource_version"],  # type: ignore[arg-type]
            software_version=mapping["software_version"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class SnapshotCore:
    canonical_record_id: str
    pair_id: str
    payloads: tuple[AcquisitionPayload, AcquisitionPayload]
    provider_versions: ProviderVersions
    validated_at: str
    cache_contract: str = CACHE_CONTRACT
    provider: str = PROVIDER
    validation_profile: str = VALIDATION_PROFILE

    def __post_init__(self) -> None:
        record_id = _require_record_id(self.canonical_record_id)
        _require_sha256(self.pair_id, "pair_id")
        _require_payload_order(self.payloads, "snapshot payloads")
        if any(type(item) is not AcquisitionPayload for item in self.payloads):
            _fail("snapshot payloads must be exact AcquisitionPayload values")
        if any(
            _record_id_from_url(item.requested_url, item.role, "payload URL") != record_id
            for item in self.payloads
        ):
            _fail("payload URLs must match canonical_record_id")
        expected_pair = PairCore(
            record_id,
            tuple(item.to_identity() for item in self.payloads),  # type: ignore[arg-type]
        )
        if compute_pair_id(expected_pair) != self.pair_id:
            _fail("pair_id does not match the snapshot payload identities")
        if type(self.provider_versions) is not ProviderVersions:
            _fail("provider_versions must be exact ProviderVersions")
        validated_at = _require_timestamp(self.validated_at, "validated_at")
        if any(
            _timestamp_value(validated_at) < _timestamp_value(item.completed_at)
            for item in self.payloads
        ):
            _fail("validated_at must not precede payload completion")
        _require_literal(self.cache_contract, CACHE_CONTRACT, "cache_contract")
        _require_literal(self.provider, PROVIDER, "provider")
        _require_literal(self.validation_profile, VALIDATION_PROFILE, "validation_profile")

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_contract": self.cache_contract,
            "provider": self.provider,
            "canonical_record_id": self.canonical_record_id,
            "pair_id": self.pair_id,
            "payloads": [item.to_dict() for item in self.payloads],
            "provider_versions": self.provider_versions.to_dict(),
            "validation_profile": self.validation_profile,
            "validated_at": self.validated_at,
        }

    @classmethod
    def from_dict(cls, value: object) -> SnapshotCore:
        mapping = _require_closed_mapping(
            value,
            {
                "cache_contract",
                "provider",
                "canonical_record_id",
                "pair_id",
                "payloads",
                "provider_versions",
                "validation_profile",
                "validated_at",
            },
            "snapshot_core",
        )
        payloads = _require_exact_list(mapping["payloads"], "snapshot_core.payloads")
        return cls(
            canonical_record_id=mapping["canonical_record_id"],  # type: ignore[arg-type]
            pair_id=mapping["pair_id"],  # type: ignore[arg-type]
            payloads=tuple(AcquisitionPayload.from_dict(item) for item in payloads),  # type: ignore[arg-type]
            provider_versions=ProviderVersions.from_dict(mapping["provider_versions"]),
            validated_at=mapping["validated_at"],  # type: ignore[arg-type]
            cache_contract=mapping["cache_contract"],  # type: ignore[arg-type]
            provider=mapping["provider"],  # type: ignore[arg-type]
            validation_profile=mapping["validation_profile"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class IndexRecord:
    generation: int
    active_snapshot_id: str | None
    snapshot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_nonnegative_int(self.generation, "record generation")
        _require_exact_type(self.snapshot_ids, tuple, "snapshot_ids")
        for snapshot_id in self.snapshot_ids:
            _require_sha256(snapshot_id, "snapshot_id")
        if tuple(sorted(set(self.snapshot_ids))) != self.snapshot_ids:
            _fail("snapshot_ids must be unique and lexicographically sorted")
        if self.active_snapshot_id is not None:
            _require_sha256(self.active_snapshot_id, "active_snapshot_id")
            if self.active_snapshot_id not in self.snapshot_ids:
                _fail("active_snapshot_id must be a member of snapshot_ids")

    def to_dict(self) -> dict[str, object]:
        return {
            "generation": self.generation,
            "active_snapshot_id": self.active_snapshot_id,
            "snapshot_ids": list(self.snapshot_ids),
        }

    @classmethod
    def from_dict(cls, value: object) -> IndexRecord:
        mapping = _require_closed_mapping(
            value,
            {"generation", "active_snapshot_id", "snapshot_ids"},
            "index record",
        )
        snapshot_ids = _require_exact_list(mapping["snapshot_ids"], "snapshot_ids")
        return cls(
            generation=mapping["generation"],  # type: ignore[arg-type]
            active_snapshot_id=mapping["active_snapshot_id"],  # type: ignore[arg-type]
            snapshot_ids=tuple(snapshot_ids),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class IndexCore:
    generation: int
    records: Mapping[str, IndexRecord]
    cache_contract: str = CACHE_CONTRACT

    def __post_init__(self) -> None:
        generation = _require_nonnegative_int(self.generation, "index generation")
        if type(self.records) not in (dict, MappingProxyType):
            _fail("records must be a plain mapping")
        copied: dict[str, IndexRecord] = {}
        for record_id, record in self.records.items():
            canonical = _require_record_id(record_id, "records key")
            if type(record) is not IndexRecord:
                _fail("records values must be exact IndexRecord values")
            if record.generation > generation:
                _fail("record generation must not exceed global generation")
            copied[canonical] = record
        object.__setattr__(self, "records", MappingProxyType(copied))
        _require_literal(self.cache_contract, CACHE_CONTRACT, "cache_contract")

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_contract": self.cache_contract,
            "generation": self.generation,
            "records": {record_id: record.to_dict() for record_id, record in self.records.items()},
        }

    @classmethod
    def from_dict(cls, value: object) -> IndexCore:
        mapping = _require_closed_mapping(
            value, {"cache_contract", "generation", "records"}, "index_core"
        )
        records = mapping["records"]
        _require_exact_type(records, dict, "index_core.records")
        assert isinstance(records, dict)
        return cls(
            generation=mapping["generation"],  # type: ignore[arg-type]
            records={
                record_id: IndexRecord.from_dict(record) for record_id, record in records.items()
            },
            cache_contract=mapping["cache_contract"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class FormatCore:
    cache_contract: str = CACHE_CONTRACT
    provider: str = PROVIDER
    canonical_json: str = CANONICAL_JSON
    digest_algorithm: str = DIGEST_ALGORITHM

    def __post_init__(self) -> None:
        _require_literal(self.cache_contract, CACHE_CONTRACT, "cache_contract")
        _require_literal(self.provider, PROVIDER, "provider")
        _require_literal(self.canonical_json, CANONICAL_JSON, "canonical_json")
        _require_literal(self.digest_algorithm, DIGEST_ALGORITHM, "digest_algorithm")

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_contract": self.cache_contract,
            "provider": self.provider,
            "canonical_json": self.canonical_json,
            "digest_algorithm": self.digest_algorithm,
        }

    @classmethod
    def from_dict(cls, value: object) -> FormatCore:
        mapping = _require_closed_mapping(
            value,
            {"cache_contract", "provider", "canonical_json", "digest_algorithm"},
            "format_core",
        )
        return cls(
            cache_contract=mapping["cache_contract"],  # type: ignore[arg-type]
            provider=mapping["provider"],  # type: ignore[arg-type]
            canonical_json=mapping["canonical_json"],  # type: ignore[arg-type]
            digest_algorithm=mapping["digest_algorithm"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class PairEnvelope:
    pair_id: str
    pair_core: PairCore

    def __post_init__(self) -> None:
        _require_sha256(self.pair_id, "pair_id")
        if type(self.pair_core) is not PairCore:
            _fail("pair_core must be exact PairCore")
        if compute_pair_id(self.pair_core) != self.pair_id:
            _fail("pair_id does not match pair_core")

    def to_dict(self) -> dict[str, object]:
        return {"pair_id": self.pair_id, "pair_core": self.pair_core.to_dict()}


@dataclass(frozen=True, slots=True)
class SnapshotEnvelope:
    snapshot_id: str
    snapshot_core: SnapshotCore

    def __post_init__(self) -> None:
        _require_sha256(self.snapshot_id, "snapshot_id")
        if type(self.snapshot_core) is not SnapshotCore:
            _fail("snapshot_core must be exact SnapshotCore")
        if compute_snapshot_id(self.snapshot_core) != self.snapshot_id:
            _fail("snapshot_id does not match snapshot_core")

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_core": self.snapshot_core.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class IndexEnvelope:
    index_id: str
    index_core: IndexCore

    def __post_init__(self) -> None:
        _require_sha256(self.index_id, "index_id")
        if type(self.index_core) is not IndexCore:
            _fail("index_core must be exact IndexCore")
        if compute_index_id(self.index_core) != self.index_id:
            _fail("index_id does not match index_core")

    def to_dict(self) -> dict[str, object]:
        return {"index_id": self.index_id, "index_core": self.index_core.to_dict()}


@dataclass(frozen=True, slots=True)
class FormatEnvelope:
    format_id: str
    format_core: FormatCore

    def __post_init__(self) -> None:
        _require_sha256(self.format_id, "format_id")
        if type(self.format_core) is not FormatCore:
            _fail("format_core must be exact FormatCore")
        if compute_format_id(self.format_core) != self.format_id:
            _fail("format_id does not match format_core")

    def to_dict(self) -> dict[str, object]:
        return {"format_id": self.format_id, "format_core": self.format_core.to_dict()}


def compute_pair_id(core: PairCore) -> str:
    validate_pair_core(core)
    return _identity(PAIR_DOMAIN, core.to_dict())


def compute_snapshot_id(core: SnapshotCore) -> str:
    validate_snapshot_core(core)
    return _identity(SNAPSHOT_DOMAIN, core.to_dict())


def compute_index_id(core: IndexCore) -> str:
    validate_index_core(core)
    return _identity(INDEX_DOMAIN, core.to_dict())


def compute_format_id(core: FormatCore) -> str:
    validate_format_core(core)
    return _identity(FORMAT_DOMAIN, core.to_dict())


def validate_pair_core(core: PairCore) -> None:
    """Validate that *core* is an exact, constructible pair-core value."""

    if type(core) is not PairCore:
        _fail("core must be exact PairCore")
    PairCore.from_dict(core.to_dict())


def validate_snapshot_core(core: SnapshotCore) -> None:
    """Validate that *core* is an exact, constructible snapshot-core value."""

    if type(core) is not SnapshotCore:
        _fail("core must be exact SnapshotCore")
    SnapshotCore.from_dict(core.to_dict())


def validate_index_core(core: IndexCore) -> None:
    """Validate that *core* is an exact, constructible index-core value."""

    if type(core) is not IndexCore:
        _fail("core must be exact IndexCore")
    IndexCore.from_dict(core.to_dict())


def validate_format_core(core: FormatCore) -> None:
    """Validate that *core* is an exact, constructible format-core value."""

    if type(core) is not FormatCore:
        _fail("core must be exact FormatCore")
    FormatCore.from_dict(core.to_dict())


def make_pair_envelope(core: PairCore) -> PairEnvelope:
    return PairEnvelope(compute_pair_id(core), core)


def make_snapshot_envelope(core: SnapshotCore) -> SnapshotEnvelope:
    return SnapshotEnvelope(compute_snapshot_id(core), core)


def make_index_envelope(core: IndexCore) -> IndexEnvelope:
    return IndexEnvelope(compute_index_id(core), core)


def make_format_envelope(core: FormatCore | None = None) -> FormatEnvelope:
    resolved = core if core is not None else FormatCore()
    return FormatEnvelope(compute_format_id(resolved), resolved)


def serialize_pair_envelope(envelope: PairEnvelope) -> bytes:
    if type(envelope) is not PairEnvelope:
        _fail("envelope must be exact PairEnvelope")
    return canonical_json_bytes(envelope.to_dict())


def serialize_snapshot_envelope(envelope: SnapshotEnvelope) -> bytes:
    if type(envelope) is not SnapshotEnvelope:
        _fail("envelope must be exact SnapshotEnvelope")
    return canonical_json_bytes(envelope.to_dict())


def serialize_index_envelope(envelope: IndexEnvelope) -> bytes:
    if type(envelope) is not IndexEnvelope:
        _fail("envelope must be exact IndexEnvelope")
    return canonical_json_bytes(envelope.to_dict())


def serialize_format_envelope(envelope: FormatEnvelope) -> bytes:
    if type(envelope) is not FormatEnvelope:
        _fail("envelope must be exact FormatEnvelope")
    return canonical_json_bytes(envelope.to_dict())


def parse_pair_envelope(data: bytes) -> PairEnvelope:
    mapping = _require_closed_mapping(
        _parse_canonical_document(data), {"pair_id", "pair_core"}, "pair envelope"
    )
    return PairEnvelope(
        pair_id=mapping["pair_id"],  # type: ignore[arg-type]
        pair_core=PairCore.from_dict(mapping["pair_core"]),
    )


def parse_snapshot_envelope(data: bytes) -> SnapshotEnvelope:
    mapping = _require_closed_mapping(
        _parse_canonical_document(data),
        {"snapshot_id", "snapshot_core"},
        "snapshot envelope",
    )
    return SnapshotEnvelope(
        snapshot_id=mapping["snapshot_id"],  # type: ignore[arg-type]
        snapshot_core=SnapshotCore.from_dict(mapping["snapshot_core"]),
    )


def parse_index_envelope(data: bytes) -> IndexEnvelope:
    mapping = _require_closed_mapping(
        _parse_canonical_document(data), {"index_id", "index_core"}, "index envelope"
    )
    return IndexEnvelope(
        index_id=mapping["index_id"],  # type: ignore[arg-type]
        index_core=IndexCore.from_dict(mapping["index_core"]),
    )


def parse_format_envelope(data: bytes) -> FormatEnvelope:
    mapping = _require_closed_mapping(
        _parse_canonical_document(data),
        {"format_id", "format_core"},
        "format envelope",
    )
    return FormatEnvelope(
        format_id=mapping["format_id"],  # type: ignore[arg-type]
        format_core=FormatCore.from_dict(mapping["format_core"]),
    )
