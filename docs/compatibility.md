# Compatibility statement

The current supported compatibility contract for Membrane Visual QC, as of the published `v0.9.0`
prerelease and the reopened `1.0.0rc1.dev0` development line. This is a
statement of what is actually verified
by this repository's own evidence (tests, CI, manual acceptance records) versus what is inherited
from PyMOL itself and outside this project's control. It does not invent guarantees beyond that
evidence.

## Validated configurations

This project uses "validated configurations" rather than "supported versions" wherever the exact
tested range is not proven by repository evidence.

- **Operating system**: primary development, manual graphical acceptance, and the
  `Stage 4/5 Windows core` CI job all target Windows (validated on Windows 10/11). Ordinary unit
  tests also run on `ubuntu-latest` in CI (`test` job matrix), which validates the pure-Python
  logic cross-platform, but no manual graphical acceptance has been performed on Linux or macOS.
- **PyMOL distribution**: manual graphical acceptance across the v0.1.0–v0.6.0 release cycle used
  Incentive PyMOL (see `docs/manual_gui_validation.md`, `docs/stage5b_graphical_acceptance.md`).
  No other PyMOL distribution (open-source builds, other vendors) has been manually verified by
  this project; the code has no known Incentive-specific dependency, but this is not the same as
  having tested it.
- **Python**: CI runs the pure-Python test suite on 3.10, 3.11, and 3.12
  (`.github/workflows/ci.yml`). The plugin runs inside PyMOL's own bundled Python interpreter at
  runtime, whose exact version is determined by the user's PyMOL distribution, not by this
  project.
- **Qt binding**: the GUI uses `pymol.Qt`, PyMOL's own Qt abstraction layer, and does not import
  PyQt5/PySide directly. `Stage 4/5 Windows core` CI installs `PyQt5==5.15.11` to exercise real-Qt
  GUI tests; this pins the *tested* binding version, not a claim about every binding PyMOL's own
  abstraction layer might select at runtime.

## Supported Plugin ZIP installation method

- Install via PyMOL's **Plugin > Plugin Manager > Install New Plugin**, selecting the published,
  checksum-verified `MembraneVisualQC-X.Y.Z.zip`.
- The ZIP's own structure (single top-level `membrane_vqc/` directory, `PLUGIN_MANIFEST.json`,
  `SHA256SUMS.txt`, deterministic byte-for-byte reproducible build) is fully controlled and tested
  by this repository (`scripts/build_plugin_zip.py`, `tests/test_plugin_zip.py`,
  `tests/test_plugin_install.py`).
- The actual behavior of PyMOL Plugin Manager's install/uninstall/overlay mechanics -- which exact
  directory it extracts into, whether it removes a prior version's files first -- is **not**
  controlled by this repository and is not proven here; see
  [What CI cannot prove](#what-ci-cannot-prove) below.

## Supported upgrade path

- **v0.6.0 → `0.7.x`**: verified by `tests/test_plugin_upgrade.py` against the genuine published
  v0.6.0 asset. See `docs/upgrade_guide.md`.
- **v0.8.0 → v0.9.0**: verified by automated installed-ZIP coverage and the owner-observed
  frozen-artifact clean replacement, retained supported data, rollback, and final reinstall in
  `docs/releases/v0.9.0_manual_acceptance.md`.
- No other version pair is currently verified. Do not assume support for arbitrary historical
  direct upgrades.
- **Clean replacement is the recommended and supported upgrade model.** Overlay installation (new
  ZIP extracted directly over an old install without removing it first) is not known to cause a
  problem for the v0.6.0 → `0.7.x` transition specifically (the packaged file *set* is identical
  between the two), but this project makes no general guarantee that overlay installation is safe
  for every future version pair, since a future release could remove a `.py` module that an
  overlay install would then leave stale and undetected at import time. Clean replacement avoids
  this risk category entirely.

## Supported report schema versions

Schemas 1.0 through 1.4 (the `single_structure_review` report family) are all validated by
`membrane_vqc.report.validate_report()`, dispatching by the report's own declared
`schema_version`. Schema 1.5 (`orientation_source_comparison`) is a structurally distinct report
type, validated only by `membrane_vqc.comparison_report.validate_comparison_report()`. See
`docs/report_schema.md` for the full per-schema contract and `docs/adr/0001-report-schema-versioning.md`
for the versioning policy (including where the 1.0→1.1 transition did not fully follow that
policy's own ideal, and how schema-1.0 read support was restored).

## Supported batch contract versions

`mvqc-batch-plan-1.0` and `mvqc-batch-result-1.0` only. Both are exact-string contract identifiers
(`membrane_vqc/batch_contracts.py`); there is no version-range parsing or migration mechanism yet.
A plan or result declaring any other contract string is rejected with a clear, typed error, not
silently reinterpreted.

## Cache format

`cache-v1`, a fixed on-disk layout under `pdbtm-api-v1/cache-v1/` at a location independent of the
plugin's own install directory (`membrane_vqc.pdbtm_cache.select_cache_root()`:
`%LOCALAPPDATA%\MembraneVisualQC\Cache` on Windows by default, or `$MVQC_CACHE_DIR` if set). The
format-version discriminator is baked into that path segment and an internal `format.json`
literal; an incompatible future format is expected to fail closed with a clear error rather than
silently misread, but no automatic migration between cache format versions currently exists. See
`docs/upgrade_guide.md` for what this means in practice across the v0.6.0 → `0.7.x` upgrade
(nothing -- the cache code is unchanged between those two versions).

## Intentionally unsupported behaviors

- No automatic cache migration, garbage collection, or format upgrade.
- No persistent (cross-session) batch run history -- session-only by design.
- No PyPI publication; GitHub Releases is the sole distribution channel.
- No automatic fitting, alignment, consensus orientation, provider ranking, preferred-source
  selection, or biological correctness verdict anywhere in the plugin.
- No support for arbitrary historical version upgrades beyond the one path stated above.
- No extended-length (`\\?\`-prefixed) Windows path support -- rejected intentionally; see
  `docs/known_limitations.md`.

## What CI cannot prove

Automated CI never launches a real PyMOL process with a graphical Plugin Manager, so the following
remain manual-verification-only, tracked in the applicable version-specific acceptance record:

- The actual graphical "Install New Plugin" flow and its file-placement/removal behavior.
- Qt menu-item registration actually appearing in a running PyMOL session.
- Whether a second, duplicate plugin entry can appear after an overlay install in practice.
- Full close/reopen and `QThread` lifecycle behavior under the genuinely installed (not
  source-tree) plugin.
- A round is not to be treated as passed unless the maintainer has actually run it and recorded
  the result in `docs/manual_install_upgrade_checklist.md` -- do not treat this document's
  existence as evidence that it has been. For the v0.6.0 -> `0.7.0.dev0` pair specifically, that
  checklist now records a PASS from an owner-observed session on 2026-08-01; this does not extend
  to any other version pair.
