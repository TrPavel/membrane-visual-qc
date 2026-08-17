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
import stat
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_plugin_zip import (  # noqa: E402
    BATCH_CONTRACT_NAMES,
    FORBIDDEN_PROVIDER_PAYLOADS,
    MANIFEST_NAME,
    SCHEMA_NAMES,
    project_version,
    sha256_file,
    validate_zip_layout,
)


SCHEMA_HASHES = {
    "1.0": "5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710",
    "1.1": "86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf",
    "1.2": "96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430",
    "1.3": "6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc",
    "1.4": "ee3bc91b2ba2c32814aad61eb69ed8413bae9460c33cb5d69d839335ff6e698e",
    "1.5": "9b94df52457668e05e6e8a9cd2a7a6c362d8da59343755875d78516ddd0a7411",
}
# Schemas that actually existed, frozen, at the v0.4.0 tag. 1.4 postdates that
# release, so it must NOT be required to stay byte-identical by the
# frozen-v0.4.0 evidence gate below, even though it is required to be
# present/pinned by the current-development artifact checks.
FROZEN_V040_SCHEMA_VERSIONS = {"1.0", "1.1", "1.2", "1.3"}
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
ALLOWED_SYNTHETIC_PROVIDER_PATHS = {
    "data/synthetic/bad_core_lys.pdb",
    "data/synthetic/local_context_review.pdb",
    "data/synthetic/opm_oriented_test.pdb",
    "data/synthetic/pdbtm_api_v1_test.json",
    "data/synthetic/pdbtm_original_test.pdb",
    "data/synthetic/pdbtm_original_1tes.pdb",
    "data/synthetic/pdbtm_transformed_test.pdb",
}
FROZEN_V040_VERSION = "0.4.0"
FROZEN_V050_VERSION = "0.5.0"
FROZEN_V050_SCHEMA_VERSIONS = set(SCHEMA_HASHES)
FROZEN_V050_RELEASE_EVIDENCE = "docs/v0.5.0_release_evidence.json"
FROZEN_V050_REPORTS = {
    "reports/pdbtm_local_v050_mvqc.json": {
        "schema": "1.3",
        "size": 10222,
        "sha256": "6035e828fa8f0d559d3f0ebe4d2c583bab15b773f44a631b9214ab80e64484e6",
    },
    "reports/pdbtm_acquisition_v050_mvqc.json": {
        "schema": "1.4",
        "size": 13851,
        "sha256": "3724848b7baca9c05482d919c8d300bc39ef829d050cad203062f734df8cf3da",
    },
    "reports/source_comparison_synthetic_mvqc.json": {
        "schema": "1.5",
        "size": 5827,
        "sha256": "91910518eefbc82b9716c2bff368a32c878661dfaa8dad0f12e9bc0bd6b6f2ed",
    },
}
FROZEN_V050_ASSETS = {
    "MembraneVisualQC-0.5.0.zip": {
        "size": 158285,
        "sha256": "ffd2a8d7eeeb1c6e638fa350c452c1f752e275655d19d2634e783c9658132431",
    },
    "MembraneVisualQC-0.5.0.zip.sha256": {
        "size": 93,
        "sha256": "6283862eeb6926e12767dda7247afd76b33f1989ac65f57410082d8474eab011",
    },
    "membrane_vqc_pymol-0.5.0-py3-none-any.whl": {
        "size": 162567,
        "sha256": "5811aae44c9afee7703cf30333a11da03fdd66787905ffb22ad4386b701060ff",
    },
    "membrane_vqc_pymol-0.5.0.tar.gz": {
        "size": 257776,
        "sha256": "3b54087434e3fd2f53cf2a8b9545c9f7477318004ca4a689df83f4559e82fcf0",
    },
}
FROZEN_V050_RELEASE = {
    "url": "https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.5.0",
    "published_at": "2026-07-31T12:41:19Z",
    "prerelease": True,
    "pypi_published": False,
}
FROZEN_V050_TAG = {
    "name": "v0.5.0",
    "object": "37e83223be8cf2531ce829ac276e9feaf0b09b0b",
    "target": "8ddf5ee621f14d1993ad2779f345b8da19fd589f",
}
FROZEN_V050_RELEASE_PR = {
    "number": 19,
    "final_head": "bc0dae3bdf380c278ad3cd7dd1cf47b18467553e",
    "squash_commit": "8ddf5ee621f14d1993ad2779f345b8da19fd589f",
}
FROZEN_V050_POST_MERGE = {
    "id": 30631158437,
    "artifact_id": 8793382353,
    "outer_size": 571626,
    "outer_sha256": "fbbbbc8f604eb29b0fb285f318d33bf91f6707e5b4e947c462b3df8b8a63bc54",
}
FROZEN_V060_VERSION = "0.6.0"
FROZEN_V060_RELEASE_EVIDENCE = "docs/v0.6.0_release_evidence.json"
# v0.6.0 (Stage 5A/5B) adds no report schema and no new retained report; schemas
# 1.0-1.5 stay byte-identical to the frozen-v0.5.0 gate above, so there is no
# separate report/schema set to freeze here. Only publication evidence is new.
FROZEN_V060_ASSETS = {
    "MembraneVisualQC-0.6.0.zip": {
        "size": 192168,
        "sha256": "7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960",
    },
    "MembraneVisualQC-0.6.0.zip.sha256": {
        "size": 93,
        "sha256": "231a0f42cda4a5714821616a884afab6b412bfe438bbb1954cc1d89d7fb4860f",
    },
    "membrane_vqc_pymol-0.6.0-py3-none-any.whl": {
        "size": 196640,
        "sha256": "3e344871206ca353d7690cfc561165a7e197e9a1a27fa5a424b357b3501b9994",
    },
    "membrane_vqc_pymol-0.6.0.tar.gz": {
        "size": 304479,
        "sha256": "c39ed66b2a93b9e244c74bc7ea04277d1e6725f3581f95d76668a2a094f8b48d",
    },
}
FROZEN_V060_RELEASE = {
    "url": "https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.6.0",
    "published_at": "2026-07-31T23:08:14Z",
    "prerelease": True,
    "pypi_published": False,
}
FROZEN_V060_TAG = {
    "name": "v0.6.0",
    "object": "a17286ff9a88809ce85e4beb355392b67fc305a8",
    "target": "58e89fed284139ea6e5d6be05a35fdeada591037",
}
FROZEN_V060_RELEASE_PR = {
    "number": 23,
    "final_head": "ba18eaf343343cb6ff1cf79221e02331b02d7712",
    "squash_commit": "58e89fed284139ea6e5d6be05a35fdeada591037",
}
FROZEN_V060_POST_MERGE = {
    "id": 30671684595,
    "artifact_id": 8809005376,
    "outer_size": 684562,
    "outer_sha256": "54c61714f2ccf3c37dab01e0b184779ae13bd251b173b60578fe4f19ae7f1f5e",
}
FROZEN_V070_VERSION = "0.7.0"
FROZEN_V070_RELEASE_EVIDENCE = "docs/v0.7.0_release_evidence.json"
# v0.7.0 is a compatibility/reliability/documentation release; it adds no report
# schema or new retained report, so schemas 1.0-1.5 stay covered by the
# frozen-v0.5.0 gate above and there is no separate report/schema set here.
FROZEN_V070_ASSETS = {
    "MembraneVisualQC-0.7.0.zip": {
        "size": 194334,
        "sha256": "4672b1b91657d0ddea9d839e99de6b1b4642a17a0008afc99ae78f5eff55fda4",
    },
    "MembraneVisualQC-0.7.0.zip.sha256": {
        "size": 93,
        "sha256": "012da72b4d3a93a602c49fe6dfedf6f423821e54035af240e1042a72e74dfa59",
    },
    "membrane_vqc_pymol-0.7.0-py3-none-any.whl": {
        "size": 199960,
        "sha256": "24c956981c0e9810e16226bbecf9949906707011302285826f0f40378fccc38a",
    },
    "membrane_vqc_pymol-0.7.0.tar.gz": {
        "size": 330834,
        "sha256": "86a830071a75214eab1a114d7f6ab21587c72bbfa754f38ad7f04a9beaffc96c",
    },
}
FROZEN_V070_RELEASE = {
    "url": "https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.7.0",
    "published_at": "2026-08-01T20:48:09Z",
    "prerelease": True,
    "pypi_published": False,
}
FROZEN_V070_TAG = {
    "name": "v0.7.0",
    "object": "fa3010f7df6c5f3b0104b4aa25a338c614143601",
    "target": "c487c2fc339d415edef80797df60e62be89e8940",
}
FROZEN_V070_RELEASE_PR = {
    "number": 30,
    "final_head": "abda63968899d31c980145ad3cb786c2ac63dbaa",
    "squash_commit": "c487c2fc339d415edef80797df60e62be89e8940",
}
FROZEN_V070_POST_MERGE = {
    "id": 30717576859,
    "artifact_id": 8823821630,
    "outer_size": 716344,
    "outer_sha256": "f05257108deff918b9ffccc77581249b956b2039a4abc1aefaf74bc9dcc47d34",
}
FROZEN_V070_MANUAL_VALIDATION = {
    "stable_artifact_smoke_test": "PASS",
    "date": "2026-08-01",
    "install_upgrade_rollback_evidence": "docs/v0.7.0_install_upgrade_manual_evidence.json",
}
FROZEN_V080_VERSION = "0.8.0"
FROZEN_V080_RELEASE_EVIDENCE = "docs/v0.8.0_release_evidence.json"
# v0.8.0 is a contract-freeze/documentation release; it adds no report schema or
# new retained report, so schemas 1.0-1.5 stay covered by the frozen-v0.5.0 gate
# above and there is no separate report/schema set here.
FROZEN_V080_ASSETS = {
    "MembraneVisualQC-0.8.0.zip": {
        "size": 194332,
        "sha256": "920eff17dd5ee3be748b9b1572d91db960e98a8669a632aae83858e5e9e49542",
    },
    "MembraneVisualQC-0.8.0.zip.sha256": {
        "size": 93,
        "sha256": "b84a69e8ef8b49c13dc843a44a7c6e14a39146b8c5322cc51b0a564ca678a906",
    },
    "membrane_vqc_pymol-0.8.0-py3-none-any.whl": {
        "size": 200297,
        "sha256": "639aeb291b373b2710061a8c2c5f91379ee9dca1541308b79f1ece17028f44dd",
    },
    "membrane_vqc_pymol-0.8.0.tar.gz": {
        "size": 337821,
        "sha256": "31057c8dfbf4ab7d250bc7628298a9229aaeb6f3d4084dc77ffda05a19e5bbb6",
    },
}
FROZEN_V080_RELEASE = {
    "url": "https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.8.0",
    "published_at": "2026-08-02T10:58:19Z",
    "prerelease": True,
    "pypi_published": False,
}
FROZEN_V080_TAG = {
    "name": "v0.8.0",
    "object": "82429b55af6c7d862dbd683753bfd7fa73fd2a04",
    "target": "481e4436f1b9ff172dee20532a3cda32974f79e5",
}
FROZEN_V080_RELEASE_PR = {
    "number": 34,
    "final_head": "a7e62b80ba1b77291ca34b4bae543408770f0f0c",
    "squash_commit": "481e4436f1b9ff172dee20532a3cda32974f79e5",
}
FROZEN_V080_POST_MERGE = {
    "id": 30744354038,
    "artifact_id": 8832374827,
    "outer_size": 723645,
    "outer_sha256": "f034006a8e29f1e4898d0e852162cb7efc7caaafcc3ff5800ef1f5eb4cfa37b4",
}
FROZEN_V080_MANUAL_VALIDATION = {
    "stable_artifact_smoke_test": "PASS",
    "date": "2026-08-02",
    "install_upgrade_rollback_evidence": "docs/v0.8.0_install_upgrade_manual_evidence.json",
}
FROZEN_V090_VERSION = "0.9.0"
FROZEN_V090_RELEASE_EVIDENCE = "docs/v0.9.0_release_evidence.json"
# v0.9.0 freezes publication and acceptance evidence without introducing a new
# report schema, so schemas 1.0-1.5 remain covered by the earlier frozen gates.
FROZEN_V090_ASSETS = {
    "MembraneVisualQC-0.9.0.zip": {
        "size": 205044,
        "sha256": "9bab918b266db7f260820e6f6d13cc8ab579748a16c077ebd508e511a556c068",
    },
    "MembraneVisualQC-0.9.0.zip.sha256": {
        "size": 93,
        "sha256": "f219bbcd77bea09421ffd22a650580d6a46b308e70b1ea3fe213ec465001937b",
    },
}
FROZEN_V090_RELEASE = {
    "url": "https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.9.0",
    "published_at": "2026-08-06T11:31:50Z",
    "prerelease": True,
    "pypi_published": False,
}
FROZEN_V090_TAG = {
    "name": "v0.9.0",
    "object": "a0a535cfd4e2f234d176724f190b7c0c5710cb06",
    "target": "38f1df0a687c5c7cd4ad4c1dff33b785d4322370",
}
FROZEN_V090_RELEASE_PR = {
    "number": 40,
    "final_head": "f0e7fa2f40ec8fe581dc6e83875361f663435b6f",
    "acceptance_evidence_commit": "f0e7fa2f40ec8fe581dc6e83875361f663435b6f",
    "squash_commit": "38f1df0a687c5c7cd4ad4c1dff33b785d4322370",
    "ci_runs": [31097313027, 31097315629],
}
FROZEN_V090_POST_MERGE = {
    "id": 31097443989,
    "artifact_id": 8966039934,
    "outer_size": 777938,
    "outer_sha256": "c3a5b7624b078ad641f7807a6aad134ffdce763ff07405c0a0d6c611cb50c17f",
}
FROZEN_V090_MANUAL_VALIDATION = {
    "stable_artifact_smoke_test": "PASS",
    "owner_verdict": "READY TO PUBLISH v0.9.0",
    "date": "2026-08-06",
    "install_upgrade_rollback_evidence": "docs/releases/v0.9.0_manual_acceptance.md",
}
FROZEN_V100RC1_VERSION = "1.0.0rc1"
FROZEN_V100RC1_RELEASE_EVIDENCE = "docs/v1.0.0rc1_release_evidence.json"
FROZEN_V100RC1_EVIDENCE_SHA256 = "30fb8e92b56b1e997be18e9b3684cbe824a06d6ecc846df6bbf1fbb5b6005076"
FROZEN_V100_VERSION = "1.0.0"
FROZEN_V100_RELEASE_EVIDENCE = "docs/v1.0.0_release_evidence.json"
FROZEN_V100_EVIDENCE_SHA256 = "c228404731e464e7418a99fb7d833cfd282e8e34e99684d4e4ff54e911a7d2d0"
STAGE4B1_RUNTIME_MODULES = {
    "membrane_vqc/pdbtm_cache.py",
    "membrane_vqc/pdbtm_cache_contract.py",
    "membrane_vqc/pdbtm_errors.py",
    "membrane_vqc/pdbtm_provider.py",
    "membrane_vqc/pdbtm_retrieval.py",
    "membrane_vqc/pdbtm_transport.py",
}
STAGE4B2_RUNTIME_MODULES = {
    "membrane_vqc/pdbtm_report_provenance.py",
}
STAGE4B3_RUNTIME_MODULES = {
    "membrane_vqc/pdbtm_worker.py",
    "membrane_vqc/pdbtm_gui_worker.py",
}
STAGE4C_RUNTIME_MODULES = {
    "membrane_vqc/opm_adapter.py",
    "membrane_vqc/orientation_comparison.py",
    "membrane_vqc/comparison_report.py",
    "membrane_vqc/comparison_worker.py",
    "membrane_vqc/comparison_gui_worker.py",
    "membrane_vqc/comparison_pymol.py",
}
STAGE5A_RUNTIME_MODULES = {
    "membrane_vqc/batch_cli.py",
    "membrane_vqc/batch_comparison.py",
    "membrane_vqc/batch_contracts.py",
    "membrane_vqc/batch_executor.py",
    "membrane_vqc/batch_paths.py",
    "membrane_vqc/batch_runner.py",
}
STAGE5B_RUNTIME_MODULES = {
    "membrane_vqc/batch_gui.py",
    "membrane_vqc/batch_result_browser.py",
}
BATCH_CONTRACT_FILES = {
    "schemas/mvqc-batch-plan-1.0.schema.json",
    "schemas/mvqc-batch-result-1.0.schema.json",
}
BATCH_CONTRACT_HASHES = {
    "schemas/mvqc-batch-plan-1.0.schema.json": (
        "996eff32e5a8e240be447ef2efa42e27e59095806c2725d42ed8d331a9bc766d"
    ),
    "schemas/mvqc-batch-result-1.0.schema.json": (
        "e61dfb6e2a635d4cf76a6f2a07ccbbcc2aea170c9e62dc50d36e07180f98163a"
    ),
}
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
    canonical_names: set[str] = set()
    for name in names:
        path = PurePosixPath(name)
        canonical = path.as_posix()
        is_directory = name.endswith("/")
        if (
            not name
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
            or "//" in name
            or any(part in {"", "."} for part in name.strip("/").split("/"))
            or name != canonical + ("/" if is_directory else "")
        ):
            raise ReleaseArtifactError(f"Non-canonical release archive entry: {name}")
        canonical_key = canonical.rstrip("/")
        if canonical_key in canonical_names:
            raise ReleaseArtifactError("Release archive contains duplicate entries")
        canonical_names.add(canonical_key)
        if (
            path.name.casefold() == "batch-result.json"
            or path.suffix.casefold() == ".csv"
            or any(part.casefold().startswith(".mvqc-batch") for part in path.parts)
            or any("session-history" in part.casefold() for part in path.parts)
        ):
            raise ReleaseArtifactError(f"Generated batch/session output is forbidden: {name}")
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


