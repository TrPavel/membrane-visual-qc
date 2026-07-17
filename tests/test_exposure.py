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
from membrane_vqc.pymol_adapter import atoms_from_selection


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
    assert set(TIEN_2013_THEORETICAL_MAX_ASA) == {
        "ALA",
        "ARG",
        "ASN",
        "ASP",
        "CYS",
        "GLN",
        "GLU",
        "GLY",
        "HIS",
        "ILE",
        "LEU",
        "LYS",
        "MET",
        "PHE",
        "PRO",
        "SER",
        "THR",
        "TRP",
        "TYR",
        "VAL",
    }
    assert TIEN_2013_THEORETICAL_MAX_ASA["ALA"] == 129.0
    assert TIEN_2013_THEORETICAL_MAX_ASA["TRP"] == 285.0


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


def test_element_inference_does_not_read_protein_ca_as_calcium():
    alpha_carbon = atom("CA", (0.0, 0.0, 0.0), element="")
    chloride = atom("CL", (0.0, 0.0, 0.0), resn="CL", element="", is_hetatm=True)
    assert normalize_or_infer_element(alpha_carbon) == "C"
    assert normalize_or_infer_element(chloride) == "CL"


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
