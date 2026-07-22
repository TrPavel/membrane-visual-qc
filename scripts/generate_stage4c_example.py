"""Print the deterministic synthetic Stage 4C comparison report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from membrane_vqc.comparison_report import (
    ComparisonPayloadDigest,
    ComparisonReportSource,
    SelectedObjectEvidence,
    build_comparison_report,
)
from membrane_vqc.comparison_worker import (
    ComparisonRequest,
    ComparisonWorkerFailure,
    ComparisonWorkerOrchestrator,
    comparable_orientation,
)
from membrane_vqc.opm_adapter import fingerprint_structure_context
from membrane_vqc.orientation_sources import StructureContext


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"


def _source(source_key: str, imported: object) -> ComparisonReportSource:
    evidence = imported.evidence
    source = imported.source
    evidence_id = hashlib.sha256(
        json.dumps(
            evidence.as_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    return ComparisonReportSource(
        source_key,
        source.name,
        evidence.adapter_name,
        evidence.adapter_version,
        source.record_id,
        source.resource_version,
        source.software_version,
        evidence_id,
        comparable_orientation(imported, source_key),
        tuple(
            ComparisonPayloadDigest(item.role, item.sha256, item.byte_size, item.media_type)
            for item in source.raw_payloads
        ),
    )


def build_example() -> dict[str, object]:
    current_payload = (SYNTHETIC / "pdbtm_original_test.pdb").read_bytes()
    context = StructureContext(
        current_payload,
        "test",
        1,
        biological_assembly=None,
        coordinate_frame="pymol_current_object",
    )
    request = ComparisonRequest(
        context,
        (SYNTHETIC / "pdbtm_api_v1_test.json").read_bytes(),
        (SYNTHETIC / "pdbtm_transformed_test.pdb").read_bytes(),
        SYNTHETIC / "opm_oriented_test.pdb",
        "test",
    )
    result = ComparisonWorkerOrchestrator().compare(request)
    if isinstance(result, ComparisonWorkerFailure):
        raise RuntimeError(f"Synthetic comparison failed: {result.code}")
    current_scope = comparable_orientation(result.opm, "opm").scope
    if current_scope is None:
        raise RuntimeError("Synthetic OPM evidence was not applicable.")
    atom_count = sum(line.startswith(b"ATOM  ") for line in current_payload.splitlines())
    return build_comparison_report(
        generated_at="2026-07-22T12:00:00Z",
        software_name="Membrane Visual QC",
        software_version="0.5.0.dev0",
        software_commit="synthetic-example",
        python_version="3.10.20",
        pymol_version="3.1.8",
        platform="Windows-10-build-26200",
        selected_object=SelectedObjectEvidence(
            "test",
            "1",
            None,
            current_scope.chains,
            "pymol_current_object",
            fingerprint_structure_context(context),
            atom_count,
        ),
        first_source=_source("pdbtm", result.pdbtm),
        second_source=_source("opm", result.opm),
        comparison=result.comparison,
    )


def main() -> int:
    print(
        json.dumps(build_example(), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
