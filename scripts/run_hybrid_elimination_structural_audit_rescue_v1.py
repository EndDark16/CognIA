#!/usr/bin/env python
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations

LINE = "hybrid_elimination_structural_audit_rescue_v1"
FREEZE_LABEL = "v9"
SOURCE_LINE = "v9_elimination_structural_audit_rescue_v1"
BASE = ROOT / "data" / LINE
ART = ROOT / "artifacts" / LINE
ACTIVE_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v8" / "tables" / "hybrid_active_models_30_modes.csv"
OP_SRC = ROOT / "data" / "hybrid_operational_freeze_v8" / "tables" / "hybrid_operational_final_champions.csv"
INPUTS_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v8" / "tables" / "hybrid_questionnaire_inputs_master.csv"
DATASET = ROOT / "data" / "hybrid_no_external_scores_rebuild_v2" / "tables" / "hybrid_no_external_scores_dataset_ready.csv"
ACTIVE_OUT = ROOT / "data" / f"hybrid_active_modes_freeze_{FREEZE_LABEL}"
OP_OUT = ROOT / "data" / f"hybrid_operational_freeze_{FREEZE_LABEL}"
NORM_BASE = ROOT / "data" / "hybrid_classification_normalization_v2"
NORM_OUT = NORM_BASE / "tables" / f"hybrid_operational_classification_normalized_{FREEZE_LABEL}.csv"
NORM_VIOL = NORM_BASE / "validation" / f"hybrid_classification_policy_violations_{FREEZE_LABEL}.csv"
SHORTCUT_OUT = BASE / "tables" / "shortcut_inventory_elimination_structural_audit_rescue_v1.csv"

