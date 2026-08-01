# Frozen historical test fixtures

Files in this directory are genuine artifacts recovered byte-for-byte from git history via
`git show <commit>:<path>`, not reconstructed from the current report writer. Each file's provenance
is recorded here; do not regenerate, reformat, or "fix" these files -- their exact historical bytes
are the point of the test.

## `genuine_v0.1.0_schema_1_0_bad_core_lys_mvqc.json`

- Source: `reports/bad_core_lys_mvqc.json` as it existed at commit
  `cddcd1c8410343e21a207a8426b81289a6bf12c1` ("Initial public release candidate: Membrane Visual QC
  v0.1.0").
- Git blob SHA-1: `8bacfb9674ba517cd1cd89061f5f155af10e7048` (verify with
  `git hash-object tests/fixtures/genuine_v0.1.0_schema_1_0_bad_core_lys_mvqc.json`).
- This is the last commit where `reports/bad_core_lys_mvqc.json` declared `schema_version: "1.0"`;
  it was silently regenerated to schema 1.1 in place by the Stage 2 commit that follows
  (`a140c46df01f609b8ab7b26107610639a83bb269`), so the current `reports/bad_core_lys_mvqc.json` is
  a different (schema-1.1) file with the same name. This fixture is the only surviving genuine
  schema-1.0 report in the repository.

## `v0.6.0/PLUGIN_MANIFEST.json`, `v0.6.0/SHA256SUMS.txt`

- Extracted unmodified from the published `MembraneVisualQC-0.6.0.zip` GitHub Release asset
  (release commit `58e89fed284139ea6e5d6be05a35fdeada591037`), verified byte-identical to the
  authoritative published artifact: SHA-256
  `7126e51acc6514e3fb73ed0113200d8da376ca75e5f128aef556db2194046960`, 192,168 bytes (matches
  `docs/v0.6.0_release_evidence.json`).
- Used by the install/upgrade compatibility tests to check real v0.6.0 file identities and the
  declared v0.6.0 version without committing the full binary ZIP to the repository. The full ZIP
  is used directly (not reconstructed) by the local-only integration test in
  `tests/test_plugin_upgrade.py` when a verified copy is present at
  `.local/release-v060-downloaded/MembraneVisualQC-0.6.0.zip` -- that test is skipped, not faked,
  when the file is absent (e.g. in ordinary CI).

## `v0.6.0_batch_result/`

- A genuine five-mode `mvqc-batch-result-1.0` bundle (`batch-result.json` plus its four successful
  jobs' report/CSV pairs) produced by a real batch run declaring `software.version: "0.6.0.dev0"`,
  captured during this project's own v0.6.0-cycle manual graphical acceptance testing (see
  `docs/stage5b_graphical_acceptance.md`). Not reconstructed: copied byte-for-byte from that run's
  output directory. `overall_status` is `COMPLETED_WITH_ERRORS` with one job (`pdbtm-cache`)
  `INPUT_REJECTED` -- this is the expected synthetic-plan result, not a fixture defect (matches the
  five-mode acceptance plan's documented expected outcome). Confirmed self-consistent against the
  current `membrane_vqc.batch_result_browser.inspect_result_bundle()` (all four successful jobs'
  reports verify; schemas 1.1/1.3/1.5 all dispatch correctly).
