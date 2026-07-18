# ADR-0005: Orientation source adapters and coordinate provenance

- Status: Accepted for Stage 4A implementation; PDBTM source-semantics preflight passed
- Date: 2026-07-18
- Depends on: ADR-0002 planar orientation convention

Architecture acceptance is not implementation completion. The required PDBTM source-semantics
preflight passed and Stage 4A1 is now implemented only on draft PR #9 for review. It is not merged,
released, or user-integrated; Stage 4A2 has not started.

## PDBTM source-semantics preflight result

**PASS (2026-07-18).** The documentation-only
[preflight](../pdbtm_semantics_preflight.md) used current official PDBTM JSON/transformed-PDB pairs
and corresponding RCSB coordinates for `1pcr` (`Tm_Alpha`) and `1a0s` (`Tm_Beta`). It confirmed:

- the documented row-major `p_transformed = R p_original + t` convention;
- direct companion matching and analytical inverse matching without fitting;
- explicit legacy-PDB-to-JSON chain mapping;
- transformed centre at the origin, +Z normal, and normal-vector magnitude as symmetric
  half-thickness;
- runtime identity limits of 0.002 angstrom and runtime inverse limits of 0.003 angstrom, applied
  to both RMSD and maximum residual;
- an independently precision-derived provider-forward validation limit for each exact payload
  pair, including 0.003 angstrom for the tested `1pcr` pair.

The machine-readable result is
[`pdbtm_semantics_preflight_results.json`](../pdbtm_semantics_preflight_results.json). Raw official
payloads were not committed. Stage 4A1 implementation remains a draft review candidate. This ADR
still does not authorize OPM, retrieval, comparison, automatic alignment, or runtime integration
outside a separately reviewed implementation PR.

## Context

ADR-0002 defines one `PlanarMembrane` in current PyMOL model coordinates. External databases and
predictors instead publish transformed coordinates, matrices, pseudo-atoms, residue regions,
simulated bilayers, or combinations of these. Their structure IDs, assemblies, chains, versions,
and coordinate frames differ. Parsing a record successfully does not establish that it applies to
the object currently loaded in PyMOL or that its orientation is biologically correct.

Network access, provider-specific parsing, coordinate mapping, scientific geometry, PyMOL state,
and report serialization need explicit boundaries.

## Decision

### Normalized model version 1

The source record and the resolved current-frame membrane remain separate immutable values. The
following is illustrative Python syntax; field names may be refined without weakening semantics.

```python
@dataclass(frozen=True)
class SourceIdentity:
    name: str
    record_id: str | None
    record_version: str | None
    software_version: str | None
    source_url: str | None
    retrieved_at: str | None
    citation: str | None
    raw_payloads: tuple[PayloadDigest, ...]

@dataclass(frozen=True)
class StructureScope:
    structure_id: str | None
    model_id: str | None
    biological_assembly: str | None
    chains: tuple[str, ...]
    provider_chain_labels: tuple[str, ...]
    legacy_chains: tuple[str, ...]
    chain_mapping: Mapping[str, tuple[str, ...]]
    selected_model: int
    chain_namespace: str
    coordinate_frame: str
    coordinate_fingerprint: str | None

@dataclass(frozen=True)
class PlanarGeometryEvidence:
    center: tuple[float, float, float]
    normal: tuple[float, float, float]
    lower_offset: float
    upper_offset: float
    interface_width: float | None
    frame: str

@dataclass(frozen=True)
class CoordinateMapping:
    source_frame: str
    current_frame: str
    source_to_current: tuple[tuple[float, float, float, float], ...]
    method: str
    residual_rmsd: float | None
    maximum_residual: float | None
    matched_atom_count: int | None
    fingerprint_algorithm: str | None
    fingerprint_version: str | None
    reference_fingerprint: str | None
    current_fingerprint: str | None
    warnings: tuple[str, ...]

@dataclass(frozen=True)
class OrientationEvidenceV1:
    model_version: str
    source: SourceIdentity
    source_scope: StructureScope
    source_geometry: PlanarGeometryEvidence
    current_scope: StructureScope
    mapping: CoordinateMapping
    current_geometry: PlanarGeometryEvidence
    geometric_confidence: str
    warnings: tuple[str, ...]
    raw_metadata: Mapping[str, JsonValue]

@dataclass(frozen=True)
class OrientationImportResult:
    evidence: OrientationEvidenceV1 | None
    status: Literal["imported", "partial", "rejected", "unsupported"]
    warnings: tuple[str, ...]
```

