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

## Planar-orientation workflow

Stage 2 accepts a strict local JSON document instead of fragile comma-separated vectors:

Prepare the validated manual fixture in graphical PyMOL without reproducing coordinate operations:

```pml
run C:/Pymol_script_1/demo/prepare_rotated_1ubq.py
```

```pml
mvqc_check_orientation selection=1UBQ_rotated, orientation_file=demo/rotated_1ubq_orientation.json, ligand=
```

The demo orientation belongs only to the documented rigid transform in the validation script.
The GUI offers **Legacy global-z** and **Planar orientation file** modes. Advanced manual-plane
fields and automatic external adapters are deferred.

## Offline PDBTM workflow

Version `0.4.0` can apply one explicit matching local PDBTM API-v1 JSON and
transformed-PDB companion to a complete single-state PyMOL object without fitting or modifying it:

```pml
mvqc_check_pdbtm selection=my_object, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb, ligand=
mvqc_slab_pdbtm selection=my_object, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb
```

Select **PDBTM offline pair** in the GUI for the same workflow. The JSON and transformed-PDB must
belong to the same provider record. The plugin performs no download, coordinate fitting, or
automatic transform. See `docs/pdbtm_offline_import.md` for the exact object and provenance
contract.

## GUI workflow

Open **Plugin > Membrane Visual QC**, select the orientation mode, enter a non-empty selection and
a positive cutoff. Legacy mode requires finite `zmin < zmax`; planar file mode requires valid
local JSON; PDBTM mode requires two explicit matching local files.
Ligand selection may be empty.

See `docs/manual_gui_validation.md` for the release checklist.

## Report review

Use `review_items` as prompts for contextual inspection. Check orientation warnings before
interpreting depth-related output. The current rules do not calculate exposure, salt bridges,
hydrogen bonds, energetic stability, or persistent hydration.
