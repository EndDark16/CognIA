from __future__ import annotations

import argparse
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd

from evaluate_abstention_policy import evaluate_abstention_policy
from ml_rf_common import (
    RANDOM_STATE,
    TARGET_COLUMNS,
    approximate_local_contributors,
    binary_metrics,
    compute_importance_reports,
    plot_binary_curves,
    sanitize_features,
)
from optimize_precision_thresholds import PrecisionThresholdPolicy, optimize_precision_thresholds
from run_versioned_experiments import (
    _current_champion_map,
    _fit_calibrator,
    _fit_search,
    _load_frozen_splits,
    _relative,
    _resolve_dataset_path,
    _resolve_split_dir,
    _save_feature_list,
    apply_feature_strategy,
)
from versioning_utils import ensure_versioning_dirs, load_registry, metric_value, save_registry, to_json_str, utcnow_iso


LOGGER = logging.getLogger("rf-precision-campaign")


@dataclass(frozen=True)
class PrecisionExperiment:
    model_version: str
    disorder: str
    dataset_name: str
    data_scope: str
    feature_strategy: str
    top_k: Optional[int]
    class_balance_strategy: str
    calibration_strategy: str
    notes: str
    priority: str  # primary | sanity
    experimental: bool = False

    @property
    def target(self) -> str:
        return f"target_{self.disorder}"

    @property
    def dataset_variant(self) -> str:
        parts = self.dataset_name.split("_")
        return "_".join(parts[2:]) if len(parts) >= 3 else self.dataset_name


PRIMARY_EXPERIMENTS: List[PrecisionExperiment] = [
    PrecisionExperiment(
        model_version="rf_depression_v4_precision_thresholded",
        disorder="depression",
        dataset_name="dataset_depression_parent",
        data_scope="strict_no_leakage",
        feature_strategy="mi_top_k",
        top_k=18,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="none",
        notes="Precision-focused threshold optimization on depression parent set.",
        priority="primary",
    ),
    PrecisionExperiment(
        model_version="rf_depression_v5_precision_calibrated",
        disorder="depression",
        dataset_name="dataset_depression_parent",
        data_scope="strict_no_leakage",
        feature_strategy="mi_top_k",
        top_k=24,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="sigmoid",
        notes="Depression precision challenger with calibration + constrained threshold.",
        priority="primary",
    ),
    PrecisionExperiment(
        model_version="rf_depression_v6_precision_pruned",
        disorder="depression",
        dataset_name="dataset_depression_combined",
        data_scope="strict_no_leakage",
        feature_strategy="mi_top_k",
        top_k=16,
        class_balance_strategy="balanced",
        calibration_strategy="sigmoid",
        notes="Aggressive pruning on combined depression features for PPV uplift.",
        priority="primary",
    ),
    PrecisionExperiment(
        model_version="rf_conduct_v4_precision_thresholded",
        disorder="conduct",
        dataset_name="dataset_conduct_minimal",
        data_scope="strict_no_leakage",
        feature_strategy="mi_top_k",
        top_k=18,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="none",
        notes="Conduct minimal set tuned for precision with constrained threshold.",
        priority="primary",
    ),
    PrecisionExperiment(
        model_version="rf_conduct_v5_precision_calibrated",
        disorder="conduct",
        dataset_name="dataset_conduct_clinical",
        data_scope="strict_no_leakage",
        feature_strategy="externalizing_focus",
        top_k=26,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="sigmoid",
        notes="Clinical conduct challenger with externalizing focus and calibration.",
        priority="primary",
    ),
    PrecisionExperiment(
        model_version="rf_conduct_v6_precision_externalizing_pruned",
        disorder="conduct",
        dataset_name="dataset_conduct_clinical",
        data_scope="strict_no_leakage",
        feature_strategy="externalizing_focus",
        top_k=18,
        class_balance_strategy="balanced",
        calibration_strategy="none",
        notes="Externalizing-focused pruned conduct challenger for PPV improvement.",
        priority="primary",
    ),
    PrecisionExperiment(
        model_version="rf_elimination_v5_precision_missingness",
        disorder="elimination",
        dataset_name="dataset_elimination_core",
        data_scope="strict_no_leakage",
        feature_strategy="missingness_augmented",
        top_k=None,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="sigmoid",
        notes="Elimination core with missingness flags and precision-constrained threshold.",
        priority="primary",
    ),
    PrecisionExperiment(
        model_version="rf_elimination_v6_precision_proxy_pruned",
        disorder="elimination",
        dataset_name="dataset_elimination_items",
        data_scope="strict_no_leakage",
        feature_strategy="proxy_pruned",
        top_k=36,
        class_balance_strategy="balanced",
        calibration_strategy="sigmoid",
        notes="Elimination proxy-pruned precision challenger.",
        priority="primary",
    ),
    PrecisionExperiment(
        model_version="rf_elimination_v7_precision_experimental_research",
        disorder="elimination",
        dataset_name="dataset_elimination_core",
        data_scope="research_extended",
        feature_strategy="missingness_augmented",
        top_k=None,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="sigmoid",
        notes="Research scope precision challenger (non-promotable by policy).",
        priority="primary",
        experimental=True,
    ),
]


