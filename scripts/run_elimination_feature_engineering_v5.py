#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import logging
import re
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


LOGGER = logging.getLogger("elimination-feature-engineering-v5")
RANDOM_STATE = 42
TARGET_COL = "target_domain_elimination"


@dataclass
class Paths:
    root: Path
    out: Path
    inventory: Path
    feature_audit: Path
    feature_generation: Path
    feature_sets: Path
    trials: Path
    tables: Path
    reports: Path
    artifacts: Path
    v2: Path
    v3: Path
    v4: Path
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
    out = root / "data" / "elimination_feature_engineering_v5"
    return Paths(
        root=root,
        out=out,
        inventory=out / "inventory",
        feature_audit=out / "feature_audit",
        feature_generation=out / "feature_generation",
        feature_sets=out / "feature_sets",
        trials=out / "trials",
        tables=out / "tables",
        reports=out / "reports",
        artifacts=root / "artifacts" / "elimination_feature_engineering_v5",
        v2=root / "data" / "elimination_iterative_recovery_v2",
        v3=root / "data" / "elimination_refinement_v3",
        v4=root / "data" / "elimination_target_redesign_v4",
        hybrid=root / "data" / "processed_hybrid_dsm5_v2",
        dsm5_exact=root / "data" / "processed_dsm5_exact_v1",
    )


