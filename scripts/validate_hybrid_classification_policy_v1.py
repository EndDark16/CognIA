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
SHORTCUT_INV_V6_HOTFIX = ROOT / "data" / "hybrid_v6_quick_champion_guard_hotfix_v1" / "tables" / "shortcut_inventory_v6_hotfix_v1.csv"
SHORTCUT_INV_V8 = ROOT / "data" / "hybrid_structural_mode_rescue_v1" / "tables" / "shortcut_inventory_structural_mode_rescue_v1.csv"
SHORTCUT_INV_V9 = ROOT / "data" / "hybrid_elimination_structural_audit_rescue_v1" / "tables" / "shortcut_inventory_elimination_structural_audit_rescue_v1.csv"
SHORTCUT_INV_V10 = ROOT / "data" / "hybrid_final_model_structural_compliance_v1" / "tables" / "shortcut_inventory_final_model_structural_compliance_v1.csv"
SHORTCUT_INV_V11 = ROOT / "data" / "hybrid_rf_max_real_metrics_v1" / "tables" / "shortcut_inventory_rf_max_real_metrics_v1.csv"
SHORTCUT_INV_V12 = ROOT / "data" / "hybrid_final_rf_plus_maximize_metrics_v1" / "tables" / "shortcut_inventory_final_rf_plus_maximize_metrics_v1.csv"

LABELS = ["v2", "v3", "v4", "v5", "v6_hotfix_v1", "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15", "v16"]


def _shortcut_inventory_for(label: str) -> Path | None:
    if label in {"v13", "v14", "v15", "v16"} and SHORTCUT_INV_V12.exists():
        return SHORTCUT_INV_V12
    if label == "v12" and SHORTCUT_INV_V12.exists():
        return SHORTCUT_INV_V12
    if label == "v11" and SHORTCUT_INV_V11.exists():
        return SHORTCUT_INV_V11
    if label == "v10" and SHORTCUT_INV_V10.exists():
        return SHORTCUT_INV_V10
    if label == "v9" and SHORTCUT_INV_V9.exists():
        return SHORTCUT_INV_V9
    if label == "v8" and SHORTCUT_INV_V8.exists():
        return SHORTCUT_INV_V8
    if label == "v6_hotfix_v1" and SHORTCUT_INV_V6_HOTFIX.exists():
        return SHORTCUT_INV_V6_HOTFIX
    if label == "v6" and SHORTCUT_INV_V6.exists():
        return SHORTCUT_INV_V6
    if label == "v5" and SHORTCUT_INV_V5.exists():
        return SHORTCUT_INV_V5
    return SHORTCUT_INV if SHORTCUT_INV.exists() else None


def _line_paths(label: str) -> tuple[Path, Path]:
    return (
        ROOT / "data" / f"hybrid_operational_freeze_{label}" / "tables" / "hybrid_operational_final_champions.csv",
        ROOT / "data" / f"hybrid_active_modes_freeze_{label}" / "tables" / "hybrid_active_models_30_modes.csv",
    )


def main() -> int:
    output_dir = DATA_BASE / "validation"
    output_dir.mkdir(parents=True, exist_ok=True)
    violations_total = 0
    lines_checked = 0
    details: dict[str, int] = {}

    for label in LABELS:
        op_csv, active_csv = _line_paths(label)
        if not op_csv.exists() or not active_csv.exists():
            continue
        lines_checked += 1
        normalized = build_normalized_table(
            PolicyInputs(
                operational_csv=op_csv,
                active_csv=active_csv,
                shortcut_inventory_csv=_shortcut_inventory_for(label),
            )
        )
        violations = policy_violations(normalized)
        details[label] = int(len(violations))
        violations_total += int(len(violations))
        violations.to_csv(output_dir / f"hybrid_classification_policy_violations_{label}.csv", index=False, lineterminator="\n")

    payload = {"lines_checked": lines_checked, "violation_count": violations_total, "per_line": details}
    print(json.dumps(payload, ensure_ascii=False))
    return 1 if violations_total > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
