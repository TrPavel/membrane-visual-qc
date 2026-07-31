# Development Report

## Current status

Stage 4A, Stage 4B1–4B4, and Stage 4C are complete. The repository is preparing v0.5.0 as a GitHub
prerelease for limited public testing. The release includes offline PDBTM pairs, bounded direct
PDBTM retrieval, a validated local cache, schema 1.4 acquisition provenance, offline-only OPM
input, and explicit schema 1.5 PDBTM–OPM geometric comparison. It performs no automatic fitting,
coordinate mutation, source selection, provider ranking, consensus, or biological verdict.

Final v0.5.0 test totals, artifact identities, release PR/commit/tag data, publication URL, and
downloaded-asset verification are **PENDING** exact-artifact acceptance and publication. Historical
v0.1.0–v0.4.0 and `0.5.0.dev0` evidence below remains intentionally unchanged. PyPI is not used.

## Environment

- Windows: Python 3.12 workspace venv for tooling.
- PyMOL: Incentive PyMOL 3.1.8 with bundled Python 3.10.20.
- Linux portability: Docker `python:3.12-slim`, Python 3.12.13, read-only checkout.
- Tools: pytest 9.1.1, Ruff 0.15.21, build 1.5.1, jsonschema 4.26.0.

## Scope completed

- Replaced the Windows-only path assertion with a `Path` comparison.
- Split GUI validation by action and made export-before-analysis a clear error.
- Added package-based source loading through `load_mvqc.py`.
- Populated `runtime.pymol` from `cmd.get_version()`.
- Added explicit availability statuses for input hash, PyMOL version, and Git commit.
- Exposed optional `input_path` end-to-end; hashing occurs only for an explicit real file.
- Strengthened report review-item validation and JSON Schema requirements.
- Replaced the placeholder schema ID with `urn:membrane-vqc:schema:report:1.0`.
- Added executable validation of five generated reports against JSON Schema.
- Changed Plugin ZIP to a single top-level `membrane_vqc/` directory; integrity metadata is
  inside the package and the archive digest remains beside the ZIP.
- Added Ruff format checking and report-schema validation to the CI workflow.
- Built wheel, sdist, and deterministic Plugin ZIP artefacts.

## Exact commands and results

```powershell
ruff check .
# All checks passed!

ruff format --check .
# 32 files already formatted

pytest
# 56 passed in 1.10s

python -m build
# Successfully built membrane_vqc_pymol-0.1.0.tar.gz
# and membrane_vqc_pymol-0.1.0-py3-none-any.whl

python scripts\build_plugin_zip.py
# built dist/MembraneVisualQC-0.1.0.zip

python scripts\build_plugin_zip.py --validate dist\MembraneVisualQC-0.1.0.zip
# valid

python scripts\validate_example_reports.py
# Validated 5 reports against schemas/mvqc-report-1.0.schema.json
```

Determinism check built `repro-a.zip` and `repro-b.zip`; their byte strings were identical
(17,691 bytes) and both had SHA-256
`2b42dfca836b20da4421394e7b71c9c02b100fc5d5948fee876ac2b50ac7f892`.

Linux portability command:

```bash
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 \
  -v "${PWD}:/workspace:ro" -w /workspace python:3.12-slim \
  sh -lc "pip install pytest jsonschema && python -m pytest \
  -p no:cacheprovider --basetemp=/tmp/mvqc-pytest -vv -s"
```

Result: 56 passed on Linux. In a preceding read-only-container command, `ruff check .` and
`ruff format --check .` also passed with cache directed to `/tmp`.

A writable temporary Linux copy executed the complete workflow commands: Ruff check and
format, pytest-cov (56 passed, 69% total coverage), JSON Schema validation, `python -m build`,
Plugin ZIP build, and ZIP validation. All passed.

## Public workflow and release

The final public [GitHub Actions run](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29289031923)
completed successfully for release commit `a8c7959fb1d53dd99771a184443aa16afd287aa6`.
All three matrix jobs passed: Python 3.10, 3.11, and 3.12.

The [v0.1.0 GitHub release](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.1.0)
is published as a prerelease for limited public testing. The final Plugin ZIP SHA-256 is
`2b42dfca836b20da4421394e7b71c9c02b100fc5d5948fee876ac2b50ac7f892`.

PyMOL checks:

```powershell
<PYMOL> -cq tests\pymol_smoke\smoke_import.py
<PYMOL> -cq load_mvqc.py
<PYMOL> -cq tests\pymol_smoke\validate_structures.py
```