def ensure_dirs(paths: Paths) -> None:
    for p in [
        paths.out,
        paths.inventory,
        paths.feature_audit,
        paths.feature_generation,
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

    semantic_path = paths.v2 / "audit" / "elimination_semantic_proximity_audit.csv"
    semantic = pd.read_csv(semantic_path) if semantic_path.exists() else pd.DataFrame(columns=["feature_name", "risk_level"])
    return {"strict": strict, "research": research, "semantic": semantic}


def create_input_inventory(paths: Paths, data: Dict[str, pd.DataFrame]) -> None:
    required = [
        paths.v2 / "reports" / "elimination_final_decision_v2.md",
        paths.v3 / "reports" / "elimination_final_decision_v3.md",
        paths.v4 / "reports" / "elimination_final_decision_v4.md",
        paths.v2 / "tables" / "elimination_honest_model_ranking.csv",
        paths.v3 / "tables" / "elimination_abstention_policy_results.csv",
        paths.v4 / "tables" / "elimination_generation_comparison.csv",
        paths.v4 / "tables" / "elimination_fp_comparison_across_generations.csv",
        paths.v4 / "tables" / "elimination_subtype_results.csv",
        paths.v4 / "tables" / "elimination_clear_vs_ambiguous_evaluation.csv",
        paths.hybrid / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv",
    ]

    rows: List[Dict[str, Any]] = []
    missing: List[str] = []
    for p in required:
        exists = p.exists()
        rows.append(
            {
                "path": str(p),
                "exists": exists,
                "size_bytes": int(p.stat().st_size) if exists else None,
                "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat() if exists else None,
            }
        )
        if not exists:
            missing.append(str(p))
    for name, df in data.items():
        if isinstance(df, pd.DataFrame):
            rows.append({"path": f"in_memory::{name}", "exists": True, "rows": len(df), "cols": len(df.columns), "modified_utc": now_iso()})

    inv = pd.DataFrame(rows)
    safe_csv(inv, paths.inventory / "input_inventory.csv")
    fallback = pd.DataFrame(
        [{"expected_path": p, "resolved_equivalent": "not_found", "status": "missing"} for p in missing]
        if missing
        else [{"expected_path": "all_required_inputs", "resolved_equivalent": "exact_paths_found", "status": "ok"}]
    )
    safe_csv(fallback, paths.inventory / "path_mapping_fallbacks.csv")

    safe_text(
        "# Elimination Feature Engineering v5 - Input Summary\n\n"
        f"- generated_at_utc: {now_iso()}\n"
        f"- checked_inputs: {len(required)}\n"
        f"- missing_inputs: {len(missing)}\n"
        f"- strict_rows: {len(data['strict'])}\n"
        f"- research_rows: {len(data['research'])}\n"
        f"- strict_cols: {len(data['strict'].columns)}\n"
        f"- research_cols: {len(data['research'].columns)}\n",
        paths.reports / "input_summary.md",
    )


def build_risk_map(semantic_df: pd.DataFrame) -> Dict[str, str]:
    risk_map: Dict[str, str] = {}
    if "feature_name" in semantic_df.columns and "risk_level" in semantic_df.columns:
        for _, row in semantic_df.iterrows():
            risk_map[str(row["feature_name"])] = str(row["risk_level"])
    return risk_map


def risk_level(feature: str, risk_map: Dict[str, str]) -> str:
    if feature in risk_map:
        return str(risk_map[feature])
    low = feature.lower()
    if feature.startswith("target_"):
        return "critical"
    if any(tok in low for tok in ["diagnosis", "ksads", "consensus"]):
        return "critical"
    if low.endswith("_direct_criteria_count") or low.endswith("_proxy_criteria_count"):
        return "high"
    if feature.startswith("q_qi_"):
        return "high"
    if feature.startswith("has_"):
        return "moderate"
    return "low"


def is_blocked_feature(feature: str) -> bool:
    low = feature.lower()
    blocked_exact = {
        "participant_id",
        TARGET_COL,
        "domain_any_positive",
        "internal_exact_any_positive",
        "domain_comorbidity_count",
        "internal_exact_comorbidity_count",
        "has_any_target_disorder",
        "n_diagnoses",
        "comorbidity_count_5targets",
    }
    if feature in blocked_exact:
        return True
    if feature.startswith("target_"):
        return True
    if any(tok in low for tok in ["diagnosis", "ksads", "consensus"]):
        return True
    if low.endswith("_status") or low.endswith("_confidence") or low.endswith("_coverage"):
        return True
    return False


def col_float(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)
    return pd.Series(np.zeros(len(df)), index=df.index, dtype=float)


def run_feature_audit(paths: Paths, strict: pd.DataFrame) -> None:
    _ = strict
    rows = [
        {
            "feature_family": "composite_clinical",
            "candidate_feature_name": "v5_comp_elim_core_sum",
            "source_columns": "cbcl_108,cbcl_112,sdq_impact",
            "source_tables": "HBN_hybrid_existing",
            "transformation_type": "sum",
            "clinical_rationale": "Concentrates compatible elimination core evidence",
            "expected_effect": "improve_signal_quality",
            "methodological_risk": "low",
            "leakage_risk": "low",
            "implementation_priority": 1,
            "promotable_yes_no": "yes",
        },
        {
            "feature_family": "composite_clinical",
            "candidate_feature_name": "v5_comp_elim_source_convergence",
            "source_columns": "has_cbcl,has_sdq",
            "source_tables": "HBN_hybrid_existing",
            "transformation_type": "binary_flag",
            "clinical_rationale": "Captures convergence across available parent sources",
            "expected_effect": "stability_gain",
            "methodological_risk": "low",
            "leakage_risk": "low",
            "implementation_priority": 1,
            "promotable_yes_no": "yes",
        },
        {
            "feature_family": "anti_transdiagnostic",
            "candidate_feature_name": "v5_anti_specificity_ratio",
            "source_columns": "elim_core,internalizing_proxy,externalizing_proxy,sdq_difficulties",
            "source_tables": "HBN_hybrid_existing",
            "transformation_type": "ratio",
            "clinical_rationale": "Relative specificity signal vs diffuse burden",
            "expected_effect": "false_positive_reduction",
            "methodological_risk": "moderate",
            "leakage_risk": "low",
            "implementation_priority": 1,
            "promotable_yes_no": "yes",
        },
        {
            "feature_family": "evidence_quality",
            "candidate_feature_name": "v5_eq_evidence_quality_score",
            "source_columns": "has_* flags plus observed core ratio",
            "source_tables": "HBN_hybrid_existing",
            "transformation_type": "composite_score",
            "clinical_rationale": "Quantifies evidence completeness and quality",
            "expected_effect": "robustness_gain",
            "methodological_risk": "low",
            "leakage_risk": "low",
            "implementation_priority": 2,
            "promotable_yes_no": "yes",
        },
        {
            "feature_family": "subtype_auxiliary",
            "candidate_feature_name": "v5_sub_aux_overlap_flag",
            "source_columns": "cbcl_108,cbcl_112",
            "source_tables": "HBN_hybrid_existing",
            "transformation_type": "auxiliary_flag",
            "clinical_rationale": "Subtype-aware structure for internal support only",
            "expected_effect": "analytic_support",
            "methodological_risk": "moderate",
            "leakage_risk": "moderate",
            "implementation_priority": 2,
            "promotable_yes_no": "yes",
        },
        {
            "feature_family": "hard_negative",
            "candidate_feature_name": "v5_hn_negative_guard",
            "source_columns": "transdiagnostic_burden,elimination_core",
            "source_tables": "HBN_hybrid_existing",
            "transformation_type": "difference",
            "clinical_rationale": "Hard-negative guard against diffuse distress FPs",
            "expected_effect": "specificity_gain",
            "methodological_risk": "moderate",
            "leakage_risk": "low",
            "implementation_priority": 1,
            "promotable_yes_no": "yes",
        },
        {
            "feature_family": "danger_zone",
            "candidate_feature_name": "target_* criteria counts as features",
            "source_columns": "target_*",
            "source_tables": "derived_targets",
            "transformation_type": "unsafe_direct_proxy",
            "clinical_rationale": "Near-direct diagnostic reconstruction risk",
            "expected_effect": "artificial_metric_inflation",
            "methodological_risk": "critical",
            "leakage_risk": "critical",
            "implementation_priority": 0,
            "promotable_yes_no": "no",
        },
    ]
    safe_csv(pd.DataFrame(rows), paths.feature_audit / "elimination_feature_engineering_opportunity_matrix.csv")
    safe_text(
        "# Elimination Feature Engineering Audit v5\n\n"
        "- Scope: feature representation only, no new instruments, no new external data.\n"
        "- Primary families: composite_clinical, anti_transdiagnostic, evidence_quality, hard_negative.\n"
        "- Subtype-aware features are auxiliary and not standalone target promotion.\n"
        "- All target-derived direct/proxy counts remain blocked from promotable sets.\n",
        paths.reports / "elimination_feature_engineering_audit.md",
    )


def add_generated_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, List[str]]]:
    out = df.copy()

    cbcl_108 = col_float(out, "cbcl_108")
    cbcl_112 = col_float(out, "cbcl_112")
    sdq_impact = col_float(out, "sdq_impact")
    has_cbcl = col_float(out, "has_cbcl")
    has_sdq = col_float(out, "has_sdq")
    has_ari_p = col_float(out, "has_ari_p")
    has_ari_sr = col_float(out, "has_ari_sr")

    internal_proxy = col_float(out, "cbcl_internalizing_proxy") + col_float(out, "asr_internalizing_proxy") + col_float(out, "ysr_internalizing_proxy")
    external_proxy = col_float(out, "cbcl_externalizing_proxy") + col_float(out, "asr_externalizing_proxy") + col_float(out, "ysr_externalizing_proxy")
    sdq_total_diff = col_float(out, "sdq_total_difficulties") + col_float(out, "sdq_difficulties_total_proxy")
    anti_burden = internal_proxy + external_proxy + sdq_total_diff
    elim_core_sum = cbcl_108 + cbcl_112 + sdq_impact
    elim_core_mean = elim_core_sum / 3.0

    core_df = pd.DataFrame({"cbcl_108": cbcl_108, "cbcl_112": cbcl_112, "sdq_impact": sdq_impact})
    core_observed_ratio = core_df.notna().mean(axis=1)
    core_observed_ratio = core_observed_ratio.fillna(0.0).astype(float)
    core_missing_ratio = 1.0 - core_observed_ratio

    availability_count = has_cbcl + has_sdq + has_ari_p + has_ari_sr

    q108 = float(cbcl_108.quantile(0.70)) if len(cbcl_108) else 0.0
    q112 = float(cbcl_112.quantile(0.70)) if len(cbcl_112) else 0.0
    negative_guard = anti_burden - elim_core_sum
    qneg = float(negative_guard.quantile(0.75)) if len(negative_guard) else 0.0

    generated_defs: List[Tuple[str, str, pd.Series, List[str], str, str, str, str]] = [
        (
            "v5_comp_elim_core_sum",
            "composite_clinical",
            elim_core_sum,
            ["cbcl_108", "cbcl_112", "sdq_impact"],
            "cbcl_108 + cbcl_112 + sdq_impact",
            "Core compatible elimination signal sum",
            "low",
            "low",
        ),
        (
            "v5_comp_elim_core_mean",
            "composite_clinical",
            elim_core_mean,
            ["cbcl_108", "cbcl_112", "sdq_impact"],
            "(cbcl_108 + cbcl_112 + sdq_impact) / 3",
            "Core compatible elimination signal mean",
            "low",
            "low",
        ),
        (
            "v5_comp_elim_source_convergence",
            "composite_clinical",
            ((has_cbcl + has_sdq) >= 2).astype(float),
            ["has_cbcl", "has_sdq"],
            "1 if has_cbcl + has_sdq >= 2 else 0",
            "Convergence flag between available parent-report sources",
            "low",
            "low",
        ),
        (
            "v5_comp_elim_consistency",
            "composite_clinical",
            (1.0 / (1.0 + (cbcl_108 - cbcl_112).abs())).astype(float),
            ["cbcl_108", "cbcl_112"],
            "1 / (1 + abs(cbcl_108 - cbcl_112))",
            "Consistency between core subtype proxies",
            "low",
            "low",
        ),
        (
            "v5_anti_transdiag_burden",
            "anti_transdiagnostic",
            anti_burden,
            ["cbcl_internalizing_proxy", "cbcl_externalizing_proxy", "asr_internalizing_proxy", "asr_externalizing_proxy", "ysr_internalizing_proxy", "ysr_externalizing_proxy", "sdq_total_difficulties", "sdq_difficulties_total_proxy"],
            "sum(internalizing, externalizing, sdq_difficulties proxies)",
            "Global transdiagnostic burden proxy",
            "moderate",
            "low",
        ),
        (
            "v5_anti_specificity_ratio",
            "anti_transdiagnostic",
            (elim_core_sum / (1.0 + anti_burden)).astype(float),
            ["v5_comp_elim_core_sum", "v5_anti_transdiag_burden"],
            "elim_core_sum / (1 + transdiag_burden)",
            "Relative elimination specificity vs diffuse burden",
            "moderate",
            "low",
        ),
        (
            "v5_anti_focality_index",
            "anti_transdiagnostic",
            (elim_core_mean - 0.35 * (internal_proxy + external_proxy)).astype(float),
            ["v5_comp_elim_core_mean", "cbcl_internalizing_proxy", "cbcl_externalizing_proxy"],
            "elim_core_mean - 0.35*(internalizing + externalizing)",
            "Focal elimination signal against broad internalizing/externalizing",
            "moderate",
            "low",
        ),
        (
            "v5_anti_internalizing_minus_elim",
            "anti_transdiagnostic",
            (internal_proxy - elim_core_sum).astype(float),
            ["cbcl_internalizing_proxy", "asr_internalizing_proxy", "ysr_internalizing_proxy", "v5_comp_elim_core_sum"],
            "internalizing_proxy_sum - elim_core_sum",
            "High values suggest non-specific internalizing profile",
            "moderate",
            "low",
        ),
        (
            "v5_eq_source_count",
            "evidence_quality",
            availability_count.astype(float),
            ["has_cbcl", "has_sdq", "has_ari_p", "has_ari_sr"],
            "has_cbcl + has_sdq + has_ari_p + has_ari_sr",
            "Number of useful sources available per case",
            "low",
            "low",
        ),
        (
            "v5_eq_core_observed_ratio",
            "evidence_quality",
            core_observed_ratio.astype(float),
            ["cbcl_108", "cbcl_112", "sdq_impact"],
            "non_missing_ratio([cbcl_108, cbcl_112, sdq_impact])",
            "Observed core signal ratio",
            "low",
            "low",
        ),
        (
            "v5_eq_missing_ratio_core",
            "evidence_quality",
            core_missing_ratio.astype(float),
            ["v5_eq_core_observed_ratio"],
            "1 - core_observed_ratio",
            "Core missingness ratio",
            "low",
            "low",
        ),
        (
            "v5_eq_evidence_quality_score",
            "evidence_quality",
            (availability_count + core_observed_ratio - 0.5 * core_missing_ratio).astype(float),
            ["v5_eq_source_count", "v5_eq_core_observed_ratio", "v5_eq_missing_ratio_core"],
            "source_count + core_observed_ratio - 0.5*missing_ratio_core",
            "Simple evidence quality score",
            "low",
            "low",
        ),
        (
            "v5_sub_aux_enuresis_proxy_flag",
            "subtype_auxiliary",
            (cbcl_108 >= q108).astype(float),
            ["cbcl_108"],
            f"1 if cbcl_108 >= q70({q108:.4f}) else 0",
            "Auxiliary enuresis-like proxy flag",
            "moderate",
            "moderate",
        ),
        (
            "v5_sub_aux_encopresis_proxy_flag",
            "subtype_auxiliary",
            (cbcl_112 >= q112).astype(float),
            ["cbcl_112"],
            f"1 if cbcl_112 >= q70({q112:.4f}) else 0",
            "Auxiliary encopresis-like proxy flag",
            "moderate",
            "moderate",
        ),
        (
            "v5_sub_aux_overlap_flag",
            "subtype_auxiliary",
            (((cbcl_108 >= q108) & (cbcl_112 >= q112)).astype(float)),
            ["v5_sub_aux_enuresis_proxy_flag", "v5_sub_aux_encopresis_proxy_flag"],
            "1 if both subtype auxiliary flags are active else 0",
            "Auxiliary mixed subtype pattern",
            "moderate",
            "moderate",
        ),
        (
            "v5_sub_aux_dominance_index",
            "subtype_auxiliary",
            (cbcl_108 - cbcl_112).astype(float),
            ["cbcl_108", "cbcl_112"],
            "cbcl_108 - cbcl_112",
            "Subtype dominance proxy (auxiliary only)",
            "moderate",
            "moderate",
        ),
        (
            "v5_hn_negative_guard",
            "hard_negative",
            negative_guard.astype(float),
            ["v5_anti_transdiag_burden", "v5_comp_elim_core_sum"],
            "transdiag_burden - elim_core_sum",
            "Hard-negative guard against diffuse distress false positives",
            "moderate",
            "low",
        ),
        (
            "v5_hn_transdiag_pressure",
            "hard_negative",
            anti_burden.astype(float),
            ["v5_anti_transdiag_burden"],
            "copy(v5_anti_transdiag_burden)",
            "Raw transdiagnostic pressure for guard analysis",
            "moderate",
            "low",
        ),
        (
            "v5_hn_hard_negative_flag",
            "hard_negative",
            (negative_guard >= qneg).astype(float),
            ["v5_hn_negative_guard"],
            f"1 if negative_guard >= q75({qneg:.4f}) else 0",
            "Flag likely hard negatives with diffuse burden",
            "moderate",
            "low",
        ),
    ]

    registry_rows: List[Dict[str, Any]] = []
    lineage_rows: List[Dict[str, Any]] = []
    family_map: Dict[str, List[str]] = {}
    for name, family, series, src_cols, rule, rationale, methodological_risk, leakage_risk in generated_defs:
        out[name] = pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)
        family_map.setdefault(family, []).append(name)
        registry_rows.append(
            {
                "generated_feature_name": name,
                "feature_family": family,
                "source_columns": ",".join(src_cols),
                "transformation_type": "derived_composite",
                "derivation_rule": rule,
                "clinical_rationale": rationale,
                "methodological_risk": methodological_risk,
                "leakage_risk": leakage_risk,
                "promotable_yes_no": "yes" if leakage_risk != "critical" else "no",
            }
        )
        lineage_rows.append(
            {
                "generated_feature_name": name,
                "source_columns": ",".join(src_cols),
                "source_tables": "HBN_hybrid_existing",
                "derivation_rule": rule,
                "base_data_scope": "strict_no_leakage_hybrid_or_research_extended_hybrid",
                "lineage_version": "v5",
            }
        )
    return out, registry_rows, lineage_rows, family_map


