"""Shared rigid transform for the Stage 2 rotated-1UBQ validation fixture."""

from __future__ import annotations

from typing import Any


def transform_point(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Apply the validated rigid transform to one Cartesian coordinate."""
    return (float(z) + 10.0, float(y) - 5.0, -float(x) + 3.0)


def transform_coordinates(coordinates: Any) -> Any:
    """Return a copied coordinate array transformed point-by-point."""
    transformed = coordinates.copy()
    for index, coordinate in enumerate(coordinates):
        transformed[index] = transform_point(*coordinate)
    return transformed
