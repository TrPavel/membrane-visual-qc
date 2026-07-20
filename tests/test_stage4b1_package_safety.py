import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_stage4b1_imports_do_not_open_sockets_write_cache_or_import_ui(tmp_path):
    cache_root = tmp_path / "must-not-exist"
    script = r"""
import socket
import sys
import http.client
import ssl

def forbidden_socket(*args, **kwargs):
    raise AssertionError("socket creation during import")

socket.socket = forbidden_socket
import membrane_vqc
import membrane_vqc.pdbtm_cache_contract
import membrane_vqc.pdbtm_errors
import membrane_vqc.pdbtm_provider
import membrane_vqc.pdbtm_retrieval
import membrane_vqc.pdbtm_transport
import membrane_vqc.pdbtm_cache

for forbidden in ("pymol", "PyQt5", "PySide2", "PySide6", "membrane_vqc.gui", "membrane_vqc.commands", "membrane_vqc.report", "membrane_vqc.pdbtm_pymol"):
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
