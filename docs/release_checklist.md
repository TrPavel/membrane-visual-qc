# Release checklist

The exact two-PR process this project uses to cut a release, generalized from the v0.5.0, v0.6.0,
and v0.7.0 releases. Follow it in order; do not skip the owner manual smoke test or publish before
it passes. See `docs/versioning_policy.md` for what version number to pick and
`docs/v1.0_contract_freeze.md` for what must not silently change along the way.

Notation: `X.Y.Z` is the new stable version (for example `0.8.0`); `X.Y.Z.devN` is the current
active development version being promoted (for example `0.8.0.dev0`); `(X.Y.Z+1).dev0` is the next
development version the cycle reopens as (for example `0.9.0.dev0`).

## Phase 1 -- release-preparation PR

Branch: `release/vX.Y.Z-prepare`

1. Confirm `main` is clean, CI is green, and every intended feature PR is already merged.
2. Bump the version in exactly two places: `pyproject.toml` and `membrane_vqc/constants.py`
   (`X.Y.Z.devN` -> `X.Y.Z`).
3. Update `.github/workflows/ci.yml`: the `--validate dist/MembraneVisualQC-X.Y.Z.zip` line, the
   `release-candidate --version X.Y.Z` step name and `--version`, and the four artifact paths under
   `Upload release-build inputs`.
4. Update the version-literal tests tied to the exact version string (currently 5: `test_gui_version.py`,
   `test_pdbtm_adapter.py`, `test_release_version.py` -- 3 occurrences, `test_report.py`).
5. Convert `CHANGELOG.md`'s `[Unreleased]` section into `## [X.Y.Z] - PENDING`, grouped by what
   actually landed. Leave a short `[Unreleased]` note that publication evidence is pending.
6. Create `docs/vX.Y.Z_release_notes.md` with `Status: **release preparation**` and `**PENDING**`
   placeholders for every publication-time fact (asset sizes/hashes, tag, release URL, CI run,
   validation results) -- do not invent these values.
7. Update `README.md`, `Report.md`, `docs/development_state.md`, and `docs/compatibility.md`'s
   "active version" line for the version-identity promotion, keeping the *previous* release as the
   latest *published* package until this one actually ships.
8. Do **not** touch: frozen historical evidence (`docs/vPREV_release_evidence.json`), any completed
   manual-validation record tied to a specific already-tested `.devN` artifact hash (for example
   `docs/manual_install_upgrade_checklist.md` if it names an exact `.devN` SHA-256), or the
   generic-minor-line framing in `docs/upgrade_guide.md` unless the supported upgrade path itself
   changed.
9. Run the full validation suite (below) locally.
10. Commit as `chore: prepare vX.Y.Z release`, push, open **one draft PR** against `main`.
11. Wait for both push and pull_request CI to go green. Fix in-scope failures; do not merge until
    both are green.
12. Mark ready, squash-merge, delete the branch, `git fetch --prune && git switch main && git pull --ff-only`.
13. Record the exact squash-merge commit SHA -- this is the release commit.

## Phase 2 -- build, verify, and publish

