"""Validate generated MVQC example reports against the published JSON Schema."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from membrane_vqc.report import validate_stage4_report_semantics  # noqa: E402
from membrane_vqc.comparison_report import validate_comparison_report  # noqa: E402

SCHEMA_BY_VERSION = {
    "1.0": Path("schemas/mvqc-report-1.0.schema.json"),
    "1.1": Path("schemas/mvqc-report-1.1.schema.json"),
    "1.2": Path("schemas/mvqc-report-1.2.schema.json"),
    "1.3": Path("schemas/mvqc-report-1.3.schema.json"),
    "1.4": Path("schemas/mvqc-report-1.4.schema.json"),
    "1.5": Path("schemas/mvqc-report-1.5.schema.json"),
}

V050_RELEASE_REPORTS = {
    Path("reports/pdbtm_local_v050_mvqc.json"): "1.3",
    Path("reports/pdbtm_acquisition_v050_mvqc.json"): "1.4",
    Path("reports/source_comparison_synthetic_mvqc.json"): "1.5",
}
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)(?:(?<![a-z0-9])[a-z]:[\\/]|\\\\[^\\]+[\\/][^\\]+)")
_IP_ADDRESS = re.compile(
    r"(?<![0-9])(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})"
    r"(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}(?![0-9])"
)
_SENSITIVE_KEY = re.compile(
    r"(?i)(?:password|passwd|secret|token|credential|authorization|cookie|"
    r"proxy|hostname|user(?:name)?|traceback|exception|cache_(?:dir|path|root))"
)
_RAW_MATERIAL_KEY = re.compile(
    r"(?i)^(?:body|payload_body|provider_payload|provider_response|raw_response)$"
)


def default_report_paths(root: Path = Path("reports")) -> list[Path]:
    """Return generated fixtures plus retained manual-acceptance evidence when present."""
    paths = set(root.glob("*_mvqc.json"))
    manual_evidence = root / "manual_stage2_check.json"
    if manual_evidence.is_file():
        paths.add(manual_evidence)
    return sorted(paths)


def validate_reports(schema_path: Path, report_paths: list[Path]) -> None:
    """Raise on an invalid schema or the first invalid report."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - dependency failure is user-facing
        raise SystemExit(
            "jsonschema is required for report validation; install the project dev dependencies."
        ) from exc

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for report_path in report_paths:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        validator.validate(report)
        if report.get("report_type") == "orientation_source_comparison":
            validate_comparison_report(report)
        if "evidence" in report.get("orientation", {}):
            validate_stage4_report_semantics(report)


def validate_reports_by_version(report_paths: list[Path]) -> dict[str, int]:
    """Validate each report against the schema version it declares."""
    grouped: dict[str, list[Path]] = {}
    for report_path in report_paths:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        version = str(report.get("schema_version", ""))
        if version not in SCHEMA_BY_VERSION:
            raise ValueError(
                f"{report_path} declares unsupported report schema version {version!r}"
            )
        grouped.setdefault(version, []).append(report_path)
    for version, paths in grouped.items():
        validate_reports(SCHEMA_BY_VERSION[version], paths)
    return {version: len(paths) for version, paths in sorted(grouped.items())}


def validate_retained_report_privacy(report: object, *, label: str = "report") -> None:
    """Reject environment, credential, raw-error, and local-path leakage."""

    def walk(value: object, location: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if _SENSITIVE_KEY.search(str(key)) or _RAW_MATERIAL_KEY.fullmatch(str(key)):
                    raise ValueError(f"{label}: sensitive field at {location}.{key}")
                walk(item, f"{location}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{location}[{index}]")
        elif isinstance(value, str):
            if (
                value.startswith(("/", "file://"))
                or _WINDOWS_ABSOLUTE_PATH.search(value)
                or _IP_ADDRESS.search(value)
                or "Traceback (most recent call last)" in value
                or value.startswith(("ATOM  ", "HETATM"))
            ):
                raise ValueError(f"{label}: sensitive value at {location}")

    walk(report, "$")


def v050_release_report_inventory(
    root: Path, *, software_version: str = "0.5.0"
) -> list[dict[str, object]]:
    """Validate and inventory the three reports representing the v0.5 release."""

    paths = [root / path for path in V050_RELEASE_REPORTS]
    validate_reports_by_version(paths)
    inventory = []
    for relative, expected_schema in V050_RELEASE_REPORTS.items():
        path = root / relative
        raw = path.read_bytes()
        report = json.loads(raw)
        if report.get("schema_version") != expected_schema:
            raise ValueError(f"{relative} does not declare schema {expected_schema}")
        software = report.get("software")
        if not isinstance(software, dict) or software.get("version") != software_version:
            raise ValueError(f"{relative} does not record software {software_version}")
        commit = str(software.get("commit", ""))
        if not _COMMIT.fullmatch(commit):
            raise ValueError(f"{relative} does not record an exact generation commit")
        if report.get("version", software_version) != software_version:
            raise ValueError(f"{relative} has a contradictory legacy version")
        validate_retained_report_privacy(report, label=str(relative))
        inventory.append(
            {
                "path": relative.as_posix(),
                "schema_version": expected_schema,
                "software_version": software_version,
                "generation_commit": commit,
                "byte_size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reports",
        nargs="*",
        type=Path,
        help="Report JSON files (default: reports/*_mvqc.json)",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="Override schema for all reports (default: use each report's schema_version)",
    )
    args = parser.parse_args()
    reports = args.reports or default_report_paths()
    if not reports:
        parser.error("no report files were supplied or discovered")
    if args.schema is not None:
        validate_reports(args.schema, reports)
        print(f"Validated {len(reports)} report(s) against {args.schema}")
    else:
        counts = validate_reports_by_version(reports)
        summary = ", ".join(f"schema {version}: {count}" for version, count in counts.items())
        print(f"Validated {len(reports)} report(s) ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
