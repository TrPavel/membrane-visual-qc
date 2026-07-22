"""Import, offline-only, and artifact-exclusion safety for Stage 4C."""

import ast
import os
from pathlib import Path
import subprocess
import sys

from scripts.build_plugin_zip import FORBIDDEN_PROVIDER_PAYLOADS, REQUIRED_PACKAGE_FILES
from scripts.validate_release_artifacts import STAGE4C_RUNTIME_MODULES


ROOT = Path(__file__).resolve().parents[1]
STAGE4C_IMPORTS = (
    "membrane_vqc.opm_adapter",
    "membrane_vqc.orientation_comparison",
    "membrane_vqc.comparison_report",
    "membrane_vqc.comparison_worker",
    "membrane_vqc.comparison_gui_worker",
    "membrane_vqc.comparison_pymol",
)


def test_stage4c_imports_are_socket_free_qt_lazy_and_cache_free(tmp_path):
    cache_root = tmp_path / "must-not-exist"
    imports = "\n".join(f"import {module}" for module in STAGE4C_IMPORTS)
    script = f"""
import socket
import sys

def forbidden_socket(*args, **kwargs):
    raise AssertionError("socket creation during import")

socket.socket = forbidden_socket
{imports}
for forbidden in ("pymol", "PyQt5", "PySide2", "PySide6", "membrane_vqc.gui"):
    assert forbidden not in sys.modules, forbidden
"""
    environment = os.environ.copy()
    environment["MVQC_CACHE_DIR"] = str(cache_root)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert not cache_root.exists()


def test_opm_and_comparison_core_have_no_network_client_imports():
    forbidden_roots = {"http", "httpx", "requests", "socket", "urllib"}
    for relative in (
        "membrane_vqc/opm_adapter.py",
        "membrane_vqc/orientation_comparison.py",
        "membrane_vqc/comparison_report.py",
    ):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert imported.isdisjoint(forbidden_roots), (relative, imported & forbidden_roots)


def test_stage4c_runtime_and_official_opm_exclusion_are_packaging_requirements():
    assert STAGE4C_RUNTIME_MODULES <= REQUIRED_PACKAGE_FILES
    assert (
        801_495,
        "5805025619dafa256cb5508021f3406bb97cd84b4366cf62c98f1b46f5ea5561",
    ) in FORBIDDEN_PROVIDER_PAYLOADS
