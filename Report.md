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

## Unreleased Stage 2 validation

Stage 2 is isolated on `feat/planar-orientation-depth`; `v0.1.0` remains immutable. Orientation
JSON uses schema 1.0 and new reports use additive schema 1.1. The legacy command is unchanged.

```powershell
ruff check .
# All checks passed!
ruff format --check .
# 42 files already formatted
pytest --cov=membrane_vqc --cov=scripts --cov-report=term-missing
# 153 passed; 80% combined coverage
python scripts\validate_example_reports.py
# Validated 6 report(s) (schema 1.1: 6)
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

The final pre-correction Stage 2 head `29ab66a4e8bf35b6f73b70049f7595b3f3700139` passed draft-PR
[Actions run 29350123791](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29350123791)
on Python 3.10, 3.11, and 3.12. Earlier Stage 2 implementation run
[29349967133](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29349967133) is retained
as historical evidence. Remaining acceptance work is interactive validation of the new GUI file
mode. The PR must remain draft and must not be merged automatically.
