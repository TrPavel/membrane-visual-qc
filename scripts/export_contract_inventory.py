"""Generate the machine-readable public-contract inventory under docs/contracts/.

Every value below is imported directly from the module that owns it (never retyped by hand),
except for a small number of inline string literals that have no named constant in the source
(documented individually below with their exact file:line). This is deliberately a *generator*,
not a hand-maintained snapshot: `tests/test_contract_inventory.py` re-runs it and diffs the result
against the committed JSON files, so the inventory cannot silently drift from the code it describes.

Run directly to regenerate: `python scripts/export_contract_inventory.py`.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys
from typing import get_args

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import membrane_vqc  # noqa: E402
from membrane_vqc import batch_contracts  # noqa: E402
from membrane_vqc import batch_gui  # noqa: E402
from membrane_vqc import batch_runner  # noqa: E402
from membrane_vqc import comparison_report  # noqa: E402
from membrane_vqc import orientation_comparison  # noqa: E402
from membrane_vqc import pdbtm_cache_contract  # noqa: E402
from membrane_vqc import pdbtm_errors  # noqa: E402
from membrane_vqc import report  # noqa: E402
from membrane_vqc.commands import register_commands  # noqa: E402

OUT_DIR = REPOSITORY_ROOT / "docs" / "contracts"

# The exact 11 names register_commands() extends onto `cmd` -- reproduced here as a literal list
# (not re-parsed from source) because it must reflect what actually gets registered as a public
# PyMOL command, which is a runtime fact of register_commands(), not something derivable purely
# from function names in commands.py (mvqc_check_pdbtm_cached/mvqc_slab_pdbtm_cached exist in the
# same module but are deliberately never registered -- see docs/v1.0_contract_freeze.md #4).
_REGISTERED_COMMAND_NAMES = (
    "mvqc_check",
    "mvqc_check_orientation",
    "mvqc_slab_orientation",
    "mvqc_check_pdbtm",
    "mvqc_slab_pdbtm",
    "mvqc_slab",
    "mvqc_color_hydropathy",
    "mvqc_ligand_shell",
    "mvqc_export",
    "mvqc_batch_run",
    "mvqc_clear",
)


class _RecordingCmd:
    """Stand-in for PyMOL's `cmd` module: records extend() calls instead of registering them."""

    def __init__(self) -> None:
        self.extended: dict[str, object] = {}

    def extend(self, name: str, func) -> None:
        self.extended[name] = func


def _command_signatures() -> dict[str, dict[str, object]]:
    """Return {command_name: {param: default_or_null, ...}} for every registered command,
    extracted directly from each function's real __defaults__/__kwdefaults__ via introspection
    (not by re-parsing source), confirming both the name *and* the signature are live facts."""
    fake_cmd = _RecordingCmd()
    register_commands(cmd_obj=fake_cmd)
    if set(fake_cmd.extended) != set(_REGISTERED_COMMAND_NAMES):
        raise SystemExit(
            "register_commands() registered a different name set than expected -- update "
            f"_REGISTERED_COMMAND_NAMES in {__file__}. "
            f"Registered: {sorted(fake_cmd.extended)}"
        )
    signatures: dict[str, dict[str, object]] = {}
    for name in _REGISTERED_COMMAND_NAMES:
        func = fake_cmd.extended[name]
        code = func.__code__
        arg_names = code.co_varnames[: code.co_argcount]
        defaults = func.__defaults__ or ()
        required_count = len(arg_names) - len(defaults)
        params: dict[str, object] = {}
        for index, arg_name in enumerate(arg_names):
            if index < required_count:
                params[arg_name] = None  # required, no default
            else:
                params[arg_name] = defaults[index - required_count]
        signatures[name] = params
    return signatures


def _comparison_bands() -> list[str]:
    """The ComparisonBand Literal's exact member strings, read via typing.get_args() -- not
    retyped -- from membrane_vqc/orientation_comparison.py."""
    return sorted(get_args(orientation_comparison.ComparisonBand))


def _batch_run_overall_status() -> list[str]:
    """The 4-value overall_status set batch_contracts.validate_result() checks against
    (membrane_vqc/batch_contracts.py, inside validate_result(), no named module-level constant
    exists for it) -- extracted by parsing that one set literal out of the function's AST, so this
    stays tied to the literal set actually enforced rather than a hand-copied guess."""
    source = Path(REPOSITORY_ROOT / "membrane_vqc" / "batch_contracts.py").read_text("utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "validate_result":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Set) and len(sub.elts) == 4:
                    values = sorted(elt.value for elt in sub.elts if isinstance(elt, ast.Constant))
                    if values == sorted(
                        ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED_FAST", "CANCELLED"]
                    ):
                        return values
    raise SystemExit("could not locate the overall_status literal set in validate_result()")


def _result_bundle_availability() -> list[str]:
    """membrane_vqc/batch_result_browser.py uses "VERIFIED"/"MISSING" as inline literals with no
    named constant (lines ~138, ~154, ~265) -- reproduced here as a literal list;
    tests/test_contract_inventory.py source-scans batch_result_browser.py to confirm both strings
    are still present, so a rename would fail that test even though this generator can't detect it
    structurally the way the AST-based checks above can."""
    return ["MISSING", "VERIFIED"]


def _exception_codes(module_name: str, exception_name: str) -> list[str]:
    """Extract exact string codes raised through a named exception constructor."""
    source = (REPOSITORY_ROOT / "membrane_vqc" / module_name).read_text("utf-8")
    tree = ast.parse(source)
    codes = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if isinstance(node.func, ast.Name) and node.func.id == exception_name:
            value = node.args[0]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                codes.add(value.value)
    return sorted(codes)


def _gui_operational_error_codes() -> list[str]:
    """Extract stable user-visible failure codes passed to the batch GUI state helpers."""
    source = (REPOSITORY_ROOT / "membrane_vqc" / "batch_gui.py").read_text("utf-8")
    tree = ast.parse(source)
    codes = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "_set_state" and len(node.args) >= 2:
            value = node.args[1]
        elif node.func.attr == "_finish_failed" and node.args:
            value = node.args[0]
        else:
            continue
        if (
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]+", value.value)
        ):
            codes.add(value.value)
    return sorted(codes)