For PDBTM, `raw_payloads` contains separate named SHA-256 values for the official JSON and official
transformed-PDB companion. JSON provenance without its companion may be retained as `partial`, but
it cannot populate `current_geometry` or create a `PlanarMembrane`.

`source_geometry` is exactly what the provider supplies or what its documented representation
deterministically encodes. PDBTM does not provide an MVQC interface width, so its source geometry
uses `interface_width = None`; the resolved current geometry records the separately configured
MVQC analysis width. `mapping` records the exact transform applied by the adapter.
`current_geometry` is the only geometry converted to `PlanarMembrane`. Reports retain all three.

The homogeneous matrix convention is fixed: column coordinate `p_current = M * p_source`, with a
4x4 matrix whose final row is `(0, 0, 0, 1)`. If a provider supplies the inverse convention, the
adapter stores the provider matrix in metadata and stores its calculated inverse explicitly as
`source_to_current`. Rotation is checked for finiteness, orthonormality and determinant near +1;
non-rigid transforms are rejected for Stage 4A.

### Adapter contract

```python
@dataclass(frozen=True)
class OrientationPayload:
    role: str
    content: bytes
    media_type: str | None
    source_url: str | None

@dataclass(frozen=True)
class OrientationPayloadSet:
    primary: OrientationPayload
    companions: tuple[OrientationPayload, ...]

class OrientationAdapter(Protocol):
    source_name: str
    adapter_name: str
    adapter_version: str
    supported_media_types: tuple[str, ...]
    supported_format_profiles: tuple[str, ...]

    def can_parse(
        self, payloads: OrientationPayloadSet, metadata: Mapping[str, object]
    ) -> bool: ...

    def parse(
        self,
        payloads: OrientationPayloadSet,
        *,
        structure_context: StructureContext,
        metadata: Mapping[str, object],
    ) -> OrientationImportResult: ...
```

Adapters are pure Python and must not import PyMOL, Qt, HTTP clients, archive libraries, templates,
or subprocess tooling. `can_parse` is a bounded content check, not a full parse and never asserts
scientific applicability. Explicit user-selected source wins over auto-detection; disagreement is
a readable rejection.

Every parse:

- hashes every exact input payload before decoding;
- uses declared UTF-8/ASCII only, rejects undecodable bytes, duplicate security-sensitive keys,
  NaN and infinity;
- accepts only OpenAPI/API v1 payloads whose required JSON field structure and numeric precision
  profile are inside the reviewed adapter contract and precision envelope;
- serializes provider `resource_version` and `software_version` as provenance on every result;
- does not reject a record solely because its resource snapshot incremented, but does not claim
  compatibility with an untested future schema;
- derives decimal precision and precision bounds from each exact payload; changed field structure,
  changed matrix semantics, non-rigid transforms, or precision outside the reviewed envelope return
  `unsupported`, with no historical fixed threshold silently reused;
- uses angstroms internally and records any source-unit conversion;
- enforces source-specific normal semantics without replacing an arbitrary vector direction;
- produces ordered `lower_offset < upper_offset`; recoverable unlabeled reversal is reordered with
  `BOUNDARIES_REORDERED`, while ambiguous/labeled conflicts are rejected;
- distinguishes malformed, unsupported, partial and scope-mismatch results;
- never selects one of multiple membranes silently;
- verifies structure ID, model, assembly, chains and coordinate frame before resolving geometry;
- emits stable warning codes plus readable messages in deterministic order.

