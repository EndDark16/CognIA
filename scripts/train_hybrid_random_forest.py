#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    hamming_loss,
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


LOGGER = logging.getLogger("hybrid-rf")
RANDOM_STATE = 42

DOMAIN_TARGETS = {
    "adhd": "target_domain_adhd",
    "conduct": "target_domain_conduct",
    "elimination": "target_domain_elimination",
    "anxiety": "target_domain_anxiety",
    "depression": "target_domain_depression",
}

INTERNAL_TARGETS = {
    "adhd": "target_adhd_exact",
    "conduct_disorder": "target_conduct_disorder_exact",
    "enuresis": "target_enuresis_exact",
    "encopresis": "target_encopresis_exact",
    "separation_anxiety_disorder": "target_separation_anxiety_disorder_exact",
    "generalized_anxiety_disorder": "target_generalized_anxiety_disorder_exact",
    "major_depressive_disorder": "target_major_depressive_disorder_exact",
    "persistent_depressive_disorder": "target_persistent_depressive_disorder_exact",
    "dmdd": "target_dmdd_exact",
}

TARGET_COLUMNS = list(DOMAIN_TARGETS.values()) + list(INTERNAL_TARGETS.values())


@dataclass
class DatasetTask:
    task_name: str
    task_kind: str  # binary_domain | binary_internal | multilabel_domain
    scope: str  # strict_no_leakage_hybrid | research_extended_hybrid
    dataset_variant: str  # full | compact | internal_compact | multilabel
    dataset_path: Path
    target_column: Optional[str] = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def safe_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_json(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def safe_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sanitize_binary_features(df: pd.DataFrame, target_col: str) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    y = pd.to_numeric(df[target_col], errors="coerce").fillna(0).astype(int)
    drop_cols: List[str] = []
    for col in df.columns:
        low = col.lower()
        if col == target_col or col == "participant_id":
            drop_cols.append(col)
            continue
        if col.startswith("target_"):
            drop_cols.append(col)
            continue
        if low.endswith("_status") or low.endswith("_confidence") or low.endswith("_coverage"):
            drop_cols.append(col)
            continue
        if "diagnosis" in low or "consensus" in low or "ksads" in low:
            drop_cols.append(col)
            continue
    X = df.drop(columns=drop_cols, errors="ignore").copy()
    extra_drop: List[str] = []
    extra_drop += [c for c in X.columns if X[c].notna().sum() == 0]
    extra_drop += [c for c in X.columns if X[c].notna().mean() < 0.02]
    extra_drop += [c for c in X.columns if X[c].nunique(dropna=True) <= 1]
    if extra_drop:
        X = X.drop(columns=sorted(set(extra_drop)), errors="ignore")
    if X.shape[1] > 600:
        keep = X.notna().mean().sort_values(ascending=False).head(600).index.tolist()
        trimmed = [c for c in X.columns if c not in keep]
        X = X[keep].copy()
        extra_drop += trimmed
    drop_cols += extra_drop
    return X, y, sorted(set(drop_cols))


def sanitize_multilabel_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    y = df[list(DOMAIN_TARGETS.values())].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    drop_cols: List[str] = []
    for col in df.columns:
        low = col.lower()
        if col == "participant_id" or col.startswith("target_"):
            drop_cols.append(col)
            continue
        if low.endswith("_status") or low.endswith("_confidence") or low.endswith("_coverage"):
            drop_cols.append(col)
            continue
        if "diagnosis" in low or "consensus" in low or "ksads" in low:
            drop_cols.append(col)
            continue
    X = df.drop(columns=drop_cols, errors="ignore").copy()
    extra_drop: List[str] = []
    extra_drop += [c for c in X.columns if X[c].notna().sum() == 0]
    extra_drop += [c for c in X.columns if X[c].notna().mean() < 0.02]
    extra_drop += [c for c in X.columns if X[c].nunique(dropna=True) <= 1]
    if extra_drop:
        X = X.drop(columns=sorted(set(extra_drop)), errors="ignore")
    if X.shape[1] > 600:
        keep = X.notna().mean().sort_values(ascending=False).head(600).index.tolist()
        trimmed = [c for c in X.columns if c not in keep]
        X = X[keep].copy()
        extra_drop += trimmed
    drop_cols += extra_drop
    return X, y, sorted(set(drop_cols))


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    num_cols = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    cat_cols = [c for c in X.columns if c not in num_cols]
    return ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num_cols),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("ohe", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                cat_cols,
            ),
        ],
        remainder="drop",
    )


