"""Strict PyMOL-free Stage 5A batch plan and result contracts."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Mapping

from .batch_paths import BatchPathError, validate_relative_path


PLAN_CONTRACT = "mvqc-batch-plan-1.0"
RESULT_CONTRACT = "mvqc-batch-result-1.0"
MAX_PLAN_BYTES = 1024 * 1024
MAX_RESULT_BYTES = 4 * 1024 * 1024
MAX_JOBS = 100
MAX_JOB_ID = 64
MAX_ERROR_TEXT = 512
STATUSES = (
    "SUCCESS",
    "REVIEW_ITEMS",
    "INSUFFICIENT_CONTEXT",
    "ANALYSIS_ERROR",
    "INPUT_REJECTED",
    "CANCELLED",
    "SKIPPED_DEPENDENCY",
)
MODES = (
    "legacy_global_z",
    "planar_orientation",
    "pdbtm_local",
    "pdbtm_cache",
    "pdbtm_opm_comparison",
)
_JOB_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$", re.ASCII)
_RECORD_ID = re.compile(r"^[0-9a-z]{4}$", re.ASCII)
_DIGEST = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_COMMIT = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$", re.ASCII)
_SENSITIVE = re.compile(
    r"(?:[A-Za-z]:[\\/]|/(?:home|Users|tmp|var)/|\\\\|https?://|Traceback|password|credential|proxy|token)",
    re.IGNORECASE,
)
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")


class BatchContractError(ValueError):
    """A plan or result violates its closed Stage 5A contract."""


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BatchContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(_: str) -> object:
    raise BatchContractError("non-finite JSON numbers are forbidden")


def canonical_json_bytes(value: object, *, pretty: bool = False) -> bytes:
    """Serialize contract data deterministically as UTF-8 JSON plus LF."""
    options = {"ensure_ascii": False, "allow_nan": False, "sort_keys": True}
    if pretty:
        text = json.dumps(value, indent=2, **options)
    else:
        text = json.dumps(value, separators=(",", ":"), **options)
    return (text + "\n").encode("utf-8")


def _schema_path(name: str) -> Path:
    candidates = (
        Path(__file__).resolve().parent / "schemas" / name,
        Path(__file__).resolve().parents[1] / "schemas" / name,
        Path(sys.prefix) / "schemas" / name,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise BatchContractError(f"required contract schema is unavailable: {name}")


def validate_json_schema(value: object, name: str) -> None:
    """Validate against an installed strict contract without importing PyMOL."""
    try:
        from jsonschema import Draft202012Validator

        schema = json.loads(_schema_path(name).read_text(encoding="utf-8"))
        Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(
            value
        )
    except BatchContractError:
        raise
    except Exception as error:
        raise BatchContractError(f"JSON Schema validation failed for {name}") from error


def load_plan(path: str | Path) -> tuple[dict[str, object], bytes]:
    """Read, strictly parse, and validate one bounded batch-plan document."""
    plan_path = Path(path)
    size = plan_path.stat().st_size
    if size < 2 or size > MAX_PLAN_BYTES:
        raise BatchContractError(f"plan must be between 2 and {MAX_PLAN_BYTES} bytes")
    data = plan_path.read_bytes()
    if len(data) < 2 or len(data) > MAX_PLAN_BYTES:
        raise BatchContractError(f"plan must be between 2 and {MAX_PLAN_BYTES} bytes")
    if data.startswith(b"\xef\xbb\xbf"):
        raise BatchContractError("plan must be UTF-8 without a BOM")
    try:
        plan = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant
        )
    except BatchContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BatchContractError("plan must be strict UTF-8 JSON") from error
    validate_plan(plan)
    return plan, data


def load_result(path: str | Path) -> tuple[dict[str, object], bytes]:
    """Read, strictly parse, and validate one bounded batch-result document."""
    result_path = Path(path)
    size = result_path.stat().st_size
    if size < 2 or size > MAX_RESULT_BYTES:
        raise BatchContractError(f"result must be between 2 and {MAX_RESULT_BYTES} bytes")
    data = result_path.read_bytes()
    if len(data) != size or len(data) < 2 or len(data) > MAX_RESULT_BYTES:
        raise BatchContractError("result changed while it was being read")
    if data.startswith(b"\xef\xbb\xbf"):
        raise BatchContractError("result must be UTF-8 without a BOM")
    try:
        result = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant
        )
    except BatchContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BatchContractError("result must be strict UTF-8 JSON") from error
    validate_result(result)
    return result, data


def _mapping(value: object, *, field: str, required: set[str], optional: set[str] = set()):
    if type(value) is not dict:
        raise BatchContractError(f"{field} must be an object")
    actual = set(value)
    if actual != required | (actual & optional) or not required <= actual:
        raise BatchContractError(
            f"{field} has an invalid closed shape (missing={sorted(required - actual)}, extra={sorted(actual - required - optional)})"
        )
    return value


def _text(value: object, *, field: str, maximum: int = 256, empty: bool = False) -> str:
    if type(value) is not str or len(value) > maximum or (not empty and not value.strip()):
        raise BatchContractError(f"{field} must be a bounded string")
    if any(0xD800 <= ord(char) <= 0xDFFF or ord(char) < 32 for char in value):
        raise BatchContractError(f"{field} contains invalid characters")
    return value


def _finite(value: object, *, field: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise BatchContractError(f"{field} must be finite")
    return float(value)


def _path(value: object, *, field: str) -> str:
    try:
        return validate_relative_path(value, field=field)
    except BatchPathError as error:
        raise BatchContractError(str(error)) from error


def _record(value: object, *, field: str) -> str:
    if type(value) is not str or _RECORD_ID.fullmatch(value) is None:
        raise BatchContractError(f"{field} must be a canonical four-character record ID")
    return value


def _digest(value: object, *, field: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise BatchContractError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _validate_pdbtm_source(value: object, field: str) -> bool:
    source = _mapping(
        value,
        field=field,
        required={"kind", "record_id"},
        optional={"pdbtm_json", "transformed_pdb", "snapshot_id", "biological_assembly"},
    )
    kind = source["kind"]
    _record(source["record_id"], field=f"{field}.record_id")
    if kind == "local":
        if set(source) - {
            "kind",
            "record_id",
            "pdbtm_json",
            "transformed_pdb",
            "biological_assembly",
        } or not {"pdbtm_json", "transformed_pdb"} <= set(source):
            raise BatchContractError(f"{field} local source is incomplete or ambiguous")
        _path(source["pdbtm_json"], field=f"{field}.pdbtm_json")
        _path(source["transformed_pdb"], field=f"{field}.transformed_pdb")
        return False
    if kind == "cache":
        if (
            set(source) - {"kind", "record_id", "snapshot_id", "biological_assembly"}
            or "snapshot_id" not in source
        ):
            raise BatchContractError(f"{field} cache source is incomplete or ambiguous")
        _digest(source["snapshot_id"], field=f"{field}.snapshot_id")
        return True
    raise BatchContractError(f"{field}.kind has an unknown discriminator")


def validate_plan(value: object) -> dict[str, object]:
    """Validate the closed discriminated Stage 5A plan contract."""
    plan = _mapping(
        value,
        field="plan",
        required={"contract", "jobs", "execution"},
        optional={"cache_root"},
    )
    if plan["contract"] != PLAN_CONTRACT:
        raise BatchContractError(f"contract must be {PLAN_CONTRACT}")
    jobs = plan["jobs"]
    if type(jobs) is not list or not jobs or len(jobs) > MAX_JOBS:
        raise BatchContractError(f"jobs must contain between 1 and {MAX_JOBS} entries")
    uses_cache = False
    ids: set[str] = set()
    for index, raw_job in enumerate(jobs):
        field = f"jobs[{index}]"
        job = _mapping(
            raw_job,
            field=field,
            required={"id", "input", "analysis", "output"},
            optional={"context", "ligand"},
        )
        job_id = job["id"]
        if type(job_id) is not str or _JOB_ID.fullmatch(job_id) is None:
            raise BatchContractError(f"{field}.id must match {_JOB_ID.pattern}")
        if job_id in ids:
            raise BatchContractError("job IDs must be unique")
        if f"{job_id}.json" == "batch-result.json":
            raise BatchContractError("job ID collides with the reserved batch manifest")
        ids.add(job_id)
        input_spec = _mapping(
            job["input"], field=f"{field}.input", required={"kind"}, optional={"selection", "path"}
        )
        if input_spec["kind"] == "pymol" and set(input_spec) == {"kind", "selection"}:
            _text(input_spec["selection"], field=f"{field}.input.selection")
        elif input_spec["kind"] == "file" and set(input_spec) == {"kind", "path"}:
            _path(input_spec["path"], field=f"{field}.input.path")
        else:
            raise BatchContractError(f"{field}.input has an invalid discriminator or shape")
        analysis = _mapping(
            job["analysis"],
            field=f"{field}.analysis",
            required={"mode"},
            optional={
                "zmin",
                "zmax",
                "orientation_json",
                "record_id",
                "pdbtm_json",
                "transformed_pdb",
                "snapshot_id",
                "biological_assembly",
                "pdbtm",
                "opm_pdb",
            },
        )
        mode = analysis["mode"]
        if mode not in MODES:
            raise BatchContractError(f"{field}.analysis.mode is unsupported")
        allowed: set[str]
        required: set[str]
        if mode == "legacy_global_z":
            allowed, required = {"mode", "zmin", "zmax"}, {"zmin", "zmax"}
            lower = _finite(analysis.get("zmin"), field=f"{field}.analysis.zmin")
            upper = _finite(analysis.get("zmax"), field=f"{field}.analysis.zmax")
            if lower >= upper:
                raise BatchContractError("legacy zmin must be less than zmax")
        elif mode == "planar_orientation":
            allowed, required = {"mode", "orientation_json"}, {"orientation_json"}
            _path(analysis.get("orientation_json"), field=f"{field}.analysis.orientation_json")
        elif mode == "pdbtm_local":
            allowed = {"mode", "record_id", "pdbtm_json", "transformed_pdb", "biological_assembly"}
            required = {"record_id", "pdbtm_json", "transformed_pdb"}
            _record(analysis.get("record_id"), field=f"{field}.analysis.record_id")
            _path(analysis.get("pdbtm_json"), field=f"{field}.analysis.pdbtm_json")
            _path(analysis.get("transformed_pdb"), field=f"{field}.analysis.transformed_pdb")
        elif mode == "pdbtm_cache":
            allowed = {"mode", "record_id", "snapshot_id", "biological_assembly"}
            required = {"record_id", "snapshot_id"}
            _record(analysis.get("record_id"), field=f"{field}.analysis.record_id")
            _digest(analysis.get("snapshot_id"), field=f"{field}.analysis.snapshot_id")
            uses_cache = True
        else:
            allowed, required = {"mode", "pdbtm", "opm_pdb"}, {"pdbtm", "opm_pdb"}
            uses_cache |= _validate_pdbtm_source(analysis.get("pdbtm"), f"{field}.analysis.pdbtm")
            _path(analysis.get("opm_pdb"), field=f"{field}.analysis.opm_pdb")
        if not required <= set(analysis) or set(analysis) - allowed:
            raise BatchContractError(f"{field}.analysis is incomplete or ambiguous")
        if "biological_assembly" in analysis:
            _text(
                analysis["biological_assembly"],
                field=f"{field}.analysis.biological_assembly",
                maximum=64,
            )
        source = analysis.get("pdbtm")
        if isinstance(source, dict) and "biological_assembly" in source:
            _text(
                source["biological_assembly"],
                field=f"{field}.analysis.pdbtm.biological_assembly",
                maximum=64,
            )
        output = _mapping(job["output"], field=f"{field}.output", required={"write_csv"})
        if type(output["write_csv"]) is not bool:
            raise BatchContractError(f"{field}.output.write_csv must be boolean")
        if mode == "pdbtm_opm_comparison" and output["write_csv"]:
            raise BatchContractError("comparison jobs do not support CSV output")
        if "context" in job:
            context = _mapping(
                job["context"],
                field=f"{field}.context",
                required={"enabled"},
                optional={"quality", "backend"},
            )
            if type(context["enabled"]) is not bool:
                raise BatchContractError(f"{field}.context.enabled must be boolean")
            if context.get("quality", "Standard") not in {
                "Fast",
                "Standard",
                "High",
            } or context.get("backend", "Built-in") not in {"Built-in", "FreeSASA"}:
                raise BatchContractError(f"{field}.context has unsupported settings")
        if "ligand" in job:
            ligand = _mapping(
                job["ligand"], field=f"{field}.ligand", required={"selection", "cutoff"}
            )
            _text(ligand["selection"], field=f"{field}.ligand.selection", empty=True)
            cutoff = _finite(ligand["cutoff"], field=f"{field}.ligand.cutoff")
            if not 0 < cutoff <= 100:
                raise BatchContractError("ligand cutoff must be in (0, 100]")
    execution = _mapping(
        plan["execution"], field="execution", required={"failure_policy", "overwrite"}
    )
    if execution["failure_policy"] not in {"continue_on_error", "fail_fast"} or execution[
        "overwrite"
    ] not in {"refuse", "same_batch"}:
        raise BatchContractError("execution policy is unsupported")
    if uses_cache:
        if "cache_root" not in plan:
            raise BatchContractError("cache_root is required for exact cached jobs")
        _path(plan["cache_root"], field="cache_root")
    elif "cache_root" in plan:
        _path(plan["cache_root"], field="cache_root")
    validate_json_schema(plan, "mvqc-batch-plan-1.0.schema.json")
    return plan


def identity_core(result: Mapping[str, object]) -> dict[str, object]:
    """Return the stable result core excluding run ID and run timestamps."""
    jobs = []
    for raw in result["jobs"]:
        job = dict(raw)
        for label in ("report", "csv"):
            identity = job[label]
            if identity is not None:
                job[label] = {"path": identity["path"]}
        jobs.append(job)
    return {
        "contract": result["contract"],
        "plan_sha256": result["plan_sha256"],
        "software": result["software"],
        "execution": result["execution"],
        "jobs": jobs,
        "counts": result["counts"],
        "overall_status": result["overall_status"],
    }


def identity_core_sha256(result: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(identity_core(result))).hexdigest()


def validate_run_id(value: object) -> str:
    """Validate one explicit same-batch run identity before any output is touched."""
    return _digest(value, field="run_id")


def validate_result(value: object) -> dict[str, object]:
    """Validate result closure, privacy, aggregates, and stable identity."""
    result = _mapping(
        value,
        field="result",
        required={
            "contract",
            "plan_sha256",
            "run_id",
            "software",
            "started_at",
            "completed_at",
            "execution",
            "jobs",
            "counts",
            "overall_status",
            "identity_core_sha256",
        },
    )
    if result["contract"] != RESULT_CONTRACT:
        raise BatchContractError("invalid batch-result contract")
    _digest(result["plan_sha256"], field="plan_sha256")
    _digest(result["run_id"], field="run_id")
    software = _mapping(result["software"], field="software", required={"version", "commit"})
    _text(software["version"], field="software.version", maximum=64)
    if software["commit"] is not None and (
        type(software["commit"]) is not str or _COMMIT.fullmatch(software["commit"]) is None
    ):
        raise BatchContractError("software.commit must be null or a Git SHA")
    parsed_timestamps = []
    for field in ("started_at", "completed_at"):
        timestamp = _text(result[field], field=field, maximum=64)
        if _UTC_TIMESTAMP.fullmatch(timestamp) is None:
            raise BatchContractError(f"{field} must be a UTC timestamp ending in Z")
        try:
            parsed_timestamps.append(datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00"))
        except ValueError as error:
            raise BatchContractError(f"{field} must be a valid UTC timestamp") from error
    if parsed_timestamps[1] < parsed_timestamps[0]:
        raise BatchContractError("completed_at must not precede started_at")
    execution = _mapping(
        result["execution"], field="execution", required={"failure_policy", "overwrite"}
    )
    if execution["failure_policy"] not in {"continue_on_error", "fail_fast"} or execution[
        "overwrite"
    ] not in {"refuse", "same_batch"}:
        raise BatchContractError("invalid result execution policy")
    jobs = result["jobs"]
    if type(jobs) is not list or not jobs or len(jobs) > MAX_JOBS:
        raise BatchContractError("result jobs are invalid")
    observed: Counter[str] = Counter()
    seen: set[str] = set()
    for index, raw in enumerate(jobs):
        job = _mapping(
            raw,
            field=f"jobs[{index}]",
            required={
                "job_id",
                "mode",
                "status",
                "error_code",
                "report",
                "report_schema",
                "csv",
                "warnings_count",
                "review_items_count",
                "coordinate_preserved",
            },
        )
        job_id = job["job_id"]
        if type(job_id) is not str or _JOB_ID.fullmatch(job_id) is None or job_id in seen:
            raise BatchContractError("result job IDs are invalid or duplicated")
        seen.add(job_id)
        if job["mode"] not in MODES or job["status"] not in STATUSES:
            raise BatchContractError("result mode or status is invalid")
        observed[job["status"]] += 1
        failed = job["status"] in {"ANALYSIS_ERROR", "INPUT_REJECTED"}
        if failed:
            if (
                type(job["error_code"]) is not str
                or _ERROR_CODE.fullmatch(job["error_code"]) is None
            ):
                raise BatchContractError("failed jobs require a stable error code")
        elif job["error_code"] is not None:
            raise BatchContractError("non-failed jobs must not have an error code")
        for label in ("report", "csv"):
            item = job[label]
            if item is not None:
                identity = _mapping(item, field=f"job.{label}", required={"path", "size", "sha256"})
                _path(identity["path"], field=f"job.{label}.path")
                if type(identity["size"]) is not int or identity["size"] < 0:
                    raise BatchContractError("output size must be non-negative")
                _digest(identity["sha256"], field=f"job.{label}.sha256")
        successful = job["status"] in {"SUCCESS", "REVIEW_ITEMS", "INSUFFICIENT_CONTEXT"}
        if successful != (job["report"] is not None):
            raise BatchContractError("report presence contradicts operational status")
        if successful and job["report_schema"] not in {"1.1", "1.2", "1.3", "1.4", "1.5"}:
            raise BatchContractError("successful job has an invalid report schema")
        if not successful and job["report_schema"] is not None:
            raise BatchContractError("failed/skipped job must not claim a report schema")
        expected_schemas = {
            "legacy_global_z": {"1.1", "1.2"},
            "planar_orientation": {"1.1", "1.2"},
            "pdbtm_local": {"1.3"},
            "pdbtm_cache": {"1.4"},
            "pdbtm_opm_comparison": {"1.5"},
        }
        if successful and job["report_schema"] not in expected_schemas[job["mode"]]:
            raise BatchContractError("report schema contradicts the analysis mode")
        if job["mode"] == "pdbtm_opm_comparison" and job["csv"] is not None:
            raise BatchContractError("comparison results cannot contain CSV output")
        if type(job["warnings_count"]) is not int or job["warnings_count"] < 0:
            raise BatchContractError("warnings_count must be non-negative")
        if job["review_items_count"] is not None and (
            type(job["review_items_count"]) is not int or job["review_items_count"] < 0
        ):
            raise BatchContractError("review_items_count must be null or non-negative")
        if job["coordinate_preserved"] not in {True, False, None}:
            raise BatchContractError("coordinate_preserved must be boolean or null")
        if successful and job["coordinate_preserved"] is not True:
            raise BatchContractError("successful jobs require coordinate preservation")
        if not successful and job["coordinate_preserved"] is not None:
            raise BatchContractError("unsuccessful jobs cannot claim coordinate preservation")
    counts = _mapping(result["counts"], field="counts", required={"total", *STATUSES})
    if type(counts["total"]) is not int or counts["total"] != len(jobs):
        raise BatchContractError("aggregate total contradicts jobs")
    if any(
        type(counts[status]) is not int or counts[status] != observed[status] for status in STATUSES
    ):
        raise BatchContractError("aggregate status counts contradict jobs")
    if result["overall_status"] not in {
        "COMPLETED",
        "COMPLETED_WITH_ERRORS",
        "FAILED_FAST",
        "CANCELLED",
    }:
        raise BatchContractError("overall status is invalid")
    if observed["CANCELLED"]:
        expected_overall = "CANCELLED"
    elif execution["failure_policy"] == "fail_fast" and (
        observed["ANALYSIS_ERROR"] or observed["INPUT_REJECTED"]
    ):
        expected_overall = "FAILED_FAST"
    elif observed["ANALYSIS_ERROR"] or observed["INPUT_REJECTED"]:
        expected_overall = "COMPLETED_WITH_ERRORS"
    else:
        expected_overall = "COMPLETED"
    if result["overall_status"] != expected_overall:
        raise BatchContractError("overall status contradicts job counts and execution policy")
    if _SENSITIVE.search(canonical_json_bytes(result, pretty=True).decode("utf-8")):
        raise BatchContractError("batch result contains sensitive material")
    expected = identity_core_sha256(result)
    if result["identity_core_sha256"] != expected:
        raise BatchContractError("identity core digest is inconsistent")
    validate_json_schema(result, "mvqc-batch-result-1.0.schema.json")
    return result
