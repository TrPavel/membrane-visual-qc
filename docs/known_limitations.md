# Known Limitations

## v0.6.0 limitations

- Execution requires PyMOL and runs sequentially on its main thread; the standalone CLI validates
  plans only.
- Cached PDBTM jobs require an exact, already validated snapshot. A missing or corrupt snapshot
  fails closed and never triggers a fetch or active-snapshot fallback. OPM remains local-only.
- Cancellation is cooperative between jobs and at existing safe single-operation checkpoints; it
  does not terminate threads or interrupt PyMOL commands forcibly.
- Result manifests are timestamp-bearing operational indexes. Their canonical identity core omits
  the run ID and timestamps, but the complete manifest bytes are not promised identical per run.
- The GUI is a validator, queue runner, and integrity-checked result browser, not a visual plan
  editor. History is limited to 20 entries in the current dialog session and is not discovered or
  persisted. Missing or changed referenced outputs cannot be revealed.
- There is no cache manager, garbage collection, automatic fitting, consensus, ranking, preferred
  source, or biological verdict. Stage 5C has not started.

## Installation and upgrade

- PyMOL Plugin Manager's own install-directory placement and whether it removes a prior version's
  files before extracting a new one are not controlled by this repository and are not proven by
  automated tests; see `docs/compatibility.md`. Clean replacement (removing the previous install
  before installing a new ZIP) is the recommended, supported upgrade method for this reason, not
  because overlay installation is currently known to fail -- see `docs/upgrade_guide.md`.
- Batch run history remains session-only (see above) across an upgrade too: it is never written to
  disk by any version, so there is nothing for an upgrade to preserve or lose, and no version's
  documentation should be read as implying otherwise.
- The PDBTM cache has no automatic format migration between versions (unchanged from the v0.6.0
  limitation above); for the v0.6.0 → `0.7.x` upgrade specifically, no migration is needed because
  the cache code itself did not change.

## Windows paths

- Ordinary paths containing spaces or Unicode (Cyrillic, CJK, accented) components are fully
  supported for plan, input, and output paths.
- Traversal (`..`), drive-relative (`C:foo`), UNC (`\\server\share`), device (`\\.\`), pipe, and
  symlink/reparse-point paths remain intentionally rejected wherever the batch path contract
  applies.
- Extended-length `\\?\`-prefixed paths are intentionally not accepted, so this plugin cannot opt
  into Windows' long-path support even when the OS has it enabled; keep plan, input, and output
  paths within practical Windows path-length limits.
- A permission-denied destination fails promptly and cleanly, with no partial or leftover output.

## v0.5.0 limitations

- v0.5.0 is intended as a GitHub prerelease for limited public testing; PyPI publication is not
  provided.
- OPM support is offline-only and requires an explicit local oriented-PDB file. There is no live
  OPM retrieval.
- PDBTM retrieval is direct HTTPS only. Proxy discovery, PAC, CONNECT, proxy credentials,
  redirects, and retries are unsupported.
- The validated cache has no automatic migration or garbage collection. Fetch/Refresh, use, and
  clear remain explicit user actions.
- Stage 5B adds a local GUI queue and bounded current-session history, but no persistent history,
  resume manager, scheduler, or automatic source selection.
- There is no automatic fitting, alignment, consensus orientation, provider ranking, or preferred
  source.
- Only one planar membrane per source is represented; curved, multiple, intersecting, and double
  membranes are unsupported.
- Comparison thresholds are conservative geometric review bands, not biological truth. The
  software makes no biological correctness verdict.
- Official PDBTM and OPM provider payloads are not redistributed in Git or release archives.

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

## v0.4.0 offline PDBTM limitations

- Offline PDBTM import accepts explicit local files only. It does not download, cache, discover,
  extract, or execute provider content.
- There is no network retrieval, cache, OPM adapter, source comparison, or automatic alignment.
- Only reviewed API-v1-compatible JSON plus a plain legacy transformed-PDB companion is supported.
- Exactly one complete, single-state, legacy-PDB-compatible PyMOL object is supported. Object
  names and file names are not treated as structure or assembly provenance.
- Schema 1.3 is the immutable v0.4.0 release contract. Partial, rejected, or unsupported imports do
  not create reports.
- Provider Side1/Side2 labels are not converted into inside/outside biology, and geometric
  applicability is not a biological-correctness verdict.
- Slab planes may have relatively low contrast on a dark background; this is a non-blocking
  pre-v1.0 UI backlog item.

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