All passed. Reports were regenerated for 1C3W, 2RH1, 1PCR, 1UBQ, and `bad_core_lys`.

## Artefacts

- `dist/MembraneVisualQC-0.1.0.zip`
- `dist/MembraneVisualQC-0.1.0.zip.sha256`
- `dist/membrane_vqc_pymol-0.1.0-py3-none-any.whl`
- `dist/membrane_vqc_pymol-0.1.0.tar.gz`
- `reports/release_validation.json`

## Provenance qualification

Generated PyMOL reports now record `runtime.pymol = 3.1.8`. Their input path/hash remain empty
with `input.provenance_status = input_path_not_supplied` because PyMOL selections do not reliably
retain source filenames. Supplying `mvqc_check input_path=data/model.cif` records the basename and
SHA-256. Reports generated before repository initialisation correctly record
`software.commit_status = unavailable`.

## Manual GUI validation

Passed in Incentive PyMOL 3.1.8 on Windows 10 build 26200. Plugin Manager installation, restart
menu registration, GUI opening, synthetic `bad_core_lys` analysis, empty-ligand handling,
action-specific validation, invalid-range handling, export, and `mvqc_clear` all passed. The
observed summary was `10 core residues; 1 charged core residue; 0 polar core residues; 0
ligand-neighbour residues`. No interactive-session screenshot was supplied; headless screenshots
remain under `docs/screenshots/` and are identified as such in the manual validation record.

## Released v0.1 limitations

- global-z manual orientation is the only path in the immutable v0.1 release;
- no data manifest, exposure/context engine, comparison, or CLI yet.

## Readiness statement

v0.1 is release-ready for limited public testing.

## Historical Stage 2 development validation

This section preserves validation evidence from the accepted `0.2.0.dev0` build; it is not
rewritten as final `0.2.0` output. `v0.1.0` remains immutable. Orientation JSON uses schema 1.0,
new reports use additive schema 1.1, and the legacy global-z command remains supported.

```powershell
ruff check .
# All checks passed!
ruff format --check .
# 42 files already formatted
pytest --cov=membrane_vqc --cov=scripts --cov-report=term-missing
# 153 passed; 80% combined coverage
python scripts\validate_example_reports.py
# Validated 7 report(s) (schema 1.1: 7), including manual acceptance evidence
python -m build
# Successfully built membrane_vqc_pymol-0.2.0.dev0-py3-none-any.whl
# and membrane_vqc_pymol-0.2.0.dev0.tar.gz
python scripts\build_plugin_zip.py
python scripts\build_plugin_zip.py --validate dist\MembraneVisualQC-0.2.0.dev0.zip
<PYMOL> -cq tests\pymol_smoke\smoke_import.py
<PYMOL> -cq tests\pymol_smoke\validate_structures.py
<PYMOL> -cq demo\prepare_rotated_1ubq.py
```

Legacy summaries remain exactly 1UBQ `76/40/11/13/0`, 1C3W `222/147/11/30/88`, 2RH1
`442/269/38/66/96`, 1PCR `823/176/43/33/241`, and `bad_core_lys` `10/10/1/0/0`.
Rotated 1UBQ with normal `[1,0,0]` has the same complete summary.

Stage 2 builds and generated reports identify themselves as `0.2.0.dev0`; the development ZIP is
`dist/MembraneVisualQC-0.2.0.dev0.zip`. All six generated schema-1.1 reports record
`software.version = 0.2.0.dev0`. The correction-build ZIP SHA-256 is
`841abe95cad44b99108cb4834ad593ef0bb4e99f64b8572cad87f088a5ac8307`. It does not replace the
published v0.1.0 asset.

The lifecycle correction makes orientation commands the sole file parser. Failed planar QC clears
all plugin-owned review visuals and `LAST_REPORT`; failed planar slab display clears both slab
objects. The GUI replaces stale source text with `unavailable`. The graphical/manual fixture can
be prepared reproducibly with `run C:/Pymol_script_1/demo/prepare_rotated_1ubq.py`; the helper and
headless validation share the same point transform.

### Stage 2 graphical acceptance

Complete graphical acceptance passed on 2026-07-15 using Windows 10 build 26200, Incentive PyMOL
3.1.8, bundled Python 3.10.20, and `MembraneVisualQC-0.2.0.dev0.zip` with SHA-256
`841abe95cad44b99108cb4834ad593ef0bb4e99f64b8572cad87f088a5ac8307`.

