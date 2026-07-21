# Changelog

All notable changes to `membrane-vqc-pymol` will be documented in this file.

The format follows Keep a Changelog style, and this project intends to use semantic versioning once releases begin.

## [Unreleased]

### Changed

- Reopened source development as `0.5.0.dev0` after publishing v0.4.0. This lifecycle reset does
  not change released reports or schemas.

### Added

- Added the Stage 4B1 pure-Python direct-HTTPS PDBTM transport, deterministic provider-pair
  validation, canonical content-addressed cache, atomic generation-aware publication, explicit
  clear, and cancellation/delivery state machine.
- Added adversarial transport/cache tests, an ordinary-test non-loopback network guard, a blocking
  Windows Python 3.10 core job, and artifact gates that exclude official provider and cache data.
- Added report schema 1.4 (draft) and `membrane_vqc.pdbtm_report_provenance`: a pure, I/O-free
  conversion from an already-validated Stage 4B1 cache read result to a typed, immutable
  `orientation.acquisition` provenance block (provider identity, pair/snapshot IDs, per-payload
  acquisition evidence, and pair self-consistency), plus a `build_report(pdbtm_acquisition=...)`
  parameter that selects schema 1.4 explicitly. Schemas 1.0-1.3 and existing report-generation
  call sites are unaffected; schema 1.4 is never selected implicitly.

- Added Stage 4B3: a cached-PDBTM GUI workflow inside the existing **PDBTM offline pair** mode.
  `membrane_vqc/pdbtm_worker.py` is a Qt-free orchestration layer over the Stage 4B1
  transport/cache stack (`PdbtmWorkerOrchestrator.inspect/fetch/use_cached_pair/clear`);
  `membrane_vqc/pdbtm_gui_worker.py` is a thin lazily-imported `QObject`/`QThread` glue layer that
  runs it off the main thread via queued trigger signals. The GUI adds a `Local files` /
  `Validated cache` source selector, a canonical record-ID field, `Fetch / Refresh`, `Cancel`,
  visible cache status/metadata, `Use cached pair`, `Open cache location`, and `Clear cached
  record`. Only `Fetch / Refresh` ever authorizes network access; every other action (including
  automatic cache-status inspection on ID/source changes) is network-free. A per-dialog session
  ID, generation counter, and per-request ID guard stale worker deliveries -- a superseded fetch,
  use, or clear result is silently ignored and never selects a snapshot, runs QC, renders a slab,
  or changes `qc.LAST_REPORT`.
- Added `membrane_vqc.pdbtm_pymol.resolve_pdbtm_from_payloads()`, an in-memory-bytes sibling of
  `resolve_pdbtm_from_pymol()`, and `commands.mvqc_check_pdbtm_cached()` /
  `mvqc_slab_pdbtm_cached()` (internal helpers, not new PyMOL commands), which establish
  current-object applicability against the exact validated cached snapshot returned by
  `Use cached pair` and build a schema-1.4 report containing both `orientation.evidence`
  (current-object applicability) and `orientation.acquisition` (cache provenance). Local PDBTM
  file workflows are unchanged and continue to emit schema 1.3.

### Security

- Restricted Stage 4B1 to the reviewed PDBTM host and routes with ordinary TLS verification,
  bounded streaming, zero redirects/retries, no proxy discovery, redacted stable errors, and
  symlink/junction/reparse-aware cache access.
- Schema 1.4's acquisition provenance is closed and strict (no additional properties, bounded/
  allow-listed strings, exact enums) and always states that PDBTM cache acquisition does not by
  itself establish that any loaded structure matches the cached pair.
- Stage 4B3's worker never imports PyMOL or Qt, never calls a `cmd` method, and never tests
  applicability against a live object; the GUI never displays an absolute cache path, raw
  exception text, or other local/network diagnostic detail, and `Clear cached record` requires
  explicit confirmation.

## [0.4.0] - 2026-07-19

### Added

- Added offline PDBTM API-v1 import from an explicit JSON record and matching transformed-PDB
  companion, with direct identity or analytical-inverse coordinate applicability and no fitting.
- Added `mvqc_check_pdbtm`, `mvqc_slab_pdbtm`, current-frame membrane rendering, Context OFF/ON,
  and the third GUI orientation mode, **PDBTM offline pair**.
- Added report schema 1.3 provenance for exact payload digests, provider/adapter versions, source
  and current geometry, coordinate fingerprints, precision profiles, matrices, thresholds, and
  direct-match evidence while preserving existing CSV columns.
- Added strict payload-role/count/size, chain, assembly, normal, precision, coordinate-frame,
  occupancy, duplicate-ATOM, and spatial-witness validation.
- Added mandatory schema-1.3 semantic validation for nonlinear scientific invariants after JSON
  Schema structural validation.
- Added synthetic CI fixtures, real PyMOL snapshot probes, and ignored local-only official-payload
  acceptance for `1pcr` and `1a0s`; official provider payloads remain outside Git.

### Changed

- Promoted the active release-candidate identity to `0.4.0` and froze schema 1.3 as the v0.4.0
  release contract; schemas 1.0–1.3 are immutable release schemas.
- Made schema 1.3 normative for resolved PDBTM evidence and fixed offline retrieval provenance at
  unverified; source geometry does not claim an MVQC interface width.
- Restricted offline PDBTM input to one primary `pdbtm_json` payload and zero or one
  `transformed_pdb` companion; unknown roles and duplicate companions are rejected.
- Kept the input PyMOL object unchanged: applicability uses the complete containing single-state
  object even when analysis targets a selection inside it.
- Kept network retrieval, OPM, cross-source comparison, and automatic fitting/alignment outside
  v0.4.0.

### Fixed

- Replaced corrupted PDBTM GUI literals with explicit Unicode escapes so ellipses, middle dots,
  and angstrom symbols render correctly across source-loading environments.
- Made PDBTM Show Slab invalidate every prior plugin visual and `LAST_REPORT` on both success and
  failure; a slab-only orientation can no longer leave stale review/context evidence exportable.

### Documentation

- Added the offline PDBTM workflow, exact-artifact graphical acceptance record, schema 1.3
  structural/semantic contract, limitations, validation evidence, and v0.4.0 release notes.
- Recorded relatively low slab contrast on dark backgrounds as a non-blocking pre-v1.0 UI backlog
  item without changing runtime rendering.

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
