"""Validation for the v0.9.0 scientific-foundation/README session: CITATION.cff,
docs/references.bib, docs/scientific_background.md, the new geometry diagram, and the
README sections that summarize them. Deliberately stdlib-only (no PyYAML/bibtexparser) --
CITATION.cff and references.bib are simple enough to check with targeted regexes rather than
a full parser.
"""

from __future__ import annotations

import re
import xml.dom.minidom as minidom
from pathlib import Path

from membrane_vqc.constants import VERSION

ROOT = Path(__file__).resolve().parents[1]
CITATION = ROOT / "CITATION.cff"
REFERENCES_BIB = ROOT / "docs" / "references.bib"
SCI_BACKGROUND = ROOT / "docs" / "scientific_background.md"
GEOMETRY_SVG = ROOT / "docs" / "assets" / "diagrams" / "membrane-geometry.svg"

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _readme() -> str:
    return _read(ROOT / "README.md")


# ---------------------------------------------------------------------------
# CITATION.cff
# ---------------------------------------------------------------------------


def test_citation_cff_exists_and_has_required_top_level_fields():
    assert CITATION.is_file()
    text = _read(CITATION)
    for field in (
        "cff-version",
        "message",
        "title",
        "type",
        "version",
        "url",
        "repository-code",
        "license",
        "authors",
    ):
        assert re.search(rf"^{re.escape(field)}:", text, re.MULTILINE), (
            f"CITATION.cff is missing required field {field!r}"
        )
    assert re.search(r"^type:\s*software\s*$", text, re.MULTILINE)


def test_citation_cff_cited_version_is_an_actual_published_release():
    text = _read(CITATION)
    match = re.search(r"^version:\s*(\S+)\s*$", text, re.MULTILINE)
    assert match, "CITATION.cff has no version: field"
    cited_version = match.group(1)
    assert cited_version != VERSION, (
        "CITATION.cff should name the latest *published* release, not the untagged "
        f"active development version {VERSION!r} -- see README.md's Citation and references "
        "section for the documented policy"
    )
    evidence = ROOT / "docs" / f"v{cited_version}_release_evidence.json"
    assert evidence.is_file(), (
        f"CITATION.cff cites version {cited_version!r}, but {evidence} does not exist -- "
        "it must name a version this repository actually published and froze evidence for"
    )


def test_citation_cff_has_no_placeholder_doi_or_orcid():
    text = _read(CITATION)
    assert "doi:" not in text.lower(), "CITATION.cff must not invent a DOI"
    assert "orcid:" not in text.lower(), "CITATION.cff must not invent an ORCID"
    assert "identifiers:" not in text, "CITATION.cff must not invent identifiers"
    for placeholder in ("10.0000", "0000-0000-0000-0000", "xxxx", "XXXX"):
        assert placeholder not in text


def test_citation_cff_has_no_private_paths():
    text = _read(CITATION)
    for token in ("Pymol_script_1", "C:\\Users", "C:/Users"):
        assert token not in text


# ---------------------------------------------------------------------------
# docs/references.bib
# ---------------------------------------------------------------------------

_REQUIRED_REFERENCE_KEYS = (
    "Tusnady2005PDBTM",
    "Kozma2013PDBTM",
    "Lomize2006OPM",
    "Lomize2012PPM",
    "KyteDoolittle1982",
    "ShrakeRupley1973",
    "Mitternacht2016FreeSASA",
)


def test_references_bib_exists():
    assert REFERENCES_BIB.is_file()


def test_references_bib_has_every_required_selected_reference():
    text = _read(REFERENCES_BIB)
    for key in _REQUIRED_REFERENCE_KEYS:
        assert f"{{{key}," in text, f"docs/references.bib is missing @article{{{key}, ...}}"


def test_references_bib_every_doi_is_syntactically_valid():
    text = _read(REFERENCES_BIB)
    dois = re.findall(r"doi\s*=\s*\{([^}]+)\}", text)
    assert len(dois) >= len(_REQUIRED_REFERENCE_KEYS)
    for doi in dois:
        assert _DOI_RE.match(doi), f"docs/references.bib contains a malformed DOI: {doi!r}"


def test_references_bib_entries_are_balanced():
    text = _read(REFERENCES_BIB)
    entries = re.findall(r"@article\{[^,]+,", text)
    assert len(entries) == len(_REQUIRED_REFERENCE_KEYS) + 2  # + Tien2013MaxASA + Bondi1964
    assert text.count("{") == text.count("}")


# ---------------------------------------------------------------------------
# docs/scientific_background.md
# ---------------------------------------------------------------------------


def test_scientific_background_doc_exists_and_cites_every_bib_entry():
    assert SCI_BACKGROUND.is_file()
    text = _read(SCI_BACKGROUND)
    for doi in re.findall(r"doi\s*=\s*\{([^}]+)\}", _read(REFERENCES_BIB)):
        assert doi in text, f"docs/scientific_background.md never cites DOI {doi!r}"


def test_scientific_background_does_not_call_review_items_errors_or_imply_simulation():
    text = _read(SCI_BACKGROUND).lower()
    assert "review_items is an error" not in text
    assert "physical bilayer simulation" in text or "not a physical" in text


# ---------------------------------------------------------------------------
# README: equations
# ---------------------------------------------------------------------------

_SIGNED_DISTANCE_EQUATION = r"d_i = n \cdot (r_i - c)"
_CLASSIFICATION_FRAGMENT = r"\texttt{core} & L \le d_i \le U \\"