def run_feature_generation(paths: Paths, strict: pd.DataFrame, research: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, List[str]]]:
    strict_v5, strict_reg, strict_lin, family_map = add_generated_features(strict)
    research_v5, _, _, _ = add_generated_features(research)
    safe_csv(pd.DataFrame(strict_reg), paths.feature_generation / "elimination_generated_feature_registry.csv")
    safe_csv(pd.DataFrame(strict_lin), paths.feature_generation / "elimination_generated_feature_lineage.csv")
    safe_text(
        "# Elimination Generated Features Report v5\n\n"
        f"- generated_at_utc: {now_iso()}\n"
        f"- generated_feature_count: {len(strict_reg)}\n"
        f"- families: {', '.join(sorted(family_map.keys()))}\n"
        "- Rule: all generated features are derived only from existing HBN+DSM artifacts.\n"
        "- Guard: no target/raw diagnostic fields were used for generated promotable features.\n",
        paths.reports / "elimination_generated_features_report.md",
    )
    return strict_v5, research_v5, family_map


def cap_features(df: pd.DataFrame, columns: List[str], max_features: int) -> List[str]:
    cols = [c for c in columns if c in df.columns]
    if len(cols) <= max_features:
        return cols
    quality = df[cols].notna().mean().sort_values(ascending=False)
    return quality.head(max_features).index.tolist()


