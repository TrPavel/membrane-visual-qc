# Stage 4A2 graphical acceptance

Status: PASS — exact-artifact interactive graphical acceptance complete

This record captures orientation applicability, rendering, export, and lifecycle behaviour. It does
not claim biological correctness.

## Accepted environment and artifact

- OS: Windows 10 build 26200
- PyMOL: Incentive PyMOL 3.1.8
- bundled Python: 3.10.20
- development version: `0.4.0.dev0`
- installed ZIP: `MembraneVisualQC-0.4.0.dev0.zip`
- size: 69,251 bytes
- SHA-256: `3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`
- Plugin Manager installation: PASS
- complete PyMOL restart: PASS

The earlier 69,255-byte artifact with SHA-256
`446f7af119508dd8f66396dfbc39b4444517a5b2dac9d46368f34ee07cbacb92` is superseded and was not
used for acceptance. Official payloads remained in ignored local storage; no provider payload, raw
provider coordinate file, or absolute local provider path is committed.

## GUI acceptance

- PASS — all three modes were visible: **Legacy global-z**, **Planar orientation file**, and
  **PDBTM offline pair**.
- PASS — both PDBTM file choosers opened and populated their corresponding fields.
- PASS — `Browse…`, middle dots (`·`), and angstrom symbols (`Å`) rendered correctly.
- PASS — no `Â`, `Ã`, or `â` mojibake was observed.

No screenshot from the accepted artifact was supplied for inclusion in Git; none is claimed here.

## Official-payload applicability observations

| Record | Current coordinate role | Method | Matched ATOM records | RMSD Å | Maximum residual Å | Half-thickness Å | Schema | Result |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1pcr | PDBTM transformed companion | `identity` | 6469 | 0 | 0 | 12.25 | 1.3 | PASS |
| 1pcr | deposited coordinates | `inverse_provider_transform` | 6469 | 0.000501969 | 0.00083495 | 12.25 | 1.3 | PASS |
| 1a0s | PDBTM transformed companion | `identity` | 9606 | 0 | 0 | 9.75 | 1.3 | PASS |
| 1a0s | deposited coordinates | `inverse_provider_transform` | 9606 | 0.000501151 | 0.000846301 | 9.75 | 1.3 | PASS |

Both records serialized provider resource version `1017` and provider software version `3.2.134`.
In every case the membrane boundaries rendered in the current coordinate frame and the input
molecular coordinates remained unchanged.

For 1pcr identity, context OFF and ON both passed. JSON and CSV export passed, schema 1.3 structural
and semantic validation passed, CSV columns remained unchanged, and exported JSON contained no
absolute local paths. Context ON observed 11 `BURIED_WITH_POTENTIAL_SUPPORT` and 28
`ACCESSIBLE_WITH_POTENTIAL_SUPPORT` states.

The 1a0s transformed companion produced 33 ligand-neighbour residues, while the deposited-coordinate
case produced zero. This HETATM-dependent difference does not affect orientation applicability,
which used the same 9606 matched ATOM records.

## Failure and lifecycle acceptance

- PASS — a wrong pair was rejected with `COMPANION_ID_MISMATCH`.
- PASS — a manually rotated and translated object was rejected with `COORDINATE_FRAME_MISMATCH`;
  its transformed coordinates remained transformed after rejection.
- PASS — no traceback, fallback, fitting, or automatic alignment occurred.
- PASS — failed Run QC cleared plugin-owned state and `LAST_REPORT`; stale export was blocked.
- PASS — failed Show Slab removed the prior slab and all other plugin-owned state.
- PASS — valid Show Slab created boundaries but no QC report.
- PASS — `valid → invalid → valid`, repeated Run QC, and repeated Show Slab lifecycles completed
  without stale labels, stale reports, or duplicate slab objects.
- PASS — closing and reopening the GUI preserved usable state.
- PASS — `mvqc_clear` removed only plugin-owned state.
- PASS — every loaded input molecular object survived all tested sequences.

## Legacy regressions

Legacy global-z passed with schema 1.1, orientation source `manual_global_z`, 40 core residues,
11 charged core residues, 13 polar core residues, zero ligand-neighbour residues, unchanged input
coordinates, normal slab rendering, review objects, report generation, and export.

The planar orientation-file workflow passed with schema 1.1, orientation source
`synthetic_rigid_transform`, 40 core residues, 11 charged core residues, 13 polar core residues,
zero ligand-neighbour residues, arbitrary-plane slab rendering, report export, lifecycle cleanup,
and unchanged input coordinates. Neither legacy workflow emitted schema 1.3 without PDBTM evidence.

## Non-blocking observations

The slab planes are visible but relatively low contrast on a dark background. This is a
non-blocking UI/rendering backlog item; runtime rendering was not changed during acceptance. Modern
UI styling remains deferred to a dedicated pre-v1.0 polish pass.

## Checklist closure

- [x] Plugin Manager installation and PyMOL restart — PASS
- [x] all three GUI orientation modes visible — PASS
- [x] both PDBTM file chooser controls work — PASS
- [x] 1pcr identity and inverse imports — PASS
- [x] 1a0s identity and inverse imports — PASS
- [x] current-frame slab rendering without changing input coordinates — PASS
- [x] schema-1.3 export with context OFF and ON — PASS
- [x] invalid-pair and transformed-object cleanup without traceback — PASS
- [x] repeated lifecycle and `mvqc_clear` input preservation — PASS
- [x] legacy global-z regression — PASS
- [x] planar orientation-file regression — PASS
