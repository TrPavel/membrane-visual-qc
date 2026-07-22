"""Generate deterministic schema-1.3/1.4 PDBTM release examples."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile

from membrane_vqc.constants import VERSION
from membrane_vqc.pdbtm_adapter import import_pdbtm_orientation
from membrane_vqc.pdbtm_cache import CacheRepository
from membrane_vqc.pdbtm_report_provenance import build_pdbtm_acquisition_provenance
from membrane_vqc.report import build_report, validate_report
from membrane_vqc.orientation_sources import StructureContext


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"
GENERATED_AT = "2026-07-22T12:00:00.000000+00:00"
VALIDATED_AT = datetime(2026, 7, 22, 11, 59, 59, tzinfo=timezone.utc)
RUNTIME = {
    "python": "3.10.20",
    "pymol": "3.1.8",
    "pymol_status": "recorded",
    "platform": "Windows-10-build-26200",
}
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


@dataclass(frozen=True)
class _Evidence:
    requested_url: str
    final_url: str
    status: int
    content_type: str
    charset: str | None
    content_encoding: str | None
    etag: str | None
    last_modified: str | None
    requested_at: str
    completed_at: str
    byte_size: int
    sha256: str
    tls_verified: bool = True


@dataclass(frozen=True)
class _Payload:
    role: str
    body: bytes
    evidence: _Evidence


@dataclass(frozen=True)
class _Versions:
    resource_version: str = "1017"
    software_version: str = "3.2.134"


@dataclass(frozen=True)
class _Candidate:
    canonical_record_id: str
    payloads: tuple[_Payload, _Payload]
    provider_versions: _Versions = _Versions()


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


def _acquisition_payload(record_id: str, role: str, body: bytes, second: int) -> _Payload:
    suffix = "json" if role == "pdbtm_json" else "trpdb"
    url = f"https://pdbtm.unitmp.org/api/v1/entry/{record_id}.{suffix}"
    media_type = "application/json" if role == "pdbtm_json" else "text/plain"
    charset = None if role == "pdbtm_json" else "utf-8"
    return _Payload(
        role,
        body,
        _Evidence(
            url,
            url,
            200,
            media_type,
            charset,
            None,
            None,
            None,
            f"2026-07-22T11:59:5{second}.000000Z",
            f"2026-07-22T11:59:5{second + 1}.000000Z",
            len(body),
            hashlib.sha256(body).hexdigest(),
        ),
    )


def build_cached_pdbtm_example(*, software_version: str, software_commit: str) -> dict[str, object]:
    """Build schema 1.4 through the real cache and provenance boundaries."""

    _require_release_identity(software_version, software_commit)
    record_id = "9zzz"
    json_bytes, pdb_bytes = _payloads(record_id)
    candidate = _Candidate(
        record_id,
        (
            _acquisition_payload(record_id, "pdbtm_json", json_bytes, 0),
            _acquisition_payload(record_id, "transformed_pdb", pdb_bytes, 2),
        ),
    )
    with tempfile.TemporaryDirectory(prefix="mvqc-v050-report-") as temporary:
        repository = CacheRepository(Path(temporary) / "cache", utc_now=lambda: VALIDATED_AT)
        generation = repository.capture_record_generation(record_id)
        repository.commit_validated_pair(candidate, expected_record_generation=generation)
        snapshot = repository.read_active(record_id)
    provenance = build_pdbtm_acquisition_provenance(
        snapshot, consumption_mode="active_cache_read", cache_generation=1
    )
    imported = import_pdbtm_orientation(
        json_bytes, pdb_bytes, StructureContext(pdb_bytes, record_id, 1)
    )
    if imported.status != "imported" or imported.membrane is None or imported.evidence is None:
        raise RuntimeError("accepted cached PDBTM fixture did not import")
    report = build_report(
        selection="synthetic_pdbtm_cached_v050",
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    builder = build_local_pdbtm_example if args.kind == "local" else build_cached_pdbtm_example
    try:
        report = builder(
            software_version=args.software_version,
            software_commit=args.software_commit,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_text(serialize(report), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
