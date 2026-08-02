# Quick start

The fastest path from a fresh install to your first result. For the full walkthrough of every
workflow, see [docs/tutorial.md](tutorial.md); for batch jobs, see
[docs/batch_plan_reference.md](batch_plan_reference.md) and
[docs/five_mode_walkthrough.md](five_mode_walkthrough.md).

## Prerequisites

- PyMOL (Incentive PyMOL is the only distribution manually verified so far -- see
  [docs/compatibility_matrix.md](compatibility_matrix.md)).
- The downloaded, checksum-verified `MembraneVisualQC-X.Y.Z.zip` from the
  [releases page](https://github.com/TrPavel/membrane-visual-qc/releases). See
  [README.md](../README.md#installation) for the exact current release.

## 1. Install

1. Verify the ZIP against its `.sha256` sidecar (`Get-FileHash` on Windows, `sha256sum -c` on
   macOS/Linux).
2. In PyMOL: **Plugin > Plugin Manager > Install New Plugin**, select the verified ZIP.
3. **Fully restart PyMOL** (not just the dialog).

If you already have an older version installed, use the recommended clean-replacement method
instead -- see [docs/upgrade_guide.md](upgrade_guide.md).

## 2. Launch

Open **Plugin > Membrane Visual QC**. Confirm the dialog's title shows the version you just
installed, and that there is exactly one entry in the Plugin menu -- see
[docs/troubleshooting.md#installation](troubleshooting.md#installation) if not.

## 3. Select a structure

Load a structure into PyMOL first, the ordinary way:

```pml
load path/to/your_structure.pdb, my_structure
```

## 4. Choose a mode

In the **Single structure** tab, pick one of the five analysis modes (legacy global-z, planar
orientation, PDBTM local, PDBTM cache, or PDBTM-OPM comparison). If you're not sure which one
applies to your data, see [docs/tutorial.md](tutorial.md) -- each mode's section states exactly
what inputs it needs and when to use it. For a first try with no external files, legacy global-z
needs only a selection and a `zmin`/`zmax` range.

## 5. Validate and run

Enter a non-empty selection and, for legacy mode, a finite `zmin < zmax`. Click **Run QC**. A
result appears as flagged residues (if any) plus a summary; this is not a pass/fail grade -- see
[docs/scientific_interpretation.md](scientific_interpretation.md).

## 6. Inspect the result

Read the summary and any `review_items` as prompts for manual inspection, not verdicts. Check
active sites, ion-binding sites, and cofactors before treating a flagged residue as a problem. See
[docs/status_vocabulary.md](status_vocabulary.md) for exactly what each status literal means.

## 7. Export

Click **Export JSON**, or run `mvqc_export path=reports/my_result.json` in the PyMOL command line. This
writes a versioned JSON report and a deterministic CSV companion. See
[docs/report_schema.md](report_schema.md) for the schema, and
[docs/outputs_and_manifests.md](outputs_and_manifests.md) for single-export vs. batch output
layout.

## 8. One minimal batch example

To run more than one job at once, use **Batch review** with a plan file instead of repeating steps
3-7 by hand. The smallest valid plan (one legacy global-z job):

```json
{
  "contract": "mvqc-batch-plan-1.0",
  "jobs": [
    {
      "id": "legacy",
      "input": {"kind": "pymol", "selection": "my_structure"},
      "analysis": {"mode": "legacy_global_z", "zmin": -15.0, "zmax": 15.0},
      "output": {"write_csv": true}
    }
  ],
  "execution": {"failure_policy": "continue_on_error", "overwrite": "refuse"}
}
```

Save it as `my_plan.json`, then either validate it offline:

```bash
python -m membrane_vqc.batch_cli validate my_plan.json
```

or, in **Batch review**: select the plan and an output directory, press **Validate**, then **Run batch**.
For a complete five-mode example with a full narrated walkthrough, see
[docs/five_mode_walkthrough.md](five_mode_walkthrough.md).

## Where to go next

| If you want to... | Read |
|---|---|
| Understand every single-structure mode in depth | [docs/tutorial.md](tutorial.md) |
| Write your own batch plans | [docs/batch_plan_reference.md](batch_plan_reference.md) |
| Understand output files and the result manifest | [docs/outputs_and_manifests.md](outputs_and_manifests.md) |
| Fix an installation or runtime problem | [docs/troubleshooting.md](troubleshooting.md) |
| Understand what a result does and doesn't mean | [docs/scientific_interpretation.md](scientific_interpretation.md) |
| See the full documentation map | [docs/index.md](index.md) |
