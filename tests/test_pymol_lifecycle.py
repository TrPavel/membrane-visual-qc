import pytest

from membrane_vqc.pymol_adapter import (
    MVQC_NAMES,
    MVQC_SLAB_NAMES,
    apply_review_style,
    clear_owned,
    clear_slab,
    show_ligand_shell,
)
from membrane_vqc import commands, qc


class FakeCmd:
    def __init__(self, names=()):
        self.names = set(names)
        self.deleted = []
        self.selected = []
        self.shown = []
        self.colored = []

    def delete(self, name):
        self.deleted.append(name)
        self.names.discard(name)

    def get_names(self, mode):
        assert mode == "all"
        return sorted(self.names)

    def select(self, name, expression):
        self.names.add(name)
        self.selected.append((name, expression))

    def show(self, representation, selection):
        self.shown.append((representation, selection))

    def color(self, color, selection):
        self.colored.append((color, selection))


def test_clear_owned_deletes_exactly_central_owned_names():
    cmd = FakeCmd({"user_object", *MVQC_NAMES})

    clear_owned(cmd)

    assert cmd.deleted == sorted(MVQC_NAMES)
    assert "user_object" in cmd.names


def test_clear_slab_deletes_only_boundary_objects():
    cmd = FakeCmd({"user_object", *MVQC_NAMES})

    clear_slab(cmd)

    assert cmd.deleted == list(MVQC_SLAB_NAMES)
    assert "user_object" in cmd.names
    assert "mvqc_core_charged" in cmd.names


def test_review_style_is_applied_after_ligand_context_colors():
    cmd = FakeCmd({"mvqc_core_charged", "mvqc_core_polar_inspect"})

    show_ligand_shell("protein", "organic", [], cmd)

    assert cmd.colored[-2:] == [
        ("orange", "mvqc_core_charged"),
        ("yellow", "mvqc_core_polar_inspect"),
    ]


def test_empty_ligand_only_clears_owned_ligand_context():
    cmd = FakeCmd({"user_object", "mvqc_ligand", "mvqc_ligand_shell"})

    show_ligand_shell("protein", "  ", [], cmd)

    assert cmd.deleted == ["mvqc_ligand", "mvqc_ligand_shell"]
    assert cmd.selected == []
    assert "user_object" in cmd.names


def test_review_style_is_noop_before_review_selections_exist():
    cmd = FakeCmd({"user_object"})

    apply_review_style(cmd)

    assert cmd.shown == []
    assert cmd.colored == []


def test_mvqc_clear_resets_visuals_and_last_report(monkeypatch):
    called = []
    monkeypatch.setattr(commands, "clear_owned", lambda: called.append(True))
    qc.LAST_REPORT = {"summary": {}}

    names = commands.mvqc_clear()

    assert called == [True]
    assert qc.LAST_REPORT is None
    assert names == sorted(MVQC_NAMES)


def test_register_commands_includes_clear():
    registered = {}

    class Registry:
        def extend(self, name, callback):
            registered[name] = callback

    commands.register_commands(Registry())

    assert registered["mvqc_clear"] is commands.mvqc_clear


def test_mvqc_check_forwards_explicit_input_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(commands, "clear_owned", lambda: None)

    def fake_run_check(*args, **kwargs):
        captured.update(kwargs)
        return {"summary": {}}

    monkeypatch.setattr(qc, "run_check", fake_run_check)

    commands.mvqc_check(selection="all", input_path=" data/model.cif ")

    assert captured["input_path"] == "data/model.cif"


def test_failed_orientation_check_clears_previous_visuals_and_report(monkeypatch):
    cleared = []
    monkeypatch.setattr(commands, "clear_owned", lambda: cleared.append("all"))
    monkeypatch.setattr(
        commands,
        "load_orientation_file",
        lambda path: (_ for _ in ()).throw(ValueError(f"invalid orientation file: {path}")),
    )
    qc.LAST_REPORT = {"orientation": {"source": "stale"}}

    with pytest.raises(ValueError, match="invalid orientation file"):
        commands.mvqc_check_orientation(orientation_file="missing.json")

    assert cleared == ["all", "all"]
    assert qc.LAST_REPORT is None


def test_failed_orientation_slab_clears_previous_slab_objects(monkeypatch):
    cleared = []
    monkeypatch.setattr(commands, "clear_slab", lambda: cleared.append("slab"))
    monkeypatch.setattr(
        commands,
        "load_orientation_file",
        lambda path: (_ for _ in ()).throw(ValueError(f"invalid orientation file: {path}")),
    )

    with pytest.raises(ValueError, match="invalid orientation file"):
        commands.mvqc_slab_orientation(orientation_file="missing.json")

    assert cleared == ["slab", "slab"]
