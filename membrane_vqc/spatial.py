"""Small deterministic spatial cell list with no optional dependencies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

Point3 = tuple[float, float, float]
CellKey = tuple[int, int, int]


@dataclass(frozen=True)
class CellList:
    """Immutable mapping from cubic cells to stable atom indices."""

    cell_size: float
    cells: Mapping[CellKey, tuple[int, ...]]

    @classmethod
    def build(cls, points: Iterable[Point3], cell_size: float) -> "CellList":
        if not math.isfinite(float(cell_size)) or cell_size <= 0.0:
            raise ValueError("cell_size must be finite and greater than zero.")
        mutable: dict[CellKey, list[int]] = {}
        for index, point in enumerate(points):
            if len(point) != 3 or not all(math.isfinite(float(value)) for value in point):
                raise ValueError("Cell-list coordinates must be finite 3-vectors.")
            mutable.setdefault(_cell_key(point, cell_size), []).append(index)
        frozen = MappingProxyType(
            {key: tuple(sorted(indices)) for key, indices in sorted(mutable.items())}
        )
        return cls(float(cell_size), frozen)

    def nearby_indices(self, point: Point3) -> tuple[int, ...]:
        """Return stable indices in the point's cell and its 26 neighbours."""
        center = _cell_key(point, self.cell_size)
        indices: list[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    indices.extend(
                        self.cells.get((center[0] + dx, center[1] + dy, center[2] + dz), ())
                    )
        return tuple(indices)


def _cell_key(point: Point3, cell_size: float) -> CellKey:
    return tuple(math.floor(float(value) / cell_size) for value in point)  # type: ignore[return-value]
