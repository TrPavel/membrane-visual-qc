"""Regression tests for the v1.0 contract freeze (docs/v1.0_contract_freeze.md).

These tests lock in the exact shape of every interface that page declares Frozen, so a
change to any of them fails a test here -- forcing the change to go through
docs/versioning_policy.md's deprecation process and an update to the contract-freeze
page in the same PR, rather than drifting silently. They deliberately do not test
Not frozen / Internal interfaces (scientific thresholds, GUI layout, module internals)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from membrane_vqc import commands, errors
from membrane_vqc.batch_contracts import MODES, PLAN_CONTRACT, RESULT_CONTRACT, STATUSES
from membrane_vqc.batch_gui import BATCH_STATES
from membrane_vqc.pdbtm_cache import _CACHE_SUFFIX
from membrane_vqc.pdbtm_errors import Stage4BErrorCode

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# 4. PyMOL commands (frozen: names and existing parameters)
# ---------------------------------------------------------------------------

FROZEN_COMMANDS = {
    "mvqc_check": {
        "selection": "all",
        "zmin": commands.DEFAULT_ZMIN,
        "zmax": commands.DEFAULT_ZMAX,
        "ligand": "organic",
        "cutoff": commands.DEFAULT_LIGAND_CUTOFF,
        "quiet": 1,
        "export_path": "",
        "input_path": "",
        "analyze_context": 0,
        "exposure_quality": "Standard",
        "exposure_backend": "Built-in",
    },
    "mvqc_slab": {"zmin": commands.DEFAULT_ZMIN, "zmax": commands.DEFAULT_ZMAX},
    "mvqc_check_orientation": {
        "selection": "all",
        "orientation_file": "",
        "ligand": "organic",
        "cutoff": commands.DEFAULT_LIGAND_CUTOFF,
        "quiet": 1,
        "export_path": "",
        "input_path": "",
        "analyze_context": 0,
        "exposure_quality": "Standard",
        "exposure_backend": "Built-in",
    },
    "mvqc_slab_orientation": {"selection": "all", "orientation_file": ""},
    "mvqc_check_pdbtm": {
        "selection": "all",
        "pdbtm_json": "",
        "transformed_pdb": "",
        "biological_assembly": "",
        "ligand": "organic",
        "cutoff": commands.DEFAULT_LIGAND_CUTOFF,
        "quiet": 1,
        "export_path": "",
        "input_path": "",
        "analyze_context": 0,
        "exposure_quality": "Standard",
        "exposure_backend": "Built-in",
    },
    "mvqc_slab_pdbtm": {
        "selection": "all",
        "pdbtm_json": "",
        "transformed_pdb": "",
        "biological_assembly": "",
    },
    "mvqc_color_hydropathy": {"selection": "all"},
    "mvqc_ligand_shell": {
        "protein": "all",
        "ligand": "organic",
        "cutoff": commands.DEFAULT_LIGAND_CUTOFF,
    },
    "mvqc_export": {"path": "reports/mvqc_report.json"},
    "mvqc_batch_run": {
        "plan": "",
        "output_dir": "",
        "fail_fast": 0,
        "quiet": 1,
        "run_id": "",
    },
    "mvqc_clear": {},
}


class _RecordingCmd:
    """Stand-in for PyMOL's `cmd` object that only records `.extend()` calls."""

    def __init__(self):
        self.registered: dict[str, object] = {}

    def extend(self, name, function):
        self.registered[name] = function


def test_pymol_commands_are_the_frozen_set():
    recorder = _RecordingCmd()
    commands.register_commands(cmd_obj=recorder)
    assert set(recorder.registered) == set(FROZEN_COMMANDS)


def test_pymol_command_signatures_match_frozen_defaults():
    recorder = _RecordingCmd()
    commands.register_commands(cmd_obj=recorder)
    for name, expected_defaults in FROZEN_COMMANDS.items():
        signature = inspect.signature(recorder.registered[name])
        actual_defaults = {
            parameter.name: parameter.default
            for parameter in signature.parameters.values()
            if parameter.default is not inspect.Parameter.empty
        }
        assert set(expected_defaults) <= set(actual_defaults), (
            f"{name} is missing frozen parameter(s): "
            f"{set(expected_defaults) - set(actual_defaults)}"
        )
        for parameter_name, expected_default in expected_defaults.items():
            assert actual_defaults[parameter_name] == expected_default, (
                f"{name}({parameter_name}=...) default changed: "
                f"expected {expected_default!r}, got {actual_defaults[parameter_name]!r}"
            )


