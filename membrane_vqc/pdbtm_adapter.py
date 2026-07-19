"""Deterministic offline PDBTM API-v1 orientation adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import hashlib
import json
import math
from typing import Protocol

from .constants import DEFAULT_INTERFACE_WIDTH
from .errors import OrientationError
from .orientation import PlanarMembrane
from .orientation_sources import (
    CoordinateMapping,
    ImportMessage,
    OrientationEvidenceV1,
    OrientationImportResult,
    OrientationPayload,
    OrientationPayloadSet,
    PayloadDigest,
    PlanarGeometryEvidence,
    SourceIdentity,
    StructureContext,
    StructureScope,
)

MAX_PAYLOAD_BYTES = 5 * 1024 * 1024
MAX_JSON_DEPTH = 32
MAX_LINE_BYTES = 4096
MAX_RECORDS = 250_000
MAX_CHAINS = 512
MAX_MEMBRANES = 8
MAX_STRING_CODEPOINTS = 4096
MAX_COORDINATE = 1_000_000.0
MIN_NORMAL_NORM = 1e-12
NORMAL_XY_NOISE_LIMIT = 1e-7
RUNTIME_IDENTITY_LIMIT = 0.002
RUNTIME_INVERSE_LIMIT = 0.003
RIGID_TOLERANCE = 1e-5
FINGERPRINT_ALGORITHM = "mvqc_atom_identity_coordinates_sha256"
FINGERPRINT_VERSION = "1"
ADAPTER_NAME = "pdbtm_api_v1_offline"
ADAPTER_VERSION = "1"


class OrientationAdapter(Protocol):
    source_name: str
    adapter_name: str
    adapter_version: str
    supported_media_types: tuple[str, ...]
    supported_format_profiles: tuple[str, ...]

    def can_parse(
        self, payloads: OrientationPayloadSet, metadata: Mapping[str, object]
    ) -> bool: ...

    def parse(
        self,
        payloads: OrientationPayloadSet,
        *,
        structure_context: StructureContext,
        metadata: Mapping[str, object],
    ) -> OrientationImportResult: ...


@dataclass(frozen=True, order=True, slots=True)
class AtomIdentity:
    chain: str
    residue_number: str
    insertion_code: str
    residue_name: str
    atom_name: str
    resolved_altloc: str


@dataclass(frozen=True, slots=True)
class _Atom:
    identity: AtomIdentity
    coordinates: tuple[float, float, float]
    occupancy: float
    altloc: str


@dataclass(frozen=True, slots=True)
class _PdbData:
    atoms: Mapping[AtomIdentity, _Atom]
    chains: tuple[str, ...]
    coordinate_decimal_places: int
    structure_id: str | None
    model: int


@dataclass(frozen=True, slots=True)
class _Transform:
    rows3: tuple[tuple[float, float, float, float], ...]
    matrix4: tuple[tuple[float, float, float, float], ...]
    inverse4: tuple[tuple[float, float, float, float], ...]
    determinant: float
    orthonormality_error: float
    precision: Mapping[str, object]


class _AdapterFailure(Exception):
    def __init__(self, status: str, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.issue = ImportMessage(code, message)


def _failure(status: str, code: str, message: str) -> None:
    raise _AdapterFailure(status, code, message)


def _digest(payload: OrientationPayload) -> PayloadDigest:
    return PayloadDigest(
        role=payload.role,
        sha256=hashlib.sha256(payload.content).hexdigest(),
        byte_size=len(payload.content),
        source=payload.source_url,
        media_type=payload.media_type,
        retrieved_at=payload.retrieved_at,
        retrieval_verified=False,
    )


def _check_payload(payload: OrientationPayload) -> None:
    data = payload.content
    if len(data) > MAX_PAYLOAD_BYTES:
        _failure("rejected", "PAYLOAD_TOO_LARGE", f"{payload.role} exceeds the 5 MiB limit.")
    if data.startswith((b"PK\x03\x04", b"\x1f\x8b", b"ustar")) or data[257:262] == b"ustar":
        _failure(
            "rejected", "CONTAINER_NOT_ALLOWED", f"{payload.role} must be an uncompressed payload."
        )
    if b"\x00" in data:
        _failure("rejected", "NUL_BYTE", f"{payload.role} contains a NUL byte.")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _failure("rejected", "DUPLICATE_JSON_KEY", f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


def _json_depth_and_strings(value: object, depth: int = 1) -> None:
    if depth > MAX_JSON_DEPTH:
        _failure("rejected", "JSON_DEPTH_LIMIT", "JSON nesting exceeds 32 levels.")
    if isinstance(value, str) and len(value) > MAX_STRING_CODEPOINTS:
        _failure("rejected", "STRING_TOO_LONG", "JSON scalar string exceeds 4096 code points.")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if len(key) > MAX_STRING_CODEPOINTS:
                _failure("rejected", "STRING_TOO_LONG", "JSON key exceeds 4096 code points.")
            _json_depth_and_strings(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _json_depth_and_strings(item, depth + 1)


def _load_json(payload: OrientationPayload) -> dict[str, object]:
    _check_payload(payload)
    try:
        text = payload.content.decode("utf-8")
    except UnicodeDecodeError as exc:
        _failure("rejected", "INVALID_ENCODING", "PDBTM JSON must be valid UTF-8.")
        raise AssertionError from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_float=Decimal,
            parse_int=Decimal,
            parse_constant=lambda token: _failure(
                "rejected",
                "NONFINITE_JSON_NUMBER",
                f"Non-finite JSON number {token} is not allowed.",
            ),
        )
    except _AdapterFailure:
        raise
    except (json.JSONDecodeError, InvalidOperation) as exc:
        _failure("rejected", "INVALID_JSON", f"Invalid PDBTM JSON: {exc}.")
    if not isinstance(value, dict):
        _failure("unsupported", "UNSUPPORTED_FIELD_STRUCTURE", "PDBTM JSON root must be an object.")
    _json_depth_and_strings(value)
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        _failure("unsupported", "UNSUPPORTED_FIELD_STRUCTURE", f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number) or abs(number) > MAX_COORDINATE:
        _failure(
            "rejected", "INVALID_NUMBER", f"{label} must be finite and within coordinate limits."
        )
    return 0.0 if number == 0 else number


def _decimal_places(value: object) -> int | None:
    if not isinstance(value, Decimal):
        return None
    exponent = value.as_tuple().exponent
    return max(0, -exponent)


def _matrix(metadata: Mapping[str, object]) -> _Transform:
    try:
        annotations = metadata["additional_entry_annotations"]
        membrane = annotations["membrane"]  # type: ignore[index]
        if isinstance(membrane, list):
            if len(membrane) > MAX_MEMBRANES:
                _failure(
                    "rejected",
                    "CANDIDATE_MEMBRANE_LIMIT",
                    "PDBTM payload exceeds eight candidate membrane records.",
                )
            if len(membrane) > 1:
                _failure(
                    "rejected", "MULTIPLE_MEMBRANES", "Multiple membrane records are not supported."
                )
            membrane = membrane[0] if membrane else None
        raw = membrane["transformation_matrix"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        _failure(
            "unsupported",
            "UNSUPPORTED_FIELD_STRUCTURE",
            "Required API-v1 matrix fields are missing.",
        )
        raise AssertionError from exc
    if not isinstance(raw, Mapping) or set(raw) != {"rowx", "rowy", "rowz"}:
        _failure(
            "unsupported",
            "UNSUPPORTED_FIELD_STRUCTURE",
            "Matrix must contain rowx, rowy, and rowz.",
        )
    rows = []
    rotation_places: list[list[int | None]] = []
    translation_places: list[int | None] = []
    for row_name in ("rowx", "rowy", "rowz"):
        row = raw[row_name]
        if not isinstance(row, Mapping) or set(row) != {"x", "y", "z", "t"}:
            _failure(
                "unsupported",
                "UNSUPPORTED_FIELD_STRUCTURE",
                f"{row_name} must contain x, y, z, and t.",
            )
        rows.append(tuple(_number(row[key], f"{row_name}.{key}") for key in ("x", "y", "z", "t")))
        rotation_places.append([_decimal_places(row[key]) for key in ("x", "y", "z")])
        translation_places.append(_decimal_places(row["t"]))
    noninteger_rotation = [p for row in rotation_places for p in row if p]
    noninteger_translation = [p for p in translation_places if p]
    if not noninteger_rotation or max(noninteger_rotation) != 8 or min(noninteger_rotation) < 7:
        _failure(
            "unsupported",
            "PRECISION_OUTSIDE_ENVELOPE",
            "Rotation precision is outside the reviewed 7-8 decimal envelope.",
        )
    if noninteger_translation and (
        min(noninteger_translation) < 7 or max(noninteger_translation) > 8
    ):
        _failure(
            "unsupported",
            "PRECISION_OUTSIDE_ENVELOPE",
            "Translation precision is outside the reviewed 7-8 decimal envelope.",
        )
    rotation = tuple(tuple(row[:3]) for row in rows)
    determinant = _det3(rotation)
    ortho = max(
        abs(sum(rotation[k][i] * rotation[k][j] for k in range(3)) - (1.0 if i == j else 0.0))
        for i in range(3)
        for j in range(3)
    )
    if determinant <= 0 or abs(determinant - 1.0) > RIGID_TOLERANCE or ortho > RIGID_TOLERANCE:
        _failure(
            "unsupported",
            "NON_RIGID_TRANSFORM",
            "Provider transform is not a reviewed rigid rotation.",
        )
    matrix4 = tuple((*row,) for row in rows) + ((0.0, 0.0, 0.0, 1.0),)
    inverse4 = _invert_affine(matrix4)
    composition = max(
        abs(_matmul4(matrix4, inverse4)[i][j] - (1.0 if i == j else 0.0))
        for i in range(4)
        for j in range(4)
    )
    if composition > 1e-8:
        _failure(
            "unsupported",
            "NON_INVERTIBLE_TRANSFORM",
            "Provider transform inverse composition failed.",
        )
    precision = {
        "rotation_decimal_places": [
            [8 if p is None or p == 0 else p for p in row] for row in rotation_places
        ],
        "translation_decimal_places": [8 if p is None or p == 0 else p for p in translation_places],
        "integer_values_use_sibling_field_precision": True,
    }
    return _Transform(tuple(rows), matrix4, inverse4, determinant, ortho, precision)


def _det3(matrix: tuple[tuple[float, float, float], ...]) -> float:
    a, b, c = matrix
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def _invert_affine(
    matrix: tuple[tuple[float, float, float, float], ...],
) -> tuple[tuple[float, float, float, float], ...]:
    r = tuple(tuple(matrix[i][j] for j in range(3)) for i in range(3))
    det = _det3(r)
    if abs(det) < 1e-12:
        _failure("unsupported", "SINGULAR_TRANSFORM", "Provider transform is singular.")
    a, b, c = r
    inv = (
        (
            (b[1] * c[2] - b[2] * c[1]) / det,
            (a[2] * c[1] - a[1] * c[2]) / det,
            (a[1] * b[2] - a[2] * b[1]) / det,
        ),
        (
            (b[2] * c[0] - b[0] * c[2]) / det,
            (a[0] * c[2] - a[2] * c[0]) / det,
            (a[2] * b[0] - a[0] * b[2]) / det,
        ),
        (
            (b[0] * c[1] - b[1] * c[0]) / det,
            (a[1] * c[0] - a[0] * c[1]) / det,
            (a[0] * b[1] - a[1] * b[0]) / det,
        ),
    )
    t = tuple(matrix[i][3] for i in range(3))
    it = tuple(-sum(inv[i][j] * t[j] for j in range(3)) for i in range(3))
    return tuple((*inv[i], it[i]) for i in range(3)) + ((0.0, 0.0, 0.0, 1.0),)


def _matmul4(left, right):
    return tuple(
        tuple(sum(left[i][k] * right[k][j] for k in range(4)) for j in range(4)) for i in range(4)
    )


def _point(matrix, point):
    return tuple(sum(matrix[i][j] * point[j] for j in range(3)) + matrix[i][3] for i in range(3))


def _vector(matrix, vector):
    return tuple(sum(matrix[i][j] * vector[j] for j in range(3)) for i in range(3))


def _parse_pdb(payload: bytes, model: int, role: str) -> _PdbData:
    if len(payload) > MAX_PAYLOAD_BYTES:
        _failure("rejected", "PAYLOAD_TOO_LARGE", f"{role} exceeds the 5 MiB limit.")
    if payload.startswith((b"PK\x03\x04", b"\x1f\x8b")) or payload[257:262] == b"ustar":
        _failure("rejected", "CONTAINER_NOT_ALLOWED", f"{role} must be plain legacy PDB.")
    if b"\x00" in payload:
        _failure("rejected", "NUL_BYTE", f"{role} contains a NUL byte.")
    lines = payload.splitlines()
    if len(lines) > MAX_RECORDS:
        _failure("rejected", "RECORD_LIMIT", f"{role} exceeds 250000 records.")
    if any(len(line) > MAX_LINE_BYTES for line in lines):
        _failure("rejected", "LINE_LENGTH_LIMIT", f"{role} contains a line longer than 4096 bytes.")
    try:
        decoded = [line.decode("ascii") for line in lines]
    except UnicodeDecodeError as exc:
        _failure("rejected", "INVALID_ENCODING", f"{role} must be ASCII legacy PDB.")
        raise AssertionError from exc
    structure_id = None
    current_model = 1
    saw_model = False
    candidates: dict[tuple[str, str, str, str, str], list[_Atom]] = {}
    seen_identity_altloc: set[tuple[str, str, str, str, str, str]] = set()
    decimal_places = set()
    for line in decoded:
        record = line[:6].strip()
        if record == "HEADER" and len(line) >= 66 and line[62:66].strip():
            structure_id = line[62:66].strip().lower()
        if record == "MODEL":
            saw_model = True
            try:
                current_model = int(line[10:14].strip())
            except ValueError:
                _failure("rejected", "MALFORMED_PDB", f"{role} has an invalid MODEL record.")
            continue
        if record != "ATOM" or current_model != model:
            continue
        if len(line) < 60:
            _failure("rejected", "MALFORMED_PDB", f"{role} contains a short ATOM record.")
        try:
            coord_text = (line[30:38].strip(), line[38:46].strip(), line[46:54].strip())
            coordinates = tuple(float(value) for value in coord_text)
            occupancy = float(line[54:60].strip() or "0")
        except ValueError as exc:
            _failure("rejected", "MALFORMED_PDB", f"{role} contains malformed coordinates.")
            raise AssertionError from exc
        if any(not math.isfinite(v) or abs(v) > MAX_COORDINATE for v in coordinates):
            _failure("rejected", "INVALID_COORDINATE", f"{role} contains an invalid coordinate.")
        if not math.isfinite(occupancy):
            _failure("rejected", "INVALID_OCCUPANCY", f"{role} contains non-finite occupancy.")
        decimal_places.update(len(value.partition(".")[2]) for value in coord_text)
        chain = line[21:22].strip() or "_"
        residue_number = line[22:26].strip()
        insertion = line[26:27].strip()
        residue_name = line[17:20].strip().upper()
        atom_name = line[12:16].strip().upper()
        altloc = line[16:17].strip()
        base = (chain, residue_number, insertion, residue_name, atom_name)
        identity_altloc = (*base, altloc)
        if identity_altloc in seen_identity_altloc:
            _failure(
                "rejected",
                "DUPLICATE_ATOM_IDENTITY",
                f"{role} repeats an identical ATOM identity and altloc.",
            )
        seen_identity_altloc.add(identity_altloc)
        identity = AtomIdentity(*base, altloc)
        candidates.setdefault(base, []).append(_Atom(identity, coordinates, occupancy, altloc))
    if saw_model and not any(
        line[:6].strip() == "MODEL" and line[10:14].strip() == str(model) for line in decoded
    ):
        _failure("rejected", "MODEL_MISMATCH", f"Selected model {model} is absent from {role}.")
    if not candidates:
        _failure("rejected", "NO_ATOMS", f"{role} has no ATOM records for selected model {model}.")
    atoms = {}
    for variants in candidates.values():
        selected = min(variants, key=lambda atom: (atom.altloc != "", -atom.occupancy, atom.altloc))
        identity = AtomIdentity(
            selected.identity.chain,
            selected.identity.residue_number,
            selected.identity.insertion_code,
            selected.identity.residue_name,
            selected.identity.atom_name,
            selected.altloc,
        )
        atoms[identity] = _Atom(identity, selected.coordinates, selected.occupancy, selected.altloc)
    chains = tuple(sorted({identity.chain for identity in atoms}))
    if len(chains) > MAX_CHAINS:
        _failure("rejected", "CHAIN_LIMIT", f"{role} exceeds 512 chains.")
    if len(decimal_places) != 1:
        _failure(
            "unsupported", "PRECISION_OUTSIDE_ENVELOPE", f"{role} has mixed coordinate precision."
        )
    precision = next(iter(decimal_places))
    if precision != 3:
        _failure(
            "unsupported",
            "PRECISION_OUTSIDE_ENVELOPE",
            f"{role} coordinate precision must be three decimals.",
        )
    return _PdbData(atoms, chains, precision, structure_id, model)


def _metrics(
    current: _PdbData, reference: Mapping[AtomIdentity, tuple[float, float, float]]
) -> dict[str, object]:
    identities = sorted(set(current.atoms) & set(reference))
    residues = {(i.chain, i.residue_number, i.insertion_code, i.residue_name) for i in identities}
    if len(identities) < 12:
        _failure(
            "rejected",
            "INSUFFICIENT_MATCHED_ATOMS",
            "At least 12 matched ATOM identities are required.",
        )
    if len(residues) < 3:
        _failure(
            "rejected",
            "INSUFFICIENT_MATCHED_RESIDUES",
            "At least three matched residues are required.",
        )
    residuals = []
    axis_sq = [0.0, 0.0, 0.0]
    axis_max = [0.0, 0.0, 0.0]
    points = []
    for identity in identities:
        observed = current.atoms[identity].coordinates
        expected = reference[identity]
        diff = tuple(observed[i] - expected[i] for i in range(3))
        residuals.append(math.sqrt(sum(v * v for v in diff)))
        points.append(observed)
        for i in range(3):
            axis_sq[i] += diff[i] ** 2
            axis_max[i] = max(axis_max[i], abs(diff[i]))
    first = min(range(len(points)), key=lambda i: points[i])
    far = max(range(len(points)), key=lambda i: math.dist(points[first], points[i]))
    other = max(range(len(points)), key=lambda i: math.dist(points[far], points[i]))
    separation = math.dist(points[far], points[other])
    start, end = points[far], points[other]
    direction = tuple(end[i] - start[i] for i in range(3))
    denom = sum(v * v for v in direction)
    off_axis = 0.0
    if denom:
        for point in points:
            relative = tuple(point[i] - start[i] for i in range(3))
            projection = sum(relative[i] * direction[i] for i in range(3)) / denom
            closest = tuple(start[i] + projection * direction[i] for i in range(3))
            off_axis = max(off_axis, math.dist(point, closest))
    if separation < 10:
        _failure(
            "rejected", "INSUFFICIENT_SPATIAL_EXTENT", "Matched atoms do not span 10 angstrom."
        )
    if off_axis < 2:
        _failure(
            "rejected",
            "COLLINEAR_MATCHED_ATOMS",
            "Matched atoms lack the required off-axis distribution.",
        )
    return {
        "matched_atom_count": len(identities),
        "matched_residue_count": len(residues),
        "rmsd": math.sqrt(sum(v * v for v in residuals) / len(residuals)),
        "maximum_residual": max(residuals),
        "per_axis_rmsd": [math.sqrt(value / len(residuals)) for value in axis_sq],
        "per_axis_maximum_residual": axis_max,
        "spatial_witness_separation_lower_bound": separation,
        "maximum_distance_from_spatial_witness_line": off_axis,
        "spatial_witness_method": "lexicographic_double_sweep_lower_bound_v1",
        "identities": identities,
    }


def _fingerprint(identities, coordinates, places: int) -> str:
    lines = []
    for identity in identities:
        fields = (
            identity.chain,
            identity.residue_number,
            identity.insertion_code,
            identity.residue_name,
            identity.atom_name,
            identity.resolved_altloc,
        )
        xyz = coordinates[identity]
        quantum = Decimal(1).scaleb(-places)
        normalized = []
        for value in xyz:
            rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_EVEN)
            if rounded == 0:
                rounded = abs(rounded)
            normalized.append(format(rounded, f".{places}f"))
        lines.append("\t".join((*fields, *normalized)))
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def _source_identity(metadata, payloads, digests) -> SourceIdentity:
    return SourceIdentity(
        "PDBTM",
        str(metadata.get("pdb_id", "")).lower() or None,
        str(metadata.get("resource_version", "")).strip() or None,
        str(metadata.get("software_version", "")).strip() or None,
        payloads.primary.source_url,
        payloads.primary.retrieved_at,
        "PDBTM database",
        tuple(digests),
    )


def _provider_identity_contract(metadata: Mapping[str, object]) -> None:
    if metadata.get("data_resource") != "PDBTM":
        _failure(
            "unsupported",
            "UNSUPPORTED_FIELD_STRUCTURE",
            "data_resource must identify PDBTM.",
        )
    for key in ("pdb_id", "resource_version", "software_version"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            _failure(
                "unsupported",
                "UNSUPPORTED_FIELD_STRUCTURE",
                f"{key} must be non-empty text.",
            )


def _provider_chain_labels(metadata: Mapping[str, object]) -> tuple[str, ...]:
    json_chains = metadata.get("chains")
    if not isinstance(json_chains, list):
        _failure("unsupported", "UNSUPPORTED_FIELD_STRUCTURE", "chains must be an array.")
    if len(json_chains) > MAX_CHAINS:
        _failure("rejected", "CHAIN_LIMIT", "PDBTM JSON exceeds 512 chains.")
    if any(
        not isinstance(item, Mapping)
        or not isinstance(item.get("chain_label"), str)
        or not item["chain_label"].strip()
        for item in json_chains
    ):
        _failure("unsupported", "UNSUPPORTED_FIELD_STRUCTURE", "Every chain needs chain_label.")
    labels = {str(item["chain_label"]) for item in json_chains}
    if len(labels) != len(json_chains):
        _failure("rejected", "DUPLICATE_CHAIN_LABEL", "PDBTM JSON chain labels must be unique.")
    return tuple(sorted(labels))


def _provider_chain_mapping(
    metadata: Mapping[str, object], provider_labels: tuple[str, ...]
) -> dict[str, tuple[str, ...]]:
    annotations = metadata.get("additional_entry_annotations")
    if not isinstance(annotations, Mapping):
        _failure(
            "unsupported",
            "UNSUPPORTED_FIELD_STRUCTURE",
            "additional_entry_annotations is required.",
        )
    mapping_results = annotations.get("ent_cif_mapping_results")
    mapping = (
        mapping_results.get("ent_cif_chain_map") if isinstance(mapping_results, Mapping) else None
    )
    if not isinstance(mapping, Mapping) or not mapping:
        _failure("unsupported", "CHAIN_MAPPING_MISSING", "ent_cif_chain_map is required.")
    if len(mapping) > MAX_CHAINS:
        _failure("rejected", "CHAIN_LIMIT", "ent_cif_chain_map exceeds 512 legacy chains.")
    labels = set(provider_labels)
    normalized: dict[str, tuple[str, ...]] = {}
    for chain, targets in mapping.items():
        if not isinstance(chain, str) or not chain:
            _failure(
                "unsupported",
                "UNSUPPORTED_FIELD_STRUCTURE",
                "ent_cif_chain_map keys must be non-empty text.",
            )
        if (
            not isinstance(targets, list)
            or not targets
            or any(not isinstance(value, str) or value not in labels for value in targets)
        ):
            _failure(
                "rejected",
                "CHAIN_NAMESPACE_MISMATCH",
                f"Legacy chain {chain} is not mapped to a declared JSON chain.",
            )
        normalized[chain] = tuple(sorted(targets))
    mapped_labels = {label for targets in normalized.values() for label in targets}
    if mapped_labels != labels:
        _failure(
            "rejected",
            "CHAIN_NAMESPACE_MISMATCH",
            "Provider chain labels must exactly match ent_cif_chain_map targets.",
        )
    return dict(sorted(normalized.items()))


def _chain_contract(
    current: _PdbData,
    transformed: _PdbData,
    mapping: Mapping[str, tuple[str, ...]],
) -> None:
    if set(current.chains) != set(transformed.chains):
        _failure(
            "rejected",
            "CHAIN_SET_MISMATCH",
            "Current and transformed legacy-PDB chain sets must match exactly.",
        )
    if set(mapping) != set(transformed.chains):
        _failure(
            "rejected",
            "CHAIN_NAMESPACE_MISMATCH",
            "ent_cif_chain_map keys must exactly match the legacy-PDB chain set.",
        )


def _normal_and_thickness(metadata) -> tuple[tuple[float, float, float], float]:
    annotations = metadata.get("additional_entry_annotations")
    membrane = annotations.get("membrane") if isinstance(annotations, Mapping) else None
    if isinstance(membrane, list):
        if len(membrane) > MAX_MEMBRANES:
            _failure(
                "rejected",
                "CANDIDATE_MEMBRANE_LIMIT",
                "PDBTM payload exceeds eight candidate membrane records.",
            )
        if len(membrane) > 1:
            _failure(
                "rejected", "MULTIPLE_MEMBRANES", "Multiple membrane records are not supported."
            )
        membrane = membrane[0] if membrane else None
    if not isinstance(membrane, Mapping):
        _failure("rejected", "MISSING_MEMBRANE", "One planar membrane record is required.")
    normal = membrane.get("normal")
    if not isinstance(normal, Mapping) or not all(axis in normal for axis in ("x", "y", "z")):
        _failure("rejected", "MISSING_NORMAL", "PDBTM membrane normal is required.")
    vector = tuple(_number(normal[axis], f"normal.{axis}") for axis in ("x", "y", "z"))
    if abs(vector[0]) > NORMAL_XY_NOISE_LIMIT or abs(vector[1]) > NORMAL_XY_NOISE_LIMIT:
        _failure(
            "unsupported",
            "UNSUPPORTED_NORMAL_SEMANTICS",
            "PDBTM transformed normal x/y exceed the reviewed serialization-noise envelope.",
        )
    if abs(vector[2]) <= MIN_NORMAL_NORM:
        _failure("rejected", "ZERO_NORMAL", "PDBTM membrane normal must be non-zero.")
    if vector[2] < 0:
        _failure(
            "unsupported",
            "UNSUPPORTED_NORMAL_SEMANTICS",
            "PDBTM transformed normal z must be positive.",
        )
    return (0.0, 0.0, 1.0), vector[2]


def _precision_bounds(transform: _Transform, original, transformed) -> dict[str, object]:
    eps_x = 0.5 * 10**-original.coordinate_decimal_places
    eps_y = 0.5 * 10**-transformed.coordinate_decimal_places
    rotation_places = transform.precision["rotation_decimal_places"]
    translation_places = transform.precision["translation_decimal_places"]
    magnitudes = [
        max(abs(atom.coordinates[i]) for atom in original.atoms.values()) + eps_x for i in range(3)
    ]
    axis_bounds = []
    for i in range(3):
        bound = eps_y + 0.5 * 10 ** -translation_places[i]
        for j in range(3):
            eps_r = 0.5 * 10 ** -rotation_places[i][j]
            bound += abs(transform.rows3[i][j]) * eps_x + magnitudes[j] * eps_r + eps_x * eps_r
        axis_bounds.append(bound)
    forward = math.sqrt(sum(value * value for value in axis_bounds))
    limit = math.ceil(forward * 1000) / 1000
    identity = math.sqrt(3.0) * (eps_x + eps_y)
    inverse = tuple(tuple(transform.inverse4[i][j] for j in range(3)) for i in range(3))
    inverse_norm = max(sum(abs(value) for value in row) for row in inverse)
    matrix_error_norm = max(
        sum(0.5 * 10 ** -rotation_places[i][j] for j in range(3)) for i in range(3)
    )
    translation_error = max(0.5 * 10**-places for places in translation_places)
    source_magnitude = max(magnitudes)
    inverse_axis = eps_x + inverse_norm * (
        matrix_error_norm * source_magnitude + translation_error + eps_y
    )
    inverse_bound = math.sqrt(3.0) * inverse_axis
    return {
        "runtime_identity_theoretical_bound": identity,
        "provider_forward_theoretical_bound": forward,
        "runtime_inverse_theoretical_bound": inverse_bound,
        "provider_forward_axis_bounds": axis_bounds,
        "provider_forward_validation_limit": limit,
        "reviewed_envelope_decision": "accepted",
    }


def _provider_assembly(metadata: Mapping[str, object]) -> str | None:
    values = {
        str(metadata[key]).strip()
        for key in ("assembly_id", "biological_assembly")
        if metadata.get(key) is not None and str(metadata[key]).strip()
    }
    if len(values) > 1:
        _failure(
            "unsupported",
            "UNSUPPORTED_FIELD_STRUCTURE",
            "Provider assembly fields disagree.",
        )
    return next(iter(values), None)


class PdbtmApiV1Adapter:
    source_name = "PDBTM"
    adapter_name = ADAPTER_NAME
    adapter_version = ADAPTER_VERSION
    supported_media_types = ("application/json", "text/plain", "chemical/x-pdb")
    supported_format_profiles = ("pdbtm-api-v1-reviewed-precision-envelope",)

    def can_parse(self, payloads: OrientationPayloadSet, metadata: Mapping[str, object]) -> bool:
        return (
            payloads.primary.role == "pdbtm_json"
            and payloads.primary.content.lstrip().startswith(b"{")
        )

    def parse(
        self,
        payloads: OrientationPayloadSet,
        *,
        structure_context: StructureContext,
        metadata: Mapping[str, object],
    ) -> OrientationImportResult:
        digests = []
        source = None
        try:
            if payloads.primary.role != "pdbtm_json":
                _failure(
                    "rejected",
                    "UNEXPECTED_PAYLOAD_ROLE",
                    "Primary payload role must be exactly pdbtm_json.",
                )
            unexpected_roles = sorted(
                {item.role for item in payloads.companions if item.role != "transformed_pdb"}
            )
            if unexpected_roles:
                _failure(
                    "rejected",
                    "UNEXPECTED_PAYLOAD_ROLE",
                    "Companion payload roles must be exactly transformed_pdb; received "
                    + ", ".join(unexpected_roles)
                    + ".",
                )
            if len(payloads.companions) > 1:
                _failure(
                    "rejected",
                    "COMPANION_COUNT",
                    "At most one transformed-PDB companion is permitted.",
                )
            for payload in (payloads.primary, *payloads.companions):
                _check_payload(payload)
                digests.append(_digest(payload))
            document = _load_json(payloads.primary)
            _provider_identity_contract(document)
            source = _source_identity(document, payloads, digests)
            transform = _matrix(document)
            _normal_and_thickness(document)
            provider_chain_labels = _provider_chain_labels(document)
            chain_mapping = _provider_chain_mapping(document, provider_chain_labels)
            companions = list(payloads.companions)
            if not companions:
                return OrientationImportResult(
                    "partial",
                    source=source,
                    messages=(
                        ImportMessage(
                            "TRANSFORMED_COMPANION_REQUIRED",
                            "JSON provenance was retained, but a transformed-PDB companion is required for geometry resolution.",
                        ),
                    ),
                )
            transformed = _parse_pdb(
                companions[0].content, structure_context.model_id, "transformed_pdb"
            )
            current = _parse_pdb(
                structure_context.pdb_payload, structure_context.model_id, "current_structure"
            )
            record_id = str(document.get("pdb_id", "")).lower()
            if (
                structure_context.structure_id
                and structure_context.structure_id.lower() != record_id
            ):
                _failure(
                    "rejected",
                    "STRUCTURE_ID_MISMATCH",
                    "PDBTM record does not match StructureContext structure_id.",
                )
            if transformed.structure_id and transformed.structure_id != record_id:
                _failure(
                    "rejected",
                    "COMPANION_ID_MISMATCH",
                    "Transformed companion PDB ID does not match JSON record.",
                )
            if current.structure_id and current.structure_id != record_id:
                _failure(
                    "rejected",
                    "STRUCTURE_ID_MISMATCH",
                    "Current legacy-PDB ID does not match the PDBTM record.",
                )
            _chain_contract(current, transformed, chain_mapping)
            provider_assembly = _provider_assembly(document)
            if (
                provider_assembly is not None
                and structure_context.biological_assembly is not None
                and provider_assembly != structure_context.biological_assembly
            ):
                _failure(
                    "rejected",
                    "ASSEMBLY_MISMATCH",
                    "Provider and current biological assemblies do not match.",
                )
            reference_a = {
                identity: atom.coordinates for identity, atom in transformed.atoms.items()
            }
            reference_b = {
                identity: _point(transform.inverse4, atom.coordinates)
                for identity, atom in transformed.atoms.items()
            }
            bounds = _precision_bounds(
                transform,
                _PdbData(
                    {i: _Atom(i, reference_b[i], 1, "") for i in reference_b},
                    transformed.chains,
                    current.coordinate_decimal_places,
                    record_id,
                    structure_context.model_id,
                ),
                transformed,
            )
            if (
                bounds["runtime_identity_theoretical_bound"] > RUNTIME_IDENTITY_LIMIT
                or bounds["runtime_inverse_theoretical_bound"] > RUNTIME_INVERSE_LIMIT
            ):
                _failure(
                    "unsupported",
                    "PRECISION_OUTSIDE_ENVELOPE",
                    "Exact payload rounding bounds exceed the reviewed runtime match envelope.",
                )
            metrics_a = _metrics(current, reference_a)
            metrics_b = _metrics(current, reference_b)
            pass_a = (
                metrics_a["rmsd"] <= RUNTIME_IDENTITY_LIMIT
                and metrics_a["maximum_residual"] <= RUNTIME_IDENTITY_LIMIT
            )
            pass_b = (
                metrics_b["rmsd"] <= RUNTIME_INVERSE_LIMIT
                and metrics_b["maximum_residual"] <= RUNTIME_INVERSE_LIMIT
            )
            if pass_a and pass_b:
                _failure(
                    "rejected",
                    "AMBIGUOUS_COORDINATE_FRAME",
                    "Current coordinates match both permitted references.",
                )
            if not pass_a and not pass_b:
                _failure(
                    "rejected",
                    "COORDINATE_FRAME_MISMATCH",
                    "Current coordinates match neither permitted reference.",
                )
            selected = metrics_a if pass_a else metrics_b
            identities = selected.pop("identities")
            metrics_a.pop("identities", None)
            metrics_b.pop("identities", None)
            current_coordinates = {
                identity: current.atoms[identity].coordinates for identity in identities
            }
            fingerprints = {
                "algorithm": FINGERPRINT_ALGORITHM,
                "version": FINGERPRINT_VERSION,
                "transformed_reference": _fingerprint(
                    identities, reference_a, transformed.coordinate_decimal_places
                ),
                "inverse_reference": _fingerprint(
                    identities, reference_b, transformed.coordinate_decimal_places
                ),
                "current": _fingerprint(
                    identities, current_coordinates, transformed.coordinate_decimal_places
                ),
                "matched_count": len(identities),
            }
            normal, half = _normal_and_thickness(document)
            source_geometry = PlanarGeometryEvidence(
                (0, 0, 0), normal, -half, half, None, "pdbtm_transformed"
            )
            source_to_current = (
                tuple(tuple(1.0 if i == j else 0.0 for j in range(4)) for i in range(4))
                if pass_a
                else transform.inverse4
            )
            center = _point(source_to_current, (0.0, 0.0, 0.0))
            mapped_normal = _vector(source_to_current, normal)
            length = math.sqrt(sum(value * value for value in mapped_normal))
            mapped_normal = tuple(value / length for value in mapped_normal)
            current_geometry = PlanarGeometryEvidence(
                center,
                mapped_normal,
                -half,
                half,
                DEFAULT_INTERFACE_WIDTH,
                structure_context.coordinate_frame,
            )
            membrane = PlanarMembrane(
                center,
                mapped_normal,
                -half,
                half,
                DEFAULT_INTERFACE_WIDTH,
                "pdbtm_offline",
                source_version=source.resource_version,
                confidence="coordinate_verified",
                metadata={"adapter": ADAPTER_NAME},
            )
            precision = {
                **transform.precision,
                "current_coordinate_decimal_places": current.coordinate_decimal_places,
                "transformed_coordinate_decimal_places": transformed.coordinate_decimal_places,
                "normal_xy_noise_limit": NORMAL_XY_NOISE_LIMIT,
                "normal_semantics": "positive_z_half_thickness",
                **bounds,
            }
            mapping = CoordinateMapping(
                "pdbtm_transformed",
                structure_context.coordinate_frame,
                source_to_current,
                transform.matrix4,
                transform.inverse4,
                "identity" if pass_a else "inverse_provider_transform",
                {"runtime_identity": metrics_a, "runtime_inverse": metrics_b},
                fingerprints,
                precision,
                {
                    "runtime_identity_match_limit": {
                        "rmsd": RUNTIME_IDENTITY_LIMIT,
                        "maximum_residual": RUNTIME_IDENTITY_LIMIT,
                    },
                    "runtime_inverse_match_limit": {
                        "rmsd": RUNTIME_INVERSE_LIMIT,
                        "maximum_residual": RUNTIME_INVERSE_LIMIT,
                    },
                    "provider_forward_validation_limit": bounds[
                        "provider_forward_validation_limit"
                    ],
                },
                transform.determinant,
                transform.orthonormality_error,
            )
            source_scope = StructureScope(
                record_id,
                str(structure_context.model_id),
                provider_assembly,
                transformed.chains,
                "legacy_pdb",
                "pdbtm_transformed",
                fingerprints["transformed_reference"],
                provider_chain_labels,
                transformed.chains,
                chain_mapping,
                structure_context.model_id,
            )
            current_scope = StructureScope(
                structure_context.structure_id or record_id,
                str(structure_context.model_id),
                structure_context.biological_assembly,
                current.chains,
                "legacy_pdb",
                structure_context.coordinate_frame,
                fingerprints["current"],
                provider_chain_labels,
                current.chains,
                chain_mapping,
                structure_context.model_id,
            )
            evidence = OrientationEvidenceV1(
                "1",
                ADAPTER_NAME,
                ADAPTER_VERSION,
                source,
                source_scope,
                source_geometry,
                current_scope,
                mapping,
                current_geometry,
                "coordinate_verified",
                raw_metadata={
                    "resource_version": source.resource_version,
                    "software_version": source.software_version,
                    "provider_assembly": provider_assembly,
                    "current_assembly": structure_context.biological_assembly,
                    "provider_chain_labels": provider_chain_labels,
                    "ent_cif_chain_map": chain_mapping,
                    "mvqc_interface_width": DEFAULT_INTERFACE_WIDTH,
                },
            )
            return OrientationImportResult("imported", source, evidence, membrane)
        except _AdapterFailure as exc:
            return OrientationImportResult(exc.status, source=source, messages=(exc.issue,))
        except OrientationError as exc:
            return OrientationImportResult(
                "rejected",
                source=source,
                messages=(ImportMessage("INVALID_DOMAIN_EVIDENCE", str(exc)),),
            )


def import_pdbtm_orientation(
    json_payload: bytes,
    transformed_pdb_payload: bytes | None,
    structure_context: StructureContext,
    metadata: Mapping[str, object] | None = None,
) -> OrientationImportResult:
    """Import explicit offline PDBTM bytes without network or PyMOL dependencies."""
    metadata = dict(metadata or {})
    primary = OrientationPayload(
        "pdbtm_json",
        json_payload,
        metadata.get("json_media_type"),
        metadata.get("json_source"),
        metadata.get("json_retrieved_at"),
        False,
    )
    companions = (
        ()
        if transformed_pdb_payload is None
        else (
            OrientationPayload(
                "transformed_pdb",
                transformed_pdb_payload,
                metadata.get("pdb_media_type"),
                metadata.get("pdb_source"),
                metadata.get("pdb_retrieved_at"),
                False,
            ),
        )
    )
    return PdbtmApiV1Adapter().parse(
        OrientationPayloadSet(primary, companions),
        structure_context=structure_context,
        metadata=metadata,
    )
