"""Regression coverage for the historical frozen-evidence Git guard."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "scripts" / "check_frozen_evidence_diff.py"


@pytest.fixture()
def frozen_repository(tmp_path: Path) -> tuple[Path, str, Path]:
    """Create a minimal repository containing one validator-pinned evidence file."""
    evidence = tmp_path / "docs" / "v0.5.0_release_evidence.json"
    evidence.parent.mkdir()
    evidence.write_text('{"version": "0.5.0"}\n', encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=MVQC test",
            "-c",
            "user.email=mvqc@example.invalid",
            "commit",
            "-m",
            "freeze evidence",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    baseline = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, text=True, capture_output=True
    ).stdout.strip()
    return tmp_path, baseline, evidence


@pytest.fixture()
def guard_module():
    spec = importlib.util.spec_from_file_location("check_frozen_evidence_diff", GUARD_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_untouched_frozen_evidence_passes(guard_module, frozen_repository) -> None:
    root, baseline, _ = frozen_repository
    assert guard_module.changed_frozen_paths(baseline, root=root) == []


@pytest.mark.parametrize("mutation", ["modified", "deleted", "renamed"])
def test_frozen_evidence_mutations_are_rejected(
    guard_module, frozen_repository, mutation: str
) -> None:
    root, baseline, evidence = frozen_repository
    if mutation == "modified":
        evidence.write_text('{"version": "corrupted"}\n', encoding="utf-8")
    elif mutation == "deleted":
        evidence.unlink()
    else:
        evidence.rename(evidence.with_name("replacement.json"))

    changed = guard_module.changed_frozen_paths(baseline, root=root)

    assert changed
    assert any(line.startswith(("M", "D", "R")) for line in changed)
    assert any("docs/v0.5.0_release_evidence.json" in line for line in changed)
