from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from membrane_vqc.errors import OrientationError
from membrane_vqc.orientation_io import (
    SCHEMA_VERSION,
    dumps_orientation,
    load_orientation_file,
    load_planar_membrane,
    orientation_to_dict,
    parse_orientation,
    write_orientation_file,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "mvqc-orientation-1.0.schema.json"


def orientation_document(**updates):
    document = {
        "schema_version": "1.0",
        "geometry": "planar",
        "center": [1.0, 2.0, 3.0],
        "normal": [0.0, 0.0, 2.0],
        "lower_offset": -12.0,
        "upper_offset": 18.0,
        "interface_width": 3.0,
        "source": "manual_fixture",
        "source_version": None,
        "confidence": "test-only",
        "metadata": {"nested": {"values": [1, 2.5, None, True]}},
    }
    document.update(updates)
    return document


def test_schema_is_valid_and_strict_at_document_boundary():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:membrane-vqc:schema:orientation:1.0"
    assert schema["additionalProperties"] is False


def test_parse_builds_normalised_planar_membrane():
    membrane = parse_orientation(orientation_document())

    assert membrane.center == (1.0, 2.0, 3.0)
    assert membrane.normal == pytest.approx((0.0, 0.0, 1.0))
    assert membrane.lower_offset == -12.0
    assert membrane.upper_offset == 18.0
    assert membrane.source == "manual_fixture"
    assert membrane.metadata["nested"]["values"] == (1, 2.5, None, True) or membrane.metadata[
        "nested"
    ]["values"] == [1, 2.5, None, True]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"schema_version": "2.0"}, "schema_version"),
        ({"geometry": "curved"}, "geometry"),
        ({"center": [0, 1]}, "center"),
        ({"normal": [0, 0, float("nan")]}, "normal[2]"),
        ({"normal": [0, 0, 10**400]}, "normal[2]"),
        ({"lower_offset": True}, "lower_offset"),
        ({"interface_width": float("inf")}, "interface_width"),
        ({"source": ""}, "source"),
        ({"source_version": 1}, "source_version"),
        ({"confidence": False}, "confidence"),
        ({"metadata": []}, "metadata"),
        ({"metadata": {"bad": {"value": float("-inf")}}}, "metadata.bad.value"),
        ({"metadata": {"bad": {"value": 10**400}}}, "metadata.bad.value"),
    ],
)
def test_parse_rejects_invalid_documents_with_field_context(updates, message):
    with pytest.raises(OrientationError, match=message.replace("[", r"\[").replace("]", r"\]")):
        parse_orientation(orientation_document(**updates))


def test_parse_rejects_missing_and_unknown_fields():
    missing = orientation_document()
    del missing["normal"]
    with pytest.raises(OrientationError, match="missing required field.*normal"):
        parse_orientation(missing)

    with pytest.raises(OrientationError, match="unknown field.*typo"):
        parse_orientation(orientation_document(typo=123))


def test_metadata_must_be_recursively_json_safe():
    with pytest.raises(OrientationError, match="metadata.bad contains a non-JSON value"):
        parse_orientation(orientation_document(metadata={"bad": object()}))
    with pytest.raises(OrientationError, match="metadata keys must be strings"):
        parse_orientation(orientation_document(metadata={1: "bad"}))


def test_serialisation_is_deterministic_utf8_and_newline_terminated():
    membrane = parse_orientation(
        orientation_document(source="μ-manual", metadata={"z": 1, "a": "α"})
    )

    first = dumps_orientation(membrane)
    second = dumps_orientation(membrane)

    assert first == second
    assert first.endswith("\n") and not first.endswith("\n\n")
    assert "μ-manual" in first
    assert list(json.loads(first)) == sorted(json.loads(first))
    assert parse_orientation(json.loads(first)).as_dict() == membrane.as_dict()


def test_orientation_to_dict_is_canonical_and_has_no_file_provenance():
    document = orientation_to_dict(parse_orientation(orientation_document()))

    assert document["schema_version"] == SCHEMA_VERSION
    assert document["geometry"] == "planar"
    assert "orientation_path" not in document
    assert "sha256" not in document


def test_write_and_load_record_orientation_file_provenance(tmp_path):
    membrane = parse_orientation(orientation_document())
    path = tmp_path / "example.orientation.json"
    returned = write_orientation_file(membrane, path)
    payload = path.read_bytes()

    loaded = load_orientation_file(path)

    assert returned == path
    assert loaded.membrane.as_dict() == membrane.as_dict()
    assert loaded.orientation is loaded.membrane
    assert loaded.orientation_path == path.name
    assert loaded.sha256 == hashlib.sha256(payload).hexdigest()
    assert loaded.schema_version == "1.0"
    assert loaded.provenance.as_dict() == {
        "basename": path.name,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    assert load_planar_membrane(path).as_dict() == membrane.as_dict()
    assert "orientation_path" not in loaded.membrane.metadata
    assert "sha256" not in loaded.membrane.metadata


def test_loader_rejects_duplicate_fields_nonstandard_numbers_and_invalid_utf8(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":"1.0","schema_version":"1.0"}', encoding="utf-8")
    with pytest.raises(OrientationError, match="duplicate JSON field"):
        load_orientation_file(duplicate)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text(
        json.dumps(orientation_document()).replace("3.0", "NaN", 1), encoding="utf-8"
    )
    with pytest.raises(OrientationError, match="non-finite JSON number"):
        load_orientation_file(nonfinite)

    overflow = tmp_path / "overflow.json"
    overflow.write_text(
        json.dumps(orientation_document()).replace("3.0", "1e999", 1), encoding="utf-8"
    )
    with pytest.raises(OrientationError, match=r"center\[2\].*finite"):
        load_orientation_file(overflow)

    invalid_utf8 = tmp_path / "invalid.json"
    invalid_utf8.write_bytes(b"\xff\xfe")
    with pytest.raises(OrientationError, match="not valid UTF-8"):
        load_orientation_file(invalid_utf8)


def test_loader_reports_json_location_and_missing_file(tmp_path):
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{\n  nope\n}", encoding="utf-8")
    with pytest.raises(OrientationError, match=r"line 2, column"):
        load_orientation_file(malformed)

    with pytest.raises(OrientationError, match="could not read orientation file"):
        load_orientation_file(tmp_path / "missing.json")


def test_schema_validates_canonical_document():
    jsonschema = pytest.importorskip("jsonschema")
    document = orientation_to_dict(parse_orientation(orientation_document()))

    jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(
        document
    )
