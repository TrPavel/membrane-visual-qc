import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from membrane_vqc.comparison_report import (
    ComparisonPayloadDigest,
    ComparisonReportSource,
    SelectedObjectEvidence,
    build_comparison_report,
    export_comparison_report,
    validate_comparison_report,
)
from membrane_vqc.errors import ReportError
from membrane_vqc.orientation_comparison import ComparableOrientation, compare_orientations
from membrane_vqc.orientation_sources import PlanarGeometryEvidence, StructureScope

ROOT = Path(__file__).resolve().parents[1]
OLD_SCHEMA_HASHES = {
    "1.0": "5153097dde8fda81a4348243d7f940642310e1e9c1fb58b6533456f3722d8710",
    "1.1": "86af40c08cd8c3d1bf3bbe86f359b648384704a84e43748b548bc0c28f5ebecf",
    "1.2": "96bacd127dfd6204bc9bb5ddbd6583539ffc99c6443c8f995c252fa96f0d4430",
    "1.3": "6ee153bc402765a9418a72c1f08fc1e41d213e3e7442ab6b2a726813391cadfc",
    "1.4": "ee3bc91b2ba2c32814aad61eb69ed8413bae9460c33cb5d69d839335ff6e698e",
}


def _input(key, *, center=(0.0, 0.0, 0.0)):
    scope = StructureScope("1abc", "1", "1", ("A",), "legacy_pdb", "pymol_current_object", "f" * 64)
    geometry = PlanarGeometryEvidence(
        center, (0.0, 0.0, 1.0), -10.0, 10.0, 2.0, "pymol_current_object"
    )
    return ComparableOrientation(key, True, scope, geometry, "identity", 100, 20)


def _source(key, comparison_input):
    return ComparisonReportSource(
        key,
        "PDBTM" if key == "pdbtm" else "OPM",
        f"{key}_offline",
        "1",
        "1abc",
        "1017" if key == "pdbtm" else None,
        "3.2.134" if key == "pdbtm" else None,
        ("b" if key == "pdbtm" else "c") * 64,
        comparison_input,
        (ComparisonPayloadDigest(f"{key}_evidence", "d" * 64, 123, "text/plain"),),
    )


def _report():
    first = _input("pdbtm")
    second = _input("opm", center=(1.0, 0.0, 0.0))
    return build_comparison_report(
        generated_at="2026-07-22T12:00:00Z",
        software_name="Membrane Visual QC",
        software_version="0.5.0",
        software_commit="e" * 40,
        python_version="3.10.20",
        pymol_version="3.1.8",
        platform="Windows-10",
        selected_object=SelectedObjectEvidence(
            "1abc", "1", "1", ("A",), "pymol_current_object", "f" * 64, 100
        ),
        first_source=_source("pdbtm", first),
        second_source=_source("opm", second),
        comparison=compare_orientations(first, second),
    )


