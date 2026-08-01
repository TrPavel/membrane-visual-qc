"""Clean-install compatibility harness: build the deterministic Plugin ZIP, extract it
into an isolated simulated install directory, and prove the package behaves correctly
from *that* location -- not from the repository source tree.

Distinguishing this from the existing tests/test_stage4*_package_safety.py files:
those run `sys.executable -c script` with `cwd=ROOT`, which puts the *repository's own*
membrane_vqc/ package on sys.path (Python adds cwd as sys.path[0] for `-c` scripts) --
they prove the source tree is import-safe, not that an installed copy is. Every
subprocess here instead runs with `-I` (isolated mode: ignores PYTHONPATH/PYTHONHOME
and skips the user site directory, while keeping ordinary site-packages) from a neutral
cwd that contains no membrane_vqc package of its own, with sys.path seeded only with the
extracted install directory. A stale membrane_vqc already in this test-runner process's
own sys.modules cannot leak in either, since each check is a fresh subprocess.

What is and is not covered here (see docs/compatibility.md for the full picture):
- covered: ZIP layout/manifest/checksum integrity, version agreement across
  pyproject.toml/constants.py/PLUGIN_MANIFEST.json, PyMOL-free import safety and schema
  resource availability from the extracted install location, no network/cache/output
  side effects on import, spaces/Unicode install paths.
- not covered (delegated to PyMOL's own Plugin Manager, requires a real PyMOL session):
  the graphical "Install New Plugin" flow itself, the exact directory PyMOL chooses,
  whether Qt menu registration actually appears. See the manual checklist in
  docs/manual_install_upgrade_checklist.md.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from scripts.build_plugin_zip import build_plugin_zip, project_version, validate_zip_layout

ROOT = Path(__file__).resolve().parents[1]


def _build_fresh_zip(tmp_path: Path) -> Path:
    """Build the deterministic Plugin ZIP fresh, never reusing a stale dist/ file."""
    return build_plugin_zip(ROOT, tmp_path / "build" / "MembraneVisualQC-fresh.zip")


def _extract(zip_path: Path, destination: Path) -> Path:
    """Extract the ZIP with zipfile's own traversal-safe extraction; returns the
    top-level membrane_vqc/ directory (the plugin's real install root)."""
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)
    return destination / "membrane_vqc"


