"""Probe current-coordinate snapshot semantics in a real headless PyMOL process."""

from pathlib import Path

from pymol import cmd


ROOT = Path.cwd()
SOURCE = ROOT / "data" / "synthetic" / "local_context_review.pdb"


def _pdb_first_coordinates(pdb_text):
    line = next(line for line in pdb_text.splitlines() if line.startswith(("ATOM  ", "HETATM")))
    return tuple(float(line[start:end]) for start, end in ((30, 38), (38, 46), (46, 54)))


def _close(left, right, tolerance=1e-4):
    return all(abs(a - b) <= tolerance for a, b in zip(left, right))


cmd.reinitialize()
cmd.load(str(SOURCE), "snapshot_probe")
before = tuple(cmd.get_model("snapshot_probe", state=1).atom[0].coord)

# Apply a rigid object-matrix transform rather than rewriting the stored atom coordinates.
cmd.transform_object(
    "snapshot_probe",
    [
        0.0,
        -1.0,
        0.0,
        10.0,
        1.0,
        0.0,
        0.0,
        -5.0,
        0.0,
        0.0,
        1.0,
        3.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ],
)

model_coordinates = tuple(cmd.get_model("snapshot_probe", state=1).atom[0].coord)
coords_coordinates = tuple(cmd.get_coords("snapshot_probe", state=1)[0])
pdb_coordinates = _pdb_first_coordinates(cmd.get_pdbstr("snapshot_probe", state=1))

assert not _close(before, model_coordinates), (before, model_coordinates)
assert _close(coords_coordinates, model_coordinates), (coords_coordinates, model_coordinates)

print(f"before={before}", flush=True)
print(f"get_model={model_coordinates}", flush=True)
print(f"get_coords={coords_coordinates}", flush=True)
print(f"get_pdbstr={pdb_coordinates}", flush=True)
print(
    f"get_pdbstr_matches_current={_close(pdb_coordinates, model_coordinates, 0.0011)}",
    flush=True,
)

metadata_pdb = (
    f"ATOM  {1:5d} {'CA':>4}B{'GLY':>3} A{12:4d}A   "
    f"{1.0:8.3f}{2.0:8.3f}{3.0:8.3f}{0.75:6.2f}{20.0:6.2f}          C \nEND\n"
)
cmd.read_pdbstr(metadata_pdb, "metadata_probe")
metadata_atom = cmd.get_model("metadata_probe", state=1).atom[0]
metadata_line = next(
    line
    for line in cmd.get_pdbstr("metadata_probe", state=1).splitlines()
    if line.startswith("ATOM  ")
)
assert metadata_atom.chain == metadata_line[21:22].strip() == "A"
assert metadata_atom.resi == metadata_line[22:27].strip() == "12A"
assert metadata_atom.resn == metadata_line[17:20].strip() == "GLY"
assert metadata_atom.name == metadata_line[12:16].strip() == "CA"
assert metadata_atom.alt == metadata_line[16:17].strip() == "B"
assert abs(float(metadata_atom.q) - float(metadata_line[54:60])) <= 1e-9
print("legacy chain/residue/insertion/resname/atom/altloc/occupancy preserved=True", flush=True)
cmd.quit()
