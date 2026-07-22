"""Generate deterministic schema-1.3/1.4 PDBTM release examples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from membrane_vqc.constants import VERSION
from membrane_vqc.pdbtm_adapter import import_pdbtm_orientation
from membrane_vqc.pdbtm_cache import CachedSnapshot, CacheRepository
from membrane_vqc.pdbtm_cache_contract import parse_snapshot_envelope
from membrane_vqc.pdbtm_provider import validate_pdbtm_pair
from membrane_vqc.pdbtm_report_provenance import build_pdbtm_acquisition_provenance
from membrane_vqc.report import build_report, validate_report
from membrane_vqc.orientation_sources import StructureContext


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"
GENERATED_AT = "2026-07-22T12:00:00.000000+00:00"
RUNTIME = {
    "python": "3.10.20",
    "pymol": "3.1.8",
    "pymol_status": "recorded",
    "platform": "Windows-10-build-26200",
}
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def _require_release_identity(software_version: str, software_commit: str) -> None:
    if not software_version.strip():
        raise ValueError("software_version must not be empty")
    if not _COMMIT.fullmatch(software_commit):
        raise ValueError("software_commit must be an exact 40-character lowercase Git SHA")


def _payloads(record_id: str) -> tuple[bytes, bytes]:
    json_bytes = (SYNTHETIC / "pdbtm_api_v1_test.json").read_bytes()
    pdb_bytes = (SYNTHETIC / "pdbtm_transformed_test.pdb").read_bytes()
    if record_id != "test":
        json_bytes = json_bytes.replace(b'"pdb_id":"test"', f'"pdb_id":"{record_id}"'.encode(), 1)
        pdb_bytes = pdb_bytes.replace(b"TEST\n", f"{record_id.upper()}\n".encode(), 1)
    return json_bytes, pdb_bytes


def _normalize(
    report: dict[str, object], *, software_version: str, software_commit: str
) -> dict[str, object]:
    report["generated_at"] = GENERATED_AT
    report["timestamp"] = GENERATED_AT
    report["version"] = software_version
    report["runtime"] = dict(RUNTIME)
    software = report["software"]
    assert isinstance(software, dict)
    software.update(
        version=software_version,
        commit=software_commit,
        commit_status="recorded",
    )
    validate_report(report)
    return report


def build_local_pdbtm_example(*, software_version: str, software_commit: str) -> dict[str, object]:
    """Build the schema-1.3 example from the accepted offline fixture pair."""

    _require_release_identity(software_version, software_commit)
    json_bytes, pdb_bytes = _payloads("test")
    imported = import_pdbtm_orientation(
        json_bytes, pdb_bytes, StructureContext(pdb_bytes, "test", 1)
    )
    if imported.status != "imported" or imported.membrane is None or imported.evidence is None:
        raise RuntimeError("accepted local PDBTM fixture did not import")
    report = build_report(
        selection="synthetic_pdbtm_local_v050",
        zmin=-15.0,
        zmax=15.0,
        ligand_selection="",
        cutoff=5.0,
        total_residues=0,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        membrane=imported.membrane,
        orientation_evidence=imported.evidence,
        software_commit=software_commit,
        pymol_version=RUNTIME["pymol"],
    )
    return _normalize(report, software_version=software_version, software_commit=software_commit)


def build_cached_pdbtm_example(
    *,
    software_version: str,
    software_commit: str,
    cache_dir: Path,
    record_id: str,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    """Build schema 1.4 from a real, integrity-checked provider cache snapshot."""

    _require_release_identity(software_version, software_commit)
    cache_dir = cache_dir.resolve()
    repository = CacheRepository(cache_dir)
    if snapshot_id is None:
        snapshot = repository.read_active(record_id)
        inspection = repository.inspect()
        record = inspection.records.get(snapshot.canonical_record_id)
        if record is None:
            raise RuntimeError("active cache record disappeared during retained-report generation")
        cache_generation = record.generation
        consumption_mode = "active_cache_read"
    else:
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot_id):
            raise ValueError("snapshot_id must be an exact lowercase SHA-256")
        manifest = cache_dir / "records" / record_id / "snapshots" / f"{snapshot_id}.json"
        envelope = parse_snapshot_envelope(manifest.read_bytes())
        if (
            envelope.snapshot_id != snapshot_id
            or envelope.snapshot_core.canonical_record_id != record_id
        ):
            raise ValueError("preserved snapshot identity does not match the requested record")
        bodies = tuple(
            (cache_dir / "blobs" / "sha256" / item.sha256[:2] / item.sha256).read_bytes()
            for item in envelope.snapshot_core.payloads
        )
        semantic_result = validate_pdbtm_pair(record_id, *bodies)
        snapshot = CachedSnapshot(  # type: ignore[arg-type]
            snapshot_id, envelope.snapshot_core, bodies, semantic_result
        )
        cache_generation = None
        consumption_mode = "snapshot_cache_read"
    json_bytes, pdb_bytes = snapshot.payloads
    provenance = build_pdbtm_acquisition_provenance(
        snapshot, consumption_mode=consumption_mode, cache_generation=cache_generation
    )
    imported = import_pdbtm_orientation(
        json_bytes, pdb_bytes, StructureContext(pdb_bytes, record_id, 1)
    )
    if imported.status != "imported" or imported.membrane is None or imported.evidence is None:
        raise RuntimeError("accepted cached PDBTM fixture did not import")
    report = build_report(
        selection=f"pdbtm_cached_{snapshot.canonical_record_id}_v050",
        zmin=-15.0,
        zmax=15.0,
        ligand_selection="",
        cutoff=5.0,
        total_residues=0,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        membrane=imported.membrane,
        orientation_evidence=imported.evidence,
        pdbtm_acquisition=provenance,
        software_commit=software_commit,
        pymol_version=RUNTIME["pymol"],
    )
    return _normalize(report, software_version=software_version, software_commit=software_commit)


def serialize(report: dict[str, object]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("local", "cached"))
    parser.add_argument("--software-version", default=VERSION)
    parser.add_argument("--software-commit", required=True)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--record-id", default="1pcr")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.kind == "local":
            report = build_local_pdbtm_example(
                software_version=args.software_version, software_commit=args.software_commit
            )
        else:
            if args.cache_dir is None:
                parser.error("cached generation requires --cache-dir from a real provider fetch")
            report = build_cached_pdbtm_example(
                software_version=args.software_version,
                software_commit=args.software_commit,
                cache_dir=args.cache_dir,
                record_id=args.record_id,
                snapshot_id=args.snapshot_id,
            )
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_text(serialize(report), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
