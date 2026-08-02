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
  tab selected, populated fields above, and the resulting summary text showing exactly one
  `WARNING`-severity charged-core review item (this fixture is designed to produce exactly one).
  The PyMOL viewport behind/beside the dialog should show the colored slab boundaries and the one
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
- **Visible**: the ordered job queue with each row's `status` cell readable, the run-level banner
  showing `COMPLETED_WITH_ERRORS`, and the **Manifest** / **Reveal output** controls in their
  normal (enabled, post-run) state.
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
