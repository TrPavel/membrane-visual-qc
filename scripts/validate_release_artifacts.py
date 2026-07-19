#!/usr/bin/env python3
"""Validate release-version agreement and the complete local release artifact set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
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
FROZEN_V040_VERSION = "0.4.0"
FROZEN_V040_REPORT = "reports/pdbtm_synthetic_mvqc.json"
FROZEN_V040_FILE_HASHES = {
    FROZEN_V040_REPORT: "18874373d3792f70919b985162fd1982cd3d41595d5f589955069af37788bb0e",
    "docs/v0.4.0_release_notes.md": (
        "2bb7889301eeb30966f5a0e7360d5af6aa49f3db651922a3f3572d715211309c"
    ),
    "docs/v0.4.0_graphical_smoke.md": (
        "4434c5d4689fcbae0be12395294cced9926875013715ab0d5832240df520ba55"
    ),
}
FROZEN_V040_REPORT_PROVENANCE = {
    "commit": "2f0247474c1b1a8da59c7307fa12fba8c009ca97",
    "timestamp": "2026-07-19T20:48:41.424766+00:00",
    "payloads": {
        "pdbtm_json": {
            "byte_size": 527,
            "sha256": "7577a8135d0934ea39f118ad0b19b2475f48529dc105626b37a2437522272a7e",
        },
        "transformed_pdb": {
            "byte_size": 1019,
            "sha256": "2bf25ae63c52eae197de7d9bf1f963dca972ff687a2482282a19ef3900f59cb1",
        },
    },
}
_PACKAGE_VERSION_PROBE = """
import json
from pathlib import Path

import membrane_vqc
from membrane_vqc.constants import VERSION

