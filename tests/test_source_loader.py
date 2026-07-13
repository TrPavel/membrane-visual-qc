import runpy
import sys
import types


class FakeCmd:
    def __init__(self):
        self.registered = []

    def extend(self, name, function):
        self.registered.append(name)


def test_source_loader_registers_commands_through_package_import(monkeypatch):
    fake_cmd = FakeCmd()
    fake_pymol = types.ModuleType("pymol")
    fake_pymol.cmd = fake_cmd
    fake_plugins = types.ModuleType("pymol.plugins")
    fake_plugins.QtNotAvailableError = RuntimeError
    fake_plugins.addmenuitemqt = lambda *_args: None
    monkeypatch.setitem(sys.modules, "pymol", fake_pymol)
    monkeypatch.setitem(sys.modules, "pymol.plugins", fake_plugins)
    sys.modules.pop("membrane_vqc.commands", None)

    runpy.run_path("load_mvqc.py")

    assert {
        "mvqc_check",
        "mvqc_slab",
        "mvqc_color_hydropathy",
        "mvqc_ligand_shell",
        "mvqc_export",
        "mvqc_clear",
    }.issubset(fake_cmd.registered)
