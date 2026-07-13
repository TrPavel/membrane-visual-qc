from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))

from pymol import cmd

from membrane_vqc.commands import register_commands


register_commands()
path = Path("data/raw/1UBQ.cif")
if not path.exists():
    raise SystemExit("data/raw/1UBQ.cif is missing")
cmd.load(str(path), "1UBQ")
cmd.do("mvqc_check selection=1UBQ, zmin=-15, zmax=15, ligand=organic, quiet=0")
print("MVQC smoke 1UBQ OK")
