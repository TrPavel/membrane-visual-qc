# Stage 4 scope proposal

Status: proposed; requires explicit review acceptance before Stage 4A coding.

## Goal and subdivision

Stage 4 is **orientation interoperability, provenance, retrieval, and source comparison**:

- **Stage 4A:** offline import adapters and normalized provenance;
- **Stage 4B:** optional retrieval, bounded local cache, timeout handling, and reproducibility;
- **Stage 4C:** comparison of multiple orientation sources with explicit conflict evidence.

The substages need not share a release. Imported or predicted orientation is never labelled
biologically correct merely because its source is external.

## Smallest useful Stage 4A

### Supported target

Implement one fully tested **PDBTM JSON** adapter for user-downloaded official entry records. This
recommendation is conditional on a pre-code fixture check that establishes the documented matrix
direction and half-thickness convention against paired official transformed coordinates. If those
semantics cannot be demonstrated independently, Stage 4A pauses rather than guessing.

The workflow is:

1. user selects a local official record and source (or requests deterministic auto-detection);
2. a pure-Python adapter hashes and parses the bytes under fixed limits;
3. the adapter verifies PDB ID, biological assembly/chain scope, source version and coordinate
   mapping against a `StructureContext`;
4. it emits source-frame evidence, the exact mapping, current-frame planar geometry, warnings, and
   confidence—not a biological verdict;
5. the existing command layer converts the resolved current-frame geometry to `PlanarMembrane`;
6. reports serialize provenance and the slab renderer uses exactly that membrane.

### Experimental target

An **OPM oriented-PDB** adapter may be included as experimental if it accepts only a current object
whose coordinates correspond to that OPM-oriented file, or a separately supplied exact mapping.
It reads the half-thickness REMARK and validates both DUM planes. It must reject an ordinary wwPDB
object instead of silently aligning it.

### Explicit non-goals

- no network dependency or automatic download;
- no provider ranking or “best orientation”;
- no HTML scraping or job submission;
- no automatic structural alignment;
- no curved, multiple, intersecting, or double membranes;
- no execution of PPM/TmDet or other external binaries;
- no changes to existing manual orientation behaviour;
- no changes to existing CSV columns.

PPM 3.0, direct TmDet output, MemProtMD, TmAlphaFold, and ANVIL are deferred as explained in the
[source matrix](stage4_source_matrix.md).

## Stage 4A acceptance gate

Stage 4A is not complete until:

- the normalized model and ADR are accepted;
- source semantics are backed by provider-derived fixtures with recorded hashes and allowed
  redistribution, or by small hand-authored fixtures independently derived from published specs;
- adapters have no PyMOL, Qt, HTTP, archive, template, or subprocess imports;
- invalid input clears only plugin-owned state and gives a readable error without traceback;
- source, adapter, raw hash, assembly, chains, coordinate frames, and exact transform are reported;
- the rendered planes match the resolved `PlanarMembrane` in headless and graphical PyMOL;
- all released schemas and historical evidence remain byte-unchanged;
- manual/global-Z and local orientation JSON workflows retain their current schema behaviour.

## Stage 4B design boundary

Retrieval should live **inside the plugin as a separate infrastructure layer**, invoked only by an
explicit command/GUI action. This offers a reproducible cache and usable offline fallback without
placing HTTP in scientific parsing modules. An external helper would fragment provenance; parsing
network data inside adapters would couple deterministic science to service availability.

Network access is disabled by default. The first allowlist should contain only the exact official
PDBTM API host and path template. Expansion requires a new reviewed source contract. Requirements:

- HTTPS only, no arbitrary URLs or credentials;
- validated provider name and identifier before URL construction;
- 5 s connection, 15 s read, 30 s total deadline;
- at most three same-allowlist redirects;
- 5 MiB compressed/wire and 20 MiB decompressed limits;
- cache raw bytes, SHA-256, retrieval time, final URL, selected headers, and source identity;
- write cache entries atomically, verify hashes on every reuse, and never silently refresh;
- explicit “use cached”, “refresh”, and “offline” choices;
- network failure cannot break local/manual orientation workflows.

No provider has a documented unlimited rate. A conservative client must serialize requests, avoid
background polling, and honour `Retry-After` when present.

## Stage 4C comparison semantics

Comparison operates only after both records are mapped into the same current coordinate frame and
structure scope. Proposed evidence:

- physical normal-axis angle: `acos(abs(dot(n1, n2)))`;
- directional normal angle separately when both sources declare side topology;
- centre displacement along each normal;
- total slab-thickness and asymmetric-offset differences;
- core/interface classification overlap and per-residue disagreement;
- assembly, chain-set, structure-ID, frame, source, version and raw-hash differences.

Proposed configurable review defaults—not universal truths—are 5 degrees normal-axis difference,
2 angstrom centre displacement, 2 angstrom thickness difference, and 95% core-classification
agreement. Results use only:

```text
CONSISTENT_WITHIN_TOLERANCE
GEOMETRIC_DIFFERENCE
ASSEMBLY_MISMATCH
COORDINATE_FRAME_MISMATCH
INSUFFICIENT_INFORMATION
```

Assembly/frame mismatches preclude a geometric verdict. No state says correct, incorrect, valid,
or biologically wrong.

## Schema strategy

Stage 4 import requires **report schema 1.3** because orientation provenance, adapter identity,
coordinate mapping and optional comparison have new defined semantics. Released 1.0, 1.1 and 1.2
remain immutable.

- legacy/manual orientation with context disabled remains schema 1.1;
- v0.3 context analysis remains schema 1.2;
- using a Stage 4 adapter produces schema 1.3 whether context is enabled or not;
- comparison is optional in 1.3 and absent when not requested;
- existing CSV columns remain unchanged; rich provenance remains JSON-only.

Schema 1.3 is not created on this research branch.

## Estimate

After design acceptance, the minimal PDBTM-only Stage 4A is estimated at **18–25 engineer-days**:
4–5 for source-semantic fixtures/model, 4–6 for adapter and mapping, 3–4 for report/schema work,
3–4 for command/GUI/render lifecycle, and 4–6 for unit, headless, graphical, security and release
validation. The experimental OPM adapter adds approximately 5–8 engineer-days. Review latency and
provider clarification are not included.

## Unresolved decisions requiring acceptance

1. Confirm PDBTM half-thickness and matrix direction with paired official fixtures.
2. Decide whether a redistributable minimal provider fixture is permitted; otherwise use derived
   synthetic fixtures plus runtime user files.
3. Define the exact coordinate-identity test and acceptable numeric residual for source/current
   mapping.
4. Decide whether experimental OPM support belongs in the first Stage 4A PR or a follow-up.
5. Confirm schema-1.3 opt-in dispatch when Stage 4 orientation and Stage 3 context are both enabled.
6. Ask PDBTM maintainers for explicit API rate-limit and redistribution guidance before Stage 4B.
