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
