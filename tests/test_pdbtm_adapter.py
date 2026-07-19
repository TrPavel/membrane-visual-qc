import copy
from dataclasses import replace
import hashlib
import itertools
import json
import math
from pathlib import Path

import pytest

from membrane_vqc.context_models import ExposureConfig
from membrane_vqc.errors import OrientationError, ReportError
from membrane_vqc.exposure import calculate_exposure
from membrane_vqc.membrane import AtomRecord
from membrane_vqc.orientation_sources import (
    OrientationImportResult,
    OrientationPayload,
    OrientationPayloadSet,
    StructureContext,
)
from membrane_vqc.pdbtm_adapter import (
    MAX_PAYLOAD_BYTES,
    PdbtmApiV1Adapter,
    import_pdbtm_orientation,
)
from membrane_vqc.report import build_report, validate_report, validate_stage4_report_semantics
from scripts.validate_example_reports import validate_reports


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_1_3 = ROOT / "schemas" / "mvqc-report-1.3.schema.json"


POINTS = [
    (0.0, 0.0, 0.0),
    (12.0, 0.0, 0.0),
    (0.0, 3.0, 0.0),
    (0.0, 0.0, 4.0),
    (3.0, 2.0, 1.0),
    (5.0, -2.0, 3.0),
    (7.0, 4.0, -1.0),
    (9.0, 1.0, 5.0),
    (11.0, -3.0, 2.0),
    (2.0, 5.0, 6.0),
    (6.0, 6.0, -2.0),
    (13.0, 3.0, 4.0),
]


ROTATION = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
TRANSLATION = (10.0, -5.0, 3.0)


def _apply(points, rotation=ROTATION, translation=TRANSLATION):
    return [
        tuple(sum(rotation[i][j] * point[j] for j in range(3)) + translation[i] for i in range(3))
        for point in points
    ]


