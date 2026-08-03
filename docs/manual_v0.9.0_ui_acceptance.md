# Manual v0.9.0 UI/UX acceptance checklist

Status: **not yet run**. This document is the exact, reproducible acceptance plan for the v0.9.0
UI/UX polish session (`design/v0.9.0-ui-ux-polish`) -- a real-PyMOL, owner-observed pass, the same
kind of evidence `docs/manual_gui_validation.md` and `docs/manual_install_upgrade_checklist.md`
recorded for earlier releases. This repository's own environment cannot open a graphical PyMOL
session, so nothing below has been executed yet. Do not mark any round PASS without having
actually run it -- see `docs/manual_install_upgrade_checklist.md`'s own recording rule, which
applies here identically.

## What changed (scope of this pass)

Presentation and interaction only, across three implementation passes on the same branch.

**Pass 1** (colors/typography only -- the owner's real-PyMOL review found this insufficient on
its own, see Pass 2): a small internal design system (`membrane_vqc/ui_theme.py`,
`membrane_vqc/ui_components.py`), primary/secondary button styling, a supplementary status glyph
on `cache_status`/`comparison_status`/`status_message`/error text (never replacing the exact
text), and a message/category distinction between a `COMPLETED_WITH_ERRORS` batch outcome and a
true `FAILED_FAST` one.

**Pass 2** (structural information architecture -- the owner's second real-PyMOL review confirmed
this was materially better, but flagged compactness issues, see Pass 3): the **Single structure**
tab's one long, undifferentiated form is now six distinct `QGroupBox` panels -- *Structure &
mode*, *Orientation source*, *Analysis options*, a collapsible *Advanced analysis (optional)*,
*Run*, *Results* -- plus the *Source comparison (optional)* group, now collapsed by default
instead of always occupying the bottom of the tab. Fields that do not apply to the selected
orientation mode (Legacy global-z / Planar orientation file / PDBTM offline pair, and PDBTM's
local-vs-cache sub-choice) are now hidden. A compact "Ready to analyze `<selection>` using
`<mode>`" context line replaces guessing the current state from scattered fields. `Export JSON`
starts disabled/unstyled and only becomes the primary, accent-styled action once a result actually
exists to export. A new result headline (`✓ NO_FLAGS` / `◆ REVIEW_ITEMS (n)` / etc.) sits above
the summary text. **Batch review** gained a compact metadata grid for plan facts
(contract/SHA/job count/policies) and execution facts (progress/current job/mode/run state), a
result headline above the run summary, empty-state banners for the job queue and session history
("Validate a plan to populate the job queue.", "No batch runs yet this session."), and the
session-history group is now collapsed by default (it is secondary to the current run, not the
visual center).

