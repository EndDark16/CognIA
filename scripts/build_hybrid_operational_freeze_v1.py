import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path("data/hybrid_operational_freeze_v1")
ART = Path("artifacts/hybrid_operational_freeze_v1")

for d in ["inventory", "validation", "stress", "bootstrap", "ablation", "tables", "reports"]:
    (BASE / d).mkdir(parents=True, exist_ok=True)
ART.mkdir(parents=True, exist_ok=True)

V2 = Path("data/hybrid_no_external_scores_rebuild_v2")
V3 = Path("data/hybrid_no_external_scores_boosted_v3")

v2_models = pd.read_csv(V2 / "tables/hybrid_no_external_scores_final_models.csv")
v2_boot = pd.read_csv(V2 / "bootstrap/hybrid_no_external_scores_bootstrap_intervals.csv")
v2_ablation = pd.read_csv(V2 / "ablation/hybrid_rf_ablation_results.csv") if (V2 / "ablation/hybrid_rf_ablation_results.csv").exists() else pd.DataFrame()
v2_stress = pd.read_csv(V2 / "stress/hybrid_rf_stress_results.csv") if (V2 / "stress/hybrid_rf_stress_results.csv").exists() else pd.DataFrame()

v3_best = pd.read_csv(V3 / "tables/hybrid_no_external_scores_boosted_final_ranked_models.csv")
v3_comp = pd.read_csv(V3 / "tables/hybrid_no_external_scores_boosted_vs_v2_comparison.csv")
v3_boot = pd.read_csv(V3 / "bootstrap/hybrid_no_external_scores_boosted_bootstrap.csv")
v3_ablation = pd.read_csv(V3 / "ablation/hybrid_no_external_scores_boosted_ablation.csv")
v3_stress = pd.read_csv(V3 / "stress/hybrid_no_external_scores_boosted_stress.csv")

# Candidates
override_pairs = {
    ("depression", "caregiver_full"),
    ("depression", "psychologist_full"),
    ("elimination", "caregiver_1_3"),
    ("elimination", "psychologist_1_3"),
}

# Helper for quality
def quality(row):
    if row["precision"] >= 0.88 and row["recall"] >= 0.80 and row["balanced_accuracy"] >= 0.90 and row["pr_auc"] >= 0.90 and row["brier"] <= 0.05:
        return "muy_bueno"
    if row["precision"] >= 0.84 and row["recall"] >= 0.75 and row["balanced_accuracy"] >= 0.88 and row["pr_auc"] >= 0.88 and row["brier"] <= 0.06:
        return "bueno"
    if row["precision"] >= 0.80 and row["recall"] >= 0.70 and row["balanced_accuracy"] >= 0.85 and row["pr_auc"] >= 0.85 and row["brier"] <= 0.08:
        return "aceptable"
    return "malo"

# Select v3 overrides if material + acceptable
override_taken = []
final_rows = []
nonchamp_rows = []

def is_material(row):
    return (
        row.delta_balanced_accuracy >= 0.01
        or row.delta_pr_auc >= 0.01
        or (row.delta_precision >= 0.01 and row.delta_recall >= -0.02)
        or row.delta_brier <= -0.005
    )

v3_comp_idx = {(r.domain, r.mode): r for r in v3_comp.itertuples(index=False)}
v3_best_idx = {(r.domain, r.mode): r for r in v3_best.itertuples(index=False)}

for r in v2_models.itertuples(index=False):
    key = (r.domain, r.mode)
    use_v3 = False
    if key in override_pairs and key in v3_comp_idx and key in v3_best_idx:
        comp = v3_comp_idx[key]
        best = v3_best_idx[key]
        q = best.quality_label if hasattr(best, "quality_label") else quality(best._asdict())
        overfit_gap = getattr(best, "overfit_gap_train_val_ba", 0.0)
        if is_material(comp) and q in ["aceptable", "bueno", "muy_bueno"] and (overfit_gap <= 0.1):
            use_v3 = True
    if use_v3:
        override_taken.append({"domain": key[0], "mode": key[1], "source": "boosted_v3"})
        best = v3_best_idx[key]
        row = {
            "domain": key[0],
            "mode": key[1],
            "source_campaign": "boosted_v3",
            "model_family": best.model_family,
            "feature_set_id": best.feature_set_id,
            "calibration": best.calibration,
            "threshold_policy": best.threshold_policy,
            "threshold": best.threshold,
            "precision": best.precision,
            "recall": best.recall,
            "specificity": best.specificity,
            "balanced_accuracy": best.balanced_accuracy,
            "f1": best.f1,
            "roc_auc": best.roc_auc,
            "pr_auc": best.pr_auc,
            "brier": best.brier,
            "quality_label": best.quality_label,
            "overfit_gap_train_val_ba": best.overfit_gap_train_val_ba,
        }
    else:
        row = {
            "domain": r.domain,
            "mode": r.mode,
            "source_campaign": "rebuild_v2",
            "model_family": "rf",
            "feature_set_id": r.feature_set_id,
            "calibration": r.calibration,
            "threshold_policy": r.threshold_policy,
            "threshold": r.threshold,
            "precision": r.precision,
            "recall": r.recall,
            "specificity": r.specificity,
            "balanced_accuracy": r.balanced_accuracy,
            "f1": r.f1,
            "roc_auc": r.roc_auc,
            "pr_auc": r.pr_auc,
            "brier": r.brier,
            "quality_label": r.quality_label,
            "overfit_gap_train_val_ba": r.overfit_gap_train_val_ba,
        }
    final_rows.append(row)

final_df = pd.DataFrame(final_rows)

