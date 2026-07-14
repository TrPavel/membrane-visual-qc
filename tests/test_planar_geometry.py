import math

import pytest

from membrane_vqc.orientation import PlanarMembrane, add, dot, measure_point, scale
from membrane_vqc.orientation import orthonormal_basis

ABS_TOL = 1e-7


def plane(center=(0, 0, 0), normal=(0, 0, 1), lower=-15, upper=15, width=3):
    return PlanarMembrane(center, normal, lower, upper, width, "test")


def assert_equivalent(actual, expected):
    assert actual.signed_distance == pytest.approx(expected.signed_distance, abs=ABS_TOL)
    assert actual.absolute_center_distance == pytest.approx(
        expected.absolute_center_distance, abs=ABS_TOL
    )
    assert actual.nearest_boundary_distance == pytest.approx(
        expected.nearest_boundary_distance, abs=ABS_TOL
    )
    assert actual.outside_distance == pytest.approx(expected.outside_distance, abs=ABS_TOL)
    if expected.normalized_depth is None:
        assert actual.normalized_depth is None
    else:
        assert actual.normalized_depth == pytest.approx(expected.normalized_depth, abs=ABS_TOL)
    assert actual.classification == expected.classification


def test_global_z_and_x_axis_measure_same_geometry():
    z_result = measure_point((4, 5, 6), plane())
    x_result = measure_point((6, 4, 5), plane(normal=(1, 0, 0)))
    assert x_result == z_result
    assert z_result.normalized_depth == pytest.approx(0.6)


def test_diagonal_normal_is_normalized():
    result = measure_point((1, 1, 1), plane(normal=(1, 1, 1), lower=-2, upper=2))
    assert result.signed_distance == pytest.approx(math.sqrt(3), abs=ABS_TOL)
    assert result.normalized_depth == pytest.approx((2 - math.sqrt(3)) / 2, abs=ABS_TOL)


def test_joint_translation_is_invariant():
    original = plane((1, -2, 3), (1, 2, 3), -4, 7)
    point, translation = (4, 5, 6), (20, -10, 8)
    moved = plane(add(original.center, translation), original.normal, -4, 7)
    assert_equivalent(measure_point(add(point, translation), moved), measure_point(point, original))


def test_joint_rotation_is_invariant():
    def rotate(vector):
        return -vector[1], vector[0], vector[2]

    original = plane((1, 2, 3), (1, 2, 3), -4, 7)
    point = (8, -3, 2)
    rotated = plane(rotate(original.center), rotate(original.normal), -4, 7)
    assert_equivalent(measure_point(rotate(point), rotated), measure_point(point, original))


@pytest.mark.parametrize("distance", [-20, -15, -4, 0, 7, 15, 19])
def test_normal_reversal_with_swapped_offsets(distance):
    original = plane(lower=-15, upper=7, width=4)
    reversed_plane = plane(normal=(0, 0, -1), lower=-7, upper=15, width=4)
    before = measure_point((0, 0, distance), original)
    after = measure_point((0, 0, distance), reversed_plane)
    assert after.signed_distance == pytest.approx(-before.signed_distance)
    assert after.nearest_boundary_distance == pytest.approx(before.nearest_boundary_distance)
    assert after.outside_distance == pytest.approx(before.outside_distance)
    assert after.normalized_depth == before.normalized_depth
    expected = {"lower_interface": "upper_interface", "upper_interface": "lower_interface"}
    assert after.classification == expected.get(before.classification, before.classification)


def test_asymmetric_side_specific_depth():
    membrane = plane(lower=-10, upper=20)
    depths = [
        measure_point((0, 0, distance), membrane).normalized_depth
        for distance in (-10, -5, 0, 10, 20)
    ]
    assert depths == [0, 0.5, 1, 0.5, 0]


@pytest.mark.parametrize(
    ("distance", "classification", "nearest", "outside", "depth"),
    [
        (-18, "lower_interface", 3, 3, None),
        (-15, "core", 0, 0, 0),
        (0, "core", 15, 0, 1),
        (15, "core", 0, 0, 0),
        (18, "upper_interface", 3, 3, None),
        (-18.0001, "outside", 3.0001, 3.0001, None),
        (18.0001, "outside", 3.0001, 3.0001, None),
    ],
)
def test_exact_boundaries_interfaces_and_distances(
    distance, classification, nearest, outside, depth
):
    result = measure_point((0, 0, distance), plane())
    assert result.classification == classification
    assert result.nearest_boundary_distance == pytest.approx(nearest)
    assert result.outside_distance == pytest.approx(outside)
    assert result.normalized_depth == depth


def test_non_bracketing_slab_has_no_normalized_depth():
    result = measure_point((0, 0, 10), plane(lower=5, upper=15))
    assert result.classification == "core"
    assert result.normalized_depth is None


@pytest.mark.parametrize("normal", [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1e-14, 0), (1, 1, 1)])
def test_basis_is_stable_and_orthonormal_near_axes(normal):
    membrane = plane(normal=normal)
    first, second = orthonormal_basis(membrane.normal)
    assert dot(first, membrane.normal) == pytest.approx(0, abs=ABS_TOL)
    assert dot(second, membrane.normal) == pytest.approx(0, abs=ABS_TOL)
    assert dot(first, second) == pytest.approx(0, abs=ABS_TOL)
    assert dot(first, first) == pytest.approx(1, abs=ABS_TOL)
    assert dot(second, second) == pytest.approx(1, abs=ABS_TOL)


def test_in_plane_center_shift_does_not_change_distance():
    assert measure_point((1000, -900, 35), plane(center=(10, 20, 30))).signed_distance == 5


def test_point_constructed_along_normal_has_requested_distance():
    membrane = plane((1, 2, 3), (1, 2, 3))
    point = add(membrane.center, scale(membrane.normal, 8.5))
    assert measure_point(point, membrane).signed_distance == pytest.approx(8.5, abs=ABS_TOL)