Missing centre, thickness, mapping, or scope can yield `partial` evidence for inspection, but never
a fabricated `PlanarMembrane`. Adapter failures do not fall back to manual geometry automatically.

### PDBTM Stage 4A runtime contract

A fully imported PDBTM orientation requires all three inputs:

1. official PDBTM JSON;
2. its matching official PDBTM transformed-PDB companion;
3. a current `StructureContext` with one model explicitly selected.

The JSON supplies provider metadata, membrane geometry and
`provider_original_to_transformed`. The companion supplies the atom-coordinate evidence needed to
establish applicability. PDB ID, assembly and chain metadata are necessary scope checks but are
never sufficient coordinate evidence.

The adapter constructs exactly two reference coordinate sets without fitting:

- the transformed companion coordinates as published;
- the coordinates obtained by analytically applying
  `inverse(provider_original_to_transformed)` to every companion atom.

It directly compares the current coordinates with both references using identical atom identities.
There are only three outcomes:

- current matches the transformed companion: `source_to_current = identity`;
- current matches the inverse-transformed companion:
  `source_to_current = inverse(provider_original_to_transformed)`;
- neither matches: `COORDINATE_FRAME_MISMATCH`, no `PlanarMembrane`, and no QC report.

Runtime Case A uses `runtime_identity_match_limit`: RMSD and maximum residual must each be no more
than 0.002 angstrom when current coordinates are directly compared with the transformed companion.
Runtime Case B uses `runtime_inverse_match_limit`: RMSD and maximum residual must each be no more
than 0.003 angstrom when current coordinates are compared with the analytically
inverse-transformed companion.

These runtime limits are distinct from `provider_forward_validation_limit`, which validates the
provider matrix by transforming original/deposited coordinates and comparing them with the
transformed companion. That limit is derived independently from each exact payload pair and may be
0.003 angstrom for `1pcr`; it is not the runtime Case-A identity limit. All provider resource and
software versions, derived precision, and limits are serialized.

If both runtime references appear to match within their respective limits, the result is ambiguous
and rejected rather than choosing one. No Kabsch fit, translation fit, atom-derived transform, or
other optimization is permitted.

### Coordinate and scope matching

Chain labels are matched through the exact provider `ent_cif_chain_map`, not by raw equality.
Evidence serializes provider JSON labels, transformed companion legacy chains, current legacy
chains, the exact map, and the selected model. Transformed and current legacy chain sets must be
identical; Stage 4A1 has no subset mode. Provider assembly, when supplied, and current assembly are
serialized separately. Assembly identity is exact, not inferred from chain equality, and current
assembly is never copied into source scope.

The model is explicitly selected before matching. Canonical atom identity is:

```text
(provider chain namespace, residue number, insertion code, residue name, atom name, resolved altloc)
```

Altloc resolution uses one documented, versioned policy on both sides. The matched intersection is
sorted by canonical atom identity. Matching requires at least 12 atoms across at least three
residues. Spatial sufficiency uses the deterministic
`lexicographic_double_sweep_lower_bound_v1` witness: its endpoint separation must be at least 10
angstrom and at least one matched point must be 2 angstrom from that witness line. The witness is
a conservative lower bound, not a claimed maximum pairwise distance. It may reject a set whose
true diameter is larger; it cannot fabricate evidence that the 10-angstrom threshold was met.

Coordinates are compared directly. RMSD and maximum per-atom Euclidean residual are calculated for
each candidate reference without fitting. The adapter derives decimal coordinate and matrix
precision from every exact payload before comparison and computes
`runtime_identity_theoretical_bound`, `provider_forward_theoretical_bound`, and
`runtime_inverse_theoretical_bound`. If either runtime theoretical bound exceeds its fixed reviewed
limit, the format is `unsupported / PRECISION_OUTSIDE_ENVELOPE` before coordinate-frame matching;
bounds cannot be chosen after examining implementation output.

