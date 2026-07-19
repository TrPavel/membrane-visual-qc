import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import zipfile

import pytest

from scripts.build_plugin_zip import build_plugin_zip
from scripts.validate_release_artifacts import (
    ReleaseArtifactError,
    _assert_safe_archive_names,
    validate_current_development_artifacts,
    validate_release_candidate_artifacts,
    verify_frozen_v040_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_consistent_across_representative_artifacts(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    version = "0.5.0.dev0"
    wheel = dist / f"membrane_vqc_pymol-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("membrane_vqc/__init__.py", "")
        archive.writestr(
            f"membrane_vqc_pymol-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: membrane-vqc-pymol\nVersion: {version}\n",
        )

    sdist = dist / f"membrane_vqc_pymol-{version}.tar.gz"
    root = f"membrane_vqc_pymol-{version}"
    required = {
        "PKG-INFO": (f"Metadata-Version: 2.4\nName: membrane-vqc-pymol\nVersion: {version}\n"),
        "membrane_vqc/__init__.py": "",
        "membrane_vqc/commands.py": "",
        "membrane_vqc/pdbtm_pymol.py": "",
        "membrane_vqc/report.py": "",
        "schemas/mvqc-report-1.0.schema.json": "{}",
        "schemas/mvqc-report-1.1.schema.json": "{}",
        "schemas/mvqc-report-1.2.schema.json": "{}",
        "schemas/mvqc-report-1.3.schema.json": "{}",
    }
    with tarfile.open(sdist, "w:gz") as archive:
        for name, text in required.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(f"{root}/{name}")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))

    build_plugin_zip(ROOT, dist / f"MembraneVisualQC-{version}.zip")

    result = validate_current_development_artifacts(ROOT, dist)

    assert result["version"] == version
    assert set(result["artifacts"]) == {
        f"MembraneVisualQC-{version}.zip",
        f"MembraneVisualQC-{version}.zip.sha256",
        f"membrane_vqc_pymol-{version}-py3-none-any.whl",
        f"membrane_vqc_pymol-{version}.tar.gz",
    }
    assert validate_release_candidate_artifacts(version, ROOT, dist) == result


def test_frozen_v040_evidence_is_verified_independently():
    result = verify_frozen_v040_evidence(ROOT)

    assert result["version"] == "0.4.0"
    assert result["report"] == "reports/pdbtm_synthetic_mvqc.json"
    assert set(result["schemas"]) == {"1.0", "1.1", "1.2", "1.3"}


def test_frozen_v040_evidence_rejects_byte_changes(tmp_path):
    for directory in ("reports", "docs", "schemas"):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    report = tmp_path / "reports" / "pdbtm_synthetic_mvqc.json"
    report.write_bytes(report.read_bytes() + b"\n")

    with pytest.raises(ReleaseArtifactError, match="Frozen v0.4.0 evidence changed"):
        verify_frozen_v040_evidence(tmp_path)


def test_schema_1_3_release_report_has_no_absolute_local_provider_path():
    report = json.loads((ROOT / "reports" / "pdbtm_synthetic_mvqc.json").read_text("utf-8"))

    assert report["schema_version"] == "1.3"
    assert report["software"]["version"] == "0.4.0"
    assert report["version"] == "0.4.0"
    assert report["software"]["commit_status"] == "recorded"
    assert report["software"]["commit"] == "2f0247474c1b1a8da59c7307fa12fba8c009ca97"
    assert report["generated_at"] == "2026-07-19T20:48:41.424766+00:00"
    assert report["timestamp"] == report["generated_at"]
    assert all(
        payload["source"] is None
        for payload in report["orientation"]["evidence"]["source"]["raw_payloads"]
    )
    payloads = {
        payload["role"]: payload
        for payload in report["orientation"]["evidence"]["source"]["raw_payloads"]
    }
    for role, relative_path in {
        "pdbtm_json": "data/synthetic/pdbtm_api_v1_test.json",
        "transformed_pdb": "data/synthetic/pdbtm_transformed_test.pdb",
    }.items():
        data = (ROOT / relative_path).read_bytes()
        assert payloads[role]["byte_size"] == len(data)
        assert payloads[role]["sha256"] == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize(
    "name",
    [
        ".local/provider.json",
        "reports/manual_export.json",
        "stage4a2_manual.json",
        "pdbtm.trpdb",
        ".pytest_cache/state",
        ".ruff_cache/state",
        "pkg/__pycache__/module.pyc",
        "pkg/module.pyc",
        "/absolute/path",
        "../parent/path",
        "C:/absolute/path",
        "..\\parent\\path",
    ],
)
def test_release_validator_rejects_unsafe_archive_names(name):
    with pytest.raises(ReleaseArtifactError, match="Forbidden release archive entry"):
        _assert_safe_archive_names([name])
