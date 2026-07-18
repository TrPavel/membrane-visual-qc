import gzip
import json

import pytest

from scripts.research.pdbtm_semantics_preflight import (
    AffineTransform,
    analyze_pair,
    derive_tolerances,
    invert_transform,
    load_pdbtm_json,
    main,
    matrix_diagnostics,
    parse_pdb,
    pretranslation_convention_point,
    residual_metrics,
    sha256_file,
    spatial_distribution,
    transform_point,
    transpose_convention_point,
)


IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
ZEROS = ((0.0, 0.0, 0.0),) * 3


def _pdb_line(
    serial,
    name,
    residue,
    number,
    xyz,
    *,
    chain="A",
    altloc="",
    occupancy=1.0,
    record="ATOM",
):
    return (
        f"{record:<6}{serial:>5} {name:^4}{altloc:1}{residue:>3} {chain:1}{number:>4}    "
        f"{xyz[0]:>8.3f}{xyz[1]:>8.3f}{xyz[2]:>8.3f}{occupancy:>6.2f}{20.0:>6.2f}"
        f"          {name[0]:>2}\n"
    )


def _write_pdb(path, points, *, transformed=None, gzip_file=False):
    lines = []
    for index, point in enumerate(points, 1):
        if transformed is not None:
            point = transform_point(transformed, point)
        lines.append(_pdb_line(index, "CA", "ALA", index, point))
    text = "".join(lines) + "END\n"
    if gzip_file:
        with gzip.open(path, "wt", encoding="ascii") as handle:
            handle.write(text)
    else:
        path.write_text(text, encoding="ascii")


