# Development state

Snapshot date: 2026-07-17 (Europe/Moscow).

Stage 1 is closed. Immutable tag `v0.1.0` points to
`a8c7959fb1d53dd99771a184443aa16afd287aa6`; its prerelease remains unchanged. Release workflow
[29289031923](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29289031923) passed on
Python 3.10, 3.11, and 3.12. Graphical v0.1 validation passed with Incentive PyMOL 3.1.8.

## Stage 2 — merged and accepted

Stage 2 was squash-merged from
[#2](https://github.com/TrPavel/membrane-visual-qc/pull/2) into `main`. Release preparation is
isolated on `release/v0.2.0`; Stage 3 has not started.

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

The accepted Stage 2 build used development version `0.2.0.dev0` consistently in package metadata,
generated reports, wheel/sdist names, and `dist/MembraneVisualQC-0.2.0.dev0.zip`. Historical local
evidence:
Ruff passed; 153 tests passed with 80% combined coverage; seven schema-1.1 reports validated; PyMOL
3.1.8 smoke plus five legacy and one rotated case passed; wheel/sdist built; two development ZIPs
were byte-identical. The correction-build ZIP SHA-256 is
`841abe95cad44b99108cb4834ad593ef0bb4e99f64b8572cad87f088a5ac8307`; it is not a replacement
for the published v0.1 asset.

The final lifecycle correction removes duplicate GUI orientation parsing. Commands now clear stale
review/report or slab state before orientation-file validation, while the GUI displays returned
source metadata only after success and `unavailable` after failure. Manual and headless rotated
1UBQ preparation share `demo/rotated_1ubq_transform.py`.

Complete interactive acceptance passed on Windows 10 build 26200 with Incentive PyMOL 3.1.8. The
graphical arbitrary plane, footprint/framing, summary equivalence, review styling, exports,
orientation/depth evidence, invalid-file lifecycle, source reset, zero-normal rejection, and
`mvqc_clear` object preservation all passed. The installed ZIP correctly reported Git commit
provenance as unavailable; structure provenance was unavailable because no explicit `input_path`
was supplied. Stage 2 implementation, acceptance, and merge are complete.

Final PR head `272f288819965e72a53e4ea6fe3cb953131c3881` passed
[PR workflow 29410043646](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29410043646)
on Python 3.10, 3.11, and 3.12. It was squash-merged as
`faa7bae062c4ae43a9e9b738f6392bc2a228eb0e`; the corresponding
[post-merge main workflow 29410159752](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29410159752)
also passed all three jobs.

## Final Stage 2 status

Stage 2 is complete and merged into main.

## v0.2.0 release candidate

The release branch promoted package metadata, generated current examples, and artifact names to
`0.2.0`. The final Plugin Manager artifact is `dist/MembraneVisualQC-0.2.0.zip`. Historical
manual exports and screenshots retain their truthful `0.2.0.dev0` identity. Report schema 1.0
remains immutable; v0.2.0 produces additive report schema 1.1.

Automated release-candidate results and the short graphical smoke of the exact final ZIP are
recorded separately in `Report.md` and `reports/release_validation.json`. The v0.1.0 tag and release
remain immutable.

Local automated release-candidate validation passed: 153 tests, 80% combined coverage, seven
schema-1.1 reports, PyMOL smoke plus all five legacy and rotated fixtures, the preparation helper,
wheel/sdist, and deterministic double ZIP build. The 27,459-byte candidate SHA-256 is
`084a7e384364bc46b5b9b3ecdc1b705a4ac80d15e6c320d25f0e1c9f6ec16054`. The exact-artifact
graphical smoke also passed with that exact artifact.

Release PR [#3](https://github.com/TrPavel/membrane-visual-qc/pull/3) passed
[workflow 29487841498](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29487841498)
and was squash-merged as `7877fed3c83419e6affa1e4353a65f8756e9303a`. The
[post-merge workflow 29488017586](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29488017586)
passed on Python 3.10, 3.11, and 3.12. Annotated tag `v0.2.0` points to that release commit, and the
[v0.2.0 GitHub prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.2.0)
contains the four verified assets. PyPI was not used. Stage 3 had not started at publication;
Stage 3A is now isolated on its own development branch.

v0.2.0 is published as a prerelease for limited public testing.

## Stage 3A — exposure foundation

Unreleased work is isolated on `feat/exposure-foundation` with development version `0.3.0.dev0`.
Stage 3A passed its research and ADR-0003/ADR-0004 semantics gate. Its built-in deterministic
Shrake–Rupley backend reports solvent-accessible surface area, relative solvent accessibility,
and membrane-region accessible area without claiming lipid accessibility. FreeSASA is optional and
lazy. Report schema 1.2 is an unreleased draft; released schemas 1.0 and 1.1 remain immutable.

The pure-Python backend uses 240 deterministic golden-spiral points by default, a 1.4 Å probe,
the versioned `element_vdw_v1` Bondi radius table, the complete Tien et al. 2013 theoretical
20-residue maximum-ASA scale, deterministic alternate-location collapse, per-model isolation, and
a spatial cell list. Exposure runs only when an `ExposureConfig` is supplied. Context-disabled
calls still produce schema 1.1 and preserve the released v0.2 behaviour.

Draft PR [#4](https://github.com/TrPavel/membrane-visual-qc/pull/4) remains unmerged. Local PyMOL
3.1.8 validation produced five schema-1.2 exposure reports and retained every legacy summary.
Measured 240-point exposure times were 0.018 s synthetic, 0.653 s 1UBQ, 0.979 s 1C3W, 4.098 s
2RH1, and 2.854 s 1PCR. These are development observations, not runtime guarantees.

Current local validation: Ruff check and format check passed; 211 tests passed, five FreeSASA
reference tests skipped because FreeSASA is unavailable in the Windows environment, and combined
coverage is 83%. A separate Ubuntu/FreeSASA 2.2.1 run passed all seven reference tests.
Twelve reports validated (seven schema
1.1 and five draft schema 1.2). PyMOL smoke, five legacy fixtures, rotated 1UBQ, the exposure
timing set, and the preparation helper passed. Wheel and sdist built as `0.3.0.dev0`. Two Plugin
ZIP builds were byte-identical at SHA-256
`342fbffcf01dcad1f2847b873358c5292be908c0e9676259bedc0f7871988f51`; the ZIP is 40,529
bytes. Singleton FreeSASA models are now guarded before native entry, and enabled non-protein
occlusion uses all atoms inside the exact user selection while retaining protein-only targets.

Previous implementation workflow
[29573971744](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29573971744) is historical.
Head `60872c70d570b5821f1b2cc1bfe271798100ec7c` and workflow
[29576377936](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29576377936) form the
validated correction baseline immediately before the final safety pass. Python 3.10, 3.11, 3.12,
and the blocking Python 3.11 FreeSASA job passed. PR #4 remains draft and unmerged.

Stage 3B has not started and cannot begin until Stage 3A is reviewed, accepted, merged, and its
post-merge workflow is green. No v0.3.0 release is being prepared.
