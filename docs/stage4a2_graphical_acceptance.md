# Stage 4A2 graphical acceptance

Status: automated and real headless PyMOL validation passed; exact-Plugin-ZIP interactive
graphical acceptance is pending and must not be inferred from the headless result.

## Validated environment

- OS: Windows 10 build 26200
- PyMOL: Incentive PyMOL 3.1.8
- bundled Python: 3.10.20
- development version: `0.4.0.dev0`

## Headless acceptance

The synthetic retained fixture passed identity, inverse-provider-transform, arbitrary current-frame
slab rendering, schema 1.3, context OFF/ON, repeated execution, transformed-coordinate rejection,
failure cleanup, `LAST_REPORT` reset, and input-object preservation.

Official payloads were used only from ignored `.local/` storage. Raw coordinates and provider
payloads are not reproduced here and are not committed.

| Record | Class | Current coordinate role | Method | Matched atoms | RMSD Å | Maximum residual Å | Half-thickness Å | Result |
|---|---|---|---|---:|---:|---:|---:|---|
| 1pcr | Tm_Alpha | PDBTM transformed companion | identity | 6469 | 0.000000000 | 0.000000000 | 12.25 | PASS |
| 1pcr | Tm_Alpha | RCSB deposited legacy PDB | inverse_provider_transform | 6469 | 0.000501969 | 0.000834950 | 12.25 | PASS |
| 1a0s | Tm_Beta | PDBTM transformed companion | identity | 9606 | 0.000000000 | 0.000000000 | 9.75 | PASS |
| 1a0s | Tm_Beta | RCSB deposited legacy PDB | inverse_provider_transform | 9606 | 0.000501151 | 0.000846301 | 9.75 | PASS |

Both records report PDBTM resource version `1017` and provider software `3.2.134`. Context ON also
passed for both identity cases. A wrong JSON/transformed pair and a manually transformed current
object were rejected; plugin state/report cleanup passed, and `mvqc_clear` preserved the input.

Official URLs, timestamps, and hashes remain the separately reviewed provenance in
`pdbtm_semantics_preflight_results.json`. No local absolute paths enter exported evidence.

## Exact development ZIP interactive checklist

The initial pre-review artifact is superseded and must not be used for final graphical acceptance:

- size: 69,255 bytes
- SHA-256: `446f7af119508dd8f66396dfbc39b4444517a5b2dac9d46368f34ee07cbacb92`

Corrected pre-graphical candidate built after Unicode and complete slab-lifecycle fixes:

- file: `dist/MembraneVisualQC-0.4.0.dev0.zip`
- size: 69,251 bytes
- SHA-256: `3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`

The two corrected deterministic builds were byte-for-byte identical. These values identify the artifact
that must be installed for interactive acceptance; they are not themselves graphical evidence.

The following must be performed after the deterministic final ZIP is built and its exact filename,
size, and SHA-256 are recorded:

- [ ] Plugin Manager installation and PyMOL restart
- [ ] all three GUI orientation modes visible
- [ ] both PDBTM file chooser controls work
- [ ] 1pcr identity import and source/status label
- [ ] 1pcr inverse import
- [ ] 1a0s identity and inverse imports
- [ ] current-frame slab rendering without changing the input object
- [ ] schema-1.3 QC export with context OFF and ON
- [ ] invalid-pair and transformed-object cleanup without traceback
- [ ] repeated lifecycle and `mvqc_clear` input preservation
- [ ] legacy global-z regression
- [ ] planar orientation-file regression

Only genuine screenshots and observations from that exact artifact may change these items to PASS.
