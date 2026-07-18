from types import SimpleNamespace

import pytest

from membrane_vqc import commands, qc
from membrane_vqc import gui
from membrane_vqc.errors import OrientationError


class FakeText:
    def __init__(self, value=""):
        self.value = value

    def text(self):
        return self.value

    def setText(self, value):
        self.value = value

    def setPlainText(self, value):
        self.value = value

    def currentText(self):
        return self.value


class FakeCheck:
    def __init__(self, checked):
        self.checked = checked

    def isChecked(self):
        return self.checked


def planar_dialog():
    dialog = object.__new__(gui.MembraneVQCDialog)
    dialog.QtWidgets = SimpleNamespace()
    dialog.window = object()
    dialog.action_buttons = []
    dialog.orientation_mode = FakeText(gui.ORIENTATION_FILE_MODE)
    dialog.orientation_file = FakeText("demo/rotated_1ubq_orientation.json")
    dialog.orientation_source = FakeText("stale_source")
    dialog.selection = FakeText("1UBQ_rotated")
    dialog.ligand = FakeText("")
    dialog.cutoff = FakeText("5")
    dialog.summary = FakeText()
    return dialog


def test_export_before_analysis_raises_clear_error():
    previous = qc.LAST_REPORT
    qc.LAST_REPORT = None
    try:
        with pytest.raises(RuntimeError, match="Run mvqc_check first"):
            commands.mvqc_export("unused.json")
    finally:
        qc.LAST_REPORT = previous


def test_successful_planar_gui_run_displays_returned_orientation_source(monkeypatch):
    dialog = planar_dialog()
    report = {"orientation": {"source": "synthetic_rigid_transform"}, "summary": {}}
    calls = []

    def run_orientation(**kwargs):
        calls.append(kwargs)
        return report

    monkeypatch.setattr(gui, "mvqc_check_orientation", run_orientation)
    monkeypatch.setattr(gui, "format_summary", lambda value: "planar summary")

    dialog.run_qc()

    assert dialog.orientation_source.value == "synthetic_rigid_transform"
    assert dialog.summary.value == "planar summary"
    assert len(calls) == 1


def test_gui_forwards_compact_context_controls(monkeypatch):
    dialog = planar_dialog()
    dialog.analyze_context = FakeCheck(True)
    dialog.exposure_quality = FakeText("High")
    dialog.exposure_backend = FakeText("Auto")
    calls = []
    monkeypatch.setattr(
        gui,
        "mvqc_check_orientation",
        lambda **kwargs: calls.append(kwargs) or {"orientation": {"source": "test"}, "summary": {}},
    )
    monkeypatch.setattr(gui, "format_summary", lambda value: "summary")

    dialog.run_qc()

    assert calls[0]["analyze_context"] == 1
    assert calls[0]["exposure_quality"] == "High"
    assert calls[0]["exposure_backend"] == "Auto"


def test_failed_planar_gui_run_replaces_previous_source_and_shows_readable_error(monkeypatch):
    dialog = planar_dialog()
    results = iter(
        [
            {"orientation": {"source": "synthetic_rigid_transform"}, "summary": {}},
            OrientationError("could not read orientation file missing.json"),
        ]
    )

    def run_orientation(**kwargs):
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(gui, "mvqc_check_orientation", run_orientation)
    monkeypatch.setattr(gui, "format_summary", lambda value: "planar summary")

    dialog.run_qc()
    assert dialog.orientation_source.value == "synthetic_rigid_transform"

    dialog.orientation_file.value = "missing.json"
    dialog.run_qc()

    assert dialog.orientation_source.value == "unavailable"
    assert "could not read orientation file missing.json" in dialog.summary.value
    assert "Traceback" not in dialog.summary.value


def test_successful_planar_gui_slab_displays_command_source(monkeypatch):
    dialog = planar_dialog()
    monkeypatch.setattr(
        gui,
        "mvqc_slab_orientation",
        lambda selection, path: {"source": "synthetic_rigid_transform"},
    )

    dialog.show_slab()

    assert dialog.orientation_source.value == "synthetic_rigid_transform"
    assert dialog.summary.value == "Planar membrane boundaries updated."


def test_failed_planar_gui_slab_replaces_previous_source(monkeypatch):
    dialog = planar_dialog()
    monkeypatch.setattr(
        gui,
        "mvqc_slab_orientation",
        lambda selection, path: (_ for _ in ()).throw(OrientationError("invalid orientation")),
    )

    dialog.show_slab()

    assert dialog.orientation_source.value == "unavailable"
    assert "invalid orientation" in dialog.summary.value
    assert "Traceback" not in dialog.summary.value
