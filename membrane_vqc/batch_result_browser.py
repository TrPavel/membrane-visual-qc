"""Read-only integrity verification for explicitly selected Stage 5A result bundles."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .batch_contracts import BatchContractError, load_result, validate_json_schema
from .batch_paths import BatchPathError, resolve_existing_root, resolve_input_path, safe_output_name
from .batch_runner import BatchExecutionFailed, _scientific_status
from .comparison_report import validate_comparison_report
from .report import ReportError, validate_report


MAX_REFERENCED_FILE_BYTES = 64 * 1024 * 1024
MAX_REFERENCED_TOTAL_BYTES = 512 * 1024 * 1024
MAX_DETAIL_TEXT = 512


class BatchResultBrowserError(ValueError):
    """An explicitly selected result bundle is unsafe or internally inconsistent."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class VerifiedArtifact:
    role: str
    relative_path: str
    expected_size: int
    expected_sha256: str
    path: Path | None
    availability: str


@dataclass(frozen=True, slots=True)
class VerifiedJob:
    job_id: str
    mode: str
    status: str
    report_schema: str | None
    review_items_count: int | None
    warnings_count: int
    error_code: str | None
    coordinate_preserved: bool | None
    report: VerifiedArtifact | None
    csv: VerifiedArtifact | None
    summary: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class VerifiedBatchResult:
    manifest_path: Path
    output_root: Path
    manifest_size: int
    manifest_sha256: str
    plan_sha256: str
    identity_core_sha256: str
    run_id: str
    overall_status: str
    started_at: str
    completed_at: str
    software_version: str
    counts: Mapping[str, int]
    jobs: tuple[VerifiedJob, ...]


def _strict_json(data: bytes) -> dict[str, object]:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise BatchResultBrowserError("REPORT_JSON_INVALID")
            result[key] = value
        return result

    def reject_constant(_):
        raise BatchResultBrowserError("REPORT_JSON_INVALID")

    try:
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject_constant
        )
    except BatchResultBrowserError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BatchResultBrowserError("REPORT_JSON_INVALID") from error
    if type(value) is not dict:
        raise BatchResultBrowserError("REPORT_JSON_INVALID")
    return value


def _read_verified(path: Path, identity: Mapping[str, object]) -> bytes:
    expected_size = int(identity["size"])
    if expected_size > MAX_REFERENCED_FILE_BYTES:
        raise BatchResultBrowserError("OUTPUT_SIZE_INVALID")
    try:
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
    except OSError as error:
        raise BatchResultBrowserError("OUTPUT_UNAVAILABLE") from error
    if (
        before.st_size != expected_size
        or after.st_size != expected_size
        or len(data) != expected_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ino != after.st_ino
    ):
        raise BatchResultBrowserError("OUTPUT_IDENTITY_CHANGED")
    if hashlib.sha256(data).hexdigest() != identity["sha256"]:
        raise BatchResultBrowserError("OUTPUT_IDENTITY_CHANGED")
    return data


def _artifact(
    root: Path, role: str, identity: Mapping[str, object] | None
) -> tuple[VerifiedArtifact | None, bytes | None]:
    if identity is None:
        return None, None
    relative = str(identity["path"])
    try:
        path = resolve_input_path(root, relative, field=f"result.{role}")
    except FileNotFoundError:
        return (
            VerifiedArtifact(
                role,
                relative,
                int(identity["size"]),
                str(identity["sha256"]),
                None,
                "MISSING",
            ),
            None,
        )
    except BatchPathError as error:
        raise BatchResultBrowserError("OUTPUT_PATH_UNSAFE") from error
    except OSError as error:
        raise BatchResultBrowserError("OUTPUT_UNAVAILABLE") from error
    data = _read_verified(path, identity)
    return (
        VerifiedArtifact(
            role,
            relative,
            int(identity["size"]),
            str(identity["sha256"]),
            path,
            "VERIFIED",
        ),
        data,
    )


def _safe_report_summary(report: Mapping[str, object]) -> Mapping[str, object]:
    schema = str(report.get("schema_version", ""))
    summary = report.get("summary")
    comparison = report.get("comparison")
    source = report.get("orientation")
    value: dict[str, object] = {"report_schema": schema}
    if isinstance(summary, Mapping):
        value["review_status"] = str(summary.get("overall_status", ""))[:MAX_DETAIL_TEXT]
    if isinstance(source, Mapping):
        value["source"] = str(source.get("source", source.get("mode", "")))[:MAX_DETAIL_TEXT]
    if isinstance(comparison, Mapping):
        value["comparison_band"] = str(comparison.get("band", ""))[:MAX_DETAIL_TEXT]
        value["comparable"] = comparison.get("comparable") is True
    return MappingProxyType(value)


