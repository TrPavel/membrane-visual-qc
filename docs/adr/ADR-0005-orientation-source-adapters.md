# ADR-0005: Orientation source adapters and coordinate provenance

- Status: Accepted for Stage 4A architecture; PDBTM source-semantics preflight required before production implementation
- Date: 2026-07-18
- Depends on: ADR-0002 planar orientation convention

Architecture acceptance does not mean that Stage 4 functionality is implemented. Production
implementation cannot start until the PDBTM source-semantics preflight described here is reviewed.

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
deterministically encodes. `mapping` records the exact transform applied by the adapter.
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
    supported_source_versions: tuple[str, ...]

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
- accepts only documented source versions; unknown versions return `unsupported`;
- uses angstroms internally and records any source-unit conversion;
- normalizes a finite non-zero normal without losing the supplied vector in raw metadata;
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

If both appear to match within the preflight-derived tolerance, the result is ambiguous and
rejected rather than choosing one. No Kabsch fit, translation fit, atom-derived transform, or other
optimization is permitted.

### Coordinate and scope matching

Chain labels are matched in the provider-declared namespace (`auth_asym_id`, `label_asym_id`, or
legacy PDB chain) and the namespace is serialized. Assembly identity is exact, not inferred from
chain equality. A provider record for a different assembly or chain set returns a scope mismatch.

The model is explicitly selected before matching. Canonical atom identity is:

```text
(provider chain namespace, residue number, insertion code, residue name, atom name, resolved altloc)
```

Altloc resolution uses one documented, versioned policy on both sides. The matched intersection is
sorted by canonical atom identity. Matching requires at least 12 atoms across at least three
residues, a maximum pairwise separation of at least 10 angstrom, and at least one matched point at
least 2 angstrom from the line through the farthest pair. These are minimum applicability checks,
not biological-quality thresholds.

Coordinates are compared directly. RMSD and maximum per-atom Euclidean residual are calculated for
each candidate reference without fitting. The acceptance tolerance must be derived before
implementation from the decimal coordinate precision and matrix precision observed in at least two
official provider pairs; it cannot be chosen after examining implementation output.

The evidence serializes the selected model, chain namespace, altloc policy, matched atom count,
RMSD, maximum residual, spatial-distribution measurements, selected reference, and both canonical
coordinate fingerprints. The fingerprint contract is
`mvqc_atom_identity_coordinates_sha256`, version `1`: canonical UTF-8 atom-identity records plus
coordinates rounded only to the provider precision established by preflight. The unrounded
residuals remain the matching evidence.

Any later atom-derived alignment requires a new ADR, atom mapping provenance, residual thresholds,
and explicit user action.

### Boundary and normal semantics

`lower` and `upper` retain ADR-0002 geometric meaning. Normal reversal is physically equivalent
only with offset reversal and any source side labels updated. Adapters do not canonicalize the
normal direction merely for display. Provider topology terms are evidence and remain separate from
geometric lower/upper labels.

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
