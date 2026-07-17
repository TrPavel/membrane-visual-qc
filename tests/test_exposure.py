import math

import pytest

from membrane_vqc.context_models import ExposureConfig
from membrane_vqc.exposure import (
    ELEMENT_VDW_RADII,
    TIEN_2013_THEORETICAL_MAX_ASA,
    calculate_exposure,
    collapse_alternate_locations,
    fibonacci_sphere_points,
    normalize_or_infer_element,
)
from membrane_vqc.membrane import AtomRecord
from membrane_vqc.orientation import PlanarMembrane
from membrane_vqc.pymol_adapter import atoms_from_selection, structure_atoms


def atom(
    name: str,
    xyz: tuple[float, float, float],
    *,
    model: str = "m",
    chain: str = "A",
    resi: str = "1",
    resn: str = "ALA",
    element: str = "C",
    altloc: str = "",
    occupancy: float | None = 1.0,
    is_hetatm: bool | None = False,
) -> AtomRecord:
    return AtomRecord(
        model,
        chain,
        resi,
        resn,
        name,
        *xyz,
        element=element,
        altloc=altloc,
        occupancy=occupancy,
        is_hetatm=is_hetatm,
    )


def residue_key(value: AtomRecord) -> tuple[str, str, str, str]:
    return value.model, value.chain, value.resi, value.resn


def membrane(
    *,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    normal: tuple[float, float, float] = (0.0, 0.0, 1.0),
    lower: float = -10.0,
    upper: float = 10.0,
    interface: float = 2.0,
) -> PlanarMembrane:
    return PlanarMembrane(center, normal, lower, upper, interface, "test")


def result_for(atoms, key, **kwargs):
    result = calculate_exposure(atoms, target_residues=[key], **kwargs)
    return result.by_residue()[key]


def test_tien_reference_has_complete_twenty_residue_table():
    assert TIEN_2013_THEORETICAL_MAX_ASA == {
        "ALA": 129.0,
        "ARG": 274.0,
        "ASN": 195.0,
        "ASP": 193.0,
        "CYS": 167.0,
        "GLN": 225.0,
        "GLU": 223.0,
        "GLY": 104.0,
        "HIS": 224.0,
        "ILE": 197.0,
        "LEU": 201.0,
        "LYS": 236.0,
        "MET": 224.0,
        "PHE": 240.0,
        "PRO": 159.0,
        "SER": 155.0,
        "THR": 172.0,
        "TRP": 285.0,
        "TYR": 263.0,
        "VAL": 174.0,
    }


def test_isolated_atom_matches_analytical_expanded_sphere_area():
    target = atom("CB", (0.0, 0.0, 0.0))
    result = result_for([target], residue_key(target), config=ExposureConfig(sphere_points=96))
    expected = 4.0 * math.pi * (ELEMENT_VDW_RADII["C"] + 1.4) ** 2
    assert result.residue_sasa == pytest.approx(expected, abs=1e-9)


def test_two_separated_atoms_equal_two_isolated_surfaces():
    left = atom("CB", (-20.0, 0.0, 0.0), resi="1")
    right = atom("CB", (20.0, 0.0, 0.0), resi="2")
    analysis = calculate_exposure([left, right], config=ExposureConfig(target_scope="all_residues"))
    expected = 4.0 * math.pi * (1.7 + 1.4) ** 2
    assert [item.residue_sasa for item in analysis.residues] == pytest.approx(
        [expected, expected], abs=1e-9
    )


def test_overlapping_expanded_spheres_reduce_accessible_area():
    left = atom("CB", (-1.0, 0.0, 0.0), resi="1")
    right = atom("CB", (1.0, 0.0, 0.0), resi="2")
    analysis = calculate_exposure([left, right], config=ExposureConfig(target_scope="all_residues"))
    isolated = 4.0 * math.pi * (1.7 + 1.4) ** 2
    assert all(item.residue_sasa < isolated for item in analysis.residues)


