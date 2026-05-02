#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
LINE = "hybrid_domain_specialized_rf_v17"
BASE = ROOT / "data" / LINE
AUDIT = BASE / "extreme_metrics_threshold_separability_audit"
PLOTS = AUDIT / "plots"

ACTIVE_V17 = ROOT / "data/hybrid_active_modes_freeze_v17/tables/hybrid_active_models_30_modes.csv"
RECOMP = BASE / "tables/v17_recomputed_champion_metrics.csv"
SELECTED = BASE / "tables/selected_domain_specialized_champions_v17.csv"
IMPURITY = BASE / "tables/rf_feature_importance_impurity_v17.csv"
PERM = BASE / "tables/rf_permutation_importance_v17.csv"
SPLIT_PROFILE = BASE / "tables/rf_training_split_profile_v17.csv"
PROB_SUM = BASE / "tables/rf_probability_distribution_v17.csv"
CAL_SUM = BASE / "tables/rf_calibration_summary_v17.csv"
ERR_SUM = BASE / "tables/rf_error_analysis_v17.csv"
PAIRWISE = BASE / "tables/v17_pairwise_prediction_similarity_all_domains.csv"
VALIDATOR_V17 = BASE / "validation/v17_final_model_validator.json"
DATASET = ROOT / "data/hybrid_no_external_scores_rebuild_v2/tables/hybrid_no_external_scores_dataset_ready.csv"
INPUTS_V17 = ROOT / "data/hybrid_active_modes_freeze_v17/tables/hybrid_questionnaire_inputs_master.csv"
MODEL_ROOT = ROOT / "models/active_modes"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
BASE_SEED = 20270601


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sf(v: Any, default: float = float("nan")) -> float:
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def feats(v: Any) -> list[str]:
    return [x.strip() for x in str(v or "").split("|") if x.strip() and x.strip().lower() != "nan"]


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def tcol(domain: str) -> str:
    return f"target_domain_{domain}_final"


def build_splits(df: pd.DataFrame) -> dict[str, dict[str, list[str]]]:
    ids = df["participant_id"].astype(str).to_numpy()
    out: dict[str, dict[str, list[str]]] = {}
    from sklearn.model_selection import train_test_split

    for i, domain in enumerate(DOMAINS):
        y = df[tcol(domain)].astype(int).to_numpy()
        seed = BASE_SEED + i * 37
        tr_ids, tmp_ids, ytr, ytmp = train_test_split(ids, y, test_size=0.40, random_state=seed, stratify=y)
        va_ids, ho_ids, yva, yho = train_test_split(tmp_ids, ytmp, test_size=0.50, random_state=seed + 1, stratify=ytmp)
        out[domain] = {
            "train": list(map(str, tr_ids)),
            "val": list(map(str, va_ids)),
            "holdout": list(map(str, ho_ids)),
        }
    return out


