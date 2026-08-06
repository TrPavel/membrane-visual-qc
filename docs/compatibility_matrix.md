# Compatibility matrix

A grid view of what this project actually validates, where, and how -- complementing the prose in
`docs/compatibility.md`. Every cell is grounded in a specific CI job, test, or manual acceptance
record; "not verified" is not the same as "known broken."

## Platform x validation method

| Platform | Pure-Python test suite | Graphical/GUI acceptance | Windows filesystem hardening |
|---|---|---|---|
| Linux (`ubuntu-latest`) | CI `test` job, Python 3.10/3.11/3.12 | Not performed | N/A (Windows-specific tests skip) |
| Windows 10/11 | CI `Stage 4/5 Windows core` job, Python 3.10 + `PyQt5==5.15.11` | Manual, Incentive PyMOL (see `docs/manual_gui_validation.md`, `docs/stage5b_graphical_acceptance.md`) | CI `Stage 4/5 Windows core` job |
| macOS | Not run in CI, not manually verified | Not performed | N/A |

## PyMOL distribution

| Distribution | Status |
|---|---|
| Incentive PyMOL 3.1.8 (bundled Python 3.10.20) | Manually verified, Windows -- the only distribution used for every graphical acceptance record to date |
| Open-source PyMOL builds (other vendors) | Not manually verified. No known Incentive-specific dependency in the code, but this is not the same as having tested it (`docs/compatibility.md#validated-configurations`) |

## Python version

| Version | Coverage |
|---|---|
| 3.10 | Full CI matrix + Windows core job (this is also PyMOL 3.1.8's bundled interpreter version) |
| 3.11 | Full CI matrix + FreeSASA reference job |
| 3.12 | Full CI matrix |

The plugin runs inside PyMOL's own bundled interpreter at runtime, whose version is determined by
the user's PyMOL distribution, not by this project.

## Report schema support by release

| Release | Schemas readable | Schemas this release can *write* |
|---|---|---|
| v0.1.0 | 1.0 | 1.0 |
| v0.2.0 | 1.0-1.1 | 1.1 |
| v0.3.0 | 1.0-1.2 | 1.1, 1.2 |
| v0.4.0 | 1.0-1.3 | 1.1, 1.2, 1.3 |
| v0.5.0 | 1.0-1.5 | 1.1, 1.2, 1.3, 1.4, 1.5 |
| v0.6.0 | 1.0-1.5 | 1.1, 1.2, 1.3, 1.4, 1.5 (adds batch contracts, no new report schema) |
| v0.7.0 | 1.0-1.5 (restores 1.0 read support) | 1.1, 1.2, 1.3, 1.4, 1.5 |
| v0.8.0 | 1.0-1.5 | 1.1, 1.2, 1.3, 1.4, 1.5 |
| v0.9.0 | 1.0-1.5 | 1.1, 1.2, 1.3, 1.4, 1.5 |

Which schema a *write* path selects depends on the mode/options used (legacy/planar -> 1.1, +context
-> 1.2, offline PDBTM -> 1.3, cached PDBTM -> 1.4, comparison -> 1.5); see `docs/report_schema.md`.
No release has ever produced a schema-1.0 report by choice -- only v0.1.0 could, since 1.1
superseded it immediately in v0.2.0. Read support for 1.0 lapsed between v0.2.0 and v0.7.0 and was
restored in v0.7.0; see `docs/adr/0001-report-schema-versioning.md`.

## Batch contract support by release

| Release | `mvqc-batch-plan-1.0` / `mvqc-batch-result-1.0` |
|---|---|
| v0.1.0-v0.5.0 | Not present (introduced in v0.6.0) |
| v0.6.0 | Introduced, full support (5 modes, CLI, GUI) |
| v0.7.0 | Unchanged, full support |

## Verified upgrade paths

| From | To | Status |
|---|---|---|
| v0.6.0 | v0.7.0 | **Verified** -- automated harness (`tests/test_plugin_install.py`, `tests/test_plugin_upgrade.py`) against the genuine v0.6.0 asset, plus owner-observed real-PyMOL clean-install/upgrade/rollback (`docs/manual_install_upgrade_checklist.md`) |
| Any release before v0.6.0 | v0.7.x or later | **Not verified.** Upgrade to v0.6.0 first, confirm it works, then follow the verified path above (`docs/upgrade_guide.md#1-supported-upgrade-path`) |
| v0.7.0 | v0.8.0 | **Verified by owner-observed manual smoke test only** -- clean-replacement upgrade, version display, and outputs/cache preservation confirmed (`docs/v0.8.0_install_upgrade_manual_evidence.json`). No automated `tests/test_plugin_install.py` / `tests/test_plugin_upgrade.py` harness exists for this pair, and rollback was not exercised; `docs/upgrade_guide.md` is intentionally not extended to name this pair "supported" until such a harness exists |
| v0.8.0 | v0.9.0 | **Prepared, not yet manually accepted** -- installed-ZIP mechanics are automated and `docs/upgrade_guide.md` defines clean replacement/rollback; support remains provisional until `docs/releases/v0.9.0_manual_acceptance.md` records a real-PyMOL PASS against the frozen ZIP |

## Cache format support by release

| Release | Cache format |
|---|---|
| v0.5.0-v0.7.0 | `cache-v1`, unchanged byte-for-byte since introduction. No migration needed across the v0.6.0 -> v0.7.0 upgrade because none exists to do. |

## What CI cannot prove (unchanged from `docs/compatibility.md`)

The actual graphical "Install New Plugin" flow, Qt menu-item registration in a running session,
duplicate-plugin-entry behavior after an overlay install, and full close/reopen `QThread` lifecycle
under a genuinely installed (not source-tree) plugin all remain manual-verification-only --
tracked per version in `docs/manual_install_upgrade_checklist.md`, not assumed from this matrix or
from passing CI alone.
