# Screenshot and demo capture plan

Status: **4 of 5 required screenshots captured** (owner-captured, 2026-08-04, against `0.9.0.dev0`
and the final PR #37 UI); `recovery-state.png` and the demo remain outstanding. The assets in
`docs/screenshots/` (singular) predate the five-mode/Batch review GUI, show an intentional error
state, and one embeds a local checkout path -- they remain valid only as historical validation
evidence (see `docs/manual_gui_validation.md`, `Report.md`), not as current visual-identity assets,
and were not used here. This document is the exact, reproducible plan for the owner (or any
contributor with a real PyMOL install) to capture the one remaining screenshot and the demo.

Do not commit a file claimed to be current unless it was captured against the exact
`membrane_vqc.constants.VERSION` in the checkout at capture time, against the final,
owner-accepted UI merged in [PR #37](https://github.com/TrPavel/membrane-visual-qc/pull/37) (three
implementation passes -- colors/typography, structural information architecture, then compactness
refinement; see `docs/manual_v0.9.0_ui_acceptance.md`'s "What changed" section for the complete,
current description of the dialog). If the active version or dialog layout has moved on since this
plan was written, recapture rather than reuse an older image.

## Required files

| File | Status | Shows |
|---|---|---|
| `docs/assets/screenshots/hero-single-structure.png` | **captured** | Structure + membrane slab in the PyMOL viewport, **Single structure** tab, a populated Results state. |
| `docs/assets/screenshots/single-structure-result.png` | **captured** | The same tab after a completed QC run: a useful orientation source, populated Results (`REVIEW_ITEMS (39)`), `Export JSON` enabled. |
| `docs/assets/screenshots/batch-review-completed.png` | **captured** -- different composition than originally planned; see note below | **Batch review** after the five-mode plan finishes, with a job selected so its details are populated. |
| `docs/assets/screenshots/source-comparison-result.png` | **captured** -- from Batch review, not the Single structure tab's comparison panel; see note below | The completed PDBTM-OPM comparison job's own result: populated metrics (comparison band, comparable), captured from Batch review's Selected job panel. |
| `docs/assets/screenshots/recovery-state.png` | **outstanding** | One concise, useful recovery/error state (e.g. a rejected batch job, or a clear validation message) -- no raw traceback, and not used as the hero. |
| `docs/assets/demos/membrane-visual-qc-demo.gif` (or `.webp`) | **outstanding** | 8-15 seconds: structure loaded -> mode selected -> Run QC -> result appears -> optional switch to Batch review. Clean loop, reasonable file size. |

### Note on `batch-review-completed.png`'s composition

The originally planned composition for this shot was `SUCCESS=3` / `INPUT_REJECTED=1` /
`REVIEW_ITEMS=1`, overall `COMPLETED_WITH_ERRORS` (matching the separately documented, owner-tested
**v0.8.0** run in README's "Real example output" section). The captured `0.9.0.dev0` run of the
same five-mode plan instead completed with `SUCCESS=4` / `REVIEW_ITEMS=1` (no rejected job), overall
`COMPLETED` -- a different, but equally real, operational outcome. README's caption for this image
states the actual numbers shown rather than the originally planned ones; the v0.8.0
`COMPLETED_WITH_ERRORS` matrix stays documented separately, as text, in "Real example output". A
future recapture that reproduces an `INPUT_REJECTED` job under `continue_on_error` would give full
parity with the originally planned composition, but is not required to keep the current screenshot
in place.

### Unused captures

Two additional screenshots captured in the same session were not integrated: a PyMOL-viewport-only
shot with no dialog visible, and a **Batch review** shot in the `READY` (not-yet-run) state. Neither
matches a required composition (every required shot needs the dialog visible; this plan's shots are
all post-run states). They were left in `docs/assets/screenshots/` under their original
`Screenshot <timestamp>.png` names, unreferenced from README -- delete them or repurpose them for a
future capture pass at the owner's discretion.

## Common capture settings

- **Window size**: resize the Membrane Visual QC dialog to exactly 900x700 px before capturing
  (Windows: use a tool that reports exact client-area pixel dimensions, not just a dragged
  approximation). Keep all five screenshots at consistent dimensions/cropping.
- **Display scaling**: 100% (no Windows display scaling), to keep text/control proportions
  consistent across shots and with any future recapture.
- **PyMOL viewport background**: default PyMOL background (black) unless a step says otherwise.
- **PyMOL viewport size**: 1000x800 px, positioned so the dialog does not overlap it.
- **Redact before saving**: crop or blur any taskbar, desktop icons, browser tabs, or other
  windows. No personal file paths, usernames, or unrelated application content anywhere in frame.
  Use only the repository-relative example paths named below.
- **Format**: PNG, 24-bit color, no compression artifacts; run through `pillow`'s PNG optimizer
  (`Image.save(path, optimize=True)`) or equivalent before committing.

## Shot 1 -- hero-single-structure.png (captured)

- **Structure**: load `data/synthetic/bad_core_lys.pdb` as object `bad_core_lys`.
- **Dialog state**: **Single structure** tab active. Selection `bad_core_lys`, orientation mode
  "Legacy global-z", `zmin=-15`, `zmax=15`, ligand selection empty, cutoff `5.0`. Run the analysis
  (equivalent to `mvqc_check`) so the Results panel shows a completed, populated result.
  `Export JSON` should be in its enabled/accent post-run state, not its initial disabled state.
- **Visible**: dialog title bar showing `Membrane Visual QC <version>`; the *Structure & mode*,
  *Orientation source* (only the Legacy-relevant rows visible), *Analysis options*, and *Results*
  panels (result headline such as `✓ NO_FLAGS` or `◆ REVIEW_ITEMS (1)` above a populated summary);
  the PyMOL viewport beside/behind the dialog showing the colored slab boundaries and the
  highlighted charged residue.
- **Do not show**: any error/validation dialog, unrelated loaded object, or a file-path field
  containing anything other than the repository-relative example paths in this plan.

## Shot 2 -- single-structure-result.png (captured)

- **Precondition**: Shot 1's completed run (or an equivalent fresh run in the same session).
- **Focus**: a closer, result-focused crop of the **Single structure** tab -- the *Orientation
  source* panel showing a useful resolved orientation, the *Results* panel expanded with the
  populated result headline and summary text, and `Export JSON` visibly enabled.

## Shot 3 -- batch-review-completed.png (captured, different composition -- see note above)

- **Plan**: `data/synthetic/stage5a_batch_plan.json` (the same fixture
  `docs/five_mode_walkthrough.md` walks through).
- **Dialog state**: **Batch review** tab active, plan path set to the fixture above, **Validate**
  pressed (state `READY`), an output directory chosen under a throwaway path such as
  `reports/batch_capture/` (relative to the checkout, not an absolute personal path), then **Run**
  pressed and allowed to reach `COMPLETED_WITH_ERRORS` -- `SUCCESS=3`, `INPUT_REJECTED=1`,
  `REVIEW_ITEMS=1`, matching what `docs/status_vocabulary.md` documents. Select one completed job
  in the queue so its details panel is populated. **This is still the ideal target composition for
  a future recapture** -- see "Note on `batch-review-completed.png`'s composition" above for what
  was actually captured instead.
- **Visible**: the compact Plan/Execution metadata grids, the job queue as the visual center with
  each row's `status` cell exactly as the status vocabulary defines it (unstyled), the result
  headline above a populated run summary, and the selected job's populated details panel.
- **Do not show**: any absolute path outside the repository checkout, any username-bearing path, or
  a mid-run (`RUNNING`/`CANCELLING`) transient state.

## Shot 4 -- source-comparison-result.png (captured, alternate source -- see note above)

- **Ideal setup** (for a future recapture): **Single structure** tab, orientation mode "PDBTM vs.
  OPM comparison", with a valid local PDBTM pair and OPM file (see
  `docs/pdbtm_offline_import.md`, `docs/stage4c_source_comparison.md`). Run **Compare** to
  completion.
- **Visible**: the *Source comparison (optional)* panel expanded, populated comparison metrics
  (angle/displacement/thickness), and -- in this image or its README/doc caption -- the fixed
  scientific-boundary statement that the comparison does not select a source, create a consensus,
  or make a biological verdict. If practical, both boundaries visible together in the PyMOL
  viewport.
- **What was actually captured instead**: the comparison job's result from **Batch review**'s
  Selected job panel (Mode `pdbtm_opm_comparison`, Status `REVIEW_ITEMS`, Comparison Band
  `measurable_geometric_difference`) -- real, populated metrics, but without the Single structure
  tab's dedicated panel or the PyMOL viewport. README's caption states the boundary text since the
  image itself doesn't show it.

## Shot 5 -- recovery-state.png (outstanding)

- **Setup**: trigger one concise, realistic recovery/error state -- for example, a single
  `INPUT_REJECTED` batch job's status, or a clear pre-execution validation message (e.g.
  `zmin >= zmax`). The dialog must show a readable, typed message, not a raw Python traceback.