The graphical arbitrary-plane view, plane footprint and framing, orientation source, UTF-8 status
text, summary equivalence, review styling, schema-1.1 JSON/CSV export, orientation provenance,
residue-depth evidence, invalid zero-normal handling, and `mvqc_clear` all passed. Invalid Run QC
cleared stale report/review state; invalid Show Slab cleared stale slab objects; both changed the
source label to `unavailable` and produced no graphical traceback. `mvqc_clear` preserved
`1UBQ_rotated`.

The observed summary was `76/40/11/13/0`. Orientation source was
`synthetic_rigid_transform`, centre `[10.0,-5.0,3.0]`, normal `[1.0,0.0,0.0]`, and offsets
`[-15.0,15.0]`. Import provenance recorded `rotated_1ubq_orientation.json`, schema `1.0`, and
SHA-256 `75456606ebae906f9a131825a9a3edc05f74805fc03572979e1daec677ed7e2d`.

Manual evidence is retained as `reports/manual_stage2_check.json` and `.csv`. The JSON has 24
review items (11 `WARNING`, 13 `INSPECT`), each with all five depth/distance fields. It correctly
records `software.commit_status = unavailable` because execution came from an installed ZIP and
`input.provenance_status = input_path_not_supplied` because the GUI supplied no explicit source
path. Actual graphical screenshots are retained at:

- `docs/screenshots/manual_stage2_planar_qc.png`
- `docs/screenshots/manual_stage2_planar_edge_view.png`
- `docs/screenshots/manual_stage2_invalid_orientation.png`

Final PR head `272f288819965e72a53e4ea6fe3cb953131c3881` passed
[PR workflow 29410043646](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29410043646)
on Python 3.10, 3.11, and 3.12. PR #2 was squash-merged as
`faa7bae062c4ae43a9e9b738f6392bc2a228eb0e`; the
[post-merge main workflow 29410159752](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29410159752)
also passed all three matrix jobs. No v0.2.0 tag or release was created.

Stage 2 is complete and merged into main.

## v0.2.0 release-candidate validation

The release candidate promotes package metadata and current generated examples to `0.2.0` and
builds these exact artifact names:

- `dist/MembraneVisualQC-0.2.0.zip`
- `dist/MembraneVisualQC-0.2.0.zip.sha256`
- `dist/membrane_vqc_pymol-0.2.0-py3-none-any.whl`
- `dist/membrane_vqc_pymol-0.2.0.tar.gz`

Validation commands:

```powershell
ruff check .
ruff format --check .
pytest --cov=membrane_vqc --cov=scripts --cov-report=term-missing
python scripts\validate_example_reports.py
python -m build
python scripts\build_plugin_zip.py
python scripts\build_plugin_zip.py --validate dist\MembraneVisualQC-0.2.0.zip
<PYMOL> -cq tests\pymol_smoke\smoke_import.py
<PYMOL> -cq tests\pymol_smoke\validate_structures.py
<PYMOL> -cq C:\Pymol_script_1\demo\prepare_rotated_1ubq.py
```

Automated release-candidate validation passed on Windows: Ruff check and format check passed; 153
tests passed with 80% combined coverage; seven schema-1.1 reports validated (six regenerated
`0.2.0` examples plus one historical `0.2.0.dev0` manual report); PyMOL smoke import, all five
legacy structures, rotated 1UBQ, and the preparation helper passed. Wheel and sdist built with the
expected names.

Two independent Plugin ZIP builds were byte-for-byte identical. The final candidate is 27,459
bytes with SHA-256
`084a7e384364bc46b5b9b3ecdc1b705a4ac80d15e6c320d25f0e1c9f6ec16054`. The historical graphical
acceptance files above retain their `0.2.0.dev0` identity.

The short graphical smoke passed with this exact final artifact: Plugin Manager installation and
restart, both orientation modes, `prepare_rotated_1ubq.py`, arbitrary-plane Show Slab, QC summary
`76/40/11/13/0`, export schema 1.1 with `software.version = 0.2.0`, readable invalid-orientation
handling without traceback, and `mvqc_clear` preserving `1UBQ_rotated`. This was packaging/version
smoke evidence, not a repetition or replacement of the detailed `0.2.0.dev0` acceptance.

