from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from ml_rf_common import (
    RANDOM_STATE,
    TARGET_COLUMNS,
    DatasetSpec,
    approximate_local_contributors,
    binary_metrics,
    compute_importance_reports,
    copy_model_artifact,
    discover_datasets,
    ensure_output_structure,
    infer_target_column,
    get_feature_names_from_pipeline,
    load_or_create_splits,
    map_risk_band,
    maybe_fit_calibrator,
    pick_recommended_threshold,
    plot_binary_curves,
    read_manifest,
    run_binary_hyperparam_search,
    safe_csv,
    safe_json,
    sanitize_features,
    subgroup_binary_metrics,
    threshold_candidates,
    build_binary_pipeline_from_params,
)


def _setup_logger() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("rf-binary")


def _version_order(version: str) -> int:
    return 0 if version == "strict_no_leakage" else 1


def _iter_for_spec(spec: DatasetSpec) -> int:
    if spec.version != "strict_no_leakage":
        return 0
    if spec.variant in {"items"}:
        return 6
    return 8


def _model_dirs(root: Path, model_id: str) -> Dict[str, Path]:
    return {
        "artifact_binary": root / "artifacts" / "models" / "binary" / model_id,
        "artifact_calibrated": root / "artifacts" / "models" / "calibrated" / model_id,
        "models_binary": root / "models" / "binary" / model_id,
        "models_calibrated": root / "models" / "calibrated" / model_id,
        "figures": root / "reports" / "figures" / model_id,
        "training": root / "reports" / "training" / model_id,
    }


def _save_split_mirror(root: Path, spec: DatasetSpec, splits: Dict[str, pd.DataFrame]) -> None:
    split_dir = root / "data" / "processed" / "splits" / spec.dataset_name / spec.version
    for key, frame in splits.items():
        safe_csv(frame, split_dir / f"{key}.csv")


