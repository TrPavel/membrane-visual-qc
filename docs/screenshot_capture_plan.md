# Screenshot and demo capture plan

Status: **not yet captured**. This repository's automated environment cannot open a real,
graphical PyMOL session, so no current screenshot or GIF of the plugin dialog exists yet. The
assets in `docs/screenshots/` predate the five-mode/Batch review GUI, show an intentional error
state, and one embeds a local checkout path -- they remain valid only as historical validation
evidence (see `docs/manual_gui_validation.md`, `Report.md`), not as current visual-identity
assets. This document is the exact, reproducible plan for the owner (or any contributor with a
real PyMOL install) to capture the assets `README.md` currently references as pending.

Do not commit a screenshot claimed to be current unless it was captured against the exact
`membrane_vqc.constants.VERSION` in the checkout at capture time. If the active version has moved
on since this plan was written, recapture rather than reuse an older image.

The v0.9.0 UI/UX polish session (`design/v0.9.0-ui-ux-polish`) restructured the dialog across two
passes: colors/typography/status glyphs first, then -- after real-PyMOL review found that
insufficient -- a structural pass regrouping the **Single structure** tab into six `QGroupBox`
panels with mode-based row hiding, a collapsed-by-default comparison section, and result headlines
on both tabs (see `docs/manual_v0.9.0_ui_acceptance.md`'s "What changed" section for the full
list). No control's exact label, tab order, or the queue table's status-cell text changed. The
"Visible" notes below describe the new structure; capture these shots only after completing (or
alongside) Rounds A and F of `docs/manual_v0.9.0_ui_acceptance.md`, since those rounds exercise the
exact states these shots depend on and are the right place to judge whether the composition below
still looks right once you can actually see it.

## Common capture settings

- **Window size**: resize the Membrane Visual QC dialog to exactly 900x700 px before capturing
  (Windows: use a tool that reports exact client-area pixel dimensions, not just a dragged
  approximation).
- **Display scaling**: 100% (no Windows display scaling), to keep text/control proportions
  consistent with any future recapture.
- **PyMOL viewport background**: default PyMOL background (black) unless a step says otherwise.
- **PyMOL viewport size**: 1000x800 px, positioned so the dialog does not overlap it.
- **Redact before saving**: crop or blur any taskbar, desktop icons, browser tabs, or other
  windows. No personal file paths, usernames, or unrelated application content anywhere in frame.
  Use only the repository-relative example paths named below.
- **Format**: PNG, 24-bit color, no compression artifacts; run through `pillow`'s PNG optimizer
  (`Image.save(path, optimize=True)`) or equivalent before committing.
- **Filenames and destination**: `docs/assets/screenshots/<name>.png`, exactly as named per step.

## Shot 1 -- hero: Single structure tab, legacy global-z mode

- **File**: `docs/assets/screenshots/hero-single-structure.png`
- **Structure**: load `data/synthetic/bad_core_lys.pdb` as object `bad_core_lys`.
- **Dialog state**: **Single structure** tab active. Selection `bad_core_lys`, orientation mode
  "Legacy global-z", `zmin=-15`, `zmax=15`, ligand selection empty, cutoff `5.0`.
- **Action**: run the analysis (equivalent to `mvqc_check`) so the summary panel shows a completed
  result, then **Export JSON** once so the dialog reflects a normal post-run state (button
  enabled, no pending validation warnings).
- **Visible**: dialog title bar showing `Membrane Visual QC <version>`, the **Single structure**
  tab selected showing its distinct group panels in order -- *Structure & mode* (with the compact
  "Ready to analyze bad_core_lys using Legacy global-z." context line), *Orientation source*
  (only the Legacy-relevant `zmin`/`zmax`/Resolved orientation rows visible -- PDBTM/planar rows
  actually hidden, not grayed out), *Analysis options*, the collapsed *Advanced analysis
  (optional)* group (title visible, contents collapsed), *Run* (the accent-styled `Run QC` and
  `Export JSON` standing out from the unstyled `Show Slab`/`Colour Hydropathy`/`Ligand Shell`
  beside them; `Export JSON` should be in its post-run enabled/accent state, not its initial
  disabled state), and *Results* (the result headline reading something like
  `✓ NO_FLAGS` or `◆ REVIEW_ITEMS (1)` above a populated, non-empty summary box). The collapsed
  *Source comparison (optional)* group should be visible at the bottom, still collapsed. The
  PyMOL viewport behind/beside the dialog should show the colored slab boundaries and the one
  highlighted charged residue.
