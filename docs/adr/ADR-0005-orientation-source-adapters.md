# ADR-0005: Orientation source adapters and coordinate provenance
geometry ADR rather than coercion into a plane.
geometry ADR rather than coercion into a plane.
- Status: Proposed for Stage 4 design review
- Date: 2026-07-18
- Depends on: ADR-0002 planar orientation convention

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
    raw_record_sha256: str

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
    matched_atom_count: int | None
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
class OrientationAdapter(Protocol):
    source_name: str
    adapter_name: str
    adapter_version: str
    supported_media_types: tuple[str, ...]
    supported_source_versions: tuple[str, ...]

    def can_parse(self, payload: bytes, metadata: Mapping[str, object]) -> bool: ...

    def parse(
        self,
        payload: bytes,
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

- hashes the exact input bytes before decoding;
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

### Coordinate and scope matching

Chain labels are matched in the provider-declared namespace (`auth_asym_id`, `label_asym_id`, or
legacy PDB chain) and the namespace is serialized. Assembly identity is exact, not inferred from
chain equality. A provider record for a different assembly or chain set returns a scope mismatch.

No Stage 4A adapter performs automatic best-fit alignment. A documented provider transform may be
inverted/composed deterministically. An already oriented provider coordinate file may use identity
mapping only after a coordinate fingerprint check. Any later atom-derived alignment requires a new
ADR, atom mapping provenance, residual thresholds, and explicit user action.

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

Stage 4 adapter use requires schema 1.3. The orientation record adds normalized source identity,
raw SHA-256, adapter name/version, source/current scopes, source geometry, exact coordinate mapping,
current geometry, confidence, and warnings. Optional `orientation_comparison` records thresholds,
metrics, mismatch states and both evidence IDs.

Schemas 1.0, 1.1 and 1.2 are immutable. Manual/local-file workflows retain current schema dispatch;
CSV columns remain unchanged.

## Consequences

The model is more verbose, but makes silent coordinate transformation and provenance loss
structurally difficult. Some apparently usable provider files will be rejected until their
assembly/frame can be established. This is preferable to displaying a precise but unrelated slab.

PDBTM JSON becomes the first implementation target; OPM oriented PDB is experimental. Network
retrieval and comparison are separate substages. Curved and multiple membranes require a future
geometry ADR rather than coercion into a plane.

## Alternatives rejected

- Treat provider coordinates as current coordinates: loses frame provenance.
- Auto-align provider and loaded structures: atom/assembly choices are hidden scientific decisions.
- Put HTTP in each adapter: makes parsing nondeterministic and offline tests fragile.
- Store only the resolved plane: prevents reproduction and source comparison.
- Rank sources automatically: implies a biological verdict not justified by geometry alone.
