# Stage 4B2 provenance and report schema 1.4

Status: complete and merged. Schema 1.4 provenance is used by the explicit validated-cache PDBTM
workflow added in Stage 4B3.

## Scope and boundaries

Stage 4B2 adds a typed, immutable report-provenance model for a validated Stage 4B1 PDBTM cache
result, a new draft report schema 1.4 that can represent it, and the minimal `build_report()`
wiring to select schema 1.4 explicitly when that provenance is supplied. The package version
remains `0.5.0.dev0`.

- `membrane_vqc/pdbtm_report_provenance.py` is the entire new runtime surface: a pure conversion
  from an already-validated `CachedSnapshot` (Stage 4B1) to `PdbtmAcquisitionProvenance` (Stage
  4B2), plus its immutable nested dataclasses.
- `schemas/mvqc-report-1.4.schema.json` is a new, additive, self-contained schema file. Schemas
  1.0, 1.1, 1.2, and 1.3 were not edited.
- `membrane_vqc/report.py` gained one new optional `build_report(pdbtm_acquisition=...)` parameter
  and a fourth schema-version branch. No existing parameter, branch, or output field for schemas
  1.0-1.3 changed.

Explicitly out of scope for this stage (unchanged from the Stage 4B1 boundary, and now also
excluded from Stage 4B2 specifically): GUI buttons, Qt worker orchestration, PyMOL commands,
automatic network fetching during report generation, automatic source selection, fitting or
structural alignment, RCSB/OPM retrieval, proxy/PAC/CONNECT support, cache migration or garbage
collection, and any Stage 4B3/4B4/4C work. Those remain fully unstarted.

## The report layer performs no I/O

`build_report()` and `membrane_vqc.pdbtm_report_provenance.build_pdbtm_acquisition_provenance()`
never perform network I/O, never open or discover the Stage 4B1 cache, never mutate the cache, and
never call PyMOL or Qt. The intended flow is:

```text
validated Stage 4B1 cache/read result (CachedSnapshot)
    -> build_pdbtm_acquisition_provenance()   (pure; re-derives and cross-checks every fact)
    -> PdbtmAcquisitionProvenance             (typed, immutable, no raw bytes, no cache path)
    -> build_report(pdbtm_acquisition=...)
    -> schema-1.4 report dict
```

The caller is responsible for having already produced a validated `CachedSnapshot` (e.g. via
`PdbtmCacheRepository.read_active()`/`.read_snapshot()`) before this stage's code ever runs; no
Stage 4B2 function accepts a record ID, a cache path, or a raw byte pair as untrusted input, and
`report.py` only imports the provenance module's type under `TYPE_CHECKING`, so importing
`membrane_vqc.report` does not pull in the Stage 4B1 cache subsystem at all.

`build_pdbtm_acquisition_provenance()` does not trust its input at face value: it independently
re-derives the pair ID from the payload identities and rejects a mismatch, re-hashes the raw
payload bytes and rejects a size/digest contradiction, cross-checks the pair-validation summary's
provider versions and record ID against the snapshot's own recorded values, and requires every
payload's transport evidence to carry the exact verified-direct-HTTPS marker. Several of these
checks are intentionally redundant with invariants `membrane_vqc.pdbtm_cache_contract` already
enforces at construction time (documented per-check in `tests/test_pdbtm_report_provenance.py`);
that redundancy is deliberate defense in depth at the boundary between the cache subsystem and the
report layer, not dead code.

## Scientific-truthfulness boundary

`validate_pdbtm_pair()` (the validator behind every `CachedSnapshot`) only ever checks that the
acquired PDBTM JSON and transformed-PDB payloads are mutually consistent with each other in the
`pdbtm_transformed_companion` identity frame; it never receives a loaded PyMOL object's
coordinates. A Stage 4B1 cache read therefore can truthfully support only pair
*self-consistency* -- never object *applicability*.

Schema 1.4's `orientation.acquisition.pair_self_consistency` block records exactly that
self-consistency result (adapter identity, method, coordinate frame, residuals, fingerprint
match). Its sibling `object_applicability` block is always
`{"established": false, "scope": "not_evaluated", "statement": "..."}` for every provenance this
stage can produce, with an explicit statement that acquisition/caching a pair does not confirm any
currently loaded structure matches it. Establishing real object applicability requires the
existing offline adapter path (Stage 4A2, `mvqc_check_pdbtm`) with a live `StructureContext` built
from the actual loaded object -- that remains a distinct, unrelated code path, and wiring PDBTM
cache results into it through the GUI/PyMOL orchestration layer is Stage 4B3 work, not this one.

Schema 1.4 keeps schema 1.3's `orientation.evidence` block available and unmodified (a report can
in principle carry both, if Stage 4B3 later supplies real matching evidence alongside acquisition
provenance) but does not require it; only `orientation.acquisition` is required whenever
`schema_version` is `"1.4"`.

## Schema 1.4 field summary

`orientation.acquisition` (new, closed, `additionalProperties: false` throughout its own `$defs`,
unlike the historically permissive report root/orientation shape that 1.0-1.3 already rely on for
legacy top-level fields):

