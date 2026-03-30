from __future__ import annotations

import argparse
from pathlib import Path

from run_precision_bottleneck_audit import (
    _load_champion_contexts,
    _setup_logging,
    ensure_audit_dirs,
    run_diagnostic_hypotheses,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run diagnostic precision hypotheses.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    _setup_logging(args.verbose)
    dirs = ensure_audit_dirs(root)
    contexts = _load_champion_contexts(root)
    run_diagnostic_hypotheses(root, dirs, contexts)


if __name__ == "__main__":
    main()
