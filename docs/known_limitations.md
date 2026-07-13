# Known Limitations

Membrane Visual QC is an inspection helper, not a definitive validator of membrane protein correctness.

## MVP Limitations

- The membrane slab is manually defined by `zmin` and `zmax`.
- No automatic orientation from OPM, PDBTM, UniTmp, or other databases is included in v0.1.
- Residue classification is geometric and depends on the input coordinate frame.
- Charged or polar residues in the slab are not necessarily wrong; they may be functional.
- Hydropathy colouring uses a simple built-in scale and does not model local environment or energetics.
- Ligand-neighbour detection is distance-based and does not classify interaction chemistry.
- JSON/CSV reports are summaries for review, not validation certificates.
- The Qt GUI is a convenience wrapper and does not contain separate scientific logic.

## Data Limitations

- RCSB structures may not be aligned to membrane coordinates.
- OPM-aligned files are not required for the MVP and are not downloaded automatically.
- The synthetic PDB is intentionally artificial and only tests deterministic warning behaviour.

## Scientific Interpretation

Inspect flagged residues in context:

- active sites
- ion-binding sites
- cofactors and ligands
- internal water chains
- proton-transfer networks
- known functional polar networks

Avoid language such as "invalid", "failed", or "wrong" for normal user structures. Prefer "inspect", "review", or "warning".
