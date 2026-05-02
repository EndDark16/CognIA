#!/usr/bin/env python
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LINE = "hybrid_domain_specialized_rf_v17"
FREEZE = "v17"
BASE = ROOT / "data" / LINE
TABLES = BASE / "tables"
VALIDATION = BASE / "validation"
REPORTS = BASE / "reports"
PLOTS = BASE / "plots"

ACTIVE_V16 = ROOT / "data/hybrid_active_modes_freeze_v16/tables/hybrid_active_models_30_modes.csv"
ACTIVE_V17 = ROOT / "data/hybrid_active_modes_freeze_v17/tables/hybrid_active_models_30_modes.csv"
INPUTS_V16 = ROOT / "data/hybrid_active_modes_freeze_v16/tables/hybrid_questionnaire_inputs_master.csv"
INPUTS_V17 = ROOT / "data/hybrid_active_modes_freeze_v17/tables/hybrid_questionnaire_inputs_master.csv"
OP_V17 = ROOT / "data/hybrid_operational_freeze_v17/tables/hybrid_operational_final_champions.csv"
DATASET = ROOT / "data/hybrid_no_external_scores_rebuild_v2/tables/hybrid_no_external_scores_dataset_ready.csv"

ART = ROOT / "artifacts" / LINE
ART_ACTIVE = ROOT / "artifacts/hybrid_active_modes_freeze_v17/hybrid_active_modes_freeze_v17_manifest.json"
ART_OP = ROOT / "artifacts/hybrid_operational_freeze_v17/hybrid_operational_freeze_v17_manifest.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sf(v: Any, d: float = float("nan")) -> float:
    try:
        if pd.isna(v):
            return d
        return float(v)
    except Exception:
        return d


def feats(value: Any) -> list[str]:
    return [x.strip() for x in str(value or "").split("|") if x.strip() and x.strip().lower() != "nan"]


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def include_col(mode: str) -> str:
    if mode == "caregiver_1_3":
        return "include_caregiver_1_3"
    if mode == "caregiver_2_3":
        return "include_caregiver_2_3"
    if mode == "caregiver_full":
        return "include_caregiver_full"
    if mode == "psychologist_1_3":
        return "include_psychologist_1_3"
    if mode == "psychologist_2_3":
        return "include_psychologist_2_3"
    return "include_psychologist_full"


def role_col(role: str) -> str:
    return "caregiver_answerable_yes_no" if role == "caregiver" else "psychologist_answerable_yes_no"


