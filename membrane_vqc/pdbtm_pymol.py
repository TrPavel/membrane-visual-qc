"""Offline PDBTM command-layer integration for a current PyMOL object."""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any

from .errors import PyMOLAdapterError
from .orientation_sources import OrientationImportResult, StructureContext
from .pdbtm_adapter import MAX_PAYLOAD_BYTES, import_pdbtm_orientation
from .pymol_adapter import get_cmd

_URL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


class PdbtmCommandError(PyMOLAdapterError):
    """Stable user-facing failure at the offline PyMOL command boundary."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")


def read_local_payload(path: str, *, role: str) -> bytes:
    """Read exact bytes from one explicit local regular file within the payload limit."""

    text = str(path).strip()
    if not text:
        raise PdbtmCommandError("LOCAL_PATH_REQUIRED", f"{role} path must not be empty.")
    if _URL_PATTERN.match(text):
        raise PdbtmCommandError("LOCAL_URL_NOT_ALLOWED", f"{role} must be a local file path.")
    source = Path(text)
    try:
        if not source.exists():
            raise PdbtmCommandError("LOCAL_FILE_NOT_FOUND", f"{role} file does not exist.")
        if not source.is_file():
            raise PdbtmCommandError("LOCAL_FILE_NOT_REGULAR", f"{role} path is not a file.")
        size = source.stat().st_size
    except PdbtmCommandError:
        raise
    except OSError as exc:
        raise PdbtmCommandError(
            "LOCAL_FILE_UNREADABLE", f"Could not inspect {role} file: {exc}"
        ) from exc
    if size > MAX_PAYLOAD_BYTES:
        raise PdbtmCommandError("PAYLOAD_TOO_LARGE", f"{role} exceeds the 5 MiB limit.")
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise PdbtmCommandError(
            "LOCAL_FILE_UNREADABLE", f"Could not read {role} file: {exc}"
        ) from exc
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise PdbtmCommandError("PAYLOAD_TOO_LARGE", f"{role} exceeds the 5 MiB limit.")
    return payload


def structure_context_from_pymol(
    selection: str,
    *,
    biological_assembly: str | None = None,
    cmd_obj: object | None = None,
) -> StructureContext:
    """Capture one complete, single-state PyMOL object in its current coordinate frame."""

    selection = str(selection).strip()
    if not selection:
        raise PdbtmCommandError("SELECTION_REQUIRED", "Analysis selection must not be empty.")
    cmd = get_cmd(cmd_obj)
    try:
        objects = tuple(dict.fromkeys(str(name) for name in cmd.get_object_list(selection)))
    except (AttributeError, TypeError, RuntimeError) as exc:
        raise PdbtmCommandError(
            "OBJECT_RESOLUTION_FAILED", "Could not resolve molecular objects from the selection."
        ) from exc
    if not objects:
        raise PdbtmCommandError(
            "OBJECT_COUNT", "Analysis selection must resolve exactly one molecular object; found 0."
        )
    if len(objects) != 1:
        raise PdbtmCommandError(
            "OBJECT_COUNT",
            f"Analysis selection must resolve exactly one molecular object; found {len(objects)}.",
        )
    object_name = objects[0]
    try:
        states = int(cmd.count_states(object_name))
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        raise PdbtmCommandError(
            "STATE_COUNT_FAILED", "Could not determine the current object's state count."
        ) from exc
    if states != 1:
        raise PdbtmCommandError(
            "MULTI_STATE_UNSUPPORTED",
            f"Stage 4A2 requires a single-state object; {object_name!r} has {states} states.",
        )
    try:
        model = cmd.get_model(object_name, state=1)
    except (AttributeError, TypeError, RuntimeError) as exc:
        raise PdbtmCommandError(
            "SNAPSHOT_FAILED", "Could not inspect the complete current molecular object."
        ) from exc
    atoms = tuple(getattr(model, "atom", ()))
    if not atoms:
        raise PdbtmCommandError("OBJECT_EMPTY", "The resolved molecular object contains no atoms.")
    for atom in atoms:
        _validate_legacy_atom_metadata(atom)
    try:
        snapshot = cmd.get_pdbstr(object_name, state=1)
    except (AttributeError, TypeError, RuntimeError) as exc:
        raise PdbtmCommandError(
            "SNAPSHOT_FAILED", "Could not serialize the complete current molecular object."
        ) from exc
    if not isinstance(snapshot, str):
        raise PdbtmCommandError("SNAPSHOT_FAILED", "PyMOL returned a non-text structure snapshot.")
    try:
        payload = snapshot.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PdbtmCommandError(
            "LEGACY_PDB_UNSAFE", "Current object metadata is not ASCII legacy-PDB compatible."
        ) from exc
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise PdbtmCommandError("PAYLOAD_TOO_LARGE", "Current object snapshot exceeds 5 MiB.")
    assembly = str(biological_assembly or "").strip() or None
    return StructureContext(
        payload,
        None,
        1,
        biological_assembly=assembly,
        coordinate_frame="pymol_current_object",
    )


def resolve_pdbtm_from_pymol(
    *,
    selection: str,
    pdbtm_json_path: str,
    transformed_pdb_path: str,
    biological_assembly: str | None = None,
    cmd_obj: object | None = None,
) -> OrientationImportResult:
    """Resolve one accepted offline PDBTM pair against the complete current PyMOL object."""

    json_payload = read_local_payload(pdbtm_json_path, role="pdbtm_json")
    transformed_payload = read_local_payload(transformed_pdb_path, role="transformed_pdb")
    return resolve_pdbtm_from_payloads(
        selection=selection,
        pdbtm_json_payload=json_payload,
        transformed_pdb_payload=transformed_payload,
        biological_assembly=biological_assembly,
        cmd_obj=cmd_obj,
    )


def resolve_pdbtm_from_payloads(
    *,
    selection: str,
    pdbtm_json_payload: bytes,
    transformed_pdb_payload: bytes,
    biological_assembly: str | None = None,
    cmd_obj: object | None = None,
) -> OrientationImportResult:
    """Resolve one accepted PDBTM pair, given already-in-memory exact bytes.

    This is the byte-origin-agnostic sibling of :func:`resolve_pdbtm_from_pymol`
    used by the Stage 4B3 cached-selection path: the caller (a validated
    ``CachedSnapshot``) has already proven pair self-consistency; this
    function only ever establishes *current-object applicability* against the
    live PyMOL object, exactly like the local-file path above.
    """

    context = structure_context_from_pymol(
        selection,
        biological_assembly=biological_assembly,
        cmd_obj=cmd_obj,
    )
    result = import_pdbtm_orientation(
        pdbtm_json_payload,
        transformed_pdb_payload,
        context,
        metadata={
            "json_media_type": "application/json",
            "pdb_media_type": "chemical/x-pdb",
        },
    )
    if result.status != "imported":
        issue = result.messages[0] if result.messages else None
        code = issue.code if issue is not None else "IMPORT_NOT_ACCEPTED"
        message = (
            issue.message if issue is not None else f"PDBTM import status was {result.status}."
        )
        raise PdbtmCommandError(code, message)
    return result


def _validate_legacy_atom_metadata(atom: Any) -> None:
    chain = str(getattr(atom, "chain", "") or "")
    if len(chain) > 1 or (chain and (not chain.isascii() or chain.isspace())):
        raise PdbtmCommandError(
            "CHAIN_NAMESPACE_UNSAFE",
            f"Current chain ID {chain!r} cannot be represented safely in legacy PDB.",
        )
    for field, limit in (("name", 4), ("resn", 3), ("alt", 1)):
        value = str(getattr(atom, field, "") or "")
        if len(value) > limit or not value.isascii():
            raise PdbtmCommandError(
                "LEGACY_PDB_UNSAFE",
                f"Current atom {field} {value!r} is not legacy-PDB compatible.",
            )
    occupancy = getattr(atom, "q", 1.0)
    try:
        occupancy_value = float(occupancy)
    except (TypeError, ValueError) as exc:
        raise PdbtmCommandError(
            "INVALID_OCCUPANCY", "Current atom occupancy must be numeric."
        ) from exc
    if not math.isfinite(occupancy_value):
        raise PdbtmCommandError("INVALID_OCCUPANCY", "Current atom occupancy must be finite.")
