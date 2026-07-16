# Manual GUI validation

The interactive v0.1 release check passed on 2026-07-14 (Europe/Moscow).

1. Open normal graphical PyMOL 3.x.
2. Install `dist/MembraneVisualQC-0.1.0.zip` through **Plugin > Plugin Manager**.
3. Restart PyMOL and open **Plugin > Membrane Visual QC**.
4. Load `data/synthetic/bad_core_lys.pdb` as `bad_core_lys`.
5. Enter selection `bad_core_lys`, `zmin=-15`, `zmax=15`, empty ligand, cutoff `5`.
6. Click **Run QC**.
7. Confirm two translucent boundaries, one orange Lys, readable summary, and no ligand error.
8. Enter `zmin=15`, `zmax=-15`; confirm a readable validation dialog and no traceback.
9. Restore valid values, export to `reports/manual_gui_check.json`, and confirm JSON/CSV creation.
10. Run `mvqc_clear`; confirm all `mvqc_*` names disappear while `bad_core_lys` remains.

| Check | Expected | Result |
|---|---|---|
| ZIP installs | menu item appears after restart | PASS |
| Menu and GUI | menu item appears after restart; GUI opens | PASS |
| Valid synthetic analysis | exactly one charged review item | PASS |
| Empty ligand | accepted; ligand context cleared | PASS |
| Action-specific validation | each action validates only its own fields | PASS |
| Invalid range | readable error, no traceback | PASS |
| Export | schema v1 JSON and deterministic CSV | PASS |
| Clear | only `mvqc_*` names removed | PASS |

Validation environment:

- OS: Windows 10, build 26200.
- PyMOL: Incentive PyMOL 3.1.8 (bundled Python 3.10.20).
- Installation: graphical Plugin Manager installation passed.
- GUI result: passed, including the synthetic `bad_core_lys` analysis.
- Summary: `10 core residues; 1 charged core residue; 0 polar core residues; 0 ligand-neighbour residues`.
- Export: passed; the JSON/CSV report pair was created.
- `mvqc_clear`: passed; plugin-owned names were removed and the user object remained.

No screenshot from the interactive session was supplied. Existing headless validation screenshots
are `docs/screenshots/1ubq_mvqc.png`, `docs/screenshots/1c3w_mvqc.png`,
`docs/screenshots/2rh1_mvqc.png`, `docs/screenshots/1pcr_mvqc.png`, and
`docs/screenshots/bad_core_lys_mvqc.png`; they are not represented as evidence of the graphical
Plugin Manager session.

The archive has one top-level directory, `membrane_vqc/`; integrity metadata is inside that
directory and the archive checksum is beside the ZIP. Automated layout validation, headless
package loading, and the graphical Plugin Manager check all passed.

## Stage 2 interactive acceptance — PASS

The complete graphical Stage 2 acceptance passed on 2026-07-15 using Windows 10 build 26200,
Incentive PyMOL 3.1.8, bundled Python 3.10.20, and development build `0.2.0.dev0`. The tested
archive was `MembraneVisualQC-0.2.0.dev0.zip`, SHA-256
`841abe95cad44b99108cb4834ad593ef0bb4e99f64b8572cad87f088a5ac8307`. This did not alter the
published v0.1.0 release.

With `data/raw/1UBQ.cif` present, the validated rotated object was prepared in graphical PyMOL with:

```pml
run C:/Pymol_script_1/demo/prepare_rotated_1ubq.py
```

The helper located the repository from its own file path, applied the shared validated transform,
displayed `1UBQ_rotated` as cartoon, and printed the absolute path to
`demo/rotated_1ubq_orientation.json`. It did not run QC or remove unrelated objects.

