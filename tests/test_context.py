from __future__ import annotations

import csv
from dataclasses import replace
import json
from pathlib import Path

import pytest
from jsonschema import validate

from membrane_vqc.chemistry import charged_role
from membrane_vqc.context import analyze_local_context, derive_context_state
from membrane_vqc.context_models import (
    CONTACT_TYPES,
    ExposureAnalysis,
    ExposureBackendMetadata,
    ExposureConfig,
    LocalContextAnalysis,
    LocalContextConfig,
    ResidueLocalContext,
    ResidueExposure,
    SurfacePartition,
)
from membrane_vqc.membrane import AtomRecord
from membrane_vqc.orientation import legacy_global_z
from membrane_vqc.report import build_report, export_report


def atom(resn, name, x, *, resi="1", chain="A", model="m", element="", het=False, alt=""):
    return AtomRecord(
        model,
        chain,
        resi,
        resn,
        name,
        x,
        0.0,
        0.0,
        element=element,
        altloc=alt,
        occupancy=1.0,
        is_hetatm=het,
    )


def exposure(key=("m", "A", "1", "LYS"), classification="buried"):
    empty = SurfacePartition(*(None for _ in range(7)))
    residue = ResidueExposure(
        *key,
        status="completed",
        residue_sasa=0.0,
        sidechain_sasa=0.0,
        relative_sasa=None if classification == "unknown" else 0.0,
        reference_max_sasa=None,
        reference_status="unavailable" if classification == "unknown" else "available",
        classification=classification,
        partition=empty,
        sidechain_partition=empty,
    )
    metadata = ExposureBackendMetadata(
        backend="builtin_shrake_rupley",
        backend_version="1",
        config=ExposureConfig(),
        alternate_atoms_seen=0,
        alternate_atoms_discarded=0,
        alternate_location_policy="test",
        models=(key[0],),
        freesasa_status="unavailable",
        warnings=(),
        elapsed_seconds=0.0,
    )
    return ExposureAnalysis("completed", (residue,), metadata)


def run(atoms, *, key=("m", "A", "1", "LYS"), classification="buried", config=None):
    return analyze_local_context(
        atoms,
        target_residues=[key],
        exposure_analysis=exposure(key, classification),
        config=config,
    ).residues[0]


def test_stage3b_contact_vocabulary_is_exactly_six_types():
    assert CONTACT_TYPES == {
        "putative_salt_bridge",
        "distance_only_potential_hbond",
        "nearby_water",
        "nearby_ion",
        "ligand_proximity",
        "polar_ligand_proximity",
    }


@pytest.mark.parametrize(
    ("partner", "expected"),
    [
        (atom("ASP", "OD1", 4.0, resi="2", chain="B", element="O"), "putative_salt_bridge"),
        (atom("HOH", "O", 3.5, resi="20", element="O", het=True), "nearby_water"),
        (atom("NA", "NA", 4.0, resi="21", element="NA", het=True), "nearby_ion"),
        (atom("LIG", "N1", 3.8, resi="22", element="N", het=True), "polar_ligand_proximity"),
        (atom("LIG", "C1", 5.0, resi="22", element="C", het=True), "ligand_proximity"),
    ],
)
def test_every_non_hbond_contact_type_and_inclusive_cutoff(partner, expected):
    result = run([atom("LYS", "NZ", 0, element="N"), partner])
    assert [contact.contact_type for contact in result.contacts] == [expected]
    assert result.context_state == "BURIED_WITH_POTENTIAL_SUPPORT"


def test_distance_only_potential_hbond_and_histidine_is_not_ionic():
    ser = atom("SER", "OG", 0, element="O")
    his = atom("HIS", "ND1", 3.5, resi="2", element="N")
    result = run([ser, his], key=("m", "A", "1", "SER"))
    assert charged_role(his) == ""
    assert [contact.contact_type for contact in result.contacts] == [
        "distance_only_potential_hbond"
    ]


def test_just_outside_cutoffs_are_not_detected():
    config = LocalContextConfig(salt_bridge_cutoff=4.0)
    result = run(
        [atom("LYS", "NZ", 0, element="N"), atom("ASP", "OD1", 4.0001, resi="2", element="O")],
        config=config,
    )
    assert result.contacts == ()
    assert result.context_state == "BURIED_NO_DETECTED_SUPPORT"


@pytest.mark.parametrize(
    ("burial", "support", "state"),
    [
        ("buried", "not_detected", "BURIED_NO_DETECTED_SUPPORT"),
        ("buried", "detected", "BURIED_WITH_POTENTIAL_SUPPORT"),
        ("intermediate", "not_detected", "ACCESSIBLE_NO_DETECTED_SUPPORT"),
        ("exposed", "detected", "ACCESSIBLE_WITH_POTENTIAL_SUPPORT"),
        ("unknown", "detected", "INSUFFICIENT_CONTEXT"),
        ("buried", "unavailable", "INSUFFICIENT_CONTEXT"),
    ],
)
def test_every_context_state_derivation(burial, support, state):
    assert derive_context_state(burial, support) == state


