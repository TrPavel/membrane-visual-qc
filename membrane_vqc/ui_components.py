"""Small, Qt-dependent widget-building helpers used by gui.py and batch_gui.py.

Every function here takes the caller's already-imported ``QtWidgets`` module as a parameter,
matching the lazy-import convention used throughout this package (see ``gui._wrap_scrollable``).
Styling calls are always guarded with ``hasattr`` so these helpers are safe to call from code
paths exercised by this project's fake-Qt test shims (which model only the widget methods each
test actually needs, and do not implement ``setStyleSheet``) -- under a fake shim the call is a
harmless no-op; under real Qt it applies.

Nothing here is a frozen contract: nothing in this module chooses status literals, wording, or
scientific meaning -- it only lays out and colors text that the caller supplies.
"""

from __future__ import annotations

from . import ui_theme


def section_label(QtWidgets, text: str):
    """A bold, ruled label used as a section header inside a QFormLayout."""
    label = QtWidgets.QLabel(text)
    if hasattr(label, "setStyleSheet"):
        label.setStyleSheet(ui_theme.SECTION_TITLE_QSS)
    return label


def helper_label(QtWidgets, text: str):
    """A small, muted, word-wrapping label for one-sentence explanatory text."""
    label = QtWidgets.QLabel(text)
    if hasattr(label, "setWordWrap"):
        label.setWordWrap(True)
    if hasattr(label, "setStyleSheet"):
        label.setStyleSheet(ui_theme.HELPER_TEXT_QSS)
    return label


def style_primary(button) -> None:
    """Mark *button* as this screen's primary action (accent background)."""
    if hasattr(button, "setStyleSheet"):
        button.setStyleSheet(ui_theme.PRIMARY_BUTTON_QSS)


def style_group_title(group_box) -> None:
    """Give a QGroupBox's title the accent color used across the dialog."""
    if hasattr(group_box, "setStyleSheet"):
        group_box.setStyleSheet(ui_theme.GROUP_TITLE_QSS)


def stretch_last_table_section(table, *, section: int | None = None) -> None:
    """Let one table column (default: the last) absorb extra width instead of leaving a gap.

    No-op under a fake test shim (no ``horizontalHeader``) or when the table has no columns.
    """
    header = getattr(table, "horizontalHeader", None)
    if header is None:
        return
    header = header()
    resize_mode = getattr(header, "setSectionResizeMode", None)
    stretch = getattr(header, "Stretch", None)
    if resize_mode is None or stretch is None:
        return
    column_count = getattr(table, "columnCount", None)
    total_columns = column_count() if column_count is not None else 0
    if total_columns <= 0:
        return
    target = total_columns - 1 if section is None else section
    resize_mode(target, stretch)