def _pdb(
    points,
    *,
    pdb_id="test",
    model=None,
    altlocs=None,
    chains=None,
    residues=None,
    atom_names=None,
):
    lines = [f"HEADER{'':56}{pdb_id.upper():>4}"]
    if model is not None:
        lines.append(f"MODEL     {model:4d}")
    for index, point in enumerate(points, 1):
        residue = (residues or {}).get(index, (index - 1) // 4 + 1)
        atom_name = (atom_names or {}).get(index, ("CA", "CB", "CG", "CD")[(index - 1) % 4])
        altloc = (altlocs or {}).get(index, "")
        chain = (chains or {}).get(index, "A")
        lines.append(
            f"ATOM  {index:5d} {atom_name:>4}{altloc:1}{'ALA':>3} {chain:1}{residue:4d}    "
            f"{point[0]:8.3f}{point[1]:8.3f}{point[2]:8.3f}{1.00:6.2f}{20.00:6.2f}          C "
        )
    if model is not None:
        lines.append("ENDMDL")
    lines.append("END")
    return ("\n".join(lines) + "\n").encode("ascii")


def _matrix_rows(rotation=ROTATION, translation=TRANSLATION):
    names = ("rowx", "rowy", "rowz")
    rows = []
    for i, name in enumerate(names):
        rows.append(
            f'"{name}":{{"x":{rotation[i][0]:.8f},"y":{rotation[i][1]:.8f},'
            f'"z":{rotation[i][2]:.8f},"t":{translation[i]:.8f}}}'
        )
    return "{" + ",".join(rows) + "}"


def _json_payload(
    *,
    resource_version="1017",
    rotation=ROTATION,
    translation=TRANSLATION,
    normal=(0.0, 0.0, 15.0),
    mapping=None,
    extra="",
    multiple_membranes=False,
    assembly=None,
    chain_labels=("X",),
):
    mapping = mapping or {"A": ["X"]}
    mapping_text = json.dumps(mapping, separators=(",", ":"))
    membrane = (
        "{"
        f'"normal":{{"x":{normal[0]:.8f},"y":{normal[1]:.8f},"z":{normal[2]:.8f}}},'
        f'"transformation_matrix":{_matrix_rows(rotation, translation)}'
        f"{extra}"
        "}"
    )
    membrane_value = f"[{membrane},{membrane}]" if multiple_membranes else membrane
    assembly_text = f'"assembly_id":"{assembly}",' if assembly is not None else ""
    chains_text = json.dumps(
        [{"chain_label": label} for label in chain_labels], separators=(",", ":")
    )
    return (
        "{"
        '"pdb_id":"test","data_resource":"PDBTM",'
        f'"resource_version":"{resource_version}","software_version":"3.2.134",'
        f"{assembly_text}"
        f'"chains":{chains_text},'
        '"additional_entry_annotations":{'
        f'"ent_cif_mapping_results":{{"ent_cif_chain_map":{mapping_text}}},'
        f'"membrane":{membrane_value}'
        "}}"
    ).encode("utf-8")


def _import(current_points, **json_kwargs):
    transformed = _apply(
        POINTS, json_kwargs.get("rotation", ROTATION), json_kwargs.get("translation", TRANSLATION)
    )
    context = StructureContext(_pdb(current_points), "test", 1)
    return import_pdbtm_orientation(_json_payload(**json_kwargs), _pdb(transformed), context)


def _codes(result):
    return [item.code for item in result.messages]


def _adapter_parse(primary_role="pdbtm_json", companion_roles=()):
    transformed = _pdb(_apply(POINTS))
    primary = OrientationPayload(primary_role, _json_payload())
    companions = tuple(OrientationPayload(role, transformed) for role in companion_roles)
    return PdbtmApiV1Adapter().parse(
        OrientationPayloadSet(primary, companions),
        structure_context=StructureContext(transformed, "test", 1),
        metadata={},
    )


def _stage4_report():
    imported = _import(_apply(POINTS))
    return build_report(
        selection="test",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=0,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        membrane=imported.membrane,
        orientation_evidence=imported.evidence,
    )


def test_adapter_rejects_wrong_primary_role_before_parsing_json():
    result = _adapter_parse(primary_role="json")

    assert result.status == "rejected"
    assert _codes(result) == ["UNEXPECTED_PAYLOAD_ROLE"]


def test_adapter_rejects_unexpected_extra_companion_role():
    result = _adapter_parse(companion_roles=("transformed_pdb", "notes"))

    assert result.status == "rejected"
    assert _codes(result) == ["UNEXPECTED_PAYLOAD_ROLE"]


def test_adapter_rejects_duplicate_transformed_companions():
    result = _adapter_parse(companion_roles=("transformed_pdb", "transformed_pdb"))

    assert result.status == "rejected"
    assert _codes(result) == ["COMPANION_COUNT"]


def test_adapter_accepts_exact_partial_and_imported_payload_sets():
    partial = _adapter_parse()
    imported = _adapter_parse(companion_roles=("transformed_pdb",))

    assert partial.status == "partial"
    assert [item.role for item in partial.source.raw_payloads] == ["pdbtm_json"]
    assert imported.status == "imported"
    assert [item.role for item in imported.source.raw_payloads] == [
        "pdbtm_json",
        "transformed_pdb",
    ]


def test_transformed_identity_match_and_evidence_are_deterministic():
    transformed = _apply(POINTS)
    first = _import(transformed)
    second = _import(transformed)

    assert first.status == "imported"
    assert first.evidence.mapping.method == "identity"
    assert first.membrane.center == (0.0, 0.0, 0.0)
    assert first.membrane.normal == (0.0, 0.0, 1.0)
    assert first.evidence.as_dict() == second.evidence.as_dict()
    fingerprints = first.evidence.mapping.fingerprints
    assert fingerprints["algorithm"] == "mvqc_atom_identity_coordinates_sha256"
    assert fingerprints["version"] == "1"
    assert fingerprints["current"] == fingerprints["transformed_reference"]
    precision = first.evidence.mapping.precision_profile
    assert precision["runtime_identity_theoretical_bound"] <= 0.002
    assert precision["runtime_inverse_theoretical_bound"] <= 0.003
    assert precision["provider_forward_theoretical_bound"] > 0
    assert precision["reviewed_envelope_decision"] == "accepted"


def test_inverse_match_maps_geometry_into_original_frame():
    result = _import(POINTS)

    assert result.status == "imported"
    assert result.evidence.mapping.method == "inverse_provider_transform"
    assert result.membrane.center == pytest.approx((5.0, 10.0, -3.0))
    assert result.membrane.normal == pytest.approx((0.0, 0.0, 1.0))
    assert result.evidence.current_geometry.center == result.membrane.center
    assert result.evidence.current_geometry.normal == result.membrane.normal


def test_provider_geometry_has_no_mvqc_interface_width():
    result = _import(_apply(POINTS))

    assert result.status == "imported"
    assert result.evidence.source_geometry.interface_width is None
    assert result.evidence.current_geometry.interface_width == pytest.approx(3.0)
    assert result.membrane.interface_width == pytest.approx(3.0)
    assert result.evidence.raw_metadata["mvqc_interface_width"] == pytest.approx(3.0)


def test_neither_reference_matches_without_fitting():
    shifted = [(x + 1.0, y + 2.0, z - 3.0) for x, y, z in POINTS]
    result = _import(shifted)

    assert result.status == "rejected"
    assert _codes(result) == ["COORDINATE_FRAME_MISMATCH"]
    assert result.membrane is None


def test_near_identity_transform_is_rejected_as_ambiguous():
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    zero = (0.0, 0.0, 0.0)
    result = _import(POINTS, rotation=identity, translation=zero)

    assert result.status == "rejected"
    assert _codes(result) == ["AMBIGUOUS_COORDINATE_FRAME"]


def test_json_without_companion_is_partial_and_never_creates_membrane():
    context = StructureContext(_pdb(POINTS), "test", 1)
    result = import_pdbtm_orientation(_json_payload(), None, context)

    assert result.status == "partial"
    assert result.source.raw_payloads[0].role == "pdbtm_json"
    assert result.source.raw_payloads[0].retrieval_verified is False
    assert result.membrane is None
    assert result.evidence is None


def test_caller_cannot_spoof_verified_retrieval_provenance():
    context = StructureContext(_pdb(_apply(POINTS)), "test", 1)
    result = import_pdbtm_orientation(
        _json_payload(),
        _pdb(_apply(POINTS)),
        context,
        {
            "json_retrieval_verified": True,
            "pdb_retrieval_verified": True,
            "json_source": "https://example.invalid/declared",
        },
    )

    assert result.status == "imported"
    assert {item.retrieval_verified for item in result.source.raw_payloads} == {False}


def test_future_resource_snapshot_with_same_contract_is_supported():
    result = _import(_apply(POINTS), resource_version="1018")

    assert result.status == "imported"
    assert result.source.resource_version == "1018"
    assert result.source.software_version == "3.2.134"


def test_json_field_order_does_not_change_normalized_geometry_or_mapping():
    base = _json_payload()
    reordered = base.replace(
        b'"pdb_id":"test","data_resource":"PDBTM",',
        b'"data_resource":"PDBTM","pdb_id":"test",',
        1,
    )
    context = StructureContext(_pdb(_apply(POINTS)), "test", 1)
    first = import_pdbtm_orientation(base, _pdb(_apply(POINTS)), context)
    second = import_pdbtm_orientation(reordered, _pdb(_apply(POINTS)), context)

    assert first.status == second.status == "imported"
    assert first.evidence.current_geometry == second.evidence.current_geometry
    assert first.evidence.mapping == second.evidence.mapping
    assert first.source.raw_payloads != second.source.raw_payloads


@pytest.mark.parametrize(
    ("json_payload", "expected"),
    [
        (_json_payload(normal=(0.0, 0.0, 0.0)), "ZERO_NORMAL"),
        (_json_payload().replace(b'"normal"', b'"missing_normal"'), "MISSING_NORMAL"),
        (_json_payload().replace(b"1.00000000", b"1.10000000", 1), "NON_RIGID_TRANSFORM"),
        (
            _json_payload().replace(b'"rowy":{"x":1.00000000', b'"rowy":{"x":-1.00000000', 1),
            "NON_RIGID_TRANSFORM",
        ),
        (
            _json_payload().replace(b'"rowx":{"x":0.00000000', b'"rowx":{"x":0.000001', 1),
            "PRECISION_OUTSIDE_ENVELOPE",
        ),
        (
            _json_payload().replace(b'"rowy":{"x":1.00000000', b'"rowy":{"x":0.00000000', 1),
            "NON_RIGID_TRANSFORM",
        ),
        (_json_payload(multiple_membranes=True), "MULTIPLE_MEMBRANES"),
        (_json_payload().replace(b'"rowx"', b'"different_row"', 1), "UNSUPPORTED_FIELD_STRUCTURE"),
    ],
)
def test_invalid_geometry_format_and_precision_paths(json_payload, expected):
    context = StructureContext(_pdb(POINTS), "test", 1)
    result = import_pdbtm_orientation(json_payload, _pdb(_apply(POINTS)), context)

    assert result.status in {"rejected", "unsupported"}
    assert _codes(result) == [expected]


@pytest.mark.parametrize(
    "normal",
    [
        (0.001, 0.0, 15.0),
        (0.0, -0.001, 15.0),
        (0.0, 0.0, -15.0),
    ],
)
def test_unreviewed_pdbtm_normal_semantics_are_unsupported(normal):
    result = _import(_apply(POINTS), normal=normal)

    assert result.status == "unsupported"
    assert _codes(result) == ["UNSUPPORTED_NORMAL_SEMANTICS"]


def test_reviewed_near_zero_normal_xy_noise_is_accepted():
    result = _import(_apply(POINTS), normal=(0.00000001, -0.00000001, 15.0))

    assert result.status == "imported"
    assert result.evidence.source_geometry.normal == (0.0, 0.0, 1.0)
    assert result.evidence.source_geometry.upper_offset == 15.0


def test_candidate_membrane_limit_is_enforced_before_resolution():
    single = _json_payload()
    marker = b'"membrane":'
    prefix, membrane = single.split(marker, 1)
    membrane = membrane[:-2]
    payload = prefix + marker + b"[" + b",".join([membrane] * 9) + b"]}}"
    context = StructureContext(_pdb(POINTS), "test", 1)

    result = import_pdbtm_orientation(payload, _pdb(_apply(POINTS)), context)

    assert result.status == "rejected"
    assert _codes(result) == ["CANDIDATE_MEMBRANE_LIMIT"]


def test_duplicate_sensitive_json_key_and_nonfinite_number_are_rejected():
    duplicate = _json_payload().replace(b'"pdb_id":"test"', b'"pdb_id":"test","pdb_id":"evil"')
    nonfinite = _json_payload().replace(b"15.00000000", b"NaN")
    context = StructureContext(_pdb(POINTS), "test", 1)

    assert _codes(import_pdbtm_orientation(duplicate, None, context)) == ["DUPLICATE_JSON_KEY"]
    assert _codes(import_pdbtm_orientation(nonfinite, None, context)) == ["NONFINITE_JSON_NUMBER"]


def test_chain_namespace_and_structure_scope_mismatches_are_rejected():
    wrong_chain = _import(_apply(POINTS), mapping={"B": ["X"]})
    context = StructureContext(_pdb(_apply(POINTS)), "other", 1)
    wrong_id = import_pdbtm_orientation(_json_payload(), _pdb(_apply(POINTS)), context)

    assert _codes(wrong_chain) == ["CHAIN_NAMESPACE_MISMATCH"]
    assert _codes(wrong_id) == ["STRUCTURE_ID_MISMATCH"]


def test_missing_chain_map_is_unsupported_even_without_companion():
    payload = _json_payload().replace(b'"ent_cif_chain_map"', b'"missing_chain_map"')
    result = import_pdbtm_orientation(payload, None, StructureContext(_pdb(POINTS), "test", 1))

    assert result.status == "unsupported"
    assert _codes(result) == ["CHAIN_MAPPING_MISSING"]


@pytest.mark.parametrize("current_has_extra", [False, True])
def test_missing_or_extra_legacy_chain_is_rejected(current_has_extra):
    transformed = _apply(POINTS)
    companion_chains = {12: "B"} if not current_has_extra else {}
    current_chains = {12: "B"} if current_has_extra else {}
    mapping = {"A": ["X"], "B": ["Y"]}
    payload = _json_payload(mapping=mapping, chain_labels=("X", "Y"))
    context = StructureContext(_pdb(transformed, chains=current_chains), "test", 1)

    result = import_pdbtm_orientation(payload, _pdb(transformed, chains=companion_chains), context)

    assert result.status == "rejected"
    assert _codes(result) == ["CHAIN_SET_MISMATCH"]


def test_chain_map_and_assembly_provenance_are_serialized_separately():
    transformed = _apply(POINTS)
    context = StructureContext(_pdb(transformed), "test", 1, biological_assembly="1")
    result = import_pdbtm_orientation(_json_payload(assembly="1"), _pdb(transformed), context)

    assert result.status == "imported"
    source = result.evidence.source_scope.as_dict()
    current = result.evidence.current_scope.as_dict()
    assert source["biological_assembly"] == "1"
    assert current["biological_assembly"] == "1"
    assert source["provider_chain_labels"] == ["X"]
    assert source["legacy_chains"] == ["A"]
    assert source["chain_mapping"] == {"A": ["X"]}
    assert source["selected_model"] == current["selected_model"] == 1


def test_provider_assembly_is_not_copied_from_current_and_mismatch_rejects():
    transformed = _apply(POINTS)
    no_provider = import_pdbtm_orientation(
        _json_payload(),
        _pdb(transformed),
        StructureContext(_pdb(transformed), "test", 1, biological_assembly="2"),
    )
    mismatch = import_pdbtm_orientation(
        _json_payload(assembly="1"),
        _pdb(transformed),
        StructureContext(_pdb(transformed), "test", 1, biological_assembly="2"),
    )

    assert no_provider.status == "imported"
    assert no_provider.evidence.source_scope.biological_assembly is None
    assert no_provider.evidence.current_scope.biological_assembly == "2"
    assert mismatch.status == "rejected"
    assert _codes(mismatch) == ["ASSEMBLY_MISMATCH"]


def test_companion_id_and_model_mismatch_are_rejected():
    context = StructureContext(_pdb(_apply(POINTS)), "test", 1)
    wrong_companion = import_pdbtm_orientation(
        _json_payload(), _pdb(_apply(POINTS), pdb_id="evil"), context
    )
    model_context = StructureContext(_pdb(_apply(POINTS), model=2), "test", 1)
    wrong_model = import_pdbtm_orientation(
        _json_payload(), _pdb(_apply(POINTS), model=2), model_context
    )

    assert _codes(wrong_companion) == ["COMPANION_ID_MISMATCH"]
    assert _codes(wrong_model) == ["MODEL_MISMATCH"]


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        (POINTS[:11], "INSUFFICIENT_MATCHED_ATOMS"),
        ([(float(i), 0.0, 0.0) for i in range(12)], "COLLINEAR_MATCHED_ATOMS"),
        ([(i / 10, (i % 3) / 10, (i % 2) / 10) for i in range(12)], "INSUFFICIENT_SPATIAL_EXTENT"),
    ],
)
def test_applicability_minimums(points, expected):
    transformed = _apply(points)
    context = StructureContext(_pdb(transformed), "test", 1)
    result = import_pdbtm_orientation(_json_payload(), _pdb(transformed), context)

    assert _codes(result) == [expected]


