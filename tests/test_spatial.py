import pytest

from membrane_vqc.spatial import CellList


def test_cell_list_returns_stable_local_neighbours():
    index = CellList.build([(0.0, 0.0, 0.0), (0.9, 0.0, 0.0), (3.0, 0.0, 0.0)], 1.0)
    assert index.nearby_indices((0.1, 0.0, 0.0)) == (0, 1)


@pytest.mark.parametrize("cell_size", [0.0, -1.0, float("nan"), float("inf")])
def test_cell_list_rejects_invalid_cell_size(cell_size):
    with pytest.raises(ValueError, match="cell_size"):
        CellList.build([], cell_size)


def test_cell_list_rejects_nonfinite_coordinates():
    with pytest.raises(ValueError, match="finite 3-vectors"):
        CellList.build([(float("nan"), 0.0, 0.0)], 1.0)
