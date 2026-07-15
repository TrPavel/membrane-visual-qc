"""Strict, local-only I/O for versioned planar-orientation documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .errors import OrientationError
from .orientation import PlanarMembrane


SCHEMA_VERSION = "1.0"
GEOMETRY = "planar"

_REQUIRED_FIELDS = {
    "schema_version",
    "geometry",
    "center",
    "normal",
    "lower_offset",
    "upper_offset",
    "interface_width",
    "source",
}
_OPTIONAL_FIELDS = {"source_version", "confidence", "metadata"}
_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS


@dataclass(frozen=True)
class OrientationFileProvenance:
    """Identity of a local orientation document, separate from structure provenance."""

    basename: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {"basename": self.basename, "sha256": self.sha256}


@dataclass(frozen=True)
class LoadedOrientation:
    """A parsed membrane model together with provenance of its orientation file."""

    membrane: PlanarMembrane
    orientation_path: str
    sha256: str
    schema_version: str

    @property
    def orientation(self) -> PlanarMembrane:
        """Alias useful to callers which name the domain object by its report role."""
        return self.membrane

    @property
    def provenance(self) -> OrientationFileProvenance:
        """Return orientation-file provenance without adding it to structure input data."""
        return OrientationFileProvenance(self.orientation_path, self.sha256)


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OrientationError(f"duplicate JSON field: {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_number(value: str) -> None:
    raise OrientationError(f"non-finite JSON number is not allowed: {value}")


def _loads_document(text: str, *, source_name: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_json_object,
            parse_constant=_reject_nonstandard_number,
        )
    except OrientationError:
        raise
    except json.JSONDecodeError as exc:
        raise OrientationError(
            f"invalid orientation JSON in {source_name}: line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc


def _validate_json_value(value: Any, *, path: str) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise OrientationError(f"{path} must contain only finite numbers")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise OrientationError(f"{path} keys must be strings")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    raise OrientationError(f"{path} contains a non-JSON value of type {type(value).__name__}")


def _number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OrientationError(f"{field} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise OrientationError(f"{field} must be a finite number") from exc
    if not math.isfinite(result):
        raise OrientationError(f"{field} must be a finite number")
    return result


def _vector(value: Any, *, field: str) -> tuple[float, float, float]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) != 3
    ):
        raise OrientationError(f"{field} must be an array of exactly three finite numbers")
    components = tuple(
        _number(component, field=f"{field}[{index}]") for index, component in enumerate(value)
    )
    return components  # type: ignore[return-value]


def _nullable_string(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise OrientationError(f"{field} must be a string or null")
    return value


def parse_orientation(data: Any) -> PlanarMembrane:
    """Validate a decoded orientation document and build its pure domain model."""
    if not isinstance(data, Mapping):
        raise OrientationError("orientation document must be a JSON object")
    if any(not isinstance(key, str) for key in data):
        raise OrientationError("orientation document field names must be strings")

    fields = set(data)
    missing = sorted(_REQUIRED_FIELDS - fields)
    if missing:
        raise OrientationError(
            f"orientation document is missing required field(s): {', '.join(missing)}"
        )
    unknown = sorted(fields - _ALLOWED_FIELDS)
    if unknown:
        raise OrientationError(f"orientation document has unknown field(s): {', '.join(unknown)}")

    if data["schema_version"] != SCHEMA_VERSION:
        raise OrientationError(
            f"unsupported orientation schema_version {data['schema_version']!r}; "
            f"expected {SCHEMA_VERSION!r}"
        )
    if data["geometry"] != GEOMETRY:
        raise OrientationError(
            f"unsupported orientation geometry {data['geometry']!r}; expected {GEOMETRY!r}"
        )
    source = data["source"]
    if not isinstance(source, str) or not source.strip():
        raise OrientationError("source must be a non-empty string")

    metadata = data.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise OrientationError("metadata must be a JSON object")
    _validate_json_value(metadata, path="metadata")

    try:
        return PlanarMembrane(
            center=_vector(data["center"], field="center"),
            normal=_vector(data["normal"], field="normal"),
            lower_offset=_number(data["lower_offset"], field="lower_offset"),
            upper_offset=_number(data["upper_offset"], field="upper_offset"),
            interface_width=_number(data["interface_width"], field="interface_width"),
            source=source,
            source_version=_nullable_string(data.get("source_version"), field="source_version"),
            confidence=_nullable_string(data.get("confidence"), field="confidence"),
            metadata=dict(metadata),
        )
    except OrientationError:
        raise
    except (TypeError, ValueError) as exc:
        raise OrientationError(f"invalid planar orientation: {exc}") from exc


def orientation_to_dict(membrane: PlanarMembrane) -> dict[str, Any]:
    """Return the canonical versioned document for a planar membrane."""
    try:
        values = dict(membrane.as_dict())
    except (AttributeError, TypeError, ValueError) as exc:
        raise OrientationError("orientation object cannot be serialised safely") from exc

    document = {
        "schema_version": SCHEMA_VERSION,
        "geometry": GEOMETRY,
        "center": values.get("center"),
        "normal": values.get("normal"),
        "lower_offset": values.get("lower_offset"),
        "upper_offset": values.get("upper_offset"),
        "interface_width": values.get("interface_width"),
        "source": values.get("source"),
        "source_version": values.get("source_version"),
        "confidence": values.get("confidence"),
        "metadata": values.get("metadata", {}),
    }
    parse_orientation(document)
    return document


def dumps_orientation(membrane: PlanarMembrane) -> str:
    """Serialise deterministically as UTF-8-compatible JSON ending in one newline."""
    try:
        return (
            json.dumps(
                orientation_to_dict(membrane),
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    except (TypeError, ValueError) as exc:
        raise OrientationError(f"orientation cannot be encoded as JSON: {exc}") from exc


def write_orientation_file(membrane: PlanarMembrane, path: str | Path) -> Path:
    """Write a canonical orientation document using UTF-8 and Unix newlines."""
    destination = Path(path)
    try:
        destination.write_text(dumps_orientation(membrane), encoding="utf-8", newline="\n")
    except OSError as exc:
        raise OrientationError(f"could not write orientation file {destination}: {exc}") from exc
    return destination


def load_orientation_file(path: str | Path) -> LoadedOrientation:
    """Load a local JSON file and retain provenance of that orientation input only."""
    source = Path(path)
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise OrientationError(f"could not read orientation file {source}: {exc}") from exc
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OrientationError(f"orientation file {source} is not valid UTF-8") from exc

    membrane = parse_orientation(_loads_document(text, source_name=str(source)))
    return LoadedOrientation(
        membrane=membrane,
        orientation_path=source.name,
        sha256=hashlib.sha256(payload).hexdigest(),
        schema_version=SCHEMA_VERSION,
    )


def load_planar_membrane(path: str | Path) -> PlanarMembrane:
    """Convenience loader for callers which do not need file provenance."""
    return load_orientation_file(path).membrane
