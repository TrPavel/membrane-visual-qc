import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from membrane_vqc import qc
from membrane_vqc.batch_contracts import canonical_json_bytes, identity_core_sha256
from membrane_vqc.batch_result_browser import (
    BatchResultBrowserError,
    inspect_result_bundle,
    revalidate_artifact,
)
from membrane_vqc.batch_paths import BatchPathError, prepare_output_root, resolve_existing_root
from membrane_vqc.batch_runner import ExecutedReport, run_batch


ROOT = Path(__file__).resolve().parents[1]
GENUINE_V010_FIXTURE = (
    ROOT / "tests" / "fixtures" / "genuine_v0.1.0_schema_1_0_bad_core_lys_mvqc.json"
)


@pytest.mark.parametrize("path", [r"\\server\share", r"\\?\C:\device", r"\\.\pipe\name"])
def test_unc_device_and_pipe_roots_are_rejected_without_access(path):
    with pytest.raises(BatchPathError):
        resolve_existing_root(path)
    with pytest.raises(BatchPathError):
        prepare_output_root(path)


def _plan(write_csv=True):
    return {
        "contract": "mvqc-batch-plan-1.0",
        "jobs": [
            {
                "id": "one",
                "input": {"kind": "pymol", "selection": "one"},
                "analysis": {"mode": "legacy_global_z", "zmin": -15, "zmax": 15},
                "output": {"write_csv": write_csv},
            }
        ],
        "execution": {"failure_policy": "continue_on_error", "overwrite": "refuse"},
    }


def _report():
    return json.loads((ROOT / "reports" / "bad_core_lys_mvqc.json").read_text("utf-8"))


def _bundle(tmp_path, write_csv=True):
    plan = _plan(write_csv)
    run_batch(
        plan,
        canonical_json_bytes(plan),
        tmp_path,
        lambda job: ExecutedReport(_report(), True),
        software_version="0.6.0.dev0",
        software_commit=None,
        run_id="a" * 64,
        now=lambda: "2026-07-31T00:00:00.000000Z",
    )
    return tmp_path / "batch-result.json"


def _plan_for_mode(mode, write_csv=False):
    """A structurally valid single-job plan for `mode`, reusing the reviewed five-mode fixture's
    job shape (data/synthetic/stage5a_batch_plan.json) so the plan/mode pairing is realistic. The
    executor is always faked in these tests, so the referenced input paths are never read."""
    fixture_plan = json.loads(
        (ROOT / "data" / "synthetic" / "stage5a_batch_plan.json").read_text("utf-8")
    )
    job = copy.deepcopy(next(j for j in fixture_plan["jobs"] if j["analysis"]["mode"] == mode))
    job["id"] = "one"
    job["output"]["write_csv"] = write_csv
    return {
        "contract": "mvqc-batch-plan-1.0",
        "jobs": [job],
        "execution": {"failure_policy": "continue_on_error", "overwrite": "refuse"},
    }


def _bundle_with_report(tmp_path, report, mode="legacy_global_z", write_csv=False):
    plan = _plan_for_mode(mode, write_csv)
    run_batch(
        plan,
        canonical_json_bytes(plan),
        tmp_path,
        lambda job: ExecutedReport(report, True),
        software_version="0.6.0.dev0",
        software_commit=None,
        run_id="a" * 64,
        now=lambda: "2026-07-31T00:00:00.000000Z",
    )
    return tmp_path / "batch-result.json"


def _rewrite_manifest(path, mutate):
    value = json.loads(path.read_text("utf-8"))
    mutate(value)
    value["identity_core_sha256"] = identity_core_sha256(value)
    path.write_bytes(canonical_json_bytes(value, pretty=True))


def test_valid_bundle_verifies_manifest_report_and_csv(tmp_path):
    manifest = _bundle(tmp_path)
    sentinel = {"single": "unchanged"}
    previous = qc.LAST_REPORT
    qc.LAST_REPORT = sentinel
    try:
        bundle = inspect_result_bundle(manifest)
        assert bundle.manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
        assert bundle.jobs[0].report.availability == "VERIFIED"
        assert bundle.jobs[0].csv.availability == "VERIFIED"
        assert qc.LAST_REPORT is sentinel
    finally:
        qc.LAST_REPORT = previous


def test_missing_output_is_reported_unavailable_without_deletion(tmp_path):
    manifest = _bundle(tmp_path, write_csv=False)
    (tmp_path / "one.json").unlink()
    bundle = inspect_result_bundle(manifest)
    assert bundle.jobs[0].report.availability == "MISSING"
    with pytest.raises(BatchResultBrowserError, match="OUTPUT_UNAVAILABLE"):
        revalidate_artifact(bundle, bundle.jobs[0].report)


