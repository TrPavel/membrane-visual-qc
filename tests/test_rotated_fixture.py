from demo.rotated_1ubq_transform import transform_coordinates, transform_point


def test_rotated_1ubq_transform_matches_documented_equations():
    assert transform_point(1.0, 2.0, 3.0) == (13.0, -3.0, 2.0)
    coordinates = [[1.0, 2.0, 3.0], [-4.0, 5.0, -6.0]]

    transformed = transform_coordinates(coordinates)

    assert transformed == [(13.0, -3.0, 2.0), (4.0, 0.0, 7.0)]
    assert coordinates == [[1.0, 2.0, 3.0], [-4.0, 5.0, -6.0]]
