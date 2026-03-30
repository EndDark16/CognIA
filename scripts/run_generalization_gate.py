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
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


LOGGER = logging.getLogger("generalization-gate-v1")
RANDOM_STATE = 42

DOMAIN_TARGETS = {
    "adhd": "target_domain_adhd",
    "conduct": "target_domain_conduct",
    "elimination": "target_domain_elimination",
    "anxiety": "target_domain_anxiety",
    "depression": "target_domain_depression",
}


@dataclass
class Paths:
    root: Path
    hybrid: Path
    gate: Path
    inventory: Path
    diagnostics: Path
    stress: Path
    retrained: Path
    reports: Path
    tables: Path
    artifacts: Path


@dataclass
class DomainModel:
    domain: str
    model_id: str
    target_col: str
    dataset_path: Path
    scope: str
    model_path: Path
    metadata_path: Path


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


def metric_binary(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> Dict[str, Any]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    return {
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
    }


def sanitize_features(df: pd.DataFrame, target_col: str) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    y = pd.to_numeric(df[target_col], errors="coerce").fillna(0).astype(int)
    drops: List[str] = []
    for c in df.columns:
        low = c.lower()
        if c == "participant_id" or c == target_col:
            drops.append(c)
            continue
        if c.startswith("target_"):
            drops.append(c)
            continue
        if low.endswith("_status") or low.endswith("_confidence") or low.endswith("_coverage"):
            drops.append(c)
            continue
        if "diagnosis" in low or "consensus" in low or "ksads" in low:
            drops.append(c)
            continue
    X = df.drop(columns=drops, errors="ignore").copy()
    extra = [c for c in X.columns if X[c].notna().sum() == 0 or X[c].nunique(dropna=True) <= 1]
    extra += [c for c in X.columns if X[c].notna().mean() < 0.02]
    if extra:
        X = X.drop(columns=sorted(set(extra)), errors="ignore")
    if X.shape[1] > 600:
        keep = X.notna().mean().sort_values(ascending=False).head(600).index.tolist()
        trim = [c for c in X.columns if c not in keep]
        X = X[keep].copy()
        extra += trim
    return X, y, sorted(set(drops + extra))


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    num_cols = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    cat_cols = [c for c in X.columns if c not in num_cols]
    return ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num_cols),
            (
                "cat",
                Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("ohe", OneHotEncoder(handle_unknown="ignore"))]),
                cat_cols,
            ),
        ],
        remainder="drop",
    )


def build_pipeline(X: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> Pipeline:
    model = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=1)
    if params:
        model.set_params(**params)
    return Pipeline([("preprocessor", build_preprocessor(X)), ("model", model)])


def parse_best_params(meta: Dict[str, Any]) -> Dict[str, Any]:
    params = meta.get("best_params", {}) if isinstance(meta, dict) else {}
    out: Dict[str, Any] = {}
    for k, v in params.items():
        if k.startswith("model__"):
            out[k.replace("model__", "")] = v
        else:
            out[k] = v
    return out


def force_single_thread(model: Any) -> None:
    try:
        if hasattr(model, "n_jobs"):
            setattr(model, "n_jobs", 1)
    except Exception:
        pass
    if isinstance(model, Pipeline):
        for step in model.named_steps.values():
            force_single_thread(step)
    if hasattr(model, "estimator"):
        force_single_thread(getattr(model, "estimator"))
    if hasattr(model, "base_estimator"):
        force_single_thread(getattr(model, "base_estimator"))
    if hasattr(model, "estimators_"):
        try:
            for est in getattr(model, "estimators_"):
                force_single_thread(est)
        except Exception:
            pass
    if hasattr(model, "calibrated_classifiers_"):
        try:
            for cal in getattr(model, "calibrated_classifiers_"):
                if hasattr(cal, "estimator"):
                    force_single_thread(cal.estimator)
        except Exception:
            pass


def split_ids(ids: pd.Series, y: pd.Series, split_seed: int) -> Tuple[List[str], List[str], List[str]]:
    strat = y if y.value_counts().min() >= 2 else None
    idx = np.arange(len(ids))
    idx_tv, idx_test = train_test_split(
        idx,
        test_size=0.15,
        random_state=split_seed,
        stratify=(strat.values if strat is not None else None),
    )
    strat_tv = y.iloc[idx_tv]
    strat_tv = strat_tv if strat_tv.value_counts().min() >= 2 else None
    idx_train, idx_val = train_test_split(
        idx_tv,
        test_size=0.1764706,
        random_state=split_seed,
        stratify=(strat_tv.values if strat_tv is not None else None),
    )
    return (
        ids.iloc[idx_train].astype(str).tolist(),
        ids.iloc[idx_val].astype(str).tolist(),
        ids.iloc[idx_test].astype(str).tolist(),
    )


def subset_by_ids(df: pd.DataFrame, ids: List[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(ids)].copy()


def choose_threshold(y_val: np.ndarray, prob_val: np.ndarray) -> float:
    best_thr = 0.5
    best_score = -1.0
    for thr in np.linspace(0.05, 0.95, 19):
        m = metric_binary(y_val, prob_val, float(thr))
        score = 0.6 * m["precision"] + 0.4 * m["balanced_accuracy"]
        if m["recall"] >= 0.60 and score > best_score:
            best_score = score
            best_thr = float(thr)
    return best_thr


def noise_apply(X: pd.DataFrame, level: int, rng: np.random.Generator) -> pd.DataFrame:
    Xn = X.copy()
    q_cols = [c for c in Xn.columns if c.startswith("q_")]
    cols = q_cols if q_cols else Xn.columns.tolist()
    if not cols:
        return Xn

    if level == 0:
        return Xn
    miss_ratio = {1: 0.05, 2: 0.15, 3: 0.30}[level]
    n_rows = len(Xn)
    n_cols = len(cols)
    n_mask = int(n_rows * n_cols * miss_ratio)
    if n_mask > 0:
        ridx = rng.integers(0, n_rows, size=n_mask)
        cidx = rng.integers(0, n_cols, size=n_mask)
        for r, c in zip(ridx, cidx):
            Xn.iat[r, Xn.columns.get_loc(cols[c])] = np.nan

    if level >= 2:
        num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(Xn[c])]
        for c in num_cols:
            mask = rng.random(n_rows) < (0.10 if level == 2 else 0.20)
            jitter = rng.integers(-1, 2, size=n_rows)
            Xn.loc[mask, c] = pd.to_numeric(Xn.loc[mask, c], errors="coerce") + jitter[mask]

    if level == 3:
        bool_cols = [c for c in cols if pd.api.types.is_bool_dtype(Xn[c]) or set(pd.to_numeric(Xn[c], errors="coerce").dropna().unique()).issubset({0, 1})]
        for c in bool_cols[:40]:
            mask = rng.random(n_rows) < 0.10
            cur = pd.to_numeric(Xn[c], errors="coerce")
            Xn.loc[mask, c] = 1 - cur.loc[mask]
    return Xn


def realism_apply(X: pd.DataFrame, scenario: str, rng: np.random.Generator) -> pd.DataFrame:
    Xr = X.copy()
    q_cols = [c for c in Xr.columns if c.startswith("q_")]
    if scenario == "incomplete_inputs":
        keep = int(max(1, len(q_cols) * 0.6))
        drop_cols = q_cols[keep:]
        Xr.loc[:, drop_cols] = np.nan
    elif scenario == "contradictory_inputs":
        num_cols = [c for c in q_cols if pd.api.types.is_numeric_dtype(Xr[c])]
        for c in num_cols[:60]:
            mask = rng.random(len(Xr)) < 0.15
            Xr.loc[mask, c] = pd.to_numeric(Xr.loc[mask, c], errors="coerce") * -1
    elif scenario == "mixed_comorbidity_signals":
        num_cols = [c for c in Xr.columns if pd.api.types.is_numeric_dtype(Xr[c])]
        for c in num_cols[:80]:
            mask = rng.random(len(Xr)) < 0.12
            Xr.loc[mask, c] = pd.to_numeric(Xr.loc[mask, c], errors="coerce") + rng.normal(0, 1, size=len(Xr))[mask]
    return Xr


