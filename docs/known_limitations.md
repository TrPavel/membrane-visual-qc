# Known Limitations

Membrane Visual QC is an inspection helper, not a definitive validator of membrane protein correctness.

## Released v0.1 limitations

- The membrane slab is manually defined by `zmin` and `zmax`.
- No automatic orientation from OPM, PDBTM, UniTmp, or other databases is included in v0.1.
- Residue classification is geometric and depends on the input coordinate frame.
- Charged or polar residues in the slab are not necessarily wrong; they may be functional.
- Hydropathy colouring uses a simple built-in scale and does not model local environment or energetics.
- Ligand-neighbour detection is distance-based and does not classify interaction chemistry.
- JSON/CSV reports are summaries for review, not validation certificates.
- The Qt GUI is a convenience wrapper and does not contain separate scientific logic.

## v0.2.0 limitations

- Only one planar membrane is modelled; curved and double membranes are out of scope.
- Orientation import is local and generic; no OPM/PPM/PDBTM/TmDet network adapter is implemented.
- Depth uses CA or a residue-coordinate average, not side-chain functional groups.
- Exposure, hydration, interaction chemistry, energetics, comparisons, and batch work are deferred.

## Data Limitations

- RCSB structures may not be aligned to membrane coordinates.
- OPM-aligned files are not required for the MVP and are not downloaded automatically.
- The synthetic PDB is intentionally artificial and only tests deterministic warning behaviour.

## Stage 4A development limitations

- Offline PDBTM core and PyMOL/GUI integration are development-only in `0.4.0.dev0`; v0.3.0
  remains the latest published release.
- Stage 4A2 accepts explicit local files only. It does not download, cache, discover, extract, or
  execute provider content.
- There is no network retrieval, cache, OPM adapter, source comparison, or automatic alignment.
- Only reviewed API-v1-compatible JSON plus a plain legacy transformed-PDB companion is supported.
- Exactly one complete, single-state, legacy-PDB-compatible PyMOL object is supported. Object
  names and file names are not treated as structure or assembly provenance.
- Schema 1.3 is draft/unreleased. Partial, rejected, or unsupported imports do not create reports.

## v0.3.0 exposure limitations

- Conventional SASA and RSA describe solvent accessibility, not lipid accessibility.
- Membrane-region accessible area is a geometric partition; it cannot distinguish a lipid-facing
  surface from a water-filled pore.
- Finite sphere sampling introduces controlled discretization error; the configured point count,
  probe radius, radius model, thresholds, and backend are recorded in schema-1.2 reports.
- Non-standard residues without a Tien reference retain absolute SASA but have no RSA or exposure
  class.
- Unknown elements without a safe versioned radius are warned about and excluded, never silently
  assigned carbon radii.
- FreeSASA is optional. Its adapter is for reference/parity work and cannot provide membrane-region
  sample partitions through `calcCoord`.

## v0.3.0 local-context limitations

- Contacts are distance-only review evidence, not energetic stabilization, coordination,
  protonation, bond-order, or biological validation claims.
- Histidine is not treated as unconditionally charged. Arbitrary ligand donor/acceptor chemistry,
  water bridges, oxidation states, and ion-coordination geometry are not inferred.
- Only same-model contacts are considered. Missing or ambiguous metadata is reported as
  unavailable or excluded rather than guessed.
- GUI context analysis remains opt-in and disabled by default until graphical Stage 3B acceptance.

## Scientific Interpretation

Inspect flagged residues in context:

- active sites
- ion-binding sites
- cofactors and ligands
- internal water chains
- proton-transfer networks
- known functional polar networks

Avoid language such as "invalid", "failed", or "wrong" for normal user structures. Prefer "inspect", "review", or "warning".