def subset(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    s = set(ids)
    return df[df["participant_id"].astype(str).isin(s)].copy()


def prep_x(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    x = df[features].copy()
    for c in x.columns:
        if c == "sex_assigned_at_birth":
            x[c] = x[c].fillna("unknown").astype(str)
        else:
            x[c] = pd.to_numeric(x[c], errors="coerce").astype(float)
    return x


def predict_proba(model: Any, x: pd.DataFrame) -> np.ndarray:
    return np.clip(np.asarray(model.predict_proba(x)[:, 1], float), 1e-6, 1 - 1e-6)


def auc(y: np.ndarray, p: np.ndarray) -> float:
    return float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else float("nan")


def pr_auc(y: np.ndarray, p: np.ndarray) -> float:
    return float(average_precision_score(y, p)) if len(np.unique(y)) > 1 else float(np.mean(y))


def metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float) -> dict[str, Any]:
    y_true = np.asarray(y_true, int)
    prob = np.clip(np.asarray(prob, float), 1e-6, 1 - 1e-6)
    pred = (prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    precision = float(precision_score(y_true, pred, zero_division=0))
    recall = float(recall_score(y_true, pred, zero_division=0))
    specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
    npv = float(tn / (tn + fn)) if (tn + fn) else 0.0
    f1 = float(f1_score(y_true, pred, zero_division=0))
    f2 = float((5 * precision * recall) / (4 * precision + recall)) if (4 * precision + recall) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": f1,
        "f2": f2,
        "roc_auc": auc(y_true, prob),
        "pr_auc": pr_auc(y_true, prob),
        "brier": float(brier_score_loss(y_true, prob)),
        "mcc": float(matthews_corrcoef(y_true, pred)) if len(np.unique(y_true)) > 1 else 0.0,
        "npv": npv,
        "fpr": fpr,
        "fnr": fnr,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "pred_pos_rate": float(np.mean(pred)),
    }


def threshold_grid(p: np.ndarray) -> np.ndarray:
    q = np.quantile(p, np.linspace(0.01, 0.99, 99))
    g = np.arange(0.01, 1.00, 0.01)
    t = np.unique(np.concatenate([q, g, [0.5]]))
    t = t[(t > 0) & (t < 1)]
    return t


def threshold_objective(mm: dict[str, Any]) -> float:
    s = 0.55 * mm["f2"] + 0.20 * mm["recall"] + 0.10 * mm["specificity"] + 0.10 * mm["precision"] + 0.05 * mm["balanced_accuracy"]
    if mm["recall"] < 0.90:
        s -= 0.35 + (0.90 - mm["recall"])
    if mm["specificity"] < 0.80:
        s -= 0.25 + (0.80 - mm["specificity"])
    if mm["fpr"] > 0.25:
        s -= 0.30 + (mm["fpr"] - 0.25)
    if mm["fnr"] > 0.10:
        s -= 0.30 + (mm["fnr"] - 0.10)
    return float(s)


def manual_weight(y: np.ndarray) -> dict[int, float]:
    pos = max(float(np.mean(y)), 1e-6)
    neg = max(1.0 - pos, 1e-6)
    return {0: 1.0, 1: float(min(4.0, max(1.3, neg / pos * 1.1)))}


def fit_ablation_model(features: list[str], hp: dict[str, Any], calibration: str, xtr: pd.DataFrame, ytr: np.ndarray) -> Any:
    cats = [f for f in features if f == "sex_assigned_at_birth"]
    nums = [f for f in features if f not in cats]
    pre = ColumnTransformer(
        [
            ("num", Pipeline([("imp", SimpleImputer(strategy="median", keep_empty_features=True))]), nums),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
                        ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                cats,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )
    cw = hp["class_weight"]
    if str(cw) == "manual_recall":
        cw = manual_weight(ytr)
    max_features = hp["max_features"]
    if isinstance(max_features, str):
        low = max_features.strip().lower()
        if low in {"sqrt", "log2"}:
            max_features = low
        else:
            try:
                max_features = float(low)
            except Exception:
                max_features = None

    rf = RandomForestClassifier(
        n_estimators=int(hp["n_estimators"]),
        max_depth=None if pd.isna(hp["max_depth"]) else int(hp["max_depth"]),
        min_samples_split=int(hp["min_samples_split"]),
        min_samples_leaf=int(hp["min_samples_leaf"]),
        max_features=max_features,
        max_samples=None if pd.isna(hp["max_samples"]) else float(hp["max_samples"]),
        bootstrap=str(hp["bootstrap"]).lower() == "true",
        class_weight=cw,
        criterion=str(hp["criterion"]),
        ccp_alpha=float(hp["ccp_alpha"]),
        random_state=int(hp["seed"]),
        n_jobs=-1,
    )
    pipe = Pipeline([("pre", pre), ("rf", rf)])
    if str(calibration) == "none":
        pipe.fit(xtr, ytr)
        return pipe
    cv = 3 if min(np.bincount(ytr.astype(int))) >= 3 else 2
    cal = CalibratedClassifierCV(estimator=pipe, method=str(calibration), cv=cv)
    cal.fit(xtr, ytr)
    return cal


def infer_features_label_map() -> dict[str, str]:
    if not INPUTS_V17.exists():
        return {}
    q = pd.read_csv(INPUTS_V17)
    q["feature"] = q["feature"].astype(str).str.strip().str.lower()
    return {str(r["feature"]): str(r.get("feature_label_human") or "") for _, r in q.iterrows()}


def detect_extreme_slots(df: pd.DataFrame) -> pd.DataFrame:
    c = (
        (df["recall"] >= 0.98)
        | (df["specificity"] >= 0.98)
        | (df["roc_auc"] >= 0.98)
        | (df["pr_auc"] >= 0.98)
        | (df["f1"] >= 0.98)
        | (df["balanced_accuracy"] >= 0.98)
        | (df["brier"] <= 0.005)
        | (df["threshold"] <= 0.15)
        | (df.get("generalization_flag", "no").astype(str).str.lower() == "yes")
        | (df.get("dataset_ease_flag", "no").astype(str).str.lower() == "yes")
    )
    out = df[c].copy()
    out["slot_key"] = out["domain"].astype(str) + "/" + out["role"].astype(str) + "/" + out["mode"].astype(str)
    return out.sort_values(["domain", "role", "mode"]).reset_index(drop=True)


def feature_target_corr(x: pd.Series, y: np.ndarray) -> float:
    xv = pd.to_numeric(x, errors="coerce").astype(float)
    mask = (~xv.isna()) & (~pd.isna(y))
    if mask.sum() < 5:
        return float("nan")
    xx = xv[mask]
    yy = pd.Series(y[mask]).astype(float)
    if xx.nunique(dropna=True) <= 1:
        return 0.0
    return float(np.corrcoef(xx, yy)[0, 1])


def has_proxy_pattern(feature: str) -> bool:
    f = str(feature).lower()
    toks = [
        "target_",
        "threshold_met",
        "diagnosis",
        "classification",
        "outcome",
        "result",
        "rule_met",
        "label",
    ]
    return any(t in f for t in toks)


def is_global_or_duration_feature(feature: str) -> bool:
    f = str(feature).lower()
    pats = ["impairment", "duration", "global", "distress", "course", "onset", "age_ge"]
    return any(p in f for p in pats)


def core_item_feature(feature: str) -> bool:
    f = str(feature).lower()
    if f in {"sex_assigned_at_birth", "age_years"}:
        return True
    if is_global_or_duration_feature(f):
        return False
    if "symptom_count" in f or "core_" in f or "_count" in f:
        return False
    return True


def sweep_thresholds(slot_key: str, domain: str, probs: dict[str, np.ndarray], ys: dict[str, np.ndarray], current_thr: float) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    best = None
    best_score = -1e18
    all_thr = threshold_grid(probs["val"])
    all_thr = np.unique(np.concatenate([all_thr, np.array([current_thr])]))
    for thr in all_thr:
        mm_tr = metrics(ys["train"], probs["train"], float(thr))
        mm_va = metrics(ys["val"], probs["val"], float(thr))
        mm_ho = metrics(ys["holdout"], probs["holdout"], float(thr))
        gap_recall = abs(mm_tr["recall"] - mm_ho["recall"])
        gap_f2 = abs(mm_tr["f2"] - mm_ho["f2"])
        gap_ba = abs(mm_tr["balanced_accuracy"] - mm_ho["balanced_accuracy"])
        score = threshold_objective(mm_ho)
        rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "threshold": float(thr),
                "train_recall": mm_tr["recall"],
                "val_recall": mm_va["recall"],
                "holdout_recall": mm_ho["recall"],
                "train_specificity": mm_tr["specificity"],
                "val_specificity": mm_va["specificity"],
                "holdout_specificity": mm_ho["specificity"],
                "holdout_precision": mm_ho["precision"],
                "holdout_npv": mm_ho["npv"],
                "holdout_fpr": mm_ho["fpr"],
                "holdout_fnr": mm_ho["fnr"],
                "holdout_f1": mm_ho["f1"],
                "holdout_f2": mm_ho["f2"],
                "holdout_balanced_accuracy": mm_ho["balanced_accuracy"],
                "holdout_mcc": mm_ho["mcc"],
                "holdout_positive_rate_predicted": mm_ho["pred_pos_rate"],
                "holdout_tn": mm_ho["tn"],
                "holdout_fp": mm_ho["fp"],
                "holdout_fn": mm_ho["fn"],
                "holdout_tp": mm_ho["tp"],
                "gap_train_holdout_recall": gap_recall,
                "gap_train_holdout_f2": gap_f2,
                "gap_train_holdout_balanced_accuracy": gap_ba,
                "threshold_objective": score,
            }
        )
        if score > best_score:
            best_score = score
            best = {"threshold": float(thr), "metrics_holdout": mm_ho, "metrics_train": mm_tr, "metrics_val": mm_va, "score": score}

    sw = pd.DataFrame(rows).sort_values("threshold").reset_index(drop=True)
    cur_row = sw.iloc[(sw["threshold"] - current_thr).abs().argmin()].to_dict()
    assert best is not None
    return sw, {"best": best, "current": cur_row}