def test_symmetric_two_atom_geometry_gives_symmetric_results():
    left = atom("CB", (-1.0, 0.0, 0.0), resi="1")
    right = atom("CB", (1.0, 0.0, 0.0), resi="2")
    analysis = calculate_exposure(
        [left, right], config=ExposureConfig(target_scope="all_residues", sphere_points=240)
    )
    assert analysis.residues[0].residue_sasa == pytest.approx(
        analysis.residues[1].residue_sasa, abs=1e-12
    )


def test_translation_invariance():
    atoms = [
        atom("CB", (0.0, 0.0, 0.0), resi="1"),
        atom("CB", (2.5, 0.5, 0.0), resi="2"),
        atom("N", (0.5, 2.0, 1.0), resi="3", element="N"),
    ]
    config = ExposureConfig(target_scope="all_residues")
    baseline = calculate_exposure(atoms, config=config)
    shift = (11.0, -7.0, 3.5)
    shifted = [
        atom(
            item.name,
            (item.x + shift[0], item.y + shift[1], item.z + shift[2]),
            resi=item.resi,
            element=item.element,
        )
        for item in atoms
    ]
    moved = calculate_exposure(shifted, config=config)
    assert [item.residue_sasa for item in moved.residues] == pytest.approx(
        [item.residue_sasa for item in baseline.residues], abs=1e-7
    )


def test_rotation_invariance_for_non_collinear_geometry():
    atoms = [
        atom("CB", (0.0, 0.0, 0.0), resi="1"),
        atom("CB", (2.5, 0.5, 0.0), resi="2"),
        atom("N", (0.5, 2.0, 1.0), resi="3", element="N"),
    ]
    rotated = [
        atom(item.name, (-item.y, item.x, item.z), resi=item.resi, element=item.element)
        for item in atoms
    ]
    config = ExposureConfig(target_scope="all_residues")
    baseline = calculate_exposure(atoms, config=config)
    transformed = calculate_exposure(rotated, config=config)
    assert [item.residue_sasa for item in transformed.residues] == pytest.approx(
        [item.residue_sasa for item in baseline.residues], abs=1e-7
    )


def test_atom_input_order_invariance():
    atoms = [
        atom("CB", (0.0, 0.0, 0.0), resi="1"),
        atom("O", (2.0, 0.0, 0.0), resi="2", element="O"),
        atom("N", (0.0, 2.0, 0.0), resi="3", element="N"),
    ]
    config = ExposureConfig(target_scope="all_residues")
    forward = calculate_exposure(atoms, config=config)
    reverse = calculate_exposure(list(reversed(atoms)), config=config)
    assert [item.as_report_dict() for item in forward.residues] == [
        item.as_report_dict() for item in reverse.residues
    ]


def test_target_only_matches_full_evaluation_for_same_residue():
    first = atom("CB", (0.0, 0.0, 0.0), resi="1")
    second = atom("CB", (2.0, 0.0, 0.0), resi="2")
    targeted = result_for([first, second], residue_key(first))
    full = calculate_exposure(
        [first, second], config=ExposureConfig(target_scope="all_residues")
    ).by_residue()[residue_key(first)]
    assert targeted.as_report_dict() == full.as_report_dict()


def test_models_do_not_occlude_each_other():
    first = atom("CB", (0.0, 0.0, 0.0), model="A")
    second = atom("CB", (0.0, 0.0, 0.0), model="B")
    analysis = calculate_exposure(
        [first, second], config=ExposureConfig(target_scope="all_residues")
    )
    isolated = 4.0 * math.pi * (1.7 + 1.4) ** 2
    assert [item.residue_sasa for item in analysis.residues] == pytest.approx(
        [isolated, isolated], abs=1e-9
    )
    assert any("multiple models" in warning for warning in analysis.metadata.warnings)


def test_alternate_location_selection_is_deterministic():
    variants = [
        atom("CB", (2.0, 0.0, 0.0), altloc="B", occupancy=0.8),
        atom("CB", (1.0, 0.0, 0.0), altloc="A", occupancy=0.8),
        atom("CB", (0.0, 0.0, 0.0), altloc="", occupancy=0.8),
    ]
    collapsed, seen, discarded = collapse_alternate_locations(reversed(variants))
    assert collapsed[0].altloc == ""
    assert collapsed[0].x == 0.0
    assert (seen, discarded) == (3, 2)


