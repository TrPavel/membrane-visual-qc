# Report schemas

Released v0.1 reports use `schemas/mvqc-report-1.0.schema.json`. v0.2.0 analysis uses
additive schema 1.1; schema 1.0 remains immutable and validation dispatches by declared version.

Unreleased Stage 3A develops `schemas/mvqc-report-1.2.schema.json` as a draft for structured
exposure evidence. Released schemas 1.0 and 1.1 are immutable. Context-disabled Stage 3A calls
continue to produce the v0.2-compatible schema 1.1 contract; schema 1.2 is used only when exposure
analysis is explicitly requested.

Schema 1.1 records the direct planar orientation fields, optional orientation-file basename and
SHA-256, and residue depth evidence. For coordinate `r`, centre `c`, and unit normal `n`:

```text
signed_distance = dot(r - c, n)
```

Positive values point along `n`. Reports also include absolute centre distance, nearest-boundary
distance, outside distance, and normalised depth. Normalised depth is defined only inside a core
whose bounds bracket zero: 0 at either boundary and 1 at the centre, scaled separately on each
side for asymmetric bounds. It is `null` outside or when the centre is not bracketed. These are
geometric measurements, not proof of biological burial.

CA is used when available, otherwise the residue atom-coordinate mean. Cartesian `z` remains for
compatibility. Orientation-file provenance is separate from structure provenance. Structure
SHA-256 is recorded only for an explicit real `input_path`; commit and PyMOL provenance use clear
recorded/unavailable statuses.

The v0.1 aliases and CSV columns remain compatible:

```text
model,chain,resi,resn,classification,severity,reason,z
```
