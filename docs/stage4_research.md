# Stage 4 orientation-source research

Status: design gate; no production implementation has started.
Research snapshot: 2026-07-18.

## Question and evidence standard

Stage 4 is proposed as **orientation interoperability, provenance, retrieval, and source
comparison**. An external record is evidence produced by a named method, not proof of biological
correctness. Import success therefore means only that a supported record was parsed and mapped to
the loaded coordinates reproducibly.

This review used provider documentation, official APIs and source repositories, and primary
publications. HTML scraping is not an acceptable core dependency. Where a provider does not state
rate limits, stability, or data licensing explicitly, the design records that fact instead of
inventing a policy.

## Findings

### PDBTM / UniTmp

PDBTM is online within UniTmp and describes itself as weekly updated. Its current manual documents
JSON and XML entry downloads, transformed coordinates, chain identifiers, and a transformation
matrix from the deposited coordinates to the membrane-oriented coordinates. The public OpenAPI
document (version 1.0.0) defines:

```text
GET https://pdbtm.unitmp.org/api/v1/entry/{code}.{format}
format = json | xml | fastop
```

The JSON record exposes the PDB ID, resource/software versions, chains, membrane data, and a 3x4
rigid transformation. The manual says the transformed Z axis is the membrane normal. An official
example (`1a0s.json`) was reachable during this review. The database publication says all data can
be freely downloaded, but the site does not present a precise data-redistribution licence beside
the API. Stage 4 should therefore cite PDBTM/UniTmp, retain source URLs and hashes, and not bundle or
redistribute a database snapshot without clarification.

PDBTM is the strongest Stage 4A candidate because it has a machine-readable official endpoint, an
explicit coordinate mapping, and an official transformed-PDB companion. The JSON is not sufficient
to prove that its geometry applies to the current PyMOL object. A fully resolved import therefore
requires the official JSON, its matching transformed PDB, and a current `StructureContext` with an
explicit model. JSON alone yields at most partial provenance evidence and no `PlanarMembrane`.

Before coding, locally downloaded official pairs must settle the half-thickness convention, matrix
direction and numeric coordinate tolerance as executable invariants. The adapter compares current
coordinates directly with the transformed companion and with an analytically inverse-transformed
copy. It accepts only identity or the inverse provider transform; it performs no structural fit.

