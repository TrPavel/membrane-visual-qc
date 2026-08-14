# Upgrade guide: clean replacement and rollback

This guide preserves the owner-accepted v0.8.0-to-v0.9.0 procedure and the verified
v0.9.0-to-v1.0.0rc1-to-v1.0.0 clean-replacement path. Automated installed-ZIP coverage verifies
package isolation and upgrade mechanics; exact frozen artifacts also passed owner-observed upgrade
and rollback acceptance.
See `docs/compatibility.md` for the supported-surface boundary and `docs/troubleshooting.md` for
the full symptom guide.

## Stable path: v0.9.0 or v1.0.0rc1 to v1.0.0

1. Download and checksum-verify the published starting-version ZIP for rollback and the stable
   `MembraneVisualQC-1.0.0.zip` for upgrade.
2. Record the current plugin version and exact install, external output, and PDBTM-cache locations.
   Keep all user-owned reports, plans, result bundles, outputs, and cache outside the plugin tree.
3. Fully exit PyMOL, remove the exact installed plugin directory, confirm it is absent, and install
   the stable ZIP through **Plugin > Plugin Manager > Install New Plugin**. Never overlay the ZIP.
4. Fully exit and restart PyMOL. Confirm displayed version `1.0.0`, exactly one menu entry and
   dialog, then execute the relevant smoke checks.
5. Confirm retained reports (schemas 1.0-1.5), batch plans/results, and `cache-v1` data validate
   without being rewritten. Session-only history is intentionally not persisted.
6. For rollback, fully exit PyMOL, remove the v1.0.0 plugin directory, reinstall the
   checksum-verified starting-version ZIP, restart, and confirm its displayed version. This is
   another clean replacement.

The frozen RC and stable sizes and SHA-256 values are recorded in their acceptance checklists.
Those records distinguish owner-observed PASS results from automated evidence.

## 1. Supported upgrade path

- **v0.8.0 to v0.9.0**: automated-harness-covered and owner-accepted against the published frozen
  artifact, including rollback and final reinstall.
- **v0.9.0 to v1.0.0rc1 and v1.0.0**: automated-harness-covered and owner-accepted against the
  exact frozen artifacts, including clean replacement and rollback.
- Older installations: upgrade sequentially using their release documentation, or perform a clean
  v0.9.0 install while retaining user-owned reports and outputs. No arbitrary historical in-place
  upgrade is promised.

## 2. Before upgrading

1. Download and verify both the official v0.8.0 ZIP (for rollback) and the frozen v0.9.0 ZIP.
2. Record the current plugin version, plugin install directory, external output directories, and
   PDBTM cache directory.
3. Fully exit PyMOL. Replacing files while PyMOL is running can leave old modules in Python's
   module cache even when the files on disk are new.
4. Keep reports, plans, batch-result bundles, and cache outside the plugin installation directory.

## 3. Replace the v0.8.0 installation

Clean replacement is required for the accepted procedure:

1. With PyMOL fully closed, remove v0.8.0 using Plugin Manager's uninstall option, if available,
   or delete the exact installed `membrane_vqc` plugin directory recorded above.
2. Confirm the old plugin directory is gone. Do not extract v0.9.0 over v0.8.0: an overlay cannot
   remove files that a prior version installed and can therefore preserve stale modules.
3. Start PyMOL and use **Plugin > Plugin Manager > Install New Plugin** to select the verified
   `MembraneVisualQC-0.9.0.zip`.
4. Fully exit and restart PyMOL. Closing only the plugin dialog is insufficient.

## 4. Verify version and stale-module absence

1. Confirm displayed version `0.9.0`, exactly one menu item, and one dialog.
2. Run one valid single-structure QC and one minimal batch plan.
3. Close/reopen the dialog, then fully restart and reopen once more. Confirm the version and
   commands remain `0.9.0`, with no traceback, duplicate UI, or `QThread` warning.
4. If the old version appears, stop: another PyMOL process or old install directory remains.

## 5. Existing data

| Data | v0.9.0 behavior |
|---|---|
| Reports | Valid single-structure schemas 1.0-1.4 remain readable; comparison schema 1.5 remains readable by its comparison validator. Validation does not rewrite files. |
| Batch plans | `mvqc-batch-plan-1.0` remains frozen. A valid v0.8.0 plan remains valid unless it relied on invalid filesystem input. |
| Batch results | Files remain in place. The browser revalidates manifests/artifacts; missing or stale outputs are reported, never silently substituted. |
| PDBTM cache | `cache-v1` remains outside the plugin tree. No migration is required. Corrupt/incompatible entries fail closed; preserve evidence before clearing one. |
| Session history | Not migrated. It is deliberately in-memory; manifests are the persistent record. |

The formal checklist verifies these promises with retained v0.8.0 data. Forward compatibility from
v0.8.0 to future additive fields is not promised after rollback.

## 6. Roll back to v0.8.0

1. Fully exit PyMOL and remove the v0.9.0 plugin directory completely.
2. Install the checksum-verified official `MembraneVisualQC-0.8.0.zip`.
3. Fully restart PyMOL and confirm displayed version `0.8.0`.
4. Retain external outputs/cache, but use v0.8.0 only with schemas it understands.

Rollback is another clean replacement, never an overlay.

## 7. Troubleshooting and uninstall

- **Old version/duplicate menu:** exit every PyMOL process, remove every old plugin directory,
  reinstall once, and restart.
- **Stale files:** compare installed files to `membrane_vqc/PLUGIN_MANIFEST.json`; perform clean
  replacement if anything unlisted remains.
- **Cache failure:** record the failure; `cache-v1` fails closed. Clear only after retaining
  evidence, or restore a backed-up valid cache.
- **Uninstall:** fully exit PyMOL, uninstall through Plugin Manager or delete the exact plugin
  directory, then restart. External user outputs/cache remain unless removed separately.

## 8. Integrity verification

```powershell
Get-FileHash .\MembraneVisualQC-0.9.0.zip -Algorithm SHA256
```

```bash
sha256sum -c MembraneVisualQC-0.9.0.zip.sha256
```

The size and digest must match the release-preparation report and checklist header exactly.
