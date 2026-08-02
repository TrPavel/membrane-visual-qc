# Manual v0.9.0 UI/UX acceptance checklist

Status: **not yet run**. This document is the exact, reproducible acceptance plan for the v0.9.0
UI/UX polish session (`design/v0.9.0-ui-ux-polish`) -- a real-PyMOL, owner-observed pass, the same
kind of evidence `docs/manual_gui_validation.md` and `docs/manual_install_upgrade_checklist.md`
recorded for earlier releases. This repository's own environment cannot open a graphical PyMOL
session, so nothing below has been executed yet. Do not mark any round PASS without having
actually run it -- see `docs/manual_install_upgrade_checklist.md`'s own recording rule, which
applies here identically.

## What changed (scope of this pass)

Presentation and interaction only: a small internal design system
(`membrane_vqc/ui_theme.py`, `membrane_vqc/ui_components.py`), section-header labels grouping the
**Single structure** tab's long form, primary/secondary button styling (`Run QC`, `Export JSON`,
`Compare`, `Validate`, `Run batch` are now visually primary), a supplementary status glyph on
`cache_status`/`comparison_status`/`status_message`/error text (never replacing the exact text),
and a message/category distinction between a `COMPLETED_WITH_ERRORS` batch outcome and a true
`FAILED_FAST` one. No scientific algorithm, report schema, batch contract, cache format, command
signature, or status literal changed -- see `docs/status_vocabulary.md` (unchanged) and
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
| **Single structure** tab shows the new section headers (Structure & orientation source; PDBTM source & cache; Resolved orientation & membrane boundaries; Ligand context & export; Run) in reading order, each visually distinct from field labels |  |
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

## Overall result

**PENDING.** Record `PASS`/`FAIL` per round above with the exact date, PyMOL
distribution/version, and any deviation observed -- following the same recording convention as
`docs/manual_install_upgrade_checklist.md#recording-results`. A `FAIL` on any row should be filed
as an issue before this document is considered complete for v0.9.0.