def test_insufficient_matched_residues_is_separate_from_atom_count():
    atom_names = {index: f"A{index:02d}" for index in range(1, 13)}
    residues = {index: 1 if index <= 6 else 2 for index in range(1, 13)}
    transformed = _apply(POINTS)
    current = _pdb(transformed, atom_names=atom_names, residues=residues)
    companion = _pdb(transformed, atom_names=atom_names, residues=residues)

    result = import_pdbtm_orientation(
        _json_payload(), companion, StructureContext(current, "test", 1)
    )

    assert _codes(result) == ["INSUFFICIENT_MATCHED_RESIDUES"]


def test_transpose_and_translation_before_rotation_traps_do_not_fit():
    transpose = tuple(tuple(ROTATION[j][i] for j in range(3)) for i in range(3))
    transposed_current = _apply(POINTS, transpose, TRANSLATION)
    pretranslated = [
        tuple(sum(ROTATION[i][j] * (point[j] + TRANSLATION[j]) for j in range(3)) for i in range(3))
        for point in POINTS
    ]

    assert _codes(_import(transposed_current)) == ["COORDINATE_FRAME_MISMATCH"]
    assert _codes(_import(pretranslated)) == ["COORDINATE_FRAME_MISMATCH"]


def test_altloc_policy_prefers_blank_then_occupancy_and_lexical():
    transformed = _apply(POINTS)
    current = _pdb(transformed).decode("ascii").splitlines()
    duplicate = current[1][:16] + "A" + current[1][17:]
    duplicate = duplicate[:54] + f"{0.50:6.2f}" + duplicate[60:]
    current.insert(2, duplicate)
    context = StructureContext(("\n".join(current) + "\n").encode("ascii"), "test", 1)
    result = import_pdbtm_orientation(_json_payload(), _pdb(transformed), context)

    assert result.status == "imported"


