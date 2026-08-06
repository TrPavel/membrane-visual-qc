# Scientific background

This is a methods document: exactly what Membrane Visual QC computes, from which module, under
which assumptions, and which parts are calculation versus visualization versus an external-source
interpretation. It is not a marketing page and not a journal-article imitation. Every equation
below is transcribed from the implementation cited beside it, not derived independently -- if code
and this document ever disagree, the code is authoritative and this document has drifted.

Read [docs/scientific_interpretation.md](scientific_interpretation.md) first for the vocabulary and
claims boundary this document operates inside. Nothing here overrides it: a geometric calculation
being exact does not make its biological interpretation automatic -- see
[Interpretation limits](#13-interpretation-limits).

## 1. Purpose and scope

This document covers the geometry, classification, coloring, and evidence-comparison logic behind
every number a report contains. It does not cover the GUI, batch execution mechanics, file formats,
or release process -- see [docs/index.md](index.md) for those.

## 2. Coordinate and orientation representation

An orientation is a `PlanarMembrane`: a center point $c$, a unit normal $n$, a lower/upper offset
pair (`lower_offset < upper_offset`, in Å, measured along $n$ from $c$), and a non-negative
interface width $w$ (Å) (`membrane_vqc/orientation.py:PlanarMembrane`). The normal is validated as
finite and normalized at construction (`normalize()`); a zero-length normal is rejected
(`NORMAL_ZERO_TOLERANCE = 1e-12`). Five orientation sources populate this same structure
differently:

| Source | Center / normal | Module |
|---|---|---|
| Legacy global-z | $c=(0,0,0)$, $n=(0,0,1)$ -- the object's own z-axis, not fit | `orientation.legacy_global_z` |
| Planar orientation file | Read directly from a versioned local JSON file | `orientation_io.py` |
| PDBTM local / cache | Derived from the provider's coordinate frame, applicable only if identity-matched (§10) | `pdbtm_adapter.py` |
| OPM (comparison only) | Least-squares plane fit through each DUM boundary's points (§11) | `opm_adapter.py` |

No source is fit, rotated, or translated to match another; see [§13](#13-interpretation-limits) and
[docs/offline_and_safety.md](offline_and_safety.md).

## 3. Signed-distance geometry

For a representative point $r_i$ (§5) and a resolved `PlanarMembrane`, the signed distance from the
midplane is:

$$d_i = n \cdot (r_i - c)$$

Implementation: `orientation.signed_distance(point, membrane)` --
`dot(subtract(point, membrane.center), membrane.normal)`. $d_i$ is in Å, positive on the side the
normal points toward. This is a coordinate-frame projection, not a claim about which side is
extracellular, cytoplasmic, or lipid-facing -- see
[docs/scientific_interpretation.md#membrane-context-limits](scientific_interpretation.md#membrane-context-limits).

## 4. Slab / core / interface / outside classification

`orientation.classify_signed_distance(distance, membrane)` applies this exact, non-overlapping
partition of $d_i$ against `lower_offset` ($L$), `upper_offset` ($U$), and `interface_width` ($w$):

$$
\text{classification}(d_i) =
\begin{cases}
\texttt{core} & L \le d_i \le U \\
\texttt{lower\_interface} & L-w \le d_i < L \\
\texttt{upper\_interface} & U < d_i \le U+w \\
\texttt{outside} & \text{otherwise}
\end{cases}
$$

Boundary equality is deliberate: $d_i = L$ or $d_i = U$ is `core` (closed interval on both sides);
$d_i = L - w$ is `lower_interface`, not `outside`. A structure with `interface_width = 0` (as
`legacy_global_z`'s explicit-zero case would produce, though its default is `DEFAULT_INTERFACE_WIDTH
= 3.0`) has no interface band at all -- the classification falls straight from `core` to `outside`.
There is no missing-coordinate case at this layer: `measure_point`/`signed_distance` require a
finite 3-vector and raise `OrientationError` otherwise (`orientation.vector3`); a residue that
cannot be represented by a coordinate is excluded upstream (§5), not classified as a fourth state.

Three further per-point measurements, all from `orientation.measure_point`:

$$\text{absolute\_center\_distance} = |d_i|$$

$$\text{nearest\_boundary\_distance} = \min(|d_i - L|,\ |d_i - U|)$$

$$\text{outside\_distance} = \max(L - d_i,\ d_i - U,\ 0)$$

`outside_distance` is `0` for any point classified `core`, `lower_interface`, or `upper_interface`
-- it is strictly a "how far past the core boundary" measure, not a general distance-to-core.

**Normalized depth** is defined only for `core`-classified points, and only when the center lies
strictly between the two offsets ($L < 0 < U$ -- true for `legacy_global_z` and any orientation
centered inside its own slab, but not guaranteed for an arbitrary imported orientation):

$$
\text{normalized\_depth}(d_i) =
\begin{cases}
\dfrac{d_i - L}{-L} & d_i \le 0 \\[4pt]
\dfrac{U - d_i}{U} & d_i > 0
\end{cases}
\qquad \text{(undefined, i.e. \texttt{None}, otherwise)}
$$

This maps the center to `0.0` and either core boundary to `1.0`; it is a within-core position
indicator, not a physical burial depth or an energetic quantity.

## 5. Residue representative points

Each residue is reduced to exactly one representative point, `membrane.py:_representative_atom`:
the atom named `CA` if the residue has one (first found, after grouping by
`(model, chain, resi, resn)`); otherwise the unweighted arithmetic mean of all its atoms' $(x,y,z)$
coordinates. This is a coordinate simplification for a single-point classification, not a claim
about a residue's center of mass, side-chain orientation, or functional group position.

## 6. Hydropathy visualization

`membrane_vqc/hydropathy.py` maps each of the 20 standard residue names to a fixed numeric value
and buckets it into one of three coloring bins:

$$
\text{bin}(v) =
\begin{cases}
\texttt{hydrophobic} & v \ge 1.0 \\
\texttt{hydrophilic} & v \le -2.0 \\
\texttt{neutral} & \text{otherwise}
\end{cases}
$$

The 20 fixed values are the Kyte & Doolittle (1982) hydropathy scale verbatim (`HYDROPATHY` dict;
e.g. `ILE: 4.5`, `ARG: -4.5`) -- see [§15](#15-references) [2]. This is a fixed lookup table
rendered as three PyMOL colors (`tv_green` / `sand` / `marine`); it is a visualization aid, not a
per-residue energetic or environmental calculation, and it does not account for local structural
context.

## 7. Charged and polar review items

`membrane_vqc.membrane.flag_core_residues` inspects only `core`-classified residues (§4) against
two fixed sets from `constants.py`:

- `CHARGED_RESIDUES = {ASP, GLU, LYS, ARG}` → severity `WARNING`, reason "charged residue in
  [manually defined] ... membrane core; inspect local environment".
- `POLAR_INSPECT_RESIDUES = {HIS, ASN, GLN, SER, THR, TYR}` → severity `INSPECT`, reason "polar
  residue in ... membrane core; may be functional".

This is a fixed-membership lookup against `resn`, not a pKa, protonation-state, or
solvation-energy calculation. A flagged residue is a manual-review cue -- `REVIEW_ITEMS` is not an
error state; see [docs/scientific_interpretation.md#use-of-review_items](scientific_interpretation.md#use-of-review_items).

## 8. Ligand context

`neighbors.ligand_neighbor_residues` returns every residue with at least one atom within a
Euclidean `cutoff` (Å) of any ligand-selection atom (`math.dist`, straight-line 3-D distance; no
periodic boundary, no bond-graph awareness). `chemistry.py` separately classifies individual atoms'
donor/acceptor/charged roles from fixed atom-name tables (e.g. `LYS:NZ` → positive,
`ASP:{OD1,OD2}` → negative; histidine is intentionally left uncharged, see its docstring) for
distance-only contact evidence -- not protonation state, bond order, or binding-energy inference;
see [docs/known_limitations.md#v030-local-context-limitations](known_limitations.md).

## 9. Exposure / SASA context

`membrane_vqc/exposure.py` implements the **Shrake–Rupley** rolling-sphere algorithm [3] directly:
a Fibonacci-spiral point set is generated per atom (`fibonacci_sphere_points`, a deterministic
golden-angle sphere sampling, not the original 1973 paper's construction, but the same
occlusion-counting principle), each expanded-radius sample point is tested for occlusion by
neighboring atoms' expanded radii (via `spatial.CellList`, a uniform grid for neighbor lookup), and
SASA is the accessible fraction times the point's share of the expanded sphere's area. Atomic radii
follow Bondi (1964); relative SASA (RSA) is computed against theoretical maximum ASA values from
Tien et al. (2013), not from the original Shrake–Rupley paper. This is the built-in
`builtin_shrake_rupley` backend (`BACKEND_NAME`) -- always available, pure Python, no optional
dependency.

`membrane_vqc/freesasa_backend.py` is a separate, **optional** `freesasa_reference` backend that
calls the third-party [FreeSASA](https://freesasa.github.io/) C library [4] (imported lazily; the
module docstring states results are typed `unavailable` if it is not installed). It exists for
parity/reference comparison against the built-in backend, not as the default path, and its Python
API does not expose per-sample coordinates, so it cannot report the membrane-region partition
(core/interface/outside SASA) the built-in backend can. **The two backends are not claimed
equivalent** -- both implement Shrake–Rupley, but with different sampling constructions,
independent implementations, and (for the built-in backend) an additional membrane-region
partition FreeSASA's API cannot provide.

RSA is classified into a fixed three-band scale (`classify_exposure`, thresholds from
`ExposureConfig`, default `buried < 0.2 ≤ intermediate < 0.5 ≤ exposed`) -- an operational bucket
for review, not a lipid-accessibility claim; ordinary SASA/RSA describes solvent accessibility, not
membrane/lipid accessibility (see [docs/scientific_interpretation.md#membrane-context-limits](scientific_interpretation.md#membrane-context-limits)).

## 10. PDBTM source handling

`membrane_vqc/pdbtm_adapter.py` resolves a PDBTM API-v1 orientation from explicit local
JSON+transformed-PDB bytes only -- never fetched inline (fetching is a separate, explicit action;
see [docs/offline_and_safety.md](offline_and_safety.md)). Applicability is **identity-only**: the
current object's coordinates must match the provider's transformed-PDB companion (or its analytical
inverse) to within a fixed RMSD/max-residual envelope (`RUNTIME_IDENTITY_LIMIT = 0.002` Å) --
`identity_no_transform`, i.e. no fitting, alignment, or rigid-body transform is ever computed or
applied to make them match. If neither match, the source is rejected as inapplicable; no analysis
runs against mismatched coordinates. This is an offline geometric applicability check, not a
statement that the PDBTM assignment is biologically correct.

The `0.002` Å envelope is retained unchanged from the owner-accepted v0.9.0 baseline for RC
compatibility. It is an identity/serialization tolerance for the paired PDBTM transformed-coordinate
workflow, not a scientific classification threshold and not an allowance to fit coordinates.

## 11. OPM source handling

`membrane_vqc/opm_adapter.py` parses an explicit local, legacy-format oriented-PDB file (never
fetched -- OPM has no network path in this project). The two `DUM` boundary point sets (labeled `N`
and `O`) are each fit to a plane by the smallest eigenvector of their covariance matrix (a Jacobi
eigenvalue iteration implemented directly, `_smallest_eigenvector_symmetric3` -- no external linear-
algebra dependency), with a fixed planarity check (`PLANE_RESIDUAL_LIMIT = 0.003` Å) and a
parallel-boundary check (`PARALLEL_ANGLE_LIMIT_DEGREES = 0.1°`). The two plane centroids' midpoint
becomes $c$; half their separation becomes the symmetric $\pm$ offset. Applicability uses the same
identity-only philosophy as §10, with its own fixed envelope (`IDENTITY_LIMIT = 0.003` Å) and a
minimum-evidence floor (at least 12 matched atoms across at least 3 residues, spanning at least 10 Å
with at least 2 Å of off-axis extent, to reject a degenerate or coincidental match). OPM's `N`/`O`
dummy-atom labels distinguish the two boundary surfaces only; the code explicitly does not treat
them as inside/outside biology (`directional_topology_available = False`, enforced in
`OpmOrientationEvidence.__post_init__`).

The OPM `0.003` Å envelope is intentionally retained unchanged from v0.9.0 rather than unified
during release hardening. OPM enters through a separately parsed legacy oriented-PDB source and is
also guarded by the minimum-evidence and spatial-extent checks above. The `0.001` Å difference from
the PDBTM envelope is therefore treated as a source-adapter compatibility detail, not as scientific
evidence or a comparison threshold. Changing either value requires explicit versioned rationale and
regression evidence under `docs/versioning_policy.md`.

## 12. PDBTM–OPM geometric comparison

`membrane_vqc/orientation_comparison.py` (`COMPARISON_METHOD = "planar_axis_geometry_v1"`) compares
two independently-applicable resolved orientations with three fixed, reviewed (not
biologically-derived) thresholds: normal-axis angle (5°), center displacement along the reviewed
direction (2 Å), and slab-thickness difference (2 Å). The two normals are sign-aligned (via their
dot product) before comparison, since an antiparallel normal describing the same physical plane is
not itself a disagreement. The result is one of three bands --
`geometrically_close_under_reviewed_tolerance`, `measurable_geometric_difference`, or
`not_comparable` -- and the result object hard-codes `consensus=False`, `ranking=False`,
`preferred_source=None`, `biological_verdict=False`, with the literal statement: *"This is a
geometric comparison for review. It does not select a source, create a consensus orientation, rank
providers, or make a biological verdict."* No fitting, alignment, or coordinate mutation occurs at
any point in this comparison.

## 13. Coordinate-preservation mechanism

Both `pdbtm_adapter.py` and `opm_adapter.py` compute a SHA-256 fingerprint
(`mvqc_atom_identity_coordinates_sha256`, version `1`) over an atom-identity-ordered, fixed-3-decimal-
place coordinate serialization, captured when a source is confirmed applicable and rechecked
immediately before the corresponding action runs. A mismatch (the object's coordinates changed
between capture and use) fails the action rather than silently analyzing stale evidence against new
coordinates. Full mechanism, including the batch-execution per-job `coordinate_preserved` field:
[docs/offline_and_safety.md#part-2-coordinate-preservation](offline_and_safety.md#part-2-coordinate-preservation).

## 14. Interpretation limits

Everything above is a deterministic geometric, statistical, or lookup-table calculation over the
coordinates and parameters supplied. None of it is inferred, predicted, or machine-learned from
biological training data. In particular, and consistently with
[docs/scientific_interpretation.md](scientific_interpretation.md):

- The membrane "slab" is a coordinate-frame partition defined by up to two offsets and a width --
  **not** a physical bilayer simulation, force field, or energetic model of any kind.
- PDBTM and OPM applicability are geometric identity checks against explicitly supplied evidence --
  **not** a claim that either provider's orientation, or the structure itself, is biologically
  correct.
- The PDBTM–OPM comparison never selects, ranks, or prefers a source, and never constructs a
  consensus orientation.
- `REVIEW_ITEMS` is a manual-review cue produced by fixed, documented rules -- **not** an error, and
  not evidence that a residue's placement is wrong.
- Ordinary SASA/RSA measures solvent accessibility -- **not** lipid/membrane accessibility.

## 15. References

Full bibliographic records: [docs/references.bib](references.bib). Inclusion here follows the exact
implementation this document cites -- see each section above for which specific claim each
reference supports; none is included merely because it is standard in the field, and none is an
endorsement of this software by its authors.

1. Tusnády GE, Dosztányi Z, Simon I. PDB_TM: selection and membrane localization of transmembrane
   proteins in the Protein Data Bank. *Nucleic Acids Res.* 2005;33(Database issue):D275-D278.
   doi:[10.1093/nar/gki002](https://doi.org/10.1093/nar/gki002). -- §10 (PDBTM source handling: the
   applicability method and API-v1 evidence model this project reads).
2. Kozma D, Simon I, Tusnády GE. PDBTM: Protein Data Bank of transmembrane proteins after 8 years.
   *Nucleic Acids Res.* 2013;41(D1):D524-D529.
   doi:[10.1093/nar/gks1169](https://doi.org/10.1093/nar/gks1169). -- §10 (the current PDBTM
   API/database revision this project's adapter targets).
3. Lomize AL, Pogozheva ID, Lomize MA, Mosberg HI. OPM: Orientations of Proteins in Membranes
   database. *Bioinformatics.* 2006;22(5):623-625.
   doi:[10.1093/bioinformatics/btk023](https://doi.org/10.1093/bioinformatics/btk023). -- §11 (OPM
   source handling: the oriented-PDB/`DUM`-boundary format this project parses).
4. Lomize MA, Pogozheva ID, Joo H, Mosberg HI, Lomize AL. OPM database and PPM web server: resources
   for positioning of proteins in membranes. *Nucleic Acids Res.* 2012;40(D1):D370-D376.
   doi:[10.1093/nar/gkr703](https://doi.org/10.1093/nar/gkr703). -- §11 (the current OPM
   database/PPM revision).
5. Kyte J, Doolittle RF. A simple method for displaying the hydropathic character of a protein.
   *J Mol Biol.* 1982;157(1):105-132.
   doi:[10.1016/0022-2836(82)90515-0](https://doi.org/10.1016/0022-2836(82)90515-0). -- §6
   (hydropathy visualization: `hydropathy.py`'s `HYDROPATHY` table is this scale verbatim).
6. Shrake A, Rupley JA. Environment and exposure to solvent of protein atoms. Lysozyme and insulin.
   *J Mol Biol.* 1973;79(2):351-371.
   doi:[10.1016/0022-2836(73)90011-9](https://doi.org/10.1016/0022-2836(73)90011-9). -- §9 (the
   rolling-sphere algorithm `exposure.py`'s built-in backend implements).
7. Mitternacht S. FreeSASA: An open source C library for solvent accessible surface area
   calculations. *F1000Research.* 2016;5:189.
   doi:[10.12688/f1000research.7931.1](https://doi.org/10.12688/f1000research.7931.1). -- §9 (the
   optional third-party reference backend `freesasa_backend.py` calls).
8. Tien MZ, Meyer AG, Sydykova DK, Spielman SJ, Wilke CO. Maximum allowed solvent accessibilities of
   residues in proteins. *PLoS ONE.* 2013;8(11):e80635.
   doi:[10.1371/journal.pone.0080635](https://doi.org/10.1371/journal.pone.0080635). -- §9 (the
   theoretical maximum-ASA reference table `TIEN_2013_THEORETICAL_MAX_ASA` uses for RSA).
9. Bondi A. van der Waals Volumes and Radii. *J Phys Chem.* 1964;68(3):441-451.
   doi:[10.1021/j100785a001](https://doi.org/10.1021/j100785a001). -- §9 (the fixed
   `ELEMENT_VDW_RADII` element-radius table used by both SASA backends).

See also: [docs/scientific_interpretation.md](scientific_interpretation.md) (claims boundary),
[docs/offline_and_safety.md](offline_and_safety.md) (coordinate-preservation and network
boundaries), [docs/status_vocabulary.md](status_vocabulary.md) (every status literal this project
produces), [docs/known_limitations.md](known_limitations.md) (full, release-by-release limitations
list), [docs/report_schema.md](report_schema.md) (exact field-level schema each of these values is
serialized into).
