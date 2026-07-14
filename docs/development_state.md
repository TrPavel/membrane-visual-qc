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

Local evidence before push: Ruff passes; 144 tests pass with 76% combined coverage; six schema-1.1
reports validate; PyMOL 3.1.8 smoke plus five legacy and one rotated case pass; wheel/sdist build;
two development ZIPs are byte-identical. The final development ZIP hash is recorded in
`Report.md`; it is not a replacement for the published v0.1 asset.

Real draft-PR CI passed in
[GitHub Actions run 29349967133](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29349967133)
for Python 3.10, 3.11, and 3.12. Remaining: an interactive check of the new GUI file mode and
arbitrary plane. Do not merge automatically.
