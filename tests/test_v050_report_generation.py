from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.generate_stage4c_example import build_example as build_comparison_example
from scripts.generate_v050_pdbtm_examples import (
    build_cached_pdbtm_example,
    build_local_pdbtm_example,
    serialize,
)
from scripts.validate_example_reports import (
    V050_RELEASE_REPORTS,
    v050_release_report_inventory,
    validate_retained_report_privacy,
)


COMMIT = "a" * 40


@pytest.mark.parametrize(
    ("builder", "schema"),
    [(build_local_pdbtm_example, "1.3"), (build_cached_pdbtm_example, "1.4")],
)
def test_pdbtm_release_examples_are_deterministic_and_private(builder, schema):
    first = builder(software_version="0.5.0", software_commit=COMMIT)
    second = builder(software_version="0.5.0", software_commit=COMMIT)

    assert first == second
    assert serialize(first) == serialize(second)
    assert first["schema_version"] == schema
    assert first["software"]["version"] == "0.5.0"
    assert first["software"]["commit"] == COMMIT
    assert first["runtime"] == {
        "python": "3.10.20",
        "pymol": "3.1.8",
        "pymol_status": "recorded",
        "platform": "Windows-10-build-26200",
    }
    validate_retained_report_privacy(first)


def test_release_generators_require_truthful_commit():
    with pytest.raises(ValueError, match="40-character"):
        build_local_pdbtm_example(software_version="0.5.0", software_commit="placeholder")


def test_v050_inventory_records_exact_bytes(tmp_path):
    reports = {
        "1.3": build_local_pdbtm_example(software_version="0.5.0", software_commit=COMMIT),
        "1.4": build_cached_pdbtm_example(software_version="0.5.0", software_commit=COMMIT),
        "1.5": build_comparison_example(software_version="0.5.0", software_commit=COMMIT),
    }
    for relative, schema in V050_RELEASE_REPORTS.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(reports[schema], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    inventory = v050_release_report_inventory(tmp_path)

    assert [item["schema_version"] for item in inventory] == ["1.3", "1.4", "1.5"]
    assert all(item["generation_commit"] == COMMIT for item in inventory)
    assert all(item["byte_size"] > 0 for item in inventory)
    assert all(len(item["sha256"]) == 64 for item in inventory)


@pytest.mark.parametrize(
    "leak",
    [
        {"input": {"path": r"C:\\Users\\owner\\secret.pdb"}},
        {"runtime": {"hostname": "workstation"}},
        {"network": {"address": "192.168.1.7"}},
        {"error": "Traceback (most recent call last): private details"},
        {"credential": "abc"},
        {"cache_path": "/tmp/pdbtm-cache"},
        {"provider_payload": '{"pdb_id":"9zzz"}'},
        {"data": "ATOM      1  CA  ALA A   1       0.000   0.000   0.000"},
    ],
)
def test_privacy_validator_rejects_environment_leaks(leak):
    with pytest.raises(ValueError, match="sensitive"):
        validate_retained_report_privacy(leak)


def test_historical_schema_1_3_report_is_not_a_v050_inventory_member():
    assert Path("reports/pdbtm_synthetic_mvqc.json") not in V050_RELEASE_REPORTS
