"""Qt- and PyMOL-free orchestration for explicit offline source comparison."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import threading
from collections.abc import Mapping
from typing import Callable, Protocol

from .errors import MVQCError
from .orientation_comparison import ComparableOrientation
from .orientation_sources import ImportMessage, StructureContext
from .pdbtm_adapter import import_pdbtm_orientation


MAX_OPM_PAYLOAD_BYTES = 5 * 1024 * 1024
_RECORD_ID = re.compile(r"^[A-Za-z0-9]{4}$")


@dataclass(frozen=True, slots=True)
class ComparisonRequest:
    """One immutable, explicit comparison request captured by the GUI thread."""

    structure_context: StructureContext
    pdbtm_json_payload: bytes
    pdbtm_transformed_pdb_payload: bytes
    opm_path: Path
    expected_record_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.structure_context, StructureContext):
            raise ValueError("structure_context must be an immutable StructureContext.")
        for name in ("pdbtm_json_payload", "pdbtm_transformed_pdb_payload"):
            if not isinstance(getattr(self, name), bytes):
                raise ValueError(f"{name} must contain exact bytes.")
        path_text = str(self.opm_path).strip()
        if not path_text:
            raise ValueError("opm_path must not be empty.")
        path = Path(path_text)
        object.__setattr__(self, "opm_path", path)
        record_id = str(self.expected_record_id).strip().lower()
        if not _RECORD_ID.fullmatch(record_id):
            raise ValueError("expected_record_id must be a four-character PDB identifier.")
        object.__setattr__(self, "expected_record_id", record_id)


@dataclass(frozen=True, slots=True)
class ComparisonWorkerResult:
    """Plain-data result delivered to the main thread for review and rendering."""

    pdbtm: "OrientationImportLike"
    opm: "OrientationImportLike"
    comparison: object
    opm_byte_size: int
    opm_sha256: str
    expected_record_id: str
    pdbtm_json_byte_size: int
    pdbtm_json_sha256: str
    pdbtm_transformed_pdb_byte_size: int
    pdbtm_transformed_pdb_sha256: str


@dataclass(frozen=True, slots=True)
class ComparisonWorkerFailure:
    """Stable, path-free failure safe to display at the GUI boundary."""

    code: str
    message: str
    retryable: bool = False


class ComparisonOperation:
    """Thread-safe cooperative cancellation token owned by the GUI."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()

    def request_cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()


class OrientationImportLike(Protocol):
    """Structural result shared by provider-specific orientation adapters."""

    @property
    def status(self) -> str: ...

    @property
    def evidence(self) -> object | None: ...

    @property
    def messages(self) -> tuple[ImportMessage, ...]: ...


PdbtmLoader = Callable[..., OrientationImportLike]
OpmLoader = Callable[..., OrientationImportLike]
Comparer = Callable[..., object]


class ComparisonWorkerOrchestrator:
    """Read one bounded local OPM file and compare two validated sources."""

    def __init__(
        self,
        *,
        pdbtm_loader: PdbtmLoader = import_pdbtm_orientation,
        opm_loader: OpmLoader | None = None,
        comparer: Comparer | None = None,
    ) -> None:
        self._pdbtm_loader = pdbtm_loader
        self._opm_loader = opm_loader
        self._comparer = comparer

    def compare(
        self, request: ComparisonRequest, operation: ComparisonOperation | None = None
    ) -> ComparisonWorkerResult | ComparisonWorkerFailure:
        """Return a result or a stable safe failure; never raise raw local diagnostics."""
        operation = operation or ComparisonOperation()
        if operation.is_cancelled():
            return _cancelled()
        payload = _read_opm_payload(request.opm_path)
        if isinstance(payload, ComparisonWorkerFailure):
            return payload
        if operation.is_cancelled():
            return _cancelled()

        try:
            pdbtm = self._pdbtm_loader(
                request.pdbtm_json_payload,
                request.pdbtm_transformed_pdb_payload,
                request.structure_context,
                metadata={"expected_record_id": request.expected_record_id},
            )
            if operation.is_cancelled():
                return _cancelled()
            opm_loader = self._opm_loader
            if opm_loader is None:
                from .opm_adapter import import_opm_orientation

                opm_loader = import_opm_orientation
            opm = opm_loader(
                payload,
                request.structure_context,
                expected_record_id=request.expected_record_id,
            )
            if operation.is_cancelled():
                return _cancelled()
            comparer = self._comparer
            if comparer is None:
                from .orientation_comparison import compare_orientations

                comparer = compare_orientations
            comparison = comparer(
                comparable_orientation(pdbtm, "pdbtm"),
                comparable_orientation(opm, "opm"),
            )
        except (MVQCError, TypeError, ValueError):
            return ComparisonWorkerFailure(
                "SOURCE_INVALID",
                "One of the selected orientation sources could not be validated.",
            )
        except Exception:
            return ComparisonWorkerFailure(
                "COMPARISON_FAILED",
                "The geometric source comparison could not be completed.",
            )
        if operation.is_cancelled():
            return _cancelled()
        return ComparisonWorkerResult(
            pdbtm=pdbtm,
            opm=opm,
            comparison=comparison,
            opm_byte_size=len(payload),
            opm_sha256=hashlib.sha256(payload).hexdigest(),
            expected_record_id=request.expected_record_id,
            pdbtm_json_byte_size=len(request.pdbtm_json_payload),
            pdbtm_json_sha256=hashlib.sha256(request.pdbtm_json_payload).hexdigest(),
            pdbtm_transformed_pdb_byte_size=len(request.pdbtm_transformed_pdb_payload),
            pdbtm_transformed_pdb_sha256=hashlib.sha256(
                request.pdbtm_transformed_pdb_payload
            ).hexdigest(),
        )