def test_missing_element_is_warned_and_not_given_carbon_radius():
    unknown = atom("QX", (0.0, 0.0, 0.0), element="")
    analysis = calculate_exposure([unknown], target_residues=[residue_key(unknown)])
    assert analysis.residues[0].status == "unavailable"
    assert analysis.residues[0].residue_sasa is None
    assert any("Unknown element" in warning for warning in analysis.metadata.warnings)


@pytest.mark.parametrize(
    ("atom_name", "expected"),
    [
        ("CA", "C"),
        ("CB", "C"),
        ("CG", "C"),
        ("CD", "C"),
        ("CE", "C"),
        ("N", "N"),
        ("ND", "N"),
        ("NE", "N"),
        ("NZ", "N"),
        ("O", "O"),
        ("OD", "O"),
        ("OE", "O"),
        ("OG", "O"),
        ("OH", "O"),
        ("S", "S"),
        ("SD", "S"),
        ("SG", "S"),
    ],
)
def test_missing_element_inference_retains_standard_protein_atoms(atom_name, expected):
    protein_atom = atom(atom_name, (0.0, 0.0, 0.0), element="", is_hetatm=False)
    assert normalize_or_infer_element(protein_atom) == expected


@pytest.mark.parametrize(
    ("atom_name", "expected"),
    [("C1", "C"), ("N1", "N"), ("O1", "O"), ("S1", "S"), ("CL", "CL"), ("BR", "BR")],
)
def test_missing_element_inference_accepts_unambiguous_supported_hetatm_names(atom_name, expected):
    heteroatom = atom(
        atom_name,
        (0.0, 0.0, 0.0),
        resn=atom_name,
        element="",
        is_hetatm=True,
    )
    assert normalize_or_infer_element(heteroatom) == expected


@pytest.mark.parametrize("atom_name", ["CA", "NA", "FE", "MG", "ZN", "CU", "MN", "CO", "NI", "SE"])
def test_missing_element_inference_rejects_unsupported_two_letter_hetatm_elements(atom_name):
    ion = atom(
        atom_name,
        (0.0, 0.0, 0.0),
        resn=atom_name,
        element="",
        is_hetatm=True,
    )
    assert normalize_or_infer_element(ion) == ""


def test_explicit_unsupported_element_never_falls_back_to_atom_name():
    explicit_iron = atom("F1", (0.0, 0.0, 0.0), resn="FE", element="Fe", is_hetatm=True)
    assert normalize_or_infer_element(explicit_iron) == ""

    analysis = calculate_exposure(
        [explicit_iron],
        config=ExposureConfig(include_nonprotein_occluders=True),
        target_residues=[residue_key(explicit_iron)],
    )
    assert any(
        "Unsupported supplied element FE" in warning and "without atom-name fallback" in warning
        for warning in analysis.metadata.warnings
    )


def test_unsupported_hetatm_is_excluded_with_conservative_warning():
    calcium = atom("CA", (0.0, 0.0, 0.0), resn="CA", element="", is_hetatm=True)
    analysis = calculate_exposure(
        [calcium],
        config=ExposureConfig(include_nonprotein_occluders=True),
        target_residues=[residue_key(calcium)],
    )
    assert analysis.residues[0].status == "unavailable"
    assert any(
        "Could not safely infer HETATM element" in warning for warning in analysis.metadata.warnings
    )


def test_unsupported_hetatm_does_not_occlude_but_supported_hetatm_does():
    target = atom("CB", (0.0, 0.0, 0.0), resi="1", element="C", is_hetatm=False)
    unsupported_iron = atom(
        "FE",
        (0.0, 0.0, 0.0),
        resi="900",
        resn="FE",
        element="",
        is_hetatm=True,
    )
    supported_iodine = atom(
        "I",
        (0.0, 0.0, 0.0),
        resi="901",
        resn="IOD",
        element="",
        is_hetatm=True,
    )
    config = ExposureConfig(include_nonprotein_occluders=True)

    isolated = result_for([target], residue_key(target), config=config)
    with_iron = result_for([target, unsupported_iron], residue_key(target), config=config)
    with_iodine = result_for([target, supported_iodine], residue_key(target), config=config)

    assert with_iron.residue_sasa == pytest.approx(isolated.residue_sasa, abs=1e-12)
    assert with_iodine.residue_sasa < isolated.residue_sasa


