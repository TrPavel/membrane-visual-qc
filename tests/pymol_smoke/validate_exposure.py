"""Headless PyMOL validation and timing for the opt-in Stage 3A exposure path."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from pymol import cmd

from membrane_vqc.context_models import ExposureConfig
from membrane_vqc.qc import run_check


CASES = (
    ("bad_core_lys", Path("data/synthetic/bad_core_lys.pdb")),
    ("1UBQ", Path("data/raw/1UBQ.cif")),
    ("1C3W", Path("data/raw/1C3W.cif")),
    ("2RH1", Path("data/raw/2RH1.cif")),
    ("1PCR", Path("data/raw/1PCR.cif")),
)


def main() -> None:
    output = {}
    config = ExposureConfig()
    for label, source in CASES:
        if not source.is_file():
            raise SystemExit(f"Missing validation input: {source}")
        cmd.reinitialize()
        cmd.load(str(source), label)
        report_path = Path("reports") / f"{label.lower()}_exposure_mvqc.json"
        report = run_check(
            selection=label,
            ligand="organic",
            quiet=1,
            export_path=str(report_path),
            cmd_obj=cmd,
            input_path=str(source),
            exposure_config=config,
        )
        if report["schema_version"] != "1.2":
            raise AssertionError(f"{label} did not produce schema 1.2")
        review_items = report["review_items"]
        if any(item["exposure"]["status"] != "completed" for item in review_items):
            raise AssertionError(f"{label} contains unavailable review-item exposure")
        output[label] = {
            "atoms": cmd.count_atoms(f"({label}) and polymer.protein"),
            "review_items": len(review_items),
            "elapsed_seconds": report["context_analysis"]["exposure"]["elapsed_seconds"],
            "backend": report["context_analysis"]["exposure"]["backend"],
            "report": str(report_path),
            "warnings": report["context_analysis"]["exposure"]["warnings"],
        }

    summary_path = Path("reports/exposure_timing.json")
    summary_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


main()
