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

## Historical Stage 3A development validation policy

Stage 3A uses development version `0.3.0.dev0` and
`dist/MembraneVisualQC-0.3.0.dev0.zip`. It must preserve every v0.2 legacy summary and keep
exposure disabled unless explicitly requested. Required checks include analytical and invariance
fixtures for the built-in backend, optional FreeSASA parity, timing on the synthetic fixture and
1UBQ/1C3W/2RH1/1PCR, schema 1.2 draft validation, current PyMOL headless validation, and a
deterministic double ZIP build. Coverage may not fall below 80%.

## Stage 3A local exposure validation

The opt-in built-in backend was exercised in Incentive PyMOL 3.1.8 with 240 sphere points and a
1.4 Å probe. All five historical development exposure reports declare draft schema 1.2 and
`software.version = 0.3.0.dev0`; the seven context-disabled and historical reports remain schema
1.1. `python scripts/validate_example_reports.py` validated all 12 by declared version.

| Structure | protein atoms | review targets | exposure seconds |
|---|---:|---:|---:|
| synthetic `bad_core_lys` | 51 | 1 | 0.018 |
| 1UBQ | 602 | 24 | 0.653 |
| 1C3W | 1,720 | 41 | 0.979 |
| 2RH1 | 3,601 | 104 | 4.098 |
| 1PCR | 6,494 | 76 | 2.854 |

An initial 28–30 s 1PCR path was investigated and traced to re-sorting all model atoms for every
target atom. Reusing stable identity order removed that O(target × N log N) overhead while
retaining the predeclared invariance tolerances. These timings are observations, not promises.

FreeSASA is absent in the Windows environment, so normal analysis reports
`freesasa_status = unavailable` without a traceback and five local reference tests are skipped. A
separate Ubuntu run with FreeSASA 2.2.1 passed all seven tests. It confirmed that singleton models
never enter native `calcCoord`, return explicit unavailable evidence, and that mixed singleton plus
valid models produce a partial result. Non-protein occluder tests also confirm exact selection
scope, protein-only targets, truthful serialized configuration, and cross-model isolation.

The complete Windows result is 246 passed, five FreeSASA reference tests skipped, and 83% combined
coverage. Ruff check and format check passed. Wheel and
sdist built successfully. Two consecutive Plugin ZIP builds were byte-identical;
`MembraneVisualQC-0.3.0.dev0.zip` is 41,209 bytes with SHA-256
`3c8fb30e9b3dd259c7759c2cbb736326856492cfbcfe6fd78ead101e40914722`, and the project ZIP
validator accepted it.

Element-inference safety tests confirm that missing protein C/N/O/S metadata remains usable,
unambiguous supported ligand elements remain available, and recognized unsupported two-letter
HETATM elements cannot fall back to scientifically false one-letter radii.

The previous implementation workflow
[29573971744](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29573971744) is historical.
Head `60872c70d570b5821f1b2cc1bfe271798100ec7c` and workflow
[29576377936](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29576377936) are the
validated correction baseline immediately before this final safety pass; all three Python matrix
jobs and the blocking Python 3.11 FreeSASA reference job passed.

## Stage 3A CI closure

