# Validation

Validation demonstrates software reproducibility and graceful behaviour. It does not establish
biological correctness or membrane orientation.

## Released v0.1 results

Environment: Incentive PyMOL 3.1.8 with bundled Python 3.10.20.

| Case | Total | Geometric core | Charged review | Polar inspect | Ligand neighbours | Software result |
|---|---:|---:|---:|---:|---:|---|
| 1UBQ soluble control | 76 | 40 | 11 | 13 | 0 | completed with manual-orientation warning |
| 1C3W bacteriorhodopsin | 222 | 147 | 11 | 30 | 88 | completed |
| 2RH1 GPCR | 442 | 269 | 38 | 66 | 96 | completed |
| 1PCR reaction centre | 823 | 176 | 43 | 33 | 241 | completed |
| synthetic bad-core Lys | 10 | 10 | 1 | 0 | 0 | regression invariant satisfied |

The 1UBQ slab intersection is arbitrary geometry and must not be interpreted as membrane biology.

## Unreleased Stage 2 rigid-transform result

The script generates `r' = Rr+t` with `R=[[0,0,1],[0,1,0],[-1,0,0]]`, `t=[10,-5,3]`, centre
`t`, and normal `[1,0,0]`. With offsets `[-15,15]`, rotated 1UBQ exactly preserves the legacy
summary: 76 total, 40 core, 11 charged, 13 polar, zero ligand neighbours. This validates software
invariance, not biological orientation of RCSB coordinates.

## Commands and results

```powershell
<PYMOL_PYTHON> -m pytest tests -q --basetemp C:\tmp\mvqc-full-tests
<PYMOL_PYTHON> -m compileall -q membrane_vqc scripts
<PYMOL> -cq tests\pymol_smoke\smoke_import.py
<PYMOL> -cq tests\pymol_smoke\validate_structures.py
```

Stage 2 local result: 153 tests passed with 80% combined coverage; Ruff, schema validation, smoke
import, five legacy structures, and the rotated structure passed.
The unreleased build and its generated schema-1.1 reports use development version `0.2.0.dev0`;
the Plugin Manager archive is `dist/MembraneVisualQC-0.2.0.dev0.zip`.

Released v0.1 interactive validation passed. The new Stage 2 file mode still needs an interactive
GUI pass before Stage 2 completion.
