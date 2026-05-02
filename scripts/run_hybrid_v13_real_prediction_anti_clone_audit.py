#!/usr/bin/env python
from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

LINE = "hybrid_v13_real_prediction_anti_clone_audit"
BASE = ROOT / "data" / LINE
TABLES = BASE / "tables"
VALIDATION = BASE / "validation"
REPORTS = BASE / "reports"
PLOTS = BASE / "plots"

LOADER_PATH = ROOT / "api/services/questionnaire_v2_loader_service.py"
ACTIVE_V13_PATH = ROOT / "data/hybrid_active_modes_freeze_v13/tables/hybrid_active_models_30_modes.csv"
OP_V13_PATH = ROOT / "data/hybrid_operational_freeze_v13/tables/hybrid_operational_final_champions.csv"
SELECTION_REPORT_V13_PATH = ROOT / "data/hybrid_global_contract_compatible_rf_champion_selection_v13/reports/final_selection_report_v13.md"
ANTI_CLONE_PROXY_V13_PATH = ROOT / "data/hybrid_global_contract_compatible_rf_champion_selection_v13/validation/anti_clone_validator_v13.csv"
CONTRACT_VALIDATOR_V13_PATH = ROOT / "data/hybrid_global_contract_compatible_rf_champion_selection_v13/validation/contract_compatibility_validator_v13.csv"
GUARDRAIL_VALIDATOR_V13_PATH = ROOT / "data/hybrid_global_contract_compatible_rf_champion_selection_v13/validation/guardrail_validator_v13.csv"
DATASET_PATH = ROOT / "data/hybrid_no_external_scores_rebuild_v2/tables/hybrid_no_external_scores_dataset_ready.csv"

V10_SELECTED_PATH = ROOT / "data/hybrid_rf_max_real_metrics_v1/tables/selected_rf_champions_with_deltas_v11.csv"
V11_SELECTED_PATH = ROOT / "data/hybrid_final_rf_plus_maximize_metrics_v1/tables/selected_rf_champions_with_deltas_v12.csv"

SCRIPT_V10_PATH = ROOT / "scripts/run_hybrid_rf_max_real_metrics_v1.py"
SCRIPT_V11_PATH = ROOT / "scripts/run_hybrid_final_rf_plus_maximize_metrics_v1.py"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
WATCH = ["recall", "specificity", "roc_auc", "pr_auc"]
METRICS_CORE = ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]
METRICS_WITH_COUNTS = METRICS_CORE + ["tn", "fp", "fn", "tp", "threshold", "n_features"]
BASE_SEED = 20261101


@dataclass
class ArtifactResolution:
    artifacts_available: str
    artifact_path: str | None
    artifact_origin: str | None
    artifact_hash: str | None
    metadata_path: str | None
    metadata_hash: str | None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def mkdirs() -> None:
    for path in [BASE, TABLES, VALIDATION, REPORTS, PLOTS]:
        path.mkdir(parents=True, exist_ok=True)


def sf(value: Any, default: float = float("nan")) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def feats(value: Any) -> list[str]:
    return [x.strip() for x in str(value or "").split("|") if x.strip() and x.strip().lower() != "nan"]


def tcol(domain: str) -> str:
    return f"target_domain_{domain}_final"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


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


def detect_active_line_from_loader(loader_text: str) -> dict[str, Any]:
    active_match = re.search(r'hybrid_active_modes_freeze_(v\d+)', loader_text)
    op_match = re.search(r'hybrid_operational_freeze_(v\d+)', loader_text)
    active_line = active_match.group(1) if active_match else "por_confirmar"
    operational_line = op_match.group(1) if op_match else "por_confirmar"
    points_v13 = active_line == "v13" and operational_line == "v13"
    return {
        "loader_active_line": active_line,
        "loader_operational_line": operational_line,
        "loader_points_v13": "yes" if points_v13 else "no",
    }


def external_artifact_roots() -> list[tuple[str, Path]]:
    parent = ROOT.parent
    return [
        ("current_repo", ROOT / "models" / "active_modes"),
        ("worktree_rf_max_real_metrics", parent / "cognia_app_rf_max_real_metrics" / "models" / "active_modes"),
        ("worktree_final_rf_plus", parent / "cognia_app_final_rf_plus_maximize" / "models" / "active_modes"),
    ]