def test_unsupported_residue_has_sasa_but_no_rsa():
    target = atom("CB", (0.0, 0.0, 0.0), resn="MSE", element="C")
    result = result_for([target], residue_key(target))
    assert result.status == "completed"
    assert result.residue_sasa is not None
    assert result.reference_max_sasa is None
    assert result.relative_sasa is None
    assert result.classification == "unknown"


def test_sidechain_and_total_sasa_are_separated():
    backbone = atom("N", (-20.0, 0.0, 0.0), element="N")
    sidechain = atom("CB", (20.0, 0.0, 0.0))
    result = result_for([backbone, sidechain], residue_key(backbone))
    expected_sidechain = 4.0 * math.pi * (1.7 + 1.4) ** 2
    expected_backbone = 4.0 * math.pi * (1.55 + 1.4) ** 2
    assert result.sidechain_sasa == pytest.approx(expected_sidechain, abs=1e-9)
    assert result.residue_sasa == pytest.approx(expected_sidechain + expected_backbone, abs=1e-9)


def test_membrane_partition_sums_to_total_area():
    target = atom("CB", (0.0, 0.0, 0.0))
    result = result_for(
        [target],
        residue_key(target),
        membrane=membrane(lower=-1.0, upper=1.0, interface=1.0),
    )
    partition_sum = (
        result.partition.core_area + result.partition.interface_area + result.partition.outside_area
    )
    assert partition_sum == pytest.approx(result.residue_sasa, abs=1e-6)
    assert 0.0 <= result.partition.membrane_fraction <= 1.0


def test_zero_sasa_preserves_zero_areas_and_null_fractions():
    target = atom("CB", (0.0, 0.0, 0.0), resi="1", resn="ALA", element="C")
    enclosing = atom("I1", (0.0, 0.0, 0.0), resi="2", resn="UNK", element="I")
    result = result_for(
        [target, enclosing],
        residue_key(target),
        membrane=membrane(lower=-1.0, upper=2.0, interface=1.0),
    )

    assert result.residue_sasa == 0.0
    assert (
        result.partition.core_area,
        result.partition.interface_area,
        result.partition.outside_area,
    ) == (
        0.0,
        0.0,
        0.0,
    )
    assert (
        result.partition.core_fraction,
        result.partition.interface_fraction,
        result.partition.outside_fraction,
        result.partition.membrane_fraction,
    ) == (None, None, None, None)


def test_glycine_zero_sidechain_areas_have_null_fractions():
    gly_ca = atom("CA", (0.0, 0.0, 0.0), resn="GLY", element="C")
    result = result_for(
        [gly_ca],
        residue_key(gly_ca),
        membrane=membrane(lower=-1.0, upper=2.0, interface=1.0),
    )

    assert result.sidechain_sasa == 0.0
    assert (
        result.sidechain_partition.core_area,
        result.sidechain_partition.interface_area,
        result.sidechain_partition.outside_area,
    ) == (0.0, 0.0, 0.0)
    assert (
        result.sidechain_partition.core_fraction,
        result.sidechain_partition.interface_fraction,
        result.sidechain_partition.outside_fraction,
        result.sidechain_partition.membrane_fraction,
    ) == (None, None, None, None)


def test_unavailable_partition_never_materializes_zero():
    unknown = atom("QX", (0.0, 0.0, 0.0), element="")
    result = result_for([unknown], residue_key(unknown), membrane=membrane())

    assert result.status == "unavailable"
    assert set(result.partition.as_dict().values()) == {None}
    assert set(result.sidechain_partition.as_dict(prefix="sidechain_").values()) == {None}


