import math

import pytest

from membrane_vqc.errors import OrientationError
from membrane_vqc.orientation_comparison import (
    ComparableOrientation,
    ComparisonThresholds,
    compare_orientations,
)
from membrane_vqc.orientation_sources import PlanarGeometryEvidence, StructureScope


def _scope(*, frame="pymol_current_object", assembly="1", chains=("A",)):
    return StructureScope("1abc", "1", assembly, chains, "legacy_pdb", frame)


def _geometry(*, center=(0.0, 0.0, 0.0), normal=(0.0, 0.0, 1.0), lower=-10.0, upper=10.0):
    return PlanarGeometryEvidence(center, normal, lower, upper, 2.0, "pymol_current_object")


def _source(key, geometry=None, *, applicable=True, scope=None):
    return ComparableOrientation(
        key,
        applicable,
        _scope() if scope is None and applicable else scope,
        (_geometry() if geometry is None else geometry) if applicable else None,
        "direct_coordinate_evidence" if applicable else None,
        100 if applicable else None,
        20 if applicable else None,
    )


def test_identical_planes_are_close_with_finite_zero_metrics():
    result = compare_orientations(_source("pdbtm"), _source("opm"))
    assert result.comparable is True
    assert result.band == "geometrically_close_under_reviewed_tolerance"
    assert result.metrics.normal_axis_angle_degrees == 0.0
    assert result.metrics.center_displacement_angstrom == 0.0
    assert all(
        math.isfinite(value)
        for value in result.metrics.as_dict().values()
        if isinstance(value, float)
    )


def test_opposite_normals_and_reversed_offsets_are_the_same_physical_plane():
    first = _source("pdbtm", _geometry(lower=-10.0, upper=12.0))
    second = _source("opm", _geometry(normal=(0.0, 0.0, -1.0), lower=-12.0, upper=10.0))
    metrics = compare_orientations(first, second).metrics
    assert metrics.second_normal_sign == -1
    assert metrics.normal_axis_angle_degrees == 0.0
    assert metrics.lower_offset_difference_angstrom == 0.0
    assert metrics.upper_offset_difference_angstrom == 0.0


@pytest.mark.parametrize("angle", [1e-9, 179.999999999])
def test_near_parallel_and_antiparallel_angles_are_numerically_stable(angle):
    radians = math.radians(angle)
    normal = (math.sin(radians), 0.0, math.cos(radians))
    result = compare_orientations(_source("pdbtm"), _source("opm", _geometry(normal=normal)))
    assert result.comparable
    assert 0.0 <= result.metrics.normal_axis_angle_degrees <= 90.0
    assert math.isfinite(result.metrics.center_perpendicular_to_reviewed_direction_angstrom)


def test_shift_tilt_and_thickness_are_continuous_raw_metrics():
    angle = math.radians(10.0)
    second = _geometry(
        center=(3.0, 4.0, 1.0),
        normal=(math.sin(angle), 0.0, math.cos(angle)),
        lower=-12.0,
        upper=12.0,
    )
    result = compare_orientations(_source("pdbtm"), _source("opm", second))
    assert result.band == "measurable_geometric_difference"
    assert result.metrics.normal_axis_angle_degrees == pytest.approx(10.0)
    assert result.metrics.center_displacement_angstrom == pytest.approx(math.sqrt(26.0))
    assert result.metrics.thickness_difference_angstrom == 4.0


def test_in_plane_anchor_translation_does_not_change_close_slab_band():
    second = _geometry(center=(100.0, -75.0, 0.0))

    result = compare_orientations(_source("pdbtm"), _source("opm", second))

    assert result.band == "geometrically_close_under_reviewed_tolerance"
    assert result.metrics.center_displacement_angstrom == pytest.approx(125.0)
    assert result.metrics.center_along_reviewed_direction_angstrom == pytest.approx(0.0)
    assert result.metrics.lower_offset_difference_angstrom == pytest.approx(0.0)
    assert result.metrics.upper_offset_difference_angstrom == pytest.approx(0.0)


def test_axial_center_shift_is_reflected_in_boundaries_and_band():
    second = _geometry(center=(0.0, 0.0, 3.0))

    result = compare_orientations(_source("pdbtm"), _source("opm", second))

    assert result.band == "measurable_geometric_difference"
    assert result.metrics.lower_offset_difference_angstrom == pytest.approx(3.0)
    assert result.metrics.upper_offset_difference_angstrom == pytest.approx(3.0)


def test_review_thresholds_are_inclusive_and_described_as_nonbiological():
    angle = math.radians(5.0)
    second = _geometry(
        center=(2.0, 0.0, 0.0),
        normal=(math.sin(angle), 0.0, math.cos(angle)),
        lower=-11.0,
        upper=11.0,
    )
    result = compare_orientations(_source("pdbtm"), _source("opm", second))
    assert result.band == "geometrically_close_under_reviewed_tolerance"
    assert result.thresholds.as_dict()["interpretation"] == "review_flags_not_biological_truth"


@pytest.mark.parametrize(
    ("scope", "reason"),
    [
        (_scope(frame="other"), "COORDINATE_FRAME_MISMATCH"),
        (_scope(assembly="2"), "ASSEMBLY_MISMATCH"),
        (_scope(chains=("B",)), "CHAIN_SCOPE_MISMATCH"),
    ],
)
def test_scope_mismatches_are_not_comparable(scope, reason):
    result = compare_orientations(_source("pdbtm"), _source("opm", scope=scope))
    assert not result.comparable
    assert result.metrics is None
    assert reason in result.reasons


def test_one_or_neither_applicable_is_explicitly_not_comparable():
    one = compare_orientations(_source("pdbtm"), _source("opm", applicable=False))
    neither = compare_orientations(
        _source("pdbtm", applicable=False), _source("opm", applicable=False)
    )
    assert one.reasons == ("SECOND_SOURCE_NOT_APPLICABLE",)
    assert neither.reasons == (
        "FIRST_SOURCE_NOT_APPLICABLE",
        "SECOND_SOURCE_NOT_APPLICABLE",
    )
    assert neither.as_dict()["interpretation"] == {
        "consensus": False,
        "ranking": False,
        "preferred_source": None,
        "biological_verdict": False,
        "statement": (
            "This is a geometric comparison for review. It does not select a source, "
            "create a consensus orientation, rank providers, or make a biological verdict."
        ),
    }


def test_invalid_nonfinite_input_and_thresholds_are_rejected():
    with pytest.raises(OrientationError):
        _geometry(center=(math.nan, 0.0, 0.0))
    with pytest.raises(OrientationError):
        ComparisonThresholds(center_displacement_angstrom=math.inf)


def test_comparison_is_deterministic_and_does_not_mutate_inputs():
    first = _source("pdbtm")
    second = _source("opm", _geometry(center=(1.0, 2.0, 3.0)))
    before = (first.geometry, second.geometry)
    assert compare_orientations(first, second) == compare_orientations(first, second)
    assert (first.geometry, second.geometry) == before
