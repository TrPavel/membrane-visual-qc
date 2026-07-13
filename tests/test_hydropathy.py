from membrane_vqc.hydropathy import color_bin, hydropathy


def test_hydropathy_known_residues_and_unknown_safe_default():
    assert hydropathy("ILE") > 0
    assert hydropathy("ARG") <= -4.0
    assert hydropathy("UNK") is None


def test_color_binning_is_deterministic():
    assert color_bin("ILE") == "hydrophobic"
    assert color_bin("ARG") == "hydrophilic"
    assert color_bin("GLY") == "neutral"
    assert color_bin("UNK") == "unknown"
