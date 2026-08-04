"""Consistency checks for the consolidated user-facing documentation set added alongside
docs/index.md. These check facts, required links, and literal synchronization with code --
not prose or formatting -- so they stay meaningful as the docs are edited going forward."""

from __future__ import annotations

import re
from pathlib import Path

from membrane_vqc.batch_contracts import MODES, PLAN_CONTRACT, RESULT_CONTRACT, STATUSES
from membrane_vqc.batch_gui import BATCH_STATES
from membrane_vqc.constants import VERSION
from membrane_vqc.pdbtm_errors import Stage4BErrorCode

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _read(*parts: str) -> str:
    return Path(ROOT, *parts).read_text("utf-8")


def _local_link_targets(text: str) -> list[str]:
    targets = []
    for target in _LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        targets.append(target.split("#", 1)[0])
    return [target for target in targets if target]


def _sentence_windows(text: str, phrase: str) -> list[str]:
    """Return a generous context window around each case-insensitive occurrence of
    *phrase*, wide enough to include a negating word/label from an earlier sentence or
    list header (e.g. "Does not cover:" followed by a bullet)."""
    windows = []
    lowered = text.lower()
    needle = phrase.lower()
    start = 0
    while (index := lowered.find(needle, start)) != -1:
        windows.append(text[max(0, index - 200) : index + len(phrase) + 20])
        start = index + len(needle)
    return windows


_NEGATION = re.compile(r"\b(not|no|never|n't|without)\b", re.IGNORECASE)


def _assert_always_negated(text: str, phrase: str, *, doc_name: str) -> None:
    windows = _sentence_windows(text, phrase)
    for window in windows:
        assert _NEGATION.search(window), (
            f"{doc_name} uses {phrase!r} without an apparent negation nearby -- context: {window!r}"
        )


def _assert_never_present(text: str, phrase: str, *, doc_name: str) -> None:
    assert phrase.lower() not in text.lower(), f"{doc_name} must never use the phrase {phrase!r}"


# ---------------------------------------------------------------------------
# 1. docs/index.md exists, and every canonical user-facing document it lists exists
# ---------------------------------------------------------------------------


def test_docs_index_exists():
    assert (DOCS / "index.md").is_file()


_CANONICAL_USER_DOCS = (
    "quick_start.md",
    "tutorial.md",
    "pdbtm_offline_import.md",
    "batch_plan_reference.md",
    "five_mode_walkthrough.md",
    "troubleshooting.md",
    "outputs_and_manifests.md",
    "report_schema.md",
    "status_vocabulary.md",
    "offline_and_safety.md",
    "scientific_interpretation.md",
    "known_limitations.md",
    "compatibility.md",
    "compatibility_matrix.md",
    "upgrade_guide.md",
    "manual_install_upgrade_checklist.md",
    "v1.0_contract_freeze.md",
    "versioning_policy.md",
    "release_checklist.md",
    "scientific_background.md",
)


def test_every_canonical_user_doc_exists():
    for name in _CANONICAL_USER_DOCS:
        assert (DOCS / name).is_file(), f"canonical document docs/{name} is missing"


def test_docs_index_lists_every_canonical_user_doc():
    text = _read("docs", "index.md")
    for name in _CANONICAL_USER_DOCS:
        assert name in text, f"docs/index.md does not list docs/{name}"


# ---------------------------------------------------------------------------
# 2 & 3. README/docs-index links resolve, and every local link in every doc resolves
# ---------------------------------------------------------------------------


def test_readme_local_links_resolve():
    text = _read("README.md")
    for target in _local_link_targets(text):
        resolved = (ROOT / target).resolve()
        assert resolved.is_file(), f"README.md links to missing file: {target}"


def test_docs_index_local_links_resolve():
    text = _read("docs", "index.md")
    for target in _local_link_targets(text):
        resolved = (DOCS / target).resolve()
        assert resolved.is_file() or resolved.is_dir(), (
            f"docs/index.md links to missing file/directory: {target}"
        )