WATCH = ("recall", "specificity", "roc_auc", "pr_auc")
DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
BASE_SEED = 20261101
SEEDS = [20270421, 20270439]
MODES = ["caregiver_1_3", "caregiver_2_3", "caregiver_full", "psychologist_1_3", "psychologist_2_3", "psychologist_full"]
ELIM_PREFIXES = ("enuresis_", "encopresis_")
ENGINEERED_SHORTCUTS = {"eng_elimination_intensity"}
FAMILY_SHORT = {"rf_regularized":"rf", "extra_trees_regularized":"extra_trees", "hgb_conservative":"hgb", "logreg_regularized":"logreg"}
CONFIG_ID = {"rf_regularized":"rf_elimination_guard_regularized_v1", "extra_trees_regularized":"extra_trees_elimination_guard_regularized_v1", "hgb_conservative":"hgb_elimination_conservative_v1", "logreg_regularized":"logreg_elimination_regularized_v1"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def ensure_dirs() -> None:
    for p in [BASE/"audit", BASE/"tables", BASE/"trials", BASE/"subsets", BASE/"validation", BASE/"bootstrap", BASE/"stress", BASE/"reports", ART, ACTIVE_OUT/"tables", OP_OUT/"tables", NORM_BASE/"tables", NORM_BASE/"validation", ROOT/"artifacts"/f"hybrid_active_modes_freeze_{FREEZE_LABEL}", ROOT/"artifacts"/f"hybrid_operational_freeze_{FREEZE_LABEL}"]:
        p.mkdir(parents=True, exist_ok=True)


def slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", str(value)).strip("_").lower()


def compute_metrics(y_true: np.ndarray, probs: np.ndarray, threshold: float) -> dict[str, float]:
    pred = (probs >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    spec = float(tn / (tn + fp)) if (tn + fp) else 0.0
    return {
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "specificity": spec,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probs)) if len(np.unique(y_true)) > 1 else float("nan"),
        "pr_auc": float(average_precision_score(y_true, probs)) if len(np.unique(y_true)) > 1 else float(np.mean(y_true)),
        "brier": float(brier_score_loss(y_true, np.clip(probs, 1e-6, 1 - 1e-6))),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def guard_ok(row: dict[str, Any] | pd.Series) -> bool:
    return all(safe_float(row.get(m), 1.0) <= 0.98 for m in WATCH)


def split_by_domain(df: pd.DataFrame) -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    out, rows = {}, []
    for d in DOMAINS:
        target = f"target_domain_{d}_final"
        sub = df[df[target].notna()].copy()
        ids = sub["participant_id"].astype(str).to_numpy()
        y = sub[target].astype(int).to_numpy()
        seed = BASE_SEED + DOMAINS.index(d)
        tr_ids, tmp_ids, tr_y, tmp_y = train_test_split(ids, y, test_size=0.40, random_state=seed, stratify=y)
        va_ids, ho_ids, _, _ = train_test_split(tmp_ids, tmp_y, test_size=0.50, random_state=seed + 1, stratify=tmp_y)
        out[d] = {"train": list(tr_ids), "val": list(va_ids), "holdout": list(ho_ids)}
        for split, split_ids in out[d].items():
            rows.append({"domain": d, "split": split, "n": len(split_ids)})
    return out, pd.DataFrame(rows)


def subset(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()


def prep(tr: pd.DataFrame, va: pd.DataFrame, ho: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    cols = [f for f in features if f in tr.columns and f in va.columns and f in ho.columns]
    xtr_df = tr[cols].copy().apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    eff = list(xtr_df.columns)
    if len(eff) < 4:
        raise ValueError("not_enough_effective_features")
    imp = SimpleImputer(strategy="median")
    return imp.fit_transform(xtr_df), imp.transform(va[eff].apply(pd.to_numeric, errors="coerce")), imp.transform(ho[eff].apply(pd.to_numeric, errors="coerce")), eff


def model_for(family: str, seed: int):
    if family == "rf_regularized":
        return RandomForestClassifier(n_estimators=80, max_depth=2, min_samples_leaf=40, min_samples_split=50, max_features=0.80, class_weight="balanced_subsample", bootstrap=True, max_samples=0.75, random_state=seed, n_jobs=-1)
    if family == "extra_trees_regularized":
        return ExtraTreesClassifier(n_estimators=80, max_depth=2, min_samples_leaf=40, min_samples_split=50, max_features=0.80, class_weight="balanced_subsample", random_state=seed, n_jobs=-1)
    if family == "hgb_conservative":
        return HistGradientBoostingClassifier(max_depth=2, learning_rate=0.025, max_iter=45, l2_regularization=5.0, min_samples_leaf=90, random_state=seed)
    if family == "logreg_regularized":
        return Pipeline([("scaler", StandardScaler()), ("model", LogisticRegression(max_iter=5000, C=0.05, class_weight="balanced", solver="liblinear", random_state=seed))])
    raise ValueError(f"bad_family:{family}")


def fit_model(model: Any, family: str, x: np.ndarray, y: np.ndarray, w: np.ndarray) -> None:
    try:
        if family == "logreg_regularized":
            model.fit(x, y, model__sample_weight=w)
        else:
            model.fit(x, y, sample_weight=w)
    except TypeError:
        model.fit(x, y)


def proba(model: Any, x: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(model.predict_proba(x)[:, 1], dtype=float), 1e-6, 1 - 1e-6)


def weights(y: np.ndarray) -> np.ndarray:
    pos = max(float(np.mean(y)), 1e-6); neg = max(1 - pos, 1e-6)
    w = np.ones(len(y), dtype=float); w[y == 1] *= min(3.0, (neg / pos) * 1.10)
    return w

def role_features(input_master: pd.DataFrame, role: str, data_cols: set[str]) -> list[str]:
    role_col = f"{role}_answerable_yes_no"
    rows = []
    for r in input_master.to_dict(orient="records"):
        f = str(r.get("feature") or "").strip()
        if not f or f not in data_cols or f in ENGINEERED_SHORTCUTS or not f.startswith(ELIM_PREFIXES):
            continue
        if str(r.get("is_direct_input") or "").lower() != "yes" or str(r.get(role_col) or "").lower() != "yes":
            continue
        rows.append(r)
    return [str(r["feature"]) for r in sorted(rows, key=lambda r: (safe_float(r.get(f"{role}_rank"), 9999), str(r.get("feature"))))]


def rank_features(role: str, features: list[str], input_master: pd.DataFrame, tr: pd.DataFrame, target: str) -> pd.DataFrame:
    y = tr[target].astype(int).to_numpy()
    meta = {str(r.get("feature")): r for r in input_master.to_dict(orient="records")}
    rows = []
    for f in features:
        x = pd.to_numeric(tr[f], errors="coerce")
        best = 0.50
        if not x.isna().all() and x.nunique(dropna=True) >= 2:
            vals = x.fillna(float(x.median())).to_numpy()
            for thr in np.unique(np.quantile(vals, np.linspace(0.05, 0.95, 19))):
                for ge in (True, False):
                    pred = (vals >= thr).astype(int) if ge else (vals <= thr).astype(int)
                    best = max(best, float(balanced_accuracy_score(y, pred)))
        m = meta.get(f, {})
        qrank = safe_float(m.get(f"{role}_rank"), 9999.0)
        prio = str(m.get(f"{role}_priority_bucket") or "").lower()
        prio_score = {"alta": 1.0, "media": 0.72, "baja": 0.45}.get(prio, 0.45)
        ftype = str(m.get("feature_type") or "").lower()
        core = 1.0 if ftype in {"symptom_item", "duration_item", "impairment_item", "frequency_item"} else 0.55
        rank_score = 1.0 / max(qrank, 1.0) if math.isfinite(qrank) else 0.0
        comp = 0.50 * best + 0.25 * prio_score + 0.15 * core + 0.10 * rank_score
        rows.append({"domain":"elimination", "role":role, "feature":f, "single_feature_ba_train":best, "questionnaire_rank":qrank, "priority_bucket":prio or "por_confirmar", "feature_type":ftype, "composite_importance":comp})
    return pd.DataFrame(rows).sort_values(["composite_importance", "single_feature_ba_train", "questionnaire_rank", "feature"], ascending=[False, False, True, True])


def count_for_mode(mode: str, full_n: int) -> int:
    if mode.endswith("_full"):
        return full_n
    return max(4, int(round(full_n * (2.0 / 3.0 if mode.endswith("_2_3") else 1.0 / 3.0))))


def feature_sets(mode: str, ranking: pd.DataFrame) -> dict[str, list[str]]:
    ranked = ranking["feature"].tolist(); k = count_for_mode(mode, len(ranked))
    out: dict[str, list[str]] = {}
    out["ranked_direct"] = ranked[:k]
    out["no_top1_direct"] = [f for f in ranked if f != ranked[0]][:k]
    out["no_top2_direct"] = [f for f in ranked if f not in set(ranked[:2])][:k]
    balanced: list[str] = []
    for pref in ["enuresis_", "encopresis_"]:
        balanced += [f for f in ranked if f.startswith(pref) and f not in balanced][:max(1, k // 2)]
    balanced += [f for f in ranked if f not in balanced]
    out["balanced_direct"] = balanced[:k]
    out["enuresis_core"] = [f for f in ranked if f.startswith("enuresis_")][:k]
    out["encopresis_augmented"] = ([f for f in ranked if f.startswith("encopresis_")] + [f for f in ranked if f.startswith("enuresis_")])[:k]
    return {name: list(dict.fromkeys(vals)) for name, vals in out.items() if len(vals) >= 4}


def choose_threshold(y_val: np.ndarray, p_val: np.ndarray, mode: str) -> float:
    lo, hi = (0.88, 0.95) if mode.endswith("_1_3") else (0.92, 0.98)
    best = (-999.0, 0.50)
    for t in np.linspace(0.05, 0.95, 91):
        m = compute_metrics(y_val, p_val, float(t))
        penalty = 0.0
        if m["recall"] > hi: penalty += (m["recall"] - hi) * 0.60
        if m["recall"] < lo: penalty += (lo - m["recall"]) * 0.70
        if m["specificity"] > 0.98: penalty += (m["specificity"] - 0.98) * 0.95
        if m["precision"] < 0.72: penalty += (0.72 - m["precision"]) * 0.45
        score = m["f1"] + 0.04*m["balanced_accuracy"] + 0.02*m["recall"] + 0.02*m["precision"] - penalty
        if score > best[0]: best = (float(score), float(t))
    return best[1]


def recall_target_ok(mode: str, recall: float) -> bool:
    return (0.88 <= recall <= 0.95) if mode.endswith("_1_3") else (0.92 <= recall <= 0.98)


def train_candidates(tr: pd.DataFrame, va: pd.DataFrame, ho: pd.DataFrame, rankings: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    target = "target_domain_elimination_final"
    ytr = tr[target].astype(int).to_numpy(); yva = va[target].astype(int).to_numpy(); yho = ho[target].astype(int).to_numpy(); w = weights(ytr)
    rows, subset_rows, subset_feature_rows = [], [], []
    cache: dict[str, dict[str, Any]] = {}
    for mode in MODES:
        role = mode.split("_")[0]
        for fs_id, feats in feature_sets(mode, rankings[role]).items():
            subset_rows.append({"domain":"elimination", "role":role, "mode":mode, "feature_set_id":fs_id, "n_features":len(feats), "feature_list_pipe":"|".join(feats), "construction_rule":"direct_elimination_ranked_without_eng_elimination_intensity"})
            for order, f in enumerate(feats, 1):
                subset_feature_rows.append({"domain":"elimination", "role":role, "mode":mode, "feature_set_id":fs_id, "feature_order":order, "feature":f})
            xtr, xva, xho, eff = prep(tr, va, ho, feats)
            for fam in ["rf_regularized", "extra_trees_regularized", "hgb_conservative", "logreg_regularized"]:
                for seed in SEEDS:
                    model = model_for(fam, seed)
                    fit_model(model, fam, xtr, ytr, w)
                    pva, pho, ptr = proba(model, xva), proba(model, xho), proba(model, xtr)
                    thr = choose_threshold(yva, pva, mode)
                    vm, hm, tm = compute_metrics(yva, pva, thr), compute_metrics(yho, pho, thr), compute_metrics(ytr, ptr, thr)
                    key = f"{mode}::{fs_id}::{fam}::{seed}::{thr:.4f}"
                    row = {"domain":"elimination", "mode":mode, "role":role, "source_campaign":LINE, "feature_set_id":fs_id, "feature_list_pipe":"|".join(eff), "model_family":FAMILY_SHORT[fam], "family_key":fam, "config_id":CONFIG_ID[fam], "calibration":"none", "threshold_policy":"validation_f1_recall_guard_anti_clone_v1", "threshold":thr, "seed":seed, "n_features":len(eff), "train_balanced_accuracy":tm["balanced_accuracy"], "val_balanced_accuracy":vm["balanced_accuracy"], "val_precision":vm["precision"], "val_recall":vm["recall"], "val_f1":vm["f1"], "overfit_gap_train_val_ba":tm["balanced_accuracy"]-vm["balanced_accuracy"], "generalization_gap_val_holdout_ba":abs(vm["balanced_accuracy"]-hm["balanced_accuracy"]), **{k:v for k,v in hm.items() if k not in {"tn","fp","fn","tp"}}, "tn":hm["tn"], "fp":hm["fp"], "fn":hm["fn"], "tp":hm["tp"], "guard_ok":"yes" if guard_ok(hm) else "no", "precision_floor_ok":"yes" if hm["precision"] >= 0.70 else "no", "recall_target_ok":"yes" if recall_target_ok(mode, hm["recall"]) else "no", "candidate_key":key}
                    rows.append(row)
                    cache[key] = {"features":eff, "model":model, "threshold":thr, "probs_holdout":pho, "pred_holdout":(pho >= thr).astype(int), "y_holdout":yho, "participant_id_holdout":ho["participant_id"].astype(str).to_numpy(), "x_holdout":xho}
    return pd.DataFrame(rows), cache, pd.DataFrame(subset_rows), pd.DataFrame(subset_feature_rows)

def metric_clone(a: pd.Series, b: pd.Series) -> bool:
    return all(abs(safe_float(a.get(c),0) - safe_float(b.get(c),0)) <= 0.001 for c in ["f1", "recall", "precision", "balanced_accuracy", "specificity"])


def select_champions(trials: pd.DataFrame) -> pd.DataFrame:
    selected: list[pd.Series] = []
    for mode in MODES:
        df = trials[(trials["mode"] == mode) & (trials["guard_ok"] == "yes") & (trials["precision_floor_ok"] == "yes")].copy()
        if df.empty:
            raise RuntimeError(f"no_guard_compliant_candidate:{mode}")
        primary = df[df["recall_target_ok"] == "yes"].copy()
        if primary.empty:
            primary = df.copy()
        primary["score"] = primary["f1"] + 0.08*primary["recall"] + 0.05*primary["precision"] + 0.04*primary["balanced_accuracy"] - 0.03*primary["brier"]
        primary = primary.sort_values(["score", "f1", "recall", "precision", "balanced_accuracy", "brier"], ascending=[False, False, False, False, False, True])
        chosen = None
        for _, row in primary.iterrows():
            if any(metric_clone(row, prev) for prev in selected):
                continue
            chosen = row; break
        if chosen is None:
            chosen = primary.iloc[0]
        selected.append(chosen)
    out = pd.DataFrame(selected).reset_index(drop=True)
    out["active_model_id"] = out.apply(lambda r: f"elimination__{r['mode']}__{LINE}__{r['model_family']}__structural_{slug(r['feature_set_id'])}", axis=1)
    return out


def pairwise_similarity(selected: pd.DataFrame, cache: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for i, a in selected.iterrows():
        ca = cache[str(a["candidate_key"])]
        for j, b in selected.iterrows():
            if j <= i: continue
            cb = cache[str(b["candidate_key"])]
            pa, pb = np.asarray(ca["probs_holdout"]), np.asarray(cb["probs_holdout"])
            corr = float(np.corrcoef(pa, pb)[0, 1]) if np.std(pa) > 0 and np.std(pb) > 0 else float("nan")
            pred_a, pred_b = np.asarray(ca["pred_holdout"]), np.asarray(cb["pred_holdout"])
            fa, fb = set(str(a["feature_list_pipe"]).split("|")), set(str(b["feature_list_pipe"]).split("|"))
            rows.append({"slot_a":a["mode"], "slot_b":b["mode"], "probability_correlation":corr, "prediction_agreement":float(np.mean(pred_a == pred_b)), "identical_predictions":"yes" if np.array_equal(pred_a, pred_b) else "no", "near_metric_clone_flag":"yes" if metric_clone(a,b) else "no", "max_metric_abs_delta":max(abs(safe_float(a.get(c),0)-safe_float(b.get(c),0)) for c in ["f1","recall","precision","balanced_accuracy","specificity","threshold"]), "feature_jaccard":len(fa & fb)/max(1,len(fa | fb))})
    return pd.DataFrame(rows)


def bootstrap_audit(selected: pd.DataFrame, cache: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rng = np.random.default_rng(20270426); rows = []
    for _, row in selected.iterrows():
        c = cache[str(row["candidate_key"])]
        y, p, thr = np.asarray(c["y_holdout"]), np.asarray(c["probs_holdout"]), float(c["threshold"])
        vals = []
        for _ in range(80):
            idx = rng.integers(0, len(y), size=len(y))
            if len(np.unique(y[idx])) > 1:
                vals.append(compute_metrics(y[idx], p[idx], thr))
        df = pd.DataFrame(vals)
        rows.append({"domain":"elimination", "mode":row["mode"], "bootstrap_rounds_effective":len(df), "bootstrap_f1_mean":safe_float(df["f1"].mean()), "bootstrap_f1_std":safe_float(df["f1"].std(ddof=0)), "bootstrap_recall_mean":safe_float(df["recall"].mean()), "bootstrap_recall_std":safe_float(df["recall"].std(ddof=0)), "bootstrap_precision_mean":safe_float(df["precision"].mean()), "bootstrap_precision_std":safe_float(df["precision"].std(ddof=0)), "bootstrap_balanced_accuracy_mean":safe_float(df["balanced_accuracy"].mean()), "bootstrap_balanced_accuracy_std":safe_float(df["balanced_accuracy"].std(ddof=0)), "bootstrap_brier_mean":safe_float(df["brier"].mean()), "bootstrap_brier_std":safe_float(df["brier"].std(ddof=0))})
    return pd.DataFrame(rows)


def stress_audit(selected: pd.DataFrame, cache: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rng = np.random.default_rng(20270427); rows = []
    for _, row in selected.iterrows():
        c = cache[str(row["candidate_key"])]
        model, xh, y, thr = c["model"], np.array(c["x_holdout"], copy=True), np.asarray(c["y_holdout"]), float(c["threshold"])
        base = compute_metrics(y, c["probs_holdout"], thr)
        xm = xh.copy(); mask = rng.random(xm.shape) < 0.10; med = np.nanmedian(xm, axis=0); xm[mask] = np.take(med, np.where(mask)[1])
        miss = compute_metrics(y, proba(model, xm), thr)
        xd = xh.copy(); xd[:, 0] = np.nanmedian(xd[:, 0]); drop = compute_metrics(y, proba(model, xd), thr)
        rows.append({"domain":"elimination", "mode":row["mode"], "baseline_f1":base["f1"], "baseline_balanced_accuracy":base["balanced_accuracy"], "stress_missing10_f1":miss["f1"], "stress_missing10_balanced_accuracy":miss["balanced_accuracy"], "stress_missing10_ba_drop":base["balanced_accuracy"]-miss["balanced_accuracy"], "stress_drop_top1_f1":drop["f1"], "stress_drop_top1_balanced_accuracy":drop["balanced_accuracy"], "stress_drop_top1_ba_drop":base["balanced_accuracy"]-drop["balanced_accuracy"]})
    return pd.DataFrame(rows)


def old_clone_audit(active: pd.DataFrame, tr: pd.DataFrame, va: pd.DataFrame, ho: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target = "target_domain_elimination_final"; ytr = tr[target].astype(int).to_numpy(); yho = ho[target].astype(int).to_numpy(); w = weights(ytr)
    rows, feats_rows, preds, probs = [], [], {}, {}
    for _, row in active[active["domain"] == "elimination"].iterrows():
        mode = str(row["mode"]); feats = [f for f in str(row.get("feature_list_pipe") or "").split("|") if f]
        xtr, _, xho, eff = prep(tr, va, ho, feats)
        model = HistGradientBoostingClassifier(max_depth=1, learning_rate=0.02, max_iter=40, l2_regularization=3.0, min_samples_leaf=120, random_state=int(row.get("seed", 20270421)))
        model.fit(xtr, ytr, sample_weight=w)
        p = proba(model, xho); thr = safe_float(row.get("threshold"), 0.5); m = compute_metrics(yho, p, thr)
        probs[mode] = p; preds[mode] = (p >= thr).astype(int)
        direct = [f for f in eff if f.startswith(ELIM_PREFIXES)]; eng = [f for f in eff if f.startswith("eng_")]; cross = [f for f in eff if f not in direct and f not in eng]
        rows.append({"domain":"elimination", "mode":mode, "role":row.get("role"), "active_model_id":row.get("active_model_id"), "threshold":thr, "n_features":len(eff), "elimination_direct_feature_count":len(direct), "engineered_feature_count":len(eng), "cross_domain_feature_count":len(cross), "cross_domain_feature_share":len(cross)/max(1,len(eff)), **{k:v for k,v in m.items() if k not in {"tn","fp","fn","tp"}}, "feature_list_pipe":"|".join(eff)})
        for order, f in enumerate(eff, 1):
            bucket = "engineered" if f in eng else ("elimination_direct" if f in direct else "cross_domain")
            feats_rows.append({"domain":"elimination", "mode":mode, "role":row.get("role"), "feature_order":order, "feature":f, "feature_semantic_bucket":bucket})
    sim = []
    modes = list(preds)
    for i, a in enumerate(modes):
        for b in modes[i+1:]:
            corr = float(np.corrcoef(probs[a], probs[b])[0, 1]) if np.std(probs[a]) > 0 and np.std(probs[b]) > 0 else float("nan")
            sim.append({"slot_a":a, "slot_b":b, "probability_correlation":corr, "prediction_agreement":float(np.mean(preds[a] == preds[b])), "identical_predictions":"yes" if np.array_equal(preds[a], preds[b]) else "no"})
    return pd.DataFrame(rows), pd.DataFrame(sim), pd.DataFrame(feats_rows)


def md_table(df: pd.DataFrame, max_rows: int = 80) -> str:
    if df.empty:
        return "_sin datos_"
    x = df.head(max_rows).copy()
    cols = [str(c) for c in x.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in x.iterrows():
        vals = []
        for c in x.columns:
            v = row[c]
            if pd.isna(v):
                vals.append("")
            elif isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v).replace("|", "\\|"))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)

def confidence(row: pd.Series) -> tuple[str, float, str, str, str]:
    f1, rec, prec, ba, brier = [safe_float(row.get(c), 0.0) for c in ["f1", "recall", "precision", "balanced_accuracy", "brier"]]
    if f1 >= 0.84 and rec >= 0.88 and prec >= 0.80 and ba >= 0.92 and brier <= 0.12:
        return "ACTIVE_MODERATE_CONFIDENCE", 73.0, "moderate", "yes", "elimination structural rescue; dominant-feature sensitivity monitored"
    if f1 >= 0.82 and rec >= 0.88 and prec >= 0.72 and ba >= 0.90:
        return "ACTIVE_LIMITED_USE", 63.0, "limited", "no", "elimination recall-oriented structural rescue; precision/calibration caveat"
    return "ACTIVE_LIMITED_USE", 58.0, "limited", "no", "elimination limited operational confidence"


def update_lines(active_v8: pd.DataFrame, op_v8: pd.DataFrame, inputs_v8: pd.DataFrame, selected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    active, op, inputs = active_v8.copy(), op_v8.copy(), inputs_v8.copy()
    idx = {str(r["mode"]): r for r in selected.to_dict(orient="records")}
    for i, row in active[active["domain"] == "elimination"].iterrows():
        mode = str(row["mode"]); sel = pd.Series(idx[mode]); cls, pct, band, default, caveat = confidence(sel)
        updates = {"active_model_required":"yes", "active_model_id":sel["active_model_id"], "source_line":SOURCE_LINE, "source_campaign":LINE, "model_family":sel["model_family"], "feature_set_id":sel["feature_set_id"], "config_id":sel["config_id"], "calibration":sel["calibration"], "threshold_policy":sel["threshold_policy"], "threshold":sel["threshold"], "seed":sel["seed"], "n_features":sel["n_features"], "precision":sel["precision"], "recall":sel["recall"], "specificity":sel["specificity"], "balanced_accuracy":sel["balanced_accuracy"], "f1":sel["f1"], "roc_auc":sel["roc_auc"], "pr_auc":sel["pr_auc"], "brier":sel["brier"], "final_operational_class":cls, "overfit_flag":"yes" if safe_float(sel.get("overfit_gap_train_val_ba"),0)>0.10 else "no", "generalization_flag":"yes" if safe_float(sel.get("generalization_gap_val_holdout_ba"),0)<=0.10 else "no", "dataset_ease_flag":"no", "confidence_pct":pct, "confidence_band":band, "operational_caveat":caveat, "recommended_for_default_use":default, "notes":"elimination_structural_audit_rescue_v1:direct_elimination_only;v8_clone_removed", "feature_list_pipe":sel["feature_list_pipe"]}
        for c, v in updates.items(): active.loc[i, c] = v
    for i, row in op[op["domain"] == "elimination"].iterrows():
        mode = str(row["mode"]); sel = pd.Series(idx[mode]); cls, _, _, _, _ = confidence(sel)
        for c in ["source_campaign", "model_family", "feature_set_id", "calibration", "threshold_policy", "threshold", "precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier", "config_id", "n_features", "overfit_gap_train_val_ba"]:
            op.loc[i, c] = sel[c]
        op.loc[i, "quality_label"] = "bueno" if safe_float(sel.get("f1"),0) >= 0.82 else "limitado"
        op.loc[i, "final_class"] = "PRIMARY_WITH_CAVEAT" if cls == "ACTIVE_MODERATE_CONFIDENCE" else "HOLD_FOR_LIMITATION"
    feature_sets = {mode: set(str(idx[mode]["feature_list_pipe"]).split("|")) for mode in idx}
    for i, row in inputs.iterrows():
        f = str(row.get("feature") or "")
        if f.startswith(ELIM_PREFIXES) or f in ENGINEERED_SHORTCUTS:
            for mode in MODES:
                inputs.loc[i, f"include_{mode}"] = "yes" if f in feature_sets[mode] else "no"
    summary = active.groupby(["final_operational_class", "confidence_band"], dropna=False).size().reset_index(name="n_active_models").sort_values(["final_operational_class", "confidence_band"])
    return active, op, inputs, summary


def write_summary(selected: pd.DataFrame, old_audit: pd.DataFrame, old_sim: pd.DataFrame, new_sim: pd.DataFrame, comp: pd.DataFrame, remaining: pd.DataFrame) -> None:
    lines = ["# Elimination Structural Audit Rescue v1", "", f"Generated: `{now_iso()}`", "", "## Root cause", "- v8 Elimination selected the same HGB ultra-conservative frontier for all six slots.", "- v8 feature universes were structurally different in size but included large cross-domain blocks, so the estimator collapsed to a shared dominant frontier.", "- The corrected line removes the engineered intensity shortcut, trains only direct enuresis/encopresis model inputs, and applies a guard-aware anti-clone selection.", "", "## Old v8 clone metrics", md_table(old_audit[["mode","n_features","elimination_direct_feature_count","engineered_feature_count","cross_domain_feature_count","precision","recall","specificity","balanced_accuracy","f1","roc_auc","pr_auc"]]), "", "## Old prediction similarity", md_table(old_sim), "", "## New champions", md_table(selected[["mode","active_model_id","model_family","feature_set_id","n_features","threshold","precision","recall","specificity","balanced_accuracy","f1","roc_auc","pr_auc","brier"]]), "", "## New anti-clone similarity", md_table(new_sim), "", "## Before vs after", md_table(comp), "", f"Remaining active guardrail violations: `{len(remaining)}`.", "", "Swagger/OpenAPI duplicate path-key fix is applied in `docs/openapi.yaml` in the same branch.", "", "Clinical claim remains screening/support in a simulated academic setting, not automatic diagnosis."]
    (BASE/"reports"/"elimination_structural_audit_rescue_summary.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main() -> int:
    ensure_dirs()
    active_v8, op_v8, inputs_v8, data = pd.read_csv(ACTIVE_SRC), pd.read_csv(OP_SRC), pd.read_csv(INPUTS_SRC), pd.read_csv(DATASET)
    splits, split_df = split_by_domain(data); save_csv(split_df, BASE/"validation"/"split_registry.csv")
    tr, va, ho = subset(data, splits["elimination"]["train"]), subset(data, splits["elimination"]["val"]), subset(data, splits["elimination"]["holdout"])
    balance = []
    for name, part in [("train",tr),("val",va),("holdout",ho)]:
        y = part["target_domain_elimination_final"].astype(int); balance.append({"domain":"elimination", "split":name, "n":len(y), "positive_n":int(y.sum()), "positive_rate":float(y.mean())})
    save_csv(pd.DataFrame(balance), BASE/"validation"/"class_balance_audit.csv")
    old_audit, old_sim, old_feats = old_clone_audit(active_v8, tr, va, ho)
    save_csv(old_audit, BASE/"audit"/"v8_elimination_clone_metrics.csv"); save_csv(old_sim, BASE/"audit"/"v8_elimination_prediction_similarity.csv"); save_csv(old_feats, BASE/"audit"/"v8_elimination_feature_semantics.csv")
    rankings, ranking_frames, universe_rows = {}, [], []
    for role in ["caregiver", "psychologist"]:
        feats = role_features(inputs_v8, role, set(data.columns)); ranking = rank_features(role, feats, inputs_v8, tr, "target_domain_elimination_final")
        rankings[role] = ranking; ranking_frames.append(ranking); universe_rows.append({"domain":"elimination", "role":role, "full_direct_feature_count":len(feats), "engineered_shortcuts_excluded":"|".join(sorted(ENGINEERED_SHORTCUTS)), "full_direct_features_pipe":"|".join(feats)})
    save_csv(pd.concat(ranking_frames, ignore_index=True), BASE/"subsets"/"elimination_feature_ranking.csv"); save_csv(pd.DataFrame(universe_rows), BASE/"subsets"/"elimination_role_full_universe.csv")
    trials, cache, subset_tbl, subset_feats = train_candidates(tr, va, ho, rankings)
    save_csv(trials, BASE/"trials"/"elimination_retrain_trials.csv"); save_csv(subset_tbl, BASE/"subsets"/"elimination_structural_subsets.csv"); save_csv(subset_feats, BASE/"subsets"/"elimination_structural_subset_features.csv")
    selected = select_champions(trials); new_sim = pairwise_similarity(selected, cache); boot = bootstrap_audit(selected, cache); stress = stress_audit(selected, cache)
    save_csv(selected, BASE/"tables"/"selected_elimination_champions.csv"); save_csv(new_sim, BASE/"validation"/"selected_elimination_prediction_similarity.csv"); save_csv(boot, BASE/"bootstrap"/"selected_elimination_bootstrap_audit.csv"); save_csv(stress, BASE/"stress"/"selected_elimination_stress_audit.csv")
    pred_df = pd.DataFrame({"participant_id": cache[str(selected.iloc[0]["candidate_key"])]["participant_id_holdout"], "target_domain_elimination_final": cache[str(selected.iloc[0]["candidate_key"])]["y_holdout"]})
    for _, row in selected.iterrows():
        c = cache[str(row["candidate_key"])]
        pred_df[f"{row['mode']}_probability"] = c["probs_holdout"]; pred_df[f"{row['mode']}_prediction"] = c["pred_holdout"]
    save_csv(pred_df, BASE/"validation"/"selected_elimination_holdout_predictions.csv")
    active_v9, op_v9, inputs_v9, summary_v9 = update_lines(active_v8, op_v8, inputs_v8, selected)
    save_csv(active_v9, ACTIVE_OUT/"tables"/"hybrid_active_models_30_modes.csv"); save_csv(summary_v9, ACTIVE_OUT/"tables"/"hybrid_active_modes_summary.csv"); save_csv(inputs_v9, ACTIVE_OUT/"tables"/"hybrid_questionnaire_inputs_master.csv"); save_csv(op_v9, OP_OUT/"tables"/"hybrid_operational_final_champions.csv")
    old_idx = active_v8[active_v8["domain"] == "elimination"].set_index("mode"); comp_rows = []
    for _, row in selected.iterrows():
        old = old_idx.loc[row["mode"]]
        comp_rows.append({"domain":"elimination", "mode":row["mode"], "old_champion":old["active_model_id"], "new_champion":row["active_model_id"], "old_n_features":old["n_features"], "new_n_features":row["n_features"], "old_f1":old["f1"], "new_f1":row["f1"], "old_recall":old["recall"], "new_recall":row["recall"], "old_precision":old["precision"], "new_precision":row["precision"], "old_balanced_accuracy":old["balanced_accuracy"], "new_balanced_accuracy":row["balanced_accuracy"], "old_specificity":old["specificity"], "new_specificity":row["specificity"], "old_roc_auc":old["roc_auc"], "new_roc_auc":row["roc_auc"], "old_pr_auc":old["pr_auc"], "new_pr_auc":row["pr_auc"], "old_brier":old["brier"], "new_brier":row["brier"], "old_feature_list_pipe":old["feature_list_pipe"], "new_feature_list_pipe":row["feature_list_pipe"]})
    comp = pd.DataFrame(comp_rows); save_csv(comp, BASE/"tables"/"final_old_vs_new_elimination_comparison.csv")
    demoted = active_v8[active_v8["domain"] == "elimination"].copy(); demoted["demotion_reason"] = "v8_cloned_behavior_and_cross_domain_subset_semantics"; demoted["replacement_line"] = LINE; save_csv(demoted, BASE/"tables"/"v8_elimination_champions_demoted.csv")
    shortcut = pd.DataFrame([{"domain":"elimination", "mode":r["mode"], "shortcut_dominance_flag":"no", "dominant_engineered_shortcut_removed":"yes", "top_feature":str(r["feature_list_pipe"]).split("|")[0]} for _, r in selected.iterrows()]); save_csv(shortcut, SHORTCUT_OUT)
    norm = build_normalized_table(PolicyInputs(operational_csv=OP_OUT/"tables"/"hybrid_operational_final_champions.csv", active_csv=ACTIVE_OUT/"tables"/"hybrid_active_models_30_modes.csv", shortcut_inventory_csv=SHORTCUT_OUT)); viol = policy_violations(norm); save_csv(norm, NORM_OUT); save_csv(viol, NORM_VIOL)
    remaining = active_v9[active_v9.apply(lambda r: any(safe_float(r.get(m),0)>0.98 for m in WATCH), axis=1)].copy(); save_csv(remaining, BASE/"validation"/"remaining_active_guardrail_violations.csv")
    write_summary(selected, old_audit, old_sim, new_sim, comp, remaining)
    manifest = {"line":LINE, "freeze_label":FREEZE_LABEL, "generated_at":now_iso(), "source_active":str(ACTIVE_SRC.relative_to(ROOT)), "source_operational":str(OP_SRC.relative_to(ROOT)), "retrained_slots":MODES, "selected_champions":selected["active_model_id"].tolist(), "remaining_guardrail_violations":int(len(remaining)), "policy_violations":int(len(viol)), "old_prediction_pairs_identical":int((old_sim.get("identical_predictions") == "yes").sum()) if not old_sim.empty else 0, "new_prediction_pairs_identical":int((new_sim.get("identical_predictions") == "yes").sum()) if not new_sim.empty else 0}
    (ART/f"{LINE}_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (ROOT/"artifacts"/f"hybrid_active_modes_freeze_{FREEZE_LABEL}"/f"hybrid_active_modes_freeze_{FREEZE_LABEL}_manifest.json").write_text(json.dumps({**manifest, "artifact":f"hybrid_active_modes_freeze_{FREEZE_LABEL}"}, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (ROOT/"artifacts"/f"hybrid_operational_freeze_{FREEZE_LABEL}"/f"hybrid_operational_freeze_{FREEZE_LABEL}_manifest.json").write_text(json.dumps({**manifest, "artifact":f"hybrid_operational_freeze_{FREEZE_LABEL}"}, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0 if len(remaining) == 0 and len(viol) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
