from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    hamming_loss,
    precision_recall_curve,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

RANDOM_STATE = 42
TARGET_COLUMNS = [
    "target_conduct",
    "target_adhd",
    "target_elimination",
    "target_anxiety",
    "target_depression",
]

TARGET_BY_DISORDER = {
    "conduct": "target_conduct",
    "adhd": "target_adhd",
    "elimination": "target_elimination",
    "anxiety": "target_anxiety",
    "depression": "target_depression",
}

POST_DIAG_PATTERNS = (
    "diag_",
    "diagnosis",
    "consensus",
    "ksads",
    "source_target",
    "n_diagnoses",
    "has_any_target_disorder",
    "label_pattern",
)

DROP_ALWAYS = {"participant_id", "primary_target", "dataset_name", "is_exploratory"}


@dataclass
class DatasetSpec:
    path: Path
    version: str
    dataset_name: str
    disorder: str
    variant: str
    is_multilabel: bool

    @property
    def model_id(self) -> str:
        return f"{self.dataset_name}__{self.version}"


def ensure_dirs(paths: Iterable[Path]) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def safe_json(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def parse_dataset_spec(path: Path, version: str) -> Optional[DatasetSpec]:
    stem = path.stem
    if stem.startswith("dataset_"):
        base = stem
        suffix = f"_{version}"
        if base.endswith(suffix):
            base = base[: -len(suffix)]
        parts = base.split("_")
        if len(parts) < 3:
            return None
        disorder = parts[1]
        variant = "_".join(parts[2:])
        return DatasetSpec(
            path=path,
            version=version,
            dataset_name=base,
            disorder=disorder,
            variant=variant,
            is_multilabel=False,
        )
    if "master_multilabel_ready" in stem:
        return DatasetSpec(
            path=path,
            version=version,
            dataset_name="master_multilabel_ready",
            disorder="multilabel",
            variant="master",
            is_multilabel=True,
        )
    return None


def discover_datasets(root: Path) -> List[DatasetSpec]:
    result: List[DatasetSpec] = []
    base = root / "data" / "processed" / "final"
    for version in ("strict_no_leakage", "research_extended"):
        ver_dir = base / version
        if not ver_dir.exists():
            continue
        for path in sorted(ver_dir.glob("*.csv")):
            spec = parse_dataset_spec(path, version)
            if spec is not None:
                result.append(spec)
    return result


def read_manifest(root: Path, dataset_name: str, version: str) -> Optional[Dict[str, Any]]:
    manifest = root / "data" / "processed" / "metadata" / "model_manifests" / f"{dataset_name}__{version}.json"
    if manifest.exists():
        return json.loads(manifest.read_text(encoding="utf-8"))
    return None


def infer_target_column(df: pd.DataFrame, spec: DatasetSpec) -> Optional[str]:
    if spec.is_multilabel:
        return None
    if "primary_target" in df.columns and df["primary_target"].notna().any():
        value = str(df["primary_target"].dropna().iloc[0]).strip()
        if value in TARGET_COLUMNS:
            return value
    return TARGET_BY_DISORDER.get(spec.disorder)


def sanitize_features(
    df: pd.DataFrame,
    task: str,
    target_column: Optional[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    if "participant_id" not in df.columns:
        raise ValueError("Dataset without participant_id is not supported.")

    removed: Dict[str, str] = {}
    if task == "binary":
        if not target_column or target_column not in df.columns:
            raise ValueError(f"Binary dataset missing target column: {target_column}")
        y = pd.DataFrame({target_column: pd.to_numeric(df[target_column], errors="coerce").fillna(0).astype(int)})
    else:
        missing_targets = [c for c in TARGET_COLUMNS if c not in df.columns]
        if missing_targets:
            raise ValueError(f"Multilabel dataset missing targets: {missing_targets}")
        y = df[TARGET_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)

    feature_cols: List[str] = []
    for col in df.columns:
        low = col.lower()
        if col in DROP_ALWAYS:
            removed[col] = "meta"
            continue
        if col in TARGET_COLUMNS:
            removed[col] = "target_column"
            continue
        if low in {"primary_target"}:
            removed[col] = "meta"
            continue
        if any(token in low for token in POST_DIAG_PATTERNS):
            removed[col] = "post_diagnostic_pattern"
            continue
        feature_cols.append(col)

    X = df[feature_cols].copy()
    overlap = sorted(set(X.columns) & set(TARGET_COLUMNS))
    if overlap:
        raise RuntimeError(f"Leakage guard failed, targets found in X: {overlap}")
    return X, y, removed


def _build_stratify_vector(task: str, y: pd.DataFrame, target_col: Optional[str]) -> Optional[pd.Series]:
    if task == "binary" and target_col:
        vc = y[target_col].value_counts()
        if len(vc) > 1 and vc.min() >= 2:
            return y[target_col]
        return None

    if task == "multilabel":
        label_pattern = y[TARGET_COLUMNS].astype(str).agg("".join, axis=1)
        vc = label_pattern.value_counts()
        if len(vc) > 1 and vc.min() >= 2:
            return label_pattern
    return None


def _split_ids_with_reproducibility(
    ids: pd.Series,
    y: pd.DataFrame,
    task: str,
    target_col: Optional[str],
) -> Tuple[List[str], List[str], List[str]]:
    strat = _build_stratify_vector(task, y, target_col)
    idx = np.arange(len(ids))
    idx_tv, idx_test = train_test_split(
        idx,
        test_size=0.15,
        random_state=RANDOM_STATE,
        stratify=(strat.values if strat is not None else None),
    )

    strat_tv = None
    if strat is not None:
        strat_tv = strat.iloc[idx_tv]
        if strat_tv.value_counts().min() < 2:
            strat_tv = None

    idx_train, idx_val = train_test_split(
        idx_tv,
        test_size=0.1764706,
        random_state=RANDOM_STATE,
        stratify=(strat_tv.values if strat_tv is not None else None),
    )
    return (
        ids.iloc[idx_train].astype(str).tolist(),
        ids.iloc[idx_val].astype(str).tolist(),
        ids.iloc[idx_test].astype(str).tolist(),
    )


def _validate_existing_id_splits(ids_train: Sequence[str], ids_val: Sequence[str], ids_test: Sequence[str], all_ids: set[str]) -> Optional[str]:
    tr, va, te = set(ids_train), set(ids_val), set(ids_test)
    if tr & va or tr & te or va & te:
        return "participant_overlap_between_splits"
    if not tr or not va or not te:
        return "one_split_is_empty"
    if not (tr | va | te).issubset(all_ids):
        return "ids_not_present_in_dataset"
    return None


def load_or_create_splits(
    root: Path,
    spec: DatasetSpec,
    df: pd.DataFrame,
    X: pd.DataFrame,
    y: pd.DataFrame,
    task: str,
    target_col: Optional[str],
    split_decisions: List[Dict[str, Any]],
) -> Dict[str, pd.DataFrame]:
    split_dir = root / "data" / "processed" / "splits" / spec.dataset_name / spec.version
    ensure_dirs([split_dir])

    ids_series = df["participant_id"].astype(str)
    all_ids = set(ids_series.tolist())
    required = [split_dir / f"ids_{name}.csv" for name in ("train", "val", "test")]
    use_existing = all(p.exists() for p in required)
    regen_reason = ""

    if use_existing:
        ids_train = pd.read_csv(split_dir / "ids_train.csv")["participant_id"].astype(str).tolist()
        ids_val = pd.read_csv(split_dir / "ids_val.csv")["participant_id"].astype(str).tolist()
        ids_test = pd.read_csv(split_dir / "ids_test.csv")["participant_id"].astype(str).tolist()
        err = _validate_existing_id_splits(ids_train, ids_val, ids_test, all_ids)
        if err:
            use_existing = False
            regen_reason = err
    else:
        ids_train = ids_val = ids_test = []
        regen_reason = "missing_split_files"

    if not use_existing:
        ids_train, ids_val, ids_test = _split_ids_with_reproducibility(ids_series, y, task, target_col)
        safe_csv(pd.DataFrame({"participant_id": ids_train}), split_dir / "ids_train.csv")
        safe_csv(pd.DataFrame({"participant_id": ids_val}), split_dir / "ids_val.csv")
        safe_csv(pd.DataFrame({"participant_id": ids_test}), split_dir / "ids_test.csv")
        split_decisions.append(
            {
                "dataset": spec.dataset_name,
                "version": spec.version,
                "action": "regenerated",
                "reason": regen_reason or "missing_or_inconsistent",
            }
        )
    else:
        split_decisions.append(
            {
                "dataset": spec.dataset_name,
                "version": spec.version,
                "action": "reused",
                "reason": "existing_ids_consistent",
            }
        )

    indexed = pd.concat([df[["participant_id"]], X, y], axis=1).copy()
    indexed["participant_id"] = indexed["participant_id"].astype(str)
    indexed = indexed.set_index("participant_id", drop=True)

    def subset(ids_list: Sequence[str]) -> pd.DataFrame:
        return indexed.loc[list(ids_list)].reset_index(drop=True)

    tr = subset(ids_train)
    va = subset(ids_val)
    te = subset(ids_test)

    X_cols = list(X.columns)
    y_cols = list(y.columns)

    return {
        "X_train": tr[X_cols].copy(),
        "X_val": va[X_cols].copy(),
        "X_test": te[X_cols].copy(),
        "y_train": tr[y_cols].copy(),
        "y_val": va[y_cols].copy(),
        "y_test": te[y_cols].copy(),
        "ids_train": pd.DataFrame({"participant_id": ids_train}),
        "ids_val": pd.DataFrame({"participant_id": ids_val}),
        "ids_test": pd.DataFrame({"participant_id": ids_test}),
    }


def build_preprocessor(X_train: pd.DataFrame) -> Tuple[ColumnTransformer, List[str], List[str]]:
    numeric_cols = [c for c in X_train.columns if pd.api.types.is_numeric_dtype(X_train[c])]
    categorical_cols = [c for c in X_train.columns if c not in numeric_cols]
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric_cols),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical_cols,
            ),
        ],
        remainder="drop",
    )
    return preprocessor, numeric_cols, categorical_cols