def create_pipeline(X: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> Pipeline:
    model = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1)
    if params:
        model.set_params(**params)
    return Pipeline([("preprocessor", build_preprocessor(X)), ("model", model)])


def binary_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> Dict[str, Any]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    out = {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "specificity": float(specificity),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan"),
        "pr_auc": float(average_precision_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan"),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "support_negative": int((y_true == 0).sum()),
        "support_positive": int((y_true == 1).sum()),
        "false_positive_rate": float(fp / (fp + tn) if (fp + tn) else 0.0),
        "false_negative_rate": float(fn / (fn + tp) if (fn + tp) else 0.0),
    }
    return out


def get_split_ids(
    ids: pd.Series,
    y: pd.Series,
    split_dir: Path,
) -> Tuple[List[str], List[str], List[str], str]:
    split_dir.mkdir(parents=True, exist_ok=True)
    train_path = split_dir / "ids_train.csv"
    val_path = split_dir / "ids_val.csv"
    test_path = split_dir / "ids_test.csv"
    if train_path.exists() and val_path.exists() and test_path.exists():
        return (
            pd.read_csv(train_path)["participant_id"].astype(str).tolist(),
            pd.read_csv(val_path)["participant_id"].astype(str).tolist(),
            pd.read_csv(test_path)["participant_id"].astype(str).tolist(),
            "reused",
        )

    strat = y if y.value_counts().min() >= 2 else None
    idx = np.arange(len(ids))
    idx_tv, idx_test = train_test_split(
        idx,
        test_size=0.15,
        random_state=RANDOM_STATE,
        stratify=(strat.values if strat is not None else None),
    )
    strat_tv = y.iloc[idx_tv]
    strat_tv = strat_tv if strat_tv.value_counts().min() >= 2 else None
    idx_train, idx_val = train_test_split(
        idx_tv,
        test_size=0.1764706,
        random_state=RANDOM_STATE,
        stratify=(strat_tv.values if strat_tv is not None else None),
    )
    ids_train = ids.iloc[idx_train].astype(str).tolist()
    ids_val = ids.iloc[idx_val].astype(str).tolist()
    ids_test = ids.iloc[idx_test].astype(str).tolist()
    safe_csv(pd.DataFrame({"participant_id": ids_train}), train_path)
    safe_csv(pd.DataFrame({"participant_id": ids_val}), val_path)
    safe_csv(pd.DataFrame({"participant_id": ids_test}), test_path)
    return ids_train, ids_val, ids_test, "created"


def split_by_ids(df: pd.DataFrame, ids_train: List[str], ids_val: List[str], ids_test: List[str]) -> Dict[str, pd.DataFrame]:
    dfx = df.copy()
    dfx["participant_id"] = dfx["participant_id"].astype(str)
    return {
        "train": dfx[dfx["participant_id"].isin(ids_train)].copy(),
        "val": dfx[dfx["participant_id"].isin(ids_val)].copy(),
        "test": dfx[dfx["participant_id"].isin(ids_test)].copy(),
    }


def get_feature_names(pipe: Pipeline) -> List[str]:
    pre = pipe.named_steps["preprocessor"]
    try:
        return list(pre.get_feature_names_out())
    except Exception:
        return [f"f_{i}" for i in range(pipe.named_steps["model"].n_features_in_)]


def threshold_sweep(
    y_val: np.ndarray,
    val_prob: np.ndarray,
    recall_floor: float = 0.60,
    bal_tol: float = 0.05,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    thresholds = np.unique(np.concatenate([np.linspace(0.05, 0.95, 19), np.array([0.5])]))
    rows: List[Dict[str, Any]] = []
    for thr in thresholds:
        m = binary_metrics(y_val, val_prob, float(thr))
        m["method"] = "grid"
        rows.append(m)
    df = pd.DataFrame(rows)
    fpr, tpr, thr_roc = roc_curve(y_val, val_prob)
    youden_idx = int(np.argmax(tpr - fpr))
    youden_thr = float(np.clip(thr_roc[youden_idx], 0.0, 1.0))
    best_f1_thr = float(df.sort_values(["f1", "balanced_accuracy"], ascending=False).iloc[0]["threshold"])
    sens_df = df[df["recall"] >= 0.85]
    sensitivity_thr = float(sens_df.sort_values(["precision", "balanced_accuracy"], ascending=False).iloc[0]["threshold"]) if len(sens_df) else 0.5
    base_bal = float(df.loc[np.isclose(df["threshold"], 0.5), "balanced_accuracy"].iloc[0])
    constrained = df[(df["recall"] >= recall_floor) & (df["balanced_accuracy"] >= (base_bal - bal_tol))]
    precision_thr = float(constrained.sort_values(["precision", "balanced_accuracy"], ascending=False).iloc[0]["threshold"]) if len(constrained) else best_f1_thr

    methods = [
        ("default_0_5", 0.5),
        ("youden_j", youden_thr),
        ("best_f1", best_f1_thr),
        ("sensitivity_priority", sensitivity_thr),
        ("precision_constrained", precision_thr),
    ]
    method_rows: List[Dict[str, Any]] = []
    for name, thr in methods:
        m = binary_metrics(y_val, val_prob, float(thr))
        m["method"] = name
        m["recall_floor"] = recall_floor
        m["balanced_accuracy_tolerance"] = bal_tol
        method_rows.append(m)
    method_df = pd.DataFrame(method_rows)
    preferred = method_df[method_df["method"] == "precision_constrained"].iloc[0].to_dict()
    return pd.concat([df, method_df], ignore_index=True), preferred


def fit_calibrators(
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> Tuple[Any, pd.DataFrame]:
    rows: List[Dict[str, Any]] = []
    base_prob = pipeline.predict_proba(X_val)[:, 1]
    best_model: Any = pipeline
    best_method = "none"
    best_score = float(brier_score_loss(y_val, base_prob))
    rows.append({"method": "none", "brier_score_val": best_score, "status": "ok"})

    for method in ("sigmoid", "isotonic"):
        try:
            cal = CalibratedClassifierCV(estimator=pipeline, method=method, cv=3)
            cal.fit(X_train, y_train)
            prob = cal.predict_proba(X_val)[:, 1]
            brier = float(brier_score_loss(y_val, prob))
            rows.append({"method": method, "brier_score_val": brier, "status": "ok"})
            if brier < best_score:
                best_score = brier
                best_model = cal
                best_method = method
        except Exception as exc:
            rows.append({"method": method, "brier_score_val": float("nan"), "status": f"failed:{exc.__class__.__name__}"})

    out = pd.DataFrame(rows)
    out["selected"] = out["method"] == best_method
    return best_model, out


def model_tasks(root: Path) -> List[DatasetTask]:
    strict_path = root / "data" / "processed_hybrid_dsm5_v2" / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv"
    research_path = root / "data" / "processed_hybrid_dsm5_v2" / "final" / "model_ready" / "research_extended_hybrid" / "dataset_hybrid_model_ready_research_extended_hybrid.csv"
    tasks: List[DatasetTask] = []
    compact_priority = {"conduct", "elimination", "depression"}
    for domain, target in DOMAIN_TARGETS.items():
        tasks.append(DatasetTask(f"domain_{domain}_strict_full", "binary_domain", "strict_no_leakage_hybrid", "full", strict_path, target))
        if domain in compact_priority:
            tasks.append(DatasetTask(f"domain_{domain}_strict_compact", "binary_domain", "strict_no_leakage_hybrid", "compact", root / "data" / "processed_hybrid_dsm5_v2" / "final" / "external_domains" / f"dataset_domain_{domain}.csv", target))
        tasks.append(DatasetTask(f"domain_{domain}_research_full", "binary_domain", "research_extended_hybrid", "full", research_path, target))

    decisions_path = root / "data" / "processed_hybrid_dsm5_v2" / "modelability_audit" / "tables" / "final_modelability_decisions.csv"
    if decisions_path.exists():
        dec = pd.read_csv(decisions_path)
        allowed = set(dec[dec["decision_class"].isin(["trainable_high_rigor", "trainable_moderate_rigor", "experimental_only"])]["unit_key"].astype(str).tolist())
    else:
        allowed = {"adhd"}
    for unit, target in INTERNAL_TARGETS.items():
        if unit in allowed:
            tasks.append(DatasetTask(f"internal_{unit}_strict_compact", "binary_internal", "strict_no_leakage_hybrid", "internal_compact", root / "data" / "processed_hybrid_dsm5_v2" / "final" / "internal_exact" / f"dataset_{unit}_exact.csv", target))

    tasks.append(DatasetTask("multilabel_domain_strict", "multilabel_domain", "strict_no_leakage_hybrid", "multilabel", strict_path))
    return [t for t in tasks if t.dataset_path.exists()]


def run() -> None:
    parser = argparse.ArgumentParser(description="Train Random Forest models on hybrid DSM5 v2 datasets.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)
    root = Path(args.root).resolve()

    out_models = root / "models" / "hybrid_dsm5_v2"
    out_artifacts = root / "artifacts" / "hybrid_dsm5_v2" / "models"
    history_dir = root / "reports" / "training_history"
    metrics_dir = root / "reports" / "metrics_hybrid_v2"
    modes_dir = root / "reports" / "operating_modes"
    for d in [out_models, out_artifacts, history_dir, metrics_dir, modes_dir]:
        d.mkdir(parents=True, exist_ok=True)

    tasks = model_tasks(root)
    LOGGER.info("Hybrid RF tasks discovered: %d", len(tasks))

    trial_rows: List[Dict[str, Any]] = []
    fold_rows: List[Dict[str, Any]] = []
    search_rows: List[Dict[str, Any]] = []
    n_estimators_rows: List[Dict[str, Any]] = []
    learning_rows: List[Dict[str, Any]] = []
    threshold_rows: List[Dict[str, Any]] = []
    calibration_rows: List[Dict[str, Any]] = []
    model_comp_rows: List[Dict[str, Any]] = []
    feature_imp_rows: List[Dict[str, Any]] = []
    perm_imp_rows: List[Dict[str, Any]] = []
    mode_rows: List[Dict[str, Any]] = []

    for idx, task in enumerate(tasks, start=1):
        LOGGER.info("[%d/%d] %s", idx, len(tasks), task.task_name)
        model_dir = out_models / task.task_name
        artifact_dir = out_artifacts / task.task_name
        model_dir.mkdir(parents=True, exist_ok=True)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        df = pd.read_csv(task.dataset_path, low_memory=False)
        if "participant_id" not in df.columns:
            LOGGER.warning("Skipping %s because participant_id is missing", task.task_name)
            continue
        df["participant_id"] = df["participant_id"].astype(str)

        if task.task_kind == "multilabel_domain":
            X, y, removed_cols = sanitize_multilabel_features(df)
            label_pattern = y.astype(str).agg("".join, axis=1)
            strat = label_pattern if label_pattern.value_counts().min() >= 2 else None
            split_dir = root / "data" / "processed_hybrid_dsm5_v2" / "splits" / task.task_name
            split_dir.mkdir(parents=True, exist_ok=True)
            train_p, val_p, test_p = split_dir / "ids_train.csv", split_dir / "ids_val.csv", split_dir / "ids_test.csv"
            if train_p.exists() and val_p.exists() and test_p.exists():
                ids_train = pd.read_csv(train_p)["participant_id"].astype(str).tolist()
                ids_val = pd.read_csv(val_p)["participant_id"].astype(str).tolist()
                ids_test = pd.read_csv(test_p)["participant_id"].astype(str).tolist()
                split_source = "reused"
            else:
                idx_all = np.arange(len(df))
                idx_tv, idx_test = train_test_split(idx_all, test_size=0.15, random_state=RANDOM_STATE, stratify=(strat.values if strat is not None else None))
                strat_tv = label_pattern.iloc[idx_tv]
                strat_tv = strat_tv if strat_tv.value_counts().min() >= 2 else None
                idx_train, idx_val = train_test_split(idx_tv, test_size=0.1764706, random_state=RANDOM_STATE, stratify=(strat_tv.values if strat_tv is not None else None))
                ids_train = df.iloc[idx_train]["participant_id"].astype(str).tolist()
                ids_val = df.iloc[idx_val]["participant_id"].astype(str).tolist()
                ids_test = df.iloc[idx_test]["participant_id"].astype(str).tolist()
                safe_csv(pd.DataFrame({"participant_id": ids_train}), train_p)
                safe_csv(pd.DataFrame({"participant_id": ids_val}), val_p)
                safe_csv(pd.DataFrame({"participant_id": ids_test}), test_p)
                split_source = "created"

            feature_cols = X.columns.tolist()
            target_cols = list(DOMAIN_TARGETS.values())
            clean_df = pd.concat([df[["participant_id"]].reset_index(drop=True), X.reset_index(drop=True), y.reset_index(drop=True)], axis=1)
            splits = split_by_ids(clean_df, ids_train, ids_val, ids_test)
            X_train = splits["train"][feature_cols].copy()
            X_val = splits["val"][feature_cols].copy()
            X_test = splits["test"][feature_cols].copy()
            y_train = splits["train"][target_cols].copy()
            y_val = splits["val"][target_cols].copy()
            y_test = splits["test"][target_cols].copy()

            base_pipe = create_pipeline(
                X_train,
                params={
                    "n_estimators": 300,
                    "max_depth": None,
                    "min_samples_split": 2,
                    "min_samples_leaf": 1,
                    "class_weight": "balanced_subsample",
                    "max_features": "sqrt",
                },
            )
            model = MultiOutputClassifier(base_pipe.named_steps["model"])
            pre = base_pipe.named_steps["preprocessor"]
            X_train_enc = pre.fit_transform(X_train)
            X_test_enc = pre.transform(X_test)
            model.fit(X_train_enc, y_train)

            test_prob = np.column_stack([est.predict_proba(X_test_enc)[:, 1] for est in model.estimators_])
            test_pred = (test_prob >= 0.5).astype(int)
            p_micro, r_micro, f_micro, _ = precision_recall_fscore_support(y_test.values, test_pred, average="micro", zero_division=0)
            p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(y_test.values, test_pred, average="macro", zero_division=0)
            p_weight, _, f_weight, _ = precision_recall_fscore_support(y_test.values, test_pred, average="weighted", zero_division=0)
            summary = {
                "model_id": task.task_name,
                "task_kind": task.task_kind,
                "scope": task.scope,
                "dataset_variant": task.dataset_variant,
                "split_source": split_source,
                "n_rows": int(len(df)),
                "n_features": int(X.shape[1]),
                "subset_accuracy": float((test_pred == y_test.values).all(axis=1).mean()),
                "hamming_loss": float(hamming_loss(y_test.values, test_pred)),
                "micro_precision": float(p_micro),
                "micro_recall": float(r_micro),
                "micro_f1": float(f_micro),
                "macro_precision": float(p_macro),
                "macro_recall": float(r_macro),
                "macro_f1": float(f_macro),
                "weighted_f1": float(f_weight),
            }
            safe_json(summary, model_dir / "metrics_summary.json")
            safe_csv(
                pd.DataFrame(
                    [
                        {
                            "label": lbl,
                            "precision": float(precision_score(y_test[lbl], test_pred[:, i], zero_division=0)),
                            "recall": float(recall_score(y_test[lbl], test_pred[:, i], zero_division=0)),
                            "f1": float(f1_score(y_test[lbl], test_pred[:, i], zero_division=0)),
                            "roc_auc": float(roc_auc_score(y_test[lbl], test_prob[:, i])) if len(np.unique(y_test[lbl])) > 1 else float("nan"),
                            "pr_auc": float(average_precision_score(y_test[lbl], test_prob[:, i])) if len(np.unique(y_test[lbl])) > 1 else float("nan"),
                        }
                        for i, lbl in enumerate(DOMAIN_TARGETS.values())
                    ]
                ),
                model_dir / "per_label_metrics.csv",
            )
            joblib.dump({"preprocessor": pre, "model": model, "labels": list(DOMAIN_TARGETS.values())}, artifact_dir / "model.joblib")
            trial_rows.append(
                {
                    "trial_id": task.task_name,
                    "task_kind": task.task_kind,
                    "scope": task.scope,
                    "dataset_variant": task.dataset_variant,
                    "target": "multilabel_domains",
                    "status": "completed",
                    "started_at_utc": now_iso(),
                    "finished_at_utc": now_iso(),
                    "n_train": int(len(X_train)),
                    "n_val": int(len(X_val)),
                    "n_test": int(len(X_test)),
                    "n_features": int(X.shape[1]),
                    "split_source": split_source,
                    "removed_columns": ";".join(removed_cols),
                }
            )
            model_comp_rows.append(summary)
            continue

        target_col = task.target_column
        if target_col is None or target_col not in df.columns:
            LOGGER.warning("Skipping %s because target is missing (%s)", task.task_name, target_col)
            continue

        X, y, removed_cols = sanitize_binary_features(df, target_col)
        split_dir = root / "data" / "processed_hybrid_dsm5_v2" / "splits" / task.task_name
        ids_train, ids_val, ids_test, split_source = get_split_ids(df["participant_id"], y, split_dir)
        feature_cols = X.columns.tolist()
        clean_df = pd.concat(
            [
                df[["participant_id"]].reset_index(drop=True),
                X.reset_index(drop=True),
                y.rename(target_col).reset_index(drop=True),
            ],
            axis=1,
        )
        splits = split_by_ids(clean_df, ids_train, ids_val, ids_test)
        X_train = splits["train"][feature_cols].copy()
        X_val = splits["val"][feature_cols].copy()
        X_test = splits["test"][feature_cols].copy()
        y_train = pd.to_numeric(splits["train"][target_col], errors="coerce").fillna(0).astype(int)
        y_val = pd.to_numeric(splits["val"][target_col], errors="coerce").fillna(0).astype(int)
        y_test = pd.to_numeric(splits["test"][target_col], errors="coerce").fillna(0).astype(int)

        param_dist = {
            "model__n_estimators": [120, 180, 260, 360, 450],
            "model__max_depth": [None, 10, 16, 24],
            "model__min_samples_split": [2, 4, 8, 12],
            "model__min_samples_leaf": [1, 2, 4, 6],
            "model__max_features": ["sqrt", "log2", None],
            "model__class_weight": [None, "balanced", "balanced_subsample"],
            "model__bootstrap": [True, False],
        }
        base_pipe = create_pipeline(X_train)
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
        search = RandomizedSearchCV(
            base_pipe,
            param_distributions=param_dist,
            n_iter=6,
            scoring="balanced_accuracy",
            n_jobs=-1,
            cv=cv,
            random_state=RANDOM_STATE,
            refit=True,
            return_train_score=False,
        )
        started = now_iso()
        search.fit(X_train, y_train)
        finished = now_iso()

        best_pipe: Pipeline = search.best_estimator_
        best_params = search.best_params_
        cv_results = pd.DataFrame(search.cv_results_).sort_values("rank_test_score")
        for _, row in cv_results.iterrows():
            search_rows.append(
                {
                    "trial_id": task.task_name,
                    "candidate_rank": int(row["rank_test_score"]),
                    "mean_balanced_accuracy_cv": float(row["mean_test_score"]),
                    "std_balanced_accuracy_cv": float(row["std_test_score"]),
                    "params_json": json.dumps(row["params"]),
                }
            )
            for i_fold in range(cv.get_n_splits()):
                key = f"split{i_fold}_test_score"
                if key in row:
                    fold_rows.append(
                        {
                            "trial_id": task.task_name,
                            "candidate_rank": int(row["rank_test_score"]),
                            "fold_index": int(i_fold),
                            "balanced_accuracy": float(row[key]),
                        }
                    )

        scorer, calib_df = fit_calibrators(best_pipe, X_train, y_train, X_val, y_val)
        calib_df.insert(0, "trial_id", task.task_name)
        for r in calib_df.to_dict(orient="records"):
            calibration_rows.append(r)

        val_prob = scorer.predict_proba(X_val)[:, 1]
        test_prob = scorer.predict_proba(X_test)[:, 1]
        sweep_df, preferred = threshold_sweep(y_val.to_numpy(), val_prob, recall_floor=0.60, bal_tol=0.05)
        sweep_df.insert(0, "trial_id", task.task_name)
        for r in sweep_df.to_dict(orient="records"):
            threshold_rows.append(r)

        threshold = float(preferred["threshold"])
        val_m = binary_metrics(y_val.to_numpy(), val_prob, threshold)
        test_m = binary_metrics(y_test.to_numpy(), test_prob, threshold)

        best_model_params = {k.replace("model__", ""): v for k, v in best_params.items() if k.startswith("model__")}
        for n_est in [80, 160, 320, 500]:
            sweep_params = dict(best_model_params)
            sweep_params["n_estimators"] = n_est
            p_n = create_pipeline(X_train, params=sweep_params)
            p_n.fit(X_train, y_train)
            vm = binary_metrics(y_val.to_numpy(), p_n.predict_proba(X_val)[:, 1], 0.5)
            tm = binary_metrics(y_test.to_numpy(), p_n.predict_proba(X_test)[:, 1], 0.5)
            n_estimators_rows.append(
                {
                    "trial_id": task.task_name,
                    "n_estimators": int(n_est),
                    "balanced_accuracy_val": vm["balanced_accuracy"],
                    "balanced_accuracy_test": tm["balanced_accuracy"],
                    "precision_val": vm["precision"],
                    "precision_test": tm["precision"],
                    "recall_val": vm["recall"],
                    "recall_test": tm["recall"],
                }
            )

        train_index = np.arange(len(X_train))
        for frac in [0.3, 0.6, 1.0]:
            if frac >= 0.999:
                sub_idx = train_index
            else:
                sub_size = max(40, int(len(train_index) * frac))
                sub_idx = train_test_split(
                    train_index,
                    train_size=sub_size,
                    random_state=RANDOM_STATE,
                    stratify=(y_train if y_train.value_counts().min() >= 2 else None),
                )[0]
            X_sub, y_sub = X_train.iloc[sub_idx], y_train.iloc[sub_idx]
            p_lc = create_pipeline(X_sub, params=best_model_params)
            p_lc.fit(X_sub, y_sub)
            m_lc = binary_metrics(y_val.to_numpy(), p_lc.predict_proba(X_val)[:, 1], 0.5)
            learning_rows.append(
                {
                    "trial_id": task.task_name,
                    "train_fraction": frac,
                    "train_rows": int(len(X_sub)),
                    "balanced_accuracy_val": m_lc["balanced_accuracy"],
                    "precision_val": m_lc["precision"],
                    "recall_val": m_lc["recall"],
                    "pr_auc_val": m_lc["pr_auc"],
                }
            )

        feat_names = get_feature_names(best_pipe)
        importances = best_pipe.named_steps["model"].feature_importances_
        top_idx = np.argsort(importances)[::-1][:30]
        for rank, i_top in enumerate(top_idx, start=1):
            feature_imp_rows.append(
                {
                    "trial_id": task.task_name,
                    "feature_rank": rank,
                    "feature_name": feat_names[i_top] if i_top < len(feat_names) else f"f_{i_top}",
                    "importance_gini": float(importances[i_top]),
                }
            )
        try:
            perm = permutation_importance(best_pipe, X_val, y_val, n_repeats=5, random_state=RANDOM_STATE, n_jobs=-1)
            p_idx = np.argsort(perm.importances_mean)[::-1][:30]
            for rank, i_top in enumerate(p_idx, start=1):
                perm_imp_rows.append(
                    {
                        "trial_id": task.task_name,
                        "feature_rank": rank,
                        "feature_name": feat_names[i_top] if i_top < len(feat_names) else f"f_{i_top}",
                        "importance_permutation_mean": float(perm.importances_mean[i_top]),
                        "importance_permutation_std": float(perm.importances_std[i_top]),
                    }
                )
        except Exception as exc:
            perm_imp_rows.append(
                {
                    "trial_id": task.task_name,
                    "feature_rank": 0,
                    "feature_name": "permutation_importance_failed",
                    "importance_permutation_mean": float("nan"),
                    "importance_permutation_std": float("nan"),
                    "error": exc.__class__.__name__,
                }
            )

        model_meta = {
            "trial_id": task.task_name,
            "task_kind": task.task_kind,
            "scope": task.scope,
            "dataset_variant": task.dataset_variant,
            "target_column": target_col,
            "dataset_path": str(task.dataset_path),
            "split_source": split_source,
            "best_params": best_params,
            "threshold_recommended": threshold,
            "threshold_method": preferred.get("method", "precision_constrained"),
            "metrics_val": val_m,
            "metrics_test": test_m,
            "started_at_utc": started,
            "finished_at_utc": finished,
            "removed_columns": removed_cols,
        }
        safe_json(model_meta, model_dir / "model_metadata.json")
        safe_csv(calib_df, model_dir / "calibration_summary.csv")
        safe_csv(sweep_df, model_dir / "threshold_sweep.csv")
        safe_csv(pd.DataFrame([val_m]), model_dir / "metrics_val.csv")
        safe_csv(pd.DataFrame([test_m]), model_dir / "metrics_test.csv")
        joblib.dump({"model": scorer, "feature_columns": list(X.columns), "target": target_col}, artifact_dir / "model.joblib")

        for mode, thr in [("sensitive", max(0.20, threshold - 0.15)), ("precise", min(0.90, threshold + 0.10)), ("abstention_assisted", threshold)]:
            mm = binary_metrics(y_test.to_numpy(), test_prob, thr)
            mode_rows.append(
                {
                    "trial_id": task.task_name,
                    "mode": mode,
                    "threshold": float(thr),
                    "precision_test": mm["precision"],
                    "recall_test": mm["recall"],
                    "specificity_test": mm["specificity"],
                    "balanced_accuracy_test": mm["balanced_accuracy"],
                }
            )

        model_comp_rows.append(
            {
                "model_id": task.task_name,
                "task_kind": task.task_kind,
                "scope": task.scope,
                "dataset_variant": task.dataset_variant,
                "target": target_col,
                "n_rows": int(len(df)),
                "n_features": int(X.shape[1]),
                "split_source": split_source,
                "best_params_json": json.dumps(best_params),
                "threshold_recommended": threshold,
                "precision_val": val_m["precision"],
                "precision_test": test_m["precision"],
                "recall_val": val_m["recall"],
                "recall_test": test_m["recall"],
                "specificity_test": test_m["specificity"],
                "balanced_accuracy_val": val_m["balanced_accuracy"],
                "balanced_accuracy_test": test_m["balanced_accuracy"],
                "f1_test": test_m["f1"],
                "roc_auc_test": test_m["roc_auc"],
                "pr_auc_test": test_m["pr_auc"],
                "brier_score_test": test_m["brier_score"],
                "fp_test": test_m["fp"],
                "fn_test": test_m["fn"],
            }
        )

        trial_rows.append(
            {
                "trial_id": task.task_name,
                "task_kind": task.task_kind,
                "scope": task.scope,
                "dataset_variant": task.dataset_variant,
                "target": target_col,
                "status": "completed",
                "started_at_utc": started,
                "finished_at_utc": finished,
                "n_train": int(len(X_train)),
                "n_val": int(len(X_val)),
                "n_test": int(len(X_test)),
                "n_features": int(X.shape[1]),
                "split_source": split_source,
                "removed_columns": ";".join(removed_cols),
            }
        )

    safe_csv(pd.DataFrame(trial_rows), history_dir / "trial_registry.csv")
    safe_csv(pd.DataFrame(fold_rows), history_dir / "fold_metrics_history.csv")
    safe_csv(pd.DataFrame(search_rows), history_dir / "hyperparameter_search_history.csv")
    safe_csv(pd.DataFrame(n_estimators_rows), history_dir / "n_estimators_curve.csv")
    safe_csv(pd.DataFrame(learning_rows), history_dir / "learning_curve_history.csv")
    safe_csv(pd.DataFrame(threshold_rows), history_dir / "threshold_sweep_history.csv")
    safe_csv(pd.DataFrame(calibration_rows), history_dir / "calibration_history.csv")
    safe_csv(pd.DataFrame(model_comp_rows), history_dir / "model_comparison_history.csv")
    safe_csv(pd.DataFrame(feature_imp_rows), history_dir / "feature_importance_history.csv")
    safe_csv(pd.DataFrame(perm_imp_rows), history_dir / "permutation_importance_history.csv")

    comp_df = pd.DataFrame(model_comp_rows)
    if not comp_df.empty:
        safe_csv(comp_df.sort_values(["task_kind", "balanced_accuracy_test", "precision_test"], ascending=[True, False, False]), metrics_dir / "model_results_summary.csv")
        safe_csv(comp_df[comp_df["task_kind"] == "binary_domain"], metrics_dir / "domain_results_summary.csv")
        safe_csv(comp_df[comp_df["task_kind"] == "binary_internal"], metrics_dir / "internal_results_summary.csv")
        safe_csv(comp_df[comp_df["task_kind"] == "multilabel_domain"], metrics_dir / "multilabel_results_summary.csv")
    safe_csv(pd.DataFrame(mode_rows), modes_dir / "operating_modes_comparison.csv")

    rec_lines = [
        "# Hybrid RF Training Summary",
        "",
        f"- generated_at_utc: {now_iso()}",
        f"- trials_completed: {len(trial_rows)}",
        f"- model_comparisons: {len(model_comp_rows)}",
        "",
        "Top models by task:",
    ]
    if comp_df.empty:
        rec_lines.append("- No models trained.")
    else:
        for kind in sorted(comp_df["task_kind"].unique()):
            top = comp_df[comp_df["task_kind"] == kind].sort_values(["balanced_accuracy_test", "precision_test"], ascending=False).head(3)
            for _, row in top.iterrows():
                rec_lines.append(
                    f"- {kind}: {row['model_id']} | target={row.get('target','')} | bal_acc_test={row.get('balanced_accuracy_test', float('nan')):.4f} | precision_test={row.get('precision_test', float('nan')):.4f}"
                )
    safe_text("\n".join(rec_lines) + "\n", metrics_dir / "training_summary.md")


if __name__ == "__main__":
    run()
