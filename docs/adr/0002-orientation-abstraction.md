# ADR-0002: Planar orientation and membrane-depth convention

- Status: Accepted for Stage 2
- Date: 2026-07-14
- Supersedes: the underspecified 2026-07-13 orientation abstraction in this ADR

## Context

v0.1 classifies representative residue coordinates against an xy-parallel slab bounded by
`zmin/zmax`. Stage 2 must make that calculation independent of the global z-axis without treating
an imported or manually supplied orientation as biological ground truth. OPM/PPM, PDBTM/TmDet,
imported files, and manual placement have different algorithms, coordinate frames, scope, and
provenance. Ordinary RCSB coordinates do not establish membrane orientation.

The initial scientific geometry is deliberately limited to one planar membrane. Curved and
multiple membranes need different domain models and are not approximated as planes here.

## Decision

### Coordinate convention

All geometry uses PyMOL model-space Cartesian coordinates in angstroms. Scientific calculations
must not depend on camera/view axes and must not rotate or translate the user's structure. PyMOL
coordinates are acquired consistently through `cmd.get_model`, which reflects the coordinates
used by the current analysis path.

A planar membrane is represented by a finite point `c` on the source-declared
membrane-centre/reference plane, a finite unit normal `n`, signed finite offsets `lower` and
`upper` with `lower < upper`, a finite non-negative interface width `w`, and explicit source plus
optional source version, confidence, warnings, and immutable metadata.

The constructor normalises a non-zero normal once. Norms less than or equal to `1e-12`, NaN, and
infinity are rejected. Mutable input metadata is recursively copied and frozen so a frozen model
cannot be mutated through a retained nested reference.

### Centre, normal, boundaries, and sign

The centre `c` is the orientation source's declared membrane-centre plane origin. It is the
signed-distance zero plane; translating `c` within that plane does not change classification.
For legacy inputs whose bounds do not bracket zero, it remains a reference plane required for
exact compatibility and is not misrepresented as the deepest point of the slab.

For coordinate `r`, signed distance is:

```text
d(r) = dot(r - c, n)
```

Positive values point in the direction of `n`; negative values point in the opposite direction.
These are geometric sides only. They acquire cytoplasmic/extracellular meaning only when an
orientation source explicitly supplies that topology.

The physical boundary planes are `d(r) = lower` and `d(r) = upper`. `lower` and `upper` name
ordered signed offsets, not biological leaflets. Core classification includes both boundaries.
The lower interface is immediately outside the lower plane, and the upper interface is
immediately outside the upper plane.

An equivalent reversal uses the same `c` and `w` with:

```text
n' = -n
lower' = -upper
upper' = -lower
```

This preserves the physical planes, regions, unsigned distances, and normalised depth while
reversing signed distance. Any source-specific side/topology metadata must also be updated rather
than silently copied.

### Classification and numerical tolerances

Classification preserves exact v0.1 boundary semantics: core is `lower <= d <= upper`; lower
interface is `lower - w <= d < lower`; upper interface is `upper < d <= upper + w`; everything
else is outside. Exact core and interface boundaries remain inclusive as before.

Normal validation uses `1e-12`; rigid-transform invariance tests compare distances and depth with
absolute tolerance `1e-7`. These are floating-point stability allowances, not scientific
uncertainty. Classification does not use a tolerance because doing so would change the legacy
result for a coordinate infinitesimally outside a boundary. Reported negative zero may be
canonicalised to zero.

### Depth measurements

Every representative residue records `signed_distance`, `absolute_center_distance`,
`nearest_boundary_distance`, `outside_distance`, `classification`, and `normalized_depth` when
meaningful:

```text
signed_distance = d
absolute_center_distance = abs(d)
nearest_boundary_distance = min(abs(d-lower), abs(d-upper))
outside_distance = max(lower-d, d-upper, 0)
```

Normalised depth is geometric and dimensionless. When `lower < 0 < upper` and the residue is in
the core, it is defined piecewise:

```text
(d - lower) / (0 - lower)   for lower <= d <= 0
(upper - d) / (upper - 0)   for 0 <= d <= upper
```

It is `0.0` at either boundary and `1.0` at the declared centre plane. The separate denominators
handle asymmetric membranes correctly. It is `null` outside the core. For a legacy-compatible
slab that does not strictly bracket zero, centre-relative normalisation is ambiguous and is also
`null`; the report carries a warning while classification and all distance values remain valid.

Depth is geometric evidence only. It is not proof of biological burial, insertion, stability, or
membrane assignment.

### Representative residue coordinate

Stage 2 retains the v0.1 policy: use CA when present, otherwise use the arithmetic mean of residue
atom coordinates. Geometry accepts a general coordinate, so later side-chain-centre or
functional-group policies can be added without changing plane mathematics.