def _write_json(path, transform):
    rows = []
    for index, name in enumerate(("rowx", "rowy", "rowz")):
        rows.append(
            (
                name,
                {
                    "x": transform.rotation[index][0],
                    "y": transform.rotation[index][1],
                    "z": transform.rotation[index][2],
                    "t": transform.translation[index],
                },
            )
        )
    payload = {
        "data_resource": "PDBTM",
        "resource_version": "synthetic-1",
        "software_version": "test",
        "pdb_id": "test",
        "chains": [{"chain_label": "A"}],
        "additional_entry_annotations": {
            "tm_type": "Tm_Alpha",
            "membrane": {
                "normal": {"x": 0.0, "y": 0.0, "z": 10.0},
                "radius": 20.0,
                "transformation_matrix": dict(rows),
            },
            "ent_cif_mapping_results": {"ent_cif_chain_map": {"A": ["A"]}},
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def rigid_transform():
    return AffineTransform(
        rotation=((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        translation=(10.0, -5.0, 3.0),
        rotation_rounding=ZEROS,
        translation_rounding=(0.0, 0.0, 0.0),
    )


def test_matrix_forward_inverse_and_diagnostics(rigid_transform):
    point = (2.0, 4.0, 6.0)
    transformed = transform_point(rigid_transform, point)
    assert transformed == pytest.approx((6.0, -3.0, 9.0))
    assert transform_point(invert_transform(rigid_transform), transformed) == pytest.approx(point)
    diagnostics = matrix_diagnostics(rigid_transform)
    assert diagnostics["determinant"] == pytest.approx(1.0)
    assert diagnostics["orthonormality_max_abs_error"] == pytest.approx(0.0)
    assert diagnostics["forward_inverse_composition_max_error"] < 1e-12
    assert transpose_convention_point(rigid_transform, point) != pytest.approx(transformed)
    assert pretranslation_convention_point(rigid_transform, point) != pytest.approx(transformed)


def test_singular_matrix_is_rejected():
    transform = AffineTransform(((0.0, 0.0, 0.0),) * 3, (0.0, 0.0, 0.0), ZEROS, (0, 0, 0))
    with pytest.raises(ValueError, match="singular"):
        invert_transform(transform)


def test_pdb_parser_resolves_altloc_and_filters_hetatm(tmp_path):
    path = tmp_path / "atoms.pdb"
    path.write_text(
        "MODEL        1\n"
        + _pdb_line(1, "CA", "ALA", 1, (0, 0, 0), altloc="B", occupancy=0.6)
        + _pdb_line(2, "CA", "ALA", 1, (1, 0, 0), altloc="A", occupancy=0.6)
        + _pdb_line(3, "N", "ALA", 1, (0, 1, 0))
        + _pdb_line(4, "O", "HOH", 2, (0, 0, 1), record="HETATM")
        + "ENDMDL\nEND\n",
        encoding="ascii",
    )
    parsed = parse_pdb(path)
    assert len(parsed.atoms) == 2
    assert parsed.excluded_altloc_records == 1
    assert parsed.hetatm_records == 1
    assert {key.resolved_altloc for key in parsed.atoms} == {"", "A"}
    assert len(parse_pdb(path, include_hetatm=True).atoms) == 3
    with pytest.raises(ValueError, match="model 2"):
        parse_pdb(path, model=2)


def test_pdb_parser_supports_gzip_and_rejects_empty(tmp_path):
    gz_path = tmp_path / "atoms.pdb.gz"
    _write_pdb(gz_path, [(0, 0, 0), (1, 0, 0)], gzip_file=True)
    assert len(parse_pdb(gz_path).atoms) == 2
    empty = tmp_path / "empty.pdb"
    empty.write_text("END\n", encoding="ascii")
    with pytest.raises(ValueError, match="no selected atoms"):
        parse_pdb(empty)


def test_residual_and_spatial_metrics(tmp_path, rigid_transform):
    points = [(0, 0, 0), (12, 0, 0), (0, 3, 0), (0, 0, 4)]
    source_path = tmp_path / "source.pdb"
    target_path = tmp_path / "target.pdb"
    _write_pdb(source_path, points)
    _write_pdb(target_path, points, transformed=rigid_transform)
    source = parse_pdb(source_path)
    target = parse_pdb(target_path)
    metrics = residual_metrics(source, target, lambda p: transform_point(rigid_transform, p))
    assert metrics["matched_atom_count"] == 4
    assert metrics["matched_residue_count"] == 4
    assert metrics["rmsd"] == pytest.approx(0.0)
    distribution = spatial_distribution(source.atoms, metrics["matched_identities"])
    assert distribution["maximum_pairwise_separation"] > 12
    assert distribution["maximum_distance_from_farthest_pair_line"] > 2
    disjoint_path = tmp_path / "disjoint.pdb"
    disjoint_path.write_text(_pdb_line(1, "CA", "ALA", 99, (0, 0, 0), chain="B"), encoding="ascii")
    with pytest.raises(ValueError, match="no canonical"):
        residual_metrics(source, parse_pdb(disjoint_path), lambda point: point)
    one = {next(iter(source.atoms)): next(iter(source.atoms.values()))}
    with pytest.raises(ValueError, match="at least two"):
        spatial_distribution(one, list(one))


def test_load_json_precision_and_tolerance_derivation(tmp_path):
    transform = AffineTransform(
        rotation=((0.99999999, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        translation=(1.12345678, 0.0, 0.0),
        rotation_rounding=ZEROS,
        translation_rounding=(0.0, 0.0, 0.0),
    )
    json_path = tmp_path / "record.json"
    _write_json(json_path, transform)
    _, loaded = load_pdbtm_json(json_path)
    assert loaded.rotation_rounding[0][0] == pytest.approx(0.5e-8)
    assert loaded.translation_rounding[0] == pytest.approx(0.5e-8)
    source_path = tmp_path / "source.pdb"
    target_path = tmp_path / "target.pdb"
    _write_pdb(source_path, [(0, 0, 0), (10, 2, 3)])
    _write_pdb(target_path, [(0, 0, 0), (10, 2, 3)], transformed=loaded)
    tolerances = derive_tolerances(loaded, parse_pdb(source_path), parse_pdb(target_path))
    assert tolerances["identity_proposed_maximum_residual_limit"] == 0.002
    assert tolerances["forward_theoretical_maximum_residual"] > 0
    assert tolerances["inverse_theoretical_maximum_residual"] > 0


def test_analyze_pair_and_cli(tmp_path, rigid_transform, capsys):
    points = [(0, 0, 0), (12, 0, 0), (0, 3, 0)] + [
        (float(i), float(i % 4), float(i % 3)) for i in range(3, 15)
    ]
    json_path = tmp_path / "record.json"
    current_path = tmp_path / "current.pdb"
    transformed_path = tmp_path / "transformed.pdb"
    assembly_path = tmp_path / "assembly.pdb.gz"
    output_path = tmp_path / "result.json"
    _write_json(json_path, rigid_transform)
    _write_pdb(current_path, points)
    _write_pdb(transformed_path, points, transformed=rigid_transform)
    _write_pdb(assembly_path, points, gzip_file=True)
    result = analyze_pair(json_path, transformed_path, current_path, assembly_path=assembly_path)
    assert result["direct_residuals"]["documented_forward_current_to_transformed"][
        "maximum_residual"
    ] == pytest.approx(0.0)
    assert result["minimum_applicability_checks"]["at_least_12_atoms"]
    assert result["assembly_identity_to_current"]["maximum_residual"] == pytest.approx(0.0)
    assert result["direct_residuals"]["supplemental_atom_and_hetatm_forward"][
        "matched_atom_count"
    ] == len(points)
    assert result["observed_precision"]["current_coordinate_decimal_places"] == 3
    assert sha256_file(json_path) == result["payloads"]["json"]["sha256"]
    assert (
        main(
            [
                "--pdbtm-json",
                str(json_path),
                "--transformed-pdb",
                str(transformed_path),
                "--current-pdb",
                str(current_path),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    assert json.loads(output_path.read_text())["pdb_id"] == "test"
    assert (
        main(
            [
                "--pdbtm-json",
                str(json_path),
                "--transformed-pdb",
                str(transformed_path),
                "--current-pdb",
                str(current_path),
            ]
        )
        == 0
    )
    assert '"pdb_id": "test"' in capsys.readouterr().out
