# ADR-0003: Integrate FreeSASA through an optional exposure adapter

- Status: Accepted
- Date: 2026-07-13

## Context

Solvent exposure is useful context for membrane-core charges, but FreeSASA is a compiled optional dependency and is absent from the verified PyMOL runtime. Results depend on algorithm and atom/radius settings. The pure scientific core and plugin import must remain usable without it.

## Decision

Define an exposure-provider protocol independent of PyMOL. Implement FreeSASA as a lazy optional adapter that:

- never imports at package top level;
- detects availability and reports a structured capability/diagnostic;
- computes per-atom/per-residue absolute SASA and, only with a named reference scale, relative SASA;
- records FreeSASA version, algorithm, probe radius, point/slice parameters, classifier/radii, atom filtering, model/state, and warnings;
- maps results through full residue identity including model, chain, author number, insertion code, and residue name;
- raises `OptionalDependencyError` when explicitly requested but unavailable.

Absence of FreeSASA yields exposure method `unavailable`, not zero exposure. A future PyMOL `get_area` provider may be offered under a distinct method name; it cannot masquerade as FreeSASA.

## Alternatives considered

- Make FreeSASA mandatory: rejected because it could break Plugin Manager installation and base workflows.
- Use PyMOL area silently as fallback: rejected because methods/parameters differ.
- Implement SASA ourselves: rejected as unnecessary scientific and maintenance risk.

## Consequences

Base installation stays small and robust, while exposure evidence remains reproducible when available. Review logic must handle missing exposure explicitly. Packaging and CI require both dependency-present and dependency-absent matrices.

## Validation plan

Test absence diagnostics, lazy import, known FreeSASA examples (including 1UBQ), per-residue sums, alternate locations, insertion codes, missing/modified atoms, multi-model input, parameter serialization, and deterministic tolerances across supported platforms.
