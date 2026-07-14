# Membrane Visual QC

An open-source PyMOL plugin for explainable, membrane-aware visual review of protein structures.

> Membrane Visual QC is a review assistant. It does not prove that a structure is correct,
> stable, membrane-inserted, or experimentally validated.

## What it does

- displays a manually defined membrane slab;
- classifies residues as core, interface, or outside;
- highlights charged and selected polar core residues for review;
- applies a coarse Kyte-Doolittle-like hydropathy palette;
- selects residues near a ligand/cofactor selection;
- exports versioned JSON and deterministic CSV reports;
- records manual-orientation warnings and conservative review statuses.

The released v0.1 workflow is command-first. Unreleased Stage 2 work adds an arbitrary planar
normal, geometric depth, orientation JSON import, and matching PyMOL rendering.

## Installation

v0.1.0 is a prerelease for limited public testing. Public users should download
`MembraneVisualQC-0.1.0.zip` and its checksum from the
[v0.1.0 GitHub release](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.1.0),
install the ZIP through PyMOL Plugin Manager, restart PyMOL, and open
**Plugin > Membrane Visual QC**. The archive contains only runtime package files and an integrity
manifest; verify it with the accompanying `.zip.sha256` file.

`dist/MembraneVisualQC-0.2.0.dev0.zip` is the distinct local build path for the unreleased Stage 2
development branch; it is not the primary public installation route and does not replace the
published v0.1.0 asset.

For source development:

```bash
conda env create -f environment.yml
conda activate mvqc
```

For source development, start PyMOL in the checkout root and run:

```pml
run load_mvqc.py
```

Do not execute `membrane_vqc/commands.py` directly: it is a package module and uses relative
imports. If the exact `pymol-open-source=3.1.0` pin is unavailable, use a compatible build and
record the tested version.

## 60-second quick start

```pml
load data/synthetic/bad_core_lys.pdb, bad_core_lys
mvqc_check selection=bad_core_lys, zmin=-15, zmax=15, ligand=, cutoff=5.0
mvqc_export path=reports/bad_core_lys_mvqc.json
```

The artificial structure must produce exactly one charged-core review item. This verifies
software behaviour, not biology.

## PyMOL commands

- `mvqc_check selection=all, zmin=-15, zmax=15, ligand=organic, cutoff=5.0`
- `mvqc_check_orientation selection=all, orientation_file=demo/rotated_1ubq_orientation.json`
- `mvqc_slab_orientation selection=all, orientation_file=demo/rotated_1ubq_orientation.json`
- `mvqc_slab zmin=-15, zmax=15`
- `mvqc_color_hydropathy selection=all`
- `mvqc_ligand_shell protein=all, ligand=organic, cutoff=5.0`
- `mvqc_export path=reports/mvqc_report.json`
- `mvqc_clear`

`mvqc_clear` removes only plugin-owned names beginning with `mvqc_`. A failed analysis
clears partial plugin output so stale visuals do not appear current.
Planar orientation commands own file parsing and cleanup: an invalid file clears stale QC state or
slab boundaries, and the GUI reports the orientation source as `unavailable`.

## Reports and interpretation

Released v0.1 reports use schema 1.0; unreleased Stage 2 reports use additive schema 1.1. Both are
documented in [docs/report_schema.md](docs/report_schema.md). Biological review
states are `NO_FLAGS`, `REVIEW_ITEMS`, `INSUFFICIENT_CONTEXT`, and `ANALYSIS_ERROR`.
`NO_FLAGS` means only that configured heuristics emitted no items.

`runtime.pymol` is read from the PyMOL command API. Input SHA-256 is recorded only when the
caller supplies an explicit real local `input_path`; PyMOL object selections do not reliably
retain source-file provenance. Reports created before Git initialisation may record commit
provenance as unavailable. Future reports produced from a Git checkout should record
`software.commit` when the runtime can resolve the checkout commit.

The v0.1 orientation is manual and assumes the membrane normal is the global z-axis. Stage 2 maps
that command to the general planar model as `manual_global_z`; it can also import a local,
versioned orientation JSON file. No external orientation adapter is included. Ordinary RCSB
coordinates are not assumed to be membrane-aligned.

## Validation and development status

The pure-Python suite and headless workflows have been tested with Incentive PyMOL 3.1.8 /
Python 3.10.20 on `1C3W`, `2RH1`, `1PCR`, `1UBQ`, and the synthetic fixture. See
[Report.md](Report.md), [docs/validation.md](docs/validation.md), and
[docs/development_state.md](docs/development_state.md).

Graphical Plugin Manager installation and GUI validation passed on Windows with Incentive PyMOL
3.1.8. The evidence and checklist are recorded in
[docs/manual_gui_validation.md](docs/manual_gui_validation.md).

## Current limitations

No automatic orientation, exposure calculation, chemical interaction validation, MD,
electrostatics, Rosetta energy analysis, model comparison, or HTML dashboard is included in
v0.1. See [docs/known_limitations.md](docs/known_limitations.md).

## Licence and citation

MIT. No formal citation is available yet; cite `membrane-vqc-pymol v0.1.0` and the exact
version used. The implementation is clean-room and does not copy GPL PyMOL plugin code.
