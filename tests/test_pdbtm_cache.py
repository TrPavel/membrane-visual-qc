from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import threading

import pytest

import membrane_vqc.pdbtm_cache as cache_module
from membrane_vqc.pdbtm_cache import CacheRepository, select_cache_root
from membrane_vqc.pdbtm_errors import Stage4BError, Stage4BErrorCode


@dataclass(frozen=True)
class FakeEvidence:
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
class FakePayload:
    role: str
    body: bytes
    evidence: FakeEvidence


@dataclass(frozen=True)
class FakeVersions:
    resource_version: str = "1017"
    software_version: str = "3.2.134"


@dataclass(frozen=True)
class FakeCandidate:
    canonical_record_id: str
    payloads: tuple[FakePayload, FakePayload]
    provider_versions: FakeVersions = FakeVersions()


_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "data" / "synthetic"
_JSON_TEMPLATE = (_FIXTURE_ROOT / "pdbtm_api_v1_test.json").read_bytes()
_PDB_TEMPLATE = (_FIXTURE_ROOT / "pdbtm_transformed_test.pdb").read_bytes()


def _resource_version(marker: bytes) -> str:
    return f"1017.{marker.decode('ascii')}"


def _valid_pdbtm_bytes(record_id: str, marker: bytes) -> tuple[bytes, bytes]:
    """Build a genuinely valid synthetic PDBTM pair so real semantic validation

    (now required by ``commit_validated_pair``) actually accepts it. ``marker``
    only varies the otherwise-unvalidated ``resource_version`` field, so
    distinct markers still parse and validate identically while producing
    distinguishable bytes/digests/snapshot ids for the same record.
    """

    json_bytes = _JSON_TEMPLATE.replace(b'"pdb_id":"test"', f'"pdb_id":"{record_id}"'.encode(), 1)
    json_bytes = json_bytes.replace(
        b'"resource_version":"1017"',
        f'"resource_version":"{_resource_version(marker)}"'.encode(),
        1,
    )
    pdb_bytes = _PDB_TEMPLATE.replace(b"TEST\n", (record_id.upper() + "\n").encode(), 1)
    return json_bytes, pdb_bytes


def _payload(record_id: str, role: str, body: bytes, second: int) -> FakePayload:
    suffix = "json" if role == "pdbtm_json" else "trpdb"
    url = f"https://pdbtm.unitmp.org/api/v1/entry/{record_id}.{suffix}"
    digest = hashlib.sha256(body).hexdigest()
    return FakePayload(
        role,
        body,
        FakeEvidence(
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
            digest,
        ),
    )


def _candidate(record_id: str = "1pcr", marker: bytes = b"one") -> FakeCandidate:
    json_bytes, pdb_bytes = _valid_pdbtm_bytes(record_id, marker)
    return FakeCandidate(
        record_id,
        (
            _payload(record_id, "pdbtm_json", json_bytes, 0),
            _payload(record_id, "transformed_pdb", pdb_bytes, 2),
        ),
        provider_versions=FakeVersions(resource_version=_resource_version(marker)),
    )


def _repository(tmp_path: Path, **kwargs) -> CacheRepository:
    return CacheRepository(
        tmp_path / "cache-v1",
        utc_now=lambda: datetime(2026, 7, 20, 0, 0, 4, tzinfo=timezone.utc),
        **kwargs,
    )


def _accept(record_id: str, json_body: bytes, pdb_body: bytes):
    return record_id, hashlib.sha256(json_body + pdb_body).hexdigest()


def test_root_selection_rejects_relative_tilde_unc_and_device_paths(tmp_path):
    with pytest.raises(Stage4BError) as relative:
        select_cache_root(environ={"MVQC_CACHE_DIR": "relative"})
    assert relative.value.code is Stage4BErrorCode.CACHE_OPEN_FAILED

    for unsafe in ("~/cache", r"\\server\share", r"\\?\C:\cache", r"\\.\device"):
        with pytest.raises(Stage4BError):
            select_cache_root(environ={"MVQC_CACHE_DIR": unsafe})

    selected = select_cache_root(environ={"MVQC_CACHE_DIR": str(tmp_path)})
    assert selected == tmp_path / "pdbtm-api-v1" / "cache-v1"