def test_all_local_markdown_links_in_every_doc_resolve():
    files = list(DOCS.rglob("*.md")) + [ROOT / "README.md"]
    broken = []
    for path in files:
        text = path.read_text("utf-8")
        for target in _local_link_targets(text):
            resolved = (path.parent / target).resolve()
            if not (resolved.is_file() or resolved.is_dir()):
                broken.append((str(path.relative_to(ROOT)), target))
    assert not broken, f"broken local markdown link(s): {broken}"


# ---------------------------------------------------------------------------
# 4. canonical docs cross-link appropriately
# ---------------------------------------------------------------------------


def test_batch_plan_reference_and_five_mode_walkthrough_cross_link():
    reference = _read("docs", "batch_plan_reference.md")
    walkthrough = _read("docs", "five_mode_walkthrough.md")
    assert "five_mode_walkthrough.md" in reference
    assert "batch_plan_reference.md" in walkthrough


def test_scientific_interpretation_and_known_limitations_cross_link():
    interpretation = _read("docs", "scientific_interpretation.md")
    limitations = _read("docs", "known_limitations.md")
    assert "known_limitations.md" in interpretation
    assert "scientific_interpretation.md" in limitations


def test_quick_start_links_tutorial_and_offline_and_safety():
    text = _read("docs", "quick_start.md")
    assert "tutorial.md" in text
    assert "offline_and_safety.md" in text or "scientific_interpretation.md" in text


# ---------------------------------------------------------------------------
# 5. no user-facing doc references an obsolete development version as current
# ---------------------------------------------------------------------------

_ACTIVE_VERSION_CLAIM = re.compile(
    r"Active source development has version `([^`]+)`", re.IGNORECASE
)


def test_no_user_facing_doc_claims_a_stale_active_development_version():
    """README states "Active source development has version `X.Y.Z.devN`" only while
    the active version actually has a .devN suffix -- during a release-preparation
    window the version is bumped to a plain X.Y.Z with no distinct "active dev" line
    to state (see docs/release_checklist.md Phase 1), so this sentence's absence is
    not itself a staleness signal. What must never happen is the sentence naming a
    version that disagrees with the real one."""
    text = _read("README.md")
    matches = _ACTIVE_VERSION_CLAIM.findall(text)
    for claimed in matches:
        assert claimed == VERSION, (
            f"README.md claims active development version {claimed!r}, "
            f"but membrane_vqc.constants.VERSION is {VERSION!r}"
        )


# ---------------------------------------------------------------------------
# 6. no user-facing doc claims schema 1.0 -> 1.1 was additive
# ---------------------------------------------------------------------------


def test_no_doc_claims_the_1_0_to_1_1_transition_was_additive():
    for relative in ("docs/report_schema.md", "docs/v1.0_contract_freeze.md"):
        text = _read(*relative.split("/"))
        for window in _sentence_windows(text, "1.0"):
            if "1.1" in window and "additive" in window.lower():
                assert re.search(r"\b(not|did not|didn't)\b", window, re.IGNORECASE), (
                    f"{relative} appears to claim the 1.0->1.1 transition was additive "
                    f"without qualification -- context: {window!r}"
                )


# ---------------------------------------------------------------------------
# 7. no user-facing doc claims session history persists
#    (see test_no_doc_claims_persistent_session_history further below, which needs
#    _USER_FACING_DOCS defined after this point in the file)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 8. no user-facing doc claims batch manifests accept schema-1.0 standalone reports
# ---------------------------------------------------------------------------


def test_no_doc_claims_batch_accepts_schema_1_0_reports():
    for relative in ("docs/outputs_and_manifests.md", "docs/batch_plan_reference.md"):
        text = _read(*relative.split("/"))
        assert "schema 1.0" not in text.lower() and '"1.0"' not in text, (
            f"{relative} should not reference schema 1.0 in a batch/manifest context -- "
            "no batch mode ever produces schema 1.0"
        )


# ---------------------------------------------------------------------------
# 9. status vocabulary literals match current schema/code enums
# ---------------------------------------------------------------------------


