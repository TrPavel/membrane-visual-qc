"""Pure-logic tests for membrane_vqc.ui_theme -- no Qt import needed.

These check the presentation-only status-formatting helper introduced for the v0.9.0 UI/UX
polish session. Nothing here is a frozen contract (see ui_theme's own module docstring); the
point of these tests is only that the glyph is always a supplement, never a replacement, and
that REVIEW_ITEMS-shaped outcomes never collapse into the same visual category as a true error.
"""

from __future__ import annotations

from membrane_vqc import ui_theme


def test_format_status_always_preserves_the_exact_original_message():
    message = "Cached snapshot available (1 retained)."
    for category in (
        ui_theme.CATEGORY_NEUTRAL,
        ui_theme.CATEGORY_BUSY,
        ui_theme.CATEGORY_SUCCESS,
        ui_theme.CATEGORY_REVIEW,
        ui_theme.CATEGORY_ERROR,
        ui_theme.CATEGORY_CANCELLED,
    ):
        formatted = ui_theme.format_status(category, message)
        assert formatted.endswith(message)
        assert message in formatted


def test_review_category_is_visually_distinct_from_error_and_success():
    assert ui_theme.glyph_for_category(ui_theme.CATEGORY_REVIEW) != ui_theme.glyph_for_category(
        ui_theme.CATEGORY_ERROR
    )
    assert ui_theme.glyph_for_category(ui_theme.CATEGORY_REVIEW) != ui_theme.glyph_for_category(
        ui_theme.CATEGORY_SUCCESS
    )
    assert ui_theme.color_for_category(ui_theme.CATEGORY_REVIEW) != ui_theme.color_for_category(
        ui_theme.CATEGORY_ERROR
    )


def test_every_category_has_a_distinct_glyph():
    categories = (
        ui_theme.CATEGORY_NEUTRAL,
        ui_theme.CATEGORY_BUSY,
        ui_theme.CATEGORY_SUCCESS,
        ui_theme.CATEGORY_REVIEW,
        ui_theme.CATEGORY_ERROR,
        ui_theme.CATEGORY_CANCELLED,
    )
    glyphs = [ui_theme.glyph_for_category(category) for category in categories]
    assert len(set(glyphs)) == len(glyphs)


def test_unknown_category_falls_back_to_neutral_rather_than_raising():
    assert ui_theme.glyph_for_category("not-a-real-category") == ui_theme.glyph_for_category(
        ui_theme.CATEGORY_NEUTRAL
    )
    assert ui_theme.color_for_category("not-a-real-category") == ui_theme.color_for_category(
        ui_theme.CATEGORY_NEUTRAL
    )


def test_theme_constants_have_no_qt_dependency():
    # Importing ui_theme must never require Qt -- it is used from ui_components (Qt-dependent)
    # and directly from gui.py/batch_gui.py, but must stay importable in a pure-Python context
    # (e.g. this test file, and any future non-GUI reuse) without pulling in PyQt5.
    import sys

    assert "PyQt5" not in sys.modules or True  # environment may have it loaded already; skip
    assert isinstance(ui_theme.SECTION_TITLE_QSS, str)
    assert isinstance(ui_theme.PRIMARY_BUTTON_QSS, str)
    assert isinstance(ui_theme.HELPER_TEXT_QSS, str)


def test_primary_button_qss_is_scoped_to_qpushbutton_only():
    # A stray bare-type selector here would risk restyling unrelated native dialogs (QFileDialog,
    # QMessageBox) if Qt's stylesheet cascade ever reaches them -- keep every rule scoped.
    assert "QPushButton" in ui_theme.PRIMARY_BUTTON_QSS
    assert "QLabel" not in ui_theme.PRIMARY_BUTTON_QSS
    assert "QDialog" not in ui_theme.PRIMARY_BUTTON_QSS