def test_xdg_relative_value_falls_back_to_home(tmp_path):
    selected = select_cache_root(
        environ={"XDG_CACHE_HOME": "relative"}, platform="linux", home=tmp_path
    )
    assert selected == tmp_path / ".cache" / "membrane-visual-qc" / "pdbtm-api-v1" / "cache-v1"


def test_initialize_creates_canonical_empty_cache(tmp_path):
    repository = _repository(tmp_path)
    repository.initialize()

    assert repository.root == tmp_path / "cache-v1"
    assert repository.inspect().generation == 0
    assert dict(repository.inspect().records) == {}
    assert (repository.root / "format.json").is_file()
    assert (repository.root / "index.json").is_file()
    assert repository.list_snapshots("1pcr") == ()
    reopened = CacheRepository(repository.root)
    assert reopened.inspect().generation == 0


def test_concurrent_initializers_converge_on_one_valid_empty_cache(tmp_path):
    root = tmp_path / "cache-v1"
    repositories = [CacheRepository(root) for _ in range(4)]
    barrier = threading.Barrier(5)
    errors: list[BaseException] = []

    def initialize(repository: CacheRepository) -> None:
        barrier.wait()
        try:
            repository.initialize()
        except BaseException as error:  # pragma: no cover - asserted empty below
            errors.append(error)

    threads = [
        threading.Thread(target=initialize, args=(repository,)) for repository in repositories
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert errors == []
    assert repositories[0].inspect().generation == 0


def test_identical_snapshot_is_deduplicated_but_publication_advances_generation(tmp_path):
    repository = _repository(tmp_path)
    first = repository.commit_validated_pair(_candidate(), expected_record_generation=0)
    first_generation = repository.capture_record_generation("1pcr")
    second = repository.commit_validated_pair(
        _candidate(), expected_record_generation=first_generation
    )

    assert second.snapshot_id == first.snapshot_id
    assert repository.list_snapshots("1pcr") == (first.snapshot_id,)
    assert repository.capture_record_generation("1pcr") == first_generation + 1


def test_commit_rejects_missing_or_false_tls_verification(tmp_path):
    repository = _repository(tmp_path)
    candidate = _candidate()
    unsafe_first = replace(
        candidate.payloads[0], evidence=replace(candidate.payloads[0].evidence, tls_verified=False)
    )
    unsafe = replace(candidate, payloads=(unsafe_first, candidate.payloads[1]))

    with pytest.raises(Stage4BError) as caught:
        repository.commit_validated_pair(unsafe, expected_record_generation=0)
    assert caught.value.code is Stage4BErrorCode.CACHE_WRITE_FAILED
    assert repository.capture_record_generation("1pcr") == 0


def test_candidate_with_lying_provider_versions_cannot_replace_active_snapshot(tmp_path):
    """A hand-constructed candidate cannot be trusted merely because it has the

    right shape: ``commit_validated_pair`` must independently re-derive
    provider_versions from the raw bytes and reject any disagreement before
    the previous active snapshot is ever replaced.
    """

    repository = _repository(tmp_path)
    original = repository.commit_validated_pair(
        _candidate(marker=b"one"), expected_record_generation=0
    )

    lying = replace(
        _candidate(marker=b"two"),
        provider_versions=FakeVersions(resource_version="9999-not-really-embedded"),
    )

    with pytest.raises(Stage4BError) as caught:
        repository.commit_validated_pair(
            lying, expected_record_generation=repository.capture_record_generation("1pcr")
        )
    assert caught.value.code is Stage4BErrorCode.CACHE_WRITE_FAILED

    assert repository.capture_record_generation("1pcr") == 1
    assert repository.read_active("1pcr", validator=_accept).snapshot_id == original.snapshot_id


def test_structurally_plausible_but_adapter_invalid_candidate_cannot_replace_active_snapshot(
    tmp_path,
):
    repository = _repository(tmp_path)
    original = repository.commit_validated_pair(
        _candidate(marker=b"one"), expected_record_generation=0
    )

    bad_json = _JSON_TEMPLATE.replace(b'"pdb_id":"test"', b'"pdb_id":"1pcr"', 1)
    # Break the identity-frame transformation matrix so the offline adapter's
    # scientific pair validation fails, even though every structural/digest
    # check the repository performs on its own would otherwise accept this.
    bad_json = bad_json.replace(b'"y":-1.00000000', b'"y":-0.90000000', 1)
    bad_pdb = _PDB_TEMPLATE.replace(b"TEST\n", b"1PCR\n", 1)
    candidate = FakeCandidate(
        "1pcr",
        (
            _payload("1pcr", "pdbtm_json", bad_json, 0),
            _payload("1pcr", "transformed_pdb", bad_pdb, 2),
        ),
        provider_versions=FakeVersions(resource_version="1017"),
    )

    with pytest.raises(Stage4BError) as caught:
        repository.commit_validated_pair(
            candidate, expected_record_generation=repository.capture_record_generation("1pcr")
        )
    assert caught.value.code is Stage4BErrorCode.CACHE_WRITE_FAILED

    assert repository.capture_record_generation("1pcr") == 1
    assert repository.read_active("1pcr", validator=_accept).snapshot_id == original.snapshot_id


def test_oversized_manifest_is_rejected_before_index_replacement(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    original = repository.commit_validated_pair(
        _candidate(marker=b"one"), expected_record_generation=0
    )

    monkeypatch.setattr(cache_module, "_MANIFEST_LIMIT", 10)
    try:
        with pytest.raises(Stage4BError) as caught:
            repository.commit_validated_pair(
                _candidate(marker=b"two"),
                expected_record_generation=repository.capture_record_generation("1pcr"),
            )
        assert caught.value.code is Stage4BErrorCode.CACHE_WRITE_FAILED
        assert repository.capture_record_generation("1pcr") == 1
    finally:
        monkeypatch.setattr(cache_module, "_MANIFEST_LIMIT", 1024 * 1024)

    assert repository.read_active("1pcr", validator=_accept).snapshot_id == original.snapshot_id


def test_oversized_index_is_rejected_before_replacement(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    original = repository.commit_validated_pair(
        _candidate(marker=b"one"), expected_record_generation=0
    )
    generation = repository.capture_record_generation("1pcr")
    # Pin the limit just above the *current* (still-readable) index size, so
    # only the larger index produced by adding a second snapshot is refused.
    current_index_size = (repository.root / "index.json").stat().st_size

    monkeypatch.setattr(cache_module, "_INDEX_LIMIT", current_index_size + 5)
    try:
        with pytest.raises(Stage4BError) as caught:
            repository.commit_validated_pair(
                _candidate(marker=b"two"), expected_record_generation=generation
            )
        assert caught.value.code is Stage4BErrorCode.CACHE_WRITE_FAILED
        assert repository.capture_record_generation("1pcr") == 1
    finally:
        monkeypatch.setattr(cache_module, "_INDEX_LIMIT", 4 * 1024 * 1024)

    assert repository.read_active("1pcr", validator=_accept).snapshot_id == original.snapshot_id


def test_commit_read_and_list_validate_all_bytes(tmp_path):
    repository = _repository(tmp_path)
    generation = repository.capture_record_generation("1pcr")
    committed = repository.commit_validated_pair(
        _candidate(), expected_record_generation=generation
    )

    assert repository.list_snapshots("1pcr") == (committed.snapshot_id,)
    # Calling inspect from the validator proves the filesystem lock was released.
    checked = repository.read_active(
        "1pcr",
        validator=lambda record, first, second: (
            repository.inspect(),
            _accept(record, first, second),
        ),
    )
    assert checked.snapshot_id == committed.snapshot_id
    assert checked.payloads == (
        _candidate().payloads[0].body,
        _candidate().payloads[1].body,
    )
    assert checked.semantic_result[1][0] == "1pcr"
    explicit = repository.read_snapshot("1pcr", committed.snapshot_id, validator=_accept)
    assert explicit.semantic_result == _accept("1pcr", *explicit.payloads)


def test_corrupt_active_blob_fails_without_fallback(tmp_path):
    repository = _repository(tmp_path)
    committed = repository.commit_validated_pair(_candidate(), expected_record_generation=0)
    digest = committed.snapshot_core.payloads[0].sha256
    blob = repository.root / "blobs" / "sha256" / digest[:2] / digest
    blob.write_bytes(b"corrupt")

    with pytest.raises(Stage4BError) as caught:
        repository.read_active("1pcr", validator=_accept)
    assert caught.value.code is Stage4BErrorCode.CACHE_CORRUPT


def test_missing_active_blob_is_cache_corruption(tmp_path):
    repository = _repository(tmp_path)
    committed = repository.commit_validated_pair(_candidate(), expected_record_generation=0)
    digest = committed.snapshot_core.payloads[0].sha256
    blob = repository.root / "blobs" / "sha256" / digest[:2] / digest
    blob.unlink()

    with pytest.raises(Stage4BError) as caught:
        repository.read_active("1pcr", validator=_accept)
    assert caught.value.code is Stage4BErrorCode.CACHE_CORRUPT


def test_manifest_corruption_and_missing_active_never_fall_back(tmp_path):
    repository = _repository(tmp_path)
    committed = repository.commit_validated_pair(_candidate(), expected_record_generation=0)
    manifest = repository.root / "records" / "1pcr" / "snapshots" / f"{committed.snapshot_id}.json"
    manifest.write_bytes(manifest.read_bytes() + b"\n")

    with pytest.raises(Stage4BError) as caught:
        repository.read_active("1pcr", validator=_accept)
    assert caught.value.code is Stage4BErrorCode.CACHE_CORRUPT

    clean = _repository(tmp_path / "other")
    with pytest.raises(Stage4BError) as missing:
        clean.read_active("1pcr", validator=_accept)
    assert missing.value.code is Stage4BErrorCode.CACHE_MISS


def test_explicit_older_snapshot_remains_selectable_after_refresh(tmp_path):
    repository = _repository(tmp_path)
    first = repository.commit_validated_pair(
        _candidate(marker=b"one"), expected_record_generation=0
    )
    second = repository.commit_validated_pair(
        _candidate(marker=b"two"),
        expected_record_generation=repository.capture_record_generation("1pcr"),
    )

    assert second.snapshot_id != first.snapshot_id
    assert repository.read_active("1pcr", validator=_accept).snapshot_id == second.snapshot_id
    older = repository.read_snapshot("1pcr", first.snapshot_id, validator=_accept)
    assert older.snapshot_id == first.snapshot_id
    assert repository.list_snapshots("1pcr") == tuple(
        sorted((first.snapshot_id, second.snapshot_id))
    )


def test_clear_preserves_tombstone_and_blocks_stale_publication(tmp_path):
    repository = _repository(tmp_path)
    repository.commit_validated_pair(_candidate(), expected_record_generation=0)
    captured = repository.capture_record_generation("1pcr")
    tombstone = repository.clear("1pcr")

    assert tombstone == captured + 1
    assert repository.inspect().records["1pcr"].snapshot_ids == ()
    with pytest.raises(Stage4BError) as missing:
        repository.read_active("1pcr", validator=_accept)
    assert missing.value.code is Stage4BErrorCode.CACHE_MISS
    with pytest.raises(Stage4BError) as conflict:
        repository.commit_validated_pair(
            _candidate(marker=b"stale"), expected_record_generation=captured
        )
    assert conflict.value.code is Stage4BErrorCode.CACHE_CONFLICT


def test_refresh_failure_before_index_preserves_previous_active_snapshot(tmp_path):
    base = _repository(tmp_path)
    original = base.commit_validated_pair(_candidate(), expected_record_generation=0)

    def failpoint(name: str) -> None:
        if name == "before_index_replace":
            raise OSError("injected")

    failing = _repository(tmp_path, failpoint=failpoint)
    with pytest.raises(Stage4BError) as caught:
        failing.commit_validated_pair(
            _candidate(marker=b"two"),
            expected_record_generation=base.capture_record_generation("1pcr"),
        )
    assert caught.value.code is Stage4BErrorCode.CACHE_WRITE_FAILED
    assert base.read_active("1pcr", validator=_accept).snapshot_id == original.snapshot_id


def test_post_index_replace_failure_reports_uncertain_durability(tmp_path):
    replacements = 0

    def failpoint(name: str) -> None:
        nonlocal replacements
        if name == "after_index_replace":
            replacements += 1
        if replacements == 2 and name == "after_index_replace":
            raise OSError("injected")

    repository = _repository(tmp_path, failpoint=failpoint)
    with pytest.raises(Stage4BError) as caught:
        repository.commit_validated_pair(_candidate(), expected_record_generation=0)
    assert caught.value.code is Stage4BErrorCode.CACHE_DURABILITY_UNCERTAIN

    reopened = CacheRepository(repository.root)
    assert reopened.read_active("1pcr", validator=_accept).canonical_record_id == "1pcr"


def test_two_writers_from_one_generation_have_one_winner(tmp_path):
    repository = _repository(tmp_path)
    expected = repository.capture_record_generation("1pcr")
    barrier = threading.Barrier(3)
    outcomes: list[object] = []

    def write(marker: bytes) -> None:
        barrier.wait()
        try:
            outcomes.append(
                repository.commit_validated_pair(
                    _candidate(marker=marker), expected_record_generation=expected
                )
            )
        except Stage4BError as error:
            outcomes.append(error.code)

    threads = [threading.Thread(target=write, args=(marker,)) for marker in (b"a", b"b")]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert len([item for item in outcomes if item is Stage4BErrorCode.CACHE_CONFLICT]) == 1
    assert len([item for item in outcomes if not isinstance(item, Stage4BErrorCode)]) == 1


def test_active_read_rechecks_generation_after_semantic_validation(tmp_path):
    repository = _repository(tmp_path)
    repository.commit_validated_pair(_candidate(), expected_record_generation=0)

    def clearing_validator(record_id: str, first: bytes, second: bytes):
        repository.clear(record_id)
        return first, second

    with pytest.raises(Stage4BError) as caught:
        repository.read_active("1pcr", validator=clearing_validator)
    assert caught.value.code is Stage4BErrorCode.CACHE_CONFLICT


def test_explicit_snapshot_rechecks_membership_after_semantic_validation(tmp_path):
    repository = _repository(tmp_path)
    committed = repository.commit_validated_pair(_candidate(), expected_record_generation=0)

    def clearing_validator(record_id: str, first: bytes, second: bytes):
        repository.clear(record_id)
        return first, second

    with pytest.raises(Stage4BError) as caught:
        repository.read_snapshot("1pcr", committed.snapshot_id, validator=clearing_validator)
    assert caught.value.code is Stage4BErrorCode.CACHE_CONFLICT


def test_symlinked_or_reparse_cache_owned_directory_is_rejected(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    repository.initialize()
    blobs = repository.root / "blobs"
    target = tmp_path / "outside"
    target.mkdir()
    real_blobs = repository.root / "real-blobs"
    blobs.rename(real_blobs)
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(blobs), str(target)],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            real_blobs.rename(blobs)
            monkeypatch.setattr(
                cache_module,
                "_is_reparse_point",
                lambda path: Path(path) == blobs,
            )
    else:
        blobs.symlink_to(target, target_is_directory=True)

    with pytest.raises(Stage4BError) as caught:
        repository.capture_record_generation("1pcr")
    assert caught.value.code is Stage4BErrorCode.CACHE_OPEN_FAILED


def test_noncanonical_record_and_snapshot_paths_are_rejected(tmp_path):
    repository = _repository(tmp_path)
    for value in ("../x", "1PCR", "", "abcde"):
        with pytest.raises(Stage4BError):
            repository.capture_record_generation(value)
    with pytest.raises(Stage4BError) as caught:
        repository.read_snapshot("1pcr", "../manifest", validator=_accept)
    assert caught.value.code is Stage4BErrorCode.CACHE_MISS


def test_format_or_index_shape_changes_fail_closed(tmp_path):
    repository = _repository(tmp_path)
    repository.initialize()
    (repository.root / "format.json").write_bytes(b"{}")
    with pytest.raises(Stage4BError) as format_error:
        repository.inspect()
    assert format_error.value.code is Stage4BErrorCode.CACHE_FORMAT_UNSUPPORTED

    other = _repository(tmp_path / "other")
    other.initialize()
    (other.root / "index.json").write_bytes(b"{}")
    with pytest.raises(Stage4BError) as index_error:
        other.inspect()
    assert index_error.value.code is Stage4BErrorCode.CACHE_CORRUPT


@pytest.mark.parametrize("relative", ["format.json", "index.json", "locks/cache.lock"])
def test_nonregular_fixed_cache_files_are_rejected(tmp_path, relative):
    repository = _repository(tmp_path)
    repository.initialize()
    path = repository.root / relative
    path.unlink()
    path.mkdir()

    with pytest.raises(Stage4BError) as caught:
        repository.inspect()
    assert caught.value.code in {
        Stage4BErrorCode.CACHE_OPEN_FAILED,
        Stage4BErrorCode.CACHE_FORMAT_UNSUPPORTED,
        Stage4BErrorCode.CACHE_CORRUPT,
    }