def test_nonfinite_occupancy_and_duplicate_identity_altloc_are_rejected():
    transformed = _apply(POINTS)
    lines = _pdb(transformed).decode("ascii").splitlines()
    nonfinite = list(lines)
    nonfinite[1] = nonfinite[1][:54] + "   nan" + nonfinite[1][60:]
    duplicate = list(lines)
    duplicate.insert(2, duplicate[1])
    payload = _json_payload()

    invalid_occupancy = import_pdbtm_orientation(
        payload,
        _pdb(transformed),
        StructureContext(("\n".join(nonfinite) + "\n").encode("ascii"), "test", 1),
    )
    duplicate_identity = import_pdbtm_orientation(
        payload,
        _pdb(transformed),
        StructureContext(("\n".join(duplicate) + "\n").encode("ascii"), "test", 1),
    )

    assert _codes(invalid_occupancy) == ["INVALID_OCCUPANCY"]
    assert _codes(duplicate_identity) == ["DUPLICATE_ATOM_IDENTITY"]


def test_spatial_witness_is_explicitly_a_lower_bound_not_a_maximum():
    points = [
        (3.0, -2.0, -1.0),
        (9.0, -9.0, 1.0),
        (9.0, 6.0, -2.0),
        (3.0, 7.0, 2.0),
        (4.0, 0.0, 0.0),
        (5.0, 1.0, 1.0),
        (6.0, -1.0, 0.0),
        (7.0, 0.0, 1.0),
        (4.0, 2.0, -1.0),
        (5.0, 3.0, 0.0),
        (6.0, 2.0, 1.0),
        (7.0, 1.0, -1.0),
    ]
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    translation = (1.0, 0.0, 0.0)
    transformed = _apply(points, identity, translation)
    result = import_pdbtm_orientation(
        _json_payload(rotation=identity, translation=translation),
        _pdb(transformed),
        StructureContext(_pdb(transformed), "test", 1),
    )
    metrics = result.evidence.mapping.metrics["runtime_identity"]
    exact = max(math.dist(a, b) for a, b in itertools.combinations(points, 2))

    assert result.status == "imported"
    assert metrics["spatial_witness_method"] == "lexicographic_double_sweep_lower_bound_v1"
    assert metrics["spatial_witness_separation_lower_bound"] < exact
    assert "maximum_pairwise_separation" not in metrics