def binary_param_grid() -> Dict[str, Sequence[Any]]:
    return {
        "model__n_estimators": [150, 250, 350],
        "model__max_depth": [None, 10, 20, 30],
        "model__min_samples_split": [2, 5, 10],
        "model__min_samples_leaf": [1, 2, 4],
        "model__max_features": ["sqrt", "log2", 0.5],
        "model__class_weight": [None, "balanced", "balanced_subsample"],
    }


def build_binary_pipeline(X_train: pd.DataFrame) -> Tuple[Pipeline, List[str], List[str]]:
    preprocessor, numeric_cols, categorical_cols = build_preprocessor(X_train)
    clf = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1)
    pipe = Pipeline([("preprocessor", preprocessor), ("model", clf)])
    return pipe, numeric_cols, categorical_cols


def run_binary_hyperparam_search(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_iter: int,
    logger: logging.Logger,
) -> Tuple[Pipeline, Dict[str, Any], Dict[str, Any]]:
    base_pipe, _, _ = build_binary_pipeline(X_train)
    class_counts = y_train.value_counts()
    min_count = int(class_counts.min()) if len(class_counts) else 0
    cv_splits = 3 if min_count >= 3 else 2
    if cv_splits < 2:
        raise ValueError("Not enough samples per class for CV search.")

    cv = StratifiedKFold(n_splits=cv_splits, shuffle=True, random_state=RANDOM_STATE)
    search = RandomizedSearchCV(
        estimator=base_pipe,
        param_distributions=binary_param_grid(),
        n_iter=n_iter,
        scoring="balanced_accuracy",
        n_jobs=-1,
        cv=cv,
        refit=True,
        random_state=RANDOM_STATE,
        verbose=0,
    )
    search.fit(X_train, y_train)
    logger.info("Best params: %s | best_cv_balanced_accuracy=%.4f", search.best_params_, search.best_score_)
    return search.best_estimator_, search.best_params_, {
        "best_cv_balanced_accuracy": float(search.best_score_),
        "cv_splits": cv_splits,
        "n_iter": n_iter,
    }


