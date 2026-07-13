"""JSON and CSV report export helpers."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import LIMITATIONS, PLUGIN_NAME, VERSION
from .errors import ReportError

SCHEMA_VERSION = "1.0"
REPORT_TYPE = "single_structure_review"
CSV_FIELDS = ["model", "chain", "resi", "resn", "classification", "severity", "reason", "z"]


def build_report(
    *,
    selection: str,
    zmin: float,
    zmax: float,
    ligand_selection: str,
    cutoff: float,
    total_residues: int,
    core_residues: int | None = None,
    flagged_residues: list[dict[str, Any]],
    ligand_neighbours: list[dict[str, Any]],
    warnings: list[str],
    slab_mode: str = "manual",
    input_path: str | Path | None = None,
    input_format: str = "",
    structure_source: str = "",
    structure_type: str = "unknown",
    software_commit: str = "",
    pymol_version: str = "",
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a versioned, machine-readable single-structure review report.

    Legacy top-level fields are retained through the v1 compatibility period.
    New consumers should use ``software``, ``orientation`` and ``review_items``.
    """
    charged = sum(1 for item in flagged_residues if item.get("severity") == "WARNING")
    polar = sum(1 for item in flagged_residues if item.get("severity") == "INSPECT")
    overall_status = (
        "INSUFFICIENT_CONTEXT"
        if int(total_residues) == 0
        else "REVIEW_ITEMS"
        if flagged_residues
        else "NO_FLAGS"
    )
    core_count = (
        int(core_residues)
        if core_residues is not None
        else sum(1 for item in flagged_residues if item.get("classification") == "core")
    )

    review_items = sorted((dict(item) for item in flagged_residues), key=_residue_sort_key)
    neighbours = sorted((dict(item) for item in ligand_neighbours), key=_residue_sort_key)
    source_path, source_hash = _portable_input_metadata(input_path)
    timestamp = datetime.now(timezone.utc).isoformat()
    orientation_warnings = [
        warning for warning in warnings if "slab" in warning.lower() or "orient" in warning.lower()
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE,
        "software": {
            "name": PLUGIN_NAME,
            "version": VERSION,
            "commit": software_commit,
            "commit_status": "recorded" if software_commit else "unavailable",
        },
        "runtime": {
            "python": platform.python_version(),
            "pymol": pymol_version,
            "pymol_status": "recorded" if pymol_version else "unavailable",
            "platform": platform.platform(),
        },
        "capabilities": dict(capabilities or {}),
        "generated_at": timestamp,
        "plugin": PLUGIN_NAME,
        "version": VERSION,
        "timestamp": timestamp,
        "input": {
            "path": source_path,
            "sha256": source_hash,
            "selection": selection,
            "format": input_format,
            "structure_source": structure_source,
            "structure_type": structure_type,
            "provenance_status": "file_hashed" if source_hash else "input_path_not_supplied",
        },
        "orientation": {
            "source": slab_mode,
            "geometry": "planar",
            "parameters": {
                "center": [0.0, 0.0, 0.0],
                "normal": [0.0, 0.0, 1.0],
                "zmin": float(zmin),
                "zmax": float(zmax),
            },
            "warnings": orientation_warnings,
        },
        "parameters": {
            "ligand_selection": ligand_selection,
            "ligand_cutoff_angstrom": float(cutoff),
        },
        "summary": {
            "total_residues": int(total_residues),
            "core_residues": int(core_count),
            "charged_core_residues": int(charged),
            "polar_core_inspect_residues": int(polar),
            "ligand_neighbour_residues": len(ligand_neighbours),
            "overall_status": overall_status,
        },
        "review_items": review_items,
        "ligand_neighbours": neighbours,
        "warnings": list(warnings),
        "limitations": list(LIMITATIONS),
    }
    # Transitional aliases for scripts written against the v0.1 development schema.
    report["input"].update(
        {
            "zmin": float(zmin),
            "zmax": float(zmax),
            "ligand_selection": ligand_selection,
            "cutoff": float(cutoff),
            "slab_mode": slab_mode,
        }
    )
    report["flagged_residues"] = review_items
    validate_report(report)
    return report


def export_report(
    report: dict[str, Any],
    path: str | Path,
    *,
    write_csv: bool = True,
) -> list[Path]:
    """Atomically export report JSON and optional CSV of review items."""
    validate_report(report)
    output = Path(path)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(output, json.dumps(report, indent=2, sort_keys=True) + "\n")
        written = [output]
        if write_csv:
            csv_path = output.with_suffix(".csv")
            _write_flags_csv(
                report.get("review_items", report.get("flagged_residues", [])), csv_path
            )
            written.append(csv_path)
        return written
    except OSError as exc:
        raise ReportError(f"Could not export report to {output}: {exc}") from exc


def _write_flags_csv(flagged_residues: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for item in sorted(flagged_residues, key=_residue_sort_key):
                writer.writerow({field: item.get(field, "") for field in CSV_FIELDS})
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def validate_report(report: dict[str, Any]) -> None:
    """Validate the required v1 report contract without optional dependencies."""
    if not isinstance(report, dict):
        raise ReportError("Report must be a JSON object.")
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ReportError(f"Unsupported report schema version: {report.get('schema_version')!r}")
    required = (
        "software",
        "runtime",
        "input",
        "orientation",
        "parameters",
        "summary",
        "review_items",
    )
    missing = [key for key in required if key not in report]
    if missing:
        raise ReportError("Report is missing required fields: " + ", ".join(missing))
    status = report.get("summary", {}).get("overall_status")
    if status not in {"NO_FLAGS", "REVIEW_ITEMS", "INSUFFICIENT_CONTEXT", "ANALYSIS_ERROR"}:
        raise ReportError(f"Invalid biological review status: {status!r}")
    if report.get("orientation", {}).get("source") in (None, ""):
        raise ReportError("Orientation source is required.")
    required_review_fields = {
        "model",
        "chain",
        "resi",
        "resn",
        "classification",
        "severity",
        "reason",
        "z",
    }
    for index, item in enumerate(report.get("review_items", [])):
        if not isinstance(item, dict):
            raise ReportError(f"Review item {index} must be a JSON object.")
        missing_fields = sorted(required_review_fields.difference(item))
        if missing_fields:
            raise ReportError(
                f"Review item {index} is missing required fields: " + ", ".join(missing_fields)
            )


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a local input file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_input_metadata(path: str | Path | None) -> tuple[str, str]:
    if path in (None, ""):
        return "", ""
    source = Path(path)
    if not source.is_file():
        return source.name, ""
    return source.name, sha256_file(source)


def _residue_sort_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(item.get(key, "")) for key in ("model", "chain", "resi", "resn"))


def _atomic_write_text(path: Path, text: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
