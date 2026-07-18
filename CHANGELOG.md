# Changelog

All notable changes to `membrane-vqc-pymol` will be documented in this file.

The format follows Keep a Changelog style, and this project intends to use semantic versioning once releases begin.

## [Unreleased]

### Added

- Added the Stage 4A1 pure-Python offline PDBTM domain model and API-v1 adapter with strict payload
  limits, direct coordinate applicability, analytical inverse mapping, precision-derived bounds,
  deterministic fingerprints, and no fitting or network dependency.
- Added draft report schema 1.3 for resolved external-orientation provenance while preserving
  schemas 1.0/1.1/1.2 and existing CSV columns.

### Changed

- Promoted the active development identity to `0.4.0.dev0`; v0.3.0 remains the latest published
  prerelease. GUI/PyMOL integration, retrieval, OPM, comparison, and Stage 4A2 remain unstarted.

## [0.3.0] - 2026-07-18

### Added

- Added Stage 3B local chemical-context review with conservative contacts, independent context
  states, schema-1.2 evidence, and plugin-owned PyMOL context visuals.
- Added compact opt-in GUI controls for Fast/Standard/High exposure sampling and Built-in/Auto/
  FreeSASA-reference backends; context remains disabled by default.
- Added deterministic pure-Python and headless PyMOL chemical-context fixtures and lifecycle,
  schema, invariance, cutoff, and deterministic-export coverage.
- Added the separately reviewed Stage 3A exposure foundation with explicit scientific semantics
  for SASA, RSA, membrane-region accessible area, atom/model preprocessing, and optional FreeSASA
  parity.
- Added a deterministic dependency-free Shrake–Rupley backend with a spatial cell list, immutable
  configuration/results, per-model isolation, stable altloc handling, side-chain SASA, and
  membrane-region surface partitions.
- Added the complete Tien et al. 2013 theoretical maximum-ASA scale and report schema 1.2
  for opt-in exposure evidence.
- Added a lazy optional FreeSASA reference adapter and a separate blocking Python 3.11 CI parity
  job on its supported platform; core Python 3.10/3.11/3.12 jobs remain FreeSASA-independent.

### Changed

- Made review styling lifecycle-safe across repeated graphical runs by enumerating real named
  selections, styling each review selection independently, and removing premature hydropathy and
  ligand-shell restyling assumptions.
- Made FreeSASA orchestration use its real membrane-independent signature, centralized context
  priority ordering, tightened the binary context command flag, and limited schema 1.2 to its six
  explicitly supported conservative contact labels.
- Completed schema 1.2 with serialized context thresholds, category availability,
  per-review-item contacts/counts/states, and top-level context-state counts while retaining the
  existing CSV columns.
- Promoted the active release-candidate identity to `0.3.0`; released v0.2.0 remains immutable.
- Replaced the unused combined analysis extra with an explicit optional
  `exposure-reference = ["freesasa>=2.2,<3"]` extra. Core analysis remains dependency-free.
- Guarded the known native FreeSASA singleton-model crash with explicit unavailable/partial
  evidence, without substituting the built-in backend.
- Made `include_nonprotein_occluders` extract all atoms inside the user selection for occlusion
  while keeping membrane classification and exposure targets protein-only.
- Made missing HETATM element inference conservative so recognized unsupported two-letter elements
  are excluded with warnings instead of being remapped to a supported first-letter radius.

### Documentation

- Added ADR-0003 for exposure semantics and ADR-0004 as the deferred Stage 3B chemical-context
  contract, backed by the required primary-source review.

## [0.2.0] - 2026-07-15

### Added

- Added an immutable arbitrary planar-membrane model with signed-distance and membrane-depth
  metrics, including asymmetric membrane boundaries.
- Added strict orientation JSON import using orientation schema 1.0 and additive report schema
  1.1 while preserving immutable report schema 1.0.
- Added arbitrary-plane PyMOL rendering, a GUI orientation-file mode, and reproducible rotated
  1UBQ validation.

### Changed

- Routed the legacy `mvqc_check zmin/zmax` workflow through the general planar engine while
  preserving global-z compatibility and all five fixture summaries.
- Promoted the accepted Stage 2 implementation from `0.2.0.dev0` to `0.2.0` for limited public
  testing.

### Fixed

- Corrected the UTF-8 ellipsis in the planar GUI progress messages and added regression coverage
  against mojibake.
- Made orientation commands the sole owner of file parsing and failure cleanup so stale planar
  source labels, review state, reports, and slab boundaries cannot survive invalid-file actions.
- Added a shared, reproducible rotated-1UBQ preparation helper for headless and graphical PyMOL.

### Documentation

- Synchronized public release status and GitHub Releases installation instructions after v0.1.0
  publication.
- Recorded complete graphical Stage 2 acceptance on Incentive PyMOL 3.1.8, including lifecycle,
  arbitrary-plane rendering, export provenance, residue-depth evidence, and manual fixtures.

### Known limitations

- No automatic OPM/PPM/PDBTM/TmDet adapter, exposure engine, FreeSASA integration,
  interaction-context engine, comparison workflow, batch CLI, or curved/multiple-membrane model
  is included.

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
