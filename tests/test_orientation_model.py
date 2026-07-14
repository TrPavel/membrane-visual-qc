from dataclasses import FrozenInstanceError
import math

import pytest

from membrane_vqc.errors import OrientationError
from membrane_vqc.orientation import PlanarMembrane, legacy_global_z, normalize, vector3


def membrane(**overrides):
    values = {
        "center": (1, 2, 3),
        "normal": (0, 0, 5),
        "lower_offset": -12,
        "upper_offset": 18,
        "interface_width": 3,
        "source": "manual",
    }
    values.update(overrides)
    return PlanarMembrane(**values)


def test_normalization_and_report_safe_serialization():
    plane = membrane(
        metadata={"provider": {"record": "x"}, "scores": [1, 2.5]},
        source_version=" 1.0 ",
        confidence=" declared ",
        warnings=("manual orientation",),
    )
    assert plane.center == (1.0, 2.0, 3.0)
    assert plane.normal == (0.0, 0.0, 1.0)
    assert plane.as_dict() == {
        "geometry": "planar",
        "source": "manual",
        "source_version": "1.0",
        "confidence": "declared",
        "center": [1.0, 2.0, 3.0],
        "normal": [0.0, 0.0, 1.0],
        "lower_offset": -12.0,
        "upper_offset": 18.0,
        "interface_width": 3.0,
        "metadata": {"provider": {"record": "x"}, "scores": [1, 2.5]},
        "warnings": ["manual orientation"],
    }


def test_metadata_is_deep_copied_and_frozen():
    original = {"nested": {"values": [1, 2]}}
    plane = membrane(metadata=original)
    original["nested"]["values"].append(3)
    assert plane.as_dict()["metadata"] == {"nested": {"values": [1, 2]}}
    with pytest.raises(TypeError):
        plane.metadata["new"] = "value"
    with pytest.raises(TypeError):
        plane.metadata["nested"]["new"] = "value"
    with pytest.raises(FrozenInstanceError):
        plane.normal = (1.0, 0.0, 0.0)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"center": (0, 1)}, "center"),
        ({"center": (0, math.nan, 0)}, "finite"),
        ({"normal": (0, 0, 0)}, "greater than"),
        ({"normal": (1e-13, 0, 0)}, "greater than"),
        ({"normal": (math.inf, 0, 0)}, "finite"),
        ({"lower_offset": math.nan}, "finite"),
        ({"upper_offset": math.inf}, "finite"),
        ({"lower_offset": 2, "upper_offset": 2}, "smaller"),
        ({"lower_offset": 3, "upper_offset": 2}, "smaller"),
        ({"interface_width": -1}, "non-negative"),
        ({"interface_width": math.inf}, "finite"),
        ({"source": " "}, "source"),
        ({"source": None}, "source"),
        ({"source_version": " "}, "source_version"),
        ({"confidence": " "}, "confidence"),
        ({"metadata": {"bad": math.nan}}, "finite JSON"),
        ({"metadata": {1: "bad"}}, "keys must be strings"),
        ({"metadata": {"bad": {1, 2}}}, "not JSON-safe"),
        ({"warnings": ("",)}, "warnings"),
        ({"warnings": (1,)}, "warnings"),
    ],
)
def test_invalid_values_are_rejected(overrides, message):
    with pytest.raises(OrientationError, match=message):
        membrane(**overrides)


def test_vector_helpers_reject_boolean_and_normalize_diagonal():
    with pytest.raises(OrientationError, match="boolean"):
        vector3((True, 0, 0))
    assert normalize((1, 1, 1)) == pytest.approx((1 / math.sqrt(3),) * 3)


def test_legacy_mapping_sorts_bounds_and_has_explicit_source():
    plane = legacy_global_z(15, -15)
    assert plane.center == (0.0, 0.0, 0.0)
    assert plane.normal == (0.0, 0.0, 1.0)
    assert (plane.lower_offset, plane.upper_offset) == (-15.0, 15.0)
    assert plane.source == "manual_global_z"
