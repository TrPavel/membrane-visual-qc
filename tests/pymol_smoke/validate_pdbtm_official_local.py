"""Ignored-local official PDBTM Stage 4A2 acceptance; never used by CI."""

from pathlib import Path
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from pymol import cmd  # noqa: E402

from membrane_vqc import qc  # noqa: E402
from membrane_vqc.commands import mvqc_check_pdbtm, mvqc_clear  # noqa: E402
from membrane_vqc.pdbtm_pymol import PdbtmCommandError  # noqa: E402


LOCAL = ROOT / ".local" / "pdbtm_preflight"


def _metrics(report):
    evidence = report["orientation"]["evidence"]
    mapping = evidence["coordinate_mapping"]
    method = mapping["method"]
    key = "runtime_identity" if method == "identity" else "runtime_inverse"
    values = mapping["metrics"][key]
    return method, values["matched_atom_count"], values["rmsd"], values["maximum_residual"]


def _run(record_id, coordinate_name, expected_method, *, context=False):
    directory = LOCAL / record_id
    object_name = f"official_{record_id}_{expected_method}"
    cmd.delete("all")
    file_format = "pdb" if coordinate_name.endswith(".trpdb") else ""
    cmd.load(str(directory / coordinate_name), object_name, format=file_format)
    before = tuple(tuple(row) for row in cmd.get_coords(object_name, state=1))
    report = mvqc_check_pdbtm(
        selection=object_name,
        pdbtm_json=str(directory / "pdbtm.json"),
        transformed_pdb=str(directory / "pdbtm.trpdb"),
        ligand="",
        quiet=1,
        analyze_context=int(context),
    )
    assert report["schema_version"] == "1.3"
    method, matched, rmsd, maximum = _metrics(report)
    assert method == expected_method
    assert tuple(tuple(row) for row in cmd.get_coords(object_name, state=1)) == before
    if context:
        assert "context_analysis" in report
    print(
        f"{record_id} {expected_method} context={int(context)} "
        f"matched={matched} rmsd={rmsd:.9f} max={maximum:.9f}: PASS",
        flush=True,
    )
    return object_name


cmd.reinitialize()
for record_id in ("1pcr", "1a0s"):
    _run(record_id, "pdbtm.trpdb", "identity")
    _run(record_id, "rcsb_deposited.pdb", "inverse_provider_transform")
    _run(record_id, "pdbtm.trpdb", "identity", context=True)

# Wrong pair is rejected and clears all plugin-owned/report state.
cmd.delete("all")
cmd.load(str(LOCAL / "1pcr" / "pdbtm.trpdb"), "wrong_pair", format="pdb")
try:
    mvqc_check_pdbtm(
        "wrong_pair",
        str(LOCAL / "1a0s" / "pdbtm.json"),
        str(LOCAL / "1pcr" / "pdbtm.trpdb"),
        ligand="",
    )
except PdbtmCommandError:
    pass
else:
    raise AssertionError("Wrong official pair was unexpectedly accepted.")
assert qc.LAST_REPORT is None

# Current displayed transforms are real geometry and are rejected without changing the object.
cmd.delete("all")
cmd.load(str(LOCAL / "1pcr" / "pdbtm.trpdb"), "manual_transform", format="pdb")
cmd.transform_object(
    "manual_transform",
    [1.0, 0.0, 0.0, 4.0, 0.0, 1.0, 0.0, -3.0, 0.0, 0.0, 1.0, 2.0, 0, 0, 0, 1],
)
transformed = tuple(tuple(row) for row in cmd.get_coords("manual_transform", state=1))
try:
    mvqc_check_pdbtm(
        "manual_transform",
        str(LOCAL / "1pcr" / "pdbtm.json"),
        str(LOCAL / "1pcr" / "pdbtm.trpdb"),
        ligand="",
    )
except PdbtmCommandError as exc:
    assert exc.code == "COORDINATE_FRAME_MISMATCH"
else:
    raise AssertionError("Manually transformed official object was unexpectedly accepted.")
assert tuple(tuple(row) for row in cmd.get_coords("manual_transform", state=1)) == transformed
assert qc.LAST_REPORT is None

mvqc_clear()
assert "manual_transform" in cmd.get_names("objects")
print("Official local wrong-pair/transform/repeat/clear lifecycle: PASS", flush=True)
cmd.quit()
