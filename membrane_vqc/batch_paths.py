"""Pure path and atomic-output safety helpers for Stage 5A batches."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import tempfile


MAX_PATH_LENGTH = 512
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


def resolve_input_path(root: Path, relative: object, *, field: str) -> Path:
    """Resolve a safe regular file below an approved root without link components."""
    safe = validate_relative_path(relative, field=field)
    approved = root.resolve(strict=True)
    _reject_link_or_reparse(approved)
    candidate = approved.joinpath(*PurePosixPath(safe).parts)
    cursor = approved
    for part in PurePosixPath(safe).parts:
        cursor = cursor / part
        _reject_link_or_reparse(cursor)
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(approved) or not resolved.is_file():
        raise BatchPathError(f"{field} must resolve to a regular file inside the input root")
    return resolved


def resolve_input_directory(root: Path, relative: object, *, field: str) -> Path:
    """Resolve an existing link-free directory below an approved root."""
    safe = validate_relative_path(relative, field=field)
    approved = root.resolve(strict=True)
    candidate = approved.joinpath(*PurePosixPath(safe).parts)
    cursor = approved
    for part in PurePosixPath(safe).parts:
        cursor = cursor / part
        _reject_link_or_reparse(cursor)
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(approved) or not resolved.is_dir():
        raise BatchPathError(f"{field} must resolve to a directory inside the input root")
    return resolved


def resolve_existing_root(path: str | Path) -> Path:
    """Resolve one existing local directory without following link/reparse components."""
    lexical = Path(path).absolute()
    windows_text = str(PureWindowsPath(lexical))
    if windows_text.startswith(("\\\\", "\\?\\", "\\.\\", "\\??\\")):
        raise BatchPathError("local root must not be a UNC or device path")
    if ".." in lexical.parts:
        raise BatchPathError("local root must not contain traversal components")
    cursor = Path(lexical.anchor) if lexical.anchor else Path()
    parts = lexical.parts[1:] if lexical.anchor else lexical.parts
    for part in parts:
        cursor = cursor / part
        _reject_link_or_reparse(cursor)
    resolved = lexical.resolve(strict=True)
    if resolved != lexical or not resolved.is_dir():
        raise BatchPathError("local root must be an existing link-free directory")
    return resolved


def prepare_output_root(path: str | Path) -> Path:
    """Create or validate one explicit output directory with no link components."""
    root = Path(path)
    lexical = root.absolute()
    windows_text = str(PureWindowsPath(lexical))
    if windows_text.startswith(("\\\\", "\\?\\", "\\.\\", "\\??\\")):
        raise BatchPathError("output root must not be a UNC or device path")
    if ".." in lexical.parts:
        raise BatchPathError("output root must not contain traversal components")
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
    return resolved


def safe_output_name(job_id: str, suffix: str) -> str:
    """Derive a deterministic single-component output name from a validated job ID."""
    name = f"{job_id}{suffix}"
    validate_relative_path(name, field="output name")
    if "/" in name or "\\" in name:
        raise BatchPathError("output name must contain exactly one component")
    return name


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically publish bytes beside their destination without following the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
