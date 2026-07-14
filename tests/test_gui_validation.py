from pathlib import Path

import pytest

from membrane_vqc.gui import (
    GUIInputs,
    LigandShellInputs,
    PLANAR_BOUNDARIES_STATUS,
    PLANAR_REVIEW_STATUS,
    SlabInputs,
    parse_export_path,
    parse_gui_inputs,
    parse_ligand_shell_inputs,
    parse_selection,
    parse_slab_inputs,
)


def test_planar_status_messages_are_utf8_without_mojibake():
    assert PLANAR_REVIEW_STATUS == "Running planar membrane review…"
    assert PLANAR_BOUNDARIES_STATUS == "Creating planar membrane boundaries…"
    assert "â" not in PLANAR_REVIEW_STATUS + PLANAR_BOUNDARIES_STATUS


def test_parse_gui_inputs_strips_text_and_allows_empty_ligand():
    parsed = parse_gui_inputs("  model_a ", "-15", "15.5", "  ", "5")

    assert parsed == GUIInputs("model_a", -15.0, 15.5, "", 5.0)


@pytest.mark.parametrize(
    ("field", "values", "message"),
    [
        ("selection", ("", "-15", "15", "organic", "5"), "must not be empty"),
        ("zmin", ("all", "bad", "15", "organic", "5"), "zmin must be a number"),
        ("zmax", ("all", "-15", "inf", "organic", "5"), "zmax must be finite"),
        ("order", ("all", "15", "-15", "organic", "5"), "zmin must be less"),
        ("cutoff", ("all", "-15", "15", "organic", "0"), "greater than zero"),
    ],
)
def test_parse_gui_inputs_rejects_invalid_values(field, values, message):
    del field
    with pytest.raises(ValueError, match=message):
        parse_gui_inputs(*values)


def test_parse_export_path_rejects_blank_and_preserves_relative_path():
    with pytest.raises(ValueError, match="must not be empty"):
        parse_export_path("   ")

    assert parse_export_path(" reports/result.json ") == Path("reports") / "result.json"


def test_action_specific_parsers_accept_only_their_own_fields():
    assert parse_slab_inputs("-12", "18") == SlabInputs(-12.0, 18.0)
    assert parse_selection(" model_a ") == "model_a"
    assert parse_ligand_shell_inputs(" model_a ", " organic ", "4.5") == (
        LigandShellInputs("model_a", "organic", 4.5)
    )


@pytest.mark.parametrize(
    ("parser", "args", "message"),
    [
        (parse_slab_inputs, ("bad", "15"), "zmin must be a number"),
        (parse_slab_inputs, ("15", "-15"), "zmin must be less"),
        (parse_selection, (" ",), "must not be empty"),
        (
            parse_ligand_shell_inputs,
            ("all", "organic", "0"),
            "greater than zero",
        ),
    ],
)
def test_action_specific_parsers_reject_relevant_invalid_fields(parser, args, message):
    with pytest.raises(ValueError, match=message):
        parser(*args)
