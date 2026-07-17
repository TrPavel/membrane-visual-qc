"""Headless PyMOL validation for Stage 3B local-context extraction and visuals."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))

from pymol import cmd

from membrane_vqc.context_models import ExposureConfig, LocalContextConfig
from membrane_vqc.qc import run_check

ROOT = Path.cwd()
cmd.load(str(ROOT / "data" / "synthetic" / "local_context_review.pdb"), "mvqc_context_fixture")
report = run_check(
    selection="mvqc_context_fixture",
    zmin=-15,
    zmax=15,
    ligand="organic",
    quiet=1,
    export_path=str(ROOT / "reports" / "local_context_mvqc.json"),
    cmd_obj=cmd,
    input_path=str(ROOT / "data" / "synthetic" / "local_context_review.pdb"),
    exposure_config=ExposureConfig(target_scope="review_items"),
    local_context_config=LocalContextConfig(),
)

assert report["schema_version"] == "1.2"
assert report["review_items"]
assert all("local_context" in item for item in report["review_items"])
contacts = {
    contact["type"]
    for item in report["review_items"]
    for contact in item["local_context"]["contacts"]
}
assert "putative_salt_bridge" in contacts
assert "distance_only_potential_hbond" in contacts
assert "nearby_water" in contacts
assert "nearby_ion" in contacts
assert "polar_ligand_proximity" in contacts
for name in (
    "mvqc_context_partners",
    "mvqc_context_waters",
    "mvqc_context_ions",
    "mvqc_context_ligands",
):
    assert name in cmd.get_names("all")
print("Stage 3B context fixture: PASS")
