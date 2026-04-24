#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations

DATA_BASE = ROOT / "data" / "hybrid_classification_normalization_v2"
SHORTCUT_INV = ROOT / "data" / "hybrid_secondary_honest_retrain_v1" / "tables" / "non_conduct_suspect_inventory.csv"
SHORTCUT_INV_V5 = ROOT / "data" / "hybrid_final_decisive_rescue_v5" / "tables" / "shortcut_inventory_v5.csv"
SHORTCUT_INV_V6 = ROOT / "data" / "hybrid_final_aggressive_rescue_v6" / "tables" / "shortcut_inventory_v6.csv"
SHORTCUT_INV_V7 = ROOT / "data" / "hybrid_final_aggressive_honest_rescue_v7" / "tables" / "shortcut_inventory_v7.csv"

LINES = [
    (
        "v2",
        ROOT / "data" / "hybrid_operational_freeze_v2" / "tables" / "hybrid_operational_final_champions.csv",
        ROOT / "data" / "hybrid_active_modes_freeze_v2" / "tables" / "hybrid_active_models_30_modes.csv",
    ),
    (
        "v3",
        ROOT / "data" / "hybrid_operational_freeze_v3" / "tables" / "hybrid_operational_final_champions.csv",
        ROOT / "data" / "hybrid_active_modes_freeze_v3" / "tables" / "hybrid_active_models_30_modes.csv",
    ),
    (
        "v4",
        ROOT / "data" / "hybrid_operational_freeze_v4" / "tables" / "hybrid_operational_final_champions.csv",
        ROOT / "data" / "hybrid_active_modes_freeze_v4" / "tables" / "hybrid_active_models_30_modes.csv",
    ),
    (
        "v5",
        ROOT / "data" / "hybrid_operational_freeze_v5" / "tables" / "hybrid_operational_final_champions.csv",
        ROOT / "data" / "hybrid_active_modes_freeze_v5" / "tables" / "hybrid_active_models_30_modes.csv",
    ),
    (
        "v6",
        ROOT / "data" / "hybrid_operational_freeze_v6" / "tables" / "hybrid_operational_final_champions.csv",
        ROOT / "data" / "hybrid_active_modes_freeze_v6" / "tables" / "hybrid_active_models_30_modes.csv",
    ),
    (
        "v7",
        ROOT / "data" / "hybrid_operational_freeze_v7" / "tables" / "hybrid_operational_final_champions.csv",
        ROOT / "data" / "hybrid_active_modes_freeze_v7" / "tables" / "hybrid_active_models_30_modes.csv",
    ),
]


def main() -> int:
    output_dir = DATA_BASE / "validation"
    output_dir.mkdir(parents=True, exist_ok=True)

    violations_total = 0
    lines_checked = 0
    details: dict[str, int] = {}

    for label, op_csv, active_csv in LINES:
        if not op_csv.exists() or not active_csv.exists():
            continue
        lines_checked += 1
        normalized = build_normalized_table(
            PolicyInputs(
                operational_csv=op_csv,
                active_csv=active_csv,
                shortcut_inventory_csv=(
                    SHORTCUT_INV_V7
                    if label == "v7" and SHORTCUT_INV_V7.exists()
                    else (
                        SHORTCUT_INV_V6
                        if label == "v6" and SHORTCUT_INV_V6.exists()
                        else (
                            SHORTCUT_INV_V5
                            if label == "v5" and SHORTCUT_INV_V5.exists()
                            else (SHORTCUT_INV if SHORTCUT_INV.exists() else None)
                        )
                    )
                ),
            )
        )
        violations = policy_violations(normalized)
        details[label] = int(len(violations))
        violations_total += int(len(violations))
        violations.to_csv(output_dir / f"hybrid_classification_policy_violations_{label}.csv", index=False)

    payload = {
        "lines_checked": lines_checked,
        "violation_count": violations_total,
        "per_line": details,
    }
    print(json.dumps(payload, ensure_ascii=False))
    if violations_total > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
