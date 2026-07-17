# ADR-0003: Solvent exposure and membrane-region surface semantics

- Status: Accepted for Stage 3A implementation
- Date: 2026-07-17

## Context

Stage 3A adds review evidence about solvent-accessible surface area (SASA) without claiming that
ordinary SASA identifies a lipid-facing surface. A water-filled pore and a lipid-facing protein
surface can occupy the same membrane-region geometry. Ordinary RCSB coordinates are not
membrane-oriented unless an explicit orientation is supplied.

## Decision

### SASA, RSA, and reference scale

SASA is the area traced by the centre of a spherical solvent probe rolled over the union of atomic
van der Waals spheres. The built-in backend uses the Shrake–Rupley point approximation. The default
probe radius is 1.4 Å and the default deterministic sampling density is 240 points per target atom.
Both values are validated, configurable, and serialized.

Residue RSA is `residue_sasa / reference_max_sasa`. The reference is the theoretical ALLOWED
Gly-X-Gly scale in Table 1 of Tien et al. 2013, DOI `10.1371/journal.pone.0080635`. The complete
20-residue table is required in code and tests. Non-standard or unsupported residues retain
absolute SASA, while reference maximum, RSA, and exposure class are explicitly unavailable.

The display bins are project heuristics, not universal physical boundaries:

- `buried`: `RSA < 0.05`;
- `intermediate`: `0.05 <= RSA < 0.25`;
- `exposed`: `RSA >= 0.25`;
- `unknown`: RSA unavailable.

Continuous area and RSA are primary evidence; the bin is secondary. RSA may exceed one for unusual
or incomplete structures and is not clipped.

### Atomic-radius model and element handling

`element_vdw_v1` is a fixed element-level van der Waals table based on Bondi 1964, DOI
`10.1021/j100785a001`: H 1.20, C 1.70, N 1.55, O 1.52, F 1.47, P 1.80, S 1.80, Cl 1.75, Br 1.85,
and I 1.98 Å. These are method parameters, not atom-typing chemistry. The version and exact table
are shared by the built-in and optional FreeSASA adapters.

PyMOL's element field is normalized first. If absent, inference is deterministic: remove leading
digits and whitespace from the atom name; accept an unambiguous two-letter supported element only
when its conventional capitalization is present or the residue/atom metadata identifies it;
otherwise use the first supported one-letter symbol. Protein atom `CA` therefore means carbon,
not calcium. An unresolved or unsupported element emits an explicit warning and the atom is
excluded; it never silently receives a carbon radius.

Hydrogens are excluded by default. `include_hydrogens` can enable them. Protein heavy atoms are the
default occluders. Non-protein occluders are excluded unless explicitly requested.

### Atom scope, alternate locations, and models

`AtomRecord` gains defaulted element, altloc, occupancy, formal-charge, and HETATM metadata so old
constructors remain valid. Coordinates must be finite.

Alternate conformers are collapsed before exposure. Duplicate identity is
`(model, chain, resi, resn, atom_name)`. Selection priority is: highest finite occupancy; blank
altloc on a tie; altloc `A`; then lexical altloc. Missing occupancy ranks below a finite occupancy
and ties with other missing values. The report records alternate atoms seen, discarded, and policy
identifier `highest_occupancy_blank_A_lexical_v1`.

Each PyMOL model/object is calculated independently by default. Inter-chain occlusion within one
model is allowed. Cross-model occlusion is forbidden. A selection spanning multiple models emits a
warning and yields independent per-model calculations. Combining models requires a future explicit
configuration and is not part of Stage 3A.

Default target scope is `review_items`: all valid atoms of flagged residues are sampled, while all
valid protein heavy atoms in the same model occlude them. The backend supports explicit target atom
indices for testing and future orchestration. It calculates surface points only for targets.

Side-chain SASA includes all residue atoms except `N`, `CA`, `C`, `O`, and `OXT`.

### Deterministic Shrake–Rupley backend

