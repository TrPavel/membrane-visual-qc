"""Pure-Python geometry for a single planar membrane."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import TypeAlias

from .errors import OrientationError

Vector3: TypeAlias = tuple[float, float, float]
NORMAL_ZERO_TOLERANCE = 1e-12


def _finite_float(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise OrientationError(f"{label} must be a finite number, not a boolean.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OrientationError(f"{label} must be a finite number.") from exc
    if not math.isfinite(number):
        raise OrientationError(f"{label} must be finite.")
    return _canonical_zero(number)


def vector3(value: object, label: str = "vector") -> Vector3:
    """Return a validated immutable three-dimensional vector."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 3:
        raise OrientationError(f"{label} must contain exactly three finite numbers.")
    return (
        _finite_float(value[0], f"{label}[0]"),
        _finite_float(value[1], f"{label}[1]"),
        _finite_float(value[2], f"{label}[2]"),
    )


def add(left: Vector3, right: Vector3) -> Vector3:
    return left[0] + right[0], left[1] + right[1], left[2] + right[2]


def subtract(left: Vector3, right: Vector3) -> Vector3:
    return left[0] - right[0], left[1] - right[1], left[2] - right[2]


def scale(vector: Vector3, factor: float) -> Vector3:
    return vector[0] * factor, vector[1] * factor, vector[2] * factor


def dot(left: Vector3, right: Vector3) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def norm(vector: Vector3) -> float:
    return math.sqrt(dot(vector, vector))


def normalize(vector: object, label: str = "normal") -> Vector3:
    checked = vector3(vector, label)
    length = norm(checked)
    if length <= NORMAL_ZERO_TOLERANCE:
        raise OrientationError(f"{label} length must be greater than {NORMAL_ZERO_TOLERANCE:g}.")
    return (
        _canonical_zero(checked[0] / length),
        _canonical_zero(checked[1] / length),
        _canonical_zero(checked[2] / length),
    )


@dataclass(frozen=True, slots=True)
class PlanarMembrane:
    """Immutable geometry and provenance for one planar membrane."""

    center: Vector3
    normal: Vector3
    lower_offset: float
    upper_offset: float
    interface_width: float
    source: str
    source_version: str | None = None
    confidence: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        center = vector3(self.center, "center")
        normal = normalize(self.normal, "normal")
        lower = _finite_float(self.lower_offset, "lower_offset")
        upper = _finite_float(self.upper_offset, "upper_offset")
        width = _finite_float(self.interface_width, "interface_width")
        if lower >= upper:
            raise OrientationError("lower_offset must be smaller than upper_offset.")
        if width < 0:
            raise OrientationError("interface_width must be non-negative.")
        if not isinstance(self.source, str):
            raise OrientationError("orientation source must be text.")
        source = self.source.strip()
        if not source:
            raise OrientationError("orientation source must not be empty.")
        source_version = _optional_text(self.source_version, "source_version")
        confidence = _optional_text(self.confidence, "confidence")
        if isinstance(self.warnings, (str, bytes)) or any(
            not isinstance(item, str) for item in self.warnings
        ):
            raise OrientationError("orientation warnings must be a sequence of strings.")
        warnings = tuple(item.strip() for item in self.warnings)
        if any(not item for item in warnings):
            raise OrientationError("orientation warnings must not contain empty strings.")
        if not isinstance(self.metadata, Mapping):
            raise OrientationError("metadata must be a JSON-safe mapping.")
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "normal", normal)
        object.__setattr__(self, "lower_offset", lower)
        object.__setattr__(self, "upper_offset", upper)
        object.__setattr__(self, "interface_width", width)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "source_version", source_version)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))
        object.__setattr__(self, "warnings", warnings)

    def as_dict(self) -> dict[str, object]:
        return {
            "geometry": "planar",
            "source": self.source,
            "source_version": self.source_version,
            "confidence": self.confidence,
            "center": list(self.center),
            "normal": list(self.normal),
            "lower_offset": self.lower_offset,
            "upper_offset": self.upper_offset,
            "interface_width": self.interface_width,
            "metadata": _thaw_json(self.metadata),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class PointMembraneMeasurement:
    signed_distance: float
    absolute_center_distance: float
    nearest_boundary_distance: float
    outside_distance: float
    classification: str
    normalized_depth: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "signed_distance": self.signed_distance,
            "absolute_center_distance": self.absolute_center_distance,
            "nearest_boundary_distance": self.nearest_boundary_distance,
            "outside_distance": self.outside_distance,
            "classification": self.classification,
            "normalized_depth": self.normalized_depth,
        }


