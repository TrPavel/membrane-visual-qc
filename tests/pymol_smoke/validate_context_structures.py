"""Headless PyMOL Stage 3B context validation and timing on retained structures."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))

from pymol import cmd

from membrane_vqc.context_models import ExposureConfig, LocalContextConfig
from membrane_vqc.qc import run_check

CASES = (
    ("bad_core_lys", Path("data/synthetic/bad_core_lys.pdb")),
    ("1UBQ", Path("data/raw/1UBQ.cif")),
    ("1C3W", Path("data/raw/1C3W.cif")),
    ("2RH1", Path("data/raw/2RH1.cif")),
    ("1PCR", Path("data/raw/1PCR.cif")),
)
EXPECTED = {
    "bad_core_lys": (10, 10, 1, 0, 0),
    "1UBQ": (76, 40, 11, 13, 0),
    "1C3W": (222, 147, 11, 30, 88),
    "2RH1": (442, 269, 38, 66, 96),
    "1PCR": (823, 176, 43, 33, 241),
}


def main() -> None:
    results = {}
    for label, source in CASES:
        cmd.reinitialize()
        cmd.load(str(source), label)
        report = run_check(
            selection=label,
            ligand="organic",
            quiet=1,
            export_path=f"reports/{label.lower()}_context_mvqc.json",
            input_path=str(source),
            cmd_obj=cmd,
            exposure_config=ExposureConfig(target_scope="review_items"),
            local_context_config=LocalContextConfig(),
        )
        summary = report["summary"]
        observed = tuple(
            summary[field]
            for field in (
                "total_residues",
                "core_residues",
                "charged_core_residues",
                "polar_core_inspect_residues",
                "ligand_neighbour_residues",
            )
        )
        if observed != EXPECTED[label]:
            raise AssertionError(f"{label} legacy summary changed: {observed}")
        metadata = report["context_analysis"]
        results[label] = {
            "review_items": len(report["review_items"]),
            "context_state_counts": summary["context_state_counts"],
            "exposure_seconds": metadata["exposure"]["elapsed_seconds"],
            "local_context_seconds": metadata["local_context"]["elapsed_seconds"],
            "report": f"reports/{label.lower()}_context_mvqc.json",
        }
    Path("reports/context_timing.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2, sort_keys=True))


main()