def build_feature_sets(
    paths: Paths,
    strict_v5: pd.DataFrame,
    risk_map: Dict[str, str],
    family_map: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    all_cols = strict_v5.columns.tolist()
    candidate_pool: List[str] = []
    for c in all_cols:
        if is_blocked_feature(c):
            continue
        s = strict_v5[c]
        if s.nunique(dropna=True) <= 1:
            continue
        if s.notna().mean() < 0.03:
            continue
        candidate_pool.append(c)

    generated_cols = {c for c in all_cols if c.startswith("v5_")}

    def by_risk(max_risk: str) -> List[str]:
        order = {"low": 1, "moderate": 2, "high": 3, "critical": 4}
        max_val = order[max_risk]
        return [c for c in candidate_pool if order[risk_level(c, risk_map)] <= max_val]

    replay = [c for c in by_risk("moderate") if (not c.startswith("q_qi_")) and (c not in generated_cols)]
    replay = cap_features(strict_v5, replay, 240)

    comp = cap_features(strict_v5, list(dict.fromkeys(replay + family_map.get("composite_clinical", []))), 220)
    anti_base = [
        c
        for c in replay
        if not any(tok in c.lower() for tok in ["anxiety", "depress", "adhd", "conduct", "dmdd", "internalizing", "externalizing"])
    ]
    anti = cap_features(strict_v5, list(dict.fromkeys(anti_base + family_map.get("anti_transdiagnostic", []) + ["cbcl_108", "cbcl_112", "sdq_impact"])), 220)
    evidence = cap_features(strict_v5, list(dict.fromkeys(replay + family_map.get("evidence_quality", []))), 220)
    subtype = cap_features(strict_v5, list(dict.fromkeys(replay + family_map.get("subtype_auxiliary", []) + ["cbcl_108", "cbcl_112"])), 220)
    hard_negative = cap_features(strict_v5, list(dict.fromkeys(anti_base + family_map.get("hard_negative", []) + ["cbcl_108", "cbcl_112", "sdq_impact"])), 220)
    combined = cap_features(
        strict_v5,
        list(
            dict.fromkeys(
                replay
                + family_map.get("composite_clinical", [])
                + family_map.get("anti_transdiagnostic", [])
                + family_map.get("evidence_quality", [])
                + family_map.get("hard_negative", [])
            )
        ),
        210,
    )
    two_stage_ready = cap_features(
        strict_v5,
        list(dict.fromkeys(combined + family_map.get("subtype_auxiliary", []) + ["v5_hn_negative_guard", "v5_anti_specificity_ratio"])),
        190,
    )
    abstention_ready = cap_features(
        strict_v5,
        list(dict.fromkeys(combined + family_map.get("evidence_quality", []) + family_map.get("hard_negative", []))),
        220,
    )
    research_context = cap_features(strict_v5, list(dict.fromkeys(comp + family_map.get("anti_transdiagnostic", []))), 260)

    sets: Dict[str, List[str]] = {
        "elimination_fs_v5_replay_v2_best": replay,
        "elimination_fs_v5_composite_clinical": comp,
        "elimination_fs_v5_anti_transdiagnostic": anti,
        "elimination_fs_v5_evidence_quality": evidence,
        "elimination_fs_v5_subtype_auxiliary": subtype,
        "elimination_fs_v5_hard_negative_filtering": hard_negative,
        "elimination_fs_v5_compact_best_combined": combined,
        "elimination_fs_v5_two_stage_ready": two_stage_ready,
        "elimination_fs_v5_abstention_ready": abstention_ready,
        "elimination_fs_v5_research_context_only": research_context,
    }

    family_lookup = {f: set(cols) for f, cols in family_map.items()}
    registry_rows: List[Dict[str, Any]] = []
    drop_rows: List[Dict[str, Any]] = []
    for name, cols in sets.items():
        fams = [fam for fam, fam_cols in family_lookup.items() if any(c in fam_cols for c in cols)]
        leakage = "low"
        if any(risk_level(c, risk_map) == "critical" for c in cols):
            leakage = "high"
        elif any(risk_level(c, risk_map) == "high" for c in cols):
            leakage = "medium"
        complexity = "compact" if len(cols) <= 180 else ("moderate" if len(cols) <= 240 else "broad")
        hypothesis = {
            "elimination_fs_v5_replay_v2_best": "control_replay",
            "elimination_fs_v5_composite_clinical": "H1",
            "elimination_fs_v5_anti_transdiagnostic": "H2",
            "elimination_fs_v5_evidence_quality": "H3",
            "elimination_fs_v5_subtype_auxiliary": "H4",
            "elimination_fs_v5_hard_negative_filtering": "H5",
            "elimination_fs_v5_compact_best_combined": "H1+H2+H3+H5",
            "elimination_fs_v5_two_stage_ready": "H6",
            "elimination_fs_v5_abstention_ready": "H6",
            "elimination_fs_v5_research_context_only": "context_only",
        }[name]
        promotable = "no" if name.endswith("research_context_only") else "yes"
        registry_rows.append(
            {
                "feature_set_name": name,
                "n_features": len(cols),
                "contains_generated_families": ",".join(sorted(fams)) if fams else "",
                "hypothesis_tested": hypothesis,
                "complexity": complexity,
                "leakage_risk": leakage,
                "promotable": promotable,
                "notes": "strict_no_leakage_main" if promotable == "yes" else "research_secondary_non_promotable",
            }
        )

        for c in all_cols:
            if c in cols:
                continue
            if is_blocked_feature(c):
                reason = "leakage_guard_or_non_feature"
            elif c not in candidate_pool:
                reason = "low_utility_or_sparse_or_constant"
            elif risk_level(c, risk_map) in {"high", "critical"} and name != "elimination_fs_v5_research_context_only":
                reason = "risk_filter"
            else:
                reason = "not_selected_for_strategy"
            drop_rows.append({"feature_set_name": name, "feature_name": c, "drop_reason": reason})

    safe_csv(pd.DataFrame(registry_rows), paths.feature_sets / "elimination_v5_feature_set_registry.csv")
    safe_csv(pd.DataFrame(drop_rows), paths.feature_sets / "elimination_v5_feature_drop_log.csv")
    safe_text(
        "# Elimination v5 Feature Set Design\n\n"
        "- Main scope uses strict_no_leakage_hybrid and excludes target/raw diagnostic fields.\n"
        "- Research-only set is explicitly non-promotable.\n"
        "- Feature sets are hypothesis-linked and capped for stability.\n",
        paths.reports / "elimination_v5_feature_set_design.md",
    )
    return sets


def trial_plan() -> List[Dict[str, Any]]:
    base = {
        "n_estimators": 220,
        "max_depth": 6,
        "min_samples_leaf": 8,
        "min_samples_split": 20,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
    }
    return [
        {"trial_id": "V5_T01_control_replay_v2_best", "linked_hypothesis": "control", "dataset_key": "strict", "feature_set": "elimination_fs_v5_replay_v2_best", "threshold_strategy": "balanced", "calibration": False, "params": base},
        {"trial_id": "V5_T02_composite_clinical", "linked_hypothesis": "H1", "dataset_key": "strict", "feature_set": "elimination_fs_v5_composite_clinical", "threshold_strategy": "balanced", "calibration": False, "params": {**base, "n_estimators": 240, "min_samples_leaf": 9}},
        {"trial_id": "V5_T03_anti_transdiagnostic", "linked_hypothesis": "H2", "dataset_key": "strict", "feature_set": "elimination_fs_v5_anti_transdiagnostic", "threshold_strategy": "precision", "recall_floor": 0.65, "calibration": False, "params": {**base, "max_depth": 5, "min_samples_leaf": 10, "max_features": "log2"}},
        {"trial_id": "V5_T04_evidence_quality_meta", "linked_hypothesis": "H3", "dataset_key": "strict", "feature_set": "elimination_fs_v5_evidence_quality", "threshold_strategy": "balanced", "calibration": True, "params": {**base, "n_estimators": 260, "min_samples_leaf": 10}},
        {"trial_id": "V5_T05_subtype_auxiliary", "linked_hypothesis": "H4", "dataset_key": "strict", "feature_set": "elimination_fs_v5_subtype_auxiliary", "threshold_strategy": "balanced", "calibration": False, "params": {**base, "max_depth": 5, "min_samples_leaf": 12}},
        {"trial_id": "V5_T06_hard_negative_engineering", "linked_hypothesis": "H5", "dataset_key": "strict", "feature_set": "elimination_fs_v5_hard_negative_filtering", "threshold_strategy": "conservative", "calibration": True, "params": {**base, "max_depth": 5, "min_samples_leaf": 11, "min_samples_split": 24}},
        {"trial_id": "V5_T07_compact_best_combined", "linked_hypothesis": "H1+H2+H3+H5", "dataset_key": "strict", "feature_set": "elimination_fs_v5_compact_best_combined", "threshold_strategy": "balanced", "calibration": True, "params": {**base, "n_estimators": 280, "max_depth": 6, "min_samples_leaf": 10}},
        {"trial_id": "V5_T08_two_stage_filter", "linked_hypothesis": "H6", "dataset_key": "strict", "feature_set": "elimination_fs_v5_two_stage_ready", "threshold_strategy": "balanced", "calibration": True, "two_stage": True, "params": {**base, "n_estimators": 260, "max_depth": 6, "min_samples_leaf": 9}},
        {"trial_id": "V5_T09_abstention_ready_refit", "linked_hypothesis": "H6", "dataset_key": "strict", "feature_set": "elimination_fs_v5_abstention_ready", "threshold_strategy": "balanced", "calibration": True, "params": {**base, "n_estimators": 240, "max_depth": 6, "min_samples_leaf": 9}},
        {"trial_id": "V5_T10_research_context_optional", "linked_hypothesis": "context_only", "dataset_key": "research", "feature_set": "elimination_fs_v5_research_context_only", "threshold_strategy": "balanced", "calibration": False, "non_promotable": True, "params": {**base, "n_estimators": 220}},
        {"trial_id": "V5_T11_stop_condition_control", "linked_hypothesis": "H7", "dataset_key": "strict", "feature_set": "elimination_fs_v5_compact_best_combined", "threshold_strategy": "conservative", "calibration": True, "params": {**base, "n_estimators": 320, "max_depth": 5, "min_samples_leaf": 13, "min_samples_split": 28}},
        {"trial_id": "V5_T12_best_honest_candidate_final", "linked_hypothesis": "best_candidate", "dataset_key": "strict", "feature_set": "elimination_fs_v5_compact_best_combined", "threshold_strategy": "precision", "recall_floor": 0.67, "calibration": True, "params": {**base, "n_estimators": 300, "max_depth": 6, "min_samples_leaf": 11, "min_samples_split": 24}},
    ]


def derive_stage2_config(X_val: pd.DataFrame, y_val: np.ndarray) -> Dict[str, Any]:
    if "v5_hn_negative_guard" not in X_val.columns or "v5_anti_specificity_ratio" not in X_val.columns:
        return {"enabled": False}
    guard = pd.to_numeric(X_val["v5_hn_negative_guard"], errors="coerce").fillna(0.0).to_numpy()
    ratio = pd.to_numeric(X_val["v5_anti_specificity_ratio"], errors="coerce").fillna(0.0).to_numpy()
    neg = guard[y_val == 0] if np.any(y_val == 0) else guard
    pos = ratio[y_val == 1] if np.any(y_val == 1) else ratio
    guard_cut = float(np.quantile(neg, 0.65)) if len(neg) else float(np.quantile(guard, 0.65))
    ratio_cut = float(np.quantile(pos, 0.35)) if len(pos) else float(np.quantile(ratio, 0.35))
    return {"enabled": True, "guard_col": "v5_hn_negative_guard", "ratio_col": "v5_anti_specificity_ratio", "guard_cut": guard_cut, "ratio_cut": ratio_cut, "soft_penalty": 0.35}


def apply_stage2(prob: np.ndarray, X: pd.DataFrame, cfg: Dict[str, Any]) -> np.ndarray:
    if not cfg.get("enabled", False):
        return prob
    guard = pd.to_numeric(X.get(cfg["guard_col"], pd.Series(np.zeros(len(X)), index=X.index)), errors="coerce").fillna(0.0).to_numpy()
    ratio = pd.to_numeric(X.get(cfg["ratio_col"], pd.Series(np.zeros(len(X)), index=X.index)), errors="coerce").fillna(0.0).to_numpy()
    gate = (guard <= float(cfg["guard_cut"])) & (ratio >= float(cfg["ratio_cut"]))
    scale = np.where(gate, 1.0, float(cfg["soft_penalty"]))
    return (prob * scale).astype(float)


def metric_nan() -> Dict[str, Any]:
    return {
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


def fit_trial_once(
    source_df: pd.DataFrame,
    feature_cols: List[str],
    params: Dict[str, Any],
    threshold_strategy: str,
    recall_floor: float,
    calibration: bool,
    split_seed: int,
    model_seed: int,
    two_stage: bool,
) -> Dict[str, Any]:
    y = pd.to_numeric(source_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    ids_train, ids_val, ids_test = v2.split_ids(source_df["participant_id"].astype(str), y, split_seed)
    frame = pd.concat(
        [
            source_df[["participant_id"]].reset_index(drop=True),
            source_df[feature_cols].reset_index(drop=True),
            y.rename("y").reset_index(drop=True),
        ],
        axis=1,
    )
    tr = v2.subset_by_ids(frame, ids_train)
    va = v2.subset_by_ids(frame, ids_val)
    te = v2.subset_by_ids(frame, ids_test)

    X_train = tr[feature_cols].copy()
    y_train = pd.to_numeric(tr["y"], errors="coerce").fillna(0).astype(int)
    X_val = va[feature_cols].copy()
    y_val = pd.to_numeric(va["y"], errors="coerce").fillna(0).astype(int)
    X_test = te[feature_cols].copy()
    y_test = pd.to_numeric(te["y"], errors="coerce").fillna(0).astype(int)

    if y_train.nunique() < 2 or y_val.nunique() < 2 or y_test.nunique() < 2:
        return {
            "ok": False,
            "reason": "insufficient_class_support",
            "train_metrics": metric_nan(),
            "val_metrics": metric_nan(),
            "test_metrics": metric_nan(),
            "threshold": np.nan,
            "calibration_strategy": "none",
            "brier_val": np.nan,
            "brier_test": np.nan,
            "split_sizes": {"train": len(y_train), "val": len(y_val), "test": len(y_test)},
            "y_val": np.array([]),
            "p_val": np.array([]),
            "y_test": np.array([]),
            "p_test": np.array([]),
            "model": None,
            "stage2_cfg": {"enabled": False},
            "X_test": X_test,
        }

    model_params = dict(params)
    model_params["random_state"] = model_seed
    model = v2.build_pipeline(X_train, model_params)
    model.fit(X_train, y_train)
    v2.force_single_thread(model)

    calibration_strategy = "none"
    if calibration:
        try:
            calibrator = CalibratedClassifierCV(estimator=model, method="sigmoid", cv=3)
            calibrator.fit(X_train, y_train)
            model = calibrator
            v2.force_single_thread(model)
            calibration_strategy = "sigmoid"
        except Exception:
            calibration_strategy = "sigmoid_failed_fallback_none"

    p_train = model.predict_proba(X_train)[:, 1]
    p_val = model.predict_proba(X_val)[:, 1]
    p_test = model.predict_proba(X_test)[:, 1]

    stage2_cfg = {"enabled": False}
    if two_stage:
        stage2_cfg = derive_stage2_config(X_val, y_val.to_numpy())
        p_train = apply_stage2(p_train, X_train, stage2_cfg)
        p_val = apply_stage2(p_val, X_val, stage2_cfg)
        p_test = apply_stage2(p_test, X_test, stage2_cfg)

    threshold = v2.choose_threshold(y_val.to_numpy(), p_val, strategy=threshold_strategy, recall_floor=recall_floor)
    train_metrics = v2.metric_binary(y_train.to_numpy(), p_train, threshold)
    val_metrics = v2.metric_binary(y_val.to_numpy(), p_val, threshold)
    test_metrics = v2.metric_binary(y_test.to_numpy(), p_test, threshold)

    return {
        "ok": True,
        "reason": "",
        "train_metrics": train_metrics,
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "threshold": float(threshold),
        "calibration_strategy": calibration_strategy,
        "brier_val": float(brier_score_loss(y_val.to_numpy(), p_val)),
        "brier_test": float(brier_score_loss(y_test.to_numpy(), p_test)),
        "split_sizes": {"train": len(y_train), "val": len(y_val), "test": len(y_test)},
        "y_val": y_val.to_numpy(),
        "p_val": p_val,
        "y_test": y_test.to_numpy(),
        "p_test": p_test,
        "model": model,
        "stage2_cfg": stage2_cfg,
        "X_test": X_test,
        "X_train": X_train,
        "X_val": X_val,
    }


def evaluate_trial(
    trial: Dict[str, Any],
    strict_df: pd.DataFrame,
    research_df: pd.DataFrame,
    feature_sets: Dict[str, List[str]],
    risk_map: Dict[str, str],
) -> Dict[str, Any]:
    source = strict_df if trial["dataset_key"] == "strict" else research_df
    feature_cols = [c for c in feature_sets[trial["feature_set"]] if c in source.columns]
    feature_cols = [c for c in feature_cols if not is_blocked_feature(c)]

    fit = fit_trial_once(
        source_df=source,
        feature_cols=feature_cols,
        params=trial["params"],
        threshold_strategy=trial.get("threshold_strategy", "balanced"),
        recall_floor=float(trial.get("recall_floor", 0.60)),
        calibration=bool(trial.get("calibration", False)),
        split_seed=RANDOM_STATE,
        model_seed=RANDOM_STATE,
        two_stage=bool(trial.get("two_stage", False)),
    )

    seed_balacc: List[float] = []
    split_balacc: List[float] = []
    seed_rows: List[Dict[str, Any]] = []
    split_rows: List[Dict[str, Any]] = []
    stress_rows: List[Dict[str, Any]] = []
    realism_rows: List[Dict[str, Any]] = []
    threshold_rows: List[Dict[str, Any]] = []

    if fit["ok"]:
        for seed in [7, 42, 2026]:
            run = fit_trial_once(
                source_df=source,
                feature_cols=feature_cols,
                params=trial["params"],
                threshold_strategy=trial.get("threshold_strategy", "balanced"),
                recall_floor=float(trial.get("recall_floor", 0.60)),
                calibration=bool(trial.get("calibration", False)),
                split_seed=RANDOM_STATE,
                model_seed=seed,
                two_stage=bool(trial.get("two_stage", False)),
            )
            b = float(run["test_metrics"]["balanced_accuracy"])
            seed_balacc.append(b)
            seed_rows.append({"trial_id": trial["trial_id"], "seed": seed, "test_balanced_accuracy": b, "test_precision": run["test_metrics"]["precision"], "test_recall": run["test_metrics"]["recall"]})

        for split_seed in [42, 99, 777]:
            run = fit_trial_once(
                source_df=source,
                feature_cols=feature_cols,
                params=trial["params"],
                threshold_strategy=trial.get("threshold_strategy", "balanced"),
                recall_floor=float(trial.get("recall_floor", 0.60)),
                calibration=bool(trial.get("calibration", False)),
                split_seed=split_seed,
                model_seed=RANDOM_STATE,
                two_stage=bool(trial.get("two_stage", False)),
            )
            b = float(run["test_metrics"]["balanced_accuracy"])
            split_balacc.append(b)
            split_rows.append({"trial_id": trial["trial_id"], "split_seed": split_seed, "test_balanced_accuracy": b, "test_precision": run["test_metrics"]["precision"], "test_recall": run["test_metrics"]["recall"]})

        model = fit["model"]
        threshold = float(fit["threshold"])
        y_test = fit["y_test"]
        X_test = fit["X_test"]
        stage2_cfg = fit["stage2_cfg"]
        rng = np.random.default_rng(RANDOM_STATE)

        for lvl in [1, 2]:
            X_noise = v2.noise_apply(X_test.copy(), lvl, rng)
            p_noise = model.predict_proba(X_noise)[:, 1]
            if stage2_cfg.get("enabled", False):
                p_noise = apply_stage2(p_noise, X_noise, stage2_cfg)
            m_noise = v2.metric_binary(y_test, p_noise, threshold)
            stress_rows.append({"trial_id": trial["trial_id"], "test_type": f"noise_level_{lvl}", **m_noise})

        for scenario in ["incomplete_inputs", "contradictory_inputs", "mixed_comorbidity_signals"]:
            X_real = v2.realism_apply(X_test.copy(), scenario, rng)
            p_real = model.predict_proba(X_real)[:, 1]
            if stage2_cfg.get("enabled", False):
                p_real = apply_stage2(p_real, X_real, stage2_cfg)
            m_real = v2.metric_binary(y_test, p_real, threshold)
            realism_rows.append({"trial_id": trial["trial_id"], "scenario": scenario, **m_real})

        p_val = fit["p_val"]
        y_val = fit["y_val"]
        for thr in np.linspace(max(0.05, threshold - 0.20), min(0.95, threshold + 0.20), 9):
            m_thr = v2.metric_binary(y_val, p_val, float(thr))
            threshold_rows.append({"trial_id": trial["trial_id"], "threshold": float(thr), "precision": m_thr["precision"], "recall": m_thr["recall"], "specificity": m_thr["specificity"], "balanced_accuracy": m_thr["balanced_accuracy"]})

    seed_std = float(np.std(seed_balacc)) if seed_balacc else np.nan
    split_std = float(np.std(split_balacc)) if split_balacc else np.nan
    stress_df = pd.DataFrame(stress_rows)
    realism_df = pd.DataFrame(realism_rows)
    base_balacc = float(fit["test_metrics"]["balanced_accuracy"])
    noise_mild_drop = float(base_balacc - stress_df.loc[stress_df["test_type"] == "noise_level_1", "balanced_accuracy"].iloc[0]) if len(stress_df) else np.nan
    noise_moderate_drop = float(base_balacc - stress_df.loc[stress_df["test_type"] == "noise_level_2", "balanced_accuracy"].iloc[0]) if len(stress_df) else np.nan
    realism_worst_drop = float(base_balacc - realism_df["balanced_accuracy"].min()) if len(realism_df) else np.nan

    metrics_for_perfect = [
        fit["train_metrics"]["precision"],
        fit["train_metrics"]["balanced_accuracy"],
        fit["val_metrics"]["precision"],
        fit["val_metrics"]["balanced_accuracy"],
        fit["test_metrics"]["precision"],
        fit["test_metrics"]["balanced_accuracy"],
        fit["test_metrics"]["recall"],
        fit["test_metrics"]["specificity"],
    ]
    suspicious_perfect = bool(any(np.isfinite(v) and float(v) >= 0.999 for v in metrics_for_perfect))
    residual_critical = int(sum(1 for c in feature_cols if risk_level(c, risk_map) == "critical"))
    residual_high = int(sum(1 for c in feature_cols if risk_level(c, risk_map) == "high"))

    if residual_critical > 0:
        leakage_class = "high"
    elif residual_high > 20:
        leakage_class = "medium"
    else:
        leakage_class = "low"

    if not fit["ok"]:
        preliminary = "insufficient_class_support"
    elif residual_critical > 0:
        preliminary = "leakage_residual"
    elif suspicious_perfect:
        preliminary = "suspicious_perfect_score"
    elif (np.isfinite(seed_std) and seed_std > 0.03) or (np.isfinite(split_std) and split_std > 0.04):
        preliminary = "unstable"
    elif (np.isfinite(noise_moderate_drop) and noise_moderate_drop > 0.08) or (np.isfinite(realism_worst_drop) and realism_worst_drop > 0.10):
        preliminary = "fragile_under_shift"
    else:
        preliminary = "candidate_honest"

    return {
        "trial": trial,
        "feature_cols": feature_cols,
        "fit": fit,
        "seed_rows": seed_rows,
        "split_rows": split_rows,
        "stress_rows": stress_rows,
        "realism_rows": realism_rows,
        "threshold_rows": threshold_rows,
        "seed_std": seed_std,
        "split_std": split_std,
        "noise_mild_drop_balacc": noise_mild_drop,
        "noise_moderate_drop_balacc": noise_moderate_drop,
        "realism_worst_drop_balacc": realism_worst_drop,
        "suspicious_perfect_score": suspicious_perfect,
        "residual_critical": residual_critical,
        "residual_high": residual_high,
        "leakage_class": leakage_class,
        "preliminary_decision": preliminary,
    }


def run_trials(
    paths: Paths,
    strict_df: pd.DataFrame,
    research_df: pd.DataFrame,
    feature_sets: Dict[str, List[str]],
    family_map: Dict[str, List[str]],
    risk_map: Dict[str, str],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, Any]]]:
    registry_rows: List[Dict[str, Any]] = []
    metrics_rows: List[Dict[str, Any]] = []
    stability_rows: List[Dict[str, Any]] = []
    perfect_rows: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    stress_rows: List[Dict[str, Any]] = []
    realism_rows: List[Dict[str, Any]] = []
    threshold_rows: List[Dict[str, Any]] = []
    trial_outputs: Dict[str, Dict[str, Any]] = {}
    family_lookup = {f: set(cols) for f, cols in family_map.items()}

    for trial in trial_plan():
        LOGGER.info("Running %s", trial["trial_id"])
        result = evaluate_trial(trial, strict_df, research_df, feature_sets, risk_map)
        trial_outputs[trial["trial_id"]] = result
        fit = result["fit"]
        used_fams = [fam for fam, fam_cols in family_lookup.items() if any(c in fam_cols for c in result["feature_cols"])]

        registry_rows.append(
            {
                "trial_id": trial["trial_id"],
                "linked_hypothesis": trial["linked_hypothesis"],
                "feature_set_used": trial["feature_set"],
                "generated_feature_families_used": ",".join(sorted(used_fams)) if used_fams else "",
                "dataset_key": trial["dataset_key"],
                "threshold_strategy": trial.get("threshold_strategy", "balanced"),
                "calibration_strategy": "sigmoid" if trial.get("calibration", False) else "none",
                "two_stage": bool(trial.get("two_stage", False)),
                "hyperparameters": json.dumps(trial["params"]),
                "n_features": len(result["feature_cols"]),
                "non_promotable": bool(trial.get("non_promotable", False)),
                "preliminary_decision": result["preliminary_decision"],
                "residual_critical": result["residual_critical"],
                "residual_high": result["residual_high"],
            }
        )

        metrics_rows.append(
            {
                "trial_id": trial["trial_id"],
                "linked_hypothesis": trial["linked_hypothesis"],
                "feature_set_used": trial["feature_set"],
                "dataset_key": trial["dataset_key"],
                "n_features": len(result["feature_cols"]),
                "threshold_strategy": trial.get("threshold_strategy", "balanced"),
                "calibration_strategy": fit["calibration_strategy"],
                "threshold_value": fit["threshold"],
                "train_accuracy": fit["train_metrics"]["accuracy"],
                "train_balanced_accuracy": fit["train_metrics"]["balanced_accuracy"],
                "train_precision": fit["train_metrics"]["precision"],
                "train_recall": fit["train_metrics"]["recall"],
                "train_specificity": fit["train_metrics"]["specificity"],
                "train_f1": fit["train_metrics"]["f1"],
                "train_roc_auc": fit["train_metrics"]["roc_auc"],
                "train_pr_auc": fit["train_metrics"]["pr_auc"],
                "val_accuracy": fit["val_metrics"]["accuracy"],
                "val_balanced_accuracy": fit["val_metrics"]["balanced_accuracy"],
                "val_precision": fit["val_metrics"]["precision"],
                "val_recall": fit["val_metrics"]["recall"],
                "val_specificity": fit["val_metrics"]["specificity"],
                "val_f1": fit["val_metrics"]["f1"],
                "val_roc_auc": fit["val_metrics"]["roc_auc"],
                "val_pr_auc": fit["val_metrics"]["pr_auc"],
                "test_accuracy": fit["test_metrics"]["accuracy"],
                "test_balanced_accuracy": fit["test_metrics"]["balanced_accuracy"],
                "test_precision": fit["test_metrics"]["precision"],
                "test_recall": fit["test_metrics"]["recall"],
                "test_specificity": fit["test_metrics"]["specificity"],
                "test_f1": fit["test_metrics"]["f1"],
                "test_roc_auc": fit["test_metrics"]["roc_auc"],
                "test_pr_auc": fit["test_metrics"]["pr_auc"],
                "brier_val": fit["brier_val"],
                "brier_test": fit["brier_test"],
                "seed_std_balacc": result["seed_std"],
                "split_std_balacc": result["split_std"],
                "noise_mild_drop_balacc": result["noise_mild_drop_balacc"],
                "noise_moderate_drop_balacc": result["noise_moderate_drop_balacc"],
                "realism_worst_drop_balacc": result["realism_worst_drop_balacc"],
                "suspicious_perfect_score": result["suspicious_perfect_score"],
                "residual_critical": result["residual_critical"],
                "residual_high": result["residual_high"],
                "leakage_class": result["leakage_class"],
                "preliminary_decision": result["preliminary_decision"],
                "non_promotable": bool(trial.get("non_promotable", False)),
            }
        )

        seed_values = [r["test_balanced_accuracy"] for r in result["seed_rows"]]
        split_values = [r["test_balanced_accuracy"] for r in result["split_rows"]]
        stability_rows.append(
            {
                "trial_id": trial["trial_id"],
                "seed_mean_balacc": float(np.mean(seed_values)) if seed_values else np.nan,
                "seed_std_balacc": float(np.std(seed_values)) if seed_values else np.nan,
                "seed_min_balacc": float(np.min(seed_values)) if seed_values else np.nan,
                "seed_max_balacc": float(np.max(seed_values)) if seed_values else np.nan,
                "seed_cv_balacc": float(np.std(seed_values) / np.mean(seed_values)) if seed_values and np.mean(seed_values) else np.nan,
                "split_mean_balacc": float(np.mean(split_values)) if split_values else np.nan,
                "split_std_balacc": float(np.std(split_values)) if split_values else np.nan,
                "split_min_balacc": float(np.min(split_values)) if split_values else np.nan,
                "split_max_balacc": float(np.max(split_values)) if split_values else np.nan,
                "split_cv_balacc": float(np.std(split_values) / np.mean(split_values)) if split_values and np.mean(split_values) else np.nan,
                "noise_mild_drop_balacc": result["noise_mild_drop_balacc"],
                "noise_moderate_drop_balacc": result["noise_moderate_drop_balacc"],
                "realism_worst_drop_balacc": result["realism_worst_drop_balacc"],
            }
        )

        perfect_rows.append({"trial_id": trial["trial_id"], "suspicious_perfect_score": result["suspicious_perfect_score"], "trigger_detail": "metric>=0.999 in train/val/test set" if result["suspicious_perfect_score"] else "none", "blocked_from_promotion": bool(result["suspicious_perfect_score"])})
        leakage_rows.append({"trial_id": trial["trial_id"], "residual_critical_features": result["residual_critical"], "residual_high_features": result["residual_high"], "leakage_risk_class": result["leakage_class"], "blocked_from_promotion": bool(result["residual_critical"] > 0)})

        stress_rows.extend(result["stress_rows"])
        realism_rows.extend(result["realism_rows"])
        threshold_rows.extend(result["threshold_rows"])

    reg_df = pd.DataFrame(registry_rows)
    met_df = pd.DataFrame(metrics_rows)
    stability_df = pd.DataFrame(stability_rows)
    perfect_df = pd.DataFrame(perfect_rows)
    leakage_df = pd.DataFrame(leakage_rows)
    stress_df = pd.DataFrame(stress_rows)
    realism_df = pd.DataFrame(realism_rows)
    threshold_df = pd.DataFrame(threshold_rows)

    safe_csv(reg_df, paths.trials / "elimination_v5_trial_registry.csv")
    safe_csv(met_df, paths.trials / "elimination_v5_trial_metrics_full.csv")
    safe_csv(stability_df, paths.tables / "elimination_v5_stability_review.csv")
    safe_csv(perfect_df, paths.tables / "elimination_v5_perfect_score_audit.csv")
    safe_csv(leakage_df, paths.tables / "elimination_v5_leakage_review.csv")
    safe_csv(stress_df, paths.tables / "elimination_v5_stress_results.csv")
    safe_csv(realism_df, paths.tables / "elimination_v5_realism_results.csv")
    safe_csv(threshold_df, paths.tables / "elimination_v5_threshold_sweep.csv")
    return reg_df, met_df, trial_outputs


def select_best_honest(reg_df: pd.DataFrame, met_df: pd.DataFrame, paths: Paths) -> pd.Series:
    merged = met_df.copy()
    if "non_promotable" not in merged.columns:
        merged = merged.merge(reg_df[["trial_id", "non_promotable"]], on="trial_id", how="left")
    merged["non_promotable"] = merged["non_promotable"].fillna(False).astype(bool)
    merged["honest_score"] = (
        100.0 * merged["test_balanced_accuracy"].fillna(-1.0)
        + 18.0 * merged["test_precision"].fillna(-1.0)
        + 10.0 * merged["test_recall"].fillna(-1.0)
        + 8.0 * merged["test_specificity"].fillna(-1.0)
        - 120.0 * merged["seed_std_balacc"].fillna(0.0)
        - 140.0 * merged["split_std_balacc"].fillna(0.0)
        - 40.0 * merged["noise_moderate_drop_balacc"].fillna(0.0)
        - 40.0 * merged["realism_worst_drop_balacc"].fillna(0.0)
        - 80.0 * merged["residual_critical"].fillna(0.0)
        - 20.0 * merged["suspicious_perfect_score"].astype(int)
    )
    merged["eligible_honest"] = (
        (~merged["non_promotable"])
        & (merged["residual_critical"] == 0)
        & (~merged["suspicious_perfect_score"])
        & (merged["test_balanced_accuracy"].notna())
    )
    ranking = merged.sort_values(["eligible_honest", "honest_score", "test_balanced_accuracy", "test_precision"], ascending=[False, False, False, False]).copy()
    safe_csv(ranking, paths.tables / "elimination_v5_honest_ranking.csv")
    return ranking.iloc[0]


def evaluate_two_stage_table(paths: Paths, met_df: pd.DataFrame) -> None:
    def row_for(trial_id: str) -> Optional[pd.Series]:
        m = met_df[met_df["trial_id"] == trial_id]
        return m.iloc[0] if len(m) else None

    one = row_for("V5_T07_compact_best_combined")
    two = row_for("V5_T08_two_stage_filter")
    rows: List[Dict[str, Any]] = []
    if one is not None:
        rows.append({"pipeline_type": "single_stage", "trial_id": "V5_T07_compact_best_combined", "precision": float(one["test_precision"]), "recall": float(one["test_recall"]), "specificity": float(one["test_specificity"]), "balanced_accuracy": float(one["test_balanced_accuracy"]), "f1": float(one["test_f1"]), "pr_auc": float(one["test_pr_auc"]), "noise_moderate_drop_balacc": float(one["noise_moderate_drop_balacc"]), "realism_worst_drop_balacc": float(one["realism_worst_drop_balacc"]), "interpretation": "reference_single_stage"})
    if two is not None:
        rows.append({"pipeline_type": "two_stage", "trial_id": "V5_T08_two_stage_filter", "precision": float(two["test_precision"]), "recall": float(two["test_recall"]), "specificity": float(two["test_specificity"]), "balanced_accuracy": float(two["test_balanced_accuracy"]), "f1": float(two["test_f1"]), "pr_auc": float(two["test_pr_auc"]), "noise_moderate_drop_balacc": float(two["noise_moderate_drop_balacc"]), "realism_worst_drop_balacc": float(two["realism_worst_drop_balacc"]), "interpretation": "rf_plus_transparent_specificity_filter"})
    if one is not None and two is not None:
        rows.append({"pipeline_type": "delta_two_minus_single", "trial_id": "V5_T08-V5_T07", "precision": float(two["test_precision"] - one["test_precision"]), "recall": float(two["test_recall"] - one["test_recall"]), "specificity": float(two["test_specificity"] - one["test_specificity"]), "balanced_accuracy": float(two["test_balanced_accuracy"] - one["test_balanced_accuracy"]), "f1": float(two["test_f1"] - one["test_f1"]), "pr_auc": float(two["test_pr_auc"] - one["test_pr_auc"]), "noise_moderate_drop_balacc": float(two["noise_moderate_drop_balacc"] - one["noise_moderate_drop_balacc"]), "realism_worst_drop_balacc": float(two["realism_worst_drop_balacc"] - one["realism_worst_drop_balacc"]), "interpretation": "positive_delta_specificity_with_limited_recall_loss_is_desired"})

    out = pd.DataFrame(rows)
    safe_csv(out, paths.tables / "elimination_v5_two_stage_results.csv")
    if one is not None and two is not None:
        safe_text(
            "# Elimination v5 Two-Stage Analysis\n\n"
            f"- single_stage_trial: V5_T07_compact_best_combined precision={float(one['test_precision']):.4f} recall={float(one['test_recall']):.4f} specificity={float(one['test_specificity']):.4f}\n"
            f"- two_stage_trial: V5_T08_two_stage_filter precision={float(two['test_precision']):.4f} recall={float(two['test_recall']):.4f} specificity={float(two['test_specificity']):.4f}\n"
            f"- delta_precision: {float(two['test_precision'] - one['test_precision']):.4f}\n"
            f"- delta_recall: {float(two['test_recall'] - one['test_recall']):.4f}\n"
            f"- delta_specificity: {float(two['test_specificity'] - one['test_specificity']):.4f}\n"
            "- interpretation: two-stage accepted only if specificity gain is real and recall loss remains moderate.\n",
            paths.reports / "elimination_v5_two_stage_analysis.md",
        )
    else:
        safe_text("# Elimination v5 Two-Stage Analysis\n\n- Required one-stage or two-stage trial row is missing; comparison not available.\n", paths.reports / "elimination_v5_two_stage_analysis.md")


def evaluate_abstention_v5(paths: Paths, best_trial: pd.Series, trial_outputs: Dict[str, Dict[str, Any]], v2_rank: pd.DataFrame, v3_abst: pd.DataFrame) -> pd.DataFrame:
    trial_id = str(best_trial["trial_id"])
    out = trial_outputs[trial_id]
    fit = out["fit"]
    rows: List[Dict[str, Any]] = []
    rows.append({"version": "v5", "mode": "binary_default", "trial_id": trial_id, "coverage": 1.0, "precision_high_confidence_positive": float(best_trial["test_precision"]), "effective_recall": float(best_trial["test_recall"]), "uncertain_pct": 0.0, "low_threshold": np.nan, "high_threshold": np.nan, "thesis_utility": "baseline", "product_utility": "not_product_ready"})

    if fit["ok"] and len(fit["y_val"]) and len(fit["y_test"]):
        low, high = v3.select_abstention_band(fit["y_val"], fit["p_val"])
        m = v3.abstention_metrics(fit["y_test"], fit["p_test"], low, high)
        rows.append({"version": "v5", "mode": "abstention_assisted", "trial_id": trial_id, "coverage": float(m["coverage"]), "precision_high_confidence_positive": float(m["precision_high_confidence_positive"]), "effective_recall": float(m["effective_recall"]), "uncertain_pct": float(m["uncertain_pct"]), "low_threshold": float(m["low_threshold"]), "high_threshold": float(m["high_threshold"]), "thesis_utility": "high_if_disclaimer_present", "product_utility": "experimental_only"})
    else:
        rows.append({"version": "v5", "mode": "abstention_assisted", "trial_id": trial_id, "coverage": np.nan, "precision_high_confidence_positive": np.nan, "effective_recall": np.nan, "uncertain_pct": np.nan, "low_threshold": np.nan, "high_threshold": np.nan, "thesis_utility": "not_computable", "product_utility": "not_applicable"})

    v3_ref = v3_abst[v3_abst["mode"] == "abstention_assisted"].head(1)
    if len(v3_ref):
        r = v3_ref.iloc[0]
        rows.append({"version": "v3_reference", "mode": "abstention_assisted", "trial_id": str(r.get("trial_id", "v3_reference")), "coverage": float(r.get("coverage", np.nan)), "precision_high_confidence_positive": float(r.get("precision", np.nan)), "effective_recall": float(r.get("effective_recall", np.nan)), "uncertain_pct": float(r.get("uncertain_pct", np.nan)), "low_threshold": np.nan, "high_threshold": np.nan, "thesis_utility": str(r.get("thesis_utility", "reference")), "product_utility": str(r.get("product_utility", "reference"))})

    if len(v2_rank):
        r2 = v2_rank.iloc[0]
        rows.append({"version": "v2_reference", "mode": "binary_default", "trial_id": str(r2.get("trial_id", "v2_reference")), "coverage": 1.0, "precision_high_confidence_positive": float(r2.get("test_precision", np.nan)), "effective_recall": float(r2.get("test_recall", np.nan)), "uncertain_pct": 0.0, "low_threshold": np.nan, "high_threshold": np.nan, "thesis_utility": "reference", "product_utility": "not_product_ready"})

    abst = pd.DataFrame(rows)
    safe_csv(abst, paths.tables / "elimination_v5_abstention_results.csv")
    v5_bin = abst[(abst["version"] == "v5") & (abst["mode"] == "binary_default")].iloc[0]
    v5_abs = abst[(abst["version"] == "v5") & (abst["mode"] == "abstention_assisted")].iloc[0]
    safe_text(
        "# Elimination v5 Abstention Analysis\n\n"
        f"- selected_trial: {trial_id}\n"
        f"- v5_binary_precision: {float(v5_bin['precision_high_confidence_positive']):.4f}\n"
        f"- v5_abstention_precision: {float(v5_abs['precision_high_confidence_positive']):.4f}\n"
        f"- v5_abstention_coverage: {float(v5_abs['coverage']):.4f}\n"
        f"- v5_uncertain_pct: {float(v5_abs['uncertain_pct']):.4f}\n"
        "- interpretation: abstention is treated as operational complement and does not replace primary binary output.\n",
        paths.reports / "elimination_v5_abstention_analysis.md",
    )
    return abst


def read_selected_trial_from_report(report_path: Path) -> Optional[str]:
    if not report_path.exists():
        return None
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"selected_trial:\s*([A-Za-z0-9_\\-]+)", text)
    return m.group(1).strip() if m else None


