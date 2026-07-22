"""Deterministic, offline-only adapter for planar OPM legacy-PDB files.

The adapter deliberately performs no fitting, alignment, transformation, path I/O,
network I/O, or PyMOL mutation.  An OPM orientation is applicable only when its
non-dummy ATOM coordinates already match the supplied current-object snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import math
import re
from types import MappingProxyType
from typing import Literal

from .constants import DEFAULT_INTERFACE_WIDTH
from .errors import OrientationError
from .orientation import PlanarMembrane
from .orientation_sources import (
    ImportMessage,
    PayloadDigest,
    PlanarGeometryEvidence,
    SourceIdentity,
    StructureContext,
    StructureScope,
)

MAX_PAYLOAD_BYTES = 5 * 1024 * 1024
MAX_LINE_BYTES = 4096
MAX_RECORDS = 500_000
MAX_CHAINS = 512
MAX_COORDINATE = 1_000_000.0
IDENTITY_LIMIT = 0.003
PLANE_RESIDUAL_LIMIT = 0.003
PARALLEL_ANGLE_LIMIT_DEGREES = 0.1
MIN_MATCHED_ATOMS = 12
MIN_MATCHED_RESIDUES = 3
MIN_SPATIAL_EXTENT = 10.0
MIN_OFF_AXIS_EXTENT = 2.0
MIN_THICKNESS = 0.006
MAX_THICKNESS = 200.0
ADAPTER_NAME = "opm_pdb_offline"
ADAPTER_VERSION = "1"
EVIDENCE_MODEL_VERSION = "1"
FINGERPRINT_ALGORITHM = "mvqc_atom_identity_coordinates_sha256"
FINGERPRINT_VERSION = "1"

OpmImportStatus = Literal["imported", "rejected", "unsupported"]
Vector3 = tuple[float, float, float]


@dataclass(frozen=True, order=True, slots=True)
class OpmAtomIdentity:
    chain: str
    residue_number: str
    insertion_code: str
    residue_name: str
    atom_name: str
    resolved_altloc: str


@dataclass(frozen=True, slots=True)
class _Atom:
    identity: OpmAtomIdentity
    coordinates: Vector3
    occupancy: float
    altloc: str


@dataclass(frozen=True, slots=True)
class _ParsedPdb:
    atoms: Mapping[OpmAtomIdentity, _Atom]
    chains: tuple[str, ...]
    structure_id: str | None
    coordinate_decimal_places: int
    dummy_n: tuple[Vector3, ...]
    dummy_o: tuple[Vector3, ...]
    half_thickness_remark: float | None


@dataclass(frozen=True, slots=True)
class OpmBoundaryPlaneEvidence:
    label: str
    centroid: Vector3
    normal: Vector3
    point_count: int
    rms_residual: float
    maximum_residual: float

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "centroid": list(self.centroid),
            "normal": list(self.normal),
            "point_count": self.point_count,
            "rms_residual": self.rms_residual,
            "maximum_residual": self.maximum_residual,
        }


@dataclass(frozen=True, slots=True)
class OpmIdentityApplicability:
    method: str
    matched_atom_count: int
    matched_residue_count: int
    rmsd: float
    maximum_residual: float
    source_atom_count: int
    current_atom_count: int
    source_fingerprint: str
    current_fingerprint: str
    thresholds: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.method != "identity_no_transform":
            raise OrientationError("OPM applicability method must be identity_no_transform.")
        object.__setattr__(self, "thresholds", _freeze(self.thresholds))

    def as_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "matched_atom_count": self.matched_atom_count,
            "matched_residue_count": self.matched_residue_count,
            "rmsd": self.rmsd,
            "maximum_residual": self.maximum_residual,
            "source_atom_count": self.source_atom_count,
            "current_atom_count": self.current_atom_count,
            "source_fingerprint": self.source_fingerprint,
            "current_fingerprint": self.current_fingerprint,
            "thresholds": _thaw(self.thresholds),
        }


@dataclass(frozen=True, slots=True)
class OpmOrientationEvidence:
    model_version: str
    adapter_name: str
    adapter_version: str
    source: SourceIdentity
    source_scope: StructureScope
    current_scope: StructureScope
    source_geometry: PlanarGeometryEvidence
    current_geometry: PlanarGeometryEvidence
    boundary_planes: tuple[OpmBoundaryPlaneEvidence, OpmBoundaryPlaneEvidence]
    applicability: OpmIdentityApplicability
    directional_topology_available: bool
    raw_metadata: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[ImportMessage, ...] = ()

    def __post_init__(self) -> None:
        if self.directional_topology_available:
            raise OrientationError("OPM DUM labels do not establish directional topology.")
        object.__setattr__(self, "raw_metadata", _freeze(self.raw_metadata))
        object.__setattr__(self, "warnings", tuple(sorted(self.warnings, key=lambda x: x.code)))

    def as_dict(self) -> dict[str, object]:
        return {
            "model_version": self.model_version,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "source": self.source.as_dict(),
            "source_scope": self.source_scope.as_dict(),
            "current_scope": self.current_scope.as_dict(),
            "source_geometry": self.source_geometry.as_dict(),
            "current_geometry": self.current_geometry.as_dict(),
            "boundary_planes": [plane.as_dict() for plane in self.boundary_planes],
            "applicability": self.applicability.as_dict(),
            "directional_topology_available": False,
            "raw_metadata": _thaw(self.raw_metadata),
            "warnings": [warning.as_dict() for warning in self.warnings],
        }


@dataclass(frozen=True, slots=True)
class OpmImportResult:
    status: OpmImportStatus
    source: SourceIdentity
    evidence: OpmOrientationEvidence | None = None
    membrane: PlanarMembrane | None = None
    messages: tuple[ImportMessage, ...] = ()

    def __post_init__(self) -> None:
        if self.status == "imported":
            if self.evidence is None or self.membrane is None:
                raise OrientationError("Imported OPM result requires evidence and a membrane.")
            if self.source != self.evidence.source:
                raise OrientationError("OPM result source must match its evidence source.")
        elif self.evidence is not None or self.membrane is not None:
            raise OrientationError("Rejected or unsupported OPM results cannot contain geometry.")
        object.__setattr__(self, "messages", tuple(self.messages))

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source": self.source.as_dict(),
            "evidence": None if self.evidence is None else self.evidence.as_dict(),
            "messages": [message.as_dict() for message in self.messages],
        }


class _AdapterFailure(Exception):
    def __init__(self, status: OpmImportStatus, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.issue = ImportMessage(code, message)


def _failure(status: OpmImportStatus, code: str, message: str) -> None:
    raise _AdapterFailure(status, code, message)


def _freeze(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OrientationError("OPM evidence numbers must be finite.")
        return 0.0 if value == 0 else value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    raise OrientationError("OPM evidence must be JSON-safe.")


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _canonical_record_id(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9]{4}", value.strip()) is None:
        raise OrientationError("expected_record_id must be exactly four ASCII letters or digits.")
    return value.strip().lower()


def _digest(payload: bytes) -> PayloadDigest:
    return PayloadDigest(
        "opm_pdb",
        hashlib.sha256(payload).hexdigest(),
        len(payload),
        media_type="chemical/x-pdb",
    )


def _source(record_id: str, payload: bytes) -> SourceIdentity:
    return SourceIdentity(
        "OPM",
        record_id,
        None,
        None,
        None,
        None,
        "Orientations of Proteins in Membranes database",
        (_digest(payload),),
    )


def _parse_coordinate(line: str, role: str) -> tuple[Vector3, int]:
    if len(line) < 54:
        _failure("rejected", "MALFORMED_PDB", f"{role} contains a short coordinate record.")
    fields = (line[30:38].strip(), line[38:46].strip(), line[46:54].strip())
    try:
        xyz = tuple(float(field) for field in fields)
    except ValueError as exc:
        _failure("rejected", "MALFORMED_PDB", f"{role} contains malformed coordinates.")
        raise AssertionError from exc
    if any(not math.isfinite(value) or abs(value) > MAX_COORDINATE for value in xyz):
        _failure("rejected", "INVALID_COORDINATE", f"{role} contains an invalid coordinate.")
    places = {len(field.partition(".")[2]) for field in fields}
    if len(places) != 1:
        _failure("unsupported", "PRECISION_OUTSIDE_ENVELOPE", f"{role} has mixed precision.")
    return xyz, next(iter(places))  # type: ignore[return-value]


def _parse_pdb(payload: bytes, role: str, *, require_dummy: bool) -> _ParsedPdb:
    if not isinstance(payload, bytes):
        raise OrientationError(f"{role} must be exact bytes.")
    if len(payload) > MAX_PAYLOAD_BYTES:
        _failure("rejected", "PAYLOAD_TOO_LARGE", f"{role} exceeds the 5 MiB limit.")
    if payload.startswith((b"PK\x03\x04", b"\x1f\x8b")) or payload[257:262] == b"ustar":
        _failure("rejected", "CONTAINER_NOT_ALLOWED", f"{role} must be plain legacy PDB.")
    if b"\x00" in payload:
        _failure("rejected", "NUL_BYTE", f"{role} contains a NUL byte.")
    lines = payload.splitlines()
    if len(lines) > MAX_RECORDS:
        _failure("rejected", "RECORD_LIMIT", f"{role} exceeds 500000 records.")
    if any(len(line) > MAX_LINE_BYTES for line in lines):
        _failure("rejected", "LINE_LENGTH_LIMIT", f"{role} contains an overlong line.")
    try:
        decoded = [line.decode("ascii") for line in lines]
    except UnicodeDecodeError as exc:
        _failure("rejected", "INVALID_ENCODING", f"{role} must be ASCII legacy PDB.")
        raise AssertionError from exc

    model_numbers: list[int] = []
    for line in decoded:
        if line[:6].strip() != "MODEL":
            continue
        try:
            model_numbers.append(int(line[10:14].strip()))
        except ValueError as exc:
            _failure("rejected", "MALFORMED_PDB", f"{role} has an invalid MODEL record.")
            raise AssertionError from exc
    if len(model_numbers) > 1 or len(set(model_numbers)) > 1:
        _failure("unsupported", "MULTIPLE_MODELS", f"{role} must contain exactly one model.")
    if model_numbers and model_numbers[0] != 1:
        _failure("unsupported", "MODEL_MISMATCH", f"{role} must use model 1.")
    structure_id = None
    half_thickness = None
    dummy: dict[str, list[Vector3]] = {"N": [], "O": []}
    candidates: dict[tuple[str, str, str, str, str], list[_Atom]] = {}
    seen: set[tuple[str, str, str, str, str, str]] = set()
    precisions: set[int] = set()
    for line in decoded:
        record = line[:6].strip()
        if record == "HEADER" and len(line) >= 66 and line[62:66].strip():
            structure_id = line[62:66].strip().lower()
        if record == "MODEL":
            continue
        if record == "REMARK":
            match = re.search(r"1/2\s+of\s+bilayer\s+thickness\s*:\s*([-+0-9.eE]+)", line)
            if match:
                try:
                    value = float(match.group(1))
                except ValueError:
                    value = math.nan
                if not math.isfinite(value) or value <= 0:
                    _failure(
                        "rejected", "INVALID_THICKNESS_REMARK", "Invalid OPM thickness remark."
                    )
                if half_thickness is not None and not math.isclose(
                    half_thickness, value, rel_tol=0.0, abs_tol=1e-12
                ):
                    _failure("rejected", "AMBIGUOUS_THICKNESS_REMARK", "Conflicting OPM remarks.")
                half_thickness = value
            continue
        if record not in {"ATOM", "HETATM"}:
            continue
        xyz, places = _parse_coordinate(line, role)
        precisions.add(places)
        residue_name = line[17:20].strip().upper()
        atom_name = line[12:16].strip().upper()
        if record == "HETATM" and residue_name == "DUM":
            if not require_dummy:
                continue
            if atom_name not in dummy:
                _failure("unsupported", "UNSUPPORTED_DUMMY_LABEL", "DUM labels must be N and O.")
            if line[16:17].strip():
                _failure("rejected", "AMBIGUOUS_DUMMY_ALTLOC", "DUM points cannot use altlocs.")
            dummy[atom_name].append(xyz)
            continue
        if record != "ATOM":
            continue
        if len(line) < 60:
            _failure("rejected", "MALFORMED_PDB", f"{role} contains a short ATOM record.")
        try:
            occupancy = float(line[54:60].strip() or "0")
        except ValueError as exc:
            _failure("rejected", "MALFORMED_PDB", f"{role} contains invalid occupancy.")
            raise AssertionError from exc
        if not math.isfinite(occupancy):
            _failure("rejected", "INVALID_OCCUPANCY", f"{role} contains invalid occupancy.")
        chain = line[21:22].strip() or "_"
        residue_number = line[22:26].strip()
        insertion = line[26:27].strip()
        altloc = line[16:17].strip()
        base = (chain, residue_number, insertion, residue_name, atom_name)
        identity_altloc = (*base, altloc)
        if identity_altloc in seen:
            _failure("rejected", "DUPLICATE_ATOM_IDENTITY", f"{role} repeats an atom identity.")
        seen.add(identity_altloc)
        identity = OpmAtomIdentity(*base, altloc)
        candidates.setdefault(base, []).append(_Atom(identity, xyz, occupancy, altloc))

    if not candidates:
        _failure("rejected", "NO_ATOMS", f"{role} has no ATOM records.")
    if len(precisions) != 1 or next(iter(precisions)) != 3:
        _failure("unsupported", "PRECISION_OUTSIDE_ENVELOPE", f"{role} must use 0.001 A precision.")
    atoms: dict[OpmAtomIdentity, _Atom] = {}
    for variants in candidates.values():
        chosen = min(variants, key=lambda atom: (atom.altloc != "", -atom.occupancy, atom.altloc))
        identity = OpmAtomIdentity(
            chosen.identity.chain,
            chosen.identity.residue_number,
            chosen.identity.insertion_code,
            chosen.identity.residue_name,
            chosen.identity.atom_name,
            chosen.altloc,
        )
        atoms[identity] = _Atom(identity, chosen.coordinates, chosen.occupancy, chosen.altloc)
    chains = tuple(sorted({identity.chain for identity in atoms}))
    if len(chains) > MAX_CHAINS:
        _failure("rejected", "CHAIN_LIMIT", f"{role} exceeds 512 chains.")
    if require_dummy and (not dummy["N"] or not dummy["O"]):
        _failure("rejected", "MISSING_DUMMY_BOUNDARY", "OPM PDB requires DUM N and O surfaces.")
    return _ParsedPdb(
        MappingProxyType(atoms),
        chains,
        structure_id,
        3,
        tuple(dummy["N"]),
        tuple(dummy["O"]),
        half_thickness,
    )


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _norm(vector: Vector3) -> float:
    return math.sqrt(_dot(vector, vector))


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _normalize(vector: Vector3) -> Vector3:
    length = _norm(vector)
    if length <= 1e-12:
        _failure("unsupported", "DEGENERATE_DUMMY_PLANE", "DUM surface is degenerate.")
    return tuple((0.0 if value == 0 else value / length) for value in vector)  # type: ignore[return-value]


def _canonical_normal(vector: Vector3) -> Vector3:
    unit = _normalize(vector)
    for value in unit:
        if abs(value) > 1e-12:
            if value < 0:
                return tuple(-item for item in unit)  # type: ignore[return-value]
            break
    return unit


def _smallest_eigenvector_symmetric3(matrix: list[list[float]]) -> Vector3:
    a = [row[:] for row in matrix]
    vectors = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(32):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda pair: abs(a[pair[0]][pair[1]]))
        if abs(a[p][q]) <= 1e-15:
            break
        angle = 0.5 * math.atan2(2.0 * a[p][q], a[q][q] - a[p][p])
        c, s = math.cos(angle), math.sin(angle)
        for k in range(3):
            if k not in (p, q):
                apk, aqk = a[p][k], a[q][k]
                a[p][k] = a[k][p] = c * apk - s * aqk
                a[q][k] = a[k][q] = s * apk + c * aqk
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        a[p][p] = c * c * app - 2.0 * s * c * apq + s * s * aqq
        a[q][q] = s * s * app + 2.0 * s * c * apq + c * c * aqq
        a[p][q] = a[q][p] = 0.0
        for k in range(3):
            vkp, vkq = vectors[k][p], vectors[k][q]
            vectors[k][p] = c * vkp - s * vkq
            vectors[k][q] = s * vkp + c * vkq
    index = min(range(3), key=lambda i: a[i][i])
    return _canonical_normal(tuple(vectors[row][index] for row in range(3)))


def _fit_plane(label: str, points: tuple[Vector3, ...]) -> OpmBoundaryPlaneEvidence:
    if len(points) < 3:
        _failure("unsupported", "INSUFFICIENT_DUMMY_POINTS", f"DUM {label} needs three points.")
    centroid = tuple(sum(point[i] for point in points) / len(points) for i in range(3))
    covariance = [[0.0] * 3 for _ in range(3)]
    for point in points:
        delta = tuple(point[i] - centroid[i] for i in range(3))
        for i in range(3):
            for j in range(3):
                covariance[i][j] += delta[i] * delta[j]
    normal = _smallest_eigenvector_symmetric3(covariance)
    residuals = [
        abs(_dot(tuple(point[i] - centroid[i] for i in range(3)), normal)) for point in points
    ]
    rms = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    maximum = max(residuals)
    # A plane also requires two independent in-plane directions.  Check the
    # smaller eigenvalue of covariance expressed in a deterministic plane basis.
    axes: tuple[Vector3, ...] = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    reference = min(axes, key=lambda axis: abs(_dot(axis, normal)))
    basis_u = _normalize(_cross(normal, reference))
    basis_v = _normalize(_cross(normal, basis_u))
    covariance_uu = sum(
        basis_u[i] * covariance[i][j] * basis_u[j] for i in range(3) for j in range(3)
    )
    covariance_vv = sum(
        basis_v[i] * covariance[i][j] * basis_v[j] for i in range(3) for j in range(3)
    )
    covariance_uv = sum(
        basis_u[i] * covariance[i][j] * basis_v[j] for i in range(3) for j in range(3)
    )
    smaller_in_plane = 0.5 * (
        covariance_uu
        + covariance_vv
        - math.sqrt((covariance_uu - covariance_vv) ** 2 + 4.0 * covariance_uv * covariance_uv)
    )
    if smaller_in_plane <= 1e-8:
        _failure("unsupported", "DEGENERATE_DUMMY_PLANE", f"DUM {label} points are collinear.")
    if rms > PLANE_RESIDUAL_LIMIT or maximum > PLANE_RESIDUAL_LIMIT:
        _failure("unsupported", "NON_PLANAR_MEMBRANE", f"DUM {label} surface is not planar.")
    return OpmBoundaryPlaneEvidence(label, centroid, normal, len(points), rms, maximum)


def _geometry(
    parsed: _ParsedPdb,
) -> tuple[
    PlanarGeometryEvidence,
    tuple[OpmBoundaryPlaneEvidence, OpmBoundaryPlaneEvidence],
    tuple[ImportMessage, ...],
]:
    plane_n = _fit_plane("N", parsed.dummy_n)
    plane_o = _fit_plane("O", parsed.dummy_o)
    dot_value = _dot(plane_n.normal, plane_o.normal)
    angle = math.degrees(math.acos(max(-1.0, min(1.0, abs(dot_value)))))
    if angle > PARALLEL_ANGLE_LIMIT_DEGREES:
        _failure("unsupported", "NON_PARALLEL_BOUNDARIES", "OPM DUM boundaries are not parallel.")
    aligned_o = plane_o.normal if dot_value >= 0 else tuple(-x for x in plane_o.normal)
    common = _canonical_normal(tuple(plane_n.normal[i] + aligned_o[i] for i in range(3)))
    separation = abs(
        _dot(tuple(plane_o.centroid[i] - plane_n.centroid[i] for i in range(3)), common)
    )
    if separation < MIN_THICKNESS or separation > MAX_THICKNESS:
        _failure("unsupported", "INVALID_MEMBRANE_THICKNESS", "OPM DUM thickness is unsupported.")
    center = tuple((plane_n.centroid[i] + plane_o.centroid[i]) / 2.0 for i in range(3))
    half = separation / 2.0
    warnings: list[ImportMessage] = []
    if parsed.half_thickness_remark is not None and not math.isclose(
        parsed.half_thickness_remark, half, rel_tol=0.0, abs_tol=IDENTITY_LIMIT
    ):
        warnings.append(
            ImportMessage(
                "THICKNESS_REMARK_MISMATCH",
                "The OPM half-thickness remark does not match the DUM boundary geometry.",
            )
        )
    return (
        PlanarGeometryEvidence(center, common, -half, half, None, "opm_oriented_pdb"),
        (plane_n, plane_o),
        tuple(warnings),
    )


def _identity_metrics(
    source: _ParsedPdb, current: _ParsedPdb
) -> tuple[OpmIdentityApplicability, tuple[OpmAtomIdentity, ...]]:
    source_ids, current_ids = set(source.atoms), set(current.atoms)
    if source_ids != current_ids:
        _failure("rejected", "ATOM_SCOPE_MISMATCH", "OPM and current ATOM identity sets differ.")
    if source.chains != current.chains:
        _failure("rejected", "CHAIN_SCOPE_MISMATCH", "OPM and current chain sets differ.")
    identities = tuple(sorted(source_ids))
    residues = {(i.chain, i.residue_number, i.insertion_code, i.residue_name) for i in identities}
    if len(identities) < MIN_MATCHED_ATOMS:
        _failure(
            "rejected", "INSUFFICIENT_MATCHED_ATOMS", "At least 12 matched atoms are required."
        )
    if len(residues) < MIN_MATCHED_RESIDUES:
        _failure(
            "rejected", "INSUFFICIENT_MATCHED_RESIDUES", "At least three residues are required."
        )
    points = [source.atoms[identity].coordinates for identity in identities]
    # Deterministic double sweep gives an actual atom-pair witness in O(n),
    # avoiding the former quadratic all-pairs scan on large valid proteins.
    first_seed = points[0]
    first = max(points, key=lambda point: (math.dist(first_seed, point), point))
    second = max(points, key=lambda point: (math.dist(first, point), point))
    max_separation = math.dist(first, second)
    if max_separation < MIN_SPATIAL_EXTENT:
        _failure("rejected", "INSUFFICIENT_SPATIAL_EXTENT", "Matched atoms span less than 10 A.")
    direction = tuple(second[i] - first[i] for i in range(3))
    denominator = _dot(direction, direction)
    off_axis = 0.0
    for point in points:
        relative = tuple(point[i] - first[i] for i in range(3))
        scale = _dot(relative, direction) / denominator
        closest = tuple(first[i] + scale * direction[i] for i in range(3))
        off_axis = max(off_axis, math.dist(point, closest))
    if off_axis < MIN_OFF_AXIS_EXTENT:
        _failure("rejected", "COLLINEAR_MATCHED_ATOMS", "Matched atoms lack off-axis extent.")
    residuals = [
        math.dist(source.atoms[identity].coordinates, current.atoms[identity].coordinates)
        for identity in identities
    ]
    rmsd = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    maximum = max(residuals)
    if rmsd > IDENTITY_LIMIT or maximum > IDENTITY_LIMIT:
        _failure(
            "rejected",
            "COORDINATE_FRAME_MISMATCH",
            "Current coordinates do not match OPM in the identity frame; fitting is not allowed.",
        )
    source_fp = _fingerprint(identities, source.atoms)
    current_fp = _fingerprint(identities, current.atoms)
    return (
        OpmIdentityApplicability(
            "identity_no_transform",
            len(identities),
            len(residues),
            rmsd,
            maximum,
            len(source.atoms),
            len(current.atoms),
            source_fp,
            current_fp,
            {
                "rmsd": IDENTITY_LIMIT,
                "maximum_residual": IDENTITY_LIMIT,
                "fit_alignment_transform_allowed": False,
            },
        ),
        identities,
    )


def _fingerprint(
    identities: tuple[OpmAtomIdentity, ...], atoms: Mapping[OpmAtomIdentity, _Atom]
) -> str:
    quantum = Decimal("0.001")
    lines = []
    for identity in identities:
        coordinates = []
        for value in atoms[identity].coordinates:
            rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_EVEN)
            if rounded == 0:
                rounded = abs(rounded)
            coordinates.append(format(rounded, ".3f"))
        lines.append(
            "\t".join(
                (
                    identity.chain,
                    identity.residue_number,
                    identity.insertion_code,
                    identity.residue_name,
                    identity.atom_name,
                    identity.resolved_altloc,
                    *coordinates,
                )
            )
        )
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def fingerprint_structure_context(structure_context: StructureContext) -> str:
    """Return the shared legacy-PDB coordinate fingerprint used by comparison reports."""

    current = _parse_pdb(structure_context.pdb_payload, "current_structure", require_dummy=False)
    identities = tuple(sorted(current.atoms))
    if not identities:
        raise OrientationError("Current structure contains no fingerprintable protein atoms.")
    return _fingerprint(identities, current.atoms)


def import_opm_orientation(
    opm_pdb: bytes,
    structure_context: StructureContext,
    *,
    metadata: Mapping[str, object] | None = None,
    expected_record_id: str | None = None,
) -> OpmImportResult:
    """Resolve explicit OPM PDB bytes only when already in the current coordinate frame."""

    supplied_metadata = dict(metadata or {})
    unexpected = set(supplied_metadata) - {"expected_record_id"}
    if unexpected:
        raise OrientationError("OPM metadata contains unsupported fields.")
    metadata_id = supplied_metadata.get("expected_record_id")
    if (
        expected_record_id is not None
        and metadata_id is not None
        and expected_record_id != metadata_id
    ):
        raise OrientationError("Conflicting expected_record_id values were supplied.")
    record_id = _canonical_record_id(
        expected_record_id if expected_record_id is not None else metadata_id
    )
    if not isinstance(opm_pdb, bytes):
        raise OrientationError("opm_pdb must be exact bytes.")
    source = _source(record_id, opm_pdb)
    try:
        opm = _parse_pdb(opm_pdb, "opm_pdb", require_dummy=True)
        current = _parse_pdb(
            structure_context.pdb_payload, "current_structure", require_dummy=False
        )
        if opm.structure_id not in {None, "", "xxxx", record_id}:
            _failure(
                "rejected", "RECORD_ID_MISMATCH", "OPM HEADER does not match expected_record_id."
            )
        if (
            structure_context.structure_id is not None
            and structure_context.structure_id.lower() != record_id
        ):
            _failure(
                "rejected",
                "CURRENT_ID_MISMATCH",
                "Current structure ID does not match expected_record_id.",
            )
        if structure_context.model_id != 1:
            _failure(
                "unsupported", "MODEL_MISMATCH", "OPM offline comparison supports model 1 only."
            )
        source_geometry, planes, geometry_warnings = _geometry(opm)
        applicability, _ = _identity_metrics(opm, current)
        current_geometry = PlanarGeometryEvidence(
            source_geometry.center,
            source_geometry.normal,
            source_geometry.lower_offset,
            source_geometry.upper_offset,
            DEFAULT_INTERFACE_WIDTH,
            structure_context.coordinate_frame,
        )
        membrane = PlanarMembrane(
            current_geometry.center,
            current_geometry.normal,
            current_geometry.lower_offset,
            current_geometry.upper_offset,
            DEFAULT_INTERFACE_WIDTH,
            "opm_offline_pdb",
            source_version=None,
            confidence="coordinate_verified_identity_only",
            metadata={
                "record_id": record_id,
                "payload_sha256": source.raw_payloads[0].sha256,
                "directional_topology_available": False,
            },
            warnings=tuple(warning.message for warning in geometry_warnings),
        )
        source_scope = StructureScope(
            record_id,
            "1",
            structure_context.biological_assembly,
            opm.chains,
            "legacy_pdb",
            "opm_oriented_pdb",
            applicability.source_fingerprint,
            selected_model=1,
        )
        current_scope = StructureScope(
            structure_context.structure_id or record_id,
            "1",
            structure_context.biological_assembly,
            current.chains,
            "legacy_pdb",
            structure_context.coordinate_frame,
            applicability.current_fingerprint,
            selected_model=1,
        )
        warnings = list(geometry_warnings)
        if opm.structure_id in {None, "", "xxxx"}:
            warnings.append(
                ImportMessage(
                    "HEADER_ID_UNAVAILABLE",
                    "OPM HEADER has no usable record ID; explicit expected_record_id was used.",
                )
            )
        evidence = OpmOrientationEvidence(
            EVIDENCE_MODEL_VERSION,
            ADAPTER_NAME,
            ADAPTER_VERSION,
            source,
            source_scope,
            current_scope,
            source_geometry,
            current_geometry,
            planes,
            applicability,
            False,
            raw_metadata={
                "dum_label_semantics": "N/O distinguish boundary surfaces only; no biological sidedness inferred",
                "half_thickness_remark": opm.half_thickness_remark,
                "interface_width": DEFAULT_INTERFACE_WIDTH,
                "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
                "fingerprint_version": FINGERPRINT_VERSION,
            },
            warnings=tuple(warnings),
        )
        return OpmImportResult("imported", source, evidence, membrane)
    except _AdapterFailure as exc:
        return OpmImportResult(exc.status, source, messages=(exc.issue,))
    except OrientationError as exc:
        return OpmImportResult(
            "rejected", source, messages=(ImportMessage("INVALID_DOMAIN_EVIDENCE", str(exc)),)
        )


__all__ = [
    "ADAPTER_NAME",
    "ADAPTER_VERSION",
    "IDENTITY_LIMIT",
    "OpmBoundaryPlaneEvidence",
    "OpmIdentityApplicability",
    "OpmImportResult",
    "OpmOrientationEvidence",
    "fingerprint_structure_context",
    "import_opm_orientation",
]
