"""Hydropathy helpers using a built-in Kyte-Doolittle-like scale."""

HYDROPATHY = {
    "ILE": 4.5,
    "VAL": 4.2,
    "LEU": 3.8,
    "PHE": 2.8,
    "CYS": 2.5,
    "MET": 1.9,
    "ALA": 1.8,
    "GLY": -0.4,
    "THR": -0.7,
    "SER": -0.8,
    "TRP": -0.9,
    "TYR": -1.3,
    "PRO": -1.6,
    "HIS": -3.2,
    "GLU": -3.5,
    "GLN": -3.5,
    "ASP": -3.5,
    "ASN": -3.5,
    "LYS": -3.9,
    "ARG": -4.5,
}


def hydropathy(resn: str) -> float | None:
    """Return hydropathy value for a three-letter residue name."""
    return HYDROPATHY.get(resn.strip().upper())


def color_bin(resn: str) -> str:
    """Return a deterministic coarse colour bin for a residue."""
    value = hydropathy(resn)
    if value is None:
        return "unknown"
    if value >= 1.0:
        return "hydrophobic"
    if value <= -2.0:
        return "hydrophilic"
    return "neutral"


def color_name_for_residue(resn: str) -> str:
    """Return a PyMOL-friendly color name for a residue bin."""
    return {
        "hydrophobic": "tv_green",
        "neutral": "sand",
        "hydrophilic": "marine",
        "unknown": "gray70",
    }[color_bin(resn)]
