"""Lightweight consistency checks between the install/upgrade documentation and the
actual version/contract constants -- not a claim that the prose itself is correct, only
that it has not silently drifted from the values it describes."""

from __future__ import annotations

from pathlib import Path

from membrane_vqc.batch_contracts import PLAN_CONTRACT, RESULT_CONTRACT
from membrane_vqc.report import SUPPORTED_SCHEMA_VERSIONS
from scripts.build_plugin_zip import project_version

ROOT = Path(__file__).resolve().parents[1]


def test_readme_links_to_the_upgrade_guide_and_compatibility_statement():
    text = (ROOT / "README.md").read_text("utf-8")
    assert "docs/upgrade_guide.md" in text
    assert "docs/compatibility.md" in text


def test_upgrade_guide_names_the_supported_v060_upgrade_path():
    text = (ROOT / "docs" / "upgrade_guide.md").read_text("utf-8")
    assert "v0.6.0" in text
    assert "0.7.x" in text
    # The exact verified v0.6.0 asset identity must not silently drift from
    # docs/v0.6.0_release_evidence.json.
    assert "7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960" in text


def test_upgrade_guide_does_not_reference_a_stale_active_development_version():
    """The guide describes upgrading TO the current dev line; if the active version
    stops being 0.7.0.dev0, this is a reminder to revisit the guide's version-specific
    claims (it deliberately uses the generic "0.7.x" rather than the exact dev suffix,
    so this only pins the major.minor line, not every patch)."""
    version = project_version(ROOT)
    assert version.startswith("0.7."), (
        f"active version is now {version!r}; docs/upgrade_guide.md's 'v0.6.0 -> 0.7.x' "
        "framing needs a fresh look, not just this test updated"
    )


def test_compatibility_statement_matches_supported_schema_and_contract_versions():
    text = (ROOT / "docs" / "compatibility.md").read_text("utf-8")
    # docs/compatibility.md states the schema range in prose ("1.0 through 1.4"), not
    # as an enumerated list, so check the endpoints rather than every version string.
    assert min(SUPPORTED_SCHEMA_VERSIONS) in text
    assert max(SUPPORTED_SCHEMA_VERSIONS) in text
    assert "1.5" in text  # the separate comparison-report schema
    assert PLAN_CONTRACT in text
    assert RESULT_CONTRACT in text


def test_manual_checklist_exists_and_is_not_falsely_marked_complete():
    text = (ROOT / "docs" / "manual_install_upgrade_checklist.md").read_text("utf-8")
    assert "pending owner observation" in text
    # All three rounds (A, B, C) must be genuinely PENDING in the committed version of
    # this file -- marking one PASS without the owner having actually run it would be a
    # false completion claim (see the task's own explicit constraint on this point). The
    # "Result: **PASS**" string does legitimately appear once, in the "Recording
    # results" section's template explanation of the format to use later -- so check the
    # per-round markers specifically rather than searching for the substring's absence.
    assert text.count("Result: **PENDING**") >= 3  # at least Round A, B, and C
