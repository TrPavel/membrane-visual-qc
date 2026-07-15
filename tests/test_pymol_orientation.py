import sys
from types import ModuleType

import pytest

from membrane_vqc.membrane import AtomRecord
from membrane_vqc.orientation import PlanarMembrane, orthonormal_basis
from membrane_vqc.pymol_adapter import (
    create_membrane_planes,
    create_slab,
    projected_coordinates,
    projected_footprint,
)


def _membrane(**overrides):
    values = {
        "center": (1.0, 2.0, 3.0),
        "normal": (1.0, 1.0, 1.0),
        "lower_offset": -4.0,
        "upper_offset": 6.0,
        "interface_width": 3.0,
        "source": "test",
    }
    values.update(overrides)
    return PlanarMembrane(**values)


def _atom(x, y, z):
    return AtomRecord("model", "A", "1", "ALA", "CA", x, y, z)


def _point(center, axis_u, axis_v, u_value, v_value):
    return tuple(
        center[index] + u_value * axis_u[index] + v_value * axis_v[index] for index in range(3)
    )


def test_projected_coordinates_are_relative_to_membrane_center():
    membrane = _membrane()
    axis_u, axis_v = orthonormal_basis(membrane.normal)
    first = _point(membrane.center, axis_u, axis_v, -5.0, 7.0)
    second = _point(membrane.center, axis_u, axis_v, 3.0, -2.0)

    projected = projected_coordinates(membrane, [_atom(*first), _atom(*second)])

    assert projected[0] == pytest.approx((-5.0, 7.0))
    assert projected[1] == pytest.approx((3.0, -2.0))


def test_projected_footprint_uses_margin_and_minimum_size():
    membrane = _membrane(normal=(1.0, 0.0, 0.0))
    axis_u, axis_v = orthonormal_basis(membrane.normal)
    points = [
        _point(membrane.center, axis_u, axis_v, -2.0, -1.0),
        _point(membrane.center, axis_u, axis_v, 4.0, 1.0),
    ]

    bounds = projected_footprint(
        membrane,
        [_atom(*point) for point in points],
        margin=1.0,
        minimum_size=10.0,
        maximum_size=30.0,
    )

    assert bounds == pytest.approx((-4.0, 6.0, -5.0, 5.0))


def test_projected_footprint_clamps_large_selection_without_recentering():
    membrane = _membrane(normal=(0.0, 0.0, 1.0))
    axis_u, axis_v = orthonormal_basis(membrane.normal)
    points = [
        _point(membrane.center, axis_u, axis_v, -100.0, -50.0),
        _point(membrane.center, axis_u, axis_v, 20.0, 10.0),
    ]

    u_min, u_max, v_min, v_max = projected_footprint(
        membrane,
        [_atom(*point) for point in points],
        margin=4.0,
        minimum_size=10.0,
        maximum_size=40.0,
    )

    assert (u_max - u_min, v_max - v_min) == pytest.approx((40.0, 40.0))
    assert ((u_min + u_max) / 2, (v_min + v_max) / 2) == pytest.approx((-40.0, -20.0))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"margin": -1.0}, "non-negative"),
        ({"minimum_size": 0.0}, "minimum <= maximum"),
        ({"minimum_size": 20.0, "maximum_size": 10.0}, "minimum <= maximum"),
        ({"maximum_size": float("inf")}, "finite"),
    ],
)
def test_projected_footprint_rejects_invalid_display_dimensions(kwargs, message):
    with pytest.raises(ValueError, match=message):
        projected_footprint(_membrane(), [], **kwargs)


class FakeCmd:
    def __init__(self):
        self.deleted = []
        self.loaded = []
        self.centered = []
        self.zoomed = []

    def delete(self, name):
        self.deleted.append(name)

    def load_cgo(self, data, name):
        self.loaded.append((name, data))

    def center(self, selection):
        self.centered.append(selection)

    def zoom(self, selection):
        self.zoomed.append(selection)


@pytest.fixture
def cgo_constants(monkeypatch):
    constants = {
        "ALPHA": 101.0,
        "BEGIN": 102.0,
        "COLOR": 103.0,
        "END": 104.0,
        "NORMAL": 105.0,
        "TRIANGLES": 106.0,
        "VERTEX": 107.0,
    }
    pymol_module = ModuleType("pymol")
    cgo_module = ModuleType("pymol.cgo")
    for name, value in constants.items():
        setattr(cgo_module, name, value)
    pymol_module.cgo = cgo_module
    monkeypatch.setitem(sys.modules, "pymol", pymol_module)
    monkeypatch.setitem(sys.modules, "pymol.cgo", cgo_module)
    return constants


def _vertices(cgo, vertex_constant):
    return [
        tuple(cgo[index + 1 : index + 4])
        for index, value in enumerate(cgo)
        if value == vertex_constant
    ]


def test_create_membrane_planes_emits_two_triangles_at_each_boundary(cgo_constants):
    membrane = _membrane(normal=(1.0, 2.0, -1.0))
    cmd = FakeCmd()

    create_membrane_planes(membrane, [], "protein", cmd, minimum_size=12.0)

    assert cmd.deleted == ["mvqc_slab_lower", "mvqc_slab_upper"]
    assert [name for name, _ in cmd.loaded] == [
        "mvqc_slab_lower",
        "mvqc_slab_upper",
    ]
    assert cmd.centered == ["protein"]
    assert cmd.zoomed == ["protein"]

    for (_, cgo), expected_offset in zip(
        cmd.loaded,
        (membrane.lower_offset, membrane.upper_offset),
        strict=True,
    ):
        vertices = _vertices(cgo, cgo_constants["VERTEX"])
        assert len(vertices) == 6
        distances = [
            sum(
                (vertex[index] - membrane.center[index]) * membrane.normal[index]
                for index in range(3)
            )
            for vertex in vertices
        ]
        assert distances == pytest.approx([expected_offset] * 6)
        assert cgo.count(cgo_constants["NORMAL"]) == 1
        assert cgo.count(cgo_constants["BEGIN"]) == 1
        assert cgo.count(cgo_constants["TRIANGLES"]) == 1


def test_legacy_create_slab_preserves_names_colors_and_footprint(cgo_constants):
    cmd = FakeCmd()

    create_slab(-15.0, 15.0, cmd)

    assert [name for name, _ in cmd.loaded] == [
        "mvqc_slab_lower",
        "mvqc_slab_upper",
    ]
    lower_vertices = _vertices(cmd.loaded[0][1], cgo_constants["VERTEX"])
    assert {vertex[2] for vertex in lower_vertices} == {-15.0}
    assert min(vertex[0] for vertex in lower_vertices) == pytest.approx(-80.0)
    assert max(vertex[0] for vertex in lower_vertices) == pytest.approx(80.0)
    assert min(vertex[1] for vertex in lower_vertices) == pytest.approx(-80.0)
    assert max(vertex[1] for vertex in lower_vertices) == pytest.approx(80.0)