def test_status_vocabulary_matches_batch_job_statuses():
    text = _read("docs", "status_vocabulary.md")
    for status in STATUSES:
        assert f"`{status}`" in text, f"docs/status_vocabulary.md is missing job status {status!r}"


def test_status_vocabulary_matches_batch_gui_states():
    text = _read("docs", "status_vocabulary.md")
    for state in BATCH_STATES:
        assert f"`{state}`" in text, f"docs/status_vocabulary.md is missing GUI state {state!r}"


def test_status_vocabulary_matches_cache_error_codes():
    text = _read("docs", "status_vocabulary.md")
    for code in Stage4BErrorCode:
        assert f"`{code.value}`" in text, (
            f"docs/status_vocabulary.md is missing cache/provider error code {code.value!r}"
        )


# ---------------------------------------------------------------------------
# 10. batch mode names match frozen values
# ---------------------------------------------------------------------------


def test_batch_plan_reference_lists_every_frozen_mode():
    text = _read("docs", "batch_plan_reference.md")
    for mode in MODES:
        assert f"`{mode}`" in text, f"docs/batch_plan_reference.md is missing mode {mode!r}"


# ---------------------------------------------------------------------------
# 11. outputs/manifests guide mentions current manifest filename and contract version
# ---------------------------------------------------------------------------


def test_outputs_guide_mentions_manifest_filename_and_contract():
    text = _read("docs", "outputs_and_manifests.md")
    assert "batch-result.json" in text
    assert RESULT_CONTRACT in text
    assert PLAN_CONTRACT in text


# ---------------------------------------------------------------------------
# 12. upgrade guide links to compatibility and troubleshooting
# ---------------------------------------------------------------------------


def test_upgrade_guide_links_compatibility_and_troubleshooting():
    text = _read("docs", "upgrade_guide.md")
    assert "compatibility.md" in text
    assert "troubleshooting.md" in text


# ---------------------------------------------------------------------------
# 13. quick start links to batch-plan and output guides
# ---------------------------------------------------------------------------


def test_quick_start_links_batch_plan_and_outputs():
    text = _read("docs", "quick_start.md")
    assert "batch_plan_reference.md" in text
    assert "outputs_and_manifests.md" in text


# ---------------------------------------------------------------------------
# 14. internal stage documents are not presented as the main documentation entry
# ---------------------------------------------------------------------------

_SEMI_CANONICAL_STAGE_DOCS = {
    "stage4c_source_comparison.md",
    "stage5a_batch_review.md",
    "stage5b_gui_batch.md",
}


def test_internal_stage_documents_are_not_in_primary_navigation():
    text = _read("docs", "index.md")
    governance_start = text.index("## Developer/release")
    primary_navigation = text[:governance_start]
    stage_link_re = re.compile(r"\]\((stage\d[^)]*\.md)\)")
    linked_in_primary_nav = set(stage_link_re.findall(primary_navigation))
    unexpected = linked_in_primary_nav - _SEMI_CANONICAL_STAGE_DOCS
    assert not unexpected, (
        f"internal stage document(s) linked outside Developer/release: {unexpected}"
    )


def test_stage_documents_are_headed_with_a_status_note():
    stage_docs = sorted(DOCS.glob("stage*.md"))
    assert stage_docs, "expected at least one stage-named document"
    for path in stage_docs:
        text = path.read_text("utf-8")
        assert "> **" in text.split("\n\n")[0] + text.split("\n\n")[1], (
            f"{path.name} is missing its internal/historical/technical-reference status header"
        )


# ---------------------------------------------------------------------------
# 15. all new canonical documents are included in the documentation index
#     (covered by test_docs_index_lists_every_canonical_user_doc above)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 3 (troubleshooting). troubleshooting guide exists and contains required major topics
# ---------------------------------------------------------------------------


