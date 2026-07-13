"""Membrane Visual QC PyMOL plugin package."""

from .constants import VERSION

__version__ = VERSION
_MENU_REGISTERED = False


def __init_plugin__(app=None):
    """Register the Qt menu entry when loaded as a PyMOL plugin."""
    global _MENU_REGISTERED
    if _MENU_REGISTERED:
        return
    try:
        from pymol.plugins import QtNotAvailableError, addmenuitemqt
    except ModuleNotFoundError as exc:
        if exc.name == "pymol" or (exc.name or "").startswith("pymol."):
            return
        raise
    except ImportError:
        return

    from .gui import show_dialog

    try:
        addmenuitemqt("Membrane Visual QC", show_dialog)
    except QtNotAvailableError:
        # Headless PyMOL exposes the plugin module but has no Qt menu.
        return
    _MENU_REGISTERED = True
