# Stage 4A2 PyMOL snapshot semantics

Status: verified locally on 2026-07-19 with Incentive PyMOL 3.1.8 and bundled Python 3.10.20 on
Windows 10 build 26200.

## Question

Stage 4A2 needs a legacy-PDB snapshot of the actual current PyMOL object. The check did not assume
that `cmd.get_pdbstr()` applies an object matrix. It loaded a small single-state structure, recorded
coordinates, applied a nontrivial rigid object-matrix rotation/translation, and compared three
independent API views.

## Result

For the measured first atom:

- before transform: `(-1.5, 0.0, 0.0)`;
- `cmd.get_model(..., state=1)`: `(10.0, -6.5, 3.0)`;
- `cmd.get_coords(..., state=1)`: `(10.0, -6.5, 3.0)`;
- coordinates parsed from `cmd.get_pdbstr(..., state=1)`: `(10.0, -6.5, 3.0)`.

The legacy snapshot also preserved chain ID, residue number, insertion code, residue name, atom
name, altloc, and occupancy in a dedicated non-empty metadata case. The executable regression is
`tests/pymol_smoke/validate_pdbtm_snapshot_semantics.py`.

## Decision

Stage 4A2 uses one `cmd.get_pdbstr(complete_object, state=1)` snapshot. Before serialization it
uses `cmd.get_object_list`, `cmd.count_states`, and `cmd.get_model` to require exactly one complete
single-state molecular object and reject metadata that cannot be represented safely in the
reviewed legacy-PDB contract. The snapshot is ASCII encoded, limited to 5 MiB, and passed directly
to the accepted Stage 4A1 adapter. No temporary object or filesystem file is created.

This result establishes current-coordinate serialization behaviour for the named tested PyMOL
build. It does not promise identical behaviour for untested future PyMOL versions; the retained
headless probe must be rerun when the supported runtime changes.