def domain_model_specs(paths: Paths) -> List[DomainModel]:
    best_path = paths.root / "reports" / "comparisons" / "hybrid_domain_best_models.csv"
    if best_path.exists():
        best = pd.read_csv(best_path)
    else:
        comp = pd.read_csv(paths.root / "reports" / "training_history" / "model_comparison_history.csv")
        best_rows = []
        for target, g in comp[comp["task_kind"] == "binary_domain"].groupby("target"):
            best_rows.append(g.sort_values(["balanced_accuracy_test", "precision_test"], ascending=False).iloc[0])
        best = pd.DataFrame(best_rows)
    specs: List[DomainModel] = []
    for _, row in best.iterrows():
        target_col = str(row["target"])
        domain = target_col.replace("target_domain_", "")
        model_id = str(row["model_id"])
        model_dir = paths.root / "models" / "hybrid_dsm5_v2" / model_id
        metadata_path = model_dir / "model_metadata.json"
        if metadata_path.exists():
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            dataset_path = Path(meta.get("dataset_path", ""))
            if not dataset_path.is_absolute():
                dataset_path = (paths.root / dataset_path).resolve()
            scope = str(meta.get("scope", row.get("scope", "")))
        else:
            scope = str(row.get("scope", "strict_no_leakage_hybrid"))
            if scope == "research_extended_hybrid":
                dataset_path = paths.hybrid / "final" / "model_ready" / "research_extended_hybrid" / "dataset_hybrid_model_ready_research_extended_hybrid.csv"
            else:
                dataset_path = paths.hybrid / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv"
        specs.append(
            DomainModel(
                domain=domain,
                model_id=model_id,
                target_col=target_col,
                dataset_path=dataset_path,
                scope=scope,
                model_path=paths.root / "artifacts" / "hybrid_dsm5_v2" / "models" / model_id / "model.joblib",
                metadata_path=metadata_path,
            )
        )
    return specs


@dataclass
class DomainRuntime:
    spec: DomainModel
    df: pd.DataFrame
    X: pd.DataFrame
    y: pd.Series
    removed_cols: List[str]
    ids_train: List[str]
    ids_val: List[str]
    ids_test: List[str]
    threshold_base: float
    params_base: Dict[str, Any]
    base_model: Any
    metrics_train: Dict[str, Any]
    metrics_val: Dict[str, Any]
    metrics_test: Dict[str, Any]
    overfit_class: str


def build_paths(root: Path) -> Paths:
    gate = root / "data" / "generalization_gate_v1"
    return Paths(
        root=root,
        hybrid=root / "data" / "processed_hybrid_dsm5_v2",
        gate=gate,
        inventory=gate / "inventory",
        diagnostics=gate / "diagnostics",
        stress=gate / "stress_tests",
        retrained=gate / "retrained_models",
        reports=gate / "reports",
        tables=gate / "tables",
        artifacts=root / "artifacts" / "generalization_gate_v1",
    )


def ensure_dirs(paths: Paths) -> None:
    for d in [
        paths.gate,
        paths.inventory,
        paths.diagnostics,
        paths.stress,
        paths.retrained,
        paths.reports,
        paths.tables,
        paths.artifacts,
    ]:
        d.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def classify_overfit(
    m_train: Dict[str, Any],
    m_val: Dict[str, Any],
    m_test: Dict[str, Any],
    criteria: Dict[str, float],
) -> str:
    gap_train_val = abs(m_train["balanced_accuracy"] - m_val["balanced_accuracy"])
    gap_val_test = abs(m_val["balanced_accuracy"] - m_test["balanced_accuracy"])
    near_perfect = (
        m_val["balanced_accuracy"] >= 0.995
        and m_test["balanced_accuracy"] >= 0.995
        and m_val["precision"] >= 0.995
        and m_test["precision"] >= 0.995
    )
    if near_perfect:
        return "suspicious_perfect_score"
    if gap_train_val > criteria["acceptable_train_val_gap"] or gap_val_test > criteria["acceptable_val_test_gap"]:
        if gap_train_val > criteria["acceptable_train_val_gap"] * 1.5:
            return "high_risk_overfit"
        return "possible_overfit"
    return "likely_generalizing"


def load_split_or_create(df: pd.DataFrame, target: str, split_dir: Path, split_seed: int) -> Tuple[List[str], List[str], List[str], str]:
    train_p = split_dir / "ids_train.csv"
    val_p = split_dir / "ids_val.csv"
    test_p = split_dir / "ids_test.csv"
    if train_p.exists() and val_p.exists() and test_p.exists():
        return (
            pd.read_csv(train_p)["participant_id"].astype(str).tolist(),
            pd.read_csv(val_p)["participant_id"].astype(str).tolist(),
            pd.read_csv(test_p)["participant_id"].astype(str).tolist(),
            "reused",
        )
    ids_train, ids_val, ids_test = split_ids(df["participant_id"].astype(str), pd.to_numeric(df[target], errors="coerce").fillna(0).astype(int), split_seed)
    return ids_train, ids_val, ids_test, "created"


def generate_input_inventory(paths: Paths, specs: List[DomainModel]) -> pd.DataFrame:
    check_paths = [
        paths.hybrid,
        paths.root / "reports" / "training_history",
        paths.root / "reports" / "operating_modes",
        paths.root / "artifacts" / "inference_v2",
        paths.root / "data" / "questionnaire_dsm5_v1",
        paths.hybrid / "final" / "model_ready" / "strict_no_leakage_hybrid",
        paths.hybrid / "final" / "model_ready" / "research_extended_hybrid",
        paths.hybrid / "modelability_audit",
        paths.hybrid / "feature_lineage_dsm5_exact.csv",
        paths.hybrid / "parameter_lineage_dsm5_exact.csv",
        paths.hybrid / "leakage_audit_dsm5_exact.csv",
    ]
    rows: List[Dict[str, Any]] = []
    for p in check_paths:
        if p.exists():
            rows.append(
                {
                    "path": str(p),
                    "exists": True,
                    "type": "dir" if p.is_dir() else "file",
                    "size_bytes": int(p.stat().st_size) if p.is_file() else None,
                    "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
                }
            )
        else:
            rows.append({"path": str(p), "exists": False, "type": "missing", "size_bytes": None, "modified_utc": None})

    for spec in specs:
        for p in [spec.dataset_path, spec.model_path, spec.metadata_path]:
            rows.append(
                {
                    "path": str(p),
                    "exists": p.exists(),
                    "type": "file",
                    "size_bytes": int(p.stat().st_size) if p.exists() else None,
                    "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat() if p.exists() else None,
                    "domain": spec.domain,
                    "model_id": spec.model_id,
                }
            )
    inv = pd.DataFrame(rows).drop_duplicates(subset=["path"]).sort_values("path")
    safe_csv(inv, paths.inventory / "input_inventory.csv")
    missing_count = int((~inv["exists"]).sum())
    summary = [
        "# Input Summary",
        "",
        f"- generated_at_utc: {now_iso()}",
        f"- total_inputs_checked: {len(inv)}",
        f"- missing_inputs: {missing_count}",
        f"- discovered_domain_models: {len(specs)}",
        "",
        "## Domain Models",
    ]
    for spec in specs:
        summary.append(f"- {spec.domain}: `{spec.model_id}` | scope={spec.scope} | dataset=`{spec.dataset_path}`")
    safe_text("\n".join(summary) + "\n", paths.reports / "input_summary.md")
    return inv