- **Do not show**: any error/validation dialog, any unrelated loaded object, any file-path field
  containing anything other than the repository-relative example paths in this plan.

## Shot 2 -- Batch review tab, five-mode plan validated and run

- **File**: `docs/assets/screenshots/batch-review-five-mode.png`
- **Plan**: `data/synthetic/stage5a_batch_plan.json` (the same fixture
  `docs/five_mode_walkthrough.md` walks through).
- **Dialog state**: **Batch review** tab active, plan path set to the fixture above, **Validate**
  pressed (state `READY`), an output directory chosen under a throwaway path such as
  `reports/batch_capture/` (relative to the checkout, not an absolute personal path), then **Run**
  pressed and allowed to reach `COMPLETED_WITH_ERRORS` -- i.e. the batch actually finishes with a
  mix of `SUCCESS`, `REVIEW_ITEMS`, and one rejected/errored job, matching what
  `docs/status_vocabulary.md` documents. Do not stage a run that reaches plain `COMPLETED` for this
  shot -- the point is to show the queue's ordered per-job status column with more than one status
  value visible at once.
- **Visible**: the compact *Plan* metadata grid (Contract/Plan SHA-256/Jobs/Failure policy/
  Overwrite policy as short label:value pairs, not a tall list of full-width rows), the *Execution*
  group's own compact grid (Completed / total, Current job, Current mode, Run state) with the
  status line below it showing the v0.9.0 supplementary glyph and a message that reads as
  distinguishable from a true failure (see `docs/manual_v0.9.0_ui_acceptance.md` Round E), the job
  queue as the visual center of the tab with each row's `status` cell readable and exactly as the
  status vocabulary defines it (unstyled -- the v0.9.0 restyle never changes this cell's text), the
  *Results* group's own result headline (e.g. `◆ COMPLETED_WITH_ERRORS · success=3, ...`) above a
  populated run-summary box, and the **Manifest** / **Reveal output** controls in their normal
  (enabled, post-run) state. The `Validate` and `Run batch` buttons should be visible in their
  accent-styled (primary) state. The *Current-session history* group should be visible but
  collapsed (title only) -- it is intentionally secondary to the current run.
- **Do not show**: any absolute path outside the repository checkout, any username-bearing path,
  or a mid-run (`RUNNING`/`CANCELLING`) transient state.

## Shot 3 -- result browser, one report open

- **File**: `docs/assets/screenshots/result-browser.png`
- **Precondition**: Shot 2's completed batch run.
- **Action**: open the result browser on the one job that reached `REVIEW_ITEMS`, so a real report
  renders in the browser pane.
- **Visible**: the selected job's report content (summary, review items) and the
  `VERIFIED` artifact-availability state for it -- not `MISSING`.

## Animated demo (optional, only after Shots 1-3 exist)

- **File**: `docs/assets/demos/quick-start.gif`
- **Length**: under 20 seconds, under 6 MB, looping cleanly (first and last frame should look like
  a natural loop point -- e.g. both showing the idle **Single structure** tab before/after input).
- **Sequence**: open Plugin Manager entry -> **Single structure** tab -> fill in Shot 1's exact
  fields -> run -> show the summary appear -> **Export JSON** -> switch to **Batch review** ->
  load Shot 2's plan -> **Validate** -> **Run** -> show the queue reach `COMPLETED_WITH_ERRORS`.
- **Frame rate**: 8-12 fps is sufficient; this is a workflow demonstration, not a smooth-motion
  recording, and keeping fps low keeps file size down.
- **Static fallback required in README**: the GIF must sit next to (not replace) the static Shot 1
  hero image and a text description of the same sequence, so the demo remains understandable with
  images disabled or motion not perceived.
- **Do not fabricate**: if a clean, on-topic recording cannot be produced in one take without
  narration edits, ship Shots 1-3 alone and leave this GIF for a follow-up session -- a missing
  demo is honest; a staged or edited one is not worth the maintenance burden this document is
  trying to avoid.

## After capturing

1. Save each file exactly as named above under `docs/assets/screenshots/` (or
   `docs/assets/demos/` for the GIF).
2. Update `README.md`'s hero and workflow sections to reference the real files instead of the
   current SVG-only hero, following `docs/visual_identity.md`'s screenshot conventions.
3. Run `pytest tests/test_visual_identity.py` (or the current equivalent) to confirm the new
   `<img>` references resolve, have alt text, and do not reintroduce a stale-version or
   private-path violation.
4. Update this document's **Status** line once captured, naming the exact
   `membrane_vqc.constants.VERSION` the shots were captured against.