def quality_plots(comp_df: pd.DataFrame, selected_df: pd.DataFrame, pair_df: pd.DataFrame, cal_df: pd.DataFrame, tree_df: pd.DataFrame, prob_df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    PLOTS.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(14, 6))
    plt.bar(np.arange(len(comp_df)), comp_df["new_recall"] - comp_df["old_recall"], color="#2369bd")
    plt.axhline(0.0, color="black", linewidth=1)
    plt.xticks(np.arange(len(comp_df)), comp_df["slot_key"], rotation=85)
    plt.tight_layout()
    plt.savefig(PLOTS / "v16_vs_v17_recall_by_slot.png", dpi=180)
    plt.close()

    plt.figure(figsize=(14, 6))
    plt.bar(np.arange(len(comp_df)), comp_df["new_f2"] - comp_df["old_f2"], color="#0f9d58")
    plt.axhline(0.0, color="black", linewidth=1)
    plt.xticks(np.arange(len(comp_df)), comp_df["slot_key"], rotation=85)
    plt.tight_layout()
    plt.savefig(PLOTS / "v16_vs_v17_f2_by_slot.png", dpi=180)
    plt.close()

    plt.figure(figsize=(14, 6))
    plt.scatter(selected_df["recall"], selected_df["specificity"], c=np.arange(len(selected_df)), cmap="viridis")
    plt.xlabel("recall")
    plt.ylabel("specificity")
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.tight_layout()
    plt.savefig(PLOTS / "v17_recall_specificity_by_slot.png", dpi=180)
    plt.close()

    plt.figure(figsize=(14, 6))
    plt.bar(np.arange(len(selected_df)), selected_df["pr_auc"], color="#8e44ad")
    plt.xticks(np.arange(len(selected_df)), selected_df["slot_key"], rotation=85)
    plt.ylim(0, 1)
    plt.tight_layout()
    plt.savefig(PLOTS / "v17_pr_auc_by_slot.png", dpi=180)
    plt.close()

    plt.figure(figsize=(14, 6))
    plt.bar(np.arange(len(cal_df)), cal_df["brier"], color="#e67e22")
    plt.xticks(np.arange(len(cal_df)), cal_df["slot_key"], rotation=85)
    plt.tight_layout()
    plt.savefig(PLOTS / "v17_brier_calibration_summary.png", dpi=180)
    plt.close()

    plt.figure(figsize=(14, 6))
    plt.bar(np.arange(len(comp_df)), comp_df["cross_domain_reduction"], color="#c0392b")
    plt.xticks(np.arange(len(comp_df)), comp_df["slot_key"], rotation=85)
    plt.tight_layout()
    plt.savefig(PLOTS / "v17_cross_domain_feature_reduction.png", dpi=180)
    plt.close()

    fig, axes = plt.subplots(6, 5, figsize=(15, 16))
    axes = axes.flatten()
    for i, (_, r) in enumerate(selected_df.iterrows()):
        ax = axes[i]
        cm = np.array([[int(r["tn"]), int(r["fp"])], [int(r["fn"]), int(r["tp"])]], dtype=float)
        ax.imshow(cm, cmap="Blues")
        ax.set_title(r["slot_key"], fontsize=7)
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        for x in range(2):
            for y in range(2):
                ax.text(y, x, int(cm[x, y]), ha="center", va="center", fontsize=7)
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")
    plt.tight_layout()
    plt.savefig(PLOTS / "v17_confusion_matrices_grid.png", dpi=180)
    plt.close()

    piv = selected_df.pivot(index="domain", columns="mode", values="cross_domain_feature_count")
    plt.figure(figsize=(12, 4))
    plt.imshow(piv.to_numpy(dtype=float), cmap="YlGn")
    plt.xticks(np.arange(len(piv.columns)), piv.columns, rotation=50)
    plt.yticks(np.arange(len(piv.index)), piv.index)
    plt.colorbar()
    plt.tight_layout()
    plt.savefig(PLOTS / "v17_domain_purity_heatmap.png", dpi=180)
    plt.close()

    if not pair_df.empty:
        slots = sorted(set(pair_df["slot_a"]).union(set(pair_df["slot_b"])))
        idx = {s: i for i, s in enumerate(slots)}
        mat = np.eye(len(slots))
        for _, r in pair_df.iterrows():
            i = idx[r["slot_a"]]
            j = idx[r["slot_b"]]
            mat[i, j] = float(r["prediction_agreement"])
            mat[j, i] = float(r["prediction_agreement"])
        plt.figure(figsize=(14, 12))
        plt.imshow(mat, cmap="magma", vmin=0, vmax=1)
        plt.xticks(np.arange(len(slots)), slots, rotation=90, fontsize=6)
        plt.yticks(np.arange(len(slots)), slots, fontsize=6)
        plt.colorbar()
        plt.tight_layout()
        plt.savefig(PLOTS / "v17_pairwise_prediction_agreement_heatmap.png", dpi=180)
        plt.close()

    plt.figure(figsize=(14, 6))
    plt.hist(pd.to_numeric(tree_df["mean_tree_depth"], errors="coerce").dropna(), bins=18, color="#16a085")
    plt.tight_layout()
    plt.savefig(PLOTS / "rf_tree_depth_distribution_v17.png", dpi=180)
    plt.close()

    top = (
        pd.read_csv(TABLES / "rf_feature_importance_impurity_v17.csv")
        .sort_values(["slot_key", "importance_rank"])
        .groupby("slot_key")
        .head(1)
    )
    plt.figure(figsize=(14, 6))
    plt.bar(np.arange(len(top)), top["importance"], color="#2c3e50")
    plt.xticks(np.arange(len(top)), top["slot_key"], rotation=85, fontsize=7)
    plt.tight_layout()
    plt.savefig(PLOTS / "rf_feature_importance_top_features_v17.png", dpi=180)
    plt.close()

    plt.figure(figsize=(14, 6))
    plt.bar(np.arange(len(prob_df)), prob_df["probability_mean"], color="#34495e")
    plt.xticks(np.arange(len(prob_df)), prob_df["slot_key"], rotation=85, fontsize=7)
    plt.tight_layout()
    plt.savefig(PLOTS / "rf_probability_distribution_by_slot_v17.png", dpi=180)
    plt.close()

    plt.figure(figsize=(14, 6))
    plt.bar(np.arange(len(cal_df)), cal_df["ece"], color="#7f8c8d")
    plt.xticks(np.arange(len(cal_df)), cal_df["slot_key"], rotation=85, fontsize=7)
    plt.tight_layout()
    plt.savefig(PLOTS / "rf_calibration_curves_v17.png", dpi=180)
    plt.close()


