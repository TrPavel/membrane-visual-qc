from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from membrane_vqc.batch_contracts import (
    BatchContractError,
    canonical_json_bytes,
    load_plan,
    validate_plan,
)


def valid_job(job_id="legacy", analysis=None):
    return {
        "id": job_id,
        "input": {"kind": "pymol", "selection": "protein"},
        "analysis": analysis or {"mode": "legacy_global_z", "zmin": -15, "zmax": 15},
        "output": {"write_csv": True},
    }


def valid_plan(jobs=None):
    return {
        "contract": "mvqc-batch-plan-1.0",
        "jobs": jobs or [valid_job()],
        "execution": {"failure_policy": "continue_on_error", "overwrite": "refuse"},
    }


def test_valid_minimal_plan():
    assert validate_plan(valid_plan())["jobs"][0]["id"] == "legacy"


@pytest.mark.parametrize(
    ("zmin", "zmax", "valid"),
    [
        (-1, 0, True),
        (0, 1, True),
        (-1.0, 1.0, True),
        (0, 0, False),
        (1, 0, False),
        (float("nan"), 1, False),
        (-1, float("nan"), False),
        (float("-inf"), 1, False),
        (-1, float("inf"), False),
    ],
)
def test_legacy_batch_slab_numeric_boundaries(zmin, zmax, valid):
    plan = valid_plan()
    plan["jobs"][0]["analysis"].update({"zmin": zmin, "zmax": zmax})
    if valid:
        assert validate_plan(plan)["jobs"][0]["analysis"]["zmin"] == zmin
    else:
        with pytest.raises(BatchContractError):
            validate_plan(plan)


@pytest.mark.parametrize(
    ("cutoff", "valid"),
    [
        (-1, False),
        (0, False),
        (0.000001, True),
        (1, True),
        (100, True),
        (100.000001, False),
        (float("nan"), False),
        (float("inf"), False),
        (float("-inf"), False),
    ],
)
def test_batch_ligand_cutoff_numeric_boundaries(cutoff, valid):
    plan = valid_plan()
    plan["jobs"][0]["ligand"] = {"selection": "organic", "cutoff": cutoff}
    if valid:
        assert validate_plan(plan)["jobs"][0]["ligand"]["cutoff"] == cutoff
    else:
        with pytest.raises(BatchContractError):
            validate_plan(plan)


def test_canonical_json_rejects_nested_nonfinite_numbers_and_preserves_valid_bytes():
    assert (
        canonical_json_bytes({"nested": [1.0, {"ok": True}]}) == b'{"nested":[1.0,{"ok":true}]}\n'
    )
    for value in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match="Out of range float values"):
            canonical_json_bytes({"nested": [value]})


def test_all_five_modes_are_closed_and_accepted():
    digest = "a" * 64
    jobs = [
        valid_job("legacy"),
        valid_job("planar", {"mode": "planar_orientation", "orientation_json": "orientation.json"}),
        valid_job(
            "local",
            {
                "mode": "pdbtm_local",
                "record_id": "test",
                "pdbtm_json": "pair.json",
                "transformed_pdb": "pair.pdb",
            },
        ),
        valid_job("cached", {"mode": "pdbtm_cache", "record_id": "test", "snapshot_id": digest}),
        valid_job(
            "comparison",
            {
                "mode": "pdbtm_opm_comparison",
                "pdbtm": {"kind": "cache", "record_id": "test", "snapshot_id": digest},
                "opm_pdb": "opm.pdb",
            },
        ),
    ]
    jobs[-1]["output"]["write_csv"] = False
    plan = valid_plan(jobs)
    plan["cache_root"] = "synthetic-cache"
    assert [job["analysis"]["mode"] for job in validate_plan(plan)["jobs"]] == [
        "legacy_global_z",
        "planar_orientation",
        "pdbtm_local",
        "pdbtm_cache",
        "pdbtm_opm_comparison",
    ]
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1] / "schemas" / "mvqc-batch-plan-1.0.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(plan)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda plan: plan["jobs"].append(valid_job()), "unique"),
        (lambda plan: plan.update({"unknown": True}), "closed shape"),
        (lambda plan: plan["jobs"][0]["analysis"].update({"mode": "unknown"}), "unsupported"),
        (lambda plan: plan["jobs"][0]["analysis"].pop("zmin"), "finite"),
        (lambda plan: plan["jobs"][0]["analysis"].update({"zmax": float("inf")}), "finite"),
        (lambda plan: plan.update({"jobs": []}), "between 1"),
        (
            lambda plan: plan.update({"jobs": [valid_job(f"j{index}") for index in range(101)]}),
            "between 1",
        ),
        (lambda plan: plan["jobs"][0].update({"id": "x" * 65}), "must match"),
    ],
)
def test_invalid_plan_shapes(mutation, match):
    plan = valid_plan()
    mutation(plan)
    with pytest.raises(BatchContractError, match=match):
        validate_plan(plan)


@pytest.mark.parametrize(
    "path",
    [
        "../escape.pdb",
        "/absolute.pdb",
        "C:/absolute.pdb",
        "C:drive-relative.pdb",
        "https://example.test/a.pdb",
        r"\\server\share\a.pdb",
        r"\\?\C:\a.pdb",
        "CON.json",
        "dir/NUL.txt",
    ],
)
def test_input_path_policy_rejects_unsafe_cross_platform_paths(path):
    plan = valid_plan()
    plan["jobs"][0]["input"] = {"kind": "file", "path": path}
    with pytest.raises(BatchContractError):
        validate_plan(plan)


def test_json_schema_itself_rejects_traversal():
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1] / "schemas" / "mvqc-batch-plan-1.0.schema.json"
        ).read_text(encoding="utf-8")
    )
    plan = valid_plan()
    plan["jobs"][0]["input"] = {"kind": "file", "path": "../escape.pdb"}
    assert list(Draft202012Validator(schema).iter_errors(plan))


def test_reserved_manifest_job_id_and_oversized_assembly_are_rejected():
    reserved = valid_plan([valid_job("batch-result")])
    with pytest.raises(BatchContractError, match="reserved"):
        validate_plan(reserved)
    assembly = valid_plan(
        [
            valid_job(
                "local",
                {
                    "mode": "pdbtm_local",
                    "record_id": "test",
                    "pdbtm_json": "pair.json",
                    "transformed_pdb": "pair.pdb",
                    "biological_assembly": "x" * 65,
                },
            )
        ]
    )
    with pytest.raises(BatchContractError):
        validate_plan(assembly)


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text('{"contract":"mvqc-batch-plan-1.0","contract":"x"}', encoding="utf-8")
    with pytest.raises(BatchContractError, match="duplicate JSON key"):
        load_plan(path)


def test_empty_mode_specific_input_is_rejected():
    plan = valid_plan([valid_job("planar", {"mode": "planar_orientation", "orientation_json": ""})])
    with pytest.raises(BatchContractError):
        validate_plan(plan)


def test_retained_example_plan_and_negative_fixture():
    root = Path(__file__).resolve().parents[1] / "data" / "synthetic"
    plan, _ = load_plan(root / "stage5a_batch_plan.json")
    assert [job["analysis"]["mode"] for job in plan["jobs"]] == [
        "legacy_global_z",
        "planar_orientation",
        "pdbtm_local",
        "pdbtm_cache",
        "pdbtm_opm_comparison",
    ]
    with pytest.raises(BatchContractError):
        load_plan(root / "stage5a_batch_plan_invalid.json")
