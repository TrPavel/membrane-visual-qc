# Development Report

## Current status

The Stage 1 correction and portability pass is complete. Graphical Plugin Manager installation,
interactive GUI validation, and the public GitHub Actions workflow all passed.

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

## Unreleased Stage 3A

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

## Unreleased Stage 3B — local chemical context

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
types. Unsupported ambiguous HETATM chemistry is excluded with warnings and cannot create contact
support. Overall `contact_support` spans those six types; zero extracted water, ion, or ligand
counts are availability observations, not biological-absence claims.

Corrected local automated validation passed with 297 tests, eight optional FreeSASA tests skipped
on Windows, 85% coverage, Ruff, 18 schema-valid reports, wheel/sdist, and the full retained headless
PyMOL suite. The 49,328-byte development ZIP has SHA-256
`411752e953785452d58babd0840df425bc1f3f9f3f4d488d106b4489050fdddf`.

The headless synthetic PDB produced four `ACCESSIBLE_WITH_POTENTIAL_SUPPORT` review items. The
independent state fixtures cover one buried/no-support, one buried/with-support, one
accessible/no-support, one accessible/with-support, and two insufficient-context cases. The final
correction-run Standard-quality local-context times were 0.001 s synthetic, 0.116 s
1UBQ, 1.068 s 1C3W, 6.063 s 2RH1, and 10.362 s 1PCR. These are observations, not performance
promises. Every legacy structure summary remained unchanged.

Contacts are distance-only; histidine ionic interpretation is disabled; arbitrary ligand
chemistry, water bridges, protonation, coordination energetics, curved/multiple membranes,
network orientation, model comparison, and batch CLI remain out of scope. Graphical Stage 3B
acceptance and green PR CI are still required. PR #5 remains draft and unmerged; Stage 3 is not
complete and no v0.3.0 tag or release may be created.
