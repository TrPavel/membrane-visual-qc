# Validation

Validation demonstrates software reproducibility and graceful behaviour. It does not establish
biological correctness or membrane orientation.

## Automated results (2026-07-13)

Environment: Incentive PyMOL 3.1.8 with bundled Python 3.10.20.

| Case | Total | Geometric core | Charged review | Polar inspect | Ligand neighbours | Software result |
|---|---:|---:|---:|---:|---:|---|
| 1UBQ soluble control | 76 | 40 | 11 | 13 | 0 | completed with manual-orientation warning |
| 1C3W bacteriorhodopsin | 222 | 147 | 11 | 30 | 88 | completed |
| 2RH1 GPCR | 442 | 269 | 38 | 66 | 96 | completed |
| 1PCR reaction centre | 823 | 176 | 43 | 33 | 241 | completed |
| synthetic bad-core Lys | 10 | 10 | 1 | 0 | 0 | regression invariant satisfied |

The 1UBQ slab intersection is arbitrary geometry and must not be interpreted as membrane
biology. All generated reports record `orientation.source = manual`.

## Commands and results

```powershell
<PYMOL_PYTHON> -m pytest tests -q --basetemp C:\tmp\mvqc-full-tests
<PYMOL_PYTHON> -m compileall -q membrane_vqc scripts
<PYMOL> -cq tests\pymol_smoke\smoke_import.py
<PYMOL> -cq tests\pymol_smoke\validate_structures.py
```

Results: 40 unit tests passed; compilation passed; smoke import and five-structure headless
validation passed. A third-party PyMOL licensing `DeprecationWarning` was the only warning.

Plugin Manager installation and interactive Qt behaviour require the checklist in
`docs/manual_gui_validation.md`. Ruff is configured for CI but unavailable in the verified
local PyMOL interpreter.
