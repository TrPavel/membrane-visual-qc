from __future__ import annotations

from types import ModuleType, SimpleNamespace
import sys

from membrane_vqc.comparison_pymol import (
    capture_comparison_snapshot,
    clear_comparison_boundaries,
    comparison_snapshot_is_current,
    show_comparison_boundaries,
)
from membrane_vqc.orientation import PlanarMembrane
from membrane_vqc.pymol_adapter import MVQC_COMPARISON_NAMES, MVQC_NAMES


class FakeCmd:
    def __init__(self, pdb_text):
        self.pdb_text = pdb_text
        self.deleted = []
        self.loaded = []
        self.centered = []
        self.zoomed = []
        self.atom = SimpleNamespace(
            model="protein",
            chain="A",
            resi="1",
            resn="ALA",
            name="CA",
            alt="",
            q=1.0,
            coord=(0.0, 0.0, 0.0),
            symbol="C",
        )

    def get_object_list(self, selection):
        return ["protein"]

    def count_states(self, object_name):
        return 1

    def get_model(self, selection, state=1):
        return SimpleNamespace(atom=[self.atom])

    def get_pdbstr(self, selection, state=1):
        return self.pdb_text

    def delete(self, name):
        self.deleted.append(name)

    def load_cgo(self, payload, name):
        self.loaded.append((name, payload))

    def center(self, selection):
        self.centered.append(selection)

    def zoom(self, selection):
        self.zoomed.append(selection)


def _install_fake_cgo(monkeypatch):
    pymol = ModuleType("pymol")
    cgo = ModuleType("pymol.cgo")
    for index, name in enumerate(
        ("ALPHA", "BEGIN", "COLOR", "END", "NORMAL", "TRIANGLES", "VERTEX"), start=1
    ):
        setattr(cgo, name, index)
    pymol.cgo = cgo
    monkeypatch.setitem(sys.modules, "pymol", pymol)
    monkeypatch.setitem(sys.modules, "pymol.cgo", cgo)


def _membrane(source, center=(0.0, 0.0, 0.0)):
    return PlanarMembrane(center, (0.0, 0.0, 1.0), -10.0, 10.0, 0.0, source)


def test_comparison_names_are_globally_owned_but_separate_from_standard_slab():
    assert set(MVQC_COMPARISON_NAMES) <= MVQC_NAMES
    assert not {"mvqc_slab_lower", "mvqc_slab_upper"} & set(MVQC_COMPARISON_NAMES)


def test_clear_comparison_deletes_only_four_comparison_objects():
    cmd = FakeCmd("ATOM\n")

    clear_comparison_boundaries(cmd)

    assert cmd.deleted == list(MVQC_COMPARISON_NAMES)


def test_show_comparison_uses_four_distinct_names_and_preserves_coordinates(monkeypatch):
    _install_fake_cgo(monkeypatch)
    cmd = FakeCmd(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n"
    )
    snapshot = capture_comparison_snapshot("protein", cmd_obj=cmd)
    before = cmd.atom.coord

    show_comparison_boundaries(
        _membrane("pdbtm"),
        _membrane("opm", center=(1.0, 0.0, 0.0)),
        snapshot,
        "protein",
        cmd_obj=cmd,
    )

    assert [name for name, _ in cmd.loaded] == list(MVQC_COMPARISON_NAMES)
    assert cmd.atom.coord == before
    assert "mvqc_slab_lower" not in cmd.deleted
    assert "mvqc_slab_upper" not in cmd.deleted
    assert cmd.centered == ["protein"]
    assert cmd.zoomed == ["protein"]


def test_snapshot_fingerprint_detects_coordinate_payload_change():
    cmd = FakeCmd(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n"
    )
    snapshot = capture_comparison_snapshot("protein", cmd_obj=cmd)
    assert comparison_snapshot_is_current(snapshot, "protein", cmd_obj=cmd)

    cmd.pdb_text = cmd.pdb_text.replace("   0.000   0.000   0.000", "   1.000   0.000   0.000")

    assert not comparison_snapshot_is_current(snapshot, "protein", cmd_obj=cmd)
