"""Visual-only constants and status-text formatting for the GUI.

Everything in this module is presentation only: it carries no scientific meaning, is not a
frozen public contract (unlike ``membrane_vqc.batch_gui.BATCH_STATES`` or the report/batch status
vocabularies documented in ``docs/status_vocabulary.md``), and can be freely restyled without
affecting any schema, contract, or command signature. This module has no Qt import so it stays
importable and unit-testable without a display.

Status *category* (below) is a purely visual grouping used to pick a glyph/color -- it is not
itself a status literal and must never be confused with one. In particular:

- ``review`` must never look like ``error`` (REVIEW_ITEMS is not a failure -- see
  ``docs/status_vocabulary.md``);
- the glyph is always a supplement to the text label, never a replacement for it.
"""

from __future__ import annotations

SPACING_SM = 6
SPACING_MD = 10
SPACING_LG = 16

# Restrained palette matching docs/visual_identity.md's README accent (teal), extended with a
# secondary amber accent (review/attention) and a muted error red -- never used alone, always
# paired with a glyph and a text label.
COLOR_ACCENT = "#0F766E"
COLOR_ACCENT_TEXT = "#FFFFFF"
COLOR_ACCENT_DISABLED_BG = "#94A3B8"
COLOR_ACCENT_DISABLED_TEXT = "#E5E7EB"
COLOR_MUTED_TEXT = "#55606B"
COLOR_SECTION_RULE = "#CBD5E1"
COLOR_SUCCESS = "#15803D"
COLOR_REVIEW = "#B45309"
COLOR_ERROR = "#B91C1C"
COLOR_NEUTRAL = "#334155"

CATEGORY_NEUTRAL = "neutral"
CATEGORY_BUSY = "busy"
CATEGORY_SUCCESS = "success"
CATEGORY_REVIEW = "review"
CATEGORY_ERROR = "error"
CATEGORY_CANCELLED = "cancelled"

_GLYPHS = {
    CATEGORY_NEUTRAL: "○",  # ○ ready/idle/informational
    CATEGORY_BUSY: "◐",  # ◐ in progress
    CATEGORY_SUCCESS: "✓",  # ✓ operational success (not a biological verdict)
    CATEGORY_REVIEW: "◆",  # ◆ needs manual review / attention, not a failure
    CATEGORY_ERROR: "✕",  # ✕ operational error/rejection
    CATEGORY_CANCELLED: "⊘",  # ⊘ cancelled
}

_COLORS = {
    CATEGORY_NEUTRAL: COLOR_NEUTRAL,
    CATEGORY_BUSY: COLOR_ACCENT,
    CATEGORY_SUCCESS: COLOR_SUCCESS,
    CATEGORY_REVIEW: COLOR_REVIEW,
    CATEGORY_ERROR: COLOR_ERROR,
    CATEGORY_CANCELLED: COLOR_MUTED_TEXT,
}


def glyph_for_category(category: str) -> str:
    """Return the supplementary glyph for a visual status category."""
    return _GLYPHS.get(category, _GLYPHS[CATEGORY_NEUTRAL])


def color_for_category(category: str) -> str:
    """Return the accent color (hex) for a visual status category."""
    return _COLORS.get(category, _COLORS[CATEGORY_NEUTRAL])


def format_status(category: str, message: str) -> str:
    """Prefix *message* with a supplementary glyph for *category*.

    The glyph is never the only signal -- ``message`` is always the exact, unabbreviated text
    that was previously shown, so nothing that already read this label's text (tests, screen
    readers, an ``in text`` substring check) loses information.
    """
    return f"{glyph_for_category(category)} {message}"


SECTION_TITLE_QSS = (
    f"font-weight: 600; padding-top: {SPACING_MD}px; padding-bottom: 2px; "
    f"border-bottom: 1px solid {COLOR_SECTION_RULE};"
)
HELPER_TEXT_QSS = f"color: {COLOR_MUTED_TEXT}; font-size: 9pt;"
PRIMARY_BUTTON_QSS = (
    f"QPushButton {{ background-color: {COLOR_ACCENT}; color: {COLOR_ACCENT_TEXT}; "
    f"font-weight: 600; padding: 4px 14px; border-radius: 3px; border: none; }} "
    f"QPushButton:disabled {{ background-color: {COLOR_ACCENT_DISABLED_BG}; "
    f"color: {COLOR_ACCENT_DISABLED_TEXT}; }} "
    f"QPushButton:hover:!disabled {{ background-color: #115e59; }}"
)
GROUP_TITLE_QSS = f"QGroupBox {{ font-weight: 600; }} QGroupBox::title {{ color: {COLOR_ACCENT}; }}"
