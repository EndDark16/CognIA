import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations


ROOT = Path(PROJECT_ROOT)
SHORTCUT_INV = ROOT / "data" / "hybrid_secondary_honest_retrain_v1" / "tables" / "non_conduct_suspect_inventory.csv"


def _line_inputs() -> list[PolicyInputs]:
    lines = [
        PolicyInputs(
            operational_csv=ROOT / "data" / "hybrid_operational_freeze_v2" / "tables" / "hybrid_operational_final_champions.csv",
            active_csv=ROOT / "data" / "hybrid_active_modes_freeze_v2" / "tables" / "hybrid_active_models_30_modes.csv",
            shortcut_inventory_csv=SHORTCUT_INV if SHORTCUT_INV.exists() else None,
        )
    ]
    v3_op = ROOT / "data" / "hybrid_operational_freeze_v3" / "tables" / "hybrid_operational_final_champions.csv"
    v3_active = ROOT / "data" / "hybrid_active_modes_freeze_v3" / "tables" / "hybrid_active_models_30_modes.csv"
    if v3_op.exists() and v3_active.exists():
        lines.append(
            PolicyInputs(
                operational_csv=v3_op,
                active_csv=v3_active,
                shortcut_inventory_csv=SHORTCUT_INV if SHORTCUT_INV.exists() else None,
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
