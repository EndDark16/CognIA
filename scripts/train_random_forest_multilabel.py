from __future__ import annotations

import argparse
import json
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    make_scorer,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)
from sklearn.model_selection import KFold, RandomizedSearchCV

from ml_rf_common import (
    RANDOM_STATE,
    TARGET_COLUMNS,
    DatasetSpec,
    build_multilabel_pipeline,
    copy_model_artifact,
    discover_datasets,
    ensure_output_structure,
    get_feature_names_from_pipeline,
    get_multilabel_probabilities,
    load_or_create_splits,
    multilabel_comorbidity_matrix,
    multilabel_metrics,
    multilabel_param_grid,
    read_manifest,
    safe_csv,
    safe_json,
    sanitize_features,
)


def _setup_logger() -> logging.Logger:
    warnings.filterwarnings(
        "ignore",
        message="`sklearn.utils.parallel.delayed` should be used with `sklearn.utils.parallel.Parallel`",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("rf-multilabel")


def _version_order(version: str) -> int:
    return 0 if version == "strict_no_leakage" else 1


def _plot_multilabel_figures(model_id: str, y_true: np.ndarray, y_prob: np.ndarray, y_pred: np.ndarray, out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    figure_paths: Dict[str, str] = {}
    for i, target in enumerate(TARGET_COLUMNS):
        yt = y_true[:, i]
        yp = y_prob[:, i]
        yhat = y_pred[:, i]

        fpr, tpr, _ = roc_curve(yt, yp)
        auc = roc_auc_score(yt, yp) if len(np.unique(yt)) > 1 else float("nan")
        plt.figure(figsize=(5, 4))
        plt.plot(fpr, tpr, label=f"AUC={auc:.3f}")
        plt.plot([0, 1], [0, 1], "--", color="gray")
        plt.title(f"{model_id} - {target} ROC")
        plt.xlabel("FPR")
        plt.ylabel("TPR")
        plt.legend(loc="lower right")
        roc_path = out_dir / f"{model_id}_{target}_roc.png"
        plt.tight_layout()
        plt.savefig(roc_path, dpi=150)
        plt.close()

        pr, rc, _ = precision_recall_curve(yt, yp)
        pr_auc = average_precision_score(yt, yp)
        plt.figure(figsize=(5, 4))
        plt.plot(rc, pr, label=f"AP={pr_auc:.3f}")
        plt.title(f"{model_id} - {target} PR")
        plt.xlabel("Recall")
        plt.ylabel("Precision")
        plt.legend(loc="lower left")
        pr_path = out_dir / f"{model_id}_{target}_pr.png"
        plt.tight_layout()
        plt.savefig(pr_path, dpi=150)
        plt.close()

        cm = confusion_matrix(yt, yhat, labels=[0, 1], normalize="true")
        plt.figure(figsize=(4, 3))
        plt.imshow(cm, cmap="Blues")
        plt.xticks([0, 1], ["Pred 0", "Pred 1"])
        plt.yticks([0, 1], ["True 0", "True 1"])
        for r in range(2):
            for c in range(2):
                plt.text(c, r, f"{cm[r, c]:.2f}", ha="center", va="center")
        plt.title(f"{model_id} - {target} CM")
        plt.colorbar()
        cm_path = out_dir / f"{model_id}_{target}_cm_norm.png"
        plt.tight_layout()
        plt.savefig(cm_path, dpi=150)
        plt.close()

        figure_paths[f"{target}_roc"] = str(roc_path)
        figure_paths[f"{target}_pr"] = str(pr_path)
        figure_paths[f"{target}_cm"] = str(cm_path)
    return figure_paths


def _train_one_multilabel(
    root: Path,
    spec: DatasetSpec,
    strict_params: Dict[str, Any] | None,
    split_decisions: List[Dict[str, Any]],
    logger: logging.Logger,
) -> Dict[str, Any]:
    logger.info("Training multilabel model: %s (%s)", spec.dataset_name, spec.version)
    df = pd.read_csv(spec.path)
    X, y, removed = sanitize_features(df, task="multilabel", target_column=None)

    splits = load_or_create_splits(root, spec, df, X, y, task="multilabel", target_col=None, split_decisions=split_decisions)
    split_dir = root / "data" / "processed" / "splits" / spec.dataset_name / spec.version
    for k, frame in splits.items():
        safe_csv(frame, split_dir / f"{k}.csv")

    X_train, X_val, X_test = splits["X_train"], splits["X_val"], splits["X_test"]
    y_train, y_val, y_test = splits["y_train"], splits["y_val"], splits["y_test"]

    if strict_params:
        pipe = build_multilabel_pipeline(X_train)
        pipe.set_params(**strict_params)
        pipe.fit(X_train, y_train)
        best_params = strict_params
        search_meta = {"source": "strict_reuse", "n_iter": 0}
    else:
        pipe = build_multilabel_pipeline(X_train)
        cv = KFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
        search = RandomizedSearchCV(
            estimator=pipe,
            param_distributions=multilabel_param_grid(),
            n_iter=8 if spec.version == "strict_no_leakage" else 4,
            scoring=make_scorer(f1_score, average="micro"),
            n_jobs=-1,
            cv=cv,
            random_state=RANDOM_STATE,
            refit=True,
            verbose=0,
        )
        search.fit(X_train, y_train)
        pipe = search.best_estimator_
        best_params = search.best_params_
        search_meta = {"source": "search", "best_cv_micro_f1": float(search.best_score_), "n_iter": int(search.n_iter)}

    val_prob = get_multilabel_probabilities(pipe, X_val)
    test_prob = get_multilabel_probabilities(pipe, X_test)
    val_pred = (val_prob >= 0.5).astype(int)
    test_pred = (test_prob >= 0.5).astype(int)

    val_metrics = multilabel_metrics(y_val.to_numpy(), val_pred, val_prob)
    test_metrics = multilabel_metrics(y_test.to_numpy(), test_pred, test_prob)

    model_id = spec.model_id
    model_dir = root / "artifacts" / "models" / "multilabel" / model_id
    model_dir.mkdir(parents=True, exist_ok=True)
    training_dir = root / "reports" / "training" / model_id
    training_dir.mkdir(parents=True, exist_ok=True)
    figure_dir = root / "reports" / "figures" / model_id
    figure_paths = _plot_multilabel_figures(model_id, y_test.to_numpy(), test_prob, test_pred, figure_dir)

    feat_names = get_feature_names_from_pipeline(pipe)
    estimators = pipe.named_steps["model"].estimators_
    importances = np.mean([est.feature_importances_ for est in estimators], axis=0)
    dim = min(len(feat_names), len(importances))
    feat_names = feat_names[:dim]
    importances = importances[:dim]
    imp_df = pd.DataFrame({"feature": feat_names, "importance_mean": importances}).sort_values(
        "importance_mean", ascending=False
    )
    safe_csv(imp_df, training_dir / "feature_importance_impurity.csv")

    perm = permutation_importance(
        estimator=pipe,
        X=X_val,
        y=y_val,
        n_repeats=5,
        random_state=RANDOM_STATE,
        scoring=make_scorer(f1_score, average="micro"),
        n_jobs=-1,
    )
    p_dim = len(perm.importances_mean)
    perm_names = feat_names[:p_dim] if len(feat_names) >= p_dim else feat_names + [f"feature_{i}" for i in range(len(feat_names), p_dim)]
    perm_df = pd.DataFrame(
        {"feature": perm_names, "importance_mean": perm.importances_mean, "importance_std": perm.importances_std}
    ).sort_values("importance_mean", ascending=False)
    safe_csv(perm_df, training_dir / "feature_importance_permutation.csv")

    real_comorb = multilabel_comorbidity_matrix(y_test.to_numpy(), TARGET_COLUMNS)
    pred_comorb = multilabel_comorbidity_matrix(test_pred, TARGET_COLUMNS)
    safe_csv(real_comorb.reset_index().rename(columns={"index": "target"}), training_dir / "comorbidity_real_test.csv")
    safe_csv(pred_comorb.reset_index().rename(columns={"index": "target"}), training_dir / "comorbidity_pred_test.csv")

    per_label_df = pd.DataFrame(test_metrics["per_label"])
    safe_csv(per_label_df, training_dir / "per_label_metrics_test.csv")

    model_path = model_dir / "pipeline.joblib"
    joblib.dump(pipe, model_path)
    copy_model_artifact(model_path, root / "models" / "multilabel" / model_id / "pipeline.joblib")

    inference_meta = {
        "model_id": model_id,
        "dataset": spec.dataset_name,
        "version": spec.version,
        "targets": TARGET_COLUMNS,
        "feature_columns": list(X.columns),
        "thresholds": {t: 0.5 for t in TARGET_COLUMNS},
        "top_features": imp_df.head(20)["feature"].tolist(),
    }
    safe_json(inference_meta, model_dir / "metadata.json")

    summary = {
        "model_id": model_id,
        "dataset_name": spec.dataset_name,
        "version": spec.version,
        "n_rows": int(len(df)),
        "n_features": int(X.shape[1]),
        "subset_accuracy_val": float(val_metrics["subset_accuracy"]),
        "subset_accuracy_test": float(test_metrics["subset_accuracy"]),
        "hamming_loss_test": float(test_metrics["hamming_loss"]),
        "micro_f1_test": float(test_metrics["micro_f1"]),
        "macro_f1_test": float(test_metrics["macro_f1"]),
        "weighted_f1_test": float(test_metrics["weighted_f1"]),
        "search_meta": search_meta,
        "best_params": best_params,
        "artifact_pipeline_path": str(model_path.relative_to(root)),
        "artifact_metadata_path": str((model_dir / "metadata.json").relative_to(root)),
        "manifest_exists": read_manifest(root, spec.dataset_name, spec.version) is not None,
        "figure_count": len(figure_paths),
    }

    safe_json(
        {
            "summary": summary,
            "validation_metrics": val_metrics,
            "test_metrics": test_metrics,
            "removed_columns": removed,
            "figure_paths": figure_paths,
        },
        training_dir / "result.json",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate RandomForest multilabel models.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--versions", type=str, default="strict_no_leakage,research_extended")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    versions = [v.strip() for v in args.versions.split(",") if v.strip()]

    logger = _setup_logger()
    ensure_output_structure(root)

    specs = [s for s in discover_datasets(root) if s.is_multilabel and s.version in versions]
    specs = sorted(specs, key=lambda s: (_version_order(s.version), s.dataset_name))
    logger.info("Multilabel datasets discovered: %d", len(specs))

    strict_params: Dict[str, Any] | None = None
    split_decisions: List[Dict[str, Any]] = []
    summaries: List[Dict[str, Any]] = []

    for spec in specs:
        summary = _train_one_multilabel(root, spec, strict_params if spec.version == "research_extended" else None, split_decisions, logger)
        summaries.append(summary)
        if spec.version == "strict_no_leakage":
            strict_params = summary["best_params"]

    safe_csv(pd.DataFrame(summaries), root / "reports" / "metrics" / "multilabel_model_results_detailed.csv")
    safe_csv(pd.DataFrame(split_decisions), root / "reports" / "training" / "split_decisions_multilabel.csv")
    logger.info("Multilabel training finished. Models=%d", len(summaries))


if __name__ == "__main__":
    main()
