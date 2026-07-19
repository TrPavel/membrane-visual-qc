# Stage 4B official-provider preflight

Status: complete for design review. Raw provider material is local-only and not committed.

## Date and environment

- preflight date: 2026-07-20 (Europe/Moscow);
- response dates: 2026-07-19 23:01:54–23:01:59 UTC;
- OS: Windows 10 build 26200;
- Incentive PyMOL: 3.1.8 installation;
- bundled Python: CPython 3.10.20;
- bundled OpenSSL: OpenSSL 3.6.1, 27 January 2026;
- active source version: `0.5.0.dev0`.

`ssl.create_default_context()` reported `CERT_REQUIRED` and hostname checking enabled. The bundled
environment successfully performed explicit HTTPS GET requests to the official provider. Its
standard-library `ssl`, `socket`, `http.client`, `urllib`, `hashlib`, `gzip`, and `zlib` facilities
are available. This is evidence that the necessary primitives and direct certificate verification
work in the accepted graphical Python environment; it is not yet acceptance of a production
transport implementation.

The default Windows cache rule `%LOCALAPPDATA%\MembraneVisualQC\Cache` was writable. A temporary
file was flushed and atomically replaced on the target filesystem, then read back with the expected
SHA-256. Windows lock, ACL, reparse-point, concurrent writer, and open-file semantics remain Stage
4B1 gates.

An import probe blocked socket creation while importing `membrane_vqc` and `membrane_vqc.gui` and
observed zero network attempts. No Stage 4B runtime exists, so dialog-open network absence is also
established by current-code inspection rather than by claiming a future GUI test has passed.

## Official sources consulted

