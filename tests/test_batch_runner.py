from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import stat

import pytest

from membrane_vqc.batch_contracts import BatchContractError, canonical_json_bytes, validate_result
from membrane_vqc.batch_paths import BatchPathError, prepare_output_root
from membrane_vqc.batch_runner import (
    BatchCancelled,
    BatchExecutionFailed,
    BatchInputRejected,
    ExecutedReport,
    run_batch,
)


ROOT = Path(__file__).resolve().parents[1]


def plan(ids=("one", "two"), failure_policy="continue_on_error"):
    return {
        "contract": "mvqc-batch-plan-1.0",
        "jobs": [
            {
                "id": item,
                "input": {"kind": "pymol", "selection": item},
                "analysis": {"mode": "legacy_global_z", "zmin": -15, "zmax": 15},
                "output": {"write_csv": False},
            }
            for item in ids
        ],
        "execution": {"failure_policy": failure_policy, "overwrite": "refuse"},
    }


def retained_report():
    return json.loads((ROOT / "reports" / "bad_core_lys_mvqc.json").read_text(encoding="utf-8"))


def test_sequential_order_and_continue_on_error(tmp_path):
    calls = []

    def execute(job):
        calls.append(job["id"])
        if job["id"] == "one":
            raise BatchInputRejected("INPUT_INVALID")
        return ExecutedReport(retained_report(), True)

    value = plan()
    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        execute,
        software_version="0.6.0.dev0",
        software_commit=None,
    )
    assert calls == ["one", "two"]
    assert [item["status"] for item in result["jobs"]] == ["INPUT_REJECTED", "REVIEW_ITEMS"]
    assert validate_result(result) is result


def test_fail_fast_skips_remaining_jobs(tmp_path):
    calls = []

    def execute(job):
        calls.append(job["id"])
        raise BatchExecutionFailed("ANALYSIS_FAILED")

    value = plan(failure_policy="fail_fast")
    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        execute,
        software_version="0.6.0.dev0",
        software_commit=None,
    )
    assert calls == ["one"]
    assert [item["status"] for item in result["jobs"]] == ["ANALYSIS_ERROR", "SKIPPED_DEPENDENCY"]


@pytest.mark.parametrize("cancel_after", [0, 1, 2])
def test_cooperative_cancellation_and_atomic_manifest(tmp_path, cancel_after):
    calls = []

    def execute(job):
        calls.append(job["id"])
        return ExecutedReport(retained_report(), True)

    value = plan(("one", "two", "three"))
    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        execute,
        software_version="0.6.0.dev0",
        software_commit=None,
        cancel_requested=lambda: len(calls) >= cancel_after,
    )
    assert (tmp_path / "batch-result.json").is_file()
    assert result["counts"]["CANCELLED"] == 3 - min(cancel_after, 3)


def test_stale_report_not_reused_and_coordinate_change_fails(tmp_path):
    value = plan(("one",))
    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        lambda job: ExecutedReport(retained_report(), False),
        software_version="0.6.0.dev0",
        software_commit=None,
    )
    assert result["jobs"][0]["status"] == "ANALYSIS_ERROR"
    assert result["jobs"][0]["report"] is None


def test_collision_refuses_unrelated_existing_output_before_execution(tmp_path):
    (tmp_path / "one.json").write_text("unrelated", encoding="utf-8")
    called = False

    def execute(job):
        nonlocal called
        called = True
        return ExecutedReport(retained_report(), True)

    value = plan(("one",))
    with pytest.raises(BatchInputRejected, match="OUTPUT_COLLISION"):
        run_batch(
            value,
            canonical_json_bytes(value),
            tmp_path,
            execute,
            software_version="0.6.0.dev0",
            software_commit=None,
        )
    assert called is False
    assert (tmp_path / "one.json").read_text(encoding="utf-8") == "unrelated"


def test_deterministic_output_names_and_identity_core(tmp_path):
    value = plan(("one",))
    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        lambda job: ExecutedReport(retained_report(), True),
        software_version="0.6.0.dev0",
        software_commit=None,
        now=lambda: "2026-07-31T00:00:00.000000Z",
        run_id="a" * 64,
    )
    assert result["jobs"][0]["report"]["path"] == "one.json"
    assert len(result["identity_core_sha256"]) == 64


def test_late_collision_is_not_overwritten(tmp_path):
    value = plan(("one",))

    def execute(job):
        (tmp_path / "one.json").write_text("late unrelated", encoding="utf-8")
        return ExecutedReport(retained_report(), True)

    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        execute,
        software_version="0.6.0.dev0",
        software_commit=None,
    )
    assert result["jobs"][0]["status"] == "INPUT_REJECTED"
    assert (tmp_path / "one.json").read_text(encoding="utf-8") == "late unrelated"


def test_output_limit_failure_leaves_no_partial_csv(tmp_path, monkeypatch):
    value = plan(("one",))
    value["jobs"][0]["output"]["write_csv"] = True
    monkeypatch.setattr("membrane_vqc.batch_runner.MAX_TOTAL_OUTPUT_BYTES", 1)
    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        lambda job: ExecutedReport(retained_report(), True),
        software_version="0.6.0.dev0",
        software_commit=None,
    )
    assert result["jobs"][0]["status"] == "ANALYSIS_ERROR"
    assert not (tmp_path / "one.json").exists()
    assert not (tmp_path / "one.csv").exists()


def test_report_requires_frozen_json_schema_validation(tmp_path):
    value = plan(("one",))
    report = retained_report()
    report["orientation"]["normal"] = [0.0, 0.0, 1.0, 2.0]
    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        lambda job: ExecutedReport(report, True),
        software_version="0.6.0.dev0",
        software_commit=None,
    )
    assert result["jobs"][0]["error_code"] == "REPORT_INVALID"