Final PR head `b7491ab7cf82e473635bf3191abb960b0b7adcde` passed
[workflow 29584460029](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29584460029).
PR [#4](https://github.com/TrPavel/membrane-visual-qc/pull/4) was squash-merged as
`294cf52912e0006d413316b89d7a55fed43f1429`. The subsequent `main`
[workflow 29584633452](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29584633452)
passed all four jobs: Python 3.10, 3.11, 3.12, and the blocking Python 3.11 FreeSASA reference job.
Stage 3A is complete and merged into main; the section below records the subsequent Stage 3B work.

## Historical Stage 3B development local-context validation

Stage 3B is opt-in and retains development version `0.3.0.dev0`. The pure-Python suite covers all
contact and context-state labels, inclusive and just-outside cutoffs, same-model inter-chain and
cross-model isolation, histidine ambiguity, altlocs, input-order and rigid-transform invariance,
missing/unsupported elements, schema 1.2, deterministic exports, GUI forwarding, and PyMOL
ownership/lifecycle/colour precedence.

The lifecycle-corrected Windows result is 299 passed, eight optional FreeSASA tests skipped, and 85% combined
coverage. Ruff check and format check passed. Eighteen reports validated: seven schema 1.1 and
eleven schema 1.2. Wheel and sdist built successfully. The corrected development artifact
`MembraneVisualQC-0.3.0.dev0.zip` is 49,414 bytes with SHA-256
`53a34dddcb1d3157f240d03ece3251c6c0565f5bb4bead70c807d641de9a65a1`.

Headless Incentive PyMOL 3.1.8 passed smoke import, all legacy summaries, rotated 1UBQ, Stage 3A
exposure, the preparation helper, the deterministic context fixture, all four context visual
objects, and five-structure timing. Observed local-context times at Standard quality were 0.001 s
synthetic, 0.116 s 1UBQ, 1.068 s 1C3W, 6.063 s 2RH1, and 10.362 s 1PCR. These are observations, not
promises. The blocking Ubuntu/FreeSASA job remains required in PR CI.

The correction suite also verifies the real FreeSASA orchestration signature (including explicit
and Auto selection), schema 1.2 command output, the shared five-state review priority, WARNING
before INSPECT, unchanged CSV residue order, strict 0/1 command parsing, the exact six-type contact
vocabulary, unsupported HETATM warnings, and zero optional-category count semantics.

The stateful headless PyMOL lifecycle regression runs context ON, OFF, ON, and ON again in one
process, then attempts an invalid orientation file. It verifies recreation/removal of review and
context selections, the absence of invalid-review-selection failures, cleared plugin state and
`LAST_REPORT`, and preservation of the original structure object. This directly covers the
graphical blocker found after the initially successful rendering checks.

Focused graphical acceptance passed on Windows 10 build 26200, Incentive PyMOL 3.1.8, and bundled
Python 3.10.20 with the exact corrected 49,414-byte ZIP, SHA-256
`53a34dddcb1d3157f240d03ece3251c6c0565f5bb4bead70c807d641de9a65a1`. Installation/restart,
`ON → OFF → ON → ON → invalid orientation`, selection recreation, invalid-file cleanup without a
traceback, schema 1.2 export and unchanged CSV columns, `mvqc_clear` input preservation,
Standard/Built-in responsiveness, and rotated 1UBQ `76/40/11/13/0` passed. The prior SHA
`411752e953785452d58babd0840df425bc1f3f9f3f4d488d106b4489050fdddf` remains partial historical
evidence. Stage 3B graphical acceptance is complete.

Graphical integration is accepted. Final PR head `0c08029b15baa2786681a0d73002d89f7d4e36db`
passed [workflow 29643963613](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29643963613).
The squash merge commit is `bc29918686206292c00a13cc74d6d20e60292653`, and
[post-merge workflow 29644011836](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29644011836)
passed Python 3.10, 3.11, 3.12, and FreeSASA.

Stage 3B is complete and merged into main.

Stage 3 is complete and merged into main.

## v0.3.0 release-candidate validation

The active release-candidate identity is `0.3.0`; its Plugin Manager artifact is
`dist/MembraneVisualQC-0.3.0.zip`. Schemas 1.0 and 1.1 remain immutable. Schema 1.2 is the
scientifically frozen v0.3.0 release contract for opt-in exposure/context reports and becomes
immutable on publication; context-disabled runs continue to emit schema 1.1. The exact final ZIP
has passed the separate graphical packaging/version prerequisite for opening the release PR.

Local results: Ruff check and format check passed; 299 tests passed, eight optional FreeSASA tests
were skipped on Windows, and combined coverage is 85%. Eighteen reports validated (seven schema
1.1 and eleven schema 1.2). The retained headless PyMOL suite, distribution inspection, ZIP
validator, and byte-for-byte deterministic double ZIP build passed. The 49,415-byte candidate
SHA-256 is `ae6bddcd95bd96be590077849879c64d57a07c0bffacf1779ff526ea22ddd7cb`.

The blocking Ubuntu Python 3.11 FreeSASA job cannot run locally because this Windows workspace has
neither FreeSASA, WSL, nor a running Docker engine. It remains a required release-PR job alongside
the Python 3.10, 3.11, and 3.12 matrix.

The exact 49,415-byte ZIP graphical smoke passed on 2026-07-18 with SHA-256
`ae6bddcd95bd96be590077849879c64d57a07c0bffacf1779ff526ea22ddd7cb`. All focused packaging,
version, context-default, synthetic summary, context-selection, export/fallback, lifecycle,
invalid-orientation cleanup, structure-preservation, and rotated-1UBQ checks passed. This evidence
is recorded separately from the unchanged historical `0.3.0.dev0` acceptance.

## v0.3.0 publication verification

Final PR workflow [29649788155](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29649788155)
and post-merge `main` workflow
[29649853994](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29649853994) passed Python
3.10, 3.11, 3.12, and the blocking Ubuntu FreeSASA job. The final release commit is
`5caf9ee0d89721ccfa560de9136b82cc87436c3b`.

All four uploaded release assets were downloaded again. Each matched its local source
byte-for-byte; the ZIP remained 49,415 bytes with SHA-256
`ae6bddcd95bd96be590077849879c64d57a07c0bffacf1779ff526ea22ddd7cb`, the checksum file contained
the same digest, and wheel/sdist metadata reported `0.3.0`. Schema 1.2 is released and immutable
with SHA-256 `96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`.

The v0.1.0/v0.2.0 tag objects, targets, prereleases, and asset sets remain unchanged. The PyPI JSON
endpoint returns 404 for this distribution. Stage 4 has not started.

## Stage 4A1 offline-import development validation

The Stage 4A1 core validation uses only synthetic PDBTM-compatible JSON and legacy-PDB payloads.
No official provider payload is committed or used by CI. The local Windows gate passed Ruff check
and format check, 384 tests with eight optional FreeSASA skips, 87% combined coverage, and 19
schema-valid reports (1.1: 7, 1.2: 11, 1.3: 1). Wheel and sdist build as version `0.4.0.dev0`.

Schema-1.3 examples pass two distinct gates: JSON Schema validates the structural contract, then
the mandatory Stage 4 semantic validator checks nonlinear scientific invariants using the same
`1e-9` domain tolerance. Adapter tests also require the exact payload-role sets: JSON-only for
partial provenance, or one `pdbtm_json` plus one `transformed_pdb` for an imported result.

Two independent Plugin ZIP builds were byte-for-byte identical. The validated development ZIP is
`dist/MembraneVisualQC-0.4.0.dev0.zip`, 65,209 bytes, SHA-256
`059264627139ec1a2091fd0f7604d42e16297062f5d5349d270ef53edad0fc9e`.

Schema hashes are 1.0
`5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710`, 1.1
`86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf`, 1.2
`96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`, and draft 1.3
`6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`.
The Python 3.10/3.11/3.12 and blocking Ubuntu FreeSASA results are recorded by the draft-PR
workflow; GUI/PyMOL integration is not part of this validation phase.

## Stage 4A2 offline PyMOL integration validation

The Stage 4A2 branch adds real Incentive PyMOL 3.1.8 snapshot probes and headless workflows. A
translated object proved that `cmd.get_pdbstr(object, state=1)` matches current coordinates from
`get_model` and `get_coords`; the command layer therefore validates a single snapshot of the
complete containing object. Synthetic identity/inverse imports, context OFF/ON, schema 1.3,
current-frame slab rendering, repeated lifecycle, failure cleanup, and input preservation pass.

Ignored local official payloads for `1pcr` and `1a0s` pass identity and analytical-inverse paths;
wrong pairs and manually changed coordinate frames are rejected. Provider payloads remain outside
Git.

Exact-artifact graphical acceptance passed on Windows 10 build 26200 with Incentive PyMOL 3.1.8
and bundled Python 3.10.20. The installed `MembraneVisualQC-0.4.0.dev0.zip` was 69,251 bytes with
SHA-256 `3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`. Both file choosers and
all three orientation modes passed with correctly rendered Unicode. The `1pcr` and `1a0s` identity
and inverse-provider-transform cases passed with unchanged coordinates and schema 1.3; 1pcr
context OFF/ON, JSON/CSV export, structural plus semantic validation, and absence of absolute local
paths also passed. Wrong-pair and transformed-coordinate errors produced no traceback, fitting, or
fallback and cleared stale plugin/report state. Repeated lifecycle, `mvqc_clear`, global-z, and
planar orientation-file regressions passed. Full observations are recorded in
`docs/stage4a2_graphical_acceptance.md`.

The corrected local suite passed Ruff check/format, 418 tests with eight optional FreeSASA skips,
87% combined coverage, and 19 reports (schema 1.1: 7, 1.2: 11, 1.3: 1). Wheel and sdist built as
`0.4.0.dev0`. Two corrected Plugin ZIP builds were byte-identical: 69,251 bytes, SHA-256
`3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`. The superseded
pre-review artifact had SHA-256 `446f7af119508dd8f66396dfbc39b4444517a5b2dac9d46368f34ee07cbacb92`.

Released schema hashes remain unchanged: schema 1.0
`5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710`, schema 1.1
`86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf`, and schema 1.2
`96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`. Draft schema 1.3 remains
`6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`.

The v0.4.0 release candidate promotes the active version to `0.4.0` and freezes schema 1.3 as an
immutable release contract without changing its accepted bytes. Schema-1.3 validation remains
structural plus semantic. Historical `0.4.0.dev0` acceptance evidence above remains unchanged.
No network retrieval, OPM integration, source comparison, automatic alignment, tag, GitHub
Release, or PyPI publication was added; Stage 4B has not started.

The local v0.4.0 release-candidate gate passed Ruff check and format check, 421 tests with eight
optional FreeSASA skips, 87% combined coverage, and all 19 example reports (schema 1.1: 7, schema
1.2: 11, schema 1.3: 1). Wheel and sdist metadata report `0.4.0`; the sdist contains the package,
immutable schemas, synthetic fixtures, and validation scripts without report exports. The release-artifact
validator also confirms active schema-1.3 report identity, clean archive layouts, Plugin Manifest
consistency, and the exact checksum sidecar.

Two Plugin ZIP builds were byte-identical. `MembraneVisualQC-0.4.0.zip` is 69,241 bytes with
SHA-256 `bba1891a8fa84c0575442d17daccbb6a6ad3bc54e60ad626ac1000cc59a079b5`.
The standard setuptools wheel and sdist contain timestamps and therefore are not asserted to be
byte-reproducible across separate builds; their version metadata and required contents pass the
deterministic validator. The blocking Python matrix and Ubuntu FreeSASA job remain required in the
draft PR workflow.

The final publication assets are frozen from workflow `29703424337`, artifact ID `8447146429`,
archive digest `ff7eab5b149452795d37d85059a938598fd6c16b4a6bb6d08f7c61495d08f5ed`.
The authoritative wheel is 73,261 bytes with SHA-256
`449e091743e5811da70c5309c86274abc5a4144cd8a842fc61f1723552b1b658`; the authoritative
sdist is 128,782 bytes with SHA-256
`8853b893e08a33feb742c9679241116628955c995ded12898a9ea407c38f1c07`. Inspection confirmed
version `0.4.0`, wheel tag `py3-none-any`, schemas 1.0–1.3 in the sdist, and absence of `.local`,
reports, manual Stage 4A2 exports, official provider payloads, and unsafe paths. Byte reproducibility
is not claimed for wheel or sdist.

`reports/pdbtm_synthetic_mvqc.json` was regenerated from release-preparation parent commit
`2f0247474c1b1a8da59c7307fa12fba8c009ca97` at `2026-07-19T20:48:41.424766+00:00`. Its current
payload digests and commit provenance are generated rather than hand-promoted; structural schema
1.3 and mandatory Stage 4 semantic validation both pass.

Exact v0.4.0 release-artifact graphical smoke passed on Windows 10 build 26200 with Incentive
PyMOL 3.1.8 and bundled Python 3.10.20. The tested authoritative Plugin ZIP is 69,241 bytes with
SHA-256 `bba1891a8fa84c0575442d17daccbb6a6ad3bc54e60ad626ac1000cc59a079b5` and is
byte-identical to the ZIP from corrected workflow `29703424337`. Identity and analytical-inverse
1pcr cases, failure cleanup, `mvqc_clear`, legacy global-Z, planar orientation-file regression,
version `0.4.0`, schema 1.3, Unicode rendering, and coordinate preservation passed. Relatively low
slab contrast remains a non-blocking pre-v1.0 backlog item. The exact authoritative Plugin ZIP is
approved for publication; `docs/v0.4.0_graphical_smoke.md` records the complete evidence.