| Interactive check | Result |
|---|---|
| Plugin Manager installation | PASS |
| Both GUI orientation modes visible | PASS |
| Preparation helper and `1UBQ_rotated` creation | PASS |
| Absolute orientation path output | PASS |
| Planar orientation-file Run QC | PASS |
| Arbitrary-plane Show Slab rendering, footprint, and framing | PASS |
| Orientation source display | PASS |
| Correct UTF-8 progress text | PASS |
| Complete summary equivalence | PASS |
| Review styling | PASS |
| JSON/CSV export | PASS |
| Schema 1.1 and software version `0.2.0.dev0` | PASS |
| Orientation provenance and residue-depth evidence | PASS |
| Invalid-file Run QC lifecycle | PASS |
| Invalid-file Show Slab lifecycle | PASS |
| Source reset to `unavailable` | PASS |
| Invalid zero-normal JSON handling | PASS |
| `mvqc_clear` and preservation of `1UBQ_rotated` | PASS |
| No graphical traceback | PASS |

The observed summary was `76 total / 40 core / 11 charged / 13 polar / 0 ligand-neighbour`.
Orientation evidence was source `synthetic_rigid_transform`, centre `[10.0, -5.0, 3.0]`, normal
`[1.0, 0.0, 0.0]`, and offsets `[-15.0, 15.0]`. Import provenance recorded basename
`rotated_1ubq_orientation.json`, orientation schema `1.0`, and SHA-256
`75456606ebae906f9a131825a9a3edc05f74805fc03572979e1daec677ed7e2d`.

The manual export evidence is `reports/manual_stage2_check.json` and
`reports/manual_stage2_check.csv`. The JSON contains 24 review items: 11 `WARNING` and 13
`INSPECT`. Every item contains signed distance, absolute centre distance, nearest-boundary
distance, outside distance, and normalised depth.

Because the plugin was installed from a ZIP, `software.commit_status` is `unavailable`. Structure
input provenance is `input_path_not_supplied` because the GUI action did not receive an explicit
`input_path`; no structure path or SHA-256 is implied.

Lifecycle failures behaved conservatively: invalid Run QC cleared stale report and review state;
invalid Show Slab cleared stale slab objects; both reset the source label to `unavailable` and
showed readable errors without a traceback. `mvqc_clear` removed plugin-owned state while
preserving `1UBQ_rotated`.

Graphical evidence paths:

- `docs/screenshots/manual_stage2_planar_qc.png`
- `docs/screenshots/manual_stage2_planar_edge_view.png`
- `docs/screenshots/manual_stage2_invalid_orientation.png`

## v0.2.0 final-artifact graphical smoke — PASS

This short smoke is separate from, and does not overwrite, the full `0.2.0.dev0` acceptance above.
It must use the exact final `dist/MembraneVisualQC-0.2.0.zip` release candidate.

1. Install `MembraneVisualQC-0.2.0.zip` through graphical PyMOL Plugin Manager and restart PyMOL.
2. Confirm both GUI orientation modes appear.
3. Run `run C:/Pymol_script_1/demo/prepare_rotated_1ubq.py`.
4. Select the printed `demo/rotated_1ubq_orientation.json` path and run **Show Slab**.
5. Run orientation-file QC and confirm summary `76/40/11/13/0`.
6. Export JSON and confirm report schema `1.1` and software version `0.2.0`.
7. Select an invalid orientation file and confirm a readable error without traceback.
8. Run `mvqc_clear` and confirm `1UBQ_rotated` remains.

| Release smoke check | Result |
|---|---|
| Plugin Manager installation of exact final ZIP | PASS |
| Both orientation modes visible | PASS |
| Rotated fixture helper | PASS |
| Arbitrary-plane Show Slab | PASS |
| Run QC summary `76/40/11/13/0` | PASS |
| Export schema 1.1 and software version 0.2.0 | PASS |
| Invalid-file readable error | PASS |
| `mvqc_clear` preserves `1UBQ_rotated` | PASS |

The user-reported smoke passed on 2026-07-16 with the exact 27,459-byte candidate whose SHA-256
is `084a7e384364bc46b5b9b3ecdc1b705a4ac80d15e6c320d25f0e1c9f6ec16054`. This was a focused
packaging/version smoke, not a repetition of the full scientific and lifecycle acceptance recorded
for `0.2.0.dev0`.
