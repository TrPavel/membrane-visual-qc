# Release integrity and supply-chain boundaries

This document describes the integrity checks implemented by this repository. It does not claim
publisher authentication or a provenance standard that the release process does not produce.

## What the release process verifies

- The Plugin Manager ZIP is built deterministically by `scripts/build_plugin_zip.py`. Its member
  names are ordinally sorted; all members are under `membrane_vqc/`; duplicate, traversal, symlink,
  test, documentation, cache, and development metadata entries are rejected by the validator.
- Release preparation rebuilds the ZIP independently at least three times and requires identical
  bytes. CI independently performs a two-build byte comparison.
- Each ZIP has a `.zip.sha256` sidecar containing its SHA-256 digest and filename. The ZIP also
  carries member-level `PLUGIN_MANIFEST.json` and `SHA256SUMS.txt`, validated by the build tool.
- Stable releases use an annotated Git tag. Release validation verifies that the exact tag object
  resolves to the recorded release commit; GitHub Release assets are checked against recorded names,
  sizes, and SHA-256 values.
- After publication, the release procedure downloads the public assets again, verifies their bytes
  and ZIP sidecar, and records the results in immutable release evidence.
- Historical release evidence is retained byte-for-byte and checked by release-specific frozen
  validators. `scripts/check_frozen_evidence_diff.py` additionally rejects a Git diff that changes
  validator-pinned evidence paths, including deletion or rename.
- GitHub Releases is the only distribution channel. This project does not publish to PyPI. Most
  workflows are offline-oriented; network access is explicitly limited in
  [offline_and_safety.md](offline_and_safety.md).

## Verify a downloaded ZIP

Download the ZIP and its matching `.zip.sha256` sidecar from the same GitHub Release. In Windows
PowerShell, calculate the archive digest and compare it to the first field of the sidecar:

```powershell
Get-FileHash C:\MVQC_acceptance\1.0.0\MembraneVisualQC-1.0.0.zip -Algorithm SHA256
Get-Content C:\MVQC_acceptance\1.0.0\MembraneVisualQC-1.0.0.zip.sha256
```

With Python, calculate the expected digest (replace `<expected-sha256>` with the sidecar value):

```powershell
& .\python.exe -c "import hashlib, pathlib; p=pathlib.Path(r'C:\MVQC_acceptance\1.0.0\MembraneVisualQC-1.0.0.zip'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
```

Then validate the archive's internal manifest and checksums from a source checkout:

```powershell
& .\python.exe scripts\build_plugin_zip.py --validate C:\MVQC_acceptance\1.0.0\MembraneVisualQC-1.0.0.zip
```

The checksum establishes only that the downloaded bytes match the expected digest. Obtain the
sidecar from the official GitHub Release and confirm the release/tag context independently.

## Deliberate limitations

- No Authenticode or other code signing is provided.
- No signed installer is provided.
- No Sigstore attestation is provided.
- No SLSA provenance claim is made.
- No cryptographic build attestation is provided.
- No SBOM is produced.
- SHA-256 integrity alone does not authenticate publisher identity.

For the release sequence and immutable evidence layout, see
[release_checklist.md](release_checklist.md). For compatibility and manual-verification limits, see
[compatibility.md](compatibility.md).
