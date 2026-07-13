# Membrane Visual QC demo scene.
# Public structures must be downloaded first; see data/README.md.

reinitialize

# Synthetic deterministic charged-core example.
load data/synthetic/bad_core_lys.pdb, bad_core_lys
show cartoon, bad_core_lys
mvqc_slab zmin=-15, zmax=15
mvqc_check selection=bad_core_lys, zmin=-15, zmax=15, ligand=organic, cutoff=5.0
mvqc_export path=reports/bad_core_lys_mvqc.json

# Uncomment after downloading public mmCIF files.
# load data/raw/1UBQ.cif, 1UBQ
# mvqc_check selection=1UBQ, zmin=-15, zmax=15, ligand=organic, cutoff=5.0
# mvqc_export path=reports/1ubq_mvqc.json

# load data/raw/1C3W.cif, 1C3W
# mvqc_check selection=1C3W, zmin=-15, zmax=15, ligand=organic, cutoff=5.0
# mvqc_export path=reports/1c3w_mvqc.json

# load data/raw/2RH1.cif, 2RH1
# mvqc_check selection=2RH1, zmin=-15, zmax=15, ligand=organic, cutoff=5.0
# mvqc_export path=reports/2rh1_mvqc.json

# load data/raw/1PCR.cif, 1PCR
# mvqc_check selection=1PCR, zmin=-15, zmax=15, ligand=organic, cutoff=5.0
# mvqc_export path=reports/1pcr_mvqc.json

zoom bad_core_lys