def phase_generalization_criteria(paths: Paths) -> Dict[str, float]:
    criteria = {
        "acceptable_train_val_gap": 0.08,
        "acceptable_val_test_gap": 0.10,
        "acceptable_seed_variability": 0.06,
        "acceptable_split_variability": 0.08,
        "acceptable_threshold_instability": 0.12,
        "acceptable_calibration_drift": 0.05,
        "acceptable_noise_degradation": 0.15,
        "acceptable_domain_shift_degradation": 0.18,
        "recall_floor": 0.60,
        "balanced_accuracy_tolerance": 0.06,
    }
    safe_csv(
        pd.DataFrame([{"metric": k, "threshold": v} for k, v in criteria.items()]),
        paths.tables / "generalization_thresholds.csv",
    )
    md = [
        "# Generalization Criteria",
        "",
        "This gate rejects cosmetics and focuses on stability under perturbation.",
        "",
    ]
    for k, v in criteria.items():
        md.append(f"- {k}: {v}")
    safe_text("\n".join(md) + "\n", paths.reports / "generalization_criteria.md")
    return criteria


def phase_overfit_audit(paths: Paths, specs: List[DomainModel], criteria: Dict[str, float]) -> Tuple[pd.DataFrame, List[DomainRuntime]]:
    rows: List[Dict[str, Any]] = []
    runtimes: List[DomainRuntime] = []

    for spec in specs:
        df = pd.read_csv(spec.dataset_path, low_memory=False)
        if "participant_id" not in df.columns or spec.target_col not in df.columns:
            continue
        df["participant_id"] = df["participant_id"].astype(str)
        payload = None
        if spec.model_path.exists():
            payload = joblib.load(spec.model_path)
        y = pd.to_numeric(df[spec.target_col], errors="coerce").fillna(0).astype(int)

        if isinstance(payload, dict) and "feature_columns" in payload:
            feature_cols = [str(c) for c in payload["feature_columns"]]
            for c in feature_cols:
                if c not in df.columns:
                    df[c] = np.nan
            X = df[feature_cols].copy()
            removed = [c for c in df.columns if c not in (["participant_id", spec.target_col] + feature_cols)]
        else:
            X, y, removed = sanitize_features(df, spec.target_col)
            feature_cols = X.columns.tolist()

        clean = pd.concat([df[["participant_id"]].reset_index(drop=True), X.reset_index(drop=True), y.rename(spec.target_col).reset_index(drop=True)], axis=1)
        split_dir = paths.hybrid / "splits" / spec.model_id
        ids_train, ids_val, ids_test, split_source = load_split_or_create(clean, spec.target_col, split_dir, RANDOM_STATE)

        train_df = subset_by_ids(clean, ids_train)
        val_df = subset_by_ids(clean, ids_val)
        test_df = subset_by_ids(clean, ids_test)
        X_train = train_df[feature_cols].copy()
        y_train = pd.to_numeric(train_df[spec.target_col], errors="coerce").fillna(0).astype(int)
        X_val = val_df[feature_cols].copy()
        y_val = pd.to_numeric(val_df[spec.target_col], errors="coerce").fillna(0).astype(int)
        X_test = test_df[feature_cols].copy()
        y_test = pd.to_numeric(test_df[spec.target_col], errors="coerce").fillna(0).astype(int)

        meta = read_json(spec.metadata_path)
        params = parse_best_params(meta)
        threshold = float(meta.get("threshold_recommended", 0.5))

        if payload is not None:
            model = payload["model"] if isinstance(payload, dict) and "model" in payload else payload
        else:
            model = build_pipeline(X_train, params)
            model.fit(X_train, y_train)
        force_single_thread(model)

        train_prob = model.predict_proba(X_train)[:, 1]
        val_prob = model.predict_proba(X_val)[:, 1]
        test_prob = model.predict_proba(X_test)[:, 1]

        m_train = metric_binary(y_train.to_numpy(), train_prob, threshold)
        m_val = metric_binary(y_val.to_numpy(), val_prob, threshold)
        m_test = metric_binary(y_test.to_numpy(), test_prob, threshold)
        overfit_class = classify_overfit(m_train, m_val, m_test, criteria)
        rows.append(
            {
                "domain": spec.domain,
                "model_id": spec.model_id,
                "scope": spec.scope,
                "target": spec.target_col,
                "split_source": split_source,
                "threshold": threshold,
                "train_balanced_accuracy": m_train["balanced_accuracy"],
                "val_balanced_accuracy": m_val["balanced_accuracy"],
                "test_balanced_accuracy": m_test["balanced_accuracy"],
                "train_precision": m_train["precision"],
                "val_precision": m_val["precision"],
                "test_precision": m_test["precision"],
                "train_recall": m_train["recall"],
                "val_recall": m_val["recall"],
                "test_recall": m_test["recall"],
                "train_val_gap_balanced_accuracy": abs(m_train["balanced_accuracy"] - m_val["balanced_accuracy"]),
                "val_test_gap_balanced_accuracy": abs(m_val["balanced_accuracy"] - m_test["balanced_accuracy"]),
                "prob_overconfidence_share_test": float((test_prob >= 0.95).mean()),
                "suspicious_near_perfect_flag": bool(
                    m_val["balanced_accuracy"] >= 0.995 and m_test["balanced_accuracy"] >= 0.995 and m_test["precision"] >= 0.995
                ),
                "overfit_class": overfit_class,
            }
        )
        runtimes.append(
            DomainRuntime(
                spec=spec,
                df=clean,
                X=clean[feature_cols].copy(),
                y=y,
                removed_cols=removed,
                ids_train=ids_train,
                ids_val=ids_val,
                ids_test=ids_test,
                threshold_base=threshold,
                params_base=params,
                base_model=model,
                metrics_train=m_train,
                metrics_val=m_val,
                metrics_test=m_test,
                overfit_class=overfit_class,
            )
        )

    out = pd.DataFrame(rows).sort_values(["domain", "scope", "model_id"])
    safe_csv(out, paths.tables / "overfit_audit.csv")
    md = [
        "# Overfit Audit Summary",
        "",
        f"- generated_at_utc: {now_iso()}",
        f"- audited_models: {len(out)}",
        "",
        "## Counts by class",
    ]
    if not out.empty:
        for key, val in out["overfit_class"].value_counts().items():
            md.append(f"- {key}: {int(val)}")
    safe_text("\n".join(md) + "\n", paths.reports / "overfit_audit_summary.md")
    return out, runtimes


def leakage_risk_for_feature(col: str, corr: float) -> Tuple[str, str]:
    low = col.lower()
    if col.startswith("target_") or "diagnosis" in low or "consensus" in low or "ksads" in low:
        return "critical", "direct_target_or_diagnostic_field"
    if low.endswith("_status") or low.endswith("_confidence") or low.endswith("_coverage"):
        return "high", "post_target_metadata"
    if "exact_direct_criteria_count" in low or "exact_proxy_criteria_count" in low:
        return "high", "target_equivalent_count_feature"
    if abs(corr) >= 0.95:
        return "high", "extreme_target_correlation"
    if abs(corr) >= 0.80:
        return "medium", "very_high_target_correlation"
    if low.startswith("q_qi_"):
        return "low", "questionnaire_item_requires_monitoring"
    return "none", "no_strong_signal"