def test_troubleshooting_guide_covers_required_topics():
    text = _read("docs", "troubleshooting.md")
    for heading in (
        "## Installation",
        "## GUI",
        "## Plans",
        "## Batch execution",
        "## Reports/results",
        "## Networking/cache",
        "## Scientific interpretation",
    ):
        assert heading in text, f"docs/troubleshooting.md is missing the {heading!r} section"


# ---------------------------------------------------------------------------
# offline/safety docs match the explicit fetch-action boundary
# ---------------------------------------------------------------------------


def test_offline_and_safety_names_the_one_network_module():
    text = _read("docs", "offline_and_safety.md")
    assert "pdbtm_transport.py" in text
    assert "Fetch" in text


def test_only_pdbtm_transport_imports_networking_primitives():
    """Ground docs/offline_and_safety.md's central claim directly against the source
    tree: exactly membrane_vqc/pdbtm_transport.py may import socket/ssl/http.client."""
    package = ROOT / "membrane_vqc"
    offenders = []
    for path in package.glob("*.py"):
        if path.name == "pdbtm_transport.py":
            continue
        text = path.read_text("utf-8")
        if re.search(r"^\s*(import|from)\s+(socket|ssl|http\.client)\b", text, re.MULTILINE):
            offenders.append(path.name)
    assert not offenders, (
        f"unexpected network-capable import(s) outside pdbtm_transport.py: {offenders} -- "
        "update docs/offline_and_safety.md if this is an intentional change"
    )


def test_offline_and_safety_references_both_fingerprint_mechanisms():
    text = _read("docs", "offline_and_safety.md")
    assert "pdbtm_adapter.py" in text
    assert "opm_adapter.py" in text
    assert "transformed_reference" in text
    assert "source_fingerprint" in text


def test_batch_plan_reference_links_five_mode_example():
    text = _read("docs", "batch_plan_reference.md")
    assert "five_mode_walkthrough.md" in text


def test_five_mode_walkthrough_references_the_synthetic_plan():
    text = _read("docs", "five_mode_walkthrough.md")
    assert "data/synthetic/stage5a_batch_plan.json" in text


def test_readme_links_all_primary_guides():
    text = _read("README.md")
    for doc in (
        "docs/index.md",
        "docs/quick_start.md",
        "docs/tutorial.md",
        "docs/batch_plan_reference.md",
        "docs/five_mode_walkthrough.md",
        "docs/outputs_and_manifests.md",
        "docs/status_vocabulary.md",
        "docs/troubleshooting.md",
        "docs/offline_and_safety.md",
        "docs/scientific_interpretation.md",
        "docs/upgrade_guide.md",
        "docs/compatibility.md",
        "docs/compatibility_matrix.md",
        "docs/known_limitations.md",
        "docs/v1.0_contract_freeze.md",
        "docs/versioning_policy.md",
        "docs/release_checklist.md",
        "docs/scientific_background.md",
        "docs/references.bib",
    ):
        assert doc in text, f"README.md does not link {doc}"


# ---------------------------------------------------------------------------
# historical manual evidence remains unchanged (beyond cross-links)
# ---------------------------------------------------------------------------


def test_manual_install_upgrade_evidence_still_records_its_pass_result():
    text = _read("docs", "manual_install_upgrade_checklist.md")
    assert "Status: **PASS**" in text
    assert "d11234fc3e74bbc7427d6bb18f36897bc86a9d27a9bfec134df9b623307d638c" in text
    assert "7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960" in text


# ---------------------------------------------------------------------------
# forbidden claims without an apparent negation nearby
# ---------------------------------------------------------------------------

_USER_FACING_DOCS = (
    "README.md",
    "docs/index.md",
    "docs/quick_start.md",
    "docs/tutorial.md",
    "docs/batch_plan_reference.md",
    "docs/five_mode_walkthrough.md",
    "docs/outputs_and_manifests.md",
    "docs/status_vocabulary.md",
    "docs/troubleshooting.md",
    "docs/offline_and_safety.md",
    "docs/scientific_interpretation.md",
    "docs/compatibility.md",
    "docs/compatibility_matrix.md",
    "docs/known_limitations.md",
    "docs/v1.0_contract_freeze.md",
    "docs/versioning_policy.md",
    "docs/release_checklist.md",
    "docs/scientific_background.md",
)