def resolve_artifact_and_metadata(model_id: str) -> ArtifactResolution:
    metadata_path = ROOT / "models" / "active_modes" / model_id / "metadata.json"
    metadata_hash = None
    metadata_path_out = None
    if metadata_path.exists():
        metadata_path_out = str(metadata_path.relative_to(ROOT)).replace("\\", "/")
        metadata_hash = sha256_file(metadata_path)

    for origin, base in external_artifact_roots():
        candidate = base / model_id / "pipeline.joblib"
        if candidate.exists():
            artifact_hash = sha256_file(candidate)
            try:
                rel = candidate.relative_to(ROOT)
                artifact_rel = str(rel).replace("\\", "/")
            except Exception:
                artifact_rel = str(candidate)
            return ArtifactResolution(
                artifacts_available="yes",
                artifact_path=artifact_rel,
                artifact_origin=origin,
                artifact_hash=artifact_hash,
                metadata_path=metadata_path_out,
                metadata_hash=metadata_hash,
            )

    return ArtifactResolution(
        artifacts_available="no",
        artifact_path=None,
        artifact_origin=None,
        artifact_hash=None,
        metadata_path=metadata_path_out,
        metadata_hash=metadata_hash,
    )


def load_pipeline_from_resolved_path(artifact_path: str | None) -> Any:
    if not artifact_path:
        return None
    path = Path(artifact_path)
    if not path.is_absolute():
        path = ROOT / artifact_path
    return joblib.load(path)


def metric_compare_records(
    row: pd.Series,
    recomputed: dict[str, Any],
    source_lookup: dict[str, dict[str, Any]],
    tolerance: float,
) -> list[dict[str, Any]]:
    model_id = str(row["active_model_id"])
    source = source_lookup.get(model_id, {})

    out: list[dict[str, Any]] = []
    for metric_name in METRICS_WITH_COUNTS:
        if metric_name in {"threshold", "n_features"}:
            registered_value = sf(row.get(metric_name), float("nan"))
            registered_source = "active_v13"
        elif metric_name in source:
            registered_value = sf(source.get(metric_name), float("nan"))
            registered_source = str(source.get("registered_source", "source_campaign"))
        else:
            registered_value = sf(row.get(metric_name), float("nan"))
            registered_source = "active_v13"

        recalculated_value = sf(recomputed.get(metric_name), float("nan"))

        if math.isnan(registered_value) or math.isnan(recalculated_value):
            abs_delta = float("nan")
            within = "por_confirmar"
        else:
            abs_delta = abs(registered_value - recalculated_value)
            within = "yes" if abs_delta <= tolerance else "no"

        out.append(
            {
                "domain": row["domain"],
                "role": row["role"],
                "mode": row["mode"],
                "active_model_id": model_id,
                "metric_name": metric_name,
                "registered_value": registered_value,
                "recomputed_value": recalculated_value,
                "abs_delta": abs_delta,
                "tolerance": tolerance,
                "within_tolerance": within,
                "registered_source": registered_source,
            }
        )
    return out


def shared_error_overlap(
    y_true: np.ndarray,
    pred_a: np.ndarray,
    pred_b: np.ndarray,
) -> tuple[float, int, int, int]:
    err_a = set(np.where(pred_a != y_true)[0].tolist())
    err_b = set(np.where(pred_b != y_true)[0].tolist())
    union = err_a | err_b
    inter = err_a & err_b
    overlap = float(len(inter) / len(union)) if union else 0.0
    return overlap, len(inter), len(err_a), len(err_b)


