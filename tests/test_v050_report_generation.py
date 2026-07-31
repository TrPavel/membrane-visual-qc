from __future__ import annotations

import json
from dataclasses import dataclass
import hashlib
from pathlib import Path

import pytest

from scripts.generate_stage4c_example import build_example as build_comparison_example
from scripts.generate_v050_pdbtm_examples import (
    build_cached_pdbtm_example,
    build_local_pdbtm_example,
    serialize,
)
from scripts.validate_example_reports import (
    V050_RELEASE_REPORTS,
    v050_release_report_inventory,
    validate_retained_report_privacy,
)
from membrane_vqc.pdbtm_cache import CacheRepository


COMMIT = "a" * 40


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


def _seed_cache(cache_dir: Path, record_id: str = "9zzz") -> None:
    fixture = Path(__file__).resolve().parents[1] / "data" / "synthetic"
    json_bytes = (
        (fixture / "pdbtm_api_v1_test.json")
        .read_bytes()
        .replace(b'"pdb_id":"test"', f'"pdb_id":"{record_id}"'.encode(), 1)
    )
    pdb_bytes = (
        (fixture / "pdbtm_transformed_test.pdb")
        .read_bytes()
        .replace(b"TEST\n", f"{record_id.upper()}\n".encode(), 1)
    )
    payloads = []
    for role, suffix, body, second in (
        ("pdbtm_json", "json", json_bytes, 0),
        ("transformed_pdb", "trpdb", pdb_bytes, 2),
    ):
        url = f"https://pdbtm.unitmp.org/api/v1/entry/{record_id}.{suffix}"
        payloads.append(
            _Payload(
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
        )
    repository = CacheRepository(cache_dir)
    generation = repository.capture_record_generation(record_id)
    repository.commit_validated_pair(
        _Candidate(record_id, tuple(payloads)), expected_record_generation=generation
    )


def test_local_pdbtm_release_example_is_deterministic_and_private():
    first = build_local_pdbtm_example(software_version="0.5.0", software_commit=COMMIT)
    second = build_local_pdbtm_example(software_version="0.5.0", software_commit=COMMIT)

    assert first == second
    assert serialize(first) == serialize(second)
    assert first["schema_version"] == "1.3"
    assert first["software"]["version"] == "0.5.0"
    assert first["software"]["commit"] == COMMIT
    assert first["runtime"] == {
        "python": "3.10.20",
        "pymol": "3.1.8",
        "pymol_status": "recorded",
        "platform": "Windows-10-build-26200",
    }
    validate_retained_report_privacy(first)


def test_cached_pdbtm_release_example_reads_real_cache_snapshot(tmp_path):
    cache_dir = tmp_path / "cache"
    _seed_cache(cache_dir)
    arguments = {
        "software_version": "0.5.0",
        "software_commit": COMMIT,
        "cache_dir": cache_dir,
        "record_id": "9zzz",
    }
    first = build_cached_pdbtm_example(**arguments)
    second = build_cached_pdbtm_example(**arguments)
    assert first == second
    assert first["schema_version"] == "1.4"
    assert first["orientation"]["acquisition"]["canonical_record_id"] == "9zzz"
    validate_retained_report_privacy(first)


def test_release_generators_require_truthful_commit():
    with pytest.raises(ValueError, match="40-character"):
        build_local_pdbtm_example(software_version="0.5.0", software_commit="placeholder")


def test_v050_inventory_records_exact_bytes(tmp_path):
    cache_dir = tmp_path / "cache"
    _seed_cache(cache_dir)
    reports = {
        "1.3": build_local_pdbtm_example(software_version="0.5.0", software_commit=COMMIT),
        "1.4": build_cached_pdbtm_example(
            software_version="0.5.0",
            software_commit=COMMIT,
            cache_dir=cache_dir,
            record_id="9zzz",
        ),
        "1.5": build_comparison_example(software_version="0.5.0", software_commit=COMMIT),
    }
    for relative, schema in V050_RELEASE_REPORTS.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(reports[schema], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    inventory = v050_release_report_inventory(tmp_path)

    assert [item["schema_version"] for item in inventory] == ["1.3", "1.4", "1.5"]
    assert all(item["generation_commit"] == COMMIT for item in inventory)
    assert all(item["byte_size"] > 0 for item in inventory)
    assert all(len(item["sha256"]) == 64 for item in inventory)


@pytest.mark.parametrize(
    "leak",
    [
        {"input": {"path": r"C:\\Users\\owner\\secret.pdb"}},
        {"runtime": {"hostname": "workstation"}},
        {"network": {"address": "192.168.1.7"}},
        {"error": "Traceback (most recent call last): private details"},
        {"credential": "abc"},
        {"cache_path": "/tmp/pdbtm-cache"},
        {"provider_payload": '{"pdb_id":"9zzz"}'},
        {"data": "ATOM      1  CA  ALA A   1       0.000   0.000   0.000"},
    ],
)
def test_privacy_validator_rejects_environment_leaks(leak):
    with pytest.raises(ValueError, match="sensitive"):
        validate_retained_report_privacy(leak)


def test_historical_schema_1_3_report_is_not_a_v050_inventory_member():
    assert Path("reports/pdbtm_synthetic_mvqc.json") not in V050_RELEASE_REPORTS
