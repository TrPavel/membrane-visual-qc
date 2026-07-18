# Report schemas

Released v0.1.0 reports use `schemas/mvqc-report-1.0.schema.json`; released v0.2.0 analysis uses
additive schema 1.1. Both schemas are immutable, and validation dispatches by the declared version.

v0.3.0 opt-in exposure or local-context analysis uses `schemas/mvqc-report-1.2.schema.json`.
Context-disabled calls continue to produce the v0.2-compatible schema 1.1 contract. Schema 1.2 is
the v0.3.0 release schema and becomes immutable when v0.3.0 is published; its scientific meaning
is frozen during release preparation.

Schema 1.2 adds top-level `context_analysis` metadata and an `exposure` object on every
review item. Continuous residue SASA, side-chain SASA, and RSA are primary evidence. The exposure
bin is a display heuristic using serialized thresholds 0.05 and 0.25. Tien et al. 2013 theoretical
maximum ASA values provide the RSA reference; unsupported residues retain absolute SASA with
`relative_sasa: null`, `classification: "unknown"`, and an explicit unavailable reference status.
Tien 2013 maxima were derived with DSSP; Stage 3A applies them as a declared cross-method
normalization reference to its Shrake–Rupley/Bondi calculation, not as a method-identical DSSP
calibration. Backend, radius model, probe radius, and reference scale are serialized. RSA is not
clipped and may exceed 1; exposure classes remain project review heuristics.

Accessible sample areas and fractions are split into core, interface, outside, and combined
membrane regions. This geometric partition cannot distinguish lipid-facing surfaces from
water-filled pores and must not be interpreted as lipid accessibility. Missing calculations use
explicit `null` values and statuses, never substituted zeroes. The rich JSON is canonical and the
existing CSV columns remain unchanged in Stage 3A.

The local-context portion gives each analyzed review item independent
`burial_state`, `contact_support`, and `context_state` fields, conservative contact records, and
counts for putative salt bridges, distance-only potential hydrogen bonds, waters, ions, and ligand
contacts. Top-level metadata serializes every cutoff, `standard_residue_roles_v1`, category atom
counts, warnings, elapsed time, and all five context-state counts. These fields never replace or
downgrade the original `WARNING`/`INSPECT` severity. JSON remains canonical and CSV columns remain
unchanged.

For a known partition with total SASA zero, core/interface/outside areas remain numeric `0.0` and
all derived fractions are `null`. For an unavailable partition, both areas and fractions are
`null`. Schema 1.2 analysis status is `completed`, `partial`, or `unavailable`; residue status is
`completed` or `unavailable`. Context-disabled execution emits schema 1.1 with no exposure block.
Backend-error and lifecycle-skipped report states are deferred to Stage 3B; unexpected programming
errors continue to raise.

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
