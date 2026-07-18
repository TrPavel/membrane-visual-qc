"""Immutable domain models for external orientation-source evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Literal

from .errors import OrientationError
from .orientation import PlanarMembrane

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
ImportStatus = Literal["imported", "partial", "rejected", "unsupported"]
GEOMETRY_MATCH_TOLERANCE = 1e-9


def _text(value: object, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise OrientationError(f"{name} must be non-empty text.")
    return value.strip()


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise OrientationError(f"{name} must be finite.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OrientationError(f"{name} must be finite.") from exc
    if not math.isfinite(number):
        raise OrientationError(f"{name} must be finite.")
    return 0.0 if number == 0 else number


def _tuple3(value: object, name: str) -> tuple[float, float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise OrientationError(f"{name} must contain three numbers.")
    return tuple(_finite(item, f"{name}[{index}]") for index, item in enumerate(value))  # type: ignore[return-value]


def _matrix4(value: object, name: str) -> tuple[tuple[float, float, float, float], ...]:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise OrientationError(f"{name} must be a 4x4 matrix.")
    rows = []
    for i, row in enumerate(value):
        if not isinstance(row, (tuple, list)) or len(row) != 4:
            raise OrientationError(f"{name}[{i}] must contain four numbers.")
        rows.append(tuple(_finite(item, f"{name}[{i}]") for item in row))
    return tuple(rows)  # type: ignore[return-value]


def _json_safe(value: object, path: str = "metadata") -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return _finite(value, path)
    if isinstance(value, Mapping):
        result = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise OrientationError(f"{path} keys must be text.")
            result[key] = _json_safe(value[key], f"{path}.{key}")
        return MappingProxyType(result)
    if isinstance(value, (tuple, list)):
        return tuple(_json_safe(item, f"{path}[]") for item in value)
    raise OrientationError(f"{path} must be JSON-safe.")


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class ImportMessage:
    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _text(self.code, "message code"))
        object.__setattr__(self, "message", _text(self.message, "message"))

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class PayloadDigest:
    role: str
    sha256: str
    byte_size: int
    source: str | None = None
    media_type: str | None = None
    retrieved_at: str | None = None
    retrieval_verified: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _text(self.role, "payload role"))
        digest = _text(self.sha256, "payload sha256")
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise OrientationError("payload sha256 must be 64 lowercase hexadecimal characters.")
        object.__setattr__(self, "sha256", digest)
        if isinstance(self.byte_size, bool) or self.byte_size < 0:
            raise OrientationError("payload byte_size must be non-negative.")
        for name in ("source", "media_type", "retrieved_at"):
            object.__setattr__(self, name, _text(getattr(self, name), name, optional=True))
        # Offline Stage 4A1 callers supply untrusted local bytes. Verified retrieval
        # is reserved for a future trusted transport boundary.
        object.__setattr__(self, "retrieval_verified", False)

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "source": self.source,
            "media_type": self.media_type,
            "retrieved_at": self.retrieved_at,
            "retrieval_verified": self.retrieval_verified,
        }


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    name: str
    record_id: str | None
    resource_version: str | None
    software_version: str | None
    source_url: str | None
    retrieved_at: str | None
    citation: str | None
    raw_payloads: tuple[PayloadDigest, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "source name"))
        for name in (
            "record_id",
            "resource_version",
            "software_version",
            "source_url",
            "retrieved_at",
            "citation",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name, optional=True))
        object.__setattr__(
            self, "raw_payloads", tuple(sorted(self.raw_payloads, key=lambda x: x.role))
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "record_id": self.record_id,
            "resource_version": self.resource_version,
            "software_version": self.software_version,
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "citation": self.citation,
            "raw_payloads": [item.as_dict() for item in self.raw_payloads],
        }


@dataclass(frozen=True, slots=True)
class StructureScope:
    structure_id: str | None
    model_id: str
    biological_assembly: str | None
    chains: tuple[str, ...]
    chain_namespace: str
    coordinate_frame: str
    coordinate_fingerprint: str | None = None
    provider_chain_labels: tuple[str, ...] = ()
    legacy_chains: tuple[str, ...] = ()
    chain_mapping: Mapping[str, object] = field(default_factory=dict)
    selected_model: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "structure_id", _text(self.structure_id, "structure_id", optional=True)
        )
        object.__setattr__(self, "model_id", _text(self.model_id, "model_id"))
        object.__setattr__(
            self,
            "biological_assembly",
            _text(self.biological_assembly, "biological_assembly", optional=True),
        )
        object.__setattr__(self, "chains", tuple(sorted({_text(x, "chain") for x in self.chains})))
        object.__setattr__(self, "chain_namespace", _text(self.chain_namespace, "chain_namespace"))
        object.__setattr__(
            self, "coordinate_frame", _text(self.coordinate_frame, "coordinate_frame")
        )
        object.__setattr__(
            self,
            "coordinate_fingerprint",
            _text(self.coordinate_fingerprint, "coordinate_fingerprint", optional=True),
        )
        object.__setattr__(
            self,
            "provider_chain_labels",
            tuple(sorted({_text(x, "provider_chain_label") for x in self.provider_chain_labels})),
        )
        object.__setattr__(
            self,
            "legacy_chains",
            tuple(sorted({_text(x, "legacy_chain") for x in self.legacy_chains})),
        )
        object.__setattr__(self, "chain_mapping", _json_safe(self.chain_mapping, "chain_mapping"))
        if isinstance(self.selected_model, bool) or self.selected_model < 1:
            raise OrientationError("selected_model must be a positive integer.")

    def as_dict(self) -> dict[str, object]:
        return {
            "structure_id": self.structure_id,
            "model_id": self.model_id,
            "biological_assembly": self.biological_assembly,
            "chains": list(self.chains),
            "chain_namespace": self.chain_namespace,
            "coordinate_frame": self.coordinate_frame,
            "coordinate_fingerprint": self.coordinate_fingerprint,
            "provider_chain_labels": list(self.provider_chain_labels),
            "legacy_chains": list(self.legacy_chains),
            "chain_mapping": _thaw(self.chain_mapping),
            "selected_model": self.selected_model,
        }


@dataclass(frozen=True, slots=True)
class PlanarGeometryEvidence:
    center: tuple[float, float, float]
    normal: tuple[float, float, float]
    lower_offset: float
    upper_offset: float
    interface_width: float | None
    frame: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "center", _tuple3(self.center, "center"))
        object.__setattr__(self, "normal", _tuple3(self.normal, "normal"))
        normal_length = math.sqrt(sum(value * value for value in self.normal))
        if normal_length <= GEOMETRY_MATCH_TOLERANCE:
            raise OrientationError("normal must be non-zero.")
        if not math.isclose(normal_length, 1.0, rel_tol=0.0, abs_tol=GEOMETRY_MATCH_TOLERANCE):
            raise OrientationError("normal must be a unit vector.")
        object.__setattr__(self, "lower_offset", _finite(self.lower_offset, "lower_offset"))
        object.__setattr__(self, "upper_offset", _finite(self.upper_offset, "upper_offset"))
        if self.lower_offset >= self.upper_offset:
            raise OrientationError("lower_offset must be less than upper_offset.")
        if self.interface_width is not None:
            object.__setattr__(
                self, "interface_width", _finite(self.interface_width, "interface_width")
            )
            if self.interface_width < 0:
                raise OrientationError("interface_width must be non-negative or null.")
        object.__setattr__(self, "frame", _text(self.frame, "frame"))

    def as_dict(self) -> dict[str, object]:
        return {
            "geometry": "planar",
            "center": list(self.center),
            "normal": list(self.normal),
            "lower_offset": self.lower_offset,
            "upper_offset": self.upper_offset,
            "interface_width": self.interface_width,
            "frame": self.frame,
        }


@dataclass(frozen=True, slots=True)
class CoordinateMapping:
    source_frame: str
    current_frame: str
    source_to_current: tuple[tuple[float, float, float, float], ...]
    provider_original_to_transformed: tuple[tuple[float, float, float, float], ...]
    provider_transformed_to_original: tuple[tuple[float, float, float, float], ...]
    method: str
    metrics: Mapping[str, object]
    fingerprints: Mapping[str, object]
    precision_profile: Mapping[str, object]
    thresholds: Mapping[str, object]
    determinant: float
    orthonormality_error: float

    def __post_init__(self) -> None:
        for name in ("source_frame", "current_frame", "method"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "source_to_current",
            "provider_original_to_transformed",
            "provider_transformed_to_original",
        ):
            object.__setattr__(self, name, _matrix4(getattr(self, name), name))
        for name in ("metrics", "fingerprints", "precision_profile", "thresholds"):
            object.__setattr__(self, name, _json_safe(getattr(self, name), name))
        object.__setattr__(self, "determinant", _finite(self.determinant, "determinant"))
        object.__setattr__(
            self, "orthonormality_error", _finite(self.orthonormality_error, "orthonormality_error")
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "source_frame": self.source_frame,
            "current_frame": self.current_frame,
            "source_to_current": [list(row) for row in self.source_to_current],
            "provider_original_to_transformed": [
                list(row) for row in self.provider_original_to_transformed
            ],
            "provider_transformed_to_original": [
                list(row) for row in self.provider_transformed_to_original
            ],
            "method": self.method,
            "metrics": _thaw(self.metrics),
            "fingerprints": _thaw(self.fingerprints),
            "precision_profile": _thaw(self.precision_profile),
            "thresholds": _thaw(self.thresholds),
            "determinant": self.determinant,
            "orthonormality_error": self.orthonormality_error,
        }


@dataclass(frozen=True, slots=True)
class OrientationEvidenceV1:
    model_version: str
    adapter_name: str
    adapter_version: str
    source: SourceIdentity
    source_scope: StructureScope
    source_geometry: PlanarGeometryEvidence
    current_scope: StructureScope
    mapping: CoordinateMapping
    current_geometry: PlanarGeometryEvidence
    geometric_confidence: str
    warnings: tuple[ImportMessage, ...] = ()
    raw_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("model_version", "adapter_name", "adapter_version", "geometric_confidence"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "warnings", tuple(sorted(self.warnings, key=lambda x: x.code)))
        object.__setattr__(self, "raw_metadata", _json_safe(self.raw_metadata, "raw_metadata"))

    def as_dict(self) -> dict[str, object]:
        return {
            "model_version": self.model_version,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "source": self.source.as_dict(),
            "source_scope": self.source_scope.as_dict(),
            "source_geometry": self.source_geometry.as_dict(),
            "current_scope": self.current_scope.as_dict(),
            "coordinate_mapping": self.mapping.as_dict(),
            "current_geometry": self.current_geometry.as_dict(),
            "geometric_confidence": self.geometric_confidence,
            "warnings": [item.as_dict() for item in self.warnings],
            "raw_metadata": _thaw(self.raw_metadata),
        }


@dataclass(frozen=True, slots=True)
class OrientationPayload:
    role: str
    content: bytes
    media_type: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    retrieval_verified: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _text(self.role, "payload role"))
        if not isinstance(self.content, bytes):
            raise OrientationError("payload content must be bytes.")


@dataclass(frozen=True, slots=True)
class OrientationPayloadSet:
    primary: OrientationPayload
    companions: tuple[OrientationPayload, ...] = ()


@dataclass(frozen=True, slots=True)
class StructureContext:
    pdb_payload: bytes
    structure_id: str | None
    model_id: int
    biological_assembly: str | None = None
    coordinate_frame: str = "current_model"

    def __post_init__(self) -> None:
        if not isinstance(self.pdb_payload, bytes):
            raise OrientationError("StructureContext.pdb_payload must be bytes.")
        if isinstance(self.model_id, bool) or self.model_id < 1:
            raise OrientationError("StructureContext.model_id must be a positive integer.")
        object.__setattr__(
            self, "structure_id", _text(self.structure_id, "structure_id", optional=True)
        )
        object.__setattr__(
            self,
            "biological_assembly",
            _text(self.biological_assembly, "biological_assembly", optional=True),
        )
        object.__setattr__(
            self, "coordinate_frame", _text(self.coordinate_frame, "coordinate_frame")
        )


@dataclass(frozen=True, slots=True)
class OrientationImportResult:
    status: ImportStatus
    source: SourceIdentity | None = None
    evidence: OrientationEvidenceV1 | None = None
    membrane: PlanarMembrane | None = None
    messages: tuple[ImportMessage, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"imported", "partial", "rejected", "unsupported"}:
            raise OrientationError(f"invalid import status {self.status!r}.")
        if self.status == "imported" and (self.evidence is None or self.membrane is None):
            raise OrientationError("imported result requires evidence and a membrane.")
        if self.status == "imported":
            validate_membrane_geometry(self.membrane, self.evidence.current_geometry)
        if self.status != "imported" and self.membrane is not None:
            raise OrientationError(
                "partial/rejected/unsupported results cannot contain a membrane."
            )
        object.__setattr__(self, "messages", tuple(self.messages))

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source": None if self.source is None else self.source.as_dict(),
            "evidence": None if self.evidence is None else self.evidence.as_dict(),
            "messages": [item.as_dict() for item in self.messages],
        }


def validate_membrane_geometry(membrane: PlanarMembrane, geometry: PlanarGeometryEvidence) -> None:
    """Require one numerical geometry across the resolved domain and report evidence."""

    checks = (
        (membrane.center, geometry.center, "centre"),
        (membrane.normal, geometry.normal, "normal"),
    )
    for actual, expected, label in checks:
        if any(
            not math.isclose(a, b, rel_tol=0.0, abs_tol=GEOMETRY_MATCH_TOLERANCE)
            for a, b in zip(actual, expected, strict=True)
        ):
            raise OrientationError(
                f"resolved membrane {label} does not match orientation evidence."
            )
    scalar_checks = (
        (membrane.lower_offset, geometry.lower_offset, "lower_offset"),
        (membrane.upper_offset, geometry.upper_offset, "upper_offset"),
        (membrane.interface_width, geometry.interface_width, "interface_width"),
    )
    for actual, expected, label in scalar_checks:
        if expected is None or not math.isclose(
            actual, expected, rel_tol=0.0, abs_tol=GEOMETRY_MATCH_TOLERANCE
        ):
            raise OrientationError(
                f"resolved membrane {label} does not match orientation evidence."
            )
