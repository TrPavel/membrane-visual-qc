"""Validated, deterministic filesystem cache for PDBTM API-v1 pairs.

The repository owns persistence only.  It never performs network I/O and it
never holds its advisory lock while running the scientific pair validator.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
from types import MappingProxyType
from typing import BinaryIO, Iterator
from uuid import uuid4

from .pdbtm_cache_contract import (
    AcquisitionPayload,
    ContentTypeEvidence,
    FormatCore,
    IndexCore,
    IndexRecord,
    PAYLOAD_ROLES,
    PairCore,
    PayloadIdentity,
    ProviderVersions,
    ResponseHeaders,
    SnapshotCore,
    SnapshotEnvelope,
    compute_pair_id,
    make_format_envelope,
    make_index_envelope,
    make_snapshot_envelope,
    parse_format_envelope,
    parse_index_envelope,
    parse_snapshot_envelope,
    serialize_format_envelope,
    serialize_index_envelope,
    serialize_snapshot_envelope,
)
from .pdbtm_errors import Stage4BError, Stage4BErrorCode

_CACHE_SUFFIX = ("pdbtm-api-v1", "cache-v1")
_RECORD_ID = re.compile(r"[0-9][a-z0-9]{3}\Z", re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_FORMAT_LIMIT = 16 * 1024
_INDEX_LIMIT = 4 * 1024 * 1024
_MANIFEST_LIMIT = 1024 * 1024
_BLOB_LIMIT = 5 * 1024 * 1024
_PAIR_LIMIT = 10 * 1024 * 1024
_DEFAULT_LOCK_TIMEOUT = 5.0
_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.Lock] = {}

SemanticValidator = Callable[[str, bytes, bytes], object]
Failpoint = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class CachedSnapshot:
    """One integrity-checked snapshot copied fully into memory."""

    snapshot_id: str
    snapshot_core: SnapshotCore
    payloads: tuple[bytes, bytes]
    semantic_result: object | None = None

    @property
    def canonical_record_id(self) -> str:
        return self.snapshot_core.canonical_record_id


@dataclass(frozen=True, slots=True)
class CacheInspection:
    """Safe cache metadata; absolute filesystem paths are deliberately absent."""

    generation: int
    records: Mapping[str, IndexRecord]


def select_cache_root(
    *,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: Path | None = None,
) -> Path:
    """Select the versioned cache root without consulting the current directory."""

    environment = os.environ if environ is None else environ
    platform_name = sys.platform if platform is None else platform
    override = environment.get("MVQC_CACHE_DIR")
    if override is not None:
        base = _validated_base_path(override)
    elif platform_name == "win32":
        local_app_data = environment.get("LOCALAPPDATA")
        if not local_app_data:
            raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
        base = _validated_base_path(local_app_data) / "MembraneVisualQC" / "Cache"
    elif platform_name == "darwin":
        base = (Path.home() if home is None else home) / "Library" / "Caches" / "MembraneVisualQC"
    else:
        xdg = environment.get("XDG_CACHE_HOME")
        if xdg and Path(xdg).is_absolute() and "~" not in xdg:
            base = Path(xdg) / "membrane-visual-qc"
        else:
            base = (Path.home() if home is None else home) / ".cache" / "membrane-visual-qc"
    return base.joinpath(*_CACHE_SUFFIX)


def _validated_base_path(value: str) -> Path:
    if not value or "~" in value:
        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
    # Stage 4B1 intentionally rejects UNC and Win32 device namespaces.
    normalized = value.replace("/", "\\")
    if (
        normalized.startswith("\\\\")
        or normalized.startswith("\\?\\")
        or normalized.startswith("\\.\\")
    ):
        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
    path = Path(value)
    if not path.is_absolute():
        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
    return path


def _error(code: Stage4BErrorCode) -> Stage4BError:
    return Stage4BError(code)


def _record_id(value: str) -> str:
    if type(value) is not str or _RECORD_ID.fullmatch(value) is None:
        raise _error(Stage4BErrorCode.INVALID_RECORD_ID)
    return value


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except AttributeError:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _reject_link_or_special(path: Path, *, directory: bool | None = None) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as error:
        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED) from error
    if stat.S_ISLNK(details.st_mode) or _is_reparse_point(path):
        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
    if directory is True and not stat.S_ISDIR(details.st_mode):
        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
    if directory is False and not stat.S_ISREG(details.st_mode):
        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
    return details


def _reject_existing_parent_links(path: Path) -> None:
    """Reject links/reparse points in every already-existing path component."""

    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        if os.path.lexists(current):
            _reject_link_or_special(current, directory=True)


def _process_lock(path: Path) -> threading.Lock:
    key = os.path.normcase(os.path.abspath(path))
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(key, threading.Lock())


def _open_existing_regular(path: Path, flags: int, error_code: Stage4BErrorCode) -> int:
    """Open an existing regular file without following a Windows reparse point."""

    binary_flags = flags | getattr(os, "O_BINARY", 0)
    if os.name != "nt":
        return os.open(path, binary_flags | getattr(os, "O_NOFOLLOW", 0))

    import ctypes
    from ctypes import wintypes
    import msvcrt

    generic_read = 0x80000000
    generic_write = 0x40000000
    desired_access = generic_read | (generic_write if flags & os.O_RDWR else 0)
    share_all = 0x00000001 | 0x00000002 | 0x00000004
    open_existing = 3
    file_attribute_normal = 0x00000080
    file_flag_open_reparse_point = 0x00200000
    file_attribute_reparse_point = 0x00000400
    file_attribute_tag_info = 9
    invalid_handle = ctypes.c_void_p(-1).value

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        desired_access,
        share_all,
        None,
        open_existing,
        file_attribute_normal | file_flag_open_reparse_point,
        None,
    )
    if handle == invalid_handle:
        raise _error(error_code)

    class FileAttributeTagInfo(ctypes.Structure):
        _fields_ = (("file_attributes", wintypes.DWORD), ("reparse_tag", wintypes.DWORD))

    information = FileAttributeTagInfo()
    get_information = kernel32.GetFileInformationByHandleEx
    get_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    get_information.restype = wintypes.BOOL
    try:
        if (
            not get_information(
                handle,
                file_attribute_tag_info,
                ctypes.byref(information),
                ctypes.sizeof(information),
            )
            or information.file_attributes & file_attribute_reparse_point
        ):
            raise _error(error_code)
        descriptor = msvcrt.open_osfhandle(handle, binary_flags)
    except BaseException:
        kernel32.CloseHandle(handle)
        raise
    return descriptor


class PdbtmCacheRepository:
    """Filesystem repository implementing the frozen Stage 4B1 cache contract."""

    def __init__(
        self,
        cache_root: str | os.PathLike[str] | None = None,
        *,
        lock_timeout: float = _DEFAULT_LOCK_TIMEOUT,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] | None = None,
        failpoint: Failpoint | None = None,
    ) -> None:
        if lock_timeout <= 0:
            raise ValueError("lock_timeout must be positive")
        self._root = (
            select_cache_root()
            if cache_root is None
            else _validated_base_path(os.fspath(cache_root))
        )
        self._lock_timeout = lock_timeout
        self._monotonic = monotonic
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self._failpoint = failpoint

    @property
    def root(self) -> Path:
        return self._root

    def initialize(self) -> None:
        """Create or validate the fixed cache-v1 layout."""

        try:
            self._create_layout()
            with self._locked():
                format_path = self._root / "format.json"
                index_path = self._root / "index.json"
                if format_path.exists():
                    self._read_format()
                elif index_path.exists() or self._has_materialized_state():
                    raise _error(Stage4BErrorCode.CACHE_FORMAT_UNSUPPORTED)
                else:
                    envelope = make_format_envelope(FormatCore())
                    data = serialize_format_envelope(envelope)
                    if len(data) > _FORMAT_LIMIT:
                        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
                    self._atomic_write(format_path, data, "format")
                    try:
                        stored = self._read_regular(format_path, _FORMAT_LIMIT)
                        if (
                            stored != data
                            or parse_format_envelope(stored).format_id != envelope.format_id
                        ):
                            raise ValueError("format read-back did not match the written document")
                    except Exception as error:
                        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED) from error
                if index_path.exists():
                    self._read_index()
                elif self._has_materialized_state():
                    raise _error(Stage4BErrorCode.CACHE_CORRUPT)
                else:
                    self._write_index(IndexCore(0, {}))
        except Stage4BError:
            raise
        except OSError as error:
            raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED) from error

    def capture_record_generation(self, record_id: str) -> int:
        canonical = _record_id(record_id)
        self.initialize()
        with self._locked():
            index = self._read_index().index_core
            record = index.records.get(canonical)
            return 0 if record is None else record.generation

    def inspect(self) -> CacheInspection:
        self.initialize()
        with self._locked():
            index = self._read_index().index_core
            return CacheInspection(index.generation, MappingProxyType(dict(index.records)))

    def list_snapshots(self, record_id: str) -> tuple[str, ...]:
        canonical = _record_id(record_id)
        self.initialize()
        with self._locked():
            index = self._read_index().index_core
            record = index.records.get(canonical)
            if record is None:
                return ()
            for snapshot_id in record.snapshot_ids:
                self._copy_snapshot_locked(canonical, snapshot_id)
            return record.snapshot_ids

    def read_active(
        self,
        record_id: str,
        *,
        validator: SemanticValidator | None = None,
    ) -> CachedSnapshot:
        canonical = _record_id(record_id)
        self.initialize()
        with self._locked():
            index = self._read_index().index_core
            record = index.records.get(canonical)
            if record is None or record.active_snapshot_id is None:
                raise _error(Stage4BErrorCode.CACHE_MISS)
            generation = record.generation
            snapshot_id = record.active_snapshot_id
            copied = self._copy_snapshot_locked(canonical, snapshot_id)
        checked = self._semantic_check(copied, validator)
        # A clear or refresh during semantic validation must not make stale
        # bytes appear to be the currently active selection.
        with self._locked():
            current = self._read_index().index_core.records.get(canonical)
            if (
                current is None
                or current.generation != generation
                or current.active_snapshot_id != snapshot_id
            ):
                raise _error(Stage4BErrorCode.CACHE_CONFLICT)
        return checked

    def read_snapshot(
        self,
        record_id: str,
        snapshot_id: str,
        *,
        validator: SemanticValidator | None = None,
    ) -> CachedSnapshot:
        canonical = _record_id(record_id)
        if type(snapshot_id) is not str or _SHA256.fullmatch(snapshot_id) is None:
            raise _error(Stage4BErrorCode.CACHE_MISS)
        self.initialize()
        with self._locked():
            index = self._read_index().index_core
            record = index.records.get(canonical)
            if record is None or snapshot_id not in record.snapshot_ids:
                raise _error(Stage4BErrorCode.CACHE_MISS)
            generation = record.generation
            copied = self._copy_snapshot_locked(canonical, snapshot_id)
        checked = self._semantic_check(copied, validator)
        with self._locked():
            current = self._read_index().index_core.records.get(canonical)
            if (
                current is None
                or current.generation != generation
                or snapshot_id not in current.snapshot_ids
            ):
                raise _error(Stage4BErrorCode.CACHE_CONFLICT)
        return checked

    def commit_validated_pair(
        self,
        candidate: object,
        *,
        expected_record_generation: int,
    ) -> CachedSnapshot:
        if type(expected_record_generation) is not int or expected_record_generation < 0:
            raise ValueError("expected_record_generation must be a non-negative integer")
        snapshot, bodies = self._prepare_candidate(candidate)
        self._revalidate_before_commit(snapshot.snapshot_core, bodies)
        canonical = snapshot.snapshot_core.canonical_record_id
        self.initialize()
        try:
            with self._locked():
                index = self._read_index().index_core
                previous = index.records.get(canonical)
                actual_generation = 0 if previous is None else previous.generation
                if actual_generation != expected_record_generation:
                    raise _error(Stage4BErrorCode.CACHE_CONFLICT)
                for acquisition, body in zip(snapshot.snapshot_core.payloads, bodies, strict=True):
                    self._materialize_blob(acquisition.sha256, body)
                self._materialize_manifest(snapshot)
                snapshot_ids = tuple(
                    sorted(
                        set(() if previous is None else previous.snapshot_ids)
                        | {snapshot.snapshot_id}
                    )
                )
                new_generation = index.generation + 1
                records = dict(index.records)
                records[canonical] = IndexRecord(
                    generation=actual_generation + 1,
                    active_snapshot_id=snapshot.snapshot_id,
                    snapshot_ids=snapshot_ids,
                )
                self._write_index(IndexCore(new_generation, records))
        except Stage4BError:
            raise
        except (OSError, ValueError) as error:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED) from error
        return CachedSnapshot(snapshot.snapshot_id, snapshot.snapshot_core, bodies)

    def clear(self, record_id: str) -> int:
        """Clear one record while retaining its incremented tombstone generation."""

        canonical = _record_id(record_id)
        self.initialize()
        try:
            with self._locked():
                index = self._read_index().index_core
                previous = index.records.get(canonical)
                previous_generation = 0 if previous is None else previous.generation
                generation = index.generation + 1
                records = dict(index.records)
                records[canonical] = IndexRecord(previous_generation + 1, None, ())
                self._write_index(IndexCore(generation, records))
                return previous_generation + 1
        except Stage4BError:
            raise
        except OSError as error:
            raise _error(Stage4BErrorCode.CACHE_CLEAR_FAILED) from error

    def _prepare_candidate(self, candidate: object) -> tuple[SnapshotEnvelope, tuple[bytes, bytes]]:
        try:
            return self._prepare_candidate_checked(candidate)
        except Stage4BError:
            raise
        except Exception as error:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED) from error

    def _revalidate_before_commit(self, core: SnapshotCore, bodies: tuple[bytes, bytes]) -> None:
        """Independently re-derive identity from the exact raw bytes before commit.

        The candidate's self-reported ``provider_versions`` must never be
        trusted on its own: this repeats the scientific pair validator here,
        outside the cache lock, and rejects any candidate whose claimed
        version provenance disagrees with what the raw bytes actually contain.
        """

        from .pdbtm_provider import validate_pdbtm_pair

        try:
            _, versions, _ = validate_pdbtm_pair(core.canonical_record_id, *bodies)
        except Stage4BError as error:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED) from error
        except Exception as error:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED) from error
        if (
            versions.resource_version != core.provider_versions.resource_version
            or versions.software_version != core.provider_versions.software_version
        ):
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)

    def _prepare_candidate_checked(
        self, candidate: object
    ) -> tuple[SnapshotEnvelope, tuple[bytes, bytes]]:
        record_id = _record_id(getattr(candidate, "canonical_record_id", ""))
        raw_payloads = getattr(candidate, "payloads", None)
        if type(raw_payloads) is not tuple or len(raw_payloads) != 2:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)
        acquisitions: list[AcquisitionPayload] = []
        bodies: list[bytes] = []
        identities: list[PayloadIdentity] = []
        total_bytes = 0
        for expected_role, payload in zip(PAYLOAD_ROLES, raw_payloads, strict=True):
            role = getattr(payload, "role", None)
            body = getattr(payload, "body", None)
            evidence = getattr(payload, "evidence", payload)
            if role != expected_role or type(body) is not bytes:
                raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)
            if getattr(evidence, "tls_verified", False) is not True:
                raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)
            digest = hashlib.sha256(body).hexdigest()
            byte_size = len(body)
            if byte_size > _BLOB_LIMIT:
                raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)
            total_bytes += byte_size
            if (
                getattr(evidence, "sha256", digest) != digest
                or getattr(evidence, "byte_size", byte_size) != byte_size
            ):
                raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)
            headers = ResponseHeaders(
                ContentTypeEvidence(
                    getattr(evidence, "content_type"),
                    getattr(evidence, "charset"),
                ),
                getattr(evidence, "content_encoding", None),
                getattr(evidence, "etag", None),
                getattr(evidence, "last_modified", None),
            )
            acquisitions.append(
                AcquisitionPayload(
                    role=role,
                    sha256=digest,
                    byte_size=byte_size,
                    requested_url=getattr(evidence, "requested_url"),
                    final_url=getattr(evidence, "final_url"),
                    requested_at=getattr(evidence, "requested_at"),
                    completed_at=getattr(evidence, "completed_at"),
                    status=getattr(evidence, "status"),
                    headers=headers,
                )
            )
            identities.append(PayloadIdentity(role, digest, byte_size))
            bodies.append(body)
        if total_bytes > _PAIR_LIMIT:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)
        pair_id = compute_pair_id(PairCore(record_id, tuple(identities)))  # type: ignore[arg-type]
        versions = getattr(candidate, "provider_versions", None)
        validated_at = self._utc_now().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        core = SnapshotCore(
            canonical_record_id=record_id,
            pair_id=pair_id,
            payloads=tuple(acquisitions),  # type: ignore[arg-type]
            provider_versions=ProviderVersions(
                getattr(versions, "resource_version"),
                getattr(versions, "software_version"),
            ),
            validated_at=validated_at,
        )
        return make_snapshot_envelope(core), tuple(bodies)  # type: ignore[return-value]

    def _semantic_check(
        self,
        snapshot: CachedSnapshot,
        validator: SemanticValidator | None,
    ) -> CachedSnapshot:
        if validator is None:
            from .pdbtm_provider import validate_pdbtm_pair

            validator = validate_pdbtm_pair
        try:
            result = validator(snapshot.canonical_record_id, *snapshot.payloads)
        except Stage4BError as error:
            raise _error(Stage4BErrorCode.CACHE_CORRUPT) from error
        except Exception as error:
            raise _error(Stage4BErrorCode.CACHE_CORRUPT) from error
        return CachedSnapshot(
            snapshot.snapshot_id,
            snapshot.snapshot_core,
            snapshot.payloads,
            result,
        )

    def _create_layout(self) -> None:
        _reject_existing_parent_links(self._root.parent)
        if self._root.exists():
            _reject_link_or_special(self._root, directory=True)
        else:
            try:
                self._root.mkdir(parents=True, mode=0o700)
            except FileExistsError:
                _reject_link_or_special(self._root, directory=True)
        _reject_existing_parent_links(self._root)
        for relative in (
            ("locks",),
            ("blobs", "sha256"),
            ("records",),
            ("tmp",),
            ("quarantine",),
        ):
            current = self._root
            for component in relative:
                current = current / component
                if current.exists():
                    _reject_link_or_special(current, directory=True)
                else:
                    try:
                        current.mkdir(mode=0o700)
                    except FileExistsError:
                        _reject_link_or_special(current, directory=True)
        lock_path = self._root / "locks" / "cache.lock"
        if lock_path.exists():
            _reject_link_or_special(lock_path, directory=False)
        else:
            try:
                descriptor = os.open(
                    lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
                    0o600,
                )
            except FileExistsError:
                _reject_link_or_special(lock_path, directory=False)
                return
            try:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def _has_materialized_state(self) -> bool:
        for relative in (("records",), ("blobs", "sha256")):
            directory = self._root.joinpath(*relative)
            if any(directory.iterdir()):
                return True
        return False

    @contextmanager
    def _locked(self) -> Iterator[None]:
        lock_path = self._root / "locks" / "cache.lock"
        self._assert_cache_directory_chain(lock_path.parent)
        _reject_link_or_special(lock_path, directory=False)
        process_lock = _process_lock(lock_path)
        deadline = self._monotonic() + self._lock_timeout
        while not process_lock.acquire(blocking=False):
            if self._monotonic() >= deadline:
                raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
            time.sleep(0.01)
        stream: BinaryIO | None = None
        try:
            descriptor = _open_existing_regular(
                lock_path, os.O_RDWR, Stage4BErrorCode.CACHE_OPEN_FAILED
            )
            self._assert_cache_directory_chain(lock_path.parent)
            stream = os.fdopen(descriptor, "r+b", buffering=0)
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
            while True:
                try:
                    self._platform_lock(stream)
                    break
                except (BlockingIOError, OSError):
                    if self._monotonic() >= deadline:
                        raise _error(Stage4BErrorCode.CACHE_OPEN_FAILED)
                    time.sleep(0.01)
            try:
                yield
            finally:
                self._platform_unlock(stream)
        finally:
            if stream is not None:
                stream.close()
            process_lock.release()

    @staticmethod
    def _platform_lock(stream: BinaryIO) -> None:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _platform_unlock(stream: BinaryIO) -> None:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _read_format(self):
        try:
            return parse_format_envelope(
                self._read_regular(self._root / "format.json", _FORMAT_LIMIT)
            )
        except Exception as error:
            raise _error(Stage4BErrorCode.CACHE_FORMAT_UNSUPPORTED) from error

    def _read_index(self):
        try:
            return parse_index_envelope(self._read_regular(self._root / "index.json", _INDEX_LIMIT))
        except Stage4BError:
            raise
        except Exception as error:
            raise _error(Stage4BErrorCode.CACHE_CORRUPT) from error

    def _read_regular(self, path: Path, maximum: int) -> bytes:
        try:
            self._assert_cache_directory_chain(path.parent)
            details = _reject_link_or_special(path, directory=False)
        except Stage4BError as error:
            raise _error(Stage4BErrorCode.CACHE_CORRUPT) from error
        if details.st_size > maximum:
            raise _error(Stage4BErrorCode.CACHE_CORRUPT)
        try:
            descriptor = _open_existing_regular(path, os.O_RDONLY, Stage4BErrorCode.CACHE_CORRUPT)
            try:
                self._assert_cache_directory_chain(path.parent)
                opened = os.fstat(descriptor)
                opened_attributes = getattr(opened, "st_file_attributes", 0)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_size > maximum
                    or opened_attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                ):
                    raise _error(Stage4BErrorCode.CACHE_CORRUPT)
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > maximum:
                        raise _error(Stage4BErrorCode.CACHE_CORRUPT)
                return b"".join(chunks)
            finally:
                os.close(descriptor)
        except Stage4BError:
            raise
        except OSError as error:
            raise _error(Stage4BErrorCode.CACHE_CORRUPT) from error

    def _copy_snapshot_locked(self, record_id: str, snapshot_id: str) -> CachedSnapshot:
        manifest_path = self._root / "records" / record_id / "snapshots" / f"{snapshot_id}.json"
        try:
            envelope = parse_snapshot_envelope(self._read_regular(manifest_path, _MANIFEST_LIMIT))
        except Stage4BError:
            raise
        except Exception as error:
            raise _error(Stage4BErrorCode.CACHE_CORRUPT) from error
        if (
            envelope.snapshot_id != snapshot_id
            or envelope.snapshot_core.canonical_record_id != record_id
        ):
            raise _error(Stage4BErrorCode.CACHE_CORRUPT)
        bodies: list[bytes] = []
        for payload in envelope.snapshot_core.payloads:
            body = self._read_regular(self._blob_path(payload.sha256), _BLOB_LIMIT)
            if len(body) != payload.byte_size or hashlib.sha256(body).hexdigest() != payload.sha256:
                raise _error(Stage4BErrorCode.CACHE_CORRUPT)
            bodies.append(body)
        return CachedSnapshot(snapshot_id, envelope.snapshot_core, tuple(bodies))  # type: ignore[arg-type]

    def _blob_path(self, digest: str) -> Path:
        if _SHA256.fullmatch(digest) is None:
            raise _error(Stage4BErrorCode.CACHE_CORRUPT)
        return self._root / "blobs" / "sha256" / digest[:2] / digest

    def _materialize_blob(self, digest: str, body: bytes) -> None:
        if len(body) > _BLOB_LIMIT:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)
        path = self._blob_path(digest)
        self._ensure_cache_directory(path.parent)
        if path.exists():
            existing = self._read_regular(path, _BLOB_LIMIT)
            if len(existing) != len(body) or hashlib.sha256(existing).hexdigest() != digest:
                raise _error(Stage4BErrorCode.CACHE_CORRUPT)
            return
        self._atomic_write(path, body, "blob")
        stored = self._read_regular(path, _BLOB_LIMIT)
        if len(stored) != len(body) or hashlib.sha256(stored).hexdigest() != digest:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)

    def _materialize_manifest(self, snapshot: SnapshotEnvelope) -> None:
        data = serialize_snapshot_envelope(snapshot)
        if len(data) > _MANIFEST_LIMIT:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)
        directory = (
            self._root / "records" / snapshot.snapshot_core.canonical_record_id / "snapshots"
        )
        self._ensure_cache_directory(directory)
        path = directory / f"{snapshot.snapshot_id}.json"
        if path.exists():
            if self._read_regular(path, _MANIFEST_LIMIT) != data:
                raise _error(Stage4BErrorCode.CACHE_CORRUPT)
            return
        self._atomic_write(path, data, "manifest")
        try:
            stored = self._read_regular(path, _MANIFEST_LIMIT)
            if (
                stored != data
                or parse_snapshot_envelope(stored).snapshot_id != snapshot.snapshot_id
            ):
                raise ValueError("manifest read-back did not match the written document")
        except Exception as error:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED) from error

    def _write_index(self, core: IndexCore) -> None:
        envelope = make_index_envelope(core)
        data = serialize_index_envelope(envelope)
        if len(data) > _INDEX_LIMIT:
            raise _error(Stage4BErrorCode.CACHE_WRITE_FAILED)
        self._atomic_write(self._root / "index.json", data, "index")
        try:
            stored = self._read_regular(self._root / "index.json", _INDEX_LIMIT)
            if stored != data or parse_index_envelope(stored).index_id != envelope.index_id:
                raise ValueError("index read-back did not match the written document")
        except Exception as error:
            raise _error(Stage4BErrorCode.CACHE_DURABILITY_UNCERTAIN) from error

    def _atomic_write(self, destination: Path, data: bytes, kind: str) -> None:
        self._run_failpoint(f"before_{kind}_temp_write")
        temporary = self._root / "tmp" / f"{uuid4().hex}.part"
        descriptor = -1
        try:
            self._assert_cache_directory_chain(temporary.parent)
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
            descriptor = os.open(temporary, flags, 0o600)
            self._assert_cache_directory_chain(temporary.parent)
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("short cache write")
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            self._run_failpoint(f"before_{kind}_replace")
            self._assert_cache_directory_chain(destination.parent)
            os.replace(temporary, destination)
            self._assert_cache_directory_chain(destination.parent)
            try:
                self._run_failpoint(f"after_{kind}_replace")
                self._fsync_directory(destination.parent)
            except Exception as error:
                if kind == "index":
                    raise _error(Stage4BErrorCode.CACHE_DURABILITY_UNCERTAIN) from error
                raise
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _assert_cache_directory_chain(self, directory: Path) -> None:
        relative = directory.relative_to(self._root)
        current = self._root
        _reject_link_or_special(current, directory=True)
        for component in relative.parts:
            current = current / component
            _reject_link_or_special(current, directory=True)

    def _ensure_cache_directory(self, directory: Path) -> None:
        relative = directory.relative_to(self._root)
        current = self._root
        _reject_link_or_special(current, directory=True)
        for component in relative.parts:
            current = current / component
            if current.exists():
                _reject_link_or_special(current, directory=True)
            else:
                try:
                    current.mkdir(mode=0o700)
                except FileExistsError:
                    _reject_link_or_special(current, directory=True)

    def _run_failpoint(self, name: str) -> None:
        if self._failpoint is not None:
            self._failpoint(name)

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


# The shorter name is the primary public spelling used by orchestration.
CacheRepository = PdbtmCacheRepository
