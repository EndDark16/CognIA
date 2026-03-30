from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from versioning_utils import ensure_versioning_dirs, load_registry, metric_value, save_registry, utcnow_iso


PRIMARY_DISORDERS = ["depression", "conduct", "elimination"]
SANITY_DISORDERS = ["adhd", "anxiety"]


def _metric_with_fallback(root: Path, row: pd.Series, split: str, metric_key: str) -> float:
    json_col = "validation_metrics_json" if split == "val" else "test_metrics_json"
    value = metric_value(row[json_col], metric_key)
    if pd.notna(value):
        return float(value)
    source_model_id = str(row.get("source_model_id", "")).strip()
    if not source_model_id:
        return float("nan")
    result_path = root / "reports" / "training" / source_model_id / "result.json"
    if not result_path.exists():
        return float("nan")
    try:
        import json

        data = json.loads(result_path.read_text(encoding="utf-8"))
        split_key = "validation_metrics" if split == "val" else "test_metrics"
        metrics = data.get(split_key, {})
        return float(metrics.get(metric_key, float("nan")))
    except Exception:
        return float("nan")


def _extract(root: Path, row: pd.Series, split: str) -> Dict[str, float]:
    return {
        "precision": _metric_with_fallback(root, row, split, "precision"),
        "recall": _metric_with_fallback(root, row, split, "recall"),
        "specificity": _metric_with_fallback(root, row, split, "specificity"),
        "balanced_accuracy": _metric_with_fallback(root, row, split, "balanced_accuracy"),
        "f1": _metric_with_fallback(root, row, split, "f1"),
    }


def _is_non_promotable(row: pd.Series) -> bool:
    scope = str(row.get("data_scope", ""))
    notes = str(row.get("notes", "")).lower()
    return scope == "research_extended" or "experimental_only" in notes or "experimental" in notes


def _promotion_threshold(disorder: str) -> float:
    return 0.03 if disorder in PRIMARY_DISORDERS else 0.02


