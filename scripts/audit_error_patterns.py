from __future__ import annotations

import argparse
from pathlib import Path

from run_precision_bottleneck_audit import (
    _load_champion_contexts,
    _setup_logging,
    audit_error_patterns,
    ensure_audit_dirs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run error taxonomy audit (FP/FN drivers).")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    _setup_logging(args.verbose)
    dirs = ensure_audit_dirs(root)
    contexts = _load_champion_contexts(root)
    audit_error_patterns(root, dirs, contexts)


if __name__ == "__main__":
    main()