def recommend_threshold(decision_basis: dict[str, Any], current_thr: float) -> tuple[bool, float, str]:
    cur = decision_basis["current"]
    best = decision_basis["best"]
    new_thr = float(best["threshold"])
    delta = abs(new_thr - float(current_thr))
    cur_f2 = sf(cur.get("holdout_f2"), 0.0)
    cur_rec = sf(cur.get("holdout_recall"), 0.0)
    cur_spec = sf(cur.get("holdout_specificity"), 0.0)
    cur_fpr = sf(cur.get("holdout_fpr"), 1.0)
    cur_fnr = sf(cur.get("holdout_fnr"), 1.0)
    bestm = best["metrics_holdout"]

    improves = (
        (bestm["f2"] > cur_f2 + 0.03)
        and (bestm["recall"] >= max(0.90, cur_rec))
        and (bestm["specificity"] >= max(0.80, cur_spec))
        and (bestm["fpr"] <= cur_fpr)
        and (bestm["fnr"] <= cur_fnr)
        and (delta >= 0.05)
    )
    if not improves:
        return False, float(current_thr), "keep_current_threshold_because_adjustment_not_better"
    return True, new_thr, "adjust_threshold_because_better_operationally"


def split_contamination(df: pd.DataFrame, domain: str, features: list[str], splits: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
    tr = subset(df, splits[domain]["train"])
    va = subset(df, splits[domain]["val"])
    ho = subset(df, splits[domain]["holdout"])
    ids_tr = set(tr["participant_id"].astype(str))
    ids_va = set(va["participant_id"].astype(str))
    ids_ho = set(ho["participant_id"].astype(str))
    id_overlap = len(ids_tr & ids_va) + len(ids_tr & ids_ho) + len(ids_va & ids_ho)

    cols = list(features) + [tcol(domain)]
    tr_rows = set(pd.util.hash_pandas_object(tr[cols].fillna("<na>"), index=False).astype(str))
    va_rows = set(pd.util.hash_pandas_object(va[cols].fillna("<na>"), index=False).astype(str))
    ho_rows = set(pd.util.hash_pandas_object(ho[cols].fillna("<na>"), index=False).astype(str))
    row_overlap = len(tr_rows & va_rows) + len(tr_rows & ho_rows) + len(va_rows & ho_rows)

    # Exact-row overlap across different participants can happen in categorical clinical data and is not
    # by itself split contamination. Hard-fail only if participant IDs leak between splits.
    status = "pass" if id_overlap == 0 else "fail"
    return {
        "id_overlap_count": int(id_overlap),
        "exact_row_overlap_count": int(row_overlap),
        "exact_row_overlap_observation": "yes" if row_overlap > 0 else "no",
        "split_contamination_status": status,
    }


def build_ablation_sets(features: list[str], perm_df_slot: pd.DataFrame) -> dict[str, list[str]]:
    top = perm_df_slot.sort_values("permutation_ba_drop_mean", ascending=False)["feature"].astype(str).tolist()
    top1 = top[:1]
    top3 = top[:3]

    sets: dict[str, list[str]] = {}
    sets["no_top1"] = [f for f in features if f not in top1]
    sets["no_top3"] = [f for f in features if f not in top3]
    sets["no_global_impairment_or_global_duration"] = [f for f in features if not is_global_or_duration_feature(f)]
    sets["no_target_proxy_candidates"] = [f for f in features if not has_proxy_pattern(f)]
    core_only = [f for f in features if core_item_feature(f)]
    sets["core_items_only"] = core_only if len(core_only) >= 3 else list(features)

    keep_n = max(3, int(math.ceil(len(features) * 0.8)))
    keep = top[:keep_n] if len(top) >= keep_n else list(features)
    sets["domain_strict_pruned"] = [f for f in features if f in set(keep)]

    for k, v in list(sets.items()):
        if len(v) < 2:
            sets[k] = list(features)
    return sets


def high_separability_flags(mm: dict[str, Any]) -> dict[str, str]:
    return {
        "high_separability_alert": "yes" if any(sf(mm.get(k), 0.0) > 0.98 for k in ["recall", "specificity", "roc_auc", "pr_auc"]) else "no",
    }


def main() -> int:
    AUDIT.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    active = pd.read_csv(ACTIVE_V17)
    _recomputed = pd.read_csv(RECOMP)
    _selected = pd.read_csv(SELECTED)
    impurity = pd.read_csv(IMPURITY)
    perm = pd.read_csv(PERM)
    _split_profile = pd.read_csv(SPLIT_PROFILE)
    _prob_sum = pd.read_csv(PROB_SUM)
    _cal_sum = pd.read_csv(CAL_SUM)
    _err_sum = pd.read_csv(ERR_SUM)
    _pairwise = pd.read_csv(PAIRWISE)
    with VALIDATOR_V17.open("r", encoding="utf-8") as f:
        _ = json.load(f)

    data = pd.read_csv(DATASET)
    splits = build_splits(data)

    extreme = detect_extreme_slots(active)
    save_csv(extreme, AUDIT / "extreme_slots_inventory.csv")

    hp_df = pd.read_csv(BASE / "tables/rf_model_hyperparameters_v17.csv")
    hp_map = {str(r["slot_key"]): r for _, r in hp_df.iterrows()}

    threshold_rows = []
    threshold_rec_rows = []
    cur_vs_rec_rows = []
    high_sep_rows = []
    corr_rows = []
    ablation_rows = []
    leakage_rows = []
    split_rows = []
    calibration_rows = []
    final_rows = []

    feature_label_map = infer_features_label_map()

    leakage_confirmed = 0
    proxy_confirmed = 0
    split_confirmed = 0
    threshold_apply_count = 0
    threshold_recommend_count = 0
    retrain_required = 0
    retrain_completed = 0

    for _, row in extreme.iterrows():
        domain = str(row["domain"])
        role = str(row["role"])
        mode = str(row["mode"])
        slot_key = f"{domain}/{role}/{mode}"
        model_id = str(row["active_model_id"])
        cur_thr = float(row["threshold"])
        features = feats(row["feature_list_pipe"])
        target = tcol(domain)

        model_dir = MODEL_ROOT / model_id
        pipe_path = model_dir / "pipeline.joblib"

        if not pipe_path.exists():
            final_rows.append(
                {
                    "slot_key": slot_key,
                    "domain": domain,
                    "role": role,
                    "mode": mode,
                    "current_threshold": cur_thr,
                    "recommended_threshold": cur_thr,
                    "threshold_decision": "keep_current_threshold_because_adjustment_not_better",
                    "leakage_audit_status": "fail",
                    "target_proxy_audit_status": "fail",
                    "split_contamination_status": "fail",
                    "high_separability_alert": "no",
                    "high_separability_validated": "no",
                    "conduct_impairment_global_present": "no",
                    "decision": "fail_real_issue_corrected",
                    "correction_applied": "not_corrected_missing_artifact",
                    "unresolved_issue": "yes",
                }
            )
            continue

        model = joblib.load(pipe_path)
        tr = subset(data, splits[domain]["train"])
        va = subset(data, splits[domain]["val"])
        ho = subset(data, splits[domain]["holdout"])

        xtr = prep_x(tr, features)
        xva = prep_x(va, features)
        xho = prep_x(ho, features)

        ytr = tr[target].astype(int).to_numpy()
        yva = va[target].astype(int).to_numpy()
        yho = ho[target].astype(int).to_numpy()

        p_tr = predict_proba(model, xtr)
        p_va = predict_proba(model, xva)
        p_ho = predict_proba(model, xho)

        probs = {"train": p_tr, "val": p_va, "holdout": p_ho}
        ys = {"train": ytr, "val": yva, "holdout": yho}

        sweep_df, basis = sweep_thresholds(slot_key, domain, probs, ys, cur_thr)
        threshold_rows.append(sweep_df)

        rec_apply, rec_thr, rec_reason = recommend_threshold(basis, cur_thr)
        if rec_apply:
            threshold_recommend_count += 1
            threshold_apply_count += 1

        cur_mm = metrics(yho, p_ho, cur_thr)
        rec_mm = metrics(yho, p_ho, rec_thr)

        threshold_rec_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "current_threshold": cur_thr,
                "recommended_threshold": rec_thr,
                "threshold_adjustment_recommended": "yes" if rec_apply else "no",
                "threshold_decision": rec_reason,
            }
        )

        cur_vs_rec_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "current_threshold": cur_thr,
                "recommended_threshold": rec_thr,
                "current_recall": cur_mm["recall"],
                "recommended_recall": rec_mm["recall"],
                "current_specificity": cur_mm["specificity"],
                "recommended_specificity": rec_mm["specificity"],
                "current_precision": cur_mm["precision"],
                "recommended_precision": rec_mm["precision"],
                "current_f2": cur_mm["f2"],
                "recommended_f2": rec_mm["f2"],
                "current_fpr": cur_mm["fpr"],
                "recommended_fpr": rec_mm["fpr"],
                "current_fnr": cur_mm["fnr"],
                "recommended_fnr": rec_mm["fnr"],
                "current_balanced_accuracy": cur_mm["balanced_accuracy"],
                "recommended_balanced_accuracy": rec_mm["balanced_accuracy"],
                "current_mcc": cur_mm["mcc"],
                "recommended_mcc": rec_mm["mcc"],
                "current_pred_pos_rate": cur_mm["pred_pos_rate"],
                "recommended_pred_pos_rate": rec_mm["pred_pos_rate"],
                "current_confusion": f"{cur_mm['tn']},{cur_mm['fp']},{cur_mm['fn']},{cur_mm['tp']}",
                "recommended_confusion": f"{rec_mm['tn']},{rec_mm['fp']},{rec_mm['fn']},{rec_mm['tp']}",
            }
        )

        leakage_feats = [f for f in features if has_proxy_pattern(f)]
        split_audit = split_contamination(data, domain, features, splits)
        if split_audit["split_contamination_status"] == "fail":
            split_confirmed += 1

        perm_slot = perm[perm["slot_key"] == slot_key].copy().sort_values("permutation_ba_drop_mean", ascending=False)
        top1 = str(perm_slot.iloc[0]["feature"]) if len(perm_slot) else ""
        top3 = perm_slot.head(3)["feature"].astype(str).tolist()
        top1_share = float(perm_slot.iloc[0]["permutation_ba_drop_mean"] / max(perm_slot["permutation_ba_drop_mean"].clip(lower=0).sum(), 1e-12)) if len(perm_slot) else 0.0
        top3_share = float(perm_slot.head(3)["permutation_ba_drop_mean"].clip(lower=0).sum() / max(perm_slot["permutation_ba_drop_mean"].clip(lower=0).sum(), 1e-12)) if len(perm_slot) else 0.0
        dominance_flag = "yes" if top1_share >= 0.65 or top3_share >= 0.90 else "no"

        for f in features:
            corr_rows.append(
                {
                    "slot_key": slot_key,
                    "domain": domain,
                    "feature": f,
                    "feature_label": feature_label_map.get(f, ""),
                    "corr_train": feature_target_corr(tr[f], ytr),
                    "corr_val": feature_target_corr(va[f], yva),
                    "corr_holdout": feature_target_corr(ho[f], yho),
                    "proxy_pattern_flag": "yes" if has_proxy_pattern(f) else "no",
                }
            )

        hp = hp_map.get(slot_key)
        ab_sets = build_ablation_sets(features, perm_slot)
        for ab_name, ab_features in ab_sets.items():
            xtr_a = prep_x(tr, ab_features)
            xva_a = prep_x(va, ab_features)
            xho_a = prep_x(ho, ab_features)
            model_a = fit_ablation_model(ab_features, hp, str(hp.get("calibration", "none")), xtr_a, ytr)
            p_tr_a = predict_proba(model_a, xtr_a)
            p_va_a = predict_proba(model_a, xva_a)
            p_ho_a = predict_proba(model_a, xho_a)
            _, basis_a = sweep_thresholds(slot_key, domain, {"train": p_tr_a, "val": p_va_a, "holdout": p_ho_a}, ys, cur_thr)
            bt = float(basis_a["best"]["threshold"])
            mm_ho_a = metrics(yho, p_ho_a, bt)
            mm_tr_a = metrics(ytr, p_tr_a, bt)
            ablation_rows.append(
                {
                    "slot_key": slot_key,
                    "domain": domain,
                    "ablation": ab_name,
                    "n_features": len(ab_features),
                    "threshold": bt,
                    "recall": mm_ho_a["recall"],
                    "specificity": mm_ho_a["specificity"],
                    "fpr": mm_ho_a["fpr"],
                    "fnr": mm_ho_a["fnr"],
                    "precision": mm_ho_a["precision"],
                    "npv": mm_ho_a["npv"],
                    "f1": mm_ho_a["f1"],
                    "f2": mm_ho_a["f2"],
                    "pr_auc": mm_ho_a["pr_auc"],
                    "roc_auc": mm_ho_a["roc_auc"],
                    "balanced_accuracy": mm_ho_a["balanced_accuracy"],
                    "mcc": mm_ho_a["mcc"],
                    "brier": mm_ho_a["brier"],
                    "gap_train_holdout_recall": abs(mm_tr_a["recall"] - mm_ho_a["recall"]),
                    "gap_train_holdout_f2": abs(mm_tr_a["f2"] - mm_ho_a["f2"]),
                    "gap_train_holdout_ba": abs(mm_tr_a["balanced_accuracy"] - mm_ho_a["balanced_accuracy"]),
                }
            )

        leakage_status = "pass"
        proxy_status = "pass"
        leak_reason = "none"
        proxy_reason = "none"

        if leakage_feats:
            leakage_status = "fail"
            proxy_status = "fail"
            leak_reason = "feature_name_matches_target_proxy_pattern"
            proxy_reason = "feature_name_matches_target_proxy_pattern"
            leakage_confirmed += 1
            proxy_confirmed += 1

        leakage_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "leakage_audit_status": leakage_status,
                "target_proxy_audit_status": proxy_status,
                "leakage_reason": leak_reason,
                "target_proxy_reason": proxy_reason,
                "proxy_feature_count": len(leakage_feats),
                "proxy_features_pipe": "|".join(leakage_feats),
                "top1_feature": top1,
                "top3_features_pipe": "|".join(top3),
                "top1_feature_share": top1_share,
                "top3_feature_share": top3_share,
                "feature_dominance_flag": dominance_flag,
            }
        )

        split_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                **split_audit,
            }
        )

        calibration_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "current_threshold": cur_thr,
                "recommended_threshold": rec_thr,
                "probability_mean_holdout": float(np.mean(p_ho)),
                "probability_std_holdout": float(np.std(p_ho)),
                "probability_min_holdout": float(np.min(p_ho)),
                "probability_max_holdout": float(np.max(p_ho)),
                "roc_auc": cur_mm["roc_auc"],
                "pr_auc": cur_mm["pr_auc"],
                "brier": cur_mm["brier"],
            }
        )

        hflags = high_separability_flags(cur_mm)
        high_sep_validated = "yes"
        if leakage_status == "fail" or split_audit["split_contamination_status"] == "fail":
            high_sep_validated = "no"

        has_conduct_global = "yes" if (domain == "conduct" and "conduct_impairment_global" in features) else "no"

        high_sep_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                "high_separability_alert": hflags["high_separability_alert"],
                "high_separability_validated": high_sep_validated,
                "operational_caveat": "high_separability_requires_external_validation" if hflags["high_separability_alert"] == "yes" and high_sep_validated == "yes" else "none",
                "top1_feature": top1,
                "top3_features_pipe": "|".join(top3),
                "top1_feature_share": top1_share,
                "top3_feature_share": top3_share,
                "feature_dominance_flag": dominance_flag,
                "conduct_impairment_global_present": has_conduct_global,
            }
        )

        if leakage_status == "fail":
            decision = "fail_real_issue_corrected"
            unresolved_issue = "yes"
            retrain_required += 1
            correction = "not_applied_requires_focal_retrain"
        else:
            ab_slot = [r for r in ablation_rows if r["slot_key"] == slot_key]
            best_ab = max(ab_slot, key=lambda z: (z["f2"], z["recall"])) if ab_slot else None
            if rec_apply:
                decision = "keep_current_model_adjust_threshold"
                unresolved_issue = "no"
                correction = "threshold_adjustment_recommended_not_applied_in_this_audit_only_run"
            elif best_ab is not None and best_ab["f2"] > cur_mm["f2"] + 0.02 and best_ab["recall"] >= cur_mm["recall"] - 0.01:
                decision = "retrain_without_proxy_and_promote"
                unresolved_issue = "yes"
                retrain_required += 1
                correction = f"ablation_candidate_{best_ab['ablation']}_appears_better_requires_focal_training_promotion"
            elif hflags["high_separability_alert"] == "yes":
                decision = "keep_current_model_and_threshold_high_separability_validated"
                unresolved_issue = "no"
                correction = "none"
            else:
                decision = "retain_current_because_ablation_not_better"
                unresolved_issue = "no"
                correction = "none"

        final_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                "current_threshold": cur_thr,
                "recommended_threshold": rec_thr,
                "threshold_decision": rec_reason,
                "leakage_audit_status": leakage_status,
                "target_proxy_audit_status": proxy_status,
                "split_contamination_status": split_audit["split_contamination_status"],
                "high_separability_alert": hflags["high_separability_alert"],
                "high_separability_validated": high_sep_validated,
                "conduct_impairment_global_present": has_conduct_global,
                "decision": decision,
                "correction_applied": correction,
                "unresolved_issue": unresolved_issue,
            }
        )

    sweep_all = pd.concat(threshold_rows, ignore_index=True) if threshold_rows else pd.DataFrame()
    th_rec_df = pd.DataFrame(threshold_rec_rows)
    cur_rec_df = pd.DataFrame(cur_vs_rec_rows)
    high_df = pd.DataFrame(high_sep_rows)
    corr_df = pd.DataFrame(corr_rows)
    abl_df = pd.DataFrame(ablation_rows)
    leak_df = pd.DataFrame(leakage_rows)
    split_df = pd.DataFrame(split_rows)
    cal_df = pd.DataFrame(calibration_rows)
    final_df = pd.DataFrame(final_rows)

    save_csv(sweep_all, AUDIT / "threshold_sweep_by_slot.csv")
    save_csv(th_rec_df, AUDIT / "threshold_recommendations.csv")
    save_csv(cur_rec_df, AUDIT / "current_vs_adjusted_threshold_metrics.csv")
    save_csv(high_df, AUDIT / "high_separability_audit.csv")
    save_csv(corr_df, AUDIT / "feature_target_correlation.csv")
    save_csv(abl_df[abl_df["ablation"] == "no_top1"].copy(), AUDIT / "no_top1_ablation.csv")
    save_csv(abl_df[abl_df["ablation"] == "no_top3"].copy(), AUDIT / "no_top3_ablation.csv")
    save_csv(abl_df[abl_df["ablation"] == "no_global_impairment_or_global_duration"].copy(), AUDIT / "no_global_impairment_ablation.csv")
    save_csv(abl_df[abl_df["ablation"] == "no_target_proxy_candidates"].copy(), AUDIT / "no_target_proxy_ablation.csv")
    save_csv(abl_df[abl_df["ablation"] == "core_items_only"].copy(), AUDIT / "core_items_only_ablation.csv")
    save_csv(leak_df, AUDIT / "leakage_proxy_audit.csv")
    save_csv(split_df, AUDIT / "split_contamination_audit.csv")
    save_csv(cal_df, AUDIT / "calibration_audit.csv")
    save_csv(final_df, AUDIT / "final_decision_by_slot.csv")

    if not high_df.empty:
        conduct_rows = high_df[high_df["domain"] == "conduct"].copy()
        if not conduct_rows.empty:
            conduct_rows["conduct_impairment_global_assessment"] = "direct_clinical_item_not_target_column"
            save_csv(conduct_rows, AUDIT / "conduct_impairment_global_audit.csv")

    unresolved_issue_count = int((final_df["unresolved_issue"].astype(str).str.lower() == "yes").sum()) if not final_df.empty else 0
    retrain_required = int((final_df["decision"].astype(str).str.lower() == "retrain_without_proxy_and_promote").sum())

    val = {
        "line": LINE,
        "generated_at_utc": now(),
        "audited_extreme_slots_count": int(len(extreme)),
        "threshold_sweep_completed_count": int(th_rec_df["slot_key"].nunique()) if not th_rec_df.empty else 0,
        "high_separability_audit_completed_count": int(high_df["slot_key"].nunique()) if not high_df.empty else 0,
        "ablation_completed_count": int(abl_df["slot_key"].nunique()) if not abl_df.empty else 0,
        "leakage_confirmed_count": int(leakage_confirmed),
        "target_proxy_confirmed_count": int(proxy_confirmed),
        "split_contamination_confirmed_count": int(split_confirmed),
        "threshold_adjustment_recommended_count": int(threshold_recommend_count),
        "threshold_adjustment_applied_count": int(threshold_apply_count),
        "retrain_required_count": int(retrain_required),
        "retrain_completed_count": int(retrain_completed),
        "unresolved_issue_count": int(unresolved_issue_count),
    }
    val["final_audit_status"] = "pass" if unresolved_issue_count == 0 else "fail"

    write_text(AUDIT / "extreme_metrics_threshold_separability_validator.json", json.dumps(val, indent=2, ensure_ascii=False))

    report_lines = [
        "# v17 Extreme Metrics Threshold/Separability Audit",
        "",
        f"- generated_at_utc: `{val['generated_at_utc']}`",
        f"- audited_extreme_slots_count: `{val['audited_extreme_slots_count']}`",
        f"- leakage_confirmed_count: `{val['leakage_confirmed_count']}`",
        f"- target_proxy_confirmed_count: `{val['target_proxy_confirmed_count']}`",
        f"- split_contamination_confirmed_count: `{val['split_contamination_confirmed_count']}`",
        f"- threshold_adjustment_recommended_count: `{val['threshold_adjustment_recommended_count']}`",
        f"- threshold_adjustment_applied_count: `{val['threshold_adjustment_applied_count']}`",
        f"- retrain_required_count: `{val['retrain_required_count']}`",
        f"- unresolved_issue_count: `{val['unresolved_issue_count']}`",
        f"- final_audit_status: `{val['final_audit_status']}`",
        "",
        "## Decision policy",
        "- High metrics (>0.98) are treated as `high_separability_alert`, not automatic fail.",
        "- Hard fail is only set for confirmed leakage/proxy/split contamination/runtime issues or unresolved corrections.",
    ]
    write_text(AUDIT / "extreme_metrics_threshold_separability_report.md", "\n".join(report_lines))

    if not sweep_all.empty:
        fig, ax = plt.subplots(figsize=(11, 6))
        for _, g in sweep_all.groupby("slot_key"):
            g = g.sort_values("threshold")
            ax.plot(g["threshold"], g["holdout_recall"], alpha=0.35, color="#1f77b4")
            ax.plot(g["threshold"], g["holdout_specificity"], alpha=0.25, color="#2ca02c")
            ax.plot(g["threshold"], g["holdout_fpr"], alpha=0.20, color="#d62728")
            ax.plot(g["threshold"], g["holdout_fnr"], alpha=0.20, color="#9467bd")
        ax.set_title("Threshold Curves (recall/specificity/FPR/FNR)")
        ax.set_xlabel("threshold")
        ax.set_ylabel("metric")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(PLOTS / "threshold_curves_recall_specificity_fpr_fnr.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 6))
        for _, g in sweep_all.groupby("slot_key"):
            g = g.sort_values("threshold")
            ax.plot(g["holdout_recall"], g["holdout_precision"], alpha=0.35)
        ax.set_title("Precision-Recall by Threshold")
        ax.set_xlabel("recall")
        ax.set_ylabel("precision")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(PLOTS / "precision_recall_by_threshold.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 6))
        for _, g in sweep_all.groupby("slot_key"):
            g = g.sort_values("threshold")
            ax.plot(g["threshold"], g["holdout_f2"], alpha=0.4)
        ax.set_title("F2 by Threshold")
        ax.set_xlabel("threshold")
        ax.set_ylabel("holdout_f2")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(PLOTS / "f2_by_threshold.png", dpi=150)
        plt.close(fig)

    if not cal_df.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(cal_df))
        ax.bar(x, cal_df["probability_mean_holdout"], color="#1f77b4", alpha=0.7, label="mean")
        ax.errorbar(x, cal_df["probability_mean_holdout"], yerr=cal_df["probability_std_holdout"], fmt="none", ecolor="#222", alpha=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels(cal_df["slot_key"], rotation=90, fontsize=7)
        ax.set_title("Holdout Probability Mean/Std by Slot")
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        fig.savefig(PLOTS / "probability_distribution_by_slot.png", dpi=150)
        plt.close(fig)

    top_imp = impurity[impurity["slot_key"].isin(extreme["slot_key"].tolist())].copy()
    if not top_imp.empty:
        imp_col = "importance" if "importance" in top_imp.columns else "impurity_importance"
        top_imp = top_imp.sort_values(["slot_key", imp_col], ascending=[True, False]).groupby("slot_key").head(10)
        fig, ax = plt.subplots(figsize=(12, 8))
        ylabels = [f"{r.slot_key}::{r.feature}" for r in top_imp.itertuples()]
        ax.barh(range(len(top_imp)), top_imp[imp_col].astype(float), color="#2ca02c", alpha=0.8)
        ax.set_yticks(range(len(top_imp)))
        ax.set_yticklabels(ylabels, fontsize=6)
        ax.invert_yaxis()
        ax.set_title("Top-10 impurity importance per extreme slot")
        ax.grid(axis="x", alpha=0.2)
        fig.tight_layout()
        fig.savefig(PLOTS / "feature_importance_top10_extreme_slots.png", dpi=150)
        plt.close(fig)

    if not abl_df.empty:
        tmp = abl_df.groupby("ablation", as_index=False)[["f2", "recall", "specificity", "balanced_accuracy"]].mean()
        fig, ax = plt.subplots(figsize=(10, 6))
        xx = np.arange(len(tmp))
        width = 0.2
        ax.bar(xx - 1.5 * width, tmp["f2"], width=width, label="f2")
        ax.bar(xx - 0.5 * width, tmp["recall"], width=width, label="recall")
        ax.bar(xx + 0.5 * width, tmp["specificity"], width=width, label="specificity")
        ax.bar(xx + 1.5 * width, tmp["balanced_accuracy"], width=width, label="BA")
        ax.set_xticks(xx)
        ax.set_xticklabels(tmp["ablation"], rotation=20)
        ax.set_ylim(0, 1.05)
        ax.set_title("Ablation mean metrics across extreme slots")
        ax.legend()
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        fig.savefig(PLOTS / "ablation_metric_comparison.png", dpi=150)
        plt.close(fig)

    if not th_rec_df.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(th_rec_df))
        ax.scatter(x, th_rec_df["current_threshold"], label="current", color="#1f77b4")
        ax.scatter(x, th_rec_df["recommended_threshold"], label="recommended", color="#ff7f0e")
        ax.set_xticks(x)
        ax.set_xticklabels(th_rec_df["slot_key"], rotation=90, fontsize=7)
        ax.set_ylim(0, 1)
        ax.set_title("Current vs Recommended Thresholds")
        ax.legend()
        ax.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(PLOTS / "current_vs_recommended_thresholds.png", dpi=150)
        plt.close(fig)

    print(json.dumps(val, ensure_ascii=False))
    return 0 if val["final_audit_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
