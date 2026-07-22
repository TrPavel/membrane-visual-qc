"""Provider-neutral, no-fit comparison of two resolved planar orientations."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from .errors import OrientationError
from .orientation_sources import PlanarGeometryEvidence, StructureScope

COMPARISON_METHOD = "planar_axis_geometry_v1"
ANGLE_THRESHOLD_DEGREES = 5.0
CENTER_THRESHOLD_ANGSTROM = 2.0
THICKNESS_THRESHOLD_ANGSTROM = 2.0

ComparisonBand = Literal[
    "geometrically_close_under_reviewed_tolerance",
    "measurable_geometric_difference",
    "not_comparable",
]


def _safe_text(value: object, label: str) -> str:
    text = str(value).strip()
    if not text or len(text) > 256 or any(ord(character) < 32 for character in text):
        raise OrientationError(f"{label} must be non-empty bounded text without controls.")
    return text


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OrientationError(f"{label} must be a finite number.")
    result = float(value)
    if not math.isfinite(result):
        raise OrientationError(f"{label} must be a finite number.")
    return 0.0 if result == 0.0 else result


@dataclass(frozen=True, slots=True)
class ComparisonThresholds:
    """Reviewed geometric flags, not biological correctness thresholds."""

    normal_axis_angle_degrees: float = ANGLE_THRESHOLD_DEGREES
    center_displacement_angstrom: float = CENTER_THRESHOLD_ANGSTROM
    thickness_difference_angstrom: float = THICKNESS_THRESHOLD_ANGSTROM

    def __post_init__(self) -> None:
        for field in (
            "normal_axis_angle_degrees",
            "center_displacement_angstrom",
            "thickness_difference_angstrom",
        ):
            value = _finite(getattr(self, field), field)
            if value <= 0:
                raise OrientationError(f"{field} must be positive.")
            object.__setattr__(self, field, value)

    def as_dict(self) -> dict[str, object]:
        return {
            "normal_axis_angle_degrees": self.normal_axis_angle_degrees,
            "center_displacement_angstrom": self.center_displacement_angstrom,
            "thickness_difference_angstrom": self.thickness_difference_angstrom,
            "interpretation": "review_flags_not_biological_truth",
        }


@dataclass(frozen=True, slots=True)
class ComparableOrientation:
    """Small provider-neutral projection of independently evaluated evidence."""

    source_key: str
    applicable: bool
    scope: StructureScope | None = None
    geometry: PlanarGeometryEvidence | None = None
    applicability_method: str | None = None
    matched_atom_count: int | None = None
    matched_residue_count: int | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_key", _safe_text(self.source_key, "source_key"))
        if type(self.applicable) is not bool:
            raise OrientationError("applicable must be boolean.")
        if self.applicable and (self.scope is None or self.geometry is None):
            raise OrientationError("Applicable evidence requires scope and current geometry.")
        if not self.applicable and self.geometry is not None:
            raise OrientationError("Non-applicable evidence cannot carry resolved geometry.")
        if self.applicability_method is not None:
            object.__setattr__(
                self,
                "applicability_method",
                _safe_text(self.applicability_method, "applicability_method"),
            )
        for field in ("matched_atom_count", "matched_residue_count"):
            value = getattr(self, field)
            if value is not None and (type(value) is not int or value < 0):
                raise OrientationError(f"{field} must be a non-negative integer or None.")
        object.__setattr__(
            self,
            "warnings",
            tuple(sorted({_safe_text(item, "warning") for item in self.warnings})),
        )


@dataclass(frozen=True, slots=True)
class ComparisonMetrics:
    normal_axis_angle_degrees: float
    second_normal_sign: int
    center_displacement_angstrom: float
    center_along_first_normal_angstrom: float
    center_along_second_normal_angstrom: float
    center_along_reviewed_direction_angstrom: float
    center_perpendicular_to_reviewed_direction_angstrom: float
    first_thickness_angstrom: float
    second_thickness_angstrom: float
    thickness_difference_angstrom: float
    lower_offset_difference_angstrom: float
    upper_offset_difference_angstrom: float

    def as_dict(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class OrientationComparisonResult:
    method: str
    first_source: str
    second_source: str
    comparable: bool
    band: ComparisonBand
    thresholds: ComparisonThresholds
    metrics: ComparisonMetrics | None
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    consensus: bool = False
    ranking: bool = False
    preferred_source: None = None
    biological_verdict: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "method_version": "1",
            "first_source": self.first_source,
            "second_source": self.second_source,
            "comparable": self.comparable,
            "band": self.band,
            "thresholds": self.thresholds.as_dict(),
            "metrics": None if self.metrics is None else self.metrics.as_dict(),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "interpretation": {
                "consensus": self.consensus,
                "ranking": self.ranking,
                "preferred_source": self.preferred_source,
                "biological_verdict": self.biological_verdict,
                "statement": (
                    "This is a geometric comparison for review. It does not select a source, "
                    "create a consensus orientation, rank providers, or make a biological verdict."
                ),
            },
        }


def compare_orientations(
    first: ComparableOrientation,
    second: ComparableOrientation,
    *,
    thresholds: ComparisonThresholds | None = None,
) -> OrientationComparisonResult:
    """Compare two independently applicable planes without fitting or mutation."""

    reviewed = thresholds or ComparisonThresholds()
    reasons = _noncomparability_reasons(first, second)
    warnings = tuple(sorted(set((*first.warnings, *second.warnings))))
    if reasons:
        return OrientationComparisonResult(
            COMPARISON_METHOD,
            first.source_key,
            second.source_key,
            False,
            "not_comparable",
            reviewed,
            None,
            tuple(reasons),
            warnings,
        )

    assert first.geometry is not None and second.geometry is not None
    metrics = _metrics(first.geometry, second.geometry)
    close = (
        metrics.normal_axis_angle_degrees <= reviewed.normal_axis_angle_degrees
        # A provider may choose any in-plane anchor for the same infinite
        # midplane. The full anchor displacement remains a transparent raw
        # metric, but only its reviewed-direction component represents slab
        # separation for this tolerance band.
        and abs(metrics.center_along_reviewed_direction_angstrom)
        <= reviewed.center_displacement_angstrom
        and abs(metrics.thickness_difference_angstrom) <= reviewed.thickness_difference_angstrom
    )
    return OrientationComparisonResult(
        COMPARISON_METHOD,
        first.source_key,
        second.source_key,
        True,
        (
            "geometrically_close_under_reviewed_tolerance"
            if close
            else "measurable_geometric_difference"
        ),
        reviewed,
        metrics,
        (),
        warnings,
    )


def _noncomparability_reasons(
    first: ComparableOrientation, second: ComparableOrientation
) -> list[str]:
    reasons: list[str] = []
    if not first.applicable:
        reasons.append("FIRST_SOURCE_NOT_APPLICABLE")
    if not second.applicable:
        reasons.append("SECOND_SOURCE_NOT_APPLICABLE")
    if reasons:
        return reasons
    assert first.scope is not None and second.scope is not None
    if first.scope.coordinate_frame != second.scope.coordinate_frame:
        reasons.append("COORDINATE_FRAME_MISMATCH")
    if (
        first.scope.structure_id
        and second.scope.structure_id
        and (first.scope.structure_id.casefold() != second.scope.structure_id.casefold())
    ):
        reasons.append("STRUCTURE_ID_MISMATCH")
    if first.scope.model_id != second.scope.model_id:
        reasons.append("MODEL_MISMATCH")
    if (
        first.scope.biological_assembly is not None
        and second.scope.biological_assembly is not None
        and first.scope.biological_assembly != second.scope.biological_assembly
    ):
        reasons.append("ASSEMBLY_MISMATCH")
    if first.scope.chains != second.scope.chains:
        reasons.append("CHAIN_SCOPE_MISMATCH")
    return reasons


def _metrics(first: PlanarGeometryEvidence, second: PlanarGeometryEvidence) -> ComparisonMetrics:
    dot = sum(a * b for a, b in zip(first.normal, second.normal, strict=True))
    clamped_axis_dot = min(1.0, max(0.0, abs(dot)))
    angle = math.degrees(math.acos(clamped_axis_dot))
    sign = -1 if dot < 0.0 else 1
    aligned_second = tuple(sign * value for value in second.normal)
    second_lower, second_upper = (
        (second.lower_offset, second.upper_offset)
        if sign == 1
        else (-second.upper_offset, -second.lower_offset)
    )
    delta = tuple(b - a for a, b in zip(first.center, second.center, strict=True))
    distance = math.sqrt(sum(value * value for value in delta))
    along_first = sum(d * n for d, n in zip(delta, first.normal, strict=True))
    along_second = sum(d * n for d, n in zip(delta, aligned_second, strict=True))
    bisector = tuple(a + b for a, b in zip(first.normal, aligned_second, strict=True))
    bisector_norm = math.sqrt(sum(value * value for value in bisector))
    if bisector_norm <= 1e-15:  # defensive; sign alignment makes this unreachable for unit vectors
        raise OrientationError("Reviewed comparison direction is numerically undefined.")
    direction = tuple(value / bisector_norm for value in bisector)
    along_reviewed = sum(d * n for d, n in zip(delta, direction, strict=True))
    perpendicular = math.sqrt(max(0.0, distance * distance - along_reviewed * along_reviewed))
    first_thickness = first.upper_offset - first.lower_offset
    second_thickness = second_upper - second_lower
    values = (
        angle,
        distance,
        along_first,
        along_second,
        along_reviewed,
        perpendicular,
        first_thickness,
        second_thickness,
        second_thickness - first_thickness,
        along_reviewed + second_lower - first.lower_offset,
        along_reviewed + second_upper - first.upper_offset,
    )
    if not all(math.isfinite(value) for value in values):
        raise OrientationError("Comparison produced a non-finite metric.")
    normalized = tuple(0.0 if value == 0.0 else value for value in values)
    return ComparisonMetrics(
        normalized[0],
        sign,
        *normalized[1:],
    )