def test_large_coordinates_with_valid_decimals_can_exceed_precision_envelope():
    c = math.sqrt(0.5)
    rotation = ((c, -c, 0.0), (c, c, 0.0), (0.0, 0.0, 1.0))
    points = [(9000.0 + x, y, z) for x, y, z in POINTS]
    transformed = _apply(points, rotation, (0.0, 0.0, 0.0))
    payload = _json_payload(rotation=rotation, translation=(0.0, 0.0, 0.0))
    payload = payload.replace(b"0.70710678", b"0.7071068").replace(b"-0.70710678", b"-0.7071068")

    result = import_pdbtm_orientation(
        payload, _pdb(transformed), StructureContext(_pdb(points), "test", 1)
    )

    assert result.status == "unsupported"
    assert _codes(result) == ["PRECISION_OUTSIDE_ENVELOPE"]


def test_signed_zero_fingerprint_is_canonical_and_deterministic():
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    translation = (1.0, 0.0, 0.0)
    transformed = _apply(POINTS, identity, translation)
    signed = [(x, -0.0 if y == 0 else y, z) for x, y, z in transformed]
    result = import_pdbtm_orientation(
        _json_payload(rotation=identity, translation=translation),
        _pdb(signed),
        StructureContext(_pdb(transformed), "test", 1),
    )
    fingerprint = result.evidence.mapping.fingerprints["current"]
    records = []
    for index, point in enumerate(transformed, 1):
        residue = (index - 1) // 4 + 1
        atom = ("CA", "CB", "CG", "CD")[(index - 1) % 4]
        fields = ("A", str(residue), "", "ALA", atom, "")
        xyz = tuple(0.0 if round(value, 3) == 0 else round(value, 3) for value in point)
        records.append((fields, xyz))
    lines = [
        "\t".join((*fields, *(f"{value:.3f}" for value in xyz))) for fields, xyz in sorted(records)
    ]
    independent = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()

    assert result.status == "imported"
    assert result.evidence.mapping.fingerprints["transformed_reference"] == fingerprint
    assert fingerprint == independent


