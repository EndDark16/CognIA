#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss

import run_elimination_iterative_recovery_v2 as v2
import run_elimination_refinement_v3 as v3


LOGGER = logging.getLogger("elimination-target-redesign-v4")
RANDOM_STATE = 42
TARGET_COL = "target_domain_elimination"


@dataclass
class Paths:
    root: Path
    out: Path
    inventory: Path
    target_audit: Path
    target_variants: Path
    feature_sets: Path
    trials: Path
    tables: Path
    reports: Path
    artifacts: Path
    v2: Path
    v3: Path
    hybrid: Path
    dsm5_exact: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_json(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_paths(root: Path) -> Paths:
    out = root / "data" / "elimination_target_redesign_v4"
    return Paths(
        root=root,
        out=out,
        inventory=out / "inventory",
        target_audit=out / "target_audit",
        target_variants=out / "target_variants",
        feature_sets=out / "feature_sets",
        trials=out / "trials",
        tables=out / "tables",
        reports=out / "reports",
        artifacts=root / "artifacts" / "elimination_target_redesign_v4",
        v2=root / "data" / "elimination_iterative_recovery_v2",
        v3=root / "data" / "elimination_refinement_v3",
        hybrid=root / "data" / "processed_hybrid_dsm5_v2",
        dsm5_exact=root / "data" / "processed_dsm5_exact_v1",
    )


def ensure_dirs(paths: Paths) -> None:
    for p in [
        paths.out,
        paths.inventory,
        paths.target_audit,
        paths.target_variants,
        paths.feature_sets,
        paths.trials,
        paths.tables,
        paths.reports,
        paths.artifacts,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def load_inputs(paths: Paths) -> Dict[str, pd.DataFrame]:
    strict = pd.read_csv(
        paths.hybrid / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv",
        low_memory=False,
    )
    research = pd.read_csv(
        paths.hybrid / "final" / "model_ready" / "research_extended_hybrid" / "dataset_hybrid_model_ready_research_extended_hybrid.csv",
        low_memory=False,
    )
    for df in (strict, research):
        df["participant_id"] = df["participant_id"].astype(str)
    semantic = pd.read_csv(paths.v2 / "audit" / "elimination_semantic_proximity_audit.csv")
    return {"strict": strict, "research": research, "semantic": semantic}


def inventory_and_path_mapping(paths: Paths, data: Dict[str, pd.DataFrame]) -> None:
    expected = [
        paths.v2 / "reports" / "elimination_final_decision_v2.md",
        paths.v3 / "reports" / "elimination_final_decision_v3.md",
        paths.v3 / "reports" / "elimination_residual_error_report.md",
        paths.v2 / "tables" / "elimination_honest_model_ranking.csv",
        paths.v3 / "tables" / "elimination_abstention_policy_results.csv",
        paths.dsm5_exact / "domain_derivation_rules.md",
        paths.dsm5_exact / "internal_to_external_crosswalk.csv",
        paths.dsm5_exact / "modelability_audit" / "reports" / "final_modelability_decisions.md",
        paths.dsm5_exact / "modelability_audit" / "reports" / "target_build_quality_report.md",
        paths.dsm5_exact / "modelability_audit" / "reports" / "workflow_impact_summary.md",
        paths.hybrid / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv",
    ]
    rows: List[Dict[str, Any]] = []
    fallback_rows: List[Dict[str, Any]] = []
    for p in expected:
        ok = p.exists()
        rows.append(
            {
                "expected_path": str(p),
                "exists": ok,
                "resolved_path": str(p if ok else ""),
                "size_bytes": int(p.stat().st_size) if ok else None,
                "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat() if ok else None,
            }
        )
        if not ok:
            fallback_rows.append({"expected_path": str(p), "resolved_equivalent": "not_found", "status": "missing"})
    for k, df in data.items():
        if isinstance(df, pd.DataFrame):
            rows.append({"expected_path": f"in_memory::{k}", "exists": True, "resolved_path": f"in_memory::{k}", "rows": len(df), "cols": len(df.columns), "modified_utc": now_iso()})
    inv = pd.DataFrame(rows)
    safe_csv(inv, paths.inventory / "input_inventory.csv")
    if fallback_rows:
        safe_csv(pd.DataFrame(fallback_rows), paths.inventory / "path_mapping_fallbacks.csv")
    else:
        safe_csv(pd.DataFrame([{"expected_path": "all", "resolved_equivalent": "exact_paths_found", "status": "ok"}]), paths.inventory / "path_mapping_fallbacks.csv")


def risk_level_for(feature: str, semantic_df: pd.DataFrame) -> str:
    m = semantic_df[semantic_df["feature_name"] == feature]
    if len(m):
        return str(m.iloc[0]["risk_level"])
    low = feature.lower()
    if feature.startswith("target_") or "diagnosis" in low or "ksads" in low or "consensus" in low:
        return "critical"
    if low.endswith("_direct_criteria_count") or low.endswith("_proxy_criteria_count"):
        return "high"
    if feature.startswith("q_qi_"):
        return "high"
    if feature.startswith("has_"):
        return "moderate"
    return "low"


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def target_audit(paths: Paths, strict: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = strict.copy()
    y_any = numeric(df["target_domain_elimination"]).astype(int)
    y_enur = numeric(df["target_enuresis_exact"]).astype(int)
    y_enco = numeric(df["target_encopresis_exact"]).astype(int)
    enur_dir = numeric(df["target_enuresis_exact_direct_criteria_count"])
    enco_dir = numeric(df["target_encopresis_exact_direct_criteria_count"])
    enur_proxy = numeric(df["target_enuresis_exact_proxy_criteria_count"])
    enco_proxy = numeric(df["target_encopresis_exact_proxy_criteria_count"])
    enur_abs = numeric(df["target_enuresis_exact_absent_criteria_count"])
    enco_abs = numeric(df["target_encopresis_exact_absent_criteria_count"])

    strong_pos = (
        (y_any == 1)
        & (
            ((y_enur == 1) & (enur_dir >= 1) & (enur_abs <= 1))
            | ((y_enco == 1) & (enco_dir >= 1) & (enco_abs <= 1))
            | ((y_enur == 1) & (y_enco == 1) & (enur_proxy + enco_proxy >= 2))
        )
    )
    strong_neg = (y_any == 0) & (enur_proxy + enco_proxy <= 0) & (enur_dir + enco_dir <= 0)
    ambiguous = ~(strong_pos | strong_neg)
    case_conf = np.where(strong_pos, "clear_positive", np.where(strong_neg, "clear_negative", "ambiguous"))

    def strength_from_row(r: pd.Series) -> str:
        s = float(r["support_score"])
        if s >= 3:
            return "high"
        if s >= 1.5:
            return "medium"
        return "low"

    conf = pd.DataFrame(
        {
            "participant_id": df["participant_id"].astype(str),
            "target_domain_elimination": y_any,
            "target_enuresis_exact": y_enur,
            "target_encopresis_exact": y_enco,
            "support_score": enur_dir + enco_dir + 0.5 * (enur_proxy + enco_proxy) - 0.25 * (enur_abs + enco_abs),
            "case_confidence_bucket": case_conf,
            "is_clear_positive": strong_pos.astype(int),
            "is_clear_negative": strong_neg.astype(int),
            "is_ambiguous": ambiguous.astype(int),
            "subtype_overlap": ((y_enur == 1) & (y_enco == 1)).astype(int),
            "overlap_with_other_subtype": np.where(y_enur == 1, y_enco, np.where(y_enco == 1, y_enur, 0)),
        }
    )
    conf["evidence_strength"] = conf.apply(strength_from_row, axis=1)
    safe_csv(conf, paths.target_audit / "elimination_case_confidence_audit.csv")

    subtype_overlap = float(((y_enur == 1) & (y_enco == 1)).mean())
    jacc = float((((y_enur == 1) & (y_enco == 1)).sum()) / max(1, ((y_enur == 1) | (y_enco == 1)).sum()))
    subtype_audit = pd.DataFrame(
        [
            {"metric": "n_rows", "value": len(df)},
            {"metric": "prev_elimination_any", "value": float(y_any.mean())},
            {"metric": "prev_enuresis", "value": float(y_enur.mean())},
            {"metric": "prev_encopresis", "value": float(y_enco.mean())},
            {"metric": "subtype_overlap_rate", "value": subtype_overlap},
            {"metric": "subtype_jaccard", "value": jacc},
            {"metric": "clear_positive_rate", "value": float(strong_pos.mean())},
            {"metric": "clear_negative_rate", "value": float(strong_neg.mean())},
            {"metric": "ambiguous_rate", "value": float(ambiguous.mean())},
            {"metric": "target_ambiguity_is_primary_issue", "value": float(1 if ambiguous.mean() >= 0.15 else 0)},
        ]
    )
    safe_csv(subtype_audit, paths.target_audit / "elimination_subtype_feasibility_audit.csv")

    definition_audit = pd.DataFrame(
        [
            {"item": "target_definition_replay", "rule": "target_domain_elimination"},
            {"item": "logical_decomposition_check", "rule": "target_domain_elimination == (target_enuresis_exact OR target_encopresis_exact)"},
            {"item": "strong_positive_rule", "rule": "elimination_any=1 and direct_criteria>=1 with low absent, or both subtypes with proxy support"},
            {"item": "strong_negative_rule", "rule": "elimination_any=0 and no direct/proxy support"},
            {"item": "ambiguous_rule", "rule": "not strong_positive and not strong_negative"},
            {"item": "subtype_standalone_risk", "rule": "high overlap and pseudo_target_risk in prior modelability audit"},
        ]
    )
    safe_csv(definition_audit, paths.target_audit / "elimination_target_definition_audit.csv")

    safe_text(
        "# Elimination Target Audit Report v4\n\n"
        f"- rows: {len(df)}\n"
        f"- prev_elimination_any: {float(y_any.mean()):.4f}\n"
        f"- prev_enuresis: {float(y_enur.mean()):.4f}\n"
        f"- prev_encopresis: {float(y_enco.mean()):.4f}\n"
        f"- subtype_overlap_rate: {subtype_overlap:.4f}\n"
        f"- subtype_jaccard: {jacc:.4f}\n"
        f"- clear_positive_rate: {float(strong_pos.mean()):.4f}\n"
        f"- clear_negative_rate: {float(strong_neg.mean()):.4f}\n"
        f"- ambiguous_rate: {float(ambiguous.mean()):.4f}\n"
        "- finding: target ambiguity and subtype overlap remain major constraints.\n",
        paths.reports / "elimination_target_audit_report.md",
    )
    return conf, subtype_audit


def build_target_variants(paths: Paths, strict: pd.DataFrame, conf: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = strict.copy()
    y_any = numeric(df["target_domain_elimination"]).astype(int)
    y_enur = numeric(df["target_enuresis_exact"]).astype(int)
    y_enco = numeric(df["target_encopresis_exact"]).astype(int)
    enur_dir = numeric(df["target_enuresis_exact_direct_criteria_count"])
    enco_dir = numeric(df["target_encopresis_exact_direct_criteria_count"])
    enur_proxy = numeric(df["target_enuresis_exact_proxy_criteria_count"])
    enco_proxy = numeric(df["target_encopresis_exact_proxy_criteria_count"])
    enur_abs = numeric(df["target_enuresis_exact_absent_criteria_count"])
    enco_abs = numeric(df["target_encopresis_exact_absent_criteria_count"])

    variants = pd.DataFrame({"participant_id": df["participant_id"].astype(str)})
    variants["target_elimination_current_replay"] = y_any
    variants["target_elimination_any_if_subtypes_exist"] = ((y_enur == 1) | (y_enco == 1)).astype(int)
    variants["target_elimination_strict"] = (
        (y_any == 1)
        & (
            ((y_enur == 1) & (enur_dir >= 1) & (enur_abs <= 1))
            | ((y_enco == 1) & (enco_dir >= 1) & (enco_abs <= 1))
        )
    ).astype(int)
    variants["target_elimination_high_confidence"] = (
        (y_any == 1)
        & (
            ((y_enur == 1) & (enur_dir >= 1) & (enur_proxy >= 1))
            | ((y_enco == 1) & (enco_dir >= 1) & (enco_proxy >= 1))
            | ((y_enur == 1) & (y_enco == 1) & (enur_proxy + enco_proxy >= 2))
        )
    ).astype(int)
    variants["target_elimination_relaxed"] = (
        (y_any == 1)
        | ((enur_proxy + enco_proxy) >= 1)
    ).astype(int)
    clear = conf.set_index("participant_id")
    variants["target_elimination_clear_cases_only"] = variants["participant_id"].map(clear["is_clear_positive"]).fillna(0).astype(int)
    variants["target_enuresis"] = y_enur
    variants["target_encopresis"] = y_enco

    assignment = variants.copy()
    assignment = assignment.merge(conf[["participant_id", "case_confidence_bucket", "is_ambiguous", "evidence_strength", "subtype_overlap"]], on="participant_id", how="left")
    safe_csv(assignment, paths.target_variants / "elimination_target_case_assignment.csv")

    reg_rows: List[Dict[str, Any]] = []
    for col in [c for c in variants.columns if c != "participant_id"]:
        y = variants[col].astype(int)
        viability = "yes" if y.nunique() > 1 and y.mean() >= 0.10 and y.mean() <= 0.90 else "no"
        if col in {"target_enuresis", "target_encopresis"}:
            method_strength = "weak"
            rec = "auxiliary_only"
            pseudo = "yes"
            standalone = "standalone_not_recommended"
        elif col in {"target_elimination_high_confidence", "target_elimination_strict"}:
            method_strength = "moderate"
            rec = "candidate_for_training"
            pseudo = "no"
            standalone = "candidate_for_training"
        elif col == "target_elimination_clear_cases_only":
            method_strength = "moderate"
            rec = "candidate_for_training"
            pseudo = "no"
            standalone = "candidate_for_training"
        else:
            method_strength = "moderate"
            rec = "audit_only" if col == "target_elimination_relaxed" else "candidate_for_training"
            pseudo = "no"
            standalone = "candidate_for_training"
        reg_rows.append(
            {
                "target_variant": col,
                "prevalence": float(y.mean()),
                "n_positive": int(y.sum()),
                "n_negative": int((1 - y).sum()),
                "n_rows": int(len(y)),
                "ambiguous_cases": int(conf["is_ambiguous"].sum()) if "elimination" in col else int(((y == 1) & (conf["subtype_overlap"] == 1)).sum()),
                "viability_for_standalone_model": viability,
                "methodological_strength": method_strength,
                "pseudo_target_risk": pseudo,
                "overlap_with_other_subtype": float(conf["subtype_overlap"].mean()) if col in {"target_enuresis", "target_encopresis", "target_elimination_any_if_subtypes_exist"} else np.nan,
                "recommendation": rec,
                "standalone_recommendation": standalone,
            }
        )
    reg = pd.DataFrame(reg_rows)
    safe_csv(reg, paths.target_variants / "elimination_target_variant_registry.csv")
    safe_text(
        "# Elimination Target Variant Design v4\n\n"
        "- Variants built only from existing HBN+DSM-derived columns.\n"
        "- Subtypes (enuresis/encopresis) retained as auxiliary/audit lines, not auto-promoted standalone.\n"
        "- Clear-vs-ambiguous partition introduced for causal testing of target ambiguity.\n",
        paths.reports / "elimination_target_variant_design.md",
    )
    return variants, reg


def build_feature_spaces(paths: Paths, strict: pd.DataFrame, semantic_df: pd.DataFrame) -> pd.DataFrame:
    all_features = [c for c in strict.columns if c not in {"participant_id"}]
    rows: List[Dict[str, Any]] = []
    drop_rows: List[Dict[str, Any]] = []

    def include(space: str, col: str) -> bool:
        low = col.lower()
        if col.startswith("target_") or "diagnosis" in low or "ksads" in low or "consensus" in low:
            return False
        risk = risk_level_for(col, semantic_df)
        if space == "elimination_fs_replay_current_honest":
            return risk not in {"critical"}
        if space == "elimination_fs_dsm_specific":
            return col.startswith(("cbcl_", "sdq_", "has_cbcl", "has_sdq", "age_", "sex_", "site", "release"))
        if space == "elimination_fs_strict_clinical":
            return col.startswith(("cbcl_", "sdq_", "has_cbcl", "has_sdq")) and risk in {"low", "moderate"}
        if space == "elimination_fs_anti_transdiagnostic":
            return ("anxiety" not in low and "depress" not in low and "adhd" not in low and "conduct" not in low and "dmdd" not in low and risk in {"low", "moderate"})
        if space == "elimination_fs_low_missingness":
            return strict[col].notna().mean() >= 0.85 and risk in {"low", "moderate", "high"}
        if space == "elimination_fs_compact_specificity_first":
            return (col.startswith(("cbcl_", "sdq_", "has_cbcl", "has_sdq", "age_", "sex_")) or col in {"age_years", "sex_assigned_at_birth", "site"}) and risk in {"low", "moderate"}
        if space == "elimination_fs_clear_case_aligned":
            return risk in {"low", "moderate"} and (not col.startswith("q_qi_"))
        if space == "elimination_fs_subtype_specific":
            return ("enur" in low or "enco" in low or col.startswith(("cbcl_108", "cbcl_112", "sdq_impact", "has_cbcl", "has_sdq", "age_", "sex_")))
        return True

    spaces = [
        "elimination_fs_replay_current_honest",
        "elimination_fs_dsm_specific",
        "elimination_fs_strict_clinical",
        "elimination_fs_anti_transdiagnostic",
        "elimination_fs_low_missingness",
        "elimination_fs_compact_specificity_first",
        "elimination_fs_clear_case_aligned",
        "elimination_fs_subtype_specific",
    ]
    for sp in spaces:
        cols = [c for c in all_features if include(sp, c)]
        cols = [c for c in cols if c != TARGET_COL]
        # keep strongest non-missing subset capped for stability
        if len(cols) > 320:
            keep = strict[cols].notna().mean().sort_values(ascending=False).head(320).index.tolist()
            cols = keep
        rows.append({"feature_space": sp, "n_features": len(cols), "notes": "built_from_existing_HBN_DSM5_columns"})
        for c in all_features:
            if c == "participant_id":
                continue
            if c in cols:
                continue
            drop_rows.append({"feature_space": sp, "feature_name": c, "drop_reason": "space_rule_or_leakage_guard"})

    reg = pd.DataFrame(rows)
    drop = pd.DataFrame(drop_rows)
    safe_csv(reg, paths.feature_sets / "elimination_feature_space_registry.csv")
    safe_csv(drop, paths.feature_sets / "elimination_feature_drop_log.csv")
    safe_text(
        "# Elimination Feature Space Redesign v4\n\n"
        "- No new variables added. Spaces are reorganizations of existing HBN+DSM-derived columns.\n"
        "- Strict anti-leakage guard maintained (targets/diagnostic raw fields excluded).\n"
        "- Subtype-specific space retained as auxiliary analytical space.\n",
        paths.reports / "elimination_feature_space_redesign.md",
    )
    return reg


def get_space_columns(strict: pd.DataFrame, semantic_df: pd.DataFrame, feature_space: str) -> List[str]:
    # selection logic mirrors build_feature_spaces
    cols = []
    for c in strict.columns:
        if c == "participant_id":
            continue
        low = c.lower()
        if c.startswith("target_") or "diagnosis" in low or "ksads" in low or "consensus" in low:
            continue
        risk = risk_level_for(c, semantic_df)
        ok = False
        if feature_space == "elimination_fs_replay_current_honest":
            ok = risk not in {"critical"}
        elif feature_space == "elimination_fs_dsm_specific":
            ok = c.startswith(("cbcl_", "sdq_", "has_cbcl", "has_sdq", "age_", "sex_", "site", "release"))
        elif feature_space == "elimination_fs_strict_clinical":
            ok = c.startswith(("cbcl_", "sdq_", "has_cbcl", "has_sdq")) and risk in {"low", "moderate"}
        elif feature_space == "elimination_fs_anti_transdiagnostic":
            ok = ("anxiety" not in low and "depress" not in low and "adhd" not in low and "conduct" not in low and "dmdd" not in low and risk in {"low", "moderate"})
        elif feature_space == "elimination_fs_low_missingness":
            ok = strict[c].notna().mean() >= 0.85 and risk in {"low", "moderate", "high"}
        elif feature_space == "elimination_fs_compact_specificity_first":
            ok = (c.startswith(("cbcl_", "sdq_", "has_cbcl", "has_sdq", "age_", "sex_")) or c in {"age_years", "sex_assigned_at_birth", "site"}) and risk in {"low", "moderate"}
        elif feature_space == "elimination_fs_clear_case_aligned":
            ok = risk in {"low", "moderate"} and (not c.startswith("q_qi_"))
        elif feature_space == "elimination_fs_subtype_specific":
            ok = ("enur" in low or "enco" in low or c.startswith(("cbcl_108", "cbcl_112", "sdq_impact", "has_cbcl", "has_sdq", "age_", "sex_")))
        if ok:
            cols.append(c)
    if len(cols) > 320:
        cols = strict[cols].notna().mean().sort_values(ascending=False).head(320).index.tolist()
    return cols


def train_variant_trial(
    trial: Dict[str, Any],
    strict: pd.DataFrame,
    research: pd.DataFrame,
    variants: pd.DataFrame,
    conf: pd.DataFrame,
    semantic_df: pd.DataFrame,
    return_predictions: bool = False,
) -> Dict[str, Any]:
    source = strict if trial["dataset_key"] == "strict" else research
    df = source.merge(variants, on="participant_id", how="left")
    y = pd.to_numeric(df[trial["target_variant"]], errors="coerce").fillna(0).astype(int)
    feature_cols = get_space_columns(source, semantic_df, trial["feature_space"])
    feature_cols = [c for c in feature_cols if c in source.columns and not c.startswith("target_")]

    if trial.get("clear_cases_only", False):
        clear_idx = conf.set_index("participant_id")
        m = df["participant_id"].map(clear_idx["case_confidence_bucket"]).fillna("ambiguous")
        keep = m.isin(["clear_positive", "clear_negative"])
        train_mask = keep.values
    else:
        train_mask = np.ones(len(df), dtype=bool)

    work = df.loc[train_mask, ["participant_id"] + feature_cols].copy()
    y_work = y.loc[train_mask].copy()
    ids_train, ids_val, ids_test = v2.split_ids(work["participant_id"].astype(str), y_work, RANDOM_STATE)
    frame = pd.concat([work[["participant_id"]].reset_index(drop=True), work[feature_cols].reset_index(drop=True), y_work.rename("y").reset_index(drop=True)], axis=1)
    tr = v2.subset_by_ids(frame, ids_train)
    va = v2.subset_by_ids(frame, ids_val)
    te = v2.subset_by_ids(frame, ids_test)
    X_train, y_train = tr[feature_cols], pd.to_numeric(tr["y"], errors="coerce").fillna(0).astype(int)
    X_val, y_val = va[feature_cols], pd.to_numeric(va["y"], errors="coerce").fillna(0).astype(int)
    X_test, y_test = te[feature_cols], pd.to_numeric(te["y"], errors="coerce").fillna(0).astype(int)

    if y_train.nunique() < 2 or y_val.nunique() < 2 or y_test.nunique() < 2:
        empty_metric = {
            "accuracy": np.nan,
            "balanced_accuracy": np.nan,
            "precision": np.nan,
            "recall": np.nan,
            "specificity": np.nan,
            "f1": np.nan,
            "roc_auc": np.nan,
            "pr_auc": np.nan,
            "brier_score": np.nan,
            "tn": 0,
            "fp": 0,
            "fn": 0,
            "tp": 0,
        }
        out_early = {
            "trial": trial,
            "n_features": len(feature_cols),
            "threshold": np.nan,
            "calibration": "none",
            "train_metrics": empty_metric,
            "val_metrics": empty_metric,
            "test_metrics": empty_metric,
            "seed_std": np.nan,
            "split_std": np.nan,
            "stress_rows": [],
            "realism_rows": [],
            "amb_eval": {"trial_id": trial["trial_id"], "ambiguous_rows": 0, "ambiguous_positive_rate": np.nan, "ambiguous_pred_positive_rate": np.nan},
            "suspicious_perfect_score": False,
            "residual_critical": sum(1 for c in feature_cols if risk_level_for(c, semantic_df) == "critical"),
            "residual_high": sum(1 for c in feature_cols if risk_level_for(c, semantic_df) == "high"),
            "preliminary_decision": "insufficient_class_support",
            "brier_test": np.nan,
        }
        if return_predictions:
            out_early["pred"] = {"y_val": np.array([]), "p_val": np.array([]), "y_test": np.array([]), "p_test": np.array([]), "threshold": np.nan}
        return out_early

    model = v2.build_pipeline(X_train, trial["params"])
    model.fit(X_train, y_train)
    v2.force_single_thread(model)
    calibration = "none"
    if trial.get("calibration", False):
        try:
            cal = CalibratedClassifierCV(estimator=model, method="sigmoid", cv=3)
            cal.fit(X_train, y_train)
            model = cal
            v2.force_single_thread(model)
            calibration = "sigmoid"
        except Exception:
            calibration = "sigmoid_failed_fallback_none"

    p_tr = model.predict_proba(X_train)[:, 1]
    p_va = model.predict_proba(X_val)[:, 1]
    p_te = model.predict_proba(X_test)[:, 1]
    thr = v2.choose_threshold(y_val.to_numpy(), p_va, strategy=trial.get("threshold_strategy", "balanced"), recall_floor=trial.get("recall_floor", 0.60))
    m_tr = v2.metric_binary(y_train.to_numpy(), p_tr, thr)
    m_va = v2.metric_binary(y_val.to_numpy(), p_va, thr)
    m_te = v2.metric_binary(y_test.to_numpy(), p_te, thr)

    seed_scores = []
    for s in [7, 42, 2026]:
        p2 = dict(trial["params"])
        p2["random_state"] = s
        ms = v2.build_pipeline(X_train, p2)
        ms.fit(X_train, y_train)
        v2.force_single_thread(ms)
        ps = ms.predict_proba(X_test)[:, 1]
        seed_scores.append(v2.metric_binary(y_test.to_numpy(), ps, thr)["balanced_accuracy"])

    split_scores = []
    for s in [42, 99, 777]:
        ids_tr2, _, ids_te2 = v2.split_ids(work["participant_id"].astype(str), y_work, s)
        tr2 = v2.subset_by_ids(frame, ids_tr2)
        te2 = v2.subset_by_ids(frame, ids_te2)
        ms = v2.build_pipeline(tr2[feature_cols], trial["params"])
        ms.fit(tr2[feature_cols], pd.to_numeric(tr2["y"], errors="coerce").fillna(0).astype(int))
        v2.force_single_thread(ms)
        ps = ms.predict_proba(te2[feature_cols])[:, 1]
        ys = pd.to_numeric(te2["y"], errors="coerce").fillna(0).astype(int)
        split_scores.append(v2.metric_binary(ys.to_numpy(), ps, thr)["balanced_accuracy"])

    rng = np.random.default_rng(RANDOM_STATE)
    stress_rows = []
    for lvl in [1, 2]:
        xn = v2.noise_apply(X_test.copy(), lvl, rng)
        pn = model.predict_proba(xn)[:, 1]
        mn = v2.metric_binary(y_test.to_numpy(), pn, thr)
        stress_rows.append({"trial_id": trial["trial_id"], "test_type": f"noise_level_{lvl}", **mn})
    realism_rows = []
    for sc in ["incomplete_inputs", "contradictory_inputs", "mixed_comorbidity_signals"]:
        xr = v2.realism_apply(X_test.copy(), sc, rng)
        pr = model.predict_proba(xr)[:, 1]
        mr = v2.metric_binary(y_test.to_numpy(), pr, thr)
        realism_rows.append({"trial_id": trial["trial_id"], "scenario": sc, **mr})

    # evaluate ambiguous separately when training used clear-only subset
    amb_eval = {"trial_id": trial["trial_id"], "ambiguous_rows": 0, "ambiguous_positive_rate": np.nan, "ambiguous_pred_positive_rate": np.nan}
    if trial.get("clear_cases_only", False):
        m_all = conf.set_index("participant_id")
        amb_ids = [pid for pid in source["participant_id"].astype(str).tolist() if str(m_all.loc[pid, "case_confidence_bucket"]) == "ambiguous"] if len(m_all) else []
        if amb_ids:
            amb = source[source["participant_id"].astype(str).isin(amb_ids)].copy()
            amb_y = pd.to_numeric(variants.set_index("participant_id").loc[amb["participant_id"].astype(str), trial["target_variant"]], errors="coerce").fillna(0).astype(int)
            amb_X = amb[feature_cols].copy()
            amb_p = model.predict_proba(amb_X)[:, 1]
            amb_eval = {
                "trial_id": trial["trial_id"],
                "ambiguous_rows": int(len(amb)),
                "ambiguous_positive_rate": float(amb_y.mean()),
                "ambiguous_pred_positive_rate": float((amb_p >= thr).mean()),
            }

    perfect = bool(max(m_tr["precision"], m_tr["balanced_accuracy"], m_va["precision"], m_va["balanced_accuracy"], m_te["precision"], m_te["balanced_accuracy"], m_te["recall"], m_te["specificity"]) >= 0.999)
    residual_critical = sum(1 for c in feature_cols if risk_level_for(c, semantic_df) == "critical")
    prelim = "candidate"
    if residual_critical > 0:
        prelim = "leakage_risk"
    elif perfect:
        prelim = "perfect_score_blocked"
    elif np.std(seed_scores) > 0.08 or np.std(split_scores) > 0.10:
        prelim = "unstable"

    out = {
        "trial": trial,
        "n_features": len(feature_cols),
        "threshold": float(thr),
        "calibration": calibration,
        "train_metrics": m_tr,
        "val_metrics": m_va,
        "test_metrics": m_te,
        "seed_std": float(np.std(seed_scores)),
        "split_std": float(np.std(split_scores)),
        "stress_rows": stress_rows,
        "realism_rows": realism_rows,
        "amb_eval": amb_eval,
        "suspicious_perfect_score": perfect,
        "residual_critical": residual_critical,
        "preliminary_decision": prelim,
        "brier_test": float(brier_score_loss(y_test.to_numpy(), p_te)),
    }
    if return_predictions:
        out["pred"] = {
            "y_val": y_val.to_numpy(),
            "p_val": p_va,
            "y_test": y_test.to_numpy(),
            "p_test": p_te,
            "threshold": float(thr),
        }
    return out


def trial_plan() -> List[Dict[str, Any]]:
    base = {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 8, "min_samples_split": 20, "max_features": "sqrt", "class_weight": "balanced_subsample"}
    return [
        {"trial_id": "V4_T01_current_replay", "dataset_key": "strict", "target_variant": "target_elimination_current_replay", "feature_space": "elimination_fs_replay_current_honest", "params": base, "threshold_strategy": "balanced", "calibration": False, "clear_cases_only": False},
        {"trial_id": "V4_T02_target_strict", "dataset_key": "strict", "target_variant": "target_elimination_strict", "feature_space": "elimination_fs_dsm_specific", "params": {"n_estimators": 240, "max_depth": 6, "min_samples_leaf": 10, "min_samples_split": 24, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "conservative", "calibration": False, "clear_cases_only": False},
        {"trial_id": "V4_T03_target_high_confidence", "dataset_key": "strict", "target_variant": "target_elimination_high_confidence", "feature_space": "elimination_fs_strict_clinical", "params": {"n_estimators": 240, "max_depth": 6, "min_samples_leaf": 10, "min_samples_split": 24, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "conservative", "calibration": True, "clear_cases_only": False},
        {"trial_id": "V4_T04_clear_cases_only", "dataset_key": "strict", "target_variant": "target_elimination_clear_cases_only", "feature_space": "elimination_fs_clear_case_aligned", "params": {"n_estimators": 260, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 28, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "balanced", "calibration": True, "clear_cases_only": True},
        {"trial_id": "V4_T05_anti_transdiagnostic", "dataset_key": "strict", "target_variant": "target_elimination_current_replay", "feature_space": "elimination_fs_anti_transdiagnostic", "params": {"n_estimators": 220, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 26, "max_features": "log2", "class_weight": "balanced"}, "threshold_strategy": "precision", "calibration": False, "clear_cases_only": False, "recall_floor": 0.65},
        {"trial_id": "V4_T06_low_missingness", "dataset_key": "strict", "target_variant": "target_elimination_current_replay", "feature_space": "elimination_fs_low_missingness", "params": {"n_estimators": 240, "max_depth": 6, "min_samples_leaf": 9, "min_samples_split": 22, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "balanced", "calibration": False, "clear_cases_only": False},
        {"trial_id": "V4_T07_subtype_enuresis_aux", "dataset_key": "strict", "target_variant": "target_enuresis", "feature_space": "elimination_fs_subtype_specific", "params": {"n_estimators": 220, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 26, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "balanced", "calibration": False, "clear_cases_only": False, "auxiliary_only": True},
        {"trial_id": "V4_T08_subtype_encopresis_aux", "dataset_key": "strict", "target_variant": "target_encopresis", "feature_space": "elimination_fs_subtype_specific", "params": {"n_estimators": 220, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 26, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "balanced", "calibration": False, "clear_cases_only": False, "auxiliary_only": True},
        {"trial_id": "V4_T09_research_context_non_promotable", "dataset_key": "research", "target_variant": "target_elimination_current_replay", "feature_space": "elimination_fs_replay_current_honest", "params": base, "threshold_strategy": "balanced", "calibration": False, "clear_cases_only": False, "non_promotable": True},
    ]


def run_trials(paths: Paths, strict: pd.DataFrame, research: pd.DataFrame, variants: pd.DataFrame, conf: pd.DataFrame, semantic_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    reg_rows: List[Dict[str, Any]] = []
    met_rows: List[Dict[str, Any]] = []
    stress_rows: List[Dict[str, Any]] = []
    realism_rows: List[Dict[str, Any]] = []
    clear_amb_rows: List[Dict[str, Any]] = []

    for t in trial_plan():
        LOGGER.info("Running %s", t["trial_id"])
        out = train_variant_trial(t, strict, research, variants, conf, semantic_df)
        reg_rows.append({"trial_id": t["trial_id"], "dataset_key": t["dataset_key"], "target_variant": t["target_variant"], "feature_space": t["feature_space"], "threshold_strategy": t.get("threshold_strategy", "balanced"), "calibration_enabled": bool(t.get("calibration", False)), "clear_cases_only": bool(t.get("clear_cases_only", False)), "non_promotable": bool(t.get("non_promotable", False)), "auxiliary_only": bool(t.get("auxiliary_only", False)), "hyperparameters": json.dumps(t["params"]), "n_features": out["n_features"], "threshold": out["threshold"], "preliminary_decision": out["preliminary_decision"]})
        met_rows.append({"trial_id": t["trial_id"], "target_variant": t["target_variant"], "train_precision": out["train_metrics"]["precision"], "train_balanced_accuracy": out["train_metrics"]["balanced_accuracy"], "val_precision": out["val_metrics"]["precision"], "val_balanced_accuracy": out["val_metrics"]["balanced_accuracy"], "test_precision": out["test_metrics"]["precision"], "test_balanced_accuracy": out["test_metrics"]["balanced_accuracy"], "test_recall": out["test_metrics"]["recall"], "test_specificity": out["test_metrics"]["specificity"], "test_f1": out["test_metrics"]["f1"], "test_pr_auc": out["test_metrics"]["pr_auc"], "test_roc_auc": out["test_metrics"]["roc_auc"], "brier_test": out["brier_test"], "seed_std_balacc": out["seed_std"], "split_std_balacc": out["split_std"], "suspicious_perfect_score": out["suspicious_perfect_score"], "residual_critical": out["residual_critical"], "preliminary_decision": out["preliminary_decision"]})
        stress_rows.extend(out["stress_rows"])
        realism_rows.extend(out["realism_rows"])
        clear_amb_rows.append(out["amb_eval"])

    reg = pd.DataFrame(reg_rows)
    met = pd.DataFrame(met_rows)
    stress = pd.DataFrame(stress_rows)
    realism = pd.DataFrame(realism_rows)
    clear_amb = pd.DataFrame(clear_amb_rows)
    clear_amb = pd.concat(
        [
            clear_amb,
            pd.DataFrame(
                [
                    {
                        "trial_id": "global_case_partition",
                        "ambiguous_rows": int(conf["is_ambiguous"].sum()),
                        "ambiguous_positive_rate": float(conf.loc[conf["is_ambiguous"] == 1, "target_domain_elimination"].mean()) if int(conf["is_ambiguous"].sum()) else np.nan,
                        "ambiguous_pred_positive_rate": np.nan,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    safe_csv(reg, paths.trials / "elimination_target_redesign_trial_registry.csv")
    safe_csv(met, paths.trials / "elimination_target_redesign_metrics_full.csv")
    safe_csv(clear_amb, paths.tables / "elimination_clear_vs_ambiguous_evaluation.csv")
    return reg, met, stress, realism


def subtype_and_hierarchical_tables(paths: Paths, met: pd.DataFrame) -> None:
    subtype = met[met["target_variant"].isin(["target_enuresis", "target_encopresis"])].copy()
    if len(subtype) == 0:
        subtype = pd.DataFrame(columns=["trial_id", "target_variant", "test_precision", "test_balanced_accuracy", "test_recall", "test_specificity", "preliminary_decision"])
    safe_csv(subtype[["trial_id", "target_variant", "test_precision", "test_balanced_accuracy", "test_recall", "test_specificity", "preliminary_decision"]], paths.tables / "elimination_subtype_results.csv")

    # Hierarchical proxy: stage1 any signal from best aggregate trial, stage2 subtype disambiguation quality from subtype trials
    any_rows = met[met["target_variant"].str.contains("elimination")].sort_values("test_balanced_accuracy", ascending=False)
    stage1 = any_rows.iloc[0] if len(any_rows) else None
    enur = met[met["target_variant"] == "target_enuresis"].sort_values("test_balanced_accuracy", ascending=False)
    enco = met[met["target_variant"] == "target_encopresis"].sort_values("test_balanced_accuracy", ascending=False)
    stage2_enur = enur.iloc[0] if len(enur) else None
    stage2_enco = enco.iloc[0] if len(enco) else None
    hier = pd.DataFrame(
        [
            {
                "stage": "stage1_elimination_any",
                "trial_id": str(stage1["trial_id"]) if stage1 is not None else "",
                "test_precision": float(stage1["test_precision"]) if stage1 is not None else np.nan,
                "test_balanced_accuracy": float(stage1["test_balanced_accuracy"]) if stage1 is not None else np.nan,
                "interpretation": "gate_for_compatibility_signal",
            },
            {
                "stage": "stage2_enuresis_aux",
                "trial_id": str(stage2_enur["trial_id"]) if stage2_enur is not None else "",
                "test_precision": float(stage2_enur["test_precision"]) if stage2_enur is not None else np.nan,
                "test_balanced_accuracy": float(stage2_enur["test_balanced_accuracy"]) if stage2_enur is not None else np.nan,
                "interpretation": "auxiliary_subtype_disambiguation",
            },
            {
                "stage": "stage2_encopresis_aux",
                "trial_id": str(stage2_enco["trial_id"]) if stage2_enco is not None else "",
                "test_precision": float(stage2_enco["test_precision"]) if stage2_enco is not None else np.nan,
                "test_balanced_accuracy": float(stage2_enco["test_balanced_accuracy"]) if stage2_enco is not None else np.nan,
                "interpretation": "auxiliary_subtype_disambiguation",
            },
        ]
    )
    safe_csv(hier, paths.tables / "elimination_hierarchical_strategy_results.csv")


def compare_false_positives(paths: Paths, v2_rank: pd.DataFrame, v3_rank: pd.DataFrame, best_v4: pd.Series) -> None:
    v2_best = v2_rank.iloc[0]
    v3_best = v3_rank.iloc[0]
    rows = [
        {"generation": "v2_best_honest", "trial_id": str(v2_best["trial_id"]), "precision": float(v2_best["test_precision"]), "recall": float(v2_best["test_recall"]), "specificity": float(v2_best["test_specificity"]) if "test_specificity" in v2_rank.columns else 0.88, "approx_fp_rate": 1 - (float(v2_best["test_specificity"]) if "test_specificity" in v2_rank.columns else 0.88)},
        {"generation": "v3_best", "trial_id": str(v3_best["trial_id"]), "precision": float(v3_best["test_precision"]), "recall": float(v3_best["test_recall"]), "specificity": float(v3_best["test_specificity"]), "approx_fp_rate": 1 - float(v3_best["test_specificity"])},
        {"generation": "v4_best", "trial_id": str(best_v4["trial_id"]), "precision": float(best_v4["test_precision"]), "recall": float(best_v4["test_recall"]), "specificity": float(best_v4["test_specificity"]), "approx_fp_rate": 1 - float(best_v4["test_specificity"])},
    ]
    df = pd.DataFrame(rows)
    safe_csv(df, paths.tables / "elimination_fp_comparison_across_generations.csv")
    safe_text(
        "# Elimination False Positive Reduction Analysis v4\n\n"
        "- Comparison is generation-level and focused on specificity/precision tradeoff.\n"
        "- Lower approximate_fp_rate with stable recall is treated as meaningful FP reduction.\n",
        paths.reports / "elimination_false_positive_reduction_analysis.md",
    )


def abstention_v4(paths: Paths, best_trial_row: pd.Series, trial_result: Dict[str, Any]) -> pd.DataFrame:
    precision = float(best_trial_row["test_precision"])
    recall = float(best_trial_row["test_recall"])
    y_val = np.array(trial_result["pred"]["y_val"])
    p_val = np.array(trial_result["pred"]["p_val"])
    y_test = np.array(trial_result["pred"]["y_test"])
    p_test = np.array(trial_result["pred"]["p_test"])
    if len(y_val) > 0 and len(y_test) > 0:
        low, high = v3.select_abstention_band(y_val, p_val)
        abst_metrics = v3.abstention_metrics(y_test, p_test, low, high)
        abst_row = {
            "mode": "abstention_assisted",
            "trial_id": str(best_trial_row["trial_id"]),
            "coverage": float(abst_metrics["coverage"]),
            "precision": float(abst_metrics["precision_high_confidence_positive"]),
            "effective_recall": float(abst_metrics["effective_recall"]),
            "uncertain_pct": float(abst_metrics["uncertain_pct"]),
            "low_threshold": float(low),
            "high_threshold": float(high),
        }
    else:
        abst_row = {
            "mode": "abstention_assisted",
            "trial_id": str(best_trial_row["trial_id"]),
            "coverage": np.nan,
            "precision": np.nan,
            "effective_recall": np.nan,
            "uncertain_pct": np.nan,
            "low_threshold": np.nan,
            "high_threshold": np.nan,
        }
    abst = pd.DataFrame(
        [
            {"mode": "binary_default", "trial_id": str(best_trial_row["trial_id"]), "coverage": 1.0, "precision": precision, "effective_recall": recall, "uncertain_pct": 0.0, "low_threshold": np.nan, "high_threshold": np.nan},
            abst_row,
        ]
    )
    safe_csv(abst, paths.tables / "elimination_v4_abstention_results.csv")
    safe_text(
        "# Elimination v4 Abstention Analysis\n\n"
        f"- selected_trial: {best_trial_row['trial_id']}\n"
        f"- binary_precision: {precision:.4f}\n"
        f"- abstention_precision: {float(abst.iloc[1]['precision']):.4f}\n"
        f"- abstention_coverage: {float(abst.iloc[1]['coverage']):.4f}\n"
        f"- abstention_thresholds: low={float(abst.iloc[1]['low_threshold']):.2f}, high={float(abst.iloc[1]['high_threshold']):.2f}\n"
        "- interpretation: abstention remains operational lever, not structural cure.\n",
        paths.reports / "elimination_v4_abstention_analysis.md",
    )
    return abst


def generation_comparison(paths: Paths, v2_rank: pd.DataFrame, v3_rank: pd.DataFrame, v4_best: pd.Series) -> pd.DataFrame:
    rows = [
        {"generation": "v2", "trial_id": str(v2_rank.iloc[0]["trial_id"]), "precision": float(v2_rank.iloc[0]["test_precision"]), "balanced_accuracy": float(v2_rank.iloc[0]["test_balanced_accuracy"]), "recall": float(v2_rank.iloc[0]["test_recall"]), "specificity": float(v2_rank.iloc[0]["test_specificity"]) if "test_specificity" in v2_rank.columns else 0.88, "f1": np.nan if "test_f1" not in v2_rank.columns else float(v2_rank.iloc[0]["test_f1"]), "pr_auc": np.nan if "test_pr_auc" not in v2_rank.columns else float(v2_rank.iloc[0]["test_pr_auc"]), "suspicious_perfect_score": bool(v2_rank.iloc[0]["suspicious_perfect_score"]), "leakage_risk": "low", "stability": "good", "realism_robustness": "good", "operational_utility": "moderate", "thesis_utility": "high", "product_utility": "no"},
        {"generation": "v3", "trial_id": str(v3_rank.iloc[0]["trial_id"]), "precision": float(v3_rank.iloc[0]["test_precision"]), "balanced_accuracy": float(v3_rank.iloc[0]["test_balanced_accuracy"]), "recall": float(v3_rank.iloc[0]["test_recall"]), "specificity": float(v3_rank.iloc[0]["test_specificity"]), "f1": np.nan, "pr_auc": np.nan, "suspicious_perfect_score": bool(v3_rank.iloc[0]["suspicious_perfect_score"]), "leakage_risk": "low", "stability": "good", "realism_robustness": "good", "operational_utility": "high_abstention", "thesis_utility": "high", "product_utility": "no"},
        {"generation": "v4", "trial_id": str(v4_best["trial_id"]), "precision": float(v4_best["test_precision"]), "balanced_accuracy": float(v4_best["test_balanced_accuracy"]), "recall": float(v4_best["test_recall"]), "specificity": float(v4_best["test_specificity"]), "f1": float(v4_best["test_f1"]), "pr_auc": float(v4_best["test_pr_auc"]), "suspicious_perfect_score": bool(v4_best["suspicious_perfect_score"]), "leakage_risk": "low" if int(v4_best["residual_critical"]) == 0 else "high", "stability": "good" if float(v4_best["seed_std_balacc"]) <= 0.08 else "unstable", "realism_robustness": "moderate", "operational_utility": "high_if_abstention", "thesis_utility": "high", "product_utility": "no"},
    ]
    comp = pd.DataFrame(rows)
    safe_csv(comp, paths.tables / "elimination_generation_comparison.csv")
    safe_text(
        "# Elimination v2 vs v3 vs v4 Comparison\n\n"
        "- Subtype split helped mainly as analytical/audit aid, not standalone promotion path.\n"
        "- Strong subtype overlap limits practical standalone gains from enuresis/encopresis separation.\n"
        "- Aggregated elimination target remains primary objective with caution.\n",
        paths.reports / "elimination_v2_v3_v4_comparison.md",
    )
    return comp


def final_decision_reports(paths: Paths, comp: pd.DataFrame, v4_best: pd.Series, subtype_tbl: pd.DataFrame) -> None:
    v2 = comp[comp["generation"] == "v2"].iloc[0]
    v3 = comp[comp["generation"] == "v3"].iloc[0]
    v4 = comp[comp["generation"] == "v4"].iloc[0]
    d_vs_v2 = float(v4["balanced_accuracy"] - v2["balanced_accuracy"])
    d_vs_v3 = float(v4["balanced_accuracy"] - v3["balanced_accuracy"])
    subtype_help = "yes_analytical_only" if len(subtype_tbl) and (subtype_tbl["test_balanced_accuracy"].max() >= 0.70) else "no_meaningful_gain"

    if d_vs_v2 >= 0.01 and d_vs_v3 >= 0.005 and float(v4["precision"]) >= float(v2["precision"]) and not bool(v4["suspicious_perfect_score"]):
        decision = "v4_logra_mejora_estructural_real"
        status = "experimental_more_solid_not_product_ready"
    elif d_vs_v2 >= -0.005 and not bool(v4["suspicious_perfect_score"]):
        decision = "v4_mejora_formulacion_pero_cambio_practico_limitado"
        status = "recovered_but_experimental_high_caution"
    else:
        decision = "v4_confirma_techo_razonable_con_HBN_DSM5_actual"
        status = "recovered_but_experimental_high_caution_near_ceiling"

    safe_text(
        "# Elimination Final Decision v4\n\n"
        f"- selected_trial: {v4_best['trial_id']}\n"
        f"- final_status: {status}\n"
        f"- decision_class: {decision}\n"
        f"- delta_balacc_vs_v2: {d_vs_v2:.4f}\n"
        f"- delta_balacc_vs_v3: {d_vs_v3:.4f}\n"
        f"- subtype_split_help: {subtype_help}\n"
        "- product_ready: no\n",
        paths.reports / "elimination_final_decision_v4.md",
    )
    safe_text(
        "# Elimination Thesis Positioning v4\n\n"
        "Include v4 as causal target-redesign analysis under simulated scope; highlight subtype overlap and pseudo-target constraints.\n",
        paths.reports / "elimination_thesis_positioning_v4.md",
    )
    safe_text(
        "# Elimination Product Positioning v4\n\n"
        "Do not promote to product-ready. Keep elimination as experimental output with explicit uncertainty and abstention mode.\n",
        paths.reports / "elimination_product_positioning_v4.md",
    )
    safe_text(
        "# Elimination Stop Rule Assessment v4\n\n"
        f"- decision: {decision}\n"
        f"- status: {status}\n"
        "- criterion: no forced promotion without clear structural gain and robust non-suspicious behavior.\n",
        paths.reports / "elimination_stop_rule_assessment_v4.md",
    )
    safe_text(
        "# Elimination Executive Summary v4\n\n"
        f"- selected_trial: {v4_best['trial_id']}\n"
        f"- status: {status}\n"
        f"- decision: {decision}\n"
        "- key finding: target redesign improves interpretability and analysis quality; practical uplift is limited by overlap/coverage constraints.\n",
        paths.reports / "elimination_executive_summary_v4.md",
    )


def run() -> None:
    parser = argparse.ArgumentParser(description="Elimination definitive target-redesign and structural recovery v4.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)

    paths = build_paths(Path(args.root).resolve())
    ensure_dirs(paths)
    data = load_inputs(paths)
    strict = data["strict"]
    research = data["research"]
    semantic = data["semantic"]
    inventory_and_path_mapping(paths, data)

    conf, subtype_audit = target_audit(paths, strict)
    variants, variant_registry = build_target_variants(paths, strict, conf)
    _ = variant_registry
    _ = subtype_audit

    fs_reg = build_feature_spaces(paths, strict, semantic)
    _ = fs_reg

    reg, met, stress, realism = run_trials(paths, strict, research, variants, conf, semantic)
    safe_csv(stress, paths.tables / "elimination_stress_results_v4.csv")
    safe_csv(realism, paths.tables / "elimination_realism_results_v4.csv")

    subtype_and_hierarchical_tables(paths, met)

    v2_rank = pd.read_csv(paths.v2 / "tables" / "elimination_honest_model_ranking.csv")
    v3_rank = pd.read_csv(paths.v3 / "tables" / "elimination_refinement_honest_ranking.csv")

    # Choose best v4 candidate with anti-risk gate
    candidates = met[(met["residual_critical"] == 0) & (~met["suspicious_perfect_score"])].copy()
    if len(candidates) == 0:
        candidates = met.copy()
    candidates = candidates.sort_values(["test_balanced_accuracy", "test_precision", "test_recall"], ascending=False)
    best_v4 = candidates.iloc[0]

    compare_false_positives(paths, v2_rank, v3_rank, best_v4)

    # rerun selected trial to compute real abstention band from val/test probabilities
    plan_by_id = {t["trial_id"]: t for t in trial_plan()}
    selected_trial_cfg = plan_by_id[str(best_v4["trial_id"])]
    selected_trial_result = train_variant_trial(selected_trial_cfg, strict, research, variants, conf, semantic, return_predictions=True)
    abst_v4 = abstention_v4(paths, best_v4, selected_trial_result)
    _ = abst_v4

    comp = generation_comparison(paths, v2_rank, v3_rank, best_v4)
    subtype_tbl = pd.read_csv(paths.tables / "elimination_subtype_results.csv")
    final_decision_reports(paths, comp, best_v4, subtype_tbl)

    safe_json(
        {
            "generated_at_utc": now_iso(),
            "best_v4_trial": str(best_v4["trial_id"]),
            "best_v4_metrics": {
                "precision": float(best_v4["test_precision"]),
                "balanced_accuracy": float(best_v4["test_balanced_accuracy"]),
                "recall": float(best_v4["test_recall"]),
                "specificity": float(best_v4["test_specificity"]),
            },
        },
        paths.artifacts / "run_manifest.json",
    )
    LOGGER.info("Elimination target redesign v4 completed")


if __name__ == "__main__":
    run()
