# ADR-0002: Treat membrane orientation as a provenance-rich abstraction

- Status: Accepted
- Date: 2026-07-13

## Context

The MVP assumes an xy-parallel slab bounded by `zmin/zmax`. OPM/PPM, PDBTM/TmDet, imported files, and user/manual placement have different algorithms, scopes, geometries, transforms, and uncertainties. Ordinary RCSB coordinates do not establish membrane orientation.

## Decision

Introduce a PyMOL-independent `Orientation` domain model. The initial geometry is a general planar membrane represented by a finite non-zero normal, centre/origin, and positive half-thickness or two signed boundaries. It also records:

- source enum (`manual`, `already_aligned`, `OPM`, `PDBTM`, `TmDet`, `PPM`, `imported_external`, `unknown`);
- source record/URL, retrieval/import time, original file hash, adapter name/version;
- coordinate transform and units;
- supported geometry and membrane identity where available;
- uncertainty/confidence only when supplied or legitimately computed;
- warnings and missing data.

Legacy `zmin/zmax` maps exactly to normal `(0,0,1)` and the corresponding centre/thickness. Adapters parse immutable external outputs into this model; they do not mutate the structure silently. Multiple orientations are compared and disagreement is reported rather than resolved invisibly. Remote submission of user coordinates requires explicit approval.

## Alternatives considered

- Keep only `zmin/zmax`: rejected because it cannot express arbitrary planes or provenance.
- Store only a 4×4 transform: rejected because thickness, source, uncertainty, and interpretation would be lost.
- Choose one orientation provider as truth: rejected because providers use different methods and scopes.
- Implement a new predictor: rejected as out of scope and scientifically unjustified.

## Consequences

Depth becomes coordinate-frame independent for planar membranes and reports become reproducible. All membrane-aware analysis must carry orientation provenance. Curved/double membranes remain explicit unsupported geometries until a later model extension; they must not be silently flattened.

## Validation plan

Test normal validation/normalisation, sign convention, arbitrary rotations/translations, legacy z equivalence, serialization round trips, malformed imports, provenance completeness, OPM/TmDet fixtures, and orientation-disagreement reports.
