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
