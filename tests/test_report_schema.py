import json
from pathlib import Path

import pytest

from scripts.validate_example_reports import validate_reports


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "mvqc-report-1.0.schema.json"


def test_schema_has_stable_non_placeholder_identifier():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert schema["$id"] == "urn:membrane-vqc:schema:report:1.0"


def test_generated_example_reports_validate_against_json_schema():
    pytest.importorskip("jsonschema")
    reports = sorted((ROOT / "reports").glob("*_mvqc.json"))

    assert reports
    validate_reports(SCHEMA, reports)
