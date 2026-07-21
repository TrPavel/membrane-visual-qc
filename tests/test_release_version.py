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
    STAGE4B1_RUNTIME_MODULES,
    STAGE4B2_RUNTIME_MODULES,
    _assert_safe_archive_names,
    _assert_safe_archive_payload,
    _validate_version_agreement,
    validate_current_development_artifacts,
    validate_release_candidate_artifacts,
    verify_frozen_v040_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


def test_release_validator_rejects_known_provider_payload_content(monkeypatch):
    payload = b"official-provider-body-for-release-test"
    identity = (len(payload), hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(
        "scripts.validate_release_artifacts.FORBIDDEN_PROVIDER_PAYLOADS", {identity}
    )
    with pytest.raises(ReleaseArtifactError, match="Official provider payload"):
        _assert_safe_archive_payload("renamed.bin", payload)


def _copy_project_with_version(tmp_path, version):
    project = tmp_path / "alternate-project"
    project.mkdir()
    shutil.copytree(ROOT / "membrane_vqc", project / "membrane_vqc")
    shutil.copy2(ROOT / "pyproject.toml", project / "pyproject.toml")
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'version = "0.5.0.dev0"', f'version = "{version}"', 1
        ),
        encoding="utf-8",
    )
    constants = project / "membrane_vqc" / "constants.py"
    constants.write_text(
        constants.read_text(encoding="utf-8").replace(
            'VERSION = "0.5.0.dev0"', f'VERSION = "{version}"', 1
        ),
        encoding="utf-8",
    )
    return project


def test_version_agreement_imports_the_supplied_alternate_project(tmp_path):
    from membrane_vqc.constants import VERSION as ambient_version

    version = "9.9.9.dev0"
    project = _copy_project_with_version(tmp_path, version)

    result = _validate_version_agreement(project, version)

    assert ambient_version != version
    assert result["pyproject"] == version
    assert result["constants"] == version
    assert result["package"] == version
    assert Path(result["file"]).is_relative_to(project / "membrane_vqc")


def test_version_agreement_reports_all_target_version_values(tmp_path):
    project = _copy_project_with_version(tmp_path, "9.9.9.dev0")
    constants = project / "membrane_vqc" / "constants.py"
    constants.write_text(
        constants.read_text(encoding="utf-8").replace(
            'VERSION = "9.9.9.dev0"', 'VERSION = "9.9.8.dev0"', 1
        ),
        encoding="utf-8",
    )
    package_init = project / "membrane_vqc" / "__init__.py"
    package_init.write_text(
        package_init.read_text(encoding="utf-8") + '\n__version__ = "9.9.7.dev0"\n',
        encoding="utf-8",
    )

    with pytest.raises(ReleaseArtifactError) as captured:
        _validate_version_agreement(project, "9.9.9.dev0")

    message = str(captured.value)
    assert "pyproject=9.9.9.dev0" in message
    assert "constants=9.9.8.dev0" in message
    assert "package=9.9.7.dev0" in message


def test_version_agreement_rejects_package_from_wrong_origin(tmp_path, monkeypatch):
    project = tmp_path / "alternate-project"
    project.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", project / "pyproject.toml")
    monkeypatch.setenv("PYTHONPATH", str(ROOT))

    with pytest.raises(ReleaseArtifactError, match="resolved outside") as captured:
        _validate_version_agreement(project, "0.5.0.dev0")

    assert str(ROOT / "membrane_vqc") in str(captured.value)
    assert str(project / "membrane_vqc") in str(captured.value)


def test_version_agreement_wraps_broken_target_package(tmp_path):
    project = _copy_project_with_version(tmp_path, "9.9.9.dev0")
    (project / "membrane_vqc" / "__init__.py").write_text(
        "this is not valid Python !!!\n", encoding="utf-8"
    )

    with pytest.raises(ReleaseArtifactError, match="Could not inspect target package"):
        _validate_version_agreement(project, "9.9.9.dev0")


def test_release_version_is_consistent_across_representative_artifacts(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    version = "0.5.0.dev0"
    wheel = dist / f"membrane_vqc_pymol-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("membrane_vqc/__init__.py", "")
        for module in sorted(STAGE4B1_RUNTIME_MODULES | STAGE4B2_RUNTIME_MODULES):
            archive.writestr(module, "")
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
        "schemas/mvqc-report-1.4.schema.json": "{}",
    }
    required.update({module: "" for module in STAGE4B1_RUNTIME_MODULES | STAGE4B2_RUNTIME_MODULES})
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
    assert set(result["schemas"]) == {"1.0", "1.1", "1.2", "1.3", "1.4"}


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
