# Stage 4 orientation import threat model

Status: proposed design controls; applies before Stage 4A implementation.

## Assets and trust boundaries

Assets are the user's molecular objects, plugin-owned PyMOL/report state, local files, provenance
records, cache integrity, and a reproducible scientific interpretation. Local “downloaded” files
are untrusted. Provider HTTPS responses are also untrusted input: TLS authenticates a host, not the
scientific applicability or safety of a record. Source metadata, filenames, identifiers, redirects,
cache entries, and HTML are never trusted merely because they came from an official domain.

Adapters are deterministic parsers. They cannot execute code, access the network, mutate PyMOL,
write files, expand archives, call templates/macros, or launch external binaries.

## Baseline parsing limits

Stage 4A accepts only uncompressed regular files supplied as bytes:

| Limit | Proposed value | Failure |
|---|---:|---|
| Raw local payload | 5 MiB | `PAYLOAD_TOO_LARGE` before parsing |
| JSON/XML nesting | 32 levels | `NESTING_LIMIT_EXCEEDED` |
| Text line length | 4,096 bytes | `LINE_TOO_LONG` |
| PDB/mmCIF-like records | 250,000 | `RECORD_LIMIT_EXCEEDED` |
| Chains | 512 | `CHAIN_LIMIT_EXCEEDED` |
| Candidate membranes | 8 | `CANDIDATE_LIMIT_EXCEEDED`; never auto-select |
| Scalar string | 4,096 Unicode code points | `STRING_LIMIT_EXCEEDED` |
| Total decoded scalar fields | 1,000,000 | `FIELD_LIMIT_EXCEEDED` |
| Finite coordinate magnitude | 1,000,000 angstrom | `COORDINATE_OUT_OF_RANGE` |
| Normal norm | greater than `1e-12` | zero/smaller rejected |

The limits are safety ceilings, not claims that records near them are scientifically reasonable.
Adapters may impose smaller documented source limits. XML parsing disables DTDs and external
entities; XInclude is never processed. JSON rejects duplicate keys for identity, geometry,
transformation, version and scope fields. NaN, infinity, numeric overflow and non-UTF-8/ASCII input
are rejected.

Stage 4A rejects ZIP, TAR, GZIP and other containers. If Stage 4B accepts HTTP content encoding,
the wire body is capped at 5 MiB, decompressed bytes at 20 MiB, and the expansion ratio at 20:1.
Nested or user-supplied archives remain unsupported. Limits are enforced while streaming, not
after allocation.

## Threats and controls

| Threat | Example impact | Required controls |
|---|---|---|
| Malicious/malformed downloaded file | parser crash, memory exhaustion, false geometry | byte/field/depth limits; strict decoder; finite numeric checks; explicit formats; no generic deserialization |
| Oversized payload / parser denial of service | UI freeze or process exhaustion | pre-read size check; bounded streaming; record limits; no regex with catastrophic backtracking; deterministic linear passes |
| Path traversal / special file | overwrite/read outside intended file | local file picker only; resolve path; require regular file; no payload-derived output path; no device, UNC, symlink-following cache target |
| Compressed-file bomb | memory/disk exhaustion | reject archives in 4A; wire/decompressed/ratio limits in 4B; no nested archives |
| Script, template, macro or binary execution | arbitrary code execution | treat all content as data; never `eval`, load templates, execute macros, invoke PPM/TmDet, shell, or external converters |
| Arbitrary URL / SSRF | access private services or local files | no URL parameter; construct URL from source enum + validated ID; HTTPS allowlist; block IP literals, userinfo and non-default ports |
| Redirect abuse | leave allowlist, downgrade, credential leak | maximum three redirects; validate every hop; HTTPS only; same approved provider family; no auth headers |
| Response-size deception | memory exhaustion despite `Content-Length` | stream and count bytes; reject missing/false length only when actual cap is crossed |
| Cache poisoning / partial writes | replay wrong record | key includes provider, record ID, endpoint version and raw SHA; write temp file, fsync where supported, atomic replace; verify manifest/hash on read |
| Stale data | irreproducible reanalysis | immutable content-addressed entries; retrieval timestamp; explicit refresh; never silently replace old bytes; report cache status/hash |
| Identifier confusion | fetch wrong PDB/model | source-specific anchored regex; uppercase canonical PDB ID only after preserving supplied ID; returned record ID must match request |
| Chain/assembly mismatch | precise slab applied to wrong object | explicit namespace, assembly, model and exact chain-set checks; mismatch blocks membrane creation |
| Coordinate-frame mismatch | stale or unrelated slab | exact documented transform or fingerprint; no silent alignment; serialize source/current frames and matrix |
| Source service compromise | plausible malicious data | same strict parser/limits as local input; retain raw hash; warnings; never elevate source name to correctness |
| Untrusted HTML | script content or unstable scraping | never parse provider HTML as an orientation record; no scraping in core plugin |
| Provenance spoofing | local file claims to be official | distinguish `declared_source` from `retrieval_verified`; store final URL only for plugin retrieval; raw hash always authoritative |
| Symlink/cache race | overwrite/read unintended path | private cache directory, safe permissions, no user-controlled cache path components, atomic exclusive creation and post-open checks |

## Stage 4B network policy

Network is disabled by default and requires an explicit user action. Initial retrieval is limited to
a reviewed endpoint template such as:

```text
https://pdbtm.unitmp.org/api/v1/entry/{validated_pdb_id}.json
```

Defaults: 5 s connect timeout, 15 s read timeout, 30 s total deadline, three redirects, one active
request, no automatic retries except an explicit user retry, and honour `Retry-After`. Authentication
and credential collection are prohibited. Cookies are not persisted. Proxy behaviour follows the
host runtime but is disclosed in errors; proxy credentials are never logged.

The retrieval layer returns raw bytes and transport metadata. It does not parse scientific content.
Offline/manual workflows remain fully functional after DNS failure, timeout, TLS failure, HTTP
error, invalid content, or cache corruption. User-facing errors contain provider, identifier and
failure class but no traceback or sensitive environment values.

## Lifecycle response

A failed Run QC with imported orientation clears plugin-owned report and review/slab state under
the existing command lifecycle. A failed Show Slab clears only slab-owned state as currently
defined. Input molecular objects are preserved. Defensive exception handling is restricted to
known file/network/parser/PyMOL lifecycle boundaries; programming errors are not swallowed.

## Security acceptance tests

Tests must cover each row above, including payloads that cross each limit by one unit, redirects to
HTTP/private/unknown hosts, corrupted and swapped cache manifests, duplicate JSON keys, XML entity
declarations, deep nesting, NaN/infinity, misleading identifiers, and an official-looking local
file with no verified retrieval provenance.
