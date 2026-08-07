# Documentation map

This page is the entry point into Membrane Visual QC's documentation, grouped into five sections:
**Using the plugin**, **Reference**, **Scientific boundaries**, **Installation and maintenance**,
and **Developer/release**. No document in the first four sections requires knowing this project's
internal development-stage numbering to use. It links to documents; it does not duplicate their
content.

If you only read one thing: start with the [README](../README.md), then
[docs/quick_start.md](quick_start.md).

## Recommended reading paths

**First-time user** -- installing the plugin and running your first analysis:
[README](../README.md) → [Quick start](quick_start.md) → [Tutorial](tutorial.md) →
[Status vocabulary](status_vocabulary.md) (as a reference while reading results) →
[Known limitations](known_limitations.md).

**Batch user** -- running many jobs at once:
[Tutorial](tutorial.md) (to understand each mode individually first) →
[Batch plan reference](batch_plan_reference.md) → [Five-mode walkthrough](five_mode_walkthrough.md)
→ [Outputs and manifests](outputs_and_manifests.md) → [Troubleshooting](troubleshooting.md).

**Developer/maintainer** -- working on the code:
[Report schemas](report_schema.md) → [Compatibility statement](compatibility.md) →
[Contract freeze](v1.0_contract_freeze.md) and [Versioning policy](versioning_policy.md) → the
ADRs under [`adr/`](adr/) → the internal design documents (see
[Developer/release](#developer-release) below) → [known_limitations.md](known_limitations.md).

**Reviewer/auditor** -- verifying a claim or a release:
[Compatibility statement](compatibility.md) → [Manual install/upgrade checklist](manual_install_upgrade_checklist.md)
→ release notes and `*_release_evidence.json` files → [Offline guarantees and safety](offline_and_safety.md).

## Using the plugin

Task-oriented guides for running the plugin -- no prior knowledge of how it was built required.

| Document | Purpose |
|---|---|
| [README](../README.md) | Product entry point: what it does, installation, quick start, PyMOL commands. |
| [Quick start](quick_start.md) | The fastest path from a fresh install to your first exported result, including one minimal batch example. |
| [Tutorial](tutorial.md) | Every current single-structure workflow (legacy global-z, planar, PDBTM local, PDBTM cache, PDBTM-OPM comparison) in depth, plus a Batch review pointer and a visualization color-legend section. |
| [Offline PDBTM import](pdbtm_offline_import.md) | Detailed contract for the local PDBTM API-v1 pair (`pdbtm_local` mode): required files, commands, coordinate/lifecycle rules, provenance. |
| [Batch plan reference](batch_plan_reference.md) | Field-by-field reference for the `mvqc-batch-plan-1.0` contract: structure, fields, path rules, each mode, validation, cancellation, and collision behavior. |
| [Five-mode walkthrough](five_mode_walkthrough.md) | A narrated, run-it-yourself example exercising all five batch modes: what each job demonstrates, expected status, and what the example does and doesn't prove. |
| [Troubleshooting](troubleshooting.md) | Symptom → likely cause → recovery, covering installation, GUI, plans, batch execution, reports/results, networking/cache, and diagnostics. |

## Reference

Technical/contract detail for a specific interface, once you already know which workflow you're
using.

| Document | Purpose |
|---|---|
| [Outputs and manifests](outputs_and_manifests.md) | The on-disk output contract: output root, filenames, `batch-result.json` fields, atomic publication, collision/cancellation layout, and result-browser behavior. |
| [Report schemas](report_schema.md) | Every report schema (1.0-1.5): what each records, which version a given workflow produces, and the versioning history. |
| [Status vocabulary](status_vocabulary.md) | One canonical table of every status/error literal this project uses, where it appears, and its operational meaning. |
| [Offline guarantees and safety](offline_and_safety.md) | Exactly which code touches the network, the coordinate-preservation guarantee, and filesystem-safety behaviors (atomic writes, path containment, symlink protection). |
| [Batch review dialog reference](stage5b_gui_batch.md) | Detailed reference for the **Batch review** dialog itself: controls, state machine, main-thread execution model, cancellation, and history. |
| [Scientific background](scientific_background.md) | Methods reference: every equation and classification rule this project implements, mapped to its exact function/file, plus the literature that motivates each one ([references.bib](references.bib)). |

## Scientific boundaries

What a result reports, and -- just as importantly -- what it deliberately does not claim.

| Document | Purpose |
|---|---|
| [Scientific interpretation](scientific_interpretation.md) | The consolidated scientific-wording boundary: what's reported, what's not claimed, comparison and membrane-context limits, `REVIEW_ITEMS` usage, and the vocabulary this project uses and avoids. |
| [Known limitations](known_limitations.md) | Full list of intentionally unsupported behaviors, by release, including the Windows-paths safety boundary. Read this before interpreting any result. |
| [Scientific background](scientific_background.md) | What is actually calculated, classified, or visualized (with equations), versus what is an external-source interpretation or a manual-review cue -- read this before treating any equation or reference as a validation claim. |

## Installation and maintenance

| Document | Purpose |
|---|---|
| [Compatibility statement](compatibility.md) | Validated configurations (OS, PyMOL distribution, Python, Qt), supported upgrade path, supported schema/contract versions, cache format, and what CI structurally cannot prove. |
| [Compatibility matrix](compatibility_matrix.md) | Grid view: platform × validation method, PyMOL distribution, Python version, schema/contract support per release, and validated configurations vs. formally supported ranges. |
| [Upgrade guide](upgrade_guide.md) | Clean-replacement upgrade and rollback procedures, including the owner-accepted v0.8.0-to-v0.9.0 path and focused v0.9.0-to-v1.0.0rc1 candidate path. |
| [Manual install/upgrade checklist](manual_install_upgrade_checklist.md) | The owner-observed manual PASS record for the v0.6.0 → `0.7.0.dev0` install/upgrade/rollback path -- real evidence, not a template to assume passed for other version pairs. |

## Developer/release

Contract governance, release process, and the historical/internal record of how the software was
built and verified. Not user instructions -- if a document here and a guide above ever disagree,
the guide above wins.

**Contract and release governance:**

| Document | Purpose |
|---|---|
| [v1.0 contract freeze](v1.0_contract_freeze.md) | The audit of every public/machine-readable interface (PyMOL commands, report schemas, batch contracts, cache format, error codes, output layout) and its frozen/not-frozen/internal status ahead of v1.0. |
| [Versioning policy](versioning_policy.md) | How the package version, report schema versions, and batch contract versions are meant to change, and the deprecation process required before a frozen interface can break. |
| [Release checklist](release_checklist.md) | The exact two-PR release process (prepare → tag/publish → evidence-freeze/reopen), developer-facing -- not user installation instructions (see [Installation and maintenance](#installation-and-maintenance) for that). |
| [1.0.0rc1 release notes](1.0.0rc1_release_notes.md) | The release-hardening delta, compatibility boundary, artifact identity, and pending manual status for the RC candidate. |
| [1.0.0rc1 manual acceptance](releases/1.0.0rc1_manual_acceptance.md) | Focused owner-run checklist for the frozen RC; deliberately contains no fabricated results. |
| [Final 1.0 exit criteria](releases/1.0.0_exit_criteria.md) | Evidence and acceptance conditions that remain required before the final 1.0 release. |

**Architecture Decision Records** (`adr/`) -- the reasoning behind specific design decisions:
orientation geometry (`0002`), exposure/SASA semantics (`0003-exposure-semantics.md`), the optional
FreeSASA adapter (`0003-optional-freesasa-adapter.md`), report schema versioning
(`0001-report-schema-versioning.md`), comparison residue mapping
(`0004-comparison-residue-mapping.md`), local chemical-context semantics
(`0004-local-context-semantics.md`), and orientation source adapters (`ADR-0005-orientation-source-adapters.md`).
Note: ADR numbers `0003` and `0004` are each used twice, for two unrelated decisions made the same
day -- a known filename-numbering quirk, not a content error; use the descriptive part of each
filename to tell them apart.

**Internal design and research documents** -- pre-implementation design records, threat models, and
research logs, each headed with a note on its status: `stage4_scope.md`, `stage4_research.md`,
`stage4_source_matrix.md`, `stage4_threat_model.md`, `stage4_fixture_plan.md`,
`stage4a2_pymol_snapshot_semantics.md`, `stage4b_network_cache_design.md`, `stage4b_preflight.md`,
`pdbtm_semantics_preflight.md`, and `superpowers/plans/2026-05-23-membrane-vqc-mvp.md` (the
original, now fully superseded, project MVP plan).

**Implementation and acceptance records** -- what was built and how it was verified, per
development phase: `stage4a2_graphical_acceptance.md`, `stage4b1_implementation.md`,
`stage4b2_implementation.md`, `stage4b3_gui_orchestration.md`, `stage4b4_exact_acceptance.md`,
`stage4c_source_comparison.md`, `stage5a_batch_review.md`, `stage5b_graphical_acceptance.md`. Two
of these remain semi-canonical technical references (linked above under Using the plugin/Reference
as well): `stage5a_batch_review.md` for the batch execution contract's design rationale, and
`stage5b_gui_batch.md` for the Batch review dialog itself.

**Release evidence** -- exact artifact identities and manual smoke-test results per release:
`v0.4.0_release_notes.md` / `v0.4.0_graphical_smoke.md`, `v0.5.0_release_notes.md` /
`v0.5.0_graphical_smoke.md` / `v0.5.0_release_evidence.json`, `v0.6.0_release_notes.md` /
`v0.6.0_release_evidence.json`, `v0.7.0_release_notes.md` / `v0.7.0_release_evidence.json` /
`v0.7.0_install_upgrade_manual_evidence.json`, and `v0.8.0_release_notes.md` /
`v0.8.0_release_evidence.json` / `v0.8.0_install_upgrade_manual_evidence.json` -- see
`docs/release_checklist.md` for how each is produced.

**Internal project-management history** -- rolling development logs, not reference material:
`development_state.md`, `research_log.md`, `validation.md`. `manual_gui_validation.md` is the full
historical graphical-acceptance record across v0.1.0-v0.3.0.

**Other reference material:** [`visual_style.md`](visual_style.md) (the color-legend source table,
now also summarized in the Tutorial), [`visual_identity.md`](visual_identity.md) (the README's own
branding/design conventions -- a different thing from the PyMOL color legend above),
[`screenshot_capture_plan.md`](screenshot_capture_plan.md) (the reproducible plan for capturing a
current, real GUI screenshot and demo, not yet done in this repository's own environment),
[`references.bib`](references.bib) (the full bibliography behind `scientific_background.md`),
`../CITATION.cff` at the repository root (software citation metadata -- see the README's Citation
and references section), and `Report.md` at the repository root (implementation status notes).

## Keeping this map accurate

`tests/test_documentation_consistency.py` checks that the links above resolve and that key facts
(current manifest filename, contract identifiers, offline-action boundary, frozen status/error
vocabulary) stay synchronized with code. It does not, and cannot, verify that prose descriptions
remain accurate indefinitely -- if you find a stale claim, please fix the source document and, if
the fact it states is checkable, consider adding a test for it.
