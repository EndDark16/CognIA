from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.utils import resample

from evaluate_abstention_policy import evaluate_abstention_policy
from ml_rf_common import (
    RANDOM_STATE,
    binary_metrics,
    build_binary_pipeline,
    sanitize_features,
    threshold_candidates,
)
from optimize_precision_thresholds import PrecisionThresholdPolicy, optimize_precision_thresholds
from versioning_utils import ensure_versioning_dirs, load_registry, metric_value, save_registry, utcnow_iso


LOGGER = logging.getLogger("precision-bottleneck-audit")
TARGETS = ["adhd", "anxiety", "depression", "conduct", "elimination"]
TARGET_COL = {d: f"target_{d}" for d in TARGETS}
SOURCE_TABLES = [
    "Diagnosis_ClinicianConsensus.csv",
    "Diagnosis_KSADS_D.csv",
    "Diagnosis_KSADS_P.csv",
    "Diagnosis_KSADS_T.csv",
]


def _setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def ensure_audit_dirs(root: Path) -> Dict[str, Path]:
    paths = {
        "audit": root / "reports" / "audit",
        "figures": root / "reports" / "audit" / "figures",
        "diagnostics": root / "reports" / "audit" / "diagnostics",
        "roadmaps": root / "reports" / "audit" / "roadmaps",
        "artifacts": root / "artifacts" / "audit",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_md(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(list(lines)).rstrip() + "\n", encoding="utf-8")


def _safe_div(a: float, b: float) -> float:
    return float(a / b) if b else float("nan")


def _compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    indices = np.digitize(y_prob, bins) - 1
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        mask = indices == i
        if not np.any(mask):
            continue
        acc = float(np.mean(y_true[mask]))
        conf = float(np.mean(y_prob[mask]))
        ece += float(np.abs(acc - conf) * np.sum(mask) / n)
    return float(ece)


def _apply_abstention_thresholds(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    low_threshold: float,
    high_threshold: float,
) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    n = len(y_true)
    if n == 0:
        return {
            "coverage": float("nan"),
            "uncertain_rate": float("nan"),
            "confident_positive_n": 0,
            "confident_negative_n": 0,
            "uncertain_n": 0,
            "precision_high": float("nan"),
            "npv_low": float("nan"),
            "recall_effective": float("nan"),
            "specificity_effective": float("nan"),
            "selection_reason": "empty_input",
        }

    pos_mask = y_prob >= float(high_threshold)
    neg_mask = y_prob <= float(low_threshold)
    uncertain_mask = ~(pos_mask | neg_mask)

    tp = int(np.logical_and(pos_mask, y_true == 1).sum())
    fp = int(np.logical_and(pos_mask, y_true == 0).sum())
    tn = int(np.logical_and(neg_mask, y_true == 0).sum())
    fn_low = int(np.logical_and(neg_mask, y_true == 1).sum())

    total_pos = max(int((y_true == 1).sum()), 1)
    total_neg = max(int((y_true == 0).sum()), 1)
    pos_n = int(pos_mask.sum())
    neg_n = int(neg_mask.sum())
    uncertain_n = int(uncertain_mask.sum())

    return {
        "coverage": float((pos_n + neg_n) / n),
        "uncertain_rate": float(uncertain_n / n),
        "confident_positive_n": pos_n,
        "confident_negative_n": neg_n,
        "uncertain_n": uncertain_n,
        "precision_high": _safe_div(tp, tp + fp),
        "npv_low": _safe_div(tn, tn + fn_low),
        "recall_effective": float(tp / total_pos),
        "specificity_effective": float(tn / total_neg),
        "selection_reason": "fixed_thresholds",
    }


@dataclass
class ChampionContext:
    disorder: str
    model_version: str
    dataset_name: str
    data_scope: str
    target_col: str
    model_dir: Path
    metadata: Dict[str, Any]
    pipeline: Any
    calibrator: Optional[Any]
    threshold: float
    source_model_id: str
    train_df: pd.DataFrame
    val_df: pd.DataFrame
    test_df: pd.DataFrame
    feature_columns: List[str]
    y_train: np.ndarray
    y_val: np.ndarray
    y_test: np.ndarray


def _align_X(X: pd.DataFrame, feature_columns: Sequence[str]) -> pd.DataFrame:
    out = X.copy()
    for col in feature_columns:
        if col not in out.columns:
            out[col] = np.nan
    return out[list(feature_columns)].copy()


def _load_split_participants(root: Path, dataset_name: str, scope: str) -> Tuple[List[str], List[str], List[str]]:
    split_dir = root / "data" / "processed" / "splits" / dataset_name / scope
    tr = pd.read_csv(split_dir / "ids_train.csv")["participant_id"].astype(str).tolist()
    va = pd.read_csv(split_dir / "ids_val.csv")["participant_id"].astype(str).tolist()
    te = pd.read_csv(split_dir / "ids_test.csv")["participant_id"].astype(str).tolist()
    return tr, va, te


def _subset_by_ids(df: pd.DataFrame, ids: Sequence[str]) -> pd.DataFrame:
    idx = df.copy()
    idx["participant_id"] = idx["participant_id"].astype(str)
    idx = idx.set_index("participant_id", drop=True)
    return idx.loc[list(ids)].reset_index().rename(columns={"index": "participant_id"})


def _load_champion_contexts(root: Path) -> Dict[str, ChampionContext]:
    registry = load_registry(root / "reports" / "versioning" / "model_registry.csv")
    champions = registry[
        (registry["task_type"] == "binary")
        & (registry["promoted"].astype(str).str.lower() == "yes")
        & (registry["promoted_status"].astype(str).str.lower() == "champion")
    ].copy()
    contexts: Dict[str, ChampionContext] = {}
    for disorder in TARGETS:
        row_df = champions[champions["disorder"] == disorder]
        if row_df.empty:
            continue
        row = row_df.iloc[-1]
        model_version = str(row["model_version"])
        model_dir = root / "models" / "versioned" / model_version
        metadata = _read_json(model_dir / "metadata.json")
        pipeline = joblib.load(model_dir / "pipeline.joblib")
        calibrator_path = model_dir / "calibrated.joblib"
        calibrator = joblib.load(calibrator_path) if calibrator_path.exists() else None

        dataset_name = str(row["dataset_name"])
        scope = str(row["data_scope"])
        dataset_path = root / "data" / "processed" / "final" / scope / f"{dataset_name}_{scope}.csv"
        df = pd.read_csv(dataset_path)
        target_col = TARGET_COL[disorder]
        X_all, y_df, _ = sanitize_features(df, task="binary", target_column=target_col)
        feature_columns = list(metadata.get("feature_columns", list(X_all.columns)))
        X_all = _align_X(X_all, feature_columns)

        tr_ids, va_ids, te_ids = _load_split_participants(root, dataset_name, scope)
        indexed = pd.concat([df[["participant_id"]], X_all, y_df], axis=1)
        train_df = _subset_by_ids(indexed, tr_ids)
        val_df = _subset_by_ids(indexed, va_ids)
        test_df = _subset_by_ids(indexed, te_ids)

        threshold = metadata.get("threshold_value", metadata.get("recommended_threshold", row.get("threshold_value", 0.5)))
        try:
            threshold = float(threshold)
        except Exception:
            threshold = 0.5

        contexts[disorder] = ChampionContext(
            disorder=disorder,
            model_version=model_version,
            dataset_name=dataset_name,
            data_scope=scope,
            target_col=target_col,
            model_dir=model_dir,
            metadata=metadata,
            pipeline=pipeline,
            calibrator=calibrator,
            threshold=threshold,
            source_model_id=str(row.get("source_model_id", "")).strip(),
            train_df=train_df,
            val_df=val_df,
            test_df=test_df,
            feature_columns=feature_columns,
            y_train=train_df[target_col].to_numpy(dtype=int),
            y_val=val_df[target_col].to_numpy(dtype=int),
            y_test=test_df[target_col].to_numpy(dtype=int),
        )
    return contexts


def _predict_prob(ctx: ChampionContext, X: pd.DataFrame) -> np.ndarray:
    X_aligned = _align_X(X, ctx.feature_columns)
    model = ctx.calibrator if ctx.calibrator is not None else ctx.pipeline
    return model.predict_proba(X_aligned)[:, 1]


def _diagnosis_keywords() -> Dict[str, List[str]]:
    return {
        "adhd": ["adhd", "attention-deficit", "hyperactivity", "inattention"],
        "anxiety": ["anxiety", "panic", "phobia", "separation anxiety", "social anxiety", "generalized anxiety"],
        "depression": ["depress", "major depressive", "mood disorder"],
        "conduct": ["conduct", "oppositional", "disruptive", "impulse-control"],
        "elimination": ["elimination", "enuresis", "encopresis"],
    }


def _map_consensus_targets(df: pd.DataFrame) -> pd.DataFrame:
    keys = _diagnosis_keywords()
    out = pd.DataFrame({"participant_id": df["participant_id"].astype(str)})
    diag_cols = [c for c in df.columns if c.startswith("diagnosis_") and not c.endswith("_certainty")]
    for disorder in TARGETS:
        vals = np.zeros(len(df), dtype=int)
        pats = keys[disorder]
        for col in diag_cols:
            s = df[col].fillna("").astype(str).str.lower()
            mask = np.zeros(len(df), dtype=bool)
            for p in pats:
                mask |= s.str.contains(p, regex=False).to_numpy()
            vals = np.maximum(vals, mask.astype(int))
        out[f"{disorder}_consensus"] = vals
    return out


def build_source_vote_table(root: Path, participant_ids: Sequence[str]) -> pd.DataFrame:
    base = root / "data" / "HBN_synthetic_release11_focused_subset_csv"
    ids = set(str(x) for x in participant_ids)
    cc = pd.read_csv(base / "Diagnosis_ClinicianConsensus.csv")
    cc_map = _map_consensus_targets(cc)
    cc_map = cc_map[cc_map["participant_id"].isin(ids)].copy()

    ksads_map = {
        "ADHD_present": "adhd",
        "AnxietyDisorders_present": "anxiety",
        "DepressiveDisorders_present": "depression",
        "DisruptiveImpulseControlConductDisorders_present": "conduct",
        "EliminationDisorders_present": "elimination",
    }

    merged = pd.DataFrame({"participant_id": sorted(ids)})
    merged = merged.merge(cc_map, on="participant_id", how="left")
    for src_name, src_file in [("ksads_d", "Diagnosis_KSADS_D.csv"), ("ksads_p", "Diagnosis_KSADS_P.csv"), ("ksads_t", "Diagnosis_KSADS_T.csv")]:
        d = pd.read_csv(base / src_file)
        d["participant_id"] = d["participant_id"].astype(str)
        d = d[d["participant_id"].isin(ids)].copy()
        for k, disorder in ksads_map.items():
            col = f"{disorder}_{src_name}"
            d[col] = pd.to_numeric(d[k], errors="coerce").fillna(0).astype(int)
        keep = ["participant_id"] + [f"{disorder}_{src_name}" for disorder in TARGETS]
        merged = merged.merge(d[keep], on="participant_id", how="left")

    for disorder in TARGETS:
        consensus_col = f"{disorder}_consensus"
        consensus_series = (
            merged[consensus_col]
            if consensus_col in merged.columns
            else pd.Series(0, index=merged.index, dtype="int64")
        )
        merged[consensus_col] = pd.to_numeric(consensus_series, errors="coerce").fillna(0).astype(int)
        for src_name in ["ksads_d", "ksads_p", "ksads_t"]:
            col = f"{disorder}_{src_name}"
            src_series = (
                merged[col]
                if col in merged.columns
                else pd.Series(0, index=merged.index, dtype="int64")
            )
            merged[col] = pd.to_numeric(src_series, errors="coerce").fillna(0).astype(int)
        vote_cols = [f"{disorder}_consensus", f"{disorder}_ksads_d", f"{disorder}_ksads_p", f"{disorder}_ksads_t"]
        merged[f"{disorder}_vote_count"] = merged[vote_cols].sum(axis=1).astype(int)
        merged[f"{disorder}_vote_agreement"] = merged[vote_cols].nunique(axis=1).map({1: 1, 2: 0, 3: 0, 4: 0}).astype(int)
    return merged


def _master_strict(root: Path) -> pd.DataFrame:
    return pd.read_csv(root / "data" / "processed" / "final" / "strict_no_leakage" / "master_multilabel_ready_strict_no_leakage.csv")


def audit_target_quality(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    master = _master_strict(root)
    master["participant_id"] = master["participant_id"].astype(str)
    votes = build_source_vote_table(root, master["participant_id"].tolist())
    data = master.merge(votes, on="participant_id", how="left")
    rows = []
    for disorder in TARGETS:
        tgt = TARGET_COL[disorder]
        vote_cols = [f"{disorder}_consensus", f"{disorder}_ksads_d", f"{disorder}_ksads_p", f"{disorder}_ksads_t"]
        vote_count = data[f"{disorder}_vote_count"].fillna(0)
        majority = (vote_count >= 2).astype(int)
        master_y = data[tgt].astype(int)

        pair_agreements = []
        for i in range(len(vote_cols)):
            for j in range(i + 1, len(vote_cols)):
                a = data[vote_cols[i]].fillna(0).astype(int)
                b = data[vote_cols[j]].fillna(0).astype(int)
                pair_agreements.append(float((a == b).mean()))
        inter_source_agreement = float(np.mean(pair_agreements)) if pair_agreements else float("nan")
        disagreement_rate = float((majority != master_y).mean())
        uncertain_rate = float(((vote_count > 0) & (vote_count < 3)).mean())
        high_conf_rate = float(((vote_count >= 3) & (master_y == 1)).mean())
        strict_pos_rate = float((vote_count >= 3).mean())

        rows.append(
            {
                "disorder": disorder,
                "n_samples": len(data),
                "prevalence_master": float(master_y.mean()),
                "prevalence_consensus": float(data[f"{disorder}_consensus"].fillna(0).mean()),
                "prevalence_ksads_d": float(data[f"{disorder}_ksads_d"].fillna(0).mean()),
                "prevalence_ksads_p": float(data[f"{disorder}_ksads_p"].fillna(0).mean()),
                "prevalence_ksads_t": float(data[f"{disorder}_ksads_t"].fillna(0).mean()),
                "inter_source_pairwise_agreement": inter_source_agreement,
                "disagreement_with_master_rate": disagreement_rate,
                "uncertain_case_rate": uncertain_rate,
                "high_confidence_positive_rate": high_conf_rate,
                "strict_positive_rate_votes_ge3": strict_pos_rate,
                "label_noise_risk_index": float(0.6 * disagreement_rate + 0.4 * uncertain_rate),
            }
        )

    out = pd.DataFrame(rows).sort_values("disorder")
    out.to_csv(dirs["audit"] / "target_quality_audit.csv", index=False)

    rec_lines = ["# Target Confidence Recommendations", ""]
    for row in out.itertuples(index=False):
        recommendation = "keep_current_target"
        if row.label_noise_risk_index >= 0.22:
            recommendation = "evaluate_high_confidence_targets_and_uncertain_case_exclusion"
        elif row.label_noise_risk_index >= 0.14:
            recommendation = "add_uncertainty_flag_and_secondary_training_split"
        rec_lines.append(
            f"- {row.disorder}: label_noise_risk_index={row.label_noise_risk_index:.3f}, "
            f"uncertain_case_rate={row.uncertain_case_rate:.3f}, recommendation={recommendation}."
        )
    _write_md(dirs["audit"] / "target_confidence_recommendations.md", rec_lines)

    noise_lines = [
        "# Label Noise Hypotheses",
        "",
        "1. Cross-source disagreement suggests latent label ambiguity, strongest where vote disagreement is highest.",
        "2. Comorbidity likely causes heterogeneous positives, reducing PPV even when ranking quality is acceptable.",
        "3. Targets with high uncertain-case rates should be split into strict-positive and uncertain cohorts for diagnostics.",
        "",
        "## Disorder-level hypothesis strength",
    ]
    for row in out.sort_values("label_noise_risk_index", ascending=False).itertuples(index=False):
        strength = "high" if row.label_noise_risk_index >= 0.22 else ("medium" if row.label_noise_risk_index >= 0.14 else "low")
        noise_lines.append(f"- {row.disorder}: {strength} (index={row.label_noise_risk_index:.3f}).")
    _write_md(dirs["audit"] / "label_noise_hypotheses.md", noise_lines)


def _dsm_criteria_catalog() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "adhd": [
            {"criterion": "Inattention symptoms", "patterns": ["swan_inattention", "conners_cognitive", "sdq_hyperactivity", "cbcl_attention"]},
            {"criterion": "Hyperactivity/impulsivity", "patterns": ["swan_hyperactive", "conners_hyperactivity", "sdq_hyperactivity"]},
            {"criterion": "Cross-setting impairment", "patterns": ["sdq_impact", "conners_total", "cbcl_externalizing"]},
            {"criterion": "Functional interference", "patterns": ["total", "impact"]},
        ],
        "anxiety": [
            {"criterion": "Core anxiety symptoms", "patterns": ["scared", "cbcl_anxious", "sdq_emotional"]},
            {"criterion": "Panic/somatic", "patterns": ["panic", "somatic"]},
            {"criterion": "Avoidance and social fear", "patterns": ["social", "school_avoidance", "separation"]},
            {"criterion": "Functional impairment", "patterns": ["sdq_impact", "total"]},
        ],
        "depression": [
            {"criterion": "Depressed mood / anhedonia proxy", "patterns": ["mfq", "cdi", "cbcl_anxious_depressed"]},
            {"criterion": "Neurovegetative / cognitive symptom proxy", "patterns": ["mfq", "cdi", "sdq_emotional"]},
            {"criterion": "Severity and persistence proxy", "patterns": ["mfq_total", "cdi_total", "internalizing"]},
            {"criterion": "Functional impairment", "patterns": ["sdq_impact", "total_difficulties"]},
        ],
        "conduct": [
            {"criterion": "Aggression to people/animals proxy", "patterns": ["cbcl_aggressive", "ari", "icut"]},
            {"criterion": "Rule violation / deceit proxy", "patterns": ["cbcl_rule_breaking", "sdq_conduct", "conduct"]},
            {"criterion": "Callous-unemotional traits", "patterns": ["icut_callousness", "icut_uncaring", "icut_total"]},
            {"criterion": "Cross-context persistence", "patterns": ["cbcl_externalizing", "sdq_total", "ari_sr", "ari_p"]},
        ],
        "elimination": [
            {"criterion": "Enuresis/encopresis direct evidence", "patterns": ["elimination", "enuresis", "encopresis"]},
            {"criterion": "Internalizing/externalizing comorbidity context", "patterns": ["cbcl", "sdq"]},
            {"criterion": "Functional impact proxy", "patterns": ["sdq_impact", "total_difficulties"]},
            {"criterion": "Missingness/availability robustness", "patterns": ["has_", "__missing"]},
        ],
    }


def audit_dsm5_alignment(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    master_cols = set(_master_strict(root).columns)
    catalog = _dsm_criteria_catalog()
    rows: List[Dict[str, Any]] = []
    for disorder in TARGETS:
        ctx = contexts[disorder]
        champion_feats = [f.lower() for f in ctx.feature_columns]
        for item in catalog[disorder]:
            pats = [p.lower() for p in item["patterns"]]
            champ_matches = [f for f in champion_feats if any(p in f for p in pats)]
            data_matches = [c for c in master_cols if any(p in c.lower() for p in pats)]
            if champ_matches:
                quality = "high"
            elif data_matches:
                quality = "medium"
            else:
                quality = "absent"
            if quality == "high":
                risk = "low"
            elif quality == "medium":
                risk = "medium"
            else:
                risk = "high"
            recommendation = (
                "retain_and_monitor"
                if quality == "high"
                else ("add_to_model_variant_and_validate_specificity" if quality == "medium" else "requires_new_measurement_or_target_redefinition")
            )
            rows.append(
                {
                    "disorder": disorder,
                    "criterion_dsm5": item["criterion"],
                    "instrument_or_source_proxy": "|".join(item["patterns"]),
                    "feature_in_current_champion": ";".join(champ_matches[:6]),
                    "feature_available_in_dataset": ";".join(data_matches[:8]),
                    "mapping_quality": quality,
                    "precision_risk_level": risk,
                    "recommendation": recommendation,
                }
            )

    matrix = pd.DataFrame(rows)
    matrix.to_csv(dirs["audit"] / "dsm5_feature_alignment_matrix.csv", index=False)

    gap_lines = ["# DSM-5 Feature Gap Report", ""]
    for disorder in TARGETS:
        sub = matrix[matrix["disorder"] == disorder]
        absent = int((sub["mapping_quality"] == "absent").sum())
        medium = int((sub["mapping_quality"] == "medium").sum())
        high = int((sub["mapping_quality"] == "high").sum())
        gap_lines.append(f"- {disorder}: high={high}, medium={medium}, absent={absent}.")
    _write_md(dirs["audit"] / "dsm5_feature_gap_report.md", gap_lines)

    risk_lines = ["# Clinical Specificity Risks", ""]
    risk_df = matrix[matrix["precision_risk_level"] != "low"].copy()
    if risk_df.empty:
        risk_lines.append("- No medium/high specificity risks detected in current mapping.")
    else:
        for row in risk_df.itertuples(index=False):
            risk_lines.append(
                f"- {row.disorder} | {row.criterion_dsm5}: risk={row.precision_risk_level}, recommendation={row.recommendation}."
            )
    _write_md(dirs["audit"] / "clinical_specificity_risks.md", risk_lines)


def _strict_variant_paths(root: Path, disorder: str) -> List[Path]:
    base = root / "data" / "processed" / "final" / "strict_no_leakage"
    return sorted(base.glob(f"dataset_{disorder}_*_strict_no_leakage.csv"))


def _coverage_from_has_columns(df: pd.DataFrame) -> Tuple[float, int]:
    has_cols = [c for c in df.columns if c.startswith("has_")]
    if not has_cols:
        return float("nan"), 0
    arr = df[has_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    return float(arr.mean().mean()), len(has_cols)


def audit_dataset_coverage(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    rows: List[Dict[str, Any]] = []
    missing_rows: List[Dict[str, Any]] = []
    for disorder in TARGETS:
        for path in _strict_variant_paths(root, disorder):
            df = pd.read_csv(path)
            target = TARGET_COL[disorder]
            y = pd.to_numeric(df[target], errors="coerce").fillna(0).astype(int)
            feature_cols = [c for c in df.columns if c not in ["participant_id", *TARGET_COL.values()]]
            X = df[feature_cols]
            missing = X.isna()
            pos_mask = y == 1
            neg_mask = y == 0
            pos_missing = float(missing[pos_mask].mean().mean()) if pos_mask.any() else float("nan")
            neg_missing = float(missing[neg_mask].mean().mean()) if neg_mask.any() else float("nan")
            nonnull_ratio = 1.0 - missing.mean(axis=1)
            sufficient_cov = float((nonnull_ratio >= 0.60).mean())
            avg_nonnull = float(nonnull_ratio.mean())
            cov_mean, n_has = _coverage_from_has_columns(df)

            rows.append(
                {
                    "dataset_name": path.stem.replace("_strict_no_leakage", ""),
                    "disorder": disorder,
                    "n_rows": len(df),
                    "n_features": len(feature_cols),
                    "positive_count": int(pos_mask.sum()),
                    "negative_count": int(neg_mask.sum()),
                    "positive_rate": float(pos_mask.mean()),
                    "overall_missing_pct": float(missing.mean().mean()),
                    "missing_pct_positive": pos_missing,
                    "missing_pct_negative": neg_missing,
                    "missingness_gap_pos_minus_neg": float(pos_missing - neg_missing) if pd.notna(pos_missing) and pd.notna(neg_missing) else float("nan"),
                    "avg_nonnull_ratio_per_participant": avg_nonnull,
                    "sufficient_coverage_ratio_nonnull_ge_0_60": sufficient_cov,
                    "instrument_availability_mean": cov_mean,
                    "instrument_flag_count": n_has,
                }
            )

            # Top differential missingness
            if pos_mask.any() and neg_mask.any():
                pos_feat = missing[pos_mask].mean(axis=0)
                neg_feat = missing[neg_mask].mean(axis=0)
                gap = (pos_feat - neg_feat).abs().sort_values(ascending=False).head(12)
                for feat, gapv in gap.items():
                    missing_rows.append(
                        {
                            "dataset_name": path.stem.replace("_strict_no_leakage", ""),
                            "disorder": disorder,
                            "feature": feat,
                            "missing_positive": float(pos_feat.get(feat, np.nan)),
                            "missing_negative": float(neg_feat.get(feat, np.nan)),
                            "abs_missing_gap": float(gapv),
                        }
                    )

    cov = pd.DataFrame(rows).sort_values(["disorder", "dataset_name"])
    cov.to_csv(dirs["audit"] / "dataset_coverage_audit.csv", index=False)
    pd.DataFrame(missing_rows).sort_values(["disorder", "abs_missing_gap"], ascending=[True, False]).to_csv(
        dirs["audit"] / "missingness_by_class.csv",
        index=False,
    )


def _fit_rf_with_params(X_train: pd.DataFrame, y_train: np.ndarray, params: Dict[str, Any], class_weight_override: Optional[str] = None):
    pipe, _, _ = build_binary_pipeline(X_train)
    safe_params = {k: v for k, v in params.items() if isinstance(k, str) and k.startswith("model__")}
    if class_weight_override is not None:
        safe_params["model__class_weight"] = class_weight_override
    if safe_params:
        pipe.set_params(**safe_params)
    pipe.fit(X_train, y_train)
    return pipe


def _parse_hyperparams(row: pd.Series) -> Dict[str, Any]:
    raw = row.get("hyperparameters_json", "")
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def audit_learning_curves(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    registry = load_registry(root / "reports" / "versioning" / "model_registry.csv")
    rows: List[Dict[str, Any]] = []
    fractions = [0.2, 0.4, 0.6, 0.8, 1.0]
    for disorder, ctx in contexts.items():
        row_df = registry[registry["model_version"] == ctx.model_version]
        hyper = _parse_hyperparams(row_df.iloc[-1]) if not row_df.empty else {}
        X_train = ctx.train_df[ctx.feature_columns].copy()
        y_train = ctx.y_train.copy()
        X_val = ctx.val_df[ctx.feature_columns].copy()
        y_val = ctx.y_val.copy()
        for frac in fractions:
            if frac < 1.0:
                X_sub, _, y_sub, _ = train_test_split(
                    X_train,
                    y_train,
                    train_size=frac,
                    random_state=RANDOM_STATE,
                    stratify=y_train,
                )
            else:
                X_sub, y_sub = X_train, y_train

            model = _fit_rf_with_params(X_sub, y_sub, hyper)
            prob = model.predict_proba(X_val)[:, 1]
            selected, _ = optimize_precision_thresholds(
                y_true=y_val,
                y_prob=prob,
                policy=PrecisionThresholdPolicy(recall_floor=0.65 if disorder != "elimination" else 0.45, balanced_accuracy_floor=0.55),
            )
            thr = float(selected["threshold"])
            m = binary_metrics(y_val, prob, threshold=thr)
            rows.append(
                {
                    "disorder": disorder,
                    "fraction_train_used": frac,
                    "n_train_used": len(X_sub),
                    "precision_val": float(m["precision"]),
                    "balanced_accuracy_val": float(m["balanced_accuracy"]),
                    "pr_auc_val": float(m["pr_auc"]),
                    "threshold_used": thr,
                }
            )

        # plot curves
        sub = pd.DataFrame([r for r in rows if r["disorder"] == disorder]).sort_values("fraction_train_used")
        plt.figure(figsize=(6, 4))
        plt.plot(sub["fraction_train_used"], sub["precision_val"], marker="o", label="precision")
        plt.plot(sub["fraction_train_used"], sub["balanced_accuracy_val"], marker="o", label="balanced_accuracy")
        plt.plot(sub["fraction_train_used"], sub["pr_auc_val"], marker="o", label="pr_auc")
        plt.title(f"{disorder} learning curves (validation)")
        plt.xlabel("Train fraction")
        plt.ylabel("Metric")
        plt.ylim(0.0, 1.0)
        plt.grid(alpha=0.3)
        plt.legend()
        fig_path = dirs["figures"] / f"learning_curve_{disorder}.png"
        plt.tight_layout()
        plt.savefig(fig_path, dpi=160)
        plt.close()

    curves = pd.DataFrame(rows).sort_values(["disorder", "fraction_train_used"])
    curves.to_csv(dirs["audit"] / "learning_curves_summary.csv", index=False)

    interp = ["# Learning Curves Interpretation", ""]
    for disorder in TARGETS:
        sub = curves[curves["disorder"] == disorder].sort_values("fraction_train_used")
        if sub.empty:
            continue
        p_delta = float(sub.iloc[-1]["precision_val"] - sub.iloc[0]["precision_val"])
        pr_delta = float(sub.iloc[-1]["pr_auc_val"] - sub.iloc[0]["pr_auc_val"])
        if p_delta > 0.04 and pr_delta > 0.04:
            status = "still_ascending_more_effective_samples_likely_help"
        elif abs(p_delta) < 0.02 and abs(pr_delta) < 0.02:
            status = "mostly_flat_limited_gain_from_more_of_same_data"
        else:
            status = "mixed_or_noisy_curve_possible_label_noise_or_high_variance"
        interp.append(f"- {disorder}: precision_delta={p_delta:.3f}, pr_auc_delta={pr_delta:.3f}, interpretation={status}.")
    _write_md(dirs["audit"] / "learning_curves_interpretation.md", interp)


def _top_challenger_features(root: Path, disorder: str, top_n: int = 1) -> List[set[str]]:
    file_path = root / "reports" / "experiments" / f"{disorder}_precision_experiments.csv"
    if not file_path.exists():
        return []
    df = pd.read_csv(file_path)
    if df.empty:
        return []
    df = df.sort_values(["val_precision", "val_balanced_accuracy", "val_recall"], ascending=[False, False, False]).head(top_n)
    sets: List[set[str]] = []
    for mv in df["model_version"].tolist():
        md = _read_json(root / "models" / "versioned" / str(mv) / "metadata.json")
        feats = set(md.get("feature_columns", []))
        if feats:
            sets.append(feats)
    return sets


def audit_feature_quality(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    rows: List[Dict[str, Any]] = []
    fp_patterns: List[Dict[str, Any]] = []
    for disorder, ctx in contexts.items():
        X_train = ctx.train_df[ctx.feature_columns].copy()
        X_test = ctx.test_df[ctx.feature_columns].copy()
        y_test = ctx.y_test
        prob = _predict_prob(ctx, X_test)
        pred = (prob >= ctx.threshold).astype(int)
        cm = binary_metrics(y_test, prob, ctx.threshold)["confusion_matrix"]

        numeric_cols = [c for c in X_train.columns if pd.api.types.is_numeric_dtype(X_train[c])]
        corr_pairs = 0
        if len(numeric_cols) >= 2:
            corr = X_train[numeric_cols].corr().abs()
            upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
            corr_pairs = int((upper > 0.90).sum().sum())
        missing_high = float((X_train.isna().mean() > 0.40).mean())

        challenger_sets = _top_challenger_features(root, disorder, top_n=1)
        jaccard = float("nan")
        if challenger_sets:
            a = set(ctx.feature_columns)
            b = challenger_sets[0]
            jaccard = _safe_div(len(a & b), len(a | b))

        rows.append(
            {
                "disorder": disorder,
                "current_champion": ctx.model_version,
                "n_features": len(ctx.feature_columns),
                "high_missing_feature_ratio_gt_40pct": missing_high,
                "high_correlation_pairs_gt_0_90": corr_pairs,
                "jaccard_with_top_precision_challenger": jaccard,
                "test_precision": float(binary_metrics(y_test, prob, ctx.threshold)["precision"]),
                "test_false_positives": int(cm[0][1]),
                "test_false_negatives": int(cm[1][0]),
            }
        )

        # FP feature patterns vs TN
        fp_mask = (pred == 1) & (y_test == 0)
        tn_mask = (pred == 0) & (y_test == 0)
        if fp_mask.any() and tn_mask.any() and numeric_cols:
            diff = (
                X_test.loc[fp_mask, numeric_cols].mean(axis=0, numeric_only=True)
                - X_test.loc[tn_mask, numeric_cols].mean(axis=0, numeric_only=True)
            ).abs().sort_values(ascending=False).head(10)
            for feat, delta in diff.items():
                fp_patterns.append(
                    {
                        "disorder": disorder,
                        "feature": feat,
                        "abs_mean_delta_fp_vs_tn": float(delta),
                        "fp_mean": float(X_test.loc[fp_mask, feat].mean()),
                        "tn_mean": float(X_test.loc[tn_mask, feat].mean()),
                    }
                )

    pd.DataFrame(rows).sort_values("disorder").to_csv(dirs["audit"] / "feature_quality_audit.csv", index=False)
    pd.DataFrame(fp_patterns).sort_values(["disorder", "abs_mean_delta_fp_vs_tn"], ascending=[True, False]).to_csv(
        dirs["audit"] / "false_positive_feature_patterns.csv",
        index=False,
    )

    pr_lines = ["# Feature Pruning Opportunity Report", ""]
    for row in pd.DataFrame(rows).sort_values("disorder").itertuples(index=False):
        if row.high_correlation_pairs_gt_0_90 > 25 or row.high_missing_feature_ratio_gt_40pct > 0.15:
            status = "high_pruning_opportunity"
        elif row.high_correlation_pairs_gt_0_90 > 10:
            status = "medium_pruning_opportunity"
        else:
            status = "low_pruning_opportunity"
        pr_lines.append(
            f"- {row.disorder}: n_features={row.n_features}, corr_pairs={row.high_correlation_pairs_gt_0_90}, "
            f"high_missing_ratio={row.high_missing_feature_ratio_gt_40pct:.3f}, status={status}."
        )
    _write_md(dirs["audit"] / "feature_pruning_opportunity_report.md", pr_lines)


def _error_rule(
    prob: float,
    threshold: float,
    missing_ratio: float,
    other_targets: int,
    vote_count: float,
    disorder: str,
    row: pd.Series,
) -> str:
    if abs(prob - threshold) <= 0.05:
        return "threshold_borderline"
    if missing_ratio >= 0.30:
        return "missingness_critical"
    if other_targets >= 2:
        return "comorbidity_close"
    if vote_count in (1, 2):
        return "label_ambiguity"
    if disorder in {"depression", "anxiety"} and float(row.get("cbcl_internalizing_proxy", 0) or 0) > 4:
        return "transdiagnostic_pattern"
    if disorder in {"conduct", "adhd"} and float(row.get("cbcl_externalizing_proxy", 0) or 0) > 4:
        return "transdiagnostic_pattern"
    if vote_count >= 3 and prob > threshold:
        return "clinically_similar_pattern"
    return "noise_uninterpretable"


def audit_error_patterns(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    master = _master_strict(root)
    master["participant_id"] = master["participant_id"].astype(str)
    votes = build_source_vote_table(root, master["participant_id"].tolist())
    merged_master = master.merge(votes, on="participant_id", how="left")

    rows: List[Dict[str, Any]] = []
    for disorder, ctx in contexts.items():
        part_test = ctx.test_df["participant_id"].astype(str)
        X_test = ctx.test_df[ctx.feature_columns].copy()
        y_true = ctx.y_test
        prob = _predict_prob(ctx, X_test)
        pred = (prob >= ctx.threshold).astype(int)
        base = merged_master.set_index("participant_id")

        for i, pid in enumerate(part_test.tolist()):
            yt = int(y_true[i])
            yp = int(pred[i])
            if yt == yp:
                continue
            row = base.loc[pid] if pid in base.index else pd.Series(dtype=float)
            err = "FP" if yp == 1 and yt == 0 else "FN"
            miss_ratio = float(ctx.test_df.iloc[i][ctx.feature_columns].isna().mean())
            other_targets = int(sum(int(row.get(TARGET_COL[d], 0) or 0) for d in TARGETS if d != disorder)) if not row.empty else 0
            vote_count = float(row.get(f"{disorder}_vote_count", np.nan)) if not row.empty else float("nan")
            taxonomy = _error_rule(prob[i], ctx.threshold, miss_ratio, other_targets, vote_count, disorder, row)
            rows.append(
                {
                    "disorder": disorder,
                    "model_version": ctx.model_version,
                    "participant_id": pid,
                    "error_type": err,
                    "taxonomy_class": taxonomy,
                    "probability": float(prob[i]),
                    "threshold": float(ctx.threshold),
                    "missing_ratio": miss_ratio,
                    "other_target_count": other_targets,
                    "source_vote_count": vote_count,
                }
            )

    err_df = pd.DataFrame(rows)
    err_df.to_csv(dirs["audit"] / "error_taxonomy.csv", index=False)

    for err_type, filename, title in [
        ("FP", "false_positive_audit.md", "False Positive Audit"),
        ("FN", "false_negative_audit.md", "False Negative Audit"),
    ]:
        lines = [f"# {title}", ""]
        sub = err_df[err_df["error_type"] == err_type]
        if sub.empty:
            lines.append("- No cases found.")
        else:
            grp = sub.groupby(["disorder", "taxonomy_class"]).size().reset_index(name="count")
            for row in grp.sort_values(["disorder", "count"], ascending=[True, False]).itertuples(index=False):
                lines.append(f"- {row.disorder} | {row.taxonomy_class}: {row.count}")
        _write_md(dirs["audit"] / filename, lines)

    driver = ["# Error Driver Summary", ""]
    if err_df.empty:
        driver.append("- No FP/FN errors available.")
    else:
        summary = err_df.groupby(["disorder", "taxonomy_class"]).size().reset_index(name="count")
        for disorder in TARGETS:
            sub = summary[summary["disorder"] == disorder].sort_values("count", ascending=False).head(3)
            if sub.empty:
                continue
            driver.append(f"- {disorder}: " + ", ".join([f"{r.taxonomy_class} ({r.count})" for r in sub.itertuples(index=False)]))
    _write_md(dirs["audit"] / "error_driver_summary.md", driver)


def audit_thresholds_and_calibration(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    sweep_rows: List[Dict[str, Any]] = []
    cal_rows: List[Dict[str, Any]] = []
    abst_rows: List[Dict[str, Any]] = []
    diag_lines = ["# Ranking vs Threshold Diagnosis", ""]
    for disorder, ctx in contexts.items():
        X_val = ctx.val_df[ctx.feature_columns].copy()
        X_test = ctx.test_df[ctx.feature_columns].copy()
        y_val = ctx.y_val
        y_test = ctx.y_test
        val_prob = _predict_prob(ctx, X_val)
        test_prob = _predict_prob(ctx, X_test)

        # candidate thresholds
        cand = threshold_candidates(y_val, val_prob, sensitivity_target=0.85)
        methods = {"fixed_0_5": 0.5}
        for method in ["youden_j", "best_f1", "sensitivity_priority"]:
            sub = cand[cand["method"] == method]
            if not sub.empty:
                methods[method] = float(sub.iloc[0]["threshold"])

        # precision-constrained
        selected, full_diag = optimize_precision_thresholds(
            y_true=y_val,
            y_prob=val_prob,
            policy=PrecisionThresholdPolicy(
                recall_floor=0.65 if disorder != "elimination" else 0.45,
                balanced_accuracy_floor=0.55,
            ),
        )
        methods["precision_constrained"] = float(selected["threshold"])

        grid = np.linspace(0.05, 0.95, 37)
        for split, y, p in [("validation", y_val, val_prob), ("test", y_test, test_prob)]:
            for thr in grid:
                m = binary_metrics(y, p, threshold=float(thr))
                sweep_rows.append(
                    {
                        "disorder": disorder,
                        "model_version": ctx.model_version,
                        "split": split,
                        "threshold": float(thr),
                        "method": "grid",
                        "precision": float(m["precision"]),
                        "recall": float(m["recall"]),
                        "specificity": float(m["specificity"]),
                        "balanced_accuracy": float(m["balanced_accuracy"]),
                        "f1": float(m["f1"]),
                        "roc_auc": float(m["roc_auc"]),
                        "pr_auc": float(m["pr_auc"]),
                        "brier_score": float(m["brier_score"]),
                        "fpr": float(1.0 - m["specificity"]),
                        "fnr": float(1.0 - m["recall"]),
                    }
                )
            for name, thr in methods.items():
                m = binary_metrics(y, p, threshold=float(thr))
                sweep_rows.append(
                    {
                        "disorder": disorder,
                        "model_version": ctx.model_version,
                        "split": split,
                        "threshold": float(thr),
                        "method": name,
                        "precision": float(m["precision"]),
                        "recall": float(m["recall"]),
                        "specificity": float(m["specificity"]),
                        "balanced_accuracy": float(m["balanced_accuracy"]),
                        "f1": float(m["f1"]),
                        "roc_auc": float(m["roc_auc"]),
                        "pr_auc": float(m["pr_auc"]),
                        "brier_score": float(m["brier_score"]),
                        "fpr": float(1.0 - m["specificity"]),
                        "fnr": float(1.0 - m["recall"]),
                    }
                )

        for split, y, p in [("validation", y_val, val_prob), ("test", y_test, test_prob)]:
            cal_rows.append(
                {
                    "disorder": disorder,
                    "model_version": ctx.model_version,
                    "split": split,
                    "brier_score": float(np.mean((p - y) ** 2)),
                    "ece_10bins": _compute_ece(y, p, n_bins=10),
                    "roc_auc": float(roc_auc_score(y, p)),
                    "pr_auc": float(average_precision_score(y, p)),
                }
            )

        abst_val, abst_grid = evaluate_abstention_policy(
            y_true=y_val,
            y_prob=val_prob,
            base_threshold=methods["precision_constrained"],
            target_high_precision=0.75 if disorder != "elimination" else 0.55,
            min_confident_coverage=0.1,
        )
        low_thr = float(abst_val["low_threshold"])
        high_thr = float(abst_val["high_threshold"])
        abst_test = _apply_abstention_thresholds(y_test, test_prob, low_thr, high_thr)
        abst_rows.append(
            {
                "disorder": disorder,
                "model_version": ctx.model_version,
                "split": "validation",
                **abst_val,
            }
        )
        abst_rows.append(
            {
                "disorder": disorder,
                "model_version": ctx.model_version,
                "split": "test",
                "low_threshold": low_thr,
                "high_threshold": high_thr,
                **abst_test,
            }
        )
        abst_grid.to_csv(dirs["diagnostics"] / f"abstention_grid_{disorder}.csv", index=False)

        # ranking vs threshold diagnosis
        base_prec = binary_metrics(y_val, val_prob, threshold=ctx.threshold)["precision"]
        best_prec = float(
            max(
                binary_metrics(y_val, val_prob, threshold=float(t))["precision"]
                for t in np.linspace(0.05, 0.95, 37)
            )
        )
        roc = float(roc_auc_score(y_val, val_prob))
        pr = float(average_precision_score(y_val, val_prob))
        if roc >= 0.84 and (best_prec - base_prec) >= 0.08:
            status = "threshold_operating_point_is_primary_bottleneck"
        elif roc < 0.76 or pr < 0.35:
            status = "ranking_capacity_is_primary_bottleneck"
        else:
            status = "mixed_ranking_and_threshold_limitations"
        diag_lines.append(
            f"- {disorder}: roc_auc_val={roc:.3f}, pr_auc_val={pr:.3f}, "
            f"precision_gain_possible_from_threshold={best_prec-base_prec:.3f}, diagnosis={status}."
        )

    pd.DataFrame(sweep_rows).to_csv(dirs["audit"] / "threshold_sweep_results.csv", index=False)
    pd.DataFrame(cal_rows).to_csv(dirs["audit"] / "calibration_audit.csv", index=False)
    pd.DataFrame(abst_rows).to_csv(dirs["audit"] / "abstention_policy_audit.csv", index=False)
    _write_md(dirs["audit"] / "ranking_vs_threshold_diagnosis.md", diag_lines)


def audit_class_imbalance(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    imbalance_rows: List[Dict[str, Any]] = []
    intervention_rows: List[Dict[str, Any]] = []
    for disorder, ctx in contexts.items():
        y_tr = ctx.y_train
        pos = int((y_tr == 1).sum())
        neg = int((y_tr == 0).sum())
        ratio = _safe_div(pos, neg)
        imbalance_rows.append(
            {
                "disorder": disorder,
                "model_version": ctx.model_version,
                "train_positive": pos,
                "train_negative": neg,
                "train_pos_neg_ratio": ratio,
                "prevalence_train": float(np.mean(y_tr)),
            }
        )

        X_train = ctx.train_df[ctx.feature_columns].copy()
        y_train = ctx.y_train.copy()
        X_val = ctx.val_df[ctx.feature_columns].copy()
        y_val = ctx.y_val.copy()

        # derive base params from champion metadata when available
        params = {}
        if isinstance(ctx.metadata.get("best_params"), dict):
            params = ctx.metadata["best_params"]

        strategies = [
            ("class_weight_none", "none"),
            ("class_weight_balanced", "balanced"),
            ("class_weight_balanced_subsample", "balanced_subsample"),
        ]
        for label, cw in strategies:
            override = None if cw == "none" else cw
            model = _fit_rf_with_params(X_train, y_train, params, class_weight_override=override)
            prob = model.predict_proba(X_val)[:, 1]
            sel, _ = optimize_precision_thresholds(
                y_val,
                prob,
                PrecisionThresholdPolicy(
                    recall_floor=0.65 if disorder != "elimination" else 0.45,
                    balanced_accuracy_floor=0.55,
                ),
            )
            m = binary_metrics(y_val, prob, float(sel["threshold"]))
            intervention_rows.append(
                {
                    "disorder": disorder,
                    "strategy": label,
                    "precision_val": float(m["precision"]),
                    "recall_val": float(m["recall"]),
                    "balanced_accuracy_val": float(m["balanced_accuracy"]),
                    "threshold": float(sel["threshold"]),
                }
            )

        # undersampling / oversampling in train only
        df_train = X_train.copy()
        df_train["__y__"] = y_train
        cls0 = df_train[df_train["__y__"] == 0]
        cls1 = df_train[df_train["__y__"] == 1]
        if len(cls0) >= 5 and len(cls1) >= 5:
            if len(cls0) >= len(cls1):
                maj = cls0
                mino = cls1
            else:
                maj = cls1
                mino = cls0
            # undersample
            maj_down = resample(
                maj,
                replace=False,
                n_samples=min(len(mino), len(maj)),
                random_state=RANDOM_STATE,
            )
            under = pd.concat([maj_down, mino], axis=0).sample(frac=1.0, random_state=RANDOM_STATE)
            model = _fit_rf_with_params(under.drop(columns="__y__"), under["__y__"].to_numpy(dtype=int), params)
            prob = model.predict_proba(X_val)[:, 1]
            sel, _ = optimize_precision_thresholds(y_val, prob, PrecisionThresholdPolicy(0.55 if disorder != "elimination" else 0.40, 0.52))
            m = binary_metrics(y_val, prob, float(sel["threshold"]))
            intervention_rows.append(
                {
                    "disorder": disorder,
                    "strategy": "undersample_majority_train_only",
                    "precision_val": float(m["precision"]),
                    "recall_val": float(m["recall"]),
                    "balanced_accuracy_val": float(m["balanced_accuracy"]),
                    "threshold": float(sel["threshold"]),
                }
            )

            # oversample
            mino_up = resample(mino, replace=True, n_samples=len(maj), random_state=RANDOM_STATE)
            over = pd.concat([maj, mino_up], axis=0).sample(frac=1.0, random_state=RANDOM_STATE)
            model = _fit_rf_with_params(over.drop(columns="__y__"), over["__y__"].to_numpy(dtype=int), params)
            prob = model.predict_proba(X_val)[:, 1]
            sel, _ = optimize_precision_thresholds(y_val, prob, PrecisionThresholdPolicy(0.55 if disorder != "elimination" else 0.40, 0.52))
            m = binary_metrics(y_val, prob, float(sel["threshold"]))
            intervention_rows.append(
                {
                    "disorder": disorder,
                    "strategy": "oversample_minority_train_only",
                    "precision_val": float(m["precision"]),
                    "recall_val": float(m["recall"]),
                    "balanced_accuracy_val": float(m["balanced_accuracy"]),
                    "threshold": float(sel["threshold"]),
                }
            )

    pd.DataFrame(imbalance_rows).to_csv(dirs["audit"] / "class_imbalance_audit.csv", index=False)
    interventions = pd.DataFrame(intervention_rows).sort_values(["disorder", "precision_val"], ascending=[True, False])
    interventions.to_csv(dirs["audit"] / "imbalance_intervention_results.csv", index=False)

    lines = ["# PPV Prevalence Analysis", ""]
    for row in pd.DataFrame(imbalance_rows).itertuples(index=False):
        lines.append(
            f"- {row.disorder}: prevalence_train={row.prevalence_train:.3f}, pos_neg_ratio={row.train_pos_neg_ratio:.3f}. "
            "Low prevalence mechanically limits PPV unless specificity is very high."
        )
    _write_md(dirs["audit"] / "ppv_prevalence_analysis.md", lines)


def run_diagnostic_hypotheses(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    hypotheses = []
    results = []

    source_votes = build_source_vote_table(root, _master_strict(root)["participant_id"].astype(str).tolist())
    vote_idx = source_votes.set_index("participant_id")

    for disorder in ["depression", "conduct", "elimination"]:
        ctx = contexts[disorder]
        X_train = ctx.train_df[ctx.feature_columns].copy()
        y_train = ctx.y_train.copy()
        X_val = ctx.val_df[ctx.feature_columns].copy()
        y_val = ctx.y_val.copy()

        # H1 threshold-only constrained precision
        val_prob = _predict_prob(ctx, X_val)
        sel, _ = optimize_precision_thresholds(
            y_true=y_val,
            y_prob=val_prob,
            policy=PrecisionThresholdPolicy(
                recall_floor=0.65 if disorder != "elimination" else 0.45,
                balanced_accuracy_floor=0.55,
            ),
        )
        m = binary_metrics(y_val, val_prob, float(sel["threshold"]))
        hypotheses.append({"hypothesis_id": f"{disorder}_H1", "disorder": disorder, "hypothesis": "threshold_only_precision_constrained", "expected_effect": "precision_up"})
        results.append(
            {
                "hypothesis_id": f"{disorder}_H1",
                "disorder": disorder,
                "experiment": "threshold_only_precision_constrained",
                "precision_val": float(m["precision"]),
                "recall_val": float(m["recall"]),
                "balanced_accuracy_val": float(m["balanced_accuracy"]),
                "status": "executed",
            }
        )

        # H2 compact MI top-k retrain
        numeric = X_train.copy()
        target_k = 18 if disorder != "elimination" else 24
        score = numeric.apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0)).var(axis=0).sort_values(ascending=False)
        keep = score.head(min(target_k, len(score))).index.tolist()
        Xtr2, Xva2 = X_train[keep], X_val[keep]
        model2 = _fit_rf_with_params(Xtr2, y_train, params={}, class_weight_override="balanced_subsample")
        prob2 = model2.predict_proba(Xva2)[:, 1]
        sel2, _ = optimize_precision_thresholds(y_val, prob2, PrecisionThresholdPolicy(0.6 if disorder != "elimination" else 0.4, 0.52))
        m2 = binary_metrics(y_val, prob2, float(sel2["threshold"]))
        hypotheses.append({"hypothesis_id": f"{disorder}_H2", "disorder": disorder, "hypothesis": "compact_feature_subset_retrain", "expected_effect": "precision_up_if_noise_driven"})
        results.append(
            {
                "hypothesis_id": f"{disorder}_H2",
                "disorder": disorder,
                "experiment": "compact_feature_subset_retrain",
                "precision_val": float(m2["precision"]),
                "recall_val": float(m2["recall"]),
                "balanced_accuracy_val": float(m2["balanced_accuracy"]),
                "status": "executed",
            }
        )

        # H3 high-confidence target filtering on train
        train_ids = ctx.train_df["participant_id"].astype(str).tolist()
        train_votes = vote_idx.loc[train_ids, f"{disorder}_vote_count"].fillna(0) if len(train_ids) else pd.Series(dtype=float)
        keep_mask = (train_votes >= 3) | (train_votes == 0)
        if keep_mask.any() and keep_mask.sum() >= 100:
            Xtr3 = X_train.loc[keep_mask.values]
            ytr3 = y_train[keep_mask.values]
            model3 = _fit_rf_with_params(Xtr3, ytr3, params={}, class_weight_override="balanced_subsample")
            prob3 = model3.predict_proba(X_val)[:, 1]
            sel3, _ = optimize_precision_thresholds(y_val, prob3, PrecisionThresholdPolicy(0.6 if disorder != "elimination" else 0.4, 0.52))
            m3 = binary_metrics(y_val, prob3, float(sel3["threshold"]))
            status = "executed"
        else:
            m3 = {"precision": np.nan, "recall": np.nan, "balanced_accuracy": np.nan}
            status = "insufficient_support"
        hypotheses.append({"hypothesis_id": f"{disorder}_H3", "disorder": disorder, "hypothesis": "high_confidence_target_train_filter", "expected_effect": "precision_up_if_label_noise_driven"})
        results.append(
            {
                "hypothesis_id": f"{disorder}_H3",
                "disorder": disorder,
                "experiment": "high_confidence_target_train_filter",
                "precision_val": float(m3["precision"]) if pd.notna(m3["precision"]) else np.nan,
                "recall_val": float(m3["recall"]) if pd.notna(m3["recall"]) else np.nan,
                "balanced_accuracy_val": float(m3["balanced_accuracy"]) if pd.notna(m3["balanced_accuracy"]) else np.nan,
                "status": status,
            }
        )

    hyp_df = pd.DataFrame(hypotheses)
    res_df = pd.DataFrame(results)
    hyp_df.to_csv(dirs["audit"] / "hypothesis_test_matrix.csv", index=False)
    res_df.to_csv(dirs["audit"] / "diagnostic_experiment_results.csv", index=False)

    wm = ["# What Moves Precision", ""]
    for disorder in ["depression", "conduct", "elimination"]:
        sub = res_df[(res_df["disorder"] == disorder) & (res_df["status"] == "executed")].sort_values("precision_val", ascending=False)
        if sub.empty:
            wm.append(f"- {disorder}: no executable hypotheses with sufficient support.")
            continue
        top = sub.iloc[0]
        wm.append(
            f"- {disorder}: best diagnostic intervention={top['experiment']} "
            f"(precision_val={top['precision_val']:.3f}, recall_val={top['recall_val']:.3f}, bal_acc_val={top['balanced_accuracy_val']:.3f})."
        )
    _write_md(dirs["audit"] / "what_moves_precision.md", wm)


def build_disorder_bottleneck_matrix(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    target_quality = pd.read_csv(dirs["audit"] / "target_quality_audit.csv")
    dsm = pd.read_csv(dirs["audit"] / "dsm5_feature_alignment_matrix.csv")
    learning = pd.read_csv(dirs["audit"] / "learning_curves_summary.csv")
    thresh = pd.read_csv(dirs["audit"] / "threshold_sweep_results.csv")
    precision_exp = pd.read_csv(dirs["audit"] / "diagnostic_experiment_results.csv")

    rows = []
    md_lines = ["# Per-Disorder Precision Diagnosis", ""]
    for disorder in TARGETS:
        ctx = contexts[disorder]
        base_metrics = ctx.metadata.get("test_metrics", {})
        if not base_metrics and ctx.source_model_id:
            src_res = _read_json(root / "reports" / "training" / ctx.source_model_id / "result.json")
            base_metrics = src_res.get("test_metrics", {})
        current_precision = float(base_metrics.get("precision", np.nan))

        tq = target_quality[target_quality["disorder"] == disorder]
        noise = float(tq.iloc[0]["label_noise_risk_index"]) if not tq.empty else np.nan
        dsm_sub = dsm[dsm["disorder"] == disorder]
        absent = int((dsm_sub["mapping_quality"] == "absent").sum()) if not dsm_sub.empty else 0
        medium = int((dsm_sub["mapping_quality"] == "medium").sum()) if not dsm_sub.empty else 0

        lc = learning[learning["disorder"] == disorder].sort_values("fraction_train_used")
        learning_delta = float(lc.iloc[-1]["precision_val"] - lc.iloc[0]["precision_val"]) if len(lc) >= 2 else 0.0

        sweep = thresh[(thresh["disorder"] == disorder) & (thresh["split"] == "validation")]
        best_val_prec = float(sweep["precision"].max()) if not sweep.empty else current_precision
        short_ceiling = min(0.99, max(current_precision, best_val_prec))

        exp_sub = precision_exp[(precision_exp["disorder"] == disorder) & (precision_exp["status"] == "executed")]
        if not exp_sub.empty:
            short_ceiling = max(short_ceiling, float(exp_sub["precision_val"].max()))
        medium_ceiling = min(0.99, short_ceiling + 0.05)

        if noise >= 0.22:
            bottleneck = "target_quality_and_label_ambiguity"
            confidence = "high"
            action = "introduce high-confidence targets and uncertain-case handling"
        elif absent >= 1 or medium >= 2:
            bottleneck = "dsm5_representation_gap"
            confidence = "medium"
            action = "improve criterion-specific features and questionnaire coverage"
        elif learning_delta > 0.04:
            bottleneck = "effective_sample_size"
            confidence = "medium"
            action = "increase high-quality sample coverage for key instruments"
        elif best_val_prec - current_precision > 0.08:
            bottleneck = "operating_threshold_and_calibration"
            confidence = "high"
            action = "deploy precision operating mode with constrained threshold/abstention"
        else:
            bottleneck = "feature_specificity_limit"
            confidence = "medium"
            action = "compact clinically specific feature subsets and monitor drift"

        rows.append(
            {
                "disorder": disorder,
                "current_champion": ctx.model_version,
                "current_precision": current_precision,
                "estimated_precision_ceiling_short_term": short_ceiling,
                "estimated_precision_ceiling_medium_term": medium_ceiling,
                "main_bottleneck": bottleneck,
                "recommended_next_action": action,
                "confidence_in_diagnosis_of_bottleneck": confidence,
            }
        )
        md_lines.append(
            f"- {disorder}: current_precision={current_precision:.3f}, short_term_ceiling={short_ceiling:.3f}, "
            f"bottleneck={bottleneck}, next_action={action}, confidence={confidence}."
        )

    matrix = pd.DataFrame(rows).sort_values("disorder")
    matrix.to_csv(dirs["audit"] / "disorder_bottleneck_matrix.csv", index=False)
    _write_md(dirs["audit"] / "per_disorder_precision_diagnosis.md", md_lines)


def export_precision_strategy_docs(root: Path, dirs: Dict[str, Path], contexts: Dict[str, ChampionContext]) -> None:
    bottleneck = pd.read_csv(dirs["audit"] / "disorder_bottleneck_matrix.csv")
    roadmap_rows = [
        {
            "phase": "quick_win",
            "action": "Enable precision operating mode with constrained threshold + abstention band for depression and conduct.",
            "hypothesis_causal": "Decision threshold is suboptimal for PPV in part of the disorders.",
            "cost_estimate": "low",
            "methodological_risk": "low",
            "expected_precision_impact": "medium_positive",
            "expected_recall_impact": "negative_if_no_abstention_management",
            "priority": "P1",
            "requires_new_data_or_questionnaire": "no",
            "thesis_ready": "yes",
            "web_app_ready": "yes",
        },
        {
            "phase": "medium_effort_high_impact",
            "action": "Introduce high-confidence target variants and uncertain-case audit loop for depression/conduct/elimination.",
            "hypothesis_causal": "Label ambiguity and mixed-confidence positives cap PPV.",
            "cost_estimate": "medium",
            "methodological_risk": "medium",
            "expected_precision_impact": "high_positive",
            "expected_recall_impact": "moderate_negative",
            "priority": "P1",
            "requires_new_data_or_questionnaire": "partial",
            "thesis_ready": "yes",
            "web_app_ready": "partial",
        },
        {
            "phase": "long_term_structural",
            "action": "Redesign questionnaire items to strengthen DSM-5 specificity for conduct and elimination.",
            "hypothesis_causal": "Current features are too transdiagnostic, causing FP inflation.",
            "cost_estimate": "high",
            "methodological_risk": "medium",
            "expected_precision_impact": "high_positive",
            "expected_recall_impact": "neutral_to_positive",
            "priority": "P2",
            "requires_new_data_or_questionnaire": "yes",
            "thesis_ready": "yes",
            "web_app_ready": "future_release",
        },
        {
            "phase": "long_term_structural",
            "action": "Increase effective minority-class support with targeted instrument completion.",
            "hypothesis_causal": "PPV is prevalence-limited with sparse clinically specific data.",
            "cost_estimate": "high",
            "methodological_risk": "low",
            "expected_precision_impact": "medium_positive",
            "expected_recall_impact": "positive",
            "priority": "P2",
            "requires_new_data_or_questionnaire": "yes",
            "thesis_ready": "yes",
            "web_app_ready": "future_release",
        },
    ]
    roadmap = pd.DataFrame(roadmap_rows)
    roadmap.to_csv(dirs["audit"] / "precision_improvement_roadmap.csv", index=False)

    strat_lines = ["# Precision Improvement Strategy", ""]
    strat_lines.append("## Quick Wins")
    strat_lines.append("- Constrained precision thresholds + abstention for operational PPV control.")
    strat_lines.append("- Keep strict_no_leakage champion selection; only switch operating point in production mode.")
    strat_lines.append("")
    strat_lines.append("## Medium-term")
    strat_lines.append("- High-confidence target variants for diagnostics and controlled retraining.")
    strat_lines.append("- Compact feature subsets with stronger clinical specificity.")
    strat_lines.append("")
    strat_lines.append("## Long-term")
    strat_lines.append("- DSM-5-aligned questionnaire redesign and richer elimination-specific features.")
    _write_md(dirs["audit"] / "precision_improvement_strategy.md", strat_lines)

    thesis_lines = ["# Thesis-Ready Precision Diagnosis", ""]
    for row in bottleneck.itertuples(index=False):
        thesis_lines.append(
            f"- {row.disorder}: champion={row.current_champion}, precision={row.current_precision:.3f}, "
            f"bottleneck={row.main_bottleneck}, short_term_ceiling={row.estimated_precision_ceiling_short_term:.3f}."
        )
    thesis_lines.append("")
    thesis_lines.append("Limitations: synthetic cohort, potential label ambiguity, and transdiagnostic overlap constrain PPV interpretation.")
    _write_md(dirs["audit"] / "thesis_ready_precision_diagnosis.md", thesis_lines)

    product_lines = [
        "# Product-Ready Precision Recommendations",
        "",
        "## Operating Modes",
        "- sensitive: lower threshold, higher recall, expected lower PPV.",
        "- precise: constrained precision threshold with recall floor and bal-acc guardrail.",
        "- abstention-assisted: high-confidence outputs only; uncertain cases routed to manual review.",
        "",
        "## Immediate Product Actions",
        "- Deploy depression champion in precise mode; keep conduct/elimination in conservative mode.",
        "- For elimination, mark output explicitly as exploratory due to PPV ceiling and instability.",
    ]
    _write_md(dirs["audit"] / "product_ready_precision_recommendations.md", product_lines)


def _append_audit_trace(root: Path) -> None:
    line_path = root / "reports" / "versioning" / "experiment_lineage.csv"
    if line_path.exists():
        df = pd.read_csv(line_path)
    else:
        df = pd.DataFrame()
    row = {
        "experiment_id": f"audit_precision_bottleneck_{utcnow_iso().replace(':', '').replace('-', '')}",
        "model_version": "precision_bottleneck_audit",
        "parent_version": "",
        "disorder": "all",
        "change_type": "audit_run",
        "description": "Comprehensive precision bottleneck audit over champions/challengers and frozen splits.",
        "data_scope": "strict_no_leakage_primary",
        "dataset_name": "multiple",
        "feature_strategy": "audit_diagnostics",
        "class_balance_strategy": "diagnostic",
        "calibration_strategy": "diagnostic",
        "status": "completed",
        "timestamp": utcnow_iso(),
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True, sort=False)
    df.to_csv(line_path, index=False)


def run_precision_bottleneck_audit(root: Path) -> Dict[str, Any]:
    dirs = ensure_audit_dirs(root)
    ensure_versioning_dirs(root)
    contexts = _load_champion_contexts(root)
    LOGGER.info("Loaded champion contexts: %s", ", ".join(sorted(contexts.keys())))

    audit_target_quality(root, dirs, contexts)
    audit_dsm5_alignment(root, dirs, contexts)
    audit_dataset_coverage(root, dirs, contexts)
    audit_learning_curves(root, dirs, contexts)
    audit_feature_quality(root, dirs, contexts)
    audit_error_patterns(root, dirs, contexts)
    audit_thresholds_and_calibration(root, dirs, contexts)
    audit_class_imbalance(root, dirs, contexts)
    run_diagnostic_hypotheses(root, dirs, contexts)
    build_disorder_bottleneck_matrix(root, dirs, contexts)
    export_precision_strategy_docs(root, dirs, contexts)
    _append_audit_trace(root)

    # copies to diagnostics/roadmaps folders for navigation
    for src_name in [
        "threshold_sweep_results.csv",
        "calibration_audit.csv",
        "abstention_policy_audit.csv",
        "diagnostic_experiment_results.csv",
        "hypothesis_test_matrix.csv",
    ]:
        src = dirs["audit"] / src_name
        if src.exists():
            dst = dirs["diagnostics"] / src_name
            dst.write_bytes(src.read_bytes())
    for src_name in [
        "precision_improvement_roadmap.csv",
        "precision_improvement_strategy.md",
        "thesis_ready_precision_diagnosis.md",
        "product_ready_precision_recommendations.md",
    ]:
        src = dirs["audit"] / src_name
        if src.exists():
            dst = dirs["roadmaps"] / src_name
            dst.write_bytes(src.read_bytes())

    matrix = pd.read_csv(dirs["audit"] / "disorder_bottleneck_matrix.csv")
    summary = {
        "champions_audited": int(len(contexts)),
        "disorders": sorted(list(contexts.keys())),
        "avg_current_precision": float(matrix["current_precision"].mean()),
        "max_short_term_ceiling": float(matrix["estimated_precision_ceiling_short_term"].max()),
        "report_dir": str(dirs["audit"]),
    }
    artifact_summary = dict(summary)
    artifact_summary["generated_at_utc"] = utcnow_iso()
    (dirs["artifacts"] / "precision_bottleneck_audit_summary.json").write_text(
        json.dumps(artifact_summary, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run integral precision bottleneck audit.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    _setup_logging(args.verbose)
    root = Path(args.root).resolve()
    summary = run_precision_bottleneck_audit(root)
    LOGGER.info(
        "Precision bottleneck audit completed. champions=%d avg_precision=%.3f max_short_term_ceiling=%.3f",
        summary["champions_audited"],
        summary["avg_current_precision"],
        summary["max_short_term_ceiling"],
    )


if __name__ == "__main__":
    main()
