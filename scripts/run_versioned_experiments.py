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
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_selection import mutual_info_classif
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold

from ml_rf_common import (
    RANDOM_STATE,
    TARGET_COLUMNS,
    approximate_local_contributors,
    binary_metrics,
    binary_param_grid,
    build_binary_pipeline,
    compute_importance_reports,
    plot_binary_curves,
    sanitize_features,
    threshold_candidates,
)
from versioning_utils import (
    ensure_versioning_dirs,
    load_registry,
    metric_value,
    save_registry,
    to_json_str,
    utcnow_iso,
)


LOGGER = logging.getLogger("rf-versioned-experiments")


@dataclass(frozen=True)
class ExperimentConfig:
    model_version: str
    disorder: str
    dataset_name: str
    data_scope: str
    feature_strategy: str
    top_k: Optional[int]
    class_balance_strategy: str
    calibration_strategy: str
    threshold_strategy: str
    notes: str
    experimental: bool = False
    parent_version: Optional[str] = None

    @property
    def target(self) -> str:
        return f"target_{self.disorder}"

    @property
    def task_type(self) -> str:
        return "binary"

    @property
    def dataset_variant(self) -> str:
        parts = self.dataset_name.split("_")
        return "_".join(parts[2:]) if len(parts) >= 3 else self.dataset_name


EXPERIMENTS: List[ExperimentConfig] = [
    ExperimentConfig(
        model_version="rf_depression_v2_feature_pruned",
        disorder="depression",
        dataset_name="dataset_depression_parent",
        data_scope="strict_no_leakage",
        feature_strategy="mi_top_k",
        top_k=28,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="sigmoid",
        threshold_strategy="youden_j",
        notes="Parent-focused depression model with MI pruning and calibrated probabilities.",
    ),
    ExperimentConfig(
        model_version="rf_depression_v3_calibrated",
        disorder="depression",
        dataset_name="dataset_depression_combined",
        data_scope="strict_no_leakage",
        feature_strategy="mi_top_k",
        top_k=38,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="isotonic",
        threshold_strategy="sensitivity_priority",
        notes="Combined depression features with stronger recall objective and isotonic calibration.",
    ),
    ExperimentConfig(
        model_version="rf_conduct_v2_externalizing_focus",
        disorder="conduct",
        dataset_name="dataset_conduct_clinical",
        data_scope="strict_no_leakage",
        feature_strategy="externalizing_focus",
        top_k=34,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="sigmoid",
        threshold_strategy="youden_j",
        notes="Externalizing-focused conduct feature subset (ICUT/ARI/CBCL/SDQ emphasis).",
    ),
    ExperimentConfig(
        model_version="rf_conduct_v3_balanced_subsample",
        disorder="conduct",
        dataset_name="dataset_conduct_minimal",
        data_scope="strict_no_leakage",
        feature_strategy="mi_top_k",
        top_k=24,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="sigmoid",
        threshold_strategy="sensitivity_priority",
        notes="Minimal conduct dataset with aggressive pruning and sensitivity-priority threshold.",
    ),
    ExperimentConfig(
        model_version="rf_elimination_v2_missingness_augmented",
        disorder="elimination",
        dataset_name="dataset_elimination_core",
        data_scope="strict_no_leakage",
        feature_strategy="missingness_augmented",
        top_k=None,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="sigmoid",
        threshold_strategy="youden_j",
        notes="Elimination core model with explicit missingness indicators (exploratory).",
    ),
    ExperimentConfig(
        model_version="rf_elimination_v3_proxy_pruned",
        disorder="elimination",
        dataset_name="dataset_elimination_items",
        data_scope="strict_no_leakage",
        feature_strategy="proxy_pruned",
        top_k=42,
        class_balance_strategy="balanced",
        calibration_strategy="sigmoid",
        threshold_strategy="best_f1",
        notes="Elimination items reduced to interpretable proxy subset (exploratory).",
    ),
    ExperimentConfig(
        model_version="rf_elimination_v4_experimental_research",
        disorder="elimination",
        dataset_name="dataset_elimination_core",
        data_scope="research_extended",
        feature_strategy="missingness_augmented",
        top_k=None,
        class_balance_strategy="balanced_subsample",
        calibration_strategy="sigmoid",
        threshold_strategy="youden_j",
        notes="Research-extended elimination challenger for controlled comparison (experimental only).",
        experimental=True,
    ),
]


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _resolve_dataset_path(root: Path, dataset_name: str, scope: str) -> Path:
    path = root / "data" / "processed" / "final" / scope / f"{dataset_name}_{scope}.csv"
    if path.exists():
        return path
    fallback = list((root / "data" / "processed" / "final" / scope).glob(f"{dataset_name}*{scope}.csv"))
    if fallback:
        return fallback[0]
    raise FileNotFoundError(f"Dataset not found for {dataset_name} ({scope})")


