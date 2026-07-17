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

## v0.2.0 rigid-transform result

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

The accepted development build produced 153 passing tests with 80% combined coverage; Ruff,
schema validation, smoke import, five legacy structures, and the rotated structure passed. Final
v0.2.0 release-candidate results are recorded separately below and in `Report.md`.

## Historical Stage 2 graphical acceptance (`0.2.0.dev0`)

The Stage 2 file mode passed complete graphical acceptance on 2026-07-15 with Windows 10 build
26200 and Incentive PyMOL 3.1.8 (bundled Python 3.10.20). The tested development ZIP SHA-256 was
`841abe95cad44b99108cb4834ad593ef0bb4e99f64b8572cad87f088a5ac8307`.

Arbitrary-plane rendering, plane footprint/framing, source display, UTF-8 progress text, review
styling, schema-1.1 export, orientation provenance, residue-depth fields, invalid zero-normal
handling, and summary equivalence all passed. Invalid Run QC cleared stale report/review state;
invalid Show Slab cleared stale slab objects; both reset the source to `unavailable` without a
graphical traceback. `mvqc_clear` preserved `1UBQ_rotated`.

The manual report contains 24 review items (11 `WARNING`, 13 `INSPECT`) and is retained as
`reports/manual_stage2_check.json` with its CSV companion. Installed-ZIP execution correctly
records commit provenance as unavailable, and structure provenance is unavailable because no
explicit `input_path` was supplied.

The default schema-validation command includes this manual report alongside the six generated
fixtures; all seven schema-1.1 reports validate in CI.

These screenshots and manual exports are retained with their original `0.2.0.dev0` identity and
are not represented as final-build output. The final `0.2.0` ZIP requires a shorter graphical
release smoke test because the accepted feature implementation is unchanged.

## v0.2.0 release-candidate validation

The release candidate uses `dist/MembraneVisualQC-0.2.0.zip`; generated current example reports
record `software.version = 0.2.0`. Report schema 1.0 remains immutable and v0.2.0 produces report
schema 1.1. Ordinary RCSB coordinates are not automatically membrane-oriented, imported
orientation metadata is not independently verified, and depth values are geometric evidence—not
proof of biological burial.

Automated validation passed: 153 tests with 80% combined coverage, seven valid schema-1.1 reports,
PyMOL smoke import, five legacy structures, rotated 1UBQ, and the preparation helper. Wheel and
sdist built successfully. Two independent Plugin ZIP builds were byte-for-byte identical; the
27,459-byte candidate SHA-256 is
`084a7e384364bc46b5b9b3ecdc1b705a4ac80d15e6c320d25f0e1c9f6ec16054`. The short graphical
release smoke passed separately from the historical Stage 2 acceptance. It used the exact final
ZIP with SHA-256 `084a7e384364bc46b5b9b3ecdc1b705a4ac80d15e6c320d25f0e1c9f6ec16054`:
Plugin Manager installation/restart, both orientation modes, the rotated helper, arbitrary-plane
Show Slab, summary `76/40/11/13/0`, schema-1.1/version-0.2.0 export, readable invalid-file handling,
and preservation of `1UBQ_rotated` by `mvqc_clear` all passed.

## Unreleased Stage 3A validation policy

Stage 3A uses development version `0.3.0.dev0` and
`dist/MembraneVisualQC-0.3.0.dev0.zip`. It must preserve every v0.2 legacy summary and keep
exposure disabled unless explicitly requested. Required checks include analytical and invariance
fixtures for the built-in backend, optional FreeSASA parity, timing on the synthetic fixture and
1UBQ/1C3W/2RH1/1PCR, schema 1.2 draft validation, current PyMOL headless validation, and a
deterministic double ZIP build. Coverage may not fall below 80%.

## Stage 3A local exposure validation

The opt-in built-in backend was exercised in Incentive PyMOL 3.1.8 with 240 sphere points and a
1.4 Å probe. All five generated exposure reports declare draft schema 1.2 and
`software.version = 0.3.0.dev0`; the seven context-disabled and historical reports remain schema
1.1. `python scripts/validate_example_reports.py` validated all 12 by declared version.

| Structure | protein atoms | review targets | exposure seconds |
|---|---:|---:|---:|
| synthetic `bad_core_lys` | 51 | 1 | 0.014 |
| 1UBQ | 602 | 24 | 0.736 |
| 1C3W | 1,720 | 41 | 1.032 |
| 2RH1 | 3,601 | 104 | 3.940 |
| 1PCR | 6,494 | 76 | 2.804 |

An initial 28–30 s 1PCR path was investigated and traced to re-sorting all model atoms for every
target atom. Reusing stable identity order removed that O(target × N log N) overhead while
retaining the predeclared invariance tolerances. These timings are observations, not promises.

FreeSASA is absent locally, so normal analysis reports `freesasa_status = unavailable` without a
traceback and the parity test is skipped. A separate non-blocking Python 3.11 CI job installs the
`exposure-reference` extra and runs same-radii parity.

The complete local result is 201 passed, one skipped, and 83% combined coverage. Ruff check and
format check passed. Wheel and sdist built successfully. Two consecutive Plugin ZIP builds were
byte-identical; `MembraneVisualQC-0.3.0.dev0.zip` is 40,071 bytes with SHA-256
`ad4db155cd38a07d2321cdb557edb8c7ef04417fc1d5e3034fd1065817f4f0e3`, and the project ZIP
validator accepted it.