def _run_isolated(script: str, *, cwd: Path, env_extra: dict[str, str] | None = None):
    """Run `script` in a fresh, isolated interpreter: -I ignores PYTHONPATH/PYTHONHOME
    and the user site directory, so nothing from this test process or the developer's
    environment can leak in. `cwd` must contain no membrane_vqc package of its own."""
    import os

    environment = os.environ.copy()
    environment.update(env_extra or {})
    return subprocess.run(
        # -I: isolated mode (ignores PYTHONPATH/PYTHONHOME and skips user site).
        # -B: never write .pyc bytecode cache, so "did import touch the install
        # directory" checks are meaningful rather than tripping on CPython's own
        # normal (and here irrelevant) bytecode caching.
        [sys.executable, "-I", "-B", "-c", script],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# ZIP layout, manifest, and checksum integrity
# ---------------------------------------------------------------------------


def test_fresh_zip_passes_its_own_layout_validation(tmp_path):
    zip_path = _build_fresh_zip(tmp_path)
    manifest = validate_zip_layout(zip_path)
    assert manifest["plugin"]["version"] == project_version(ROOT)


def test_extracted_layout_has_no_traversal_duplicate_or_symlink_entries(tmp_path):
    zip_path = _build_fresh_zip(tmp_path)
    with zipfile.ZipFile(zip_path) as archive:
        names = [info.filename for info in archive.infolist()]
    assert len(names) == len(set(names)), "duplicate ZIP entries"
    for name in names:
        assert not name.startswith("/"), name
        assert ".." not in Path(name).parts, name
        assert "\\" not in name, name


def test_extracted_layout_has_no_unexpected_generated_files(tmp_path):
    zip_path = _build_fresh_zip(tmp_path)
    install_root = _extract(zip_path, tmp_path / "install")
    for path in install_root.rglob("*"):
        if path.is_dir():
            continue
        assert path.suffix not in {".pyc", ".pyo"}, path
        assert "__pycache__" not in path.parts, path
        assert not path.name.startswith("."), path


def test_plugin_manifest_is_valid_and_matches_every_packaged_file(tmp_path):
    zip_path = _build_fresh_zip(tmp_path)
    install_root = _extract(zip_path, tmp_path / "install")

    manifest = json.loads((install_root / "PLUGIN_MANIFEST.json").read_text("utf-8"))
    assert manifest["format_version"] == 1
    for entry in manifest["files"]:
        # entry["path"] is archive-relative ("membrane_vqc/foo.py"); the extracted
        # root passed in is already .../install/membrane_vqc, so strip one segment.
        relative = Path(entry["path"])
        on_disk = install_root.parent / relative
        assert on_disk.is_file(), on_disk
        data = on_disk.read_bytes()
        import hashlib

        assert hashlib.sha256(data).hexdigest() == entry["sha256"], relative
        assert len(data) == entry["size"], relative


def test_sha256sums_matches_every_packaged_file(tmp_path):
    zip_path = _build_fresh_zip(tmp_path)
    install_root = _extract(zip_path, tmp_path / "install")

    checksums_text = (install_root / "SHA256SUMS.txt").read_text("ascii")
    lines = [line for line in checksums_text.splitlines() if line]
    assert lines, "SHA256SUMS.txt must not be empty"
    import hashlib

    for line in lines:
        digest, _, relative = line.partition("  ")
        on_disk = install_root.parent / relative
        assert on_disk.is_file(), on_disk
        assert hashlib.sha256(on_disk.read_bytes()).hexdigest() == digest, relative


# ---------------------------------------------------------------------------
# Version agreement
# ---------------------------------------------------------------------------


def test_version_agrees_across_pyproject_constants_and_manifest(tmp_path):
    zip_path = _build_fresh_zip(tmp_path)
    install_root = _extract(zip_path, tmp_path / "install")

    pyproject_version = project_version(ROOT)
    constants_text = (install_root / "constants.py").read_text("utf-8")
    import re

    constants_version = re.search(r'^VERSION = "([^"]+)"$', constants_text, re.MULTILINE).group(1)
    manifest = json.loads((install_root / "PLUGIN_MANIFEST.json").read_text("utf-8"))

    assert pyproject_version == constants_version == manifest["plugin"]["version"]


# ---------------------------------------------------------------------------
# Import safety from the extracted install location (never the source tree)
# ---------------------------------------------------------------------------


def test_package_imports_from_extracted_install_not_source_tree(tmp_path):
    zip_path = _build_fresh_zip(tmp_path)
    install_root = _extract(zip_path, tmp_path / "install")
    neutral_cwd = tmp_path / "neutral"
    neutral_cwd.mkdir()

    script = f"""
import sys
sys.path.insert(0, {str(install_root.parent)!r})
import membrane_vqc
assert membrane_vqc.__file__.startswith({str(install_root)!r}), membrane_vqc.__file__
print("VERSION=" + membrane_vqc.__version__)
"""
    completed = _run_isolated(script, cwd=neutral_cwd)
    assert completed.returncode == 0, completed.stderr
    assert f"VERSION={project_version(ROOT)}" in completed.stdout


def test_import_never_opens_a_socket_writes_cache_or_imports_ui(tmp_path):
    """Module-level import only -- deliberately does NOT call __init_plugin__() here.
    See test_init_plugin_entrypoint_is_safe_from_installed_location below for why:
    __init_plugin__() legitimately imports the real `pymol` package when one is
    present (as it is on this dev machine, via the bundled PyMOL2 installation), and
    that package's own bundled ssl/socks modules are incompatible with a
    process-wide socket.socket monkeypatch -- an environment quirk in PyMOL's own
    dependencies, already documented as pre-existing and unrelated in
    tests/test_stage4b3_package_safety.py, not something membrane_vqc controls."""
    zip_path = _build_fresh_zip(tmp_path)
    install_root = _extract(zip_path, tmp_path / "install")
    neutral_cwd = tmp_path / "neutral2"
    neutral_cwd.mkdir()
    cache_root = tmp_path / "must-not-exist"

    script = f"""
import socket, sys

def forbidden_socket(*args, **kwargs):
    raise AssertionError("socket creation during import")

socket.socket = forbidden_socket
sys.path.insert(0, {str(install_root.parent)!r})
import membrane_vqc
import membrane_vqc.batch_contracts
import membrane_vqc.batch_paths
import membrane_vqc.orientation_io
for forbidden in ("pymol", "PyQt5", "PySide2", "PySide6", "membrane_vqc.gui", "membrane_vqc.commands"):
    assert forbidden not in sys.modules, forbidden
print("OK")
"""
    completed = _run_isolated(
        script, cwd=neutral_cwd, env_extra={"MVQC_CACHE_DIR": str(cache_root)}
    )
    assert completed.returncode == 0, completed.stderr
    assert "OK" in completed.stdout
    assert not cache_root.exists()
    assert list(install_root.parent.rglob("*.pyc")) == []


def test_init_plugin_entrypoint_is_safe_from_installed_location(tmp_path):
    """Mirrors the existing tests/test_plugin_entrypoint.py::
    test_plugin_entrypoint_is_safe_without_pymol, but from an extracted install
    directory rather than the source tree, and without restricting sockets (that
    is PyMOL's own concern once __init_plugin__ legitimately reaches it, not
    membrane_vqc's -- see the note above)."""
    zip_path = _build_fresh_zip(tmp_path)
    install_root = _extract(zip_path, tmp_path / "install")
    neutral_cwd = tmp_path / "neutral2b"
    neutral_cwd.mkdir()

    script = f"""
import sys
sys.path.insert(0, {str(install_root.parent)!r})
import membrane_vqc
membrane_vqc.__init_plugin__()
print("OK")
"""
    completed = _run_isolated(script, cwd=neutral_cwd)
    assert completed.returncode == 0, completed.stderr
    assert "OK" in completed.stdout


def test_schemas_are_reachable_by_path_from_the_extracted_install(tmp_path):
    zip_path = _build_fresh_zip(tmp_path)
    install_root = _extract(zip_path, tmp_path / "install")
    neutral_cwd = tmp_path / "neutral3"
    neutral_cwd.mkdir()

    script = f"""
import sys
sys.path.insert(0, {str(install_root.parent)!r})
from membrane_vqc.batch_contracts import _schema_path
for name in (
    "mvqc-report-1.1.schema.json",
    "mvqc-report-1.5.schema.json",
    "mvqc-batch-plan-1.0.schema.json",
    "mvqc-batch-result-1.0.schema.json",
):
    path = _schema_path(name)
    assert path.is_file(), (name, path)
    assert str(path).startswith({str(install_root)!r}), path
print("OK")
"""
    completed = _run_isolated(script, cwd=neutral_cwd)
    assert completed.returncode == 0, completed.stderr
    assert "OK" in completed.stdout


# ---------------------------------------------------------------------------
# Spaces and Unicode in the install path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dirname",
    [
        "Program Files (x86)",
        "Пример_ünïcödé_日本語",
    ],
    ids=["spaces", "unicode"],
)
def test_install_path_with_spaces_or_unicode_works(tmp_path, dirname):
    zip_path = _build_fresh_zip(tmp_path)
    install_parent = tmp_path / dirname / "plugins"
    install_root = _extract(zip_path, install_parent)
    neutral_cwd = tmp_path / "neutral4"
    neutral_cwd.mkdir()

    script = f"""
import sys
sys.path.insert(0, {str(install_parent)!r})
import membrane_vqc
print("VERSION=" + membrane_vqc.__version__)
"""
    completed = _run_isolated(script, cwd=neutral_cwd)
    assert completed.returncode == 0, completed.stderr
    assert f"VERSION={project_version(ROOT)}" in completed.stdout
    assert install_root.is_dir()
