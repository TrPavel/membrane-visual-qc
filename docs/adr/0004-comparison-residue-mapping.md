# ADR-0004: Map comparison residues by identity evidence and sequence alignment

- Status: Accepted
- Date: 2026-07-13

## Context

Model/design comparisons must survive mutations, insertions, missing residues, author numbering changes, insertion codes, and chain renames. The wwPDB distinguishes canonical `label_seq_id` from unconstrained author numbering. Matching only PyMOL `(chain, resi)` would create false deltas.

## Decision

Use a staged, deterministic mapping pipeline:

1. honour an explicit validated user mapping;
2. use stable entity/canonical sequence identifiers when both inputs preserve them;
3. allow exact chain + author residue number + insertion-code mapping only after sequence consistency checks;
4. otherwise assign chains deterministically from sequence similarity/coverage and perform global pairwise protein-sequence alignment with documented substitution and affine-gap parameters;
5. optionally use structural alignment metadata to support chain assignment, never as an undocumented replacement for residue sequence correspondence.

Each mapped pair stores original full residue IDs, canonical sequence positions where available, method, identity, coverage, gaps, ambiguity/tie information, and confidence category. Unmapped/ambiguous residues are first-class results. “New” and “resolved” review items require a sufficiently confident mapping; otherwise output is `INSUFFICIENT_CONTEXT` for that comparison.

## Alternatives considered

- Match chain/residue strings directly: rejected as brittle and scientifically unsafe.
- Always structurally align nearest Cα atoms: rejected because conformational changes and repeats can produce biologically wrong correspondences.
- Always run sequence alignment: rejected because explicit/canonical mappings are more interpretable and exact.
- Silently choose the first optimal alignment: rejected because repeated sequences may have multiple equal optima.

## Consequences

Comparison reports become explainable and robust to common renumbering. Implementation is more complex and must preserve mapping provenance. Homomers and low-complexity/partial sequences may remain ambiguous and require user mapping.

## Validation plan

Test identical models, point mutation, insertion/deletion, insertion code, chain rename, swapped chains, blank chain, duplicated homomer chains, missing termini/internal residues, engineered tags, modified residues, partial domains, equal-score alignments, and deterministic tie handling.
