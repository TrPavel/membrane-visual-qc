"""Offline, research-only verification of PDBTM coordinate semantics.

This helper deliberately has no network, PyMOL, Qt, fitting, or subprocess code. It parses only
the JSON and legacy-PDB subsets needed by the Stage 4 source-semantics preflight.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True, order=True)
class AtomIdentity:
    """Canonical identity after deterministic alternate-location resolution."""

    chain: str
    residue_number: str
    insertion_code: str
    residue_name: str
    atom_name: str
    resolved_altloc: str


@dataclass(frozen=True)
class PdbAtom:
    identity: AtomIdentity
    coordinates: tuple[float, float, float]
    occupancy: float


@dataclass(frozen=True)
class PdbData:
    atoms: dict[AtomIdentity, PdbAtom]
    coordinate_decimal_places: int
    atom_records: int
    hetatm_records: int
    excluded_altloc_records: int
    chains: tuple[str, ...]
    models: tuple[int, ...]


@dataclass(frozen=True)
class AffineTransform:
    rotation: tuple[tuple[float, float, float], ...]
    translation: tuple[float, float, float]
    rotation_rounding: tuple[tuple[float, float, float], ...]
    translation_rounding: tuple[float, float, float]


def _open_text(path: Path) -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="ascii", errors="strict")
    return path.open("r", encoding="ascii", errors="strict")


def _decimal_places(token: str) -> int:
    token = token.strip().lower()
    if "e" in token:
        mantissa, exponent = token.split("e", 1)
        places = len(mantissa.partition(".")[2]) - int(exponent)
        return max(0, places)
    return len(token.partition(".")[2])


def parse_pdb(path: Path, *, model: int = 1, include_hetatm: bool = False) -> PdbData:
    """Parse and altloc-resolve one explicit legacy-PDB model."""

    candidates: dict[tuple[str, str, str, str, str], list[PdbAtom]] = {}
    coordinate_places: list[int] = []
    atom_records = 0
    hetatm_records = 0
    observed_models: list[int] = []
    active_model = 1
    has_models = False

    with _open_text(path) as handle:
        for line in handle:
            if line.startswith("MODEL "):
                has_models = True
                active_model = int(line[10:14])
                observed_models.append(active_model)
                continue
            if line.startswith("ENDMDL"):
                active_model = -1
                continue
            record = line[:6]
            if record not in {"ATOM  ", "HETATM"}:
                continue
            if has_models and active_model != model:
                continue
            if record == "HETATM":
                hetatm_records += 1
                if not include_hetatm:
                    continue
            else:
                atom_records += 1

            xyz_tokens = (line[30:38], line[38:46], line[46:54])
            coordinate_places.extend(_decimal_places(token) for token in xyz_tokens)
            altloc = line[16:17].strip()
            identity = AtomIdentity(
                chain=line[21:22].strip(),
                residue_number=line[22:26].strip(),
                insertion_code=line[26:27].strip(),
                residue_name=line[17:20].strip(),
                atom_name=line[12:16].strip(),
                resolved_altloc=altloc,
            )
            atom = PdbAtom(
                identity=identity,
                coordinates=tuple(float(token) for token in xyz_tokens),
                occupancy=float(line[54:60].strip() or 0.0),
            )
            base = (
                identity.chain,
                identity.residue_number,
                identity.insertion_code,
                identity.residue_name,
                identity.atom_name,
            )
            candidates.setdefault(base, []).append(atom)

    if has_models and model not in observed_models:
        raise ValueError(f"model {model} is absent from {path}")
    if not candidates:
        raise ValueError(f"no selected atoms in {path}")

    atoms: dict[AtomIdentity, PdbAtom] = {}
    excluded_altloc_records = 0
    for alternatives in candidates.values():
        selected = min(
            alternatives,
            key=lambda atom: (
                atom.identity.resolved_altloc != "",
                -atom.occupancy,
                atom.identity.resolved_altloc,
            ),
        )
        atoms[selected.identity] = selected
        excluded_altloc_records += len(alternatives) - 1

    return PdbData(
        atoms=atoms,
        coordinate_decimal_places=min(coordinate_places),
        atom_records=atom_records,
        hetatm_records=hetatm_records,
        excluded_altloc_records=excluded_altloc_records,
        chains=tuple(sorted({identity.chain for identity in atoms})),
        models=tuple(observed_models) if observed_models else (1,),
    )


def _rounding_error(value: Decimal, *, integer_fallback_places: int) -> float:
    decimal_places = max(0, -value.as_tuple().exponent)
    if decimal_places == 0:
        decimal_places = integer_fallback_places
    return 0.5 * 10.0 ** (-decimal_places)


def load_pdbtm_json(path: Path) -> tuple[dict[str, object], AffineTransform]:
    data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
    matrix = data["additional_entry_annotations"]["membrane"]["transformation_matrix"]
    rows = tuple(matrix[name] for name in ("rowx", "rowy", "rowz"))
    rotation_values = tuple(tuple(row[name] for name in ("x", "y", "z")) for row in rows)
    translation_values = tuple(row["t"] for row in rows)
    rotation_places = max(
        (max(0, -value.as_tuple().exponent) for row in rotation_values for value in row),
        default=8,
    )
    translation_places = max(
        (max(0, -value.as_tuple().exponent) for value in translation_values), default=8
    )
    transform = AffineTransform(
        rotation=tuple(tuple(float(value) for value in row) for row in rotation_values),
        translation=tuple(float(value) for value in translation_values),
        rotation_rounding=tuple(
            tuple(_rounding_error(value, integer_fallback_places=rotation_places) for value in row)
            for row in rotation_values
        ),
        translation_rounding=tuple(
            _rounding_error(value, integer_fallback_places=translation_places)
            for value in translation_values
        ),
    )
    return data, transform


def transform_point(
    transform: AffineTransform, point: tuple[float, float, float]
) -> tuple[float, float, float]:
    return tuple(
        sum(transform.rotation[i][j] * point[j] for j in range(3)) + transform.translation[i]
        for i in range(3)
    )


def transpose_convention_point(
    transform: AffineTransform, point: tuple[float, float, float]
) -> tuple[float, float, float]:
    return tuple(
        sum(point[j] * transform.rotation[j][i] for j in range(3)) + transform.translation[i]
        for i in range(3)
    )


def pretranslation_convention_point(
    transform: AffineTransform, point: tuple[float, float, float]
) -> tuple[float, float, float]:
    shifted = tuple(point[i] + transform.translation[i] for i in range(3))
    return tuple(sum(transform.rotation[i][j] * shifted[j] for j in range(3)) for i in range(3))


def invert_transform(transform: AffineTransform) -> AffineTransform:
    r = transform.rotation
    determinant = matrix_determinant(r)
    if abs(determinant) < 1e-12:
        raise ValueError("singular rotation matrix")
    inverse = (
        (
            (r[1][1] * r[2][2] - r[1][2] * r[2][1]) / determinant,
            (r[0][2] * r[2][1] - r[0][1] * r[2][2]) / determinant,
            (r[0][1] * r[1][2] - r[0][2] * r[1][1]) / determinant,
        ),
        (
            (r[1][2] * r[2][0] - r[1][0] * r[2][2]) / determinant,
            (r[0][0] * r[2][2] - r[0][2] * r[2][0]) / determinant,
            (r[0][2] * r[1][0] - r[0][0] * r[1][2]) / determinant,
        ),
        (
            (r[1][0] * r[2][1] - r[1][1] * r[2][0]) / determinant,
            (r[0][1] * r[2][0] - r[0][0] * r[2][1]) / determinant,
            (r[0][0] * r[1][1] - r[0][1] * r[1][0]) / determinant,
        ),
    )
    inverse_translation = tuple(
        -sum(inverse[i][j] * transform.translation[j] for j in range(3)) for i in range(3)
    )
    zeros = ((0.0, 0.0, 0.0),) * 3
    return AffineTransform(inverse, inverse_translation, zeros, (0.0, 0.0, 0.0))


def matrix_determinant(matrix: tuple[tuple[float, float, float], ...]) -> float:
    a, b, c = matrix
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def matrix_diagnostics(transform: AffineTransform) -> dict[str, object]:
    r = transform.rotation
    product = tuple(
        tuple(sum(r[i][k] * r[j][k] for k in range(3)) for j in range(3)) for i in range(3)
    )
    orthonormality_error = max(
        abs(product[i][j] - (1.0 if i == j else 0.0)) for i in range(3) for j in range(3)
    )
    inverse = invert_transform(transform)
    composition_error = max(
        math.dist(transform_point(inverse, transform_point(transform, basis)), basis)
        for basis in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    )
    return {
        "determinant": matrix_determinant(r),
        "orthonormality_max_abs_error": orthonormality_error,
        "rotation": [list(row) for row in r],
        "translation": list(transform.translation),
        "inverse_rotation": [list(row) for row in inverse.rotation],
        "inverse_translation": list(inverse.translation),
        "forward_inverse_composition_max_error": composition_error,
    }


def residual_metrics(
    source: PdbData,
    target: PdbData,
    point_transform,
) -> dict[str, object]:
    matched = sorted(source.atoms.keys() & target.atoms.keys())
    if not matched:
        raise ValueError("no canonical atom intersection")
    squared_sum = 0.0
    axis_squared = [0.0, 0.0, 0.0]
    axis_max = [0.0, 0.0, 0.0]
    maximum = 0.0
    for identity in matched:
        predicted = point_transform(source.atoms[identity].coordinates)
        observed = target.atoms[identity].coordinates
        residual = tuple(predicted[i] - observed[i] for i in range(3))
        distance_squared = sum(value * value for value in residual)
        squared_sum += distance_squared
        maximum = max(maximum, math.sqrt(distance_squared))
        for axis, value in enumerate(residual):
            axis_squared[axis] += value * value
            axis_max[axis] = max(axis_max[axis], abs(value))
    count = len(matched)
    residues = {
        (key.chain, key.residue_number, key.insertion_code, key.residue_name) for key in matched
    }
    return {
        "matched_atom_count": count,
        "matched_residue_count": len(residues),
        "source_only_atom_count": len(source.atoms.keys() - target.atoms.keys()),
        "target_only_atom_count": len(target.atoms.keys() - source.atoms.keys()),
        "rmsd": math.sqrt(squared_sum / count),
        "maximum_residual": maximum,
        "axis_rmsd": [math.sqrt(value / count) for value in axis_squared],
        "axis_maximum_absolute_residual": axis_max,
        "matched_identities": matched,
    }


def spatial_distribution(
    atoms: dict[AtomIdentity, PdbAtom], identities: list[AtomIdentity]
) -> dict[str, float]:
    points = [atoms[identity].coordinates for identity in identities]
    if len(points) < 2:
        raise ValueError("at least two points are required")
    farthest = (0, 1)
    maximum_squared = -1.0
    for i, first in enumerate(points[:-1]):
        for j in range(i + 1, len(points)):
            second = points[j]
            distance_squared = sum((first[k] - second[k]) ** 2 for k in range(3))
            if distance_squared > maximum_squared:
                maximum_squared = distance_squared
                farthest = (i, j)
    start, end = (points[index] for index in farthest)
    direction = tuple(end[i] - start[i] for i in range(3))
    direction_squared = sum(value * value for value in direction)
    maximum_line_distance = 0.0
    for point in points:
        relative = tuple(point[i] - start[i] for i in range(3))
        projection = sum(relative[i] * direction[i] for i in range(3)) / direction_squared
        closest = tuple(start[i] + projection * direction[i] for i in range(3))
        maximum_line_distance = max(maximum_line_distance, math.dist(point, closest))
    return {
        "maximum_pairwise_separation": math.sqrt(maximum_squared),
        "maximum_distance_from_farthest_pair_line": maximum_line_distance,
    }


def derive_tolerances(
    transform: AffineTransform, source: PdbData, transformed: PdbData
) -> dict[str, object]:
    source_rounding = 0.5 * 10.0 ** (-source.coordinate_decimal_places)
    transformed_rounding = 0.5 * 10.0 ** (-transformed.coordinate_decimal_places)
    coordinate_magnitudes = [
        max(abs(atom.coordinates[axis]) for atom in source.atoms.values()) + source_rounding
        for axis in range(3)
    ]
    forward_axis_bounds = []
    for axis in range(3):
        bound = transformed_rounding + transform.translation_rounding[axis]
        for source_axis in range(3):
            rotation = abs(transform.rotation[axis][source_axis])
            matrix_rounding = transform.rotation_rounding[axis][source_axis]
            bound += rotation * source_rounding
            bound += coordinate_magnitudes[source_axis] * matrix_rounding
            bound += source_rounding * matrix_rounding
        forward_axis_bounds.append(bound)
    forward_maximum = math.sqrt(sum(value * value for value in forward_axis_bounds))

    inverse = invert_transform(transform)
    inverse_infinity_norm = max(sum(abs(value) for value in row) for row in inverse.rotation)
    matrix_error_infinity = max(sum(row) for row in transform.rotation_rounding)
    translation_error_infinity = max(transform.translation_rounding)
    source_magnitude_infinity = max(coordinate_magnitudes)
    inverse_axis_bound = source_rounding + inverse_infinity_norm * (
        matrix_error_infinity * source_magnitude_infinity
        + translation_error_infinity
        + transformed_rounding
    )
    inverse_maximum = math.sqrt(3.0) * inverse_axis_bound
    identity_maximum = math.sqrt(3.0) * 2.0 * transformed_rounding

    def ceiling_milliangstrom(value: float) -> float:
        return math.ceil(value * 1000.0) / 1000.0

    return {
        "formula": {
            "forward_axis": "eps_y + eps_t_i + sum_j(|R_ij| eps_x + |x_j| eps_R_ij + eps_x eps_R_ij)",
            "inverse_infinity": "eps_x + ||R^-1||_inf (||eps_R||_inf ||x||_inf + eps_t + eps_y)",
            "identity": "sqrt(3) * (eps_current + eps_companion)",
        },
        "source_coordinate_rounding": source_rounding,
        "transformed_coordinate_rounding": transformed_rounding,
        "rotation_rounding": [list(row) for row in transform.rotation_rounding],
        "translation_rounding": list(transform.translation_rounding),
        "coordinate_magnitude_by_axis": coordinate_magnitudes,
        "identity_theoretical_maximum_residual": identity_maximum,
        "identity_proposed_rmsd_limit": ceiling_milliangstrom(identity_maximum),
        "identity_proposed_maximum_residual_limit": ceiling_milliangstrom(identity_maximum),
        "forward_theoretical_axis_bounds": forward_axis_bounds,
        "forward_theoretical_maximum_residual": forward_maximum,
        "forward_proposed_rmsd_limit": ceiling_milliangstrom(forward_maximum),
        "forward_proposed_maximum_residual_limit": ceiling_milliangstrom(forward_maximum),
        "inverse_theoretical_maximum_residual": inverse_maximum,
        "inverse_proposed_rmsd_limit": ceiling_milliangstrom(inverse_maximum),
        "inverse_proposed_maximum_residual_limit": ceiling_milliangstrom(inverse_maximum),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pdb_summary(data: PdbData) -> dict[str, object]:
    return {
        "selected_atom_count": len(data.atoms),
        "atom_records": data.atom_records,
        "hetatm_records": data.hetatm_records,
        "excluded_altloc_records": data.excluded_altloc_records,
        "chains": list(data.chains),
        "models": list(data.models),
        "coordinate_decimal_places": data.coordinate_decimal_places,
    }


def _decimal_places_from_rounding(rounding: float) -> int:
    return round(-math.log10(2.0 * rounding))


def analyze_pair(
    json_path: Path,
    transformed_path: Path,
    current_path: Path,
    *,
    assembly_path: Path | None = None,
    model: int = 1,
) -> dict[str, object]:
    metadata, transform = load_pdbtm_json(json_path)
    transformed = parse_pdb(transformed_path, model=model)
    current = parse_pdb(current_path, model=model)
    transformed_all = parse_pdb(transformed_path, model=model, include_hetatm=True)
    current_all = parse_pdb(current_path, model=model, include_hetatm=True)
    forward = residual_metrics(
        current, transformed, lambda point: transform_point(transform, point)
    )
    inverse_transform = invert_transform(transform)
    inverse = residual_metrics(
        transformed, current, lambda point: transform_point(inverse_transform, point)
    )
    transpose = residual_metrics(
        current, transformed, lambda point: transpose_convention_point(transform, point)
    )
    pretranslation = residual_metrics(
        current, transformed, lambda point: pretranslation_convention_point(transform, point)
    )
    inverse_wrong_direction = residual_metrics(
        current, transformed, lambda point: transform_point(inverse_transform, point)
    )
    identity = residual_metrics(current, transformed, lambda point: point)
    all_record_forward = residual_metrics(
        current_all, transformed_all, lambda point: transform_point(transform, point)
    )
    distribution = spatial_distribution(current.atoms, forward.pop("matched_identities"))
    inverse.pop("matched_identities")
    transpose.pop("matched_identities")
    pretranslation.pop("matched_identities")
    inverse_wrong_direction.pop("matched_identities")
    identity.pop("matched_identities")
    all_record_forward.pop("matched_identities")
    membrane = metadata["additional_entry_annotations"]["membrane"]
    normal = membrane["normal"]
    normal_vector = [float(normal[axis]) for axis in ("x", "y", "z")]
    chain_mapping = metadata["additional_entry_annotations"].get("ent_cif_mapping_results", {})
    result = {
        "pdb_id": metadata["pdb_id"],
        "data_resource": metadata["data_resource"],
        "resource_version": str(metadata["resource_version"]).strip(),
        "software_version": metadata["software_version"],
        "tm_type": metadata["additional_entry_annotations"].get("tm_type"),
        "payloads": {
            "json": {"byte_size": json_path.stat().st_size, "sha256": sha256_file(json_path)},
            "transformed_pdb": {
                "byte_size": transformed_path.stat().st_size,
                "sha256": sha256_file(transformed_path),
            },
            "current_pdb": {
                "byte_size": current_path.stat().st_size,
                "sha256": sha256_file(current_path),
            },
        },
        "coordinate_files": {
            "transformed": _pdb_summary(transformed),
            "current": _pdb_summary(current),
        },
        "chain_namespace": {
            "json_chain_labels": [chain["chain_label"] for chain in metadata["chains"]],
            "legacy_pdb_chains": list(current.chains),
            "provider_mapping": chain_mapping,
        },
        "matrix_convention": {
            "shape": "3x4",
            "storage": "rowx/rowy/rowz; x/y/z rotation then t translation",
            "multiplication": "column coordinate; p_transformed = R p_original + t",
            "units": "angstrom for coordinates and translation; dimensionless rotation",
        },
        "matrix_diagnostics": matrix_diagnostics(transform),
        "direct_residuals": {
            "documented_forward_current_to_transformed": forward,
            "documented_inverse_transformed_to_current": inverse,
            "identity_current_to_transformed": identity,
            "transpose_rotation_current_to_transformed": transpose,
            "pretranslation_current_to_transformed": pretranslation,
            "inverse_wrong_direction_current_to_transformed": inverse_wrong_direction,
            "supplemental_atom_and_hetatm_forward": all_record_forward,
        },
        "spatial_distribution": distribution,
        "minimum_applicability_checks": {
            "at_least_12_atoms": forward["matched_atom_count"] >= 12,
            "at_least_3_residues": forward["matched_residue_count"] >= 3,
            "pairwise_separation_at_least_10": distribution["maximum_pairwise_separation"] >= 10,
            "off_axis_distance_at_least_2": distribution["maximum_distance_from_farthest_pair_line"]
            >= 2,
        },
        "membrane": {
            "raw_normal_vector": normal_vector,
            "half_thickness": math.sqrt(sum(value * value for value in normal_vector)),
            "transformed_centre": [0.0, 0.0, 0.0],
            "transformed_normal_direction": [0.0, 0.0, 1.0],
            "radius": float(membrane["radius"]),
        },
        "tolerance_derivation": derive_tolerances(transform, current, transformed),
        "observed_precision": {
            "current_coordinate_decimal_places": current.coordinate_decimal_places,
            "transformed_coordinate_decimal_places": transformed.coordinate_decimal_places,
            "rotation_decimal_places": [
                [_decimal_places_from_rounding(value) for value in row]
                for row in transform.rotation_rounding
            ],
            "translation_decimal_places": [
                _decimal_places_from_rounding(value) for value in transform.translation_rounding
            ],
            "integer_values_use_sibling_field_precision": True,
        },
        "altloc_policy": "blank preferred; otherwise highest occupancy, then lexical altloc",
        "atom_exclusions": "ATOM records only; HETATM excluded from applicability matching",
    }
    if assembly_path is not None:
        assembly = parse_pdb(assembly_path, model=model)
        assembly_identity = residual_metrics(current, assembly, lambda point: point)
        assembly_identity.pop("matched_identities")
        result["payloads"]["assembly_pdb"] = {
            "byte_size": assembly_path.stat().st_size,
            "sha256": sha256_file(assembly_path),
        }
        result["coordinate_files"]["assembly"] = _pdb_summary(assembly)
        result["assembly_identity_to_current"] = assembly_identity
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdbtm-json", type=Path, required=True)
    parser.add_argument("--transformed-pdb", type=Path, required=True)
    parser.add_argument("--current-pdb", type=Path, required=True)
    parser.add_argument("--assembly-pdb", type=Path)
    parser.add_argument("--model", type=int, default=1)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze_pair(
        args.pdbtm_json,
        args.transformed_pdb,
        args.current_pdb,
        assembly_path=args.assembly_pdb,
        model=args.model,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the script smoke command
    raise SystemExit(main())
