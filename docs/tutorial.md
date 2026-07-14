# Tutorial

## Command workflow

```pml
load data/synthetic/bad_core_lys.pdb, bad_core_lys
mvqc_check selection=bad_core_lys, zmin=-15, zmax=15, ligand=, cutoff=5
mvqc_export path=reports/bad_core_lys_mvqc.json
```

Expected result: two membrane boundaries, one highlighted charged-core residue, and one
`REVIEW_ITEMS` report entry. An empty ligand selection is valid and clears ligand context.

For a real structure:

```pml
load data/raw/1C3W.cif, 1C3W
mvqc_check selection=1C3W, zmin=-15, zmax=15, ligand=organic, cutoff=5
mvqc_export path=reports/1c3w_mvqc.json
```

The structure must already be in a meaningful coordinate frame. The plugin records manual
orientation and does not infer membrane alignment. Use `mvqc_clear` to remove all plugin-owned
objects and temporary report state without touching user objects.

## Unreleased planar-orientation workflow

Stage 2 accepts a strict local JSON document instead of fragile comma-separated vectors:

```pml
mvqc_check_orientation selection=1UBQ_rotated, orientation_file=demo/rotated_1ubq_orientation.json, ligand=
```

The demo orientation belongs only to the documented rigid transform in the validation script.
The GUI offers **Legacy global-z** and **Planar orientation file** modes. Advanced manual-plane
fields and automatic external adapters are deferred.

## GUI workflow

Open **Plugin > Membrane Visual QC**, select the orientation mode, enter a non-empty selection and
a positive cutoff. Legacy mode requires finite `zmin < zmax`; file mode requires valid local JSON.
Ligand selection may be empty.

See `docs/manual_gui_validation.md` for the release checklist.

## Report review

Use `review_items` as prompts for contextual inspection. Check orientation warnings before
interpreting depth-related output. The current rules do not calculate exposure, salt bridges,
hydrogen bonds, energetic stability, or persistent hydration.
