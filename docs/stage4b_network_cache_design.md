# Stage 4B network retrieval and cache design

Status: **COMPLETE**. The accepted design is implemented through Stage 4B1 (transport/cache core),
Stage 4B2 (schema 1.4/provenance), Stage 4B3 (GUI/PyMOL worker orchestration), and Stage 4B4
(exact-artifact acceptance). See `docs/stage4b1_implementation.md`,
`docs/stage4b2_implementation.md`, `docs/stage4b3_gui_orchestration.md`,
`docs/stage4b4_exact_acceptance.md`, and `docs/development_state.md` for completion evidence.

Stage 4B adds an optional, explicit way to retrieve the same two inputs already accepted by the
PDBTM offline-pair adapter and to store only complete validated pairs in a local cache. It does not
change membrane calculations, coordinate applicability, the selected PyMOL object, or the existing
offline workflow.

## Scope and exclusions

Stage 4B may retrieve exactly:

1. a PDBTM API-v1 JSON record; and
2. its PDBTM transformed-PDB companion.

The user continues to load and select the molecular object in PyMOL. Stage 4B does not retrieve
RCSB coordinates, replace the selected object, fit or align coordinates, or infer biological
correctness. It does not contact OPM or any mirror. The existing modes remain **Legacy global-z**,
**Planar orientation file**, and **PDBTM offline pair**; cached input is a subordinate source inside
the third mode, not a fourth orientation mode.

Explicitly deferred are OPM retrieval or adapters, PDBTM-versus-OPM comparison, source consensus,
ranking, biological verdicts, automatic fitting, batch CLI, model comparison, curved or multiple
membranes, automatic eviction, periodic refresh, telemetry, credentials, authenticated providers,
and all Stage 4C work.

## Read-only research synthesis

Six independent audits examined the provider, transport security, cache lifecycle, provenance,
PyMOL threading, and test/release strategy. Their conclusions agree on these boundaries:

- network access must be caused only by an explicit fetch action;
- retrieved bytes must pass the existing deterministic adapter before cache activation;
- raw payload hashes, not HTTP validators, establish byte identity;
- a complete immutable cache snapshot is the only path from network retrieval to later QC;
- transport/cache workers must never call PyMOL `cmd` or touch widgets;
- normal CI must be entirely independent of the live provider;
- schemas 1.0 through 1.3 and the current local-file workflow remain unchanged.

### Conflicts and resolutions

| Conflict | Resolution |
|---|---|
| `.trpdb` is linked by the official entry UI and usage guide but omitted from the OpenAPI format enum. | Treat it as an official UI-backed, empirically verified route with a documented stability risk. Stage 4B1 is a conditional GO behind mandatory low-volume manual preflights immediately before implementation and during Stage 4B4 exact-artifact acceptance. No substitute endpoint is permitted. |
| A general transport could permit same-host redirects, but the accepted endpoints currently return none. | Stage 4B1 permits zero redirects. Every 3xx is `REDIRECT_DISALLOWED` until its exact destination is independently reviewed and allowlisted in a later contract revision. Cross-host and HTTPS-to-HTTP redirects are always forbidden. |
| Atomic content-addressed writes can avoid torn blobs, but do not alone settle clear/read/refresh races. | Use immutable content-addressed blobs and manifests, atomic index replacement, generation checks, and one short-held cross-platform advisory cache lock. Network and scientific validation never hold the lock. |
| Schema 1.3 has payload hashes and URLs, but constrains retrieval evidence to unverified offline input. | Do not overload or modify 1.3. Stage 4B2 must propose a separately reviewed draft schema 1.4 for verified acquisition/cache provenance. Existing local offline reports remain schema 1.3. |
| A successful fetch could automatically become the selected source. | Fetch and Use are separate explicit actions. Retrieval may announce a validated snapshot but never select it or run QC. |
| Cache corruption could trigger an automatic older-snapshot fallback. | Fail closed with `CACHE_CORRUPT`. An older independently verified snapshot may be shown and selected explicitly, never silently. |
| Retrieval failure should preserve PyMOL state, while existing PDBTM analysis failures clear stale plugin state. | Keep these lifecycle domains separate. Fetch/cache errors are state-neutral. Once Run QC or Show Slab begins, the accepted full plugin-state cleanup remains unchanged. |
| Standard-library `urllib` is convenient but has broad automatic redirect/proxy behaviour. | The production transport is a narrow `http.client`/`ssl` implementation. `urllib` was used only by the one-off empirical measurement probe, not selected as the runtime contract. |
| Cancellation may race a validated cache publication. | A per-operation mutex linearizes `OPEN -> CANCELLED` against `OPEN -> COMMITTING`. Cancellation that wins prevents publication; once commit wins, publication may finish atomically but its stale GUI result is ignored and never auto-selected. |
| Proxy discovery varies by environment and can expose credentials or execute PAC/WPAD logic. | Stage 4B1 is direct HTTPS only and does not inspect or honor environment, Windows/macOS system, or PAC proxy configuration. Proxy support requires a later transport-contract revision. |
| Platform JSON defaults could make cache identities ambiguous. | Every cache JSON identity uses one versioned canonical UTF-8 encoding, explicit domain separation, fixed field sets, and cross-version/cross-platform golden vectors. |

## Provider contract

### Canonical record identifiers

Accept only ASCII legacy PDB identifiers matching `^[0-9][A-Za-z0-9]{3}$`. Strip no hidden
characters and reject whitespace, separators, drive prefixes, URL syntax, percent escapes, and
Unicode lookalikes. Normalize accepted identifiers to lowercase before request construction and
cache lookup.