Sphere points use a deterministic Fibonacci/golden-spiral construction with no random state.
Atoms and residue results use stable identity ordering, independent of input order. A spatial cell
list indexes expanded occluder spheres; target points are tested only against nearby cells, not by
a full `O(N² × points)` scan. A point is occluded when it lies strictly inside another expanded
sphere; tangency remains accessible.

The per-point area weight is `4*pi*(vdw_radius + probe_radius)^2 / sphere_points`. Backend metadata
records `builtin_shrake_rupley`, backend version `1`, radius model, probe, point count, warnings,
and elapsed timing.

### Membrane-region surface partition

Every accessible sample point is classified by the existing immutable `PlanarMembrane`:

- `core_region_accessible_area`: points classified `core`;
- `interface_region_accessible_area`: both interface bands;
- `outside_region_accessible_area`: all remaining points;
- `membrane_region_accessible_fraction`: `(core + interface) / total residue SASA`.

Equivalent side-chain areas and fractions are accumulated. The three areas must sum to residue
SASA within floating-point tolerance. The result is called membrane-region accessible area or
potential membrane-facing accessibility, never lipid-accessible area. Geometry alone cannot
distinguish lipid exposure from a water-filled pore. Joint rigid transformation of coordinates and
the membrane must preserve the partition.

### Optional FreeSASA reference backend

FreeSASA is lazily imported and optional. The adapter uses official `freesasa.calcCoord` with the
same flat coordinate array, element radii, target mapping, probe radius, and Shrake–Rupley point
count where supported. It does not reparse PDB files or substitute FreeSASA's default classifier.
If unavailable, normal analysis succeeds and reports `freesasa_status = unavailable` without a
traceback. The optional dependency is `freesasa>=2.2,<3`; Biopython is not required by this path.

FreeSASA is a reference/parity backend, not a biological ground truth. Different sphere-point
distributions can give small numerical differences even with identical radii and parameters.

### Validation tolerances fixed before implementation

- isolated and non-interacting analytical sphere areas: absolute tolerance `1e-9 Å²`;
- exact symmetry and input-order invariance: absolute tolerance `1e-12 Å²`;
- translation/rotation invariance on non-boundary fixtures: absolute tolerance `1e-7 Å²`;
- membrane partition sum: absolute tolerance `1e-6 Å²`;
- built-in versus FreeSASA at 240 points: `max(2.0 Å², 5% of reference area)` per compared atom or
  residue.

These tolerances are fixed before observing implementation results. A parity mismatch is reported,
not hidden by silently changing backend parameters or widening tolerance.

### Report semantics and missing data

Draft report schema 1.2 adds `context_analysis.exposure` metadata and an `exposure` object to each
review item. Status fields distinguish completed, unavailable, skipped, and error states. Missing
metrics are JSON `null`, never fabricated zero. Exposure never changes existing WARNING/INSPECT
severity or conservative overall status. CSV columns remain unchanged in Stage 3A; JSON is the
canonical rich report.

No exposure analysis runs unless explicitly requested. With context disabled, commands and schema
1.1 output preserve v0.2.0 behaviour.

## Sources

- Shrake and Rupley 1973, DOI <https://doi.org/10.1016/0022-2836(73)90011-9>.
- Mitternacht 2016 FreeSASA, DOI <https://doi.org/10.12688/f1000research.7931.1>.
- Tien et al. 2013, DOI <https://doi.org/10.1371/journal.pone.0080635>.
- Koehler Leman et al. 2017, DOI <https://doi.org/10.1186/s12859-017-1541-z>.
- Bondi 1964, DOI <https://doi.org/10.1021/j100785a001>.
- FreeSASA Python functions: <https://freesasa.github.io/python/functions.html>.
- FreeSASA Python classes: <https://freesasa.github.io/python/classes.html>.

## Consequences

Stage 3A provides reproducible solvent exposure and membrane-region geometry as review evidence,
without claiming lipid accessibility. The explicit preprocessing and radius policies cost some
coverage of unusual chemistry but prevent silent carbon substitution, model mixing, and false
precision.
