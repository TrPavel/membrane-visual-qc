"""Prepare the validated rotated 1UBQ fixture in a graphical PyMOL session."""

from __future__ import annotations

import inspect
from pathlib import Path
from runpy import run_path

from pymol import cmd


# PyMOL's ``run`` executes in its shared namespace and may retain PyMOL's own ``__file__``.
# Prefer this module's ``__file__`` and use the executing code filename for that PyMOL-only case.
SCRIPT_PATH = Path(__file__)
if SCRIPT_PATH.name != "prepare_rotated_1ubq.py":
    SCRIPT_PATH = Path(inspect.currentframe().f_code.co_filename)
SCRIPT_PATH = SCRIPT_PATH.resolve()
REPOSITORY_ROOT = SCRIPT_PATH.parents[1]
DEMO_DIRECTORY = SCRIPT_PATH.parent

OBJECT_NAME = "1UBQ_rotated"
SOURCE_PATH = REPOSITORY_ROOT / "data" / "raw" / "1UBQ.cif"
ORIENTATION_PATH = REPOSITORY_ROOT / "demo" / "rotated_1ubq_orientation.json"


def main() -> None:
    """Load, transform, and display only the rotated validation object."""
    transform_coordinates = run_path(str(DEMO_DIRECTORY / "rotated_1ubq_transform.py"))[
        "transform_coordinates"
    ]

    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(f"Rotated 1UBQ source file is missing: {SOURCE_PATH}")
    if not ORIENTATION_PATH.is_file():
        raise FileNotFoundError(f"Orientation file is missing: {ORIENTATION_PATH}")

    cmd.delete(OBJECT_NAME)
    cmd.load(str(SOURCE_PATH), OBJECT_NAME)
    coordinates = cmd.get_coords(OBJECT_NAME, state=1)
    if coordinates is None:
        raise RuntimeError(f"PyMOL returned no coordinates for {OBJECT_NAME}")
    cmd.load_coords(transform_coordinates(coordinates), OBJECT_NAME, state=1)
    cmd.hide("everything", OBJECT_NAME)
    cmd.show("cartoon", OBJECT_NAME)
    cmd.orient(OBJECT_NAME)
    cmd.zoom(OBJECT_NAME)
    print(f"Rotated 1UBQ orientation JSON: {ORIENTATION_PATH.resolve()}")


main()
