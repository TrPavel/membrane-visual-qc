"""Headless PyMOL validation for Membrane Visual QC v0.1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from pymol import cmd

from membrane_vqc.commands import (
    mvqc_check,
    mvqc_color_hydropathy,
    mvqc_ligand_shell,
    mvqc_slab,
    register_commands,
)
import membrane_vqc.gui as gui_module


CASES = [
    ("1UBQ", Path("data/raw/1UBQ.cif"), "1UBQ", "organic"),
    ("1C3W", Path("data/raw/1C3W.cif"), "1C3W", "organic"),
    ("2RH1", Path("data/raw/2RH1.cif"), "2RH1", "organic"),
    ("1PCR", Path("data/raw/1PCR.cif"), "1PCR", "organic"),
    ("bad_core_lys", Path("data/synthetic/bad_core_lys.pdb"), "bad_core_lys", "organic"),
]


def main() -> None:
    register_commands()
    Path("reports").mkdir(exist_ok=True)
    Path("docs/screenshots").mkdir(parents=True, exist_ok=True)
    results = {}

    for label, path, obj_name, ligand in CASES:
        if not path.exists():
            raise SystemExit(f"Missing validation input: {path}")

        cmd.reinitialize()
        register_commands()
        cmd.load(str(path), obj_name)
        cmd.hide("everything", "all")
        cmd.show("cartoon", obj_name)
        cmd.orient(obj_name)

        mvqc_slab(-15, 15)
        report = mvqc_check(
            selection=obj_name,
            zmin=-15,
            zmax=15,
            ligand=ligand,
            cutoff=5.0,
            quiet=1,
            export_path=f"reports/{label.lower()}_mvqc.json",
        )
        mvqc_color_hydropathy(obj_name)
        try:
            mvqc_ligand_shell(protein=obj_name, ligand=ligand, cutoff=5.0)
        except Exception as exc:
            report.setdefault("warnings", []).append(f"Ligand shell display failed: {exc}")

        png_path = Path("docs/screenshots") / f"{label.lower()}_mvqc.png"
        cmd.png(str(png_path), width=1200, height=900, ray=1)

        results[label] = {
            "report": f"reports/{label.lower()}_mvqc.json",
            "screenshot": str(png_path),
            "summary": report["summary"],
            "warnings": report.get("warnings", []),
        }

    bad_summary = results["bad_core_lys"]["summary"]
    if bad_summary["charged_core_residues"] != 1:
        raise AssertionError(
            "bad_core_lys expected exactly one charged-core warning, "
            f"got {bad_summary['charged_core_residues']}"
        )

    gui_status = f"imported {gui_module.__name__}; open not attempted in headless PyMOL"

    validation_summary = {
        "cases": results,
        "gui_status": gui_status,
    }
    Path("reports/validation_summary.json").write_text(
        json.dumps(validation_summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(validation_summary, indent=2, sort_keys=True))


main()
