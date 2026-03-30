#!/usr/bin/env python
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_step(root: Path, script_name: str) -> None:
    cmd = [sys.executable, str(root / "scripts" / script_name), "--root", str(root)]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full hybrid DSM5 v2 pipeline end to end.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--skip-training", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    run_step(root, "build_questionnaire_dsm5_layer.py")
    run_step(root, "build_hybrid_dsm5_datasets.py")
    run_step(root, "run_hybrid_modelability_audit.py")
    if not args.skip_training:
        run_step(root, "train_hybrid_random_forest.py")
    run_step(root, "export_training_history.py")
    run_step(root, "export_operating_modes.py")
    run_step(root, "export_inference_layer.py")


if __name__ == "__main__":
    main()