Uppercase live requests currently return HTTP 500 rather than canonicalizing. Obsolete or replaced
identifiers have no reviewed redirect contract. The client must not rewrite an identifier to a
different record; a returned record ID must equal the canonical requested ID.

### Allowed requests

Only HTTPS GET on host `pdbtm.unitmp.org`, port 443, with these internally constructed paths:

```text
/api/v1/entry/{canonical_id}.json
/api/v1/entry/{canonical_id}.trpdb
```

No user-supplied URL, query, fragment, user information, alternate port, IP literal, mirror,
RCSB endpoint, or OPM endpoint is accepted. A complete fetch action requests both roles
sequentially and treats them as a non-atomic provider pair until validation succeeds.

The JSON route is described by the provider OpenAPI contract. The transformed-PDB route is exposed
by the official PDBTM usage material and live entry-page download link but is absent from the
OpenAPI format enum. Maintainer confirmation and OpenAPI inclusion remain requested provider
improvements.

### Provider response policy

- Accept status 200 only for a payload body. Status 304 is unsupported until real validators are
  published and tested.
- Accept the observed `text/plain; charset=UTF-8` for both roles; the JSON role may also accept
  `application/json` with absent or UTF-8 charset after tests. Reject HTML, XML, multipart,
  octet-stream, and unsupported charsets.
- Send `Accept-Encoding: identity` and reject every non-empty, non-identity `Content-Encoding`.
- Hash exact response bytes with SHA-256 before decoding.
- Decode JSON as strict UTF-8 and transformed PDB through the existing strict legacy-PDB parser.
- Record resource and software versions from each exact JSON payload. A future resource-version
  change does not alone reject the record; the reviewed field, matrix, and precision contracts do.
- Missing `ETag` and `Last-Modified` remain null/absent. They are never fabricated from dates or
  hashes.
- A plausible missing record currently produces HTML 500, not a dependable 404. Map an actual 404
  to `PROVIDER_NOT_FOUND`; map current 500 responses to `PROVIDER_SERVER_ERROR`.

## Component architecture

```text
Explicit GUI Fetch/Refresh
        |
        v
PdbtmProviderClient ---- fixed request builder / canonical ID
        |
        v
HttpTransport ---------- bounded HTTPS raw bytes + transport evidence
        |
        v
Existing PDBTM adapter - parsing and pair semantic validation
        |
        v
CacheRepository -------- immutable blobs/snapshot + atomic active pointer

Explicit Use cached pair
        |
        v
CacheRepository read/rehash/revalidate
        |
        v
Existing main-thread Run QC / Show Slab lifecycle
```

Network, provider, and cache modules remain pure Python and import neither Qt nor PyMOL. The
existing adapter remains a byte-only deterministic scientific boundary. Network retrieval never
feeds transient bytes directly to QC; it must first commit a complete validated snapshot.

## Transport interface and policy

Conceptual interface:

```python
class HttpTransport(Protocol):
    def get(
        self,
        request: HttpRequest,
        *,
        policy: TransportPolicy,
        cancellation: CancellationToken,
    ) -> HttpResponse: ...
```

`HttpRequest` is created only by the provider client from a canonical ID and fixed role.
`HttpResponse` contains exact raw bytes, requested/final approved URL, status, selected headers,
request/completion UTC times, and redirect evidence. It performs no parsing, caching, Qt, or PyMOL
work.

The Stage 4B1 defaults are:

- standard library only: `http.client`, `ssl`, `socket`, `urllib.parse`, `hashlib`, and `time`;
- ordinary certificate and hostname verification through `ssl.create_default_context()`;
- connect timeout 5 seconds, read-inactivity timeout 15 seconds, monotonic per-response total
  deadline 30 seconds, pair action ceiling 60 seconds;
- 64 KiB streaming reads;
- 5 MiB maximum per role and 10 MiB maximum per pair, including unknown/chunked lengths;
- zero redirects and zero automatic retries;
- cooperative cancellation checked before/after each blocking phase, every chunk, between roles,
  before validation, and before cache commit;
- `User-Agent: MembraneVisualQC/0.5.0.dev0` plus the public repository URL;
- no credentials, cookies, telemetry, referrer, machine/user identity, request body, or persistent
  connection pool.

DNS resolution cannot be guaranteed to stop immediately in CPython 3.10. Cancellation invalidates
the request immediately at the application layer; the worker may exit only at the bounded network
deadline. This limitation must be displayed honestly rather than using unsafe thread termination.

### Proxy policy