Release PR [#3](https://github.com/TrPavel/membrane-visual-qc/pull/3), head
`98c67039a9bbf09e3236e49d7da4b8a801541fef`, passed
[workflow 29487841498](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29487841498)
on Python 3.10, 3.11, and 3.12. It was squash-merged as release commit
`7877fed3c83419e6affa1e4353a65f8756e9303a`; the
[post-merge workflow 29488017586](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29488017586)
also passed all matrix jobs. Annotated tag `v0.2.0` points to that commit. The
[GitHub prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.2.0) contains all
four assets, which were downloaded again and verified byte-for-byte against the local artifacts.
No PyPI publication occurred, and v0.1.0 remains unchanged.

Ordinary RCSB coordinates are not automatically membrane-oriented. Imported orientation metadata
is not independently verified. Depth values are geometric evidence, not proof of biological
burial. Report schema 1.0 remains immutable; v0.2.0 produces report schema 1.1.

v0.2.0 is published as a prerelease for limited public testing.

## Historical Stage 3A development

Stage 3A is isolated on `feat/exposure-foundation` with development identity `0.3.0.dev0`. The
scientific contract is fixed in ADR-0003 before implementation: conventional SASA is solvent
accessibility, not lipid accessibility; RSA uses the Tien et al. 2013 theoretical scale; and
membrane-region accessible area is geometric review evidence only. ADR-0004 defines deferred Stage
3B semantics but no Stage 3B implementation has begun.

The development Plugin ZIP is `dist/MembraneVisualQC-0.3.0.dev0.zip`. Released tags, releases, and
report schemas 1.0/1.1 remain immutable. Schema 1.2 is an unreleased draft.

Stage 3A validation commands:

```powershell
ruff check .
ruff format --check .
pytest --cov=membrane_vqc --cov=scripts --cov-report=term-missing
python scripts\validate_example_reports.py
python -m build
python scripts\build_plugin_zip.py
python scripts\build_plugin_zip.py --validate dist\MembraneVisualQC-0.3.0.dev0.zip
```

The Stage 3A implementation adds a dependency-free deterministic Shrake–Rupley backend, a spatial
cell list, immutable configuration/result models, deterministic altloc collapse, per-model
isolation, the complete Tien et al. 2013 theoretical maximum-ASA table, and a lazy optional
FreeSASA adapter. No exposure runs unless explicitly requested. Schema 1.2 is draft and is emitted
only for opt-in exposure reports; context-disabled output remains schema 1.1.

Local Incentive PyMOL 3.1.8 validation retained all five legacy summaries and generated five
schema-1.2 reports. At 240 points, observed exposure times were: synthetic 0.018 s, 1UBQ 0.653 s,
1C3W 0.979 s, 2RH1 4.098 s, and 1PCR 2.854 s. FreeSASA was unavailable locally and produced an
explicit typed status without traceback; parity remains covered by the blocking reference CI job.

Final local Stage 3A result: Ruff check and format check passed; 246 tests passed, five FreeSASA
reference tests skipped because FreeSASA is unavailable in the Windows environment, and combined
coverage was 83%. A separate Ubuntu run with FreeSASA 2.2.1 passed all seven reference tests,
including the singleton native-call guard and mixed-model partial result.
The schema dispatcher validated 12
reports (seven schema 1.1 and five draft schema 1.2). PyMOL smoke import, all five legacy fixtures,
rotated 1UBQ, all five exposure timing cases, and the preparation helper passed. Wheel and sdist
built with `0.3.0.dev0` names. Two consecutive Plugin ZIP builds were byte-for-byte identical;
the 41,209-byte `MembraneVisualQC-0.3.0.dev0.zip` has SHA-256
`3c8fb30e9b3dd259c7759c2cbb736326856492cfbcfe6fd78ead101e40914722` and passed the ZIP
validator. The safety pass prevents native FreeSASA calls for models with fewer than two supported
atoms and makes `include_nonprotein_occluders` control full-selection extraction while retaining
protein-only targets and classification.
Missing HETATM element metadata now uses conservative inference: recognized unsupported
two-letter elements are excluded instead of being remapped to their first letter.

The previous implementation workflow
[29573971744](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29573971744) is retained as
historical evidence. Head `60872c70d570b5821f1b2cc1bfe271798100ec7c` and workflow
[29576377936](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29576377936) are the
validated correction baseline immediately preceding this final safety pass; that run passed Python
3.10/3.11/3.12 and the blocking Python 3.11 FreeSASA job.

### Stage 3A merge closure

Final PR head `b7491ab7cf82e473635bf3191abb960b0b7adcde` passed
[workflow 29584460029](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29584460029).
PR [#4](https://github.com/TrPavel/membrane-visual-qc/pull/4) was squash-merged into `main` as
`294cf52912e0006d413316b89d7a55fed43f1429`. The
[post-merge workflow 29584633452](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29584633452)
passed all four required jobs: Python 3.10, 3.11, 3.12, and the Python 3.11 FreeSASA reference job.
Stage 3A is complete and merged into main. No v0.3.0 release was created.

## Historical Stage 3B development — local chemical context

Stage 3B is implemented for review on `feat/local-chemical-context` in draft PR
[#5](https://github.com/TrPavel/membrane-visual-qc/pull/5), retaining development identity
`0.3.0.dev0`. It adds conservative putative salt bridges, distance-only potential hydrogen bonds,
nearby waters and ions, ligand proximity, independent context states, completed draft schema 1.2
evidence, compact opt-in GUI controls, and plugin-owned context visuals. It does not alter original
`WARNING`/`INSPECT` severity or claim energetic or biological conclusions.

The pre-graphical correction pass fixed the FreeSASA orchestration boundary: the built-in backend
alone receives the membrane model, while the reference backend uses its real membrane-independent
signature and records membrane surface partitions as unavailable. Auto selects FreeSASA only when
it is importable and otherwise selects the built-in backend. Tests now exercise the explicit GUI
label, Auto selection, unavailable evidence, installed reference execution, and a command-level
schema 1.2 run; the installed paths remain blocking in the Ubuntu FreeSASA job.

One shared context priority now orders JSON review items and the GUI/report summary:
`BURIED_NO_DETECTED_SUPPORT`, `BURIED_WITH_POTENTIAL_SUPPORT`, `INSUFFICIENT_CONTEXT`,
`ACCESSIBLE_NO_DETECTED_SUPPORT`, `ACCESSIBLE_WITH_POTENTIAL_SUPPORT`. WARNING precedes INSPECT
within a state, then stable residue identity; CSV retains stable residue order. The public command
flag accepts only boolean/0/1 values. Schema 1.2 and ADR-0004 contain exactly six supported contact
types: `putative_salt_bridge`, `distance_only_potential_hbond`, `nearby_water`, `nearby_ion`,
`ligand_proximity`, and `polar_ligand_proximity`. Unsupported ambiguous HETATM chemistry is
excluded with warnings and cannot create contact support. Overall `contact_support` spans those
six types; zero extracted water, ion, or ligand counts are availability observations, not
biological-absence claims.

Corrected local automated validation passed with 299 tests, eight optional FreeSASA tests skipped
on Windows, 85% coverage, Ruff, 18 schema-valid reports, wheel/sdist, and the full retained headless
PyMOL suite. The lifecycle-corrected 49,414-byte development ZIP has SHA-256
`53a34dddcb1d3157f240d03ece3251c6c0565f5bb4bead70c807d641de9a65a1`.

The first graphical attempt with SHA-256 `411752e953785452d58babd0840df425bc1f3f9f3f4d488d106b4489050fdddf`
was partial: initial context summary, objects, colours, review precedence, and context-disabled
fallback passed, but a later sequential run failed with `Invalid selection name
"mvqc_core_charged"` from the stale compound expression `mvqc_core_charged or
mvqc_core_polar_inspect`. Review styling now enumerates actual named selections, styles valid names
one at a time, and skips deleted names. Premature hydropathy and ligand-shell review styling was
removed; orchestration still recreates review selections after base and context rendering. A new
one-process headless regression passes ON → OFF → ON → ON → invalid orientation while preserving
the input object and clearing plugin state/`LAST_REPORT`.

The focused graphical retest then passed on Windows 10 build 26200, Incentive PyMOL 3.1.8, bundled
Python 3.10.20, using the exact corrected 49,414-byte ZIP with SHA-256
`53a34dddcb1d3157f240d03ece3251c6c0565f5bb4bead70c807d641de9a65a1`. Installation/restart,
`ON → OFF → ON → ON → invalid orientation`, selection recreation, absence of the invalid-review
error, invalid-file cleanup, schema 1.2 export with unchanged CSV columns, `mvqc_clear` structure
preservation, Standard/Built-in responsiveness, and rotated 1UBQ `76/40/11/13/0` all passed.
Stage 3B graphical acceptance is complete. The earlier blocked SHA remains recorded above as
partial historical evidence.

The headless synthetic PDB produced four `ACCESSIBLE_WITH_POTENTIAL_SUPPORT` review items. The
independent state fixtures cover one buried/no-support, one buried/with-support, one
accessible/no-support, one accessible/with-support, and two insufficient-context cases. The final
correction-run Standard-quality local-context times were 0.001 s synthetic, 0.116 s
1UBQ, 1.068 s 1C3W, 6.063 s 2RH1, and 10.362 s 1PCR. These are observations, not performance
promises. Every legacy structure summary remained unchanged.

Contacts are distance-only; histidine ionic interpretation is disabled; arbitrary ligand
chemistry, water bridges, protonation, coordination energetics, curved/multiple membranes,
network orientation, model comparison, and batch CLI remain out of scope.

Final PR head `0c08029b15baa2786681a0d73002d89f7d4e36db` passed
[workflow 29643963613](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29643963613).
PR #5 was squash-merged into `main` as `bc29918686206292c00a13cc74d6d20e60292653`; all four jobs
passed again in [post-merge workflow 29644011836](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29644011836).

Stage 3B is complete and merged into main.

Stage 3 is complete and merged into main.

That development phase used `0.3.0.dev0` and created no v0.3.0 tag, GitHub release, or PyPI
publication. The separate release-candidate branch now carries active identity `0.3.0`.

## v0.3.0 release candidate

The scientific meaning of schema 1.2 is frozen for release. Schemas 1.0 and 1.1 remain immutable;
v0.3.0 opt-in exposure/context reports use schema 1.2, while context-disabled reports continue to
use schema 1.1.

Local release-candidate validation passed Ruff check and format check, 299 tests with eight
optional FreeSASA skips on Windows, and 85% combined coverage. All 18 reports validated by declared
schema (seven schema 1.1 and eleven schema 1.2). Incentive PyMOL 3.1.8 passed smoke import, five
legacy structures, rotated 1UBQ `76/40/11/13/0`, Stage 3A exposure, Stage 3B context, the rotated
preparation helper, and `ON → OFF → ON → ON → invalid orientation` lifecycle regression.

Wheel and sdist metadata/layout inspection passed. The expected artifacts are
`MembraneVisualQC-0.3.0.zip`, `MembraneVisualQC-0.3.0.zip.sha256`,
`membrane_vqc_pymol-0.3.0-py3-none-any.whl`, and `membrane_vqc_pymol-0.3.0.tar.gz`. Two Plugin ZIP
builds were byte-for-byte identical. The exact 49,415-byte candidate has SHA-256
`ae6bddcd95bd96be590077849879c64d57a07c0bffacf1779ff526ea22ddd7cb`.

Schema SHA-256 values are: 1.0
`5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710`, 1.1
`86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf`, and 1.2
`96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`.

The exact-artifact graphical smoke passed on 2026-07-18 using the same 49,415-byte ZIP and SHA-256.
Installation/restart, context-disabled default, Standard/Built-in synthetic summary
`4 core / 2 charged / 2 polar / 1 ligand-neighbour`, four supported-context items and four context
selections, schema-1.2/version-0.3.0 export, schema-1.1 fallback and cleanup, repeated lifecycle,
invalid-orientation cleanup, input preservation, and rotated 1UBQ `76/40/11/13/0` all passed.
This is separate packaging/version evidence; the detailed `0.3.0.dev0` scientific acceptance and
both historical development SHAs remain unchanged.

FreeSASA is not installed on Windows, and neither WSL nor Docker is available; the blocking Ubuntu
Python 3.11 FreeSASA job and the Python 3.10/3.11/3.12 matrix remain required PR checks.

### v0.3.0 publication closure

Final PR head `4fb65d69aa6ddc98cadd074b995bbf77b1fc503a` passed
[workflow 29649788155](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29649788155).
PR #6 was squash-merged as `5caf9ee0d89721ccfa560de9136b82cc87436c3b`; all four jobs passed
again in [post-merge workflow 29649853994](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29649853994).

Annotated tag object `e1b635f53a8c7765729d9a1d54fffb2238389fb7` targets that exact merge
commit. The [v0.3.0 GitHub prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.3.0)
contains the Plugin ZIP, checksum, wheel, and sdist. All four published assets were downloaded
again and matched their local release artifacts byte-for-byte. The ZIP is 49,415 bytes with
SHA-256 `ae6bddcd95bd96be590077849879c64d57a07c0bffacf1779ff526ea22ddd7cb`; the checksum asset
contains the same digest, and wheel/sdist metadata report version `0.3.0`.

Schema 1.2 is released and immutable with SHA-256
`96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`. v0.1.0 and v0.2.0 tag
objects, targets, releases, and four-asset sets remain unchanged. The official PyPI JSON endpoint
returns 404 for `membrane-vqc-pymol`; no PyPI publication exists. Stage 4 has not started.

v0.3.0 is published as a prerelease for limited public testing.

## Stage 4A1 offline PDBTM core candidate

The development-only `0.4.0.dev0` implementation adds immutable source evidence, a strict
pure-Python PDBTM API-v1 offline adapter, coordinate-frame applicability without fitting, mapped
planar geometry, deterministic coordinate fingerprints, and draft schema 1.3. It does not expose
GUI/PyMOL import, network retrieval, OPM, source comparison, or automatic alignment.

The requested review correction now enforces reviewed +Z normal semantics, exact chain-map and
assembly provenance, non-spoofable offline retrieval status, explicitly lower-bound spatial
witnesses, three per-payload theoretical precision bounds, domain/report geometry identity, and
strict schema-1.3 definitions with negative validation fixtures.

The final contract correction separates JSON Schema structural validation from mandatory Stage 4
semantic validation of nonlinear scientific invariants. Every schema-1.3 report now checks finite
unit normals, the reviewed positive-Z and symmetric PDBTM source geometry, and agreement between
current evidence and resolved report geometry at tolerance `1e-9`. The adapter accepts only an
exact `pdbtm_json` primary and zero or one `transformed_pdb` companion; unknown roles and duplicate
companions are rejected before scientific parsing.

Final local validation passed Ruff check and format check, 384 tests with eight optional FreeSASA
skips, 87% coverage, and 19 example reports (schema 1.1: 7, 1.2: 11, 1.3: 1). Wheel/sdist build
as `0.4.0.dev0`. Two Plugin ZIP builds were identical; the validated
`MembraneVisualQC-0.4.0.dev0.zip` is 65,209 bytes with SHA-256
`059264627139ec1a2091fd0f7604d42e16297062f5d5349d270ef53edad0fc9e`.

Released schemas 1.0–1.2 remain byte-identical. Draft schema 1.3 has SHA-256
`6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`. Only synthetic provider
fixtures are present; official PDBTM payloads remain outside Git. Cross-version Python and
blocking FreeSASA results remain the required draft-PR checks.

## Stage 4A2 offline PyMOL/GUI candidate

Development version `0.4.0.dev0` now connects the accepted Stage 4A1 core to explicit local
PDBTM JSON/transformed-PDB selection, complete single-state current-object snapshots, current-frame
slab rendering, schema-1.3 QC reports, deterministic failure cleanup, and a third GUI orientation
mode. It does not retrieve provider data, fit or transform coordinates, infer structure identity,
or begin Stage 4B.

A real Incentive PyMOL 3.1.8 probe verified that `get_pdbstr` serializes the current object matrix.
Synthetic and ignored local official-payload headless tests cover identity and analytical inverse
mapping, context OFF/ON, repeated execution, wrong-pair and transformed-object rejection,
`LAST_REPORT` cleanup, and input preservation. The pre-graphical correction uses explicit Unicode
escapes for every non-ASCII GUI symbol and makes PDBTM Show Slab invalidate all stale plugin and
report state on success or failure. Official payloads remain outside Git. Local validation passed
Ruff check/format, 418 tests with eight optional FreeSASA skips, 87% coverage,
19 example reports, wheel/sdist build, all retained headless workflows, ZIP validation, and a
byte-identical double ZIP build. The corrected `MembraneVisualQC-0.4.0.dev0.zip` is 69,251 bytes
with SHA-256 `3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`.
The prior SHA-256 `446f7af119508dd8f66396dfbc39b4444517a5b2dac9d46368f34ee07cbacb92`
is superseded and is not eligible for final graphical acceptance.

Schemas 1.0–1.2 retain their released hashes; draft schema 1.3 remains
`6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`. Interactive graphical
acceptance of the exact candidate ZIP remains pending and is not inferred from headless results.

## v0.4.0 prerelease candidate

The release branch promotes the active package, Plugin Manifest, generated schema-1.3 report,
wheel, sdist, and Plugin ZIP identity to `0.4.0`. Schema 1.3 is now the immutable v0.4.0 structural
contract and retains mandatory nonlinear semantic validation. Schemas 1.0–1.3 remain byte-identical
to their accepted hashes.

Local validation passed Ruff check and format check, 421 tests with eight optional FreeSASA skips,
87% combined coverage, and all 19 example reports (schema 1.1: 7, 1.2: 11, 1.3: 1). Wheel and
sdist package metadata report `0.4.0`, and the source archive contains the required runtime,
schemas, synthetic fixtures, and validation scripts without report exports. The release-artifact validator
enforces version consistency, archive layout, schema hashes, synthetic-only provenance, and the
checksum sidecar in local and CI validation.

Two Plugin ZIP builds were byte-for-byte identical. The candidate
`MembraneVisualQC-0.4.0.zip` is 69,241 bytes with SHA-256
`bba1891a8fa84c0575442d17daccbb6a6ad3bc54e60ad626ac1000cc59a079b5`. The standard setuptools
wheel and sdist include archive timestamps, so their exact hashes are recorded for this build but
are not claimed to reproduce across independent invocations; their metadata and contents validate.
Official PDBTM/RCSB payloads remain outside Git.

The exact v0.4.0 Plugin ZIP graphical smoke remains a separate post-review gate. No tag, GitHub
Release, or PyPI publication exists, and Stage 4B has not started.

The publication set is frozen from GitHub Actions workflow `29702735453`, artifact ID
`8446942786`, archive digest
`59884e5a6edc0f83ea3ca5ecb3e1ca0d8c092fc2fc9dc25f63c1798192bbb2fb`. Its authoritative
wheel is 73,261 bytes with SHA-256
`07a78e72d03a84c87f54dd1db64b65f2505b6663c75d0d912d0c38332d9e2ef1`; its authoritative
sdist is 128,532 bytes with SHA-256
`7cd22d8597e489876c6ac71202ef39499acbc7784b13df90771d803e2ed986f4`. The four extracted files
are retained outside Git and must be used unchanged for later publication. Inspection confirms
version `0.4.0`, wheel tag `py3-none-any`, all four report schemas in the sdist, and no local,
report-export, manual Stage 4A2, official-provider, or unsafe-path entries. Wheel/sdist byte
reproducibility is not claimed.

The active schema-1.3 report was regenerated with the release code at
`2026-07-19T20:48:41.424766+00:00` and truthfully records parent commit
`2f0247474c1b1a8da59c7307fa12fba8c009ca97`. Its accepted synthetic scientific semantics remain
unchanged, while its payload digests now describe the exact current synthetic inputs. Structural
and mandatory Stage 4 semantic validation pass.

## v0.4.0 publication closure

PR #11 final head `3e4fa8c1fa95c51aae25c48afee3c884ccf3eb98` passed workflow `29704112287`
and was squash-merged as `8fcf499467a42bda6e7b18e90a180f72a410d1db`; post-merge workflow
`29704177651` passed Python 3.10, 3.11, 3.12, and blocking FreeSASA. Annotated tag object
`bd6f67d6981266b83fddb06715df3565eb65ae7e` targets that exact merge commit.

The [v0.4.0 GitHub prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.4.0)
contains the four authoritative Plugin ZIP, checksum sidecar, wheel, and sdist assets. All four
were downloaded after publication and matched the frozen corrected-workflow files byte-for-byte.
The ZIP is 69,241 bytes with SHA-256
`bba1891a8fa84c0575442d17daccbb6a6ad3bc54e60ad626ac1000cc59a079b5`; wheel and sdist hashes
are `449e091743e5811da70c5309c86274abc5a4144cd8a842fc61f1723552b1b658` and
`8853b893e08a33feb742c9679241116628955c995ded12898a9ea407c38f1c07`.

Exact-artifact graphical smoke passed on Windows 10 build 26200 with Incentive PyMOL 3.1.8 and
Python 3.10.20. The retained suite passed 421 tests with eight optional skips and 87% coverage;
19 reports validate (schema 1.1: 7, 1.2: 11, 1.3: 1). Schema 1.3 is released and immutable with
SHA-256 `6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`; schemas 1.0–1.2
remain unchanged. The official PyPI JSON endpoint returns 404; no PyPI publication was created.
Stage 4B has not started, and low slab contrast remains a non-blocking pre-v1.0 backlog item.