def inspect_result_bundle(manifest_path: str | Path) -> VerifiedBatchResult:
    """Validate one explicit manifest and every available referenced artifact."""
    selected = Path(manifest_path).absolute()
    try:
        root = resolve_existing_root(selected.parent)
        resolved_manifest = resolve_input_path(root, selected.name, field="result manifest")
        result, data = load_result(resolved_manifest)
    except (BatchContractError, BatchPathError, OSError) as error:
        raise BatchResultBrowserError("RESULT_MANIFEST_INVALID") from error
    total_declared = 0
    referenced_paths: set[str] = set()
    jobs: list[VerifiedJob] = []
    for item in result["jobs"]:
        for role in ("report", "csv"):
            identity = item[role]
            if identity is not None:
                expected_path = safe_output_name(
                    str(item["job_id"]), ".json" if role == "report" else ".csv"
                )
                relative_path = str(identity["path"])
                path_key = relative_path.casefold()
                if relative_path != expected_path or path_key in referenced_paths:
                    raise BatchResultBrowserError("OUTPUT_INVENTORY_INVALID")
                referenced_paths.add(path_key)
                total_declared += int(identity["size"])
        if total_declared > MAX_REFERENCED_TOTAL_BYTES:
            raise BatchResultBrowserError("OUTPUT_TOTAL_LIMIT_EXCEEDED")
        report_artifact, report_bytes = _artifact(root, "report", item["report"])
        csv_artifact, _ = _artifact(root, "csv", item["csv"])
        report_summary: Mapping[str, object] = MappingProxyType({})
        if report_bytes is not None:
            report = _strict_json(report_bytes)
            schema = str(item["report_schema"])
            try:
                validate_json_schema(report, f"mvqc-report-{schema}.schema.json")
                if schema == "1.5":
                    validate_comparison_report(report)
                else:
                    validate_report(report)
            except (BatchContractError, ReportError, TypeError, ValueError) as error:
                raise BatchResultBrowserError("REPORT_INVALID") from error
            if report.get("schema_version") != schema:
                raise BatchResultBrowserError("REPORT_SCHEMA_MISMATCH")
            try:
                status, review_items, warnings = _scientific_status(report)
            except BatchExecutionFailed as error:
                raise BatchResultBrowserError("REPORT_INVALID") from error
            if (
                item["status"] != status
                or item["review_items_count"] != review_items
                or item["warnings_count"] != warnings
                or item["coordinate_preserved"] is not True
            ):
                raise BatchResultBrowserError("REPORT_RESULT_CONTRADICTION")
            report_summary = _safe_report_summary(report)
        jobs.append(
            VerifiedJob(
                str(item["job_id"]),
                str(item["mode"]),
                str(item["status"]),
                item["report_schema"],
                item["review_items_count"],
                int(item["warnings_count"]),
                item["error_code"],
                item["coordinate_preserved"],
                report_artifact,
                csv_artifact,
                report_summary,
            )
        )
    return VerifiedBatchResult(
        resolved_manifest,
        root,
        len(data),
        hashlib.sha256(data).hexdigest(),
        str(result["plan_sha256"]),
        str(result["identity_core_sha256"]),
        str(result["run_id"]),
        str(result["overall_status"]),
        str(result["started_at"]),
        str(result["completed_at"]),
        str(result["software"]["version"]),
        MappingProxyType(dict(result["counts"])),
        tuple(jobs),
    )


def revalidate_artifact(bundle: VerifiedBatchResult, artifact: VerifiedArtifact) -> Path:
    """Re-check a previously verified artifact immediately before an explicit reveal."""
    if artifact.availability != "VERIFIED":
        raise BatchResultBrowserError("OUTPUT_UNAVAILABLE")
    identity = {
        "path": artifact.relative_path,
        "size": artifact.expected_size,
        "sha256": artifact.expected_sha256,
    }
    verified, _ = _artifact(bundle.output_root, artifact.role, identity)
    if verified is None or verified.path is None:
        raise BatchResultBrowserError("OUTPUT_UNAVAILABLE")
    return verified.path