Stage 4B1 supports **direct HTTPS only**. It constructs `http.client.HTTPSConnection` only for the
fixed approved origin, sends an origin-form path, and uses that origin for `Host`, SNI, certificate,
and hostname verification. It does not read or honor `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, or
lowercase variants; Windows WinINET/Internet Options or WinHTTP proxy settings; macOS system proxy
settings; WPAD or PAC configuration. It never calls proxy-discovery APIs, evaluates or fetches PAC,
uses CONNECT tunnelling, emits an absolute-form request, or accepts proxy credentials or proxy
authentication. Normal direct TLS verification is unchanged.

Proxy support is deferred to a separate transport-contract and security review after Stage 4B1.
If proxy use is positively known without configuration discovery, such as an explicit proxy-mode
request reaching the transport boundary or HTTP 407, return `PROXY_UNSUPPORTED`. Do not inspect
proxy settings merely to choose this code. DNS, route, refusal, timeout, or reset cannot safely
prove that a proxy is required and remains `NETWORK_UNAVAILABLE`; TLS failures remain `TLS_ERROR`.
An existing valid cache remains usable in all cases.

### Logging and redaction

Logs may include provider, canonical ID, role, safe scheme/host/path, UTC times, status, selected
non-secret headers, size, SHA-256, and stable error code. Logs and reports must not include raw
bodies, cookies, proxy details or challenges, credentials, unrelated environment or system proxy
variables, local absolute cache paths, DNS addresses, usernames, hostnames, or GUI tracebacks.
Raw exception text is not logged when it could expose local network configuration.

## Validation boundary

Before cache activation, both payloads must pass:

1. HTTPS/host/path/status/content/size transport checks;
2. exact raw byte size and SHA-256 recording;
3. strict JSON and transformed-PDB parsing;
4. requested, returned, and companion record-ID consistency;
5. exact `pdbtm_json` plus `transformed_pdb` role/count contract;
6. existing resource/software/field/matrix/precision checks;
7. existing provider matrix, transformed companion, chain, assembly, and pair semantics;
8. cache-manifest construction and integrity validation.

Cache validation proves a coherent provider pair. Applicability against the user's currently
selected coordinates is repeated only when Run QC or Show Slab executes. Neither cache integrity
nor coordinate applicability is a biological correctness verdict. No fitting, alignment,
coordinate transformation, mutation, or silent fallback is allowed.

## Cache contract

### Root selection

An optional `MVQC_CACHE_DIR` override must be an absolute path; relative paths and unresolved `~`
are rejected.

- Windows: `%LOCALAPPDATA%\MembraneVisualQC\Cache`;
- macOS: `~/Library/Caches/MembraneVisualQC`;
- Linux/other POSIX: absolute `$XDG_CACHE_HOME/membrane-visual-qc`, otherwise
  `~/.cache/membrane-visual-qc`.

Append `pdbtm-api-v1/cache-v1`. Never use the current working directory and never serialize the
absolute cache root in a report. POSIX roots/files target modes 0700/0600; Windows relies on the
user-profile ACL and requires an exact bundled-Python ACL gate. Reject a cache-owned symlink,
junction, or reparse point and any path that escapes the resolved root.

### Layout

```text
<root>/pdbtm-api-v1/cache-v1/
  format.json
  locks/cache.lock
  index.json
  blobs/sha256/ab/<64-lowercase-hex>
  records/1pcr/snapshots/<snapshot-id>.json
  tmp/<uuid>.part
  quarantine/