def test_arbitrary_membrane_partition_is_joint_transform_invariant():
    atoms = [
        atom("CB", (0.0, 0.0, 0.0), resi="1"),
        atom("O", (2.0, 0.5, 0.0), resi="2", element="O"),
        atom("N", (0.5, 2.0, 1.0), resi="3", element="N"),
    ]
    original_membrane = membrane(normal=(1.0, 1.0, 0.0), lower=-1.0, upper=2.0)
    config = ExposureConfig(target_scope="all_residues")
    baseline = calculate_exposure(atoms, config=config, membrane=original_membrane)

    translation = (4.0, -3.0, 2.0)
    transformed_atoms = [
        atom(
            item.name,
            (-item.y + translation[0], item.x + translation[1], item.z + translation[2]),
            resi=item.resi,
            element=item.element,
        )
        for item in atoms
    ]
    transformed_membrane = membrane(
        center=translation,
        normal=(-1.0, 1.0, 0.0),
        lower=-1.0,
        upper=2.0,
    )
    transformed = calculate_exposure(
        transformed_atoms, config=config, membrane=transformed_membrane
    )
    for first, second in zip(baseline.residues, transformed.residues, strict=True):
        assert second.residue_sasa == pytest.approx(first.residue_sasa, abs=1e-7)
        assert second.partition.core_area == pytest.approx(first.partition.core_area, abs=1e-7)
        assert second.partition.interface_area == pytest.approx(
            first.partition.interface_area, abs=1e-7
        )
        assert second.partition.outside_area == pytest.approx(
            first.partition.outside_area, abs=1e-7
        )


def test_isolated_atom_asymmetric_membrane_partition_is_joint_transform_invariant():
    target = atom("CB", (1.2, -0.5, 2.0))
    original_membrane = membrane(
        center=(0.3, -0.2, 0.4),
        normal=(1.0, 2.0, 3.0),
        lower=-1.3,
        upper=2.1,
        interface=0.7,
    )
    baseline = result_for([target], residue_key(target), membrane=original_membrane)
    translation = (4.0, -3.0, 2.0)
    transformed_target = atom(
        "CB",
        (target.z + translation[0], target.x + translation[1], target.y + translation[2]),
    )
    transformed_membrane = membrane(
        center=(
            original_membrane.center[2] + translation[0],
            original_membrane.center[0] + translation[1],
            original_membrane.center[1] + translation[2],
        ),
        normal=(
            original_membrane.normal[2],
            original_membrane.normal[0],
            original_membrane.normal[1],
        ),
        lower=-1.3,
        upper=2.1,
        interface=0.7,
    )
    transformed = result_for(
        [transformed_target], residue_key(transformed_target), membrane=transformed_membrane
    )

    assert transformed.residue_sasa == pytest.approx(baseline.residue_sasa, abs=1e-7)
    assert transformed.partition.as_dict() == pytest.approx(baseline.partition.as_dict(), abs=1e-7)


def test_collinear_atoms_oblique_membrane_partition_is_joint_transform_invariant():
    atoms = [
        atom("CB", (-1.0, -1.0, -1.0), resi="1"),
        atom("CB", (1.0, 1.0, 1.0), resi="2"),
    ]
    original_membrane = membrane(
        center=(0.2, -0.3, 0.5),
        normal=(1.0, -2.0, 0.5),
        lower=-1.1,
        upper=1.8,
        interface=0.9,
    )
    config = ExposureConfig(target_scope="all_residues")
    baseline = calculate_exposure(atoms, config=config, membrane=original_membrane)
    translation = (3.0, 4.0, -2.0)
    transformed_atoms = [
        atom(
            item.name,
            (item.z + translation[0], item.x + translation[1], item.y + translation[2]),
            resi=item.resi,
        )
        for item in reversed(atoms)
    ]
    transformed_membrane = membrane(
        center=(
            original_membrane.center[2] + translation[0],
            original_membrane.center[0] + translation[1],
            original_membrane.center[1] + translation[2],
        ),
        normal=(
            original_membrane.normal[2],
            original_membrane.normal[0],
            original_membrane.normal[1],
        ),
        lower=-1.1,
        upper=1.8,
        interface=0.9,
    )
    transformed = calculate_exposure(
        transformed_atoms, config=config, membrane=transformed_membrane
    )

    for first, second in zip(baseline.residues, transformed.residues, strict=True):
        assert second.residue_sasa == pytest.approx(first.residue_sasa, abs=1e-7)
        assert second.partition.as_dict() == pytest.approx(first.partition.as_dict(), abs=1e-7)


