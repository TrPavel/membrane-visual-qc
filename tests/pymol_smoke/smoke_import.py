import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from membrane_vqc.commands import register_commands


register_commands()
print("MVQC smoke import OK")
