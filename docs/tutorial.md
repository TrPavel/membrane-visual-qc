# Tutorial

Covers every current single-structure workflow: **legacy global-z**, **planar orientation**,
**PDBTM local**, **PDBTM cache**, and **PDBTM-OPM comparison**. For batch (multi-job) usage, see
`docs/batch_plan_reference.md`. For the report contract each mode produces, see `docs/report_schema.md`; for
what every status literal means, see `docs/status_vocabulary.md`.

Low-level schema internals, GUI implementation details, and full acceptance evidence are not
repeated here -- each section links to its dedicated reference/historical document.

## 1. Legacy global-z

**When to use it:** the simplest case -- you already know (or want to approximate) the membrane
boundary as two fixed planes perpendicular to the global Z axis.

**Required inputs:** a loaded, already-oriented PyMOL object; `zmin < zmax` (finite); an optional
ligand selection and cutoff.

```pml
load data/synthetic/bad_core_lys.pdb, bad_core_lys
mvqc_check selection=bad_core_lys, zmin=-15, zmax=15, ligand=, cutoff=5
mvqc_export path=reports/bad_core_lys_mvqc.json
```

**Expected output:** two translucent membrane boundaries, residues classified core/interface/
outside, and a schema 1.1 (or 1.2 with context enabled) report. The synthetic fixture above
produces exactly one charged-core `REVIEW_ITEMS` entry. An empty ligand selection is valid and
simply clears ligand context.

For a real structure:

```pml
load data/raw/1C3W.cif, 1C3W
mvqc_check selection=1C3W, zmin=-15, zmax=15, ligand=organic, cutoff=5
mvqc_export path=reports/1c3w_mvqc.json
```

**Offline/network behavior:** fully offline (`docs/offline_and_safety.md`).

**Failure interpretation:** the structure must already be in a meaningful coordinate frame -- this
mode records manual orientation and never infers membrane alignment. `mvqc_clear` removes all
plugin-owned objects and temporary report state without touching your loaded object.

**Scientific boundary:** `zmin`/`zmax` are a user-supplied approximation, not a computed membrane
position. A `REVIEW_ITEMS` result flags residues for inspection; it is not a correctness verdict
(`docs/status_vocabulary.md#1-single-structure-report-status-summaryoverall_status`).

## 2. Planar orientation

**When to use it:** your membrane is a plane with an arbitrary center/normal, not necessarily
aligned to global Z, and you have (or can produce) a local orientation JSON file describing it.

**Required inputs:** a loaded object; a local orientation JSON file (center, normal, boundary
offsets).

Prepare the validated manual demo fixture without reproducing coordinate operations by hand:

```pml
run C:/Pymol_script_1/demo/prepare_rotated_1ubq.py
```

```pml
mvqc_check_orientation selection=1UBQ_rotated, orientation_file=demo/rotated_1ubq_orientation.json, ligand=
```

**Expected output:** the same review-item/boundary output as legacy mode, but computed against the
arbitrary plane described by the file, plus per-residue depth evidence (signed distance,
nearest-boundary distance, normalized depth) in schema 1.1+.

**Offline/network behavior:** fully offline -- the orientation file is local.

**Failure interpretation:** an invalid or malformed orientation file clears stale QC/slab state and
reports the orientation source as `unavailable`, with a readable error rather than a traceback.

**Scientific boundary:** the orientation file is user-supplied evidence, not a computed or verified
membrane placement -- this mode never fits, aligns, or infers a plane from the structure itself.

## 3. PDBTM local

**When to use it:** you have an explicit local PDBTM API-v1 JSON and its matching transformed-PDB
companion (downloaded or obtained separately -- this mode never fetches).

**Required inputs:** one loaded, complete, single-state PyMOL object whose coordinates match either
the transformed-PDB companion or its analytical inverse; the matching JSON/transformed-PDB pair
(same provider record).

```pml
mvqc_check_pdbtm selection=my_object, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb, ligand=
mvqc_slab_pdbtm selection=my_object, pdbtm_json=C:/payloads/1pcr.json, transformed_pdb=C:/payloads/1pcr.trpdb
```

Select **PDBTM offline pair** in the GUI for the same workflow.

**Expected output:** schema 1.3 report, with provider-derived membrane geometry, coordinate
fingerprint evidence, and precision/threshold metadata. See `docs/pdbtm_offline_import.md` for the
exact object/provenance contract.

**Offline/network behavior:** fully offline -- no download, ever, in this mode.

**Failure interpretation:** the JSON and transformed-PDB must belong to the same provider record
(mismatched pairs are rejected); coordinates must match the reference or its inverse directly (see
`docs/offline_and_safety.md`) -- this mode never fits, rotates, or translates your object to
make it match.

**Scientific boundary:** applicability is direct geometric evidence that your coordinates match a
provider's reference frame -- not a claim that the underlying orientation is biologically correct,
and provider Side1/Side2 labels are never converted into inside/outside biology.

## 4. PDBTM cache

**When to use it:** you want a validated PDBTM record without keeping your own local file pair, or
you want to reuse a previously fetched record across multiple runs/structures.

