# Research log

## 2026-07-14 — How should arbitrary planar orientation and depth be defined?

### Hypothesis

The v0.1 global-z slab can become one coordinate-frame-independent planar model without changing
legacy classifications, provided signed-distance, boundary, depth, and coordinate-space
conventions are explicit before implementation.

### Search

Reviewed PyMOL's official API and command documentation, the current open-source CGO constants,
PyMOL model-space/coordinate notes, the primary OPM/PPM planar-slab papers (Lomize et al. 2006 and
2012), the PPM 3.0 planar/curved method paper, and Duff et al.'s robust orthonormal-basis analysis.
The exact sources are linked in ADR-0002.

### Evidence

- The 2006 OPM method approximates the membrane hydrocarbon core as an adjustable planar slab
  bounded by parallel planes; this supports the Stage 2 geometry while reinforcing that it is an
  approximation rather than a biological verdict.
- OPM/PPM reports hydrophobic thickness, penetration/depth, tilt, and boundary planes from a
  method-specific model. Source and provenance must therefore remain explicit.
- PPM 3.0 models planar and curved membranes separately. A tagged `geometry=planar` domain is a
  clean extension point; flattening future curved/double membranes would be misleading.
- With a unit normal, `dot(r-c,n)` is the signed point-plane distance. Reversing the normal also
  requires `lower'=-upper` and `upper'=-lower` to preserve the same physical slab.
- PyMOL camera axes do not define model coordinates. Analysis should consistently use model-space
  coordinates and must not derive orientation from `get_view` or rotate the user's structure.
- Current PyMOL CGO supports triangle primitives while quad-like constants are not a safe portable
  assumption. Two triangles per boundary are the conservative representation.

### Decision

Adopt the conventions in ADR-0002: angstrom model space, explicit unit normal and signed offsets,
exact inclusive legacy boundaries, piecewise asymmetric normalized depth, `null` depth outside or
when a legacy slab does not bracket its centre plane, schema 1.1 for new defined fields, and v0.1 z
fields as compatibility aliases over the same classifier.

Use explicit scalar arguments for any manual-plane PyMOL command and a versioned local orientation
JSON as the stable future-adapter boundary. Render projected selection-sized triangle planes and
keep the camera centred on the molecule.

### Limitations

The model does not infer biological topology, membrane identity, curvature, provider confidence,
or correct orientation. Ordinary RCSB coordinates remain unoriented unless an explicit model is
provided. Numerical tolerances are implementation stability thresholds and must not be presented
as physical uncertainty.

### Follow-up

Implement pure geometry and invariance tests first, then JSON/report integration, and only then
PyMOL rendering/GUI wiring. Validate a reproducibly rotated existing fixture without adding
redundant coordinate files.

Access dates are stated by section date (2026-07-13 or 2026-07-14). Only official
project/database documentation, official source repositories, standards documentation, and
primary literature are used below.

## 2026-07-13 — How should a PyMOL Plugin Manager ZIP and Qt lifecycle work?

### Hypothesis

A distributable plugin should be a ZIP whose top-level member is a Python package directory, with menu registration performed once through `__init_plugin__` and `addmenuitemqt`.

### Search

