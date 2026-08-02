# Offline guarantees and safety

This page consolidates every operational safety guarantee this project makes outside of scientific
correctness: what never touches the network, what the coordinate-preservation guarantee covers,
and the filesystem-safety behaviors (atomic writes, path containment, symlink protection) that
apply across batch execution and the PDBTM cache. Every claim below is grounded in a specific
module or test in this repository -- see the citation after each item. The cache format and the
output/manifest layout described here are frozen v1.0 candidate contracts in their own right; see
[docs/v1.0_contract_freeze.md#7-cache-format-frozen](v1.0_contract_freeze.md#7-cache-format-frozen)
and
[#11-outputmanifest-layout-frozen-as-the-v10-candidate](v1.0_contract_freeze.md#11-outputmanifest-layout-frozen-as-the-v10-candidate).
The network-fetch boundary, coordinate-preservation mechanism, and atomic-write/path-safety
behaviors are current, tested behavior, not separately enumerated as their own frozen interface
line items in that audit.

## Part 1 -- Offline guarantees

### The only network-capable code

Exactly one module in this project opens a network connection:
`membrane_vqc/pdbtm_transport.py` -- a direct, bounded HTTPS client (`http.client` + `ssl` +
`socket`) to `https://pdbtm.unitmp.org`, the reviewed PDBTM API-v1 endpoint. No other module in
`membrane_vqc/` imports `socket`, `ssl`, or an HTTP client library.

### What explicitly fetches network data

The **only** user action that contacts the network is:

- **Fetch** / **Refresh** in the PDBTM cache workflow (GUI, or the equivalent programmatic
  retrieval call) -- an explicit action the user initiates to retrieve a PDBTM record and store it
  as a validated local cache-v1 snapshot.

Nothing else in the plugin -- opening the dialog, switching tabs, selecting a mode, loading a
structure, running any of the five single-structure or batch analysis modes, validating a plan,
exporting a report, browsing a result bundle, or Reveal/Open actions -- performs a Fetch. Even the
`pdbtm_cache` mode (single-structure or batch) only *reads* an already-validated local cache
snapshot; it never fetches on your behalf, and never falls back to fetching if the named snapshot
is missing (`docs/stage5a_batch_review.md`).

### What is proven offline by this repository's own tests

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

### What this project does not have, by design

- **No background telemetry.** No analytics, crash reporting, or usage-tracking code exists in
  `membrane_vqc/`.
- **No update check.** The plugin never checks GitHub, PyPI, or any other endpoint for a newer
  version, on open or otherwise.
- **No automatic fetch on plugin open.** Opening the dialog, or any tab within it, never triggers a
  network call.

### What "offline" does not guarantee

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

## Part 2 -- Coordinate preservation

Membrane Visual QC never intentionally modifies the coordinates of a structure you load. This
section explains the two distinct mechanisms that check and record this, grounded directly in
`membrane_vqc/pdbtm_adapter.py`, `membrane_vqc/opm_adapter.py`, and
`membrane_vqc/comparison_pymol.py`.

### What is fingerprinted

Both mechanisms compute a SHA-256 digest over the same kind of input: an atom-identity-ordered,
fixed-precision (3 decimal places) legacy-PDB-style coordinate serialization of the current PyMOL
object -- named `mvqc_atom_identity_coordinates_sha256` (version `1`). It captures atomic
coordinates keyed to atom identity, not the raw PDB text, camera view, display state, or any other
PyMOL session property.

This is **not** a claim about biological correctness, membrane placement, or structural validity --
it only proves that the specific atom coordinates present at one point in time are byte-identical
(to 3 decimal places) to the atom coordinates present at another point in time.

### Two related but distinct mechanisms

#### 1. Plain PDBTM/batch path (`membrane_vqc/pdbtm_adapter.py`)

Used by `pdbtm_local` and `pdbtm_cache` (single-structure and batch). Three fingerprints are
computed and compared: `transformed_reference` (the provider's transformed-PDB companion, as
provided), `inverse_reference` (the analytical inverse of that transform), and `current` (your
currently loaded object). The current object must match **either** the transformed reference
**or** its inverse directly -- the adapter never searches for, computes, or applies a rigid-body
fit to make them match. If neither matches, applicability is rejected; no analysis runs.

#### 2. Comparison path (`membrane_vqc/opm_adapter.py`, `membrane_vqc/comparison_pymol.py`)

Used by `pdbtm_opm_comparison`. Two fingerprints are compared: `source_fingerprint` (captured once,
when a source is confirmed applicable) and `current_fingerprint` (recomputed at comparison time).
Both independently selected sources (PDBTM and OPM) must match the **same** immutable snapshot of
the selected object before a comparison can run. The report schema field is named
`coordinate_fingerprint` / `coordinate_fingerprint_algorithm`
(`mvqc_atom_identity_coordinates_sha256:v1:legacy_pdb_3dp`), and comparison export explicitly
validates that the selected-object and each applicable-source fingerprint agree before accepting a
report.

### When it is captured, and when it is rechecked

- **Captured**: the moment a source (a local PDBTM/OPM pair, a cache snapshot, or an orientation
  file) is confirmed applicable to your currently selected object.
- **Rechecked**: immediately before the corresponding action actually runs -- Run QC, Show Slab, or
  Compare. If your object's coordinates changed between capture and that action, the recheck fails
  and the action is rejected with a clear error rather than silently analyzing stale-source-against-
  new-coordinates data.
- Batch execution performs the same check per job: `coordinate_preserved` in the job's manifest
  entry records whether the fingerprint matched before and after that job ran (`true`/`false`), or
  `null` if the job never reached that stage (see [status vocabulary](status_vocabulary.md),
  [outputs and manifests](outputs_and_manifests.md)).

### What operations are intentionally read-only

Every analysis mode -- legacy global-z, planar orientation, offline/cached PDBTM, and PDBTM-OPM
comparison -- is read-only with respect to your object's atomic coordinates. The plugin never fits,
aligns, rotates, translates, or otherwise transforms the coordinates of any object you load. Its own
PyMOL-owned visual objects (boundary slabs, colored selections, comparison overlays) are separate,
plugin-owned names removable with `mvqc_clear`; they do not alter your structure's coordinates.

### Coordinates vs. PyMOL visual state

The fingerprint covers atomic coordinates only -- not camera position, representation, color,
visibility, or selection state. Changing how an object *looks* in PyMOL does not invalidate a
captured fingerprint; only a change to its atomic coordinates does.

### What this guarantee does and does not cover

**Covers:** proof that the coordinates an orientation source (or a comparison source) was
determined applicable against are the same coordinates being analyzed right now -- preventing a
stale source from being silently applied to a structure that has since moved.

**Does not cover:**

- Any claim that the structure itself, or its orientation, is biologically correct.
- Any claim about coordinates *before* the fingerprint was first captured.
- Detection of edits to non-coordinate structure data (occupancy, B-factors, chain/residue
  metadata) -- the fingerprint is coordinate-only.
- Any guarantee across a PyMOL session restart -- fingerprints are in-memory/report-scoped, not
  persisted identity claims that survive reloading the same file fresh.

## Part 3 -- Filesystem safety

### Atomic-write behavior

Every artifact this project writes -- each batch job's report/CSV and the `batch-result.json`
manifest -- is published via `membrane_vqc.batch_paths.atomic_write_bytes`: written to a
securely-random temporary file in the destination directory, `fsync`'d, then published with a
single `os.replace`. There is no window where a partially-written file is visible at its final
name. See [docs/outputs_and_manifests.md#atomic-publication-and-collision-behavior](outputs_and_manifests.md#atomic-publication-and-collision-behavior)
for the complete collision/rollback mechanism.

### Path containment and symlink/reparse protection

Batch-plan paths (`membrane_vqc/batch_paths.py`) are validated against a strict safe-path
contract: path traversal (`..`), drive-relative (`C:foo`), UNC (`\\server\share`), device (`\\.\`),
pipe, reserved Windows device names, and symlink/reparse-point paths are all rejected before any
read or write. Ordinary paths with spaces or Unicode characters are fully supported. See
[docs/batch_plan_reference.md#10-safe-path-restrictions](batch_plan_reference.md#10-safe-path-restrictions)
for the complete rule set and examples. The PDBTM cache (`membrane_vqc/pdbtm_cache.py`) enforces
its own independent, equivalent symlink/reparse-point rejection on every already-existing path
component it touches -- a separate implementation from the batch-path contract, not shared code,
but the same protective outcome.

### Failure behavior

A filesystem failure (permission denial, a full/unwritable destination, a path-length limit) fails
fast with a clear, typed error rather than hanging, retrying unboundedly, or leaving a partial
output visible at its final name -- see [docs/troubleshooting.md#batch-execution](troubleshooting.md#batch-execution).

### Limitations of these guarantees

- Filesystem safety covers this project's own writes; it does not protect against another process
  concurrently modifying the same output directory outside this plugin's control.
- Coordinate preservation and atomic writes are independent guarantees -- a coordinate-fingerprint
  mismatch is a scientific-applicability rejection, not a filesystem error, and vice versa.
- None of the guarantees on this page are a claim of biological correctness -- see
  [docs/scientific_interpretation.md](scientific_interpretation.md).
