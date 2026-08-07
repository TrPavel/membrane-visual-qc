"""Pure validation CLI for versioned Stage 5A batch plans."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .batch_contracts import BatchContractError, MAX_JOBS, MAX_PLAN_BYTES, PLAN_CONTRACT, load_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate without importing PyMOL")
    validate.add_argument("plan", type=Path)
    args = parser.parse_args(argv)
    # Only the plan's own documented, expected failure modes (contract violation
    # or an unusable path) are handled here; anything else is a real internal
    # bug and must keep its traceback rather than being silently swallowed.
    try:
        plan, data = load_plan(args.plan)
    except (BatchContractError, OSError) as error:
        print(f"mvqc_batch_cli: invalid plan '{args.plan}': {error}", file=sys.stderr)
        return 1
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
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
