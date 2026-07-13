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
