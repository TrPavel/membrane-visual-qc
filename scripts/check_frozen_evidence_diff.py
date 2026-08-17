"""Reject changes to evidence protected by the frozen-release validators."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FROZEN_PATHS = (
    "docs/v0.4.0_graphical_smoke.md",
    "docs/v0.4.0_release_notes.md",
    "docs/v0.5.0_release_evidence.json",
    "docs/v0.6.0_release_evidence.json",
    "docs/v0.7.0_release_evidence.json",
    "docs/v0.8.0_release_evidence.json",
    "docs/v0.9.0_release_evidence.json",
    "docs/releases/v0.9.0_manual_acceptance.md",
    "docs/releases/1.0.0rc1_manual_acceptance.md",
    "docs/v1.0.0rc1_release_evidence.json",
    "docs/releases/1.0.0_manual_acceptance.md",
    "reports/pdbtm_synthetic_mvqc.json",
    "reports/pdbtm_local_v050_mvqc.json",
    "reports/pdbtm_acquisition_v050_mvqc.json",
    "reports/source_comparison_synthetic_mvqc.json",
    "schemas",
)


def changed_frozen_paths(base: str, *, root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", base, "--", *FROZEN_PATHS],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Trusted comparison commit")
    args = parser.parse_args()
    changed = changed_frozen_paths(args.base)
    if changed:
        parser.error("frozen evidence changed:\n" + "\n".join(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