def classify_stability(seed_std: float, split_std: float) -> str:
    if np.isnan(seed_std) or np.isnan(split_std):
        return "unknown"
    if seed_std <= 0.015 and split_std <= 0.020:
        return "good"
    if seed_std <= 0.030 and split_std <= 0.040:
        return "moderate"
    return "weak"


def classify_realism_robustness(drop_value: float) -> str:
    if np.isnan(drop_value):
        return "unknown"
    if drop_value <= 0.02:
        return "good"
    if drop_value <= 0.06:
        return "moderate"
    return "weak"


def compare_v2_v3_v4_v5(paths: Paths, best_v5: pd.Series, abst_v5: pd.DataFrame, v2_rank: pd.DataFrame, v3_rank: pd.DataFrame) -> pd.DataFrame:
    v4_metrics_path = paths.v4 / "trials" / "elimination_target_redesign_metrics_full.csv"
    v4_metrics = pd.read_csv(v4_metrics_path) if v4_metrics_path.exists() else pd.DataFrame()
    v4_selected = read_selected_trial_from_report(paths.v4 / "reports" / "elimination_final_decision_v4.md")
    if len(v4_metrics):
        if v4_selected and v4_selected in set(v4_metrics["trial_id"].astype(str)):
            v4_row = v4_metrics[v4_metrics["trial_id"].astype(str) == v4_selected].iloc[0]
        else:
            nsp = v4_metrics[(v4_metrics["residual_critical"] == 0) & (~v4_metrics["suspicious_perfect_score"])]
            v4_row = (nsp if len(nsp) else v4_metrics).sort_values(["test_balanced_accuracy", "test_precision"], ascending=False).iloc[0]
    else:
        v4_row = pd.Series(dtype=float)

    v2_row = v2_rank.iloc[0] if len(v2_rank) else pd.Series(dtype=float)
    v3_row = v3_rank.iloc[0] if len(v3_rank) else pd.Series(dtype=float)
    v5_abst_row = abst_v5[(abst_v5["version"] == "v5") & (abst_v5["mode"] == "abstention_assisted")].head(1)
    v5_abst_prec = float(v5_abst_row.iloc[0]["precision_high_confidence_positive"]) if len(v5_abst_row) else np.nan

    rows = [
        {"generation": "v2", "trial_id": str(v2_row.get("trial_id", "na")), "precision": float(v2_row.get("test_precision", np.nan)), "balanced_accuracy": float(v2_row.get("test_balanced_accuracy", np.nan)), "recall": float(v2_row.get("test_recall", np.nan)), "specificity": float(v2_row.get("test_specificity", np.nan)), "f1": float(v2_row.get("test_f1", np.nan)), "pr_auc": float(v2_row.get("test_pr_auc", np.nan)), "suspicious_perfect_score": bool(v2_row.get("suspicious_perfect_score", False)), "leakage_risk": "high" if bool(v2_row.get("has_critical_leakage", False)) else "low", "stability": classify_stability(float(v2_row.get("seed_std_balacc", np.nan)), float(v2_row.get("split_std_balacc", np.nan))), "realism_shift_robustness": classify_realism_robustness(float(v2_row.get("realism_worst_drop_balacc", np.nan))), "operational_utility": "moderate", "thesis_utility": "high", "product_utility": "no", "improvement_type": "structural_baseline"},
        {"generation": "v3", "trial_id": str(v3_row.get("trial_id", "na")), "precision": float(v3_row.get("test_precision", np.nan)), "balanced_accuracy": float(v3_row.get("test_balanced_accuracy", np.nan)), "recall": float(v3_row.get("test_recall", np.nan)), "specificity": float(v3_row.get("test_specificity", np.nan)), "f1": float(v3_row.get("test_f1", np.nan)), "pr_auc": float(v3_row.get("test_pr_auc", np.nan)), "suspicious_perfect_score": bool(v3_row.get("suspicious_perfect_score", False)), "leakage_risk": "low", "stability": classify_stability(float(v3_row.get("seed_std_balacc", np.nan)), float(v3_row.get("split_std_balacc", np.nan))), "realism_shift_robustness": classify_realism_robustness(float(v3_row.get("realism_worst_drop_balacc", np.nan))), "operational_utility": "high_abstention", "thesis_utility": "high", "product_utility": "no", "improvement_type": "operational"},
        {"generation": "v4", "trial_id": str(v4_row.get("trial_id", "na")), "precision": float(v4_row.get("test_precision", np.nan)), "balanced_accuracy": float(v4_row.get("test_balanced_accuracy", np.nan)), "recall": float(v4_row.get("test_recall", np.nan)), "specificity": float(v4_row.get("test_specificity", np.nan)), "f1": float(v4_row.get("test_f1", np.nan)), "pr_auc": float(v4_row.get("test_pr_auc", np.nan)), "suspicious_perfect_score": bool(v4_row.get("suspicious_perfect_score", False)), "leakage_risk": "high" if int(v4_row.get("residual_critical", 0)) > 0 else "low", "stability": classify_stability(float(v4_row.get("seed_std_balacc", np.nan)), float(v4_row.get("split_std_balacc", np.nan))), "realism_shift_robustness": classify_realism_robustness(float(v4_row.get("realism_worst_drop_balacc", np.nan))), "operational_utility": "diagnostic_analytic", "thesis_utility": "high", "product_utility": "no", "improvement_type": "diagnostic_analytic"},
        {"generation": "v5", "trial_id": str(best_v5.get("trial_id", "na")), "precision": float(best_v5.get("test_precision", np.nan)), "balanced_accuracy": float(best_v5.get("test_balanced_accuracy", np.nan)), "recall": float(best_v5.get("test_recall", np.nan)), "specificity": float(best_v5.get("test_specificity", np.nan)), "f1": float(best_v5.get("test_f1", np.nan)), "pr_auc": float(best_v5.get("test_pr_auc", np.nan)), "suspicious_perfect_score": bool(best_v5.get("suspicious_perfect_score", False)), "leakage_risk": str(best_v5.get("leakage_class", "unknown")), "stability": classify_stability(float(best_v5.get("seed_std_balacc", np.nan)), float(best_v5.get("split_std_balacc", np.nan))), "realism_shift_robustness": classify_realism_robustness(float(best_v5.get("realism_worst_drop_balacc", np.nan))), "operational_utility": "high_if_abstention" if np.isfinite(v5_abst_prec) and v5_abst_prec > float(best_v5.get("test_precision", 0.0)) else "moderate", "thesis_utility": "high", "product_utility": "no", "improvement_type": "pending"},
    ]
    comp = pd.DataFrame(rows)
    v2_prec = float(comp.loc[comp["generation"] == "v2", "precision"].iloc[0])
    v2_bal = float(comp.loc[comp["generation"] == "v2", "balanced_accuracy"].iloc[0])
    v3_abs = abst_v5[(abst_v5["version"] == "v3_reference") & (abst_v5["mode"] == "abstention_assisted")]
    v3_abs_prec = float(v3_abs.iloc[0]["precision_high_confidence_positive"]) if len(v3_abs) else np.nan
    v5_prec = float(comp.loc[comp["generation"] == "v5", "precision"].iloc[0])
    v5_bal = float(comp.loc[comp["generation"] == "v5", "balanced_accuracy"].iloc[0])

    improvement_type = "no_improvement"
    if (v5_bal >= v2_bal + 0.01) and (v5_prec >= v2_prec + 0.005):
        improvement_type = "structural"
    elif np.isfinite(v3_abs_prec) and np.isfinite(v5_abst_prec) and (v5_abst_prec >= v3_abs_prec + 0.01):
        improvement_type = "operational"
    elif np.isfinite(v5_bal) and np.isfinite(v2_bal) and abs(v5_bal - v2_bal) <= 0.01:
        improvement_type = "marginal"
    comp.loc[comp["generation"] == "v5", "improvement_type"] = improvement_type

    safe_csv(comp, paths.tables / "elimination_v2_v3_v4_v5_comparison.csv")
    safe_text(
        "# Elimination v2 vs v3 vs v4 vs v5 Comparison\n\n"
        f"- v5_selected_trial: {str(best_v5.get('trial_id', 'na'))}\n"
        f"- v5_improvement_type: {improvement_type}\n"
        f"- v5_precision: {v5_prec:.4f}\n"
        f"- v5_balanced_accuracy: {v5_bal:.4f}\n"
        f"- v2_precision: {v2_prec:.4f}\n"
        f"- v2_balanced_accuracy: {v2_bal:.4f}\n"
        "- subtype-aware split remains auxiliary: useful analytically, not standalone promotion path.\n",
        paths.reports / "elimination_v2_v3_v4_v5_comparison.md",
    )
    return comp


