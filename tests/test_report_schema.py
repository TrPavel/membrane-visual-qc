import json
from pathlib import Path

import pytest

from scripts.validate_example_reports import (
    default_report_paths,
    validate_reports,
    validate_reports_by_version,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "mvqc-report-1.0.schema.json"
SCHEMA_1_1 = ROOT / "schemas" / "mvqc-report-1.1.schema.json"


def test_schema_has_stable_non_placeholder_identifier():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert schema["$id"] == "urn:membrane-vqc:schema:report:1.0"
    schema_1_1 = json.loads(SCHEMA_1_1.read_text(encoding="utf-8"))
    assert schema_1_1["$id"] == "urn:membrane-vqc:schema:report:1.1"


def test_generated_example_reports_validate_against_json_schema():
    pytest.importorskip("jsonschema")
    reports = default_report_paths(ROOT / "reports")

    assert reports
    validate_reports(SCHEMA_1_1, reports)


def test_generated_examples_can_dispatch_by_declared_schema_version():
    pytest.importorskip("jsonschema")
    reports = default_report_paths(ROOT / "reports")
    assert validate_reports_by_version(reports) == {"1.1": len(reports)}