def test_no_doc_claims_pypi_publication():
    for relative in _USER_FACING_DOCS:
        text = _read(*relative.split("/"))
        _assert_always_negated(text, "PyPI", doc_name=relative)


def test_no_doc_claims_persistent_session_history():
    for relative in _USER_FACING_DOCS:
        text = _read(*relative.split("/"))
        if "persistent" in text.lower() and "history" in text.lower():
            _assert_always_negated(text, "persistent", doc_name=relative)
        for window in _sentence_windows(text, "history"):
            lowered = window.lower()
            if "persist" in lowered:
                assert re.search(r"\b(not|no|never|n't)\b", lowered), (
                    f"{relative} may claim history persists -- context: {window!r}"
                )


def test_no_doc_claims_automatic_cache_migration():
    for relative in _USER_FACING_DOCS:
        text = _read(*relative.split("/"))
        if "migration" in text.lower():
            _assert_always_negated(text, "migration", doc_name=relative)


# ---------------------------------------------------------------------------
# prohibited scientific-verdict wording in user-facing status explanations
# ---------------------------------------------------------------------------

_ALWAYS_FORBIDDEN = (
    "wrong structure",
    "invalid model",
    "failed biology",
    "best orientation",
    "correct source",
    "guaranteed membrane placement",
)


def test_no_doc_uses_prohibited_verdict_phrases():
    # docs/scientific_interpretation.md is the one canonical place these exact phrases are
    # named on purpose, as the "vocabulary to avoid" list itself -- excluded here, not from
    # any other check in this module.
    for relative in _USER_FACING_DOCS:
        if relative == "docs/scientific_interpretation.md":
            continue
        text = _read(*relative.split("/"))
        for phrase in _ALWAYS_FORBIDDEN:
            _assert_never_present(text, phrase, doc_name=relative)


def test_no_doc_claims_automatic_validation_or_biological_correctness_unqualified():
    for relative in _USER_FACING_DOCS:
        text = _read(*relative.split("/"))
        if "automatically validated" in text.lower():
            _assert_always_negated(text, "automatically validated", doc_name=relative)
        if "biologically correct" in text.lower():
            _assert_always_negated(text, "biologically correct", doc_name=relative)


# ---------------------------------------------------------------------------
# Contract-freeze documentation set (docs/v1.0_contract_freeze.md and friends)
# ---------------------------------------------------------------------------


def test_contract_freeze_docs_exist_and_cross_link():
    freeze = _read("docs", "v1.0_contract_freeze.md")
    versioning = _read("docs", "versioning_policy.md")
    checklist = _read("docs", "release_checklist.md")
    matrix = _read("docs", "compatibility_matrix.md")

    assert "versioning_policy.md" in freeze
    assert "v1.0_contract_freeze.md" in versioning
    assert "docs/v1.0_contract_freeze.md" in checklist or "v1.0_contract_freeze.md" in checklist
    assert "compatibility.md" in matrix


def test_contract_freeze_doc_lists_the_frozen_pymol_commands():
    text = _read("docs", "v1.0_contract_freeze.md")
    for command in (
        "mvqc_check",
        "mvqc_slab",
        "mvqc_check_orientation",
        "mvqc_slab_orientation",
        "mvqc_check_pdbtm",
        "mvqc_slab_pdbtm",
        "mvqc_color_hydropathy",
        "mvqc_ligand_shell",
        "mvqc_export",
        "mvqc_batch_run",
        "mvqc_clear",
    ):
        assert f"`{command}`" in text, (
            f"docs/v1.0_contract_freeze.md is missing command {command!r}"
        )


def test_outputs_and_status_docs_reference_the_contract_freeze():
    assert "v1.0_contract_freeze.md" in _read("docs", "outputs_and_manifests.md")
    assert "v1.0_contract_freeze.md" in _read("docs", "status_vocabulary.md")