The reviewed OpenAPI/API v1 field structure and numeric precision envelope define format
compatibility. PDBTM resource `1017` is the tested data snapshot and provider software `3.2.134` is
the tested software, not a promise that an untested future schema is compatible. A resource-version
increment alone is not grounds for rejection when the contract and precision profile remain inside
the reviewed envelope. Changed field structure, changed matrix semantics, a non-rigid transform, or
precision outside that envelope returns `unsupported`; no historical fixed threshold is silently
reused.

The evidence serializes the selected model, chain namespace, altloc policy, matched atom count,
RMSD, maximum residual, spatial-distribution measurements, selected reference, and both canonical
coordinate fingerprints. The fingerprint contract is
`mvqc_atom_identity_coordinates_sha256`, version `1`: canonical UTF-8 atom-identity records plus
coordinates quantized deterministically at the validated provider precision using round-half-even;
signed zero is canonicalized to positive zero. The unrounded residuals remain the matching
evidence.

Any later atom-derived alignment requires a new ADR, atom mapping provenance, residual thresholds,
and explicit user action.

### Boundary and normal semantics

For the reviewed PDBTM API-v1 planar representation, transformed physical normal direction is +Z.
The serialized x/y components may contain only noise inside the reviewed precision envelope, z
must be positive, and z itself is the symmetric half-thickness. Large x/y, negative z, zero z, or
an arbitrary non-zero direction are not normalized into apparent support; they return a stable
unsupported/rejected result. `lower` and `upper` retain ADR-0002 geometric meaning. Provider
topology terms remain separate from geometric lower/upper labels.

Offline Stage 4A1 bytes are caller-controlled. Their exact hashes and declared source metadata are
retained, but `retrieval_verified` is always false. Verified retrieval is reserved for a future
trusted Stage 4B transport path that cannot be constructed through the public offline API.

### Layering

1. retrieval/cache layer obtains bounded raw bytes and metadata;
2. adapter layer deterministically parses bytes plus `StructureContext`;
3. domain layer validates/resolves `OrientationEvidenceV1` and creates `PlanarMembrane`;
4. command layer owns PyMOL/report lifecycle;
5. GUI displays returned source/status only after command success.

No network import exists below layer 1. Offline payloads enter directly at layer 2.

### Report and schema

Successfully resolved Stage 4 adapter use requires schema 1.3. The orientation record adds
normalized source identity, raw SHA-256, adapter name/version, source/current scopes, source
geometry, exact coordinate mapping, current geometry, confidence, and warnings. Optional
`orientation_comparison` records thresholds, metrics, mismatch states and both evidence IDs.

Schema dispatch is fixed:

- manual/global-Z or local orientation JSON with context disabled: schema 1.1;
- existing Stage 3 exposure/context workflows: schema 1.2;
- successfully resolved Stage 4 adapter orientation, with context disabled or enabled: schema 1.3;
- schema 1.3 with context enabled contains both orientation provenance and Stage 3 exposure/context
  evidence.

Partial, rejected, unsupported or coordinate-mismatched imports produce no QC report and never
fall back silently to manual geometry. Schemas 1.0, 1.1 and 1.2 are immutable; CSV columns remain
unchanged. Schema 1.3 is not created in the research PR.

## Consequences

The model is more verbose, but makes silent coordinate transformation and provenance loss
structurally difficult. Some apparently usable provider files will be rejected until their
assembly/frame can be established. This is preferable to displaying a precise but unrelated slab.

The first implementation target is offline PDBTM JSON plus its transformed-PDB companion. OPM is a
separate experimental follow-up. Network retrieval and comparison are separate substages. Curved
and multiple membranes require a future geometry ADR rather than coercion into a plane.

## Alternatives rejected

- Treat provider coordinates as current coordinates: loses frame provenance.
- Auto-align provider and loaded structures: atom/assembly choices are hidden scientific decisions.
- Put HTTP in each adapter: makes parsing nondeterministic and offline tests fragile.
- Store only the resolved plane: prevents reproduction and source comparison.
- Rank sources automatically: implies a biological verdict not justified by geometry alone.
