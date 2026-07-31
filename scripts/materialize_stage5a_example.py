#!/usr/bin/env python3
"""Materialize the retained synthetic five-mode Stage 5A example without network access."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil

from membrane_vqc.batch_contracts import load_plan
from membrane_vqc.pdbtm_cache import CacheRepository


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "synthetic"
SNAPSHOT_ID = "a3d2352559891a8b544ff1666129fdb1d03e20a4ceb80be9144f1622d2b97c58"


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
    resource_version: str = "1017.one"
    software_version: str = "3.2.134"


@dataclass(frozen=True)
class _Candidate:
    canonical_record_id: str
    payloads: tuple[_Payload, _Payload]
    provider_versions: _Versions = _Versions()


def _payload(role: str, body: bytes, second: int) -> _Payload:
    suffix = "json" if role == "pdbtm_json" else "trpdb"
    url = f"https://pdbtm.unitmp.org/api/v1/entry/1tes.{suffix}"
    return _Payload(
        role,
        body,
        _Evidence(
            url,
            url,
            200,
            "text/plain",
            "utf-8",
            None,
            None,
            None,
            f"2026-07-20T00:00:0{second}.000000Z",
            f"2026-07-20T00:00:0{second + 1}.000000Z",
            len(body),
            hashlib.sha256(body).hexdigest(),
        ),
    )


def materialize(destination: Path) -> Path:
    """Create one self-contained synthetic example directory and return its plan."""
    destination = destination.resolve(strict=False)
    destination.mkdir(parents=True, exist_ok=False)
    names = (
        "pdbtm_original_test.pdb",
        "pdbtm_original_1tes.pdb",
        "pdbtm_api_v1_test.json",
        "pdbtm_transformed_test.pdb",
        "opm_oriented_test.pdb",
        "stage5a_orientation.json",
        "stage5a_batch_plan.json",
    )
    for name in names:
        shutil.copyfile(FIXTURES / name, destination / name)
    json_body = (FIXTURES / "pdbtm_api_v1_test.json").read_bytes()
    json_body = json_body.replace(b'"pdb_id":"test"', b'"pdb_id":"1tes"', 1)
    json_body = json_body.replace(b'"resource_version":"1017"', b'"resource_version":"1017.one"', 1)
    pdb_body = (
        (FIXTURES / "pdbtm_transformed_test.pdb").read_bytes().replace(b"TEST\n", b"1TES\n", 1)
    )
    candidate = _Candidate(
        "1tes",
        (
            _payload("pdbtm_json", json_body, 0),
            _payload("transformed_pdb", pdb_body, 2),
        ),
    )
    repository = CacheRepository(
        destination / "stage5a-synthetic-cache",
        utc_now=lambda: datetime(2026, 7, 31, 0, 0, 0, tzinfo=timezone.utc),
    )
    snapshot = repository.commit_validated_pair(candidate, expected_record_generation=0)
    if snapshot.snapshot_id != SNAPSHOT_ID:
        raise RuntimeError(f"synthetic snapshot identity changed: {snapshot.snapshot_id}")
    plan_path = destination / "stage5a_batch_plan.json"
    load_plan(plan_path)
    return plan_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    print(materialize(args.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