def build_binary_pipeline_from_params(X_train: pd.DataFrame, params: Dict[str, Any]) -> Pipeline:
    pipe, _, _ = build_binary_pipeline(X_train)
    pipe.set_params(**params)
    return pipe


def maybe_fit_calibrator(
    estimator: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    logger: logging.Logger,
) -> Optional[CalibratedClassifierCV]:
    class_counts = y_train.value_counts()
    min_count = int(class_counts.min()) if len(class_counts) else 0
    if min_count < 3:
        logger.warning("Calibration skipped due to low minority class support (min_count=%s).", min_count)
        return None
    try:
        calibrator = CalibratedClassifierCV(estimator=estimator, method="sigmoid", cv=3)
        calibrator.fit(X_train, y_train)
        return calibrator
    except Exception as exc:
        logger.warning("Calibration failed and will be skipped: %s", exc)
        return None


def compute_specificity(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, _, _ = cm.ravel()
    denom = tn + fp
    return float(tn / denom) if denom else 0.0


def binary_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> Dict[str, Any]:
    y_pred = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    cm_norm = confusion_matrix(y_true, y_pred, labels=[0, 1], normalize="true")
    precision, recall, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1], zero_division=0)

    out = {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "sensitivity": float(recall_score(y_true, y_pred, zero_division=0)),
        "specificity": float(compute_specificity(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "support_negative": int(support[0]),
        "support_positive": int(support[1]),
        "confusion_matrix": cm.tolist(),
        "normalized_confusion_matrix": cm_norm.tolist(),
    }
    try:
        out["roc_auc"] = float(roc_auc_score(y_true, y_prob))
    except Exception:
        out["roc_auc"] = float("nan")
    try:
        out["pr_auc"] = float(average_precision_score(y_true, y_prob))
    except Exception:
        out["pr_auc"] = float("nan")
    out["brier_score"] = float(np.mean((y_prob - y_true) ** 2))
    return out


def threshold_candidates(y_true: np.ndarray, y_prob: np.ndarray, sensitivity_target: float = 0.85) -> pd.DataFrame:
    candidates: List[Tuple[str, float]] = [("fixed_0_5", 0.5)]
    fpr, tpr, thr = roc_curve(y_true, y_prob)
    j = tpr - fpr
    if len(j):
        best_idx = int(np.argmax(j))
        youden_thr = float(thr[best_idx])
        if np.isfinite(youden_thr):
            candidates.append(("youden_j", max(0.0, min(1.0, youden_thr))))

    uniq = np.unique(np.round(y_prob, 6))
    if len(uniq) > 0:
        best_f1 = -1.0
        best_thr = 0.5
        sens_pool: List[Tuple[float, Dict[str, Any]]] = []
        for t in uniq:
            m = binary_metrics(y_true, y_prob, float(t))
            if m["f1"] > best_f1:
                best_f1 = m["f1"]
                best_thr = float(t)
            if m["recall"] >= sensitivity_target:
                sens_pool.append((float(t), m))
        candidates.append(("best_f1", best_thr))
        if sens_pool:
            sens_pool.sort(key=lambda x: (x[1]["specificity"], x[1]["balanced_accuracy"], -x[0]), reverse=True)
            candidates.append(("sensitivity_priority", sens_pool[0][0]))
        else:
            fallback = max(uniq, key=lambda t: binary_metrics(y_true, y_prob, float(t))["recall"])
            candidates.append(("sensitivity_priority", float(fallback)))

    seen = set()
    rows = []
    for method, threshold in candidates:
        key = (method, round(threshold, 6))
        if key in seen:
            continue
        seen.add(key)
        m = binary_metrics(y_true, y_prob, threshold)
        m["method"] = method
        rows.append(m)
    df = pd.DataFrame(rows)
    order = ["balanced_accuracy", "recall", "specificity", "f1", "precision"]
    return df.sort_values(order, ascending=False).reset_index(drop=True)


def pick_recommended_threshold(threshold_df: pd.DataFrame) -> Dict[str, Any]:
    best = threshold_df.iloc[0].to_dict()
    return {
        "method": best["method"],
        "threshold": float(best["threshold"]),
        "val_balanced_accuracy": float(best["balanced_accuracy"]),
        "val_recall": float(best["recall"]),
        "val_specificity": float(best["specificity"]),
        "val_f1": float(best["f1"]),
    }


def plot_binary_curves(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    y_pred: np.ndarray,
    title_prefix: str,
    out_dir: Path,
) -> Dict[str, str]:
    ensure_dirs([out_dir])
    paths: Dict[str, str] = {}

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    roc_auc = roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else float("nan")
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, label=f"ROC AUC={roc_auc:.3f}")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title(f"{title_prefix} - ROC")
    plt.legend(loc="lower right")
    roc_path = out_dir / f"{title_prefix}_roc.png"
    plt.tight_layout()
    plt.savefig(roc_path, dpi=150)
    plt.close()
    paths["roc_curve"] = str(roc_path)

    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    pr_auc = average_precision_score(y_true, y_prob)
    plt.figure(figsize=(6, 5))
    plt.plot(recall, precision, label=f"PR AUC={pr_auc:.3f}")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title(f"{title_prefix} - PR")
    plt.legend(loc="lower left")
    pr_path = out_dir / f"{title_prefix}_pr.png"
    plt.tight_layout()
    plt.savefig(pr_path, dpi=150)
    plt.close()
    paths["pr_curve"] = str(pr_path)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    cm_norm = confusion_matrix(y_true, y_pred, labels=[0, 1], normalize="true")
    for name, matrix in (("confusion", cm), ("confusion_normalized", cm_norm)):
        plt.figure(figsize=(5, 4))
        plt.imshow(matrix, cmap="Blues")
        plt.xticks([0, 1], ["Pred 0", "Pred 1"])
        plt.yticks([0, 1], ["True 0", "True 1"])
        for i in range(2):
            for j in range(2):
                val = matrix[i, j]
                txt = f"{val:.2f}" if name.endswith("normalized") else f"{int(val)}"
                plt.text(j, i, txt, ha="center", va="center", color="black")
        plt.title(f"{title_prefix} - {name.replace('_', ' ').title()}")
        plt.colorbar()
        cm_path = out_dir / f"{title_prefix}_{name}.png"
        plt.tight_layout()
        plt.savefig(cm_path, dpi=150)
        plt.close()
        paths[name] = str(cm_path)

    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy="quantile")
    plt.figure(figsize=(6, 5))
    plt.plot(prob_pred, prob_true, marker="o", label="Model")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect")
    plt.xlabel("Predicted probability")
    plt.ylabel("Observed frequency")
    plt.title(f"{title_prefix} - Calibration")
    plt.legend(loc="upper left")
    cal_path = out_dir / f"{title_prefix}_calibration.png"
    plt.tight_layout()
    plt.savefig(cal_path, dpi=150)
    plt.close()
    paths["calibration_curve"] = str(cal_path)
    return paths