def _read_opm_payload(path: Path) -> bytes | ComparisonWorkerFailure:
    try:
        if not path.is_file():
            return ComparisonWorkerFailure(
                "OPM_FILE_NOT_FOUND", "The selected OPM file does not exist or is not a file."
            )
        size = path.stat().st_size
    except OSError:
        return ComparisonWorkerFailure(
            "OPM_FILE_UNREADABLE", "The selected OPM file could not be inspected."
        )
    if size > MAX_OPM_PAYLOAD_BYTES:
        return ComparisonWorkerFailure(
            "OPM_PAYLOAD_TOO_LARGE", "The selected OPM file exceeds the 5 MiB limit."
        )
    try:
        payload = path.read_bytes()
    except OSError:
        return ComparisonWorkerFailure(
            "OPM_FILE_UNREADABLE", "The selected OPM file could not be read."
        )
    if len(payload) > MAX_OPM_PAYLOAD_BYTES:
        return ComparisonWorkerFailure(
            "OPM_PAYLOAD_TOO_LARGE", "The selected OPM file exceeds the 5 MiB limit."
        )
    return payload


def comparable_orientation(result: OrientationImportLike, source_key: str) -> ComparableOrientation:
    """Project provider-specific evidence into the comparison-facing model."""
    warning_codes = {f"{source_key}:{item.code}" for item in result.messages}
    if result.status != "imported" or result.evidence is None:
        warning_codes.add(f"{source_key}:status:{result.status}")
        return ComparableOrientation(
            source_key=source_key,
            applicable=False,
            warnings=tuple(sorted(warning_codes)),
        )
    evidence = result.evidence
    warning_codes.update(f"{source_key}:{item.code}" for item in evidence.warnings)
    mapping = getattr(evidence, "mapping", None)
    applicability = getattr(evidence, "applicability", None)
    if mapping is not None:
        method = mapping.method
        matched_atom_count = _first_non_negative_int(mapping.metrics, "matched_atom_count")
        matched_residue_count = _first_non_negative_int(mapping.metrics, "matched_residue_count")
    elif applicability is not None:
        method = applicability.method
        matched_atom_count = applicability.matched_atom_count
        matched_residue_count = applicability.matched_residue_count
    else:
        raise ValueError("Imported orientation evidence has no applicability model.")
    return ComparableOrientation(
        source_key=source_key,
        applicable=True,
        scope=evidence.current_scope,
        geometry=evidence.current_geometry,
        applicability_method=method,
        matched_atom_count=matched_atom_count,
        matched_residue_count=matched_residue_count,
        warnings=tuple(sorted(warning_codes)),
    )


def _first_non_negative_int(value: object, key: str) -> int | None:
    """Find one deterministic coverage count in a nested mapping."""
    if not isinstance(value, Mapping):
        return None
    direct = value.get(key)
    if type(direct) is int and direct >= 0:
        return direct
    for nested_key in sorted(value, key=str):
        found = _first_non_negative_int(value[nested_key], key)
        if found is not None:
            return found
    return None


def _cancelled() -> ComparisonWorkerFailure:
    return ComparisonWorkerFailure("CANCELLED", "The comparison was cancelled.", retryable=True)
