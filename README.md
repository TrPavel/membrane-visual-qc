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

The v0.3.0 workflow supports the original global-z slab and an arbitrary planar membrane defined
by a local orientation JSON file. Opt-in analysis adds deterministic SASA/RSA, membrane-region
surface partitioning, and conservative local chemical-context evidence while preserving the
original review severities.

## Installation

v0.3.0 is being prepared as a prerelease for limited public testing. The exact local release
candidate is `dist/MembraneVisualQC-0.3.0.zip`; its final graphical packaging smoke passed. After
publication, GitHub Releases will be the primary public
installation route. Until then, public users should use the immutable
[v0.2.0 GitHub release](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.2.0).

Install the release ZIP through PyMOL Plugin Manager, restart PyMOL, and open
**Plugin > Membrane Visual QC**. Verify the archive with its accompanying `.zip.sha256` file. The
published [v0.1.0](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.1.0) and v0.2.0
tags, releases, and assets remain unchanged.

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

v0.1.0 reports use immutable schema 1.0; v0.2.0 reports use immutable schema 1.1. In v0.3.0,
opt-in exposure or context analysis uses schema 1.2, while context-disabled runs continue to emit
schema 1.1. Schema 1.2 is the v0.3.0 release schema and becomes immutable on publication. All are
documented in [docs/report_schema.md](docs/report_schema.md). Biological review
states are `NO_FLAGS`, `REVIEW_ITEMS`, `INSUFFICIENT_CONTEXT`, and `ANALYSIS_ERROR`.
`NO_FLAGS` means only that configured heuristics emitted no items.

`runtime.pymol` is read from the PyMOL command API. Input SHA-256 is recorded only when the
caller supplies an explicit real local `input_path`; PyMOL object selections do not reliably
retain source-file provenance. Reports created before Git initialisation may record commit
provenance as unavailable. Future reports produced from a Git checkout should record
`software.commit` when the runtime can resolve the checkout commit.

The legacy orientation remains supported and assumes the membrane normal is the global z-axis.
v0.2.0 maps that command to the general planar model as `manual_global_z`; it can also import a
local, versioned orientation JSON file. No external orientation adapter is included. Ordinary
RCSB coordinates are not automatically membrane-oriented, and imported orientation metadata is
not independently verified. Reported depth values are geometric evidence, not proof of biological
burial.

v0.3.0 builds local chemical-context review on the deterministic SASA/RSA foundation. Opt-in
analysis adds conservative distance-only contacts and independent burial/contact/context states
without changing `WARNING`/`INSPECT` severity. The GUI offers Fast/Standard/High sampling and
Built-in/Auto/FreeSASA-reference backends; context remains disabled by default. Graphical Stage 3
acceptance passed on Windows with Incentive PyMOL 3.1.8. FreeSASA is optional and lazy.

The schema 1.2 contact vocabulary is deliberately limited to `putative_salt_bridge`,
`distance_only_potential_hbond`, `nearby_water`, `nearby_ion`, `ligand_proximity`, and
`polar_ligand_proximity`. Unsupported or ambiguous HETATM elements are excluded with warnings;
arbitrary ligand chemistry is not inferred. Overall `contact_support` reports whether any of these
six evidence types was detected. Zero extracted water, ion, or ligand atoms do not prove that the
category is biologically absent.

## Validation and development status

The pure-Python suite and headless workflows have been tested with Incentive PyMOL 3.1.8 /
Python 3.10.20 on `1C3W`, `2RH1`, `1PCR`, `1UBQ`, and the synthetic fixture. See
[Report.md](Report.md), [docs/validation.md](docs/validation.md), and
[docs/development_state.md](docs/development_state.md).

Graphical Plugin Manager installation and GUI validation passed on Windows with Incentive PyMOL
3.1.8. The evidence and checklist are recorded in
[docs/manual_gui_validation.md](docs/manual_gui_validation.md).

## Current limitations

No automatic OPM/PPM/PDBTM/TmDet adapter, definitive chemical-interaction inference, lipid-facing
surface classification, comparison workflow, batch CLI, or curved/multiple-membrane model is
included in v0.3.0. See [docs/known_limitations.md](docs/known_limitations.md).

## Licence and citation

MIT. No formal citation is available yet; cite `membrane-vqc-pymol v0.3.0` and the exact
version used. The implementation is clean-room and does not copy GPL PyMOL plugin code.
