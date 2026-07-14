# Development state

Snapshot date: 2026-07-14 (Europe/Moscow).

Stage 1 is closed. Immutable tag `v0.1.0` points to
`a8c7959fb1d53dd99771a184443aa16afd287aa6`; its prerelease remains unchanged. Release workflow
[29289031923](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29289031923) passed on
Python 3.10, 3.11, and 3.12. Graphical v0.1 validation passed with Incentive PyMOL 3.1.8.

## Unreleased Stage 2

Work is isolated on `feat/planar-orientation-depth` in draft PR
[#2](https://github.com/TrPavel/membrane-visual-qc/pull/2); it is not merged or released.

Implemented:

- immutable pure-Python `PlanarMembrane` and one classifier for legacy/global and arbitrary planes;
- signed, centre, boundary, outside, and asymmetric normalised depth;
- strict local orientation JSON/schema with deterministic serialisation and SHA-256 provenance;
- report schema 1.1 while released schema 1.0 stays immutable;
- arbitrary-plane CGO rendering sized from selection extents;
- orientation-file commands and minimal GUI mode;
- deterministic rotation/translation/reversal tests and a rotated 1UBQ PyMOL fixture.

The unchanged `mvqc_check zmin/zmax` maps to centre `(0,0,0)`, normal `(0,0,1)`, and source
`manual_global_z`. All five legacy summaries remain unchanged; `bad_core_lys` remains 10 core and
exactly one charged review item. Rotated 1UBQ uses
`R=[[0,0,1],[0,1,0],[-1,0,0]]`, `t=[10,-5,3]`, and normal `[1,0,0]`, with the complete summary
equal to legacy 1UBQ.

Stage 2 uses development version `0.2.0.dev0` consistently in package metadata, generated reports,
wheel/sdist names, and `dist/MembraneVisualQC-0.2.0.dev0.zip`. Local correction evidence:
Ruff passed; 145 tests passed with 76% combined coverage; six schema-1.1 reports validated; PyMOL
3.1.8 smoke plus five legacy and one rotated case passed; wheel/sdist built; two development ZIPs
were byte-identical. The correction-build ZIP SHA-256 is
`a93010fad30c4ba2869fc65adb4ea72ae02230bf543d63c6dd98a9e6e58e8677`; it is not a replacement
for the published v0.1 asset.

The final pre-correction head `29ab66a4e8bf35b6f73b70049f7595b3f3700139` passed real draft-PR
CI in [GitHub Actions run 29350123791](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29350123791)
for Python 3.10, 3.11, and 3.12. Earlier implementation run
[29349967133](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29349967133) remains
historical evidence. Remaining: interactive acceptance of the new GUI file mode and arbitrary
plane. Keep PR #2 draft and do not merge it.