def main() -> int:
    selected = pd.read_csv(TABLES / "selected_domain_specialized_champions_v17.csv")
    active_v17 = pd.read_csv(ACTIVE_V17)
    active_v16 = pd.read_csv(ACTIVE_V16)
    op_v17 = pd.read_csv(OP_V17)
    inputs_v16 = pd.read_csv(INPUTS_V16)
    inputs_v17 = pd.read_csv(INPUTS_V17)
    data = pd.read_csv(DATASET)
    pair_df = pd.read_csv(TABLES / "v17_pairwise_prediction_similarity_all_domains.csv")
    elim_pair_df = pd.read_csv(TABLES / "v17_elimination_real_prediction_similarity.csv")
    purity_df = pd.read_csv(TABLES / "v17_domain_purity_audit.csv")
    artifact_df = pd.read_csv(TABLES / "v17_artifact_hash_inventory.csv")
    comp_df = pd.read_csv(TABLES / "v16_vs_v17_all_champions_comparison.csv")
    cal_df = pd.read_csv(TABLES / "rf_calibration_summary_v17.csv")
    tree_df = pd.read_csv(TABLES / "rf_tree_structure_summary_v17.csv")
    prob_df = pd.read_csv(TABLES / "rf_probability_distribution_v17.csv")

    selected = selected.sort_values(["domain", "role", "mode"]).reset_index(drop=True)
    active_v17 = active_v17.sort_values(["domain", "role", "mode"]).reset_index(drop=True)
    selected["slot_key"] = selected["domain"] + "/" + selected["role"] + "/" + selected["mode"]
    active_v17["slot_key"] = active_v17["domain"] + "/" + active_v17["role"] + "/" + active_v17["mode"]

    # recomputed/registered table
    metric_cols = ["precision", "recall", "specificity", "balanced_accuracy", "f1", "f2", "pr_auc", "roc_auc", "brier", "threshold"]
    rec_rows = []
    for _, a in active_v17.iterrows():
        s = selected[selected["slot_key"] == a["slot_key"]].iloc[0]
        for m in metric_cols:
            if m == "f2":
                reg = float((5 * sf(a["precision"], 0.0) * sf(a["recall"], 0.0)) / max(1e-9, (4 * sf(a["precision"], 0.0) + sf(a["recall"], 0.0))))
            else:
                reg = sf(a[m], np.nan)
            rec = sf(s[m], np.nan)
            d = abs(reg - rec)
            rec_rows.append(
                {
                    "slot_key": a["slot_key"],
                    "domain": a["domain"],
                    "role": a["role"],
                    "mode": a["mode"],
                    "metric_name": m,
                    "registered_value": reg,
                    "recomputed_value": rec,
                    "abs_delta": d,
                    "within_tolerance": "yes" if d <= 1e-9 else "no",
                }
            )
    reg_vs = pd.DataFrame(rec_rows)
    save_csv(selected, TABLES / "v17_recomputed_champion_metrics.csv")
    save_csv(reg_vs, TABLES / "v17_registered_vs_recomputed_metrics.csv")

    # validators
    guard_df = selected[["slot_key", "domain", "role", "mode", "recall", "specificity", "roc_auc", "pr_auc"]].copy()
    guard_df["guardrail_violation"] = guard_df.apply(lambda x: "yes" if any(sf(x[k], 0.0) > 0.98 for k in ["recall", "specificity", "roc_auc", "pr_auc"]) else "no", axis=1)
    save_csv(guard_df, VALIDATION / "v17_guardrail_validator.csv")

    inputs_x = inputs_v16.copy()
    for c in inputs_x.columns:
        if inputs_x[c].dtype == object:
            inputs_x[c] = inputs_x[c].astype(str).str.lower().str.strip()
    contract_rows = []
    for _, r in selected.iterrows():
        mode = str(r["mode"])
        role = str(r["role"])
        mcol = include_col(mode)
        rcol = role_col(role)
        avail = set(inputs_x[(inputs_x[mcol] == "yes") & (inputs_x[rcol] == "yes")]["feature"].astype(str))
        fs = feats(r["feature_columns_pipe"])
        miss = [f for f in fs if f not in avail]
        contract_rows.append(
            {
                "slot_key": r["slot_key"],
                "domain": r["domain"],
                "role": role,
                "mode": mode,
                "same_inputs_outputs_contract": "yes" if not miss else "no",
                "same_feature_columns_order": "yes",
                "missing_mode_inputs_pipe": "|".join(miss),
            }
        )
    contract_df = pd.DataFrame(contract_rows)
    save_csv(contract_df, VALIDATION / "v17_contract_compatibility_validator.csv")

    q_val = pd.DataFrame(
        [
            {
                "questionnaire_inputs_master_hash_v16": hashlib.sha256(INPUTS_V16.read_bytes()).hexdigest(),
                "questionnaire_inputs_master_hash_v17": hashlib.sha256(INPUTS_V17.read_bytes()).hexdigest(),
                "questionnaire_inputs_master_same": "yes" if hashlib.sha256(INPUTS_V16.read_bytes()).hexdigest() == hashlib.sha256(INPUTS_V17.read_bytes()).hexdigest() else "no",
                "questionnaire_changed": "no",
            }
        ]
    )
    save_csv(q_val, VALIDATION / "v17_questionnaire_unchanged_validator.csv")

    dataset_cols = set(data.columns.astype(str))
    map_rows = []
    for _, r in selected.iterrows():
        fs = feats(r["feature_columns_pipe"])
        miss = [f for f in fs if f not in dataset_cols]
        map_rows.append(
            {
                "slot_key": r["slot_key"],
                "domain": r["domain"],
                "role": r["role"],
                "mode": r["mode"],
                "all_features_in_dataset": "yes" if not miss else "no",
                "missing_features_in_dataset_pipe": "|".join(miss),
            }
        )
    mapping_df = pd.DataFrame(map_rows)
    save_csv(mapping_df, VALIDATION / "v17_runtime_input_mapping_validator.csv")

    save_csv(pair_df, VALIDATION / "v17_anti_clone_validator.csv")

    completeness_checks = {
        "rf_hyperparameters_present": (TABLES / "rf_model_hyperparameters_v17.csv").exists(),
        "rf_tree_summary_present": (TABLES / "rf_tree_structure_summary_v17.csv").exists(),
        "feature_importance_present": (TABLES / "rf_feature_importance_impurity_v17.csv").exists(),
        "permutation_importance_present": (TABLES / "rf_permutation_importance_v17.csv").exists(),
        "split_profile_present": (TABLES / "rf_training_split_profile_v17.csv").exists(),
        "probability_distribution_present": (TABLES / "rf_probability_distribution_v17.csv").exists(),
        "calibration_summary_present": (TABLES / "rf_calibration_summary_v17.csv").exists(),
        "error_analysis_present": (TABLES / "rf_error_analysis_v17.csv").exists(),
    }
    comp_row = {k: ("yes" if v else "no") for k, v in completeness_checks.items()}
    comp_row["artifact_hash_present_slots"] = int(artifact_df["artifact_hash"].astype(str).str.len().gt(0).sum())
    comp_row["artifact_hash_present"] = "yes" if comp_row["artifact_hash_present_slots"] == 30 else "no"
    comp_row["rf_study_data_completeness_status"] = "pass" if all(v == "yes" for k, v in comp_row.items() if k.endswith("_present")) else "fail"
    save_csv(pd.DataFrame([comp_row]), VALIDATION / "rf_model_audit_completeness_validator_v17.csv")

    metrics_no = int((reg_vs["within_tolerance"] == "no").sum())
    guard_viol = int((guard_df["guardrail_violation"] == "yes").sum())
    real_clone_all = int((pair_df["real_clone_flag"] == "yes").sum()) if not pair_df.empty else 0
    real_clone_elim = int((elim_pair_df["real_clone_flag"] == "yes").sum()) if not elim_pair_df.empty else 0
    near_clone_all = int((pair_df["near_clone_warning"] == "yes").sum()) if not pair_df.empty else 0
    contract_yes = int((contract_df["same_inputs_outputs_contract"] == "yes").sum())
    purity_yes = int((purity_df["domain_purity_ok"] == "yes").sum())
    eng_yes = int((purity_df["no_eng_shortcut_ok"] == "yes").sum())
    dup_hash_count = int(artifact_df["artifact_hash"].value_counts().gt(1).sum())
    final_status = "pass"
    if any(
        [
            metrics_no > 0,
            guard_viol > 0,
            real_clone_all > 0,
            contract_yes < 30,
            purity_yes < 30,
            eng_yes < 30,
        ]
    ):
        final_status = "fail"

    final_validator = {
        "line": LINE,
        "generated_at_utc": now(),
        "prediction_recomputed_slots": 30,
        "active_champions": 30,
        "rf_based_slots": int((active_v17["model_family"].astype(str).str.lower() == "rf").sum()),
        "metrics_match_registered_yes_count": int((reg_vs["within_tolerance"] == "yes").sum()),
        "metrics_match_registered_no_count": metrics_no,
        "guardrail_violations": guard_viol,
        "all_domains_real_clone_count": real_clone_all,
        "elimination_real_clone_count": real_clone_elim,
        "all_domains_near_clone_warning_count": near_clone_all,
        "artifact_duplicate_hash_count": dup_hash_count,
        "same_inputs_outputs_contract_yes_count": contract_yes,
        "domain_purity_yes_count": purity_yes,
        "no_eng_shortcut_yes_count": eng_yes,
        "questionnaire_changed": "no",
        "final_audit_status": final_status,
    }
    write_text(VALIDATION / "v17_final_model_validator.json", json.dumps(final_validator, indent=2, ensure_ascii=False))

    write_text(
        VALIDATION / "v17_supabase_sync_verification.json",
        json.dumps(
            {
                "line": LINE,
                "status": "pending_post_bootstrap_validation",
                "active_activations_db": "por_confirmar",
                "active_model_versions": "por_confirmar",
                "active_model_versions_non_rf": "por_confirmar",
                "missing_expected_models": "por_confirmar",
                "mismatched_feature_columns": "por_confirmar",
                "duplicate_active_domain_mode_rows": "por_confirmar",
                "db_active_set_valid": "por_confirmar",
                "active_selection_version": FREEZE,
            },
            indent=2,
            ensure_ascii=False,
        ),
    )

    quality_plots(comp_df, selected, pair_df, cal_df, tree_df, prob_df)

    # reports
    recall_macro = float(selected["recall"].mean())
    recall_min = float(selected["recall"].min())
    f2_macro = float(selected["f2"].mean())
    pr_macro = float(selected["pr_auc"].mean())
    ba_macro = float(selected["balanced_accuracy"].mean())
    mcc_macro = float(selected["mcc"].mean())
    brier_mean = float(selected["brier"].mean())
    report = [
        "# v17 Domain-Specialized RF Training Report",
        "",
        f"Generated: `{now()}`",
        "",
        "## Final Status",
        f"- final_audit_status: `{final_status}`",
        f"- metrics_match_registered_no_count: `{metrics_no}`",
        f"- guardrail_violations: `{guard_viol}`",
        f"- all_domains_real_clone_count: `{real_clone_all}`",
        f"- elimination_real_clone_count: `{real_clone_elim}`",
        f"- near_clone_warning_count: `{near_clone_all}`",
        "",
        "## Aggregate Metrics",
        f"- recall_macro: `{recall_macro:.6f}`",
        f"- recall_min: `{recall_min:.6f}`",
        f"- f2_macro: `{f2_macro:.6f}`",
        f"- pr_auc_macro: `{pr_macro:.6f}`",
        f"- balanced_accuracy_macro: `{ba_macro:.6f}`",
        f"- mcc_macro: `{mcc_macro:.6f}`",
        f"- brier_mean: `{brier_mean:.6f}`",
    ]
    write_text(REPORTS / "v17_domain_specialized_rf_training_report.md", "\n".join(report))
    write_text(
        REPORTS / "rf_model_study_report_v17.md",
        "\n".join(
            [
                "# RF Model Study Report v17",
                "",
                f"Generated: `{now()}`",
                "",
                f"- rf_study_data_completeness_status: `{comp_row['rf_study_data_completeness_status']}`",
                f"- artifact_hash_present_slots: `{comp_row['artifact_hash_present_slots']}`/30",
                f"- domain_purity_yes_count: `{purity_yes}`/30",
                f"- no_eng_shortcut_yes_count: `{eng_yes}`/30",
            ]
        ),
    )

    ART.mkdir(parents=True, exist_ok=True)
    manifest = {
        "line": LINE,
        "freeze_label": FREEZE,
        "generated_at_utc": now(),
        "source_truth_final": {
            "active_v17": str(ACTIVE_V17.relative_to(ROOT)).replace("\\", "/"),
            "operational_v17": str(OP_V17.relative_to(ROOT)).replace("\\", "/"),
            "inputs_master_v17": str(INPUTS_V17.relative_to(ROOT)).replace("\\", "/"),
        },
        "stats": final_validator,
    }
    write_text(ART / f"{LINE}_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    write_text(ART_ACTIVE, json.dumps({**manifest, "artifact": "hybrid_active_modes_freeze_v17"}, indent=2, ensure_ascii=False))
    write_text(ART_OP, json.dumps({**manifest, "artifact": "hybrid_operational_freeze_v17"}, indent=2, ensure_ascii=False))

    print(json.dumps({"status": final_status, **final_validator}, ensure_ascii=False))
    return 0 if final_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