def test_contacts_are_same_model_only_but_interchain_is_valid():
    target = atom("LYS", "NZ", 0, element="N")
    cross_model = atom("ASP", "OD1", 1, resi="2", chain="B", model="other", element="O")
    same_model = replace(cross_model, model="m", x=3.0)
    result = run([target, cross_model, same_model])
    assert len(result.contacts) == 1
    assert result.contacts[0].partner_chain == "B"
    assert result.contacts[0].distance == 3.0


def test_input_order_and_rigid_transform_invariance():
    atoms = [
        atom("LYS", "NZ", 0, element="N"),
        atom("ASP", "OD1", 3, resi="2", element="O"),
    ]
    first = run(atoms).as_report_dict()
    second = run(list(reversed(atoms))).as_report_dict()
    shifted = [replace(item, x=item.z + 10, y=item.y - 5, z=-item.x + 3) for item in atoms]
    third = run(shifted).as_report_dict()
    assert first == second == third


def test_altloc_is_collapsed_and_partner_is_deduplicated_at_minimum_distance():
    target = atom("LYS", "NZ", 0, element="N")
    far = atom("ASP", "OD1", 4, resi="2", element="O", alt="B")
    near = replace(far, x=3, altloc="A")
    duplicate = atom("ASP", "OD2", 3.5, resi="2", element="O")
    result = run([target, far, near, duplicate])
    assert len(result.contacts) == 1
    assert result.contacts[0].distance == 3.0


def test_unsupported_hetero_element_is_not_contact_evidence():
    analysis = analyze_local_context(
        [
            atom("LYS", "NZ", 0, element="N"),
            atom("UNK", "SE", 2, resi="9", element="SE", het=True),
        ],
        target_residues=[("m", "A", "1", "LYS")],
        exposure_analysis=exposure(),
    )
    result = analysis.residues[0]
    assert result.contacts == ()
    assert "excluded from ligand context" in analysis.warnings[0]


def test_missing_optional_categories_are_counts_not_biological_absence_claims():
    exposure_result = exposure()
    analysis = analyze_local_context(
        [atom("LYS", "NZ", 0, element="N"), atom("ALA", "CA", 8, resi="2", element="C")],
        target_residues=[("m", "A", "1", "LYS")],
        exposure_analysis=exposure_result,
    )

    assert dict(analysis.category_atom_counts) == {
        "ion": 0,
        "ligand": 0,
        "other_hetatm": 0,
        "protein": 2,
        "water": 0,
    }
    assert analysis.residues[0].contact_support == "not_detected"
    assert analysis.residues[0].contacts == ()
    assert not any("absent" in warning.lower() for warning in analysis.warnings)
    report = build_report(
        selection="m",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=2,
        core_residues=1,
        flagged_residues=[
            {
                "model": "m",
                "chain": "A",
                "resi": "1",
                "resn": "LYS",
                "classification": "core",
                "severity": "WARNING",
                "reason": "zero optional-category fixture",
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
            }
        ],
        ligand_neighbours=[],
        warnings=[],
        exposure_analysis=exposure_result,
        local_context_analysis=analysis,
    )
    category_counts = report["context_analysis"]["local_context"]["category_atom_counts"]
    assert category_counts["water"] == category_counts["ion"] == category_counts["ligand"] == 0
    assert not any("biological absence" in warning.lower() for warning in report["warnings"])


def test_nonstandard_residue_with_unknown_exposure_is_insufficient():
    key = ("m", "A", "1", "MSE")
    result = run([atom("MSE", "SE", 0, element="SE")], key=key, classification="unknown")
    assert result.burial_state == "unknown"
    assert result.contact_support == "unavailable"
    assert result.context_state == "INSUFFICIENT_CONTEXT"


def test_schema_12_rich_context_and_deterministic_exports(tmp_path):
    key = ("m", "A", "1", "LYS")
    exposure_result = exposure(key)
    context_result = analyze_local_context(
        [
            atom("LYS", "NZ", 0, element="N"),
            atom("ASP", "OD1", 3, resi="2", element="O"),
        ],
        target_residues=[key],
        exposure_analysis=exposure_result,
    )
    report = build_report(
        selection="m",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=2,
        core_residues=1,
        flagged_residues=[
            {
                "model": "m",
                "chain": "A",
                "resi": "1",
                "resn": "LYS",
                "classification": "core",
                "severity": "WARNING",
                "reason": "test review evidence",
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
            }
        ],
        ligand_neighbours=[],
        warnings=[],
        membrane=legacy_global_z(-15, 15),
        exposure_analysis=exposure_result,
        local_context_analysis=context_result,
    )
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas" / "mvqc-report-1.2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validate(report, schema)
    item = report["review_items"][0]
    assert item["severity"] == "WARNING"
    assert item["local_context"]["context_state"] == "BURIED_WITH_POTENTIAL_SUPPORT"
    assert report["summary"]["context_state_counts"]["BURIED_WITH_POTENTIAL_SUPPORT"] == 1

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    export_report(report, first)
    export_report(report, second)
    assert first.read_bytes() == second.read_bytes()
    assert first.with_suffix(".csv").read_bytes() == second.with_suffix(".csv").read_bytes()