@pytest.mark.parametrize("name", ["one.json", "one.csv"])
def test_altered_output_identity_is_rejected(tmp_path, name):
    manifest = _bundle(tmp_path)
    path = tmp_path / name
    body = bytearray(path.read_bytes())
    body[-1] = (body[-1] + 1) % 255
    path.write_bytes(body)
    with pytest.raises(BatchResultBrowserError, match="OUTPUT_IDENTITY_CHANGED"):
        inspect_result_bundle(manifest)


def test_reveal_revalidates_after_bundle_was_opened(tmp_path):
    manifest = _bundle(tmp_path, write_csv=False)
    bundle = inspect_result_bundle(manifest)
    artifact = bundle.jobs[0].report
    assert revalidate_artifact(bundle, artifact) == tmp_path / "one.json"
    (tmp_path / "one.json").write_bytes(b"changed")
    with pytest.raises(BatchResultBrowserError):
        revalidate_artifact(bundle, artifact)


def test_aggregate_or_identity_core_contradiction_is_rejected(tmp_path):
    manifest = _bundle(tmp_path, write_csv=False)
    value = json.loads(manifest.read_text("utf-8"))
    value["counts"]["total"] = 2
    manifest.write_bytes(canonical_json_bytes(value, pretty=True))
    with pytest.raises(BatchResultBrowserError, match="RESULT_MANIFEST_INVALID"):
        inspect_result_bundle(manifest)


def test_semantic_invalid_referenced_report_is_rejected(tmp_path):
    manifest = _bundle(tmp_path, write_csv=False)
    report_path = tmp_path / "one.json"
    report = json.loads(report_path.read_text("utf-8"))
    report["summary"]["overall_status"] = "NOT_A_STATUS"
    report_path.write_bytes(canonical_json_bytes(report, pretty=True))

    def update_identity(value):
        identity = value["jobs"][0]["report"]
        data = report_path.read_bytes()
        identity["size"] = len(data)
        identity["sha256"] = hashlib.sha256(data).hexdigest()

    _rewrite_manifest(manifest, update_identity)
    with pytest.raises(BatchResultBrowserError, match="REPORT_INVALID"):
        inspect_result_bundle(manifest)


def test_manifest_scientific_projection_must_match_verified_report(tmp_path):
    manifest = _bundle(tmp_path, write_csv=False)

    def contradict(value):
        value["jobs"][0]["status"] = "SUCCESS"
        value["jobs"][0]["review_items_count"] = 0
        value["counts"]["REVIEW_ITEMS"] = 0
        value["counts"]["SUCCESS"] = 1

    _rewrite_manifest(manifest, contradict)
    with pytest.raises(BatchResultBrowserError, match="REPORT_RESULT_CONTRADICTION"):
        inspect_result_bundle(manifest)


def test_artifact_inventory_requires_job_derived_role_paths(tmp_path):
    manifest = _bundle(tmp_path)

    def conflict(value):
        value["jobs"][0]["csv"] = copy.deepcopy(value["jobs"][0]["report"])

    _rewrite_manifest(manifest, conflict)
    with pytest.raises(BatchResultBrowserError, match="OUTPUT_INVENTORY_INVALID"):
        inspect_result_bundle(manifest)


def test_manifest_symlink_is_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    manifest = _bundle(source, write_csv=False)
    linked = tmp_path / "linked-result.json"
    try:
        linked.symlink_to(manifest)
    except OSError:
        pytest.skip("file symlink creation is unavailable")
    with pytest.raises(BatchResultBrowserError, match="RESULT_MANIFEST_INVALID"):
        inspect_result_bundle(linked)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction semantics")
def test_result_root_junction_is_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _bundle(source, write_csv=False)
    linked = tmp_path / "linked-root"
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(linked), str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip("junction creation is unavailable")
    with pytest.raises(BatchResultBrowserError, match="RESULT_MANIFEST_INVALID"):
        inspect_result_bundle(linked / "batch-result.json")


def test_absolute_or_traversal_manifest_output_is_rejected(tmp_path):
    manifest = _bundle(tmp_path, write_csv=False)
    for unsafe in ("../one.json", str((tmp_path / "one.json").absolute())):
        original = copy.deepcopy(json.loads(manifest.read_text("utf-8")))
        original["jobs"][0]["report"]["path"] = unsafe
        original["identity_core_sha256"] = identity_core_sha256(original)
        manifest.write_bytes(canonical_json_bytes(original, pretty=True))
        with pytest.raises(BatchResultBrowserError, match="RESULT_MANIFEST_INVALID"):
            inspect_result_bundle(manifest)