def get_feature_names_from_pipeline(pipe: Pipeline) -> List[str]:
    prep: ColumnTransformer = pipe.named_steps["preprocessor"]
    names = [str(n) for n in prep.get_feature_names_out()]
    model = pipe.named_steps.get("model")
    if hasattr(model, "feature_importances_"):
        dim = len(model.feature_importances_)
        if len(names) > dim:
            names = names[:dim]
        elif len(names) < dim:
            names = names + [f"feature_{i}" for i in range(len(names), dim)]
    return names


def compute_importance_reports(
    pipe: Pipeline,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    out_dir: Path,
    top_k: int = 20,
    n_repeats: int = 5,
) -> Dict[str, Any]:
    ensure_dirs([out_dir])
    feat_names = get_feature_names_from_pipeline(pipe)
    model: RandomForestClassifier = pipe.named_steps["model"]
    model_dim = len(model.feature_importances_)
    if len(feat_names) != model_dim:
        if len(feat_names) > model_dim:
            feat_names = feat_names[:model_dim]
        else:
            feat_names = feat_names + [f"feature_{i}" for i in range(len(feat_names), model_dim)]
    impurity = pd.DataFrame({"feature": feat_names, "importance": model.feature_importances_}).sort_values(
        "importance", ascending=False
    )
    safe_csv(impurity, out_dir / "feature_importance_impurity.csv")

    perm = permutation_importance(
        estimator=pipe,
        X=X_val,
        y=y_val,
        n_repeats=n_repeats,
        random_state=RANDOM_STATE,
        scoring="balanced_accuracy",
        n_jobs=-1,
    )
    perm_dim = len(perm.importances_mean)
    perm_names = feat_names[:perm_dim] if len(feat_names) >= perm_dim else feat_names + [
        f"feature_{i}" for i in range(len(feat_names), perm_dim)
    ]
    perm_df = pd.DataFrame(
        {"feature": perm_names, "importance_mean": perm.importances_mean, "importance_std": perm.importances_std}
    ).sort_values("importance_mean", ascending=False)
    safe_csv(perm_df, out_dir / "feature_importance_permutation.csv")

    top_imp = impurity.head(top_k)
    plt.figure(figsize=(8, 6))
    plt.barh(top_imp["feature"][::-1], top_imp["importance"][::-1], color="#1790E9")
    plt.title("Top features by impurity importance")
    plt.xlabel("Importance")
    plt.tight_layout()
    fig_imp = out_dir / "top_features_impurity.png"
    plt.savefig(fig_imp, dpi=150)
    plt.close()

    top_perm = perm_df.head(top_k)
    plt.figure(figsize=(8, 6))
    plt.barh(top_perm["feature"][::-1], top_perm["importance_mean"][::-1], color="#51C2F4")
    plt.title("Top features by permutation importance")
    plt.xlabel("Mean importance")
    plt.tight_layout()
    fig_perm = out_dir / "top_features_permutation.png"
    plt.savefig(fig_perm, dpi=150)
    plt.close()

    return {
        "top_impurity_features": top_imp["feature"].tolist(),
        "top_permutation_features": top_perm["feature"].tolist(),
        "figure_top_impurity": str(fig_imp),
        "figure_top_permutation": str(fig_perm),
    }


