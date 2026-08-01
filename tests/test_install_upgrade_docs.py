"""Lightweight consistency checks between the install/upgrade documentation and the
actual version/contract constants -- not a claim that the prose itself is correct, only
that it has not silently drifted from the values it describes."""

from __future__ import annotations

import json
from pathlib import Path

from membrane_vqc.batch_contracts import PLAN_CONTRACT, RESULT_CONTRACT
from membrane_vqc.report import SUPPORTED_SCHEMA_VERSIONS
from scripts.build_plugin_zip import project_version

ROOT = Path(__file__).resolve().parents[1]
MANUAL_VALIDATION_SOURCE_COMMIT = "28802a640f8eabd38f7e8afbb529da5a306bb68f"


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


def test_upgrade_guide_does_not_claim_an_untested_active_development_upgrade_path():
    """v0.7.0 has now been published as a real release (see docs/v0.7.0_release_evidence.json),
    so docs/upgrade_guide.md's "v0.6.0 -> 0.7.x" framing is no longer "the current dev
    line" -- it is a completed, harness-tested pair, and the prose remains accurate as
    written. What this test guards now is the *next* transition: nobody should silently
    extend the guide to claim 0.7.x -> 0.8.x is supported just because 0.8.x becomes the
    active development line -- see docs/upgrade_guide.md#1-supported-upgrade-path ("Any
    earlier version... not supported by this guide")."""
    text = (ROOT / "docs" / "upgrade_guide.md").read_text("utf-8")
    version = project_version(ROOT)
    assert version.startswith("0.8."), (
        f"active version is now {version!r}; if this no longer matches, either a new "
        "upgrade path has been harness-tested (update the guide and this test together) "
        "or this test itself is stale"
    )
    assert "0.8.x" not in text


def test_compatibility_statement_matches_supported_schema_and_contract_versions():
    text = (ROOT / "docs" / "compatibility.md").read_text("utf-8")
    # docs/compatibility.md states the schema range in prose ("1.0 through 1.4"), not
    # as an enumerated list, so check the endpoints rather than every version string.
    assert min(SUPPORTED_SCHEMA_VERSIONS) in text
    assert max(SUPPORTED_SCHEMA_VERSIONS) in text
    assert "1.5" in text  # the separate comparison-report schema
    assert PLAN_CONTRACT in text
    assert RESULT_CONTRACT in text


def test_manual_checklist_records_an_owner_observed_result_not_an_invented_one():
    """As of 2026-08-01 the owner actually ran the v0.6.0 -> 0.7.0.dev0 manual checklist
    and recorded PASS -- this is a genuine completion, not the false-completion case the
    original version of this test guarded against (marking a round PASS without the owner
    having run it). The checks below confirm the recorded result stays anchored to the
    exact artifacts the owner actually tested, so a future edit cannot silently drift the
    claim away from that evidence (for example, by bumping the hash to match a
    newer, untested ZIP) without this test catching it."""
    text = (ROOT / "docs" / "manual_install_upgrade_checklist.md").read_text("utf-8")
    assert "Status: **PASS**" in text
    assert "2026-08-01" in text
    for marker in ("Round A", "Round D", "Round E", "Round F", "## Overall result"):
        assert marker in text
    # The exact tested artifact identities must not silently drift from what was actually
    # verified -- see docs/v0.7.0_install_upgrade_manual_evidence.json and
    # docs/v0.6.0_release_evidence.json.
    assert "d11234fc3e74bbc7427d6bb18f36897bc86a9d27a9bfec134df9b623307d638c" in text
    assert "7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960" in text
    assert MANUAL_VALIDATION_SOURCE_COMMIT in text


def test_manual_evidence_json_matches_the_checklist_it_summarizes():
    checklist = (ROOT / "docs" / "manual_install_upgrade_checklist.md").read_text("utf-8")
    evidence_path = ROOT / "docs" / "v0.7.0_install_upgrade_manual_evidence.json"
    assert evidence_path.is_file(), "expected a structured evidence file alongside the checklist"
    evidence = json.loads(evidence_path.read_text("utf-8"))
    assert evidence["source_commit"] in checklist
    assert evidence["development_artifact"]["sha256"] in checklist
    assert evidence["stable_artifact"]["sha256"] in checklist
    assert all(result == "PASS" for result in evidence["rounds"].values())
    assert all(flag is False for flag in evidence["observations"].values())