```

Paths are constructed only from fixed components, canonical IDs, strict roles, UUID temporary
names, and lowercase 64-hex digests. Provider strings, URLs, and headers never form path segments.

### Canonical serialization and identities

Every hashed JSON core uses `mvqc-canonical-json-v1`. First validate its closed shape and types,
then serialize exactly as:

```python
json.dumps(
    core,
    ensure_ascii=False,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
```

The bytes have no BOM or trailing newline. Keys are fixed ASCII names; object keys sort
lexicographically and array order is prescribed. Values may be only objects, arrays, Unicode-scalar
strings without lone surrogates, integers, booleans, or null. Floats, `Decimal`, bytes, sets,
custom subclasses, NaN, and infinities are rejected; booleans do not satisfy integer fields.
Timestamps are UTC RFC 3339 exactly `YYYY-MM-DDTHH:MM:SS.ffffffZ`. Digests are lowercase 64-hex.
URLs are exact already-validated approved ASCII URLs and are not reparsed or reformatted during
serialization. There is no locale, newline, filesystem, current-directory, or OS dependence.

Identity is `SHA256(domain_prefix + canonical_json(core))`, hashed exactly once. Raw payload
digests remain ordinary SHA-256 of exact response bytes without a domain prefix.

`pair_id` uses domain `b"mvqc-pdbtm-pair-v1\0"`. Its exact `pair_core` keys are
`cache_contract` (`pdbtm-api-v1/cache-v1`), `provider` (`pdbtm_api_v1`),
`canonical_record_id`, and `payloads`. `payloads` contains exactly two entries, first
`pdbtm_json`, then `transformed_pdb`, each with exactly `role`, `sha256`, and integer `byte_size`.
It excludes `pair_id`, URLs, timestamps, headers, status, transport result, provider versions,
duration, paths, and package/install identity. Provider versions remain indirectly byte-bound by
the JSON payload digest.

`snapshot_id` uses domain `b"mvqc-pdbtm-snapshot-v1\0"`. Its exact `snapshot_core` keys are
`cache_contract`, `provider`, `canonical_record_id`, `pair_id`, ordered `payloads`,
`provider_versions`, `validation_profile`, and `validated_at`. Each acquisition payload has
exactly `role`, `sha256`, `byte_size`, `requested_url`, `final_url`, `requested_at`,
`completed_at`, integer `status` (200), `headers`, and `transport_verification`. `headers` is a
closed object containing `content_type` (`media_type` and `charset` lowercase after strict parse),
`content_encoding`, `etag`, and `last_modified`; absent permitted values are explicit null.
`transport_verification` is initially `direct_https_tls_verified`. `provider_versions` contains
exact string keys `resource_version` and `software_version`. Excluded are `snapshot_id`, durations
and monotonic time, operation/cancellation/generation state, paths, machine/user/package data,
logs, and bodies. The stored manifest envelope has exactly the keys `snapshot_id` and
`snapshot_core` and is itself written with canonical JSON; identity is recomputed from only
`snapshot_core`, and the filename must equal it. Repeated identical bytes may share a `pair_id`
while acquisition times produce different snapshots.

`index_id` uses domain `b"mvqc-pdbtm-index-v1\0"`. Exact `index_core` keys are
`cache_contract`, non-negative integer `generation`, and `records`, keyed by canonical record ID.
Each record has exactly non-negative integer `generation`, `active_snapshot_id` (64-hex or null),
and unique lexicographically sorted `snapshot_ids`; a non-null active ID must be a member. It
excludes `index_id`, timestamps, temp paths, locks/PIDs/writers, UI selection, and operation state.
`index.json` has exactly the keys `index_id` and `index_core`, is written with canonical JSON, and
is rehashed before use.

`format_id` uses domain `b"mvqc-pdbtm-format-v1\0"`. Exact `format_core` keys and values are
`cache_contract: pdbtm-api-v1/cache-v1`, `provider: pdbtm_api_v1`,
`canonical_json: mvqc-canonical-json-v1`, and `digest_algorithm: sha256`. It excludes `format_id`,
package/runtime version, creation time, platform, and paths. `format.json` has exactly the keys
`format_id` and `format_core` and is written with canonical JSON. A mismatch fails closed with
`CACHE_FORMAT_UNSUPPORTED`. Index/format digests detect torn or altered content; they are integrity
checks, not authentication against a hostile local user.

Stage 4B1 must freeze these golden vectors. Lengths cover the canonical core bytes, not the domain
prefix; each identity is SHA-256 of its listed domain followed by the exact UTF-8 bytes.

**Pair vector** — domain `mvqc-pdbtm-pair-v1\0`, 349 bytes, identity
`99b69dbd1b6c813dafb045747af410baade7001dfea9af905705728fa8e82c52`:

```text
{"cache_contract":"pdbtm-api-v1/cache-v1","canonical_record_id":"1pcr","payloads":[{"byte_size":283537,"role":"pdbtm_json","sha256":"38b2f724c4271a00bf2b83aa16015783610178f18d8954a88cb932b9152f36e0"},{"byte_size":628434,"role":"transformed_pdb","sha256":"7e52525ff397e4bfa5900e602f39753628e3b1408d513a3d0d76928c0fd10698"}],"provider":"pdbtm_api_v1"}
```

**Snapshot vector** — domain `mvqc-pdbtm-snapshot-v1\0`, 1,443 bytes, identity
`4bba46290d044828df412bb1f9fdc542bc440ba4aa99518664de6ef38f2e9ef5`:

```text
{"cache_contract":"pdbtm-api-v1/cache-v1","canonical_record_id":"1pcr","pair_id":"99b69dbd1b6c813dafb045747af410baade7001dfea9af905705728fa8e82c52","payloads":[{"byte_size":283537,"completed_at":"2026-07-20T00:00:01.000000Z","final_url":"https://pdbtm.unitmp.org/api/v1/entry/1pcr.json","headers":{"content_encoding":null,"content_type":{"charset":"utf-8","media_type":"text/plain"},"etag":null,"last_modified":null},"requested_at":"2026-07-20T00:00:00.000000Z","requested_url":"https://pdbtm.unitmp.org/api/v1/entry/1pcr.json","role":"pdbtm_json","sha256":"38b2f724c4271a00bf2b83aa16015783610178f18d8954a88cb932b9152f36e0","status":200,"transport_verification":"direct_https_tls_verified"},{"byte_size":628434,"completed_at":"2026-07-20T00:00:03.000000Z","final_url":"https://pdbtm.unitmp.org/api/v1/entry/1pcr.trpdb","headers":{"content_encoding":null,"content_type":{"charset":"utf-8","media_type":"text/plain"},"etag":null,"last_modified":null},"requested_at":"2026-07-20T00:00:02.000000Z","requested_url":"https://pdbtm.unitmp.org/api/v1/entry/1pcr.trpdb","role":"transformed_pdb","sha256":"7e52525ff397e4bfa5900e602f39753628e3b1408d513a3d0d76928c0fd10698","status":200,"transport_verification":"direct_https_tls_verified"}],"provider":"pdbtm_api_v1","provider_versions":{"resource_version":"1017","software_version":"3.2.134"},"validated_at":"2026-07-20T00:00:04.000000Z","validation_profile":"pdbtm-api-v1-format-precision-envelope-v1"}
```

**Index vector** — domain `mvqc-pdbtm-index-v1\0`, 265 bytes, identity
`b28cb5c9c519950f03af7a88ee37698d1646760e50bd7d4e09a8cd6a08ecc3cd`:

```text
{"cache_contract":"pdbtm-api-v1/cache-v1","generation":1,"records":{"1pcr":{"active_snapshot_id":"4bba46290d044828df412bb1f9fdc542bc440ba4aa99518664de6ef38f2e9ef5","generation":1,"snapshot_ids":["4bba46290d044828df412bb1f9fdc542bc440ba4aa99518664de6ef38f2e9ef5"]}}}
```

**Format vector** — domain `mvqc-pdbtm-format-v1\0`, 138 bytes, identity
`d1e17f7d64ece8a7423e7214bcbb4a4a65f6307cc3e1bc6b36fb49bc5bab5cd4`:

```text
{"cache_contract":"pdbtm-api-v1/cache-v1","canonical_json":"mvqc-canonical-json-v1","digest_algorithm":"sha256","provider":"pdbtm_api_v1"}
```

Golden tests must assert these exact bytes, lengths, and hashes on CPython 3.10, 3.11, and 3.12
and on Windows and Linux. Negative vectors must prove that reordered object insertion is identical;
reversed payload arrays are rejected rather than sorted; and BOM, CRLF, trailing newline, floats,
NaN/infinity, lone surrogates, uppercase digests, noncanonical timestamps, and nonapproved URLs are
rejected.

### Atomic commit algorithm

1. Lock briefly, validate the index, capture the record generation, then release.
2. Fetch, hash, parse, and validate both roles in memory without holding the lock.
3. Reacquire one global advisory cache lock and re-read the index. A changed generation returns
   `CACHE_CONFLICT`; it cannot resurrect a cleared or superseded record.
4. Write each missing blob to a same-filesystem temporary file, flush/fsync it, and atomically
   replace it at the hash path. Verify any existing blob is a regular non-link file with the exact
   size and hash.
5. Canonically write/fsync/replace the immutable snapshot manifest and verify its name/hash.
6. Write a complete new index and atomically replace `index.json` last; fsync containing
   directories where supported.
7. Release the lock. Orphan blobs/manifests remain inactive and are handled only by explicit
   maintenance.

The lock uses `fcntl.flock` on POSIX and `msvcrt.locking` on Windows behind one tested interface.
It covers only index/materialization/commit, read-to-memory, clear, and migration. It never covers
network I/O or scientific validation. Atomic replace remains mandatory; the lock is coordination,
not an integrity primitive.

### Cancellation and publication linearization

Each retrieval has a short-held in-process operation mutex guarding:

```text
OPEN -> CANCELLED
OPEN -> FAILED_PRE_COMMIT
OPEN -> COMMITTING -> COMMITTED
                   -> COMMIT_FAILED
```

`OPEN -> CANCELLED` and `OPEN -> COMMITTING` compete under that mutex. This is the authorization
linearization point. If cancellation wins while `OPEN`, no active-index replacement occurs, no
snapshot becomes active, and the result is `RETRIEVAL_CANCELLED`; temporary or immutable orphan
material may be removed or remain inactive. If commit wins, atomic publication may finish. Later
cancellation, dialog closure, ID change, or stale GUI generation suppresses UI delivery and
automatic selection, but does not interrupt, roll back, or corrupt publication.

Atomic replacement of `index.json` is the separate persistent activation linearization point.
Blobs and manifests materialized before it are inactive. Failure before replacement leaves the old
index active. Once replacement succeeds, the result is committed and must not claim that
publication was prevented.

The implementable sequence is: capture the record generation under the cache lock and release it;
fetch, hash, parse, validate, and prepare canonical bytes without either lock; take only the
operation mutex to attempt `OPEN -> COMMITTING` and release it; take only the cache lock, recheck
the generation, materialize, and replace the index last, then release it; finally take only the
operation mutex to record `COMMITTED` or `COMMIT_FAILED`. **The operation mutex and cache lock are
never held simultaneously.** The conceptual order is operation transition, cache commit,
operation completion, with a release between phases. Cache-lock-to-operation-mutex nesting is
forbidden. No network, validation, hashing, fsync, or complete filesystem commit holds the
operation mutex.

Cancel, close, and ID change invalidate GUI delivery immediately and cooperatively attempt
`OPEN -> CANCELLED`; they never terminate or synchronously join a worker thread. The UI may show
`Cancelling...` until the worker confirms whether cancellation won. A completion is applied only
when session UUID, generation, and request ID still match. If the cache commits but delivery is
stale, record:

```text
commit_state = COMMITTED
delivery_disposition = IGNORED_STALE
internal_outcome = COMMITTED_RESULT_IGNORED
```

This is informational, not `RETRIEVAL_CANCELLED`: the snapshot exists, but no source selection,
Use cached pair, PyMOL object change, slab rendering, QC, or report creation occurs automatically.
Post-replacement durability failure must not be described as an intact old pointer; required
durability capability is a Stage 4B1 gate, and uncertain post-commit durability is reported
distinctly rather than rolled back.

### Reads, refresh, corruption, and clear

Every read validates the index, manifest identity, exact two roles, regular/non-link blob paths,
sizes, and hashes while holding the short lock, then returns bytes in memory. Corrupt or partial
content is never passed to the adapter.

Refresh is explicit and preserves the last valid active snapshot until a complete new candidate
passes and is atomically activated. There is no conditional shortcut, periodic refresh,
age-derived freshness, automatic retry, or age-only deletion.

Clearing a selected record requires confirmation, increments a tombstone generation, removes its
active references, and cannot affect PyMOL objects or an already generated report. Blob garbage
collection is deferred until cross-record reference safety is implemented and reviewed. Cache
migration copies and revalidates into a new versioned root; it never rewrites cache-v1 in place.

## Provenance and schema decision

Released schema 1.3 cannot truthfully represent verified retrieval/cache provenance: it fixes the
adapter identity to the offline adapter, constrains `retrieval_verified` to false, and has no
strict fields for cache snapshot, acquisition versus selection origin, integrity validation,
request/final URL, or HTTP validators. Putting these facts in generic metadata would be semantic
abuse.

Therefore Stage 4B2 requires a separately reviewed **draft schema 1.4**. This design PR does not
create it. Conceptually it retains all schema-1.3 scientific evidence and adds a strict
`acquisition` block with:

- `selection_origin` and per-payload `acquisition_origin`;
- snapshot/pair IDs and validation time;
- exact roles, hashes, sizes, approved request/final URLs, retrieval times, content type,
  nullable ETag/Last-Modified, and transport verification;
- cache-integrity status;
- semantic equality checks against the scientific source digests;
- an explicit coordinate-applicability-only interpretation scope.

Existing local offline pair reports remain schema 1.3. Schemas and dispatch 1.0 through 1.3 remain
byte-identical. A verified cached snapshot, even when consumed offline later, uses schema 1.4 once
that schema is independently implemented and accepted. There is no downgrade from 1.4 to 1.3.

Transport confidence, cache integrity, coordinate applicability, and biological interpretation
remain four separate domains and never share an unqualified `verified` flag.

## PyMOL threading and GUI contract

Only `Fetch / Refresh PDBTM pair` authorizes network access. Importing the package, starting the
plugin, opening the dialog, switching modes, editing the ID, Run QC, Show Slab, selecting local
files, `Use cached pair`, and cache inspection perform no network operation.

Inside the existing PDBTM panel, the future GUI adds canonical ID, local/cached source, Fetch /
Refresh, Cancel, visible cache status, Use cached pair, Open cache location, and Clear selected
record. Local files remain the default.

### Thread boundary

Main Qt/PyMOL thread only:

- read/change widgets and show messages;
- capture the current PyMOL object;
- call every PyMOL `cmd` method;
- clear/render plugin objects and change `LAST_REPORT`;
- accept a matching worker result.

Worker only:

- transport, streaming, hashing, decoding, provider/pair validation;
- cache integrity, temporary files, locks, and atomic index work.

The worker imports neither PyMOL nor widgets and never tests applicability against a live object.
Use a lazily created `QObject` moved to `QThread` with queued signals. Each operation carries a
dialog/session UUID, monotonic generation, request ID, and cancellation token. A result is applied
only when session and generation still match. Close/cancel invalidates the generation immediately,
requests cooperative cancellation, and never uses `QThread.terminate()`. The publication contract
above decides whether cancellation truly prevented commit or the committed result is merely
ignored by a stale GUI.

### GUI state machine

Retrieval state:

```text
IDLE -> FETCHING -> AVAILABLE | FAILED
IDLE -> VERIFYING_CACHE -> AVAILABLE | FAILED
FETCHING -> CANCELLING -> CANCELLED | COMMITTED_RESULT_IGNORED
any active state + close/ID change -> stale generation; late result ignored
```

Selection state is independent:

```text
LOCAL_FILES
CACHED_UNSELECTED
CACHED_SELECTED(snapshot_id)
CACHED_SELECTION_UNAVAILABLE
```

Fetch success may advertise a newer snapshot but never changes the selection. `Use cached pair`
rehashes/revalidates the snapshot in a worker and selects it without running QC. Fetch, cache-read,
clear, and cancellation failures alter no PyMOL objects, slabs, selections, or report state.

Run QC and Show Slab remain network-free main-thread actions. Once either existing scientific
command lifecycle begins, it retains the accepted full stale-plugin-state cleanup and preserves
the user input object.

## Error contract

All expected failures expose a stable code, concise user message, retryability, whether an existing
validated cache remains selectable, and state-neutral retrieval cleanup. No error displays a raw
traceback or secret/local path.

| Code | Trigger and user-facing message | Retry | Existing valid cache | Retrieval lifecycle |
|---|---|---|---|---|
| `INVALID_RECORD_ID` | ID is not one canonical legacy PDB ID. “Enter a four-character PDB ID such as 1pcr.” | After input correction | Unchanged | No request or state change |
| `CACHE_MISS` | No complete selected snapshot. “No validated cached PDBTM pair is available.” | Explicit Fetch | None for that selection | PyMOL/report unchanged |
| `CACHE_CORRUPT` | Index, manifest, role, size, hash, link, or pair check fails. “Cached pair failed integrity validation and will not be used.” | Explicit Refresh | Another separately verified snapshot may be explicitly selected | Corrupt bytes never reach adapter |
| `CACHE_WRITE_FAILED` | Temp/blob/manifest/index/permission/lock commit fails. “The validated pair could not be saved; the previous cache remains active.” | Manual | Previous valid snapshot yes | Old pointer retained |
| `NETWORK_TIMEOUT` | Connect/read/total deadline or HTTP 408. “PDBTM did not respond within the allowed time.” | Manual | Yes | No activation |
| `NETWORK_UNAVAILABLE` | DNS, connection, route, or reset without safe evidence of proxy requirements. “The PDBTM service is currently unreachable.” | Manual | Yes | No activation |
| `PROXY_UNSUPPORTED` | Explicit proxy use reaches the transport boundary or HTTP 407 is received. “This version supports direct HTTPS connections only. Configure direct access or use an existing offline/cached PDBTM pair.” | After direct access is available | Yes | No proxy discovery, credentials, or activation |
| `TLS_ERROR` | Certificate, hostname, or TLS handshake failure. “Secure connection verification failed; no data was accepted.” | After environment/provider correction | Yes | No insecure fallback |
| `REDIRECT_DISALLOWED` | Any 3xx in Stage 4B1. “The provider redirected outside the reviewed endpoint contract.” | After contract review | Yes | Redirect target is not fetched |
| `RESPONSE_TOO_LARGE` | Declared or streamed body exceeds 5 MiB. “Provider response exceeded the safety limit.” | No unchanged retry | Yes | Stream aborted; no candidate |
| `PROVIDER_NOT_FOUND` | Actual HTTP 404. “PDBTM has no record for this identifier.” | After ID/provider change | Yes, explicitly | No activation |
| `PROVIDER_RATE_LIMITED` | HTTP 429. “PDBTM rate-limited this request; retry manually after the displayed interval.” | Manual after bounded Retry-After | Yes | No sleep/retry loop |
| `PROVIDER_SERVER_ERROR` | HTTP 5xx, including current ambiguous missing-ID 500. “PDBTM returned a server error; the record status is unknown.” | Manual | Yes | No automatic not-found inference |
| `PROVIDER_RESPONSE_INVALID` | Unsupported status/type/encoding or malformed role. “The provider response does not match the reviewed contract.” | Later explicit Refresh | Yes | Invalid pair not activated |
| `COMPANION_ID_MISMATCH` | JSON/companion/request record binding differs. “The two provider payloads do not identify one record.” | New explicit retrieval | Yes | Pair rejected |
| `PAIR_VALIDATION_FAILED` | Existing matrix, precision, scope, chain, assembly, or pair semantics fail. “The retrieved pair failed scientific contract validation.” | New explicit retrieval | Yes | Pair rejected; no fitting |
| `RETRIEVAL_CANCELLED` | Cancellation wins `OPEN -> CANCELLED` before commit authorization. “PDBTM retrieval was cancelled.” | New explicit action | Yes | No index replacement or activation |

Recommended internal additions are `CACHE_CONFLICT`, `CACHE_FORMAT_UNSUPPORTED`,
`CACHE_CLEAR_FAILED`, and `CACHE_OPEN_FAILED`; they require the same stable metadata contract.
`COMMITTED_RESULT_IGNORED` is informational: publication committed, but stale GUI delivery was
suppressed. It is never presented as a retrieval failure or proof that publication was cancelled.

## Security analysis

- **SSRF and redirects:** fixed HTTPS host/path construction, no arbitrary URLs, zero redirects.
- **TLS downgrade:** default trust roots and hostname checks; no `verify=False`, custom insecure
  context, or HTTP fallback.
- **Resource exhaustion:** 5 MiB role limits, 10 MiB pair limit, 64 KiB streaming, fixed deadlines,
  identity encoding only.
- **Cache poisoning:** raw hashes before decode, exact role/ID binding, semantic validation before
  activation, immutable manifest identity, rehash on every read.
- **Traversal and links:** strict IDs/hashes, containment checks, regular-file checks, symlink and
  Windows reparse rejection, same-filesystem atomic replacement.
- **Partial writes/races:** fsync + replace, pointer last, generation tombstones, global short lock,
  no network while locked.
- **Stale ambiguity:** retrieval and selection are separate; timestamps and snapshot IDs visible;
  no age-derived “fresh” label and no silent fallback.
- **Privacy:** no credentials, cookies, telemetry, payload logging, proxy disclosure, or machine
  identity.

## Sequential adversarial review

| Challenge | Finding and required control |
|---|---|
| Implicit network access | Only Fetch/Refresh constructs a request; add socket-guard tests for import, startup, dialog open, mode changes, offline commands, and cached use. |
| Endpoint instability | `.trpdb` is not OpenAPI-enumerated. Keep conditional GO, exact allowlist, manual live preflight, and provider-contact backlog; fail closed on any change. |
| Cache poisoning | TLS is insufficient. Require exact hashes, strict role/ID binding, existing semantic validation, canonical snapshot identity, and rehash on use. |
| Path traversal | No provider-derived paths; reject noncanonical IDs, links, reparse points, escape after resolution, drive/UNC/device forms, and post-check swaps. |
| Symlink attacks | Use no-follow/descriptor-relative operations where available, recheck opened regular files, and block Stage 4B1 until Windows reparse tests pass. |
| Partial writes | Index replacement occurs last; crash failpoints must prove readers see only old-complete or new-complete state. |
| Stale-data ambiguity | Never auto-select a refresh or silently fall back. Display retrieval time, pair/snapshot identity, and explicit older selection. |
| Provenance loss | Schema 1.3 cannot carry verified acquisition truthfully. Require separately reviewed draft 1.4 and semantic cross-checks in 4B2. |
| GUI deadlock | Never block close waiting for a worker; bounded timeouts, cooperative token, queued signals, session/generation guards, and normal QThread disposal. |
| Worker-thread PyMOL calls | Pure worker modules cannot import PyMOL; instrument `cmd` thread affinity in tests. Current-object applicability remains main-thread-only. |
| Coordinate mutation/fitting | Retrieved payloads are evidence only. The selected object remains user-owned; no align, fit, transform, replacement, or automatic source change. |
| Schema 1.3 modification | Freeze its bytes/hash and dispatch in every slice; local files continue to emit 1.3. |
| Hidden OPM/Stage 4C scope | Host/path allowlist is PDBTM-only; no provider abstraction may silently add a second live source in 4B. |
| Live-network CI dependence | Autouse non-loopback socket denial; fake transport and loopback server only. Mandatory live preflight occurs only at the two manual gates, remains low volume, and never controls ordinary PR CI. |
| Cancellation/commit race | Linearize `OPEN -> CANCELLED` against `OPEN -> COMMITTING`; index replacement is the activation point. A committed stale result is ignored, not misreported as cancelled. |
| Proxy ambiguity | Stage 4B1 is direct-only and performs no proxy discovery, PAC, CONNECT, or credential handling. Positively identified proxy use is `PROXY_UNSUPPORTED`; ambiguous connection failure remains `NETWORK_UNAVAILABLE`. |
| Cache identity drift | Closed cores, canonical JSON, domain-separated SHA-256, and Windows/Linux Python 3.10–3.12 golden vectors prevent serializer and field drift. |

The review found no design-level reason to modify runtime in this PR. The endpoint documentation
gap, Windows filesystem/lock behaviour, direct-only bundled-Python transport, and Qt shutdown
semantics remain explicit implementation gates. Proxy support is not a Stage 4B1 gate; it is
deferred to its own future transport-contract revision.

## Test strategy

Normal CI uses an injectable scripted fake transport for request/error logic and a loopback server
only for socket streaming, delayed/chunked bodies, redirects, malformed lengths, and size limits.
An autouse guard rejects every non-loopback socket. Official provider payloads are never committed;
synthetic fixtures remain the scientific oracle.

Stage 4B1 requires tests for canonicalization and all golden vectors, fixed requests, direct-only
proxy non-consultation, all status/error mappings, TLS/DNS exceptions, both sides of the
cancellation/commit boundary, redirects, MIME/encoding, exact and over-limit sizes,
compression rejection, pair mismatch, traversal/link/reparse attacks, content addressing,
corruption, every atomic commit failpoint, killed writers, concurrent writers/readers/clear,
refresh preservation, clear, migration, and offline cache use. Add a blocking `windows-latest`
cache/transport job or an equivalent required workflow for every cache change.

Direct-only tests poison every recognized proxy environment variable, including credential-like
values, and prove none are read, honored, or logged; spy that only the approved origin reaches
`HTTPSConnection`; prove `set_tunnel`, PAC/system discovery, absolute-form requests,
`Proxy-Authorization`, and proxy challenge logging never occur; and map HTTP 407 to
`PROXY_UNSUPPORTED`, ordinary connection failures to `NETWORK_UNAVAILABLE`, and TLS failures to
`TLS_ERROR`, with an existing cache unchanged.

The blocking race matrix places cancellation immediately before and after `OPEN -> COMMITTING`,
after index replacement but before terminal-state recording, and during bounded DNS/read; races
close and ID change on both sides of commit; races validation failure with cancellation; clears or
competing refreshes after captured generation; injects commit failure before index replacement;
destroys the dialog before queued completion; and proves an older worker may commit safely but
cannot overwrite a newer GUI selection. Crash failpoints around blob, manifest, index replacement,
and directory durability must expose only old-complete or new-complete state. No case uses forced
thread termination.

Stage 4B2 requires exact acquisition provenance, schema compatibility, structural validation,
retained nonlinear geometry validation, and new acquisition semantic validation.

Stage 4B3 requires worker thread-identity, stale-result, cancellation/close/shutdown, duplicate
request, import/startup/dialog no-network, state-neutral fetch failure, and all retained PyMOL
lifecycle regressions.

Low-volume manual provider preflight is mandatory immediately before Stage 4B1 implementation
begins and again during Stage 4B4 exact-artifact acceptance. Each gate is limited to the reviewed
official host, paths, and records; is non-bulk and non-scientific evidence; stores raw bytes only
under ignored `.local/`; and fails closed if route, host, redirect, MIME, payload, or semantic
contract changes. It remains outside ordinary PR CI. A transient provider outage delays the
manual gate but does not fail ordinary offline CI. This documentation correction requires no new
live request; the existing evidence is reused and must be refreshed only if it is no longer
current when Stage 4B1 actually starts.

## Implementation slices and acceptance gates

### Stage 4B1 — pure-Python transport, provider client, cache

No Qt, PyMOL, report, or schema changes. Gates: the mandatory immediate pre-implementation
low-volume provider preflight confirms the conditional route; direct bundled-Python TLS GET and
direct-only/non-consultation tests pass; fake/loopback security and cancellation-linearization
suites pass; Linux and Windows atomic/cache suite passes; no implicit network; exact adapter pair
validation; independent security review; no official payload tracked or packaged.

### Stage 4B2 — provenance/report integration and draft schema 1.4

Add acquisition domain and separately reviewed draft 1.4 without changing schemas 1.0–1.3.
Gates: exact network/cache provenance, semantic cross-checks, old report validation, explicit CSV
policy, no Qt/PyMOL changes, schema review approval.

### Stage 4B3 — PyMOL worker and GUI workflow

Add explicit Fetch/Refresh and cached selection while preserving the local pair. Gates: every
thread/lifecycle/no-network test, headless sequential regression, exact Incentive PyMOL Qt binding
probe, and focused graphical pre-acceptance.

### Stage 4B4 — exact-artifact graphical and network/cache acceptance

Install the exact deterministic ZIP in Incentive PyMOL 3.1.8 / Python 3.10.20 / Windows 10.
Verify explicit live fetch, cache/offline use, refresh, cancel, failure preservation, clear,
disconnected operation, local-pair regression, exact provenance, and genuine screenshots. Release
preparation remains separate. Repeat the mandatory reviewed low-volume provider preflight as part
of this exact-artifact gate; a changed route, host, redirect, MIME, payload, or semantic contract
fails closed.

## Acceptance decision and deferred work

**Design: GO. Stage 4B1: CONDITIONAL GO.** The official provider successfully serves both accepted
pairs and the official UI exposes the transformed companion, but the OpenAPI omission prevents an
unqualified stability claim. Stage 4B1 may start only with this risk visible, strict fail-closed
allowlisting, the mandatory immediate pre-implementation manual provider preflight, and the
blocking Windows/direct-transport/cache gates above. The same manual preflight is mandatory again
during Stage 4B4 exact-artifact acceptance.

No runtime retrieval, cache implementation, schema file, GUI change, scientific change, OPM work,
or Stage 4C comparison is part of this design branch.
