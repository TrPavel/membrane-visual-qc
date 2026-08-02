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

Version `0.4.0` adds the reviewed offline PDBTM API-v1 pair contract, direct coordinate-frame
applicability, PyMOL commands, the third GUI orientation mode, and released report schema 1.3.

Version `0.5.0` adds bounded direct PDBTM retrieval, a validated local cache
with explicit **Fetch / Refresh** versus **Use cached pair** actions, schema 1.4 acquisition
provenance, and an explicit PDBTM-versus-OPM geometric comparison area with schema 1.5. PDBTM may
come from a local pair or an explicitly selected validated cache snapshot; OPM remains an explicit
local oriented-PDB file and is never fetched. Both sources must independently match the same
immutable current object. The comparison performs no fitting, coordinate mutation, automatic
source choice, consensus, provider ranking, or biological verdict. See
[docs/stage4c_source_comparison.md](docs/stage4c_source_comparison.md).

Version `0.6.0` adds strict batch contracts and the **Batch review** GUI. The
GUI validates an explicit plan, displays its ordered queue, advances one PyMOL job per queued
main-thread event, supports cooperative cancellation, retains at most 20 current-session runs, and
verifies an explicitly selected result bundle before browsing it. It never scans for plans or
history, fetches PDBTM or OPM, edits a plan, or makes a biological verdict. See
[docs/stage5a_batch_review.md](docs/stage5a_batch_review.md) and
[docs/stage5b_gui_batch.md](docs/stage5b_gui_batch.md).

Version `0.7.0` is a compatibility and reliability release: it restores historical report schema
1.0 read compatibility, converts an unhandled result-browser exception into a typed, clean error,
makes Windows filesystem failures during batch execution fail fast with clear typed errors instead
of hanging, gives a missing batch plan a clean CLI error instead of a traceback, and adds a
real-PyMOL install/upgrade/rollback compatibility harness for the v0.6.0 -> `0.7.x` transition
(automated tests plus an owner-observed manual acceptance pass). It also consolidates previously
scattered documentation into [docs/index.md](docs/index.md). It changes no scientific algorithm,
report schema, batch contract, or cache format. See
[docs/v0.7.0_release_notes.md](docs/v0.7.0_release_notes.md).

Version `0.8.0` is a contract-freeze and documentation-consolidation release: it audits and freezes
every public/machine-readable interface (PyMOL commands, report schemas, batch contracts, cache
format, status/error vocabulary, output layout) ahead of v1.0, defines the versioning and
deprecation policy in [docs/versioning_policy.md](docs/versioning_policy.md), and replaces
scattered stage-oriented documentation with a five-section documentation system starting at
[docs/index.md](docs/index.md). It changes no scientific algorithm, GUI, batch execution,
cache-format, report-schema, or batch-contract behavior relative to v0.7.0. See
[docs/v0.8.0_release_notes.md](docs/v0.8.0_release_notes.md) and
[docs/v1.0_contract_freeze.md](docs/v1.0_contract_freeze.md).

## Installation

v0.8.0 is being prepared as a GitHub prerelease for limited public testing. Until its release URL
and assets are published and byte-verified, v0.7.0 remains the latest published package. Download
`MembraneVisualQC-0.7.0.zip` and its checksum from the
[v0.7.0 GitHub prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.7.0).
GitHub Releases is the public installation route. The v0.8.0 Plugin ZIP will be named
`MembraneVisualQC-0.8.0.zip`; its final size and SHA-256 are **PENDING**. Wheel and source
distributions are release assets for inspection and development; this project is not published to
PyPI.

Install the release ZIP through PyMOL Plugin Manager, fully restart PyMOL, and open
**Plugin > Membrane Visual QC**. Verify the archive with its accompanying `.zip.sha256` file. The
published [v0.1.0](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.1.0) and
[v0.2.0](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.2.0) tags, releases, and
assets remain unchanged.