def test_review_json_uses_shared_context_priority_but_csv_keeps_residue_order(tmp_path):
    states = [
        "ACCESSIBLE_WITH_POTENTIAL_SUPPORT",
        "INSUFFICIENT_CONTEXT",
        "BURIED_WITH_POTENTIAL_SUPPORT",
        "ACCESSIBLE_NO_DETECTED_SUPPORT",
        "BURIED_NO_DETECTED_SUPPORT",
        "BURIED_NO_DETECTED_SUPPORT",
    ]
    residue_ids = ["50", "30", "20", "40", "10", "11"]
    exposure_results = []
    context_results = []
    flags = []
    empty = SurfacePartition(*(None for _ in range(7)))
    for index, (state, resi) in enumerate(zip(states, residue_ids, strict=True)):
        key = ("m", "A", resi, "LYS")
        classification = (
            "unknown"
            if state == "INSUFFICIENT_CONTEXT"
            else ("buried" if state.startswith("BURIED") else "exposed")
        )
        support = (
            "unavailable"
            if state == "INSUFFICIENT_CONTEXT"
            else "detected"
            if state.endswith("WITH_POTENTIAL_SUPPORT")
            else "not_detected"
        )
        exposure_results.append(
            ResidueExposure(
                *key,
                status="completed",
                residue_sasa=0.0,
                sidechain_sasa=0.0,
                relative_sasa=None if classification == "unknown" else 0.0,
                reference_max_sasa=None,
                reference_status="unavailable",
                classification=classification,
                partition=empty,
                sidechain_partition=empty,
            )
        )
        context_results.append(
            ResidueLocalContext(
                *key,
                status="unavailable" if support == "unavailable" else "completed",
                burial_state=classification,
                contact_support=support,
                context_state=state,
            )
        )
        flags.append(
            {
                "model": "m",
                "chain": "A",
                "resi": resi,
                "resn": "LYS",
                "classification": "core",
                "severity": "WARNING" if resi == "11" or index % 2 else "INSPECT",
                "reason": "scrambled priority fixture",
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
            }
        )
    metadata = ExposureBackendMetadata(
        backend="builtin_shrake_rupley",
        backend_version="1",
        config=ExposureConfig(),
        alternate_atoms_seen=0,
        alternate_atoms_discarded=0,
        alternate_location_policy="test",
        models=("m",),
        freesasa_status="unavailable",
        warnings=(),
        elapsed_seconds=0.0,
    )
    exposure_analysis = ExposureAnalysis("completed", tuple(exposure_results), metadata)
    context_analysis = LocalContextAnalysis("partial", tuple(context_results), LocalContextConfig())
    report = build_report(
        selection="m",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=6,
        core_residues=6,
        flagged_residues=flags,
        ligand_neighbours=[],
        warnings=[],
        exposure_analysis=exposure_analysis,
        local_context_analysis=context_analysis,
    )

    assert [item["local_context"]["context_state"] for item in report["review_items"]] == [
        "BURIED_NO_DETECTED_SUPPORT",
        "BURIED_NO_DETECTED_SUPPORT",
        "BURIED_WITH_POTENTIAL_SUPPORT",
        "INSUFFICIENT_CONTEXT",
        "ACCESSIBLE_NO_DETECTED_SUPPORT",
        "ACCESSIBLE_WITH_POTENTIAL_SUPPORT",
    ]
    assert [item["resi"] for item in report["review_items"][:2]] == ["11", "10"]
    assert list(report["summary"]["context_state_counts"]) == [
        "BURIED_NO_DETECTED_SUPPORT",
        "BURIED_WITH_POTENTIAL_SUPPORT",
        "INSUFFICIENT_CONTEXT",
        "ACCESSIBLE_NO_DETECTED_SUPPORT",
        "ACCESSIBLE_WITH_POTENTIAL_SUPPORT",
    ]
    output = tmp_path / "ordered.json"
    export_report(report, output)
    with output.with_suffix(".csv").open(newline="", encoding="utf-8") as handle:
        assert [row["resi"] for row in csv.DictReader(handle)] == sorted(residue_ids)