def test_same_batch_requires_untampered_owned_outputs(tmp_path):
    value = plan(("one",))
    value["execution"]["overwrite"] = "same_batch"
    plan_bytes = canonical_json_bytes(value)
    run_id = "a" * 64
    first = run_batch(
        value,
        plan_bytes,
        tmp_path,
        lambda job: ExecutedReport(retained_report(), True),
        software_version="0.6.0.dev0",
        software_commit=None,
        run_id=run_id,
    )
    assert first["jobs"][0]["report"] is not None
    (tmp_path / "one.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(BatchInputRejected, match="OUTPUT_OWNERSHIP_CHANGED"):
        run_batch(
            value,
            plan_bytes,
            tmp_path,
            lambda job: ExecutedReport(retained_report(), True),
            software_version="0.6.0.dev0",
            software_commit=None,
            run_id=run_id,
        )


def test_same_batch_cancellation_restores_prior_owned_outputs(tmp_path):
    value = plan(("one", "two"))
    value["execution"]["overwrite"] = "same_batch"
    plan_bytes = canonical_json_bytes(value)
    run_id = "a" * 64
    first = run_batch(
        value,
        plan_bytes,
        tmp_path,
        lambda job: ExecutedReport(retained_report(), True),
        software_version="0.6.0.dev0",
        software_commit=None,
        run_id=run_id,
    )
    prior_manifest = (tmp_path / "batch-result.json").read_bytes()
    prior_reports = {(tmp_path / name).read_bytes() for name in ("one.json", "two.json")}
    with pytest.raises(BatchExecutionFailed, match="SAME_BATCH_ROLLED_BACK"):
        run_batch(
            value,
            plan_bytes,
            tmp_path,
            lambda job: ExecutedReport(retained_report(), True),
            software_version="0.6.0.dev0",
            software_commit=None,
            run_id=run_id,
            cancel_requested=lambda: True,
        )
    assert (tmp_path / "batch-result.json").read_bytes() == prior_manifest
    assert {(tmp_path / name).read_bytes() for name in ("one.json", "two.json")} == prior_reports
    assert first["overall_status"] == "COMPLETED"


def test_same_batch_execution_failure_restores_prior_owned_outputs(tmp_path):
    value = plan(("one",))
    value["execution"]["overwrite"] = "same_batch"
    plan_bytes = canonical_json_bytes(value)
    run_id = "b" * 64
    run_batch(
        value,
        plan_bytes,
        tmp_path,
        lambda job: ExecutedReport(retained_report(), True),
        software_version="0.6.0.dev0",
        software_commit=None,
        run_id=run_id,
    )
    prior_manifest = (tmp_path / "batch-result.json").read_bytes()
    prior_report = (tmp_path / "one.json").read_bytes()
    with pytest.raises(BatchExecutionFailed, match="SAME_BATCH_ROLLED_BACK"):
        run_batch(
            value,
            plan_bytes,
            tmp_path,
            lambda job: (_ for _ in ()).throw(BatchExecutionFailed("TEST_FAILURE")),
            software_version="0.6.0.dev0",
            software_commit=None,
            run_id=run_id,
        )
    assert (tmp_path / "batch-result.json").read_bytes() == prior_manifest
    assert (tmp_path / "one.json").read_bytes() == prior_report


def test_late_output_collision_is_never_overwritten(tmp_path):
    value = plan(("one",))

    def collide_then_succeed(job):
        (tmp_path / "one.json").write_bytes(b"unrelated")
        return ExecutedReport(retained_report(), True)

    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        collide_then_succeed,
        software_version="0.6.0.dev0",
        software_commit=None,
    )
    assert result["jobs"][0]["error_code"] == "OUTPUT_COLLISION"
    assert (tmp_path / "one.json").read_bytes() == b"unrelated"


def test_invalid_explicit_run_id_is_rejected_before_output_creation(tmp_path):
    value = plan(("one",))
    with pytest.raises(BatchContractError, match="run_id"):
        run_batch(
            value,
            canonical_json_bytes(value),
            tmp_path,
            lambda job: ExecutedReport(retained_report(), True),
            software_version="0.6.0.dev0",
            software_commit=None,
            run_id="bad",
        )
    assert list(tmp_path.iterdir()) == []


def test_comparison_review_band_maps_to_review_items():
    from membrane_vqc.batch_runner import _scientific_status

    report = {
        "schema_version": "1.5",
        "comparison": {
            "comparable": True,
            "band": "measurable_geometric_difference",
            "warnings": ["review"],
        },
    }
    assert _scientific_status(report) == ("REVIEW_ITEMS", 1, 1)


def test_output_root_rejects_existing_symlink_component(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "out-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")
    with pytest.raises(BatchPathError, match="symbolic link|reparse"):
        prepare_output_root(link)


def test_output_root_rejects_windows_reparse_attribute(tmp_path, monkeypatch):
    target = (tmp_path / "output").absolute()
    original = Path.lstat

    def lstat(path):
        if path.absolute() == target:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        return original(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(BatchPathError, match="reparse"):
        prepare_output_root(target)


def test_safe_point_cancellation_finalizes_current_and_remaining_jobs(tmp_path):
    value = plan(("one", "two"))
    result = run_batch(
        value,
        canonical_json_bytes(value),
        tmp_path,
        lambda job: (_ for _ in ()).throw(BatchCancelled()),
        software_version="0.6.0.dev0",
        software_commit=None,
    )
    assert [job["status"] for job in result["jobs"]] == ["CANCELLED", "CANCELLED"]
    assert result["overall_status"] == "CANCELLED"
