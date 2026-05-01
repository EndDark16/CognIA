#!/usr/bin/env python
from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Keep inference deterministic for legacy sklearn artifacts with internal parallelism.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LINE = "hybrid_final_clean_champion_resolution_v16"
SELECTION_VERSION = "v16"

BASE = ROOT / "data" / LINE
TABLES = BASE / "tables"
VALIDATION = BASE / "validation"
REPORTS = BASE / "reports"
PLOTS = BASE / "plots"

ACTIVE_V15 = ROOT / "data/hybrid_active_modes_freeze_v15/tables/hybrid_active_models_30_modes.csv"
ACTIVE_V15_SUMMARY = ROOT / "data/hybrid_active_modes_freeze_v15/tables/hybrid_active_modes_summary.csv"
INPUTS_V15 = ROOT / "data/hybrid_active_modes_freeze_v15/tables/hybrid_questionnaire_inputs_master.csv"
OP_V15 = ROOT / "data/hybrid_operational_freeze_v15/tables/hybrid_operational_final_champions.csv"
OP_V15_NONCHAMP = ROOT / "data/hybrid_operational_freeze_v15/tables/hybrid_operational_final_nonchampions.csv"

PAIRWISE_V15 = ROOT / "data/hybrid_elimination_v15_caregiver_full_metric_rescue/tables/v15_pairwise_prediction_similarity_all_domains.csv"
RECOMP_V15 = ROOT / "data/hybrid_elimination_v15_caregiver_full_metric_rescue/tables/v15_recomputed_champion_metrics.csv"

DATASET = ROOT / "data/hybrid_no_external_scores_rebuild_v2/tables/hybrid_no_external_scores_dataset_ready.csv"
LOADER = ROOT / "api/services/questionnaire_v2_loader_service.py"

ACTIVE_V16 = ROOT / "data/hybrid_active_modes_freeze_v16/tables/hybrid_active_models_30_modes.csv"
ACTIVE_V16_SUMMARY = ROOT / "data/hybrid_active_modes_freeze_v16/tables/hybrid_active_modes_summary.csv"
INPUTS_V16 = ROOT / "data/hybrid_active_modes_freeze_v16/tables/hybrid_questionnaire_inputs_master.csv"
OP_V16 = ROOT / "data/hybrid_operational_freeze_v16/tables/hybrid_operational_final_champions.csv"
OP_V16_NONCHAMP = ROOT / "data/hybrid_operational_freeze_v16/tables/hybrid_operational_final_nonchampions.csv"

ART_ACTIVE_V16 = ROOT / "artifacts/hybrid_active_modes_freeze_v16/hybrid_active_modes_freeze_v16_manifest.json"
ART_OP_V16 = ROOT / "artifacts/hybrid_operational_freeze_v16/hybrid_operational_freeze_v16_manifest.json"
ART_LINE = ROOT / f"artifacts/{LINE}/{LINE}_manifest.json"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
WATCH = ["recall", "specificity", "roc_auc", "pr_auc"]
METRICS_CORE = ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]
METRICS_WITH_COUNTS = METRICS_CORE + ["tn", "fp", "fn", "tp", "threshold", "n_features"]
COUNT_METRICS = {"tn", "fp", "fn", "tp"}
BASE_SEED = 20261101


