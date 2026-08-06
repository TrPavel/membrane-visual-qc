"""Pin docs/contracts/*.json against the live code it's generated from.

One regeneration-and-diff test per category, rather than dozens of hand-written field assertions
that would duplicate what tests/test_contract_freeze.py and tests/test_documentation_consistency.py
already check -- this test's job is only to prove the *committed* JSON snapshot still matches what
scripts/export_contract_inventory.py would produce right now, so the inventory can never silently
drift from the code (or from the freeze tests) without a test failing.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_contract_inventory import OUT_DIR, build_inventory

ROOT = Path(__file__).resolve().parents[1]


def _committed(name: str) -> dict[str, object]:
    return json.loads((OUT_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_every_inventory_category_has_a_committed_file():
    inventory = build_inventory()
    for key in inventory:
        assert (OUT_DIR / f"{key}.json").is_file(), f"docs/contracts/{key}.json is missing"


def test_committed_inventory_matches_a_fresh_regeneration():
    """The core anti-drift check: everything scripts/export_contract_inventory.py would produce
    right now must equal what's committed. A code change to any frozen contract, without
    regenerating docs/contracts/, fails this test."""
    fresh = build_inventory()
    for key, value in fresh.items():
        committed = _committed(key)
        assert committed == value, (
            f"docs/contracts/{key}.json is stale -- run "
            "`python scripts/export_contract_inventory.py` and commit the result. "
            f"committed={committed!r} fresh={value!r}"
        )


def test_committed_files_are_canonically_formatted():
    """Guards against a hand-edited (not regenerated) docs/contracts/*.json slipping through
    review with different formatting than the generator would produce."""
    for path in sorted(OUT_DIR.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        value = json.loads(text)
        expected = json.dumps(value, indent=2, sort_keys=True) + "\n"
        assert text == expected, f"{path.relative_to(ROOT)} is not canonically formatted"


def test_csv_columns_inventory_matches_report_module():
    from membrane_vqc.report import CSV_FIELDS

    assert _committed("csv_columns")["single_structure_flags_csv"] == list(CSV_FIELDS)


def test_public_api_inventory_matches_package_all():
    import membrane_vqc

    assert _committed("public_api")["exported_names"] == sorted(membrane_vqc.__all__)


def test_result_bundle_availability_literals_still_present_in_source():
    """docs/contracts/status_vocabulary.json's result_bundle_artifact_availability list is a
    hand-reproduced literal (batch_result_browser.py has no named constant for it) -- this test
    is the drift guard the generator's docstring promises: confirm both strings are still used
    as literals in the module that owns them."""
    source = (ROOT / "membrane_vqc" / "batch_result_browser.py").read_text(encoding="utf-8")
    for literal in _committed("status_vocabulary")["result_bundle_artifact_availability"]:
        assert f'"{literal}"' in source, (
            f"batch_result_browser.py no longer contains the literal {literal!r} -- update "
            "_result_bundle_availability() in scripts/export_contract_inventory.py"
        )


def test_readme_documents_every_inventory_file():
    readme = (OUT_DIR / "README.md").read_text(encoding="utf-8")
    for path in sorted(OUT_DIR.glob("*.json")):
        assert path.name in readme, f"docs/contracts/README.md does not mention {path.name}"