Sources: [PDBTM manual](https://pdbtm.unitmp.org/documents),
[PDBTM usage and API link](https://pdbtm.unitmp.org/usage),
[PDBTM OpenAPI](https://pdbtm.unitmp.org/api/documentation/pdbtm), and
[UniTmp primary publication](https://academic.oup.com/nar/article/52/D1/D572/7327069).

### OPM

OPM is online and provides individual oriented PDB files plus bulk PDB/CSV downloads. The official
site reports PDB, UniProt, classification, topology and thickness/depth fields. Its oriented PDB
files place the membrane normal on Z, include a half-bilayer-thickness REMARK, and use DUM atom
planes to mark the boundaries. For example, the official `1a0s.pdb` has a half thickness of 11.9
angstrom and DUM planes at Z = -11.9 and +11.9.

The downloadable coordinate file is already transformed. It does not provide a documented,
versioned mapping back to an independently loaded wwPDB coordinate set. The website uses backend
endpoints internally, but no official REST contract, authentication policy, rate limit, or service
stability promise was found. Core retrieval must not depend on reverse-engineering those endpoints.

OPM may be suitable as an experimental offline follow-up only when the current object is the same
OPM-oriented coordinate record, or when an explicit, independently verified mapping is provided.
It is not part of the first Stage 4A implementation PR. A coordinate mismatch must be rejected, not
aligned silently.

Sources: [OPM home](https://opm.phar.umich.edu/),
[OPM downloads](https://opm.phar.umich.edu/download), and the
[OPM/PPM primary publication](https://pmc.ncbi.nlm.nih.gov/articles/PMC3245162/).

### PPM 3.0

PPM 3.0 is an active official web server for planar, curved, multiple-membrane, and micelle
positioning. It accepts an uploaded PDB or a PDB/OPM identifier and returns a transformed PDB with
calculated boundaries and energetic/geometric results. For a single planar membrane, the output
origin is the membrane centre and Z is the normal. The current service warns users not to submit
too many jobs at once.

No supported submission/retrieval API or versioned response schema was found. Automated form
submission or result-page scraping is therefore unsuitable. Offline import of a user-downloaded,
single-planar PPM result can be reconsidered after stable fixtures and redistribution terms are
confirmed; curved and multiple-membrane records are outside the current `PlanarMembrane` model.

Sources: [PPM 3.0 server](https://oprlm.org/ppm_server3_cgopm) and
[PPM 3.0 primary publication](https://pmc.ncbi.nlm.nih.gov/articles/PMC8740824/).

### TmDet 4.0

TmDet is actively maintained, backs PDBTM updates, accepts PDB/mmCIF uploads, supports chain
selection, and can predict planar, curved, and double membranes. Its user download contains XML
annotations and transformed CIF coordinates. A standalone C++ implementation is public, but its
repository is under CC-BY-NC-4.0 and requires external compiled dependencies.

The job service is not a documented public automation API and computations may take minutes.
Stage 4 must not invoke its executable or submit jobs automatically. PDBTM is the reproducible
database-record route for Stage 4A; user-supplied TmDet output is deferred until an output-version
contract and planar-only discriminator are fixture-tested.

Sources: [TmDet usage](https://tmdet.unitmp.org/usage),
[TmDet standalone repository](https://github.com/brgenzim/TmDet), and
[TmDet 4.0 primary publication](https://academic.oup.com/nar/article/53/W1/W542/8119806).

### RCSB-integrated membrane annotations

RCSB integrates OPM, PDBTM, MemProtMD, and mpstruc annotations into its Search, Data, and sequence
annotation services. These supported APIs are appropriate for discovering whether an entry has a
membrane annotation and for identifying provenance. The inspected Data API records contain
classification and membership metadata, not a source plane, thickness, or source-to-coordinate
transformation. RCSB Mol* can visualize a predicted membrane, but that display is not a versioned
orientation-record API.

RCSB is therefore a discovery/identifier source, not a Stage 4A geometry adapter. It must never be
treated as if ordinary wwPDB coordinates carry a membrane plane.

Sources: [RCSB membrane resources](https://www.rcsb.org/docs/general-help/membrane-protein-resources),
[RCSB Data API](https://data.rcsb.org/), and the
[RCSB membrane integration publication](https://pmc.ncbi.nlm.nih.gov/articles/PMC8826025/).

### MemProtMD

MemProtMD is online, exposes an HTTP API, updates its simulation collection from PDB structures,
and licenses its own database data under CC-BY-4.0. It provides biological-assembly simulations,
embedded coordinates, lipid contacts, and locally deformed leaflet surfaces. This is richer than a
single planar slab, but there is no provider-declared normalized centre/normal/two-offset record
equivalent to `PlanarMembrane`.

Deriving a best-fit plane from simulated lipids would be a new analysis method, not faithful import.
MemProtMD is deferred from Stage 4A. It remains a valuable future comparison source if a provider
record or explicitly versioned reduction algorithm is designed.

Sources: [MemProtMD API](https://memprotmd.bioch.ox.ac.uk/api/),
[MemProtMD licence statement](https://memprotmd.bioch.ox.ac.uk/search/text/), and the
[database publication](https://pmc.ncbi.nlm.nih.gov/articles/PMC6324062/).

### TmAlphaFold

TmAlphaFold is maintained, has a documented OpenAPI service, uses UniProt accessions, and offers
TmDet XML, rotated structures, topology predictions, and evaluation results. It is CC-BY-4.0 and
supports AlphaFold-derived alpha-helical monomers. These records are tied to a particular predicted
model and are not interchangeable with experimental PDB coordinates or arbitrary user models.

It is deferred from the initial PDB-focused Stage 4A. A later adapter may support it only when the
loaded model identity/version and coordinate hash match the source record.

Sources: [TmAlphaFold API](https://tmalphafold.ttk.hu/api/documentation),
[downloads and formats](https://tmalphafold.ttk.hu/downloads), and
[method/licence](https://tmalphafold.ttk.hu/method).

### Mol* ANVIL

Mol* contains a maintained membrane-orientation implementation based on ANVIL and RCSB uses Mol*
for interactive visualization. It is an algorithm running on a selected structure, not an
authoritative external record with stable retrieval provenance. Reimplementing or embedding it is
outside orientation-source interoperability and should be evaluated, if desired, as a separate
predictor project.

Sources: [Mol* repository](https://github.com/molstar/molstar) and the
[ANVIL publication](https://doi.org/10.1016/j.jsb.2015.12.011).

## Research conclusion

The accepted first Stage 4A scope is PDBTM only, offline only, and requires JSON plus its official
transformed-PDB companion. PPM, direct TmDet jobs, RCSB geometry, MemProtMD reduction, TmAlphaFold,
OPM and source comparison are deferred for distinct technical or scientific reasons. Network
retrieval is also deferred. Stage 4C, if later accepted, compares evidence without choosing a
biologically correct winner.
