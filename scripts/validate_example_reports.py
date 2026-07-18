"""Validate generated MVQC example reports against the published JSON Schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA_BY_VERSION = {
    "1.0": Path("schemas/mvqc-report-1.0.schema.json"),
    "1.1": Path("schemas/mvqc-report-1.1.schema.json"),
    "1.2": Path("schemas/mvqc-report-1.2.schema.json"),
    "1.3": Path("schemas/mvqc-report-1.3.schema.json"),
}


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