1. Find the CI run triggered by the squash-merge commit landing on `main` (a fresh `push` event,
   not the PR's own run) and confirm its `headSha` matches `main` exactly.
2. Download that run's `membrane-vqc-build` artifact -- never a branch build or a stale local
   `dist/` copy. Re-download once more independently and confirm byte-identical hashes.
3. Verify the Plugin ZIP: `python scripts/build_plugin_zip.py --validate <path>`, plus manually
   confirm the packaged file set matches the source tree, no traversal/symlink entries, and the
   manifest's declared version matches `X.Y.Z`.
4. **Stop.** Present the owner the exact ZIP path, size, SHA-256, source commit, and CI run. Ask
   for a real-PyMOL clean-install smoke test (version display, one plugin entry, Single structure,
   Batch review five-mode plan, Manifest/Reveal/Open, cancel, close/reopen, no
   traceback/freeze/duplicate-UI/`QThread` warning). **Do not proceed until the owner reports
   PASS.**
5. Create an annotated tag `vX.Y.Z` pointing exactly at the release commit; push it.
6. Prepare the final release-notes body (real values, not the repo's still-PENDING file) and
   `gh release create vX.Y.Z <4 assets> --prerelease --notes-file <body> --target <release commit>`.
   Upload exactly the four CI-built assets (ZIP, ZIP sidecar, wheel, sdist) -- never rebuilt or
   substituted locally.
7. Re-download every published asset directly from the release and confirm byte-identical hashes,
   confirm the sidecar matches the ZIP, confirm `isPrerelease: true`, confirm exactly four assets,
   and confirm PyPI publication did not occur (404 on the project JSON endpoint).

## Phase 3 -- evidence-freeze and reopen-development PR

Branch: `release/vX.Y.Z-evidence-and-reopen`

1. Add `docs/vX.Y.Z_release_evidence.json` (release PR number/head/squash commit, post-merge
   workflow/artifact IDs and outer hash, tag object/target, release URL/timestamp/prerelease flag,
   all four asset size/SHA-256 pairs, and the owner-observed manual-smoke-test result).
2. Add `scripts/validate_release_artifacts.py --mode frozen-vX.Y.Z`, mirroring the previous
   frozen-vX.Y.Z gate exactly (constants block, `verify_frozen_vXYZ_evidence()`, CLI wiring). Only
   include a schema/report freeze section if this release actually shipped a new schema version.
3. Finalize `docs/vX.Y.Z_release_notes.md`: replace every `**PENDING**` with the real value.
4. `CHANGELOG.md`: `[X.Y.Z] - PENDING` -> the actual publication date; reopen `[Unreleased]` with a
   one-line "Reopened development as `(X.Y.Z+1).dev0`" note.
5. Bump `pyproject.toml` / `membrane_vqc/constants.py`: `X.Y.Z` -> `(X.Y.Z+1).dev0`.
6. `ci.yml`: bump artifact filenames again, add the `frozen-vX.Y.Z` verification step.
7. Update `README.md` / `Report.md` / `docs/development_state.md` / `docs/compatibility.md` prose
   to describe the now-published `X.Y.Z` and the reopened `(X.Y.Z+1).dev0` line.
8. Update the 5 version-literal tests again; add 2 new tests for the `frozen-vX.Y.Z` mode
   (`..._is_verified_independently_of_active_version`, `..._rejects_publication_identity_changes`).
9. Check `tests/test_install_upgrade_docs.py`'s upgrade-guide version-drift tripwire test: if it
   now fails because the active version moved past the guide's documented pair, that's
   intentional -- review whether the guide's supported-path claim needs revisiting, then update the
   test to match the new state (see that test's own docstring for the reasoning).
10. Run the full validation suite (below) again, including the new `frozen-vX.Y.Z` mode.
11. Commit as `chore: reopen development after vX.Y.Z`, push, open **one draft PR**.
12. Wait for both CI workflows green, then mark ready, squash-merge, delete branch, sync `main`.
13. Confirm afterward: `frozen-vX.Y.Z` passes against final `main`, the `vX.Y.Z` tag is unmoved,
    and no release asset changed.

## Full validation suite (run before each PR in both phases)

```bash
ruff check .
ruff format --check .
pytest                                    # full suite
python scripts/validate_example_reports.py
python -m build
python scripts/build_plugin_zip.py --output .local/determinism/first.zip
python scripts/build_plugin_zip.py --output .local/determinism/second.zip
cmp --silent .local/determinism/first.zip .local/determinism/second.zip
python scripts/build_plugin_zip.py
python scripts/build_plugin_zip.py --validate dist/MembraneVisualQC-<active-version>.zip
python scripts/validate_release_artifacts.py --mode current-development
python scripts/validate_release_artifacts.py --mode frozen-v0.4.0
python scripts/validate_release_artifacts.py --mode frozen-v0.5.0
python scripts/validate_release_artifacts.py --mode frozen-v0.6.0
python scripts/validate_release_artifacts.py --mode frozen-v0.7.0   # and every later frozen-vX.Y.Z mode that exists
python scripts/validate_release_artifacts.py --mode release-candidate --version <active-version>
```

On Windows, use a short `pytest --basetemp` path (for example `C:\pt\`) to avoid an unrelated
`MAX_PATH` failure in the install/upgrade test suite. If the known local `requests`/`socks` import
failure in `tests/test_stage4b3_package_safety.py` reproduces, confirm it is pre-existing and
unrelated before proceeding -- do not hide a genuinely new failure behind it.

## Do not

- Do not merge either release PR before both its CI workflows are green.
- Do not tag or publish before the owner reports PASS on the real-PyMOL smoke test.
- Do not rebuild or substitute release assets after tagging.
- Do not publish to PyPI.
- Do not rewrite a prior release's frozen evidence, tag, or completed manual-validation record.
