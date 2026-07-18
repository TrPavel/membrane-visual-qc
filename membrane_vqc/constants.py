"""Shared constants for Membrane Visual QC."""

PLUGIN_NAME = "membrane-vqc-pymol"
DISPLAY_NAME = "Membrane Visual QC"
VERSION = "0.3.0"

DEFAULT_ZMIN = -15.0
DEFAULT_ZMAX = 15.0
DEFAULT_INTERFACE_WIDTH = 3.0
DEFAULT_LIGAND_CUTOFF = 5.0

CHARGED_RESIDUES = {"ASP", "GLU", "LYS", "ARG"}
POLAR_INSPECT_RESIDUES = {"HIS", "ASN", "GLN", "SER", "THR", "TYR"}
HYDROPHOBIC_RESIDUES = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO"}

LIMITATIONS = [
    "Manual slab orientation was used.",
    "This plugin is a visual QC helper, not a definitive structural validator.",
]