def correlation_or_nan(a: np.ndarray, b: np.ndarray) -> float:
    if np.std(a) <= 0 or np.std(b) <= 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def pairwise_rows(recomputed_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    slots_by_domain: dict[str, list[pd.Series]] = {}
    for _, r in recomputed_df.sort_values(["domain", "role", "mode"]).iterrows():
        slots_by_domain.setdefault(str(r["domain"]), []).append(r)

    for domain, slot_rows in slots_by_domain.items():
        if domain == "elimination":
            combos = list(itertools.combinations(slot_rows, 2))
        else:
            combos = []
            by_role: dict[str, list[pd.Series]] = {}
            for r in slot_rows:
                by_role.setdefault(str(r["role"]), []).append(r)
            for role_rows in by_role.values():
                combos.extend(itertools.combinations(role_rows, 2))

        for a, b in combos:
            pa = np.asarray(a["_probabilities"], dtype=float)
            pb = np.asarray(b["_probabilities"], dtype=float)
            pra = np.asarray(a["_predictions"], dtype=int)
            prb = np.asarray(b["_predictions"], dtype=int)
            y = np.asarray(a["_y_true"], dtype=int)

            if len(y) != len(np.asarray(b["_y_true"], dtype=int)):
                raise RuntimeError(f"holdout_length_mismatch_for_pair:{a['active_model_id']}:{b['active_model_id']}")

            corr = correlation_or_nan(pa, pb)
            agreement = float(np.mean(pra == prb))
            binary_identical = "yes" if np.array_equal(pra, prb) else "no"

            metrics_a = [sf(a[m], float("nan")) for m in METRICS_CORE]
            metrics_b = [sf(b[m], float("nan")) for m in METRICS_CORE]
            deltas = [abs(x - yv) for x, yv in zip(metrics_a, metrics_b) if not (math.isnan(x) or math.isnan(yv))]
            metric_max_delta = max(deltas) if deltas else float("nan")

            threshold_delta = abs(sf(a["threshold"], float("nan")) - sf(b["threshold"], float("nan")))
            feat_a = set(feats(a["feature_list_pipe"]))
            feat_b = set(feats(b["feature_list_pipe"]))
            feat_jaccard = float(len(feat_a & feat_b) / max(1, len(feat_a | feat_b)))

            overlap, shared_n, err_a_n, err_b_n = shared_error_overlap(y, pra, prb)

            same_confusion = (
                int(a["tn"]) == int(b["tn"])
                and int(a["fp"]) == int(b["fp"])
                and int(a["fn"]) == int(b["fn"])
                and int(a["tp"]) == int(b["tp"])
            )

            artifact_hash_equal = "yes" if (a["artifact_hash"] and b["artifact_hash"] and a["artifact_hash"] == b["artifact_hash"]) else "no"
            artifact_path_equal = "yes" if (a["artifact_path"] and b["artifact_path"] and a["artifact_path"] == b["artifact_path"]) else "no"

            real_hits = []
            if binary_identical == "yes":
                real_hits.append("binary_predictions_identical")
            if agreement >= 0.995 and (not math.isnan(corr)) and corr >= 0.995:
                real_hits.append("agreement_and_probability_corr_ge_0_995")
            if same_confusion and (not math.isnan(corr)) and corr >= 0.995:
                real_hits.append("same_confusion_and_probability_corr_ge_0_995")
            if threshold_delta <= 1e-12 and (not math.isnan(metric_max_delta)) and metric_max_delta <= 1e-12 and feat_jaccard >= 0.90:
                real_hits.append("same_threshold_same_main_metrics_high_feature_jaccard")
            if artifact_hash_equal == "yes":
                real_hits.append("same_artifact_hash")
            if artifact_path_equal == "yes":
                real_hits.append("same_loaded_artifact_path")

            near_hits = []
            if agreement >= 0.98:
                near_hits.append("prediction_agreement_ge_0_98")
            if (not math.isnan(corr)) and corr >= 0.98:
                near_hits.append("probability_correlation_ge_0_98")
            if (not math.isnan(metric_max_delta)) and metric_max_delta <= 0.005:
                near_hits.append("metric_max_abs_delta_le_0_005")
            if feat_jaccard >= 0.75:
                near_hits.append("feature_jaccard_ge_0_75")
            if threshold_delta <= 0.01:
                near_hits.append("threshold_almost_equal")
            if overlap >= 0.75:
                near_hits.append("shared_error_overlap_ge_0_75")

            row = {
                "domain": domain,
                "slot_a": f"{a['domain']}/{a['mode']}",
                "slot_b": f"{b['domain']}/{b['mode']}",
                "active_model_id_a": a["active_model_id"],
                "active_model_id_b": b["active_model_id"],
                "role_a": a["role"],
                "mode_a": a["mode"],
                "role_b": b["role"],
                "mode_b": b["mode"],
                "prediction_agreement": agreement,
                "probability_correlation": corr,
                "binary_predictions_identical": binary_identical,
                "metric_max_abs_delta": metric_max_delta,
                "threshold_abs_delta": threshold_delta,
                "feature_jaccard": feat_jaccard,
                "shared_error_overlap": overlap,
                "shared_error_intersection_n": shared_n,
                "error_count_a": err_a_n,
                "error_count_b": err_b_n,
                "same_confusion_matrix": "yes" if same_confusion else "no",
                "artifact_hash_equal": artifact_hash_equal,
                "artifact_path_equal": artifact_path_equal,
                "real_clone_flag": "yes" if real_hits else "no",
                "near_clone_warning": "yes" if near_hits else "no",
                "real_clone_reasons": "|".join(real_hits),
                "near_clone_reasons": "|".join(near_hits),
            }
            rows.append(row)

    return pd.DataFrame(rows)


def try_make_plots(recomputed_df: pd.DataFrame, pairwise_df: pd.DataFrame, reg_vs_recomp: pd.DataFrame) -> list[str]:
    generated: list[str] = []
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
    except Exception:
        return generated

    elim_pairs = pairwise_df[pairwise_df["domain"] == "elimination"].copy()
    if not elim_pairs.empty:
        slots = sorted(set(elim_pairs["slot_a"]).union(set(elim_pairs["slot_b"])))

        corr_mat = pd.DataFrame(np.eye(len(slots)), index=slots, columns=slots, dtype=float)
        agree_mat = pd.DataFrame(np.eye(len(slots)), index=slots, columns=slots, dtype=float)
        for _, r in elim_pairs.iterrows():
            a = r["slot_a"]
            b = r["slot_b"]
            corr_mat.loc[a, b] = r["probability_correlation"]
            corr_mat.loc[b, a] = r["probability_correlation"]
            agree_mat.loc[a, b] = r["prediction_agreement"]
            agree_mat.loc[b, a] = r["prediction_agreement"]

        plt.figure(figsize=(10, 8))
        sns.heatmap(corr_mat, annot=True, fmt=".3f", cmap="viridis", vmin=0.0, vmax=1.0)
        plt.title("Elimination Probability Correlation")
        plt.tight_layout()
        out = PLOTS / "elimination_probability_correlation_heatmap.png"
        plt.savefig(out, dpi=180)
        plt.close()
        generated.append(str(out.relative_to(ROOT)).replace("\\", "/"))

        plt.figure(figsize=(10, 8))
        sns.heatmap(agree_mat, annot=True, fmt=".3f", cmap="magma", vmin=0.0, vmax=1.0)
        plt.title("Elimination Prediction Agreement")
        plt.tight_layout()
        out = PLOTS / "elimination_prediction_agreement_heatmap.png"
        plt.savefig(out, dpi=180)
        plt.close()
        generated.append(str(out.relative_to(ROOT)).replace("\\", "/"))

        cms = recomputed_df[recomputed_df["domain"] == "elimination"].copy()
        n = len(cms)
        cols = 3
        rows = int(math.ceil(n / cols))
        fig, axes = plt.subplots(rows, cols, figsize=(15, 4 * rows))
        axes = np.array(axes).reshape(rows, cols)
        for idx, (_, r) in enumerate(cms.iterrows()):
            rr = idx // cols
            cc = idx % cols
            ax = axes[rr, cc]
            mat = np.array([[int(r["tn"]), int(r["fp"])], [int(r["fn"]), int(r["tp"])]], dtype=float)
            sns.heatmap(mat, annot=True, fmt=".0f", cmap="Blues", cbar=False, ax=ax)
            ax.set_title(f"{r['mode']} ({r['role']})")
            ax.set_xlabel("Pred")
            ax.set_ylabel("True")
        for idx in range(n, rows * cols):
            rr = idx // cols
            cc = idx % cols
            axes[rr, cc].axis("off")
        plt.tight_layout()
        out = PLOTS / "elimination_confusion_matrices.png"
        plt.savefig(out, dpi=180)
        plt.close()
        generated.append(str(out.relative_to(ROOT)).replace("\\", "/"))

    if not pairwise_df.empty:
        plt.figure(figsize=(13, 6))
        p = pairwise_df.copy()
        p["pair"] = p["slot_a"] + " vs " + p["slot_b"]
        p = p.sort_values(["domain", "prediction_agreement"], ascending=[True, False])
        sns.barplot(data=p, x="pair", y="prediction_agreement", hue="domain", dodge=False)
        plt.xticks(rotation=90)
        plt.ylim(0.0, 1.0)
        plt.title("Pairwise Prediction Agreement (All Domains)")
        plt.tight_layout()
        out = PLOTS / "all_domains_pairwise_prediction_agreement.png"
        plt.savefig(out, dpi=180)
        plt.close()
        generated.append(str(out.relative_to(ROOT)).replace("\\", "/"))

    if not reg_vs_recomp.empty:
        d = reg_vs_recomp.copy()
        d = d[d["metric_name"].isin(METRICS_CORE)]
        d = d[d["within_tolerance"] != "por_confirmar"]
        if not d.empty:
            plt.figure(figsize=(12, 5))
            sns.boxplot(data=d, x="metric_name", y="abs_delta")
            plt.yscale("log")
            plt.title("Registered vs Recomputed Metric Deltas (Abs)")
            plt.tight_layout()
            out = PLOTS / "registered_vs_recomputed_metric_deltas.png"
            plt.savefig(out, dpi=180)
            plt.close()
            generated.append(str(out.relative_to(ROOT)).replace("\\", "/"))

    return generated


def main() -> int:
    mkdirs()

    missing_required = [
        p
        for p in [
            LOADER_PATH,
            ACTIVE_V13_PATH,
            OP_V13_PATH,
            SELECTION_REPORT_V13_PATH,
            ANTI_CLONE_PROXY_V13_PATH,
            CONTRACT_VALIDATOR_V13_PATH,
            GUARDRAIL_VALIDATOR_V13_PATH,
            DATASET_PATH,
            SCRIPT_V10_PATH,
            SCRIPT_V11_PATH,
        ]
        if not p.exists()
    ]
    if missing_required:
        raise FileNotFoundError("missing_required_paths:" + "|".join(str(p) for p in missing_required))

    loader_text = LOADER_PATH.read_text(encoding="utf-8")
    loader_status = detect_active_line_from_loader(loader_text)

    active = pd.read_csv(ACTIVE_V13_PATH)
    contract_validator = pd.read_csv(CONTRACT_VALIDATOR_V13_PATH)
    guardrail_validator = pd.read_csv(GUARDRAIL_VALIDATOR_V13_PATH)

    data = pd.read_csv(DATASET_PATH)
    if "participant_id" not in data.columns:
        raise RuntimeError("dataset_missing_participant_id")

    split_map = split_registry(data)

    v10_selected = pd.read_csv(V10_SELECTED_PATH) if V10_SELECTED_PATH.exists() else pd.DataFrame()
    v11_selected = pd.read_csv(V11_SELECTED_PATH) if V11_SELECTED_PATH.exists() else pd.DataFrame()

    source_lookup: dict[str, dict[str, Any]] = {}
    for source_name, df in [("v10_selected_v11", v10_selected), ("v11_selected_v12", v11_selected)]:
        if df.empty:
            continue
        for _, r in df.iterrows():
            model_id = str(r.get("active_model_id", "")).strip()
            if not model_id:
                continue
            rec = {m: r.get(m) for m in METRICS_WITH_COUNTS if m in df.columns}
            rec["registered_source"] = source_name
            source_lookup[model_id] = rec

    recomputed_rows: list[dict[str, Any]] = []
    reg_vs_recomp_rows: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []

    tolerance_exact = 1e-6

    for _, row in active.sort_values(["domain", "role", "mode"]).iterrows():
        domain = str(row["domain"])
        role = str(row["role"])
        mode = str(row["mode"])
        model_id = str(row["active_model_id"])
        model_family = str(row.get("model_family", ""))
        feature_columns = feats(row.get("feature_list_pipe"))
        threshold = sf(row.get("threshold"), float("nan"))

        resolved = resolve_artifact_and_metadata(model_id)
        artifact_rows.append(
            {
                "domain": domain,
                "role": role,
                "mode": mode,
                "active_model_id": model_id,
                "artifacts_available": resolved.artifacts_available,
                "artifact_path": resolved.artifact_path,
                "artifact_origin": resolved.artifact_origin,
                "artifact_hash": resolved.artifact_hash,
                "metadata_path": resolved.metadata_path,
                "metadata_hash": resolved.metadata_hash,
            }
        )

        base_record = {
            "domain": domain,
            "role": role,
            "mode": mode,
            "active_model_id": model_id,
            "model_family": model_family,
            "model_key": model_id,
            "artifact_path": resolved.artifact_path,
            "artifact_origin": resolved.artifact_origin,
            "artifact_hash": resolved.artifact_hash,
            "metadata_path": resolved.metadata_path,
            "metadata_hash": resolved.metadata_hash,
            "threshold": threshold,
            "n_features": len(feature_columns),
            "feature_list_pipe": "|".join(feature_columns),
            "artifacts_available": resolved.artifacts_available,
            "prediction_recomputed": "no",
            "recompute_blocker": "",
            "probability_mean": float("nan"),
            "probability_std": float("nan"),
            "prediction_positive_rate": float("nan"),
            "holdout_n": float("nan"),
            "holdout_positive_n": float("nan"),
            "holdout_negative_n": float("nan"),
        }

        for m in METRICS_CORE + ["tn", "fp", "fn", "tp"]:
            base_record[m] = float("nan")

        base_record["_probabilities"] = np.array([], dtype=float)
        base_record["_predictions"] = np.array([], dtype=int)
        base_record["_y_true"] = np.array([], dtype=int)

        if resolved.artifacts_available != "yes" or not resolved.artifact_path:
            base_record["recompute_blocker"] = "artifact_unavailable"
            recomputed_rows.append(base_record)
            reg_vs_recomp_rows.extend(metric_compare_records(row, base_record, source_lookup, tolerance_exact))
            continue

        try:
            model = load_pipeline_from_resolved_path(resolved.artifact_path)
        except Exception as exc:
            base_record["recompute_blocker"] = f"artifact_load_error:{repr(exc)}"
            recomputed_rows.append(base_record)
            reg_vs_recomp_rows.extend(metric_compare_records(row, base_record, source_lookup, tolerance_exact))
            continue

        holdout_ids = split_map[domain]["holdout"]
        holdout = data[data["participant_id"].astype(str).isin(set(holdout_ids))].copy()
        y_true = holdout[tcol(domain)].astype(int).to_numpy()

        missing_cols = [f for f in feature_columns if f not in holdout.columns]
        if missing_cols:
            base_record["recompute_blocker"] = "missing_features_in_dataset:" + "|".join(missing_cols)
            recomputed_rows.append(base_record)
            reg_vs_recomp_rows.extend(metric_compare_records(row, base_record, source_lookup, tolerance_exact))
            continue

        x_holdout = prep_x(holdout, feature_columns)

        try:
            prob = np.asarray(model.predict_proba(x_holdout)[:, 1], dtype=float)
            prob = np.clip(prob, 1e-6, 1 - 1e-6)
        except Exception as exc:
            base_record["recompute_blocker"] = f"predict_proba_error:{repr(exc)}"
            recomputed_rows.append(base_record)
            reg_vs_recomp_rows.extend(metric_compare_records(row, base_record, source_lookup, tolerance_exact))
            continue

        pred = (prob >= threshold).astype(int)
        mm = compute_metrics(y_true, prob, threshold)

        base_record.update(mm)
        base_record["prediction_recomputed"] = "yes"
        base_record["recompute_blocker"] = ""
        base_record["probability_mean"] = float(np.mean(prob))
        base_record["probability_std"] = float(np.std(prob))
        base_record["prediction_positive_rate"] = float(np.mean(pred))
        base_record["holdout_n"] = int(len(y_true))
        base_record["holdout_positive_n"] = int(np.sum(y_true))
        base_record["holdout_negative_n"] = int(len(y_true) - np.sum(y_true))

        base_record["_probabilities"] = prob
        base_record["_predictions"] = pred
        base_record["_y_true"] = y_true

        recomputed_rows.append(base_record)
        reg_vs_recomp_rows.extend(metric_compare_records(row, base_record, source_lookup, tolerance_exact))

    recomputed_df = pd.DataFrame(recomputed_rows)
    reg_vs_recomp_df = pd.DataFrame(reg_vs_recomp_rows)
    artifact_df = pd.DataFrame(artifact_rows)

    per_slot_match_rows: list[dict[str, Any]] = []
    for _, slot in recomputed_df.iterrows():
        slot_metrics = reg_vs_recomp_df[
            (reg_vs_recomp_df["active_model_id"] == slot["active_model_id"]) & (reg_vs_recomp_df["within_tolerance"] != "por_confirmar")
        ]
        if slot["prediction_recomputed"] != "yes":
            match = "no"
        elif slot_metrics.empty:
            match = "por_confirmar"
        else:
            match = "yes" if (slot_metrics["within_tolerance"] == "yes").all() else "no"
        per_slot_match_rows.append(
            {
                "domain": slot["domain"],
                "role": slot["role"],
                "mode": slot["mode"],
                "active_model_id": slot["active_model_id"],
                "prediction_recomputed": slot["prediction_recomputed"],
                "artifacts_available": slot["artifacts_available"],
                "metrics_match_registered": match,
                "max_abs_delta_any_metric": slot_metrics["abs_delta"].max() if not slot_metrics.empty else float("nan"),
            }
        )
    per_slot_match_df = pd.DataFrame(per_slot_match_rows)

    pairwise_df = pairwise_rows(recomputed_df[recomputed_df["prediction_recomputed"] == "yes"].copy())
    elimination_pairwise_df = pairwise_df[pairwise_df["domain"] == "elimination"].copy()

    shared_error_df = pairwise_df[
        [
            "domain",
            "slot_a",
            "slot_b",
            "active_model_id_a",
            "active_model_id_b",
            "shared_error_overlap",
            "shared_error_intersection_n",
            "error_count_a",
            "error_count_b",
        ]
    ].copy()

    prob_summary_df = recomputed_df[
        [
            "domain",
            "role",
            "mode",
            "active_model_id",
            "probability_mean",
            "probability_std",
            "prediction_positive_rate",
            "holdout_n",
            "holdout_positive_n",
            "holdout_negative_n",
        ]
    ].copy()

    hash_inventory_df = artifact_df.copy()
    hash_inventory_df["duplicate_hash_group_size"] = (
        hash_inventory_df.groupby("artifact_hash")["artifact_hash"].transform("count")
    )
    hash_inventory_df.loc[hash_inventory_df["artifact_hash"].isna(), "duplicate_hash_group_size"] = 0

    artifact_duplicate_hash_count = int(
        hash_inventory_df[(hash_inventory_df["artifact_hash"].notna()) & (hash_inventory_df["duplicate_hash_group_size"] > 1)]["artifact_hash"].nunique()
    )

    elimination_real_clone_count = int((elimination_pairwise_df.get("real_clone_flag", pd.Series(dtype=str)) == "yes").sum())
    all_real_clone_count = int((pairwise_df.get("real_clone_flag", pd.Series(dtype=str)) == "yes").sum())
    all_near_clone_count = int((pairwise_df.get("near_clone_warning", pd.Series(dtype=str)) == "yes").sum())

    slots_total = int(len(recomputed_df))
    slots_recomputed = int((recomputed_df["prediction_recomputed"] == "yes").sum())
    slots_artifacts_available = int((recomputed_df["artifacts_available"] == "yes").sum())

    contract_yes_count = int((contract_validator.get("contract_compatible", pd.Series(dtype=str)).astype(str).str.lower() == "yes").sum())
    guardrail_violation_count = int((guardrail_validator.get("guardrail_violation", pd.Series(dtype=str)).astype(str).str.lower() == "yes").sum())

    if slots_recomputed < slots_total:
        final_status = "fail"
    elif all_real_clone_count > 0 or artifact_duplicate_hash_count > 0:
        final_status = "fail"
    elif all_near_clone_count > 0:
        final_status = "pass_with_warnings"
    else:
        final_status = "pass"

    validator_main = pd.DataFrame(
        [
            {
                "audit_line": LINE,
                "generated_at_utc": now_utc(),
                "loader_points_v13": loader_status["loader_points_v13"],
                "active_rows": slots_total,
                "prediction_recomputed_slots": slots_recomputed,
                "artifacts_available_slots": slots_artifacts_available,
                "metrics_match_yes_slots": int((per_slot_match_df["metrics_match_registered"] == "yes").sum()),
                "metrics_match_no_slots": int((per_slot_match_df["metrics_match_registered"] == "no").sum()),
                "elimination_real_clone_count": elimination_real_clone_count,
                "all_domains_real_clone_count": all_real_clone_count,
                "all_domains_near_clone_warning_count": all_near_clone_count,
                "artifact_duplicate_hash_count": artifact_duplicate_hash_count,
                "contract_compatible_yes_slots": contract_yes_count,
                "guardrail_violation_count": guardrail_violation_count,
                "final_audit_status": final_status,
            }
        ]
    )

    elimination_clone_validator = elimination_pairwise_df[
        [
            "slot_a",
            "slot_b",
            "prediction_agreement",
            "probability_correlation",
            "binary_predictions_identical",
            "metric_max_abs_delta",
            "threshold_abs_delta",
            "feature_jaccard",
            "shared_error_overlap",
            "real_clone_flag",
            "near_clone_warning",
            "real_clone_reasons",
            "near_clone_reasons",
        ]
    ].copy()

    out_recomputed = TABLES / "v13_recomputed_champion_metrics.csv"
    out_reg_vs_recomp = TABLES / "v13_registered_vs_recomputed_metrics.csv"
    out_pairwise = TABLES / "v13_pairwise_prediction_similarity_all_domains.csv"
    out_elim_pairwise = TABLES / "v13_elimination_real_prediction_similarity.csv"
    out_shared_error = TABLES / "v13_shared_error_overlap.csv"
    out_hashes = TABLES / "v13_artifact_hash_inventory.csv"
    out_prob_summary = TABLES / "v13_probability_distribution_summary.csv"

    save_csv(recomputed_df.drop(columns=["_probabilities", "_predictions", "_y_true"]), out_recomputed)
    save_csv(reg_vs_recomp_df, out_reg_vs_recomp)
    save_csv(pairwise_df, out_pairwise)
    save_csv(elimination_pairwise_df, out_elim_pairwise)
    save_csv(shared_error_df, out_shared_error)
    save_csv(hash_inventory_df, out_hashes)
    save_csv(prob_summary_df, out_prob_summary)

    out_main_validator = VALIDATION / "v13_real_prediction_anti_clone_validator.csv"
    out_metrics_match_validator = VALIDATION / "v13_recomputed_metrics_match_validator.csv"
    out_artifact_validator = VALIDATION / "v13_artifact_availability_validator.csv"
    out_elim_validator = VALIDATION / "v13_elimination_clone_risk_validator.csv"

    save_csv(validator_main, out_main_validator)
    save_csv(per_slot_match_df, out_metrics_match_validator)
    save_csv(artifact_df, out_artifact_validator)
    save_csv(elimination_clone_validator, out_elim_validator)

    plots_generated = try_make_plots(recomputed_df, pairwise_df, reg_vs_recomp_df)

    summary_lines = [
        "# v13 Real Prediction Anti-Clone Audit",
        "",
        f"Generated: `{now_utc()}`",
        "",
        "## Scope",
        "- Real prediction recomputation for all active v13 champions.",
        "- No retraining and no champion replacement in this audit.",
        "- Holdout reconstruction follows v10/v11/v12 split logic (participant_id stratified split).",
        "",
        "## Source Validation",
        f"- loader active line: `{loader_status['loader_active_line']}`",
        f"- loader operational line: `{loader_status['loader_operational_line']}`",
        f"- loader points to v13: `{loader_status['loader_points_v13']}`",
        f"- active rows: `{slots_total}`",
        f"- RF rows in active: `{int((active['model_family'].astype(str).str.lower() == 'rf').sum())}`",
        f"- contract_compatible yes (validator): `{contract_yes_count}`/`{len(contract_validator)}`",
        f"- guardrail violations (validator): `{guardrail_violation_count}`",
        "",
        "## Recompute Status",
        f"- prediction_recomputed yes: `{slots_recomputed}`/`{slots_total}`",
        f"- artifacts_available yes: `{slots_artifacts_available}`/`{slots_total}`",
        f"- metrics_match_registered yes: `{int((per_slot_match_df['metrics_match_registered'] == 'yes').sum())}`/`{slots_total}`",
        "",
        "## Anti-Clone Results",
        f"- all_domains_real_clone_count: `{all_real_clone_count}`",
        f"- elimination_real_clone_count: `{elimination_real_clone_count}`",
        f"- all_domains_near_clone_warning_count: `{all_near_clone_count}`",
        f"- artifact_duplicate_hash_count: `{artifact_duplicate_hash_count}`",
        f"- final_audit_status: `{final_status}`",
        "",
        "## Elimination Pairwise",
    ]

    if elimination_pairwise_df.empty:
        summary_lines.append("_No elimination pairs available._")
    else:
        cols = [
            "slot_a",
            "slot_b",
            "prediction_agreement",
            "probability_correlation",
            "binary_predictions_identical",
            "metric_max_abs_delta",
            "threshold_abs_delta",
            "feature_jaccard",
            "shared_error_overlap",
            "real_clone_flag",
            "near_clone_warning",
        ]
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        summary_lines.append(header)
        summary_lines.append(sep)
        for _, r in elimination_pairwise_df.iterrows():
            summary_lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")

    if plots_generated:
        summary_lines.extend(["", "## Plots", *[f"- `{p}`" for p in plots_generated]])

    summary_lines.extend(
        [
            "",
            "## Caveats",
            "- This audit validates prediction behavior using locally available artifacts; clinical claims remain screening/support only in simulated context.",
            "- If any slot had missing artifact or recomputation blocker, it is explicitly marked in tables and validators.",
        ]
    )

    write_text(REPORTS / "v13_real_prediction_anti_clone_report.md", "\n".join(summary_lines))

    print(
        json.dumps(
            {
                "status": "ok",
                "line": LINE,
                "loader_points_v13": loader_status["loader_points_v13"],
                "active_rows": slots_total,
                "prediction_recomputed_slots": slots_recomputed,
                "artifacts_available_slots": slots_artifacts_available,
                "all_domains_real_clone_count": all_real_clone_count,
                "elimination_real_clone_count": elimination_real_clone_count,
                "all_domains_near_clone_warning_count": all_near_clone_count,
                "artifact_duplicate_hash_count": artifact_duplicate_hash_count,
                "final_audit_status": final_status,
            },
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
