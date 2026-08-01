# Upgrade guide

This guide covers upgrading Membrane Visual QC from the published **v0.6.0** release to the
current **`0.7.x` development build**. It is version-specific, based on an automated
install/upgrade compatibility harness (`tests/test_plugin_install.py`,
`tests/test_plugin_upgrade.py`) run against the genuine, verified `MembraneVisualQC-0.6.0.zip`
release asset (SHA-256 `7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960`, see
`docs/v0.6.0_release_evidence.json`), plus a manual real-PyMOL checklist
(`docs/manual_install_upgrade_checklist.md`), which the owner ran end to end on 2026-08-01 with a
recorded PASS result -- see that file for the exact steps and observations, which this repository's
automated tests cannot substitute for (see `docs/compatibility.md`).

Once v1.0.0 is published, this guide will be extended to cover v0.6.0 → v1.0.0 directly; it does
not (and will not) attempt to support arbitrary older versions.

## 1. Supported upgrade path

- **v0.6.0 → `0.7.x` development/pre-release**: automated-harness-verified, this guide.
- Any earlier version (v0.5.0 and before): not supported by this guide. If you are running one of
  those, upgrade to v0.6.0 first, verify it works, then follow this guide.

## 2. Before upgrading

- **Close PyMOL completely.** Plugin files cannot be safely replaced while PyMOL has them loaded.
- **Keep your current, verified Plugin ZIP** (`MembraneVisualQC-0.6.0.zip`, with its `.sha256`
  sidecar) if you might want to roll back -- see [Rollback](#6-rollback).
- **You do not need to delete or move any of your outputs.** Batch output directories, exported
  reports, and standalone report files are never stored inside the plugin's own install directory
  and are never touched by installing a new Plugin ZIP.
- **Cache**: the validated PDBTM cache lives at a fixed, version-independent location outside the
  plugin install directory (`%LOCALAPPDATA%\MembraneVisualQC\Cache` on Windows, or the directory
  named by the `MVQC_CACHE_DIR` environment variable if you have set one). Upgrading the plugin
  package never reads, writes, or deletes it. See [Existing data](#5-existing-data) for what
  happens if you ever downgrade instead.
- **History is session-only.** The Batch review tab's run history (at most 20 entries) lives only
  in the dialog's memory for as long as PyMOL stays open; it is not written to disk by any version
  and is not something an upgrade can "lose" or need to preserve. If you need a permanent record of
  a run, keep the manifest/report files it wrote to your chosen output directory.
- Nothing else needs backing up specifically for this upgrade.

## 3. Recommended installation method

**Clean replacement is the officially supported and recommended method.** Remove or fully replace
the previous plugin's files before installing the new ZIP, rather than relying on Plugin Manager to
overlay the new ZIP's files over the old install directory in place.

Why: PyMOL Plugin Manager's own install-directory and overlay-vs-replace behavior is not
controlled by this repository and is not proven by automated tests here (see
`docs/compatibility.md`). This project's own harness confirms that for the v0.6.0 → `0.7.x`
transition specifically, the *set* of packaged files is unchanged (only file contents changed), so
an overlay install is not currently known to leave anything stale -- but that is a property of this
particular upgrade, not a general guarantee for future ones. Recommending clean replacement now
keeps the guidance correct as the package evolves, rather than needing to be revisited every
release.

Steps:

1. Close PyMOL completely.
2. Using Plugin Manager's own removal/uninstall option (if available in your PyMOL build) or by
   manually deleting the installed plugin's directory, remove the existing v0.6.0 installation.
   If you are unsure where Plugin Manager installed it, or your PyMOL build has no removal option,
   see [Troubleshooting](#7-troubleshooting).
3. Open **Plugin > Plugin Manager > Install New Plugin**.
4. Select the verified `MembraneVisualQC-0.7.x.zip` (check its `.sha256` sidecar first --
   [Integrity verification](#8-integrity-verification)).
5. **Fully restart PyMOL** (not just close/reopen the dialog). Plugin Manager and Python's own
   module caching both require a full process restart to pick up replaced files reliably.

## 4. Post-upgrade verification

After restarting PyMOL:

1. Open **Plugin > Membrane Visual QC** and confirm the dialog reports the new version.
2. Confirm **Single structure** opens and its controls are usable.
3. Open **Batch review**, select a plan (for example
   `data/synthetic/stage5a_batch_plan.json` from a checkout, or any plan of your own), and run
   **Validate**.
4. Run one minimal batch (**Run**) and confirm it queues and completes.
5. Select a completed job and confirm **Open result manifest** / **Reveal selected report**
   correctly open the manifest and report.
6. Close and reopen the dialog; confirm PyMOL does not print a `QThread` destroyed-while-running
   warning and remains responsive.

## 5. Existing data

| Category | What happens across this upgrade |
|---|---|
| Standalone reports (any schema 1.0–1.5) | Unaffected -- reports live wherever you exported them, never inside the plugin install directory. Schema 1.0–1.4 reports remain readable by `validate_report()`; schema 1.5 (comparison) reports remain readable by the separate comparison validator. |
| Batch plans | Unaffected. A plan that validated under v0.6.0 still validates under `0.7.x` (the `mvqc-batch-plan-1.0` contract is unchanged). |
| Batch result bundles (`batch-result.json` + job outputs) | Unaffected and remain inspectable through **Batch review**'s result browser -- verified against a genuine v0.6.0-line result bundle in this project's own test suite. |
| Cache (`cache-v1`) | Unaffected -- stored outside the plugin install directory; the cache code itself is byte-for-byte unchanged between v0.6.0 and this `0.7.x` line. No migration occurs because none is needed for this transition. |
| History | Not applicable -- session-only by design (see above); there is nothing to migrate. |

## 6. Rollback

1. Close PyMOL completely.
2. Remove the `0.7.x` plugin installation the same way you would remove any version (see
   [Troubleshooting](#7-troubleshooting) if Plugin Manager offers no direct removal option).
3. Reinstall your previously verified `MembraneVisualQC-0.6.0.zip` through Plugin Manager and
   restart PyMOL.
4. What remains compatible: all of your existing reports, batch plans, batch result bundles, and
   the PDBTM cache -- none of that data is touched by either direction of this upgrade/rollback.
5. **What not to copy backward blindly:** do not copy a `0.7.x`-generated batch result bundle or
   report back and expect an older plugin version to necessarily read every field it produced --
   older code has no obligation to understand anything a newer version might add. This project
   does not currently add such fields between v0.6.0 and `0.7.x`, but do not assume that holds for
   every future version pair without checking that version's own release notes.

## 7. Troubleshooting

**Old version is still displayed after installing the new ZIP.**
PyMOL was not fully restarted, or Python's module cache still holds the old code from before the
restart. Fully quit and relaunch PyMOL (not just close the plugin dialog); confirm no other PyMOL
process is still running in the background.

**Duplicate plugin menu entry.**
Usually means the old and new plugin files are both present under different install-directory
names. Follow [Recommended installation method](#3-recommended-installation-method) to remove the
old installation fully, then restart.

**Stale files after an overlay install.**
Compare your installed `membrane_vqc/` directory's files against its own
`membrane_vqc/PLUGIN_MANIFEST.json` -- any file present in the directory but not listed in the
manifest's `files` array was not written by this ZIP and is a leftover from a prior install.
Delete it, or perform a clean reinstall per section 3.

**"Cache format unsupported" or similar error opening the PDBTM cache.**
The cache fails closed (a clear, typed error, never a silent misread) if its on-disk format does
not match exactly what the installed code expects. For the v0.6.0 → `0.7.x` transition this should
not occur, since the cache code is unchanged. If you do see this, it indicates the cache directory
was written by a different, incompatible tool or a much older/newer plugin version than expected;
it does not necessarily mean the *plugin* installation is broken. Recovery: use **Clear cached
record** for the affected entry, or delete the cache directory named above and re-fetch.

**Invalid old report.**
A report your plugin no longer accepts should raise a clear, typed error (never mutate the file or
crash without explanation) — see `docs/report_schema.md` for exactly which schema versions are
supported. If a report you believe should be valid is rejected, check its `schema_version` field
against that document before assuming an install/upgrade problem.

**Missing output.**
A batch result bundle correctly reports an output as `MISSING` (not an error) if the referenced
file was deleted or moved after the run -- this is expected, not an upgrade defect.

**Permission or path errors while installing, running, or reading outputs.**
As of this `0.7.x` line, permission-denied and unusable-path failures during batch execution fail
promptly with a clear message rather than hanging or crashing (see `docs/known_limitations.md`'s
"Windows paths" section). If installation itself fails with a permission error, you likely lack
write access to wherever Plugin Manager is trying to install; consult your PyMOL distribution's own
documentation for its plugin-directory location and permissions.

## 8. Integrity verification

Always verify a downloaded Plugin ZIP against its `.sha256` sidecar before installing.

PowerShell:

```powershell
Get-FileHash MembraneVisualQC-0.7.x.zip -Algorithm SHA256
```

Compare the printed hash against the contents of `MembraneVisualQC-0.7.x.zip.sha256`.

Unix (macOS/Linux):

```bash
sha256sum -c MembraneVisualQC-0.7.x.zip.sha256
```

Both should confirm the ZIP matches its published checksum exactly before you install it.