Installing for the first time and upgrading an existing installation are different situations: a
first install can use Plugin Manager's normal "Install New Plugin" flow as above, but upgrading
from an existing v0.6.0 installation has its own recommended (clean-replacement) method, data-
compatibility notes, and a troubleshooting section -- see
[docs/upgrade_guide.md](docs/upgrade_guide.md). The currently validated configurations and
compatibility boundaries (OS, PyMOL distribution, supported schema/contract versions, what remains
manual-verification-only) are stated in [docs/compatibility.md](docs/compatibility.md). The v0.6.0
-> `0.7.0.dev0` clean install/upgrade/rollback path has an owner-observed manual PASS result in
[docs/manual_install_upgrade_checklist.md](docs/manual_install_upgrade_checklist.md); this does not
extend to other version pairs and does not replace automated CI.

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
- `mvqc_check_pdbtm selection=all, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb`
- `mvqc_slab_pdbtm selection=all, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb`
- `mvqc_slab zmin=-15, zmax=15`
- `mvqc_color_hydropathy selection=all`
- `mvqc_ligand_shell protein=all, ligand=organic, cutoff=5.0`
- `mvqc_export path=reports/mvqc_report.json`
- `mvqc_batch_run plan=data/synthetic/stage5a_batch_plan.json, output_dir=reports/batch, fail_fast=0, quiet=1`
- `mvqc_clear`

`mvqc_clear` removes only plugin-owned names beginning with `mvqc_`. A failed analysis
clears partial plugin output so stale visuals do not appear current.
Planar orientation commands own file parsing and cleanup: an invalid file clears stale QC state or
slab boundaries, and the GUI reports the orientation source as `unavailable`.

The offline PDBTM commands require an explicit matching local JSON/transformed-PDB pair and exactly
one single-state PyMOL molecular object. Applicability always checks the complete containing object,
although analysis may target a selection within it. Current coordinates must directly match either
the transformed companion or its analytical inverse reference. The plugin never retrieves data,
fits, rotates, translates, or otherwise transforms the input object, and it does not serialize local
paths into the report. See
[docs/pdbtm_offline_import.md](docs/pdbtm_offline_import.md).

## Reports and interpretation

v0.1.0 reports use immutable schema 1.0; v0.2.0 reports use immutable schema 1.1. In v0.3.0,
opt-in exposure or context analysis uses schema 1.2, while context-disabled runs continue to emit
schema 1.1. Schema 1.2 is the immutable v0.3.0 release schema. All are
documented in [docs/report_schema.md](docs/report_schema.md). For what every status literal
(`NO_FLAGS`, `REVIEW_ITEMS`, and everything else this project produces) actually means, see
[docs/status_vocabulary.md](docs/status_vocabulary.md) -- none of them are a biological verdict.

Resolved PDBTM reports use immutable schema 1.3 in v0.4.0, whether Context is OFF or ON. Schema
1.3 requires JSON Schema structural validation followed by a mandatory semantic
validator for nonlinear scientific invariants. Schemas 1.0–1.3 are immutable release contracts.
Cached-PDBTM reports use schema 1.4. The independent two-source comparison uses additive schema
1.5; schemas 1.0–1.3 remain immutable historical release contracts, and schemas 1.4–1.5 are
frozen for v0.5.0 publication.

`mvqc-batch-plan-1.0` and `mvqc-batch-result-1.0` are operational batch
contracts, not report schema 1.6. Validate a plan without PyMOL using
`python -m membrane_vqc.batch_cli validate PLAN.json`; execution still requires PyMOL and runs
sequentially on its main thread. A missing or invalid plan path prints a concise error to stderr
and exits non-zero rather than raising a traceback.

`runtime.pymol` is read from the PyMOL command API. Input SHA-256 is recorded only when the
caller supplies an explicit real local `input_path`; PyMOL object selections do not reliably
retain source-file provenance. Reports created before Git initialisation may record commit
provenance as unavailable. Future reports produced from a Git checkout should record
`software.commit` when the runtime can resolve the checkout commit.

