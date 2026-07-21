"""Network-free integration tests for the Stage 4B3 cached-selection QC path.

Builds one real Stage 4B1 cached snapshot (real ``CacheRepository``, real
``commit_validated_pair``/``read_active``) from the existing synthetic
fixtures, then drives the un-registered ``commands.mvqc_check_pdbtm_cached``/
``mvqc_slab_pdbtm_cached`` helpers end to end through the real
``pdbtm_report_provenance`` conversion and ``report.build_report`` -- the
first place a report combines a real ``orientation.evidence`` (current-object
applicability) with a real ``orientation.acquisition`` (cache provenance).
Only the PyMOL-object-touching resolution step is stubbed, matching the
existing boundary used by ``test_pdbtm_pymol.py``'s local-file equivalents.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

from types import SimpleNamespace

from membrane_vqc import commands, qc
from membrane_vqc.orientation_sources import StructureContext
from membrane_vqc.pdbtm_adapter import import_pdbtm_orientation
from membrane_vqc.pdbtm_cache import CacheRepository
from membrane_vqc.report import validate_stage4_report_semantics

ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_ROOT = ROOT / "data" / "synthetic"
_JSON_TEMPLATE = (_FIXTURE_ROOT / "pdbtm_api_v1_test.json").read_bytes()
_PDB_TEMPLATE = (_FIXTURE_ROOT / "pdbtm_transformed_test.pdb").read_bytes()
_RECORD_ID = "9zzz"


def _valid_pdbtm_bytes(record_id: str = _RECORD_ID) -> tuple[bytes, bytes]:
    json_bytes = _JSON_TEMPLATE.replace(b'"pdb_id":"test"', f'"pdb_id":"{record_id}"'.encode(), 1)
    pdb_bytes = _PDB_TEMPLATE.replace(b"TEST\n", (record_id.upper() + "\n").encode(), 1)
    return json_bytes, pdb_bytes


class _Evidence:
    def __init__(
        self,
        url,
        status,
        content_type,
        charset,
        requested_at,
        completed_at,
        byte_size,
        sha256,
        tls_verified=True,
    ):
        self.requested_url = url
        self.final_url = url
        self.status = status
        self.content_type = content_type
        self.charset = charset
        self.content_encoding = None
        self.etag = None
        self.last_modified = None
        self.requested_at = requested_at
        self.completed_at = completed_at
        self.byte_size = byte_size
        self.sha256 = sha256
        self.tls_verified = tls_verified


class _Payload:
    def __init__(self, role, body, evidence):
        self.role = role
        self.body = body
        self.evidence = evidence


class _Versions:
    resource_version = "1017"
    software_version = "3.2.134"


class _Candidate:
    def __init__(self, record_id, payloads):
        self.canonical_record_id = record_id
        self.payloads = payloads
        self.provider_versions = _Versions()


def _payload(record_id, role, body, second):
    suffix = "json" if role == "pdbtm_json" else "trpdb"
    url = f"https://pdbtm.unitmp.org/api/v1/entry/{record_id}.{suffix}"
    content_type = "application/json" if role == "pdbtm_json" else "text/plain"
    charset = None if role == "pdbtm_json" else "utf-8"
    digest = hashlib.sha256(body).hexdigest()
    evidence = _Evidence(
        url,
        200,
        content_type,
        charset,
        f"2026-07-21T00:00:0{second}.000000Z",
        f"2026-07-21T00:00:0{second + 1}.000000Z",
        len(body),
        digest,
    )
    return _Payload(role, body, evidence)


def _committed_snapshot(tmp_path, record_id: str = _RECORD_ID):
    json_bytes, pdb_bytes = _valid_pdbtm_bytes(record_id)
    repository = CacheRepository(
        tmp_path / "cache-v1",
        utc_now=lambda: datetime(2026, 7, 21, 0, 0, 4, tzinfo=timezone.utc),
    )
    generation = repository.capture_record_generation(record_id)
    candidate = _Candidate(
        record_id,
        (
            _payload(record_id, "pdbtm_json", json_bytes, 0),
            _payload(record_id, "transformed_pdb", pdb_bytes, 2),
        ),
    )
    repository.commit_validated_pair(candidate, expected_record_generation=generation)
    return repository.read_active(record_id)


def _current_object_imported(snapshot):
    json_bytes, pdb_bytes = snapshot.payloads
    return import_pdbtm_orientation(
        json_bytes,
        pdb_bytes,
        StructureContext(pdb_bytes, None, 1, coordinate_frame="pymol_current_object"),
    )


def test_cached_qc_produces_schema_1_4_with_both_evidence_and_acquisition(tmp_path, monkeypatch):
    snapshot = _committed_snapshot(tmp_path)
    imported = _current_object_imported(snapshot)
    assert imported.status == "imported"

    monkeypatch.setattr(commands, "clear_owned", lambda: None)
    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj=None: [])
    monkeypatch.setattr(qc, "clear_context", lambda cmd_obj=None: None)
    calls = []

    def fake_resolve(**kwargs):
        calls.append(kwargs)
        return imported

    monkeypatch.setattr(commands, "resolve_pdbtm_from_payloads", fake_resolve)
    qc.LAST_REPORT = None

    report = commands.mvqc_check_pdbtm_cached(
        snapshot,
        selection="protein and chain A",
        cache_generation=1,
    )

    assert calls[0]["pdbtm_json_payload"] == snapshot.payloads[0]
    assert calls[0]["transformed_pdb_payload"] == snapshot.payloads[1]
    assert report["schema_version"] == "1.4"
    assert "evidence" in report["orientation"]
    assert "acquisition" in report["orientation"]
    acquisition = report["orientation"]["acquisition"]
    assert acquisition["canonical_record_id"] == _RECORD_ID
    assert acquisition["consumption_mode"] == "active_cache_read"
    assert acquisition["cache_generation"] == 1
    assert acquisition["object_applicability"] == {
        "established": False,
        "scope": "not_evaluated",
        "statement": acquisition["object_applicability"]["statement"],
    }
    validate_stage4_report_semantics(report)
    assert qc.LAST_REPORT is report


def test_cached_qc_defaults_consumption_mode_to_active_cache_read(tmp_path, monkeypatch):
    snapshot = _committed_snapshot(tmp_path)
    imported = _current_object_imported(snapshot)
    monkeypatch.setattr(commands, "clear_owned", lambda: None)
    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj=None: [])
    monkeypatch.setattr(qc, "clear_context", lambda cmd_obj=None: None)
    monkeypatch.setattr(commands, "resolve_pdbtm_from_payloads", lambda **kwargs: imported)

    report = commands.mvqc_check_pdbtm_cached(snapshot, selection="protein and chain A")

    assert report["orientation"]["acquisition"]["consumption_mode"] == "active_cache_read"
    assert report["orientation"]["acquisition"]["cache_generation"] is None


def test_cached_qc_failure_clears_state_and_report(monkeypatch):
    cleared = []
    monkeypatch.setattr(commands, "clear_owned", lambda: cleared.append("clear"))
    monkeypatch.setattr(
        commands,
        "resolve_pdbtm_from_payloads",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    qc.LAST_REPORT = {"stale": True}
    fake_snapshot = SimpleNamespace(payloads=(b"json-bytes", b"pdb-bytes"))

    import pytest

    with pytest.raises(RuntimeError, match="boom"):
        commands.mvqc_check_pdbtm_cached(fake_snapshot, selection="protein and chain A")

    assert cleared == ["clear", "clear"]
    assert qc.LAST_REPORT is None


def test_cached_slab_renders_current_frame_boundaries_without_network(tmp_path, monkeypatch):
    snapshot = _committed_snapshot(tmp_path)
    imported = _current_object_imported(snapshot)
    monkeypatch.setattr(commands, "clear_owned", lambda: None)
    monkeypatch.setattr(commands, "resolve_pdbtm_from_payloads", lambda **kwargs: imported)
    monkeypatch.setattr(commands, "protein_atoms", lambda selection: [object()])
    rendered = []
    monkeypatch.setattr(
        commands,
        "create_membrane_planes",
        lambda membrane, atoms, selection: rendered.append((membrane, atoms, selection)),
    )

    result = commands.mvqc_slab_pdbtm_cached(snapshot, selection="protein and chain A")

    assert result is imported
    assert rendered[0][0] is imported.membrane


def test_local_file_reports_still_emit_schema_1_3(tmp_path, monkeypatch):
    """Regression guard: the cached path must never change the local-file dispatch."""
    from membrane_vqc.pdbtm_pymol import resolve_pdbtm_from_pymol

    json_path = _FIXTURE_ROOT / "pdbtm_api_v1_test.json"
    pdb_path = _FIXTURE_ROOT / "pdbtm_transformed_test.pdb"
    imported = resolve_pdbtm_from_pymol(
        selection="protein and chain A",
        pdbtm_json_path=str(json_path),
        transformed_pdb_path=str(pdb_path),
        cmd_obj=_LocalSnapshotCmd(pdb_path),
    )
    monkeypatch.setattr(commands, "clear_owned", lambda: None)
    monkeypatch.setattr(qc, "protein_atoms", lambda selection, cmd_obj=None: [])
    monkeypatch.setattr(qc, "clear_context", lambda cmd_obj=None: None)
    monkeypatch.setattr(commands, "resolve_pdbtm_from_pymol", lambda **kwargs: imported)

    report = commands.mvqc_check_pdbtm(
        selection="protein and chain A",
        pdbtm_json=str(json_path),
        transformed_pdb=str(pdb_path),
    )

    assert report["schema_version"] == "1.3"
    assert "acquisition" not in report["orientation"]


class _LocalSnapshotCmd:
    def __init__(self, pdb_path):
        self.pdb_text = Path(pdb_path).read_text(encoding="ascii")
        self.atoms = []
        for line in self.pdb_text.splitlines():
            if not line.startswith("ATOM  "):
                continue
            from types import SimpleNamespace

            self.atoms.append(
                SimpleNamespace(
                    chain=line[21:22].strip(),
                    resi=line[22:27].strip(),
                    resn=line[17:20].strip(),
                    name=line[12:16].strip(),
                    alt=line[16:17].strip(),
                    q=float(line[54:60]),
                    coord=(float(line[30:38]), float(line[38:46]), float(line[46:54])),
                )
            )

    def get_object_list(self, selection):
        return ["protein"]

    def count_states(self, object_name):
        return 1

    def get_model(self, selection, state=1):
        from types import SimpleNamespace

        return SimpleNamespace(atom=self.atoms)

    def get_pdbstr(self, selection, state=1):
        return self.pdb_text
