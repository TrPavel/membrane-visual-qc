# Manual install/upgrade acceptance checklist

Status: **pending owner observation**. Nothing in this document has been run yet. Automated tests
(`tests/test_plugin_install.py`, `tests/test_plugin_upgrade.py`) cannot prove PyMOL Plugin
Manager's actual graphical install/upgrade/uninstall behavior -- see
`docs/compatibility.md#what-ci-cannot-prove`. Do not treat any round below as passed until the
owner has actually performed it and recorded a result here.

Use the exact, checksum-verified `MembraneVisualQC-0.7.x.zip` for the "current development ZIP"
steps below, and the exact, checksum-verified `MembraneVisualQC-0.6.0.zip`
(SHA-256 `7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960`) for the v0.6.0 steps.

## Round A -- clean install

1. Remove or disable any existing Membrane Visual QC plugin installation.
2. Install the current development ZIP through **Plugin > Plugin Manager > Install New Plugin**.
3. Fully restart PyMOL (not just close/reopen the dialog).
4. Confirm the displayed version matches the ZIP's declared version.
5. Open **Single structure** and confirm the tab is usable.
6. Open **Batch review**.
7. **Validate** a plan (for example `data/synthetic/stage5a_batch_plan.json`).
8. **Run** the validated plan.
9. Confirm **Open result manifest** and **Reveal selected report** work for a completed job.
10. Start a run and **Cancel** it; confirm the queue stops cleanly.
11. Close and reopen the dialog; confirm no `QThread` warning and PyMOL remains responsive.

Result: **PENDING**

## Round B -- upgrade from v0.6.0

1. Install the verified v0.6.0 ZIP through Plugin Manager and restart PyMOL.
2. Create representative state: run at least one batch plan to produce a report/output bundle,
   and perform at least one PDBTM Fetch/Refresh (or Use cached pair) so a cache-v1 entry exists.
3. Close PyMOL completely.
4. Install the current development ZIP using the method recommended in
   `docs/upgrade_guide.md#3-recommended-installation-method` (clean replacement).
5. Fully restart PyMOL.
6. Confirm the displayed version is the current development version, not v0.6.0.
7. Confirm the v0.6.0-created outputs from step 2 are still present on disk (this repository never
   deletes them, but confirm Plugin Manager's install step did not touch them either).
8. Open the v0.6.0 batch result bundle from step 2 through **Batch review**'s result browser and
   confirm it still opens correctly.
9. Confirm the cache-v1 entry from step 2 is still usable (**Use cached pair** without a new
   fetch), or, if intentionally not preserved, confirm the failure is a clear, typed message, not
   a crash.
10. Run a new batch plan and confirm it completes normally.
11. Confirm no duplicate plugin menu entry and no stale UI element from the old version.
12. Confirm no `QThread` warning on close/reopen.

Result: **PENDING**

## Round C -- rollback

1. Reinstall the verified v0.6.0 ZIP (clean replacement) and restart PyMOL.
2. Confirm the plugin starts and displays v0.6.0.
3. State clearly which data created under the newer `0.7.x` build is not guaranteed
   backward-compatible with v0.6.0 (per `docs/upgrade_guide.md#6-rollback`, this project makes no
   such guarantee in general, though no concrete incompatible field is currently known to exist
   between these two specific versions).

Result: **PENDING**

## Recording results

When a round is actually run, replace its "Result: **PENDING**" line with either:

- `Result: **PASS**, <date>, <PyMOL distribution/version>` -- and note any deviation observed, or
- `Result: **FAIL**, <date>` with the exact failing step and observed behavior, filed as a new
  issue before being considered resolved.

Do not mark a round PASS based on the existence of passing automated tests alone -- the entire
point of this checklist is to cover what those tests structurally cannot reach.
