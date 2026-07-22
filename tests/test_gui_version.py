from membrane_vqc.constants import VERSION
from membrane_vqc.gui import DIALOG_TITLE


def test_dialog_title_displays_the_active_release_version():
    assert DIALOG_TITLE == f"Membrane Visual QC {VERSION}"
    assert VERSION == "0.5.0"