def _assert_safe_zip_entries(infos: list[zipfile.ZipInfo]) -> None:
    """Reject duplicate, unsafe, or non-regular ZIP members."""
    _assert_safe_archive_names([info.filename for info in infos])
    for info in infos:
        if info.is_dir():
            continue
        mode_type = stat.S_IFMT(info.external_attr >> 16)
        if mode_type not in (0, stat.S_IFREG):
            raise ReleaseArtifactError(f"Release ZIP entry is not a regular file: {info.filename}")


def _assert_safe_tar_entries(members: list[tarfile.TarInfo]) -> None:
    """Reject duplicate, unsafe, or non-file/non-directory tar members."""
    _assert_safe_archive_names([member.name for member in members])
    for member in members:
        if not (member.isfile() or member.isdir()):
            raise ReleaseArtifactError(
                f"Release tar entry is not a regular file or directory: {member.name}"
            )


def _assert_safe_archive_payload(name: str, data: bytes) -> None:
    identity = (len(data), hashlib.sha256(data).hexdigest())
    if identity in FORBIDDEN_PROVIDER_PAYLOADS:
        raise ReleaseArtifactError(f"Official provider payload is forbidden: {name}")
    normalized = PurePosixPath(name).as_posix()
    is_allowed_synthetic = any(
        normalized == allowed or normalized.endswith(f"/{allowed}")
        for allowed in ALLOWED_SYNTHETIC_PROVIDER_PATHS
    )
    suffix = PurePosixPath(normalized).suffix.lower()
    if not is_allowed_synthetic and (
        suffix in {".pdb", ".trpdb", ".ent"} or (suffix == ".json" and b'"pdb_id"' in data)
    ):
        raise ReleaseArtifactError(f"Provider-shaped payload is forbidden: {name}")


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
    for schema_version, expected_hash in SCHEMA_HASHES.items():
        schema_path = project_root / "schemas" / f"mvqc-report-{schema_version}.schema.json"
        if not schema_path.is_file() or sha256_file(schema_path) != expected_hash:
            raise ReleaseArtifactError(
                f"Schema {schema_version} does not match its recorded current-development hash"
            )
    for relative, expected_hash in BATCH_CONTRACT_HASHES.items():
        path = project_root / relative
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise ReleaseArtifactError(
                f"Batch contract does not match its recorded immutable hash: {relative}"
            )

    wheel = dist_dir / f"membrane_vqc_pymol-{expected_version}-py3-none-any.whl"
    sdist = dist_dir / f"membrane_vqc_pymol-{expected_version}.tar.gz"
    plugin_zip = dist_dir / f"MembraneVisualQC-{expected_version}.zip"
    sidecar = plugin_zip.with_suffix(".zip.sha256")
    for path in (wheel, sdist, plugin_zip, sidecar):
        if not path.is_file():
            raise ReleaseArtifactError(f"Missing release artifact: {path}")

    with zipfile.ZipFile(wheel) as archive:
        wheel_infos = archive.infolist()
        _assert_safe_zip_entries(wheel_infos)
        wheel_names = [info.filename for info in wheel_infos]
        for name in wheel_names:
            if not name.endswith("/"):
                _assert_safe_archive_payload(name, archive.read(name))
        metadata_name = f"membrane_vqc_pymol-{expected_version}.dist-info/METADATA"
        if wheel_names.count(metadata_name) != 1:
            raise ReleaseArtifactError(f"Wheel must contain exactly {metadata_name}")
        missing_wheel = (
            STAGE4B1_RUNTIME_MODULES
            | STAGE4B2_RUNTIME_MODULES
            | STAGE4B3_RUNTIME_MODULES
            | STAGE4C_RUNTIME_MODULES
            | STAGE5A_RUNTIME_MODULES
            | STAGE5B_RUNTIME_MODULES
        ) - set(wheel_names)
        if missing_wheel:
            raise ReleaseArtifactError(f"Wheel is missing: {', '.join(sorted(missing_wheel))}")
        for schema_version, expected_hash in SCHEMA_HASHES.items():
            suffix = f"/data/schemas/mvqc-report-{schema_version}.schema.json"
            wheel_schema_names = [name for name in wheel_names if name.endswith(suffix)]
            if len(wheel_schema_names) != 1 or (
                hashlib.sha256(archive.read(wheel_schema_names[0])).hexdigest() != expected_hash
            ):
                raise ReleaseArtifactError(
                    f"Wheel schema {schema_version} is missing or does not match its hash"
                )
        for relative in BATCH_CONTRACT_FILES:
            suffix = f"/data/{relative}"
            matches = [name for name in wheel_names if name.endswith(suffix)]
            if len(matches) != 1:
                raise ReleaseArtifactError(f"Wheel is missing batch contract: {relative}")
            if (
                hashlib.sha256(archive.read(matches[0])).hexdigest()
                != BATCH_CONTRACT_HASHES[relative]
            ):
                raise ReleaseArtifactError(f"Wheel batch contract differs from source: {relative}")
        wheel_version = _metadata_version(archive.read(metadata_name).decode("utf-8"))
    if wheel_version != expected_version:
        raise ReleaseArtifactError(f"Wheel metadata version mismatch: {wheel_version}")

    with tarfile.open(sdist, "r:gz") as archive:
        sdist_members = archive.getmembers()
        _assert_safe_tar_entries(sdist_members)
        sdist_names = [member.name for member in sdist_members]
        for member in sdist_members:
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is None:
                    raise ReleaseArtifactError(f"Could not read sdist entry: {member.name}")
                _assert_safe_archive_payload(member.name, stream.read())
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
        for schema_version, expected_hash in SCHEMA_HASHES.items():
            schema_name = f"{root}/schemas/mvqc-report-{schema_version}.schema.json"
            schema_stream = archive.extractfile(schema_name)
            if (
                schema_stream is None
                or hashlib.sha256(schema_stream.read()).hexdigest() != expected_hash
            ):
                raise ReleaseArtifactError(
                    f"Sdist schema {schema_version} does not match its recorded hash"
                )
        for relative, expected_hash in BATCH_CONTRACT_HASHES.items():
            stream = archive.extractfile(f"{root}/{relative}")
            if stream is None or hashlib.sha256(stream.read()).hexdigest() != expected_hash:
                raise ReleaseArtifactError(f"Sdist batch contract differs from source: {relative}")
    if sdist_version != expected_version:
        raise ReleaseArtifactError(f"Sdist metadata version mismatch: {sdist_version}")
    required_sdist = {
        "membrane_vqc/__init__.py",
        "membrane_vqc/commands.py",
        "membrane_vqc/pdbtm_pymol.py",
        *STAGE4B1_RUNTIME_MODULES,
        *STAGE4B2_RUNTIME_MODULES,
        *STAGE4B3_RUNTIME_MODULES,
        *STAGE4C_RUNTIME_MODULES,
        *STAGE5A_RUNTIME_MODULES,
        *STAGE5B_RUNTIME_MODULES,
        "membrane_vqc/report.py",
        *{f"schemas/mvqc-report-{item}.schema.json" for item in SCHEMA_HASHES},
        *BATCH_CONTRACT_FILES,
    }
    missing_sdist = required_sdist - relative_names
    if missing_sdist:
        raise ReleaseArtifactError(f"Sdist is missing: {', '.join(sorted(missing_sdist))}")

    manifest = validate_zip_layout(plugin_zip)
    if manifest["plugin"]["version"] != expected_version:
        raise ReleaseArtifactError("Plugin ZIP manifest version mismatch")
    with zipfile.ZipFile(plugin_zip) as archive:
        _assert_safe_zip_entries(archive.infolist())
        embedded = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        if embedded != manifest:
            raise ReleaseArtifactError("Plugin ZIP manifest changed while reading")
        for schema_version, expected_hash in SCHEMA_HASHES.items():
            schema_name = SCHEMA_NAMES[schema_version]
            if hashlib.sha256(archive.read(schema_name)).hexdigest() != expected_hash:
                raise ReleaseArtifactError(
                    f"Plugin ZIP schema {schema_version} does not match its recorded hash"
                )
        for contract, archive_name in BATCH_CONTRACT_NAMES.items():
            relative = f"schemas/mvqc-batch-{contract}.schema.json"
            if (
                hashlib.sha256(archive.read(archive_name)).hexdigest()
                != BATCH_CONTRACT_HASHES[relative]
            ):
                raise ReleaseArtifactError(
                    f"Plugin ZIP batch contract differs from source: {relative}"
                )

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
    for schema_version in FROZEN_V040_SCHEMA_VERSIONS:
        expected = SCHEMA_HASHES[schema_version]
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


