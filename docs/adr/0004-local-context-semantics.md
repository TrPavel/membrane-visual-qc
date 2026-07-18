# ADR-0004: Local chemical-context evidence semantics

- Status: Accepted; implementation in progress in Stage 3B
- Date: 2026-07-17
- Implementation: `feat/local-chemical-context` after Stage 3A merge and green post-merge CI

## Context

Local contacts can prioritize membrane-core review items, but incomplete hydrogen atoms,
protonation, bond orders, dielectric environment, waters, ions, ligands, and lipids prevent strong
chemical or energetic conclusions. Context evidence must not downgrade an existing review item.

## Decision

### Atom roles and target/occluder scope

Pure-Python chemistry uses explicit standard-residue atom-role tables. Canonical negative groups
are ASP `OD1/OD2` and GLU `OE1/OE2`; positive groups are LYS `NZ` and ARG `NE/NH1/NH2`.
Histidine is not unconditionally positive: its ionic role is protonation-dependent and disabled by
default, though recognized HIS donor/acceptor atoms may participate in distance-only potential
hydrogen-bond evidence.

Donor/acceptor tables cover standard amino-acid side chains, backbone N/O atoms, and unambiguous
terminal atoms. Stage 3B does not perform arbitrary ligand bond-order or protonation perception.
Non-protein evidence uses category plus element only.

Contacts are calculated independently within each PyMOL model/object. Inter-chain contacts in the
same model are valid; cross-model contacts are excluded. Category extraction belongs in
`pymol_adapter.py`; contact calculations remain pure Python. Alternate locations follow ADR-0003.

### Contact definitions and heuristic thresholds

All cutoffs are inclusive, finite, positive, configurable, serialized, and labelled heuristics:

- `putative_salt_bridge`: opposite canonical charged groups, minimum charged-atom distance
  `<= 4.0 Å`;
- `distance_only_potential_hbond`: recognized donor/acceptor heavy atoms `<= 3.5 Å`, excluding the
  same atom, same-residue trivial pairs, and direct peptide-neighbour backbone contacts;
- `nearby_water`: water oxygen within `<= 3.5 Å` of a target polar/charged atom;
- `nearby_ion`: recognized single-atom inorganic/ionic entity within `<= 4.0 Å`;
- `ligand_proximity`: non-protein, non-water, non-ion heavy atom within `<= 5.0 Å`;
- `polar_ligand_proximity`: ligand N/O/S within `<= 3.8 Å`.

These six labels are the complete Stage 3B contact vocabulary. Unsupported or ambiguous HETATM
elements are warned about and excluded; they do not create contact support. Arbitrary ligand
chemistry and generic non-polymer contact inference remain out of scope.

A water is only nearby water, not a water bridge, unless a future method explicitly demonstrates
two-partner connectivity. An ion record does not assert charge, coordination energy, or oxidation
state unless explicit metadata supports it. A ligand heteroatom does not establish a hydrogen bond.

Contacts are deduplicated by target residue, partner residue/entity, and contact type. Each retains
the minimum-distance atom pair, partner model/chain/residue, optional charged-group centroid
distance, and evidence notes. Stable identity ordering makes results input-order invariant.

### Context-state derivation

Existing severity and reasons are immutable inputs. Independent evidence fields are:

- `burial_state`: buried, intermediate, exposed, or unknown;
- `contact_support`: detected, not_detected, or unavailable;
- `context_state`:
  - buried + no detected contact → `BURIED_NO_DETECTED_SUPPORT`;
  - buried + contact → `BURIED_WITH_POTENTIAL_SUPPORT`;
  - missing exposure or unusable atoms → `INSUFFICIENT_CONTEXT`;
  - intermediate/exposed + no contact → `ACCESSIBLE_NO_DETECTED_SUPPORT`;
  - intermediate/exposed + contact → `ACCESSIBLE_WITH_POTENTIAL_SUPPORT`.

`BURIED_NO_DETECTED_SUPPORT` sorts first for review, but is not an automatic failure. Potential
support does not rescue, pass, or downgrade a WARNING/INSPECT item.

### Missing-data behaviour

Missing hydrogens, protonation, atom roles, water, ion, ligand, or model metadata is explicit.
Absence of observed contacts is `not_detected` only when the required atom categories were actually
available and searched; otherwise it is `unavailable`. Missing evidence is never evidence of
absence. Malformed coordinates or atom metadata produce structured warnings/errors and stale
context state is cleared.

`contact_support` is an overall result across the six supported contact types, not a statement
about any one category. A zero `water`, `ion`, or `ligand` atom count means that no usable atoms of
that category were extracted from the selected structure; it does not establish biological
absence. Category counts and structured warnings must be interpreted together.

### Report and UI semantics

Schema 1.2 serializes all thresholds, atom-role policy version, category availability,
contacts, counts, burial/contact/context states, warnings, and status. Existing overall biological
statuses remain unchanged; VALID/INVALID/PASS/FAIL verdicts are forbidden. Main CSV columns remain
backward-compatible.

The compact GUI control remains disabled by default until performance is validated. Suggested
sampling presets are Fast 96, Standard 240, and High 960 points, but the exact point count is stored.
Qt only forwards configuration and renders results; it does not parse orientation files or contain
scientific contact logic.

Context visualization uses plugin-owned names only. Review orange/yellow styling has precedence;
context partners are cyan sticks, waters small blue spheres, ions violet spheres, and ligands
magenta sticks. Disabling or failing context analysis removes stale context objects without
recolouring or deleting the original structure.

JSON review items and context summaries use one shared priority order:
`BURIED_NO_DETECTED_SUPPORT`, `BURIED_WITH_POTENTIAL_SUPPORT`, `INSUFFICIENT_CONTEXT`,
`ACCESSIBLE_NO_DETECTED_SUPPORT`, `ACCESSIBLE_WITH_POTENTIAL_SUPPORT`. Within a state, WARNING
precedes INSPECT, followed by stable residue identity. CSV retains stable residue identity order
for compatibility.

## Sources

- McDonald and Thornton 1994, DOI <https://doi.org/10.1006/jmbi.1994.1334>.
- Donald, Kulp, and DeGrado 2011, DOI <https://doi.org/10.1002/prot.22927>.
- Koehler Leman et al. 2017, DOI <https://doi.org/10.1186/s12859-017-1541-z>.

## Consequences

Stage 3B can add structured, conservative contact evidence without creating a second QC pipeline
or altering severity. Full ligand chemistry, energetic stabilization, protonation assignment,
water-bridge inference, and cross-model contacts remain out of scope.
