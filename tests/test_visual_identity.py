"""Validation for the v0.9.0 visual-identity/premium-README assets and README structure.

These checks are about the *presentation* layer added in this session (logo/wordmark, social
preview, the rewritten README, docs/visual_identity.md, docs/screenshot_capture_plan.md) -- not
about scientific correctness, which tests/test_documentation_consistency.py and
tests/test_contract_freeze.py already cover for the rest of the documentation set.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from membrane_vqc.constants import VERSION

ROOT = Path(__file__).resolve().parents[1]

BRAND_DIR = ROOT / "docs" / "assets" / "brand"
SOCIAL_PREVIEW = ROOT / "docs" / "assets" / "social" / "social-preview.png"

LOGO_FILES = (
    "icon-on-light.svg",
    "icon-on-dark.svg",
    "wordmark-on-light.svg",
    "wordmark-on-dark.svg",
)

# README badges are legitimately external (GitHub's own badge endpoint, shields.io) -- only these
# exact hosts are permitted for an external <img>/markdown-image reference in README.md.
_ALLOWED_EXTERNAL_IMAGE_HOSTS = ("https://github.com/", "https://img.shields.io/")

_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_HTML_IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_HTML_ATTR = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')
_MD_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")


def _read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def _readme_text() -> str:
    return _read("README.md")


def test_logo_files_exist_and_are_nonempty():
    for name in LOGO_FILES:
        path = BRAND_DIR / name
        assert path.is_file(), f"missing logo asset: {path}"
        assert path.stat().st_size > 0


def test_logo_svgs_are_well_formed_and_have_no_external_or_embedded_font_refs():
    import xml.dom.minidom as minidom

    for name in LOGO_FILES:
        text = (BRAND_DIR / name).read_text(encoding="utf-8")
        minidom.parseString(text)  # raises on malformed XML
        # The standard SVG/XML namespace declarations are required and not an external reference;
        # anything else pointing at http(s) (an <image>/<use> href, an @import, etc.) is not.
        external = re.findall(r'(?:href|xlink:href)\s*=\s*"(https?://[^"]*)"', text)
        assert not external, f"{name} must not reference external resources: {external}"
        assert "@import" not in text
        assert "@font-face" not in text and "<font" not in text.lower(), (
            f"{name} must not embed a font"
        )


def _png_dimensions(path: Path) -> tuple[int, int]:
    """Read width/height straight from a PNG's IHDR chunk (no Pillow dependency)."""
    import struct

    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG file"
    assert data[12:16] == b"IHDR", f"{path} does not start with an IHDR chunk"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_social_preview_exists_at_documented_dimensions():
    assert SOCIAL_PREVIEW.is_file(), f"missing social preview asset: {SOCIAL_PREVIEW}"
    assert _png_dimensions(SOCIAL_PREVIEW) == (1280, 640)


def test_social_preview_has_no_stray_version_number():
    # docs/visual_identity.md documents this is intentionally version-agnostic (an evergreen card).
    for token in (VERSION, "0.8.0", "0.7.0"):
        assert token.encode("ascii") not in SOCIAL_PREVIEW.read_bytes()


def test_readme_hero_has_light_and_dark_wordmark_sources():
    text = _readme_text()
    assert "<picture>" in text and "</picture>" in text
    assert "prefers-color-scheme: dark" in text
    assert "docs/assets/brand/wordmark-on-dark.svg" in text
    assert "docs/assets/brand/wordmark-on-light.svg" in text
    for relative in (
        "docs/assets/brand/wordmark-on-dark.svg",
        "docs/assets/brand/wordmark-on-light.svg",
    ):
        assert (ROOT / relative).is_file()


def _iter_readme_images():
    text = _readme_text()
    for alt, src in _MD_IMAGE.findall(text):
        yield alt, src
    for tag in _HTML_IMG.findall(text):
        attrs = dict(_HTML_ATTR.findall(tag))
        yield attrs.get("alt"), attrs.get("src")
    for tag in re.findall(r"<source\b[^>]*>", text, re.IGNORECASE):
        attrs = dict(_HTML_ATTR.findall(tag))
        if "srcset" in attrs:
            yield None, attrs["srcset"]


def test_every_readme_image_has_alt_text_or_is_a_source_element():
    text = _readme_text()
    for tag in _HTML_IMG.findall(text):
        attrs = dict(_HTML_ATTR.findall(tag))
        assert attrs.get("alt", "").strip(), f"<img> without alt text: {tag}"
    for alt, src in _MD_IMAGE.findall(text):
        assert alt.strip(), f"markdown image without alt text: ![]({src})"


