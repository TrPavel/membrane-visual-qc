import hashlib
import json
import zipfile

import pytest

from scripts.build_plugin_zip import (
    CHECKSUMS_NAME,
    FIXED_ZIP_TIMESTAMP,
    MANIFEST_NAME,
    PluginZipError,
    REQUIRED_PACKAGE_FILES,
    build_plugin_zip,
    sha256_file,
    validate_zip_layout,
)


def make_project(tmp_path):
    (tmp_path / "membrane_vqc").mkdir()
    required = {name.removeprefix("membrane_vqc/") for name in REQUIRED_PACKAGE_FILES}
    for name in (*sorted(required), "core.py"):
        (tmp_path / "membrane_vqc" / name).write_text(f"# {name}\n", encoding="utf-8")
    (tmp_path / "membrane_vqc" / "__pycache__").mkdir()
    (tmp_path / "membrane_vqc" / "__pycache__" / "core.pyc").write_bytes(b"cache")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_core.py").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    return tmp_path


def test_builder_rejects_known_provider_payload_content(tmp_path, monkeypatch):
    root = make_project(tmp_path)
    payload = b"official-provider-body-for-test"
    identity = (len(payload), hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr("scripts.build_plugin_zip.FORBIDDEN_PROVIDER_PAYLOADS", {identity})
    (root / "membrane_vqc" / "renamed.json").write_bytes(payload)

    with pytest.raises(PluginZipError, match="Official provider payload"):
        build_plugin_zip(root)


def test_builder_produces_expected_minimal_layout_and_hashes(tmp_path):
    root = make_project(tmp_path)
    output = build_plugin_zip(root)

    manifest = validate_zip_layout(output)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert MANIFEST_NAME in names
        assert CHECKSUMS_NAME in names
        assert {name.split("/", 1)[0] for name in names} == {"membrane_vqc"}
        assert "membrane_vqc/core.py" in names
        assert not any("__pycache__" in name or name.startswith("tests/") for name in names)
        assert all(info.date_time == FIXED_ZIP_TIMESTAMP for info in archive.infolist())

    assert manifest["plugin"]["version"] == "1.2.3"
    sidecar = output.with_suffix(".zip.sha256").read_text(encoding="ascii")
    assert sidecar == f"{sha256_file(output)}  {output.name}\n"


def test_builder_is_byte_for_byte_deterministic(tmp_path):
    root = make_project(tmp_path)
    first = build_plugin_zip(root, root / "dist" / "first.zip")
    second = build_plugin_zip(root, root / "dist" / "second.zip")

    assert first.read_bytes() == second.read_bytes()


def test_validator_rejects_unexpected_top_level_file(tmp_path):
    archive_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("README.md", "unexpected")

    with pytest.raises(PluginZipError, match="manifest"):
        validate_zip_layout(archive_path)


def test_validator_rejects_metadata_at_zip_root(tmp_path):
    output = build_plugin_zip(make_project(tmp_path))
    invalid = tmp_path / "root-metadata.zip"
    with zipfile.ZipFile(output) as source, zipfile.ZipFile(invalid, "w") as target:
        for info in source.infolist():
            name = info.filename
            if name == MANIFEST_NAME:
                name = "PLUGIN_MANIFEST.json"
            elif name == CHECKSUMS_NAME:
                name = "SHA256SUMS.txt"
            target.writestr(name, source.read(info.filename))

    with pytest.raises(PluginZipError, match="manifest"):
        validate_zip_layout(invalid)


def test_validator_rejects_content_tampering(tmp_path):
    output = build_plugin_zip(make_project(tmp_path))
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(output) as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "membrane_vqc/core.py":
                data += b"# changed\n"
            target.writestr(info, data)

    with pytest.raises(PluginZipError, match="hash or size mismatch"):
        validate_zip_layout(tampered)


def test_manifest_is_stable_json_and_lists_only_package_files(tmp_path):
    output = build_plugin_zip(make_project(tmp_path))
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read(MANIFEST_NAME))

    assert [entry["path"] for entry in manifest["files"]] == sorted(
        [*REQUIRED_PACKAGE_FILES, "membrane_vqc/core.py"]
    )
