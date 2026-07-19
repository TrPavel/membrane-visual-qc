# Stage 4 orientation adapter fixture plan

Status: accepted design; Stage 4A1 synthetic cases are merged and Stage 4A2 PyMOL integration
fixtures are in development. Expected results remain defined independently of implementation.

## Fixture policy

Raw official PDBTM JSON/PDB payloads are not committed while redistribution terms remain unclear.
Committed tests use small, hand-authored synthetic fixtures based on the documented format and mark
them explicitly as synthetic. Tests never fetch the network.

Official JSON/transformed-PDB pairs are downloaded locally only for the source-semantics preflight
and never placed in Git history. A metadata-only preflight record stores source URLs, retrieval
timestamps, SHA-256 values, format/resource/software versions, decimal coordinate and matrix
precision, and verification results. It contains no provider coordinate payload.

All JSON serialization comparisons use UTF-8 bytes and intentionally vary field order where the
format permits it. Expected warning codes are stable; human messages may add detail.

## Core parsing fixtures

| Fixture | Input condition | Independent expected result |
|---|---|---|
| Valid planar bundle | finite centre `(0,0,0)`, normal `(0,0,2)`, offsets `-12,+12`, JSON plus matching transformed PDB and exact current coordinate match | `imported`; normal `(0,0,1)`; offsets unchanged; separate raw hashes; direct-match evidence; source/current geometry retained |
| JSON without companion | valid official-format JSON only | `partial`; provenance retained; no current geometry, `PlanarMembrane`, or QC report |
| Inverted normal | normal `(0,0,-2)` | `unsupported` with `UNSUPPORTED_NORMAL_SEMANTICS`; reviewed PDBTM transformed normal requires positive Z |
| Reversed unlabeled boundaries | two recoverable planes supplied as `+12,-12` | ordered `-12,+12`; `BOUNDARIES_REORDERED`; raw values retained |
| Reversed labelled boundaries | biological side labels contradict numeric/matrix semantics | `rejected`; no `PlanarMembrane`; no guessed relabelling |
| Off-axis normal | large x/y component | `unsupported` with `UNSUPPORTED_NORMAL_SEMANTICS`; arbitrary direction is never replaced by +Z |
| Serialization-noise normal | near-zero x/y inside reviewed envelope and positive z | `imported`; physical direction +Z and `half_thickness = z` |
| Zero normal | `(0,0,0)` | `rejected` with `ZERO_NORMAL` |
| Missing thickness | no offsets, half-width, or boundary planes | `partial`; source identity/hash retained; no current membrane |
| Missing centre | orientation requires centre and source provides no reconstructible origin | `partial` or source-specific `rejected`; never substitute origin |
| Malformed numeric | string where number required, overflow, malformed exponent | `rejected` with field path |
| NaN / infinity | JSON constants or overflowing values | `rejected` before geometry construction |
| Unsupported source version | syntactically valid unknown record version | `unsupported`; no fallback to a similar version |
| Multiple candidate membranes | two or more provider candidates without explicit selector | `partial` with candidate summaries; never select first/best |
| Same data, different field order | semantically identical JSON order variants | equal normalized evidence except distinct raw SHA values; deterministic warnings |

## Structure-scope and coordinate fixtures

| Fixture | Input condition | Independent expected result |
|---|---|---|
| Chain mismatch | source `A,B`; current `A,C` | `rejected`/scope mismatch; lists both sets |
| Assembly mismatch | same chains, source assembly `1`, current assembly `2` | `rejected` with `ASSEMBLY_MISMATCH`; chain equality does not override |
| Coordinate-frame mismatch | source transform absent and current fingerprint differs | `rejected` with `COORDINATE_FRAME_MISMATCH` |
| Model mismatch | source model 1, current model 2 | `rejected` unless source explicitly supports both and user selected model 2 |
| Chain namespace mismatch | source `label_asym_id`, context only `auth_asym_id` with no map | `partial`/scope mismatch; no string-only match |
| Current matches transformed companion | direct atom identities/coordinates match transformed PDB | identity `source_to_current`; match count, RMSD, maximum residual and fingerprints serialized |
| Current matches inverse-transformed companion | direct coordinates match analytical inverse of provider transform | `source_to_current = inverse(provider_original_to_transformed)`; no fitted transform |
| Rotated structure | source geometry normal `(0,0,1)`, centre `(0,0,0)`; exact mapping `R=[[0,0,1],[0,1,0],[-1,0,0]], t=[10,-5,3]` | current centre `(10,-5,3)`, normal `(1,0,0)`, offsets unchanged; matrix serialized exactly |
| Non-rigid transform | scale, shear, reflection, or singular matrix | `rejected` in Stage 4A; determinant/orthogonality reason reported |
| Neither coordinate reference matches | metadata agrees but direct residuals fail for transformed and inverse-transformed references | `COORDINATE_FRAME_MISMATCH`; no membrane/QC report |
| Metadata-only apparent match | same PDB ID, chains and assembly but different coordinates | rejected as coordinate mismatch; metadata never substitutes for atom evidence |
| Too few/narrow atoms | fewer than 12 atoms, fewer than 3 residues, deterministic spatial-witness lower bound under 10 angstrom, or no point 2 angstrom off its witness line | rejected/insufficient coordinate evidence; no membrane; witness is not labelled as a maximum |
| Double-sweep counterexample | exact diameter exceeds deterministic witness separation | witness is serialized explicitly as a lower bound; no `maximum_pairwise_separation` claim |
| Precision-bound overflow | valid decimal places but large coordinates make identity/inverse theoretical bound exceed fixed runtime envelope | `unsupported / PRECISION_OUTSIDE_ENVELOPE` before coordinate-frame verdict |

