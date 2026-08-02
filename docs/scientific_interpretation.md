# Scientific interpretation

This page consolidates the scientific-wording boundaries that apply across every workflow in
Membrane Visual QC: what a result actually reports, what it deliberately does not claim, and the
vocabulary this project uses (and avoids) when describing a result. Read this before treating any
report, review item, or comparison as more than what it is -- a deterministic, geometric/statistical
review aid.

> Membrane Visual QC is a review assistant. It does not prove that a structure is correct, stable,
> membrane-inserted, or experimentally validated.

## What the plugin reports

Every workflow produces one of two kinds of evidence:

- **Deterministic geometric/statistical measurements** -- signed distances, boundary offsets,
  SASA/RSA, contact evidence, orientation angles and displacements -- computed exactly from the
  coordinates and parameters you supplied.
- **Conservative review flags** -- residues or comparisons flagged for manual inspection under
  fixed, documented rules (see [docs/status_vocabulary.md](status_vocabulary.md) for the exact
  literals).

Nothing here is inferred, predicted, or machine-learned from biological training data; every number
traces back to a documented formula over your input.

## What it does not claim

- **No biological-correctness verdict, ever.** No status, review item, or comparison result is, or
  is derived from, a claim that a structure, orientation, or membrane placement is biologically
  correct.
- **No automatic validation.** A `SUCCESS` or `NO_FLAGS` result means the configured heuristics
  found nothing to flag -- not that the structure has been "automatically validated."
  `INPUT_REJECTED` means a pre-execution safety/contract check failed -- not that the science
  itself found the structure wrong.
- **No membrane-insertion proof.** Geometric membrane-region classification (core/interface/outside)
  is a coordinate-frame partition, not evidence that a residue is actually lipid-embedded.

## Use of `REVIEW_ITEMS`

`REVIEW_ITEMS` (and the underlying `WARNING`/`INSPECT` severities) means the configured heuristics
flagged one or more residues for manual, contextual inspection -- nothing more. Before treating a
flagged residue as a problem, inspect it in context:

- active sites
- ion-binding sites
- cofactors and ligands
- internal water chains
- proton-transfer networks
- known functional polar networks

A charged or polar residue in the core is not necessarily wrong -- it may be functional. See
[docs/status_vocabulary.md#1-single-structure-report-status-summaryoverall_status](status_vocabulary.md#1-single-structure-report-status-summaryoverall_status)
and [#2-batch-job-status-jobsstatus-in-batch-resultjson](status_vocabulary.md#2-batch-job-status-jobsstatus-in-batch-resultjson)
for exactly what each status does and does not mean.

## Comparison is not source ranking

`pdbtm_opm_comparison` is an explicit geometric review between two independently applicable
orientation source records. It never:

- selects a preferred provider or changes the active QC source;
- constructs a consensus orientation;
- fits or transforms coordinates to make sources agree;
- ranks providers as more or less trustworthy;
- interprets disagreement between sources as a biological verdict.

Reported angle/displacement/thickness bands (5°, 2 Å, 2 Å) are fixed geometric review thresholds
applied only as visual review aids -- not biological truth, and not a pass/fail test. See
`docs/stage4c_source_comparison.md#scientific-boundary` for the complete original design record.

## Membrane-context limits

- Only one planar membrane per source is represented -- curved, multiple, intersecting, or double
  membranes are unsupported.
- Provider Side1/Side2 (or equivalent) labels are never converted into inside/outside biology.
- Conventional SASA/RSA describe solvent accessibility, not lipid accessibility; the geometric
  membrane-region partition cannot distinguish a lipid-facing surface from a water-filled pore.
- Local chemical-context contacts (salt bridges, hydrogen-bond distance evidence, water/ion/ligand
  proximity) are distance-only review evidence -- not energetic stabilization, coordination,
  protonation, bond-order, or biological-validation claims.

## Vocabulary this project uses and avoids

Use, consistently, across every user-facing surface:

`review item` · `operational status` · `input rejected` · `completed with errors` ·
`orientation source` · `selected structure/object` · `coordinate preservation` · `cache snapshot` ·
`report schema` · `batch contract`

Avoid, or use only with an explicit qualifier:

`wrong structure` (say "flagged for review" instead) · `invalid model` (a report validity failure
is not a structural-correctness claim) · `failed biology` (there is no such state -- see
`ANALYSIS_ERROR` vs. `REVIEW_ITEMS` in the status vocabulary) · `best orientation` / `correct
source` (comparison never ranks sources) · `automatically validated` · `biologically correct` ·
`guaranteed membrane placement`.

`tests/test_documentation_consistency.py` enforces this vocabulary boundary across every canonical
user-facing document with negation-aware checks -- see that file for the exact rules.

## See also

[docs/known_limitations.md](known_limitations.md) for the full, release-by-release list of what is
intentionally unsupported (not just the scientific-wording boundary covered here); the "Windows
paths" and "Installation and upgrade" sections there are operational, not scientific, limitations.