### Legacy mapping

`mvqc_check selection=all, zmin=-15, zmax=15` remains unchanged publicly and maps to the single
planar implementation as:

```text
center = (0, 0, 0)
normal = (0, 0, 1)
lower_offset = zmin
upper_offset = zmax
source = manual_global_z
```

There is no second z-only classifier. `classify_z` and existing command helpers are compatibility
adapters over the planar model. Existing fixture classifications and the synthetic single charged
review item are regression invariants. `classify_z` continues to sort reversed bounds for its
historical pure-Python API, while public commands continue to reject reversed bounds.

### Orientation input and serialization

The stable extensibility boundary is a local JSON document with schema version `1.0` and
`geometry = planar`. Unknown fields are rejected in the versioned document, numeric values must be
finite, and serialization is deterministic (`sort_keys`, stable arrays, UTF-8, final newline).
There are no network calls.

The legacy command remains unchanged. Stage 2 exposes the general plane through a local JSON file
because PyMOL also uses commas to delimit command arguments, making compact vector syntax fragile.
If a future manual-plane command is added, it will use explicit scalar arguments. The GUI uses the
same non-Qt parser; advanced manual-plane fields are deferred.

### Report representation

Stage 2 introduces report schema `1.1` because residue records gain defined measurements and the
orientation object gains defined direct fields. The change is additive but its meaning must not be
silently assigned to schema `1.0`. The orientation record contains:

```json
{
  "geometry": "planar",
  "source": "manual_global_z",
  "source_version": null,
  "confidence": null,
  "center": [0.0, 0.0, 0.0],
  "normal": [0.0, 0.0, 1.0],
  "lower_offset": -15.0,
  "upper_offset": 15.0,
  "interface_width": 3.0,
  "warnings": []
}
```

The v0.1 `orientation.parameters`, input `zmin/zmax`, top-level aliases, review-item `z`, and CSV
columns remain compatibility aliases during schema 1.x. Schema 1.1 requires the newly defined
fields from its producer; consumers may ignore fields they do not use. Validation selects the
declared schema, distinguishing immutable released 1.0 artefacts from new 1.1 examples.

### Rendering

Rendering constructs two rectangles perpendicular to `n` using two stable in-plane unit vectors.
Choose the Cartesian axis least aligned with `n`, then compute
`u = normalize(cross(n, axis))` and `v = cross(n, u)`. This avoids near-parallel degeneracy.

The footprint is derived from selected atom coordinates projected onto `u` and `v`, padded by a
configurable margin and clamped to documented minimum and maximum spans. Each plane is two CGO
triangles using supported `BEGIN`, `TRIANGLES`, `COLOR`, `ALPHA`, `NORMAL`, `VERTEX`, and `END`
constants. Only `mvqc_*` objects are created. The view is centred/zoomed on the analysed molecular
selection, not on the CGO footprint.

## Sources

- PyMOL's current CGO constants and supported triangle primitives:
  <https://github.com/schrodinger/pymol-open-source/blob/master/modules/pymol/cgo.py>
- PyMOL API and view/zoom behaviour: <https://pymol.org/dokuwiki/doku.php?id=api> and
  <https://pymol.org/dokuwiki/doku.php?id=command%3Azoom>
- PyMOL coordinate and model-space notes: <https://pymolwiki.org/Get_Coordinates_I> and
  <https://pymolwiki.org/index.php/Model_Space_and_Camera_Space>
- Lomize et al. 2006 planar hydrophobic-slab model, DOI 10.1110/ps.062126106:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC2242528/>
- OPM/PPM database and positioning method, Lomize et al. 2012:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC3245162/>
- PPM 3.0 planar/curved geometry distinction, Lomize et al. 2022:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC8740824/>
- Duff et al. 2017, robust orthonormal basis construction:
  <https://graphics.pixar.com/library/OrthonormalB/paper.pdf>

## Consequences

Planar classification and depth become rigid-transform invariant and provenance-aware. The
slightly richer schema and domain model add migration work, but avoid conflating legacy z values,
arbitrary planes, provider topology, and biological interpretation. Curved/double membranes,
automatic external adapters, exposure, interactions, comparison, and scoring remain explicitly
deferred.

## Validation plan

Test validation/normalisation, metadata immutability, deterministic serialization, exact legacy
equivalence, arbitrary normals, diagonal normals, translation, joint rigid rotation, normal
reversal, asymmetric bounds, exact boundaries, interfaces, malformed imports, schema 1.0/1.1
selection, CGO basis and footprint, mocked lifecycle cleanup, and headless PyMOL rendering on an
existing structure plus a reproducibly rotated copy.
