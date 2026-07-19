# Development state

Snapshot date: 2026-07-19 (Europe/Moscow).

Stage 3 is complete and merged into `main`. v0.3.0 is published from the final release commit as a
GitHub prerelease for limited public testing. PyPI is not used.

Stage 4 research and architecture design are complete and merged through
[#7](https://github.com/TrPavel/membrane-visual-qc/pull/7). Final PR head
`3740c4dd8bc3a1c6f69778c4715926a19480bbfa` passed
[workflow 29652529942](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29652529942)
and was squash-merged as `bbaabaefee2274f06f954aab16446e8f7e0def7a`. The
[post-merge workflow 29652573284](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29652573284)
passed Python 3.10, 3.11, 3.12, and the blocking Python 3.11 FreeSASA job.

ADR-0005 is accepted for Stage 4A implementation, with PDBTM-only offline import as the first
implementation scope. The isolated
[PDBTM source-semantics preflight](pdbtm_semantics_preflight.md) passed on official PDBTM/RCSB
pairs `1pcr` (`Tm_Alpha`) and `1a0s` (`Tm_Beta`). Final PR head
`76d3b45bb12a09c3e49c324f73896e282f6b4aa2` passed
[workflow 29661170245](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29661170245).
[#8](https://github.com/TrPavel/membrane-visual-qc/pull/8) was squash-merged as
`c6cd9ff676514d20bcc71834449ef225b21c188a`; its
[post-merge workflow 29661211096](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29661211096)
passed Python 3.10, 3.11, 3.12, and the blocking Python 3.11 FreeSASA job.

The tested PDBTM data snapshot was resource version `1017` and the tested provider software was
`3.2.134`. The preflight verified `p_transformed = R p_original + t`, provider chain mapping,
direct transformed-companion and analytical-inverse matching without fitting, and symmetric
half-thicknesses of 12.25 angstrom for `1pcr` and 9.75 angstrom for `1a0s`. Runtime Case A uses
`runtime_identity_match_limit` of 0.002 angstrom for both RMSD and maximum residual; Runtime Case B
uses `runtime_inverse_match_limit` of 0.003 angstrom for both. Provider-forward matrix validation
is a separate per-payload precision-derived limit.

OpenAPI/API v1 required fields, documented matrix semantics, rigid transforms, and the reviewed
precision envelope define compatibility. Resource and software versions are serialized as
provenance; a resource-version increment alone is not an automatic rejection. Decimal precision
and bounds are derived from every exact payload. Changed structure/semantics, non-rigid transforms,
or precision outside the envelope return `unsupported` without reusing a historical fixed limit.
Official payloads remain local-only and outside Git because redistribution permission is unresolved.

PDBTM source-semantics preflight and Stage 4A1 are complete and merged into `main`. Stage 4A2
offline PyMOL/GUI integration is in development on `feat/pdbtm-offline-import-pymol` with identity
`0.4.0.dev0`. The branch connects the accepted core to explicit local file selection, a complete
single-state current-object snapshot, current-frame slab rendering, QC/report lifecycle, and the
third GUI orientation mode. It adds no retrieval, OPM, comparison, fitting, or automatic
alignment. v0.3.0 remains the latest published release.

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
Stage 3A was developed on its own branch and is now merged into `main`.

v0.2.0 is published as a prerelease for limited public testing.

## Historical Stage 3A development — exposure foundation

This historical work was isolated on `feat/exposure-foundation` with development version
`0.3.0.dev0`.
Stage 3A passed its research and ADR-0003/ADR-0004 semantics gate. Its built-in deterministic
Shrake–Rupley backend reports solvent-accessible surface area, relative solvent accessibility,
and membrane-region accessible area without claiming lipid accessibility. FreeSASA is optional and
lazy. At that time report schema 1.2 was an unreleased draft; released schemas 1.0 and 1.1 remain
immutable.

The pure-Python backend uses 240 deterministic golden-spiral points by default, a 1.4 Å probe,
the versioned `element_vdw_v1` Bondi radius table, the complete Tien et al. 2013 theoretical
20-residue maximum-ASA scale, deterministic alternate-location collapse, per-model isolation, and
a spatial cell list. Exposure runs only when an `ExposureConfig` is supplied. Context-disabled
calls still produce schema 1.1 and preserve the released v0.2 behaviour.

PR [#4](https://github.com/TrPavel/membrane-visual-qc/pull/4) was squash-merged into `main`. Local PyMOL
3.1.8 validation produced five schema-1.2 exposure reports and retained every legacy summary.
Measured 240-point exposure times were 0.018 s synthetic, 0.653 s 1UBQ, 0.979 s 1C3W, 4.098 s
2RH1, and 2.854 s 1PCR. These are development observations, not runtime guarantees.

Current local validation: Ruff check and format check passed; 246 tests passed, five FreeSASA
reference tests skipped because FreeSASA is unavailable in the Windows environment, and combined
coverage is 83%. A separate Ubuntu/FreeSASA 2.2.1 run passed all seven reference tests.
Twelve reports validated (seven schema
1.1 and five draft schema 1.2). PyMOL smoke, five legacy fixtures, rotated 1UBQ, the exposure
timing set, and the preparation helper passed. Wheel and sdist built as `0.3.0.dev0`. Two Plugin
ZIP builds were byte-identical at SHA-256
`3c8fb30e9b3dd259c7759c2cbb736326856492cfbcfe6fd78ead101e40914722`; the ZIP is 41,209
bytes. Singleton FreeSASA models are now guarded before native entry, and enabled non-protein
occlusion uses all atoms inside the exact user selection while retaining protein-only targets.
Unsupported two-letter HETATM elements with missing metadata are conservatively excluded.

Previous implementation workflow
[29573971744](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29573971744) is historical.
Head `60872c70d570b5821f1b2cc1bfe271798100ec7c` and workflow
[29576377936](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29576377936) form the
validated correction baseline immediately before the final safety pass. Python 3.10, 3.11, 3.12,
and the blocking Python 3.11 FreeSASA job passed. The final PR head
`b7491ab7cf82e473635bf3191abb960b0b7adcde` passed
[workflow 29584460029](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29584460029).
PR #4 was squash-merged as `294cf52912e0006d413316b89d7a55fed43f1429`; its
[post-merge workflow 29584633452](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29584633452)
passed the Python 3.10, 3.11, 3.12, and Python 3.11 FreeSASA jobs.

Stage 3A is complete and merged into main. Stage 3B was completed through
[#5](https://github.com/TrPavel/membrane-visual-qc/pull/5).

## Historical Stage 3B development — local chemical context

The accepted development artifact used identity `0.3.0.dev0`. Pure-Python chemistry and context modules implement
ADR-0004 without PyMOL or Qt imports. Existing severity is preserved while schema 1.2 adds
independent burial, contact-support, and prioritization states. Exposure remains usable alone;
context-disabled execution continues to produce schema 1.1.

Current corrected local validation: 299 tests passed, eight optional FreeSASA tests skipped on
Windows, and combined coverage is 85%. Ruff, 18 report validations, wheel/sdist, full retained
headless PyMOL, context fixtures, sequential lifecycle, and timing passed. The 49,414-byte Plugin
ZIP has SHA-256 `53a34dddcb1d3157f240d03ece3251c6c0565f5bb4bead70c807d641de9a65a1`.

The pre-graphical pass corrected FreeSASA orchestration, centralized five-state priority ordering,
kept CSV residue ordering stable, enforced binary command flags, removed duplicate state/support
constants, and fixed the contact contract at six conservative types. The blocking installed
FreeSASA orchestration tests are assigned to the Ubuntu reference job.

The first graphical Stage 3B attempt is partial. Initial summary, context objects/colours, review
precedence, and context-disabled fallback passed, but a sequential rerun failed on a stale
`mvqc_core_charged` selection. This historical result remains partial.

Focused graphical acceptance subsequently passed on Windows 10 build 26200 with Incentive PyMOL
3.1.8, bundled Python 3.10.20, and the exact corrected 49,414-byte ZIP with SHA-256
`53a34dddcb1d3157f240d03ece3251c6c0565f5bb4bead70c807d641de9a65a1`. The complete
`ON → OFF → ON → ON → invalid orientation` lifecycle, exports, cleanup, preservation,
responsiveness, and rotated 1UBQ `76/40/11/13/0` passed. Stage 3B graphical acceptance is complete.

Final PR head `0c08029b15baa2786681a0d73002d89f7d4e36db` passed
[workflow 29643963613](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29643963613).
PR #5 was squash-merged into `main` as `bc29918686206292c00a13cc74d6d20e60292653`.
The [post-merge workflow 29644011836](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29644011836)
passed Python 3.10, 3.11, 3.12, and the Python 3.11 FreeSASA job.

Stage 3B is complete and merged into main.

Stage 3 is complete and merged into main.

That development phase did not create a v0.3.0 tag, GitHub release, or PyPI publication. The
separate release-candidate branch now carries the active `0.3.0` identity.

## v0.3.0 release candidate

The active version, package metadata, current generated reports, CI artifact path, and local
artifacts now use `0.3.0`. Local validation passed with 299 tests, 85% coverage, 18 schema-valid
reports, the complete retained headless PyMOL suite, wheel/sdist inspection, and deterministic
double ZIP construction. The exact 49,415-byte `dist/MembraneVisualQC-0.3.0.zip` has SHA-256
`ae6bddcd95bd96be590077849879c64d57a07c0bffacf1779ff526ea22ddd7cb`.

The final graphical packaging/version smoke passed on 2026-07-18 with that exact ZIP. All twelve
focused checks passed, including schema-1.2/version-0.3.0 export, schema-1.1 fallback, repeated
lifecycle, invalid-orientation cleanup, input preservation, and rotated 1UBQ `76/40/11/13/0`.
The historical partial and accepted `0.3.0.dev0` artifacts remain unchanged. The final PR and
post-merge workflows passed Python 3.10, 3.11, 3.12, and the blocking Ubuntu FreeSASA job.

Final PR head `4fb65d69aa6ddc98cadd074b995bbf77b1fc503a` was squash-merged as
`5caf9ee0d89721ccfa560de9136b82cc87436c3b`; post-merge workflow
[29649853994](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29649853994) passed all four
jobs. Annotated tag object `e1b635f53a8c7765729d9a1d54fffb2238389fb7` targets that merge commit.
The [v0.3.0 prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.3.0) contains
four verified uploaded assets. Schema 1.2 is released and immutable. v0.1.0/v0.2.0 remain
unchanged, no PyPI project exists, and Stage 4 had not started at publication.

v0.3.0 is published as a prerelease for limited public testing.

## Stage 4A1 complete — offline PDBTM import core

Stage 4A1 was accepted at PR head `4c717b751a0711cf132fa6d9011c1454a8449939` and squash-merged
as `dbe2180386bc4c7230a08b2d064b0487347964c4`. The
[post-merge workflow](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29666872403)
passed Python 3.10, 3.11, 3.12, and the blocking Ubuntu FreeSASA Python 3.11 job.

Clean synchronized `main` validation passed 384 tests with eight optional FreeSASA skips and 87%
combined coverage. All 19 example reports validate: schema 1.1: 7, schema 1.2: 11, schema 1.3: 1.
Schema-1.3 reports undergo both JSON Schema structural validation and mandatory Stage 4 semantic
validation of nonlinear scientific invariants. The offline adapter contract accepts exactly one
`pdbtm_json` primary with either zero companions for partial provenance or exactly one
`transformed_pdb` companion for resolved import; unknown roles and duplicates are rejected.

The deterministic development artifact remains `MembraneVisualQC-0.4.0.dev0.zip`, 65,209 bytes,
with SHA-256 `059264627139ec1a2091fd0f7604d42e16297062f5d5349d270ef53edad0fc9e`.
Schemas 1.0, 1.1, and 1.2 remain byte-identical to their released forms. Schema 1.3 remains draft
and unreleased with SHA-256
`6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`. Official PDBTM/RCSB
provider payloads remain outside Git.

The development version remains `0.4.0.dev0`. No release or PyPI publication was created.

## Stage 4A2 complete — offline PyMOL and GUI integration

The implementation branch now exposes `mvqc_check_pdbtm` and `mvqc_slab_pdbtm`, plus the GUI
**PDBTM offline pair** mode. It resolves one complete single-state current PyMOL object against one
explicit matching local JSON/transformed-PDB pair, renders the resolved current-frame boundaries,
and passes exact Stage 4 evidence to schema-1.3 QC. It never retrieves, fits, transforms, or
renames the input object; failure cleanup removes stale plugin-owned state and `LAST_REPORT`.

The pre-graphical correction replaces mojibake-prone GUI literals with explicit Unicode escapes and
makes PDBTM Show Slab clear all stale plugin/report state on success and failure. Local validation
passed 418 tests with eight optional FreeSASA skips and 87% coverage. The retained
headless PyMOL suite, synthetic Stage 4A2 lifecycle, official local `1pcr`/`1a0s` identity and
inverse cases, 19 example reports, wheel/sdist build, ZIP validation, and deterministic double ZIP
build passed. The corrected candidate is `MembraneVisualQC-0.4.0.dev0.zip`, 69,251 bytes, SHA-256
`3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`. The earlier SHA-256
`446f7af119508dd8f66396dfbc39b4444517a5b2dac9d46368f34ee07cbacb92` is superseded.

Exact-artifact interactive graphical acceptance passed on Windows 10 build 26200 with Incentive
PyMOL 3.1.8 and bundled Python 3.10.20. The accepted 69,251-byte ZIP has SHA-256
`3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`. Identity and analytical
inverse imports for official local-only `1pcr` and `1a0s` payload pairs passed, including context
OFF/ON, schema-1.3 export, current-frame slab rendering, failure cleanup, repeated lifecycle, input
preservation, and both legacy regressions. Detailed observations are recorded in
`stage4a2_graphical_acceptance.md`.

PR #10 final head `2b3e03eef68f583ecc50c20b882f65a8394113c8` passed
[workflow 29696327755](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29696327755)
and was squash-merged into `main` as `fd31ac89c8131060d8872ad50a77895253f93dcc`. The
[post-merge workflow 29696377197](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29696377197)
passed Python 3.10, 3.11, 3.12, and the blocking Ubuntu FreeSASA Python 3.11 job.

The retained suite passed 418 tests with eight optional FreeSASA skips and 87% combined coverage.
All 19 example reports validate: schema 1.1: 7, schema 1.2: 11, and schema 1.3: 1. Report schema
SHA-256 values are:

- schema 1.0: `5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710`;
- schema 1.1: `86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf`;
- schema 1.2: `96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`;
- draft schema 1.3: `6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`.

Clean synchronized `main` rebuilt `MembraneVisualQC-0.4.0.dev0.zip` twice, byte-identically, at
69,251 bytes with SHA-256
`3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`.

Exact-artifact graphical acceptance used Windows 10 build 26200, Incentive PyMOL 3.1.8, and bundled
Python 3.10.20. Identity and analytical-inverse cases passed for `1pcr` and `1a0s`; 1pcr context
OFF/ON, schema-1.3 export, repeated lifecycle, failure cleanup, `mvqc_clear`, global-z, and planar
orientation-file regressions passed. The coordinate-frame mismatch check used a manually translated
object (+4 Å, −3 Å, +2 Å), which was rejected without altering its translated coordinates. Slab
planes were visible but relatively low contrast on a dark background; this is a non-blocking
pre-v1.0 UI backlog item.

Stage 4A2 PyMOL and GUI integration is complete and merged into `main`. Official provider payloads
remain outside Git. No network retrieval, OPM integration, source comparison, fitting, automatic
alignment, or Stage 4B work was added.

## v0.4.0 prerelease preparation

The `release/v0.4.0` candidate promotes the active identity to `0.4.0` and freezes schema 1.3 as
the immutable v0.4.0 release contract alongside schemas 1.0–1.2. Schema-1.3 reports continue to
require structural JSON Schema validation followed by the mandatory Stage 4 semantic validator.
v0.3.0 remains the latest published release until this candidate completes automated review,
exact-artifact graphical smoke, merge, tag, and publication gates.

No v0.4.0 tag, GitHub Release, or PyPI publication has been created. The next gate after automated
review is a short graphical smoke using the exact `MembraneVisualQC-0.4.0.zip`; Stage 4B has not
started.

Local release-candidate validation passed Ruff check and format check, 421 tests with eight
optional FreeSASA skips, 87% combined coverage, and all 19 example reports (schema 1.1: 7, 1.2:
11, 1.3: 1). Schema hashes remain 1.0
`5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710`, 1.1
`86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf`, 1.2
`96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`, and 1.3
`6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`.

The deterministic Plugin ZIP is `MembraneVisualQC-0.4.0.zip`, 69,241 bytes, SHA-256
`bba1891a8fa84c0575442d17daccbb6a6ad3bc54e60ad626ac1000cc59a079b5`. Its checksum sidecar,
wheel, and sdist pass the release-artifact validator; wheel/sdist metadata report version `0.4.0`
and the sdist contains the runtime, schemas, synthetic fixtures, and validation scripts without
report exports.
Standard setuptools archive timestamps mean wheel/sdist byte hashes are candidate-build records,
not reproducibility guarantees. Official provider payloads remain outside Git.

The authoritative publication set is the extracted `membrane-vqc-build` artifact from
[workflow 29702735453](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29702735453),
artifact ID `8446942786`, archive digest
`59884e5a6edc0f83ea3ca5ecb3e1ca0d8c092fc2fc9dc25f63c1798192bbb2fb`. Its wheel is 73,261
bytes with SHA-256 `07a78e72d03a84c87f54dd1db64b65f2505b6663c75d0d912d0c38332d9e2ef1`; its sdist is
128,532 bytes with SHA-256 `7cd22d8597e489876c6ac71202ef39499acbc7784b13df90771d803e2ed986f4`.
The four extracted files are retained outside Git for later publication and must not be replaced by
subsequent local validation builds.

Inspection confirmed version `0.4.0` in the Plugin Manifest, wheel metadata, and sdist metadata;
wheel tag `py3-none-any`; schemas 1.0–1.3 in the sdist; and no `.local`, reports directory,
Stage 4A2 manual export, official provider payload, or unsafe path. Wheel/sdist byte reproducibility
is not claimed.

The active schema-1.3 example was regenerated by the release code from parent commit
`2f0247474c1b1a8da59c7307fa12fba8c009ca97` at `2026-07-19T20:48:41.424766+00:00`.
It retains the accepted synthetic scientific semantics, records current payload digests, and passes
both structural and Stage 4 semantic validation.
