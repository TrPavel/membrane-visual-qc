"""Pure path and atomic-output safety helpers for Stage 5A batches."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import secrets
import stat


MAX_PATH_LENGTH = 512
# Small and explicit on purpose: a real, permanent failure (permission denied,
# a full/unwritable filesystem) must fail fast, not retry thousands of times
# the way CPython's own tempfile.mkstemp() can on Windows. A handful of
# attempts is only ever needed to dodge a genuine same-microsecond name
# collision against the cryptographically random basename below.
_TEMP_NAME_ATTEMPTS = 8
_URL = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    "clock$",
    *{f"com{number}" for number in range(1, 10)},
    *{f"lpt{number}" for number in range(1, 10)},
}


class BatchPathError(ValueError):
    """A user path violates the reviewed local-filesystem contract."""


def describe_filesystem_error(error: OSError) -> str:
    """Classify a low-level filesystem failure without repeating the raw OSError
    text, which on Windows embeds the absolute path -- this project never
    serializes local paths into user-facing or persisted text (see
    docs/stage5a_batch_review.md), and this keeps that guarantee for the
    OSError-to-BatchPathError/BatchContractError boundary too."""
    if isinstance(error, PermissionError):
        return "permission was denied"
    if isinstance(error, FileNotFoundError):
        return "a required path component does not exist"
    if isinstance(error, NotADirectoryError):
        return "a path component is not a directory"
    if isinstance(error, FileExistsError):
        return "the destination already exists"
    if getattr(error, "winerror", None) in (3, 206) or getattr(error, "errno", None) == 36:
        return "the path is too long"
    return "a filesystem error occurred"


def validate_relative_path(value: object, *, field: str) -> str:
    """Return one safe relative path using platform-independent Windows checks."""
    if type(value) is not str:
        raise BatchPathError(f"{field} must be a string")
    text = value.strip()
    if not text or len(text) > MAX_PATH_LENGTH or any(ord(char) < 32 for char in text):
        raise BatchPathError(f"{field} is empty, oversized, or contains control characters")
    if _URL.match(text):
        raise BatchPathError(f"{field} must not be a URL")
    windows = PureWindowsPath(text)
    posix = PurePosixPath(text.replace("\\", "/"))
    lowered = text.casefold()
    if (
        windows.is_absolute()
        or windows.drive
        or posix.is_absolute()
        or lowered.startswith(("\\\\", "//", "\\?\\", "\\.\\", "\\??\\"))
        or ":" in text
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise BatchPathError(f"{field} must be a safe relative path")
    for part in posix.parts:
        if part.endswith((".", " ")) or part.split(".", 1)[0].casefold() in _RESERVED:
            raise BatchPathError(f"{field} contains a reserved Windows component")
    return posix.as_posix()


def _reject_link_or_reparse(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse):
        raise BatchPathError("path contains a symbolic link or reparse point")


def _validate_local_root_syntax(path: str | Path, *, field: str) -> None:
    """Reject Windows-dangerous syntax before ``Path.absolute()`` can reinterpret it.

    In particular, on Windows ``C:name`` resolves relative to drive C's current directory. If the
    target happens to exist, checking only the resolved path incorrectly makes acceptance depend on
    ambient process state. Device names and trailing dots/spaces are likewise lexical component
    properties and must be checked before filesystem normalization.
    """
    windows = PureWindowsPath(str(path))
    raw = str(windows)
    if raw.startswith(("\\\\", "\\?\\", "\\.\\", "\\??\\")):
        raise BatchPathError(f"{field} must not be a UNC or device path")
    if windows.drive and not windows.root:
        raise BatchPathError(f"{field} must not be drive-relative")
    for part in windows.parts:
        if part == windows.anchor:
            continue
        if part.endswith((".", " ")) or part.split(".", 1)[0].casefold() in _RESERVED:
            raise BatchPathError(f"{field} contains a reserved Windows component")


def resolve_input_path(root: Path, relative: object, *, field: str) -> Path:
    """Resolve a safe regular file below an approved root without link components.

    A target that simply does not exist still raises plain ``FileNotFoundError``
    (not ``BatchPathError``): ``batch_result_browser._artifact()`` relies on
    that exact type to distinguish an ordinary "not present" output -- a normal
    runtime state it reports as availability ``MISSING`` -- from a genuinely
    broken or unsafe root/path, which becomes ``BatchPathError`` here and
    ``OUTPUT_PATH_UNSAFE`` there. Only the *root* itself failing to resolve
    (missing, permission-denied, path-too-long, ...) is a precondition
    violation and is always typed.
    """
    safe = validate_relative_path(relative, field=field)
    try:
        approved = root.resolve(strict=True)
        _reject_link_or_reparse(approved)
    except OSError as error:
        raise BatchPathError(
            f"{field} root could not be resolved ({describe_filesystem_error(error)})"
        ) from error
    candidate = approved.joinpath(*PurePosixPath(safe).parts)
    cursor = approved
    try:
        for part in PurePosixPath(safe).parts:
            cursor = cursor / part
            _reject_link_or_reparse(cursor)
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise BatchPathError(
            f"{field} could not be resolved ({describe_filesystem_error(error)})"
        ) from error
    if not resolved.is_relative_to(approved) or not resolved.is_file():
        raise BatchPathError(f"{field} must resolve to a regular file inside the input root")
    return resolved


def resolve_input_directory(root: Path, relative: object, *, field: str) -> Path:
    """Resolve an existing link-free directory below an approved root.

    Mirrors resolve_input_path's FileNotFoundError-vs-BatchPathError split for
    the same reason: a caller may want to distinguish an ordinary missing
    target from a genuinely broken root.
    """
    safe = validate_relative_path(relative, field=field)
    try:
        approved = root.resolve(strict=True)
    except OSError as error:
        raise BatchPathError(
            f"{field} root could not be resolved ({describe_filesystem_error(error)})"
        ) from error
    candidate = approved.joinpath(*PurePosixPath(safe).parts)
    cursor = approved
    try:
        for part in PurePosixPath(safe).parts:
            cursor = cursor / part
            _reject_link_or_reparse(cursor)
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise BatchPathError(
            f"{field} could not be resolved ({describe_filesystem_error(error)})"
        ) from error
    if not resolved.is_relative_to(approved) or not resolved.is_dir():
        raise BatchPathError(f"{field} must resolve to a directory inside the input root")
    return resolved


def resolve_existing_root(path: str | Path) -> Path:
    """Resolve one existing local directory without following link/reparse components."""
    _validate_local_root_syntax(path, field="local root")
    lexical = Path(path).absolute()
    if ".." in lexical.parts:
        raise BatchPathError("local root must not contain traversal components")
    try:
        cursor = Path(lexical.anchor) if lexical.anchor else Path()
        parts = lexical.parts[1:] if lexical.anchor else lexical.parts
        for part in parts:
            cursor = cursor / part
            _reject_link_or_reparse(cursor)
        resolved = lexical.resolve(strict=True)
    except OSError as error:
        raise BatchPathError(
            f"local root could not be resolved ({describe_filesystem_error(error)})"
        ) from error
    if resolved != lexical or not resolved.is_dir():
        raise BatchPathError("local root must be an existing link-free directory")
    return resolved


def prepare_output_root(path: str | Path) -> Path:
    """Create or validate one explicit output directory with no link components."""
    root = Path(path)
    _validate_local_root_syntax(path, field="output root")
    lexical = root.absolute()
    if ".." in lexical.parts:
        raise BatchPathError("output root must not contain traversal components")
    try:
        cursor = Path(lexical.anchor) if lexical.anchor else Path()
        parts = lexical.parts[1:] if lexical.anchor else lexical.parts
        for part in parts:
            cursor = cursor / part
            if cursor.exists():
                _reject_link_or_reparse(cursor)
            else:
                cursor.mkdir()
                _reject_link_or_reparse(cursor)
        resolved = lexical.resolve(strict=True)
        if resolved != lexical:
            raise BatchPathError("output root must not traverse a symbolic link or reparse point")
        cursor = Path(lexical.anchor) if lexical.anchor else Path()
        for part in parts:
            cursor = cursor / part
            _reject_link_or_reparse(cursor)
        if not resolved.is_dir():
            raise BatchPathError("output root must be a directory")
    except OSError as error:
        raise BatchPathError(
            f"output root could not be prepared ({describe_filesystem_error(error)})"
        ) from error
    return resolved


def safe_output_name(job_id: str, suffix: str) -> str:
    """Derive a deterministic single-component output name from a validated job ID."""
    name = f"{job_id}{suffix}"
    validate_relative_path(name, field="output name")
    if "/" in name or "\\" in name:
        raise BatchPathError("output name must contain exactly one component")
    return name


def _open_exclusive(path: Path) -> int:
    """Thin, monkeypatchable wrapper around exclusive-create file opening."""
    return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)


def _create_unique_temp_file(directory: Path, stem: str) -> tuple[int, Path]:
    """Create a new file exclusively inside `directory` using a small, explicitly
    bounded number of attempts with a securely random basename.

    Deliberately not tempfile.mkstemp(): CPython's own implementation can retry
    its name-collision loop thousands of times on Windows when the destination
    genuinely denies file creation (a PermissionError can look, to that retry
    loop, indistinguishable from a transient name collision), blocking for a
    long time instead of failing fast. A collision against this function's
    16-byte cryptographically random suffix is astronomically unlikely; the
    bound exists to fail deterministically rather than loop unboundedly, not
    because collisions are expected in practice.
    """
    last_error: OSError | None = None
    for _ in range(_TEMP_NAME_ATTEMPTS):
        candidate = directory / f".{stem}.{secrets.token_hex(16)}.tmp"
        try:
            return _open_exclusive(candidate), candidate
        except FileExistsError as error:
            last_error = error
            continue
        except OSError as error:
            raise BatchPathError(
                f"temporary output file could not be created ({describe_filesystem_error(error)})"
            ) from error
    raise BatchPathError(
        f"temporary output file could not be created after "
        f"{_TEMP_NAME_ATTEMPTS} attempts ({describe_filesystem_error(last_error)})"
    ) from last_error


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically publish bytes beside their destination without following the target."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise BatchPathError(
            f"output directory could not be prepared ({describe_filesystem_error(error)})"
        ) from error
    descriptor, temporary = _create_unique_temp_file(path.parent, path.name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        # The handle (and underlying descriptor) is closed by the `with` block
        # above before this replace -- required on Windows, where a rename over
        # an open file handle fails.
        os.replace(temporary, path)
    except OSError as error:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise BatchPathError(
            f"output could not be published ({describe_filesystem_error(error)})"
        ) from error
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