print(json.dumps({
    "constants": VERSION,
    "package": membrane_vqc.__version__,
    "file": str(Path(membrane_vqc.__file__).resolve()),
}))
"""


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
            "\\" in name
            or bool(re.match(r"^[A-Za-z]:", name))
            or any(part in FORBIDDEN_ARCHIVE_PARTS for part in path.parts)
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


def _target_package_versions(project_root: Path) -> dict[str, str]:
    """Read runtime versions from an isolated import of the target checkout."""
    project_root = project_root.resolve()
    environment = os.environ.copy()
    inherited_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(project_root) + (
        os.pathsep + inherited_pythonpath if inherited_pythonpath else ""
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", _PACKAGE_VERSION_PROBE],
            cwd=project_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ReleaseArtifactError(f"Could not inspect target package: {error}") from error

    if completed.returncode != 0:
        diagnostic = next(
            (line.strip() for line in reversed(completed.stderr.splitlines()) if line.strip()),
            "no diagnostic output",
        )
        raise ReleaseArtifactError(
            f"Could not inspect target package (exit {completed.returncode}): {diagnostic}"
        )
    try:
        result = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as error:
        raise ReleaseArtifactError("Target package probe returned malformed JSON") from error
    if not isinstance(result, dict) or any(
        not isinstance(result.get(key), str) for key in ("constants", "package", "file")
    ):
        raise ReleaseArtifactError("Target package probe returned an invalid contract")

    package_file = Path(result["file"]).resolve()
    target_package = (project_root / "membrane_vqc").resolve()
    if not package_file.is_relative_to(target_package):
        raise ReleaseArtifactError(
            "Target package resolved outside the supplied project root: "
            f"file={package_file}, expected_under={target_package}"
        )
    return {key: result[key] for key in ("constants", "package", "file")}


def _validate_version_agreement(project_root: Path, expected_version: str) -> dict[str, str]:
    """Require target-checkout source and runtime versions to agree."""
    source_version = project_version(project_root)
    package = _target_package_versions(project_root)

    if {source_version, package["constants"], package["package"]} != {expected_version}:
        raise ReleaseArtifactError(
            "Version mismatch: "
            f"expected={expected_version}, pyproject={source_version}, "
            f"constants={package['constants']}, package={package['package']}"
        )
    return {
        "pyproject": source_version,
        "constants": package["constants"],
        "package": package["package"],
        "file": package["file"],
    }


def _validate_artifact_set(
    project_root: Path, dist_dir: Path, expected_version: str
) -> dict[str, object]:
    """Validate one exact four-file artifact set for an explicit version."""
    project_root = project_root.resolve()
    dist_dir = dist_dir.resolve()
    _validate_version_agreement(project_root, expected_version)

    wheel = dist_dir / f"membrane_vqc_pymol-{expected_version}-py3-none-any.whl"
    sdist = dist_dir / f"membrane_vqc_pymol-{expected_version}.tar.gz"
    plugin_zip = dist_dir / f"MembraneVisualQC-{expected_version}.zip"
    sidecar = plugin_zip.with_suffix(".zip.sha256")
    for path in (wheel, sdist, plugin_zip, sidecar):
        if not path.is_file():
            raise ReleaseArtifactError(f"Missing release artifact: {path}")

    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
        _assert_safe_archive_names(wheel_names)
        metadata_name = f"membrane_vqc_pymol-{expected_version}.dist-info/METADATA"
        if wheel_names.count(metadata_name) != 1:
            raise ReleaseArtifactError(f"Wheel must contain exactly {metadata_name}")
        wheel_version = _metadata_version(archive.read(metadata_name).decode("utf-8"))
    if wheel_version != expected_version:
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
        expected_root = f"membrane_vqc_pymol-{expected_version}"
        if root != expected_root:
            raise ReleaseArtifactError(f"Sdist root mismatch: {root}")
        relative_names = {name.removeprefix(f"{root}/") for name in sdist_names}
    if sdist_version != expected_version:
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
    if manifest["plugin"]["version"] != expected_version:
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
        "version": expected_version,
        "artifacts": {
            path.name: {"size": path.stat().st_size, "sha256": sha256_file(path)}
            for path in (plugin_zip, sidecar, wheel, sdist)
        },
    }


def validate_current_development_artifacts(
    project_root: Path = ROOT, dist_dir: Path | None = None
) -> dict[str, object]:
    """Validate the active source version and its development artifacts."""
    project_root = project_root.resolve()
    version = project_version(project_root)
    return _validate_artifact_set(
        project_root, dist_dir or project_root / "dist", expected_version=version
    )


def validate_release_candidate_artifacts(
    expected_version: str, project_root: Path = ROOT, dist_dir: Path | None = None
) -> dict[str, object]:
    """Validate artifacts for an explicitly selected future release candidate."""
    if not expected_version:
        raise ReleaseArtifactError("Release-candidate validation requires an explicit version")
    project_root = project_root.resolve()
    return _validate_artifact_set(
        project_root, dist_dir or project_root / "dist", expected_version=expected_version
    )


def verify_frozen_v040_evidence(project_root: Path = ROOT) -> dict[str, object]:
    """Verify immutable v0.4.0 report, documentation, and released schema bytes."""
    project_root = project_root.resolve()
    file_results = {}
    for relative, expected in FROZEN_V040_FILE_HASHES.items():
        path = project_root / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ReleaseArtifactError(f"Frozen v0.4.0 evidence changed: {relative}: {actual}")
        file_results[relative] = actual

    schema_results = {}
    for schema_version, expected in SCHEMA_HASHES.items():
        path = project_root / "schemas" / f"mvqc-report-{schema_version}.schema.json"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ReleaseArtifactError(f"Schema {schema_version} hash changed: {actual}")
        schema_results[schema_version] = actual

    report_path = project_root / FROZEN_V040_REPORT
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema_version") != "1.3":
        raise ReleaseArtifactError("Frozen v0.4.0 report is not schema 1.3")
    if {report.get("version"), report.get("software", {}).get("version")} != {FROZEN_V040_VERSION}:
        raise ReleaseArtifactError("Frozen report no longer declares v0.4.0")
    if report.get("software", {}).get("commit_status") != "recorded":
        raise ReleaseArtifactError("Frozen report commit provenance is no longer recorded")
    provenance = FROZEN_V040_REPORT_PROVENANCE
    if report.get("software", {}).get("commit") != provenance["commit"]:
        raise ReleaseArtifactError("Frozen report commit changed")
    if report.get("generated_at") != provenance["timestamp"]:
        raise ReleaseArtifactError("Frozen report timestamp changed")
    if report.get("timestamp") != provenance["timestamp"]:
        raise ReleaseArtifactError("Frozen report timestamp alias changed")
    if _contains_absolute_windows_path(report):
        raise ReleaseArtifactError("Absolute local path in frozen v0.4.0 report")

    payloads = {
        payload.get("role"): payload
        for payload in report["orientation"]["evidence"]["source"]["raw_payloads"]
    }
    if set(payloads) != set(provenance["payloads"]):
        raise ReleaseArtifactError("Frozen report payload roles changed")
    for role, expected in provenance["payloads"].items():
        payload = payloads[role]
        if payload.get("source") is not None:
            raise ReleaseArtifactError(f"Frozen report payload source changed: {role}")
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ReleaseArtifactError(f"Frozen report payload provenance changed: {role}")

    return {
        "version": FROZEN_V040_VERSION,
        "report": FROZEN_V040_REPORT,
        "files": file_results,
        "schemas": schema_results,
    }


# Backwards-compatible API name for callers that validate the active build.
validate_release_artifacts = validate_current_development_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("current-development", "frozen-v0.4.0", "release-candidate"),
        default="current-development",
    )
    parser.add_argument("--version", default=None)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dist", type=Path, default=None)
    args = parser.parse_args()
    if args.mode == "current-development":
        if args.version is not None:
            parser.error("--version is only valid with --mode release-candidate")
        result = validate_current_development_artifacts(args.project_root, args.dist)
    elif args.mode == "frozen-v0.4.0":
        if args.version is not None:
            parser.error("--version is only valid with --mode release-candidate")
        result = verify_frozen_v040_evidence(args.project_root)
    else:
        if args.version is None:
            parser.error("--mode release-candidate requires --version")
        result = validate_release_candidate_artifacts(args.version, args.project_root, args.dist)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
