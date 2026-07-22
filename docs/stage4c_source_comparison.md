# Stage 4C PDBTM–OPM orientation comparison

Status: **PASS — complete and merged**. v0.5.0 release packaging and exact release-artifact
acceptance are tracked separately from the completed Stage 4C implementation acceptance.

## Scientific boundary

Stage 4C is an explicit geometric review between two independently applicable orientation source records.
It never selects a preferred provider, changes the active QC source, constructs a consensus,
fits or transforms coordinates, ranks providers, or interprets disagreement as a biological
verdict. Both sources must be selected explicitly and must apply independently to one immutable
snapshot of the selected PyMOL object.

The comparison reports continuous geometry first and applies fixed reviewed bands only as visual
review aids:

- membrane-axis angle: 5 degrees;
- membrane-normal centre displacement: 2 Å;
- total-thickness difference: 2 Å.

These values are geometric review thresholds, not biological truth. Full anchor-to-anchor centre
displacement is retained as a raw metric, but arbitrary translation of a provider's centre within
the same infinite membrane plane does not change the closeness band. That band uses only the
centre displacement component along the sign-aligned reviewed membrane direction. Normal sign ambiguity is
handled with `acos(abs(dot(n1, n2)))`. When the second normal is sign-aligned, its lower and upper
offsets are swapped and negated before boundary differences are calculated. Reports retain total
centre displacement plus components along each normal and along/perpendicular to the sign-aligned
bisector. Sidedness is unavailable unless a provider supplies a separately reviewed directional
topology contract.

## OPM contract decision: offline-only

Stage 4C accepts only an explicit local OPM PDB file. OPM describes downloadable coordinate files
whose protein is spatially arranged relative to the membrane and whose hydrophobic-core boundary
planes are represented by `DUM` atoms. The inspected official `1pcr` file used `N DUM` atoms at
the negative boundary and `O DUM` atoms at the positive boundary. Stage 4C treats those labels as
surface identifiers only and does not infer a biologically privileged side.

Live OPM retrieval is deferred. The official download/API page advertises API 1.1.0 and a
`primary_structures/pdbid/{pdbid}` route, but `1pcr` is a secondary representation and is not
resolved by that route; its primary record is `2j8c`. The primary record's reported thickness also
differs from the selected secondary file's own DUM geometry. A live implementation would therefore
need a separate reviewed identity-resolution, endpoint, caching, timeout, and payload contract.
Offline comparison is not blocked by that instability.

Primary references:

- [OPM home and downloadable oriented structures](https://opm.phar.umich.edu/)
- [OPM methods and definitions](https://opm.phar.umich.edu/about)
- [OPM downloads and API description](https://opm.phar.umich.edu/download)

No official OPM payload is committed. Raw preflight evidence is retained only below ignored
`.local/stage4c-preflight-opm/`; artifact validators reject its exact observed size and SHA-256.

## Offline adapter

The pure-Python adapter has no Qt, PyMOL, cache, or network imports. It accepts exact bounded local
bytes plus an immutable `StructureContext`, validates a single legacy-PDB model and explicit
four-character identifier, derives two planar boundaries only from the DUM coordinates, and
requires the current object to match the OPM-oriented protein directly within the reviewed
identity tolerance. It does not search for or calculate a rigid transform. Malformed, incomplete,
curved, nonparallel, degenerate, ambiguous, mismatched-chain, mismatched-assembly, and mismatched-
coordinate inputs fail closed with stable codes. Reports contain only digests, sizes, typed
evidence, and safe provider identifiers—not paths or raw bytes.

## Report contract

Schemas 1.0–1.4 remain byte-identical and keep their single-source meanings. Stage 4C adds
schema 1.5 with `report_type = orientation_source_comparison`, one shared selected-object identity,
ordered PDBTM and OPM source records, per-source applicability/provenance, comparison method and
metrics, reviewed thresholds, warnings/non-comparability reasons, and explicit constants stating
that no consensus, ranking, preferred source, or biological verdict exists. Comparison export is
independent of `qc.LAST_REPORT`; existing QC reports are never replaced or modified.
Applicable sources and the selected-object record share the explicitly named
`mvqc_atom_identity_coordinates_sha256:v1:legacy_pdb_3dp` snapshot fingerprint contract.
The accepted Stage 4C schema 1.5 SHA-256 before v0.5.0 release finalization is
`1de049797e068fc6d60d7c0c73cfb64add9b24bc6b7c24e7c8cd1078b2ee47e3`.

The deterministic synthetic example is
`reports/source_comparison_synthetic_mvqc.json` (5,809 bytes, SHA-256
`22666578b124efa1f2dbbb57cbe4c17c17be4787355b54d7e538623ca6b98d18`). It uses only the
obviously synthetic `test` fixtures committed under `data/synthetic/`.

## GUI and lifecycle

Comparison is a dedicated grouped area rather than a fourth orientation mode. It summarizes the
explicit PDBTM source, accepts one explicit local OPM file, and exposes Compare, Cancel, Show both
boundaries, Export comparison report, and Clear comparison actions. Source changes invalidate the
comparison generation. Worker delivery is accepted only for the active request and unchanged
selected-object fingerprint. Local parsing and comparison run without PyMOL calls; snapshot and
render operations remain on the main thread. Comparison owns four distinct boundary objects, and
its clear action removes only those objects. Close invalidates/cancels work and requests thread
shutdown without `terminate()` or a blocking wait.
