"""Upgrade compatibility harness: v0.6.0 -> the current 0.7.0.dev0 development build.

Two tiers of coverage, per the project's install/upgrade hardening scope:

1. CI-safe tests (always run, no network, no real PyMOL, no committed binary ZIP):
   - genuine small fixtures (tests/fixtures/v0.6.0/, tests/fixtures/v0.6.0_batch_result/,
     tests/fixtures/README.md documents their exact provenance) prove real v0.6.0 file
     identities and a real v0.6.0.dev0 batch-result bundle remain correctly readable;
   - a synthetic overlay-vs-clean-replacement mechanics test, built from two temporary
     copies of the *current* source tree with only the version string patched down for
     one of them. This is intentionally NOT a claim about v0.6.0's actual file contents
     (those are already covered by PR #25/#26's targeted regression tests) -- it isolates
     the *install-mechanics* question (does overlay extraction correctly replace files,
     leave anything stale, report the right version afterward) from content differences,
     which is what install/upgrade hardening actually needs to prove.

2. Local-only integration test (test_genuine_v060_upgrade_*): uses the real, verified
   MembraneVisualQC-0.6.0.zip when present at .local/release-v060-downloaded/ (the exact
   published asset, SHA-256 7126e51a...046960, matching docs/v0.6.0_release_evidence.json).
   Skipped, never faked, when that file is absent -- e.g. in ordinary CI, or a
   contributor's checkout that hasn't downloaded it. Run it locally with:
       python -m pytest tests/test_plugin_upgrade.py -k genuine_v060 -v

Finding recorded here for the record: comparing tests/fixtures/v0.6.0/PLUGIN_MANIFEST.json
against the current package's required-file set shows the file *set* is unchanged between
v0.6.0 and 0.7.0.dev0 -- only file *contents* changed (PR #25 report.py, PR #26
batch_paths.py/batch_contracts.py/batch_cli.py, and gui.py's earlier scrollable-tabs fix).
There is therefore no genuine "file removed between v0.6.0 and current" case to test with
real data; test_synthetic_overlay_upgrade_with_a_removed_file below uses a clearly-labeled
synthetic stale file to exercise that general risk class instead, since a real one does not
yet exist for this specific transition.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from scripts.build_plugin_zip import build_plugin_zip, project_version

ROOT = Path(__file__).resolve().parents[1]
V060_ZIP = ROOT / ".local" / "release-v060-downloaded" / "MembraneVisualQC-0.6.0.zip"
V060_ZIP_SHA256 = "7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960"
V060_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "v0.6.0"
V060_BATCH_RESULT_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "v0.6.0_batch_result" / "batch-result.json"
)


def _extract(zip_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)
    return destination / "membrane_vqc"


def _run_isolated(script: str, *, cwd: Path):
    import os

    return subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        cwd=cwd,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# CI-safe: genuine v0.6.0 identity fixtures
# ---------------------------------------------------------------------------


def test_v060_fixture_manifest_declares_v060_and_matches_its_checksums():
    manifest = json.loads((V060_FIXTURES / "PLUGIN_MANIFEST.json").read_text("utf-8"))
    assert manifest["plugin"]["version"] == "0.6.0"
    checksums = (V060_FIXTURES / "SHA256SUMS.txt").read_text("ascii")
    for entry in manifest["files"]:
        assert f"{entry['sha256']}  {entry['path']}" in checksums


def test_v060_file_set_is_identical_to_current_required_files():
    """No file was ever removed between v0.6.0 and the current development build -- this is
    why no genuine "stale removed file" fixture exists (see module docstring); this test pins
    that fact so it is caught explicitly if it ever changes.

    Files may legitimately be *added* (only ever additively -- an overlay install of a newer
    ZIP over an older install always writes every file the new version needs, so a pure
    addition cannot strand anything stale; see the overlay-safety tests below). The v0.9.0
    UI/UX polish session added exactly two new presentation-only modules,
    ``membrane_vqc/ui_theme.py`` and ``membrane_vqc/ui_components.py`` -- pinned explicitly
    below so any *other*, unexpected addition or any removal is still caught."""
    from scripts.build_plugin_zip import CHECKSUMS_NAME, MANIFEST_NAME, collect_plugin_files

    v060_manifest = json.loads((V060_FIXTURES / "PLUGIN_MANIFEST.json").read_text("utf-8"))
    v060_names = {entry["path"] for entry in v060_manifest["files"]} | {
        MANIFEST_NAME,
        CHECKSUMS_NAME,
    }
    current_names = {name for name, _ in collect_plugin_files(ROOT)} | {
        MANIFEST_NAME,
        CHECKSUMS_NAME,
    }
    expected_additions = {"membrane_vqc/ui_theme.py", "membrane_vqc/ui_components.py"}
    assert v060_names - current_names == set(), (
        f"removed since v0.6.0 (never expected): {v060_names - current_names}"
    )
    assert current_names - v060_names == expected_additions, (
        f"added since v0.6.0: {current_names - v060_names}, expected: {expected_additions}"
    )


# ---------------------------------------------------------------------------
# CI-safe: genuine v0.6.0.dev0 batch-result bundle remains inspectable
# ---------------------------------------------------------------------------


def test_genuine_v060_batch_result_bundle_remains_inspectable(tmp_path):
    from membrane_vqc.batch_result_browser import inspect_result_bundle

    working_copy = tmp_path / "bundle"
    shutil.copytree(V060_BATCH_RESULT_FIXTURE.parent, working_copy)

    bundle = inspect_result_bundle(working_copy / "batch-result.json")

    assert bundle.software_version == "0.6.0.dev0"
    assert bundle.overall_status == "COMPLETED_WITH_ERRORS"
    statuses = {job.job_id: job.status for job in bundle.jobs}
    assert statuses == {
        "legacy": "SUCCESS",
        "planar": "SUCCESS",
        "pdbtm-local": "SUCCESS",
        "pdbtm-cache": "INPUT_REJECTED",
        "comparison": "REVIEW_ITEMS",
    }
    verified_reports = {
        job.job_id: job.report.availability for job in bundle.jobs if job.report is not None
    }
    assert all(availability == "VERIFIED" for availability in verified_reports.values())


def test_genuine_v060_batch_result_reports_are_not_mutated_by_inspection(tmp_path):
    working_copy = tmp_path / "bundle"
    shutil.copytree(V060_BATCH_RESULT_FIXTURE.parent, working_copy)
    before = {p.name: p.read_bytes() for p in working_copy.iterdir()}

    from membrane_vqc.batch_result_browser import inspect_result_bundle

    inspect_result_bundle(working_copy / "batch-result.json")

    after = {p.name: p.read_bytes() for p in working_copy.iterdir()}
    assert before == after


# ---------------------------------------------------------------------------
# CI-safe: standalone historical schema-1.0 report survives an "upgrade" (it is not
# part of any package/install directory, so this really just re-confirms PR #25's fix
# still holds -- included here for completeness of the "existing data" audit).
# ---------------------------------------------------------------------------


def test_genuine_historical_schema_1_0_report_remains_readable_after_upgrade():
    from membrane_vqc.report import validate_report

    fixture = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "genuine_v0.1.0_schema_1_0_bad_core_lys_mvqc.json"
    )
    report = json.loads(fixture.read_text("utf-8"))
    validate_report(report)  # must not raise


# ---------------------------------------------------------------------------
# CI-safe: cache-v1 format compatibility across this specific upgrade
# ---------------------------------------------------------------------------


_V060_COMMIT = "58e89fed284139ea6e5d6be05a35fdeada591037"


def test_pdbtm_cache_module_is_byte_identical_since_v060():
    """membrane_vqc/pdbtm_cache.py and pdbtm_cache_contract.py were not touched by
    PR #25 or #26 -- this pins that fact via git history rather than assuming it.
    Combined with the round-trip test below, this is the evidence for
    docs/compatibility.md's claim that cache-v1 needs no migration for this
    specific upgrade: the code that reads and writes it has not changed at all.

    Skips (does not silently pass) when the v0.6.0 commit is unreachable, e.g. a
    shallow CI checkout (actions/checkout@v4 defaults to fetch-depth: 1). This was
    caught during implementation: `git diff <unreachable>..HEAD` exits 128 with its
    error on stderr, leaving stdout empty -- an earlier version of this test checked
    only `stdout.strip() == ""` and passed "successfully" on GitHub's shallow
    checkout without ever actually comparing anything.
    """
    import subprocess

    reachable = subprocess.run(
        ["git", "cat-file", "-e", f"{_V060_COMMIT}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if reachable.returncode != 0:
        pytest.skip(
            f"v0.6.0 commit {_V060_COMMIT} is not reachable in this checkout "
            "(likely a shallow clone); cannot compare against it here"
        )

    for relative in ("membrane_vqc/pdbtm_cache.py", "membrane_vqc/pdbtm_cache_contract.py"):
        diff = subprocess.run(
            ["git", "diff", "--stat", f"{_V060_COMMIT}..HEAD", "--", relative],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert diff.returncode == 0, f"git diff failed for {relative}: {diff.stderr}"
        assert diff.stdout.strip() == "", f"{relative} changed since v0.6.0:\n{diff.stdout}"


def test_cache_v1_written_before_upgrade_reads_back_correctly_after(tmp_path):
    """A cache-v1 tree is never stored inside the plugin install directory (see
    membrane_vqc.pdbtm_cache.select_cache_root: %LOCALAPPDATA%/MembraneVisualQC/Cache on
    Windows, independent of where membrane_vqc itself is installed), so an "upgrade" by
    definition never touches it directly. This proves the *format* is also still
    compatible: since pdbtm_cache.py is byte-identical to v0.6.0 (previous test), a cache
    entry written before the upgrade round-trips through the exact same code after it."""
    from dataclasses import dataclass

    from membrane_vqc.pdbtm_cache import CacheRepository

    @dataclass(frozen=True)
    class _Evidence:
        requested_url: str
        final_url: str
        status: int
        content_type: str
        charset: str | None
        content_encoding: str | None
        etag: str | None
        last_modified: str | None
        requested_at: str
        completed_at: str
        byte_size: int
        sha256: str
        tls_verified: bool = True

    @dataclass(frozen=True)
    class _Payload:
        role: str
        body: bytes
        evidence: _Evidence

    @dataclass(frozen=True)
    class _Versions:
        resource_version: str = "1017"
        software_version: str = "3.2.134"

    @dataclass(frozen=True)
    class _Candidate:
        canonical_record_id: str
        payloads: tuple
        provider_versions: _Versions = _Versions()

    def _payload(role, body, media_type, charset, second):
        suffix = "json" if role == "pdbtm_json" else "trpdb"
        url = f"https://pdbtm.unitmp.org/api/v1/entry/9zzz.{suffix}"
        return _Payload(
            role,
            body,
            _Evidence(
                url,
                url,
                200,
                media_type,
                charset,
                None,
                None,
                None,
                f"2026-07-21T00:00:0{second}.000000Z",
                f"2026-07-21T00:00:0{second + 1}.000000Z",
                len(body),
                __import__("hashlib").sha256(body).hexdigest(),
            ),
        )

    synthetic_dir = ROOT / "data" / "synthetic"
    json_bytes = (
        (synthetic_dir / "pdbtm_api_v1_test.json")
        .read_bytes()
        .replace(b'"pdb_id":"test"', b'"pdb_id":"9zzz"', 1)
    )
    pdb_bytes = (
        (synthetic_dir / "pdbtm_transformed_test.pdb").read_bytes().replace(b"TEST\n", b"9ZZZ\n", 1)
    )

    cache_root = tmp_path / "pre-upgrade-cache" / "pdbtm-api-v1" / "cache-v1"
    repository = CacheRepository(cache_root)
    candidate = _Candidate(
        "9zzz",
        (
            _payload("pdbtm_json", json_bytes, "application/json", None, 0),
            _payload("transformed_pdb", pdb_bytes, "text/plain", "utf-8", 2),
        ),
    )
    generation = repository.capture_record_generation("9zzz")
    repository.commit_validated_pair(candidate, expected_record_generation=generation)

    # Simulate "after the upgrade": a fresh repository object over the same cache
    # root, exactly as a newly-imported (post-upgrade) module would create.
    post_upgrade_repository = CacheRepository(cache_root)
    snapshot = post_upgrade_repository.read_active("9zzz")
    assert snapshot.canonical_record_id == "9zzz"
    assert snapshot.payloads[0] == json_bytes
    assert snapshot.payloads[1] == pdb_bytes


# ---------------------------------------------------------------------------
# CI-safe: synthetic overlay-vs-clean-replacement install mechanics
# ---------------------------------------------------------------------------


def _patched_source_tree(tmp_path: Path, label: str, version: str) -> Path:
    """A full temporary copy of the *current* source tree with only the version
    strings patched, used solely to isolate install *mechanics* (overlay vs clean
    replacement, version reporting, stale-file behavior) from file-content
    differences. Never claims to reproduce v0.6.0's actual historical file
    contents -- see the module docstring."""
    copy_root = tmp_path / f"source-{label}"
    shutil.copytree(ROOT / "membrane_vqc", copy_root / "membrane_vqc")
    shutil.copytree(ROOT / "schemas", copy_root / "schemas")
    shutil.copy2(ROOT / "pyproject.toml", copy_root / "pyproject.toml")

    pyproject = copy_root / "pyproject.toml"
    current_version = project_version(ROOT)
    pyproject.write_text(
        pyproject.read_text("utf-8").replace(
            f'version = "{current_version}"', f'version = "{version}"', 1
        ),
        encoding="utf-8",
    )
    constants = copy_root / "membrane_vqc" / "constants.py"
    constants.write_text(
        constants.read_text("utf-8").replace(
            f'VERSION = "{current_version}"', f'VERSION = "{version}"', 1
        ),
        encoding="utf-8",
    )
    return copy_root


def test_synthetic_overlay_upgrade_reports_the_new_version(tmp_path):
    old_source = _patched_source_tree(tmp_path, "old", "0.6.0")
    old_zip = build_plugin_zip(old_source, tmp_path / "old.zip")
    new_zip = build_plugin_zip(ROOT, tmp_path / "new.zip")

    install_parent = tmp_path / "install"
    _extract(old_zip, install_parent)  # "v0.6.0" installed first
    _extract(new_zip, install_parent)  # overlay: extract new zip over it, no cleanup

    neutral_cwd = tmp_path / "neutral"
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


def test_synthetic_overlay_upgrade_leaves_no_v060_content_since_file_sets_match(tmp_path):
    """For the real v0.6.0 -> current transition specifically (confirmed by
    test_v060_file_set_is_identical_to_current_required_files above: every v0.6.0 file is
    still required now, and any files added since -- e.g. the v0.9.0 UI/UX session's
    ui_theme.py/ui_components.py -- are pure additions, never removals), overlay extraction
    is safe: every file the old version wrote is also written by the new version, so nothing
    old survives. This does NOT generalize to a future version that removes a file -- see the
    synthetic-stale-file test below and docs/compatibility.md's overlay-vs-clean-replacement
    statement."""
    old_source = _patched_source_tree(tmp_path, "old2", "0.6.0")
    old_zip = build_plugin_zip(old_source, tmp_path / "old2.zip")
    new_zip = build_plugin_zip(ROOT, tmp_path / "new2.zip")

    install_parent = tmp_path / "install2"
    _extract(old_zip, install_parent)
    _extract(new_zip, install_parent)

    with zipfile.ZipFile(new_zip) as archive:
        expected_names = set(archive.namelist())
    on_disk = {
        str(Path(p).relative_to(install_parent).as_posix())
        for p in install_parent.rglob("*")
        if p.is_file()
    }
    assert on_disk == expected_names


def test_synthetic_overlay_upgrade_with_a_removed_file_leaves_it_stale(tmp_path):
    """Clearly synthetic (see module docstring: no real removed file exists yet for this
    transition). Proves the actual risk class overlay installs carry in general: a file
    the old version wrote and the new version no longer packages is NOT deleted by
    overlay extraction, and remains silently present. It does not shadow anything here
    because nothing imports it, but a future removed .py module that collides with a
    renamed/restructured import path could behave differently -- which is exactly why
    docs/compatibility.md recommends clean replacement as the supported model."""
    old_source = _patched_source_tree(tmp_path, "old3", "0.6.0")
    stale_file = old_source / "membrane_vqc" / "_hypothetical_removed_module.py"
    stale_file.write_text("# pretend this existed in an old version and was removed\n")
    old_zip = build_plugin_zip(old_source, tmp_path / "old3.zip")
    new_zip = build_plugin_zip(ROOT, tmp_path / "new3.zip")

    install_parent = tmp_path / "install3"
    _extract(old_zip, install_parent)
    assert (install_parent / "membrane_vqc" / "_hypothetical_removed_module.py").is_file()
    _extract(new_zip, install_parent)  # overlay only; nothing removes stale files

    stale_path = install_parent / "membrane_vqc" / "_hypothetical_removed_module.py"
    assert stale_path.is_file(), "overlay extraction does not delete removed files (expected)"

    # Detectable by comparing against the new install's own manifest, which is exactly
    # the check docs/upgrade_guide.md's troubleshooting section recommends.
    manifest = json.loads((install_parent / "membrane_vqc" / "PLUGIN_MANIFEST.json").read_text())
    manifest_paths = {entry["path"] for entry in manifest["files"]}
    assert "membrane_vqc/_hypothetical_removed_module.py" not in manifest_paths


# ---------------------------------------------------------------------------
# Local-only: genuine v0.6.0 ZIP integration test (skipped without the real file)
# ---------------------------------------------------------------------------

_missing_reason = (
    f"genuine v0.6.0 asset not found locally at {V060_ZIP}; this integration test "
    "only runs when a verified copy is present (see module docstring), it is never "
    "faked or reconstructed. Not required for CI."
)


@pytest.mark.skipif(not V060_ZIP.is_file(), reason=_missing_reason)
def test_genuine_v060_upgrade_clean_replacement(tmp_path):
    import hashlib

    actual_sha256 = hashlib.sha256(V060_ZIP.read_bytes()).hexdigest()
    assert actual_sha256 == V060_ZIP_SHA256, "local v0.6.0 asset does not match the published one"

    install_parent = tmp_path / "install"
    old_root = _extract(V060_ZIP, install_parent)
    assert old_root.is_dir()

    # Representative user-owned state that must survive the upgrade untouched, all
    # deliberately kept OUTSIDE the plugin install directory (matching the real
    # architecture: cache/output/history are never stored under membrane_vqc/).
    user_output_dir = tmp_path / "user-outputs"
    user_output_dir.mkdir()
    user_report = user_output_dir / "my_v060_report.json"
    user_report.write_text(V060_BATCH_RESULT_FIXTURE.read_text("utf-8"), encoding="utf-8")
    marker_before = user_report.read_bytes()

    # Clean replacement: remove the old install directory entirely, then extract fresh.
    shutil.rmtree(install_parent)
    new_zip = build_plugin_zip(ROOT, tmp_path / "new.zip")
    new_root = _extract(new_zip, install_parent)

    neutral_cwd = tmp_path / "neutral"
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
    assert new_root.is_dir()

    # User data untouched by the upgrade.
    assert user_report.read_bytes() == marker_before


@pytest.mark.skipif(not V060_ZIP.is_file(), reason=_missing_reason)
def test_genuine_v060_upgrade_overlay(tmp_path):
    install_parent = tmp_path / "install"
    _extract(V060_ZIP, install_parent)

    # Overlay: extract the new ZIP directly over the old install, no cleanup first.
    new_zip = build_plugin_zip(ROOT, tmp_path / "new.zip")
    _extract(new_zip, install_parent)

    neutral_cwd = tmp_path / "neutral"
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

    # Confirmed identical file sets (test_v060_file_set_is_identical_to_current_required_files)
    # mean overlay onto the *real* v0.6.0 install leaves nothing stale either.
    with zipfile.ZipFile(new_zip) as archive:
        expected_names = set(archive.namelist())
    on_disk = {
        str(Path(p).relative_to(install_parent).as_posix())
        for p in install_parent.rglob("*")
        if p.is_file()
    }
    assert on_disk == expected_names
