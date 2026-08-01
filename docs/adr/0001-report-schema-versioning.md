# ADR-0001: Version the report contract

- Status: Accepted
- Date: 2026-07-13

## Context

The v0.1 development reports have unversioned/legacy fields and biological statuses such as `WARNING`. The roadmap adds orientation provenance, exposure, local context, comparison, input hashes, and runtime metadata. Consumers need to distinguish additive changes from breaking semantic changes, and old generated reports must not be mistaken for current output.

## Decision

Every JSON report has required top-level `schema_version` and `report_type`. Use a `MAJOR.MINOR` schema version independent of the package version:

- increment MINOR for backward-compatible optional/additive fields;
- increment MAJOR for removal, rename, type change, required-field addition that old producers cannot satisfy, or semantic/status change;
- readers reject unsupported major versions and may accept newer minor versions while preserving unknown fields;
- biological statuses use conservative review vocabulary (`NO_FLAGS`, `REVIEW_ITEMS`, `INSUFFICIENT_CONTEXT`, `ANALYSIS_ERROR`), never `PASS`, `VALID`, or `CORRECT`;
- reports include software/runtime, input identity/hash, parameters, orientation provenance, capabilities, warnings/limitations, deterministically ordered review items, and a UTC generation timestamp;
- migration code may emit documented transitional aliases for one major-version compatibility window.

JSON Schema files and frozen fixtures will become the executable contract. CSV remains a derived flat view and carries schema/report version metadata in its companion JSON.

## Alternatives considered

- Couple schema version to package SemVer: rejected because software releases and data-contract breaks evolve independently.
- Leave reports unversioned and infer by fields: rejected as ambiguous and unsafe.
- Accept any future schema silently: rejected because semantic changes could be misread.

## Consequences

Consumers can validate and migrate reports deterministically. Producers must maintain migrations and fixtures. A schema-major change is deliberate release work. Existing `WARNING` examples are legacy fixtures and must be regenerated or labelled.

## Validation plan

Test required fields/types/status enum, stable item ordering, unknown additive fields, unsupported major rejection, supported minor acceptance, migration aliases, JSON round trips, and deterministic snapshots excluding timestamps.

## Addendum (2026-08-01)

A v1.0-readiness audit found that the 1.0-to-1.1 transition (Stage 2, commit
`a140c46df01f609b8ab7b26107610639a83bb269`, 2026-07-14) did not follow the compatibility ideal this
ADR states: schema 1.1 made `orientation.center`/`normal`/`lower_offset`/`upper_offset`/
`interface_width` and five per-item depth fields required, which a genuine schema-1.0 producer
cannot satisfy. Per this ADR's own rule ("increment MAJOR for ... required-field addition that old
producers cannot satisfy"), that change was structurally a MAJOR break, though it was numbered as a
MINOR bump and no reader-side migration window was ever implemented for it -- `validate_report()`
simply stopped accepting `schema_version: "1.0"` the same commit it started requiring the new
fields. This addendum documents that fact rather than rewriting it out of the record above; no
migration/transitional-alias support existed for schema 1.0 until a hardening fix restored
read-only acceptance of genuine schema-1.0 reports (`membrane_vqc.report.validate_report()`,
version-conditional depth-field requirement) without changing schema 1.0's own frozen bytes or
schema 1.1's required-field contract.
