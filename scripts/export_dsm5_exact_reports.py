#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from rebuild_dsm5_exact_datasets import DSM5ExactRebuilder, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)
    root = Path(args.root).resolve()
    reb = DSM5ExactRebuilder(root)
    reb.ensure_dirs()
    reb.capture_baseline_hashes()
    reb.load_inputs()
    reb.build_normative_registries()
    reb.build_mapping()
    reb.build_participant_normative_evidence()
    reb.build_internal_exact_targets()
    reb.build_external_domain_targets()
    reb.export_datasets()
    reb.export_reports()
    reb.verify_baseline_hashes()


if __name__ == "__main__":
    main()
