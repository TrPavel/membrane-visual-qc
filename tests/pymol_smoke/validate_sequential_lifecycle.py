"""Stateful one-process PyMOL regression for repeated Stage 3B actions."""

from pathlib import Path
import sys

ROOT = Path.cwd()
if not (ROOT / "data" / "synthetic" / "local_context_review.pdb").is_file():
    raise RuntimeError("Run this smoke test from the repository root.")
sys.path.insert(0, str(ROOT))

from pymol import cmd  # noqa: E402

from membrane_vqc import commands, qc  # noqa: E402
from membrane_vqc.pymol_adapter import (  # noqa: E402
    MVQC_CONTEXT_NAMES,
    MVQC_NAMES,
    MVQC_REVIEW_NAMES,
)

FIXTURE = ROOT / "data" / "synthetic" / "local_context_review.pdb"
OBJECT = "local_context_review"


def selection_names():
    return set(cmd.get_names("selections"))


def run_context(enabled):
    return commands.mvqc_check(
        selection=OBJECT,
        zmin=-15,
        zmax=15,
        ligand="organic",
        quiet=1,
        analyze_context=enabled,
        exposure_quality="Standard",
        exposure_backend="Built-in",
    )


cmd.load(str(FIXTURE), OBJECT)

first = run_context(1)
assert first["schema_version"] == "1.2"
assert set(MVQC_CONTEXT_NAMES) <= selection_names()

without_context = run_context(0)
assert without_context["schema_version"] == "1.1"
assert not (set(MVQC_CONTEXT_NAMES) & selection_names())

third = run_context(1)
assert third["schema_version"] == "1.2"
assert set(MVQC_REVIEW_NAMES) <= selection_names()
assert set(MVQC_CONTEXT_NAMES) <= selection_names()

fourth = run_context(1)
assert fourth["schema_version"] == "1.2"
assert set(MVQC_REVIEW_NAMES) <= selection_names()
assert set(MVQC_CONTEXT_NAMES) <= selection_names()

invalid_file = ROOT / "demo" / "missing_stage3b_orientation.json"
try:
    commands.mvqc_check_orientation(
        selection=OBJECT,
        orientation_file=str(invalid_file),
        ligand="organic",
        quiet=1,
        analyze_context=1,
        exposure_quality="Standard",
        exposure_backend="Built-in",
    )
except Exception as exc:
    message = str(exc)
else:
    raise AssertionError("Missing orientation file unexpectedly succeeded.")

assert "orientation" in message.lower() or invalid_file.name in message
assert "invalid selection name" not in message.lower()
remaining_plugin_state = set(MVQC_NAMES) & (
    set(cmd.get_names("selections")) | set(cmd.get_names("objects"))
)
assert not remaining_plugin_state
assert qc.LAST_REPORT is None
assert OBJECT in cmd.get_names("objects")

print("Stage 3B sequential lifecycle: PASS")
