from __future__ import annotations

import multiprocessing
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import pytest

from membrane_vqc.pdbtm_cache import CacheRepository
from membrane_vqc.pdbtm_errors import Stage4BError, Stage4BErrorCode


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows cache gate")


def _sanitize(text: str, tmp_path: Path) -> str:
    """Strip the local filesystem layout out of subprocess output before it

    is embedded in a pytest failure message.
    """

    return text.replace(str(tmp_path), "<tmp>")


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


def test_real_directory_junction_in_cache_chain_is_rejected(tmp_path: Path):
    """A blocking, non-mocked Windows CI gate.

    Monkeypatch-based reparse-point tests (above) prove the rejection logic in
    isolation, but they cannot catch a regression in the *detection* itself.
    This test shells out to create one real NTFS directory junction and drives
    the real (non-mocked) repository against it. If junction creation itself
    fails, this must fail loudly -- never fall back to a mocked signal, or the
    gate silently stops verifying anything.
    """

    repository = CacheRepository(tmp_path / "cache")
    repository.initialize()
    link = repository.root / "blobs"
    real = repository.root / "real-blobs"
    target = tmp_path / "junction-target"
    target.mkdir()
    link.rename(real)

    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail(
            "real directory-junction creation failed, so the Windows reparse-point "
            "rejection gate is UNVERIFIED (this is a hard failure, not a skip): "
            f"mklink exit={completed.returncode} "
            f"stdout={_sanitize(completed.stdout, tmp_path)!r} "
            f"stderr={_sanitize(completed.stderr, tmp_path)!r}"
        )
    try:
        attributes = link.lstat().st_file_attributes
        assert attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT, (
            "mklink reported success but the resulting path is not actually a "
            "reparse point; the gate below would prove nothing"
        )

        with pytest.raises(Stage4BError) as caught:
            repository.capture_record_generation("1pcr")
        assert caught.value.code is Stage4BErrorCode.CACHE_OPEN_FAILED, (
            "a real junction was created but the real (non-mocked) detector did "
            f"not reject it; got {caught.value.code!r}"
        )
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(link)], capture_output=True, check=False)
        shutil.rmtree(real, ignore_errors=True)


def test_windows_unc_and_device_roots_are_rejected():
    for path in (r"\\server\share\cache", r"\\?\C:\cache", r"\\.\device"):
        with pytest.raises(Stage4BError) as caught:
            CacheRepository(path)
        assert caught.value.code is Stage4BErrorCode.CACHE_OPEN_FAILED
