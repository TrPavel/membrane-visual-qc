# Stage 4B4 exact-artifact acceptance

Status: in progress. This document is updated in place as each acceptance item completes; it must
not be finalized as complete until every item below is either PASS or explicitly recorded as
out of reach with the reason.

## Accepted environment and artifact

- OS: Windows 10 build 26200
- PyMOL: Incentive PyMOL 3.1.8 (bundled CPython 3.10.20), installed at
  `%LOCALAPPDATA%\Schrodinger\PyMOL2`
- Artifact under test: the exact deterministic Plugin ZIP produced by the final PR head's CI run
  (downloaded CI artifact, not a mutable local checkout) -- outer artifact digest, inner Plugin ZIP
  size/SHA-256, and CI run/artifact IDs are recorded here once the final PR head is green.

## Capability boundary

This session has no desktop GUI automation tool (no mouse/keyboard/screenshot driver for native
Windows applications) -- only a web browser pane and a shell are available. This means the
literal, mouse-driven steps of the acceptance checklist below (installing the exact ZIP through
the PyMOL **Plugin Manager** dialog, performing a full PyMOL GUI restart, and taking genuine
on-screen screenshots) cannot be performed by this session. Where a checklist item requires that,
it is marked **NOT PERFORMED (tool capability)** rather than fabricated.

Where the *underlying production code path* can be genuinely exercised without mouse/screenshot
interaction -- by running the bundled PyMOL interpreter's real Python (`python.exe` at the
Incentive PyMOL install root) headlessly, including with `QT_QPA_PLATFORM=offscreen` for real
(non-fake) `QApplication`/`QThread`/signal exercises -- that is done and recorded as a genuine,
non-mouse-driven PASS/FAIL, not skipped.

## GUI acceptance (regression)

| Item | Result |
|---|---|
| Plugin installed via Plugin Manager, full restart | NOT PERFORMED (tool capability) |
| Dialog opens, correct Unicode rendering | NOT PERFORMED (tool capability) |
| All 3 orientation modes selectable | NOT PERFORMED (tool capability) |
| Legacy global-z regression | NOT PERFORMED (tool capability) |
| Planar orientation file regression | NOT PERFORMED (tool capability) |
| Local PDBTM offline mode regression | NOT PERFORMED (tool capability) |
| Run QC / Show Slab / Colour Hydropathy / Ligand Shell / Export JSON | NOT PERFORMED (tool capability) |
| Wrong-pair and coordinate-frame-mismatch cleanup | NOT PERFORMED (tool capability) |
| Input coordinates preserved | NOT PERFORMED (tool capability) |

These regressions are covered instead by the retained automated suite (`tests/test_pymol_lifecycle.py`,
`tests/test_pymol_orientation.py`, `tests/test_gui_actions.py`, `tests/test_pdbtm_pymol.py`, and this
stage's own `tests/test_gui_pdbtm_cached.py`/`tests/test_commands_pdbtm_cached.py`), which exercise
the identical production code paths (including the bundled Incentive PyMOL Python interpreter for
non-Qt logic) without requiring mouse-driven interaction.

## Live fetch acceptance

Status: recorded below once run against the exact CI artifact head.

## Cached offline acceptance

Status: recorded below once run against the exact CI artifact head.

## Graphical cancellation/lifecycle acceptance

Status: recorded below (headless, real-Qt-via-offscreen where achievable) once run.

## Network failure diagnostic policy

Not invoked: outbound HTTPS to `pdbtm.unitmp.org` was reachable from this environment at the time
of testing (see below); no production code was weakened or modified to compensate for a
connectivity failure.