- **Do not use this shot as the hero** (Shot 1 is the hero); this shot's purpose is to show the
  dialog's error/recovery presentation is calm and readable, not alarming.

## Demo -- membrane-visual-qc-demo.gif (or .webp) (outstanding)

- **Length**: 8-15 seconds, reasonable file size (well under 6 MB), looping cleanly (first and last
  frame should look like a natural loop point).
- **Sequence**: **Single structure** tab -> select structure and mode -> **Run QC** -> result
  appears -> optionally switch to **Batch review**.
- **Frame rate**: 8-12 fps is sufficient; this is a workflow demonstration, not a smooth-motion
  recording, and keeping fps low keeps file size down.
- **Static fallback required in README**: the demo must sit next to (not replace) the static hero
  image and a text description of the same sequence, so it remains understandable with images
  disabled or motion not perceived.
- **Do not fabricate**: if a clean, on-topic recording cannot be produced in one take without
  narration edits, ship the five static screenshots alone and leave the demo for a follow-up
  session -- a missing demo is honest; a staged or edited one is not worth the maintenance burden
  this document is trying to avoid.
- **No private filesystem path** anywhere in frame, same rule as the static screenshots.

## After capturing the remaining files (recovery-state.png, the demo)

1. Save each file exactly as named in [Required files](#required-files) above.
2. Update `README.md`'s "Real product preview" section to reference the real files instead of the
   current outstanding-items note, following `docs/visual_identity.md`'s screenshot conventions
   (descriptive alt text, a short caption, no private paths).
3. Run `pytest tests/test_visual_identity.py tests/test_scientific_readme.py` to confirm the new
   `<img>` references resolve, have alt text, and do not reintroduce a stale-version or
   private-path violation.
4. Update this document's **Status** line once captured, naming the exact
   `membrane_vqc.constants.VERSION` the shots were captured against.
