# Stage 5B exact-artifact graphical acceptance

Overall result: **PASS**.

This is the bounded manual checkpoint for the Stage 5A/5B batch review implementation, performed
against the CI-built `MembraneVisualQC-0.6.0.dev0.zip` development artifact prior to the v0.6.0
version-identity promotion. Automated gates cover the shared stepwise runner, fake-Qt state model,
result-bundle integrity, real Qt/PyMOL offscreen lifecycle, zero-network five-mode execution,
packaging, and frozen evidence; this record is the additional literal Plugin Manager
install/restart, visible-GUI, and owner-checklist gate those automated gates cannot exercise.

## Artifact evidence

- tested package version (pre-promotion): `0.6.0.dev0`
- source commit: `9a528c4`
- CI pull_request run:
  [30656333770](https://github.com/TrPavel/membrane-visual-qc/actions/runs/30656333770)
- both CI workflows (push and pull_request) for this commit: **PASS**
- artifact: `MembraneVisualQC-0.6.0.dev0.zip`, 192,176 bytes, SHA-256
  `e5cbc47e2cf7942a24453c63035e2b7c4c99fd4d233805ece00b91293b19cd72`
- installed through PyMOL Plugin Manager with a full PyMOL restart, then exercised in a real
  (non-offscreen) PyMOL session

## Round 1: 20-item owner checklist

1. Installed plugin displays version `0.6.0.dev0`.
2. The prior single-structure GUI still works.
3. The **Batch review** tab opens.
4. No automatic plan discovery or automatic run start occurs.
5. A five-mode plan passes **Validate**.
6. All five jobs display in the correct order.
7. **Run** starts the queue.
8. Progress and current-job indicators update live.
9. Every job reaches its expected operational status.
10. Run summary and selected-job details display correctly.
11. The result manifest opens.
12. Reveal output/report works.
13. No network requests occur; the offline run passes.
14. Coordinates are unchanged before and after the run.
15. **Cancel** safely stops a running queue.
16. Close/reopen causes no crash or QThread warning.
17. History records both completed and cancelled runs.
18. **Clear history** does not delete output files on disk.
19. Legacy, Planar, PDBTM (local and cache), and Comparison GUI workflows all still work.
20. No biological verdict or source ranking is presented anywhere in the batch UI.

Result: **PASS** (all 20 items).

## Round 2: responsive/scrollable GUI smoke test

Performed after the `QScrollArea` fix (commit `9a528c4`) against the same artifact identity above:

- the dialog can be resized to a small height without content becoming unreachable;
- both the **Single structure** and **Batch review** tabs scroll vertically;
- bottom controls (action buttons, Run, Open manifest, etc.) remain reachable at reduced window
  height;
- no regression in any Round 1 item was observed while re-exercising the affected tabs.

Result: **PASS**.

## Final accepted evidence

- owner response: **PASS** for both rounds, against `MembraneVisualQC-0.6.0.dev0.zip`, 192,176
  bytes, SHA-256 `e5cbc47e2cf7942a24453c63035e2b7c4c99fd4d233805ece00b91293b19cd72` (source commit
  `9a528c4`)
- Batch review (five-mode queue, progress, statuses, manifest, summary, reveal, cancel, history,
  clear-history-preserves-outputs, offline execution, coordinate preservation): **PASS**
- responsive/scrollable dialog layout: **PASS**
- Legacy/Planar/PDBTM-local/PDBTM-cache/PDBTM-OPM-comparison GUI workflows: **PASS**
- absence of biological verdict or source ranking: **PASS**

This acceptance evidence describes the pre-promotion `0.6.0.dev0` development artifact. The final
`0.6.0` release artifact is rebuilt from the same source tree with only the version identity
changed; it is not independently re-tested unless its bytes differ from what was accepted here.