def approximate_local_contributors(
    pipe: Pipeline,
    X_reference: pd.DataFrame,
    X_samples: pd.DataFrame,
    sample_ids: Sequence[str],
    top_k: int = 10,
) -> Dict[str, Any]:
    prep: ColumnTransformer = pipe.named_steps["preprocessor"]
    model: RandomForestClassifier = pipe.named_steps["model"]
    feat_names = get_feature_names_from_pipeline(pipe)
    ref_trans = np.asarray(prep.transform(X_reference))
    sample_trans = np.asarray(prep.transform(X_samples))
    ref_median = np.median(ref_trans, axis=0)
    importances = np.asarray(model.feature_importances_)
    dim = min(len(feat_names), len(importances), ref_median.shape[0], sample_trans.shape[1])
    feat_names = feat_names[:dim]
    ref_median = ref_median[:dim]
    importances = importances[:dim]

    out: Dict[str, Any] = {}
    for idx, sid in enumerate(sample_ids):
        vec = np.asarray(sample_trans[idx, :dim]).ravel()
        contrib = (vec - ref_median) * importances
        pos_idx = np.argsort(contrib)[::-1][:top_k]
        neg_idx = np.argsort(contrib)[:top_k]
        out[str(sid)] = {
            "top_positive_contributors": [{"feature": feat_names[i], "score": float(contrib[i])} for i in pos_idx],
            "top_negative_contributors": [{"feature": feat_names[i], "score": float(contrib[i])} for i in neg_idx],
        }
    return out


