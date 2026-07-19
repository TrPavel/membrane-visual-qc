#!/usr/bin/env python3
"""Validate release-version agreement and the complete local release artifact set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_plugin_zip import (  # noqa: E402
    MANIFEST_NAME,
    project_version,
    sha256_file,
    validate_zip_layout,
)


SCHEMA_HASHES = {
    "1.0": "5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710",
    "1.1": "86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf",
    "1.2": "96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430",
    "1.3": "6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc",
}
FORBIDDEN_ARCHIVE_PARTS = {
    ".local",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "reports",
}
FORBIDDEN_PROVIDER_NAMES = {
    "pdbtm.trpdb",
    "rcsb_assembly1.pdb.gz",
    "rcsb_deposited.pdb",
}


class ReleaseArtifactError(ValueError):
    """Raised when a release version or artifact contract is inconsistent."""


def _metadata_version(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("Version: "):
            return line.removeprefix("Version: ").strip()
    raise ReleaseArtifactError("Distribution metadata does not declare Version")


def _assert_safe_archive_names(names: list[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if (
            any(part in FORBIDDEN_ARCHIVE_PARTS for part in path.parts)
            or path.suffix == ".pyc"
            or path.name in FORBIDDEN_PROVIDER_NAMES
            or path.name.startswith("stage4a2_")
            or path.is_absolute()
            or ".." in path.parts
        ):
            raise ReleaseArtifactError(f"Forbidden release archive entry: {name}")


def _contains_absolute_windows_path(value: object) -> bool:
    if isinstance(value, str):
        return bool(re.search(r"(?:^|[\s\"'])[A-Za-z]:[\\/]", value))
    if isinstance(value, dict):
        return any(_contains_absolute_windows_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_absolute_windows_path(item) for item in value)
    return False


def validate_release_artifacts(
    project_root: Path = ROOT, dist_dir: Path | None = None
) -> dict[str, object]:
    """Validate source versions, release reports, schemas, and all four release assets."""
    project_root = project_root.resolve()
    dist_dir = (dist_dir or project_root / "dist").resolve()
    version = project_version(project_root)

    from membrane_vqc import __version__
    from membrane_vqc.constants import VERSION

    if version != VERSION or version != __version__:
        raise ReleaseArtifactError(
            f"Version mismatch: pyproject={version}, constants={VERSION}, package={__version__}"
        )

    active_surfaces = [
        project_root / "pyproject.toml",
        project_root / ".github" / "workflows" / "ci.yml",
        project_root / "scripts" / "build_plugin_zip.py",
        project_root / "scripts" / "validate_release_artifacts.py",
        *sorted((project_root / "membrane_vqc").glob("*.py")),
    ]
    development_version = "0.4.0" + ".dev0"
    for path in active_surfaces:
        if development_version in path.read_text(encoding="utf-8"):
            raise ReleaseArtifactError(f"Development version remains on active surface: {path}")

    schema_results = {}
    for schema_version, expected in SCHEMA_HASHES.items():
        path = project_root / "schemas" / f"mvqc-report-{schema_version}.schema.json"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ReleaseArtifactError(f"Schema {schema_version} hash changed: {actual}")
        schema_results[schema_version] = actual

    release_reports = []
    for path in sorted((project_root / "reports").glob("*_mvqc.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("schema_version") != "1.3":
            continue
        report_versions = {report.get("version"), report.get("software", {}).get("version")}
        if report_versions != {version}:
            raise ReleaseArtifactError(f"Release report version mismatch: {path}")
        if _contains_absolute_windows_path(report):
            raise ReleaseArtifactError(f"Absolute local path in release report: {path}")
        release_reports.append(path.name)
    if not release_reports:
        raise ReleaseArtifactError("No schema-1.3 release report was found")

    wheel = dist_dir / f"membrane_vqc_pymol-{version}-py3-none-any.whl"
    sdist = dist_dir / f"membrane_vqc_pymol-{version}.tar.gz"
    plugin_zip = dist_dir / f"MembraneVisualQC-{version}.zip"
    sidecar = plugin_zip.with_suffix(".zip.sha256")
    for path in (wheel, sdist, plugin_zip, sidecar):
        if not path.is_file():
            raise ReleaseArtifactError(f"Missing release artifact: {path}")

    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
        _assert_safe_archive_names(wheel_names)
        metadata_names = [name for name in wheel_names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ReleaseArtifactError("Wheel must contain exactly one METADATA file")
        wheel_version = _metadata_version(archive.read(metadata_names[0]).decode("utf-8"))
    if wheel_version != version:
        raise ReleaseArtifactError(f"Wheel metadata version mismatch: {wheel_version}")

    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = archive.getnames()
        _assert_safe_archive_names(sdist_names)
        metadata_names = [
            name for name in sdist_names if name.count("/") == 1 and name.endswith("/PKG-INFO")
        ]
        if len(metadata_names) != 1:
            raise ReleaseArtifactError("Sdist must contain exactly one root PKG-INFO")
        metadata_file = archive.extractfile(metadata_names[0])
        if metadata_file is None:
            raise ReleaseArtifactError("Could not read sdist PKG-INFO")
        sdist_version = _metadata_version(metadata_file.read().decode("utf-8"))
        root = metadata_names[0].split("/", 1)[0]
        relative_names = {name.removeprefix(f"{root}/") for name in sdist_names}
    if sdist_version != version:
        raise ReleaseArtifactError(f"Sdist metadata version mismatch: {sdist_version}")
    required_sdist = {
        "membrane_vqc/__init__.py",
        "membrane_vqc/commands.py",
        "membrane_vqc/pdbtm_pymol.py",
        "membrane_vqc/report.py",
        *{f"schemas/mvqc-report-{item}.schema.json" for item in SCHEMA_HASHES},
    }
    missing_sdist = required_sdist - relative_names
    if missing_sdist:
        raise ReleaseArtifactError(f"Sdist is missing: {', '.join(sorted(missing_sdist))}")

    manifest = validate_zip_layout(plugin_zip)
    if manifest["plugin"]["version"] != version:
        raise ReleaseArtifactError("Plugin ZIP manifest version mismatch")
    with zipfile.ZipFile(plugin_zip) as archive:
        _assert_safe_archive_names(archive.namelist())
        embedded = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        if embedded != manifest:
            raise ReleaseArtifactError("Plugin ZIP manifest changed while reading")

    expected_sidecar = f"{sha256_file(plugin_zip)}  {plugin_zip.name}\n"
    if sidecar.read_text(encoding="ascii") != expected_sidecar:
        raise ReleaseArtifactError("Plugin ZIP checksum sidecar is inconsistent")

    return {
        "version": version,
        "reports": release_reports,
        "schemas": schema_results,
        "artifacts": {
            path.name: {"size": path.stat().st_size, "sha256": sha256_file(path)}
            for path in (plugin_zip, sidecar, wheel, sdist)
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dist", type=Path, default=None)
    args = parser.parse_args()
    result = validate_release_artifacts(args.project_root, args.dist)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
