# Development state

Snapshot date: 2026-07-22 (Europe/Moscow).

Stage 4B1–4B3 are merged into `main`; Stage 4B4's remaining literal Plugin Manager and visible-GUI
gate passed owner observation on 2026-07-22 against the exact accepted Stage 4B3 ZIP. Active source
development remains `0.5.0.dev0`. Stage 4C is implemented on
`feat/stage4c-source-comparison` and is undergoing final validation. It adds an offline-only OPM
adapter, explicit PDBTM-versus-OPM geometric comparison, dedicated GUI/worker/rendering lifecycle,
and additive draft report schema 1.5. Schemas 1.0 through 1.4 remain byte-identical. The comparison
does not fetch implicitly, fit or mutate coordinates, choose a source, create consensus, rank
providers, or make a biological verdict. No Stage 4B or Stage 4C tag, release, or PyPI publication
has been made; PyPI is not used.

## Stage 4C implementation

OPM is offline-only because the reviewed official API does not provide a stable, unambiguous
secondary-record resolution contract for the required use case. Exact local OPM legacy-PDB bytes
are bounded to 5 MiB and parsed for planar `DUM` N/O boundary evidence; the labels identify
surfaces but do not establish biological sidedness. Applicability is identity-only in the current
coordinate frame with no fit, alignment, fallback, or mutation. The comparison reports continuous
normal-axis, anchor displacement, normal/perpendicular displacement, boundary, thickness, scope,
and coverage evidence. Opposite normals are sign-aligned. The 5°, 2 Å normal-displacement, and
2 Å thickness bands are review aids, not biological truth; arbitrary in-plane centre-anchor
translation is reported but does not change the closeness band.

Draft schema 1.5 is separate from the single-source schema 1.4 contract. It binds both applicable
sources to one selected-object snapshot with the named
`mvqc_atom_identity_coordinates_sha256:v1:legacy_pdb_3dp` fingerprint, retains only payload
digests/sizes and safe provenance, and explicitly records no consensus, ranking, preferred source,
or biological verdict. Final PR/CI, artifact, report, coverage, and merge identities will be added
after their gates complete.

Schema 1.5 is pinned at SHA-256
`1de049797e068fc6d60d7c0c73cfb64add9b24bc6b7c24e7c8cd1078b2ee47e3`. The retained synthetic
comparison report is 5,809 bytes with SHA-256
`22666578b124efa1f2dbbb57cbe4c17c17be4787355b54d7e538623ca6b98d18`.

## Post-v0.4.0 development reset

The active package and build identity is `0.5.0.dev0`. Current development artifacts are checked
independently from frozen v0.4.0 release evidence; a third explicit validator mode is reserved for
future release-candidate versions. The retained schema-1.3 report remains version `0.4.0`, and its
provenance, the released schema hashes, and the recorded v0.4.0 asset evidence are verified without
requiring them to match the active development version. This reset changes no runtime or scientific
behaviour and contains no Stage 4B implementation.

### Development-reset completion

