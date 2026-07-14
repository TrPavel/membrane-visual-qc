"""Headless PyMOL validation for legacy and Stage 2 planar workflows."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from pymol import cmd

from membrane_vqc.commands import (
    mvqc_check,
    mvqc_check_orientation,
    mvqc_color_hydropathy,
    mvqc_ligand_shell,
    mvqc_slab,
    register_commands,
)
import membrane_vqc.gui as gui_module
from demo.rotated_1ubq_transform import transform_coordinates


CASES = [
    ("1UBQ", Path("data/raw/1UBQ.cif"), "1UBQ", "organic"),
    ("1C3W", Path("data/raw/1C3W.cif"), "1C3W", "organic"),
    ("2RH1", Path("data/raw/2RH1.cif"), "2RH1", "organic"),
    ("1PCR", Path("data/raw/1PCR.cif"), "1PCR", "organic"),
    ("bad_core_lys", Path("data/synthetic/bad_core_lys.pdb"), "bad_core_lys", "organic"),
]

EXPECTED_SUMMARIES = {
    "1UBQ": (76, 40, 11, 13, 0),
    "1C3W": (222, 147, 11, 30, 88),
    "2RH1": (442, 269, 38, 66, 96),
    "1PCR": (823, 176, 43, 33, 241),
    "bad_core_lys": (10, 10, 1, 0, 0),
}


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
        if not png_path.exists():
            cmd.png(str(png_path), width=1200, height=900, ray=1)

        results[label] = {
            "report": f"reports/{label.lower()}_mvqc.json",
            "screenshot": str(png_path),
            "summary": report["summary"],
            "warnings": report.get("warnings", []),
        }
        summary_tuple = tuple(
            report["summary"][field]
            for field in (
                "total_residues",
                "core_residues",
                "charged_core_residues",
                "polar_core_inspect_residues",
                "ligand_neighbour_residues",
            )
        )
        if summary_tuple != EXPECTED_SUMMARIES[label]:
            raise AssertionError(
                f"{label} legacy regression: expected {EXPECTED_SUMMARIES[label]}, got {summary_tuple}"
            )

    bad_summary = results["bad_core_lys"]["summary"]
    if bad_summary["charged_core_residues"] != 1:
        raise AssertionError(
            "bad_core_lys expected exactly one charged-core warning, "
            f"got {bad_summary['charged_core_residues']}"
        )

    cmd.reinitialize()
    register_commands()
    source_path = Path("data/raw/1UBQ.cif")
    cmd.load(str(source_path), "1UBQ_rotated")
    coordinates = cmd.get_coords("1UBQ_rotated", state=1)
    cmd.load_coords(transform_coordinates(coordinates), "1UBQ_rotated", state=1)
    rotated_report = mvqc_check_orientation(
        selection="1UBQ_rotated",
        orientation_file="demo/rotated_1ubq_orientation.json",
        ligand="organic",
        cutoff=5.0,
        quiet=1,
        export_path="reports/1ubq_rotated_mvqc.json",
        input_path=str(source_path),
    )
    baseline_summary = results["1UBQ"]["summary"]
    if rotated_report["summary"] != baseline_summary:
        raise AssertionError(
            "Rigidly transformed 1UBQ did not preserve the legacy summary: "
            f"baseline={baseline_summary}, rotated={rotated_report['summary']}"
        )
    rotated_png = Path("docs/screenshots/1ubq_rotated_mvqc.png")
    cmd.png(str(rotated_png), width=1200, height=900, ray=1)
    results["1UBQ_rotated"] = {
        "report": "reports/1ubq_rotated_mvqc.json",
        "screenshot": str(rotated_png),
        "summary": rotated_report["summary"],
        "warnings": rotated_report.get("warnings", []),
        "equivalent_to": "1UBQ",
        "transform": {
            "rotation_matrix_row_major": [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]],
            "translation": [10.0, -5.0, 3.0],
            "orientation_normal": [1.0, 0.0, 0.0],
        },
    }

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