def _copy_champion_alias(root: Path, model_version: str, disorder: str) -> None:
    src = root / "models" / "versioned" / model_version
    if not src.exists():
        return
    alias = root / "models" / "champions" / (f"rf_{disorder}_current" if disorder != "multilabel" else "rf_multilabel_current")
    if alias.exists():
        shutil.rmtree(alias)
    shutil.copytree(src, alias)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare and promote precision challengers with validation-first policy.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    dirs = ensure_versioning_dirs(root)
    registry_path = dirs["reports_versioning"] / "model_registry.csv"
    registry_jsonl = dirs["reports_versioning"] / "model_registry.jsonl"
    registry = load_registry(registry_path)
    for col in ["status", "promoted", "promoted_status", "rejection_reason", "notes"]:
        registry[col] = registry[col].fillna("").astype(str)

    champions = registry[
        (registry["task_type"] == "binary")
        & (registry["promoted"].str.lower() == "yes")
        & (registry["promoted_status"].str.lower() == "champion")
    ].copy()
    challengers = registry[
        (registry["task_type"] == "binary")
        & (registry["model_version"].astype(str).str.contains("_precision_"))
        & (registry["status"].isin(["completed", "rejected", "failed"]))
    ].copy()

    comparison_rows: List[Dict[str, Any]] = []
    decisions: List[str] = ["# Precision Promotion Recommendations", ""]

    for disorder in PRIMARY_DISORDERS + SANITY_DISORDERS:
        champ = champions[champions["disorder"] == disorder]
        if champ.empty:
            decisions.append(f"- {disorder}: no champion found, skipped.")
            continue
        champ_row = champ.iloc[0]
        champ_val = _extract(root, champ_row, "val")
        champ_test = _extract(root, champ_row, "test")

        sub = challengers[challengers["disorder"] == disorder].copy()
        if sub.empty:
            decisions.append(f"- {disorder}: no precision challengers found.")
            continue

        sub["val_precision"] = sub["validation_metrics_json"].apply(lambda s: metric_value(s, "precision"))
        sub["val_recall"] = sub["validation_metrics_json"].apply(lambda s: metric_value(s, "recall"))
        sub["val_balanced_accuracy"] = sub["validation_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
        sub["val_specificity"] = sub["validation_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
        sub["test_precision"] = sub["test_metrics_json"].apply(lambda s: metric_value(s, "precision"))
        sub["test_recall"] = sub["test_metrics_json"].apply(lambda s: metric_value(s, "recall"))
        sub["test_balanced_accuracy"] = sub["test_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
        sub["test_specificity"] = sub["test_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
        sub = sub.sort_values(
            ["val_precision", "val_balanced_accuracy", "val_recall", "val_specificity"],
            ascending=[False, False, False, False],
        )

        for _, row in sub.iterrows():
            comparison_rows.append(
                {
                    "disorder": disorder,
                    "champion_version": champ_row["model_version"],
                    "challenger_version": row["model_version"],
                    "challenger_scope": row["data_scope"],
                    "challenger_status": row["status"],
                    "non_promotable": _is_non_promotable(row),
                    "champion_val_precision": champ_val["precision"],
                    "champion_val_recall": champ_val["recall"],
                    "champion_val_balanced_accuracy": champ_val["balanced_accuracy"],
                    "champion_test_precision": champ_test["precision"],
                    "champion_test_recall": champ_test["recall"],
                    "champion_test_balanced_accuracy": champ_test["balanced_accuracy"],
                    "challenger_val_precision": row["val_precision"],
                    "challenger_val_recall": row["val_recall"],
                    "challenger_val_balanced_accuracy": row["val_balanced_accuracy"],
                    "challenger_test_precision": row["test_precision"],
                    "challenger_test_recall": row["test_recall"],
                    "challenger_test_balanced_accuracy": row["test_balanced_accuracy"],
                    "delta_val_precision": row["val_precision"] - champ_val["precision"],
                    "delta_val_recall": row["val_recall"] - champ_val["recall"],
                    "delta_val_balanced_accuracy": row["val_balanced_accuracy"] - champ_val["balanced_accuracy"],
                    "delta_test_precision": row["test_precision"] - champ_test["precision"],
                    "delta_test_recall": row["test_recall"] - champ_test["recall"],
                    "delta_test_balanced_accuracy": row["test_balanced_accuracy"] - champ_test["balanced_accuracy"],
                    "recall_floor": float(row.get("recall_floor") or 0.0),
                    "balanced_accuracy_tolerance": float(row.get("balanced_accuracy_tolerance") or 0.03),
                }
            )

        candidate = sub.iloc[0]
        if _is_non_promotable(candidate):
            idx = registry["model_version"] == candidate["model_version"]
            registry.loc[idx, "status"] = "rejected"
            registry.loc[idx, "rejection_reason"] = "non_promotable_scope"
            decisions.append(
                f"- {disorder}: `{candidate['model_version']}` no promovible (research/experimental). Se mantiene `{champ_row['model_version']}`."
            )
            continue

        min_precision_gain = _promotion_threshold(disorder)
        recall_floor = float(candidate.get("recall_floor") or max(0.55, champ_val["recall"] - 0.12))
        bal_tol = float(candidate.get("balanced_accuracy_tolerance") or (0.05 if disorder == "elimination" else 0.03))
        val_precision_gain = float(candidate["val_precision"] - champ_val["precision"])

        pass_val = (
            val_precision_gain >= min_precision_gain
            and float(candidate["val_recall"]) >= recall_floor
            and float(candidate["val_balanced_accuracy"]) >= float(champ_val["balanced_accuracy"] - bal_tol)
        )
        pass_test = (
            float(candidate["test_precision"]) >= float(champ_test["precision"] - 0.005)
            and float(candidate["test_recall"]) >= float(max(recall_floor - 0.05, 0.40))
            and float(candidate["test_balanced_accuracy"]) >= float(champ_test["balanced_accuracy"] - (bal_tol + 0.02))
        )

        if pass_val and pass_test:
            old_idx = registry["model_version"] == champ_row["model_version"]
            new_idx = registry["model_version"] == candidate["model_version"]
            registry.loc[old_idx, "promoted"] = "no"
            registry.loc[old_idx, "promoted_status"] = "former_champion"
            registry.loc[old_idx, "status"] = "completed"
            registry.loc[new_idx, "promoted"] = "yes"
            registry.loc[new_idx, "promoted_status"] = "champion"
            registry.loc[new_idx, "status"] = "promoted"
            registry.loc[new_idx, "rejection_reason"] = ""
            decisions.append(
                f"- {disorder}: PROMOVIDO `{candidate['model_version']}` "
                f"(delta val precision={val_precision_gain:.4f}, recall floor={recall_floor:.3f}, bal_tol={bal_tol:.3f})."
            )
        else:
            idx = registry["model_version"] == candidate["model_version"]
            reason = "validation_precision_or_constraints_not_met" if not pass_val else "test_confirmation_not_met"
            registry.loc[idx, "status"] = "rejected"
            registry.loc[idx, "rejection_reason"] = reason
            decisions.append(
                f"- {disorder}: rechazado `{candidate['model_version']}` ({reason}). Se mantiene `{champ_row['model_version']}`."
            )

    # Refresh champions after promotions
    champions_after = registry[
        (registry["promoted"].str.lower() == "yes")
        & (registry["promoted_status"].str.lower() == "champion")
    ].copy()
    champion_out = champions_after[
        [
            "disorder",
            "task_type",
            "model_version",
            "dataset_name",
            "data_scope",
            "feature_strategy",
            "training_date",
            "status",
        ]
    ].copy()
    champion_out["promoted_on"] = utcnow_iso()
    champion_out.to_csv(dirs["reports_versioning"] / "champion_models.csv", index=False)

    for _, row in champion_out.iterrows():
        _copy_champion_alias(root, str(row["model_version"]), str(row["disorder"]))

    matrix = pd.DataFrame(comparison_rows).sort_values(
        ["disorder", "delta_val_precision", "delta_val_balanced_accuracy"],
        ascending=[True, False, False],
    )
    matrix.to_csv(dirs["reports_promotions"] / "precision_model_comparison_matrix.csv", index=False)

    recommendations_path = dirs["reports_promotions"] / "precision_promotion_recommendations.md"
    recommendations_path.write_text("\n".join(decisions) + "\n", encoding="utf-8")

    decisions_md = dirs["reports_versioning"] / "promotion_decisions.md"
    if decisions_md.exists():
        prior = decisions_md.read_text(encoding="utf-8")
        marker = "## Precision Campaign"
        if marker in prior:
            prior = prior.split(marker, 1)[0].rstrip()
        merged = prior.rstrip() + "\n\n## Precision Campaign\n\n" + "\n".join(decisions[2:]) + "\n"
    else:
        merged = "# Promotion Decisions\n\n## Precision Campaign\n\n" + "\n".join(decisions[2:]) + "\n"
    decisions_md.write_text(merged, encoding="utf-8")

    save_registry(registry, registry_path, registry_jsonl)


if __name__ == "__main__":
    main()