def signed_distance(point: object, membrane: PlanarMembrane) -> float:
    coordinate = vector3(point, "point")
    return _canonical_zero(dot(subtract(coordinate, membrane.center), membrane.normal))


def classify_signed_distance(distance: float, membrane: PlanarMembrane) -> str:
    distance = _finite_float(distance, "signed distance")
    lower, upper, width = (
        membrane.lower_offset,
        membrane.upper_offset,
        membrane.interface_width,
    )
    if lower <= distance <= upper:
        return "core"
    if lower - width <= distance < lower:
        return "lower_interface"
    if upper < distance <= upper + width:
        return "upper_interface"
    return "outside"


def measure_point(point: object, membrane: PlanarMembrane) -> PointMembraneMeasurement:
    distance = signed_distance(point, membrane)
    lower, upper = membrane.lower_offset, membrane.upper_offset
    classification = classify_signed_distance(distance, membrane)
    nearest = min(abs(distance - lower), abs(distance - upper))
    outside = max(lower - distance, distance - upper, 0.0)
    depth = _normalized_depth(distance, membrane, classification)
    return PointMembraneMeasurement(
        distance,
        abs(distance),
        _canonical_zero(nearest),
        _canonical_zero(outside),
        classification,
        depth,
    )


def stable_plane_basis(normal: object) -> tuple[Vector3, Vector3]:
    unit = normalize(normal, "normal")
    axes: tuple[Vector3, Vector3, Vector3] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    reference = min(axes, key=lambda axis: abs(dot(unit, axis)))
    first = normalize(cross(unit, reference), "plane basis")
    second = normalize(cross(unit, first), "plane basis")
    return first, second


def orthonormal_basis(normal: object) -> tuple[Vector3, Vector3]:
    return stable_plane_basis(normal)


def boundary_point(membrane: PlanarMembrane, offset: float) -> Vector3:
    return add(membrane.center, scale(membrane.normal, _finite_float(offset, "boundary offset")))


def legacy_global_z(
    zmin: float,
    zmax: float,
    interface_width: float = 3.0,
    *,
    warnings: Sequence[str] = (),
) -> PlanarMembrane:
    lower, upper = sorted((_finite_float(zmin, "zmin"), _finite_float(zmax, "zmax")))
    return PlanarMembrane(
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        lower,
        upper,
        interface_width,
        "manual_global_z",
        warnings=tuple(warnings),
    )


def _normalized_depth(
    distance: float, membrane: PlanarMembrane, classification: str
) -> float | None:
    if classification != "core":
        return None
    lower, upper = membrane.lower_offset, membrane.upper_offset
    if not lower < 0.0 < upper:
        return None
    depth = (distance - lower) / -lower if distance <= 0.0 else (upper - distance) / upper
    return _canonical_zero(depth)


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise OrientationError(f"{label} must be text when supplied.")
    text = value.strip()
    if not text:
        raise OrientationError(f"{label} must be non-empty when supplied.")
    return text


def _freeze_mapping(value: Mapping[str, object], path: str) -> Mapping[str, object]:
    frozen: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise OrientationError(f"{path} keys must be strings.")
        frozen[key] = _freeze_json(item, f"{path}.{key}")
    return MappingProxyType(frozen)


def _freeze_json(value: object, path: str) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OrientationError(f"{path} must contain only finite JSON numbers.")
        return _canonical_zero(value)
    if isinstance(value, Mapping):
        return _freeze_mapping(value, path)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, f"{path}[{index}]") for index, item in enumerate(value))
    raise OrientationError(f"{path} contains a value that is not JSON-safe.")


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_zero(value: float) -> float:
    return 0.0 if value == 0.0 else value