@dataclass
class SlotPred:
    domain: str
    role: str
    mode: str
    active_model_id: str
    threshold: float
    feature_list_pipe: str
    n_features: int
    precision: float
    recall: float
    specificity: float
    balanced_accuracy: float
    f1: float
    roc_auc: float
    pr_auc: float
    brier: float
    tn: int
    fp: int
    fn: int
    tp: int
    probs: np.ndarray
    preds: np.ndarray
    y: np.ndarray
    artifact_hash: str | None
    artifact_path: str | None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mkdirs() -> None:
    for p in [
        BASE,
        TABLES,
        VALIDATION,
        REPORTS,
        PLOTS,
        ACTIVE_V16.parent,
        ACTIVE_V16_SUMMARY.parent,
        INPUTS_V16.parent,
        OP_V16.parent,
        ART_ACTIVE_V16.parent,
        ART_OP_V16.parent,
        ART_LINE.parent,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def sf(value: Any, default: float = float("nan")) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def tcol(domain: str) -> str:
    return f"target_domain_{domain}_final"


def feats(value: Any) -> list[str]:
    return [x.strip() for x in str(value or "").split("|") if x.strip() and x.strip().lower() != "nan"]


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def auc(y_true: np.ndarray, prob: np.ndarray) -> float:
    return float(roc_auc_score(y_true, prob)) if len(np.unique(y_true)) > 1 else float("nan")


def pr_auc(y_true: np.ndarray, prob: np.ndarray) -> float:
    return float(average_precision_score(y_true, prob)) if len(np.unique(y_true)) > 1 else float(np.mean(y_true))


def compute_metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float) -> dict[str, float | int]:
    prob = np.clip(np.asarray(prob, dtype=float), 1e-6, 1 - 1e-6)
    pred = (prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
    return {
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "specificity": specificity,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": auc(y_true, prob),
        "pr_auc": pr_auc(y_true, prob),
        "brier": float(brier_score_loss(y_true, prob)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def split_registry(df: pd.DataFrame) -> dict[str, dict[str, list[str]]]:
    ids = df["participant_id"].astype(str).to_numpy()
    out: dict[str, dict[str, list[str]]] = {}
    for i, domain in enumerate(DOMAINS):
        y = df[tcol(domain)].astype(int).to_numpy()
        seed = BASE_SEED + i * 23
        train_ids, tmp_ids, _, y_tmp = train_test_split(
            ids,
            y,
            test_size=0.40,
            random_state=seed,
            stratify=y,
        )
        val_ids, holdout_ids, _, _ = train_test_split(
            tmp_ids,
            y_tmp,
            test_size=0.50,
            random_state=seed + 1,
            stratify=y_tmp,
        )
        out[domain] = {
            "train": list(map(str, train_ids)),
            "val": list(map(str, val_ids)),
            "holdout": list(map(str, holdout_ids)),
        }
    return out


def prep_x(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    x = df[feature_columns].copy()
    for col in x.columns:
        if col == "sex_assigned_at_birth":
            x[col] = x[col].fillna("Unknown").astype(str)
        else:
            x[col] = pd.to_numeric(x[col], errors="coerce").astype(float)
    return x


def proba(model: Any, x: pd.DataFrame) -> np.ndarray:
    return np.clip(np.asarray(model.predict_proba(x)[:, 1], dtype=float), 1e-6, 1 - 1e-6)


def force_single_thread_model(obj: Any, seen: set[int] | None = None) -> None:
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen:
        return
    seen.add(oid)

    try:
        if hasattr(obj, "n_jobs") and getattr(obj, "n_jobs") not in (None, 1):
            setattr(obj, "n_jobs", 1)
    except Exception:
        pass

    for attr in ("estimator", "base_estimator", "model", "steps"):
        try:
            child = getattr(obj, attr)
        except Exception:
            child = None
        if child is None:
            continue
        if attr == "steps" and isinstance(child, list):
            for _, step_obj in child:
                force_single_thread_model(step_obj, seen)
        else:
            force_single_thread_model(child, seen)

    for attr in ("estimators_", "calibrated_classifiers_", "calibrators", "estimators"):
        try:
            children = getattr(obj, attr)
        except Exception:
            children = None
        if children is None:
            continue
        try:
            iterator = list(children)
        except Exception:
            iterator = []
        for item in iterator:
            force_single_thread_model(item, seen)


def external_artifact_roots() -> list[tuple[str, Path]]:
    parent = ROOT.parent
    return [
        ("current_repo", ROOT / "models" / "active_modes"),
        ("worktree_v15_fix", parent / "cognia_app_v15_caregiver_full_fix" / "models" / "active_modes"),
        ("worktree_v14_fix", parent / "cognia_app_elimination_v14_fix" / "models" / "active_modes"),
        ("worktree_rf_max_real_metrics", parent / "cognia_app_rf_max_real_metrics" / "models" / "active_modes"),
        ("worktree_final_rf_plus", parent / "cognia_app_final_rf_plus_maximize" / "models" / "active_modes"),
        ("worktree_v14_clean", parent / "cognia_app_elimination_v14_clean" / "models" / "active_modes"),
        ("current_main_repo", parent / "cognia_app" / "models" / "active_modes"),
    ]


def resolve_existing_artifact(model_id: str) -> tuple[str | None, str | None, str | None]:
    for origin, base in external_artifact_roots():
        for fname in ("pipeline.joblib", "calibrated.joblib"):
            candidate = base / model_id / fname
            if candidate.exists():
                try:
                    rel = candidate.relative_to(ROOT)
                    rel_path = str(rel).replace("\\", "/")
                except Exception:
                    rel_path = str(candidate)
                return rel_path, origin, sha256_file(candidate)
    return None, None, None


def detect_loader_line(text: str) -> tuple[str, str]:
    act = re.search(r"hybrid_active_modes_freeze_(v\d+)", text)
    op = re.search(r"hybrid_operational_freeze_(v\d+)", text)
    return (act.group(1) if act else "por_confirmar", op.group(1) if op else "por_confirmar")


def pairwise_similarity(a: SlotPred, b: SlotPred) -> dict[str, Any]:
    pa, pb = np.asarray(a.probs, dtype=float), np.asarray(b.probs, dtype=float)
    pra, prb = np.asarray(a.preds, dtype=int), np.asarray(b.preds, dtype=int)
    y = np.asarray(a.y, dtype=int)

    corr = float(np.corrcoef(pa, pb)[0, 1]) if np.std(pa) > 0 and np.std(pb) > 0 else float("nan")
    agreement = float(np.mean(pra == prb))
    identical = "yes" if np.array_equal(pra, prb) else "no"

    same_confusion = a.tn == b.tn and a.fp == b.fp and a.fn == b.fn and a.tp == b.tp
    metric_max_delta = max(
        abs(sf(getattr(a, m), 0) - sf(getattr(b, m), 0))
        for m in ["f1", "recall", "precision", "balanced_accuracy", "specificity"]
    )
    threshold_delta = abs(a.threshold - b.threshold)
    fa = set(feats(a.feature_list_pipe))
    fb = set(feats(b.feature_list_pipe))
    feature_jaccard = float(len(fa & fb) / max(1, len(fa | fb)))

    err_a = set(np.where(pra != y)[0].tolist())
    err_b = set(np.where(prb != y)[0].tolist())
    err_union = err_a | err_b
    err_inter = err_a & err_b
    shared_error_overlap = float(len(err_inter) / len(err_union)) if err_union else 0.0

    artifact_hash_equal = "yes" if (a.artifact_hash and b.artifact_hash and a.artifact_hash == b.artifact_hash) else "no"
    artifact_path_equal = "yes" if (a.artifact_path and b.artifact_path and a.artifact_path == b.artifact_path) else "no"

    real_reasons = []
    if identical == "yes":
        real_reasons.append("binary_predictions_identical")
    if agreement >= 0.995 and (not math.isnan(corr)) and corr >= 0.995:
        real_reasons.append("agreement_and_probability_corr_ge_0_995")
    if same_confusion and (not math.isnan(corr)) and corr >= 0.995:
        real_reasons.append("same_confusion_and_probability_corr_ge_0_995")
    if threshold_delta <= 1e-12 and metric_max_delta <= 1e-12 and feature_jaccard >= 0.90:
        real_reasons.append("same_threshold_same_main_metrics_high_feature_jaccard")
    if artifact_hash_equal == "yes":
        real_reasons.append("same_artifact_hash")
    if artifact_path_equal == "yes":
        real_reasons.append("same_loaded_artifact_path")

    near_reasons = []
    if agreement >= 0.98:
        near_reasons.append("prediction_agreement_ge_0_98")
    if (not math.isnan(corr)) and corr >= 0.98:
        near_reasons.append("probability_correlation_ge_0_98")
    if metric_max_delta <= 0.005:
        near_reasons.append("metric_max_abs_delta_le_0_005")
    if feature_jaccard >= 0.75:
        near_reasons.append("feature_jaccard_ge_0_75")
    if threshold_delta <= 0.01:
        near_reasons.append("threshold_almost_equal")
    if shared_error_overlap >= 0.75:
        near_reasons.append("shared_error_overlap_ge_0_75")

    return {
        "prediction_agreement": agreement,
        "probability_correlation": corr,
        "binary_predictions_identical": identical,
        "metric_max_abs_delta": metric_max_delta,
        "threshold_abs_delta": threshold_delta,
        "feature_jaccard": feature_jaccard,
        "shared_error_overlap": shared_error_overlap,
        "same_confusion_matrix": "yes" if same_confusion else "no",
        "artifact_hash_equal": artifact_hash_equal,
        "artifact_path_equal": artifact_path_equal,
        "real_clone_flag": "yes" if real_reasons else "no",
        "near_clone_warning": "yes" if near_reasons else "no",
        "real_clone_reasons": "|".join(real_reasons),
        "near_clone_reasons": "|".join(near_reasons),
    }


def near_clone_resolution(row: pd.Series) -> tuple[str, str]:
    if str(row.get("real_clone_flag")) == "yes":
        return "real_problem_needs_fix", "real_clone_criteria_triggered"
    if str(row.get("near_clone_warning")) != "yes":
        return "not_flagged", "no_near_warning"

    agreement = sf(row.get("prediction_agreement"), 0.0)
    corr = sf(row.get("probability_correlation"), float("nan"))
    identical = str(row.get("binary_predictions_identical") or "no")
    same_conf = str(row.get("same_confusion_matrix") or "no")
    th_delta = sf(row.get("threshold_abs_delta"), 1.0)
    feat_j = sf(row.get("feature_jaccard"), 0.0)
    shared_err = sf(row.get("shared_error_overlap"), 0.0)
    hash_eq = str(row.get("artifact_hash_equal") or "no")
    path_eq = str(row.get("artifact_path_equal") or "no")

    # Real unresolved issue only if it behaves like a clone despite not being captured.
    if identical == "yes":
        return "real_problem_needs_fix", "binary_identical_unresolved"
    if agreement >= 0.995 and (not math.isnan(corr)) and corr >= 0.995:
        return "real_problem_needs_fix", "agreement_corr_unresolved"
    if same_conf == "yes" and (not math.isnan(corr)) and corr >= 0.995:
        return "real_problem_needs_fix", "same_confusion_corr_unresolved"
    if hash_eq == "yes" or path_eq == "yes":
        return "real_problem_needs_fix", "artifact_duplication_unresolved"

    reasons = str(row.get("near_clone_reasons") or "")
    if (
        agreement < 0.98
        and ((not math.isnan(corr)) and corr < 0.98)
        and shared_err < 0.75
        and feat_j < 0.75
        and th_delta > 0.01
    ):
        return "false_positive_warning", f"threshold_rule_overlap_only:{reasons}"

    return "acceptable_similarity", f"high_similarity_explained:{reasons}"


def active_summary_table(active_df: pd.DataFrame) -> pd.DataFrame:
    out = (
        active_df.groupby(["final_operational_class", "confidence_band"], dropna=False)
        .size()
        .reset_index(name="n_active_models")
        .sort_values(["final_operational_class", "confidence_band"])
        .reset_index(drop=True)
    )
    return out


def build_slot_pred(row: pd.Series) -> SlotPred:
    return SlotPred(
        domain=str(row["domain"]),
        role=str(row["role"]),
        mode=str(row["mode"]),
        active_model_id=str(row["active_model_id"]),
        threshold=float(row["threshold"]),
        feature_list_pipe=str(row["feature_list_pipe"]),
        n_features=int(row["n_features"]),
        precision=float(row["precision"]),
        recall=float(row["recall"]),
        specificity=float(row["specificity"]),
        balanced_accuracy=float(row["balanced_accuracy"]),
        f1=float(row["f1"]),
        roc_auc=float(row["roc_auc"]),
        pr_auc=float(row["pr_auc"]),
        brier=float(row["brier"]),
        tn=int(row["tn"]),
        fp=int(row["fp"]),
        fn=int(row["fn"]),
        tp=int(row["tp"]),
        probs=np.asarray(row["_probs"], dtype=float),
        preds=np.asarray(row["_preds"], dtype=int),
        y=np.asarray(row["_y"], dtype=int),
        artifact_hash=str(row.get("artifact_hash") or "") if not pd.isna(row.get("artifact_hash")) else None,
        artifact_path=str(row.get("artifact_path") or "") if not pd.isna(row.get("artifact_path")) else None,
    )


def recompute_against_registered(active_df: pd.DataFrame, data: pd.DataFrame, splits: dict[str, dict[str, list[str]]], registered_source: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    recomputed_rows: list[dict[str, Any]] = []
    reg_vs_recomp: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []

    for _, row in active_df.iterrows():
        domain = str(row["domain"])
        role = str(row["role"])
        mode = str(row["mode"])
        model_id = str(row["active_model_id"])
        feat_pipe = str(row.get("feature_list_pipe") or "")
        fcols = feats(feat_pipe)
        thr = float(sf(row.get("threshold"), 0.5))

        local_pipeline = ROOT / "models" / "active_modes" / model_id / "pipeline.joblib"
        local_calibrated = ROOT / "models" / "active_modes" / model_id / "calibrated.joblib"
        art_path = None
        art_origin = None
        art_hash = None
        if local_pipeline.exists():
            art_path = str(local_pipeline.relative_to(ROOT)).replace("\\", "/")
            art_origin = "current_repo"
            art_hash = sha256_file(local_pipeline)
        elif local_calibrated.exists():
            art_path = str(local_calibrated.relative_to(ROOT)).replace("\\", "/")
            art_origin = "current_repo"
            art_hash = sha256_file(local_calibrated)
        else:
            art_path, art_origin, art_hash = resolve_existing_artifact(model_id)

        artifact_rows.append(
            {
                "domain": domain,
                "role": role,
                "mode": mode,
                "active_model_id": model_id,
                "artifacts_available": "yes" if art_path else "no",
                "artifact_path": art_path,
                "artifact_origin": art_origin,
                "artifact_hash": art_hash,
            }
        )

        rec: dict[str, Any] = {
            "domain": domain,
            "role": role,
            "mode": mode,
            "active_model_id": model_id,
            "model_key": model_id,
            "artifact_path": art_path,
            "artifact_origin": art_origin,
            "artifact_hash": art_hash,
            "threshold": thr,
            "n_features": len(fcols),
            "feature_list_pipe": feat_pipe,
            "artifacts_available": "yes" if art_path else "no",
            "prediction_recomputed": "no",
            "recompute_blocker": "",
            "probability_mean": float("nan"),
            "probability_std": float("nan"),
            "prediction_positive_rate": float("nan"),
            "holdout_n": float("nan"),
            "holdout_positive_n": float("nan"),
            "holdout_negative_n": float("nan"),
            "_probs": np.array([], dtype=float),
            "_preds": np.array([], dtype=int),
            "_y": np.array([], dtype=int),
        }
        for m in METRICS_CORE + ["tn", "fp", "fn", "tp"]:
            rec[m] = float("nan")

        if not art_path:
            rec["recompute_blocker"] = "artifact_unavailable"
            recomputed_rows.append(rec)
            for mn in METRICS_WITH_COUNTS:
                rv = sf(row.get(mn), float("nan"))
                qv = sf(rec.get(mn), float("nan"))
                if math.isnan(rv) and mn in COUNT_METRICS:
                    d = float("nan")
                    ok = "not_applicable"
                elif math.isnan(rv) or math.isnan(qv):
                    d = float("nan")
                    ok = "por_confirmar"
                else:
                    d = abs(rv - qv)
                    ok = "yes" if d <= 1e-6 else "no"
                reg_vs_recomp.append(
                    {
                        "domain": domain,
                        "role": role,
                        "mode": mode,
                        "active_model_id": model_id,
                        "metric_name": mn,
                        "registered_value": rv,
                        "recomputed_value": qv,
                        "abs_delta": d,
                        "tolerance": 1e-6,
                        "within_tolerance": ok,
                        "registered_source": registered_source,
                    }
                )
            continue

        model = joblib.load(Path(art_path))
        force_single_thread_model(model)
        hold_ids = set(splits[domain]["holdout"])
        hold = data[data["participant_id"].astype(str).isin(hold_ids)].copy()
        y = hold[tcol(domain)].astype(int).to_numpy()
        miss = [f for f in fcols if f not in hold.columns]
        if miss:
            rec["recompute_blocker"] = "missing_features_in_dataset:" + "|".join(miss)
            recomputed_rows.append(rec)
            continue
        x = prep_x(hold, fcols)
        try:
            p = proba(model, x)
        except Exception as exc:
            rec["recompute_blocker"] = f"predict_proba_error:{repr(exc)}"
            recomputed_rows.append(rec)
            continue
        mm = compute_metrics(y, p, thr)
        pred = (p >= thr).astype(int)
        rec.update(mm)
        rec["prediction_recomputed"] = "yes"
        rec["probability_mean"] = float(np.mean(p))
        rec["probability_std"] = float(np.std(p))
        rec["prediction_positive_rate"] = float(np.mean(pred))
        rec["holdout_n"] = int(len(y))
        rec["holdout_positive_n"] = int(np.sum(y))
        rec["holdout_negative_n"] = int(len(y) - np.sum(y))
        rec["_probs"] = p
        rec["_preds"] = pred
        rec["_y"] = y
        recomputed_rows.append(rec)

        for mn in METRICS_WITH_COUNTS:
            rv = sf(row.get(mn), float("nan"))
            qv = sf(rec.get(mn), float("nan"))
            if math.isnan(rv) and mn in COUNT_METRICS:
                d = float("nan")
                ok = "not_applicable"
            elif math.isnan(rv) or math.isnan(qv):
                d = float("nan")
                ok = "por_confirmar"
            else:
                d = abs(rv - qv)
                ok = "yes" if d <= 1e-6 else "no"
            reg_vs_recomp.append(
                {
                    "domain": domain,
                    "role": role,
                    "mode": mode,
                    "active_model_id": model_id,
                    "metric_name": mn,
                    "registered_value": rv,
                    "recomputed_value": qv,
                    "abs_delta": d,
                    "tolerance": 1e-6,
                    "within_tolerance": ok,
                    "registered_source": registered_source,
                }
            )

    return pd.DataFrame(recomputed_rows), pd.DataFrame(reg_vs_recomp), pd.DataFrame(artifact_rows)


def build_metrics_match_validator(recomputed_df: pd.DataFrame, reg_vs_recomp_df: pd.DataFrame, artifact_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    recomputed_yes_ids = set(recomputed_df[recomputed_df["prediction_recomputed"] == "yes"]["active_model_id"].astype(str))
    artifacts_yes_ids = set(artifact_df[artifact_df["artifacts_available"] == "yes"]["active_model_id"].astype(str))
    for model_id, grp in reg_vs_recomp_df.groupby("active_model_id", dropna=False):
        g2 = grp[(grp["within_tolerance"] != "por_confirmar") & (grp["within_tolerance"] != "not_applicable")]
        if g2.empty:
            mm = "por_confirmar"
            max_delta = float("nan")
        else:
            mm = "yes" if (g2["within_tolerance"] == "yes").all() else "no"
            max_delta = float(g2["abs_delta"].max())
        one = grp.iloc[0]
        rows.append(
            {
                "domain": one["domain"],
                "role": one["role"],
                "mode": one["mode"],
                "active_model_id": str(model_id),
                "prediction_recomputed": "yes" if str(model_id) in recomputed_yes_ids else "no",
                "artifacts_available": "yes" if str(model_id) in artifacts_yes_ids else "no",
                "metrics_match_registered": mm,
                "max_abs_delta_any_metric": max_delta,
            }
        )
    return pd.DataFrame(rows)


def db_verify(active_v16: pd.DataFrame, unresolved_near_clone_count: int) -> tuple[dict[str, Any], dict[str, Any]]:
    # Returns (db_active_set_validator, supabase_sync_verification_payload)
    from api.app import create_app
    from app.models import ModelModeDomainActivation, ModelRegistry, ModelVersion, QuestionnaireQuestion, QuestionnaireQuestionMode

    def _config_class_from_env():
        class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
        module_path, class_name = class_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)

    payload: dict[str, Any] = {
        "line": LINE,
        "generated_at_utc": now(),
    }
    db_validator: dict[str, Any] = {
        "line": LINE,
        "generated_at_utc": now(),
    }
    def _norm_role(value: Any) -> str:
        raw = str(value or "").strip().lower()
        return "guardian" if raw == "caregiver" else raw

    app = create_app(_config_class_from_env())
    with app.app_context():
        active_rows = (
            ModelModeDomainActivation.query.filter_by(active_flag=True).all()
        )
        active_count = len(active_rows)
        version_ids = {str(r.model_version_id) for r in active_rows if r.model_version_id}
        active_versions = ModelVersion.query.filter(ModelVersion.id.in_(list(version_ids))).all() if version_ids else []
        registry_ids = {str(r.model_registry_id) for r in active_rows if r.model_registry_id}
        active_regs = ModelRegistry.query.filter(ModelRegistry.id.in_(list(registry_ids))).all() if registry_ids else []

        non_rf = 0
        reg_by_id = {str(r.id): r for r in active_regs}
        source_campaign_db = set()
        for r in active_rows:
            reg = reg_by_id.get(str(r.model_registry_id))
            fam = str(getattr(reg, "model_family", "") or "").lower()
            if fam != "rf":
                non_rf += 1
            source_campaign_db.add(str(getattr(r, "source_campaign", "") or ""))

        expected_ids = set(active_v16["active_model_id"].astype(str))
        reg_model_keys = {str(r.model_key) for r in active_regs}
        missing_expected_models = len(expected_ids - reg_model_keys)

        # Duplicate active rows by domain/mode/role
        dup_map: dict[tuple[str, str, str], int] = {}
        for r in active_rows:
            key = (str(r.domain), str(r.mode_key), str(r.role))
            dup_map[key] = dup_map.get(key, 0) + 1
        duplicate_active_domain_mode_rows = sum(1 for _, c in dup_map.items() if c > 1)

        # Feature columns mismatch between DB active version metadata and active csv registry.
        version_by_id = {str(v.id): v for v in active_versions}
        active_index = {
            (str(r["domain"]), str(r["mode"]), _norm_role(r["role"])): feats(r["feature_list_pipe"])
            for _, r in active_v16.iterrows()
        }
        mismatched_feature_columns = 0
        for a in active_rows:
            key = (str(a.domain), str(a.mode_key), _norm_role(a.role))
            expected = active_index.get(key)
            ver = version_by_id.get(str(a.model_version_id))
            if expected is None or ver is None:
                mismatched_feature_columns += 1
                continue
            metadata = ver.metadata_json or {}
            got = metadata.get("feature_columns")
            if isinstance(got, list):
                got_list = [str(x) for x in got]
            else:
                got_list = []
            if expected != got_list:
                mismatched_feature_columns += 1

        elimination_active_rows_db = sum(1 for r in active_rows if str(r.domain) == "elimination")
        elimination_active_expected = int((active_v16["domain"] == "elimination").sum())
        non_elim_expected = int((active_v16["domain"] != "elimination").sum())
        non_elim_match = 0
        for _, row in active_v16[active_v16["domain"] != "elimination"].iterrows():
            k = (str(row["domain"]), str(row["mode"]), _norm_role(row["role"]))
            if dup_map.get(k, 0) == 1:
                non_elim_match += 1

        mixed_lineage_expected = "yes" if active_v16["source_campaign"].astype(str).nunique() > 1 else "no"
        active_model_lineage_mixed = "yes" if len({x for x in source_campaign_db if x}) > 1 else "no"
        db_active_set_valid = (
            active_count == 30
            and len(active_versions) == 30
            and non_rf == 0
            and missing_expected_models == 0
            and mismatched_feature_columns == 0
            and duplicate_active_domain_mode_rows == 0
            and elimination_active_rows_db == elimination_active_expected
            and non_elim_match == non_elim_expected
        )

        visible_count = int(QuestionnaireQuestion.query.filter_by(visible_question=True).count())
        visible_modes = int(QuestionnaireQuestionMode.query.filter_by(is_included=True).count())

        payload.update(
            {
                "active_activations_db": active_count,
                "active_model_versions": len(active_versions),
                "active_model_versions_non_rf": non_rf,
                "missing_expected_models": missing_expected_models,
                "mismatched_feature_columns": mismatched_feature_columns,
                "duplicate_active_domain_mode_rows": duplicate_active_domain_mode_rows,
                "mixed_lineage_expected": mixed_lineage_expected,
                "active_model_lineage_mixed": active_model_lineage_mixed,
                "db_active_set_valid": "yes" if db_active_set_valid else "no",
                "active_selection_version": SELECTION_VERSION,
                "active_champions_loaded_ok": "yes" if db_active_set_valid else "no",
                "elimination_active_rows_db": elimination_active_rows_db,
                "elimination_expected_rows": elimination_active_expected,
                "non_elimination_expected_match_count": non_elim_match,
                "questions_visible_count": visible_count,
                "question_modes_included_count": visible_modes,
                "unresolved_near_clone_warning_count": int(unresolved_near_clone_count),
            }
        )
        db_validator.update(payload)

    return db_validator, payload


def main() -> int:
    mkdirs()

    required = [
        LOADER,
        ACTIVE_V15,
        ACTIVE_V15_SUMMARY,
        INPUTS_V15,
        OP_V15,
        OP_V15_NONCHAMP,
        PAIRWISE_V15,
        RECOMP_V15,
        DATASET,
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("missing required files: " + "; ".join(missing))

    active_v15 = pd.read_csv(ACTIVE_V15)
    op_v15 = pd.read_csv(OP_V15)
    op_v15_nonchamp = pd.read_csv(OP_V15_NONCHAMP)
    data = pd.read_csv(DATASET)
    splits = split_registry(data)

    # Start v16 as exact copy of v15, then resolve objective issues with evidence.
    active_v16 = active_v15.copy()
    op_v16 = op_v15.copy()

    corrected_rows: list[dict[str, Any]] = []
    recomputed_df = pd.DataFrame()
    reg_vs_recomp_df = pd.DataFrame()
    artifact_df = pd.DataFrame()
    metrics_match_df = pd.DataFrame()

    # Resolve metric drift iteratively from real recomputation.
    for iteration in range(1, 5):
        recomputed_df, reg_vs_recomp_df, artifact_df = recompute_against_registered(
            active_v16, data, splits, registered_source=f"active_v16_iter_{iteration}"
        )
        metrics_match_df = build_metrics_match_validator(recomputed_df, reg_vs_recomp_df, artifact_df)
        drift_slots = metrics_match_df[metrics_match_df["metrics_match_registered"] == "no"].copy()
        if drift_slots.empty:
            break

        for _, drow in drift_slots.iterrows():
            model_id = str(drow["active_model_id"])
            rr = recomputed_df[recomputed_df["active_model_id"] == model_id]
            if rr.empty:
                continue
            rr_one = rr.iloc[0]
            mask_active = active_v16["active_model_id"] == model_id
            if not bool(mask_active.any()):
                continue

            domain = str(rr_one["domain"])
            mode = str(rr_one["mode"])
            old_active = active_v16.loc[mask_active, METRICS_CORE].iloc[0].to_dict()
            for m in METRICS_CORE:
                active_v16.loc[mask_active, m] = float(rr_one[m])

            mask_op = (op_v16["domain"] == domain) & (op_v16["mode"] == mode)
            if bool(mask_op.any()):
                for m in METRICS_CORE:
                    op_v16.loc[mask_op, m] = float(rr_one[m])
                op_v16.loc[mask_op, "threshold"] = float(rr_one["threshold"])
                op_v16.loc[mask_op, "n_features"] = int(rr_one["n_features"])

            new_active = active_v16.loc[mask_active, METRICS_CORE].iloc[0].to_dict()
            corrected_rows.append(
                {
                    "iteration": iteration,
                    "domain": domain,
                    "role": str(rr_one["role"]),
                    "mode": mode,
                    "active_model_id": model_id,
                    "change_type": "metric_registration_correction",
                    "model_replaced": "no",
                    "pre_fix_metrics_match_registered": "no",
                    "post_fix_metrics_expected": "recomputed_exact",
                    **{f"old_{k}": float(old_active[k]) for k in METRICS_CORE},
                    **{f"new_{k}": float(new_active[k]) for k in METRICS_CORE},
                }
            )

    # Final recomputation snapshot against stabilized v16.
    recomputed_df, reg_vs_recomp_df, artifact_df = recompute_against_registered(
        active_v16, data, splits, registered_source="active_v16"
    )
    metrics_match_df = build_metrics_match_validator(recomputed_df, reg_vs_recomp_df, artifact_df)

    # Contract validator (must keep exact contract/order vs v15).
    contract_rows = []
    v15_idx = active_v15.set_index(["domain", "role", "mode"])
    for _, r in active_v16.iterrows():
        key = (r["domain"], r["role"], r["mode"])
        old = v15_idx.loc[key]
        old_feats = feats(old["feature_list_pipe"])
        new_feats = feats(r["feature_list_pipe"])
        contract_rows.append(
            {
                "domain": r["domain"],
                "role": r["role"],
                "mode": r["mode"],
                "active_model_id": r["active_model_id"],
                "same_feature_columns_order": "yes" if old_feats == new_feats else "no",
                "same_inputs_outputs_contract": "yes" if old_feats == new_feats else "no",
                "questionnaire_changed": "no",
            }
        )
    contract_df = pd.DataFrame(contract_rows)

    # Non-elimination unchanged validator (model/threshold/feature columns).
    non_change_rows = []
    for _, r in active_v16[active_v16["domain"] != "elimination"].iterrows():
        key = (r["domain"], r["role"], r["mode"])
        b = v15_idx.loc[key]
        unchanged = (
            str(r["active_model_id"]) == str(b["active_model_id"])
            and abs(sf(r["threshold"], 0.0) - sf(b["threshold"], 0.0)) <= 1e-12
            and feats(r["feature_list_pipe"]) == feats(b["feature_list_pipe"])
            and all(abs(sf(r[m], 0.0) - sf(b[m], 0.0)) <= 1e-12 for m in METRICS_CORE)
        )
        non_change_rows.append(
            {
                "domain": r["domain"],
                "role": r["role"],
                "mode": r["mode"],
                "active_model_id_v15": b["active_model_id"],
                "active_model_id_v16": r["active_model_id"],
                "unchanged": "yes" if unchanged else "no",
            }
        )
    non_change_df = pd.DataFrame(non_change_rows)

    guard_df = active_v16[["domain", "role", "mode", "active_model_id", "recall", "specificity", "roc_auc", "pr_auc"]].copy()
    guard_df["guardrail_violation"] = guard_df.apply(
        lambda x: "yes" if any(sf(x[m], 0) > 0.98 for m in WATCH) else "no", axis=1
    )
    guard_viol_count = int((guard_df["guardrail_violation"] == "yes").sum())

    # Build pairwise similarity from recomputed predictions (real).
    pair_rows: list[dict[str, Any]] = []
    by_domain: dict[str, list[pd.Series]] = {}
    for _, row in recomputed_df[recomputed_df["prediction_recomputed"] == "yes"].iterrows():
        by_domain.setdefault(str(row["domain"]), []).append(row)

    for domain, arr in by_domain.items():
        if domain == "elimination":
            combos = itertools.combinations(arr, 2)
        else:
            role_map: dict[str, list[pd.Series]] = {}
            for r in arr:
                role_map.setdefault(str(r["role"]), []).append(r)
            combos = itertools.chain.from_iterable(itertools.combinations(v, 2) for v in role_map.values())

        for a, b in combos:
            sim = pairwise_similarity(build_slot_pred(a), build_slot_pred(b))
            pair_rows.append(
                {
                    "domain": domain,
                    "slot_a": f"{a['domain']}/{a['mode']}",
                    "slot_b": f"{b['domain']}/{b['mode']}",
                    "active_model_id_a": a["active_model_id"],
                    "active_model_id_b": b["active_model_id"],
                    "prediction_agreement": sim["prediction_agreement"],
                    "probability_correlation": sim["probability_correlation"],
                    "binary_predictions_identical": sim["binary_predictions_identical"],
                    "metric_max_abs_delta": sim["metric_max_abs_delta"],
                    "threshold_abs_delta": sim["threshold_abs_delta"],
                    "feature_jaccard": sim["feature_jaccard"],
                    "shared_error_overlap": sim["shared_error_overlap"],
                    "real_clone_flag": sim["real_clone_flag"],
                    "near_clone_warning": sim["near_clone_warning"],
                    "real_clone_reasons": sim["real_clone_reasons"],
                    "near_clone_reasons": sim["near_clone_reasons"],
                    "same_confusion_matrix": sim["same_confusion_matrix"],
                    "artifact_hash_equal": sim["artifact_hash_equal"],
                    "artifact_path_equal": sim["artifact_path_equal"],
                }
            )
    pair_df = pd.DataFrame(pair_rows)
    if pair_df.empty:
        raise RuntimeError("pairwise_similarity_empty_after_recompute")
    elim_pair_df = pair_df[pair_df["domain"] == "elimination"].copy()
    shared_error_df = pair_df[
        ["domain", "slot_a", "slot_b", "active_model_id_a", "active_model_id_b", "shared_error_overlap"]
    ].copy()

    # Resolve near-clone warnings explicitly.
    resolution_rows = []
    for _, row in pair_df.iterrows():
        status, detail = near_clone_resolution(row)
        resolution_rows.append(
            {
                "domain": row["domain"],
                "slot_a": row["slot_a"],
                "slot_b": row["slot_b"],
                "active_model_id_a": row["active_model_id_a"],
                "active_model_id_b": row["active_model_id_b"],
                "near_clone_warning": row["near_clone_warning"],
                "real_clone_flag": row["real_clone_flag"],
                "prediction_agreement": row["prediction_agreement"],
                "probability_correlation": row["probability_correlation"],
                "binary_predictions_identical": row["binary_predictions_identical"],
                "same_confusion_matrix": row["same_confusion_matrix"],
                "threshold_abs_delta": row["threshold_abs_delta"],
                "feature_jaccard": row["feature_jaccard"],
                "shared_error_overlap": row["shared_error_overlap"],
                "artifact_hash_equal": row["artifact_hash_equal"],
                "artifact_path_equal": row["artifact_path_equal"],
                "near_clone_reasons": row["near_clone_reasons"],
                "real_clone_reasons": row["real_clone_reasons"],
                "warning_resolution": status,
                "resolution_detail": detail,
            }
        )
    resolution_df = pd.DataFrame(resolution_rows)
    pair_df = pair_df.merge(
        resolution_df[["slot_a", "slot_b", "warning_resolution", "resolution_detail"]],
        on=["slot_a", "slot_b"],
        how="left",
    )
    elim_pair_df = elim_pair_df.merge(
        resolution_df[["slot_a", "slot_b", "warning_resolution", "resolution_detail"]],
        on=["slot_a", "slot_b"],
        how="left",
    )

    all_real_clone_count = int((pair_df["real_clone_flag"] == "yes").sum())
    elimination_real_clone_count = int((elim_pair_df["real_clone_flag"] == "yes").sum())
    near_total_count = int((pair_df["near_clone_warning"] == "yes").sum())
    unresolved_near_clone_count = int((resolution_df["warning_resolution"] == "real_problem_needs_fix").sum())
    acceptable_similarity_count = int((resolution_df["warning_resolution"] == "acceptable_similarity").sum())
    false_positive_count = int((resolution_df["warning_resolution"] == "false_positive_warning").sum())

    hash_inv = artifact_df.copy()
    hash_inv["duplicate_hash_group_size"] = hash_inv.groupby("artifact_hash")["artifact_hash"].transform("count")
    hash_inv.loc[hash_inv["artifact_hash"].isna(), "duplicate_hash_group_size"] = 0
    duplicate_hash_count = int(
        hash_inv[
            (hash_inv["artifact_hash"].notna())
            & (hash_inv["artifact_hash"] != "")
        ]["artifact_hash"].value_counts().gt(1).sum()
    )

    recomputed_yes = int((recomputed_df["prediction_recomputed"] == "yes").sum())
    artifact_yes = int((artifact_df["artifacts_available"] == "yes").sum())
    metrics_yes = int((metrics_match_df["metrics_match_registered"] == "yes").sum())
    metrics_no = int((metrics_match_df["metrics_match_registered"] == "no").sum())

    # v15 vs v16 comparison.
    v15_idx_all = active_v15.set_index(["domain", "role", "mode"])
    v16_idx_all = active_v16.set_index(["domain", "role", "mode"])
    comp_rows = []
    for key in v15_idx_all.index:
        old = v15_idx_all.loc[key]
        new = v16_idx_all.loc[key]
        comp = {
            "domain": key[0],
            "role": key[1],
            "mode": key[2],
            "active_model_id_v15": old["active_model_id"],
            "active_model_id_v16": new["active_model_id"],
            "active_model_changed": "yes" if str(old["active_model_id"]) != str(new["active_model_id"]) else "no",
            "source_campaign_v15": old["source_campaign"],
            "source_campaign_v16": new["source_campaign"],
            "threshold_v15": sf(old["threshold"], float("nan")),
            "threshold_v16": sf(new["threshold"], float("nan")),
            "threshold_delta_abs": abs(sf(old["threshold"], 0.0) - sf(new["threshold"], 0.0)),
        }
        changed_metrics = 0
        for m in METRICS_CORE:
            ov = sf(old[m], float("nan"))
            nv = sf(new[m], float("nan"))
            comp[f"v15_{m}"] = ov
            comp[f"v16_{m}"] = nv
            comp[f"delta_{m}"] = nv - ov
            if not (math.isnan(ov) and math.isnan(nv)) and abs(nv - ov) > 1e-12:
                changed_metrics += 1
        comp["metrics_changed"] = "yes" if changed_metrics > 0 else "no"
        comp_rows.append(comp)
    comp_df = pd.DataFrame(comp_rows)

    corrected_df = pd.DataFrame(corrected_rows)
    if corrected_df.empty:
        corrected_df = pd.DataFrame(
            [
                {
                    "domain": "",
                    "role": "",
                    "mode": "",
                    "active_model_id": "",
                    "change_type": "no_change_required",
                    "model_replaced": "no",
                    "pre_fix_metrics_match_registered": "yes",
                    "post_fix_metrics_expected": "yes",
                }
            ]
        )

    historical_reuse = (
        active_v16.groupby(["source_campaign", "source_line"], dropna=False)
        .size()
        .reset_index(name="active_models_count")
        .sort_values(["active_models_count", "source_campaign"], ascending=[False, True])
        .reset_index(drop=True)
    )
    historical_reuse["selection_version_final"] = SELECTION_VERSION
    historical_reuse["source_lineage_tracked"] = "yes"
    historical_reuse["mixed_lineage_by_design"] = "yes" if active_v16["source_campaign"].astype(str).nunique() > 1 else "no"

    final_inventory = active_v16.copy()
    final_inventory["selection_version_final"] = SELECTION_VERSION
    final_inventory["mixed_lineage_by_design"] = "yes" if active_v16["source_campaign"].astype(str).nunique() > 1 else "no"
    final_inventory["source_lineage_tracked"] = "yes"

    # Pass/fail without pass_with_warnings.
    contract_ok = bool((contract_df["same_inputs_outputs_contract"] == "yes").all())
    feature_order_ok = bool((contract_df["same_feature_columns_order"] == "yes").all())
    non_elim_unchanged_ok = bool((non_change_df["unchanged"] == "yes").all())
    questionnaire_changed = "no"

    if recomputed_yes < 30:
        final_status = "fail"
    elif artifact_yes < 30:
        final_status = "fail"
    elif metrics_yes < 30 or metrics_no > 0:
        final_status = "fail"
    elif all_real_clone_count > 0 or elimination_real_clone_count > 0:
        final_status = "fail"
    elif unresolved_near_clone_count > 0:
        final_status = "fail"
    elif duplicate_hash_count > 0:
        final_status = "fail"
    elif guard_viol_count > 0:
        final_status = "fail"
    elif not contract_ok or not feature_order_ok:
        final_status = "fail"
    elif not non_elim_unchanged_ok:
        final_status = "fail"
    else:
        final_status = "pass"

    main_validator = pd.DataFrame(
        [
            {
                "audit_line": LINE,
                "generated_at_utc": now(),
                "active_rows": int(len(active_v16)),
                "rf_rows": int((active_v16["model_family"].astype(str).str.lower() == "rf").sum()),
                "prediction_recomputed_slots": recomputed_yes,
                "artifacts_available_slots": artifact_yes,
                "metrics_match_yes_slots": metrics_yes,
                "metrics_match_no_slots": metrics_no,
                "all_domains_real_clone_count": all_real_clone_count,
                "elimination_real_clone_count": elimination_real_clone_count,
                "all_domains_near_clone_warning_count": near_total_count,
                "false_positive_warning_count": false_positive_count,
                "acceptable_similarity_count": acceptable_similarity_count,
                "unresolved_near_clone_warning_count": unresolved_near_clone_count,
                "artifact_duplicate_hash_count": duplicate_hash_count,
                "guardrail_violation_count": guard_viol_count,
                "same_inputs_outputs_contract_30_30": "yes" if contract_ok else "no",
                "same_feature_columns_order_30_30": "yes" if feature_order_ok else "no",
                "questionnaire_changed": questionnaire_changed,
                "non_elimination_unchanged_vs_v15": "yes" if non_elim_unchanged_ok else "no",
                "final_audit_status": final_status,
            }
        ]
    )

    near_validator = resolution_df.copy()
    near_validator["explained_non_blocking_observation"] = near_validator["warning_resolution"].map(
        lambda x: "yes" if x in {"acceptable_similarity", "false_positive_warning", "not_flagged"} else "no"
    )

    # Save v16 freeze artifacts.
    save_csv(active_v16, ACTIVE_V16)
    save_csv(active_summary_table(active_v16), ACTIVE_V16_SUMMARY)
    INPUTS_V16.write_bytes(INPUTS_V15.read_bytes())
    save_csv(op_v16, OP_V16)
    save_csv(op_v15_nonchamp, OP_V16_NONCHAMP)

    # Requested tables.
    save_csv(final_inventory, TABLES / "final_champion_inventory_v16.csv")
    save_csv(comp_df, TABLES / "v15_vs_v16_all_champions_comparison.csv")
    save_csv(near_validator, TABLES / "resolved_warning_inventory_v16.csv")
    save_csv(corrected_df, TABLES / "replaced_or_corrected_models_v16.csv")
    save_csv(historical_reuse, TABLES / "historical_model_reuse_v16.csv")
    save_csv(recomputed_df.drop(columns=["_probs", "_preds", "_y"]), TABLES / "v16_recomputed_champion_metrics.csv")
    save_csv(reg_vs_recomp_df, TABLES / "v16_registered_vs_recomputed_metrics.csv")
    save_csv(pair_df, TABLES / "v16_pairwise_prediction_similarity_all_domains.csv")
    save_csv(elim_pair_df, TABLES / "v16_elimination_real_prediction_similarity.csv")
    save_csv(shared_error_df, TABLES / "v16_shared_error_overlap.csv")
    save_csv(hash_inv, TABLES / "v16_artifact_hash_inventory.csv")

    # Validators.
    save_csv(main_validator, VALIDATION / "v16_final_audit_validator.csv")
    save_csv(metrics_match_df, VALIDATION / "v16_metrics_match_validator.csv")
    save_csv(guard_df, VALIDATION / "v16_guardrail_validator.csv")
    save_csv(contract_df, VALIDATION / "v16_contract_compatibility_validator.csv")
    save_csv(near_validator, VALIDATION / "v16_near_clone_resolution_validator.csv")
    write_text(
        VALIDATION / "v16_db_active_set_validator.json",
        json.dumps(
            {
                "line": LINE,
                "generated_at_utc": now(),
                "sync_status": "pending_external_sync",
                "note": "Populate by running bootstrap_questionnaire_backend_v2.py load-all and DB verification.",
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    write_text(
        VALIDATION / "v16_supabase_sync_verification.json",
        json.dumps(
            {
                "line": LINE,
                "generated_at_utc": now(),
                "sync_status": "pending_external_sync",
                "note": "Populate by running bootstrap_questionnaire_backend_v2.py load-all and DB verification.",
            },
            indent=2,
            ensure_ascii=False,
        ),
    )

    # Plots (best effort).
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns

        comp_elim = comp_df[comp_df["domain"] == "elimination"].copy()
        m = comp_elim.melt(
            id_vars=["domain", "role", "mode"],
            value_vars=["delta_f1", "delta_recall", "delta_precision", "delta_balanced_accuracy"],
            var_name="metric",
            value_name="delta",
        )
        plt.figure(figsize=(12, 6))
        sns.barplot(data=m, x="mode", y="delta", hue="metric")
        plt.axhline(0.0, color="black", linewidth=1)
        plt.tight_layout()
        plt.savefig(PLOTS / "elimination_v15_vs_v16_metrics.png", dpi=180)
        plt.close()

        slots = sorted(set(elim_pair_df["slot_a"]).union(set(elim_pair_df["slot_b"])))
        corr_mat = pd.DataFrame(np.eye(len(slots)), index=slots, columns=slots, dtype=float)
        agr_mat = pd.DataFrame(np.eye(len(slots)), index=slots, columns=slots, dtype=float)
        for _, r in elim_pair_df.iterrows():
            a = r["slot_a"]
            b = r["slot_b"]
            corr_mat.loc[a, b] = r["probability_correlation"]
            corr_mat.loc[b, a] = r["probability_correlation"]
            agr_mat.loc[a, b] = r["prediction_agreement"]
            agr_mat.loc[b, a] = r["prediction_agreement"]

        plt.figure(figsize=(10, 8))
        sns.heatmap(corr_mat, annot=True, fmt=".3f", cmap="viridis", vmin=0.0, vmax=1.0)
        plt.tight_layout()
        plt.savefig(PLOTS / "elimination_v16_probability_correlation_heatmap.png", dpi=180)
        plt.close()

        plt.figure(figsize=(10, 8))
        sns.heatmap(agr_mat, annot=True, fmt=".3f", cmap="magma", vmin=0.0, vmax=1.0)
        plt.tight_layout()
        plt.savefig(PLOTS / "elimination_v16_prediction_agreement_heatmap.png", dpi=180)
        plt.close()

        p = pair_df.copy()
        p["pair"] = p["slot_a"] + " vs " + p["slot_b"]
        plt.figure(figsize=(14, 6))
        sns.barplot(data=p, x="pair", y="prediction_agreement", hue="real_clone_flag")
        plt.xticks(rotation=90, fontsize=7)
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(PLOTS / "v16_all_domains_pairwise_prediction_agreement.png", dpi=180)
        plt.close()
    except Exception as exc:
        write_text(REPORTS / "v16_plot_generation_warning.md", f"plot_generation_error={repr(exc)}")

    # Update DB verification files after load-all if possible.
    db_note = ""
    try:
        db_validator, db_payload = db_verify(active_v16, unresolved_near_clone_count)
        write_text(VALIDATION / "v16_db_active_set_validator.json", json.dumps(db_validator, indent=2, ensure_ascii=False))
        write_text(VALIDATION / "v16_supabase_sync_verification.json", json.dumps(db_payload, indent=2, ensure_ascii=False))
    except Exception as exc:
        db_note = f"db_verification_error={repr(exc)}"
        write_text(
            VALIDATION / "v16_db_active_set_validator.json",
            json.dumps(
                {
                    "line": LINE,
                    "generated_at_utc": now(),
                    "db_active_set_valid": "no",
                    "error": repr(exc),
                },
                indent=2,
                ensure_ascii=False,
            ),
        )
        write_text(
            VALIDATION / "v16_supabase_sync_verification.json",
            json.dumps(
                {
                    "line": LINE,
                    "generated_at_utc": now(),
                    "synced": "no",
                    "error": repr(exc),
                },
                indent=2,
                ensure_ascii=False,
            ),
        )

    # Report.
    loader_text = LOADER.read_text(encoding="utf-8")
    loader_active_before, loader_op_before = detect_loader_line(loader_text)
    report_lines = [
        "# v16 Final Clean Champion Resolution",
        "",
        f"- generated_at_utc: `{now()}`",
        f"- line: `{LINE}`",
        f"- selection_version_final: `{SELECTION_VERSION}`",
        f"- loader_line_before_update: `active={loader_active_before}`, `operational={loader_op_before}`",
        f"- active_rows: `{len(active_v16)}`",
        f"- rf_rows: `{int((active_v16['model_family'].astype(str).str.lower() == 'rf').sum())}`",
        f"- prediction_recomputed_slots: `{recomputed_yes}`",
        f"- artifacts_available_slots: `{artifact_yes}`",
        f"- metrics_match_yes_slots: `{metrics_yes}`",
        f"- metrics_match_no_slots: `{metrics_no}`",
        f"- all_domains_real_clone_count: `{all_real_clone_count}`",
        f"- elimination_real_clone_count: `{elimination_real_clone_count}`",
        f"- all_domains_near_clone_warning_count: `{near_total_count}`",
        f"- unresolved_near_clone_warning_count: `{unresolved_near_clone_count}`",
        f"- acceptable_similarity_count: `{acceptable_similarity_count}`",
        f"- false_positive_warning_count: `{false_positive_count}`",
        f"- artifact_duplicate_hash_count: `{duplicate_hash_count}`",
        f"- guardrail_violation_count: `{guard_viol_count}`",
        f"- same_inputs_outputs_contract_30_30: `{'yes' if contract_ok else 'no'}`",
        f"- non_elimination_unchanged_vs_v15: `{'yes' if non_elim_unchanged_ok else 'no'}`",
        f"- mixed_lineage_by_design: `{'yes' if active_v16['source_campaign'].astype(str).nunique() > 1 else 'no'}`",
        f"- final_audit_status: `{final_status}`",
    ]
    if db_note:
        report_lines.extend(["", "## DB verification note", "", f"- {db_note}"])
    write_text(REPORTS / "v16_final_clean_champion_resolution_report.md", "\n".join(report_lines))

    # Manifests.
    manifest_payload = {
        "line": LINE,
        "selection_version_final": SELECTION_VERSION,
        "generated_at_utc": now(),
        "final_audit_status": final_status,
        "active_rows": int(len(active_v16)),
        "rf_rows": int((active_v16["model_family"].astype(str).str.lower() == "rf").sum()),
        "prediction_recomputed_slots": recomputed_yes,
        "metrics_match_yes_slots": metrics_yes,
        "metrics_match_no_slots": metrics_no,
        "all_domains_real_clone_count": all_real_clone_count,
        "elimination_real_clone_count": elimination_real_clone_count,
        "all_domains_near_clone_warning_count": near_total_count,
        "unresolved_near_clone_warning_count": unresolved_near_clone_count,
        "artifact_duplicate_hash_count": duplicate_hash_count,
        "guardrail_violation_count": guard_viol_count,
    }
    write_text(ART_LINE, json.dumps(manifest_payload, indent=2, ensure_ascii=False))
    write_text(ART_ACTIVE_V16, json.dumps({**manifest_payload, "artifact": "hybrid_active_modes_freeze_v16"}, indent=2, ensure_ascii=False))
    write_text(ART_OP_V16, json.dumps({**manifest_payload, "artifact": "hybrid_operational_freeze_v16"}, indent=2, ensure_ascii=False))

    print(
        json.dumps(
            {
                "line": LINE,
                "final_audit_status": final_status,
                "prediction_recomputed_slots": recomputed_yes,
                "metrics_match_yes_slots": metrics_yes,
                "metrics_match_no_slots": metrics_no,
                "all_domains_real_clone_count": all_real_clone_count,
                "elimination_real_clone_count": elimination_real_clone_count,
                "all_domains_near_clone_warning_count": near_total_count,
                "unresolved_near_clone_warning_count": unresolved_near_clone_count,
                "db_verification_note": db_note or "none",
            },
            ensure_ascii=False,
        )
    )
    return 0 if final_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