def _resolve_split_dir(root: Path, dataset_name: str, scope: str) -> Path:
    split_dir = root / "data" / "processed" / "splits" / dataset_name / scope
    if not split_dir.exists():
        raise FileNotFoundError(f"Frozen split directory missing: {split_dir}")
    required = [split_dir / "ids_train.csv", split_dir / "ids_val.csv", split_dir / "ids_test.csv"]
    missing = [str(p.name) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Frozen split files missing in {split_dir}: {missing}")
    return split_dir


def _load_frozen_splits(
    df: pd.DataFrame,
    split_dir: Path,
    target_col: str,
    X_cols: Sequence[str],
) -> Dict[str, pd.DataFrame]:
    ids_train = pd.read_csv(split_dir / "ids_train.csv")["participant_id"].astype(str).tolist()
    ids_val = pd.read_csv(split_dir / "ids_val.csv")["participant_id"].astype(str).tolist()
    ids_test = pd.read_csv(split_dir / "ids_test.csv")["participant_id"].astype(str).tolist()

    tr, va, te = set(ids_train), set(ids_val), set(ids_test)
    if tr & va or tr & te or va & te:
        raise RuntimeError(f"Invalid frozen split with overlapping IDs in {split_dir}")

    index = df.copy()
    index["participant_id"] = index["participant_id"].astype(str)
    index = index.set_index("participant_id", drop=True)
    all_ids = set(index.index.tolist())
    expected = tr | va | te
    if not expected.issubset(all_ids):
        missing = list(sorted(expected - all_ids))[:10]
        raise RuntimeError(f"Frozen split IDs not present in dataset. Example missing IDs: {missing}")

    def subset(ids_list: Sequence[str]) -> pd.DataFrame:
        return index.loc[list(ids_list)].copy()

    tr_df = subset(ids_train)
    va_df = subset(ids_val)
    te_df = subset(ids_test)

    return {
        "X_train": tr_df[list(X_cols)].reset_index(drop=True),
        "X_val": va_df[list(X_cols)].reset_index(drop=True),
        "X_test": te_df[list(X_cols)].reset_index(drop=True),
        "y_train": tr_df[[target_col]].reset_index(drop=True),
        "y_val": va_df[[target_col]].reset_index(drop=True),
        "y_test": te_df[[target_col]].reset_index(drop=True),
        "ids_train": pd.DataFrame({"participant_id": ids_train}),
        "ids_val": pd.DataFrame({"participant_id": ids_val}),
        "ids_test": pd.DataFrame({"participant_id": ids_test}),
    }


def _normalize_series_for_mi(series: pd.Series) -> Tuple[np.ndarray, bool]:
    if pd.api.types.is_numeric_dtype(series):
        vals = pd.to_numeric(series, errors="coerce")
        fill = float(vals.median()) if vals.notna().any() else 0.0
        return vals.fillna(fill).to_numpy(dtype=float), False
    vals = series.fillna("__MISSING__").astype(str)
    codes, _ = pd.factorize(vals)
    return codes.astype(float), True


def _select_top_mi_features(X_train: pd.DataFrame, y_train: pd.Series, top_k: int) -> List[str]:
    top_k = max(1, min(int(top_k), X_train.shape[1]))
    matrix = np.zeros((len(X_train), X_train.shape[1]), dtype=float)
    discrete_flags: List[bool] = []
    cols = list(X_train.columns)
    for idx, col in enumerate(cols):
        arr, is_discrete = _normalize_series_for_mi(X_train[col])
        matrix[:, idx] = arr
        discrete_flags.append(is_discrete)
    mi = mutual_info_classif(
        matrix,
        y_train.to_numpy(dtype=int),
        discrete_features=np.array(discrete_flags),
        random_state=RANDOM_STATE,
    )
    score = pd.DataFrame({"feature": cols, "mi_score": mi}).sort_values("mi_score", ascending=False)
    keep = score.head(top_k)["feature"].tolist()
    return keep if keep else cols


def _patterns_externalizing() -> Tuple[str, ...]:
    return (
        "icut",
        "ari",
        "externalizing",
        "rule_break",
        "aggressive",
        "sdq_conduct",
        "sdq_total",
        "cbcl",
        "conduct",
        "age",
        "sex",
        "site",
        "has_",
        "comorbidity",
    )


def _patterns_elimination_proxy() -> Tuple[str, ...]:
    return (
        "elimination",
        "enuresis",
        "encopresis",
        "cbcl",
        "sdq",
        "age",
        "sex",
        "site",
        "has_",
        "comorbidity",
        "sleep",
        "toilet",
    )


def _choose_pattern_features(columns: Sequence[str], patterns: Sequence[str], fallback_min: int = 12) -> List[str]:
    chosen = [c for c in columns if any(p in c.lower() for p in patterns)]
    if len(chosen) >= fallback_min:
        return chosen
    return list(columns)


def _augment_missingness(
    X_train: pd.DataFrame,
    X_val: pd.DataFrame,
    X_test: pd.DataFrame,
    min_ratio: float = 0.05,
    max_ratio: float = 0.95,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str]]:
    ratios = X_train.isna().mean()
    cols = [c for c, r in ratios.items() if r >= min_ratio and r <= max_ratio]
    if not cols:
        return X_train, X_val, X_test, []
    tr, va, te = X_train.copy(), X_val.copy(), X_test.copy()
    created: List[str] = []
    for col in cols:
        new_col = f"{col}__missing"
        tr[new_col] = tr[col].isna().astype(int)
        va[new_col] = va[col].isna().astype(int)
        te[new_col] = te[col].isna().astype(int)
        created.append(new_col)
    return tr, va, te, created


