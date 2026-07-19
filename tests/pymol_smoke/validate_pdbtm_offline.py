"""Headless Stage 4A2 offline PDBTM command and lifecycle validation."""

from pathlib import Path
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from pymol import cmd  # noqa: E402

from membrane_vqc import qc  # noqa: E402
from membrane_vqc.commands import mvqc_check_pdbtm, mvqc_clear, mvqc_slab_pdbtm  # noqa: E402
from membrane_vqc.pdbtm_pymol import PdbtmCommandError  # noqa: E402
from membrane_vqc.pymol_adapter import MVQC_NAMES  # noqa: E402


JSON_PATH = ROOT / "data" / "synthetic" / "pdbtm_api_v1_test.json"
TRANSFORMED_PATH = ROOT / "data" / "synthetic" / "pdbtm_transformed_test.pdb"
ORIGINAL_PATH = ROOT / "data" / "synthetic" / "pdbtm_original_test.pdb"
OWNED = {"mvqc_slab_lower", "mvqc_slab_upper"}


def _coordinates(name):
    return tuple(tuple(float(value) for value in row) for row in cmd.get_coords(name, state=1))


def _assert_slab_present():
    assert OWNED <= set(cmd.get_names("objects"))


def _active_plugin_names():
    return (set(cmd.get_names("objects")) | set(cmd.get_names("selections"))) & set(MVQC_NAMES)


cmd.reinitialize()
cmd.load(str(TRANSFORMED_PATH), "pdbtm_identity")
identity_before = _coordinates("pdbtm_identity")
identity_report = mvqc_check_pdbtm(
    selection="pdbtm_identity and resi 1-3",
    pdbtm_json=str(JSON_PATH),
    transformed_pdb=str(TRANSFORMED_PATH),
    ligand="",
    quiet=1,
)
assert identity_report["schema_version"] == "1.3"
assert identity_report["orientation"]["evidence"]["coordinate_mapping"]["method"] == "identity"
assert _coordinates("pdbtm_identity") == identity_before
_assert_slab_present()

# Context dispatch remains schema 1.3 and repeated execution recreates owned visuals.
context_report = mvqc_check_pdbtm(
    selection="pdbtm_identity",
    pdbtm_json=str(JSON_PATH),
    transformed_pdb=str(TRANSFORMED_PATH),
    ligand="",
    quiet=1,
    analyze_context=1,
)
assert context_report["schema_version"] == "1.3"
assert "context_analysis" in context_report
assert _coordinates("pdbtm_identity") == identity_before

mvqc_slab_pdbtm("pdbtm_identity", str(JSON_PATH), str(TRANSFORMED_PATH))
_assert_slab_present()
assert _active_plugin_names() == OWNED
assert qc.LAST_REPORT is None
assert _coordinates("pdbtm_identity") == identity_before

# A failed slab import invalidates the preceding slab and cannot leave an exportable report.
try:
    mvqc_slab_pdbtm("pdbtm_identity", str(JSON_PATH), str(ORIGINAL_PATH))
except PdbtmCommandError:
    pass
else:
    raise AssertionError("Wrong transformed companion was unexpectedly accepted for slab display.")
assert not _active_plugin_names()
assert qc.LAST_REPORT is None
assert _coordinates("pdbtm_identity") == identity_before

cmd.load(str(ORIGINAL_PATH), "pdbtm_inverse")
inverse_before = _coordinates("pdbtm_inverse")
inverse_report = mvqc_check_pdbtm(
    selection="pdbtm_inverse",
    pdbtm_json=str(JSON_PATH),
    transformed_pdb=str(TRANSFORMED_PATH),
    ligand="",
    quiet=1,
)
assert (
    inverse_report["orientation"]["evidence"]["coordinate_mapping"]["method"]
    == "inverse_provider_transform"
)
assert _coordinates("pdbtm_inverse") == inverse_before

# A nontrivial object-matrix transform is current geometry and must not be silently accepted.
cmd.transform_object(
    "pdbtm_inverse",
    [1.0, 0.0, 0.0, 4.0, 0.0, 1.0, 0.0, -3.0, 0.0, 0.0, 1.0, 2.0, 0, 0, 0, 1],
)
try:
    mvqc_check_pdbtm(
        selection="pdbtm_inverse",
        pdbtm_json=str(JSON_PATH),
        transformed_pdb=str(TRANSFORMED_PATH),
        ligand="",
        quiet=1,
    )
except PdbtmCommandError as exc:
    assert exc.code == "COORDINATE_FRAME_MISMATCH"
else:
    raise AssertionError("Transformed current coordinates were unexpectedly accepted.")
assert qc.LAST_REPORT is None
assert not (OWNED & set(cmd.get_names("objects")))
assert {"pdbtm_identity", "pdbtm_inverse"} <= set(cmd.get_names("objects"))

mvqc_clear()
assert {"pdbtm_identity", "pdbtm_inverse"} <= set(cmd.get_names("objects"))
print("Stage 4A2 synthetic identity/inverse/lifecycle: PASS", flush=True)
cmd.quit()