def final_decision_reports(paths: Paths, best_v5: pd.Series, comp: pd.DataFrame, abst_v5: pd.DataFrame) -> None:
    v2 = comp[comp["generation"] == "v2"].iloc[0]
    v5 = comp[comp["generation"] == "v5"].iloc[0]
    v5_type = str(v5["improvement_type"])
    v5_abst = abst_v5[(abst_v5["version"] == "v5") & (abst_v5["mode"] == "abstention_assisted")]
    v3_abst = abst_v5[(abst_v5["version"] == "v3_reference") & (abst_v5["mode"] == "abstention_assisted")]
    v5_abst_prec = float(v5_abst.iloc[0]["precision_high_confidence_positive"]) if len(v5_abst) else np.nan
    v3_abst_prec = float(v3_abst.iloc[0]["precision_high_confidence_positive"]) if len(v3_abst) else np.nan
    delta_bal_v2 = float(v5["balanced_accuracy"] - v2["balanced_accuracy"])
    delta_prec_v2 = float(v5["precision"] - v2["precision"])
    delta_abst_v3 = float(v5_abst_prec - v3_abst_prec) if np.isfinite(v5_abst_prec) and np.isfinite(v3_abst_prec) else np.nan
    suspicious = bool(best_v5.get("suspicious_perfect_score", False))
    leakage_high = str(best_v5.get("leakage_class", "unknown")) in {"high", "critical"}
    near_ceiling = abs(delta_bal_v2) <= 0.01 and abs(delta_prec_v2) <= 0.02

    if not suspicious and not leakage_high and (v5_type == "structural"):
        decision = "v5_achieves_real_structural_improvement_over_v2"
        global_status = "experimental_line_more_useful_not_product_ready"
        stop_assessment = "yes_hubo_mejora_incremental_real_y_defendible"
    elif not suspicious and not leakage_high and (v5_type == "operational"):
        decision = "v5_achieves_operational_gain_over_v3"
        global_status = "experimental_line_more_useful_not_product_ready"
        stop_assessment = "yes_hubo_mejora_incremental_real_y_defendible"
    elif not suspicious and not leakage_high and near_ceiling:
        decision = "v5_changes_are_minor_and_status_stays_near_ceiling"
        global_status = "recovered_but_experimental_high_caution_near_ceiling"
        stop_assessment = "hubo_cambios_menores_no_suficientes_para_cambiar_estatus"
    else:
        decision = "v5_confirms_reasonable_ceiling_with_current_HBN_DSM5"
        global_status = "recovered_but_experimental_high_caution_near_ceiling"
        stop_assessment = "no_hubo_mejora_relevante_y_esta_cerca_del_techo"

    safe_text(
        "# Elimination Final Decision v5\n\n"
        f"- selected_trial: {str(best_v5.get('trial_id', 'na'))}\n"
        f"- final_status: {global_status}\n"
        f"- decision_class: {decision}\n"
        f"- delta_balanced_accuracy_vs_v2: {delta_bal_v2:.4f}\n"
        f"- delta_precision_vs_v2: {delta_prec_v2:.4f}\n"
        f"- delta_abstention_precision_vs_v3: {delta_abst_v3:.4f}\n"
        f"- suspicious_perfect_score: {suspicious}\n"
        f"- leakage_risk_class: {str(best_v5.get('leakage_class', 'unknown'))}\n"
        "- product_ready: no\n",
        paths.reports / "elimination_final_decision_v5.md",
    )
    safe_text(
        "# Elimination Thesis Positioning v5\n\n"
        f"- status_for_thesis: includable_as_{global_status}\n"
        "- caveat_1: simulated environment only, not clinical diagnosis.\n"
        "- caveat_2: no direct elimination instrument available in HBN-derived scope.\n"
        "- caveat_3: target ambiguity and transdiagnostic overlap remain active constraints.\n",
        paths.reports / "elimination_thesis_positioning_v5.md",
    )
    safe_text(
        "# Elimination Product Positioning v5\n\n"
        "- product_ready: no\n"
        "- recommendation: keep elimination as experimental output with explicit uncertainty and optional abstention mode.\n"
        "- promotion_rule: do not promote while domain remains high-caution near-ceiling without stronger robustness evidence.\n",
        paths.reports / "elimination_product_positioning_v5.md",
    )
    safe_text(
        "# Elimination Stop Rule Assessment v5\n\n"
        f"- stop_assessment: {stop_assessment}\n"
        f"- v5_improvement_type: {v5_type}\n"
        f"- near_ceiling_flag: {near_ceiling}\n"
        "- criterion: stop iterative work when gains are marginal and major bottlenecks remain representation/coverage constraints.\n",
        paths.reports / "elimination_stop_rule_assessment_v5.md",
    )
    safe_text(
        "# Elimination Executive Summary v5\n\n"
        f"- selected_trial: {str(best_v5.get('trial_id', 'na'))}\n"
        f"- final_status: {global_status}\n"
        f"- decision: {decision}\n"
        f"- test_precision: {float(best_v5.get('test_precision', np.nan)):.4f}\n"
        f"- test_balanced_accuracy: {float(best_v5.get('test_balanced_accuracy', np.nan)):.4f}\n"
        f"- test_recall: {float(best_v5.get('test_recall', np.nan)):.4f}\n"
        f"- test_specificity: {float(best_v5.get('test_specificity', np.nan)):.4f}\n"
        f"- abstention_precision: {v5_abst_prec:.4f}\n"
        "- key_takeaway: v5 focuses on representation gains; status remains experimental and non-product.\n",
        paths.reports / "elimination_executive_summary_v5.md",
    )


