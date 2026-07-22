# Stage 4 scope and implementation boundary

Status: **COMPLETE**. Stage 4A, Stage 4B1–4B4, and Stage 4C are merged and accepted. The detailed
sections below preserve the original staged design and acceptance criteria as historical context;
later implementation documents and v0.5.0 release notes describe the completed behavior.

## Goal and subdivision

Stage 4 is **orientation interoperability, provenance, retrieval, and source comparison**:

- **Stage 4A:** offline import adapters and normalized provenance;
- **Stage 4B:** optional retrieval, bounded local cache, timeout handling, and reproducibility;
- **Stage 4C:** comparison of multiple orientation sources with explicit conflict evidence.

The substages need not share a release. Imported or predicted orientation is never labelled
biologically correct merely because its source is external.

## Smallest useful Stage 4A

### Supported target

Implement one fully tested **offline PDBTM adapter**. A successful import requires the
user-downloaded official JSON, its matching official transformed-PDB companion, and the current
`StructureContext`. JSON alone produces at most `partial` provenance evidence and cannot create a
`PlanarMembrane`. This recommendation is conditional on a pre-code fixture check that establishes
the documented matrix direction, half-thickness convention and numeric coordinate tolerance
against paired official data. If those semantics cannot be demonstrated independently, Stage 4A
pauses rather than guessing.

The workflow is:

1. user selects a local official PDBTM JSON and its transformed-PDB companion;
2. a pure-Python adapter hashes and parses both payloads under fixed limits;
3. the adapter verifies source version, explicitly selected model, provider chain namespace,
   biological assembly/chain scope and direct coordinate evidence against a `StructureContext`;
4. it emits source-frame evidence, the exact mapping, current-frame planar geometry, warnings, and
   confidence—not a biological verdict;
5. the existing command layer converts the resolved current-frame geometry to `PlanarMembrane`;
6. reports serialize provenance and the slab renderer uses exactly that membrane.

PDB ID, chains and assembly metadata never establish applicability by themselves. The current atom
coordinates are compared directly with both the transformed companion and an analytically
inverse-transformed copy. Identity or inverse-provider mapping is accepted only after the
preflight-defined direct residual check. There is no structural alignment or fitted transform.

PDBTM normal semantics require reviewed x/y serialization noise and positive-z half-thickness.
Spatial sufficiency is a deterministic lower-bound witness, not a claimed exact diameter. Exact
provider/current chain sets and `ent_cif_chain_map` are mandatory; Stage 4A1 has no subset mode.
Caller-supplied offline payloads always serialize `retrieval_verified = false`.

OPM is not included in the first implementation PR. It is a separate experimental follow-up after
the PDBTM path is accepted.

### Explicit non-goals

- no network dependency or automatic download;
- no provider ranking or “best orientation”;
- no HTML scraping or job submission;
- no automatic structural alignment;
- no OPM adapter in the first implementation PR;
- no curved, multiple, intersecting, or double membranes;
- no execution of PPM/TmDet or other external binaries;
- no changes to existing manual orientation behaviour;
- no changes to existing CSV columns.

OPM, PPM 3.0, direct TmDet output, MemProtMD, TmAlphaFold, and ANVIL are deferred as explained in the
[source matrix](stage4_source_matrix.md).

## Stage 4A acceptance gate

Stage 4A is not complete until:

- the normalized model and ADR are accepted;
- source semantics are verified locally with at least one alpha-helical and one beta-barrel
  official JSON/transformed-PDB pair, while committed tests use only small hand-authored fixtures;
- adapters have no PyMOL, Qt, HTTP, archive, template, or subprocess imports;
- invalid input clears only plugin-owned state and gives a readable error without traceback;
- source, adapter, both raw hashes, assembly, chains, coordinate frames, direct-match metrics,
  fingerprints and exact transform are reported;
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

Successfully resolved Stage 4 import requires **report schema 1.3** because orientation
provenance, adapter identity, coordinate mapping and optional comparison have new defined
semantics. Released 1.0, 1.1 and 1.2 remain immutable.

- legacy/manual orientation with context disabled remains schema 1.1;
- v0.3 context analysis remains schema 1.2;
- successfully resolved Stage 4 adapter orientation produces schema 1.3 whether context is enabled
  or not;
- schema 1.3 with context enabled contains both Stage 4 orientation provenance and Stage 3
  exposure/context evidence;
- partial, rejected, unsupported or coordinate-mismatched imports produce no QC report and do not
  silently fall back to manual geometry;
- comparison is optional in 1.3 and absent when not requested;
- existing CSV columns remain unchanged; rich provenance remains JSON-only.

Schema 1.3 is the immutable v0.4.0 release contract. Stage 4A provides explicit-byte pure-Python
import, report serialization, local file selection, offline PyMOL commands, current-frame rendering,
and GUI controls. Network acquisition remains deferred and is not part of v0.4.0.

## Estimate

After design acceptance and semantics preflight, the minimal PDBTM-only Stage 4A is estimated at
**18–25 engineer-days**: 4–5 for source-semantic fixtures/model, 4–6 for adapter and mapping, 3–4
for report/schema work, 3–4 for command/GUI/render lifecycle, and 4–6 for unit, headless,
graphical, security and release validation. The experimental OPM adapter adds approximately 5–8
engineer-days. Review latency and provider clarification are not included.

## Unresolved decisions requiring acceptance

1. Confirm PDBTM half-thickness and matrix direction with paired official fixtures.
2. Decide whether a redistributable minimal provider fixture is permitted; otherwise use derived
   synthetic fixtures plus runtime user files.
3. Derive and record the final numeric residual tolerance from official coordinate and matrix
   precision before implementation review.
4. Ask PDBTM maintainers for explicit API rate-limit and redistribution guidance before Stage 4B.
