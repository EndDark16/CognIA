#!/usr/bin/env python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from api.services.hybrid_classification_policy_v1 import (
    PolicyInputs,
    build_normalized_table,
    build_review_list,
    policy_violations,
)


ROOT = Path(__file__).resolve().parents[1]
LINE = "hybrid_classification_normalization_v1"
DATA_BASE = ROOT / "data" / LINE
ART_BASE = ROOT / "artifacts" / LINE

OP_V2 = ROOT / "data" / "hybrid_operational_freeze_v2" / "tables" / "hybrid_operational_final_champions.csv"
ACTIVE_V2 = ROOT / "data" / "hybrid_active_modes_freeze_v2" / "tables" / "hybrid_active_models_30_modes.csv"
OP_V3 = ROOT / "data" / "hybrid_operational_freeze_v3" / "tables" / "hybrid_operational_final_champions.csv"
ACTIVE_V3 = ROOT / "data" / "hybrid_active_modes_freeze_v3" / "tables" / "hybrid_active_models_30_modes.csv"
SHORTCUT_INV = ROOT / "data" / "hybrid_secondary_honest_retrain_v1" / "tables" / "non_conduct_suspect_inventory.csv"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    for p in [
        DATA_BASE / "tables",
        DATA_BASE / "reports",
        DATA_BASE / "validation",
        DATA_BASE / "inventory",
        ART_BASE,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def _save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _md_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df.empty:
        return "(sin filas)"
    frame = df.head(max_rows).copy()
    cols = list(frame.columns)
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in frame.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            if isinstance(value, float):
                vals.append(f"{value:.6f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _run_line(line_label: str, operational_csv: Path, active_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    normalized = build_normalized_table(
        PolicyInputs(
            operational_csv=operational_csv,
            active_csv=active_csv,
            shortcut_inventory_csv=SHORTCUT_INV if SHORTCUT_INV.exists() else None,
        )
    )
    violations = policy_violations(normalized)
    review = build_review_list(normalized)

    _save_csv(normalized, DATA_BASE / f"tables/hybrid_operational_classification_normalized_{line_label}.csv")
    _save_csv(violations, DATA_BASE / f"validation/hybrid_classification_policy_violations_{line_label}.csv")
    _save_csv(review, DATA_BASE / f"inventory/hybrid_classification_review_list_{line_label}.csv")
    return normalized, violations, review


def main() -> None:
    _ensure_dirs()
    if not OP_V2.exists() or not ACTIVE_V2.exists():
        raise FileNotFoundError("missing freeze_v2 source tables")

    norm_v2, viol_v2, review_v2 = _run_line("v2", OP_V2, ACTIVE_V2)

    v3_exists = OP_V3.exists() and ACTIVE_V3.exists()
    norm_v3 = pd.DataFrame()
    viol_v3 = pd.DataFrame()
    review_v3 = pd.DataFrame()
    if v3_exists:
        norm_v3, viol_v3, review_v3 = _run_line("v3", OP_V3, ACTIVE_V3)

    summary_rows = [
        {
            "line": "v2",
            "rows": int(len(norm_v2)),
            "legacy_robust": int((norm_v2["legacy_final_class"] == "ROBUST_PRIMARY").sum()),
            "normalized_robust": int((norm_v2["normalized_final_class"] == "ROBUST_PRIMARY").sum()),
            "normalized_caveat": int((norm_v2["normalized_final_class"] == "PRIMARY_WITH_CAVEAT").sum()),
            "normalized_hold": int((norm_v2["normalized_final_class"] == "HOLD_FOR_LIMITATION").sum()),
            "normalized_reject": int((norm_v2["normalized_final_class"] == "REJECT_AS_PRIMARY").sum()),
            "downgrades": int((norm_v2["class_transition"] == "downgrade").sum()),
            "violations": int(len(viol_v2)),
        }
    ]
    if v3_exists:
        summary_rows.append(
            {
                "line": "v3",
                "rows": int(len(norm_v3)),
                "legacy_robust": int((norm_v3["legacy_final_class"] == "ROBUST_PRIMARY").sum()),
                "normalized_robust": int((norm_v3["normalized_final_class"] == "ROBUST_PRIMARY").sum()),
                "normalized_caveat": int((norm_v3["normalized_final_class"] == "PRIMARY_WITH_CAVEAT").sum()),
                "normalized_hold": int((norm_v3["normalized_final_class"] == "HOLD_FOR_LIMITATION").sum()),
                "normalized_reject": int((norm_v3["normalized_final_class"] == "REJECT_AS_PRIMARY").sum()),
                "downgrades": int((norm_v3["class_transition"] == "downgrade").sum()),
                "violations": int(len(viol_v3)),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    _save_csv(summary_df, DATA_BASE / "tables/hybrid_classification_normalization_summary.csv")

    focus_v2 = review_v2[
        review_v2["mode"].astype(str).str.contains("_full|_2_3", case=False, regex=True)
    ].copy()
    _save_csv(focus_v2, DATA_BASE / "inventory/hybrid_classification_review_priority_full_2_3_v2.csv")

    report_lines = [
        "# Hybrid Classification Normalization v1",
        "",
        "Normalizacion metodologica de `final_class` (dos capas): clase principal + flags de riesgo.",
        "",
        "## Resumen",
        _md_table(summary_df),
        "",
        "## Top review priority (v2, focus full y 2_3)",
        _md_table(
            focus_v2[
                [
                    "domain",
                    "mode",
                    "legacy_final_class",
                    "normalized_final_class",
                    "review_bucket",
                    "priority_score",
                    "secondary_metric_anomaly_flag",
                    "overfit_risk_flag",
                    "shortcut_risk_flag",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## Policy violations",
        f"- v2: {len(viol_v2)}",
        f"- v3: {len(viol_v3)}" if v3_exists else "- v3: no_aplica",
    ]
    (DATA_BASE / "reports/hybrid_classification_normalization_summary.md").write_text(
        "\n".join(report_lines).strip() + "\n",
        encoding="utf-8",
    )

    manifest = {
        "run_id": LINE,
        "generated_at_utc": _now_iso(),
        "source_operational_v2": str(OP_V2.relative_to(ROOT)),
        "source_active_v2": str(ACTIVE_V2.relative_to(ROOT)),
        "source_operational_v3": str(OP_V3.relative_to(ROOT)) if v3_exists else "no_aplica",
        "source_active_v3": str(ACTIVE_V3.relative_to(ROOT)) if v3_exists else "no_aplica",
        "shortcut_inventory": str(SHORTCUT_INV.relative_to(ROOT)) if SHORTCUT_INV.exists() else "no_aplica",
        "outputs": {
            "summary": str((DATA_BASE / "tables/hybrid_classification_normalization_summary.csv").relative_to(ROOT)),
            "normalized_v2": str((DATA_BASE / "tables/hybrid_operational_classification_normalized_v2.csv").relative_to(ROOT)),
            "review_v2": str((DATA_BASE / "inventory/hybrid_classification_review_list_v2.csv").relative_to(ROOT)),
            "focus_full_2_3_v2": str((DATA_BASE / "inventory/hybrid_classification_review_priority_full_2_3_v2.csv").relative_to(ROOT)),
        },
        "policy_violation_count_v2": int(len(viol_v2)),
        "policy_violation_count_v3": int(len(viol_v3)) if v3_exists else None,
    }
    (ART_BASE / "hybrid_classification_normalization_v1_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps({"status": "ok", "line": LINE, "summary_rows": len(summary_df)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