def subgroup_binary_metrics(
    metadata_df: pd.DataFrame,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
) -> pd.DataFrame:
    y_pred = (y_prob >= threshold).astype(int)
    df = metadata_df.copy()
    df["y_true"] = y_true
    df["y_pred"] = y_pred
    df["y_prob"] = y_prob

    groups: List[Tuple[str, str, pd.Series]] = []
    if "age_years" in df.columns:
        age = pd.to_numeric(df["age_years"], errors="coerce")
        age_group = pd.cut(age, bins=[5.5, 8.5, 11.5], labels=["6-8", "9-11"])
        groups.append(("age_group", "age_years", age_group.astype(str)))
    if "sex_assigned_at_birth" in df.columns:
        groups.append(("sex_assigned_at_birth", "sex_assigned_at_birth", df["sex_assigned_at_birth"].astype(str)))
    if "comorbidity_count_5targets" in df.columns:
        c = pd.to_numeric(df["comorbidity_count_5targets"], errors="coerce")
        c_group = pd.cut(c, bins=[-0.1, 0.5, 2.5, 100], labels=["0", "1-2", "3+"])
        groups.append(("comorbidity_group", "comorbidity_count_5targets", c_group.astype(str)))

    rows: List[Dict[str, Any]] = []
    for group_name, source_col, values in groups:
        tmp = df.copy()
        tmp["_group"] = values
        for value, g in tmp.groupby("_group", dropna=False):
            n = len(g)
            if n < 30 or g["y_true"].nunique() < 2:
                rows.append(
                    {
                        "group_name": group_name,
                        "group_value": str(value),
                        "source_column": source_col,
                        "n": n,
                        "status": "insufficient_support",
                    }
                )
                continue
            m = binary_metrics(g["y_true"].to_numpy(), g["y_prob"].to_numpy(), threshold)
            m.update(
                {
                    "group_name": group_name,
                    "group_value": str(value),
                    "source_column": source_col,
                    "n": n,
                    "status": "ok",
                }
            )
            rows.append(m)
    return pd.DataFrame(rows)


