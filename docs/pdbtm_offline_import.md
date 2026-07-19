# Offline PDBTM import in PyMOL

Status: v0.4.0 release workflow. Report schema 1.3 is the immutable v0.4.0 PDBTM provenance
contract and requires both JSON Schema structural validation and Stage 4 semantic validation.

## Required local files

The workflow requires two matching official files selected by the user:

1. the PDBTM API-v1 JSON record;
2. its PDBTM transformed-PDB companion.

The plugin performs no download, URL access, archive extraction, external command execution, OPM
lookup, automatic alignment, or coordinate transformation of the loaded molecule. File extensions
and GUI filters are conveniences only; the accepted Stage 4A1 adapter validates exact content.
Both files and the current PyMOL snapshot are limited to 5 MiB.

## PyMOL commands

```pml
mvqc_check_pdbtm selection=my_object, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb, ligand=
mvqc_slab_pdbtm selection=my_object, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb
```

Optional `biological_assembly` records an explicitly supplied current assembly. The plugin never
infers assembly, structure identity, or scientific applicability from an object or file name.
`mvqc_check_pdbtm` accepts the existing `cutoff`, `quiet`, `export_path`, `input_path`,
`analyze_context`, `exposure_quality`, and `exposure_backend` parameters. `mvqc_slab_pdbtm`
renders only the resolved boundaries and creates no report.

Because Show Slab changes the displayed orientation without producing replacement QC evidence, it
first invalidates all prior plugin-owned slab/review/ligand/context visuals and `LAST_REPORT`. On
failure it repeats that complete cleanup. Input molecular objects are never included in cleanup.

The analysis selection may be a chain or residue subset, but it must resolve to exactly one
molecular object. Applicability is always checked against a single snapshot of the complete
containing object. Stage 4A2 accepts one object, one state, and legacy-PDB-compatible current chain
IDs only. Multi-object selections, multi-state objects, unsafe multi-character chains, mismatched
assemblies, changed coordinate frames, missing companions, and unsupported provider records fail
with a stable code and readable message.

## Coordinate and lifecycle contract

The complete object is serialized once with `cmd.get_pdbstr(object, state=1)` after confirming its
single-state and metadata contract through `cmd.get_model`. A real PyMOL 3.1.8 probe established
that this snapshot includes the current object matrix and agrees with `cmd.get_model` and
`cmd.get_coords`; see [snapshot semantics](stage4a2_pymol_snapshot_semantics.md).

Only direct identity or the analytically defined inverse-provider-transform match is permitted.
The plugin never fits, rotates, translates, renames, duplicates, or deletes the input object.
Failures clear plugin-owned slab/review/ligand/context objects and `LAST_REPORT`, so stale evidence
cannot be exported. `mvqc_clear` preserves every input object.

## Provenance and interpretation

Successful QC produces schema 1.3 with the resolved membrane and exact `OrientationEvidenceV1`.
The report includes a SHA-256 and byte size for exactly one `pdbtm_json` and one
`transformed_pdb`, their known media types, and `retrieval_verified: false`. Local absolute paths,
filesystem modification times, and invented retrieval timestamps are not serialized.

Schema 1.3 passes JSON Schema structural validation and the mandatory Stage 4 semantic validator.
The top-level membrane equals evidence current geometry. Context disabled, exposure enabled, and
exposure plus local context all remain schema 1.3; CSV columns are unchanged.

Coordinate applicability shows only that the loaded current coordinates match one reviewed
provider reference within declared tolerances. It is not a verdict that the membrane orientation
is biologically correct. Provider Side1/Side2 labels are not converted into inside/outside biology.
Ordinary SASA is not lipid accessibility, local chemical-context labels remain conservative
evidence, and reports are visual-QC evidence rather than definitive structural validation.

## Deferred functionality

v0.4.0 includes no network retrieval, OPM adapter, cross-source comparison, curved or multiple
membranes, batch CLI, model-to-model comparison, automatic fitting/alignment, or automatic
biological verdict. Relatively low slab contrast on dark backgrounds is a non-blocking pre-v1.0 UI
backlog item.