Checked the PyMOL Wiki pages [Plugin Architecture](https://pymolwiki.org/PluginArchitecture), [Plugins](https://pymolwiki.org/index.php/Plugins), and [Plugins Tutorial](https://pymolwiki.org/index.php/Plugins_Tutorial), plus Schrödinger's official [open-source PyMOL repository](https://github.com/schrodinger/pymol-open-source).

### Evidence

- PyMOL accepts either a single module or a directory containing `__init__.py`; a multi-file directory may be zipped and installed by Plugin Manager, which unpacks it.
- The supported lifecycle entry point is `__init_plugin__(app=None)`; legacy `__init__` is deprecated.
- A Qt menu item is registered with `pymol.plugins.addmenuitemqt(label, callback)` inside `__init_plugin__`.
- Plugin Manager installs local `.py` or `.zip` artefacts. Current PyMOL guidance prefers Qt plugins; Tkinter support is deprecated for PyMOL 3.x.

### Decision

Build a deterministic ZIP with exactly one top-level package directory, reject absolute and `..` archive members, keep import side effects minimal, register the menu only from `__init_plugin__`, and retain command registration as an explicit idempotent operation. Test install/import in a clean PyMOL process.

### Limitations

The wiki documents the contract but does not define a full package manifest or semantic version compatibility matrix. Plugin Manager behaviour must therefore also be tested against supported PyMOL builds.

### Follow-up

Automate ZIP structure/security tests and a clean headless install/import test; complete one GUI install through Plugin Manager manually.

## 2026-07-13 — What are the supported PyMOL/Python combinations?

### Hypothesis

The plugin should target the Python bundled with supported PyMOL distributions rather than assume the user's system Python.

### Search

Checked the official [PyMOL 3.1 download page](https://pymol.org/?id=52), [PyMOL support page](https://pymol.org/support.html), PyMOL Wiki [Python](https://wiki.pymol.org/index.php/Python), and the official [open-source repository](https://github.com/schrodinger/pymol-open-source). Probed the locally installed bundle.

### Evidence

- The current PyMOL 3.1.8 bundles include Python 3.10.
- Schrödinger warns that PyMOL generally does not work with arbitrary system Python installations; its bundles use isolated Anaconda environments.
- The current conda-forge open-source feedstock builds across several Python versions, but that is a distribution-specific build matrix rather than a promise that every Incentive bundle embeds those versions.
- Local validation found Incentive PyMOL 3.1.8 with Python 3.10.20, PyQt5 5.15.11, and Qt 5.15.15.

### Decision

Keep the package floor at Python 3.10 for the v0.1 line and test the actual PyMOL-bundled interpreter. Avoid relying on Python 3.11-only syntax or a system Python. Treat open-source PyMOL as a separate compatibility target.

### Limitations

There is no single upstream page promising every future PyMOL/Python pairing. Compatibility claims must name the exact tested PyMOL distribution and embedded Python.

### Follow-up

Add CI for Python 3.10+ pure core and an integration job for a pinned open-source PyMOL build; retain one Incentive PyMOL manual/headless validation record.

## 2026-07-13 — How should RCSB structures and metadata be acquired?

### Hypothesis

Benchmark acquisition should use RCSB's HTTPS file service plus Data API, prefer mmCIF, and record asymmetric-unit/assembly decisions explicitly.

### Search

Checked RCSB's official [File Download Services](https://www.rcsb.org/docs/programmatic-access/file-download-services), [Data API](https://data.rcsb.org/), and [Web APIs Overview](https://www2.rcsb.org/docs/programmatic-access/web-apis-overview), plus the wwPDB [PDBx/mmCIF resources](https://mmcif.wwpdb.org/).

### Evidence

- Entry coordinates are available at `https://files.rcsb.org/download/{ID}.cif`; biological assemblies use separate `-assemblyN.cif` resources.
- Legacy PDB is not available for every modern/large structure and RCSB documents its planned discontinuation in the extended-ID transition; mmCIF is the safer canonical format.
- Entry metadata is available from `https://data.rcsb.org/rest/v1/core/entry/{ID}` as JSON; missing resources return HTTP 404.
- The Data API exposes commonly used annotations, not every field in the PDBx/mmCIF dictionary. Coordinates and metadata therefore remain distinct provenance inputs.

### Decision

Implement an HTTPS fetcher with normalised uppercase IDs, timeouts, size/content checks, atomic writes, SHA-256, cache/offline mode, and a manifest. Fetch mmCIF and entry metadata separately. Never silently replace the asymmetric unit with an assembly or treat downloaded RCSB coordinates as membrane-oriented.

### Limitations

Assembly choice is biological and case-specific; metadata alone may not settle it. Licensing/citation fields must be verified at the time data are redistributed.

### Follow-up

Populate the manifest for the existing four RCSB fixtures and verify their hashes, experimental methods, ligands, and assembly choices.

## 2026-07-13 — What can orientation resources reliably supply?

### Hypothesis

OPM/PDBTM/TmDet/PPM should be isolated behind import adapters because they differ in model, output, automation surface, and uncertainty.

### Search

Checked the official [OPM database](https://opm.phar.umich.edu/) and [about/download page](https://opm.phar.umich.edu/about); the primary OPM/PPM database paper, [Lomize et al. 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3245162/); the PPM 3.0 primary method as linked by OPM (DOI [10.1002/pro.4219](https://doi.org/10.1002/pro.4219)); the current [TmDet server](https://tmdet.unitmp.org/), [usage](https://tmdet.unitmp.org/usage), and TmDet 4.0 primary paper (DOI [10.1093/nar/gkaf429](https://academic.oup.com/nar/article/53/W1/W542/8119806)); and the current UniTmp/PDBTM primary paper (DOI [10.1093/nar/gkad988](https://academic.oup.com/nar/article/52/D1/D572/7327069)).

### Evidence

- OPM supplies oriented downloadable coordinates and membrane-boundary markers; its placements are computed by PPM and cover transmembrane plus peripheral/monotopic proteins. It is not experimental ground truth.
- PPM 3.0 is an energy-based positioning method for planar and curved membranes. Submitting unpublished coordinates is an external upload and requires explicit user approval.
- PDBTM is now served within UniTmp and supplies membrane-embedded structures produced/curated from TmDet results. Its scope is transmembrane structures rather than all membrane-associated proteins.
- TmDet 4.0 is geometry-based, supports planar/curved/double-membrane and fragment analysis, and downloads CIF plus XML results. The primary paper explicitly notes ambiguities in sequential element annotation.
- TmDet offers a standalone implementation as well as the web service. This is preferable to scraping HTML, subject to licence and packaging review.
- The resources can disagree because they optimise different quantities and cover different structure classes. None should silently override another.

### Decision

Use one versioned internal orientation object containing plane/normal/thickness or richer geometry, source, source record ID/URL, adapter/version, transform, warnings, uncertainty, and original-file hash. Start with generic file import, then one official adapter. Preserve original external output unchanged. Never submit a user's structure remotely without explicit approval.

### Limitations

No stable production API was verified for every resource. OPM exposes downloadable records and an API surface, but endpoints and terms must be integration-tested before being relied on. Curved/double membranes exceed the initial planar domain model and should remain explicitly unsupported rather than flattened silently.

### Follow-up

Collect small licensed fixtures from OPM and TmDet, compare orientations for one shared PDB entry, and quantify depth/review-item changes.

## 2026-07-13 — Should solvent exposure use FreeSASA directly?

### Hypothesis

FreeSASA should be an optional adapter with structured capability diagnostics, not a mandatory import in the pure core.

### Search

Checked the official [FreeSASA site](https://freesasa.github.io/), [Python module 2.2.0 documentation](https://freesasa.github.io/python/), [Python introduction](https://freesasa.github.io/python/intro.html), and the primary FreeSASA paper, [Mitternacht 2016](https://doi.org/10.12688/f1000research.7931.1).

### Evidence

- FreeSASA calculates solvent-accessible surface area and exposes a C library, CLI, and separate Python bindings.
- The documented Python API builds a `Structure`, calls `calc`, and can report selected/subset areas.
- Python module 2.2.0 documents Python 3.7+ support, while its binary availability statement specifically names Python 3.7–3.11 on Windows/macOS. The verified local PyMOL Python 3.10 is in that range, but FreeSASA is not installed there.
- Algorithm, probe radius, radii/classifier, atom inclusion, and FreeSASA version affect results and must be reported.

### Decision

Define an exposure-provider interface. The FreeSASA adapter is imported lazily, returns per-residue absolute and relative SASA with complete parameters/provenance, and raises a typed optional-dependency diagnostic when unavailable. Base review remains usable without it; no fabricated SASA or silent method substitution.

### Limitations

Modified residues, missing atoms, alternate locations, membrane lipids, waters, and multi-model structures need explicit preprocessing policy. Relative SASA also requires a documented reference maximum scale.

### Follow-up

Test 1UBQ and synthetic fixtures with a pinned FreeSASA version, confirm atom-to-residue mapping including insertion codes, and compare only as a diagnostic—not as proof of correctness.

## 2026-07-13 — How should residues be mapped for model comparison?

### Hypothesis

Exact `(chain, author residue number, insertion code)` matches are useful only as a high-confidence fast path; general comparison requires chain assignment and sequence alignment with ambiguity reporting.

### Search

Checked the wwPDB PDBx/mmCIF dictionary entries for [`_atom_site.label_seq_id`](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.label_seq_id.html) and [`_atom_site.auth_seq_id`](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.auth_seq_id.html), and the official Biopython [`PairwiseAligner` documentation](https://biopython.org/docs/latest/Tutorial/chapter_pairwise.html).

### Evidence

- `label_seq_id` points to the canonical polymer sequence index and is a sequential positive integer; `auth_seq_id` is author-defined and can be non-numeric, gapped, negative, or use a homologous/full-length numbering scheme.
- Therefore `resi` equality is not a biological correspondence guarantee across files, even when residue names match.
- Pairwise sequence alignment provides aligned coordinate blocks and configurable global/local algorithms and gap scoring; it may produce multiple equally optimal mappings, especially for repeats or low-complexity sequences.

### Decision

Perform mapping in layers: explicit user mapping; stable mmCIF/entity identifiers; exact chain/number/insertion-code match when sequences confirm it; otherwise deterministic chain assignment plus global protein sequence alignment. Store method, parameters, identity, coverage, gaps, and ambiguity. Unmapped or ambiguous residues remain explicit and cannot generate confident “resolved/new” claims.

### Limitations

Homomers, chain renames, engineered tags, missing density, modified residues, circular permutations, and duplicated sequence segments can remain ambiguous. Structural alignment may help chain assignment but must not silently redefine sequence correspondence.

### Follow-up

Test chain rename, insertion, deletion, mutation, duplicated chains, missing residues, and partial domains; require stable tie-breaking and explicit low-confidence output.
