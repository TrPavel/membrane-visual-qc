"""Windows path and filesystem-edge-case regression coverage for membrane_vqc.batch_paths.

Two kinds of coverage live here:
- "already correct" behavior (spaces, Unicode, read-only files, traversal/UNC/
  device/symlink/reparse rejection) that had no dedicated test module before
  this file, found during a read-only v0.7.0 hardening audit;
- the four confirmed bugs fixed alongside this file: raw OSError/PermissionError/
  FileNotFoundError leaking out of resolve_existing_root/resolve_input_path/
  prepare_output_root, and atomic_write_bytes() hanging in CPython's Windows
  tempfile.mkstemp() retry loop against a genuinely permission-denied directory.

None of the OS-denial tests touch real ACLs (no icacls) -- they monkeypatch the
narrow, purpose-built seams (`Path.mkdir`, `_open_exclusive`) so they run
identically on any machine/CI runner. Unicode assertions never print/repr a
Unicode-bearing Path to the console: an early version of the manual audit this
file is based on nearly misdiagnosed a real bug from a Windows console
encoding limitation (cp1252 can't display Cyrillic/CJK) rather than an actual
library failure -- these tests assert on returned values and file contents
only, never on printed representations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from membrane_vqc.batch_cli import main as batch_cli_main
from membrane_vqc.batch_contracts import BatchContractError, load_plan
from membrane_vqc.batch_paths import (
    BatchPathError,
    _TEMP_NAME_ATTEMPTS,
    _create_unique_temp_file,
    atomic_write_bytes,
    describe_filesystem_error,
    prepare_output_root,
    resolve_existing_root,
    resolve_input_path,
    validate_relative_path,
)


ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# 1-12: already-correct behavior, newly locked in by regression tests
# ---------------------------------------------------------------------------


def test_space_containing_paths_resolve_correctly(tmp_path):
    root = tmp_path / "has spaces here"
    root.mkdir()
    (root / "input file.pdb").write_text("ATOM\n")

    assert resolve_existing_root(root) == root.resolve()
    resolved = resolve_input_path(root, "input file.pdb", field="input")
    assert resolved.name == "input file.pdb"
    out = prepare_output_root(root / "out dir")
    assert out.name == "out dir"


def test_unicode_cyrillic_cjk_paths_resolve_correctly(tmp_path):
    """Assert on values and content only -- never repr()/print() the Unicode path
    itself, which can raise UnicodeEncodeError on a non-UTF-8 Windows console
    and would misrepresent a console limitation as a library bug."""
    root = (
        tmp_path
        / "\u041f\u0440\u0438\u043c\u0435\u0440_\u00fcn\u00efc\u00f6d\u00e9_\u65e5\u672c\u8a9e"
    )
    root.mkdir()
    filename = "\u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0430.pdb"
    (root / filename).write_bytes(b"ATOM\n")

    resolved_root = resolve_existing_root(root)
    assert resolved_root.is_dir()
    resolved_file = resolve_input_path(root, filename, field="input")
    assert resolved_file.is_file()
    assert resolved_file.read_bytes() == b"ATOM\n"
    out = prepare_output_root(root / "\u0432\u044b\u0445\u043e\u0434")
    assert out.is_dir()


def test_readonly_input_file_remains_readable(tmp_path):
    root = tmp_path / "ro_input"
    root.mkdir()
    target = root / "readonly.pdb"
    target.write_text("ATOM\n")
    target.chmod(stat.S_IREAD)
    try:
        resolved = resolve_input_path(root, "readonly.pdb", field="input")
        assert resolved.read_text() == "ATOM\n"
    finally:
        target.chmod(stat.S_IWRITE | stat.S_IREAD)


def test_nested_relative_paths_resolve_relative_to_root(tmp_path):
    root = tmp_path / "rel_test"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "x.json").write_text("{}")

    resolved = resolve_input_path(root, "sub/x.json", field="input")
    assert resolved == (root / "sub" / "x.json").resolve()


def test_backslash_separated_relative_path_is_normalized():
    assert validate_relative_path("sub\\x.json", field="input") == "sub/x.json"


@pytest.mark.parametrize(
    "path",
    [
        "C:\\evil.json",
        "C:evil_no_slash.json",
    ],
)
def test_drive_letter_and_drive_relative_paths_are_rejected(path):
    with pytest.raises(BatchPathError, match="safe relative path"):
        validate_relative_path(path, field="input")


@pytest.mark.skipif(os.name != "nt", reason="drive-relative syntax is Windows-only")
def test_drive_relative_output_root_argument_is_rejected(tmp_path):
    """Distinct from the drive-relative *relative-path-string* case above: here
    a drive-relative value is given directly as prepare_output_root's own root
    argument, exercising PureWindowsPath/.absolute() resolution instead of
    validate_relative_path. Still fails closed. Windows-only: "C:foo" has no
    drive-relative meaning on POSIX, where it is just an ordinary (and
    perfectly safe) relative filename containing a colon."""
    with pytest.raises(BatchPathError):
        prepare_output_root("C:not_a_real_drive_relative_target_xyz")


@pytest.mark.parametrize("component", ["con", "NUL.txt", "folder.", "folder "])
def test_direct_output_root_rejects_windows_reserved_components(tmp_path, component):
    with pytest.raises(BatchPathError, match="reserved Windows component"):
        prepare_output_root(tmp_path / component)


@pytest.mark.parametrize("path", [r"\\server\share\x", r"\\?\C:\a.pdb", r"\\.\pipe\name"])
def test_unc_device_and_pipe_paths_are_rejected(path):
    with pytest.raises(BatchPathError):
        validate_relative_path(path, field="input")
    with pytest.raises(BatchPathError):
        resolve_existing_root(path)


def test_traversal_dotdot_is_rejected(tmp_path):
    root = tmp_path / "rel_test2"
    root.mkdir()
    with pytest.raises(BatchPathError, match="safe relative path"):
        resolve_input_path(root, "../escape.json", field="input")
    with pytest.raises(BatchPathError, match="safe relative path"):
        resolve_input_path(root, "C:/Windows/win.ini", field="input")


def test_symlink_reparse_protection_unchanged_for_resolve_input_path(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    (root / "linked.pdb").write_text("ATOM\n")
    target = (root / "linked.pdb").resolve()
    original = Path.lstat

    def fake_lstat(path):
        if path.resolve() == target:
            return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        return original(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(BatchPathError, match="reparse"):
        resolve_input_path(root, "linked.pdb", field="input")


def test_existing_output_with_overwrite_refuse_still_protected(tmp_path):
    """batch_runner.py's OUTPUT_COLLISION policy is unchanged by this PR (that
    logic lives in batch_runner.py, not batch_paths.py); this only confirms the
    prepare_output_root() this policy is built on top of still behaves
    correctly for an already-existing, writable output directory."""
    root = prepare_output_root(tmp_path / "out")
    (root / "existing.json").write_text("{}")

    again = prepare_output_root(root)
    assert again == root
    assert (root / "existing.json").read_text() == "{}"


# ---------------------------------------------------------------------------
# 13-23: the four confirmed bugs, fixed
# ---------------------------------------------------------------------------


def test_missing_root_becomes_batch_path_error(tmp_path):
    missing = tmp_path / "does" / "not" / "exist"
    with pytest.raises(BatchPathError, match="local root could not be resolved"):
        resolve_existing_root(missing)


def test_missing_input_root_becomes_batch_path_error(tmp_path):
    missing = tmp_path / "also-missing"
    with pytest.raises(BatchPathError, match="root could not be resolved"):
        resolve_input_path(missing, "x.pdb", field="input")


def test_missing_input_file_within_existing_root_stays_plain_filenotfounderror(tmp_path):
    """Deliberately NOT BatchPathError: membrane_vqc.batch_result_browser._artifact()
    catches FileNotFoundError specifically to report an ordinary missing output as
    availability MISSING, distinct from BatchPathError -> OUTPUT_PATH_UNSAFE for a
    genuinely broken/unsafe path. Wrapping this case would silently turn every
    missing-output report into a false "unsafe path" -- confirmed by an actual
    regression while implementing this fix, caught by
    tests/test_batch_result_browser.py::test_missing_output_is_reported_unavailable_without_deletion."""
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(FileNotFoundError):
        resolve_input_path(root, "nope.pdb", field="input")


def test_output_parent_creation_under_os_denial_becomes_batch_path_error(tmp_path, monkeypatch):
    target = tmp_path / "denied" / "child"
    original_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if self == target.parent:
            raise PermissionError(13, "Access is denied")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir)
    with pytest.raises(BatchPathError, match="permission was denied"):
        prepare_output_root(target)


def test_path_too_long_mkdir_failure_becomes_batch_path_error(tmp_path, monkeypatch):
    target = tmp_path / "toolong" / "child"
    original_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if self == target.parent:
            error = OSError("The filename or extension is too long")
            error.winerror = 206
            raise error
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir)
    with pytest.raises(BatchPathError, match="path is too long"):
        prepare_output_root(target)


def test_atomic_write_permission_denial_fails_promptly(tmp_path, monkeypatch):
    calls = []

    def fake_open_exclusive(path):
        calls.append(path)
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr("membrane_vqc.batch_paths._open_exclusive", fake_open_exclusive)
    with pytest.raises(BatchPathError, match="permission was denied"):
        atomic_write_bytes(tmp_path / "out.json", b"{}")
    # A genuine permission denial is never retried as if it were a name
    # collision -- exactly one attempt, not the bounded-collision-retry count.
    assert len(calls) == 1


def test_atomic_write_failure_leaves_no_temporary_or_destination_file(tmp_path, monkeypatch):
    destination = tmp_path / "out.json"

    def fake_open_exclusive(path):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr("membrane_vqc.batch_paths._open_exclusive", fake_open_exclusive)
    with pytest.raises(BatchPathError):
        atomic_write_bytes(destination, b"{}")

    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def test_temp_file_collision_is_retried_up_to_the_explicit_bound(tmp_path):
    import membrane_vqc.batch_paths as batch_paths_module

    attempts = {"count": 0}
    real_open_exclusive = batch_paths_module._open_exclusive

    def flaky_open_exclusive(path):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise FileExistsError(17, "File exists")
        return real_open_exclusive(path)

    original = batch_paths_module._open_exclusive
    batch_paths_module._open_exclusive = flaky_open_exclusive
    try:
        descriptor, temp_path = _create_unique_temp_file(tmp_path, "out.json")
        import os

        os.close(descriptor)
        temp_path.unlink()
    finally:
        batch_paths_module._open_exclusive = original

    assert attempts["count"] == 3
    assert attempts["count"] <= _TEMP_NAME_ATTEMPTS


def test_temp_file_collision_exhausting_the_bound_raises_typed_error(tmp_path, monkeypatch):
    calls = []

    def always_collides(path):
        calls.append(path)
        raise FileExistsError(17, "File exists")

    monkeypatch.setattr("membrane_vqc.batch_paths._open_exclusive", always_collides)
    with pytest.raises(BatchPathError, match="after"):
        _create_unique_temp_file(tmp_path, "out.json")
    assert len(calls) == _TEMP_NAME_ATTEMPTS


def test_successful_atomic_write_is_byte_correct(tmp_path):
    destination = tmp_path / "out.json"
    payload = json.dumps({"a": 1, "b": [1, 2, 3]}).encode("utf-8")

    atomic_write_bytes(destination, payload)

    assert destination.read_bytes() == payload
    # No leftover temporary file beside the published destination.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.json"]


def test_atomic_write_replacement_is_atomic_no_stray_temp_files(tmp_path):
    destination = tmp_path / "out.json"
    atomic_write_bytes(destination, b"{}")
    atomic_write_bytes(destination, b'{"updated": true}')

    assert destination.read_bytes() == b'{"updated": true}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.json"]


def test_describe_filesystem_error_never_embeds_raw_os_path_text(tmp_path):
    """The classification helper must not repeat OSError's own formatted text,
    which on Windows includes the absolute path -- matching this project's
    convention of never serializing local paths into user-facing text."""
    sensitive = tmp_path / "C-users-charm-should-not-appear"
    error = PermissionError(13, "Access is denied", str(sensitive))
    description = describe_filesystem_error(error)
    assert str(sensitive) not in description
    assert description == "permission was denied"


# ---------------------------------------------------------------------------
# 24-26: CLI boundary
# ---------------------------------------------------------------------------


def _run_cli(argv, capsys):
    exit_code = batch_cli_main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def test_cli_missing_plan_invocation_fails_cleanly(tmp_path, capsys):
    missing = tmp_path / "missing-plan.json"
    exit_code, out, err = _run_cli(["validate", str(missing)], capsys)

    assert exit_code == 1
    assert out == ""
    assert "Traceback" not in err
    assert str(missing) in err


def test_cli_malformed_plan_invocation_fails_cleanly(tmp_path, capsys):
    bad = tmp_path / "bad-plan.json"
    bad.write_bytes(b"not json at all")
    exit_code, out, err = _run_cli(["validate", str(bad)], capsys)

    assert exit_code == 1
    assert out == ""
    assert "Traceback" not in err
    # The underlying load_plan() wording is preserved unchanged.
    with pytest.raises(BatchContractError, match="strict UTF-8 JSON"):
        load_plan(bad)


def test_cli_valid_plan_invocation_still_succeeds(capsys):
    plan_path = ROOT / "data" / "synthetic" / "stage5a_batch_plan.json"
    exit_code, out, err = _run_cli(["validate", str(plan_path)], capsys)

    assert exit_code == 0
    assert err == ""
    payload = json.loads(out)
    assert payload["valid"] is True
    assert payload["jobs"] == 5


def test_cli_never_crashes_with_a_traceback_for_expected_errors(tmp_path):
    """Direct proof (not just captured stderr text) that main() itself returns
    a clean exit code for an expected error rather than letting an exception
    propagate out of it -- calling main() directly, not via subprocess, so an
    uncaught exception would fail this test with a real traceback."""
    missing = tmp_path / "definitely-missing.json"
    assert batch_cli_main(["validate", str(missing)]) == 1
