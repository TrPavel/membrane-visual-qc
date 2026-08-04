<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/wordmark-on-dark.svg">
  <img src="docs/assets/brand/wordmark-on-light.svg" alt="Membrane Visual QC" width="360">
</picture>

**Membrane-aware visual QC for PyMOL structures.**

[![CI](https://github.com/TrPavel/membrane-visual-qc/actions/workflows/ci.yml/badge.svg)](https://github.com/TrPavel/membrane-visual-qc/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/TrPavel/membrane-visual-qc?include_prereleases&label=release)](https://github.com/TrPavel/membrane-visual-qc/releases)
[![License: MIT](https://img.shields.io/github/license/TrPavel/membrane-visual-qc)](LICENSE)
![Python 3.10 | 3.11 | 3.12](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![Validated: Windows | Incentive PyMOL](https://img.shields.io/badge/validated-Windows%20%7C%20Incentive%20PyMOL-informational)

[Install](#installation-and-compatibility) ·
[Quick start](#quick-start) ·
[Scientific foundation](#scientific-foundation) ·
[Documentation](docs/index.md) ·
[Latest release](https://github.com/TrPavel/membrane-visual-qc/releases/latest)

</div>

> Membrane Visual QC is a review assistant. It does not prove that a structure is correct, stable,
> membrane-inserted, or experimentally validated -- see [Scientific interpretation](docs/scientific_interpretation.md).

Distributed as a **GitHub prerelease** (not on PyPI). Current published release: **v0.8.0**. Active
development line: **`0.9.0.dev0`**.

<p align="center">
  <img src="docs/assets/screenshots/hero-single-structure.png" alt="Membrane Visual QC's Single structure tab in Legacy global-z mode: a loaded structure with the manually defined membrane slab boundaries drawn in the PyMOL viewport, next to the dialog's populated Results panel" width="880">
</p>

<p align="center"><sub>Single structure tab, <strong>Legacy global-z</strong> mode -- a manually defined <code>zmin</code>/<code>zmax</code> slab, not a source-derived PDBTM/OPM orientation (real screenshot, own capture against the current UI).</sub></p>

## Real product preview

Owner-captured, current-UI screenshots (against `0.9.0.dev0`, the dialog restructured across three
real-PyMOL-reviewed passes most recently merged in [PR #37](https://github.com/TrPavel/membrane-visual-qc/pull/37)):

<p align="center">
  <img src="docs/assets/screenshots/single-structure-result.png" alt="Single structure tab after a completed QC run: ligand-shell residues highlighted in the PyMOL viewport, a REVIEW_ITEMS (39) result headline, and Export JSON enabled" width="880">
</p>

<p align="center"><sub>A completed run with ligand-shell residues highlighted and 39 flagged review items -- <code>REVIEW_ITEMS</code> is a manual-review cue, not an error; see <a href="docs/status_vocabulary.md">status vocabulary</a>.</sub></p>

<p align="center">
  <img src="docs/assets/screenshots/batch-review-completed.png" alt="Batch review tab after running the five-mode plan: all five jobs' status column, and a completed Results panel" width="880">
</p>

<p align="center"><sub>This <code>0.9.0.dev0</code> run of the five-mode plan completed 4 jobs and flagged 1 for review (overall <code>COMPLETED</code>). The separately documented v0.8.0 run below hit one <code>INPUT_REJECTED</code> job instead (<code>COMPLETED_WITH_ERRORS</code>) -- both are real, typed operational outcomes, not a pass/fail score; see <a href="#real-example-output">Real example output</a>.</sub></p>

<p align="center">
  <img src="docs/assets/screenshots/source-comparison-result.png" alt="Batch review's Selected job panel showing the completed PDBTM-OPM comparison job: REVIEW_ITEMS status, report schema 1.5, and a measurable_geometric_difference comparison band" width="880">
</p>

<p align="center"><sub>The PDBTM-OPM comparison job's own result (captured from Batch review's Selected job panel). The comparison never selects a preferred source or constructs a consensus -- see <a href="#scientific-foundation">Scientific foundation</a>.</sub></p>

<p align="center">
  <img src="docs/assets/screenshots/recovery-state.png" alt="A validation-error dialog reading 'Membrane Visual QC could not complete the action: zmin must be less than zmax', shown over the Single structure tab with the invalid values still visible" width="880">
</p>

<p align="center"><sub>An invalid <code>zmin</code>/<code>zmax</code> pair is rejected with a clear, typed message before any analysis runs -- no raw traceback.</sub></p>

<p align="center">
  <img src="docs/assets/demos/membrane-visual-qc-demo.gif" alt="Animated demo: the Single structure tab ready to run, then a completed NO_FLAGS result, then the Batch review tab showing a finished five-mode run" width="880">
</p>

<p align="center"><sub>A 3-frame slideshow assembled from real, individually captured states -- structure/mode ready -&gt; <code>Run QC</code> result -&gt; Batch review -- not a continuous screen recording; see <a href="docs/screenshot_capture_plan.md">docs/screenshot_capture_plan.md</a> for exactly how it was built.</sub></p>

Capture provenance and exact composition for every image above: [docs/screenshot_capture_plan.md](docs/screenshot_capture_plan.md).

## What it does

An open-source PyMOL plugin that displays an explicit membrane slab or orientation source next to a
structure, classifies residues by geometric position (core / interface / outside), flags charged and
selected polar core residues for manual review, colors by a coarse hydropathy palette, and selects
residues near a ligand/cofactor selection. Every run exports a versioned JSON report and a
deterministic CSV. None of this is a biological verdict -- see
[docs/status_vocabulary.md](docs/status_vocabulary.md) for exactly what every status literal does
and does not mean, and [Scientific foundation](#scientific-foundation) below for what's actually
computed.

| Orient | Review | Export / Batch |
|---|---|---|
| Pick one of five orientation sources (manual, file, PDBTM, or a PDBTM-OPM comparison) for a source-derived slab. | Inspect charged/polar core residues, hydropathy coloring, and solvent-accessibility context flagged for manual interpretation. | Export a deterministic JSON/CSV report, or run many structures through **Batch review** with an ordered queue and manifest. |

## Scientific foundation

Membrane Visual QC computes four things, each a deterministic calculation, classification, or
visualization over the coordinates and parameters you supply -- never a prediction or a
machine-learned inference:

1. **Membrane geometry** -- an orientation source resolves to a center, a unit normal, and a
   core/interface slab (§§2-4 below).
2. **Residue positional classification** -- each residue's representative point is classified
   `core` / `interface` / `outside` by its signed distance from the midplane (§§3-5).
3. **Hydropathy and solvent-accessibility context** -- a fixed hydropathy scale drives coloring;
   Shrake-Rupley SASA/RSA is computed for review, not lipid accessibility (§§6, 9).
4. **Orientation-source evidence** -- PDBTM/OPM applicability is an identity-only geometric check
   against your structure's exact current coordinates, never a fit (§§10-12).

| Symbol | Meaning |
|---|---|
| $r_i$ | residue representative point (C-alpha, or the residue's atom-average if no C-alpha) |
| $c$ | orientation centre |
| $n$ | unit membrane normal |
| $d_i$ | signed distance of $r_i$ from the midplane, in Å |
| $L$, $U$ | `lower_offset`, `upper_offset` (Å, measured along $n$ from $c$) |
| $w$ | `interface_width` (Å) |

Signed distance from the midplane (`orientation.signed_distance`):

$$d_i = n \cdot (r_i - c)$$

The exact implemented classification (`orientation.classify_signed_distance`):

$$
\text{classification}(d_i) =
\begin{cases}
\texttt{core} & L \le d_i \le U \\
\texttt{lower\_interface} & L-w \le d_i < L \\
\texttt{upper\_interface} & U < d_i \le U+w \\
\texttt{outside} & \text{otherwise}
\end{cases}
$$

<p align="center">
  <img src="docs/assets/diagrams/membrane-geometry.svg" alt="Schematic cross-section showing the membrane normal n, orientation centre c, a residue point r_i, its signed distance d_i, and the resulting core/interface/outside regions" width="640">
</p>

<p align="center"><sub>Coordinate-frame schematic of the geometry above -- not a physical bilayer simulation.</sub></p>

Full derivation (nearest-boundary/outside-distance/normalized-depth, residue representative points,
hydropathy, SASA backends, PDBTM/OPM applicability, and the PDBTM-OPM comparison), with the exact
function and file backing every claim: **[docs/scientific_background.md](docs/scientific_background.md)**.
Claims boundary and vocabulary: [docs/scientific_interpretation.md](docs/scientific_interpretation.md).

## How it works

```mermaid
flowchart LR
    A["Structure loaded"] --> B["Orientation source<br/>selected"]
    B --> C["Slab + residue<br/>classification"]
    C --> D["Report<br/>schema 1.0-1.5"]
```

The orientation source is one of five modes -- see [Core workflows](#core-workflows) below.

```mermaid
flowchart LR
    A["Batch plan<br/>mvqc-batch-plan-1.0"] --> B["Validation"]
    B --> C["Ordered job<br/>queue"]
    C --> D["Result bundle<br/>mvqc-batch-result-1.0"]
```

Batch review runs any single-structure mode above across many jobs sequentially, with cooperative
cancellation and a manifest -- see [docs/five_mode_walkthrough.md](docs/five_mode_walkthrough.md).

## Core workflows

| Mode | Input | What it checks |
|---|---|---|
| **Legacy global-z** | selection, `zmin`/`zmax` | Original global-z slab; the membrane normal is assumed to be the global z-axis. |
| **Planar orientation** | local orientation JSON | An arbitrary planar membrane normal from a versioned local file, not just global z. |
| **PDBTM local** | local PDBTM API-v1 pair | Reviewed offline PDBTM applicability against the structure's current coordinates. |
| **PDBTM cache** | validated local cache snapshot | The same applicability check via an explicit **Fetch/Refresh** vs. **Use cached pair** boundary -- see [Safety and scientific boundaries](#safety-and-scientific-boundaries). |
| **PDBTM vs. OPM comparison** | PDBTM pair + local OPM file | An independent two-source geometric comparison: no fitting, no automatic source choice, no consensus, no provider ranking. |
| **Batch review** | `mvqc-batch-plan-1.0` plan | Runs any of the above across many jobs sequentially on PyMOL's main thread. |

Full walkthroughs: [docs/tutorial.md](docs/tutorial.md) (each mode individually) and
[docs/five_mode_walkthrough.md](docs/five_mode_walkthrough.md) (one narrated example exercising all
five plus Batch review).

## Quick start

```bash
conda env create -f environment.yml
conda activate mvqc
```

```pml
run load_mvqc.py
load data/synthetic/bad_core_lys.pdb, bad_core_lys
mvqc_check selection=bad_core_lys, zmin=-15, zmax=15, ligand=, cutoff=5.0
mvqc_export path=reports/bad_core_lys_mvqc.json
```

The synthetic fixture must produce exactly one charged-core review item -- this verifies software
behavior, not biology. Full walkthrough: [docs/quick_start.md](docs/quick_start.md).

<details>
<summary>All PyMOL commands</summary>

- `mvqc_check selection=all, zmin=-15, zmax=15, ligand=organic, cutoff=5.0`
- `mvqc_check_orientation selection=all, orientation_file=demo/rotated_1ubq_orientation.json`
- `mvqc_slab_orientation selection=all, orientation_file=demo/rotated_1ubq_orientation.json`
- `mvqc_check_pdbtm selection=all, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb`
- `mvqc_slab_pdbtm selection=all, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb`
- `mvqc_slab zmin=-15, zmax=15`
- `mvqc_color_hydropathy selection=all`
- `mvqc_ligand_shell protein=all, ligand=organic, cutoff=5.0`
- `mvqc_export path=reports/mvqc_report.json`
- `mvqc_batch_run plan=data/synthetic/stage5a_batch_plan.json, output_dir=reports/batch, fail_fast=0, quiet=1`
- `mvqc_clear` -- removes only plugin-owned names beginning with `mvqc_`.

The offline PDBTM commands require an explicit matching local JSON/transformed-PDB pair and exactly
one single-state PyMOL molecular object; the plugin never fetches data, fits, rotates, translates,
or otherwise transforms the input object. See [docs/pdbtm_offline_import.md](docs/pdbtm_offline_import.md).

</details>

## Real example output

A real Batch review run (owner-tested against the published v0.8.0 build) produced:

<p align="center"><code>✓ SUCCESS × 3&nbsp;&nbsp;&nbsp;◆ REVIEW_ITEMS × 1&nbsp;&nbsp;&nbsp;✕ INPUT_REJECTED × 1&nbsp;&nbsp;&nbsp;→&nbsp;&nbsp;&nbsp;COMPLETED_WITH_ERRORS</code></p>

| Job outcome | Count | Meaning |
|---|---:|---|
| `SUCCESS` | 3 | Completed with no flagged review items. |
| `REVIEW_ITEMS` | 1 | Completed; one or more residues flagged for manual review. |
| `INPUT_REJECTED` | 1 | Failed pre-execution plan validation; no analysis ran at all. |
| **Overall run** | `COMPLETED_WITH_ERRORS` | At least one job failed under `continue_on_error`; every other job's output remains valid and independently readable. |

`REVIEW_ITEMS` and `INPUT_REJECTED` are specific, typed operational outcomes, not failure states to
"fix until they disappear." Complete vocabulary: [docs/status_vocabulary.md](docs/status_vocabulary.md).

## Safety and scientific boundaries

- **Coordinates are never mutated.** No mode fits, rotates, translates, or otherwise transforms the
  loaded object. **Explicit network boundary**: only **Fetch/Refresh** in PDBTM-cache mode ever
  contacts the network. **Atomic output publication** and **session-only history** (at most 20
  entries, never written to disk). Full mechanism: [docs/offline_and_safety.md](docs/offline_and_safety.md).
- **No biological-correctness verdict, ever.** `REVIEW_ITEMS` flags a residue for manual,
  contextual inspection -- it does not mean a residue is wrong. PDBTM/OPM applicability is geometric
  identity evidence, not proof an orientation is biologically correct. Ordinary SASA is solvent
  accessibility, not lipid accessibility. There is no automatic source ranking, consensus, or
  biological-correctness verdict anywhere in this project. Full boundary:
  [docs/scientific_interpretation.md](docs/scientific_interpretation.md) ·
  [docs/known_limitations.md](docs/known_limitations.md).

## Documentation

Start at [docs/index.md](docs/index.md) for the full map (Using the plugin, Reference, Scientific
boundaries, Installation and maintenance, Developer/release), grouped by reading path. Most-used
guides directly:

- **Methods**: [docs/scientific_background.md](docs/scientific_background.md) (implementation-backed
  equations and references), [docs/references.bib](docs/references.bib) (full bibliography).
- **Outputs**: [docs/outputs_and_manifests.md](docs/outputs_and_manifests.md),
  [docs/batch_plan_reference.md](docs/batch_plan_reference.md).
- **Troubleshooting**: [docs/troubleshooting.md](docs/troubleshooting.md).
- **Contract and release governance**: [docs/v1.0_contract_freeze.md](docs/v1.0_contract_freeze.md),
  [docs/versioning_policy.md](docs/versioning_policy.md), [docs/release_checklist.md](docs/release_checklist.md).
- **Visual identity**: [docs/visual_identity.md](docs/visual_identity.md) (this README's own design
  conventions, for contributors).

## Installation and compatibility

Download `MembraneVisualQC-0.8.0.zip` and its `.zip.sha256` checksum from the
[v0.8.0 GitHub prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.8.0), verify
the checksum, install through PyMOL Plugin Manager using **clean replacement**, and fully restart
PyMOL. GitHub Releases is the only distribution channel; this project is not published to PyPI.

Primary development and all graphical/manual acceptance to date target **Windows** with **Incentive
PyMOL 3.1.8**; the pure-Python logic is additionally tested cross-platform on `ubuntu-latest` in CI,
but no manual graphical acceptance has been performed on **Linux** or **macOS**, and no other PyMOL
distribution has been manually verified. Full grid and verified upgrade evidence:
[docs/compatibility_matrix.md](docs/compatibility_matrix.md) · [docs/compatibility.md](docs/compatibility.md)
· [docs/upgrade_guide.md](docs/upgrade_guide.md). Every release's exact publication evidence is
frozen and independently re-verified; see [docs/release_checklist.md](docs/release_checklist.md).

<details>
<summary>Source development setup</summary>

```bash
conda env create -f environment.yml
conda activate mvqc
```

Start PyMOL in the checkout root and run `run load_mvqc.py`. Do not execute
`membrane_vqc/commands.py` directly: it is a package module and uses relative imports.

</details>

## Citation and references

Use GitHub's **Cite this repository** action (top of this repository's page, reads `CITATION.cff`)
to cite Membrane Visual QC as software. `CITATION.cff` intentionally names the latest **published**
release (`v0.8.0`), not the untagged `0.9.0.dev0` development line -- cite the exact release version
you used, together with its release URL, not just the repository in general.

Citing this software is not a substitute for citing the source databases/methods an optional
workflow drew on -- cite these separately when that workflow was used:

- **OPM** (comparison mode, OPM side): Lomize et al. 2006, doi:10.1093/bioinformatics/btk023;
  Lomize et al. 2012, doi:10.1093/nar/gkr703.
- **PDBTM** (`pdbtm_local` / `pdbtm_cache` / comparison modes): Tusnády et al. 2005,
  doi:10.1093/nar/gki002; Kozma et al. 2013, doi:10.1093/nar/gks1169.
- **Hydropathy coloring**: Kyte & Doolittle 1982, doi:10.1016/0022-2836(82)90515-0.
- **Solvent-accessibility context**: Shrake & Rupley 1973, doi:10.1016/0022-2836(73)90011-9, and,
  only if the optional FreeSASA reference backend was used, Mitternacht 2016,
  doi:10.12688/f1000research.7931.1.

Full records and exactly what each supports: [docs/references.bib](docs/references.bib) ·
[docs/scientific_background.md#15-references](docs/scientific_background.md#15-references).

<details>
<summary>BibTeX for this software</summary>

```bibtex
@software{membrane_visual_qc_2026,
  title   = {Membrane Visual QC},
  author  = {Trofimchik, Pavel},
  year    = {2026},
  version = {0.8.0},
  url     = {https://github.com/TrPavel/membrane-visual-qc},
  note    = {GitHub prerelease; cite the exact version you used}
}
```

</details>

The implementation is clean-room and does not copy GPL PyMOL plugin code. MIT-licensed (`LICENSE`).

## Development status

Active development: **`0.9.0.dev0`**, reopened after publishing v0.8.0 (a contract-freeze and
documentation-consolidation release -- see [docs/v0.8.0_release_notes.md](docs/v0.8.0_release_notes.md)
and [docs/v1.0_contract_freeze.md](docs/v1.0_contract_freeze.md)). This session's own scope is this
scientific-foundation/README pass; it changes no runtime, scientific, batch, schema, contract, or
cache-format behavior, and does not redesign the plugin GUI itself -- the GUI/UX polish phase is
already merged (`PR #36` visual identity, `PR #37` GUI/UX restructuring). Next: continued hardening
toward a stable v1.0. Full history: [docs/development_state.md](docs/development_state.md) and
[CHANGELOG.md](CHANGELOG.md).
