# Versioning and deprecation policy

This page states how Membrane Visual QC's version number, report/batch contract versions, and
error-code vocabulary are meant to change over time, and what happens when a frozen interface
(`docs/v1.0_contract_freeze.md`) needs to change anyway. It formalizes practice this project has
already followed through v0.1.0-v0.7.0; it does not retroactively change any past release.

## 1. Package version (`membrane_vqc.constants.VERSION`, `pyproject.toml`)

- **Pre-1.0 (current)**: `0.MINOR.PATCH`, with an optional `.devN` suffix for active development
  between releases (for example `0.8.0.dev0`). A MINOR bump ships new features or fixes; this
  project does not currently use PATCH releases pre-1.0 -- every release to date has bumped MINOR.
  Any 0.x release may in principle change behavior in a way that would be "breaking" under strict
  semver; in practice this project has kept every genuinely public interface
  (`docs/v1.0_contract_freeze.md`) additive-only since v0.4.0, and intends to keep doing so through
  v1.0.
- **At v1.0**: standard semantic versioning begins. MAJOR changes signal a breaking change to a
  frozen interface; MINOR adds capability without breaking one; PATCH fixes a defect without
  changing any documented contract.
- The active version always lives in exactly two places, kept in agreement by
  `scripts/validate_release_artifacts.py`'s version-agreement check: `pyproject.toml` and
  `membrane_vqc/constants.py`. Both are updated together in every release-preparation commit; see
  `docs/release_checklist.md`.

## 2. The 1.x compatibility commitment

This section states, concretely and by name, what the entire 1.x series (`1.0.0` through the last
release before a hypothetical `2.0.0`) commits to never breaking, what may change freely within
1.x, and what would require a `2.0.0` instead. It is the operative policy referenced by
`docs/releases/1.0.0_readiness.md` and `docs/releases/1.0.0_plan.md`; those documents track *when*
each frozen item is verified, this section states *what is promised*.

### Frozen for the entire 1.x series

- **Public PyMOL command names and their required arguments** -- the 11 commands in
  `docs/v1.0_contract_freeze.md#4-pymol-commands-frozen` (`mvqc_check`, `mvqc_check_orientation`,
  `mvqc_slab_orientation`, `mvqc_check_pdbtm`, `mvqc_slab_pdbtm`, `mvqc_slab`,
  `mvqc_color_hydropathy`, `mvqc_ligand_shell`, `mvqc_export`, `mvqc_batch_run`, `mvqc_clear`) keep
  their names and required-parameter shape. Optional parameters may be added (§"Allow" below).
- **Batch-plan contract `mvqc-batch-plan-1.0`** -- the exact contract string, its required top-level
  shape, and the five-mode closed union (`legacy_global_z`, `planar_orientation`, `pdbtm_local`,
  `pdbtm_cache`, `pdbtm_opm_comparison`) as currently defined in `membrane_vqc/batch_contracts.py`.
- **Report schema versions 1.0 through 1.5 and their required fields** -- each schema's required
  fields and validation behavior, exactly as already governed by §3 below; 1.x may only *add* schema
  versions, never change what 1.0-1.5 require.
- **The PDBTM validated-cache record format (`cache-v1`)** -- the on-disk layout documented in
  `docs/v1.0_contract_freeze.md#7-cache-format-frozen` (`format.json`/`index.json` shape,
  `blobs/sha256/<2-char>/<digest>` addressing, `records/<record_id>/snapshots/<snapshot_id>.json`).
- **Output-directory layout and deterministic filename rules** -- `batch-result.json`, flat output
  root, `<job_id>.json`/`<job_id>.csv` naming via `safe_output_name()`, atomic-publish semantics, and
  the collision/rollback rules in `docs/outputs_and_manifests.md`.
- **The documented status and outcome vocabulary** -- every literal in `docs/status_vocabulary.md`
  (once that document is verified exhaustive per `docs/releases/1.0.0_readiness.md` item R-2). A
  status string's meaning, once released, is never redefined.
- **CSV column contracts** -- `CSV_FIELDS` (`membrane_vqc/report.py`) and the equivalent per-job
  batch CSV columns, once pinned by a regression test (`docs/releases/1.0.0_readiness.md` item R-1).

### Allowed within 1.x (minor version bump, no deprecation needed)

- Additive optional JSON fields on any report schema, batch-plan job, or batch-result entry.
- Additive report-schema versions (a new `schema_version` string for new evidence categories --
  the 1.5 `orientation_source_comparison` schema is the existing precedent for this).
- New optional PyMOL commands, and new optional parameters (with safe defaults) on existing
  commands.
- Non-breaking GUI layout and wording changes -- explicitly **not frozen**, see
  `docs/v1.0_contract_freeze.md#12-not-frozen-explicitly-excluded-from-any-compatibility-commitment`.
- Scientifically justified threshold changes (comparison bands, identity tolerances, exposure
  classification cutoffs), but **only** when the change is explicitly documented (what changed, why,
  since which version), the new value is itself versioned or otherwise distinguishable in report
  provenance, and the change is covered by regression evidence proving the new behavior is
  intentional, not incidental. An undocumented threshold change is treated as a defect, not a
  1.x-allowed evolution, regardless of how small the change is.

### Requires a 2.0 release

