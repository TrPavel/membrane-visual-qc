#!/usr/bin/env python3
"""Build and validate a deterministic PyMOL Plugin Manager ZIP archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable


PACKAGE_NAME = "membrane_vqc"
MANIFEST_NAME = f"{PACKAGE_NAME}/PLUGIN_MANIFEST.json"
CHECKSUMS_NAME = f"{PACKAGE_NAME}/SHA256SUMS.txt"
SCHEMA_VERSIONS = ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5")
SCHEMA_NAMES = {
    version: f"{PACKAGE_NAME}/schemas/mvqc-report-{version}.schema.json"
    for version in SCHEMA_VERSIONS
}
# Backwards-compatible name retained for callers that refer to the Stage 4C schema directly.
STAGE4C_SCHEMA_NAME = SCHEMA_NAMES["1.5"]
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
# JSON enters only through the explicit released-schema list below. This keeps
# arbitrary provider JSON bodies out of the runtime package by construction.
ALLOWED_SUFFIXES = {".py", ".txt", ".md", ".png", ".svg"}
REQUIRED_PACKAGE_FILES = {
    f"{PACKAGE_NAME}/__init__.py",
    f"{PACKAGE_NAME}/commands.py",
    f"{PACKAGE_NAME}/constants.py",
    f"{PACKAGE_NAME}/gui.py",
    f"{PACKAGE_NAME}/pdbtm_cache.py",
    f"{PACKAGE_NAME}/pdbtm_cache_contract.py",
    f"{PACKAGE_NAME}/pdbtm_errors.py",
    f"{PACKAGE_NAME}/pdbtm_provider.py",
    f"{PACKAGE_NAME}/pdbtm_retrieval.py",
    f"{PACKAGE_NAME}/pdbtm_transport.py",
    f"{PACKAGE_NAME}/opm_adapter.py",
    f"{PACKAGE_NAME}/orientation_comparison.py",
    f"{PACKAGE_NAME}/comparison_report.py",
    f"{PACKAGE_NAME}/comparison_worker.py",
    f"{PACKAGE_NAME}/comparison_gui_worker.py",
    f"{PACKAGE_NAME}/comparison_pymol.py",
    *SCHEMA_NAMES.values(),
}
FORBIDDEN_PROVIDER_PAYLOADS = {
    (283_537, "38b2f724c4271a00bf2b83aa16015783610178f18d8954a88cb932b9152f36e0"),
    (628_434, "7e52525ff397e4bfa5900e602f39753628e3b1408d513a3d0d76928c0fd10698"),
    (425_370, "22b3985dc13b14520b5507b3ec022211d4c281bdf30f2cdef057073305294f62"),
    (823_920, "f228413887e409312fba5ce76108836856fef62815b1bd8e4ffd97beb01f0b54"),
    (801_495, "5805025619dafa256cb5508021f3406bb97cd84b4366cf62c98f1b46f5ea5561"),
}


class PluginZipError(ValueError):
    """Raised when a plugin source tree or built ZIP has an invalid layout."""


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 hex digest for *data*."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reject_official_provider_payload(name: str, data: bytes) -> None:
    """Prevent accepted live-provider bodies from entering a public artifact."""

    identity = (len(data), sha256_bytes(data))
    if identity in FORBIDDEN_PROVIDER_PAYLOADS:
        raise PluginZipError(f"Official provider payload is forbidden in artifacts: {name}")


def project_version(project_root: Path) -> str:
    """Read the static project version without importing the plugin package."""
    text = (project_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']\s*$', text, re.MULTILINE)
    if not match:
        raise PluginZipError("Could not find [project] version in pyproject.toml")
    return match.group(1)


def collect_plugin_files(project_root: Path) -> list[tuple[str, Path]]:
    """Collect the allow-listed runtime files in stable archive-name order."""
    package_root = project_root / PACKAGE_NAME
    if not package_root.is_dir():
        raise PluginZipError(f"Missing plugin package directory: {package_root}")

    files: list[tuple[str, Path]] = []
    for path in package_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(project_root)
        archive_name = PurePosixPath(*relative.parts).as_posix()
        if (
            "__pycache__" in relative.parts
            or path.suffix.lower() not in ALLOWED_SUFFIXES
            or archive_name in {MANIFEST_NAME, CHECKSUMS_NAME}
        ):
            continue
        files.append((archive_name, path))

    for version, archive_name in SCHEMA_NAMES.items():
        schema_path = project_root / "schemas" / f"mvqc-report-{version}.schema.json"
        if not schema_path.is_file() or schema_path.is_symlink():
            raise PluginZipError(f"Missing report schema {version}: {schema_path}")
        files.append((archive_name, schema_path))

    names = {name for name, _ in files}
    missing = REQUIRED_PACKAGE_FILES - names
    if missing:
        raise PluginZipError(f"Missing required plugin files: {', '.join(sorted(missing))}")
    return sorted(files, key=lambda item: item[0])


def _manifest_bytes(version: str, files: Iterable[tuple[str, bytes]]) -> bytes:
    entries = [
        {"path": name, "sha256": sha256_bytes(data), "size": len(data)} for name, data in files
    ]
    manifest = {
        "format_version": 1,
        "plugin": {"name": "Membrane Visual QC", "package": PACKAGE_NAME, "version": version},
        "files": entries,
    }
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _checksums_bytes(files: Iterable[tuple[str, bytes]]) -> bytes:
    return "".join(f"{sha256_bytes(data)}  {name}\n" for name, data in files).encode("ascii")


def _write_zip_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def validate_zip_layout(zip_path: Path) -> dict[str, object]:
    """Validate a single-directory PyMOL plugin ZIP and its integrity metadata."""
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise PluginZipError("ZIP contains duplicate entries")
        if names != sorted(names):
            raise PluginZipError("ZIP entries are not sorted deterministically")
        if MANIFEST_NAME not in names or CHECKSUMS_NAME not in names:
            raise PluginZipError("ZIP must contain its plugin manifest and file checksums")

        for info in infos:
            path = PurePosixPath(info.filename)
            if info.is_dir() or path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                raise PluginZipError(f"Unsafe or unexpected ZIP entry: {info.filename}")
            mode_type = stat.S_IFMT(info.external_attr >> 16)
            if mode_type not in (0, stat.S_IFREG):
                raise PluginZipError(f"ZIP entry is not a regular file: {info.filename}")
            is_package_file = path.parts[0] == PACKAGE_NAME and len(path.parts) > 1
            if not is_package_file:
                raise PluginZipError(f"Unexpected top-level ZIP entry: {info.filename}")
            if path.parts[0] == PACKAGE_NAME and (
                "__pycache__" in path.parts or path.suffix == ".pyc"
            ):
                raise PluginZipError(f"Development cache included in ZIP: {info.filename}")

        try:
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise PluginZipError("Plugin manifest is not valid UTF-8 JSON") from error

        if manifest.get("format_version") != 1:
            raise PluginZipError("Unsupported plugin manifest format_version")
        manifest_files = manifest.get("files")
        if not isinstance(manifest_files, list):
            raise PluginZipError("Plugin manifest files must be a list")
        expected_names = [entry.get("path") for entry in manifest_files]
        package_names = [name for name in names if name not in {MANIFEST_NAME, CHECKSUMS_NAME}]
        if expected_names != package_names:
            raise PluginZipError("Manifest file list does not match ZIP package entries")

        checked_data: list[tuple[str, bytes]] = []
        for entry in manifest_files:
            name = entry["path"]
            data = archive.read(name)
            reject_official_provider_payload(name, data)
            if entry.get("sha256") != sha256_bytes(data) or entry.get("size") != len(data):
                raise PluginZipError(f"Manifest hash or size mismatch: {name}")
            checked_data.append((name, data))

        manifest_data = archive.read(MANIFEST_NAME)
        expected_checksums = _checksums_bytes([*checked_data, (MANIFEST_NAME, manifest_data)])
        if archive.read(CHECKSUMS_NAME) != expected_checksums:
            raise PluginZipError("SHA256SUMS.txt does not match archive contents")

        missing = REQUIRED_PACKAGE_FILES - set(package_names)
        if missing:
            raise PluginZipError(
                f"ZIP is missing required plugin files: {', '.join(sorted(missing))}"
            )
        return manifest


def build_plugin_zip(project_root: Path, output: Path | None = None) -> Path:
    """Build the plugin ZIP, validate it, and write a ZIP checksum sidecar."""
    project_root = project_root.resolve()
    version = project_version(project_root)
    output = output or project_root / "dist" / f"MembraneVisualQC-{version}.zip"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    package_files = [(name, path.read_bytes()) for name, path in collect_plugin_files(project_root)]
    for name, data in package_files:
        reject_official_provider_payload(name, data)
    manifest_data = _manifest_bytes(version, package_files)
    checksums_data = _checksums_bytes([*package_files, (MANIFEST_NAME, manifest_data)])
    entries = sorted(
        [*package_files, (MANIFEST_NAME, manifest_data), (CHECKSUMS_NAME, checksums_data)],
        key=lambda item: item[0],
    )

    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for name, data in entries:
                _write_zip_entry(archive, name, data)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)

    validate_zip_layout(output)
    digest = sha256_file(output)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii", newline="\n"
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Override the output ZIP path")
    parser.add_argument(
        "--validate", type=Path, help="Validate an existing ZIP instead of building"
    )
    args = parser.parse_args()

    if args.validate:
        validate_zip_layout(args.validate)
        print(f"valid: {args.validate}")
        print(f"sha256: {sha256_file(args.validate)}")
        return 0

    output = build_plugin_zip(args.project_root, args.output)
    print(f"built: {output}")
    print(f"sha256: {sha256_file(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