def test_payload_size_boundary_and_container_rejection():
    context = StructureContext(_pdb(POINTS), "test", 1)
    exact = _json_payload() + b" " * (MAX_PAYLOAD_BYTES - len(_json_payload()))
    over = exact + b" "

    assert import_pdbtm_orientation(exact, None, context).status == "partial"
    assert _codes(import_pdbtm_orientation(over, None, context)) == ["PAYLOAD_TOO_LARGE"]
    assert _codes(import_pdbtm_orientation(b"\x1f\x8bgarbage", None, context)) == [
        "CONTAINER_NOT_ALLOWED"
    ]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b'{"x":"' + b"a" * 4097 + b'"}', "STRING_TOO_LONG"),
        (b'{"x":' * 33 + b"0" + b"}" * 33, "JSON_DEPTH_LIMIT"),
        (_json_payload() + b"\x00", "NUL_BYTE"),
        (b"{\xff}", "INVALID_ENCODING"),
    ],
)
def test_strict_json_limits(payload, expected):
    result = import_pdbtm_orientation(payload, None, StructureContext(_pdb(POINTS), "test", 1))
    assert _codes(result) == [expected]


def test_json_chain_count_limit_is_enforced():
    labels = tuple(f"X{index}" for index in range(513))
    context = StructureContext(_pdb(POINTS), "test", 1)
    result = import_pdbtm_orientation(_json_payload(chain_labels=labels), None, context)
    assert result.status == "rejected"
    assert _codes(result) == ["CHAIN_LIMIT"]


