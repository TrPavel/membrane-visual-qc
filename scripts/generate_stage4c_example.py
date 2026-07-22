"""Print the deterministic synthetic Stage 4C comparison report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

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
from membrane_vqc.constants import VERSION


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


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


def build_example(
    *,
    software_commit: str,
    software_version: str = VERSION,
    generated_at: str = "2026-07-22T12:00:00Z",
    python_version: str = "3.10.20",
    pymol_version: str = "3.1.8",
    platform: str = "Windows-10-build-26200",
) -> dict[str, object]:
    """Build the deterministic comparison example for an exact Git commit."""

    if not _COMMIT.fullmatch(software_commit):
        raise ValueError("software_commit must be an exact 40-character lowercase Git SHA")
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
        generated_at=generated_at,
        software_name="Membrane Visual QC",
        software_version=software_version,
        software_commit=software_commit,
        python_version=python_version,
        pymol_version=pymol_version,
        platform=platform,
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
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--software-version", default=VERSION)
    parser.add_argument("--software-commit", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not _COMMIT.fullmatch(args.software_commit):
        parser.error("--software-commit must be an exact 40-character lowercase Git SHA")
    rendered = (
        json.dumps(
            build_example(
                software_version=args.software_version,
                software_commit=args.software_commit,
            ),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