**Required inputs:** a loaded object matching the cached record's reference frame; the record's
4-character ID.

**Workflow:** in the GUI's PDBTM cache area: enter the record ID, press **Fetch / Refresh** once
(the one action in this project that contacts the network -- see `docs/offline_and_safety.md`) to
populate a validated local cache-v1 snapshot, then press **Use cached pair** to load it for
analysis. Subsequent runs against the same record need only **Use cached pair** -- no repeated
Fetch. **Clear cached record** removes an entry; **Open cache location** reveals the cache
directory on disk.

**Expected output:** schema 1.4 report, recording cached acquisition/applicability provenance in
addition to the same geometric evidence as PDBTM local.

**Offline/network behavior:** only **Fetch / Refresh** contacts the network. **Use cached pair**,
and the `pdbtm_cache` batch mode, read only the already-validated local snapshot -- never fetch,
never fall back to fetching if the snapshot is stale or missing.

**Failure interpretation:** a cache miss, corruption, or unsupported format fails closed with a
clear typed error (`CACHE_MISS`, `CACHE_CORRUPT`, `CACHE_FORMAT_UNSUPPORTED`) rather than silently
misreading or auto-repairing -- see `docs/troubleshooting.md#networkingcache` and
`docs/status_vocabulary.md#7-cache-and-provider-error-codes`.

**Scientific boundary:** same as PDBTM local -- cache self-consistency proves the snapshot is
internally valid, not that it is biologically correct or applicable to every structure you might
load against it.

## 5. PDBTM-OPM comparison

**When to use it:** you want to review geometric agreement/disagreement between an independent
PDBTM orientation and an independent local OPM-oriented structure, both applied to the same object.

**Required inputs:** a loaded object; an applicable PDBTM source (local pair or cache snapshot, as
above); an explicit local OPM-oriented PDB file (OPM is offline-only in this project -- there is no
live OPM retrieval, see `docs/stage4c_source_comparison.md#opm-contract-decision-offline-only`).

**Workflow:** in the GUI's comparison area, establish the PDBTM source and select the local OPM
file, then press **Compare**. **Show both boundaries** renders both sources' planes; **Export
comparison report** writes the result; **Clear comparison** removes only the comparison's own
objects.

**Expected output:** schema 1.5 (`orientation_source_comparison`) -- continuous geometry (angle,
centre displacement, thickness difference) plus fixed review bands (5° angle, 2 Å centre
displacement, 2 Å thickness difference) applied only as visual review aids, never as a pass/fail
verdict.

**Offline/network behavior:** fully offline once both sources are already local/cached -- comparison
itself never fetches.

**Failure interpretation:** both sources must independently match the *same* immutable
coordinate snapshot of the selected object before a comparison can run (see
`docs/offline_and_safety.md#2-comparison-path-membrane_vqcopm_adapterpy-membrane_vqccomparison_pymolpy`);
a source that stops matching invalidates the comparison rather than silently comparing against
stale data.

**Scientific boundary:** comparison never selects a preferred source, builds a consensus, ranks
providers, or produces a biological verdict -- see
`docs/stage4c_source_comparison.md#scientific-boundary`. Disagreement between sources is reported
as geometric evidence for you to review, not resolved automatically.

## Running many jobs at once: Batch review

All five modes above are also available as jobs in a single ordered **batch plan**, run either
through **Plugin > Membrane Visual QC > Batch review** or `mvqc_batch_run`. Batch review validates
an explicit plan, shows the ordered job queue, runs one job per PyMOL main-thread event, supports
cooperative cancellation, and verifies a result bundle before browsing it -- it is a queue runner
and integrity-checked viewer, not a visual plan editor, and its operational states are not a
biological verdict. See `docs/batch_plan_reference.md` for the full guide (including a narrated five-mode
example) and `docs/stage5b_gui_batch.md` for the GUI's detailed state model.

## Reading the visualization

| Meaning | PyMOL colour family |
|---|---|
| hydrophobic base | `tv_green` |
| neutral base | `sand` |
| hydrophilic base | `marine` |
| unknown residue base | `gray70` |
| charged review (`WARNING`) | `orange` |
| polar contextual review (`INSPECT`) | `yellow` |
| ligand | `magenta` |
| ligand shell | `cyan` |
| membrane boundaries | translucent blue/orange |

Hydropathy coloring is applied first, ligand context follows, and review styling is re-applied last
so higher-priority (flagged) residues stay visible. This is a color legend for interactive review,
not a scientific classification in itself -- see `docs/visual_style.md` for the underlying z-order
detail.

## Report review

Use `review_items` as prompts for contextual inspection -- check active sites, ion-binding sites,
cofactors, and known functional polar networks before treating a flagged residue as a problem (see
`docs/known_limitations.md#scientific-interpretation`). Check orientation warnings before
interpreting depth-related output. The current rules do not calculate salt bridges, hydrogen bonds,
energetic stability, or persistent hydration beyond the conservative distance-only evidence
described in `docs/report_schema.md`.

See `docs/manual_gui_validation.md` for this project's historical release-acceptance checklists
(design history, not current instructions), and `docs/status_vocabulary.md` for what every status
literal you might see actually means.