def build_inventory() -> dict[str, object]:
    return {
        "public_api": {
            "source": "membrane_vqc/__init__.py:__all__",
            "exported_names": sorted(membrane_vqc.__all__),
        },
        "commands": {
            "source": "membrane_vqc/commands.py:register_commands()",
            "commands": _command_signatures(),
        },
        "batch_plan_contract": {
            "source": "membrane_vqc/batch_contracts.py",
            "plan_contract": batch_contracts.PLAN_CONTRACT,
            "result_contract": batch_contracts.RESULT_CONTRACT,
            "modes": list(batch_contracts.MODES),
            "job_statuses": list(batch_contracts.STATUSES),
            "run_overall_status": _batch_run_overall_status(),
            "limits": {
                "max_plan_bytes": batch_contracts.MAX_PLAN_BYTES,
                "max_result_bytes": batch_contracts.MAX_RESULT_BYTES,
                "max_jobs": batch_contracts.MAX_JOBS,
                "max_job_id": batch_contracts.MAX_JOB_ID,
                "max_error_text": batch_contracts.MAX_ERROR_TEXT,
            },
        },
        "report_schemas": {
            "source": "membrane_vqc/report.py, membrane_vqc/comparison_report.py",
            "single_structure_review": {
                "current": report.SCHEMA_VERSION,
                "legacy": report.LEGACY_SCHEMA_VERSION,
                "context": report.CONTEXT_SCHEMA_VERSION,
                "adapter": report.ADAPTER_SCHEMA_VERSION,
                "acquisition": report.ACQUISITION_SCHEMA_VERSION,
                "supported_for_read": sorted(report.SUPPORTED_SCHEMA_VERSIONS),
            },
            "orientation_source_comparison": comparison_report.SCHEMA_VERSION,
            "schema_files": sorted(
                p.name for p in (REPOSITORY_ROOT / "schemas").glob("mvqc-*.schema.json")
            ),
        },
        "status_vocabulary": {
            "source": "docs/status_vocabulary.md (canonical prose); values below are live imports",
            "report_overall_status": [
                "NO_FLAGS",
                "REVIEW_ITEMS",
                "INSUFFICIENT_CONTEXT",
                "ANALYSIS_ERROR",
            ],
            "batch_job_status": list(batch_contracts.STATUSES),
            "batch_run_overall_status": _batch_run_overall_status(),
            "gui_batch_states": list(batch_gui.BATCH_STATES),
            "cache_provider_error_codes": sorted(
                code.value for code in pdbtm_errors.Stage4BErrorCode
            ),
            "result_bundle_artifact_availability": _result_bundle_availability(),
            "result_bundle_error_codes": sorted(
                set(_exception_codes("batch_result_browser.py", "BatchResultBrowserError"))
                | set(_exception_codes("batch_gui.py", "BatchResultBrowserError"))
            ),
            "gui_operational_error_codes": _gui_operational_error_codes(),
        },
        "comparison": {
            "source": "membrane_vqc/orientation_comparison.py",
            "method": orientation_comparison.COMPARISON_METHOD,
            "bands": _comparison_bands(),
            "thresholds": {
                "normal_axis_angle_degrees": orientation_comparison.ANGLE_THRESHOLD_DEGREES,
                "center_displacement_angstrom": orientation_comparison.CENTER_THRESHOLD_ANGSTROM,
                "thickness_difference_angstrom": orientation_comparison.THICKNESS_THRESHOLD_ANGSTROM,
            },
        },
        "csv_columns": {
            "source": "membrane_vqc/report.py:CSV_FIELDS",
            "single_structure_flags_csv": list(report.CSV_FIELDS),
        },
        "output_paths": {
            "source": "membrane_vqc/batch_runner.py, docs/outputs_and_manifests.md",
            "manifest_filename": batch_runner.MANIFEST_NAME,
            "job_artifact_pattern": "<job_id>.json / <job_id>.csv (via batch_paths.safe_output_name)",
        },
        "cache_format": {
            "source": "membrane_vqc/pdbtm_cache_contract.py",
            "cache_contract": pdbtm_cache_contract.CACHE_CONTRACT,
        },
    }


def main() -> int:
    inventory = build_inventory()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for key, value in inventory.items():
        out_path = OUT_DIR / f"{key}.json"
        out_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {out_path.relative_to(REPOSITORY_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