def test_schema_1_5_is_valid_and_accepts_deterministic_report():
    schema = json.loads((ROOT / "schemas" / "mvqc-report-1.5.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    report = _report()
    Draft202012Validator(schema).validate(report)
    assert report == _report()
    assert report["report_type"] == "orientation_source_comparison"


def test_report_has_no_winner_consensus_or_biological_verdict():
    interpretation = _report()["comparison"]["interpretation"]
    assert interpretation["preferred_source"] is None
    assert interpretation["consensus"] is False
    assert interpretation["ranking"] is False
    assert interpretation["biological_verdict"] is False


def test_report_contains_digests_but_no_paths_or_raw_payloads():
    serialized = json.dumps(_report(), sort_keys=True)
    assert "sha256" in serialized
    assert "raw_payload" not in serialized
    assert "C:\\\\" not in serialized
    assert "file://" not in serialized
    with pytest.raises(ReportError, match="local path"):
        ComparisonReportSource(
            "opm",
            "OPM",
            "opm",
            "1",
            "C:\\secret\\1abc.pdb",
            None,
            None,
            "a" * 64,
            _input("opm"),
            (ComparisonPayloadDigest("opm", "b" * 64, 1),),
        )
    with pytest.raises(ReportError, match="local path"):
        ComparisonReportSource(
            "opm",
            "OPM loaded from C:\\Users\\alice\\secret.pdb",
            "opm",
            "1",
            "1abc",
            None,
            None,
            "a" * 64,
            _input("opm"),
            (ComparisonPayloadDigest("opm", "b" * 64, 1),),
        )


def test_selected_object_fingerprint_must_bind_every_applicable_source():
    report = _report()
    report["selected_object"]["coordinate_fingerprint"] = "0" * 64

    with pytest.raises(ReportError, match="fingerprint contradicts"):
        validate_comparison_report(report)


def test_semantic_validator_rejects_tampered_metric_and_source_order():
    metric = copy.deepcopy(_report())
    metric["comparison"]["metrics"]["center_displacement_angstrom"] = 99.0
    with pytest.raises(ReportError, match="does not match"):
        validate_comparison_report(metric)
    order = copy.deepcopy(_report())
    order["sources"].reverse()
    with pytest.raises(ReportError, match="ordered"):
        validate_comparison_report(order)


def test_schema_rejects_unknown_fields_and_verdict_mutation():
    schema = json.loads((ROOT / "schemas" / "mvqc-report-1.5.schema.json").read_text())
    validator = Draft202012Validator(schema)
    extra = copy.deepcopy(_report())
    extra["local_path"] = "hidden"
    with pytest.raises(ValidationError):
        validator.validate(extra)
    verdict = copy.deepcopy(_report())
    verdict["comparison"]["interpretation"]["biological_verdict"] = True
    with pytest.raises(ValidationError):
        validator.validate(verdict)
    with pytest.raises(ReportError, match="unexpected field set"):
        validate_comparison_report(extra)


def test_export_is_canonical_and_repeatable(tmp_path):
    report = _report()
    first = export_comparison_report(report, tmp_path / "one.json").read_bytes()
    second = export_comparison_report(report, tmp_path / "two.json").read_bytes()
    assert first == second
    assert first.endswith(b"\n")
    assert json.loads(first) == report


def test_existing_schema_hashes_are_unchanged():
    for version, expected in OLD_SCHEMA_HASHES.items():
        payload = (ROOT / "schemas" / f"mvqc-report-{version}.schema.json").read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected


def test_synthetic_example_is_reproducible_and_semantically_valid():
    from scripts.generate_stage4c_example import build_example

    retained = json.loads(
        (ROOT / "reports" / "source_comparison_synthetic_mvqc.json").read_text("utf-8")
    )
    commit = retained["software"]["commit"]
    # The old development fixture used a descriptive placeholder. Release
    # generation replaces it with an exact commit, at which point this test
    # provides full deterministic reproduction of the retained bytes.
    if len(commit) == 40 and set(commit) <= set("0123456789abcdef"):
        assert retained == build_example(
            software_version=retained["software"]["version"],
            software_commit=commit,
            generated_at=retained["generated_at"],
            python_version=retained["runtime"]["python"],
            pymol_version=retained["runtime"]["pymol"],
            platform=retained["runtime"]["platform"],
        )
    else:
        assert commit == "synthetic-example"
    validate_comparison_report(retained)


def test_pdbtm_cached_source_retains_exact_safe_acquisition_provenance():
    comparison_input = _input("pdbtm")
    payloads = (
        ComparisonPayloadDigest("pdbtm_json", "1" * 64, 10, "application/json"),
        ComparisonPayloadDigest("transformed_pdb", "2" * 64, 20, "chemical/x-pdb"),
    )
    acquisition = {
        "model_version": "1",
        "provider_kind": "pdbtm_api_v1",
        "provider_name": "PDBTM",
        "provider_contract": "pdbtm-cache-v1",
        "canonical_record_id": "1abc",
        "acquisition_mode": "direct_https_provider_fetch",
        "consumption_mode": "active_cache_read",
        "pair_id": "3" * 64,
        "snapshot_id": "4" * 64,
        "cache_generation": 2,
        "provider_versions": {"resource_version": "1017", "software_version": "3.2.134"},
        "validated_at": "2026-07-22T12:00:00Z",
        "payloads": [
            {"role": item.role, "sha256": item.sha256, "byte_size": item.byte_size}
            for item in payloads
        ],
        "pair_self_consistency": {
            "adapter_name": "pdbtm_api_v1_offline",
            "adapter_version": "1",
            "method": "identity",
            "coordinate_frame": "pdbtm_transformed_companion",
            "rmsd": 0.0,
            "maximum_residual": 0.0,
            "fingerprint_match": True,
        },
        "object_applicability": {
            "established": False,
            "scope": "not_evaluated",
            "statement": "Cache evidence does not establish selected-object applicability.",
        },
    }
    source = ComparisonReportSource(
        "pdbtm",
        "PDBTM",
        "pdbtm_api_v1_offline",
        "1",
        "1abc",
        "1017",
        "3.2.134",
        "5" * 64,
        comparison_input,
        payloads,
        acquisition,
    )
    assert source.as_dict()["pdbtm_cached_acquisition"] == acquisition

    for field, invalid in {
        "model_version": "999",
        "provider_name": "not PDBTM",
        "acquisition_mode": "offline",
        "consumption_mode": "implicit",
        "cache_generation": -1,
        "validated_at": "not-a-time",
    }.items():
        broken = copy.deepcopy(acquisition)
        broken[field] = invalid
        with pytest.raises(ReportError):
            ComparisonReportSource(
                "pdbtm",
                "PDBTM",
                "pdbtm_api_v1_offline",
                "1",
                "1abc",
                "1017",
                "3.2.134",
                "5" * 64,
                comparison_input,
                payloads,
                broken,
            )

    full = copy.deepcopy(acquisition)
    full["payloads"] = [
        {
            **item,
            "content_type": {"media_type": "application/octet-stream", "charset": None},
            "requested_url": f"https://pdbtm.unitmp.org/{item['role']}",
            "final_url": f"https://pdbtm.unitmp.org/{item['role']}",
            "requested_at": "2026-07-22T11:59:58Z",
            "completed_at": "2026-07-22T11:59:59Z",
            "etag": None,
            "last_modified": None,
            "transport_verification": "direct_https_tls_verified",
        }
        for item in acquisition["payloads"]
    ]
    projected = ComparisonReportSource(
        "pdbtm",
        "PDBTM",
        "pdbtm_api_v1_offline",
        "1",
        "1abc",
        "1017",
        "3.2.134",
        "5" * 64,
        comparison_input,
        payloads,
        full,
    ).as_dict()["pdbtm_cached_acquisition"]
    assert projected["payloads"] == acquisition["payloads"]
    assert "requested_url" not in json.dumps(projected)

    secret = copy.deepcopy(full)
    secret["provider_versions"]["authorization"] = "Bearer TOP-SECRET"
    with pytest.raises(ReportError, match="provider_versions"):
        ComparisonReportSource(
            "pdbtm",
            "PDBTM",
            "pdbtm_api_v1_offline",
            "1",
            "1abc",
            "1017",
            "3.2.134",
            "5" * 64,
            comparison_input,
            payloads,
            secret,
        )


def test_opm_source_cannot_claim_pdbtm_cached_acquisition():
    source = _source("opm", _input("opm"))
    with pytest.raises(ReportError, match="Only PDBTM"):
        ComparisonReportSource(
            source.source_key,
            source.provider_name,
            source.adapter_name,
            source.adapter_version,
            source.record_id,
            source.resource_version,
            source.software_version,
            source.evidence_id,
            source.comparison_input,
            source.payloads,
            {"provider_kind": "pdbtm_api_v1"},
        )