The rotated fixture uses the same rigid transform already validated by the project:

```text
x' = z + 10
y' = y - 5
z' = -x + 3
```

## PDBTM target fixtures

Before production work, locally obtain official pairs for at least one alpha-helical entry and one
beta-barrel entry. At least one pair must have nontrivial rotation and translation. Across the
preflight, use multiple non-collinear atoms and prove:

1. documented original-to-transformed matrix direction by transforming at least three non-collinear
   atoms and comparing with the official transformed coordinates;
2. membrane normal/half-width semantics by comparing JSON/XML geometry with the transformed record;
3. PDB ID, resource/software version, chain namespace and assembly mapping;
4. inversion into current coordinates using an analytically computed fixture;
5. half-thickness semantics against the transformed companion;
6. explicit model and provider chain namespace matching;
7. direct matching against transformed and analytically inverse-transformed coordinates;
8. partial/missing membrane and non-planar/double/curved cases are rejected or deferred explicitly.

Expected residual tolerance for provider-rounded coordinates must be derived from documented
coordinate and matrix precision before implementation, not chosen after seeing implementation
output. The metadata-only preflight record documents the derivation and results without retaining
the raw official payloads.

## Deferred experimental OPM fixtures

- valid oriented PDB with half-thickness REMARK and two DUM planes;
- missing REMARK but consistent DUM planes: partial unless the adapter contract explicitly permits
  plane-derived thickness;
- REMARK/DUM disagreement: reject;
- nonparallel or nonplanar DUM sets: reject;
- same oriented coordinates loaded: identity mapping accepted;
- ordinary wwPDB coordinates loaded: coordinate-frame mismatch, no automatic alignment;
- curved/multiple PPM/OPM-style boundary pseudo-atoms: unsupported.

These fixtures belong to a separate follow-up and are not part of the first Stage 4A implementation
PR.

## Size and parser safety fixtures

- exactly 5 MiB and 5 MiB + 1 byte;
- nesting depth 32 and 33;
- 4,096-byte and 4,097-byte lines;
- duplicate identity/geometry keys;
- XML DTD, entity and XInclude attempts;
- invalid UTF-8 and embedded NUL;
- 250,000 and 250,001 records;
- excessive chain/candidate/string counts;
- non-finite occupancy and duplicate identical ATOM identity/altloc;
- caller metadata attempting to set `retrieval_verified=true`;
- ZIP, GZIP and polyglot input;
- malicious filename and symlink supplied by test harness.

## Stage 4B retrieval/cache fixtures

Use a local fake transport, never the public service:

- successful HTTPS response and atomic cache write;
- network unavailable with and without valid cached bytes;
- connect timeout, read timeout and total deadline;
- HTTP error and `Retry-After` presentation;
- redirect within allowlist; too many redirects; HTTP downgrade; foreign host; IP literal;
- absent/false `Content-Length` with streamed size overflow;
- compressed response within limits and compression bomb beyond ratio/decompressed limits;
- interrupted write leaves previous entry valid;
- stale cache remains selectable but visibly stale;
- corrupt manifest, wrong SHA, swapped provider/ID, and poisoned final URL are rejected;
- explicit refresh stores new content-addressed bytes without overwriting historical bytes.

## Stage 4C conflict fixtures

Comparison expected outputs use configured thresholds serialized with the result:

- identical physical planes with reversed normals/offsets: `CONSISTENT_WITHIN_TOLERANCE` when no
  directional topology is compared;
- axis angle just below/at/above 5 degrees;
- centre displacement just below/at/above 2 angstrom along each normal;
- thickness difference just below/at/above 2 angstrom;
- residue core overlap just below/at/above 95%;
- same geometry but different provenance/hash: geometrically consistent with provenance difference;
- chain or assembly mismatch: `ASSEMBLY_MISMATCH`, no geometric verdict;
- unmapped frames: `COORDINATE_FRAME_MISMATCH`;
- missing thickness/centre: `INSUFFICIENT_INFORMATION`;
- two mapped sources above one or more review thresholds: `GEOMETRIC_DIFFERENCE`, with metrics and
  disagreements but no correct/incorrect source label.

## Integration invariants

- imported slab and QC use the exact same resolved `PlanarMembrane`;
- failed Run QC clears plugin-owned report/review/slab state and resets source display;
- failed Show Slab clears stale slab objects;
- `mvqc_clear` preserves source molecular objects;
- legacy five structures and rotated 1UBQ retain released summaries;
- schemas 1.0/1.1/1.2 and existing CSV columns remain unchanged;
- Stage 4 adapter reports use only a future reviewed schema 1.3.
