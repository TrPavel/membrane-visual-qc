# Demo

This folder contains small PyMOL command scripts for the MVP inspection workflow.

## Files

- `quickstart.pml`: minimal synthetic example intended to run without downloading public structures.
- `demo_scene.pml`: broader demo script with commented examples for public structures once downloaded.

## Before Running Public Demos

Download validation structures into `data/raw/` as described in `data/README.md`.

## Expected Language

The demo should present findings as visual inspection prompts. Charged or polar residues in a manually defined membrane core should be described as residues to inspect, not as definitive structural failures.

## Example Commands

```pml
run membrane_vqc/commands.py
load data/synthetic/bad_core_lys.pdb
mvqc_check selection=bad_core_lys, zmin=-15, zmax=15, ligand=organic, cutoff=5.0
mvqc_export path=reports/bad_core_lys_mvqc.json
```

For 2RH1, `organic` is the generic ligand/cofactor selector. Use a specific residue name when
the scientific question requires it. Run `mvqc_clear` between unrelated demo cases to remove
only plugin-owned visuals and state.