- [PDBTM OpenAPI UI](https://pdbtm.unitmp.org/api/documentation/pdbtm)
- [PDBTM raw OpenAPI document](https://pdbtm.unitmp.org/docs/pdbtm?pdbtm-api-docs.json)
- [PDBTM usage guide](https://pdbtm.unitmp.org/usage)
- [PDBTM documents/user manual](https://pdbtm.unitmp.org/documents)
- [official 1pcr entry page](https://pdbtm.unitmp.org/entry/1pcr)

The inspected OpenAPI document declares OpenAPI 3.0.0 and API-document version 1.0.0. The retained
local copy is 1,915 bytes with SHA-256
`0447baa387a340b37a685f48c0e3561a7996d249da7b5664529526ec4517e971`.

The OpenAPI path template is `GET /v1/entry/{code}.{format}` under server
`https://pdbtm.unitmp.org/api`; its format enum includes JSON but omits `trpdb`. The official usage
material and live entry page nevertheless expose the transformed-PDB download link. This gap is
the principal provider-contract qualification.

## Methodology and local evidence

A one-off, non-distributed Python probe used the bundled Python and ordinary certificate
verification. It issued seven low-volume GET requests:

1. JSON and transformed-PDB for `1pcr`;
2. JSON and transformed-PDB for `1a0s`;
3. one conditional request for `1pcr.json`;
4. one uppercase `1PCR.json` request;
5. one syntactically plausible absent-record probe, `9zzz.json`.

The probe sent `Accept-Encoding: identity`, imposed a 5 MiB read bound, recorded exact raw hashes
before decoding, retained only selected non-secret headers, and stored responses beneath ignored
`.local/stage4b-preflight/`. It recorded no cookies, credentials, proxy details, unrelated
environment variables, or absolute local paths in its manifest.

Local manifest:

```text
.local/stage4b-preflight/manifest.json
```

Manifest size: 20,779 bytes. Manifest SHA-256:
`2cd243786896a260ce66427035d2e39da4d78e225f94e3cefbc9c07cb712327c`.

The manifest and all raw responses remain outside Git. The one-off probe itself resides outside
the repository and is not part of package, source distribution, Plugin ZIP, or PR contents.

## Exact endpoint templates

```text
GET https://pdbtm.unitmp.org/api/v1/entry/{lowercase_id}.json
GET https://pdbtm.unitmp.org/api/v1/entry/{lowercase_id}.trpdb
```

All four successful requests finished on `pdbtm.unitmp.org` at the requested URL with zero
redirects.

## Payload observations

| Record | Role | Status | Bytes | SHA-256 | Parsing |
|---|---|---:|---:|---|---|
| `1pcr` | `pdbtm_json` | 200 | 283,537 | `38b2f724c4271a00bf2b83aa16015783610178f18d8954a88cb932b9152f36e0` | strict UTF-8 JSON PASS |
| `1pcr` | `transformed_pdb` | 200 | 628,434 | `7e52525ff397e4bfa5900e602f39753628e3b1408d513a3d0d76928c0fd10698` | ASCII legacy PDB PASS |
| `1a0s` | `pdbtm_json` | 200 | 425,370 | `22b3985dc13b14520b5507b3ec022211d4c281bdf30f2cdef057073305294f62` | strict UTF-8 JSON PASS |
| `1a0s` | `transformed_pdb` | 200 | 823,920 | `f228413887e409312fba5ce76108836856fef62815b1bd8e4ffd97beb01f0b54` | ASCII legacy PDB PASS |

The four hashes are identical to the accepted earlier official-payload observations. This shows
snapshot stability across the observations; it is not a permanent content guarantee.

Both JSON records declare:

- canonical lowercase record ID;
- `resource_version` raw string `" 1017"`, normalized for provenance/comparison to `1017`;
- provider `software_version` `3.2.134`.

Trimming the version for comparison does not authorize rewriting the raw provider payload. Future
resource-version changes are evaluated through the reviewed field, matrix, and precision contract,
not rejected solely for being newer.

## Headers, encoding, and redirects

All four successful payload responses reported:

- `Content-Type: text/plain; charset=UTF-8`;
- `Cache-Control: no-cache, private`;
- `Vary: Origin,Accept-Encoding`;
- no redirect;
- no `ETag`;
- no `Last-Modified`;
- no `Content-Encoding` when identity encoding was requested;
- no dependable `Content-Length` in the observation.

The transformed payloads were ASCII-only within the declared UTF-8 response. Content type does not
distinguish JSON from transformed PDB, so role-specific parsing and exact endpoint binding remain
mandatory.

## Conditional, case, and missing-record observations

A conditional `1pcr.json` GET sent a deliberately nonmatching `If-None-Match` and a future
`If-Modified-Since`. The provider returned status 200 with the complete 283,537-byte payload and the
same SHA-256, not 304. No validator headers were supplied. Conditional refresh therefore has no
reviewed benefit and is deferred; Stage 4B1 performs an explicit full GET/hash/validation.

Uppercase `1PCR.json` returned status 500 with a 6,609-byte HTML response, zero redirects, and
SHA-256 `cbe48223f81a7c52f1b49c7a66e54b592d94075fa8ead2246d9dab5f86334eba`.
The client must lowercase a valid identifier before constructing the URL.

Plausible missing identifier `9zzz.json` returned the same status-500 HTML response rather than a
404 or structured not-found document. A live 404, if later observed, maps to
`PROVIDER_NOT_FOUND`; current 500 responses remain `PROVIDER_SERVER_ERROR`. No obsolete-ID redirect
or replacement-ID contract was evidenced.

## Pair semantics and coordinate applicability

Fresh bytes were passed through the existing deterministic PDBTM API-v1 adapter. Using the
transformed companion itself as the current identity-frame structure, both pairs imported and
passed exact role, provider, matrix, precision, scope, chain, companion, and pair validation.

Prior local official deposited-coordinate references were used only to repeat analytical-inverse
applicability; no RCSB request occurred in this Stage 4B preflight.

| Record | Identity RMSD / maximum residual | Inverse RMSD / maximum residual | Result |
|---|---|---|---|
| `1pcr` | 0 / 0 Å | 0.000501969 / 0.000834950 Å | identity and inverse imported |
| `1a0s` | 0 / 0 Å | 0.000501151 / 0.000846301 Å | identity and inverse imported |

Both inverse observations are below the accepted runtime inverse limit of 0.003 Å. These checks
prove coordinate applicability to the exact tested coordinate references, not biological
correctness.

## Compatibility observations

The exact bundled Python environment demonstrated:

- SSL and normal official-host certificate verification: PASS;
- explicit official HTTPS GET: PASS;
- strict raw hashing and bounded reads: PASS;
- writable default user-cache rule: PASS;
- same-filesystem atomic replacement: PASS;
- package and GUI-module import with network blocked: PASS.

Still required for Stage 4B1:

- production `http.client` transport tests rather than the measurement probe;
- direct and system-proxy behavior without credential leakage;
- connect/read/total timeout and cooperative cancellation tests;
- Windows lock, ACL, junction/reparse, concurrent process, and interrupted-write tests;
- mandatory non-live fake/loopback CI, including a Windows runner or equivalent required gate.

Still required for Stage 4B3:

- an instrumented graphical dialog-open test proving zero transport calls;
- exact PyQt/PySide worker, close, cancellation, and shutdown behavior in Incentive PyMOL 3.1.8.

## Provider risks and unresolved questions

1. `.trpdb` is official UI-backed but not enumerated by the OpenAPI document.
2. Missing and uppercase records produce ambiguous server errors.
3. No ETag, Last-Modified, conditional 304 behavior, or atomic pair-version token is available.
4. Rate-limit headers have been observed previously, but no stable public window/policy was found.
5. Obsolete/replaced PDB ID behavior is unverified.
6. Payload redistribution terms were not established; official raw bytes remain outside Git.
7. A future cross-host redirect, compression change, MIME change, field/matrix change, or precision
   change fails closed pending review.

Recommended provider follow-up is to request that PDBTM/UniTmp add `trpdb` and structured error
responses to OpenAPI and clarify canonicalization, obsolete records, rate limits, validators, and
endpoint stability.

## Go/no-go conclusion

**Design: GO. Stage 4B1: CONDITIONAL GO.**

The exact two official payloads are retrievable, unchanged for the accepted records, parseable,
and compatible with the current adapter. The official UI-backed transformed companion makes an
implementation slice empirically viable, but its omission from the OpenAPI enum prevents an
unqualified stability claim.

Stage 4B1 may begin only under the fixed allowlist, fail-closed response contract, no-live-network
normal CI, blocking Windows/cache tests, and optional low-volume manual provider preflight defined
in the design. No runtime retrieval, cache, GUI, or schema work has started in this PR.