The legacy orientation remains supported and assumes the membrane normal is the global z-axis.
v0.2.0 maps that command to the general planar model as `manual_global_z`; it can also import a
local, versioned orientation JSON file. Ordinary RCSB coordinates are not automatically
membrane-oriented. PDBTM applicability is direct geometric evidence, not proof that an orientation
is biologically correct; provider Side1/Side2 labels are not converted into inside/outside biology.
Reported depth values are geometric evidence, not proof of biological burial.

v0.3.0 builds local chemical-context review on the deterministic SASA/RSA foundation. Opt-in
analysis adds conservative distance-only contacts and independent burial/contact/context states
without changing `WARNING`/`INSPECT` severity. The GUI offers Fast/Standard/High sampling and
Built-in/Auto/FreeSASA-reference backends; context remains disabled by default. Graphical
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

OPM is offline-only. Direct PDBTM retrieval does not support proxies, PAC, CONNECT, redirects, or
retries. There is no automatic cache migration or garbage collection, persistent batch history,
visual batch-plan editor, curved/multiple-membrane model, automatic fitting, automatic source selection, provider ranking,
consensus, or biological correctness verdict. Comparison thresholds are geometric review bands,
not biological truth. Ordinary SASA is not lipid accessibility,
local chemical-context labels are conservative evidence, and reports are visual-QC evidence rather
than definitive structural validation. See [docs/known_limitations.md](docs/known_limitations.md)
and [docs/scientific_interpretation.md](docs/scientific_interpretation.md) for the full scientific
boundary, and [docs/offline_and_safety.md](docs/offline_and_safety.md) for exactly what does and
doesn't touch the network and how this project proves it never silently modifies your structure's
coordinates.

## Documentation

Start at [docs/index.md](docs/index.md) -- the full documentation map, grouped into Using the
plugin, Reference, Scientific boundaries, Installation and maintenance, and Developer/release, with
a recommended reading path for first-time users, batch users, developers, and reviewers. Direct
links to the most-used guides:

- **Quick start**: [docs/quick_start.md](docs/quick_start.md) -- install to first exported result
  in one page.
- **Workflows**: [docs/tutorial.md](docs/tutorial.md) covers all five current analysis modes
  (legacy global-z, planar orientation, PDBTM local, PDBTM cache, PDBTM-OPM comparison) and
  **Batch review**; [docs/batch_plan_reference.md](docs/batch_plan_reference.md) is the batch-plan
  field reference, with a fully narrated five-mode example in
  [docs/five_mode_walkthrough.md](docs/five_mode_walkthrough.md).
- **Outputs**: [docs/outputs_and_manifests.md](docs/outputs_and_manifests.md) documents the batch
  output/manifest layout; [docs/status_vocabulary.md](docs/status_vocabulary.md) is the one
  canonical table of every status/error literal this project produces.
- **Troubleshooting**: [docs/troubleshooting.md](docs/troubleshooting.md), organized by symptom.
- **Installation and upgrade**: [docs/compatibility.md](docs/compatibility.md),
  [docs/compatibility_matrix.md](docs/compatibility_matrix.md), and
  [docs/upgrade_guide.md](docs/upgrade_guide.md) (already linked above).
- **Scientific boundaries**: [docs/known_limitations.md](docs/known_limitations.md) (already
  linked above), [docs/scientific_interpretation.md](docs/scientific_interpretation.md), and
  [docs/offline_and_safety.md](docs/offline_and_safety.md).
- **Contract and release governance**: [docs/v1.0_contract_freeze.md](docs/v1.0_contract_freeze.md),
  [docs/versioning_policy.md](docs/versioning_policy.md), and
  [docs/release_checklist.md](docs/release_checklist.md).

## Licence and citation

MIT. No formal citation is available yet; cite `membrane-vqc-pymol` and the exact
version used. The implementation is clean-room and does not copy GPL PyMOL plugin code.