def map_risk_band(prob: float) -> str:
    if prob < 0.33:
        return "low"
    if prob < 0.66:
        return "moderate"
    return "high"


def evidence_quality_from_missing(missing_ratio: float) -> str:
    if missing_ratio >= 0.4:
        return "weak"
    if missing_ratio >= 0.2:
        return "medium"
    return "strong"


def select_best_binary_per_disorder(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results
    ordered = results.sort_values(
        by=[
            "disorder",
            "balanced_accuracy_test",
            "recall_test",
            "specificity_test",
            "f1_test",
            "brier_score_test",
            "n_features",
        ],
        ascending=[True, False, False, False, False, True, True],
    )
    return ordered.groupby("disorder", as_index=False).head(1).reset_index(drop=True)


def multilabel_param_grid() -> Dict[str, Sequence[Any]]:
    return {
        "model__estimator__n_estimators": [150, 250, 350],
        "model__estimator__max_depth": [None, 10, 20, 30],
        "model__estimator__min_samples_split": [2, 5, 10],
        "model__estimator__min_samples_leaf": [1, 2, 4],
        "model__estimator__max_features": ["sqrt", "log2", 0.5],
        "model__estimator__class_weight": [None, "balanced", "balanced_subsample"],
    }


def build_multilabel_pipeline(X_train: pd.DataFrame) -> Pipeline:
    preprocessor, _, _ = build_preprocessor(X_train)
    base = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1)
    clf = MultiOutputClassifier(base, n_jobs=1)
    return Pipeline([("preprocessor", preprocessor), ("model", clf)])


def get_multilabel_probabilities(estimator: Pipeline, X: pd.DataFrame) -> np.ndarray:
    probs = estimator.predict_proba(X)
    out = np.zeros((len(X), len(TARGET_COLUMNS)), dtype=float)
    for i, arr in enumerate(probs):
        out[:, i] = arr[:, 1] if arr.shape[1] > 1 else arr[:, 0]
    return out


def multilabel_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> Dict[str, Any]:
    micro_p, micro_r, micro_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="micro", zero_division=0)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )
    out: Dict[str, Any] = {
        "subset_accuracy": float(accuracy_score(y_true, y_pred)),
        "hamming_loss": float(hamming_loss(y_true, y_pred)),
        "micro_precision": float(micro_p),
        "micro_recall": float(micro_r),
        "micro_f1": float(micro_f1),
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "weighted_precision": float(weighted_p),
        "weighted_recall": float(weighted_r),
        "weighted_f1": float(weighted_f1),
    }
    per_label = []
    for i, target in enumerate(TARGET_COLUMNS):
        yt = y_true[:, i]
        ypr = y_prob[:, i]
        m = binary_metrics(yt, ypr, threshold=0.5)
        m["target"] = target
        per_label.append(m)
    out["per_label"] = per_label
    return out


def multilabel_comorbidity_matrix(y: np.ndarray, labels: Sequence[str]) -> pd.DataFrame:
    mat = np.zeros((len(labels), len(labels)), dtype=int)
    for i in range(len(labels)):
        for j in range(len(labels)):
            mat[i, j] = int(np.logical_and(y[:, i] == 1, y[:, j] == 1).sum())
    return pd.DataFrame(mat, index=labels, columns=labels)


def ensure_output_structure(root: Path) -> Dict[str, Path]:
    paths = {
        "models_binary": root / "models" / "binary",
        "models_multilabel": root / "models" / "multilabel",
        "models_calibrated": root / "models" / "calibrated",
        "reports_training": root / "reports" / "training",
        "reports_metrics": root / "reports" / "metrics",
        "reports_figures": root / "reports" / "figures",
        "reports_comparisons": root / "reports" / "comparisons",
        "artifacts_models": root / "artifacts" / "models",
        "artifacts_inference": root / "artifacts" / "inference",
    }
    ensure_dirs(paths.values())
    ensure_dirs(
        [
            paths["artifacts_models"] / "binary",
            paths["artifacts_models"] / "multilabel",
            paths["artifacts_models"] / "calibrated",
        ]
    )
    return paths


def copy_model_artifact(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
