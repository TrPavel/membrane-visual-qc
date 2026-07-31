"""Pure validation CLI for versioned Stage 5A batch plans."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .batch_contracts import MAX_JOBS, MAX_PLAN_BYTES, PLAN_CONTRACT, load_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate without importing PyMOL")
    validate.add_argument("plan", type=Path)
    args = parser.parse_args(argv)
    plan, data = load_plan(args.plan)
    print(
        json.dumps(
            {
                "contract": PLAN_CONTRACT,
                "jobs": len(plan["jobs"]),
                "maximum_jobs": MAX_JOBS,
                "maximum_plan_bytes": MAX_PLAN_BYTES,
                "plan_sha256": hashlib.sha256(data).hexdigest(),
                "valid": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
