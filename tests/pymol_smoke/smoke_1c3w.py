from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))

from pymol import cmd

from membrane_vqc.commands import register_commands


register_commands()
path = Path("data/raw/1C3W.cif")
if not path.exists():
    raise SystemExit("data/raw/1C3W.cif is missing")
cmd.load(str(path), "1C3W")
cmd.do(
    "mvqc_check selection=1C3W, zmin=-15, zmax=15, ligand=organic, quiet=0, "
    "export_path=reports/1c3w_mvqc.json"
)
print("MVQC smoke 1C3W OK")