def verify_frozen_v050_evidence(project_root: Path = ROOT) -> dict[str, object]:
    """Verify published v0.5.0 evidence without consulting the active version."""
    project_root = project_root.resolve()

    schema_results = {}
    for schema_version in FROZEN_V050_SCHEMA_VERSIONS:
        path = project_root / "schemas" / f"mvqc-report-{schema_version}.schema.json"
        actual = sha256_file(path)
        if actual != SCHEMA_HASHES[schema_version]:
            raise ReleaseArtifactError(f"Frozen v0.5.0 schema {schema_version} changed: {actual}")
        schema_results[schema_version] = actual

    report_results = {}
    for relative, expected in FROZEN_V050_REPORTS.items():
        path = project_root / relative
        raw = path.read_bytes()
        actual = {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if actual != {key: expected[key] for key in ("size", "sha256")}:
            raise ReleaseArtifactError(f"Frozen v0.5.0 report changed: {relative}: {actual}")
        report = json.loads(raw)
        if report.get("schema_version") != expected["schema"]:
            raise ReleaseArtifactError(f"Frozen v0.5.0 report schema changed: {relative}")
        software = report.get("software", {})
        if software.get("version") != FROZEN_V050_VERSION:
            raise ReleaseArtifactError(f"Frozen v0.5.0 report version changed: {relative}")
        if report.get("version", FROZEN_V050_VERSION) != FROZEN_V050_VERSION:
            raise ReleaseArtifactError(f"Frozen v0.5.0 legacy report version changed: {relative}")
        if _contains_absolute_windows_path(report):
            raise ReleaseArtifactError(f"Absolute local path in frozen v0.5.0 report: {relative}")
        report_results[relative] = {**actual, "schema": expected["schema"]}

    evidence_path = project_root / FROZEN_V050_RELEASE_EVIDENCE
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    expected_sections = {
        "version": FROZEN_V050_VERSION,
        "release_pr": FROZEN_V050_RELEASE_PR,
        "post_merge_workflow": FROZEN_V050_POST_MERGE,
        "tag": FROZEN_V050_TAG,
        "release": FROZEN_V050_RELEASE,
        "assets": FROZEN_V050_ASSETS,
    }
    if evidence != expected_sections:
        raise ReleaseArtifactError("Frozen v0.5.0 publication evidence changed")

    return {
        "version": FROZEN_V050_VERSION,
        "schemas": schema_results,
        "reports": report_results,
        "assets": evidence["assets"],
        "release": evidence["release"],
        "tag": evidence["tag"],
        "release_pr": evidence["release_pr"],
        "post_merge_workflow": evidence["post_merge_workflow"],
    }


def verify_frozen_v060_evidence(project_root: Path = ROOT) -> dict[str, object]:
    """Verify published v0.6.0 publication evidence without consulting the active version."""
    project_root = project_root.resolve()

    evidence_path = project_root / FROZEN_V060_RELEASE_EVIDENCE
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    expected_sections = {
        "version": FROZEN_V060_VERSION,
        "release_pr": FROZEN_V060_RELEASE_PR,
        "post_merge_workflow": FROZEN_V060_POST_MERGE,
        "tag": FROZEN_V060_TAG,
        "release": FROZEN_V060_RELEASE,
        "assets": FROZEN_V060_ASSETS,
    }
    if evidence != expected_sections:
        raise ReleaseArtifactError("Frozen v0.6.0 publication evidence changed")

    return {
        "version": FROZEN_V060_VERSION,
        "assets": evidence["assets"],
        "release": evidence["release"],
        "tag": evidence["tag"],
        "release_pr": evidence["release_pr"],
        "post_merge_workflow": evidence["post_merge_workflow"],
    }


def verify_frozen_v070_evidence(project_root: Path = ROOT) -> dict[str, object]:
    """Verify published v0.7.0 publication evidence without consulting the active version."""
    project_root = project_root.resolve()

    evidence_path = project_root / FROZEN_V070_RELEASE_EVIDENCE
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    expected_sections = {
        "version": FROZEN_V070_VERSION,
        "release_pr": FROZEN_V070_RELEASE_PR,
        "post_merge_workflow": FROZEN_V070_POST_MERGE,
        "tag": FROZEN_V070_TAG,
        "release": FROZEN_V070_RELEASE,
        "assets": FROZEN_V070_ASSETS,
        "manual_validation": FROZEN_V070_MANUAL_VALIDATION,
    }
    if evidence != expected_sections:
        raise ReleaseArtifactError("Frozen v0.7.0 publication evidence changed")

    return {
        "version": FROZEN_V070_VERSION,
        "assets": evidence["assets"],
        "release": evidence["release"],
        "tag": evidence["tag"],
        "release_pr": evidence["release_pr"],
        "post_merge_workflow": evidence["post_merge_workflow"],
        "manual_validation": evidence["manual_validation"],
    }


def verify_frozen_v080_evidence(project_root: Path = ROOT) -> dict[str, object]:
    """Verify published v0.8.0 publication evidence without consulting the active version."""
    project_root = project_root.resolve()

    evidence_path = project_root / FROZEN_V080_RELEASE_EVIDENCE
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    expected_sections = {
        "version": FROZEN_V080_VERSION,
        "release_pr": FROZEN_V080_RELEASE_PR,
        "post_merge_workflow": FROZEN_V080_POST_MERGE,
        "tag": FROZEN_V080_TAG,
        "release": FROZEN_V080_RELEASE,
        "assets": FROZEN_V080_ASSETS,
        "manual_validation": FROZEN_V080_MANUAL_VALIDATION,
    }
    if evidence != expected_sections:
        raise ReleaseArtifactError("Frozen v0.8.0 publication evidence changed")

    return {
        "version": FROZEN_V080_VERSION,
        "assets": evidence["assets"],
        "release": evidence["release"],
        "tag": evidence["tag"],
        "release_pr": evidence["release_pr"],
        "post_merge_workflow": evidence["post_merge_workflow"],
        "manual_validation": evidence["manual_validation"],
    }


def verify_frozen_v090_evidence(project_root: Path = ROOT) -> dict[str, object]:
    """Verify published v0.9.0 publication evidence without consulting the active version."""
    project_root = project_root.resolve()

    evidence_path = project_root / FROZEN_V090_RELEASE_EVIDENCE
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    expected_sections = {
        "version": FROZEN_V090_VERSION,
        "release_pr": FROZEN_V090_RELEASE_PR,
        "post_merge_workflow": FROZEN_V090_POST_MERGE,
        "tag": FROZEN_V090_TAG,
        "release": FROZEN_V090_RELEASE,
        "assets": FROZEN_V090_ASSETS,
        "manual_validation": FROZEN_V090_MANUAL_VALIDATION,
    }
    if evidence != expected_sections:
        raise ReleaseArtifactError("Frozen v0.9.0 publication evidence changed")

    return {
        "version": FROZEN_V090_VERSION,
        "assets": evidence["assets"],
        "release": evidence["release"],
        "tag": evidence["tag"],
        "release_pr": evidence["release_pr"],
        "post_merge_workflow": evidence["post_merge_workflow"],
        "manual_validation": evidence["manual_validation"],
    }


def verify_frozen_v100rc1_evidence(project_root: Path = ROOT) -> dict[str, object]:
    """Verify immutable v1.0.0rc1 publication evidence independently of development."""
    path = project_root.resolve() / FROZEN_V100RC1_RELEASE_EVIDENCE
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_V100RC1_EVIDENCE_SHA256:
        raise ReleaseArtifactError("Frozen v1.0.0rc1 publication evidence changed")
    evidence = json.loads(raw)
    if evidence.get("version") != FROZEN_V100RC1_VERSION:
        raise ReleaseArtifactError("Frozen v1.0.0rc1 version changed")
    if evidence.get("tag", {}).get("target") != evidence.get("release_pr", {}).get("squash_commit"):
        raise ReleaseArtifactError("Frozen v1.0.0rc1 tag target changed")
    return evidence


def verify_frozen_v100_evidence(project_root: Path = ROOT) -> dict[str, object]:
    """Verify immutable v1.0.0 publication evidence independently of development."""
    path = project_root.resolve() / FROZEN_V100_RELEASE_EVIDENCE
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_V100_EVIDENCE_SHA256:
        raise ReleaseArtifactError("Frozen v1.0.0 publication evidence changed")
    evidence = json.loads(raw)
    if evidence.get("version") != FROZEN_V100_VERSION:
        raise ReleaseArtifactError("Frozen v1.0.0 version changed")
    tag = evidence.get("tag", {})
    release_pr = evidence.get("release_pr", {})
    release = evidence.get("release", {})
    if tag.get("target") != release_pr.get("squash_commit"):
        raise ReleaseArtifactError("Frozen v1.0.0 tag target changed")
    if tag.get("annotated") is not True:
        raise ReleaseArtifactError("Frozen v1.0.0 annotated-tag state changed")
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ReleaseArtifactError("Frozen v1.0.0 stable-release state changed")
    if release.get("pypi_published") is not False:
        raise ReleaseArtifactError("Frozen v1.0.0 PyPI state changed")
    return evidence


# Backwards-compatible API name for callers that validate the active build.
validate_release_artifacts = validate_current_development_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=(
            "current-development",
            "frozen-v0.4.0",
            "frozen-v0.5.0",
            "frozen-v0.6.0",
            "frozen-v0.7.0",
            "frozen-v0.8.0",
            "frozen-v0.9.0",
            "frozen-v1.0.0rc1",
            "frozen-v1.0.0",
            "release-candidate",
        ),
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
    elif args.mode == "frozen-v0.5.0":
        if args.version is not None:
            parser.error("--version is only valid with --mode release-candidate")
        result = verify_frozen_v050_evidence(args.project_root)
    elif args.mode == "frozen-v0.6.0":
        if args.version is not None:
            parser.error("--version is only valid with --mode release-candidate")
        result = verify_frozen_v060_evidence(args.project_root)
    elif args.mode == "frozen-v0.7.0":
        if args.version is not None:
            parser.error("--version is only valid with --mode release-candidate")
        result = verify_frozen_v070_evidence(args.project_root)
    elif args.mode == "frozen-v0.8.0":
        if args.version is not None:
            parser.error("--version is only valid with --mode release-candidate")
        result = verify_frozen_v080_evidence(args.project_root)
    elif args.mode == "frozen-v0.9.0":
        if args.version is not None:
            parser.error("--version is only valid with --mode release-candidate")
        result = verify_frozen_v090_evidence(args.project_root)
    elif args.mode == "frozen-v1.0.0rc1":
        if args.version is not None:
            parser.error("--version is only valid with --mode release-candidate")
        result = verify_frozen_v100rc1_evidence(args.project_root)
    elif args.mode == "frozen-v1.0.0":
        if args.version is not None:
            parser.error("--version is only valid with --mode release-candidate")
        result = verify_frozen_v100_evidence(args.project_root)
    else:
        if args.version is None:
            parser.error("--mode release-candidate requires --version")
        result = validate_release_candidate_artifacts(args.version, args.project_root, args.dist)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
