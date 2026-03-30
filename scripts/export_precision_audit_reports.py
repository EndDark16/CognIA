from __future__ import annotations

import argparse
from pathlib import Path

from run_precision_bottleneck_audit import (
    _load_champion_contexts,
    _setup_logging,
    build_disorder_bottleneck_matrix,
    ensure_audit_dirs,
    export_precision_strategy_docs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export consolidated precision bottleneck audit reports.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    _setup_logging(args.verbose)
    dirs = ensure_audit_dirs(root)
    contexts = _load_champion_contexts(root)
    build_disorder_bottleneck_matrix(root, dirs, contexts)
    export_precision_strategy_docs(root, dirs, contexts)


if __name__ == "__main__":
    main()
