"""Consistency checks for the consolidated user-facing documentation set added alongside
docs/index.md. These check facts, required links, and literal synchronization with code --
not prose or formatting -- so they stay meaningful as the docs are edited going forward."""

from __future__ import annotations

import re
from pathlib import Path

from membrane_vqc.batch_contracts import PLAN_CONTRACT, RESULT_CONTRACT, STATUSES
from membrane_vqc.batch_gui import BATCH_STATES
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
# 1. docs/index.md exists
# ---------------------------------------------------------------------------


def test_docs_index_exists():
    assert (DOCS / "index.md").is_file()


# ---------------------------------------------------------------------------
# 2. all local markdown links from README/docs/index resolve
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


# ---------------------------------------------------------------------------
# 3. troubleshooting guide exists and contains required major topics
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
# 4. status vocabulary literals match current schema/code enums
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
# 5. outputs/manifests guide mentions current manifest filename and contract version
# ---------------------------------------------------------------------------


def test_outputs_guide_mentions_manifest_filename_and_contract():
    text = _read("docs", "outputs_and_manifests.md")
    assert "batch-result.json" in text
    assert RESULT_CONTRACT in text
    assert PLAN_CONTRACT in text


# ---------------------------------------------------------------------------
# 6. offline guarantees match the explicit fetch-action boundary
# ---------------------------------------------------------------------------


def test_offline_guarantees_names_the_one_network_module():
    text = _read("docs", "offline_guarantees.md")
    assert "pdbtm_transport.py" in text
    assert "Fetch" in text


def test_only_pdbtm_transport_imports_networking_primitives():
    """Ground docs/offline_guarantees.md's central claim directly against the source
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
        "update docs/offline_guarantees.md if this is an intentional change"
    )


# ---------------------------------------------------------------------------
# 7. coordinate-preservation docs reference both fingerprint mechanisms
# ---------------------------------------------------------------------------


def test_coordinate_preservation_references_both_fingerprint_mechanisms():
    text = _read("docs", "coordinate_preservation.md")
    assert "pdbtm_adapter.py" in text
    assert "opm_adapter.py" in text
    assert "transformed_reference" in text
    assert "source_fingerprint" in text


# ---------------------------------------------------------------------------
# 8. batch-plan guide links the five-mode example
# ---------------------------------------------------------------------------


def test_batch_plan_guide_links_five_mode_example():
    text = _read("docs", "batch_plan.md")
    assert "data/synthetic/stage5a_batch_plan.json" in text


# ---------------------------------------------------------------------------
# 9. README links all primary guides
# ---------------------------------------------------------------------------


def test_readme_links_all_primary_guides():
    text = _read("README.md")
    for doc in (
        "docs/index.md",
        "docs/tutorial.md",
        "docs/batch_plan.md",
        "docs/outputs_and_manifests.md",
        "docs/status_vocabulary.md",
        "docs/troubleshooting.md",
        "docs/offline_guarantees.md",
        "docs/coordinate_preservation.md",
        "docs/upgrade_guide.md",
        "docs/compatibility.md",
        "docs/known_limitations.md",
    ):
        assert doc in text, f"README.md does not link {doc}"


# ---------------------------------------------------------------------------
# 10. historical manual evidence remains unchanged (beyond cross-links)
# ---------------------------------------------------------------------------


def test_manual_install_upgrade_evidence_still_records_its_pass_result():
    text = _read("docs", "manual_install_upgrade_checklist.md")
    assert "Status: **PASS**" in text
    assert "d11234fc3e74bbc7427d6bb18f36897bc86a9d27a9bfec134df9b623307d638c" in text
    assert "7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960" in text


# ---------------------------------------------------------------------------
# 11-13. forbidden claims without an apparent negation nearby
# ---------------------------------------------------------------------------

_USER_FACING_DOCS = (
    "README.md",
    "docs/index.md",
    "docs/tutorial.md",
    "docs/batch_plan.md",
    "docs/outputs_and_manifests.md",
    "docs/status_vocabulary.md",
    "docs/troubleshooting.md",
    "docs/offline_guarantees.md",
    "docs/coordinate_preservation.md",
    "docs/compatibility.md",
    "docs/known_limitations.md",
)


def test_no_doc_claims_pypi_publication():
    for relative in _USER_FACING_DOCS:
        text = _read(*relative.split("/"))
        _assert_always_negated(text, "PyPI", doc_name=relative)


def test_no_doc_claims_persistent_history():
    for relative in _USER_FACING_DOCS:
        text = _read(*relative.split("/"))
        if "persistent" in text.lower() and "history" in text.lower():
            _assert_always_negated(text, "persistent", doc_name=relative)


def test_no_doc_claims_automatic_cache_migration():
    for relative in _USER_FACING_DOCS:
        text = _read(*relative.split("/"))
        if "migration" in text.lower():
            _assert_always_negated(text, "migration", doc_name=relative)


# ---------------------------------------------------------------------------
# 14. prohibited scientific-verdict wording in user-facing status explanations
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
    for relative in _USER_FACING_DOCS:
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
