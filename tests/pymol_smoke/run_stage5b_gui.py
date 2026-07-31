"""Real Qt/PyMOL Stage 5B smoke: pymol -cq this_file.py -- PLAN OUTPUT_BASE."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import sys
import time
import urllib.request

from pymol import cmd
from pymol.Qt import QtCore, QtGui, QtWidgets

import membrane_vqc
from membrane_vqc.batch_contracts import identity_core_sha256, load_result
from membrane_vqc.batch_gui import CANCELLED, COMPLETED
from membrane_vqc.batch_executor import run_pymol_batch
from membrane_vqc.gui import MembraneVQCDialog


def _arguments() -> tuple[Path, Path, Path | None]:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    if len(values) not in {2, 3}:
        raise SystemExit("usage: run_stage5b_gui.py -- PLAN.json OUTPUT_BASE [PACKAGE_ROOT]")
    expected_root = Path(values[2]).resolve() if len(values) == 3 else None
    return Path(values[0]).absolute(), Path(values[1]).absolute(), expected_root


def _deny_network(*_args, **_kwargs):
    raise AssertionError("Stage 5B attempted network access")


def _drive_until(predicate, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("Qt smoke timed out")
        QtWidgets.QApplication.processEvents()
        time.sleep(0.001)


def _prepare(dialog: MembraneVQCDialog, plan: Path, output: Path) -> None:
    panel = dialog.batch_panel
    assert panel is not None
    panel.cmd_obj = cmd
    panel.plan_path.setText(str(plan))
    panel.validate_selected_plan()
    assert panel.state == "READY"
    assert panel.queue.rowCount() == 5
    panel.output_path.setText(str(output))


def _manifest(output: Path):
    result, _ = load_result(output / "batch-result.json")
    assert result["identity_core_sha256"] == identity_core_sha256(result)
    return result


plan_path, output_base, expected_package_root = _arguments()
if expected_package_root is not None:
    assert Path(membrane_vqc.__file__).resolve().is_relative_to(expected_package_root)
output_base.mkdir(parents=True, exist_ok=True)
socket.socket = _deny_network
socket.create_connection = _deny_network
socket.getaddrinfo = _deny_network
socket.gethostbyname = _deny_network
socket.gethostbyname_ex = _deny_network
socket.gethostbyaddr = _deny_network
urllib.request.urlopen = _deny_network

application = QtWidgets.QApplication.instance()
if application is None:
    application = QtWidgets.QApplication([])

dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
dialog.show()
QtWidgets.QApplication.processEvents()
assert dialog.tabs is not None
assert dialog.tabs.count() == 2
assert dialog.tabs.tabText(1) == "Batch review"
assert dialog.batch_panel is not None
assert dialog.batch_panel.state == "IDLE"
assert not dialog.batch_panel.run_button.isEnabled()
assert not dialog.batch_panel.cancel_button.isEnabled()
assert len(dialog.batch_panel.history) == 0

heartbeat = {"count": 0}
heartbeat_timer = QtCore.QTimer()
heartbeat_timer.timeout.connect(lambda: heartbeat.__setitem__("count", heartbeat["count"] + 1))
heartbeat_timer.start(1)

complete_root = output_base / "complete"
_prepare(dialog, plan_path, complete_root)
dialog.batch_panel.run_batch()
_drive_until(lambda: dialog.batch_panel.session is None)
assert dialog.batch_panel.state == COMPLETED
complete_result = _manifest(complete_root)
assert len(complete_result["jobs"]) == 5
assert all(item["coordinate_preserved"] is True for item in complete_result["jobs"])
assert heartbeat["count"] > 0

sync_root = output_base / "synchronous"
sync_result = run_pymol_batch(plan_path, sync_root, cmd_obj=cmd)
assert sync_result["identity_core_sha256"] == complete_result["identity_core_sha256"]

cancel_root = output_base / "cancel"
dialog.batch_panel.plan_path.setText(str(plan_path))
dialog.batch_panel.validate_selected_plan()
dialog.batch_panel.output_path.setText(str(cancel_root))
cancelled = {"requested": False}


def _cancel_after_first():
    if dialog.batch_panel.progress.value() >= 1 and not cancelled["requested"]:
        cancelled["requested"] = True
        dialog.batch_panel.cancel_batch()


dialog.batch_panel.timer.timeout.connect(_cancel_after_first)
dialog.batch_panel.run_batch()
_drive_until(lambda: dialog.batch_panel.session is None)
assert cancelled["requested"]
assert dialog.batch_panel.state == CANCELLED
cancel_result = _manifest(cancel_root)
assert cancel_result["jobs"][0]["coordinate_preserved"] is True
assert all(item["status"] == "CANCELLED" for item in cancel_result["jobs"][1:])

close_root = output_base / "close"
dialog.batch_panel.plan_path.setText(str(plan_path))
dialog.batch_panel.validate_selected_plan()
dialog.batch_panel.output_path.setText(str(close_root))
closed = {"done": False}


def _close_after_first():
    if dialog.batch_panel.progress.value() >= 1 and not closed["done"]:
        closed["done"] = True
        dialog.window.close()


dialog.batch_panel.timer.timeout.connect(_close_after_first)
dialog.batch_panel.run_batch()
_drive_until(lambda: dialog.batch_panel.session is None)
assert closed["done"]
close_result = _manifest(close_root)
assert close_result["overall_status"] == "CANCELLED"
dialog.show()
QtWidgets.QApplication.processEvents()
dialog.window.close()
QtWidgets.QApplication.processEvents()

# Retain one direct existing single-structure workflow and coordinate check.
single_input = plan_path.parent / "pdbtm_original_test.pdb"
cmd.load(str(single_input), "stage5b_single_smoke")
before = tuple(tuple(atom.coord) for atom in cmd.get_model("stage5b_single_smoke").atom)
dialog = MembraneVQCDialog(QtWidgets, QtGui, QtCore)
dialog.selection.setText("stage5b_single_smoke")
dialog.run_qc()
after = tuple(tuple(atom.coord) for atom in cmd.get_model("stage5b_single_smoke").atom)
assert before == after
assert str(dialog.summary.toPlainText()).strip()
dialog.window.close()
heartbeat_timer.stop()

print(
    json.dumps(
        {
            "complete_identity_core": complete_result["identity_core_sha256"],
            "complete_status": complete_result["overall_status"],
            "cancel_status": cancel_result["overall_status"],
            "close_status": close_result["overall_status"],
            "coordinates_preserved": True,
            "heartbeat_events": heartbeat["count"],
            "network": "DENIED",
            "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            "package_root_verified": expected_package_root is not None,
            "qt": QtCore.QT_VERSION_STR,
            "synchronous_identity_match": True,
        },
        sort_keys=True,
    )
)
