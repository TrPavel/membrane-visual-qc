import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

from scripts.build_plugin_zip import build_plugin_zip
from scripts.validate_release_artifacts import validate_release_artifacts


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_consistent_across_representative_artifacts(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "membrane_vqc_pymol-0.4.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("membrane_vqc/__init__.py", "")
        archive.writestr(
            "membrane_vqc_pymol-0.4.0.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: membrane-vqc-pymol\nVersion: 0.4.0\n",
        )

    sdist = dist / "membrane_vqc_pymol-0.4.0.tar.gz"
    root = "membrane_vqc_pymol-0.4.0"
    required = {
        "PKG-INFO": "Metadata-Version: 2.4\nName: membrane-vqc-pymol\nVersion: 0.4.0\n",
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

    build_plugin_zip(ROOT, dist / "MembraneVisualQC-0.4.0.zip")

    result = validate_release_artifacts(ROOT, dist)

    assert result["version"] == "0.4.0"
    assert result["reports"] == ["pdbtm_synthetic_mvqc.json"]
    assert set(result["schemas"]) == {"1.0", "1.1", "1.2", "1.3"}
    assert set(result["artifacts"]) == {
        "MembraneVisualQC-0.4.0.zip",
        "MembraneVisualQC-0.4.0.zip.sha256",
        "membrane_vqc_pymol-0.4.0-py3-none-any.whl",
        "membrane_vqc_pymol-0.4.0.tar.gz",
    }


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


def test_release_validator_rejects_report_exports_in_archives(tmp_path):
    from scripts.validate_release_artifacts import ReleaseArtifactError

    archive_path = tmp_path / "unsafe.whl"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("reports/manual_export.json", "{}")

    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()

    from scripts.validate_release_artifacts import _assert_safe_archive_names

    try:
        _assert_safe_archive_names(names)
    except ReleaseArtifactError as error:
        assert "reports/manual_export.json" in str(error)
    else:
        raise AssertionError("report export was accepted in a release archive")
