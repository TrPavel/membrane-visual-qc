# Visual identity

The visual system behind `README.md` and the repository's public presentation, introduced in the
v0.9.0 visual-identity session. This governs assets and maintenance, not the plugin GUI itself --
the GUI's own layout and styling are explicitly out of scope here (see `docs/development_state.md`
for the deferred GUI/UX polish phase).

## Principles

- **Restrained, not decorative.** One primary accent, one secondary accent used sparingly. No
  gradients-for-their-own-sake, no glassmorphism, no stock imagery, no fabricated screenshots.
- **Every visual claim must be true.** A diagram or table describing behavior must match the real
  schema/contract/status vocabulary it illustrates -- see `docs/status_vocabulary.md` and
  `docs/v1.0_contract_freeze.md` as the source of truth before adding or editing any figure.
- **Prefer maintainable formats.** Mermaid for diagrams GitHub can render natively (no image file
  to regenerate when the workflow changes); SVG for the logo/wordmark (crisp at any size, tiny
  file size, no embedded fonts); PNG only for the social-preview card, because GitHub's
  repository-social-image setting requires a raster image.
- **Light and dark both matter.** Every logo asset ships as a light-background and a
  dark-background variant, selected via a `<picture>`/`prefers-color-scheme` block -- see the
  pattern at the top of `README.md`.

## Palette

| Role | Hex | Used for |
|---|---|---|
| Ink (dark backgrounds) | `#0B1220` | Dark-variant container fill, social-preview background |
| Ink (light backgrounds) | `#0B1220` | Structure-ribbon stroke on light backgrounds |
| Primary accent (on light) | `#0F766E` | Membrane slab lines on light-background assets |
| Primary accent (on dark) | `#2DD4BF` | Membrane slab lines on dark-background assets |
| Secondary neutral | `#94A3B8` / `#64748B` | Tagline and secondary text on dark assets |
| Light surface | `#FFFFFF` | Light-background asset fill |

Do not add a third accent color. If a new figure seems to need one, reconsider whether it needs a
label or table cell instead of another color.

## Logo and wordmark

- `docs/assets/brand/icon-on-light.svg` / `docs/assets/brand/icon-on-dark.svg` -- the compact mark
  alone (a structure ribbon crossing a membrane slab), for small/square placements (for example, a
  future favicon).
- `docs/assets/brand/wordmark-on-light.svg` / `docs/assets/brand/wordmark-on-dark.svg` -- the icon
  plus the "Membrane Visual QC" wordmark, used in the `README.md` hero.
- Both variants share the exact same glyph geometry; only fill/stroke colors differ. Never
  redraw the glyph itself when adding a new variant -- copy an existing file and change colors
  only, so the mark stays recognizable.

## Social preview

- `docs/assets/social/social-preview.png`, 1280x640, generated with Pillow (no SVG rasterizer is
  available in this project's environment; regenerate by adapting the drawing script used to
  produce it rather than hand-editing the PNG).
- **To apply it**: repository Settings -> General -> Social preview -> upload this file. This is a
  manual, one-time GitHub setting; no tool available to this project can set it via API, and it is
  intentionally not automated here.
- Update this file (and re-upload) only on a deliberate visual refresh, not for routine content
  changes -- it deliberately omits a version number so it does not need to change every release.

## Scientific diagrams

- `docs/assets/diagrams/membrane-geometry.svg` -- the one original schematic illustrating the
  signed-distance/classification geometry in `docs/scientific_background.md` and README's
  Scientific foundation section. Self-contained (opaque white card background, no external
  references, no embedded fonts) so it stays readable on both GitHub themes without a separate
  dark variant -- see `docs/scientific_background.md` for what each labeled symbol means.
- A new scientific diagram must be geometrically consistent with the implementation it illustrates
  (cite the exact function/file in its caption or the surrounding prose) and must not imply a
  physical simulation, biological correctness, or a validation claim -- see
  `docs/scientific_interpretation.md`.

## Screenshot conventions

All required current-UI screenshots and the demo are captured (see `docs/screenshot_capture_plan.md`
for status and the exact composition each one shows). Every screenshot must:

- live under `docs/assets/screenshots/` (demos under `docs/assets/demos/`);
- be named descriptively (`hero-single-structure.png`, not `screenshot1.png`);
- carry meaningful alt text wherever referenced from Markdown;
- never contain a personal file path, username, or unrelated desktop/window content;
- be recaptured (not reused) once the active version has moved past what they depict, if the
  dialog's visible layout or labels changed.

The pre-existing images under `docs/screenshots/` (note: singular `screenshots/`, not
`assets/screenshots/`) are historical validation evidence tied to specific dated manual-acceptance
records (`docs/manual_gui_validation.md`, `Report.md`). They are a different thing from this
visual-identity asset set and are not reused here -- do not move, rename, or repurpose them.

## README maintenance rules

- Keep the first screen (hero through Quick start) concise; put secondary technical detail in
  `<details>` blocks or link to the canonical doc instead of duplicating it.
- Every new fact added to the README must already be true in code or in a canonical doc -- link to
  that doc rather than re-deriving the claim.
- Do not add a badge that depends on PyPI (this project is not published there) or that implies an
  unvalidated platform/OS.
- Run `pytest tests/test_visual_identity.py` after any README or asset change -- it checks that
  every referenced asset exists, every image has alt text, no stale version or PyPI claim was
  reintroduced, and local links resolve.
