from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from versioning_utils import ensure_versioning_dirs, load_registry, metric_value, save_registry, utcnow_iso


TARGET_DISORDERS = ["depression", "conduct", "elimination"]


def _extract_metrics(row: pd.Series, split: str) -> Dict[str, float]:
    key = "validation_metrics_json" if split == "val" else "test_metrics_json"
    return {
        "balanced_accuracy": metric_value(row[key], "balanced_accuracy"),
        "recall": metric_value(row[key], "recall"),
        "specificity": metric_value(row[key], "specificity"),
        "f1": metric_value(row[key], "f1"),
    }


def _champions(registry: pd.DataFrame) -> pd.DataFrame:
    champions = registry[
        (registry["promoted"].astype(str).str.lower() == "yes")
        & (registry["promoted_status"].astype(str).str.lower() == "champion")
    ].copy()
    if champions.empty:
        promoted = registry[registry["status"] == "promoted"].copy()
        return promoted.sort_values("training_date").groupby("disorder", as_index=False).tail(1)
    return champions


def _copy_current_alias(root: Path, model_version: str, disorder: str) -> None:
    src = root / "models" / "versioned" / model_version
    if not src.exists():
        return
    alias_name = "rf_multilabel_current" if disorder == "multilabel" else f"rf_{disorder}_current"
    dst = root / "models" / "champions" / alias_name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _is_promotable(row: pd.Series) -> bool:
    scope = str(row.get("data_scope", ""))
    notes = str(row.get("notes", "")).lower()
    if scope == "research_extended":
        return False
    if "experimental" in notes:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote challenger models to champion status using val-first policy.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    dirs = ensure_versioning_dirs(root)
    registry_path = dirs["reports_versioning"] / "model_registry.csv"
    registry_jsonl = dirs["reports_versioning"] / "model_registry.jsonl"

    registry = load_registry(registry_path)
    for col in ["status", "promoted", "promoted_status", "rejection_reason", "notes"]:
        if col not in registry.columns:
            registry[col] = ""
        registry[col] = registry[col].fillna("").astype(str)
    champions = _champions(registry)

    decisions: List[str] = ["# Promotion Decisions", ""]
    recs: List[str] = ["# Final Champion Recommendations", ""]
    promoted_versions: Dict[str, str] = {}

    for disorder in TARGET_DISORDERS:
        current = champions[(champions["disorder"] == disorder) & (champions["task_type"] == "binary")]
        if current.empty:
            decisions.append(f"- {disorder}: no current champion found, skipped.")
            continue
        champ = current.iloc[0]
        champ_val = _extract_metrics(champ, "val")
        champ_test = _extract_metrics(champ, "test")

        challengers = registry[
            (registry["disorder"] == disorder)
            & (registry["task_type"] == "binary")
            & (registry["model_version"] != champ["model_version"])
            & (registry["status"].isin(["completed", "rejected", "promoted"]))
        ].copy()

        if challengers.empty:
            promoted_versions[disorder] = str(champ["model_version"])
            decisions.append(f"- {disorder}: no challengers, champion remains `{champ['model_version']}`.")
            continue

        challengers["val_bal_acc"] = challengers["validation_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
        challengers["val_recall"] = challengers["validation_metrics_json"].apply(lambda s: metric_value(s, "recall"))
        challengers["val_specificity"] = challengers["validation_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
        challengers["val_f1"] = challengers["validation_metrics_json"].apply(lambda s: metric_value(s, "f1"))
        challengers["test_bal_acc"] = challengers["test_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
        challengers["test_recall"] = challengers["test_metrics_json"].apply(lambda s: metric_value(s, "recall"))
        challengers["test_specificity"] = challengers["test_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
        challengers["test_f1"] = challengers["test_metrics_json"].apply(lambda s: metric_value(s, "f1"))
        challengers = challengers.sort_values(
            ["val_bal_acc", "val_recall", "val_specificity", "val_f1", "n_features_final"],
            ascending=[False, False, False, False, True],
        )
        candidate = challengers.iloc[0]

        if not _is_promotable(candidate):
            idx = registry["model_version"] == candidate["model_version"]
            registry.loc[idx, "status"] = "rejected"
            registry.loc[idx, "rejection_reason"] = "non_promotable_scope_or_experimental"
            promoted_versions[disorder] = str(champ["model_version"])
            decisions.append(
                f"- {disorder}: `{candidate['model_version']}` rejected (research/experimental), champion remains `{champ['model_version']}`."
            )
            continue

        improvement_bal = float(candidate["val_bal_acc"] - champ_val["balanced_accuracy"])
        recall_delta = float(candidate["val_recall"] - champ_val["recall"])
        spec_delta = float(candidate["val_specificity"] - champ_val["specificity"])
        f1_delta = float(candidate["val_f1"] - champ_val["f1"])

        pass_val = (
            (improvement_bal >= 0.01 and recall_delta >= -0.03 and spec_delta >= -0.05)
            or (improvement_bal >= 0.005 and recall_delta >= 0.0 and f1_delta >= 0.0)
        )
        pass_test = (
            float(candidate["test_bal_acc"]) >= (champ_test["balanced_accuracy"] - 0.005)
            and float(candidate["test_recall"]) >= (champ_test["recall"] - 0.05)
        )

        if pass_val and pass_test:
            old_idx = registry["model_version"] == champ["model_version"]
            new_idx = registry["model_version"] == candidate["model_version"]
            registry.loc[old_idx, "promoted"] = "no"
            registry.loc[old_idx, "promoted_status"] = "former_champion"
            registry.loc[old_idx, "status"] = "completed"
            registry.loc[new_idx, "promoted"] = "yes"
            registry.loc[new_idx, "promoted_status"] = "champion"
            registry.loc[new_idx, "status"] = "promoted"
            registry.loc[new_idx, "rejection_reason"] = ""
            promoted_versions[disorder] = str(candidate["model_version"])
            decisions.append(
                f"- {disorder}: promoted `{candidate['model_version']}` over `{champ['model_version']}` "
                f"(delta val_bal_acc={improvement_bal:.4f}, delta val_recall={recall_delta:.4f}, delta val_specificity={spec_delta:.4f})."
            )
        else:
            cand_idx = registry["model_version"] == candidate["model_version"]
            reason = (
                "insufficient_validation_gain"
                if not pass_val
                else "test_confirmation_failed"
            )
            registry.loc[cand_idx, "status"] = "rejected"
            registry.loc[cand_idx, "rejection_reason"] = reason
            promoted_versions[disorder] = str(champ["model_version"])
            decisions.append(
                f"- {disorder}: kept `{champ['model_version']}`; challenger `{candidate['model_version']}` rejected ({reason})."
            )

    champions_after = _champions(registry)
    champion_rows = champions_after[
        (champions_after["task_type"].isin(["binary", "multilabel"]))
    ].copy()
    champion_rows = champion_rows.sort_values(["task_type", "disorder", "training_date"])
    out_champ = champion_rows[
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
    out_champ["promoted_on"] = utcnow_iso()
    out_champ.to_csv(dirs["reports_versioning"] / "champion_models.csv", index=False)

    for _, row in out_champ.iterrows():
        _copy_current_alias(root, str(row["model_version"]), str(row["disorder"]))

    for disorder in ["adhd", "anxiety", "depression", "conduct", "elimination", "multilabel"]:
        row = out_champ[out_champ["disorder"] == disorder]
        if row.empty:
            continue
        r = row.iloc[0]
        recs.append(
            f"- {disorder}: `{r['model_version']}` (scope={r['data_scope']}, dataset={r['dataset_name']}, strategy={r['feature_strategy']})."
        )

    (dirs["reports_versioning"] / "promotion_decisions.md").write_text("\n".join(decisions) + "\n", encoding="utf-8")
    (dirs["reports_promotions"] / "final_champion_recommendations.md").write_text("\n".join(recs) + "\n", encoding="utf-8")
    save_registry(registry, registry_path, registry_jsonl)


if __name__ == "__main__":
    main()
