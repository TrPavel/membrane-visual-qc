from types import SimpleNamespace

import pytest

from membrane_vqc import commands, qc
from membrane_vqc import gui
from membrane_vqc.errors import OrientationError


class FakeText:
    def __init__(self, value=""):
        self.value = value
        self.enabled = True

    def text(self):
        return self.value

    def setText(self, value):
        self.value = value

    def setPlainText(self, value):
        self.value = value

    def currentText(self):
        return self.value

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)


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


def pdbtm_dialog():
    dialog = planar_dialog()
    dialog.orientation_mode = FakeText(gui.PDBTM_MODE)
    dialog.pdbtm_json = FakeText("provider.json")
    dialog.transformed_pdb = FakeText("transformed.pdb")
    dialog.biological_assembly = FakeText("1")
    return dialog


def _pdbtm_evidence():
    return {
        "source": {
            "record_id": "test",
            "resource_version": "1017",
            "software_version": "3.2.134",
        },
        "source_geometry": {"upper_offset": 15.0},
        "coordinate_mapping": {
            "method": "identity",
            "metrics": {
                "runtime_identity": {
                    "matched_atom_count": 12,
                    "rmsd": 0.0,
                    "maximum_residual": 0.0,
                }
            },
        },
        "geometric_confidence": "coordinate_verified",
        "warnings": [],
    }


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


def test_pdbtm_gui_run_dispatches_paths_and_renders_source_details(monkeypatch):
    dialog = pdbtm_dialog()
    calls = []
    report = {"orientation": {"evidence": _pdbtm_evidence()}, "summary": {}}
    monkeypatch.setattr(gui, "mvqc_check_pdbtm", lambda **kwargs: calls.append(kwargs) or report)
    monkeypatch.setattr(gui, "format_summary", lambda value: "PDBTM summary")

    dialog.run_qc()

    assert calls == [
        {
            "selection": "1UBQ_rotated",
            "pdbtm_json": "provider.json",
            "transformed_pdb": "transformed.pdb",
            "biological_assembly": "1",
            "ligand": "",
            "cutoff": 5.0,
            "quiet": 1,
            "analyze_context": 0,
            "exposure_quality": "Standard",
            "exposure_backend": "Built-in",
        }
    ]
    assert dialog.orientation_source.value == (
        "PDBTM test \u00b7 identity \u00b7 coordinate verified"
    )
    assert "Matched atoms: 12" in dialog.summary.value
    assert "RMSD: 0 \u00c5" in dialog.summary.value
    assert "Maximum residual: 0 \u00c5" in dialog.summary.value
    assert "Half-thickness: 15 \u00c5" in dialog.summary.value
    assert "not a biological correctness verdict" in dialog.summary.value


def test_failed_pdbtm_gui_run_resets_status_without_traceback(monkeypatch):
    dialog = pdbtm_dialog()
    monkeypatch.setattr(
        gui,
        "mvqc_check_pdbtm",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("COORDINATE_FRAME_MISMATCH: current coordinates do not match")
        ),
    )

    dialog.run_qc()

    assert dialog.orientation_source.value == "unavailable"
    assert "COORDINATE_FRAME_MISMATCH" in dialog.summary.value
    assert "Traceback" not in dialog.summary.value


def test_pdbtm_gui_slab_dispatches_and_renders_import_result(monkeypatch):
    dialog = pdbtm_dialog()
    evidence = SimpleNamespace(as_dict=_pdbtm_evidence)
    imported = SimpleNamespace(evidence=evidence)
    calls = []
    monkeypatch.setattr(
        gui,
        "mvqc_slab_pdbtm",
        lambda **kwargs: calls.append(kwargs) or imported,
    )

    dialog.show_slab()

    assert calls[0]["pdbtm_json"] == "provider.json"
    assert dialog.orientation_source.value.startswith("PDBTM test")
    assert "boundaries updated" in dialog.summary.value


def test_orientation_modes_enable_only_compatible_controls():
    dialog = pdbtm_dialog()
    dialog.zmin = FakeText()
    dialog.zmax = FakeText()
    dialog.browse_pdbtm_json = FakeText()
    dialog.browse_transformed_pdb = FakeText()

    for mode, expected in (
        (gui.LEGACY_MODE, (True, False, False, "manual_global_z")),
        (gui.ORIENTATION_FILE_MODE, (False, True, False, "unavailable")),
        (gui.PDBTM_MODE, (False, False, True, "unavailable")),
    ):
        dialog.orientation_mode.value = mode
        dialog._update_orientation_mode()
        assert (
            dialog.zmin.enabled,
            dialog.orientation_file.enabled,
            dialog.pdbtm_json.enabled,
            dialog.orientation_source.value,
        ) == expected


def test_pdbtm_browse_buttons_assign_only_selected_local_paths():
    paths = iter(
        [
            ("C:/payloads/entry.json", ""),
            ("C:/payloads/entry.pdb", ""),
        ]
    )
    dialog = pdbtm_dialog()
    dialog.QtWidgets = SimpleNamespace(
        QFileDialog=SimpleNamespace(getOpenFileName=lambda *args: next(paths))
    )

    dialog._browse_pdbtm_json()
    dialog._browse_transformed_pdb()

    assert dialog.pdbtm_json.value == "C:/payloads/entry.json"
    assert dialog.transformed_pdb.value == "C:/payloads/entry.pdb"
