"""Load Membrane Visual QC commands from a source checkout in PyMOL.

Plugin Manager installation is the supported primary installation method. For
development, change PyMOL's working directory to this repository and run:

    run load_mvqc.py

Do not run ``membrane_vqc/commands.py`` directly: it is a package module and
uses relative imports by design.
"""

from __future__ import annotations

import sys
from pathlib import Path


# PyMOL's ``run`` executes scripts in its own namespace and may retain PyMOL's
# ``__file__`` value. The documented source workflow therefore starts in the
# checkout root, which is reliable in both GUI and headless PyMOL.
PROJECT_ROOT = Path.cwd().resolve()
if not (PROJECT_ROOT / "membrane_vqc" / "__init__.py").is_file():
    raise RuntimeError(
        "Membrane Visual QC source loader must be run from the repository root. "
        "Use: cd <checkout>; run load_mvqc.py"
    )
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import membrane_vqc  # noqa: E402
from membrane_vqc.commands import register_commands  # noqa: E402


register_commands()
membrane_vqc.__init_plugin__()