def test_pdb_line_and_record_limits_are_enforced():
    context = StructureContext(_pdb(_apply(POINTS)), "test", 1)
    long_line = _pdb(_apply(POINTS)) + b"X" * 4097 + b"\n"
    too_many = b"REMARK\n" * 250_001

    assert _codes(import_pdbtm_orientation(_json_payload(), long_line, context)) == [
        "LINE_LENGTH_LIMIT"
    ]
    assert _codes(import_pdbtm_orientation(_json_payload(), too_many, context)) == ["RECORD_LIMIT"]


def test_schema_1_3_report_without_context(tmp_path):
    pytest.importorskip("jsonschema")
    imported = _import(_apply(POINTS))
    report = build_report(
        selection="test",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=0,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        membrane=imported.membrane,
        orientation_evidence=imported.evidence,
    )
    path = tmp_path / "pdbtm.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    assert report["schema_version"] == "1.3"
    assert report["software"]["version"] == "0.4.0"
    validate_reports(SCHEMA_1_3, [path])


def test_schema_1_3_report_with_stage3_context(tmp_path):
    pytest.importorskip("jsonschema")
    imported = _import(_apply(POINTS))
    atom = AtomRecord("m", "A", "1", "LYS", "NZ", 0, 0, 0, element="N")
    exposure = calculate_exposure(
        [atom],
        config=ExposureConfig(target_scope="all_residues"),
        target_residues=[("m", "A", "1", "LYS")],
        membrane=imported.membrane,
    )
    report = build_report(
        selection="test",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=1,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        membrane=imported.membrane,
        orientation_evidence=imported.evidence,
        exposure_analysis=exposure,
    )
    path = tmp_path / "pdbtm-context.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    assert report["schema_version"] == "1.3"
    assert "context_analysis" in report
    validate_reports(SCHEMA_1_3, [path])


def test_schema_1_3_rejects_malformed_or_incomplete_stage4_evidence():
    jsonschema = pytest.importorskip("jsonschema")
    imported = _import(_apply(POINTS))
    report = build_report(
        selection="test",
        zmin=-15,
        zmax=15,
        ligand_selection="",
        cutoff=5,
        total_residues=0,
        flagged_residues=[],
        ligand_neighbours=[],
        warnings=[],
        membrane=imported.membrane,
        orientation_evidence=imported.evidence,
    )
    schema = json.loads(SCHEMA_1_3.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    invalid_reports = []

    malformed_matrix = copy.deepcopy(report)
    malformed_matrix["orientation"]["evidence"]["coordinate_mapping"]["source_to_current"] = [
        [1, 0, 0, 0]
    ]
    invalid_reports.append(malformed_matrix)

    for field in ("chain_namespace", "chain_mapping"):
        missing_scope = copy.deepcopy(report)
        del missing_scope["orientation"]["evidence"]["source_scope"][field]
        invalid_reports.append(missing_scope)

    invalid_fingerprint = copy.deepcopy(report)
    invalid_fingerprint["orientation"]["evidence"]["coordinate_mapping"]["fingerprints"][
        "current"
    ] = "not-a-digest"
    invalid_reports.append(invalid_fingerprint)

    missing_payload = copy.deepcopy(report)
    missing_payload["orientation"]["evidence"]["source"]["raw_payloads"].pop()
    invalid_reports.append(missing_payload)

    duplicate_role = copy.deepcopy(report)
    duplicate_role["orientation"]["evidence"]["source"]["raw_payloads"][1]["role"] = "pdbtm_json"
    invalid_reports.append(duplicate_role)

    missing_threshold = copy.deepcopy(report)
    del missing_threshold["orientation"]["evidence"]["coordinate_mapping"]["thresholds"][
        "runtime_inverse_match_limit"
    ]
    invalid_reports.append(missing_threshold)

    for normal in ([0, 0, 0], [0, 0, 2]):
        invalid_normal = copy.deepcopy(report)
        invalid_normal["orientation"]["evidence"]["current_geometry"]["normal"] = normal
        invalid_reports.append(invalid_normal)

    unknown_method = copy.deepcopy(report)
    unknown_method["orientation"]["evidence"]["coordinate_mapping"]["method"] = "best_fit"
    invalid_reports.append(unknown_method)

    unexpected = copy.deepcopy(report)
    unexpected["orientation"]["evidence"]["unexpected"] = True
    invalid_reports.append(unexpected)

    assert not list(validator.iter_errors(report))
    assert all(list(validator.iter_errors(item)) for item in invalid_reports)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("center", (1.0, 0.0, 0.0)),
        ("normal", (1.0, 0.0, 0.0)),
        ("lower_offset", -14.0),
        ("upper_offset", 14.0),
        ("interface_width", 4.0),
    ],
)
def test_import_result_and_report_reject_geometry_mismatch(field, value):
    imported = _import(_apply(POINTS))
    geometry = replace(imported.evidence.current_geometry, **{field: value})
    evidence = replace(imported.evidence, current_geometry=geometry)

    with pytest.raises(OrientationError, match="does not match"):
        OrientationImportResult("imported", imported.source, evidence, imported.membrane)
    with pytest.raises(ReportError, match="does not match"):
        build_report(
            selection="test",
            zmin=-15,
            zmax=15,
            ligand_selection="",
            cutoff=5,
            total_residues=0,
            flagged_residues=[],
            ligand_neighbours=[],
            warnings=[],
            membrane=imported.membrane,
            orientation_evidence=evidence,
        )


