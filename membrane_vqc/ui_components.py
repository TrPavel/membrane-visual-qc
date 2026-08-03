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


def mode_container(QtWidgets, parent_layout):
    """A plain QWidget with a zero-margin QFormLayout, meant to hold one mode/state's fields.

    Showing/hiding this *whole container* (``container.setVisible(...)``) -- rather than
    individual QFormLayout rows within one shared form -- is the only approach confirmed to
    fully collapse unused vertical space against this project's exact PyQt5 5.15.11/Qt 5.15.15
    build: hiding a row's widgets alone leaves that row's inter-row spacing reserved (there is no
    ``QFormLayout.setRowVisible`` before Qt 6.4), and with several such rows hidden at once the
    residual spacing becomes a visible gap. A hidden QWidget contributes neither size nor spacing
    to its parent QVBoxLayout, so stacking one small container per mode/state and toggling whole
    containers avoids the problem entirely. Returns ``(container, form_layout)``; the caller
    populates *form_layout* and adds *container* to *parent_layout*.
    """
    container = QtWidgets.QWidget()
    form = QtWidgets.QFormLayout(container)
    if hasattr(form, "setContentsMargins"):
        form.setContentsMargins(0, 0, 0, 0)
    if hasattr(parent_layout, "addWidget"):
        parent_layout.addWidget(container)
    return container, form


def make_collapsible_group(QtWidgets, title: str, *, checked: bool = True):
    """A QGroupBox that shows/hides its content as a unit via a checkable title.

    Returns ``(group_box, content_widget)`` -- populate *content_widget* with your own layout
    (e.g. ``QtWidgets.QFormLayout(content_widget)``); everything in it appears/disappears
    together when the group's checkbox is toggled. Falls back to an always-expanded, non-
    collapsible group under a fake test shim (no ``setCheckable``/``toggled``) or when *QtWidgets*
    has no ``QVBoxLayout``.
    """
    group_box = QtWidgets.QGroupBox(title)
    content_widget = QtWidgets.QWidget(group_box)
    if hasattr(QtWidgets, "QVBoxLayout"):
        outer_layout = QtWidgets.QVBoxLayout(group_box)
        outer_layout.addWidget(content_widget)
    if hasattr(group_box, "setCheckable") and hasattr(group_box, "toggled"):
        group_box.setCheckable(True)
        group_box.setChecked(checked)
        group_box.toggled.connect(content_widget.setVisible)
    if hasattr(content_widget, "setVisible"):
        content_widget.setVisible(checked)
    return group_box, content_widget


def empty_state_placeholder(widget, text: str) -> None:
    """Set placeholder text shown only while *widget* (a QTextEdit/QLineEdit-like field) is
    empty, so an unused text area reads as an intentional empty state rather than a blank
    rectangle. No-op under a fake test shim (no ``setPlaceholderText``)."""
    if hasattr(widget, "setPlaceholderText"):
        widget.setPlaceholderText(text)


def cap_height(widget, maximum: int, *, minimum: int | None = None) -> None:
    """Bound *widget*'s height so a text/result area cannot grow into a dominant blank region.

    The widget keeps its own internal scrollbar for content taller than *maximum* -- this only
    changes how much empty space it claims when there is little or nothing to show.
    """
    if hasattr(widget, "setMaximumHeight"):
        widget.setMaximumHeight(maximum)
    if minimum is not None and hasattr(widget, "setMinimumHeight"):
        widget.setMinimumHeight(minimum)


def empty_state_label(QtWidgets, text: str):
    """A muted, italicized one-line label for an empty-state banner (e.g. an empty table)."""
    label = helper_label(QtWidgets, text)
    if hasattr(label, "setStyleSheet"):
        label.setStyleSheet(ui_theme.HELPER_TEXT_QSS + " font-style: italic;")
    return label


def metadata_grid(QtWidgets, pairs):
    """A compact label:value grid for a handful of short metadata facts.

    Uses ``QGridLayout`` (two columns per fact, wrapping to a new grid row every two facts) when
    available; falls back to one ``QFormLayout`` row per fact otherwise (e.g. under a fake test
    shim, which defines ``QFormLayout`` but not ``QGridLayout``). Returns the container widget;
    each value is exposed as ``widget.values[key]`` (a label/field caller code can ``.setText``
    later) keyed by the same string used in *pairs*.
    """
    container = QtWidgets.QWidget()
    values: dict[str, object] = {}
    grid_cls = getattr(QtWidgets, "QGridLayout", None)
    if grid_cls is not None:
        grid = grid_cls(container)
        for index, (key, label_text, initial) in enumerate(pairs):
            row, column = divmod(index, 2)
            caption = _grid_caption_label(QtWidgets, f"{label_text}:")
            value_label = QtWidgets.QLabel(str(initial))
            grid.addWidget(caption, row, column * 2)
            grid.addWidget(value_label, row, column * 2 + 1)
            values[key] = value_label
    else:
        form = QtWidgets.QFormLayout(container)
        for key, label_text, initial in pairs:
            value_label = QtWidgets.QLabel(str(initial))
            form.addRow(label_text, value_label)
            values[key] = value_label
    container.values = values
    return container


def _grid_caption_label(QtWidgets, text: str):
    """A small muted caption label used inside metadata_grid (kept distinct from helper_label,
    which word-wraps -- a grid caption must not wrap onto a second line)."""
    label = QtWidgets.QLabel(text)
    if hasattr(label, "setStyleSheet"):
        label.setStyleSheet(ui_theme.HELPER_TEXT_QSS)
    return label
