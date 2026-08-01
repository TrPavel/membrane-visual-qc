# Offline guarantees

This page states precisely which parts of Membrane Visual QC never touch the network, which one
action explicitly does, and what "offline" does and does not mean here. Every claim below is
grounded in a specific module or test in this repository -- see the citation after each item.

## The only network-capable code

Exactly one module in this project opens a network connection:
`membrane_vqc/pdbtm_transport.py` -- a direct, bounded HTTPS client (`http.client` + `ssl` +
`socket`) to `https://pdbtm.unitmp.org`, the reviewed PDBTM API-v1 endpoint. No other module in
`membrane_vqc/` imports `socket`, `ssl`, or an HTTP client library.

## What explicitly fetches network data

The **only** user actions that contact the network are:

- **Fetch** / **Refresh** in the PDBTM cache workflow (GUI, or the equivalent programmatic
  retrieval call) -- an explicit action the user initiates to retrieve a PDBTM record and store it
  as a validated local cache-v1 snapshot.

Nothing else in the plugin -- opening the dialog, switching tabs, selecting a mode, loading a
structure, running any of the five single-structure or batch analysis modes, validating a plan,
exporting a report, browsing a result bundle, or Reveal/Open actions -- performs a Fetch. Even the
`pdbtm_cache` mode (single-structure or batch) only *reads* an already-validated local cache
snapshot; it never fetches on your behalf, and never falls back to fetching if the named snapshot
is missing (`docs/stage5a_batch_review.md`).

## What is proven offline by this repository's own tests

- **Batch plan validation is offline.** `python -m membrane_vqc.batch_cli validate PLAN.json` does
  not import PyMOL, and the CLI's own module docstring states it validates "without importing
  PyMOL" (`membrane_vqc/batch_cli.py`). Nothing in the plan-validation path imports `socket` or an
  HTTP client.
- **Importing the GUI and PDBTM worker modules never opens a socket.** This is a direct, enforced
  test guarantee: `tests/test_stage4b3_package_safety.py` monkeypatches `socket.socket` to raise if
  called, then imports `membrane_vqc.gui`, the PDBTM worker, and the PDBTM GUI worker in a
  subprocess -- an assertion failure (not just an absence of observed calls) would fail the test if
  import alone ever created a socket.
- **Five-mode batch execution is offline when its inputs and cache snapshots are already local.**
  `legacy_global_z`, `planar_orientation`, and `pdbtm_local` never reference the network by
  construction (they only read local files you supply). `pdbtm_cache` reads only the plan's exact
  predeclared local snapshot. `pdbtm_opm_comparison` requires an explicit local OPM file and either
  a local PDBTM pair or an already-cached snapshot -- OPM has no fetch path in this project at all
  (`docs/stage4c_source_comparison.md#opm-contract-decision-offline-only`).
- **Cache lookup is local.** The PDBTM cache lives on disk at a fixed location
  (`%LOCALAPPDATA%\MembraneVisualQC\Cache` or `$MVQC_CACHE_DIR`) and **Use cached pair** reads only
  from it; only **Fetch**/**Refresh** reaches the network.
- **Report/result inspection performs no network operation.** Exporting, validating, or browsing a
  report or a batch result bundle (including through the result browser's Manifest/Reveal/Open
  actions) is pure local file I/O and JSON/schema validation.

## What this project does not have, by design

- **No background telemetry.** No analytics, crash reporting, or usage-tracking code exists in
  `membrane_vqc/`.
- **No update check.** The plugin never checks GitHub, PyPI, or any other endpoint for a newer
  version, on open or otherwise.
- **No automatic fetch on plugin open.** Opening the dialog, or any tab within it, never triggers a
  network call.

## What "offline" does not guarantee

- This project cannot control or observe what **PyMOL itself**, another installed plugin, or your
  operating system does independently -- for example, PyMOL's own licensing module, an unrelated
  plugin's own update check, or OS-level DNS/telemetry are entirely outside this project's code and
  are not covered by any claim here.
- **Proxy environments are not supported for the one network action that exists.** A configured
  system proxy causes the PDBTM Fetch/Refresh transport to fail closed with `PROXY_UNSUPPORTED`
  rather than silently routing through it (`docs/status_vocabulary.md#7-cache-and-provider-error-codes`,
  `docs/known_limitations.md`).
- This page describes what *this repository's code* does; it is not a claim about network activity
  from your OS, VPN, antivirus, or any other software sharing the machine.
