import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations


ROOT = Path(PROJECT_ROOT)
SHORTCUT_INV = ROOT / "data" / "hybrid_secondary_honest_retrain_v1" / "tables" / "non_conduct_suspect_inventory.csv"
SHORTCUT_INV_V6_HOTFIX = ROOT / "data" / "hybrid_v6_quick_champion_guard_hotfix_v1" / "tables" / "shortcut_inventory_v6_hotfix_v1.csv"
SHORTCUT_INV_V8 = ROOT / "data" / "hybrid_structural_mode_rescue_v1" / "tables" / "shortcut_inventory_structural_mode_rescue_v1.csv"
SHORTCUT_INV_V9 = ROOT / "data" / "hybrid_elimination_structural_audit_rescue_v1" / "tables" / "shortcut_inventory_elimination_structural_audit_rescue_v1.csv"
SHORTCUT_INV_V10 = ROOT / "data" / "hybrid_final_model_structural_compliance_v1" / "tables" / "shortcut_inventory_final_model_structural_compliance_v1.csv"
SHORTCUT_INV_V11 = ROOT / "data" / "hybrid_rf_max_real_metrics_v1" / "tables" / "shortcut_inventory_rf_max_real_metrics_v1.csv"


def _shortcut_inventory_for(label: str) -> Path | None:
    if label == "v11" and SHORTCUT_INV_V11.exists():
        return SHORTCUT_INV_V11
    if label == "v10":
        return SHORTCUT_INV_V10
    if label == "v9":
        return SHORTCUT_INV_V9
    if label == "v8":
        return SHORTCUT_INV_V8
    if label == "v6_hotfix_v1":
        return SHORTCUT_INV_V6_HOTFIX
    return SHORTCUT_INV


def _line_inputs() -> list[PolicyInputs]:
    lines: list[PolicyInputs] = []
    for label in ["v2", "v3", "v4", "v5", "v6_hotfix_v1", "v8", "v9", "v10", "v11"]:
        op = ROOT / "data" / f"hybrid_operational_freeze_{label}" / "tables" / "hybrid_operational_final_champions.csv"
        active = ROOT / "data" / f"hybrid_active_modes_freeze_{label}" / "tables" / "hybrid_active_models_30_modes.csv"
        if not op.exists() or not active.exists():
            continue
        shortcut_inv = _shortcut_inventory_for(label)
        lines.append(
            PolicyInputs(
                operational_csv=op,
                active_csv=active,
                shortcut_inventory_csv=shortcut_inv if shortcut_inv.exists() else None,
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
