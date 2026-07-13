"""Validate generated MVQC example reports against the published JSON Schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


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
        default=Path("schemas/mvqc-report-1.0.schema.json"),
    )
    args = parser.parse_args()
    reports = args.reports or sorted(Path("reports").glob("*_mvqc.json"))
    if not reports:
        parser.error("no report files were supplied or discovered")
    validate_reports(args.schema, reports)
    print(f"Validated {len(reports)} report(s) against {args.schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
