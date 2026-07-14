# Changelog

All notable changes to `membrane-vqc-pymol` will be documented in this file.

The format follows Keep a Changelog style, and this project intends to use semantic versioning once releases begin.

## [Unreleased]

### Added

- Added an immutable arbitrary planar-membrane model, signed-distance classification, asymmetric
  depth metrics, and rigid-transform invariance tests.
- Added strict orientation JSON import, orientation schema 1.0, additive report schema 1.1, and
  arbitrary-plane PyMOL rendering with a minimal GUI file mode.

### Changed

- Routed the unchanged `mvqc_check zmin/zmax` workflow through the general planar engine while
  preserving all five fixture summaries.
- Identified unreleased Stage 2 builds and generated reports as `0.2.0.dev0`, with a distinct
  development Plugin ZIP name.

### Fixed

- Corrected the UTF-8 ellipsis in the planar GUI progress messages and added regression coverage
  against mojibake.
- Made orientation commands the sole owner of file parsing and failure cleanup so stale planar
  source labels, review state, reports, and slab boundaries cannot survive invalid-file actions.
- Added a shared, reproducible rotated-1UBQ preparation helper for headless and graphical PyMOL.

### Documentation

- Synchronized public release status and GitHub Releases installation instructions after v0.1.0
  publication.

## [0.1.0] - 2026-07-14

### Changed

- Added report schema v1 with orientation/runtime provenance, conservative review statuses,
  deterministic ordering, input hashing, validation, and atomic export.
- Hardened the Qt wrapper with testable parsing, validators, readable errors, and busy state.
- Made review colours take precedence over hydropathy and ligand context.
- Synchronized user documentation with verified PyMOL 3.1.8 headless behaviour.
- Split GUI validation by action and made export-before-analysis a clear error.
- Moved ZIP integrity metadata inside the sole top-level plugin package directory.
- Added explicit provenance availability statuses and PyMOL runtime version capture.
- Completed graphical Plugin Manager installation and interactive GUI validation on Incentive
  PyMOL 3.1.8 for Windows.

### Added

- Initial documentation and project skeleton for the Membrane Visual QC PyMOL plugin.
- MIT license text for a clean-room implementation.
- Conda environment and minimal Python project metadata.
- Demo scripts for the command-first MVP workflow.
- Synthetic `bad_core_lys.pdb` validation case with a charged residue near `z=0`.
- Tutorial, validation matrix, and known limitations documentation.
- Pure-Python residue classification, hydropathy, neighbour, and report modules.
- PyMOL command registration for `mvqc_check`, `mvqc_slab`, `mvqc_color_hydropathy`, `mvqc_ligand_shell`, and `mvqc_export`.
- Minimal Qt GUI module as a thin command wrapper.
- Unit tests and PyMOL smoke/headless validation scripts.
- JSON/CSV reports and PNG screenshots for 1UBQ, 1C3W, 2RH1, 1PCR, and synthetic bad-core Lys validation cases.
- `mvqc_clear` for exact plugin-owned object/selection cleanup.
- Deterministic Plugin Manager ZIP builder with manifest, hashes, validation, and CI coverage.
- Versioned report JSON Schema, report-contract documentation, research log, ADRs, environment
  report, and manual GUI validation checklist.
- Package-based `load_mvqc.py` source loader and Linux portability coverage.

### Fixed

- PyMOL smoke script import paths for headless execution from the project directory.
- Slab CGO rendering in Schrodinger PyMOL 3.1.8 by using triangle primitives.
- Stale plugin visuals/report state after failed analysis.
- Raw GUI validation exceptions and unsafe empty-ligand handling.