SANITY_EXPERIMENTS: List[PrecisionExperiment] = [
    PrecisionExperiment(
        model_version="rf_adhd_v2_precision_sanity",
        disorder="adhd",
        dataset_name="dataset_adhd_clinical",
        data_scope="strict_no_leakage",
        feature_strategy="mi_top_k",
        top_k=20,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="none",
        notes="Light sanity challenger for ADHD precision.",
        priority="sanity",
    ),
    PrecisionExperiment(
        model_version="rf_anxiety_v2_precision_sanity",
        disorder="anxiety",
        dataset_name="dataset_anxiety_items",
        data_scope="strict_no_leakage",
        feature_strategy="mi_top_k",
        top_k=20,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="none",
        notes="Light sanity challenger for Anxiety precision.",
        priority="sanity",
    ),
]


def _setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _precision_floor_settings(disorder: str, champ_recall: float, champ_bal_acc: float) -> Tuple[float, float]:
    if disorder == "elimination":
        recall_floor = max(0.50, champ_recall - 0.20)
        bal_tol = 0.05
    elif disorder == "conduct":
        recall_floor = max(0.70, champ_recall - 0.15)
        bal_tol = 0.03
    elif disorder == "depression":
        recall_floor = max(0.72, champ_recall - 0.12)
        bal_tol = 0.03
    else:
        recall_floor = max(0.70, champ_recall - 0.12)
        bal_tol = 0.03
    # Safety guard if champion metrics are missing
    if np.isnan(champ_recall):
        recall_floor = 0.70 if disorder != "elimination" else 0.50
    if np.isnan(champ_bal_acc):
        bal_tol = 0.05 if disorder == "elimination" else 0.03
    return float(recall_floor), float(bal_tol)


def _champion_row(registry: pd.DataFrame, disorder: str) -> pd.Series:
    candidates = registry[
        (registry["disorder"] == disorder)
        & (registry["task_type"] == "binary")
        & (registry["promoted"].astype(str).str.lower() == "yes")
        & (registry["promoted_status"].astype(str).str.lower() == "champion")
    ].copy()
    if candidates.empty:
        raise RuntimeError(f"No champion found for disorder={disorder}")
    return candidates.sort_values("training_date").iloc[-1]


def _compute_extended_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> Dict[str, Any]:
    m = binary_metrics(y_true, y_prob, threshold=threshold)
    prevalence = float(np.mean(y_true == 1))
    m["fpr"] = float(1.0 - m["specificity"])
    m["fnr"] = float(1.0 - m["recall"])
    m["prevalence"] = prevalence
    return m


def _apply_abstention_thresholds(y_true: np.ndarray, y_prob: np.ndarray, low_thr: float, high_thr: float) -> Dict[str, Any]:
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    n = len(y_true)
    pos_mask = y_prob >= high_thr
    neg_mask = y_prob <= low_thr
    uncertain_mask = ~(pos_mask | neg_mask)
    tp = int(np.logical_and(pos_mask, y_true == 1).sum())
    fp = int(np.logical_and(pos_mask, y_true == 0).sum())
    tn = int(np.logical_and(neg_mask, y_true == 0).sum())
    fn_low = int(np.logical_and(neg_mask, y_true == 1).sum())
    total_pos = max(int((y_true == 1).sum()), 1)
    total_neg = max(int((y_true == 0).sum()), 1)
    return {
        "coverage": float((pos_mask.sum() + neg_mask.sum()) / n),
        "uncertain_rate": float(uncertain_mask.mean()),
        "precision_high": float(tp / (tp + fp)) if (tp + fp) else float("nan"),
        "npv_low": float(tn / (tn + fn_low)) if (tn + fn_low) else float("nan"),
        "recall_effective": float(tp / total_pos),
        "specificity_effective": float(tn / total_neg),
        "confident_positive_n": int(pos_mask.sum()),
        "confident_negative_n": int(neg_mask.sum()),
        "uncertain_n": int(uncertain_mask.sum()),
    }


