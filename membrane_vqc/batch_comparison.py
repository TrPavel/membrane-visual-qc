"""Reusable non-GUI assembly for one accepted Stage 4C comparison report."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import platform as platform_module
from typing import Mapping

from .comparison_report import (
    ComparisonPayloadDigest,
    ComparisonReportSource,
    SelectedObjectEvidence,
    build_comparison_report,
)
from .comparison_worker import ComparisonWorkerResult, comparable_orientation
from .constants import PLUGIN_NAME, VERSION
from .pdbtm_report_provenance import build_pdbtm_acquisition_provenance


def _source(
    source_key: str,
    imported: object,
    comparison_input: object,
    fallback_record_id: str,
    fallback_payloads: tuple[ComparisonPayloadDigest, ...],
    cached_acquisition: Mapping[str, object] | None = None,
) -> ComparisonReportSource:
    evidence = imported.evidence
    source = imported.source
    evidence_dict = evidence.as_dict()
    evidence_id = hashlib.sha256(
        json.dumps(evidence_dict, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()
    payloads = (
        tuple(
            ComparisonPayloadDigest(item.role, item.sha256, item.byte_size, item.media_type)
            for item in source.raw_payloads
        )
        if source is not None
        else fallback_payloads
    )
    return ComparisonReportSource(
        source_key,
        source.name if source is not None else source_key.upper(),
        evidence.adapter_name,
        evidence.adapter_version,
        (source.record_id if source is not None else None) or fallback_record_id,
        source.resource_version if source is not None else None,
        source.software_version if source is not None else None,
        evidence_id,
        comparison_input,
        payloads,
        cached_acquisition,
    )


def _chains_and_atom_count(payload: bytes) -> tuple[tuple[str, ...], int]:
    lines = [line for line in payload.splitlines() if line.startswith(b"ATOM  ")]
    chains = tuple(sorted({line[21:22].decode("ascii").strip() or "_" for line in lines}))
    if not lines or not chains:
        raise ValueError("selected-object snapshot has no usable ATOM identities")
    return chains, len(lines)


def build_batch_comparison_report(
    result: ComparisonWorkerResult,
    snapshot: object,
    record_id: str,
    *,
    cached_snapshot: object | None = None,
    software_commit: str = "unavailable",
    pymol_version: str = "unavailable",
) -> dict[str, object]:
    """Build schema 1.5 from explicit local sources without GUI state."""
    pdbtm_input = comparable_orientation(result.pdbtm, "pdbtm")
    opm_input = comparable_orientation(result.opm, "opm")
    cached = (
        build_pdbtm_acquisition_provenance(
            cached_snapshot, consumption_mode="snapshot_cache_read"
        ).as_dict()
        if cached_snapshot is not None
        else None
    )
    pdbtm_source = _source(
        "pdbtm",
        result.pdbtm,
        pdbtm_input,
        record_id,
        (
            ComparisonPayloadDigest(
                "pdbtm_json",
                result.pdbtm_json_sha256,
                result.pdbtm_json_byte_size,
                "application/json",
            ),
            ComparisonPayloadDigest(
                "transformed_pdb",
                result.pdbtm_transformed_pdb_sha256,
                result.pdbtm_transformed_pdb_byte_size,
                "chemical/x-pdb",
            ),
        ),
        cached,
    )
    opm_source = _source(
        "opm",
        result.opm,
        opm_input,
        record_id,
        (
            ComparisonPayloadDigest(
                "opm_pdb", result.opm_sha256, result.opm_byte_size, "chemical/x-pdb"
            ),
        ),
    )
    scope = pdbtm_input.scope or opm_input.scope
    chains, atom_count = _chains_and_atom_count(snapshot.structure_context.pdb_payload)
    return build_comparison_report(
        generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        software_name=PLUGIN_NAME,
        software_version=VERSION,
        software_commit=software_commit,
        python_version=platform_module.python_version(),
        pymol_version=pymol_version,
        platform=platform_module.platform(),
        selected_object=SelectedObjectEvidence(
            (scope.structure_id if scope else None) or record_id,
            scope.model_id if scope else str(snapshot.structure_context.model_id),
            scope.biological_assembly if scope else snapshot.structure_context.biological_assembly,
            scope.chains if scope else chains,
            snapshot.structure_context.coordinate_frame,
            snapshot.coordinate_fingerprint,
            atom_count,
        ),
        first_source=pdbtm_source,
        second_source=opm_source,
        comparison=result.comparison,
    )
