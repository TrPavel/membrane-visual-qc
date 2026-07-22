"""Headless exact-artifact Stage 4C rendering and coordinate-preservation smoke."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

from pymol import cmd


artifact_root = Path(os.environ["MVQC_ARTIFACT_ROOT"]).resolve()
fixture_root = Path(os.environ["MVQC_FIXTURE_ROOT"]).resolve()
report_path = Path(os.environ["MVQC_COMPARISON_REPORT"]).resolve()
png_path = Path(os.environ["MVQC_COMPARISON_PNG"]).resolve()
sys.path.insert(0, str(artifact_root))

from membrane_vqc import __version__  # noqa: E402
from membrane_vqc.comparison_pymol import (  # noqa: E402
    capture_comparison_snapshot,
    clear_comparison_boundaries,
    comparison_snapshot_is_current,
    show_comparison_boundaries,
)
from membrane_vqc.comparison_report import (  # noqa: E402
    ComparisonPayloadDigest,
    ComparisonReportSource,
    SelectedObjectEvidence,
    build_comparison_report,
    export_comparison_report,
)
from membrane_vqc.comparison_worker import (  # noqa: E402
    ComparisonRequest,
    ComparisonWorkerFailure,
    ComparisonWorkerOrchestrator,
    comparable_orientation,
)
from membrane_vqc.commands import (  # noqa: E402
    mvqc_check,
    mvqc_check_orientation,
    mvqc_check_pdbtm,
    mvqc_clear,
)
from membrane_vqc.pymol_adapter import MVQC_COMPARISON_NAMES  # noqa: E402


def report_source(source_key, imported):
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


assert Path(sys.modules["membrane_vqc"].__file__).resolve().is_relative_to(artifact_root)
expected_version = os.environ.get("MVQC_EXPECTED_VERSION", __version__)
assert __version__ == expected_version
cmd.reinitialize()
cmd.load(str(fixture_root / "pdbtm_original_test.pdb"), "stage4c_test")
before = tuple(tuple(float(value) for value in row) for row in cmd.get_coords("stage4c_test"))
snapshot = capture_comparison_snapshot("stage4c_test", cmd_obj=cmd)
request = ComparisonRequest(
    snapshot.structure_context,
    (fixture_root / "pdbtm_api_v1_test.json").read_bytes(),
    (fixture_root / "pdbtm_transformed_test.pdb").read_bytes(),
    fixture_root / "opm_oriented_test.pdb",
    "test",
)
result = ComparisonWorkerOrchestrator().compare(request)
assert not isinstance(result, ComparisonWorkerFailure), result
assert result.pdbtm.status == result.opm.status == "imported"
assert result.comparison.comparable is True
assert comparison_snapshot_is_current(snapshot, "stage4c_test", cmd_obj=cmd)

pdbtm_input = comparable_orientation(result.pdbtm, "pdbtm")
opm_input = comparable_orientation(result.opm, "opm")
scope = opm_input.scope
report = build_comparison_report(
    generated_at="2026-07-22T12:00:00Z",
    software_name="Membrane Visual QC",
    software_version=expected_version,
    software_commit="exact-artifact-smoke",
    python_version=sys.version.split()[0],
    pymol_version=str(cmd.get_version()[0]),
    platform="Windows-10-build-26200",
    selected_object=SelectedObjectEvidence(
        "test",
        "1",
        None,
        scope.chains,
        "pymol_current_object",
        snapshot.coordinate_fingerprint,
        len(before),
    ),
    first_source=report_source("pdbtm", result.pdbtm),
    second_source=report_source("opm", result.opm),
    comparison=result.comparison,
)
export_comparison_report(report, report_path)
show_comparison_boundaries(
    result.pdbtm.membrane,
    result.opm.membrane,
    snapshot,
    "stage4c_test",
    cmd_obj=cmd,
)
names = set(cmd.get_names("objects"))
assert set(MVQC_COMPARISON_NAMES) <= names
cmd.bg_color("white")
cmd.show("cartoon", "stage4c_test")
cmd.set("two_sided_lighting", 1)
cmd.set("ray_shadows", 0)
cmd.zoom("all", buffer=5.0)
cmd.turn("x", 60)
cmd.refresh()
cmd.png(str(png_path), width=1200, height=900, ray=1)
after = tuple(tuple(float(value) for value in row) for row in cmd.get_coords("stage4c_test"))
assert before == after
clear_comparison_boundaries(cmd)
remaining = set(cmd.get_names("objects"))
assert not (set(MVQC_COMPARISON_NAMES) & remaining)
assert "stage4c_test" in remaining
legacy_report = mvqc_check(selection="stage4c_test", ligand="", quiet=1)
assert legacy_report["schema_version"] == "1.1"
planar_report = mvqc_check_orientation(
    selection="stage4c_test",
    orientation_file=str(fixture_root.parents[1] / "demo" / "rotated_1ubq_orientation.json"),
    ligand="",
    quiet=1,
)
assert planar_report["schema_version"] == "1.1"
pdbtm_report = mvqc_check_pdbtm(
    selection="stage4c_test",
    pdbtm_json=str(fixture_root / "pdbtm_api_v1_test.json"),
    transformed_pdb=str(fixture_root / "pdbtm_transformed_test.pdb"),
    ligand="",
    quiet=1,
)
assert pdbtm_report["schema_version"] == "1.3"
assert before == tuple(
    tuple(float(value) for value in row) for row in cmd.get_coords("stage4c_test")
)
mvqc_clear()
assert "stage4c_test" in set(cmd.get_names("objects"))
print(
    json.dumps(
        {
            "artifact_root": str(artifact_root),
            "band": result.comparison.band,
            "coordinate_fingerprint": snapshot.coordinate_fingerprint,
            "coordinate_preserved": before == after,
            "legacy_schema": legacy_report["schema_version"],
            "metrics": result.comparison.metrics.as_dict(),
            "pdbtm_schema": pdbtm_report["schema_version"],
            "planar_schema": planar_report["schema_version"],
            "png": str(png_path),
            "report": str(report_path),
        },
        sort_keys=True,
    )
)
