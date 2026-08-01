# Documentation map

This page is the entry point into Membrane Visual QC's documentation. It groups every document by
what it's for, distinguishes current user-facing guidance from historical design/evidence records,
and gives a recommended reading path for a few common roles. It links to documents; it does not
duplicate their content.

If you only read one thing: start with the [README](../README.md), then come back here.

## Recommended reading paths

**First-time user** -- installing the plugin and running your first analysis:
[README](../README.md) → [Tutorial](tutorial.md) → [Status vocabulary](status_vocabulary.md) (as a
reference while reading results) → [Known limitations](known_limitations.md).

**Batch user** -- running many jobs at once:
[Tutorial](tutorial.md) (to understand each mode individually first) →
[Batch plan guide](batch_plan.md) → [Outputs and manifests](outputs_and_manifests.md) →
[Troubleshooting](troubleshooting.md).

**Developer/maintainer** -- working on the code:
[Report schemas](report_schema.md) → [Compatibility statement](compatibility.md) →
[Contract freeze](v1.0_contract_freeze.md) and [Versioning policy](versioning_policy.md) → the
ADRs under [`adr/`](adr/) → the Stage 4/5 design documents (see
[Architecture and historical records](#architecture-and-historical-records) below) →
[known_limitations.md](known_limitations.md).

**Reviewer/auditor** -- verifying a claim or a release:
[Compatibility statement](compatibility.md) → [Manual install/upgrade checklist](manual_install_upgrade_checklist.md)
→ release notes and `*_release_evidence.json` files → [Offline guarantees](offline_guarantees.md)
→ [Coordinate preservation](coordinate_preservation.md).

## Getting started

| Document | Purpose |
|---|---|
| [README](../README.md) | Product entry point: what it does, installation, 60-second quick start, PyMOL commands. |
| [Tutorial](tutorial.md) | Every current single-structure workflow (legacy global-z, planar, PDBTM local, PDBTM cache, PDBTM-OPM comparison), with required inputs, expected output, and scientific boundaries for each. |
| [Known limitations](known_limitations.md) | What this project intentionally does not do, by release. Read this before interpreting any result. |

## Workflows

| Document | Purpose |
|---|---|
| [Tutorial](tutorial.md) | Single-structure workflows (see above) plus a pointer into batch and a visualization color-legend section. |
| [Offline PDBTM import](pdbtm_offline_import.md) | Detailed contract for the local PDBTM API-v1 pair (`pdbtm_local` mode): required files, commands, coordinate/lifecycle rules, provenance. |

## Batch usage

| Document | Purpose |
|---|---|
| [Batch plan guide](batch_plan.md) | First-time-user guide to the `mvqc-batch-plan-1.0` contract: structure, fields, path rules, each mode, validation, cancellation, collision behavior, and a fully narrated five-mode example. |
| [Stage 5B GUI batch](stage5b_gui_batch.md) | Detailed reference for the **Batch review** dialog itself: controls, state machine, main-thread execution model, cancellation, and history. |

## Outputs and schemas

| Document | Purpose |
|---|---|
| [Outputs and manifests](outputs_and_manifests.md) | The on-disk output contract as it exists today: output root, filenames, `batch-result.json` fields, atomic publication, collision/cancellation layout, and what's stable vs. not-yet-frozen. |
| [Report schemas](report_schema.md) | Every report schema (1.0-1.5): what each records, which version a given workflow produces, and the versioning history. |
| [Status vocabulary](status_vocabulary.md) | One canonical table of every status/error literal this project uses, where it appears, its operational meaning, and what it does *not* mean scientifically. |

## Safety and reproducibility

| Document | Purpose |
|---|---|
| [Coordinate preservation](coordinate_preservation.md) | The two coordinate-fingerprint mechanisms (plain PDBTM/batch path vs. comparison path): what's fingerprinted, when, and what the guarantee does and doesn't cover. |
| [Offline guarantees](offline_guarantees.md) | Exactly which code touches the network (one module, one user action) and what "offline" does and doesn't mean here. |
| [Known limitations](known_limitations.md) | Full list of intentionally unsupported behaviors, by release, including the Windows-paths safety boundary. |

## Troubleshooting

| Document | Purpose |
|---|---|
| [Troubleshooting](troubleshooting.md) | Symptom → likely cause → recovery, covering installation, GUI, plans, batch execution, reports/results, networking/cache, and scientific-interpretation questions. |

## Compatibility and upgrades

| Document | Purpose |
|---|---|
| [Compatibility statement](compatibility.md) | Validated configurations (OS, PyMOL distribution, Python, Qt), supported upgrade path, supported schema/contract versions, cache format, and what CI structurally cannot prove. |
| [Compatibility matrix](compatibility_matrix.md) | Grid view: platform × validation method, PyMOL distribution, Python version, schema/contract support per release, and verified vs. unverified upgrade paths. |
| [Upgrade guide](upgrade_guide.md) | Step-by-step v0.6.0 → `0.7.x` upgrade: before-upgrading checklist, recommended clean-replacement method, post-upgrade verification, existing-data compatibility table, rollback, and troubleshooting. |
| [Manual install/upgrade checklist](manual_install_upgrade_checklist.md) | The owner-observed manual PASS record for the v0.6.0 → `0.7.0.dev0` install/upgrade/rollback path -- real evidence, not a template to assume passed for other version pairs. |

## Contract and release governance

| Document | Purpose |
|---|---|
| [v1.0 contract freeze](v1.0_contract_freeze.md) | The audit of every public/machine-readable interface (PyMOL commands, report schemas, batch contracts, cache format, error codes, output layout) and its frozen/not-frozen/internal status ahead of v1.0. |
| [Versioning policy](versioning_policy.md) | How the package version, report schema versions, and batch contract versions are meant to change, and the deprecation process required before a frozen interface can break. |
| [Release checklist](release_checklist.md) | The exact two-PR process (prepare → tag/publish → evidence-freeze/reopen) used to cut every release since v0.5.0, generalized for the next one. |

## Architecture and historical records

These documents describe **how the software was built and verified**, not how to use it today.
They are retained deliberately (nothing here is deleted for being non-user-facing) but are not
instructions -- if a historical document and a current guide above ever disagree, the current guide
wins.

**Architecture Decision Records** (`adr/`) -- the reasoning behind specific design decisions:
orientation geometry (`0002`), exposure/SASA semantics (`0003-exposure-semantics.md`), the optional
FreeSASA adapter (`0003-optional-freesasa-adapter.md`), report schema versioning
(`0001-report-schema-versioning.md`), comparison residue mapping
(`0004-comparison-residue-mapping.md`), local chemical-context semantics
(`0004-local-context-semantics.md`), and orientation source adapters (`ADR-0005-orientation-source-adapters.md`).
Note: ADR numbers `0003` and `0004` are each used twice, for two unrelated decisions made the same
day -- a known filename-numbering quirk, not a content error; use the descriptive part of each
filename to tell them apart.

**Stage design and research documents** -- pre-implementation design records, threat models, and
research logs that fed into the ADRs and shipped code: `stage4_scope.md`, `stage4_research.md`,
`stage4_source_matrix.md`, `stage4_threat_model.md`, `stage4_fixture_plan.md`,
`stage4a2_pymol_snapshot_semantics.md`, `stage4b_network_cache_design.md`, `stage4b_preflight.md`,
`pdbtm_semantics_preflight.md`, and `superpowers/plans/2026-05-23-membrane-vqc-mvp.md` (the
original, now fully superseded, project MVP plan).

**Implementation and acceptance records** -- what was built and how it was verified, per stage:
`stage4a2_graphical_acceptance.md`, `stage4b1_implementation.md`, `stage4b2_implementation.md`,
`stage4b3_gui_orchestration.md`, `stage4b4_exact_acceptance.md`, `stage4c_source_comparison.md`,
`stage5a_batch_review.md`, `stage5b_graphical_acceptance.md`.

**Release evidence** -- exact artifact identities and manual smoke-test results per release:
`v0.4.0_release_notes.md` / `v0.4.0_graphical_smoke.md`, `v0.5.0_release_notes.md` /
`v0.5.0_graphical_smoke.md` / `v0.5.0_release_evidence.json`, `v0.6.0_release_notes.md` /
`v0.6.0_release_evidence.json`, and `v0.7.0_release_notes.md` / `v0.7.0_release_evidence.json` /
`v0.7.0_install_upgrade_manual_evidence.json`.

**Internal project-management history** -- rolling development logs, not reference material:
`development_state.md`, `research_log.md`, `validation.md`. `manual_gui_validation.md` is the full
historical graphical-acceptance record across v0.1.0-v0.3.0.

**Other reference material:** [`visual_style.md`](visual_style.md) (the color-legend source table,
now also summarized in the Tutorial) and `Report.md` at the repository root (implementation status
notes).

## Keeping this map accurate

`tests/test_documentation_consistency.py` checks that the links above resolve and that key facts
(current manifest filename, contract identifiers, offline-action boundary) stay synchronized with
code. It does not, and cannot, verify that prose descriptions remain accurate indefinitely --  if
you find a stale claim, please fix the source document and, if the fact it states is checkable,
consider adding a test for it.