PR [#12](https://github.com/TrPavel/membrane-visual-qc/pull/12) final head
`5e94b6d3ad544416e3bd0b3367e9bc967b40b5b0` passed
[workflow 29706357716](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29706357716)
and was squash-merged as `356f01062464dc888fa096ef20fee3e6edbebbe3`. The
[post-merge workflow 29706523306](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29706523306)
passed Python 3.10, 3.11, 3.12, and the blocking Python 3.11 FreeSASA job. Retained validation
reported 438 passed, 8 optional skips, 87% coverage, and 19 valid reports: seven schema 1.1,
eleven schema 1.2, and one schema 1.3.

The active version remains `0.5.0.dev0`. Version validation imports the package from an isolated
child process and verifies that it belongs to the explicitly supplied `project_root`. The
deterministic development artifact remains `MembraneVisualQC-0.5.0.dev0.zip`, 69,248 bytes,
SHA-256 `6b53224e6b9690fae330f2ac04b7ccd9e3ae61dd8d4eeb1ece97abaf80b8c4d0`.
Frozen v0.4.0 evidence remains immutable, and released schema hashes remain unchanged:

- schema 1.0: `5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710`;
- schema 1.1: `86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf`;
- schema 1.2: `96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`;
- schema 1.3: `6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`.

No tag, GitHub Release, or PyPI publication was created. Stage 4B runtime implementation has not
started.

## Stage 4B design and provider preflight

Stage 4B optional PDBTM network-retrieval and local-cache design and provider preflight are
accepted and merged. Design status is **GO**. Stage 4B1 implementation status is **CONDITIONAL
GO**: the transformed-PDB `.trpdb` route remains official-UI-backed but absent from the reviewed
OpenAPI format enum. A mandatory low-volume provider preflight is required immediately before
Stage 4B1 begins, and the blocking Windows transport/cache/security gates remain.

PR [#13](https://github.com/TrPavel/membrane-visual-qc/pull/13) final head
`0237860727b30aeb1e42eeb689a07586f233b2be` passed
[workflow 29708246684](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29708246684)
and was squash-merged as `2e2e7ecfe70ec2b3fc16e2d278bf7651d409c913`. The
[post-merge workflow 29733472921](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29733472921)
passed Python 3.10, 3.11, 3.12, and the blocking Python 3.11 FreeSASA job. Retained validation
reported 438 passed, 8 optional skips, 87% coverage, and 19 valid reports: seven schema 1.1,
eleven schema 1.2, and one schema 1.3. The deterministic development artifact remains
`MembraneVisualQC-0.5.0.dev0.zip`, 69,248 bytes, SHA-256
`6b53224e6b9690fae330f2ac04b7ccd9e3ae61dd8d4eeb1ece97abaf80b8c4d0`.

The mandatory Stage 4B1 entry preflight passed on 2026-07-20 with exactly four reviewed provider
GETs. The implementation branch adds direct-HTTPS transport, offline pair validation, canonical
cache identities, an atomic validated repository, cancellation/publication linearization and a
blocking Windows core job. Environment/system proxy discovery, PAC, CONNECT, proxy credentials and
proxy authentication are unsupported and deferred. Existing workflows still perform no network
access because Stage 4B1 has no GUI or command entry point. Cached data are not integrated into
reports. Draft schema 1.4 remains conceptual and unimplemented; Stage 4B2, Stage 4B3, Stage 4B4 and
Stage 4C have not started.

The current draft-branch retained validation reports 610 passed, 8 optional skips and 88% combined
coverage. All 19 retained reports validate (schema 1.1: 7, schema 1.2: 11, schema 1.3: 1).
Schemas 1.0–1.3 and frozen v0.4.0 evidence remain byte-identical. The deterministic development
Plugin ZIP is `MembraneVisualQC-0.5.0.dev0.zip`, 95,289 bytes, SHA-256
`9a27c24ab7b1be880db9be14fa8a7dfc8de4064d65e7177e4a11e3e9fff1c396`; two builds are
byte-for-byte identical. These are draft Stage 4B1 results, not a release.

**Historical/superseded:** the figures in this paragraph reflect the draft Stage 4B1 branch before
its final correction round and merge. See "Stage 4B1 completion" immediately below for the final
merged head, test counts, coverage, and Plugin ZIP identity.

## Stage 4B1 completion

Stage 4B1 is merged into `main` and complete. The active package version remains `0.5.0.dev0`.
There is still no GUI or PyMOL network action. No Stage 4B1 release or PyPI publication was made.

**Superseded:** at Stage 4B1's merge, cached provider data were not report inputs and draft schema
1.4 did not exist. Both have since changed — see "Stage 4B2 completion" after this section. Stage
4B3, Stage 4B4, and Stage 4C remain unstarted.

PR [#14](https://github.com/TrPavel/membrane-visual-qc/pull/14) final feature head
`d0321f50105dc8c1c5758b4813bb5665c2d2afc9` passed both final PR workflows —
[push run 29778771322](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29778771322) and
[pull_request run 29778774875](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29778774875)
— and was squash-merged into `main` as
`dc1122e662a13190d52f26b547dd153d8e008487`. The
[post-merge workflow 29784587968](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29784587968)
passed all five jobs: Python 3.10, Python 3.11, Python 3.12, the blocking FreeSASA reference Python
3.11 job, and the blocking Stage 4B1 Windows core Python 3.10 job.

Focused transport tests passed 73; full validation passed 634 tests with 8 optional skips and 88%
combined coverage. The final deterministic development Plugin ZIP is
`MembraneVisualQC-0.5.0.dev0.zip`, 96,356 bytes, SHA-256
`35b6cf32100ce3ca029cfb28487bf3cb59f85bbab2814722d42586b702a83351`.

Exact live-provider acceptance passed on Windows 10 build 26200 with Incentive PyMOL 3.1.8 and
bundled CPython 3.10.20: exactly two direct HTTPS requests were issued for `1pcr` (`pdbtm_json` then
`transformed_pdb`), with no proxy, redirect, or retry. The JSON payload was 283,537 bytes with
SHA-256 `38b2f724c4271a00bf2b83aa16015783610178f18d8954a88cb932b9152f36e0`; the transformed PDB
payload was 628,434 bytes with SHA-256
`7e52525ff397e4bfa5900e602f39753628e3b1408d513a3d0d76928c0fd10698`. Adapter validation, cache
commit, active read, forced-offline read, and clear all passed.

A late correction round fixed a real transport defect found only once the provider was genuinely
reachable: because every request sends `Connection: close`, CPython's `http.client` transfers
response ownership and sets `connection.sock` to `None` before the body is read, and the transport
incorrectly re-read `connection.sock` before each chunk, failing every real fetch with
`NETWORK_UNAVAILABLE` despite a fully valid response. The fix captures the connected socket once
after `connect()` and uses it for shrinking read timeouts until `response.isclosed()` indicates the
body is fully drained. This correction, its regression tests, and the live acceptance above are all
on the final merged head.

## Stage 4B2 completion

Stage 4B2, a pure schema/report-provenance integration stage, is implemented and validated on PR
[#16](https://github.com/TrPavel/membrane-visual-qc/pull/16), implementation head
`f28247a1963c67cf4f6b7e97b2194dbefcac65a5`. Six parallel adversarial-review agents (schema
correctness, backward compatibility, provenance truthfulness, cache/network side effects,
malformed-input handling, packaging/release-boundary safety) reviewed the initial implementation;
every reproduced finding was fixed on this branch, including a real gap two agents independently
found (the Stage-4 geometric semantic validator was gated on an exact `schema_version == "1.3"`
check and silently skipped a schema-1.4 report carrying `orientation.evidence`) and several
malformed-input paths in the conversion function that could raise a raw `AttributeError`/
`TypeError` instead of `ProvenanceConversionError`. It adds draft report schema 1.4
(`schemas/mvqc-report-1.4.schema.json`) and `membrane_vqc.pdbtm_report_provenance`, a pure,
network- and cache-free conversion from an already-validated Stage 4B1 `CachedSnapshot` to a
typed, immutable `orientation.acquisition` provenance block, plus one new opt-in
`build_report(pdbtm_acquisition=...)` parameter. Schemas 1.0-1.3 are unchanged (hashes verified
byte-identical); every existing report-generation call site is unaffected, since the parameter
defaults to `None` and schema 1.4 is only ever selected explicitly.

The report layer still performs no I/O of its own: it never opens or discovers the Stage 4B1
cache, never fetches a provider entry, never calls PyMOL or Qt, and `report.py` only imports the
provenance type under `TYPE_CHECKING` so importing it does not pull in the cache subsystem.
Because `validate_pdbtm_pair()` (the validator behind every cached pair) only ever checks the two
acquired PDBTM payloads against each other and never against a loaded PyMOL object, schema 1.4's
`object_applicability` is always `{"established": false, "scope": "not_evaluated"}` — acquiring or
caching a pair is never represented as confirming any loaded structure matches it. Establishing
real applicability remains the existing Stage 4A2 offline-adapter path; wiring PDBTM cache results
into it through the GUI is Stage 4B3 work and has not started.

Focused provenance tests passed 21; full validation passed 677 tests with 8 optional skips and 88%
combined coverage (685 total, zero failures), on both Python 3.12 and the bundled Incentive PyMOL
3.1.8 CPython 3.10.20. The deterministic development Plugin ZIP is
`MembraneVisualQC-0.5.0.dev0.zip`, 101,428 bytes, SHA-256
`b952b9d4305932fb1a2254023cef5be2797b5dccb3fcd7ab165be78b83027b4b`, built twice byte-identically.
`current-development`, `frozen-v0.4.0` (correctly excluding the still-draft schema 1.4 after the
review-round fix above), and `release-candidate --version 0.5.0.dev0` artifact validators all
passed; schema 1.4's own hash is
`7d981454cad061681dd5c3dc2a76a283295a7ed82bed2f0d58769d1716602530`.

One deterministic synthetic example, `reports/pdbtm_acquisition_synthetic_mvqc.json` (4,780 bytes,
SHA-256 `73ad22e1d4ef13bab72f7440b8407295360abd63c51bbc9348cc565173a257bf`), was built end to end
through the real Stage 4B1 cache and Stage 4B2 conversion using the existing synthetic fixtures
under `data/synthetic/` with an obviously fake record ID (`9zzz`); no official PDBTM/RCSB payload
was committed. Ordinary tests and CI make zero live provider requests; the Stage 4B1 live-provider
smoke was not rerun, since this is a pure schema/report stage validated entirely with synthetic
data. No Stage 4B2 release, tag, or PyPI publication was made. Stage 4B3 is implemented (see
"Stage 4B3 implementation" below); Stage 4B4 and Stage 4C have not started.

## Stage 4B3 implementation

Stage 4B3 adds the cached-PDBTM GUI/PyMOL worker orchestration on top of Stage 4B1's transport/cache
core and Stage 4B2's schema-1.4 provenance conversion: a Qt-free `PdbtmWorkerOrchestrator`
(`membrane_vqc/pdbtm_worker.py`), a lazily-Qt-imported `QObject`/`QThread` glue layer
(`membrane_vqc/pdbtm_gui_worker.py`), a `Local files`/`Validated cache` source selector and cached
controls inside the existing PDBTM panel, and network-free cached `Run QC`/`Show Slab` helpers
(`commands.mvqc_check_pdbtm_cached`/`mvqc_slab_pdbtm_cached`) that build the first real (non-
synthetic) schema-1.4 report carrying both `orientation.evidence` and `orientation.acquisition`.
Full architecture, control names, state machines, and boundaries are in
`docs/stage4b3_gui_orchestration.md`.

A parallel 7-way adversarial-review round (Qt lifecycle/thread shutdown; stale-result/cancellation
races; PyMOL thread-affinity/object preservation; cache-selection/corruption behavior;
report/provenance truthfulness; implicit-network/privacy risks; backward compatibility/packaging)
found and this branch fixed three real, reproducible defects: `_teardown_worker` dropped the last
Python reference to a still-`quit()`-ing `QThread`, risking a "destroyed while still running"
process abort on dialog close; a failed `Use cached pair` re-validation left a previously-selected
snapshot usable by Run QC/Show Slab; and a Fetch immediately followed by `Use cached pair` could
attach a stale pre-fetch cache generation to the exported provenance. Separately, direct headless
real-`QThread` smoke testing (not caught by static review or the synchronous fake-Qt unit tests)
found that `Qt.AutoConnection` did not reliably resolve to queued delivery for this worker's
self-connected-signal patterns against the bundled PyQt5 build -- every Fetch/Inspect/Use-cached-
pair/Clear would have frozen the whole PyMOL GUI for its full duration -- and that routing Cancel
through a queued signal into the worker thread could never actually interrupt an in-flight fetch;
both are fixed (explicit `QtCore.Qt.QueuedConnection` throughout; Cancel now calls the shared
`RetrievalOperation.request_cancel()` directly). See `docs/stage4b3_gui_orchestration.md` and
`docs/stage4b4_exact_acceptance.md` for full detail.

Final local validation on branch `feat/stage4b3-gui-final-acceptance` (head
`9ae38be6b6e5ffe89c40981b6a4cc277d3ad13bf`) passed: Ruff check and format check; 741 tests collected
(733 passed, 8 optional FreeSASA skips, zero failures) with 87% combined coverage; 20 example
reports validate (schema 1.1: 7, 1.2: 11, 1.3: 1, 1.4: 1); schema hashes unchanged at 1.0
`5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710`, 1.1
`86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf`, 1.2
`96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`, 1.3
`6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`, 1.4 (still draft)
`7d981454cad061681dd5c3dc2a76a283295a7ed82bed2f0d58769d1716602530`; wheel/sdist build; deterministic
double Plugin ZIP build.

Both CI workflows (push run [29853518696](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29853518696)
and pull_request run [29853522061](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29853522061))
passed all five jobs on this exact head. The exact CI-built Plugin ZIP, downloaded and verified
byte-identical from both independent runs' artifacts, is `MembraneVisualQC-0.5.0.dev0.zip`,
110,358 bytes, SHA-256 `5ad626ef12e72be4807ad15ef34f39595ca76b1addc1c19c6c2f8e5487c400c1`. Stage 4B4
exact-artifact acceptance results (live fetch, cached offline use/QC/export/clear, headless
real-Qt cancellation/lifecycle) are recorded in `docs/stage4b4_exact_acceptance.md`; literal
mouse-driven Plugin Manager installation and on-screen screenshots were not performed, since this
session has no desktop GUI automation tool.

Stage 4 research and architecture design are complete and merged through
[#7](https://github.com/TrPavel/membrane-visual-qc/pull/7). Final PR head
`3740c4dd8bc3a1c6f69778c4715926a19480bbfa` passed
[workflow 29652529942](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29652529942)
and was squash-merged as `bbaabaefee2274f06f954aab16446e8f7e0def7a`. The
[post-merge workflow 29652573284](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29652573284)
passed Python 3.10, 3.11, 3.12, and the blocking Python 3.11 FreeSASA job.

ADR-0005 is accepted for Stage 4A implementation, with PDBTM-only offline import as the first
implementation scope. The isolated
[PDBTM source-semantics preflight](pdbtm_semantics_preflight.md) passed on official PDBTM/RCSB
pairs `1pcr` (`Tm_Alpha`) and `1a0s` (`Tm_Beta`). Final PR head
`76d3b45bb12a09c3e49c324f73896e282f6b4aa2` passed
[workflow 29661170245](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29661170245).
[#8](https://github.com/TrPavel/membrane-visual-qc/pull/8) was squash-merged as
`c6cd9ff676514d20bcc71834449ef225b21c188a`; its
[post-merge workflow 29661211096](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29661211096)
passed Python 3.10, 3.11, 3.12, and the blocking Python 3.11 FreeSASA job.

The tested PDBTM data snapshot was resource version `1017` and the tested provider software was
`3.2.134`. The preflight verified `p_transformed = R p_original + t`, provider chain mapping,
direct transformed-companion and analytical-inverse matching without fitting, and symmetric
half-thicknesses of 12.25 angstrom for `1pcr` and 9.75 angstrom for `1a0s`. Runtime Case A uses
`runtime_identity_match_limit` of 0.002 angstrom for both RMSD and maximum residual; Runtime Case B
uses `runtime_inverse_match_limit` of 0.003 angstrom for both. Provider-forward matrix validation
is a separate per-payload precision-derived limit.

OpenAPI/API v1 required fields, documented matrix semantics, rigid transforms, and the reviewed
precision envelope define compatibility. Resource and software versions are serialized as
provenance; a resource-version increment alone is not an automatic rejection. Decimal precision
and bounds are derived from every exact payload. Changed structure/semantics, non-rigid transforms,
or precision outside the envelope return `unsupported` without reusing a historical fixed limit.
Official payloads remain local-only and outside Git because redistribution permission is unresolved.

PDBTM source-semantics preflight, Stage 4A1, and Stage 4A2 are complete and merged into `main`.
The released offline workflow uses explicit local file selection, a complete single-state
current-object snapshot, current-frame slab rendering, QC/report lifecycle, and the third GUI
orientation mode. It adds no retrieval, OPM, comparison, fitting, or automatic alignment.

Stage 1 is closed. Immutable tag `v0.1.0` points to
`a8c7959fb1d53dd99771a184443aa16afd287aa6`; its prerelease remains unchanged. Release workflow
[29289031923](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29289031923) passed on
Python 3.10, 3.11, and 3.12. Graphical v0.1 validation passed with Incentive PyMOL 3.1.8.

## Stage 2 — merged and accepted

Stage 2 was squash-merged from
[#2](https://github.com/TrPavel/membrane-visual-qc/pull/2) into `main`. Release preparation is
isolated on `release/v0.2.0`; Stage 3 has not started.

Implemented:

- immutable pure-Python `PlanarMembrane` and one classifier for legacy/global and arbitrary planes;
- signed, centre, boundary, outside, and asymmetric normalised depth;
- strict local orientation JSON/schema with deterministic serialisation and SHA-256 provenance;
- report schema 1.1 while released schema 1.0 stays immutable;
- arbitrary-plane CGO rendering sized from selection extents;
- orientation-file commands and minimal GUI mode;
- deterministic rotation/translation/reversal tests and a rotated 1UBQ PyMOL fixture.

The unchanged `mvqc_check zmin/zmax` maps to centre `(0,0,0)`, normal `(0,0,1)`, and source
`manual_global_z`. All five legacy summaries remain unchanged; `bad_core_lys` remains 10 core and
exactly one charged review item. Rotated 1UBQ uses
`R=[[0,0,1],[0,1,0],[-1,0,0]]`, `t=[10,-5,3]`, and normal `[1,0,0]`, with the complete summary
equal to legacy 1UBQ.

The accepted Stage 2 build used development version `0.2.0.dev0` consistently in package metadata,
generated reports, wheel/sdist names, and `dist/MembraneVisualQC-0.2.0.dev0.zip`. Historical local
evidence:
Ruff passed; 153 tests passed with 80% combined coverage; seven schema-1.1 reports validated; PyMOL
3.1.8 smoke plus five legacy and one rotated case passed; wheel/sdist built; two development ZIPs
were byte-identical. The correction-build ZIP SHA-256 is
`841abe95cad44b99108cb4834ad593ef0bb4e99f64b8572cad87f088a5ac8307`; it is not a replacement
for the published v0.1 asset.

The final lifecycle correction removes duplicate GUI orientation parsing. Commands now clear stale
review/report or slab state before orientation-file validation, while the GUI displays returned
source metadata only after success and `unavailable` after failure. Manual and headless rotated
1UBQ preparation share `demo/rotated_1ubq_transform.py`.

Complete interactive acceptance passed on Windows 10 build 26200 with Incentive PyMOL 3.1.8. The
graphical arbitrary plane, footprint/framing, summary equivalence, review styling, exports,
orientation/depth evidence, invalid-file lifecycle, source reset, zero-normal rejection, and
`mvqc_clear` object preservation all passed. The installed ZIP correctly reported Git commit
provenance as unavailable; structure provenance was unavailable because no explicit `input_path`
was supplied. Stage 2 implementation, acceptance, and merge are complete.

Final PR head `272f288819965e72a53e4ea6fe3cb953131c3881` passed
[PR workflow 29410043646](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29410043646)
on Python 3.10, 3.11, and 3.12. It was squash-merged as
`faa7bae062c4ae43a9e9b738f6392bc2a228eb0e`; the corresponding
[post-merge main workflow 29410159752](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29410159752)
also passed all three jobs.

## Final Stage 2 status

Stage 2 is complete and merged into main.

## v0.2.0 release candidate

The release branch promoted package metadata, generated current examples, and artifact names to
`0.2.0`. The final Plugin Manager artifact is `dist/MembraneVisualQC-0.2.0.zip`. Historical
manual exports and screenshots retain their truthful `0.2.0.dev0` identity. Report schema 1.0
remains immutable; v0.2.0 produces additive report schema 1.1.

Automated release-candidate results and the short graphical smoke of the exact final ZIP are
recorded separately in `Report.md` and `reports/release_validation.json`. The v0.1.0 tag and release
remain immutable.

Local automated release-candidate validation passed: 153 tests, 80% combined coverage, seven
schema-1.1 reports, PyMOL smoke plus all five legacy and rotated fixtures, the preparation helper,
wheel/sdist, and deterministic double ZIP build. The 27,459-byte candidate SHA-256 is
`084a7e384364bc46b5b9b3ecdc1b705a4ac80d15e6c320d25f0e1c9f6ec16054`. The exact-artifact
graphical smoke also passed with that exact artifact.

Release PR [#3](https://github.com/TrPavel/membrane-visual-qc/pull/3) passed
[workflow 29487841498](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29487841498)
and was squash-merged as `7877fed3c83419e6affa1e4353a65f8756e9303a`. The
[post-merge workflow 29488017586](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29488017586)
passed on Python 3.10, 3.11, and 3.12. Annotated tag `v0.2.0` points to that release commit, and the
[v0.2.0 GitHub prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.2.0)
contains the four verified assets. PyPI was not used. Stage 3 had not started at publication;
Stage 3A was developed on its own branch and is now merged into `main`.

v0.2.0 is published as a prerelease for limited public testing.

## Historical Stage 3A development — exposure foundation

This historical work was isolated on `feat/exposure-foundation` with development version
`0.3.0.dev0`.
Stage 3A passed its research and ADR-0003/ADR-0004 semantics gate. Its built-in deterministic
Shrake–Rupley backend reports solvent-accessible surface area, relative solvent accessibility,
and membrane-region accessible area without claiming lipid accessibility. FreeSASA is optional and
lazy. At that time report schema 1.2 was an unreleased draft; released schemas 1.0 and 1.1 remain
immutable.

The pure-Python backend uses 240 deterministic golden-spiral points by default, a 1.4 Å probe,
the versioned `element_vdw_v1` Bondi radius table, the complete Tien et al. 2013 theoretical
20-residue maximum-ASA scale, deterministic alternate-location collapse, per-model isolation, and
a spatial cell list. Exposure runs only when an `ExposureConfig` is supplied. Context-disabled
calls still produce schema 1.1 and preserve the released v0.2 behaviour.

PR [#4](https://github.com/TrPavel/membrane-visual-qc/pull/4) was squash-merged into `main`. Local PyMOL
3.1.8 validation produced five schema-1.2 exposure reports and retained every legacy summary.
Measured 240-point exposure times were 0.018 s synthetic, 0.653 s 1UBQ, 0.979 s 1C3W, 4.098 s
2RH1, and 2.854 s 1PCR. These are development observations, not runtime guarantees.

Current local validation: Ruff check and format check passed; 246 tests passed, five FreeSASA
reference tests skipped because FreeSASA is unavailable in the Windows environment, and combined
coverage is 83%. A separate Ubuntu/FreeSASA 2.2.1 run passed all seven reference tests.
Twelve reports validated (seven schema
1.1 and five draft schema 1.2). PyMOL smoke, five legacy fixtures, rotated 1UBQ, the exposure
timing set, and the preparation helper passed. Wheel and sdist built as `0.3.0.dev0`. Two Plugin
ZIP builds were byte-identical at SHA-256
`3c8fb30e9b3dd259c7759c2cbb736326856492cfbcfe6fd78ead101e40914722`; the ZIP is 41,209
bytes. Singleton FreeSASA models are now guarded before native entry, and enabled non-protein
occlusion uses all atoms inside the exact user selection while retaining protein-only targets.
Unsupported two-letter HETATM elements with missing metadata are conservatively excluded.

Previous implementation workflow
[29573971744](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29573971744) is historical.
Head `60872c70d570b5821f1b2cc1bfe271798100ec7c` and workflow
[29576377936](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29576377936) form the
validated correction baseline immediately before the final safety pass. Python 3.10, 3.11, 3.12,
and the blocking Python 3.11 FreeSASA job passed. The final PR head
`b7491ab7cf82e473635bf3191abb960b0b7adcde` passed
[workflow 29584460029](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29584460029).
PR #4 was squash-merged as `294cf52912e0006d413316b89d7a55fed43f1429`; its
[post-merge workflow 29584633452](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29584633452)
passed the Python 3.10, 3.11, 3.12, and Python 3.11 FreeSASA jobs.

Stage 3A is complete and merged into main. Stage 3B was completed through
[#5](https://github.com/TrPavel/membrane-visual-qc/pull/5).

## Historical Stage 3B development — local chemical context

The accepted development artifact used identity `0.3.0.dev0`. Pure-Python chemistry and context modules implement
ADR-0004 without PyMOL or Qt imports. Existing severity is preserved while schema 1.2 adds
independent burial, contact-support, and prioritization states. Exposure remains usable alone;
context-disabled execution continues to produce schema 1.1.

Current corrected local validation: 299 tests passed, eight optional FreeSASA tests skipped on
Windows, and combined coverage is 85%. Ruff, 18 report validations, wheel/sdist, full retained
headless PyMOL, context fixtures, sequential lifecycle, and timing passed. The 49,414-byte Plugin
ZIP has SHA-256 `53a34dddcb1d3157f240d03ece3251c6c0565f5bb4bead70c807d641de9a65a1`.

The pre-graphical pass corrected FreeSASA orchestration, centralized five-state priority ordering,
kept CSV residue ordering stable, enforced binary command flags, removed duplicate state/support
constants, and fixed the contact contract at six conservative types. The blocking installed
FreeSASA orchestration tests are assigned to the Ubuntu reference job.

The first graphical Stage 3B attempt is partial. Initial summary, context objects/colours, review
precedence, and context-disabled fallback passed, but a sequential rerun failed on a stale
`mvqc_core_charged` selection. This historical result remains partial.

Focused graphical acceptance subsequently passed on Windows 10 build 26200 with Incentive PyMOL
3.1.8, bundled Python 3.10.20, and the exact corrected 49,414-byte ZIP with SHA-256
`53a34dddcb1d3157f240d03ece3251c6c0565f5bb4bead70c807d641de9a65a1`. The complete
`ON → OFF → ON → ON → invalid orientation` lifecycle, exports, cleanup, preservation,
responsiveness, and rotated 1UBQ `76/40/11/13/0` passed. Stage 3B graphical acceptance is complete.

Final PR head `0c08029b15baa2786681a0d73002d89f7d4e36db` passed
[workflow 29643963613](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29643963613).
PR #5 was squash-merged into `main` as `bc29918686206292c00a13cc74d6d20e60292653`.
The [post-merge workflow 29644011836](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29644011836)
passed Python 3.10, 3.11, 3.12, and the Python 3.11 FreeSASA job.

Stage 3B is complete and merged into main.

Stage 3 is complete and merged into main.

That development phase did not create a v0.3.0 tag, GitHub release, or PyPI publication. The
separate release-candidate branch now carries the active `0.3.0` identity.

## v0.3.0 release candidate

The active version, package metadata, current generated reports, CI artifact path, and local
artifacts now use `0.3.0`. Local validation passed with 299 tests, 85% coverage, 18 schema-valid
reports, the complete retained headless PyMOL suite, wheel/sdist inspection, and deterministic
double ZIP construction. The exact 49,415-byte `dist/MembraneVisualQC-0.3.0.zip` has SHA-256
`ae6bddcd95bd96be590077849879c64d57a07c0bffacf1779ff526ea22ddd7cb`.

The final graphical packaging/version smoke passed on 2026-07-18 with that exact ZIP. All twelve
focused checks passed, including schema-1.2/version-0.3.0 export, schema-1.1 fallback, repeated
lifecycle, invalid-orientation cleanup, input preservation, and rotated 1UBQ `76/40/11/13/0`.
The historical partial and accepted `0.3.0.dev0` artifacts remain unchanged. The final PR and
post-merge workflows passed Python 3.10, 3.11, 3.12, and the blocking Ubuntu FreeSASA job.

Final PR head `4fb65d69aa6ddc98cadd074b995bbf77b1fc503a` was squash-merged as
`5caf9ee0d89721ccfa560de9136b82cc87436c3b`; post-merge workflow
[29649853994](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29649853994) passed all four
jobs. Annotated tag object `e1b635f53a8c7765729d9a1d54fffb2238389fb7` targets that merge commit.
The [v0.3.0 prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.3.0) contains
four verified uploaded assets. Schema 1.2 is released and immutable. v0.1.0/v0.2.0 remain
unchanged, no PyPI project exists, and Stage 4 had not started at publication.

v0.3.0 is published as a prerelease for limited public testing.

## Stage 4A1 complete — offline PDBTM import core

Stage 4A1 was accepted at PR head `4c717b751a0711cf132fa6d9011c1454a8449939` and squash-merged
as `dbe2180386bc4c7230a08b2d064b0487347964c4`. The
[post-merge workflow](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29666872403)
passed Python 3.10, 3.11, 3.12, and the blocking Ubuntu FreeSASA Python 3.11 job.

Clean synchronized `main` validation passed 384 tests with eight optional FreeSASA skips and 87%
combined coverage. All 19 example reports validate: schema 1.1: 7, schema 1.2: 11, schema 1.3: 1.
Schema-1.3 reports undergo both JSON Schema structural validation and mandatory Stage 4 semantic
validation of nonlinear scientific invariants. The offline adapter contract accepts exactly one
`pdbtm_json` primary with either zero companions for partial provenance or exactly one
`transformed_pdb` companion for resolved import; unknown roles and duplicates are rejected.

The deterministic development artifact remains `MembraneVisualQC-0.4.0.dev0.zip`, 65,209 bytes,
with SHA-256 `059264627139ec1a2091fd0f7604d42e16297062f5d5349d270ef53edad0fc9e`.
Schemas 1.0, 1.1, and 1.2 remain byte-identical to their released forms. Schema 1.3 remains draft
and unreleased with SHA-256
`6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`. Official PDBTM/RCSB
provider payloads remain outside Git.

The development version remains `0.4.0.dev0`. No release or PyPI publication was created.

## Stage 4A2 complete — offline PyMOL and GUI integration

The implementation branch now exposes `mvqc_check_pdbtm` and `mvqc_slab_pdbtm`, plus the GUI
**PDBTM offline pair** mode. It resolves one complete single-state current PyMOL object against one
explicit matching local JSON/transformed-PDB pair, renders the resolved current-frame boundaries,
and passes exact Stage 4 evidence to schema-1.3 QC. It never retrieves, fits, transforms, or
renames the input object; failure cleanup removes stale plugin-owned state and `LAST_REPORT`.

The pre-graphical correction replaces mojibake-prone GUI literals with explicit Unicode escapes and
makes PDBTM Show Slab clear all stale plugin/report state on success and failure. Local validation
passed 418 tests with eight optional FreeSASA skips and 87% coverage. The retained
headless PyMOL suite, synthetic Stage 4A2 lifecycle, official local `1pcr`/`1a0s` identity and
inverse cases, 19 example reports, wheel/sdist build, ZIP validation, and deterministic double ZIP
build passed. The corrected candidate is `MembraneVisualQC-0.4.0.dev0.zip`, 69,251 bytes, SHA-256
`3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`. The earlier SHA-256
`446f7af119508dd8f66396dfbc39b4444517a5b2dac9d46368f34ee07cbacb92` is superseded.

Exact-artifact interactive graphical acceptance passed on Windows 10 build 26200 with Incentive
PyMOL 3.1.8 and bundled Python 3.10.20. The accepted 69,251-byte ZIP has SHA-256
`3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`. Identity and analytical
inverse imports for official local-only `1pcr` and `1a0s` payload pairs passed, including context
OFF/ON, schema-1.3 export, current-frame slab rendering, failure cleanup, repeated lifecycle, input
preservation, and both legacy regressions. Detailed observations are recorded in
`stage4a2_graphical_acceptance.md`.

PR #10 final head `2b3e03eef68f583ecc50c20b882f65a8394113c8` passed
[workflow 29696327755](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29696327755)
and was squash-merged into `main` as `fd31ac89c8131060d8872ad50a77895253f93dcc`. The
[post-merge workflow 29696377197](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29696377197)
passed Python 3.10, 3.11, 3.12, and the blocking Ubuntu FreeSASA Python 3.11 job.

The retained suite passed 418 tests with eight optional FreeSASA skips and 87% combined coverage.
All 19 example reports validate: schema 1.1: 7, schema 1.2: 11, and schema 1.3: 1. Report schema
SHA-256 values are:

- schema 1.0: `5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710`;
- schema 1.1: `86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf`;
- schema 1.2: `96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`;
- draft schema 1.3: `6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`.

Clean synchronized `main` rebuilt `MembraneVisualQC-0.4.0.dev0.zip` twice, byte-identically, at
69,251 bytes with SHA-256
`3c439a839dacf986b8e5d86016f20ec03b4d3f30ed46a911c9d54ba9a24cb7a4`.

Exact-artifact graphical acceptance used Windows 10 build 26200, Incentive PyMOL 3.1.8, and bundled
Python 3.10.20. Identity and analytical-inverse cases passed for `1pcr` and `1a0s`; 1pcr context
OFF/ON, schema-1.3 export, repeated lifecycle, failure cleanup, `mvqc_clear`, global-z, and planar
orientation-file regressions passed. The coordinate-frame mismatch check used a manually translated
object (+4 Å, −3 Å, +2 Å), which was rejected without altering its translated coordinates. Slab
planes were visible but relatively low contrast on a dark background; this is a non-blocking
pre-v1.0 UI backlog item.

Stage 4A2 PyMOL and GUI integration is complete and merged into `main`. Official provider payloads
remain outside Git. No network retrieval, OPM integration, source comparison, fitting, automatic
alignment, or Stage 4B work was added.

## v0.4.0 prerelease preparation

The `release/v0.4.0` candidate promotes the active identity to `0.4.0` and freezes schema 1.3 as
the immutable v0.4.0 release contract alongside schemas 1.0–1.2. Schema-1.3 reports continue to
require structural JSON Schema validation followed by the mandatory Stage 4 semantic validator.
v0.3.0 remains the latest published release until this candidate completes merge, tag, and
publication gates.

No v0.4.0 tag, GitHub Release, or PyPI publication has been created. Exact graphical smoke of the
authoritative `MembraneVisualQC-0.4.0.zip` passed; Stage 4B has not started.

Local release-candidate validation passed Ruff check and format check, 421 tests with eight
optional FreeSASA skips, 87% combined coverage, and all 19 example reports (schema 1.1: 7, 1.2:
11, 1.3: 1). Schema hashes remain 1.0
`5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710`, 1.1
`86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf`, 1.2
`96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430`, and 1.3
`6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc`.

The deterministic Plugin ZIP is `MembraneVisualQC-0.4.0.zip`, 69,241 bytes, SHA-256
`bba1891a8fa84c0575442d17daccbb6a6ad3bc54e60ad626ac1000cc59a079b5`. Its checksum sidecar,
wheel, and sdist pass the release-artifact validator; wheel/sdist metadata report version `0.4.0`
and the sdist contains the runtime, schemas, synthetic fixtures, and validation scripts without
report exports.
Standard setuptools archive timestamps mean wheel/sdist byte hashes are candidate-build records,
not reproducibility guarantees. Official provider payloads remain outside Git.

The final authoritative publication set is the extracted `membrane-vqc-build` artifact from
[workflow 29703424337](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29703424337),
artifact ID `8447146429`, archive digest
`ff7eab5b149452795d37d85059a938598fd6c16b4a6bb6d08f7c61495d08f5ed`. Its wheel is 73,261
bytes with SHA-256 `449e091743e5811da70c5309c86274abc5a4144cd8a842fc61f1723552b1b658`; its sdist is
128,782 bytes with SHA-256 `8853b893e08a33feb742c9679241116628955c995ded12898a9ea407c38f1c07`.
The four extracted files are retained outside Git for later publication and must not be replaced by
subsequent local validation builds.

Inspection confirmed version `0.4.0` in the Plugin Manifest, wheel metadata, and sdist metadata;
wheel tag `py3-none-any`; schemas 1.0–1.3 in the sdist; and no `.local`, reports directory,
Stage 4A2 manual export, official provider payload, or unsafe path. Wheel/sdist byte reproducibility
is not claimed.

The active schema-1.3 example was regenerated by the release code from parent commit
`2f0247474c1b1a8da59c7307fa12fba8c009ca97` at `2026-07-19T20:48:41.424766+00:00`.
It retains the accepted synthetic scientific semantics, records current payload digests, and passes
both structural and Stage 4 semantic validation.

Exact v0.4.0 release-artifact graphical smoke passed using the 69,241-byte Plugin ZIP with SHA-256
`bba1891a8fa84c0575442d17daccbb6a6ad3bc54e60ad626ac1000cc59a079b5` on Windows 10 build
26200, Incentive PyMOL 3.1.8, and bundled Python 3.10.20. All three GUI modes, Unicode rendering,
1pcr identity and inverse applicability, failure cleanup, `mvqc_clear`, global-Z, and planar
regressions passed. The exact authoritative Plugin ZIP is approved for publication; details are in
`docs/v0.4.0_graphical_smoke.md`.

## v0.4.0 publication

PR #11 final head `3e4fa8c1fa95c51aae25c48afee3c884ccf3eb98` passed
[workflow 29704112287](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29704112287)
and was squash-merged as `8fcf499467a42bda6e7b18e90a180f72a410d1db`. All four jobs passed in
[post-merge workflow 29704177651](https://github.com/TrPavel/membrane-visual-qc/actions/runs/29704177651).

Annotated tag object `bd6f67d6981266b83fddb06715df3565eb65ae7e` targets the PR #11 squash
commit. The [v0.4.0 GitHub prerelease](https://github.com/TrPavel/membrane-visual-qc/releases/tag/v0.4.0)
contains exactly four verified assets:

- `MembraneVisualQC-0.4.0.zip`: 69,241 bytes; SHA-256
  `bba1891a8fa84c0575442d17daccbb6a6ad3bc54e60ad626ac1000cc59a079b5`;
- `MembraneVisualQC-0.4.0.zip.sha256`: 93 bytes; SHA-256
  `6527c5736aae8e226102a7e0ee7521f3dffdda9fe2b4e2a4a7c9e23719ede876`;
- `membrane_vqc_pymol-0.4.0-py3-none-any.whl`: 73,261 bytes; SHA-256
  `449e091743e5811da70c5309c86274abc5a4144cd8a842fc61f1723552b1b658`;
- `membrane_vqc_pymol-0.4.0.tar.gz`: 128,782 bytes; SHA-256
  `8853b893e08a33feb742c9679241116628955c995ded12898a9ea407c38f1c07`.

All four published assets were downloaded and matched the frozen authoritative files
byte-for-byte. Exact graphical smoke passed on Windows 10 build 26200 with Incentive PyMOL 3.1.8
and bundled Python 3.10.20. The retained suite passed 421 tests with eight optional skips and 87%
coverage; 19 reports validate (schema 1.1: 7, 1.2: 11, 1.3: 1). Schema 1.3 is released and
immutable alongside schemas 1.0–1.2. The official PyPI JSON endpoint returns 404; no PyPI
publication exists. Stage 4B has not started, and low slab contrast remains a non-blocking pre-v1.0
backlog item.