def summarize_family_uplift(met_df: pd.DataFrame) -> pd.DataFrame:
    control = met_df[met_df["trial_id"] == "V5_T01_control_replay_v2_best"]
    if len(control) == 0:
        return pd.DataFrame()
    c = control.iloc[0]
    rows: List[Dict[str, Any]] = []
    mapping = {
        "composite_clinical": "V5_T02_composite_clinical",
        "anti_transdiagnostic": "V5_T03_anti_transdiagnostic",
        "evidence_quality": "V5_T04_evidence_quality_meta",
        "subtype_auxiliary": "V5_T05_subtype_auxiliary",
        "hard_negative": "V5_T06_hard_negative_engineering",
        "combined": "V5_T07_compact_best_combined",
        "two_stage": "V5_T08_two_stage_filter",
        "abstention_ready_refit": "V5_T09_abstention_ready_refit",
    }
    for fam, tid in mapping.items():
        m = met_df[met_df["trial_id"] == tid]
        if len(m) == 0:
            continue
        r = m.iloc[0]
        rows.append(
            {
                "family_or_strategy": fam,
                "trial_id": tid,
                "delta_precision_vs_control": float(r["test_precision"] - c["test_precision"]),
                "delta_balacc_vs_control": float(r["test_balanced_accuracy"] - c["test_balanced_accuracy"]),
                "delta_recall_vs_control": float(r["test_recall"] - c["test_recall"]),
                "delta_specificity_vs_control": float(r["test_specificity"] - c["test_specificity"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["delta_balacc_vs_control", "delta_precision_vs_control"], ascending=False)


def run() -> None:
    parser = argparse.ArgumentParser(description="Elimination feature engineering v5 (causal, bounded, strict-no-leakage centered).")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)

    paths = build_paths(Path(args.root).resolve())
    ensure_dirs(paths)

    data = load_inputs(paths)
    create_input_inventory(paths, data)
    strict = data["strict"]
    research = data["research"]
    semantic = data["semantic"]
    risk_map = build_risk_map(semantic)

    run_feature_audit(paths, strict)
    strict_v5, research_v5, family_map = run_feature_generation(paths, strict, research)
    feature_sets = build_feature_sets(paths, strict_v5, risk_map, family_map)
    reg_df, met_df, trial_outputs = run_trials(paths, strict_v5, research_v5, feature_sets, family_map, risk_map)

    family_uplift = summarize_family_uplift(met_df)
    safe_csv(family_uplift, paths.tables / "elimination_v5_family_uplift_summary.csv")

    best_v5 = select_best_honest(reg_df, met_df, paths)
    evaluate_two_stage_table(paths, met_df)

    v2_rank = pd.read_csv(paths.v2 / "tables" / "elimination_honest_model_ranking.csv")
    v3_rank = pd.read_csv(paths.v3 / "tables" / "elimination_refinement_honest_ranking.csv")
    v3_abst = pd.read_csv(paths.v3 / "tables" / "elimination_abstention_policy_results.csv")
    abst_v5 = evaluate_abstention_v5(paths, best_v5, trial_outputs, v2_rank, v3_abst)
    comp = compare_v2_v3_v4_v5(paths, best_v5, abst_v5, v2_rank, v3_rank)
    final_decision_reports(paths, best_v5, comp, abst_v5)

    safe_json(
        {
            "generated_at_utc": now_iso(),
            "selected_trial_v5": str(best_v5.get("trial_id", "na")),
            "selected_trial_metrics": {
                "test_precision": float(best_v5.get("test_precision", np.nan)),
                "test_balanced_accuracy": float(best_v5.get("test_balanced_accuracy", np.nan)),
                "test_recall": float(best_v5.get("test_recall", np.nan)),
                "test_specificity": float(best_v5.get("test_specificity", np.nan)),
                "test_pr_auc": float(best_v5.get("test_pr_auc", np.nan)),
            },
            "status": "completed",
            "notes": "No previous line was overwritten; all outputs are in elimination_feature_engineering_v5.",
        },
        paths.artifacts / "run_manifest.json",
    )

    LOGGER.info("Elimination feature engineering v5 completed.")


if __name__ == "__main__":
    run()
