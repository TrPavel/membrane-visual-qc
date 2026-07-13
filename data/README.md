# Data

This folder is for local validation structures and synthetic examples used by the Membrane Visual QC MVP.

## Folder Layout

- `raw/`: downloaded public structures, primarily mmCIF from RCSB PDB.
- `processed/`: cleaned or demo-ready copies, if needed.
- `synthetic/`: artificial structures for deterministic tests.

The four public structures are present in this development workspace. Their current files predate
the reproducible data-manifest workflow, so they should not yet be treated as a published
benchmark bundle with complete provenance.

The repository's MIT licence applies to the original project code, documentation, and synthetic
test fixture. Downloaded RCSB PDB structure files remain subject to their source terms and are not
relicensed by this project.

## Recommended Public Structures

| File | Role | Expected use |
|---|---|---|
| `data/raw/1C3W.cif` | bacteriorhodopsin | compact 7-TM protein with retinal and buried polar features |
| `data/raw/2RH1.cif` | beta-2 adrenergic receptor | GPCR with small-molecule ligand |
| `data/raw/1PCR.cif` | photosynthetic reaction centre | multi-chain, cofactor-rich membrane complex |
| `data/raw/1UBQ.cif` | ubiquitin | soluble negative control |

PowerShell:

```powershell
mkdir data\raw -Force
$ids = @("1C3W", "2RH1", "1PCR", "1UBQ")
foreach ($id in $ids) {
    Invoke-WebRequest -Uri "https://files.rcsb.org/download/$id.cif" -OutFile "data\raw\$id.cif"
}
```

Bash:

```bash
mkdir -p data/raw
for id in 1C3W 2RH1 1PCR 1UBQ; do
  curl -L "https://files.rcsb.org/download/${id}.cif" -o "data/raw/${id}.cif"
done
```

## Synthetic Data

`data/synthetic/bad_core_lys.pdb` is deliberately artificial. It places a simple helix-like chain through the manual slab and includes one `LYS` near `z=0`.

Expected use:

```pml
load data/synthetic/bad_core_lys.pdb
mvqc_check selection=bad_core_lys, zmin=-15, zmax=15
```

Expected interpretation: the charged core residue should be reported as a deterministic inspection warning. This file is not biologically realistic and should not be used for scientific interpretation beyond testing the warning path.