def test_readme_contains_supported_math_syntax():
    text = _readme()
    assert "$$" in text, "README should render its equations with GitHub-supported $$ math blocks"
    assert text.count("$$") % 2 == 0, "README has an unclosed $$ math block"


def test_readme_equations_match_scientific_background_verbatim():
    readme = _readme()
    background = _read(SCI_BACKGROUND)
    for fragment in (_SIGNED_DISTANCE_EQUATION, _CLASSIFICATION_FRAGMENT):
        assert fragment in readme, f"README is missing equation fragment: {fragment!r}"
        assert fragment in background, (
            f"docs/scientific_background.md is missing equation fragment: {fragment!r}"
        )


def test_readme_links_scientific_background_and_citation_guidance():
    text = _readme()
    assert "docs/scientific_background.md" in text
    assert "## Citation and references" in text
    assert "CITATION.cff" in text
    assert "Cite this repository" in text


def test_readme_no_longer_claims_no_formal_citation_is_available():
    text = _readme()
    assert "no formal citation is available" not in text.lower()


# ---------------------------------------------------------------------------
# README: screenshot gate -- no fabricated/placeholder screenshots
# ---------------------------------------------------------------------------


def test_readme_does_not_reference_unfcaptured_screenshot_or_demo_assets():
    text = _readme()
    for planned in (
        "docs/assets/screenshots/hero-single-structure.png",
        "docs/assets/screenshots/single-structure-result.png",
        "docs/assets/screenshots/batch-review-completed.png",
        "docs/assets/screenshots/source-comparison-result.png",
        "docs/assets/screenshots/recovery-state.png",
        "docs/assets/demos/membrane-visual-qc-demo",
    ):
        assert planned not in text, (
            f"README references planned screenshot/demo asset {planned!r} before it has been "
            "captured -- see docs/screenshot_capture_plan.md"
        )
    assert not (ROOT / "docs" / "assets" / "screenshots").exists() or not any(
        (ROOT / "docs" / "assets" / "screenshots").iterdir()
    ), "a screenshot exists on disk but README was not updated to reference it"


def test_readme_real_product_preview_section_links_the_capture_plan():
    text = _readme()
    assert "## Real product preview" in text
    assert "docs/screenshot_capture_plan.md" in text


# ---------------------------------------------------------------------------
# README: workflow diagrams are the new, small ones
# ---------------------------------------------------------------------------


def test_readme_workflow_diagrams_are_small_and_split_in_two():
    text = _readme()
    mermaid_blocks = re.findall(r"```mermaid\n(.*?)```", text, re.DOTALL)
    assert len(mermaid_blocks) == 2, (
        f"expected exactly two small Mermaid diagrams (single-structure path, batch path), "
        f"found {len(mermaid_blocks)}"
    )
    for block in mermaid_blocks:
        arrows = block.count("-->")
        assert arrows <= 5, (
            f"Mermaid diagram has {arrows} edges; keep each diagram small: {block!r}"
        )
    # The old, single oversized diagram enumerated all five orientation modes as branches off one
    # decision node -- that specific fan-out pattern must not reappear.
    assert "PDBTM cached snapshot" not in text
    assert "PDBTM vs OPM comparison" not in text or "flowchart" not in text


# ---------------------------------------------------------------------------
# New geometry diagram
# ---------------------------------------------------------------------------


def test_geometry_diagram_exists_and_is_referenced():
    assert GEOMETRY_SVG.is_file()
    assert GEOMETRY_SVG.stat().st_size > 0
    assert "docs/assets/diagrams/membrane-geometry.svg" in _readme()


def test_geometry_diagram_is_well_formed_with_no_external_refs_or_embedded_fonts():
    text = _read(GEOMETRY_SVG)
    minidom.parseString(text)
    external = re.findall(r'(?:href|xlink:href)\s*=\s*"(https?://[^"]*)"', text)
    assert not external, f"membrane-geometry.svg must not reference external resources: {external}"
    assert "@import" not in text
    assert "@font-face" not in text and "<font" not in text.lower()


def test_geometry_diagram_has_alt_text_in_readme():
    text = _readme()
    match = re.search(r'<img src="docs/assets/diagrams/membrane-geometry\.svg" alt="([^"]+)"', text)
    assert match and match.group(1).strip(), "geometry diagram <img> is missing alt text"


# ---------------------------------------------------------------------------
# No private paths anywhere in the new documents
# ---------------------------------------------------------------------------


def test_no_private_windows_paths_in_new_scientific_docs():
    forbidden = ("Pymol_script_1", "C:\\Users", "C:/Users")
    for path in (CITATION, REFERENCES_BIB, SCI_BACKGROUND, GEOMETRY_SVG, ROOT / "README.md"):
        text = _read(path)
        for token in forbidden:
            assert token not in text, (
                f"{path.name} contains a private/local-machine path: {token!r}"
            )


# ---------------------------------------------------------------------------
# Package impact: the new root/docs files are not part of the packaged plugin ZIP
# ---------------------------------------------------------------------------


def test_new_scientific_docs_are_not_inside_the_packaged_plugin_directory():
    package_root = ROOT / "membrane_vqc"
    for path in (CITATION, REFERENCES_BIB, SCI_BACKGROUND, GEOMETRY_SVG):
        assert package_root not in path.parents, (
            f"{path} must stay outside membrane_vqc/ -- scripts/build_plugin_zip.py packages that "
            "directory only, and this session must not change the Plugin ZIP contents"
        )