def test_semantically_invalid_report_produces_report_invalid_not_uncaught_reporterror(tmp_path):
    """Regression: validate_report() raises ReportError, a subclass of MVQCError, not
    ValueError/BatchContractError. Before the fix, the except clause below did not list
    ReportError, so a report that is JSON-Schema-valid but fails validate_report()'s own
    nonlinear semantic checks (here, the Stage 4 non-unit-normal invariant, which JSON Schema
    cannot express) would propagate as an uncaught ReportError instead of the intended
    BatchResultBrowserError('REPORT_INVALID')."""
    base_report = json.loads((ROOT / "reports" / "pdbtm_synthetic_mvqc.json").read_text("utf-8"))
    manifest = _bundle_with_report(tmp_path, base_report, mode="pdbtm_local", write_csv=False)

    report_path = tmp_path / "one.json"
    report = json.loads(report_path.read_text("utf-8"))
    report["orientation"]["evidence"]["current_geometry"]["normal"] = [0.5, 0.5, 0.6]
    report_path.write_bytes(canonical_json_bytes(report, pretty=True))

    def update_identity(value):
        data = report_path.read_bytes()
        value["jobs"][0]["report"]["size"] = len(data)
        value["jobs"][0]["report"]["sha256"] = hashlib.sha256(data).hexdigest()

    _rewrite_manifest(manifest, update_identity)
    with pytest.raises(BatchResultBrowserError, match="REPORT_INVALID"):
        inspect_result_bundle(manifest)


def test_genuine_schema_1_0_report_passes_the_functions_report_py_fixes(tmp_path):
    """The two functions this PR actually changes (validate_json_schema against schema 1.0, and
    validate_report()) both now accept the genuine historical fixture -- exercised directly the
    same way inspect_result_bundle() calls them for a non-1.5 job (batch_result_browser.py's
    validate_json_schema(...) then validate_report(...) sequence)."""
    from membrane_vqc.batch_contracts import validate_json_schema
    from membrane_vqc.report import validate_report

    report = json.loads(GENUINE_V010_FIXTURE.read_text("utf-8"))
    validate_json_schema(report, "mvqc-report-1.0.schema.json")
    validate_report(report)  # must not raise


def test_manifest_declaring_schema_1_0_is_still_rejected_by_the_batch_result_contract(tmp_path):
    """Documents a real, deliberate scope boundary found while implementing this fix: a manifest
    declaring report_schema '1.0' is rejected before it ever reaches validate_report(), by two
    independent hardcoded allow-lists in membrane_vqc/batch_contracts.py's validate_result()
    (a bare {'1.1'..'1.5'} schema set, and a per-mode expected_schemas mapping -- neither lists
    '1.0'). Normal batch execution can never produce such a manifest itself, and widening the
    batch-result CONTRACT to accept '1.0' is a separate, out-of-scope decision for this PR (which
    touches only membrane_vqc/report.py and the browser's exception handling, not the batch-plan/
    result contract). This test pins today's actual, correct behavior so a future contract change
    is a deliberate, visible decision rather than an accidental regression either way."""
    manifest = _bundle(tmp_path, write_csv=False)
    genuine_report_bytes = GENUINE_V010_FIXTURE.read_bytes()
    (tmp_path / "one.json").write_bytes(genuine_report_bytes)

    def swap_to_legacy_schema(value):
        value["jobs"][0]["report_schema"] = "1.0"
        value["jobs"][0]["report"]["size"] = len(genuine_report_bytes)
        value["jobs"][0]["report"]["sha256"] = hashlib.sha256(genuine_report_bytes).hexdigest()

    _rewrite_manifest(manifest, swap_to_legacy_schema)

    with pytest.raises(BatchResultBrowserError, match="RESULT_MANIFEST_INVALID"):
        inspect_result_bundle(manifest)


def test_valid_current_schema_1_3_report_remains_unaffected_by_the_fix(tmp_path):
    """Confirms the schema-1.0 compatibility fix and the ReportError-catch change do not alter
    behavior for an ordinary, valid, current-generation (non-1.0) report."""
    base_report = json.loads((ROOT / "reports" / "pdbtm_synthetic_mvqc.json").read_text("utf-8"))
    manifest = _bundle_with_report(tmp_path, base_report, mode="pdbtm_local", write_csv=False)

    bundle = inspect_result_bundle(manifest)

    assert bundle.jobs[0].report_schema == "1.3"
    assert bundle.jobs[0].report.availability == "VERIFIED"
    assert bundle.jobs[0].status == "INSUFFICIENT_CONTEXT"