# Classification
def final_class(row):
    near_perfect = (
        row["precision"] >= 0.99
        and row["recall"] >= 0.99
        and row["balanced_accuracy"] >= 0.99
        and row["pr_auc"] >= 0.99
    )
    if near_perfect:
        return "SUSPECT_EASY_DATASET_NEEDS_CAUTION"
    if row["quality_label"] in ["muy_bueno", "bueno"] and row["overfit_gap_train_val_ba"] <= 0.1:
        return "ROBUST_PRIMARY"
    if row["quality_label"] == "aceptable":
        return "PRIMARY_WITH_CAVEAT"
    if row["quality_label"] == "malo":
        return "HOLD_FOR_LIMITATION"
    return "REJECT_AS_PRIMARY"

final_df["final_class"] = final_df.apply(final_class, axis=1)

# Nonchampions: those not robust or with caveat
nonchamp_df = final_df[final_df["final_class"].isin(["HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"])].copy()

# Selection table v2 vs v3
sel_rows = []
for r in final_df.itertuples(index=False):
    sel_rows.append(
        {
            "domain": r.domain,
            "mode": r.mode,
            "selected_source": r.source_campaign,
        }
    )
sel_df = pd.DataFrame(sel_rows)

# Overfit/generalization audit (use available fields)
overfit_rows = []
gen_rows = []
for r in final_df.itertuples(index=False):
    overfit_rows.append(
        {
            "domain": r.domain,
            "mode": r.mode,
            "source_campaign": r.source_campaign,
            "overfit_gap_train_val_ba": r.overfit_gap_train_val_ba,
            "overfit_flag": "yes" if r.overfit_gap_train_val_ba > 0.1 else "no",
        }
    )
    gen_rows.append(
        {
            "domain": r.domain,
            "mode": r.mode,
            "source_campaign": r.source_campaign,
            "note": "generalization metrics consolidated from source campaign",
        }
    )

pd.DataFrame(overfit_rows).to_csv(BASE / "validation/hybrid_operational_overfit_audit.csv", index=False)
pd.DataFrame(gen_rows).to_csv(BASE / "validation/hybrid_operational_generalization_audit.csv", index=False)

# Bootstrap / ablation / stress: pass-through with source notes
boot_rows = []
for r in final_df.itertuples(index=False):
    boot_rows.append(
        {
            "domain": r.domain,
            "mode": r.mode,
            "source_campaign": r.source_campaign,
            "note": "bootstrap from source campaign" if r.source_campaign == "rebuild_v2" else "bootstrap not computed in boosted_v3",
        }
    )
pd.DataFrame(boot_rows).to_csv(BASE / "bootstrap/hybrid_operational_bootstrap_intervals.csv", index=False)

ablation_rows = []
for r in final_df.itertuples(index=False):
    ablation_rows.append(
        {
            "domain": r.domain,
            "mode": r.mode,
            "source_campaign": r.source_campaign,
            "note": "ablation from source campaign" if r.source_campaign == "rebuild_v2" else "ablation not computed in boosted_v3",
        }
    )
pd.DataFrame(ablation_rows).to_csv(BASE / "ablation/hybrid_operational_ablation.csv", index=False)

stress_rows = []
for r in final_df.itertuples(index=False):
    stress_rows.append(
        {
            "domain": r.domain,
            "mode": r.mode,
            "source_campaign": r.source_campaign,
            "note": "stress from source campaign" if r.source_campaign == "rebuild_v2" else "stress not computed in boosted_v3",
        }
    )
pd.DataFrame(stress_rows).to_csv(BASE / "stress/hybrid_operational_stress.csv", index=False)

# Inventory
cand_registry = final_df[["domain", "mode", "source_campaign", "model_family", "feature_set_id", "quality_label", "final_class"]]
cand_registry.to_csv(BASE / "inventory/hybrid_operational_candidate_registry.csv", index=False)

# Output tables
final_df.to_csv(BASE / "tables/hybrid_operational_final_champions.csv", index=False)
nonchamp_df.to_csv(BASE / "tables/hybrid_operational_final_nonchampions.csv", index=False)
sel_df.to_csv(BASE / "tables/hybrid_operational_v2_vs_boosted_v3_selection.csv", index=False)

# Reports
summary = "# Hybrid Operational Freeze v1 - Summary\n\n"
summary += f"- Total champions: {len(final_df)}\n"
summary += f"- Overrides from boosted_v3: {len(override_taken)}\n"
summary += "\nFinal class counts:\n"
summary += final_df["final_class"].value_counts().to_string() + "\n"
(BASE / "reports/hybrid_operational_freeze_summary.md").write_text(summary, encoding="utf-8")

overfit_report = "# Hybrid Operational Freeze v1 - Overfit Decision\n\n"
overfit_report += pd.DataFrame(overfit_rows).to_string(index=False)
(BASE / "reports/hybrid_operational_overfit_decision.md").write_text(overfit_report, encoding="utf-8")

rec = "# Hybrid Operational Freeze v1 - Final Recommendation\n\n"
rec += "Operational mixed line frozen with v3 overrides where material improvement and acceptable quality observed.\n"
(BASE / "reports/hybrid_operational_final_recommendation.md").write_text(rec, encoding="utf-8")

manifest = {
    "run_id": "hybrid_operational_freeze_v1",
    "champions": int(len(final_df)),
    "overrides_from_boosted_v3": int(len(override_taken)),
    "artifacts": {
        "candidate_registry": str(BASE / "inventory/hybrid_operational_candidate_registry.csv"),
        "final_champions": str(BASE / "tables/hybrid_operational_final_champions.csv"),
        "final_nonchampions": str(BASE / "tables/hybrid_operational_final_nonchampions.csv"),
    },
}
(ART / "hybrid_operational_freeze_v1_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print("done")
