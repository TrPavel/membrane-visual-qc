# Membrane Visual QC MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working MVP PyMOL plugin for membrane-protein visual QC.

**Architecture:** Core pure-Python logic is isolated from PyMOL. PyMOL commands and Qt GUI are thin wrappers around the core modules and adapter helpers.

**Tech Stack:** Python 3.10+, PyMOL command API, PyMOL Qt, pytest.

---

### Task 1: Core Logic and Unit Tests

**Files:**
- Create: `membrane_vqc/constants.py`
- Create: `membrane_vqc/hydropathy.py`
- Create: `membrane_vqc/membrane.py`
- Create: `membrane_vqc/neighbors.py`
- Create: `membrane_vqc/report.py`
- Test: `tests/test_hydropathy.py`
- Test: `tests/test_membrane.py`
- Test: `tests/test_neighbors.py`
- Test: `tests/test_report.py`

- [ ] Write failing pytest tests for hydropathy, slab classification, neighbor cutoff, and report export.
- [ ] Run pytest and verify tests fail because modules do not exist yet.
- [ ] Implement minimal pure-Python modules to pass tests.
- [ ] Run pytest and verify pure-Python tests pass.

### Task 2: Project Skeleton and Data

**Files:**
- Create: `pyproject.toml`
- Create: `environment.yml`
- Create: `README.md`
- Create: `LICENSE`
- Create: `CHANGELOG.md`
- Create: `data/README.md`
- Create: `data/synthetic/bad_core_lys.pdb`
- Create: `demo/README.md`
- Create: `demo/quickstart.pml`
- Create: `demo/demo_scene.pml`
- Create: `docs/tutorial.md`
- Create: `docs/validation.md`
- Create: `docs/known_limitations.md`

- [ ] Create required folders and placeholder/docs files.
- [ ] Create synthetic bad-core Lys validation PDB.
- [ ] Add install, usage, validation philosophy, and limitations docs.

### Task 3: PyMOL Commands, GUI, and Smoke Tests

**Files:**
- Create: `membrane_vqc/__init__.py`
- Create: `membrane_vqc/pymol_adapter.py`
- Create: `membrane_vqc/qc.py`
- Create: `membrane_vqc/commands.py`
- Create: `membrane_vqc/gui.py`
- Test: `tests/pymol_smoke/smoke_import.py`
- Test: `tests/pymol_smoke/smoke_1ubq.py`
- Test: `tests/pymol_smoke/smoke_1c3w.py`

- [ ] Implement command registration for `mvqc_check`, `mvqc_slab`, `mvqc_color_hydropathy`, `mvqc_ligand_shell`, and `mvqc_export`.
- [ ] Implement simple PyMOL visual selections/objects through adapter helpers.
- [ ] Implement minimal Qt dialog calling command functions.
- [ ] Add PyMOL smoke scripts.

### Task 4: Validation and Final Report

**Files:**
- Create: `Report.md`
- Create/update: `reports/*.json`

- [ ] Attempt public structure downloads into `data/raw/`.
- [ ] Run `pytest`.
- [ ] Attempt PyMOL smoke tests if `pymol` is available.
- [ ] Generate any possible JSON/CSV reports.
- [ ] Write honest `Report.md` with created files, tests, limitations, deviations, and next steps.
