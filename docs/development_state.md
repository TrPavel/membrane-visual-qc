# Development state

Snapshot date: 2026-07-14 (Europe/Moscow). This file records the Stage 0 inventory and the v0.1
release-candidate closure state.

## Source-control state

- Git repository initialised with `main` as the default branch and published to GitHub.
- The immutable `v0.1.0` tag points to release commit
  `a8c7959fb1d53dd99771a184443aa16afd287aa6`.
- Git executable: `git version 2.53.0.windows.1`.
- The public release establishes the first auditable source snapshot and passed GitHub Actions.

## Repository tree

Generated caches and `__pycache__` entries are omitted.

```text
.
|-- CHANGELOG.md
|-- LICENSE
|-- README.md
|-- Report.md
|-- environment.yml
|-- pyproject.toml
|-- data/
|   |-- README.md
|   |-- raw/{1C3W,1PCR,1UBQ,2RH1}.cif
|   |-- processed/
|   `-- synthetic/bad_core_lys.pdb
|-- demo/{README.md,demo_scene.pml,quickstart.pml}
|-- docs/
|   |-- known_limitations.md
|   |-- tutorial.md
|   |-- validation.md
|   |-- screenshots/*.png
|   |-- research_log.md
|   |-- development_state.md
|   `-- adr/0001..0004
|-- membrane_vqc/
|   |-- __init__.py
|   |-- commands.py
|   |-- constants.py
|   |-- errors.py
|   |-- gui.py
|   |-- hydropathy.py
|   |-- membrane.py
|   |-- neighbors.py
|   |-- pymol_adapter.py
|   |-- qc.py
|   |-- report.py
|   `-- assets/README.md
|-- reports/
|   |-- *_mvqc.{json,csv}
|   |-- validation_summary.json
|   `-- release_validation.json
`-- tests/
    |-- test_*.py
    `-- pymol_smoke/*.py
```

## Package and runtime

- Package name/version: `membrane-vqc-pymol` `0.1.0` in both `pyproject.toml` and `membrane_vqc.constants.VERSION`.
- Declared project Python: `>=3.10`; Ruff target: `py310`.
- `environment.yml` requests Python 3.11 and `pymol-open-source=3.1.0`, which differs from the only verified installed runtime.
- `python`, `py`, `pymol`, and `conda` are not exposed on `PATH`.
- Verified bundled interpreter: `<HOME>/AppData/Local/Schrodinger/PyMOL2/python.exe`, Python 3.10.20 (conda-forge build, 64-bit).
- Verified PyMOL launcher: `<HOME>/AppData/Local/Schrodinger/PyMOL2/Scripts/pymol.exe`. Existing validation output and the current official installer identify the bundle as Incentive PyMOL 3.1.8; `smoke_import.py` executes successfully in it.
- Qt runtime: PyQt5 5.15.11 over Qt 5.15.15 via `pymol.Qt`.
- NumPy 1.26.4, pytest 9.0.3, Biopython 1.86.
- FreeSASA and SciPy are not installed. Ruff is not installed in the verified PyMOL interpreter.
- Exact local paths are retained only in the local environment report and are home-redacted there.

## Commands attempted and results

| Command | Result |
|---|---|
| `git status --short --branch` | Not a Git repository. |
| `python --version`, `py -0p`, `where python`, `where pymol`, `conda env list` | Commands/interpreters unavailable through `PATH`. |
| bundled `python.exe --version` | Python 3.10.20. |
| bundled `python.exe -m pytest tests -q -p no:cacheprovider` | First attempt: 8 passed and one setup error because pytest could not scan the default user temp directory. This is an environment permission error, not a test assertion failure. |
| bundled `python.exe -m pytest tests -q -p no:cacheprovider --basetemp C:\\tmp\\mvqc-pytest` | 17 passed at the time of that run. Additional tests appeared later from concurrent implementation streams and require the root integration run. |
| bundled `python.exe -m compileall -q membrane_vqc tests` | Passed (exit code 0). |
| bundled `python.exe -m ruff check membrane_vqc tests` | Not run: `No module named ruff`. |
| bundled `pymol.exe -cq tests\\pymol_smoke\\smoke_import.py` | Passed: `MVQC smoke import OK`. |

The fixed `--basetemp` path is required in this managed environment. The full structure-validation script was not rerun by this stream because it regenerates reports and screenshots outside this stream's file ownership.

## Existing generated baseline

`reports/validation_summary.json` records successful headless runs for five fixtures:

| Case | Total | Core | Charged review | Polar inspect | Ligand neighbours |
|---|---:|---:|---:|---:|---:|
| 1C3W | 222 | 147 | 11 | 30 | 88 |
| 2RH1 | 442 | 269 | 38 | 66 | 96 |
| 1PCR | 823 | 176 | 43 | 33 | 241 |
| 1UBQ | 76 | 40 | 11 | 13 | 0 |
| synthetic `bad_core_lys` | 10 | 10 | 1 | 0 | 0 |

The synthetic fixture satisfies the required regression invariant of exactly one charged-core
review item. The root integration run regenerated these reports with schema v1 and the
`REVIEW_ITEMS` status.

## Discrepancies and contradictions

- `docs/validation.md` says real PyMOL cases were not run and PyMOL was unavailable, but `Report.md`, screenshots, and `reports/validation_summary.json` record successful PyMOL 3.1.8 headless validation. Documentation is internally inconsistent.
- Existing generated reports use `overall_status: WARNING`; the roadmap explicitly forbids pass/fail-style biological conclusions and the current report code uses a revised status vocabulary.
- RCSB mmCIF fixtures exist, but no reproducible manifest with URL, timestamp, checksum, assembly decision, licence, and orientation provenance is present.
- The manual z-slab is still the only implemented scientific orientation path. Ordinary RCSB coordinates must not be represented as membrane-aligned.
- `environment.yml` targets Python 3.11/open-source PyMOL 3.1.0, while verified execution used bundled Python 3.10.20/Incentive PyMOL 3.1.8. Both environments should eventually be tested, not treated as equivalent without evidence.

## Stage 1 integration update

The correction integration run completed the versioned report, GUI/lifecycle, deterministic ZIP,
CI configuration, packaging, and documentation work. The current suite has 56 passing tests on
Windows and 56 passing tests in a read-only Linux Python 3.12 container. Ruff check/format,
wheel/sdist build, PyMOL smoke import, source loader, and five-structure headless validation pass.
Generated reports validate against schema v1. The Plugin ZIP was built twice byte-for-byte.

## Blockers and next concrete stage

Graphical Plugin Manager installation and interactive GUI validation passed on 2026-07-14 in
Incentive PyMOL 3.1.8 on Windows 10 build 26200. The synthetic summary, export, action-specific
validation, invalid-range handling, empty-ligand behaviour, and `mvqc_clear` all passed. No
interactive-session screenshot was supplied; existing screenshots are from headless validation.

Stage 1 is closed and Stage 2 has not started. Tag `v0.1.0` is published as a GitHub prerelease
for limited public testing from commit `a8c7959fb1d53dd99771a184443aa16afd287aa6`.
The final release validation workflow passed in
[GitHub Actions](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29289031923).
