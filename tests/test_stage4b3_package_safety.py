"""Stage 4B3 import-boundary safety.

Mirrors ``test_stage4b1_package_safety.py``: proves the new worker
orchestration and Qt glue modules stay importable, and never touch a
network socket or the filesystem cache, purely by being imported -- and that
the Qt-free orchestration module in particular never pulls in PyMOL, Qt, or
the GUI module as a side effect of import.
"""

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_pdbtm_worker_imports_do_not_open_sockets_write_cache_or_import_ui(tmp_path):
    cache_root = tmp_path / "must-not-exist"
    script = r"""
import socket
import sys
import http.client
import ssl

def forbidden_socket(*args, **kwargs):
    raise AssertionError("socket creation during import")

socket.socket = forbidden_socket
import membrane_vqc.pdbtm_worker

for forbidden in ("pymol", "PyQt5", "PySide2", "PySide6", "membrane_vqc.gui",
                  "membrane_vqc.commands", "membrane_vqc.pdbtm_gui_worker"):
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


def test_pdbtm_gui_worker_is_importable_without_any_qt_binding(tmp_path):
    cache_root = tmp_path / "must-not-exist"
    script = r"""
import socket
import sys
import http.client
import ssl

def forbidden_socket(*args, **kwargs):
    raise AssertionError("socket creation during import")

socket.socket = forbidden_socket
import membrane_vqc.pdbtm_gui_worker

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


def test_gui_module_imports_without_qt_installed_and_never_opens_sockets(tmp_path):
    """The GUI module itself must keep Qt fully lazy at import time."""
    cache_root = tmp_path / "must-not-exist"
    script = r"""
import socket
import http.client
import ssl

def forbidden_socket(*args, **kwargs):
    raise AssertionError("socket creation during import")

socket.socket = forbidden_socket
import membrane_vqc.gui
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
