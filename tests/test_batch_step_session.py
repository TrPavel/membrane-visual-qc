import json
from pathlib import Path

from membrane_vqc.batch_contracts import canonical_json_bytes, validate_result
from membrane_vqc.batch_runner import BatchRunSession, ExecutedReport, run_batch


ROOT = Path(__file__).resolve().parents[1]


def _plan(ids=("one", "two", "three"), failure_policy="continue_on_error"):
    return {
        "contract": "mvqc-batch-plan-1.0",
        "jobs": [
            {
                "id": job_id,
                "input": {"kind": "pymol", "selection": job_id},
                "analysis": {"mode": "legacy_global_z", "zmin": -15, "zmax": 15},
                "output": {"write_csv": False},
            }
            for job_id in ids
        ],
        "execution": {"failure_policy": failure_policy, "overwrite": "refuse"},
    }


def _report():
    return json.loads((ROOT / "reports" / "bad_core_lys_mvqc.json").read_text("utf-8"))


def _session(plan, output, executor, cancel=None):
    return BatchRunSession(
        plan,
        canonical_json_bytes(plan),
        output,
        executor,
        software_version="0.6.0.dev0",
        software_commit=None,
        cancel_requested=cancel,
        run_id="a" * 64,
        now=lambda: "2026-07-31T00:00:00.000000Z",
    )


def test_step_session_executes_exactly_one_job_per_call(tmp_path):
    calls = []
    plan = _plan()
    session = _session(
        plan,
        tmp_path,
        lambda job: calls.append(job["id"]) or ExecutedReport(_report(), True),
    ).start()
    assert calls == []
    assert session.current_job["id"] == "one"
    session.execute_next()
    assert calls == ["one"]
    assert session.current_job["id"] == "two"
    session.execute_next()
    assert calls == ["one", "two"]
    session.execute_next()
    assert session.done
    result = session.finalize()
    assert validate_result(result) is result


def test_step_and_synchronous_adapters_have_same_identity_core(tmp_path):
    plan = _plan(("one", "two"))
    first = _session(
        plan,
        tmp_path / "step",
        lambda job: ExecutedReport(_report(), True),
    ).start()
    while not first.done:
        first.execute_next()
    stepped = first.finalize()
    synchronous = run_batch(
        plan,
        canonical_json_bytes(plan),
        tmp_path / "sync",
        lambda job: ExecutedReport(_report(), True),
        software_version="0.6.0.dev0",
        software_commit=None,
        run_id="a" * 64,
        now=lambda: "2026-07-31T00:00:00.000000Z",
    )
    assert stepped["identity_core_sha256"] == synchronous["identity_core_sha256"]
    assert stepped["jobs"] == synchronous["jobs"]


def test_step_session_cancels_before_first_and_starts_no_job(tmp_path):
    calls = []
    plan = _plan(("one", "two"))
    session = _session(
        plan,
        tmp_path,
        lambda job: calls.append(job["id"]),
        cancel=lambda: True,
    ).start()
    session.execute_next()
    session.execute_next()
    result = session.finalize()
    assert calls == []
    assert [job["status"] for job in result["jobs"]] == ["CANCELLED", "CANCELLED"]
    assert result["overall_status"] == "CANCELLED"


def test_step_session_cancel_between_jobs_preserves_completed_output(tmp_path):
    cancelled = False
    plan = _plan(("one", "two"))
    session = _session(
        plan,
        tmp_path,
        lambda job: ExecutedReport(_report(), True),
        cancel=lambda: cancelled,
    ).start()
    session.execute_next()
    cancelled = True
    session.execute_next()
    result = session.finalize()
    assert [job["status"] for job in result["jobs"]] == ["REVIEW_ITEMS", "CANCELLED"]
    assert (tmp_path / "one.json").is_file()
    assert (tmp_path / "batch-result.json").is_file()


def test_step_session_fail_fast_marks_later_jobs_without_execution(tmp_path):
    calls = []
    plan = _plan(failure_policy="fail_fast")

    def execute(job):
        calls.append(job["id"])
        raise RuntimeError("not serialized")

    session = _session(plan, tmp_path, execute).start()
    while not session.done:
        session.execute_next()
    result = session.finalize()
    assert calls == ["one"]
    assert [job["status"] for job in result["jobs"]] == [
        "ANALYSIS_ERROR",
        "SKIPPED_DEPENDENCY",
        "SKIPPED_DEPENDENCY",
    ]