def test_pdbtm_cached_helpers_remain_internal_not_pymol_commands():
    recorder = _RecordingCmd()
    commands.register_commands(cmd_obj=recorder)
    assert "mvqc_check_pdbtm_cached" not in recorder.registered
    assert "mvqc_slab_pdbtm_cached" not in recorder.registered
    assert hasattr(commands, "mvqc_check_pdbtm_cached")
    assert hasattr(commands, "mvqc_slab_pdbtm_cached")


# ---------------------------------------------------------------------------
# 2 & 3. Batch contracts and modes (frozen)
# ---------------------------------------------------------------------------


def test_batch_contract_identifiers_are_frozen():
    assert PLAN_CONTRACT == "mvqc-batch-plan-1.0"
    assert RESULT_CONTRACT == "mvqc-batch-result-1.0"


def test_batch_modes_are_the_frozen_closed_set():
    assert set(MODES) == {
        "legacy_global_z",
        "planar_orientation",
        "pdbtm_local",
        "pdbtm_cache",
        "pdbtm_opm_comparison",
    }


def test_batch_job_statuses_are_the_frozen_set():
    assert set(STATUSES) == {
        "SUCCESS",
        "REVIEW_ITEMS",
        "INSUFFICIENT_CONTEXT",
        "ANALYSIS_ERROR",
        "INPUT_REJECTED",
        "CANCELLED",
        "SKIPPED_DEPENDENCY",
    }


def test_batch_gui_states_are_the_frozen_set():
    assert set(BATCH_STATES) == {
        "IDLE",
        "VALIDATING",
        "READY",
        "RUNNING",
        "CANCELLING",
        "COMPLETED",
        "CANCELLED",
        "FAILED",
    }


# ---------------------------------------------------------------------------
# 6. Error code vocabulary (frozen, additive-only)
# ---------------------------------------------------------------------------


def test_cache_provider_error_codes_are_at_least_the_frozen_set():
    frozen = {
        "INVALID_RECORD_ID",
        "CACHE_MISS",
        "CACHE_CORRUPT",
        "CACHE_WRITE_FAILED",
        "CACHE_DURABILITY_UNCERTAIN",
        "CACHE_CONFLICT",
        "CACHE_FORMAT_UNSUPPORTED",
        "CACHE_CLEAR_FAILED",
        "CACHE_OPEN_FAILED",
        "NETWORK_TIMEOUT",
        "NETWORK_UNAVAILABLE",
        "PROXY_UNSUPPORTED",
        "TLS_ERROR",
        "REDIRECT_DISALLOWED",
        "RESPONSE_TOO_LARGE",
        "PROVIDER_NOT_FOUND",
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_SERVER_ERROR",
        "PROVIDER_RESPONSE_INVALID",
        "COMPANION_ID_MISMATCH",
        "PAIR_VALIDATION_FAILED",
        "RETRIEVAL_CANCELLED",
    }
    actual = {code.value for code in Stage4BErrorCode}
    missing = frozen - actual
    assert not missing, f"frozen error code(s) removed or renamed: {missing}"


def test_exception_class_hierarchy_is_frozen():
    assert issubclass(errors.InputValidationError, (errors.MVQCError, ValueError))
    for name in (
        "StructureParseError",
        "OrientationError",
        "ExternalServiceError",
        "OptionalDependencyError",
        "ReportError",
        "PyMOLAdapterError",
    ):
        cls = getattr(errors, name)
        assert issubclass(cls, errors.MVQCError), f"{name} must remain a subclass of MVQCError"


