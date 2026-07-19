# Stage 4B network retrieval and cache design

Status: design accepted for draft review; no runtime implementation exists.

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
| `.trpdb` is linked by the official entry UI and usage guide but omitted from the OpenAPI format enum. | Treat it as an official UI-backed, empirically verified route with a documented stability risk. Stage 4B1 is a conditional GO, subject to the route continuing to pass a low-volume manual preflight. No substitute endpoint is permitted. |
| A general transport could permit same-host redirects, but the accepted endpoints currently return none. | Stage 4B1 permits zero redirects. Every 3xx is `REDIRECT_DISALLOWED` until its exact destination is independently reviewed and allowlisted in a later contract revision. Cross-host and HTTPS-to-HTTP redirects are always forbidden. |
| Atomic content-addressed writes can avoid torn blobs, but do not alone settle clear/read/refresh races. | Use immutable content-addressed blobs and manifests, atomic index replacement, generation checks, and one short-held cross-platform advisory cache lock. Network and scientific validation never hold the lock. |
| Schema 1.3 has payload hashes and URLs, but constrains retrieval evidence to unverified offline input. | Do not overload or modify 1.3. Stage 4B2 must propose a separately reviewed draft schema 1.4 for verified acquisition/cache provenance. Existing local offline reports remain schema 1.3. |
| A successful fetch could automatically become the selected source. | Fetch and Use are separate explicit actions. Retrieval may announce a validated snapshot but never select it or run QC. |
| Cache corruption could trigger an automatic older-snapshot fallback. | Fail closed with `CACHE_CORRUPT`. An older independently verified snapshot may be shown and selected explicitly, never silently. |
| Retrieval failure should preserve PyMOL state, while existing PDBTM analysis failures clear stale plugin state. | Keep these lifecycle domains separate. Fetch/cache errors are state-neutral. Once Run QC or Show Slab begins, the accepted full plugin-state cleanup remains unchanged. |
| Standard-library `urllib` is convenient but has broad automatic redirect/proxy behaviour. | The production transport is a narrow `http.client`/`ssl` implementation. `urllib` was used only by the one-off empirical measurement probe, not selected as the runtime contract. |

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

Stage 4B1 may honor the operating system's HTTPS proxy discovery only for an unauthenticated HTTP
CONNECT proxy. Reject proxy URLs containing credentials and unsupported proxy schemes. Never log
the proxy URL, host, user information, environment variable, or `Proxy-Authorization`. Direct
connection remains the default when no proxy is configured. Exact direct and proxy behaviour in
the bundled PyMOL Python is a blocking Stage 4B1 test gate; TLS verification is never weakened to
accommodate a proxy.

### Logging and redaction

Logs may include provider, canonical ID, role, safe scheme/host/path, UTC times, status, selected
non-secret headers, size, SHA-256, stable error code, and a boolean that a proxy was used. Logs and
reports must not include raw bodies, cookies, proxy details, credentials, unrelated environment
variables, local absolute cache paths, DNS addresses, usernames, hostnames, or GUI tracebacks.

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

`pair_id` is the SHA-256 of a versioned canonical representation containing the cache contract,
canonical record ID, and ordered `(role, SHA-256, byte_size)` entries. A snapshot manifest adds
per-role approved URLs, transport status/headers, retrieval times, provider versions, validation
time/profile, and `pair_id`. `snapshot_id` is the SHA-256 of the canonical UTF-8 manifest core.
Repeated retrieval of identical bytes may create a new retrieval snapshot while retaining the
same `pair_id`.

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
requests cooperative cancellation, and never uses `QThread.terminate()`.

### GUI state machine

Retrieval state:

```text
IDLE -> FETCHING -> AVAILABLE | FAILED
IDLE -> VERIFYING_CACHE -> AVAILABLE | FAILED
FETCHING -> CANCELLING -> CANCELLED
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
| `NETWORK_UNAVAILABLE` | DNS, connection, route, reset, or unsupported proxy. “The PDBTM service is currently unreachable.” | Manual | Yes | No activation |
| `TLS_ERROR` | Certificate, hostname, or TLS handshake failure. “Secure connection verification failed; no data was accepted.” | After environment/provider correction | Yes | No insecure fallback |
| `REDIRECT_DISALLOWED` | Any 3xx in Stage 4B1. “The provider redirected outside the reviewed endpoint contract.” | After contract review | Yes | Redirect target is not fetched |
| `RESPONSE_TOO_LARGE` | Declared or streamed body exceeds 5 MiB. “Provider response exceeded the safety limit.” | No unchanged retry | Yes | Stream aborted; no candidate |
| `PROVIDER_NOT_FOUND` | Actual HTTP 404. “PDBTM has no record for this identifier.” | After ID/provider change | Yes, explicitly | No activation |
| `PROVIDER_RATE_LIMITED` | HTTP 429. “PDBTM rate-limited this request; retry manually after the displayed interval.” | Manual after bounded Retry-After | Yes | No sleep/retry loop |
| `PROVIDER_SERVER_ERROR` | HTTP 5xx, including current ambiguous missing-ID 500. “PDBTM returned a server error; the record status is unknown.” | Manual | Yes | No automatic not-found inference |
| `PROVIDER_RESPONSE_INVALID` | Unsupported status/type/encoding or malformed role. “The provider response does not match the reviewed contract.” | Later explicit Refresh | Yes | Invalid pair not activated |
| `COMPANION_ID_MISMATCH` | JSON/companion/request record binding differs. “The two provider payloads do not identify one record.” | New explicit retrieval | Yes | Pair rejected |
| `PAIR_VALIDATION_FAILED` | Existing matrix, precision, scope, chain, assembly, or pair semantics fail. “The retrieved pair failed scientific contract validation.” | New explicit retrieval | Yes | Pair rejected; no fitting |
| `RETRIEVAL_CANCELLED` | User cancel, close, or stale request generation. “PDBTM retrieval was cancelled.” | New explicit action | Yes | Late UI/cache activation forbidden |

Recommended internal additions are `CACHE_CONFLICT`, `CACHE_FORMAT_UNSUPPORTED`,
`CACHE_CLEAR_FAILED`, and `CACHE_OPEN_FAILED`; they require the same stable metadata contract.

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
| Live-network CI dependence | Autouse non-loopback socket denial; fake transport and loopback server only. Live preflight is manual, low volume, non-blocking for ordinary PR CI. |

The review found no design-level reason to modify runtime in this PR. The endpoint documentation
gap, Windows filesystem/lock behaviour, bundled-Python proxy behaviour, and Qt shutdown semantics
remain explicit implementation gates.

## Test strategy

Normal CI uses an injectable scripted fake transport for request/error logic and a loopback server
only for socket streaming, delayed/chunked bodies, redirects, malformed lengths, and size limits.
An autouse guard rejects every non-loopback socket. Official provider payloads are never committed;
synthetic fixtures remain the scientific oracle.

Stage 4B1 requires tests for canonicalization, fixed requests, all status/error mappings, TLS/DNS
exceptions, cancellation boundaries, redirects, MIME/encoding, exact and over-limit sizes,
compression rejection, pair mismatch, traversal/link/reparse attacks, content addressing,
corruption, every atomic commit failpoint, killed writers, concurrent writers/readers/clear,
refresh preservation, clear, migration, and offline cache use. Add a blocking `windows-latest`
cache/transport job or an equivalent required workflow for every cache change.

Stage 4B2 requires exact acquisition provenance, schema compatibility, structural validation,
retained nonlinear geometry validation, and new acquisition semantic validation.

Stage 4B3 requires worker thread-identity, stale-result, cancellation/close/shutdown, duplicate
request, import/startup/dialog no-network, state-neutral fetch failure, and all retained PyMOL
lifecycle regressions.

Live-provider testing is manually triggered only, performs at most the four pair GETs plus a few
reviewed probes, stores all raw bytes under `.local/`, and never determines ordinary CI success.

## Implementation slices and acceptance gates

### Stage 4B1 — pure-Python transport, provider client, cache

No Qt, PyMOL, report, or schema changes. Gates: conditional provider route remains valid; direct
bundled-Python TLS GET passes; fake/loopback security suite passes; Linux and Windows atomic/cache
suite passes; no implicit network; exact adapter pair validation; independent security review; no
official payload tracked or packaged.

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
preparation remains separate.

## Acceptance decision and deferred work

**Design: GO. Stage 4B1: CONDITIONAL GO.** The official provider successfully serves both accepted
pairs and the official UI exposes the transformed companion, but the OpenAPI omission prevents an
unqualified stability claim. Stage 4B1 may start only with this risk visible, strict fail-closed
allowlisting, an optional manual provider preflight, and the blocking Windows/PyMOL transport and
cache gates above.

No runtime retrieval, cache implementation, schema file, GUI change, scientific change, OPM work,
or Stage 4C comparison is part of this design branch.