def phase_leakage_audit(paths: Paths, runtimes: List[DomainRuntime], overfit_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    f_rows: List[Dict[str, Any]] = []
    m_rows: List[Dict[str, Any]] = []
    risk_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

    for rt in runtimes:
        dom = rt.spec.domain
        target = rt.spec.target_col
        full_df = rt.df
        y = pd.to_numeric(full_df[target], errors="coerce").fillna(0).astype(int).to_numpy()
        domain_risk = 0
        risk_counts = {"none": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}

        for col in full_df.columns:
            if col in ("participant_id", target):
                continue
            series = pd.to_numeric(full_df[col], errors="coerce")
            corr = float("nan")
            if series.notna().sum() > 10 and np.nanstd(series.to_numpy()) > 0:
                corr = float(np.corrcoef(np.nan_to_num(series.to_numpy(), nan=np.nanmedian(series.to_numpy())), y)[0, 1])
                if np.isnan(corr):
                    corr = 0.0
            else:
                corr = 0.0
            risk, reason = leakage_risk_for_feature(col, corr)
            risk_counts[risk] += 1
            domain_risk = max(domain_risk, risk_rank[risk])
            f_rows.append(
                {
                    "domain": dom,
                    "model_id": rt.spec.model_id,
                    "feature": col,
                    "correlation_with_target": corr,
                    "risk_level": risk,
                    "risk_reason": reason,
                }
            )

        if domain_risk >= risk_rank["critical"]:
            model_risk = "critical"
        elif domain_risk >= risk_rank["high"]:
            model_risk = "high"
        elif domain_risk >= risk_rank["medium"]:
            model_risk = "medium"
        elif domain_risk >= risk_rank["low"]:
            model_risk = "low"
        else:
            model_risk = "none"

        overfit_class = overfit_df.loc[overfit_df["model_id"] == rt.spec.model_id, "overfit_class"].iloc[0]
        model_class = "leakage_suspected" if model_risk in ("high", "critical") and overfit_class == "suspicious_perfect_score" else overfit_class
        m_rows.append(
            {
                "domain": dom,
                "model_id": rt.spec.model_id,
                "model_risk_level": model_risk,
                "none_count": risk_counts["none"],
                "low_count": risk_counts["low"],
                "medium_count": risk_counts["medium"],
                "high_count": risk_counts["high"],
                "critical_count": risk_counts["critical"],
                "overfit_class_adjusted": model_class,
                "scope": rt.spec.scope,
            }
        )

    leak_f = pd.DataFrame(f_rows)
    leak_m = pd.DataFrame(m_rows).sort_values(["domain", "model_id"])
    safe_csv(leak_f, paths.tables / "leakage_feature_audit.csv")
    safe_csv(leak_m, paths.tables / "leakage_model_audit.csv")
    md = [
        "# Leakage Gate Report",
        "",
        f"- generated_at_utc: {now_iso()}",
        f"- audited_features: {len(leak_f)}",
        f"- audited_models: {len(leak_m)}",
        "",
        "## Model risk levels",
    ]
    if not leak_m.empty:
        for key, val in leak_m["model_risk_level"].value_counts().items():
            md.append(f"- {key}: {int(val)}")
    safe_text("\n".join(md) + "\n", paths.reports / "leakage_gate_report.md")
    return leak_f, leak_m


def run_seed_split_stability(
    paths: Paths,
    runtimes: List[DomainRuntime],
    criteria: Dict[str, float],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    seed_rows: List[Dict[str, Any]] = []
    split_rows: List[Dict[str, Any]] = []
    threshold_rows: List[Dict[str, Any]] = []
    calibration_rows: List[Dict[str, Any]] = []
    seed_list = [7, 21, 42, 84, 2026]
    split_seeds = [42, 101, 777]

    for rt in runtimes:
        feature_cols = rt.X.columns.tolist()
        train_df = subset_by_ids(rt.df, rt.ids_train)
        val_df = subset_by_ids(rt.df, rt.ids_val)
        test_df = subset_by_ids(rt.df, rt.ids_test)
        X_train = train_df[feature_cols].copy()
        y_train = pd.to_numeric(train_df[rt.spec.target_col], errors="coerce").fillna(0).astype(int)
        X_val = val_df[feature_cols].copy()
        y_val = pd.to_numeric(val_df[rt.spec.target_col], errors="coerce").fillna(0).astype(int)
        X_test = test_df[feature_cols].copy()
        y_test = pd.to_numeric(test_df[rt.spec.target_col], errors="coerce").fillna(0).astype(int)

        for seed in seed_list:
            params = dict(rt.params_base)
            params["random_state"] = seed
            model = build_pipeline(X_train, params)
            model.fit(X_train, y_train)
            force_single_thread(model)
            val_prob = model.predict_proba(X_val)[:, 1]
            test_prob = model.predict_proba(X_test)[:, 1]
            thr = choose_threshold(y_val.to_numpy(), val_prob)
            m_val = metric_binary(y_val.to_numpy(), val_prob, thr)
            m_test = metric_binary(y_test.to_numpy(), test_prob, thr)
            seed_rows.append(
                {
                    "domain": rt.spec.domain,
                    "model_id": rt.spec.model_id,
                    "seed": seed,
                    "threshold": thr,
                    "val_precision": m_val["precision"],
                    "val_balanced_accuracy": m_val["balanced_accuracy"],
                    "val_recall": m_val["recall"],
                    "test_precision": m_test["precision"],
                    "test_balanced_accuracy": m_test["balanced_accuracy"],
                    "test_recall": m_test["recall"],
                }
            )
            threshold_rows.append(
                {
                    "domain": rt.spec.domain,
                    "source": "seed_variation",
                    "seed": seed,
                    "split_seed": RANDOM_STATE,
                    "threshold_selected": thr,
                }
            )

        for split_seed in split_seeds:
            ids_train, ids_val, ids_test = split_ids(rt.df["participant_id"].astype(str), rt.y, split_seed)
            train_df_s = subset_by_ids(rt.df, ids_train)
            val_df_s = subset_by_ids(rt.df, ids_val)
            test_df_s = subset_by_ids(rt.df, ids_test)
            X_train_s = train_df_s[feature_cols].copy()
            y_train_s = pd.to_numeric(train_df_s[rt.spec.target_col], errors="coerce").fillna(0).astype(int)
            X_val_s = val_df_s[feature_cols].copy()
            y_val_s = pd.to_numeric(val_df_s[rt.spec.target_col], errors="coerce").fillna(0).astype(int)
            X_test_s = test_df_s[feature_cols].copy()
            y_test_s = pd.to_numeric(test_df_s[rt.spec.target_col], errors="coerce").fillna(0).astype(int)
            model = build_pipeline(X_train_s, rt.params_base)
            model.fit(X_train_s, y_train_s)
            force_single_thread(model)
            val_prob = model.predict_proba(X_val_s)[:, 1]
            test_prob = model.predict_proba(X_test_s)[:, 1]
            thr = choose_threshold(y_val_s.to_numpy(), val_prob)
            m_val = metric_binary(y_val_s.to_numpy(), val_prob, thr)
            m_test = metric_binary(y_test_s.to_numpy(), test_prob, thr)
            split_rows.append(
                {
                    "domain": rt.spec.domain,
                    "model_id": rt.spec.model_id,
                    "split_seed": split_seed,
                    "threshold": thr,
                    "val_precision": m_val["precision"],
                    "val_balanced_accuracy": m_val["balanced_accuracy"],
                    "val_recall": m_val["recall"],
                    "test_precision": m_test["precision"],
                    "test_balanced_accuracy": m_test["balanced_accuracy"],
                    "test_recall": m_test["recall"],
                }
            )
            threshold_rows.append(
                {
                    "domain": rt.spec.domain,
                    "source": "split_variation",
                    "seed": RANDOM_STATE,
                    "split_seed": split_seed,
                    "threshold_selected": thr,
                }
            )

        base_pipe = build_pipeline(X_train, rt.params_base)
        base_pipe.fit(X_train, y_train)
        force_single_thread(base_pipe)
        for method in ["none", "sigmoid", "isotonic"]:
            try:
                if method == "none":
                    model = base_pipe
                else:
                    model = CalibratedClassifierCV(estimator=base_pipe, method=method, cv=3)
                    model.fit(X_train, y_train)
                    force_single_thread(model)
                val_prob = model.predict_proba(X_val)[:, 1]
                test_prob = model.predict_proba(X_test)[:, 1]
                calibration_rows.append(
                    {
                        "domain": rt.spec.domain,
                        "model_id": rt.spec.model_id,
                        "calibration_method": method,
                        "brier_val": brier_score_loss(y_val, val_prob),
                        "brier_test": brier_score_loss(y_test, test_prob),
                        "val_prob_mean": float(np.mean(val_prob)),
                        "test_prob_mean": float(np.mean(test_prob)),
                    }
                )
            except Exception as exc:
                calibration_rows.append(
                    {
                        "domain": rt.spec.domain,
                        "model_id": rt.spec.model_id,
                        "calibration_method": method,
                        "brier_val": float("nan"),
                        "brier_test": float("nan"),
                        "val_prob_mean": float("nan"),
                        "test_prob_mean": float("nan"),
                        "status": f"failed:{exc.__class__.__name__}",
                    }
                )

    seed_df = pd.DataFrame(seed_rows)
    split_df = pd.DataFrame(split_rows)
    var_rows: List[Dict[str, Any]] = []
    for domain, g in seed_df.groupby("domain"):
        for metric in ["val_precision", "val_balanced_accuracy", "test_precision", "test_balanced_accuracy"]:
            vals = g[metric].to_numpy(dtype=float)
            mean_v = float(np.mean(vals))
            std_v = float(np.std(vals))
            var_rows.append(
                {
                    "domain": domain,
                    "source": "seed",
                    "metric": metric,
                    "mean": mean_v,
                    "std": std_v,
                    "min": float(np.min(vals)),
                    "max": float(np.max(vals)),
                    "cv": float(std_v / mean_v) if mean_v else float("nan"),
                }
            )
    for domain, g in split_df.groupby("domain"):
        for metric in ["val_precision", "val_balanced_accuracy", "test_precision", "test_balanced_accuracy"]:
            vals = g[metric].to_numpy(dtype=float)
            mean_v = float(np.mean(vals))
            std_v = float(np.std(vals))
            var_rows.append(
                {
                    "domain": domain,
                    "source": "split",
                    "metric": metric,
                    "mean": mean_v,
                    "std": std_v,
                    "min": float(np.min(vals)),
                    "max": float(np.max(vals)),
                    "cv": float(std_v / mean_v) if mean_v else float("nan"),
                }
            )
    var_df = pd.DataFrame(var_rows)
    threshold_df = pd.DataFrame(threshold_rows)
    calibration_df = pd.DataFrame(calibration_rows)
    threshold_stability = threshold_df.groupby("domain")["threshold_selected"].agg(["mean", "std", "min", "max"]).reset_index()
    threshold_stability["status"] = np.where(
        threshold_stability["std"] <= criteria["acceptable_threshold_instability"], "stable", "unstable"
    )
    calibration_stability = calibration_df.groupby("domain")["brier_test"].agg(["mean", "std", "min", "max"]).reset_index()
    calibration_stability["status"] = np.where(
        calibration_stability["std"] <= criteria["acceptable_calibration_drift"], "stable", "drift"
    )

    safe_csv(seed_df, paths.tables / "model_seed_stability.csv")
    safe_csv(split_df, paths.tables / "model_split_stability.csv")
    safe_csv(var_df, paths.tables / "metric_variability_summary.csv")
    safe_csv(threshold_stability, paths.tables / "threshold_stability_audit.csv")
    safe_csv(calibration_stability, paths.tables / "calibration_stability_audit.csv")
    safe_text(
        "# Threshold and Calibration Stability\n\n"
        f"- acceptable_threshold_instability: {criteria['acceptable_threshold_instability']}\n"
        f"- acceptable_calibration_drift: {criteria['acceptable_calibration_drift']}\n",
        paths.reports / "threshold_and_calibration_stability.md",
    )
    return seed_df, split_df, var_df, pd.concat([threshold_df.assign(kind="history"), threshold_stability.assign(kind="summary")], ignore_index=True)


def run_learning_curves(paths: Paths, runtimes: List[DomainRuntime]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    fracs = [0.2, 0.4, 0.6, 0.8, 1.0]
    for rt in runtimes:
        feature_cols = rt.X.columns.tolist()
        train_df = subset_by_ids(rt.df, rt.ids_train)
        val_df = subset_by_ids(rt.df, rt.ids_val)
        X_train = train_df[feature_cols].copy()
        y_train = pd.to_numeric(train_df[rt.spec.target_col], errors="coerce").fillna(0).astype(int)
        X_val = val_df[feature_cols].copy()
        y_val = pd.to_numeric(val_df[rt.spec.target_col], errors="coerce").fillna(0).astype(int)

        rng = np.random.default_rng(RANDOM_STATE)
        idx_all = np.arange(len(X_train))
        for frac in fracs:
            n = max(20, int(len(idx_all) * frac))
            idx = rng.choice(idx_all, size=n, replace=False)
            X_sub = X_train.iloc[idx].copy()
            y_sub = y_train.iloc[idx].copy()
            model = build_pipeline(X_sub, rt.params_base)
            model.fit(X_sub, y_sub)
            force_single_thread(model)
            val_prob = model.predict_proba(X_val)[:, 1]
            thr = choose_threshold(y_val.to_numpy(), val_prob)
            m_val = metric_binary(y_val.to_numpy(), val_prob, thr)
            rows.append(
                {
                    "domain": rt.spec.domain,
                    "model_id": rt.spec.model_id,
                    "train_fraction": frac,
                    "train_rows_used": n,
                    "threshold": thr,
                    "precision_val": m_val["precision"],
                    "balanced_accuracy_val": m_val["balanced_accuracy"],
                    "recall_val": m_val["recall"],
                    "specificity_val": m_val["specificity"],
                    "pr_auc_val": m_val["pr_auc"],
                }
            )
    out = pd.DataFrame(rows)
    safe_csv(out, paths.tables / "learning_curve_detailed.csv")
    md = [
        "# Learning Curve Interpretation",
        "",
        "Heuristic interpretation by domain:",
    ]
    for domain, g in out.groupby("domain"):
        g = g.sort_values("train_fraction")
        start = float(g.iloc[0]["balanced_accuracy_val"])
        end = float(g.iloc[-1]["balanced_accuracy_val"])
        trend = "still_ascending" if end - start > 0.05 else "plateau_or_noise"
        md.append(f"- {domain}: {trend} (delta_balanced_accuracy={end - start:.4f})")
    safe_text("\n".join(md) + "\n", paths.reports / "learning_curve_interpretation.md")
    return out


def run_stress_tests(paths: Paths, runtimes: List[DomainRuntime], criteria: Dict[str, float]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    noise_rows: List[Dict[str, Any]] = []
    realism_rows: List[Dict[str, Any]] = []
    rng = np.random.default_rng(RANDOM_STATE)
    for rt in runtimes:
        feat_cols = rt.X.columns.tolist()
        test_df = subset_by_ids(rt.df, rt.ids_test)
        X_test = test_df[feat_cols].copy()
        y_test = pd.to_numeric(test_df[rt.spec.target_col], errors="coerce").fillna(0).astype(int).to_numpy()
        base_m = rt.metrics_test

        for level in [0, 1, 2, 3]:
            Xn = noise_apply(X_test, level, rng)
            prob = rt.base_model.predict_proba(Xn)[:, 1]
            m = metric_binary(y_test, prob, rt.threshold_base)
            low_thr = max(0.0, rt.threshold_base - 0.10)
            high_thr = min(1.0, rt.threshold_base + 0.10)
            abstention_mask = (prob > low_thr) & (prob < high_thr)
            noise_rows.append(
                {
                    "domain": rt.spec.domain,
                    "model_id": rt.spec.model_id,
                    "noise_level": f"noise_level_{level}_{['baseline','mild','moderate','high'][level]}",
                    "precision_test": m["precision"],
                    "balanced_accuracy_test": m["balanced_accuracy"],
                    "recall_test": m["recall"],
                    "specificity_test": m["specificity"],
                    "brier_score_test": m["brier_score"],
                    "precision_degradation": base_m["precision"] - m["precision"],
                    "balanced_accuracy_degradation": base_m["balanced_accuracy"] - m["balanced_accuracy"],
                    "coverage": float((~abstention_mask).mean()),
                    "high_confidence_precision": float(precision_score(y_test[~abstention_mask], (prob[~abstention_mask] >= rt.threshold_base).astype(int), zero_division=0))
                    if (~abstention_mask).sum() > 0
                    else float("nan"),
                }
            )

        for scenario in ["incomplete_inputs", "contradictory_inputs", "mixed_comorbidity_signals"]:
            Xr = realism_apply(X_test, scenario, rng)
            prob = rt.base_model.predict_proba(Xr)[:, 1]
            m = metric_binary(y_test, prob, rt.threshold_base)
            realism_rows.append(
                {
                    "domain": rt.spec.domain,
                    "model_id": rt.spec.model_id,
                    "scenario": scenario,
                    "precision_test": m["precision"],
                    "balanced_accuracy_test": m["balanced_accuracy"],
                    "recall_test": m["recall"],
                    "specificity_test": m["specificity"],
                    "brier_score_test": m["brier_score"],
                    "precision_degradation": base_m["precision"] - m["precision"],
                    "balanced_accuracy_degradation": base_m["balanced_accuracy"] - m["balanced_accuracy"],
                }
            )

    noise_df = pd.DataFrame(noise_rows)
    realism_df = pd.DataFrame(realism_rows)
    safe_csv(noise_df, paths.stress / "noise_robustness_results.csv")
    safe_csv(realism_df, paths.stress / "realism_shift_results.csv")
    safe_text(
        "# Noise Robustness Report\n\n"
        f"- acceptable_noise_degradation: {criteria['acceptable_noise_degradation']}\n"
        f"- models_evaluated: {noise_df['model_id'].nunique()}\n",
        paths.reports / "noise_robustness_report.md",
    )
    safe_text(
        "# Realism Shift Report\n\n"
        f"- acceptable_domain_shift_degradation: {criteria['acceptable_domain_shift_degradation']}\n"
        f"- scenarios: incomplete_inputs, contradictory_inputs, mixed_comorbidity_signals\n",
        paths.reports / "realism_shift_report.md",
    )
    return noise_df, realism_df


def run_controlled_retraining(paths: Paths, runtimes: List[DomainRuntime], criteria: Dict[str, float]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trial_rows: List[Dict[str, Any]] = []
    search_rows: List[Dict[str, Any]] = []
    retrain_rows: List[Dict[str, Any]] = []
    candidate_grid = [
        {"n_estimators": 220, "max_depth": 8, "min_samples_split": 10, "min_samples_leaf": 4, "max_features": "sqrt", "class_weight": "balanced_subsample"},
        {"n_estimators": 300, "max_depth": 10, "min_samples_split": 14, "min_samples_leaf": 6, "max_features": "log2", "class_weight": "balanced"},
        {"n_estimators": 180, "max_depth": 6, "min_samples_split": 20, "min_samples_leaf": 8, "max_features": 0.5, "class_weight": "balanced_subsample"},
    ]

    for rt in runtimes:
        feat_cols = rt.X.columns.tolist()
        train_df = subset_by_ids(rt.df, rt.ids_train)
        val_df = subset_by_ids(rt.df, rt.ids_val)
        test_df = subset_by_ids(rt.df, rt.ids_test)
        X_train = train_df[feat_cols].copy()
        y_train = pd.to_numeric(train_df[rt.spec.target_col], errors="coerce").fillna(0).astype(int)
        X_val = val_df[feat_cols].copy()
        y_val = pd.to_numeric(val_df[rt.spec.target_col], errors="coerce").fillna(0).astype(int)
        X_test = test_df[feat_cols].copy()
        y_test = pd.to_numeric(test_df[rt.spec.target_col], errors="coerce").fillna(0).astype(int)

        best = None
        best_payload: Dict[str, Any] = {}
        for i, params in enumerate(candidate_grid, start=1):
            pipe = build_pipeline(X_train, params)
            pipe.fit(X_train, y_train)
            force_single_thread(pipe)
            val_prob = pipe.predict_proba(X_val)[:, 1]
            thr = choose_threshold(y_val.to_numpy(), val_prob)
            m_val = metric_binary(y_val.to_numpy(), val_prob, thr)
            test_prob = pipe.predict_proba(X_test)[:, 1]
            m_test = metric_binary(y_test.to_numpy(), test_prob, thr)
            score = 0.45 * m_val["precision"] + 0.35 * m_val["balanced_accuracy"] + 0.20 * m_val["recall"]
            candidate_id = f"{rt.spec.domain}_anti_overfit_v1_c{i}"
            search_rows.append(
                {
                    "domain": rt.spec.domain,
                    "model_id": rt.spec.model_id,
                    "candidate_id": candidate_id,
                    "params_json": json.dumps(params, ensure_ascii=True),
                    "threshold_selected": thr,
                    "val_precision": m_val["precision"],
                    "val_balanced_accuracy": m_val["balanced_accuracy"],
                    "val_recall": m_val["recall"],
                    "test_precision": m_test["precision"],
                    "test_balanced_accuracy": m_test["balanced_accuracy"],
                    "test_recall": m_test["recall"],
                    "selection_score": score,
                }
            )
            if best is None or score > best:
                best = score
                best_payload = {
                    "pipe": pipe,
                    "params": params,
                    "threshold": thr,
                    "m_val": m_val,
                    "m_test": m_test,
                    "candidate_id": candidate_id,
                    "test_prob": test_prob,
                }

        if not best_payload:
            continue
        dom_dir = paths.retrained / rt.spec.domain
        dom_dir.mkdir(parents=True, exist_ok=True)
        model_file = dom_dir / "model.joblib"
        meta_file = dom_dir / "metadata.json"
        joblib.dump(best_payload["pipe"], model_file)
        safe_json(
            {
                "domain": rt.spec.domain,
                "base_model_id": rt.spec.model_id,
                "candidate_id": best_payload["candidate_id"],
                "params": best_payload["params"],
                "threshold_recommended": best_payload["threshold"],
                "metrics_val": best_payload["m_val"],
                "metrics_test": best_payload["m_test"],
                "created_at_utc": now_iso(),
            },
            meta_file,
        )
        retrain_rows.append(
            {
                "domain": rt.spec.domain,
                "base_model_id": rt.spec.model_id,
                "retrained_model_id": f"retrained_{rt.spec.domain}_anti_overfit_v1",
                "params_json": json.dumps(best_payload["params"], ensure_ascii=True),
                "threshold_recommended": best_payload["threshold"],
                "base_precision_test": rt.metrics_test["precision"],
                "retrained_precision_test": best_payload["m_test"]["precision"],
                "base_balanced_accuracy_test": rt.metrics_test["balanced_accuracy"],
                "retrained_balanced_accuracy_test": best_payload["m_test"]["balanced_accuracy"],
                "base_recall_test": rt.metrics_test["recall"],
                "retrained_recall_test": best_payload["m_test"]["recall"],
                "delta_precision_test": best_payload["m_test"]["precision"] - rt.metrics_test["precision"],
                "delta_balanced_accuracy_test": best_payload["m_test"]["balanced_accuracy"] - rt.metrics_test["balanced_accuracy"],
                "delta_recall_test": best_payload["m_test"]["recall"] - rt.metrics_test["recall"],
            }
        )
        trial_rows.append(
            {
                "trial_id": best_payload["candidate_id"],
                "domain": rt.spec.domain,
                "base_model_id": rt.spec.model_id,
                "status": "completed",
                "selected": True,
                "threshold": best_payload["threshold"],
            }
        )

    trials_df = pd.DataFrame(trial_rows)
    search_df = pd.DataFrame(search_rows)
    retrain_df = pd.DataFrame(retrain_rows)
    safe_csv(retrain_df, paths.tables / "retraining_comparison.csv")
    safe_text("# Retraining Summary\n\nControlled anti-overfit retraining executed.\n", paths.reports / "retraining_summary.md")
    return trials_df, search_df, retrain_df


def finalize_classification(
    paths: Paths,
    overfit_df: pd.DataFrame,
    leak_model_df: pd.DataFrame,
    variability_df: pd.DataFrame,
    noise_df: pd.DataFrame,
    realism_df: pd.DataFrame,
    retrain_df: pd.DataFrame,
    criteria: Dict[str, float],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows: List[Dict[str, Any]] = []
    dom_rows: List[Dict[str, Any]] = []
    for domain in sorted(overfit_df["domain"].unique().tolist()):
        o = overfit_df[overfit_df["domain"] == domain].iloc[0]
        l = leak_model_df[leak_model_df["domain"] == domain].iloc[0]
        var_seed = variability_df[(variability_df["domain"] == domain) & (variability_df["source"] == "seed") & (variability_df["metric"] == "test_balanced_accuracy")]
        var_split = variability_df[(variability_df["domain"] == domain) & (variability_df["source"] == "split") & (variability_df["metric"] == "test_balanced_accuracy")]
        seed_std = float(var_seed.iloc[0]["std"]) if len(var_seed) else float("nan")
        split_std = float(var_split.iloc[0]["std"]) if len(var_split) else float("nan")
        noise_l2 = noise_df[(noise_df["domain"] == domain) & (noise_df["noise_level"].str.contains("moderate"))]
        noise_deg = float(noise_l2["balanced_accuracy_degradation"].mean()) if len(noise_l2) else 0.0
        real_deg = float(realism_df[realism_df["domain"] == domain]["balanced_accuracy_degradation"].max()) if len(realism_df[realism_df["domain"] == domain]) else 0.0
        retr = retrain_df[retrain_df["domain"] == domain]
        retr_delta = float(retr.iloc[0]["delta_balanced_accuracy_test"]) if len(retr) else 0.0

        status = "accepted_but_experimental"
        reason = "baseline accepted with caveats"
        if l["model_risk_level"] in ("high", "critical"):
            status = "possible_leakage_model"
            reason = "high leakage risk detected"
        elif o["overfit_class"] in ("suspicious_perfect_score", "high_risk_overfit"):
            status = "high_risk_of_overfit"
            reason = "overfit pattern in train/val/test gap or suspiciously perfect metrics"
        elif seed_std > criteria["acceptable_seed_variability"] or split_std > criteria["acceptable_split_variability"]:
            status = "unstable_across_splits"
            reason = "high variability across seeds/splits"
        elif noise_deg > criteria["acceptable_noise_degradation"] or real_deg > criteria["acceptable_domain_shift_degradation"]:
            status = "simulation_aligned_only"
            reason = "performance degrades under realism/noise stress tests"
        elif retr_delta > 0.01 and o["test_balanced_accuracy"] < 0.99:
            status = "accepted_generalizing_model"
            reason = "controlled retraining improved stability without unrealistic metrics"
        elif o["test_balanced_accuracy"] >= 0.99 and o["test_precision"] >= 0.99:
            status = "accepted_but_experimental"
            reason = "very high metrics retained but constrained to experimental usage"

        rows.append(
            {
                "domain": domain,
                "base_model_id": o["model_id"],
                "classification": status,
                "justification": reason,
                "overfit_class": o["overfit_class"],
                "leakage_risk": l["model_risk_level"],
                "seed_std_balanced_accuracy": seed_std,
                "split_std_balanced_accuracy": split_std,
                "noise_degradation_balanced_accuracy": noise_deg,
                "realism_degradation_balanced_accuracy": real_deg,
                "base_precision_test": o["test_precision"],
                "base_balanced_accuracy_test": o["test_balanced_accuracy"],
                "base_recall_test": o["test_recall"],
                "retrained_delta_balanced_accuracy_test": retr_delta,
            }
        )

    cls_df = pd.DataFrame(rows).sort_values("domain")
    safe_csv(cls_df, paths.tables / "final_model_classification.csv")
    lines = ["# Final Model Classification", ""]
    for _, r in cls_df.iterrows():
        lines.append(f"- {r['domain']}: {r['classification']} | {r['justification']}")
    safe_text("\n".join(lines) + "\n", paths.reports / "final_model_classification.md")

    for _, r in cls_df.iterrows():
        mode = "precise"
        if r["classification"] in ("simulation_aligned_only", "unstable_across_splits"):
            mode = "abstention_assisted"
        elif r["base_recall_test"] < 0.75:
            mode = "sensitive"
        product_ready = r["classification"] in ("accepted_generalizing_model", "accepted_but_experimental")
        thesis_ready = r["classification"] in ("accepted_generalizing_model", "accepted_but_experimental", "simulation_aligned_only")
        dom_rows.append(
            {
                "domain": r["domain"],
                "best_generalizing_model": f"retrained_{r['domain']}_anti_overfit_v1" if r["retrained_delta_balanced_accuracy_test"] > 0 else r["base_model_id"],
                "recommended_operating_mode": mode,
                "probability_output_ready": True,
                "explanation_output_ready": True,
                "product_ready": bool(product_ready),
                "thesis_ready": bool(thesis_ready),
                "main_risk": r["classification"],
            }
        )
    dom_df = pd.DataFrame(dom_rows).sort_values("domain")
    safe_csv(dom_df, paths.tables / "domain_generalization_decisions.csv")
    lines = ["# Domain Generalization Decisions", ""]
    for _, r in dom_df.iterrows():
        lines.append(
            f"- {r['domain']}: model={r['best_generalizing_model']} | mode={r['recommended_operating_mode']} | "
            f"product_ready={r['product_ready']} | main_risk={r['main_risk']}"
        )
    safe_text("\n".join(lines) + "\n", paths.reports / "domain_generalization_decisions.md")
    return cls_df, dom_df


def export_histories(
    paths: Paths,
    seed_df: pd.DataFrame,
    split_df: pd.DataFrame,
    search_df: pd.DataFrame,
    learning_df: pd.DataFrame,
    noise_df: pd.DataFrame,
    realism_df: pd.DataFrame,
    cls_df: pd.DataFrame,
    threshold_history: pd.DataFrame,
) -> None:
    hist = paths.root / "reports" / "training_history"
    hist.mkdir(parents=True, exist_ok=True)
    safe_csv(pd.concat([seed_df.assign(source="seed"), split_df.assign(source="split")], ignore_index=True), hist / "trial_registry_generalization.csv")
    safe_csv(split_df, hist / "fold_metrics_generalization.csv")
    safe_csv(search_df, hist / "hyperparameter_history_generalization.csv")
    safe_csv(seed_df, hist / "seed_stability_history.csv")
    safe_csv(split_df, hist / "split_stability_history.csv")
    safe_csv(learning_df, hist / "learning_curve_history.csv")
    safe_csv(threshold_history, hist / "threshold_sweep_history_generalization.csv")
    safe_csv(pd.DataFrame(), hist / "calibration_history_generalization.csv")
    safe_csv(pd.concat([noise_df.assign(test_type="noise"), realism_df.assign(test_type="realism")], ignore_index=True), hist / "stress_test_history.csv")
    safe_csv(cls_df, hist / "model_acceptance_history.csv")


def export_inference_v3(paths: Paths, cls_df: pd.DataFrame, dom_df: pd.DataFrame) -> None:
    inf = paths.root / "artifacts" / "inference_v3"
    inf.mkdir(parents=True, exist_ok=True)
    schema = {
        "type": "object",
        "properties": {
            "probability_by_domain": {"type": "object"},
            "probability_by_internal_unit_when_applicable": {"type": "object"},
            "confidence_level": {"type": "string"},
            "coverage_summary": {"type": "object"},
            "direct_proxy_absent_summary": {"type": "object"},
            "missing_critical_inputs": {"type": "array"},
            "top_positive_contributors": {"type": "array"},
            "top_negative_contributors": {"type": "array"},
            "abstention_flag": {"type": "boolean"},
            "threshold_used": {"type": "number"},
            "model_version": {"type": "string"},
            "generalization_status": {"type": "string"},
            "recommendation_text": {"type": "string"},
            "disclaimers": {"type": "array"},
        },
    }
    safe_json(schema, inf / "inference_output_schema.json")
    safe_text(
        "Inference v3 returns probabilistic outputs with explicit generalization status.\n",
        inf / "explanation_contract.md",
    )
    sample = {
        "probability_by_domain": {"adhd": 0.61, "conduct": 0.21, "elimination": 0.08, "anxiety": 0.42, "depression": 0.19},
        "probability_by_internal_unit_when_applicable": {"target_adhd_exact": 0.57},
        "confidence_level": "medium",
        "coverage_summary": {"available_features_ratio": 0.87},
        "direct_proxy_absent_summary": {"direct": 18, "proxy": 9, "absent": 4},
        "missing_critical_inputs": ["q_qi_0007"],
        "top_positive_contributors": ["cbcl_attention_problems_proxy", "sdq_hyperactivity_total"],
        "top_negative_contributors": ["has_scared_p", "q_qi_0015"],
        "abstention_flag": False,
        "threshold_used": 0.55,
        "model_version": "retrained_adhd_anti_overfit_v1",
        "generalization_status": "accepted_generalizing_model",
        "recommendation_text": "Riesgo moderado, priorizar tamizaje clinico complementario.",
        "disclaimers": ["Entorno simulado", "No constituye diagnostico clinico definitivo"],
    }
    safe_json(sample, inf / "sample_inference_outputs.json")
    safe_text(
        "from pathlib import Path\nimport joblib\n\ndef load_model(model_path: str):\n    return joblib.load(Path(model_path))\n\n"
        "def predict_domains(model, X):\n    prob = model.predict_proba(X)[:, 1]\n    return prob\n",
        inf / "predict_domains.py",
    )
    safe_text(
        "from pathlib import Path\nimport joblib\n\ndef load_model(model_path: str):\n    return joblib.load(Path(model_path))\n\n"
        "def predict_internal_units(model, X):\n    prob = model.predict_proba(X)[:, 1]\n    return prob\n",
        inf / "predict_internal_units.py",
    )


def write_final_reports(paths: Paths, cls_df: pd.DataFrame, dom_df: pd.DataFrame) -> None:
    summary = [
        "# Generalization Gate Summary",
        "",
        f"- generated_at_utc: {now_iso()}",
        f"- total_domains: {len(dom_df)}",
        f"- accepted_generalizing: {int((cls_df['classification'] == 'accepted_generalizing_model').sum())}",
        f"- high_risk_overfit: {int((cls_df['classification'] == 'high_risk_of_overfit').sum())}",
        f"- possible_leakage: {int((cls_df['classification'] == 'possible_leakage_model').sum())}",
    ]
    safe_text("\n".join(summary) + "\n", paths.reports / "generalization_gate_summary.md")

    rec = [
        "# Final Recommendations For Project",
        "",
        "Use accepted_generalizing_model first. Keep suspicious-perfect models restricted to experimental mode.",
        "",
    ]
    for _, r in dom_df.iterrows():
        rec.append(
            f"- {r['domain']}: mode={r['recommended_operating_mode']}, product_ready={r['product_ready']}, risk={r['main_risk']}"
        )
    safe_text("\n".join(rec) + "\n", paths.reports / "final_recommendations_for_project.md")


def run() -> None:
    parser = argparse.ArgumentParser(description="Run GENERALIZATION GATE v1 for hybrid DSM5 RF models.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)
    root = Path(args.root).resolve()
    paths = build_paths(root)
    ensure_dirs(paths)

    specs = domain_model_specs(paths)
    if not specs:
        raise RuntimeError("No domain model specs were discovered for generalization gate.")

    generate_input_inventory(paths, specs)
    criteria = phase_generalization_criteria(paths)
    overfit_df, runtimes = phase_overfit_audit(paths, specs, criteria)
    leak_f_df, leak_m_df = phase_leakage_audit(paths, runtimes, overfit_df)
    seed_df, split_df, var_df, threshold_history = run_seed_split_stability(paths, runtimes, criteria)
    learning_df = run_learning_curves(paths, runtimes)
    noise_df, realism_df = run_stress_tests(paths, runtimes, criteria)
    trials_df, search_df, retrain_df = run_controlled_retraining(paths, runtimes, criteria)
    cls_df, dom_df = finalize_classification(paths, overfit_df, leak_m_df, var_df, noise_df, realism_df, retrain_df, criteria)
    export_histories(paths, seed_df, split_df, search_df, learning_df, noise_df, realism_df, cls_df, threshold_history)
    export_inference_v3(paths, cls_df, dom_df)
    write_final_reports(paths, cls_df, dom_df)

    LOGGER.info("GENERALIZATION GATE v1 complete")
    LOGGER.info("Accepted generalizing models: %d", int((cls_df["classification"] == "accepted_generalizing_model").sum()))
    LOGGER.info("High risk overfit models: %d", int((cls_df["classification"] == "high_risk_of_overfit").sum()))
    LOGGER.info("Possible leakage models: %d", int((cls_df["classification"] == "possible_leakage_model").sum()))


if __name__ == "__main__":
    run()