def apply_feature_strategy(
    cfg: ExperimentConfig,
    X_train: pd.DataFrame,
    X_val: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    removed: Dict[str, str] = {}
    created: List[str] = []

    const_cols = [c for c in X_train.columns if X_train[c].nunique(dropna=False) <= 1]
    sparse_cols = [c for c in X_train.columns if X_train[c].isna().mean() >= 0.995]
    drop_initial = sorted(set(const_cols + sparse_cols))
    if drop_initial:
        X_train = X_train.drop(columns=drop_initial)
        X_val = X_val.drop(columns=drop_initial, errors="ignore")
        X_test = X_test.drop(columns=drop_initial, errors="ignore")
        for c in drop_initial:
            removed[c] = "constant_or_sparse"

    if cfg.feature_strategy == "mi_top_k":
        top_k = cfg.top_k or max(5, int(round(X_train.shape[1] * 0.6)))
        keep = _select_top_mi_features(X_train, y_train, top_k=top_k)
        to_drop = [c for c in X_train.columns if c not in keep]
        X_train = X_train[keep].copy()
        X_val = X_val[keep].copy()
        X_test = X_test[keep].copy()
        for c in to_drop:
            removed[c] = f"mi_not_in_top_{len(keep)}"
    elif cfg.feature_strategy == "externalizing_focus":
        keep = _choose_pattern_features(X_train.columns, _patterns_externalizing(), fallback_min=16)
        if cfg.top_k and len(keep) > cfg.top_k:
            keep = _select_top_mi_features(X_train[keep], y_train, top_k=cfg.top_k)
        to_drop = [c for c in X_train.columns if c not in keep]
        X_train = X_train[keep].copy()
        X_val = X_val[keep].copy()
        X_test = X_test[keep].copy()
        for c in to_drop:
            removed[c] = "externalizing_focus_filter"
    elif cfg.feature_strategy == "proxy_pruned":
        keep = _choose_pattern_features(X_train.columns, _patterns_elimination_proxy(), fallback_min=14)
        if cfg.top_k and len(keep) > cfg.top_k:
            keep = _select_top_mi_features(X_train[keep], y_train, top_k=cfg.top_k)
        to_drop = [c for c in X_train.columns if c not in keep]
        X_train = X_train[keep].copy()
        X_val = X_val[keep].copy()
        X_test = X_test[keep].copy()
        for c in to_drop:
            removed[c] = "proxy_filter"
    elif cfg.feature_strategy == "missingness_augmented":
        X_train, X_val, X_test, created = _augment_missingness(X_train, X_val, X_test)
    else:
        raise ValueError(f"Unsupported feature strategy: {cfg.feature_strategy}")

    return X_train, X_val, X_test, {
        "feature_strategy": cfg.feature_strategy,
        "removed_by_strategy": removed,
        "created_features": created,
    }


def _build_param_space(class_balance_strategy: str) -> Dict[str, Sequence[Any]]:
    space = dict(binary_param_grid())
    if class_balance_strategy == "search":
        return space
    if class_balance_strategy == "none":
        space["model__class_weight"] = [None]
    elif class_balance_strategy in {"balanced", "balanced_subsample"}:
        space["model__class_weight"] = [class_balance_strategy]
    else:
        raise ValueError(f"Unknown class balance strategy: {class_balance_strategy}")
    return space


def _fit_search(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    class_balance_strategy: str,
    n_iter: int = 10,
) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    pipe, _, _ = build_binary_pipeline(X_train)
    class_counts = y_train.value_counts()
    min_count = int(class_counts.min()) if len(class_counts) else 0
    cv_splits = 3 if min_count >= 3 else 2
    if cv_splits < 2:
        raise RuntimeError("Not enough class support in training split for CV search.")

    cv = StratifiedKFold(n_splits=cv_splits, shuffle=True, random_state=RANDOM_STATE)
    search = RandomizedSearchCV(
        estimator=pipe,
        param_distributions=_build_param_space(class_balance_strategy),
        n_iter=n_iter,
        scoring="balanced_accuracy",
        n_jobs=-1,
        cv=cv,
        refit=True,
        random_state=RANDOM_STATE,
        verbose=0,
    )
    search.fit(X_train, y_train)
    return search.best_estimator_, search.best_params_, {
        "best_cv_balanced_accuracy": float(search.best_score_),
        "cv_splits": cv_splits,
        "n_iter": int(n_iter),
    }


def _fit_calibrator(
    cfg: ExperimentConfig,
    estimator: Any,
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> Tuple[Optional[Any], str]:
    strategy = cfg.calibration_strategy.strip().lower()
    if strategy in {"none", ""}:
        return None, "none"

    class_counts = y_train.value_counts()
    min_count = int(class_counts.min()) if len(class_counts) else 0
    if min_count < 3:
        return None, "none_low_support"

    method = "sigmoid" if strategy == "sigmoid" else "isotonic"
    if method == "isotonic" and min_count < 8:
        method = "sigmoid"
    try:
        calibrator = CalibratedClassifierCV(estimator=estimator, method=method, cv=3)
        calibrator.fit(X_train, y_train)
        return calibrator, method
    except Exception:
        return None, "none_failed"


def _pick_threshold(threshold_df: pd.DataFrame, strategy: str) -> Dict[str, Any]:
    if threshold_df.empty:
        raise RuntimeError("No threshold candidates available.")
    strategy = strategy.strip().lower()
    if strategy in {"youden_j", "best_f1", "sensitivity_priority", "fixed_0_5"}:
        hit = threshold_df[threshold_df["method"] == strategy]
        if not hit.empty:
            return hit.iloc[0].to_dict()
    return threshold_df.sort_values(
        ["balanced_accuracy", "recall", "specificity", "f1", "precision"],
        ascending=False,
    ).iloc[0].to_dict()


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _save_feature_list(features: Sequence[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(list(features)) + "\n", encoding="utf-8")


def _current_champion_map(version_registry: pd.DataFrame) -> Dict[str, str]:
    out: Dict[str, str] = {}
    subset = version_registry[
        (version_registry["promoted"].astype(str).str.lower() == "yes")
        & (version_registry["promoted_status"].astype(str).str.lower() == "champion")
    ].copy()
    for _, row in subset.iterrows():
        out[str(row["disorder"])] = str(row["model_version"])
    return out


def run_experiment(
    root: Path,
    dirs: Dict[str, Path],
    cfg: ExperimentConfig,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    dataset_path = _resolve_dataset_path(root, cfg.dataset_name, cfg.data_scope)
    split_dir = _resolve_split_dir(root, cfg.dataset_name, cfg.data_scope)
    df = pd.read_csv(dataset_path)
    if "participant_id" not in df.columns:
        raise RuntimeError(f"{dataset_path} missing participant_id")
    if cfg.target not in df.columns:
        raise RuntimeError(f"{dataset_path} missing target {cfg.target}")

    X_all, y_df, removed_base = sanitize_features(df, task="binary", target_column=cfg.target)
    for target_col in TARGET_COLUMNS:
        if target_col in X_all.columns:
            raise RuntimeError(f"Leakage detected for {cfg.model_version}: {target_col} still present in X")

    split_source = pd.concat([df[["participant_id"]], X_all, y_df], axis=1)
    splits = _load_frozen_splits(split_source, split_dir, cfg.target, list(X_all.columns))
    X_train = splits["X_train"].copy()
    X_val = splits["X_val"].copy()
    X_test = splits["X_test"].copy()
    y_train = splits["y_train"][cfg.target].astype(int)
    y_val = splits["y_val"][cfg.target].astype(int)
    y_test = splits["y_test"][cfg.target].astype(int)

    raw_feature_count = X_train.shape[1]
    X_train, X_val, X_test, strategy_meta = apply_feature_strategy(cfg, X_train, X_val, X_test, y_train)
    final_feature_count = X_train.shape[1]

    estimator, best_params, search_meta = _fit_search(X_train, y_train, cfg.class_balance_strategy, n_iter=10)
    calibrator, calibration_used = _fit_calibrator(cfg, estimator, X_train, y_train)
    scorer = calibrator if calibrator is not None else estimator
    val_prob = scorer.predict_proba(X_val)[:, 1]
    test_prob = scorer.predict_proba(X_test)[:, 1]

    threshold_df = threshold_candidates(y_val.to_numpy(), val_prob, sensitivity_target=0.85)
    threshold_df.insert(0, "model_version", cfg.model_version)
    threshold_df.insert(1, "dataset_name", cfg.dataset_name)
    selected = _pick_threshold(threshold_df, cfg.threshold_strategy)
    threshold = float(selected["threshold"])

    val_metrics = binary_metrics(y_val.to_numpy(), val_prob, threshold=threshold)
    test_metrics = binary_metrics(y_test.to_numpy(), test_prob, threshold=threshold)

    model_dir = dirs["models_versioned"] / cfg.model_version
    artifact_dir = dirs["artifacts_versioned_models"] / cfg.model_version
    report_dir = dirs["reports_experiments"] / cfg.model_version
    figure_dir = root / "reports" / "figures" / cfg.model_version
    for path in [model_dir, artifact_dir, report_dir, figure_dir]:
        path.mkdir(parents=True, exist_ok=True)

    pipe_path = model_dir / "pipeline.joblib"
    calibrator_path = model_dir / "calibrated.joblib"
    metadata_path = model_dir / "metadata.json"
    manifest_path = model_dir / "manifest.json"
    feature_list_path = model_dir / "feature_list.txt"

    joblib.dump(estimator, pipe_path)
    if calibrator is not None:
        joblib.dump(calibrator, calibrator_path)

    np_test_pred = (test_prob >= threshold).astype(int)
    figs = plot_binary_curves(
        y_true=y_test.to_numpy(),
        y_prob=test_prob,
        y_pred=np_test_pred,
        title_prefix=cfg.model_version,
        out_dir=figure_dir,
    )

    importance_summary = compute_importance_reports(
        pipe=estimator,
        X_val=X_val,
        y_val=y_val,
        out_dir=report_dir,
        top_k=20,
        n_repeats=5,
    )

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

    metadata = {
        "model_version": cfg.model_version,
        "disorder": cfg.disorder,
        "target": cfg.target,
        "dataset_name": cfg.dataset_name,
        "dataset_scope": cfg.data_scope,
        "feature_strategy": cfg.feature_strategy,
        "class_balance_strategy": cfg.class_balance_strategy,
        "calibration_strategy_requested": cfg.calibration_strategy,
        "calibration_strategy_used": calibration_used,
        "threshold_strategy": cfg.threshold_strategy,
        "threshold_value": threshold,
        "feature_columns": list(X_train.columns),
        "removed_columns": removed_base,
        "strategy_meta": strategy_meta,
        "best_params": best_params,
        "search_meta": search_meta,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "figures": figs,
        "top_permutation_features": importance_summary.get("top_permutation_features", []),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    _save_feature_list(X_train.columns.tolist(), feature_list_path)

    manifest = {
        "model_version": cfg.model_version,
        "parent_version": cfg.parent_version or "",
        "task_type": "binary",
        "status": "completed",
        "dataset_name": cfg.dataset_name,
        "dataset_variant": cfg.dataset_variant,
        "data_scope": cfg.data_scope,
        "split_version": f"splits_{cfg.data_scope}_frozen_v1",
        "preprocessing_version": "rf_preproc_v1",
        "seed": RANDOM_STATE,
        "target": cfg.target,
        "n_features_raw": int(raw_feature_count),
        "n_features_final": int(final_feature_count),
        "train_rows": int(len(X_train)),
        "val_rows": int(len(X_val)),
        "test_rows": int(len(X_test)),
        "best_params": best_params,
        "search_meta": search_meta,
        "threshold_strategy": cfg.threshold_strategy,
        "threshold_value": threshold,
        "calibration_strategy": calibration_used,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "notes": cfg.notes,
        "experimental": cfg.experimental,
        "created_at": utcnow_iso(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for src in [pipe_path, metadata_path, manifest_path, feature_list_path]:
        shutil.copy2(src, artifact_dir / src.name)
    if calibrator is not None and calibrator_path.exists():
        shutil.copy2(calibrator_path, artifact_dir / calibrator_path.name)

    for fname in [
        "feature_importance_impurity.csv",
        "feature_importance_permutation.csv",
        "top_features_impurity.png",
        "top_features_permutation.png",
        "local_explanations.json",
    ]:
        src = report_dir / fname
        if src.exists():
            shutil.copy2(src, artifact_dir / fname)

    threshold_df.to_csv(report_dir / "threshold_candidates_validation.csv", index=False)
    pd.DataFrame([val_metrics]).to_csv(report_dir / "validation_metrics.csv", index=False)
    pd.DataFrame([test_metrics]).to_csv(report_dir / "test_metrics.csv", index=False)

    entry = {
        "experiment_id": f"exp_{cfg.model_version}_{utcnow_iso().replace(':', '').replace('-', '')}",
        "model_version": cfg.model_version,
        "parent_version": cfg.parent_version or "",
        "model_family": "random_forest",
        "disorder": cfg.disorder,
        "target": cfg.target,
        "task_type": cfg.task_type,
        "dataset_name": cfg.dataset_name,
        "dataset_variant": cfg.dataset_variant,
        "dataset_version": cfg.data_scope,
        "data_scope": cfg.data_scope,
        "split_version": f"splits_{cfg.data_scope}_frozen_v1",
        "preprocessing_version": "rf_preproc_v1",
        "training_date": utcnow_iso(),
        "seed": RANDOM_STATE,
        "feature_strategy": cfg.feature_strategy,
        "class_balance_strategy": cfg.class_balance_strategy,
        "calibration_strategy": calibration_used,
        "threshold_strategy": cfg.threshold_strategy,
        "threshold_value": threshold,
        "hyperparameters_json": to_json_str(best_params),
        "train_rows": int(len(X_train)),
        "val_rows": int(len(X_val)),
        "test_rows": int(len(X_test)),
        "n_features_raw": int(raw_feature_count),
        "n_features_final": int(final_feature_count),
        "validation_metrics_json": to_json_str(val_metrics),
        "test_metrics_json": to_json_str(test_metrics),
        "status": "completed",
        "promoted": "no",
        "promoted_status": "challenger",
        "rejection_reason": "",
        "notes": cfg.notes + (" | experimental" if cfg.experimental else ""),
        "artifact_dir": _relative(artifact_dir, root),
        "source_model_id": "",
    }
    lineage = {
        "experiment_id": entry["experiment_id"],
        "model_version": cfg.model_version,
        "parent_version": cfg.parent_version or "",
        "disorder": cfg.disorder,
        "change_type": "experiment_train",
        "description": cfg.notes,
        "data_scope": cfg.data_scope,
        "dataset_name": cfg.dataset_name,
        "feature_strategy": cfg.feature_strategy,
        "class_balance_strategy": cfg.class_balance_strategy,
        "calibration_strategy": calibration_used,
        "status": "completed",
        "timestamp": utcnow_iso(),
    }
    return entry, lineage


def _write_experiment_plan(path: Path, experiments: Sequence[ExperimentConfig], champion_map: Dict[str, str]) -> None:
    lines = [
        "# Versioned Experiment Plan",
        "",
        "Campaign scope: Depression, Conduct, Elimination using frozen splits and strict_no_leakage baseline.",
        "",
        "## Current champions at campaign start",
    ]
    for disorder in sorted(champion_map.keys()):
        lines.append(f"- {disorder}: {champion_map[disorder]}")
    lines.extend(["", "## Planned experiments"])
    for cfg in experiments:
        lines.append(
            f"- {cfg.model_version}: disorder={cfg.disorder}, dataset={cfg.dataset_name}, scope={cfg.data_scope}, "
            f"feature_strategy={cfg.feature_strategy}, class_balance={cfg.class_balance_strategy}, "
            f"calibration={cfg.calibration_strategy}, threshold={cfg.threshold_strategy}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run versioned RF challenger experiments on frozen splits.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)
    root = Path(args.root).resolve()
    dirs = ensure_versioning_dirs(root)

    registry_path = dirs["reports_versioning"] / "model_registry.csv"
    registry_jsonl = dirs["reports_versioning"] / "model_registry.jsonl"
    registry = load_registry(registry_path)
    champion_map = _current_champion_map(registry)
    _write_experiment_plan(dirs["reports_experiments"] / "experiment_plan.md", EXPERIMENTS, champion_map)

    lineage_path = dirs["reports_versioning"] / "experiment_lineage.csv"
    if lineage_path.exists():
        lineage_df = pd.read_csv(lineage_path)
    else:
        lineage_df = pd.DataFrame(
            columns=[
                "experiment_id",
                "model_version",
                "parent_version",
                "disorder",
                "change_type",
                "description",
                "data_scope",
                "dataset_name",
                "feature_strategy",
                "class_balance_strategy",
                "calibration_strategy",
                "status",
                "timestamp",
            ]
        )

    entries: List[Dict[str, Any]] = []
    lineage_rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    for cfg in EXPERIMENTS:
        parent = cfg.parent_version or champion_map.get(cfg.disorder, "")
        cfg_run = ExperimentConfig(
            model_version=cfg.model_version,
            disorder=cfg.disorder,
            dataset_name=cfg.dataset_name,
            data_scope=cfg.data_scope,
            feature_strategy=cfg.feature_strategy,
            top_k=cfg.top_k,
            class_balance_strategy=cfg.class_balance_strategy,
            calibration_strategy=cfg.calibration_strategy,
            threshold_strategy=cfg.threshold_strategy,
            notes=cfg.notes,
            experimental=cfg.experimental,
            parent_version=parent,
        )

        LOGGER.info("Running experiment %s", cfg_run.model_version)
        try:
            entry, lineage = run_experiment(root=root, dirs=dirs, cfg=cfg_run)
            entries.append(entry)
            lineage_rows.append(lineage)
            LOGGER.info(
                "Completed %s | val_bal_acc=%.4f | test_bal_acc=%.4f",
                cfg_run.model_version,
                metric_value(entry["validation_metrics_json"], "balanced_accuracy"),
                metric_value(entry["test_metrics_json"], "balanced_accuracy"),
            )
        except Exception as exc:
            LOGGER.exception("Experiment failed: %s", cfg_run.model_version)
            failure = {
                "experiment_id": f"exp_{cfg_run.model_version}_{utcnow_iso().replace(':', '').replace('-', '')}",
                "model_version": cfg_run.model_version,
                "parent_version": parent,
                "model_family": "random_forest",
                "disorder": cfg_run.disorder,
                "target": cfg_run.target,
                "task_type": cfg_run.task_type,
                "dataset_name": cfg_run.dataset_name,
                "dataset_variant": cfg_run.dataset_variant,
                "dataset_version": cfg_run.data_scope,
                "data_scope": cfg_run.data_scope,
                "split_version": f"splits_{cfg_run.data_scope}_frozen_v1",
                "preprocessing_version": "rf_preproc_v1",
                "training_date": utcnow_iso(),
                "seed": RANDOM_STATE,
                "feature_strategy": cfg_run.feature_strategy,
                "class_balance_strategy": cfg_run.class_balance_strategy,
                "calibration_strategy": cfg_run.calibration_strategy,
                "threshold_strategy": cfg_run.threshold_strategy,
                "threshold_value": "",
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
                "notes": cfg_run.notes,
                "artifact_dir": "",
                "source_model_id": "",
            }
            entries.append(failure)
            failures.append({"model_version": cfg_run.model_version, "error": str(exc)})
            lineage_rows.append(
                {
                    "experiment_id": failure["experiment_id"],
                    "model_version": cfg_run.model_version,
                    "parent_version": parent,
                    "disorder": cfg_run.disorder,
                    "change_type": "experiment_train",
                    "description": cfg_run.notes,
                    "data_scope": cfg_run.data_scope,
                    "dataset_name": cfg_run.dataset_name,
                    "feature_strategy": cfg_run.feature_strategy,
                    "class_balance_strategy": cfg_run.class_balance_strategy,
                    "calibration_strategy": cfg_run.calibration_strategy,
                    "status": "failed",
                    "timestamp": utcnow_iso(),
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

    summary_cols = [
        "model_version",
        "disorder",
        "dataset_name",
        "data_scope",
        "feature_strategy",
        "class_balance_strategy",
        "calibration_strategy",
        "threshold_strategy",
        "status",
        "promoted",
        "notes",
    ]
    summary_df = registry[registry["model_version"].isin([cfg.model_version for cfg in EXPERIMENTS])].copy()
    summary_df["val_balanced_accuracy"] = summary_df["validation_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
    summary_df["val_recall"] = summary_df["validation_metrics_json"].apply(lambda s: metric_value(s, "recall"))
    summary_df["val_specificity"] = summary_df["validation_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
    summary_df["val_f1"] = summary_df["validation_metrics_json"].apply(lambda s: metric_value(s, "f1"))
    summary_df["test_balanced_accuracy"] = summary_df["test_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
    summary_df["test_recall"] = summary_df["test_metrics_json"].apply(lambda s: metric_value(s, "recall"))
    summary_df["test_specificity"] = summary_df["test_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
    summary_df["test_f1"] = summary_df["test_metrics_json"].apply(lambda s: metric_value(s, "f1"))
    summary_df = summary_df[
        summary_cols
        + [
            "val_balanced_accuracy",
            "val_recall",
            "val_specificity",
            "val_f1",
            "test_balanced_accuracy",
            "test_recall",
            "test_specificity",
            "test_f1",
            "rejection_reason",
        ]
    ]

    summary_df.sort_values(["disorder", "model_version"]).to_csv(
        dirs["reports_experiments"] / "experiment_results_summary.csv",
        index=False,
    )
    for disorder in ["depression", "conduct", "elimination"]:
        summary_df[summary_df["disorder"] == disorder].copy().to_csv(
            dirs["reports_experiments"] / f"{disorder}_experiments.csv",
            index=False,
        )
    if failures:
        pd.DataFrame(failures).to_csv(dirs["reports_experiments"] / "failed_experiments.csv", index=False)

    LOGGER.info(
        "Versioned experiment campaign finished. completed=%d failed=%d",
        int((summary_df["status"] == "completed").sum()),
        int((summary_df["status"] == "failed").sum()),
    )


if __name__ == "__main__":
    main()