def test_other_typed_exception_classes_exist_with_frozen_names():
    from membrane_vqc.batch_contracts import BatchContractError
    from membrane_vqc.batch_paths import BatchPathError
    from membrane_vqc.batch_result_browser import BatchResultBrowserError
    from membrane_vqc.batch_runner import BatchCancelled, BatchExecutionFailed, BatchInputRejected
    from membrane_vqc.pdbtm_cache_contract import CacheContractError
    from membrane_vqc.pdbtm_errors import Stage4BError
    from membrane_vqc.pdbtm_pymol import PdbtmCommandError
    from membrane_vqc.pdbtm_report_provenance import ProvenanceConversionError

    assert issubclass(BatchContractError, ValueError)
    assert issubclass(BatchPathError, ValueError)
    assert issubclass(BatchResultBrowserError, ValueError)
    assert issubclass(BatchInputRejected, ValueError)
    assert issubclass(BatchExecutionFailed, RuntimeError)
    assert issubclass(BatchCancelled, RuntimeError)
    assert issubclass(CacheContractError, ValueError)
    assert issubclass(Stage4BError, errors.MVQCError)
    assert issubclass(PdbtmCommandError, errors.PyMOLAdapterError)
    assert issubclass(ProvenanceConversionError, errors.OrientationError)


# ---------------------------------------------------------------------------
# 7. Cache format (frozen)
# ---------------------------------------------------------------------------


def test_cache_path_suffix_and_env_var_are_frozen():
    assert _CACHE_SUFFIX == ("pdbtm-api-v1", "cache-v1")
    import membrane_vqc.pdbtm_cache as pdbtm_cache_module

    source = inspect.getsource(pdbtm_cache_module.select_cache_root)
    assert "MVQC_CACHE_DIR" in source


# ---------------------------------------------------------------------------
# 9. Batch limits named in docs/v1.0_contract_freeze.md and docs/batch_plan.md
# ---------------------------------------------------------------------------


def test_batch_contract_limits_match_the_documented_values():
    from membrane_vqc.batch_contracts import MAX_JOB_ID, MAX_JOBS, MAX_PLAN_BYTES, MAX_RESULT_BYTES

    assert MAX_PLAN_BYTES == 1024 * 1024
    assert MAX_RESULT_BYTES == 4 * 1024 * 1024
    assert MAX_JOBS == 100
    assert MAX_JOB_ID == 64


# ---------------------------------------------------------------------------
# 8. Genuine v0.7.0 historical fixture (self-consistency)
# ---------------------------------------------------------------------------


def test_v070_fixture_manifest_declares_the_correct_version():
    manifest = json.loads(
        (ROOT / "tests" / "fixtures" / "v0.7.0" / "PLUGIN_MANIFEST.json").read_text("utf-8")
    )
    assert manifest["format_version"] == 1
    assert manifest["plugin"]["version"] == "0.7.0"
    assert manifest["plugin"]["package"] == "membrane_vqc"


def test_v070_fixture_checksums_agree_with_the_manifest():
    fixture_dir = ROOT / "tests" / "fixtures" / "v0.7.0"
    manifest = json.loads((fixture_dir / "PLUGIN_MANIFEST.json").read_text("utf-8"))
    checksums_text = (fixture_dir / "SHA256SUMS.txt").read_text("ascii")
    checksum_lines = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in checksums_text.splitlines()
        if line.strip()
    }
    manifest_names = {entry["path"] for entry in manifest["files"]}
    # SHA256SUMS.txt covers every packaged file plus the manifest itself.
    assert manifest_names <= set(checksum_lines)
    for entry in manifest["files"]:
        assert checksum_lines[entry["path"]] == entry["sha256"]


def test_v070_fixture_matches_frozen_release_evidence():
    evidence = json.loads((ROOT / "docs" / "v0.7.0_release_evidence.json").read_text("utf-8"))
    assert evidence["version"] == "0.7.0"
    assert evidence["assets"]["MembraneVisualQC-0.7.0.zip"]["size"] == 194334
    assert (
        evidence["assets"]["MembraneVisualQC-0.7.0.zip"]["sha256"]
        == "4672b1b91657d0ddea9d839e99de6b1b4642a17a0008afc99ae78f5eff55fda4"
    )
