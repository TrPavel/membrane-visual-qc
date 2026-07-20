# Stage 4B1 transport and cache core

Status: implemented on the draft Stage 4B1 branch; not exposed through PyMOL or the GUI.

## Scope and boundaries

Stage 4B1 adds a pure-Python, opt-in core for retrieving and retaining one validated PDBTM API-v1
JSON/transformed-PDB pair. The package version remains `0.5.0.dev0`.

- `pdbtm_errors.py` defines stable, redacted error codes and handling metadata.
- `pdbtm_transport.py` owns the fixed direct-HTTPS request and bounded response policy.
- `pdbtm_provider.py` validates a transient pair with the existing deterministic offline adapter.
- `pdbtm_cache_contract.py` owns canonical JSON models and domain-separated identities.
- `pdbtm_cache.py` owns safe storage, locking, integrity reads, generations, commit and clear.
- `pdbtm_retrieval.py` owns cancellation/publication linearization and stale delivery disposition.

These modules do not import PyMOL, Qt, GUI code, command registration, report generation or schema
dispatch. Package import performs no network request and creates no cache. Existing PyMOL workflows
remain offline. Cached data are not yet report inputs and schema 1.4 does not exist.

The intentionally small core surfaces are `PdbtmHttpsTransport.fetch()`,
`PdbtmProviderClient.fetch()`, `validate_pdbtm_pair()`, `PdbtmCacheRepository` read/inspect/list/
commit/clear operations, and `retrieve_validate_and_commit()`. Canonical dataclasses and serializers
are public only to the internal persistence boundary; no Stage 4B1 symbol is re-exported from the
package top level.

## Provider-entry preflight

The mandatory pre-implementation gate passed on 2026-07-20 using Windows 10 build 26200 and the
Incentive PyMOL 3.1.8 bundled CPython 3.10.20. Exactly four direct, verified HTTPS GET requests were
made: JSON and transformed-PDB roles for `1pcr` and `1a0s`. All byte sizes, SHA-256 digests,
identifiers, provider versions, matrices, precision profiles and adapter results matched the
accepted observations. Raw responses and the sanitized manifest remain ignored under
`.local/stage4b1-entry-preflight/`; no official response is tracked or packaged.

## Direct transport

Only `https://pdbtm.unitmp.org:443/api/v1/entry/{id}.json` and `.trpdb` are constructible. Record
IDs use the four-character ASCII PDB grammar and are normalized to lowercase. The implementation
uses `ssl.create_default_context()` and `http.client.HTTPSConnection`, an origin-form request,
`Accept-Encoding: identity`, one connection per response, no redirects, no retries and no proxy
discovery or tunnelling. Connect, inactivity, response and pair deadlines are respectively 5, 15,
30 and 60 seconds. Reads use 64 KiB chunks with 5 MiB per-role and 10 MiB pair limits. Only
allow-listed, parsed transport evidence is retained; exception, credential and proxy details are
not copied into user-visible errors.

`Stage4BError` exposes only a stable code, safe user message, manual-retry hint and whether a prior
cache may remain usable. Codes cover invalid ID; cache miss/corruption/open/write/clear/conflict/
unsupported format/uncertain durability; network unavailable/timeout/TLS/proxy/redirect/size;
provider not found/rate limited/server/invalid response; companion mismatch; pair validation; and
cancellation. `COMMITTED_RESULT_IGNORED` is an informational delivery outcome, not an exception.

## Cache contract and repository

The cache uses `mvqc-canonical-json-v1`: UTF-8, sorted fixed ASCII keys, compact separators, no BOM
or newline, closed shapes, prescribed role order, scalar-valid Unicode, exact timestamps, lowercase
digests, strict integers, and no floats. Pair, snapshot, index and format IDs use separate SHA-256
domains. The four accepted golden vectors are frozen in cross-platform tests.

The platform cache root is independent of the current working directory. `MVQC_CACHE_DIR`, when
set, must be an absolute local path; UNC/device paths, unresolved `~`, symlinks, junctions, reparse
points and non-regular cache objects fail closed. Immutable blobs and manifests are written through
same-filesystem temporary files. A complete canonical index is replaced last. One bounded advisory
lock uses `fcntl.flock` on POSIX or one-byte `msvcrt.locking` on Windows. Network and scientific
validation never hold that lock. Reads verify every layer and never fall back to an older snapshot
after corruption. Clear records a higher tombstone generation so an in-flight refresh cannot
resurrect cleared state. Inactive orphan material may remain; garbage collection and migration are
deferred.

Windows existing-file opens use `CreateFileW` with `FILE_FLAG_OPEN_REPARSE_POINT`, inspect the
opened handle, and recheck cache-owned directory components around path operations. POSIX uses
`O_NOFOLLOW` where available and opened-descriptor metadata on every read. These controls and
content hashes protect normal integrity and concurrent plugin operations; the cache is not an
authentication boundary against a hostile same-user process that can continuously replace parent
directories or mutate a hard-linked file. Such interference fails integrity checks where observed
and must never be interpreted as verified provider authenticity.

## Cancellation and publication

`OPEN -> CANCELLED` competes with `OPEN -> COMMITTING` under a short in-process mutex. Cancellation
before authorization prevents activation. After authorization, publication completes or fails
without rollback; later cancellation only invalidates delivery. A committed stale result is
classified internally as `COMMITTED_RESULT_IGNORED`. The operation mutex and cache lock are never
held together, and no thread is forcibly terminated.

## Validation gates

Ordinary tests install an autouse non-loopback socket guard and use fake transports or loopback
only. They cover fixed requests, proxy non-consultation, response bounds, canonical vectors,
filesystem attacks, corruption, generations, atomic failpoints, process-safe locking and
cancellation races. CI retains the three Ubuntu Python jobs and blocking FreeSASA job, and adds a
blocking Windows Python 3.10 Stage 4B1 core job. Artifact validation requires every runtime module
and rejects cache/preflight paths and the exact accepted official provider bodies even if renamed.

The exact bundled-Python core smoke is a manual gate after green draft-PR CI. Its two live requests
are restricted to the accepted `1pcr` pair; all raw bytes and sanitized evidence remain under
ignored `.local/` storage.

## Deferred work

Stage 4B2 (schema/report integration), Stage 4B3 (GUI and PyMOL orchestration), Stage 4B4 (final
provider acceptance) and Stage 4C have not started. Proxy/PAC/CONNECT support, cache migration,
automatic garbage collection, RCSB/OPM retrieval, fitting and automatic source selection remain
outside this slice.