**Pass 3** (compactness refinement, prompted directly by the owner's Pass-2 screenshots): fixed a
real, confirmed bug where hiding a QFormLayout row's widgets alone (Pass 2's approach) does not
release that row's inter-row spacing on this project's exact PyQt5 5.15.11/Qt 5.15.15 build --
invisible with one hidden row, but a clearly visible ~60px gap with the ~10 rows the *Orientation
source* group can hide at once (verified empirically: Legacy mode's group `sizeHint` dropped from
219px to 159px, matching a from-scratch group built with only its visible fields). The fix groups
each orientation mode's fields into its own small container widget and toggles whole containers
(a hidden `QWidget` reserves neither size nor spacing in its parent `QVBoxLayout`) -- see
`membrane_vqc/ui_components.mode_container`'s docstring. `Results` (Single structure) and `Run
summary`/`Selected job` (Batch review) now start at a compact fixed height
(`ui_theme.COMPACT_RESULT_HEIGHT`, 56px) with placeholder text, and expand to a useful height
(`ui_theme.EXPANDED_RESULT_HEIGHT`, 220px) only once they actually have something to show --
`Selected job` specifically expands only once a queue row is selected, not merely once a batch
result exists. Batch review's metadata grid and execution facts now show an em dash (`—`,
`ui_theme.EMPTY_VALUE`) for values not yet known, instead of a blank cell or a misleading `0`.

No scientific algorithm, report schema, batch contract, cache format, command signature, or status
literal changed in either pass -- see `docs/status_vocabulary.md` (unchanged) and
`docs/v1.0_contract_freeze.md`.

## Environment

Record before starting:

- OS and build:
- PyMOL distribution and version:
- Display scaling (100% / 125% / 150%):
- Screen resolution:

## Round A -- layout

For **Single structure** and **Batch review**, and all six workflows/modes (Legacy global-z,
Planar orientation file, PDBTM local, PDBTM cache, PDBTM-OPM comparison, Batch review):

| Check | Result |
|---|---|
| Dialog opens without a traceback or stray process |  |
| **Single structure** tab shows six distinct panels (Structure & mode; Orientation source; Analysis options; Advanced analysis (optional); Run; Results) plus Source comparison (optional), each visually distinct from field labels |  |
| Both tabs remain vertically scrollable at a reduced window height |  |
| Dialog remains fully usable at 1366x768, 100% scaling |  |
| Dialog remains fully usable at 1920x1080, 100% / 125% / 150% scaling |  |
| No primary action (Run QC, Export JSON, Compare, Validate, Run batch) is clipped at any tested size |  |
| No giant minimum height is imposed; resizing the window shorter shrinks content instead of the window refusing to shrink |  |
| Batch review's queue table does not let the "Input summary" column force horizontal scrolling under ordinary paths |  |
| `Run QC` and `Export JSON` are visually the most prominent buttons in their row (accent color) |  |
| `Compare` is visually the most prominent button in the comparison group |  |
| `Validate` and `Run batch` are visually the most prominent buttons in **Batch review** |  |
| `Cancel` is visible during a run but does not visually compete with the primary action |  |
| Narrow dialog width remains usable (labels wrap or truncate readably, no overlap) |  |
| **Orientation source** panel sizes closely to its visible content in every mode -- no large empty gap between the helper text and the active fields (this is the specific gap Pass 3 fixed; confirm it does not reappear) |  |
| **Results** (Single structure) is compact before any result exists (short headline + small placeholder text, not a tall blank rectangle), and expands to a useful height once a result exists |  |
| **Run summary** and **Selected job** (Batch review) are each compact before they have content, and expand once a batch result exists / a job row is selected, respectively |  |
| Batch review's metadata (Plan SHA-256, Jobs, Failure/Overwrite policy, Current job/mode) shows an em dash (`—`) before validation/execution, never a blank cell or a `0` that could be misread as a real count |  |

## Round B -- states

| State | Trigger | Expected | Result |
|---|---|---|---|
| Empty | Open dialog, no plan loaded | Batch review shows an empty queue and "Select and validate a plan explicitly." with a neutral (not alarming) glyph |  |
| Invalid input | Enter `zmin >= zmax`, press Run QC | Readable validation dialog, no traceback |  |
| Ready | Validate a valid batch plan | `READY` state, Run batch enabled once an output directory is set |  |
| Running | Press Run batch | `RUNNING`, current job/mode update, Cancel enabled |  |
| Cancelling | Press Cancel mid-run | `CANCELLING`, then reaches `CANCELLED` cleanly, no stuck UI |  |
| Success | Run a plan where every job succeeds | Status message and glyph read as success, not alarming |  |
| Review items | Run a plan producing `REVIEW_ITEMS` | Status/queue do **not** look like a failure (no red, no error glyph) -- see Round E |  |
| Input rejected | Run a plan with one deliberately invalid job entry | That job's row shows `INPUT_REJECTED` in the Status column exactly (unstyled/unchanged); overall run status is clearly not confused with total failure |  |
| Completed with errors | Run the five-mode plan under `continue_on_error` with one rejected/errored job (matches the owner-tested v0.8.0 matrix: `SUCCESS=3 / INPUT_REJECTED=1 / REVIEW_ITEMS=1`, `COMPLETED_WITH_ERRORS`) | Status message text and glyph are visibly **different** from a true failure (Round E) |  |
| Missing output | Open a result bundle whose referenced report file was moved/deleted | Reports `MISSING` cleanly, no crash, no freeze |  |
| Permission denied | Point batch output at a read-only/inaccessible directory | Fails fast with a clear, typed message; no hang |  |

## Round C -- keyboard/accessibility

| Check | Result |
|---|---|
| Tab order through **Single structure** follows the new section grouping in a sensible top-to-bottom order |  |
| Tab order through **Batch review** follows Plan -> Output -> Execution -> queue -> Results -> history |  |
| Keyboard focus is visibly indicated on the currently focused control (native Qt focus rendering; this session did not override it) |  |
| Enter/Return activates the focused primary action where a native default button applies |  |
| Table navigation (arrow keys, click-to-select) works in the queue and history tables |  |
| Disabled controls (e.g. Run batch before an output directory is chosen) are visibly distinguishable from enabled ones |  |
| No information is conveyed by color alone -- every status glyph is paired with its exact unabbreviated text |  |

## Round D -- lifecycle

| Check | Result |
|---|---|
| Open, close, and reopen the dialog multiple times with no accumulating stray widgets or duplicate tabs |  |
| No `QThread: Destroyed while thread is still running` warning at any point |  |
| Cancel during a batch run reaches a clean terminal state, not a frozen UI |  |
| Closing the dialog mid-run does not crash PyMOL; reopening reflects the finished state correctly |  |

## Round E -- scientific language

| Check | Result |
|---|---|
| No visible text in this pass implies biological invalidity, model correctness, a "best" orientation source, source ranking, clinical validity, or confidence beyond what was actually computed |  |
| `REVIEW_ITEMS` is visually and textually distinguishable from an error/failure state (no red styling, no "failed" wording) |  |
| `INPUT_REJECTED` reads as an operational/pre-execution rejection, not a claim about scientific correctness |  |
| `COMPLETED_WITH_ERRORS` reads as distinguishable from total failure, and the message states that other jobs' outputs remain valid |  |
| The PDBTM-OPM comparison group's wording still states neither source is preferred and no biological verdict is made (unchanged text, only restyled) |  |

## Round F -- visual comparison against v0.8.0

This round exists specifically because the first review of Pass 1 found it read as "recoloring
and minor spacing, not a professional UI/UX redesign." Answer each question directly; do not mark
PASS by default.

| Question | Answer |
|---|---|
| Is the interface visibly, structurally different from v0.8.0 at first glance (not just different colors)? |  |
| Can you understand the Single structure workflow (structure -> mode -> orientation -> options -> run -> result) without scrolling through controls that don't apply to your selected mode? |  |
| When you switch orientation mode, do irrelevant fields actually disappear (not just gray out)? |  |
| Do the empty states (Results, Comparison metrics, job queue, session history) look like intentional, designed states -- text explaining what will appear -- rather than blank rectangles? |  |
| Does the application feel professionally, deliberately designed, rather than "the same form, recolored"? |  |
| Does Batch review have an obvious visual center (the job queue), with Plan/Output/Execution feeling like compact setup steps rather than equally-weighted forms? |  |
| Is every feature that existed in v0.8.0 still reachable and usable (nothing was hidden permanently, only collapsed/hidden-until-relevant)? |  |
| Does the collapsed Advanced analysis / Source comparison / session-history state make sense, or does it hide something you needed visible by default? |  |

## Overall result

**PENDING.** Record `PASS`/`FAIL` per round above with the exact date, PyMOL
distribution/version, and any deviation observed -- following the same recording convention as
`docs/manual_install_upgrade_checklist.md#recording-results`. A `FAIL` on any row should be filed
as an issue before this document is considered complete for v0.9.0.
