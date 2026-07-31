"""Headless PyMOL entrypoint: pymol -cq this_file.py -- PLAN OUTPUT_DIR."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from pymol import cmd

from membrane_vqc.batch_executor import run_pymol_batch


def _arguments() -> tuple[str, str]:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    if len(arguments) != 2:
        raise SystemExit("usage: run_batch_plan.py -- PLAN.json OUTPUT_DIR")
    return arguments[0], arguments[1]


plan, output = _arguments()
result = run_pymol_batch(plan, output, cmd_obj=cmd)
print(
    json.dumps(
        {"manifest": str(Path(output) / "batch-result.json"), "status": result["overall_status"]},
        sort_keys=True,
    )
)
