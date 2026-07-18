# PDBTM source-semantics preflight

Status: **PASS**

Date: 2026-07-18

Scope: research and validation only; Stage 4A production implementation has not started.

## Decision

The accepted three-input PDBTM contract is viable for the tested current provider resource:

1. official PDBTM JSON;
2. its matching official transformed-PDB companion;
3. current coordinates from an explicitly selected model.

Both official entries independently reproduce the transformed companion with the documented
PDB/REMARK-350 convention and no coordinate fitting. Both also reproduce the ordinary deposited
coordinates by analytically inverting the provider transform. The preflight therefore passes.

This result unblocks a future Stage 4A implementation PR. It does not add an adapter, schema 1.3,
GUI action, command, report field, or runtime dependency. Package version remains `0.3.0`.

Machine-readable evidence is in
[`pdbtm_semantics_preflight_results.json`](pdbtm_semantics_preflight_results.json). The analysis was
produced by the offline research helper
[`pdbtm_semantics_preflight.py`](../scripts/research/pdbtm_semantics_preflight.py).

## Source-backed semantics

The current [PDBTM user manual](https://pdbtm.unitmp.org/documents) says that original molecular
coordinates are transformed so the membrane normal coincides with Z. It defines the JSON/XML
matrix in the form used by PDB matrix records: three rotation columns and a fourth translation
column. The [original PDBTM format paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC539956/)
additionally defines the length of the stored normal vector as the membrane half-width and states
that Side1/Side2 are used because biological inside/outside cannot be inferred from coordinates.

The current [PDBTM usage guide](https://pdbtm.unitmp.org/usage) distinguishes the transformed PDB
download from the original RCSB PDB link. The current
[OpenAPI description](https://pdbtm.unitmp.org/api/documentation/pdbtm) is version 1.0.0 and exposes
the entry download endpoint. Neither IDs nor chain/assembly metadata were treated as coordinate
evidence.

No explicit current payload-redistribution licence was found in the reviewed PDBTM manual, usage
guide, or OpenAPI description. General availability for download is not treated as redistribution
permission.

## Official entries

Entry selection used current PDBTM JSON metadata, not remembered classifications.

| Entry | Current PDBTM classification | Structure characteristics | Reason selected |
|---|---|---|---|
| `1pcr` | `Tm_Alpha`; chains A/B each report five alpha segments and C reports one | Three-chain photosynthetic reaction centre; large rotation and translation | Alpha-helical pair with nontrivial transform and meaningful chain mapping |
| `1a0s` | `Tm_Beta`; chains A/B/C each report 18 beta segments | Three-chain sucrose-specific porin; nonzero rotation and translation | Beta-barrel pair selected from current provider metadata |

Both records report PDBTM resource version `1017` and software version `3.2.134`.

### Local-only payload policy

Payloads were stored under `.local/pdbtm_preflight/<pdb_id>/`; `.local/` is Git-ignored. No
official JSON, transformed PDB, RCSB coordinates, assembly file, or substantial coordinate excerpt
is committed. Only URLs, timestamps, response metadata, sizes, hashes, versions, and derived scalar
results are retained publicly.

| Entry/role | Official URL | Retrieved UTC | Bytes | SHA-256 |
|---|---|---:|---:|---|
| 1pcr JSON | `https://pdbtm.unitmp.org/api/v1/entry/1pcr.json` | 2026-07-18 17:09:47 | 283,537 | `38b2f724c4271a00bf2b83aa16015783610178f18d8954a88cb932b9152f36e0` |
| 1pcr transformed PDB | `https://pdbtm.unitmp.org/api/v1/entry/1pcr.trpdb` | 2026-07-18 17:11:50 | 628,434 | `7e52525ff397e4bfa5900e602f39753628e3b1408d513a3d0d76928c0fd10698` |
| 1pcr deposited PDB | `https://files.rcsb.org/download/1PCR.pdb` | 2026-07-18 17:11:51 | 710,208 | `2e7ed54691e1f036e9d73fa20e4ee068a8adf87969d40fdf78e6f43a6dedc0b0` |
| 1pcr assembly 1 | `https://files.rcsb.org/download/1PCR.pdb1.gz` | 2026-07-18 17:10:53 | 151,425 | `8ae14328bfe26e3154d4c019c0133b216a98230f6070fac6d4e5de7cd7318211` |
| 1a0s JSON | `https://pdbtm.unitmp.org/api/v1/entry/1a0s.json` | 2026-07-18 17:11:52 | 425,370 | `22b3985dc13b14520b5507b3ec022211d4c281bdf30f2cdef057073305294f62` |
| 1a0s transformed PDB | `https://pdbtm.unitmp.org/api/v1/entry/1a0s.trpdb` | 2026-07-18 17:13:59 | 823,920 | `f228413887e409312fba5ce76108836856fef62815b1bd8e4ffd97beb01f0b54` |
| 1a0s deposited PDB | `https://files.rcsb.org/download/1A0S.pdb` | 2026-07-18 17:11:32 | 857,871 | `5561e34be4c9846cd3aa6355f829add10208b3f62888800bbc200ee021901d28` |
| 1a0s assembly 1 | `https://files.rcsb.org/download/1A0S.pdb1.gz` | 2026-07-18 17:11:33 | 200,349 | `8d16fe0f40ec1bff7e8160e616baad38ff0b6bd480c7ecf08049ac8f8cf93c13` |

All eight downloads returned HTTP 200. PDBTM responses declared
`text/plain; charset=UTF-8`; deposited RCSB files declared `text/plain`; assemblies declared
`application/gzip`. RCSB deposited records reported latest revisions `14-FEB-24` for 1pcr and
`07-FEB-24` for 1a0s. Generated assembly files did not report their own internal version.

## Matrix direction and storage

The JSON field is:

```text
additional_entry_annotations.membrane.transformation_matrix
```

It is a 3×4 affine matrix stored as `rowx`, `rowy`, and `rowz`. Each row contains `x`, `y`, `z`,
and `t`. The accepted operation is left multiplication of a coordinate column vector:

```text
p_transformed = R p_original + t
```

Rotation is dimensionless. Coordinates and translation are in angstroms. Translation is included
in the fourth column; it is not applied before rotation.

The following alternatives were explicitly evaluated and rejected by direct residuals:

- transposed rotation/row-vector interpretation;
- applying translation before rotation;
- applying the analytical inverse in the forward direction;
- treating original and transformed coordinates as identical.

No convention was selected by searching for the smallest error. The documented REMARK-350
convention was selected first and then tested.

| Entry | det(R) | Orthonormality max error | Translation (Å) | Forward/inverse composition max error |
|---|---:|---:|---|---:|
| 1pcr | 1.0000001325 | 1.37×10⁻⁷ | `[-40.19375610, -26.91108322, -80.97983551]` | 1.63×10⁻¹⁴ |
| 1a0s | 1.0000000113 | 5.85×10⁻⁸ | `[36.43536377, 0.22734931, 14.42551613]` | 1.78×10⁻¹⁵ |

### Direct no-fit evidence

| Entry | ATOM matches | Residues | Forward RMSD (Å) | Forward max (Å) | Inverse RMSD (Å) | Inverse max (Å) |
|---|---:|---:|---:|---:|---:|---:|
| 1pcr | 6,469 | 823 | 0.000501969 | 0.000834950 | 0.000501969 | 0.000834950 |
| 1a0s | 9,606 | 1,239 | 0.000501151 | 0.000846301 | 0.000501151 | 0.000846301 |

There were no source-only or transformed-only canonical ATOM identities in either pair. A
supplemental comparison including HETATM records also produced complete intersections: 7,311 for
1pcr and 9,939 for 1a0s, with the same sub-millångström residual scale. HETATM is nevertheless
excluded from the proposed applicability contract so protein coordinate evidence remains the
stable target.

Incorrect-convention RMSDs were decisively separated from rounding noise:

| Entry | Identity wrong frame | Transposed rotation | Translation-before-rotation | Inverse in wrong direction |
|---|---:|---:|---:|---:|
| 1pcr | 93.50 Å | 134.53 Å | 78.31 Å | 170.17 Å |
| 1a0s | 39.27 Å | 3.34 Å | 1.30 Å | 78.53 Å |

No Kabsch fit, translation fit, atom-derived transform, optimization, PyMOL operation, or external
binary was used.

## Coordinate set, assembly, and chains

For both selected entries, the transformation applies directly to the ordinary deposited
legacy-PDB coordinates. RCSB assembly 1 has exactly the same selected ATOM identities and
coordinates as the deposited file for these entries (identity RMSD and maximum residual are both
zero). Thus Case B is reproducible for both deposited coordinates and assembly 1 here; this is an
observed property of these two entries, not permission to infer assembly applicability from an ID.

The JSON chain labels use a different namespace from the legacy-PDB coordinate files:

| Entry | JSON labels | Legacy-PDB chains | Provider `ent_cif_chain_map` |
|---|---|---|---|
| 1pcr | A, B, C | H, L, M | H→C, L→A, M→B |
| 1a0s | A, B, C | P, Q, R | P→A, Q→B, R→C |

The runtime contract must therefore serialize the namespace and use the provider mapping. String
equality between JSON chain labels and current PyMOL chains is invalid.

Model 1 was selected explicitly. Canonical identity was:

```text
(legacy PDB chain ID, residue number, insertion code, residue name, atom name, resolved altloc)
```

Altloc resolution prefers blank, otherwise highest occupancy, then lexical altloc. Neither pair
required an altloc collapse. Identities were sorted deterministically. ATOM records were used for
applicability; HETATM treatment is recorded separately above.

## Spatial applicability

| Entry | Maximum pairwise separation | Maximum distance from farthest-pair line |
|---|---:|---:|
| 1pcr | 92.62 Å | 48.13 Å |
| 1a0s | 92.38 Å | 47.54 Å |

Both entries pass all proposed minimum checks: at least 12 atoms, at least three residues, at least
10 Å maximum pairwise separation, and at least one point 2 Å from the farthest-pair line. These
checks were not weakened after observing the records.

## Membrane centre, normal, and half-thickness

The transformed membrane centre is the coordinate origin and its normal direction is +Z. The JSON
`additional_entry_annotations.membrane.normal` value is a vector whose magnitude is the membrane
half-width, consistent with the primary format paper.

| Entry | Stored normal vector | Magnitude/half-thickness | Symmetric boundaries |
|---|---|---:|---|
| 1pcr | `[0, 0, 12.25]` | 12.25 Å | −12.25 Å, +12.25 Å |
| 1a0s | `[2e-8, -3e-8, 9.75]` | 9.75 Å | −9.75 Å, +9.75 Å |

The near-zero x/y values in 1a0s are serialization noise, not a second normal convention. Both the
alpha-helical and beta-barrel records use the same symmetric planar representation. Each JSON has
one `membrane` object; neither is a curved, double, or multiple-membrane record.

The value is PDBTM/TMDET's membrane half-width. It is not relabelled as a universal lipid-interface
or hydrophobic-core definition. Side1 and Side2 remain provider side labels; they do not establish
biological inside/outside.

## Precision-derived tolerances

Observed precision was determined before any Stage 4A adapter exists:

| Entry | Original PDB | Transformed PDB | Rotation | Translation |
|---|---:|---:|---:|---:|
| 1pcr | 3 decimals | 3 decimals | 8 decimals | 7, 8, 8 decimals |
| 1a0s | 3 decimals | 3 decimals | 8 decimals (zero is serialized as an integer) | 8, 8, 8 decimals |

Integer-form matrix values do not establish infinite precision. Their rounding contribution is
conservatively bounded at the eight-decimal precision observed in sibling rotation fields.

For each output axis, the forward rounding bound is:

```text
εy + εt,i + Σj (|Rij| εx + |xj| εR,ij + εx εR,ij)
```

The analytical inverse uses the conservative infinity-norm bound:

```text
εx + ||R⁻¹||∞ (||εR||∞ ||x||∞ + εt + εy)
```

The identity comparison bound is `sqrt(3) × (εcurrent + εcompanion)`. Coordinate rounding is
0.0005 Å for each three-decimal coordinate component.

| Entry | Forward theoretical max | Inverse theoretical max | Conservative ceiling |
|---|---:|---:|---:|
| 1pcr | 0.002095 Å | 0.002211 Å | 0.003 Å |
| 1a0s | 0.001765 Å | 0.001782 Å | 0.002 Å |

The proposed resource-1017 policy is:

- identity match: RMSD ≤ 0.002 Å and maximum residual ≤ 0.002 Å;
- inverse match: RMSD ≤ 0.003 Å and maximum residual ≤ 0.003 Å.

The common inverse limit uses the more conservative of the two independently derived pair bounds.
It was not chosen from observed residuals. A provider version or numeric-format change requires a
new precision derivation rather than silently retaining these limits.

## Runtime-contract cases

### Case A — transformed current coordinates

Direct comparison against the official transformed companion is valid. If identity metrics pass
and inverse-reference metrics do not, `source_to_current = identity`.

### Case B — original/current coordinates

Applying `inverse(provider_original_to_transformed)` analytically to the companion reproduces the
deposited coordinates for both entries. If inverse metrics pass and identity metrics do not,
`source_to_current = inverse(provider_original_to_transformed)`.

For these entries, assembly 1 is coordinate-identical to the deposited file. Future entries still
require direct atom evidence; assembly metadata cannot substitute for it.

### Case C — neither reference matches

The result is `COORDINATE_FRAME_MISMATCH`. No membrane or QC report may be created.

### Case D — both references match

The result is ambiguous and rejected. The two selected nontrivial transforms did not enter this
state, but near-identity provider transforms can. The implementation must not select a branch by
smallest residual.

## Pass criteria

- Same documented matrix convention on alpha and beta records: **PASS**
- Reproducible transformed-companion matching: **PASS**
- Assembly and chain semantics resolved for selected pairs: **PASS**
- Membrane centre and +Z normal interpretation: **PASS**
- Half-thickness interpretation: **PASS**
- Precision-derived residual policy: **PASS**
- Identity/inverse runtime paths: **PASS**
- Atom-count and spatial-distribution checks: **PASS**
- No fit, hidden alignment, runtime code, or schema change: **PASS**

## Boundary after preflight

This PASS is specific to the documented PDBTM JSON plus transformed-PDB companion contract and the
tested provider resource/format. It does not authorize OPM, network retrieval, source comparison,
automatic alignment, curved membranes, or assumptions based only on PDB IDs/chains/assemblies.

PDBTM source-semantics preflight passed. Stage 4A production implementation is unblocked but has
not started.