def test_asymmetric_boundaries_and_interfaces_receive_accessible_area():
    target = atom("CB", (0.0, 0.0, 0.5))
    result = result_for(
        [target],
        residue_key(target),
        membrane=membrane(lower=-1.0, upper=2.0, interface=1.0),
    )
    assert result.partition.core_area > 0.0
    assert result.partition.interface_area > 0.0
    assert result.partition.outside_area > 0.0


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_probe_radius(value):
    with pytest.raises(ValueError, match="probe_radius"):
        ExposureConfig(probe_radius=value)


@pytest.mark.parametrize("value", [0, -1, 1.5, True])
def test_invalid_sphere_point_count(value):
    with pytest.raises(ValueError, match="sphere_points"):
        ExposureConfig(sphere_points=value)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"target_scope": "everything"}, "target_scope"),
        ({"include_hydrogens": 1}, "include_hydrogens"),
        ({"include_nonprotein_occluders": "yes"}, "include_nonprotein_occluders"),
        ({"radii_model": "unknown"}, "radii_model"),
        ({"rsa_reference": "unknown"}, "rsa_reference"),
        ({"buried_rsa_threshold": float("nan")}, "thresholds"),
        ({"buried_rsa_threshold": 0.3, "exposed_rsa_threshold": 0.2}, "thresholds"),
    ],
)
def test_invalid_exposure_configuration_fields(kwargs, message):
    with pytest.raises(ValueError, match=message):
        ExposureConfig(**kwargs)


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_coordinates_are_rejected(coordinate):
    target = atom("CB", (coordinate, 0.0, 0.0))
    with pytest.raises(ValueError, match="non-finite coordinates"):
        calculate_exposure([target], target_residues=[residue_key(target)])


def test_fibonacci_points_are_deterministic_unit_vectors():
    assert fibonacci_sphere_points(12) == fibonacci_sphere_points(12)
    assert all(
        math.sqrt(sum(component * component for component in point))
        == pytest.approx(1.0, abs=1e-12)
        for point in fibonacci_sphere_points(12)
    )


def test_pymol_adapter_extracts_optional_atom_metadata():
    pymol_atom = type(
        "PyMOLAtom",
        (),
        {
            "model": "m",
            "chain": "A",
            "resi": "1",
            "resn": "lys",
            "name": "nz",
            "coord": (1, 2, 3),
            "symbol": "N",
            "alt": "B",
            "q": 0.75,
            "formal_charge": 1,
            "hetatm": "0",
        },
    )()
    model = type("Model", (), {"atom": [pymol_atom]})()
    cmd = type("Cmd", (), {"get_model": lambda self, selection: model})()

    extracted = atoms_from_selection("m", cmd)[0]

    assert extracted.element == "N"
    assert extracted.altloc == "B"
    assert extracted.occupancy == 0.75
    assert extracted.formal_charge == 1
    assert extracted.is_hetatm is False


def test_structure_atoms_respects_exact_user_selection_scope():
    selections = []
    model = type("Model", (), {"atom": []})()

    class Cmd:
        def get_model(self, selection):
            selections.append(selection)
            return model

    assert structure_atoms("obj and chain A", Cmd()) == []
    assert selections == ["(obj and chain A)"]


def test_nonprotein_occluders_remain_model_isolated():
    target = atom("CB", (0.0, 0.0, 0.0), model="protein", is_hetatm=False)
    cross_model_heteroatom = atom(
        "I1",
        (0.0, 0.0, 0.0),
        model="ligand",
        resi="900",
        resn="IOD",
        element="I",
        is_hetatm=True,
    )
    config = ExposureConfig(include_nonprotein_occluders=True)

    isolated = result_for([target], residue_key(target), config=config)
    combined = result_for([target, cross_model_heteroatom], residue_key(target), config=config)

    assert combined.residue_sasa == pytest.approx(isolated.residue_sasa, abs=1e-12)
