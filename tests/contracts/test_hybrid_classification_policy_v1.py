import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations


ROOT = Path(PROJECT_ROOT)
SHORTCUT_INV = ROOT / "data" / "hybrid_secondary_honest_retrain_v1" / "tables" / "non_conduct_suspect_inventory.csv"
SHORTCUT_INV_V5 = ROOT / "data" / "hybrid_final_decisive_rescue_v5" / "tables" / "shortcut_inventory_v5.csv"
SHORTCUT_INV_V6 = ROOT / "data" / "hybrid_final_aggressive_rescue_v6" / "tables" / "shortcut_inventory_v6.csv"
SHORTCUT_INV_V7 = ROOT / "data" / "hybrid_final_aggressive_honest_rescue_v7" / "tables" / "shortcut_inventory_v7.csv"


def _line_inputs() -> list[PolicyInputs]:
    lines: list[PolicyInputs] = []
    for label in ["v2", "v3", "v4", "v5", "v6", "v7"]:
        op = ROOT / "data" / f"hybrid_operational_freeze_{label}" / "tables" / "hybrid_operational_final_champions.csv"
        active = ROOT / "data" / f"hybrid_active_modes_freeze_{label}" / "tables" / "hybrid_active_models_30_modes.csv"
        if not op.exists() or not active.exists():
            continue
        if label == "v7" and SHORTCUT_INV_V7.exists():
            shortcut_inv = SHORTCUT_INV_V7
        elif label == "v6" and SHORTCUT_INV_V6.exists():
            shortcut_inv = SHORTCUT_INV_V6
        elif label == "v5" and SHORTCUT_INV_V5.exists():
            shortcut_inv = SHORTCUT_INV_V5
        else:
            shortcut_inv = SHORTCUT_INV if SHORTCUT_INV.exists() else None
        lines.append(
            PolicyInputs(
                operational_csv=op,
                active_csv=active,
                shortcut_inventory_csv=shortcut_inv,
            )
        )
    return lines


def test_hybrid_classification_policy_has_no_hard_rule_violations():
    for inputs in _line_inputs():
        normalized = build_normalized_table(inputs)
        violations = policy_violations(normalized)
        assert violations.empty, (
            f"policy_violations_in_{inputs.operational_csv.parent.parent.name}: "
            f"{violations[['domain', 'mode', 'normalized_final_class', 'violation']].to_dict(orient='records')}"
        )