def train_binary_model(
    root: Path,
    spec: DatasetSpec,
    strict_params_lookup: Dict[str, Dict[str, Any]],
    split_decisions: List[Dict[str, Any]],
    logger: logging.Logger,
) -> Dict[str, Any]:
    logger.info("Training binary model: %s (%s)", spec.dataset_name, spec.version)
    df = pd.read_csv(spec.path)
    target = infer_target_column(df, spec)
    X, y, removed = sanitize_features(df, task="binary", target_column=target)
    for t in TARGET_COLUMNS:
        if t in X.columns:
            raise RuntimeError(f"Leakage guard failed: {t} present in X for {spec.model_id}")
    if target is None:
        raise RuntimeError(f"Could not infer primary target for {spec.model_id}")

    splits = load_or_create_splits(root, spec, df, X, y, task="binary", target_col=target, split_decisions=split_decisions)
    _save_split_mirror(root, spec, splits)

    X_train, X_val, X_test = splits["X_train"], splits["X_val"], splits["X_test"]
    y_train = splits["y_train"][target].astype(int)
    y_val = splits["y_val"][target].astype(int)
    y_test = splits["y_test"][target].astype(int)

    model_dirs = _model_dirs(root, spec.model_id)
    for p in model_dirs.values():
        p.mkdir(parents=True, exist_ok=True)

    fixed_params = None
    params_source = "search"
    if spec.version == "research_extended":
        fixed_params = strict_params_lookup.get(spec.dataset_name)
        if fixed_params:
            params_source = "strict_reuse"

    if fixed_params:
        pipeline = build_binary_pipeline_from_params(X_train, fixed_params)
        pipeline.fit(X_train, y_train)
        best_params = fixed_params
        search_meta = {"best_cv_balanced_accuracy": float("nan"), "cv_splits": 0, "n_iter": 0}
    else:
        n_iter = _iter_for_spec(spec)
        if n_iter > 0:
            pipeline, best_params, search_meta = run_binary_hyperparam_search(X_train, y_train, n_iter=n_iter, logger=logger)
        else:
            params_source = "fallback_small_search"
            pipeline, best_params, search_meta = run_binary_hyperparam_search(X_train, y_train, n_iter=4, logger=logger)

    calibrator = maybe_fit_calibrator(pipeline, X_train, y_train, logger=logger)
    scorer = calibrator if calibrator is not None else pipeline
    val_prob = scorer.predict_proba(X_val)[:, 1]
    test_prob = scorer.predict_proba(X_test)[:, 1]

    threshold_df = threshold_candidates(y_val.to_numpy(), val_prob, sensitivity_target=0.85)
    recommended = pick_recommended_threshold(threshold_df)
    threshold_df.insert(0, "dataset", spec.dataset_name)
    threshold_df.insert(1, "version", spec.version)
    safe_csv(threshold_df, model_dirs["training"] / "threshold_metrics_val.csv")

    test_rows: List[Dict[str, Any]] = []
    for row in threshold_df.to_dict(orient="records"):
        metrics = binary_metrics(y_test.to_numpy(), test_prob, threshold=float(row["threshold"]))
        metrics["method"] = row["method"]
        test_rows.append(metrics)
    threshold_test_df = pd.DataFrame(test_rows).sort_values(["balanced_accuracy", "recall", "specificity"], ascending=False)
    safe_csv(threshold_test_df, model_dirs["training"] / "threshold_metrics_test.csv")

    thr = float(recommended["threshold"])
    test_metrics = binary_metrics(y_test.to_numpy(), test_prob, threshold=thr)
    val_metrics = binary_metrics(y_val.to_numpy(), val_prob, threshold=thr)

    y_test_pred = (test_prob >= thr).astype(int)
    figure_paths = plot_binary_curves(y_test.to_numpy(), test_prob, y_test_pred, spec.model_id, model_dirs["figures"])

    import_summary = compute_importance_reports(
        pipe=pipeline,
        X_val=X_val,
        y_val=y_val,
        out_dir=model_dirs["training"],
        top_k=20,
        n_repeats=5,
    )

    sample_ids = splits["ids_test"]["participant_id"].astype(str).head(3).tolist()
    local_expl = approximate_local_contributors(
        pipe=pipeline,
        X_reference=X_train,
        X_samples=X_test.head(len(sample_ids)),
        sample_ids=sample_ids,
        top_k=10,
    )
    safe_json(local_expl, model_dirs["training"] / "local_explanations.json")

    meta_cols = [c for c in ["age_years", "sex_assigned_at_birth", "comorbidity_count_5targets"] if c in df.columns]
    if meta_cols:
        meta_idx = df[["participant_id", *meta_cols]].copy()
        meta_idx["participant_id"] = meta_idx["participant_id"].astype(str)
        meta_test = (
            meta_idx.set_index("participant_id")
            .loc[splits["ids_test"]["participant_id"].astype(str).tolist(), :]
            .reset_index(drop=True)
        )
        subgroup = subgroup_binary_metrics(meta_test, y_test.to_numpy(), test_prob, threshold=thr)
    else:
        subgroup = pd.DataFrame(
            [{"group_name": "none", "group_value": "none", "source_column": "", "n": len(y_test), "status": "no_subgroup_columns"}]
        )
    safe_csv(subgroup, model_dirs["training"] / "subgroup_metrics.csv")

    feature_names = get_feature_names_from_pipeline(pipeline)
    train_encoded = np.asarray(pipeline.named_steps["preprocessor"].transform(X_train))
    importances_arr = np.asarray(pipeline.named_steps["model"].feature_importances_)
    dim = min(len(feature_names), train_encoded.shape[1], len(importances_arr))
    feature_names = feature_names[:dim]
    feature_medians = np.median(train_encoded[:, :dim], axis=0).tolist()
    feature_importances = importances_arr[:dim].tolist()

    missing_ratio_test = float(X_test.isna().mean().mean()) if len(X_test.columns) else 0.0
    evidence_quality = "strong"
    if missing_ratio_test >= 0.4:
        evidence_quality = "weak"
    elif missing_ratio_test >= 0.2:
        evidence_quality = "medium"

    artifact_bundle = {
        "pipeline": model_dirs["artifact_binary"] / "pipeline.joblib",
        "calibrator": model_dirs["artifact_calibrated"] / "calibrated.joblib",
        "model_metadata": model_dirs["artifact_binary"] / "metadata.json",
    }
    joblib.dump(pipeline, artifact_bundle["pipeline"])
    if calibrator is not None:
        joblib.dump(calibrator, artifact_bundle["calibrator"])

    copy_model_artifact(artifact_bundle["pipeline"], model_dirs["models_binary"] / "pipeline.joblib")
    if calibrator is not None:
        copy_model_artifact(artifact_bundle["calibrator"], model_dirs["models_calibrated"] / "calibrated.joblib")

    inference_meta = {
        "model_id": spec.model_id,
        "dataset": spec.dataset_name,
        "version": spec.version,
        "target": target,
        "feature_columns": list(X.columns),
        "recommended_threshold": thr,
        "threshold_method": recommended["method"],
        "risk_band_policy": {"low_lt": 0.33, "moderate_lt": 0.66, "high_ge": 0.66},
        "evidence_quality_policy": {"weak_if_missing_ge": 0.4, "medium_if_missing_ge": 0.2},
        "top_features": import_summary["top_permutation_features"][:20],
        "encoded_feature_names": feature_names,
        "encoded_feature_medians": feature_medians,
        "encoded_feature_importances": feature_importances,
    }
    safe_json(inference_meta, artifact_bundle["model_metadata"])

    summary = {
        "model_id": spec.model_id,
        "dataset_name": spec.dataset_name,
        "version": spec.version,
        "disorder": spec.disorder,
        "variant": spec.variant,
        "target": target,
        "n_rows": int(len(df)),
        "n_features": int(X.shape[1]),
        "search_param_source": params_source,
        "best_params": best_params,
        "search_meta": search_meta,
        "threshold_method": recommended["method"],
        "threshold_value": thr,
        "balanced_accuracy_val": float(val_metrics["balanced_accuracy"]),
        "balanced_accuracy_test": float(test_metrics["balanced_accuracy"]),
        "recall_test": float(test_metrics["recall"]),
        "specificity_test": float(test_metrics["specificity"]),
        "f1_test": float(test_metrics["f1"]),
        "roc_auc_test": float(test_metrics["roc_auc"]),
        "pr_auc_test": float(test_metrics["pr_auc"]),
        "brier_score_test": float(test_metrics["brier_score"]),
        "accuracy_test": float(test_metrics["accuracy"]),
        "precision_test": float(test_metrics["precision"]),
        "support_positive_test": int(test_metrics["support_positive"]),
        "support_negative_test": int(test_metrics["support_negative"]),
        "missing_ratio_test": missing_ratio_test,
        "risk_band_example": map_risk_band(float(np.median(test_prob))),
        "evidence_quality": evidence_quality,
        "artifact_pipeline_path": str(artifact_bundle["pipeline"].relative_to(root)),
        "artifact_calibrated_path": str(artifact_bundle["calibrator"].relative_to(root)) if calibrator is not None else "",
        "artifact_metadata_path": str(artifact_bundle["model_metadata"].relative_to(root)),
        "figure_roc": figure_paths["roc_curve"],
        "figure_pr": figure_paths["pr_curve"],
        "figure_confusion": figure_paths["confusion"],
        "figure_calibration": figure_paths["calibration_curve"],
        "dropped_columns_count": len(removed),
        "manifest_exists": read_manifest(root, spec.dataset_name, spec.version) is not None,
    }

    safe_json(
        {
            "summary": summary,
            "validation_metrics": val_metrics,
            "test_metrics": test_metrics,
            "threshold_recommendation": recommended,
            "removed_columns": removed,
            "local_explanations": local_expl,
        },
        model_dirs["training"] / "result.json",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate RandomForest binary models.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument(
        "--versions",
        type=str,
        default="strict_no_leakage,research_extended",
        help="Comma-separated versions to run.",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    versions = [v.strip() for v in args.versions.split(",") if v.strip()]

    logger = _setup_logger()
    ensure_output_structure(root)

    specs = [s for s in discover_datasets(root) if (not s.is_multilabel and s.version in versions)]
    specs = sorted(specs, key=lambda s: (_version_order(s.version), s.disorder, s.variant))
    logger.info("Binary datasets discovered: %d", len(specs))

    strict_params_lookup: Dict[str, Dict[str, Any]] = {}
    split_decisions: List[Dict[str, Any]] = []
    summaries: List[Dict[str, Any]] = []

    for spec in specs:
        summary = train_binary_model(
            root=root,
            spec=spec,
            strict_params_lookup=strict_params_lookup,
            split_decisions=split_decisions,
            logger=logger,
        )
        summaries.append(summary)
        if spec.version == "strict_no_leakage":
            strict_params_lookup[spec.dataset_name] = summary["best_params"]

    summary_df = pd.DataFrame(summaries)
    safe_csv(summary_df, root / "reports" / "metrics" / "binary_model_results_detailed.csv")
    safe_csv(pd.DataFrame(split_decisions), root / "reports" / "training" / "split_decisions_binary.csv")

    logger.info(
        "Binary training finished. Models=%d | best avg balanced_accuracy_test=%.4f",
        len(summary_df),
        float(summary_df["balanced_accuracy_test"].mean()) if not summary_df.empty else float("nan"),
    )


if __name__ == "__main__":
    main()
