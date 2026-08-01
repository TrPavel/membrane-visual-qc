# Manual install/upgrade acceptance checklist

Status: **PASS** -- completed by real, owner-observed manual validation on 2026-08-01. This
records what the owner directly observed running the genuine PyMOL Plugin Manager
install/upgrade/uninstall flow for the v0.6.0 -> `0.7.0.dev0` pair. It applies only to that pair
(see [Scope](#scope) below), and it does not replace or duplicate the separate automated test
suite (`tests/test_plugin_install.py`, `tests/test_plugin_upgrade.py`) -- see
`docs/compatibility.md#what-ci-cannot-prove` for what those automated tests structurally cannot
reach, and which this session exercised directly instead.

## Tested artifacts

| | Development ZIP | Stable ZIP |
|---|---|---|
| Filename | `MembraneVisualQC-0.7.0.dev0.zip` | `MembraneVisualQC-0.6.0.zip` |
| Size | 194,338 bytes | 192,168 bytes |
| SHA-256 | `d11234fc3e74bbc7427d6bb18f36897bc86a9d27a9bfec134df9b623307d638c` | `7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960` |
| Packaged version | `0.7.0.dev0` | `0.6.0` |
| Source commit | `28802a640f8eabd38f7e8afbb529da5a306bb68f` (`main`) | published v0.6.0 release asset |

The stable ZIP's SHA-256 matches the value recorded in `docs/v0.6.0_release_evidence.json` and
`docs/upgrade_guide.md`.

## Environment

- Real PyMOL manual session, owner-operated (not headless, not CI).
- Windows (exact build not recorded).
- Exact PyMOL version/build: not recorded.
- Display scaling: not recorded.
- Short-path session root `C:\mvqc-test\` and isolated cache root `C:\mvqc-test\cache\` were used
  for this specific validation session to avoid unrelated Windows `MAX_PATH` effects and to avoid
  touching the owner's real PDBTM cache. These are evidence of what this session used, not a
  requirement for how a future validator must lay out their own session.

## Round A -- clean install (steps B0, A1-A9) -- PASS

- No stray PyMOL process remained before installing; any prior plugin installation was removed
  before the current development ZIP was installed through **Plugin > Plugin Manager > Install New
  Plugin**, followed by a full PyMOL restart (not just closing the dialog).
- After restart: exactly one MembraneVisualQC plugin entry, the dialog reported version
  `0.7.0.dev0`, opened without a traceback, at a usable window size, with working vertical
  scrolling, no duplicate tabs/actions, and no `QThread` warning.
- Single structure smoke test on the designated structure (`bad_core_lys.pdb`, legacy global-z
  mode) produced a result and export without error.
- Batch review smoke test: the five-mode plan (`stage5a_batch_plan.json`) validated, ran, jobs
  reached terminal status in the expected order, **Manifest** and **Reveal output** worked for a
  completed job, and the dialog survived close/reopen.
- A batch run was started and cancelled at a safe point; the run stopped cleanly with no `QThread`
  warning and no frozen UI.

## Round D -- genuine v0.6.0 state preparation (steps D1-D7) -- PASS

- The development plugin was removed and the genuine, checksum-verified v0.6.0 ZIP was installed
  and confirmed, after a full restart, as the sole plugin entry reporting version `0.6.0`.
- Representative pre-upgrade user state was created under v0.6.0: a standalone exported report and
  a completed batch run/output bundle (with manifest) using the five-mode plan, all written outside
  the plugin's own install directory.

## Round E -- upgrade v0.6.0 -> 0.7.0.dev0 (steps E1-E9) -- PASS

- The v0.6.0 installation was removed by **clean replacement** (the documented, supported upgrade
  method -- see `docs/upgrade_guide.md#3-recommended-installation-method`) and the current
  development ZIP was installed, followed by a full restart. Overlay installation was not the
  procedure used.
- After restart: version displayed as `0.7.0.dev0`, exactly one plugin entry, no stale or duplicate
  UI element from the old version, and no `QThread` warning.
- The v0.6.0-era standalone report, the v0.6.0-era batch result bundle, and its manifest all
  remained readable/inspectable through the upgraded plugin. The five-mode plan re-validated
  successfully after the upgrade.
- A new batch run was executed under the upgraded plugin and completed normally without disturbing
  the pre-upgrade outputs from Round D.
- Closing and reopening PyMOL confirmed batch run history did not persist across the restart,
  consistent with the documented session-only history contract.
- No automatic cache migration was claimed or observed at any point in this round.

## Round F -- rollback to genuine v0.6.0 (steps F1-F8) -- PASS

- The `0.7.0.dev0` installation was removed by clean replacement and the genuine v0.6.0 ZIP was
  reinstalled; after a full restart it was confirmed as the sole plugin entry reporting version
  `0.6.0`, with normal startup and no stale/duplicate UI.
- Original v0.6.0-created data (from Round D) remained usable after rollback.
- Artifacts created by `0.7.0.dev0` during Round E were tested under the rolled-back v0.6.0
  install. Each such artifact either opened successfully or was rejected cleanly with a typed
  message -- none caused a crash or corruption. No specific incompatible artifact is claimed to
  exist between these two versions beyond what is already documented in
  `docs/upgrade_guide.md#6-rollback`.
- `0.7.0.dev0` was reinstalled afterward so the session ended on the current development version,
  matching `main`.

## Overall result

**PASS.**

This is owner-observed manual validation, not an automated result. It exercised PyMOL Plugin
Manager's actual graphical install/upgrade/uninstall behavior directly -- something this
repository's automated CI structurally cannot do (see
`docs/compatibility.md#what-ci-cannot-prove`). Across all rounds:

- No duplicate plugin entry, no stale or duplicated UI, no traceback, no visible freeze, and no
  `QThread` warning were observed.
- No user-owned output or cache was unexpectedly deleted.
- No automatic cache migration was tested, claimed, or observed.
- Clean replacement was the upgrade/rollback method used throughout; overlay installation was not
  exercised and remains not the recommended procedure.
- History remained session-only, as documented.
- No tag or GitHub Release was created as part of this validation session.

## Scope

This record covers only the v0.6.0 -> `0.7.0.dev0` pair, using the exact artifacts identified
above. It does not extend backward-compatibility or upgrade-path claims to any other version pair
(for example, v0.5.0 or earlier upgrading directly to `0.7.x`) -- see
`docs/upgrade_guide.md#1-supported-upgrade-path`. A future release (for example, when `1.0.0` is
published) requires its own separate manual validation pass recorded here or in a successor
document; this PASS result does not carry forward automatically.

## Recording results

When a future version pair is validated, replace the relevant section's result with either:

- `PASS`, with the date, PyMOL distribution/version if known, and any deviation observed, or
- `FAIL`, with the date, the exact failing step, and the observed behavior, filed as a new issue
  before being considered resolved.

Do not mark a round PASS based on the existence of passing automated tests alone -- the entire
point of this checklist is to cover what those tests structurally cannot reach.
