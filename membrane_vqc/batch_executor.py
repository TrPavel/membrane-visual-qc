"""Main-thread PyMOL execution for validated Stage 5A batch plans."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Callable

from . import qc
from .batch_comparison import build_batch_comparison_report
from .batch_contracts import load_plan
from .batch_paths import BatchPathError, resolve_input_directory, resolve_input_path
from .batch_runner import (
    BatchCancelled,
    BatchExecutionFailed,
    BatchInputRejected,
    ExecutedReport,
    run_batch,
)
from .comparison_pymol import capture_comparison_snapshot, comparison_snapshot_is_current
from .comparison_worker import (
    ComparisonRequest,
    ComparisonWorkerFailure,
    ComparisonWorkerOrchestrator,
)
from .constants import VERSION
from .context_models import ExposureConfig, LocalContextConfig
from .orientation_io import LoadedOrientation, load_orientation_bytes
from .pdbtm_cache import PdbtmCacheRepository
from .pdbtm_pymol import resolve_pdbtm_from_payloads
from .pdbtm_report_provenance import build_pdbtm_acquisition_provenance
from .pymol_adapter import clear_owned


_COMMIT = re.compile(r"^[0-9a-f]{40}$")
MAX_INPUT_FILE_BYTES = 64 * 1024 * 1024
MAX_PREFLIGHT_FILE_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class _Prepared:
    files: dict[str, Path]
    bytes_by_name: dict[str, bytes]
    snapshot: object | None = None
    error_code: str | None = None


class _CancellationView:
    def __init__(self, check: Callable[[], bool] | None) -> None:
        self._check = check

    def is_cancelled(self) -> bool:
        return bool(self._check is not None and self._check())


def _read_exact_file(path: Path) -> bytes:
    size = path.stat().st_size
    if size < 1 or size > MAX_INPUT_FILE_BYTES:
        raise BatchInputRejected("INPUT_SIZE_INVALID")
    data = path.read_bytes()
    if len(data) != size or len(data) > MAX_INPUT_FILE_BYTES:
        raise BatchInputRejected("INPUT_CHANGED")
    return data


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result if _COMMIT.fullmatch(result) else None


def _analysis_configs(job: dict[str, object]):
    context = job.get("context", {})
    if not context.get("enabled", False):
        return None, None, "built-in"
    points = {"Fast": 96, "Standard": 240, "High": 960}[context.get("quality", "Standard")]
    backend = context.get("backend", "Built-in")
    return ExposureConfig(sphere_points=points), LocalContextConfig(), backend


def _ligand(job: dict[str, object]) -> tuple[str, float]:
    value = job.get("ligand", {})
    return str(value.get("selection", "")), float(value.get("cutoff", 5.0))


def _orientation_from_bytes(path: Path, data: bytes) -> LoadedOrientation:
    try:
        return load_orientation_bytes(data, source_name=path.name)
    except (TypeError, ValueError) as error:
        raise BatchInputRejected("ORIENTATION_INVALID") from error


def _coordinate_fingerprint(selection: str, cmd_obj: object) -> str:
    try:
        objects = sorted(cmd_obj.get_object_list(f"({selection})"))
    except Exception as error:
        raise BatchInputRejected("SELECTION_INVALID") from error
    if not objects:
        raise BatchInputRejected("SELECTION_EMPTY")
    records: list[object] = []
    for name in objects:
        state_count = int(cmd_obj.count_states(name)) if hasattr(cmd_obj, "count_states") else 1
        if state_count < 1:
            raise BatchInputRejected("SELECTION_EMPTY")
        states = []
        for state in range(1, state_count + 1):
            model = cmd_obj.get_model(name, state=state)
            atoms = []
            for atom in model.atom:
                atoms.append(
                    [
                        str(getattr(atom, field, ""))
                        for field in (
                            "model",
                            "chain",
                            "resi",
                            "resn",
                            "name",
                            "alt",
                            "segi",
                            "symbol",
                        )
                    ]
                    + [float(value).hex() for value in atom.coord]
                )
            states.append([state, atoms])
        records.append([name, state_count, states])
    return hashlib.sha256(
        json.dumps(records, sort_keys=False, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


class PymolBatchExecutor:
    """Preflight exact inputs, then invoke accepted workflows one job at a time."""

    def __init__(
        self,
        plan: dict[str, object],
        plan_dir: Path,
        cmd_obj: object,
        *,
        quiet: int = 1,
        cancel_requested: Callable[[], bool] | None = None,
    ):
        self.plan = plan
        self.plan_dir = plan_dir.resolve(strict=True)
        self.cmd = cmd_obj
        self.quiet = int(quiet)
        self.cancel_requested = cancel_requested
        self.prepared: dict[str, _Prepared] = {}
        cache = None
        if "cache_root" in plan:
            try:
                cache_root = resolve_input_directory(
                    self.plan_dir, plan["cache_root"], field="cache_root"
                )
                cache = PdbtmCacheRepository(cache_root)
            except Exception:
                cache = None
        total_preflight_bytes = 0
        for job in plan["jobs"]:
            try:
                files: dict[str, Path] = {}
                bodies: dict[str, bytes] = {}
                if job["input"]["kind"] == "file":
                    files["input"] = resolve_input_path(
                        self.plan_dir, job["input"]["path"], field=f"{job['id']}.input"
                    )
                    bodies["input"] = _read_exact_file(files["input"])
                analysis = job["analysis"]
                mode = analysis["mode"]
                for name in ("orientation_json", "pdbtm_json", "transformed_pdb", "opm_pdb"):
                    if name in analysis:
                        files[name] = resolve_input_path(
                            self.plan_dir, analysis[name], field=f"{job['id']}.{name}"
                        )
                        bodies[name] = _read_exact_file(files[name])
                source = analysis.get("pdbtm") if mode == "pdbtm_opm_comparison" else None
                if isinstance(source, dict) and source["kind"] == "local":
                    for name in ("pdbtm_json", "transformed_pdb"):
                        files[name] = resolve_input_path(
                            self.plan_dir, source[name], field=f"{job['id']}.pdbtm.{name}"
                        )
                        bodies[name] = _read_exact_file(files[name])
                snapshot = None
                cache_spec = (
                    analysis
                    if mode == "pdbtm_cache"
                    else source
                    if isinstance(source, dict) and source.get("kind") == "cache"
                    else None
                )
                if cache_spec is not None:
                    if cache is None:
                        raise BatchInputRejected("CACHE_ROOT_INVALID")
                    snapshot = cache.read_snapshot(
                        cache_spec["record_id"], cache_spec["snapshot_id"]
                    )
                total_preflight_bytes += sum(len(body) for body in bodies.values())
                if snapshot is not None:
                    total_preflight_bytes += sum(len(body) for body in snapshot.payloads)
                if total_preflight_bytes > MAX_PREFLIGHT_FILE_BYTES:
                    raise BatchInputRejected("PREFLIGHT_SIZE_EXCEEDED")
                self.prepared[job["id"]] = _Prepared(files, bodies, snapshot)
            except BatchInputRejected as error:
                self.prepared[job["id"]] = _Prepared({}, {}, error_code=error.code)
            except (BatchPathError, OSError, ValueError):
                self.prepared[job["id"]] = _Prepared({}, {}, error_code="INPUT_INVALID")

    def __call__(self, job: dict[str, object]) -> ExecutedReport:
        prepared = self.prepared[job["id"]]
        if prepared.error_code:
            raise BatchInputRejected(prepared.error_code)
        temp_name = None
        private_input_root: Path | None = None
        private_input_path: Path | None = None
        selection = str(job["input"].get("selection", ""))
        executed_report: ExecutedReport | None = None
        primary_error: Exception | None = None
        try:
            if job["input"]["kind"] == "file":
                suffix = hashlib.sha256(
                    (job["id"] + prepared.bytes_by_name["input"].hex()).encode("ascii")
                ).hexdigest()[:12]
                temp_name = f"mvqc_batch_{job['id']}_{suffix}"
                if temp_name in set(self.cmd.get_names("objects")):
                    raise BatchInputRejected("TEMP_OBJECT_COLLISION")
                private_input_root = Path(tempfile.mkdtemp(prefix="mvqc-batch-input-"))
                source_suffix = prepared.files["input"].suffix.lower()
                private_input_path = private_input_root / f"input{source_suffix}"
                try:
                    private_input_path.write_bytes(prepared.bytes_by_name["input"])
                    self.cmd.load(str(private_input_path), temp_name)
                except Exception as error:
                    raise BatchInputRejected("INPUT_LOAD_FAILED") from error
                if _read_exact_file(private_input_path) != prepared.bytes_by_name["input"]:
                    raise BatchInputRejected("INPUT_CHANGED")
                selection = temp_name
            clear_owned(self.cmd)
            qc.LAST_REPORT = None
            before = _coordinate_fingerprint(selection, self.cmd)
            report = self._execute(job, prepared, selection, private_input_path)
            after = _coordinate_fingerprint(selection, self.cmd)
            executed_report = ExecutedReport(report, before == after)
        except Exception as error:
            primary_error = error
        cleanup_failed = False
        try:
            clear_owned(self.cmd)
        except Exception:
            cleanup_failed = True
        qc.LAST_REPORT = None
        if temp_name is not None:
            try:
                self.cmd.delete(temp_name)
            except Exception:
                cleanup_failed = True
        if private_input_root is not None:
            try:
                shutil.rmtree(private_input_root)
            except OSError:
                cleanup_failed = True
        if primary_error is not None:
            raise primary_error
        if cleanup_failed:
            raise BatchExecutionFailed("CLEANUP_FAILED")
        if executed_report is None:
            raise BatchExecutionFailed("EXECUTOR_CONTRACT_INVALID")
        return executed_report

    def _execute(
        self,
        job: dict[str, object],
        prepared: _Prepared,
        selection: str,
        private_input_path: Path | None = None,
    ):
        analysis = job["analysis"]
        mode = analysis["mode"]
        ligand, cutoff = _ligand(job)
        exposure, context, backend = _analysis_configs(job)
        input_path = str(private_input_path or prepared.files.get("input", ""))
        common = dict(
            selection=selection,
            ligand=ligand,
            cutoff=cutoff,
            quiet=self.quiet,
            cmd_obj=self.cmd,
            input_path=input_path,
            exposure_config=exposure,
            local_context_config=context,
            exposure_backend=backend,
        )
        if mode == "legacy_global_z":
            return qc.run_check(zmin=analysis["zmin"], zmax=analysis["zmax"], **common)
        if mode == "planar_orientation":
            loaded = _orientation_from_bytes(
                prepared.files["orientation_json"], prepared.bytes_by_name["orientation_json"]
            )
            return qc.run_check_with_membrane(
                membrane=loaded.membrane, orientation_import=loaded, **common
            )
        if mode in {"pdbtm_local", "pdbtm_cache"}:
            if mode == "pdbtm_local":
                json_body = prepared.bytes_by_name["pdbtm_json"]
                pdb_body = prepared.bytes_by_name["transformed_pdb"]
                acquisition = None
            else:
                json_body, pdb_body = prepared.snapshot.payloads
                acquisition = build_pdbtm_acquisition_provenance(
                    prepared.snapshot, consumption_mode="snapshot_cache_read"
                )
            imported = resolve_pdbtm_from_payloads(
                selection=selection,
                pdbtm_json_payload=json_body,
                transformed_pdb_payload=pdb_body,
                biological_assembly=analysis.get("biological_assembly"),
                cmd_obj=self.cmd,
            )
            if imported.evidence.source.record_id != analysis["record_id"]:
                raise BatchInputRejected("RECORD_ID_MISMATCH")
            return qc.run_check_with_membrane(
                membrane=imported.membrane,
                orientation_evidence=imported.evidence,
                pdbtm_acquisition=acquisition,
                **common,
            )
        snapshot = capture_comparison_snapshot(
            selection,
            biological_assembly=analysis["pdbtm"].get("biological_assembly"),
            cmd_obj=self.cmd,
        )
        source = analysis["pdbtm"]
        if source["kind"] == "cache":
            pdbtm_json, transformed = prepared.snapshot.payloads
        else:
            pdbtm_json = prepared.bytes_by_name["pdbtm_json"]
            transformed = prepared.bytes_by_name["transformed_pdb"]
        request = ComparisonRequest(
            snapshot.structure_context,
            pdbtm_json,
            transformed,
            prepared.files["opm_pdb"],
            source["record_id"],
            opm_payload=prepared.bytes_by_name["opm_pdb"],
        )
        result = ComparisonWorkerOrchestrator().compare(
            request, operation=_CancellationView(self.cancel_requested)
        )
        if isinstance(result, ComparisonWorkerFailure):
            if result.code == "CANCELLED":
                raise BatchCancelled
            raise BatchExecutionFailed(result.code)
        if not comparison_snapshot_is_current(
            snapshot,
            selection,
            biological_assembly=source.get("biological_assembly"),
            cmd_obj=self.cmd,
        ):
            raise BatchExecutionFailed("COORDINATES_CHANGED")
        version = self.cmd.get_version()[0] if hasattr(self.cmd, "get_version") else "unavailable"
        return build_batch_comparison_report(
            result,
            snapshot,
            source["record_id"],
            cached_snapshot=prepared.snapshot if source["kind"] == "cache" else None,
            software_commit=_git_commit() or "unavailable",
            pymol_version=str(version),
        )


def run_pymol_batch(
    plan_path: str,
    output_dir: str,
    *,
    fail_fast: int | None = None,
    quiet: int = 1,
    cmd_obj: object | None = None,
    cancel_requested: Callable[[], bool] | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    """Run one exact local plan on the calling PyMOL main thread."""
    plan, plan_bytes = load_plan(plan_path)
    if fail_fast is not None:
        if fail_fast not in {0, 1}:
            raise ValueError("fail_fast must be 0 or 1")
        plan = {
            **plan,
            "execution": {
                **plan["execution"],
                "failure_policy": "fail_fast" if fail_fast else "continue_on_error",
            },
        }
    if cmd_obj is None:
        from pymol import cmd as cmd_obj

    executor = PymolBatchExecutor(
        plan,
        Path(plan_path).resolve().parent,
        cmd_obj,
        quiet=quiet,
        cancel_requested=cancel_requested,
    )
    return run_batch(
        plan,
        plan_bytes,
        output_dir,
        executor,
        software_version=VERSION,
        software_commit=_git_commit(),
        cancel_requested=cancel_requested,
        run_id=run_id,
    )
