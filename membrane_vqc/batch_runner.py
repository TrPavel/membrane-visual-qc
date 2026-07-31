"""Sequential Stage 5A batch state machine, independent of PyMOL imports."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import tempfile
from typing import Callable, Mapping

from .batch_contracts import (
    BatchContractError,
    RESULT_CONTRACT,
    STATUSES,
    canonical_json_bytes,
    identity_core_sha256,
    validate_json_schema,
    validate_plan,
    validate_result,
    validate_run_id,
)
from .batch_paths import atomic_write_bytes, prepare_output_root, safe_output_name
from .comparison_report import validate_comparison_report
from .report import export_report, validate_report


MAX_TOTAL_OUTPUT_BYTES = 512 * 1024 * 1024
MANIFEST_NAME = "batch-result.json"
LOCK_NAME = ".mvqc-batch.lock"


class BatchInputRejected(ValueError):
    """One prevalidated job input could not be safely established."""

    def __init__(self, code: str = "INPUT_INVALID") -> None:
        self.code = code
        super().__init__(code)


class BatchExecutionFailed(RuntimeError):
    """One accepted job failed operationally with a safe stable code."""

    def __init__(self, code: str = "ANALYSIS_FAILED") -> None:
        self.code = code
        super().__init__(code)


class BatchCancelled(RuntimeError):
    """The current job reached an accepted cooperative cancellation point."""


@dataclass(frozen=True, slots=True)
class ExecutedReport:
    """A returned existing scientific report plus preservation evidence."""

    report: dict[str, object]
    coordinate_preserved: bool


JobExecutor = Callable[[dict[str, object]], ExecutedReport]
CancelCheck = Callable[[], bool]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _file_identity(path: Path, root: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _scientific_status(report: Mapping[str, object]) -> tuple[str, int | None, int]:
    if report.get("schema_version") == "1.5":
        comparison = report.get("comparison")
        comparable = isinstance(comparison, Mapping) and comparison.get("comparable") is True
        warnings = comparison.get("warnings", []) if isinstance(comparison, Mapping) else []
        warning_count = len(warnings) if isinstance(warnings, list) else 0
        band = comparison.get("band") if isinstance(comparison, Mapping) else None
        if not comparable:
            return "INSUFFICIENT_CONTEXT", None, warning_count
        if band == "measurable_geometric_difference":
            return "REVIEW_ITEMS", 1, warning_count
        return "SUCCESS", 0, warning_count
    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        raise BatchExecutionFailed("REPORT_INVALID")
    status = summary.get("overall_status")
    mapped = {
        "NO_FLAGS": "SUCCESS",
        "REVIEW_ITEMS": "REVIEW_ITEMS",
        "INSUFFICIENT_CONTEXT": "INSUFFICIENT_CONTEXT",
    }.get(status)
    if mapped is None:
        raise BatchExecutionFailed("REPORT_ANALYSIS_ERROR")
    review_items = report.get("review_items", report.get("flagged_residues", []))
    warnings = report.get("warnings", [])
    return (
        mapped,
        len(review_items) if isinstance(review_items, list) else 0,
        len(warnings) if isinstance(warnings, list) else 0,
    )


def _validate_scientific_report(report: dict[str, object]) -> str:
    schema = report.get("schema_version")
    try:
        if schema not in {"1.1", "1.2", "1.3", "1.4", "1.5"}:
            raise BatchExecutionFailed("REPORT_SCHEMA_UNSUPPORTED")
        validate_json_schema(report, f"mvqc-report-{schema}.schema.json")
        if schema == "1.5":
            validate_comparison_report(report)
        else:
            validate_report(report)
    except BatchExecutionFailed:
        raise
    except (BatchContractError, TypeError, ValueError) as error:
        raise BatchExecutionFailed("REPORT_INVALID") from error
    return str(schema)


def _empty_job(job: Mapping[str, object], status: str, error_code: str | None = None):
    return {
        "job_id": job["id"],
        "mode": job["analysis"]["mode"],
        "status": status,
        "error_code": error_code,
        "report": None,
        "report_schema": None,
        "csv": None,
        "warnings_count": 0,
        "review_items_count": None,
        "coordinate_preserved": None,
    }


def _existing_owned_paths(root: Path, run_id: str, plan_sha: str) -> dict[str, dict[str, object]]:
    manifest = root / MANIFEST_NAME
    if not manifest.is_file():
        return {}
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
        validate_result(value)
    except Exception as error:
        raise BatchInputRejected("OUTPUT_MANIFEST_INVALID") from error
    if value["run_id"] != run_id or value["plan_sha256"] != plan_sha:
        return {}
    owned: dict[str, dict[str, object]] = {MANIFEST_NAME: {"path": MANIFEST_NAME}}
    for job in value["jobs"]:
        for key in ("report", "csv"):
            if job[key] is not None:
                identity = job[key]
                path = root / identity["path"]
                if not path.is_file() or _file_identity(path, root) != identity:
                    raise BatchInputRejected("OUTPUT_OWNERSHIP_CHANGED")
                owned[identity["path"]] = identity
    return owned


def _acquire_lock(root: Path) -> tuple[int, Path]:
    path = root / LOCK_NAME
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise BatchInputRejected("OUTPUT_BUSY") from error
    return descriptor, path


def _publish_job(staged: list[Path], root: Path) -> list[Path]:
    destinations = [root / item.name for item in staged]
    published: list[Path] = []
    try:
        for source, destination in zip(staged, destinations, strict=True):
            try:
                os.link(source, destination)
            except FileExistsError as error:
                raise BatchInputRejected("OUTPUT_COLLISION") from error
            except OSError as error:
                raise BatchExecutionFailed("OUTPUT_PUBLISH_FAILED") from error
            published.append(destination)
            source.unlink()
    except Exception:
        for path in published:
            try:
                path.unlink()
            except OSError:
                pass
        raise
    return published


def _backup_owned_outputs(
    owned: Mapping[str, object], root: Path, stage_root: Path
) -> dict[str, Path]:
    backups: dict[str, Path] = {}
    try:
        for name in sorted(owned):
            source = root / name
            backup = stage_root / f".previous-{name}"
            os.link(source, backup)
            backups[name] = backup
            source.unlink()
    except OSError as error:
        try:
            _rollback_outputs([], backups, root)
        except BatchExecutionFailed as rollback_error:
            raise rollback_error from error
        raise BatchExecutionFailed("OUTPUT_BACKUP_FAILED") from error
    return backups


def _rollback_outputs(published: list[Path], backups: Mapping[str, Path], root: Path) -> None:
    for path in reversed(published):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            raise BatchExecutionFailed("ROLLBACK_FAILED") from error
    for name, backup in backups.items():
        destination = root / name
        try:
            os.link(backup, destination)
            backup.unlink()
        except FileExistsError as error:
            raise BatchExecutionFailed("ROLLBACK_COLLISION") from error
        except OSError as error:
            raise BatchExecutionFailed("ROLLBACK_FAILED") from error


def run_batch(
    plan: dict[str, object],
    plan_bytes: bytes,
    output_root: str | Path,
    executor: JobExecutor,
    *,
    software_version: str,
    software_commit: str | None,
    cancel_requested: CancelCheck | None = None,
    run_id: str | None = None,
    now: Callable[[], str] = _utc_now,
) -> dict[str, object]:
    """Execute validated jobs sequentially and atomically finalize one manifest."""
    validate_plan(plan)
    if run_id is not None:
        validate_run_id(run_id)
    root = prepare_output_root(output_root)
    plan_sha = hashlib.sha256(plan_bytes).hexdigest()
    started = now()
    run_id = (
        run_id
        or hashlib.sha256(
            plan_sha.encode("ascii") + started.encode("ascii") + secrets.token_bytes(32)
        ).hexdigest()
    )
    execution = dict(plan["execution"])
    overwrite = execution["overwrite"]
    lock_descriptor, lock_path = _acquire_lock(root)
    try:
        owned = _existing_owned_paths(root, run_id, plan_sha) if overwrite == "same_batch" else {}
        destinations: list[str] = [MANIFEST_NAME]
        for job in plan["jobs"]:
            destinations.append(safe_output_name(job["id"], ".json"))
            if job["output"]["write_csv"]:
                destinations.append(safe_output_name(job["id"], ".csv"))
        if len(destinations) != len(set(destinations)):
            raise BatchInputRejected("OUTPUT_NAME_COLLISION")
        for relative in sorted(set(destinations)):
            target = root / relative
            if target.exists() and relative not in owned:
                raise BatchInputRejected("OUTPUT_COLLISION")
    except Exception:
        os.close(lock_descriptor)
        try:
            lock_path.unlink()
        except OSError:
            pass
        raise

    results: list[dict[str, object]] = []
    failed_fast = False
    cancelled = False
    total_output = 0
    stage_root = Path(tempfile.mkdtemp(prefix=".mvqc-batch-", dir=root))
    published: list[Path] = []
    backups: dict[str, Path] = {}
    preserve_stage = False
    try:
        if overwrite == "same_batch" and owned:
            backups = _backup_owned_outputs(owned, root, stage_root)
        for index, job in enumerate(plan["jobs"]):
            if failed_fast:
                results.append(_empty_job(job, "SKIPPED_DEPENDENCY"))
                continue
            if cancelled or (cancel_requested is not None and cancel_requested()):
                cancelled = True
                results.append(_empty_job(job, "CANCELLED"))
                continue
            try:
                executed = executor(job)
                if type(executed) is not ExecutedReport:
                    raise BatchExecutionFailed("EXECUTOR_CONTRACT_INVALID")
                if executed.coordinate_preserved is not True:
                    raise BatchExecutionFailed("COORDINATES_CHANGED")
                report = executed.report
                schema = _validate_scientific_report(report)
                status, review_count, warning_count = _scientific_status(report)
                report_name = safe_output_name(job["id"], ".json")
                staged_report = stage_root / report_name
                csv_identity = None
                staged_outputs = [staged_report]
                if schema == "1.5":
                    atomic_write_bytes(staged_report, canonical_json_bytes(report, pretty=True))
                else:
                    written = export_report(
                        report, staged_report, write_csv=bool(job["output"]["write_csv"])
                    )
                    if len(written) == 2:
                        staged_csv = written[1]
                        staged_outputs.append(staged_csv)
                job_output_size = sum(path.stat().st_size for path in staged_outputs)
                if total_output + job_output_size > MAX_TOTAL_OUTPUT_BYTES:
                    raise BatchExecutionFailed("OUTPUT_LIMIT_EXCEEDED")
                published.extend(_publish_job(staged_outputs, root))
                total_output += job_output_size
                destination_report = root / report_name
                if len(staged_outputs) == 2:
                    csv_identity = _file_identity(root / staged_outputs[1].name, root)
                results.append(
                    {
                        "job_id": job["id"],
                        "mode": job["analysis"]["mode"],
                        "status": status,
                        "error_code": None,
                        "report": _file_identity(destination_report, root),
                        "report_schema": schema,
                        "csv": csv_identity,
                        "warnings_count": warning_count,
                        "review_items_count": review_count,
                        "coordinate_preserved": True,
                    }
                )
            except BatchInputRejected as error:
                results.append(_empty_job(job, "INPUT_REJECTED", error.code))
                failed_fast = execution["failure_policy"] == "fail_fast"
            except BatchExecutionFailed as error:
                results.append(_empty_job(job, "ANALYSIS_ERROR", error.code))
                failed_fast = execution["failure_policy"] == "fail_fast"
            except BatchCancelled:
                results.append(_empty_job(job, "CANCELLED"))
                cancelled = True
            except Exception:
                results.append(_empty_job(job, "ANALYSIS_ERROR", "ANALYSIS_FAILED"))
                failed_fast = execution["failure_policy"] == "fail_fast"
        counts = Counter(item["status"] for item in results)
        count_object = {"total": len(results), **{status: counts[status] for status in STATUSES}}
        if cancelled:
            overall = "CANCELLED"
        elif failed_fast:
            overall = "FAILED_FAST"
        elif counts["ANALYSIS_ERROR"] or counts["INPUT_REJECTED"]:
            overall = "COMPLETED_WITH_ERRORS"
        else:
            overall = "COMPLETED"
        result: dict[str, object] = {
            "contract": RESULT_CONTRACT,
            "plan_sha256": plan_sha,
            "run_id": run_id,
            "software": {"version": software_version, "commit": software_commit},
            "started_at": started,
            "completed_at": now(),
            "execution": execution,
            "jobs": results,
            "counts": count_object,
            "overall_status": overall,
            "identity_core_sha256": "0" * 64,
        }
        result["identity_core_sha256"] = identity_core_sha256(result)
        validate_result(result)
        if overwrite == "same_batch" and owned and overall != "COMPLETED":
            raise BatchExecutionFailed("SAME_BATCH_ROLLED_BACK")
        staged_manifest = stage_root / MANIFEST_NAME
        atomic_write_bytes(staged_manifest, canonical_json_bytes(result, pretty=True))
        published.extend(_publish_job([staged_manifest], root))
        return result
    except Exception:
        if backups:
            try:
                _rollback_outputs(published, backups, root)
                published.clear()
                backups.clear()
            except BatchExecutionFailed:
                preserve_stage = True
                raise
        elif MANIFEST_NAME not in owned:
            for path in reversed(published):
                try:
                    path.unlink()
                except OSError:
                    pass
        raise
    finally:
        if not preserve_stage:
            shutil.rmtree(stage_root, ignore_errors=True)
        os.close(lock_descriptor)
        try:
            lock_path.unlink()
        except OSError:
            pass