- Removal or renaming of any public PyMOL command, or removal/renaming of a *required* parameter.
- Any incompatible change to an existing report schema (1.0-1.5) -- removing or changing the
  meaning of a required field, or changing how an already-released schema version is validated.
- Any incompatible batch-plan change -- removing a mode from `MODES`, changing the meaning of an
  existing mode's required fields, or changing the `mvqc-batch-plan-1.0`/`mvqc-batch-result-1.0`
  contract strings' validation behavior for plans/results that already declare them.
- Removal or semantic redefinition of any status/outcome string (adding a new status is allowed;
  changing what an existing one means, or deleting one still in use, is not).
- Any incompatible cache-format change -- one that would make an existing `cache-v1` snapshot
  unreadable without an explicit, tested migration path.
- Breaking CSV column changes -- removing, renaming, or reordering an existing column once §"Frozen"
  above applies to it. Appending a new column at the end is allowed within 1.x.

## 3. Report schema versions (`schema_version` field)

Governed by `docs/adr/0001-report-schema-versioning.md`; this section restates the operative rule.

- A report schema version string is `MAJOR.MINOR` (for example `1.3`). A MINOR bump adds fields
  additively without invalidating readers of the prior minor version's required fields. A MAJOR
  bump may restructure the report and is validated by a structurally distinct schema
  (`orientation_source_comparison`, schema 1.5, is the current example of this -- it shares no
  required-field shape with the `single_structure_review` family 1.0-1.4).
- Every released schema version is immutable once frozen (`docs/v1.0_contract_freeze.md#1-report-schemas-frozen`):
  its JSON Schema file's bytes, and `membrane_vqc.report.validate_report()`'s read-side dispatch
  behavior for it, do not change. The 1.0-to-1.1 transition did not fully follow the additive-minor
  ideal (ADR-0001 records this explicitly as a lesson, not a template) -- schema-1.0 read support
  was deliberately restored in v0.7.0 after being temporarily broken, and that restoration is
  itself now part of the frozen contract.
- A new schema version is added, never inserted retroactively or renumbered. `SUPPORTED_SCHEMA_VERSIONS`
  in `membrane_vqc/report.py` is the authoritative current read-support list; a new version is
  additive to it.

## 4. Batch contract versions (`contract` field)

- `mvqc-batch-plan-1.0` and `mvqc-batch-result-1.0` are exact-string identifiers
  (`membrane_vqc/batch_contracts.py`) -- there is no version-range parsing (`1.x` does not match
  `1.1`) and no silent reinterpretation of an unrecognized string. A future contract change ships
  as a new exact string (for example `mvqc-batch-plan-1.1` or `mvqc-batch-plan-2.0`, chosen at the
  time based on whether the change is additive or breaking), and old plans/results keep validating
  against the version they declare.
- The five-mode closed union (`MODES`) may only grow, never shrink or rename an existing mode,
  without a MAJOR-equivalent contract version bump.

## 5. Error code vocabulary

- Stable error-code strings (`docs/v1.0_contract_freeze.md#6-error-code-vocabulary-frozen-additive-only`)
  are additive-only pre-v1.0 and additive-only post-v1.0 within a MAJOR version. A code's string
  value, once released, is never reused for a different meaning.
- Removing a code entirely (as opposed to simply no longer producing it in new code paths) requires
  the deprecation process below, since an external caller may still be matching on it.

## 6. Deprecation process

Applies to anything listed as **Frozen** in `docs/v1.0_contract_freeze.md`.

1. **Announce.** The deprecation is recorded in `CHANGELOG.md` under a `### Deprecated` heading in
   the release that introduces it, naming the exact interface, why, and the planned removal
   release (or, pre-v1.0, the planned MAJOR version).
2. **Coexist.** The deprecated interface continues to function unchanged for at least one full
   MINOR release cycle (pre-v1.0) or one full MAJOR release cycle (post-v1.0) after being
   announced. It may emit a non-fatal warning during this window (a Python `DeprecationWarning`,
   or -- for a file-format-level deprecation -- a note in the relevant report/manifest) but must not
   change behavior or fail closed.
3. **Remove.** Only in the announced release does the interface actually stop working, with a
   `### Removed` CHANGELOG entry cross-referencing the original deprecation entry.
4. **Update the contract-freeze page.** `docs/v1.0_contract_freeze.md` is updated in the same PR
   that removes the interface, not before.

No interface has been removed under this process yet; v0.7.0's schema-1.0 read-compatibility
restoration is the closest precedent, and it went the other direction (undoing an accidental
removal, not a planned deprecation) -- see `docs/adr/0001-report-schema-versioning.md`.

## 7. What does *not* require this process

Changes to anything listed as **Not frozen** or **Internal** in
`docs/v1.0_contract_freeze.md#12-not-frozen-explicitly-excluded-from-any-compatibility-commitment`
may ship in any release with only a CHANGELOG entry -- no deprecation window is required. This
includes scientific thresholds/heuristics, GUI layout, and internal module structure.

## 8. Relationship to `docs/upgrade_guide.md`

`docs/upgrade_guide.md` documents the *installation and data-compatibility* mechanics of a specific
version pair (currently v0.8.0 -> v0.9.0, with formal manual acceptance still pending). This page
governs the *interface* contract
across all versions. A version pair can be interface-compatible per this policy while still needing
its own dedicated, harness-tested upgrade guide entry before this project claims the upgrade path
itself is verified -- see `docs/compatibility.md#supported-upgrade-path`.