- provider identity: `provider_kind` (`"pdbtm_api_v1"`), `provider_name` (`"PDBTM"`),
  `provider_contract` (`"pdbtm-api-v1/cache-v1"`, reusing the Stage 4B1 cache-contract constant);
- record and acquisition identity: `canonical_record_id`, `acquisition_mode`
  (`"direct_https_provider_fetch"`), `consumption_mode` (`"active_cache_read"` or
  `"snapshot_cache_read"`, distinguishing `read_active()` from an explicit `read_snapshot()`
  lookup);
- cache identity: `pair_id`, `snapshot_id`, and a nullable `cache_generation` (populated only when
  the caller separately queried the index; its absence is valid);
- `provider_versions` (`resource_version`, `software_version`) and `validated_at`;
- `payloads`: exactly two entries, in the fixed `pdbtm_json` then `transformed_pdb` order, each
  with `byte_size`, `sha256`, parsed `content_type` (`media_type`/`charset`), the fixed
  `requested_url`/`final_url`, `requested_at`/`completed_at`, nullable `etag`/`last_modified`
  (allow-listed and bounded exactly as Stage 4B1's `TransportEvidence` already requires -- their
  absence is valid and is what the shipped synthetic example demonstrates), and
  `transport_verification` (`"direct_https_tls_verified"`);
- `pair_self_consistency` and `object_applicability` as described above.

All hashes are `^[a-f0-9]{64}$`; all timestamps are strict `YYYY-MM-DDTHH:MM:SS.ffffffZ`; payload
URLs are pinned to the exact fixed PDBTM API v1 form; bounded text fields (`etag`, `last_modified`,
provider version strings) are limited to 1-1024 printable-ASCII characters. No local filesystem
path, username, IP address, proxy value, credential, raw exception text, raw provider payload
byte, or arbitrary provider header can appear in the block -- both by construction (the provenance
dataclasses only ever expose the allow-listed fields already vetted for Stage 4B1's own
`TransportEvidence`) and by schema (closed shapes, exact enums/consts, no free-form objects).

## Backward compatibility

`build_report()` calls that do not pass `pdbtm_acquisition` are completely unaffected: the new
parameter defaults to `None`, the schema-version dispatch ladder checks it first but only takes
that branch when it is supplied, and no existing field, branch, or required-field check for
schemas 1.0-1.3 changed. Schemas 1.0, 1.1, 1.2, and 1.3 are byte-identical to their previously
recorded hashes (verified in `tests/test_report_schema.py`). No historical report is regenerated
or rewritten. Schema 1.4 is only ever selected explicitly, by supplying the new typed provenance
input -- it is not wired into any existing GUI or PyMOL workflow by this stage.

## Synthetic example

`reports/pdbtm_acquisition_synthetic_mvqc.json` is a schema-1.4 example built end to end through
the real Stage 4B1 cache (`PdbtmCacheRepository`) and the real Stage 4B2 conversion, using the
existing synthetic fixtures under `data/synthetic/` with a clearly fake record ID (`9zzz`) --
never official PDBTM/RCSB payload content. It demonstrates both payload roles, pair/snapshot
identity, and the pair self-consistency block, and validates against schema 1.4.

## Final acceptance

Implemented and validated on PR [#16](https://github.com/TrPavel/membrane-visual-qc/pull/16),
implementation head `f28247a1963c67cf4f6b7e97b2194dbefcac65a5`, after a six-agent parallel
adversarial-review round whose reproduced findings (including a real, independently-confirmed gap
where the Stage-4 semantic validator skipped a schema-1.4 report carrying `orientation.evidence`,
and several unguarded attribute accesses in the conversion function) were fixed on this branch.
Focused provenance tests passed 21; full validation passed 677 tests with 8 optional skips and 88%
combined coverage (685 total, zero failures) on Python 3.12 and the bundled Incentive PyMOL 3.1.8
CPython 3.10.20. The deterministic development Plugin ZIP is `MembraneVisualQC-0.5.0.dev0.zip`,
101,428 bytes, SHA-256 `b952b9d4305932fb1a2254023cef5be2797b5dccb3fcd7ab165be78b83027b4b`. The
synthetic schema-1.4 example passed two-request-equivalent end-to-end validation through the real
Stage 4B1 cache and Stage 4B2 conversion (see "Synthetic example" above). See
`docs/development_state.md`'s "Stage 4B2
completion" section for the full CI/coverage/artifact record.

## Deferred work

Stage 4B3 (GUI and PyMOL orchestration) now wires an actual `Fetch`/`Use cached pair` action to
this provenance path; see `docs/stage4b3_gui_orchestration.md`. This stage's own runtime module
(`membrane_vqc/pdbtm_report_provenance.py`) and schema 1.4 are unchanged by that work -- Stage 4B3
only calls `build_pdbtm_acquisition_provenance()` and `build_report(pdbtm_acquisition=...)` exactly
as documented above, from a network-free, main-thread cached-QC path. Stage 4B4 (final exact-artifact
acceptance) and Stage 4C status are recorded in `docs/development_state.md`. Automatic source
selection, fitting, structural alignment, RCSB/OPM retrieval, proxy/PAC/CONNECT support, and cache
migration/garbage collection remain outside this and the prior slice.
