#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from rebuild_dsm5_exact_datasets import run_phase, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)
    run_phase(Path(args.root).resolve(), "internal_targets")


if __name__ == "__main__":
    main()
