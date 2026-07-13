import pytest

from membrane_vqc.errors import InputValidationError
from membrane_vqc.qc import validate_analysis_inputs


def test_validate_analysis_inputs_normalises_strings():
    values = validate_analysis_inputs(" all ", "-15", "15", " organic ", "5")

    assert values == ("all", -15.0, 15.0, "organic", 5.0)


@pytest.mark.parametrize(
    ("selection", "zmin", "zmax", "cutoff", "message"),
    [
        ("", -15, 15, 5, "selection"),
        ("all", 15, -15, 5, "zmin"),
        ("all", 0, 0, 5, "zmin"),
        ("all", -15, 15, 0, "cutoff"),
        ("all", -15, 15, -1, "cutoff"),
        ("all", float("nan"), 15, 5, "finite"),
        ("all", -15, float("inf"), 5, "finite"),
    ],
)
def test_validate_analysis_inputs_rejects_invalid_values(selection, zmin, zmax, cutoff, message):
    with pytest.raises(InputValidationError, match=message):
        validate_analysis_inputs(selection, zmin, zmax, "", cutoff)
