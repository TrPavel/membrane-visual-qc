# Membrane Visual QC quickstart demo.
# Run from the project root after plugin commands are implemented and loaded.

reinitialize
load data/synthetic/bad_core_lys.pdb, bad_core_lys
hide everything
show cartoon, bad_core_lys
color gray70, bad_core_lys

# Manual membrane slab: geometric inspection only, not definitive validation.
mvqc_slab zmin=-15, zmax=15
mvqc_check selection=bad_core_lys, zmin=-15, zmax=15, ligand=organic, cutoff=5.0
mvqc_color_hydropathy selection=bad_core_lys
mvqc_export path=reports/bad_core_lys_mvqc.json

zoom bad_core_lys