def test_readme_image_references_are_repo_relative_or_an_allowed_badge_host():
    for _alt, src in _iter_readme_images():
        if src is None:
            continue
        if src.startswith("http://") or src.startswith("https://"):
            assert src.startswith(_ALLOWED_EXTERNAL_IMAGE_HOSTS), (
                f"README image references an unapproved external host: {src}"
            )
            continue
        assert (ROOT / src).is_file(), f"README references a missing local image: {src}"


def test_readme_has_no_pypi_badge_or_link():
    text = _readme_text()
    assert "pypi.org" not in text.lower()
    assert "img.shields.io/pypi" not in text.lower()
    assert "badge/pypi" not in text.lower()


def test_readme_does_not_claim_unvalidated_platform_gui_support():
    text = _readme_text()
    # Only Windows/Incentive PyMOL graphical acceptance is real -- see docs/compatibility.md. Any
    # mention of Linux/macOS must be clearly negated (no manual GUI acceptance performed there),
    # never phrased as if they were validated.
    for platform_name in ("Linux", "macOS"):
        windows = list(_sentence_windows(text, platform_name))
        assert windows, f"expected README to mention {platform_name!r} in its compatibility caveat"
        for window in windows:
            assert re.search(r"\b(no|not|cannot|does not)\b", window, re.IGNORECASE), (
                f"any {platform_name!r} mention in README must be clearly negated -- "
                "see docs/compatibility.md"
            )


def _sentence_windows(text: str, needle: str):
    for match in re.finditer(re.escape(needle), text):
        start = max(0, match.start() - 160)
        end = min(len(text), match.end() + 160)
        yield text[start:end]


def test_readme_states_the_current_release_candidate_version():
    text = _readme_text()
    assert VERSION in text, f"README does not mention the active version {VERSION!r}"
    assert VERSION == "1.0.0rc1"
    # The previously *published* version (0.8.0) may still appear (install instructions, release
    # verification section) but must never be described as the active development line.
    assert "0.8.0" in text


def test_readme_links_to_the_two_new_visual_docs():
    text = _readme_text()
    assert "docs/visual_identity.md" in text
    assert "docs/screenshot_capture_plan.md" in text


def test_readme_size_stays_within_a_sensible_limit():
    lines = _readme_text().splitlines()
    assert len(lines) < 400, (
        f"README.md grew to {len(lines)} lines; move detail into a canonical doc instead "
        "of duplicating it here (see docs/visual_identity.md#readme-maintenance-rules)"
    )


def test_readme_local_markdown_links_resolve():
    text = _readme_text()
    for _label, target in _MD_LINK.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        relative = target.split("#", 1)[0]
        assert (ROOT / relative).is_file(), f"README links to a missing file: {target}"


_BACKTICK_DOC_REF = re.compile(r"`([\w./-]+/[\w.-]+\.(?:md|json|svg|png|py))`")
# Only matches backtick references containing a path separator, i.e. an actual repo-relative path
# such as `docs/development_state.md` -- bare illustrative example filenames like
# `hero-single-structure.png` (used only to demonstrate a naming convention) are not paths and are
# correctly skipped.


# docs/screenshot_capture_plan.md deliberately names files that do not exist yet (that is its
# entire purpose -- a plan for capturing them); exclude those planned paths from existence checks.
_PLANNED_ASSET_PREFIXES = ("docs/assets/screenshots/", "docs/assets/demos/")


@pytest.mark.parametrize("relative", ["docs/visual_identity.md", "docs/screenshot_capture_plan.md"])
def test_new_visual_docs_backtick_file_references_resolve(relative):
    text = _read(*relative.split("/"))
    checked = 0
    for candidate in _BACKTICK_DOC_REF.findall(text):
        if candidate.startswith(_PLANNED_ASSET_PREFIXES):
            continue
        resolved = ROOT / candidate
        if not resolved.is_file() and not candidate.startswith("docs/"):
            resolved = ROOT / "docs" / candidate
        assert resolved.is_file(), f"{relative} references a missing file: {candidate}"
        checked += 1
    assert checked > 0, f"expected at least one backtick-quoted file reference in {relative}"


def test_no_private_windows_paths_in_new_visual_docs():
    forbidden = ("Pymol_script_1", r"C:\Users\\", "C:/Users/")
    for relative in ("README.md", "docs/visual_identity.md", "docs/screenshot_capture_plan.md"):
        text = _read(*relative.split("/"))
        for token in forbidden:
            assert token not in text, f"{relative} contains a private/local-machine path: {token!r}"


def test_old_historical_screenshots_are_not_referenced_as_current_branding():
    # docs/screenshots/ (singular) is the historical validation-evidence set (Report.md,
    # docs/manual_gui_validation.md); the new visual-identity asset set lives under
    # docs/assets/ and must not point back at the historical directory.
    text = _readme_text()
    assert "docs/screenshots/" not in text