def test_stage4_semantics_reject_nonunit_normal_after_structural_validation(tmp_path):
    report = _stage4_report()
    report["orientation"]["normal"] = [0.5, 0.0, 0.0]
    report["orientation"]["evidence"]["current_geometry"]["normal"] = [0.5, 0.0, 0.0]
    path = tmp_path / "nonunit.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReportError, match="unit length"):
        validate_stage4_report_semantics(report)
    with pytest.raises(ReportError, match="unit length"):
        validate_report(report)
    with pytest.raises(ReportError, match="unit length"):
        validate_reports(SCHEMA_1_3, [path])


def test_stage4_semantics_reject_nonunit_source_normal():
    report = _stage4_report()
    report["orientation"]["evidence"]["source_geometry"]["normal"] = [0.5, 0.0, 0.0]

    with pytest.raises(ReportError, match="unit length"):
        validate_stage4_report_semantics(report)


def test_stage4_semantics_accept_valid_nonaxis_current_normal():
    report = _stage4_report()
    report["orientation"]["normal"] = [0.0, 0.6, 0.8]
    report["orientation"]["evidence"]["current_geometry"]["normal"] = [0.0, 0.6, 0.8]

    validate_stage4_report_semantics(report)


def test_stage4_semantics_reject_asymmetric_source_offsets():
    report = _stage4_report()
    report["orientation"]["evidence"]["source_geometry"]["lower_offset"] = -14.0

    with pytest.raises(ReportError, match="offsets must be symmetric"):
        validate_stage4_report_semantics(report)


def test_stage4_semantics_reject_current_and_resolved_geometry_disagreement():
    report = _stage4_report()
    report["orientation"]["evidence"]["current_geometry"]["center"][0] = 0.01

    with pytest.raises(ReportError, match="current geometry center"):
        validate_stage4_report_semantics(report)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_stage4_semantics_reject_nonfinite_normal_components(value):
    report = _stage4_report()
    report["orientation"]["normal"][0] = value
    report["orientation"]["evidence"]["current_geometry"]["normal"][0] = value

    with pytest.raises(ReportError, match="finite number"):
        validate_stage4_report_semantics(report)


def test_import_result_requires_matching_nonnull_source():
    imported = _import(_apply(POINTS))

    with pytest.raises(OrientationError, match="requires source"):
        OrientationImportResult("imported", None, imported.evidence, imported.membrane)
    mismatched_source = replace(imported.source, record_id="other")
    with pytest.raises(OrientationError, match="source must match"):
        OrientationImportResult("imported", mismatched_source, imported.evidence, imported.membrane)


def test_nonimported_result_rejects_resolved_orientation_evidence():
    imported = _import(_apply(POINTS))

    with pytest.raises(OrientationError, match="cannot contain resolved"):
        OrientationImportResult("rejected", imported.source, imported.evidence)