def _write_precision_plan(path: Path, experiments: Sequence[PrecisionExperiment], champion_map: Dict[str, str]) -> None:
    lines = [
        "# Precision Experiment Plan",
        "",
        "Campaign objective: improve precision/PPV while preserving validation rigor and frozen splits.",
        "",
        "## Champions at start",
    ]
    for disorder in sorted(champion_map.keys()):
        lines.append(f"- {disorder}: {champion_map[disorder]}")
    lines.extend(["", "## Planned challengers"])
    for exp in experiments:
        lines.append(
            f"- {exp.model_version}: disorder={exp.disorder}, dataset={exp.dataset_name}, scope={exp.data_scope}, "
            f"feature_strategy={exp.feature_strategy}, class_balance={exp.class_balance_strategy}, "
            f"calibration={exp.calibration_strategy}, priority={exp.priority}, experimental={exp.experimental}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_single_precision_experiment(
    root: Path,
    dirs: Dict[str, Path],
    registry: pd.DataFrame,
    exp: PrecisionExperiment,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    champ = _champion_row(registry, exp.disorder)
    champ_val_precision = metric_value(champ["validation_metrics_json"], "precision")
    champ_val_recall = metric_value(champ["validation_metrics_json"], "recall")
    champ_val_bal = metric_value(champ["validation_metrics_json"], "balanced_accuracy")
    champ_test_precision = metric_value(champ["test_metrics_json"], "precision")
    champ_test_recall = metric_value(champ["test_metrics_json"], "recall")
    champ_test_bal = metric_value(champ["test_metrics_json"], "balanced_accuracy")
    recall_floor, bal_tol = _precision_floor_settings(exp.disorder, champ_val_recall, champ_val_bal)
    bal_floor = float(champ_val_bal - bal_tol) if not np.isnan(champ_val_bal) else 0.55

    dataset_path = _resolve_dataset_path(root, exp.dataset_name, exp.data_scope)
    split_dir = _resolve_split_dir(root, exp.dataset_name, exp.data_scope)
    df = pd.read_csv(dataset_path)
    if exp.target not in df.columns:
        raise RuntimeError(f"Target not found in dataset: {exp.target}")

    X_all, y_df, removed_base = sanitize_features(df, task="binary", target_column=exp.target)
    for target_col in TARGET_COLUMNS:
        if target_col in X_all.columns:
            raise RuntimeError(f"Leakage guard failed: {target_col} present in X ({exp.model_version})")

    split_source = pd.concat([df[["participant_id"]], X_all, y_df], axis=1)
    splits = _load_frozen_splits(split_source, split_dir, exp.target, list(X_all.columns))
    X_train = splits["X_train"].copy()
    X_val = splits["X_val"].copy()
    X_test = splits["X_test"].copy()
    y_train = splits["y_train"][exp.target].astype(int)
    y_val = splits["y_val"][exp.target].astype(int)
    y_test = splits["y_test"][exp.target].astype(int)

    raw_features = X_train.shape[1]
    X_train, X_val, X_test, strategy_meta = apply_feature_strategy(exp, X_train, X_val, X_test, y_train)
    final_features = X_train.shape[1]

    n_iter = 8 if exp.priority == "primary" else 5
    estimator, best_params, search_meta = _fit_search(X_train, y_train, exp.class_balance_strategy, n_iter=n_iter)
    calibrator, calibration_used = _fit_calibrator(exp, estimator, X_train, y_train)
    scorer = calibrator if calibrator is not None else estimator
    val_prob = scorer.predict_proba(X_val)[:, 1]
    test_prob = scorer.predict_proba(X_test)[:, 1]

    policy = PrecisionThresholdPolicy(recall_floor=recall_floor, balanced_accuracy_floor=bal_floor)
    selected_threshold, threshold_eval = optimize_precision_thresholds(y_val.to_numpy(), val_prob, policy)
    threshold = float(selected_threshold["threshold"])
    threshold_method = str(selected_threshold.get("method", "precision_constrained"))

    val_metrics = _compute_extended_metrics(y_val.to_numpy(), val_prob, threshold)
    test_metrics = _compute_extended_metrics(y_test.to_numpy(), test_prob, threshold)

    val_metrics["precision_lift_vs_baseline"] = float(val_metrics["precision"] - champ_val_precision)
    val_metrics["recall_delta_vs_baseline"] = float(val_metrics["recall"] - champ_val_recall)
    val_metrics["balanced_accuracy_delta_vs_baseline"] = float(val_metrics["balanced_accuracy"] - champ_val_bal)
    test_metrics["precision_lift_vs_baseline"] = float(test_metrics["precision"] - champ_test_precision)
    test_metrics["recall_delta_vs_baseline"] = float(test_metrics["recall"] - champ_test_recall)
    test_metrics["balanced_accuracy_delta_vs_baseline"] = float(test_metrics["balanced_accuracy"] - champ_test_bal)

    target_high_precision = min(0.95, max(float(champ_val_precision + 0.10), 0.70))
    abstention_val_summary, abstention_grid = evaluate_abstention_policy(
        y_true=y_val.to_numpy(),
        y_prob=val_prob,
        base_threshold=threshold,
        target_high_precision=target_high_precision,
        min_confident_coverage=0.10,
    )
    abstention_test_summary = _apply_abstention_thresholds(
        y_true=y_test.to_numpy(),
        y_prob=test_prob,
        low_thr=float(abstention_val_summary["low_threshold"]),
        high_thr=float(abstention_val_summary["high_threshold"]),
    )

    model_dir = dirs["models_versioned"] / exp.model_version
    artifact_dir = dirs["artifacts_versioned_models"] / exp.model_version
    report_dir = dirs["reports_experiments"] / exp.model_version
    figure_dir = root / "reports" / "figures" / "precision" / exp.model_version
    for path in [model_dir, artifact_dir, report_dir, figure_dir]:
        path.mkdir(parents=True, exist_ok=True)

    pipeline_path = model_dir / "pipeline.joblib"
    calibrator_path = model_dir / "calibrated.joblib"
    metadata_path = model_dir / "metadata.json"
    manifest_path = model_dir / "manifest.json"
    feature_list_path = model_dir / "feature_list.txt"

    joblib.dump(estimator, pipeline_path)
    if calibrator is not None:
        joblib.dump(calibrator, calibrator_path)

    y_test_pred = (test_prob >= threshold).astype(int)
    figs = plot_binary_curves(y_test.to_numpy(), test_prob, y_test_pred, exp.model_version, figure_dir)
    importance = compute_importance_reports(estimator, X_val, y_val, report_dir, top_k=20, n_repeats=5)

    sample_n = min(3, len(X_test))
    sample_ids = splits["ids_test"]["participant_id"].astype(str).head(sample_n).tolist()
    local_explanations = approximate_local_contributors(
        pipe=estimator,
        X_reference=X_train,
        X_samples=X_test.head(sample_n),
        sample_ids=sample_ids,
        top_k=10,
    )
    (report_dir / "local_explanations.json").write_text(json.dumps(local_explanations, indent=2), encoding="utf-8")

    threshold_eval.sort_values("threshold").to_csv(report_dir / "threshold_precision_diagnostics.csv", index=False)
    abstention_grid.to_csv(report_dir / "abstention_grid_validation.csv", index=False)

    metadata = {
        "model_version": exp.model_version,
        "parent_version": str(champ["model_version"]),
        "disorder": exp.disorder,
        "target": exp.target,
        "dataset_name": exp.dataset_name,
        "data_scope": exp.data_scope,
        "feature_strategy": exp.feature_strategy,
        "class_balance_strategy": exp.class_balance_strategy,
        "calibration_strategy_requested": exp.calibration_strategy,
        "calibration_strategy_used": calibration_used,
        "threshold_strategy": threshold_method,
        "threshold_value": threshold,
        "recall_floor": recall_floor,
        "balanced_accuracy_tolerance": bal_tol,
        "balanced_accuracy_floor": bal_floor,
        "best_params": best_params,
        "search_meta": search_meta,
        "feature_columns": list(X_train.columns),
        "removed_columns": removed_base,
        "strategy_meta": strategy_meta,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "abstention_validation": abstention_val_summary,
        "abstention_test": abstention_test_summary,
        "figures": figs,
        "top_permutation_features": importance.get("top_permutation_features", []),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    _save_feature_list(X_train.columns.tolist(), feature_list_path)

    manifest = {
        "model_version": exp.model_version,
        "parent_version": str(champ["model_version"]),
        "task_type": "binary",
        "status": "completed",
        "dataset_name": exp.dataset_name,
        "dataset_variant": exp.dataset_variant,
        "data_scope": exp.data_scope,
        "split_version": f"splits_{exp.data_scope}_frozen_v1",
        "preprocessing_version": "rf_preproc_v1",
        "seed": RANDOM_STATE,
        "target": exp.target,
        "n_features_raw": int(raw_features),
        "n_features_final": int(final_features),
        "train_rows": int(len(X_train)),
        "val_rows": int(len(X_val)),
        "test_rows": int(len(X_test)),
        "threshold_strategy": threshold_method,
        "threshold_value": threshold,
        "recall_floor": recall_floor,
        "balanced_accuracy_tolerance": bal_tol,
        "calibration_strategy": calibration_used,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "abstention_validation": abstention_val_summary,
        "abstention_test": abstention_test_summary,
        "notes": exp.notes,
        "experimental": exp.experimental,
        "created_at": utcnow_iso(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for src in [pipeline_path, metadata_path, manifest_path, feature_list_path]:
        shutil.copy2(src, artifact_dir / src.name)
    if calibrator is not None and calibrator_path.exists():
        shutil.copy2(calibrator_path, artifact_dir / calibrator_path.name)
    for fname in [
        "feature_importance_impurity.csv",
        "feature_importance_permutation.csv",
        "top_features_impurity.png",
        "top_features_permutation.png",
        "threshold_precision_diagnostics.csv",
        "abstention_grid_validation.csv",
        "local_explanations.json",
    ]:
        src = report_dir / fname
        if src.exists():
            shutil.copy2(src, artifact_dir / fname)

    entry = {
        "experiment_id": f"exp_{exp.model_version}_{utcnow_iso().replace(':', '').replace('-', '')}",
        "model_version": exp.model_version,
        "parent_version": str(champ["model_version"]),
        "model_family": "random_forest",
        "disorder": exp.disorder,
        "target": exp.target,
        "task_type": "binary",
        "dataset_name": exp.dataset_name,
        "dataset_variant": exp.dataset_variant,
        "dataset_version": exp.data_scope,
        "data_scope": exp.data_scope,
        "split_version": f"splits_{exp.data_scope}_frozen_v1",
        "preprocessing_version": "rf_preproc_v1",
        "training_date": utcnow_iso(),
        "seed": RANDOM_STATE,
        "feature_strategy": exp.feature_strategy,
        "class_balance_strategy": exp.class_balance_strategy,
        "calibration_strategy": calibration_used,
        "threshold_strategy": threshold_method,
        "threshold_value": threshold,
        "recall_floor": recall_floor,
        "balanced_accuracy_tolerance": bal_tol,
        "hyperparameters_json": to_json_str(best_params),
        "train_rows": int(len(X_train)),
        "val_rows": int(len(X_val)),
        "test_rows": int(len(X_test)),
        "n_features_raw": int(raw_features),
        "n_features_final": int(final_features),
        "validation_metrics_json": to_json_str(val_metrics),
        "test_metrics_json": to_json_str(test_metrics),
        "status": "completed",
        "promoted": "no",
        "promoted_status": "challenger",
        "rejection_reason": "",
        "notes": exp.notes + (" | experimental_only" if exp.experimental else ""),
        "artifact_dir": _relative(artifact_dir, root),
        "source_model_id": "",
    }
    lineage = {
        "experiment_id": entry["experiment_id"],
        "model_version": exp.model_version,
        "parent_version": str(champ["model_version"]),
        "disorder": exp.disorder,
        "change_type": "precision_experiment_train",
        "description": exp.notes,
        "data_scope": exp.data_scope,
        "dataset_name": exp.dataset_name,
        "feature_strategy": exp.feature_strategy,
        "class_balance_strategy": exp.class_balance_strategy,
        "calibration_strategy": calibration_used,
        "status": "completed",
        "timestamp": utcnow_iso(),
    }
    return entry, lineage


def main() -> None:
    parser = argparse.ArgumentParser(description="Run precision-oriented RF challenger experiments.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--include-sanity", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    _setup_logging(verbose=args.verbose)
    root = Path(args.root).resolve()
    dirs = ensure_versioning_dirs(root)
    registry_path = dirs["reports_versioning"] / "model_registry.csv"
    registry_jsonl = dirs["reports_versioning"] / "model_registry.jsonl"
    registry = load_registry(registry_path)
    champion_map = _current_champion_map(registry)

    experiments = list(PRIMARY_EXPERIMENTS)
    if args.include_sanity:
        experiments.extend(SANITY_EXPERIMENTS)
    _write_precision_plan(dirs["reports_experiments"] / "precision_experiment_plan.md", experiments, champion_map)

    lineage_path = dirs["reports_versioning"] / "experiment_lineage.csv"
    if lineage_path.exists():
        lineage_df = pd.read_csv(lineage_path)
    else:
        lineage_df = pd.DataFrame()

    entries: List[Dict[str, Any]] = []
    lineage_rows: List[Dict[str, Any]] = []

    for exp in experiments:
        LOGGER.info("Running precision challenger: %s", exp.model_version)
        try:
            entry, lineage = run_single_precision_experiment(root, dirs, registry, exp)
            entries.append(entry)
            lineage_rows.append(lineage)
            LOGGER.info(
                "Completed %s | val_precision=%.4f | test_precision=%.4f",
                exp.model_version,
                metric_value(entry["validation_metrics_json"], "precision"),
                metric_value(entry["test_metrics_json"], "precision"),
            )
        except Exception as exc:
            LOGGER.exception("Failed precision challenger: %s", exp.model_version)
            entries.append(
                {
                    "experiment_id": f"exp_{exp.model_version}_{utcnow_iso().replace(':', '').replace('-', '')}",
                    "model_version": exp.model_version,
                    "parent_version": champion_map.get(exp.disorder, ""),
                    "model_family": "random_forest",
                    "disorder": exp.disorder,
                    "target": exp.target,
                    "task_type": "binary",
                    "dataset_name": exp.dataset_name,
                    "dataset_variant": exp.dataset_variant,
                    "dataset_version": exp.data_scope,
                    "data_scope": exp.data_scope,
                    "split_version": f"splits_{exp.data_scope}_frozen_v1",
                    "preprocessing_version": "rf_preproc_v1",
                    "training_date": utcnow_iso(),
                    "seed": RANDOM_STATE,
                    "feature_strategy": exp.feature_strategy,
                    "class_balance_strategy": exp.class_balance_strategy,
                    "calibration_strategy": exp.calibration_strategy,
                    "threshold_strategy": "precision_constrained",
                    "threshold_value": "",
                    "recall_floor": "",
                    "balanced_accuracy_tolerance": "",
                    "hyperparameters_json": "{}",
                    "train_rows": "",
                    "val_rows": "",
                    "test_rows": "",
                    "n_features_raw": "",
                    "n_features_final": "",
                    "validation_metrics_json": "{}",
                    "test_metrics_json": "{}",
                    "status": "failed",
                    "promoted": "no",
                    "promoted_status": "rejected",
                    "rejection_reason": str(exc),
                    "notes": exp.notes,
                    "artifact_dir": "",
                    "source_model_id": "",
                }
            )

    entries_df = pd.DataFrame(entries)
    if not entries_df.empty:
        registry_no_old = registry[~registry["model_version"].isin(entries_df["model_version"].tolist())]
        registry = pd.concat([registry_no_old, entries_df], ignore_index=True, sort=False)
        save_registry(registry, registry_path, registry_jsonl)

    if lineage_rows:
        lineage_df = pd.concat([lineage_df, pd.DataFrame(lineage_rows)], ignore_index=True, sort=False)
        lineage_df.to_csv(lineage_path, index=False)

    summary = registry[registry["model_version"].isin([e.model_version for e in experiments])].copy()
    summary["val_precision"] = summary["validation_metrics_json"].apply(lambda s: metric_value(s, "precision"))
    summary["val_recall"] = summary["validation_metrics_json"].apply(lambda s: metric_value(s, "recall"))
    summary["val_balanced_accuracy"] = summary["validation_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
    summary["val_specificity"] = summary["validation_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
    summary["test_precision"] = summary["test_metrics_json"].apply(lambda s: metric_value(s, "precision"))
    summary["test_recall"] = summary["test_metrics_json"].apply(lambda s: metric_value(s, "recall"))
    summary["test_balanced_accuracy"] = summary["test_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
    summary["test_specificity"] = summary["test_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
    summary.sort_values(["disorder", "val_precision", "val_balanced_accuracy"], ascending=[True, False, False]).to_csv(
        dirs["reports_experiments"] / "precision_experiment_results_summary.csv",
        index=False,
    )

    LOGGER.info("Precision experiment campaign finished. models=%d", len(summary))


if __name__ == "__main__":
    main()
