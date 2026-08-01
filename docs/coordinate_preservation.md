# Coordinate preservation

Membrane Visual QC never intentionally modifies the coordinates of a structure you load. This page
explains the two distinct mechanisms that check and record this, grounded directly in
`membrane_vqc/pdbtm_adapter.py`, `membrane_vqc/opm_adapter.py`, and `membrane_vqc/comparison_pymol.py`.

## What is fingerprinted

Both mechanisms compute a SHA-256 digest over the same kind of input: an atom-identity-ordered,
fixed-precision (3 decimal places) legacy-PDB-style coordinate serialization of the current PyMOL
object -- named `mvqc_atom_identity_coordinates_sha256` (version `1`). It captures atomic
coordinates keyed to atom identity, not the raw PDB text, camera view, display state, or any other
PyMOL session property.

This is **not** a claim about biological correctness, membrane placement, or structural validity --
it only proves that the specific atom coordinates present at one point in time are byte-identical
(to 3 decimal places) to the atom coordinates present at another point in time.

## Two related but distinct mechanisms

### 1. Plain PDBTM/batch path (`membrane_vqc/pdbtm_adapter.py`)

Used by the `pdbtm_local` and `pdbtm_cache` analysis modes (single-structure and batch). Three
fingerprints are computed and compared:

- `transformed_reference` -- the fingerprint of the provider's transformed-PDB companion file, as
  provided.
- `inverse_reference` -- the fingerprint of the analytical inverse of that same transform.
- `current` -- the fingerprint of your currently loaded object.

The current object must match **either** the transformed reference **or** its inverse directly --
the adapter never searches for, computes, or applies a rigid-body fit to make them match. If
neither matches, applicability is rejected; no analysis runs.

### 2. Comparison path (`membrane_vqc/opm_adapter.py`, `membrane_vqc/comparison_pymol.py`)

Used by `pdbtm_opm_comparison`. Two fingerprints are compared:

- `source_fingerprint` -- captured once, when a source (PDBTM or OPM) is confirmed applicable to
  the selected object.
- `current_fingerprint` -- recomputed at comparison time.

Both independently selected sources (PDBTM and OPM) must match the **same** immutable snapshot of
the selected object before a comparison can run. The `comparison_report.py` schema field is named
`coordinate_fingerprint` / `coordinate_fingerprint_algorithm`
(`mvqc_atom_identity_coordinates_sha256:v1:legacy_pdb_3dp`), and comparison export explicitly
validates that the selected-object and each applicable-source fingerprint agree before accepting a
report.

## When it is captured, and when it is rechecked

- **Captured**: the moment a source (a local PDBTM/OPM pair, a cache snapshot, or an orientation
  file) is confirmed applicable to your currently selected object.
- **Rechecked**: immediately before the corresponding action actually runs -- Run QC, Show Slab, or
  Compare. If your object's coordinates changed between capture and that action (for example, you
  moved, rotated, or reloaded the object in PyMOL), the recheck fails and the action is rejected
  with a clear error rather than silently analyzing stale-source-against-new-coordinates data.
- Batch execution performs the same check per job: `coordinate_preserved` in the job's manifest
  entry records whether the fingerprint matched before and after that job ran (`true`/`false`), or
  `null` if the job never reached that stage (see `docs/status_vocabulary.md`,
  `docs/outputs_and_manifests.md`).

## What operations are intentionally read-only

Every analysis mode in this project -- legacy global-z, planar orientation, offline/cached PDBTM,
and PDBTM-OPM comparison -- is read-only with respect to your object's atomic coordinates. The
plugin never fits, aligns, rotates, translates, or otherwise transforms the coordinates of any
object you load. Its own PyMOL-owned visual objects (boundary slabs, colored selections, comparison
overlays) are separate, plugin-owned names that can be removed with `mvqc_clear`; they do not alter
your structure's coordinates.

## Coordinates vs. PyMOL visual state

The fingerprint covers atomic coordinates only. It says nothing about, and does not detect changes
to, PyMOL's visual/display state -- camera position, representation (cartoon/sticks/surface),
color, visibility, or selection state. Changing how an object *looks* in PyMOL does not invalidate
a captured fingerprint; only a change to its atomic coordinates does.

## What this guarantee does and does not cover

**Covers:** proof that the coordinates an orientation source (or a comparison source) was
determined applicable against are the same coordinates being analyzed right now -- preventing a
stale source from being silently applied to a structure that has since moved.

**Does not cover:**

- Any claim that the structure itself, or its orientation, is biologically correct.
- Any claim about coordinates *before* the fingerprint was first captured -- if you moved the
  object and then re-established applicability, that new position is what gets fingerprinted next.
- Detection of edits to non-coordinate structure data (occupancy, B-factors, chain/residue
  metadata) -- the fingerprint is coordinate-only.
- Any guarantee across a PyMOL session restart -- fingerprints are in-memory/report-scoped, not
  persisted identity claims that survive reloading the same file fresh.

See also `docs/status_vocabulary.md#2-batch-job-status-jobsstatus-in-batch-resultjson` for how a
fingerprint mismatch surfaces in batch results, and `docs/known_limitations.md` for the broader set
of scientific-interpretation boundaries.
