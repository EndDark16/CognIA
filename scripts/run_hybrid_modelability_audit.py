#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from run_dsm5_exact_modelability_audit import run_phase, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run modelability audit for hybrid DSM5 v2 line.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument(
        "--phase",
        type=str,
        default="all",
        choices=["all", "coverage", "core", "target", "feature", "risk", "index", "export"],
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    run_phase(
        Path(args.root).resolve(),
        args.phase,
        base_subdir="data/processed_hybrid_dsm5_v2",
        artifact_subdir="artifacts/hybrid_dsm5_v2/modelability_audit",
        strict_dir_name="strict_no_leakage_exact",
        audit_label="hybrid_dsm5_v2",
    )


if __name__ == "__main__":
    main()

