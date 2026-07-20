from __future__ import annotations

import multiprocessing
from pathlib import Path
import sys

import pytest

from membrane_vqc.pdbtm_cache import CacheRepository
from membrane_vqc.pdbtm_errors import Stage4BError, Stage4BErrorCode


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows cache gate")


def _hold_windows_lock(lock_path: str, ready, release) -> None:
    import msvcrt

    with open(lock_path, "r+b", buffering=0) as stream:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        ready.send(True)
        release.recv()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def test_windows_lock_is_exclusive_across_spawned_processes(tmp_path: Path):
    repository = CacheRepository(tmp_path / "cache", lock_timeout=0.1)
    repository.initialize()
    context = multiprocessing.get_context("spawn")
    parent_ready, child_ready = context.Pipe()
    parent_release, child_release = context.Pipe()
    process = context.Process(
        target=_hold_windows_lock,
        args=(str(repository.root / "locks" / "cache.lock"), child_ready, child_release),
    )
    process.start()
    assert parent_ready.recv() is True
    try:
        with pytest.raises(Stage4BError) as caught:
            repository.inspect()
        assert caught.value.code is Stage4BErrorCode.CACHE_OPEN_FAILED
    finally:
        parent_release.send(True)
        process.join(5)
    assert process.exitcode == 0


def test_windows_reparse_flag_is_rejected(monkeypatch, tmp_path: Path):
    repository = CacheRepository(tmp_path / "cache")
    repository.initialize()
    monkeypatch.setattr("membrane_vqc.pdbtm_cache._is_reparse_point", lambda path: True)

    with pytest.raises(Stage4BError) as caught:
        repository.inspect()
    assert caught.value.code is Stage4BErrorCode.CACHE_OPEN_FAILED


def test_windows_unc_and_device_roots_are_rejected():
    for path in (r"\\server\share\cache", r"\\?\C:\cache", r"\\.\device"):
        with pytest.raises(Stage4BError) as caught:
            CacheRepository(path)
        assert caught.value.code is Stage4BErrorCode.CACHE_OPEN_FAILED
