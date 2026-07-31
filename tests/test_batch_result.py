from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from membrane_vqc.batch_contracts import BatchContractError, identity_core_sha256, validate_result


def result(status="SUCCESS"):
    successful = status in {"SUCCESS", "REVIEW_ITEMS", "INSUFFICIENT_CONTEXT"}
    job = {
        "job_id": "one",
        "mode": "legacy_global_z",
        "status": status,
        "error_code": "ANALYSIS_FAILED" if status == "ANALYSIS_ERROR" else None,
        "report": {"path": "one.json", "size": 2, "sha256": hashlib.sha256(b"{}").hexdigest()}
        if successful
        else None,
        "report_schema": "1.1" if successful else None,
        "csv": None,
        "warnings_count": 0,
        "review_items_count": 0 if successful else None,
        "coordinate_preserved": True if successful else None,
    }
    statuses = [
        "SUCCESS",
        "REVIEW_ITEMS",
        "INSUFFICIENT_CONTEXT",
        "ANALYSIS_ERROR",
        "INPUT_REJECTED",
        "CANCELLED",
        "SKIPPED_DEPENDENCY",
    ]
    value = {
        "contract": "mvqc-batch-result-1.0",
        "plan_sha256": "a" * 64,
        "run_id": "b" * 64,
        "software": {"version": "0.6.0.dev0", "commit": None},
        "started_at": "2026-07-31T00:00:00.000000Z",
        "completed_at": "2026-07-31T00:00:01.000000Z",
        "execution": {"failure_policy": "continue_on_error", "overwrite": "refuse"},
        "jobs": [job],
        "counts": {"total": 1, **{item: int(item == status) for item in statuses}},
        "overall_status": "COMPLETED" if successful else "COMPLETED_WITH_ERRORS",
        "identity_core_sha256": "0" * 64,
    }
    value["identity_core_sha256"] = identity_core_sha256(value)
    return value


@pytest.mark.parametrize(
    "status", ["SUCCESS", "REVIEW_ITEMS", "INSUFFICIENT_CONTEXT", "ANALYSIS_ERROR"]
)
def test_success_and_mixed_result_shapes(status):
    value = result(status)
    assert validate_result(value)["jobs"][0]["status"] == status
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1] / "schemas" / "mvqc-batch-result-1.0.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(value)


def test_fail_fast_and_cancellation_results():
    cancelled = result("ANALYSIS_ERROR")
    cancelled["jobs"][0].update({"status": "CANCELLED", "error_code": None})
    for key in cancelled["counts"]:
        cancelled["counts"][key] = 0
    cancelled["counts"].update({"total": 1, "CANCELLED": 1})
    cancelled["overall_status"] = "CANCELLED"
    cancelled["identity_core_sha256"] = identity_core_sha256(cancelled)
    validate_result(cancelled)

    failed = result("ANALYSIS_ERROR")
    failed["execution"]["failure_policy"] = "fail_fast"
    failed["overall_status"] = "FAILED_FAST"
    failed["identity_core_sha256"] = identity_core_sha256(failed)
    validate_result(failed)


@pytest.mark.parametrize("field,value", [("unknown", True), ("plan_sha256", "bad")])
def test_result_rejects_unknown_fields_and_invalid_digest(field, value):
    item = result()
    item[field] = value
    with pytest.raises(BatchContractError):
        validate_result(item)


@pytest.mark.parametrize(
    "path", ["C:/Users/name/result.json", "/tmp/result.json", "../result.json"]
)
def test_result_rejects_absolute_or_traversal_paths(path):
    item = result()
    item["jobs"][0]["report"]["path"] = path
    item["identity_core_sha256"] = identity_core_sha256(item)
    with pytest.raises(BatchContractError):
        validate_result(item)


def test_result_rejects_aggregate_contradictions_and_raw_exception_leakage():
    item = result()
    item["counts"]["SUCCESS"] = 0
    with pytest.raises(BatchContractError, match="contradict"):
        validate_result(item)
    leaked = result()
    leaked["software"]["version"] = "Traceback (most recent call last)"
    leaked["identity_core_sha256"] = identity_core_sha256(leaked)
    with pytest.raises(BatchContractError, match="sensitive"):
        validate_result(leaked)


def test_identity_core_excludes_run_specific_fields():
    first = result()
    second = deepcopy(first)
    second.update(
        {
            "run_id": "c" * 64,
            "started_at": "2027-01-01T00:00:00Z",
            "completed_at": "2027-01-01T00:01:00Z",
        }
    )
    assert identity_core_sha256(first) == identity_core_sha256(second)


def test_identity_core_excludes_volatile_artifact_bytes():
    first = result()
    second = deepcopy(first)
    second["jobs"][0]["report"].update({"size": 999, "sha256": "d" * 64})
    assert identity_core_sha256(first) == identity_core_sha256(second)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update({"overall_status": "CANCELLED"}),
        lambda value: value["jobs"][0].update({"mode": "pdbtm_cache"}),
        lambda value: value["jobs"][0].update({"coordinate_preserved": False}),
        lambda value: value.update({"started_at": "not-a-timestamp"}),
    ],
)
def test_result_rejects_cross_field_contradictions(mutation):
    value = result()
    mutation(value)
    value["identity_core_sha256"] = identity_core_sha256(value)
    with pytest.raises(BatchContractError):
        validate_result(value)


def test_result_rejects_completion_before_start():
    value = result()
    value["completed_at"] = "2026-07-30T23:59:59Z"
    value["identity_core_sha256"] = identity_core_sha256(value)
    with pytest.raises(BatchContractError, match="precede"):
        validate_result(value)
