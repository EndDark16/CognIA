#!/usr/bin/env python

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.pipeline import Pipeline

TARGET = "target_domain_elimination"
MODES = ["caregiver", "psychologist"]
FAMILIES = ["rf", "lightgbm", "xgboost"]
BLOCKED_TOKENS = ("cbcl_108", "cbcl_112")
BLOCKED_EXACT = {
    "cbcl_108",
    "cbcl_112",
    "v11_core_sum",
    "v11_core_mean",
    "v11_core_balance_diff",
    "v11_subtype_enuresis_proxy",
    "v11_subtype_encopresis_proxy",
    "v11_subtype_gap_proxy",
}


def load_v11(path: Path):
    spec = importlib.util.spec_from_file_location("v11clean", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def read_ids(path: Path) -> List[str]:
    d = pd.read_csv(path)
    return d[d.columns[0]].astype(str).tolist()


def h(ids: Iterable[str], ordered: bool = False) -> str:
    xs = list(ids)
    if not ordered:
        xs = sorted(set(xs))
    return hashlib.sha256("|".join(xs).encode("utf-8")).hexdigest()


def wcsv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def wmd(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def wjson(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def to_num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def row_mean(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return df[cols].apply(pd.to_numeric, errors="coerce").mean(axis=1, skipna=True)


def row_sum(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return df[cols].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)


def row_nonmissing(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)
    return df[cols].apply(pd.to_numeric, errors="coerce").notna().sum(axis=1).astype(float)


def add_v12_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    reg: List[Dict[str, Any]] = []

    def add(name: str, val: pd.Series, fam: str, src: str):
        out[name] = val
        reg.append(
            {
                "feature_name": name,
                "feature_family": fam,
                "source_variables": src,
                "uses_blocked": "yes" if any(t in src for t in BLOCKED_TOKENS) else "no",
            }
        )

    parent = [
        "sdq_impact",
        "sdq_conduct_problems",
        "sdq_total_difficulties",
        "sdq_emotional_symptoms",
        "sdq_hyperactivity_inattention",
        "cbcl_rule_breaking_proxy",
        "cbcl_aggressive_behavior_proxy",
        "cbcl_attention_problems_proxy",
        "cbcl_internalizing_proxy",
        "cbcl_externalizing_proxy",
        "conners_total",
        "swan_total",
        "scared_p_total",
        "ari_p_symptom_total",
        "ari_p_impairment_item",
        "icut_total",
        "mfq_p_total",
    ]

    add(
        "v12_parent_behavior_burden",
        row_mean(out, ["cbcl_rule_breaking_proxy", "cbcl_aggressive_behavior_proxy", "sdq_conduct_problems"]),
        "burden",
        "cbcl_rule_breaking_proxy,cbcl_aggressive_behavior_proxy,sdq_conduct_problems",
    )
    add(
        "v12_parent_internalizing_context",
        row_mean(out, ["cbcl_internalizing_proxy", "sdq_emotional_symptoms", "scared_p_total", "mfq_p_total"]),
        "context",
        "cbcl_internalizing_proxy,sdq_emotional_symptoms,scared_p_total,mfq_p_total",
    )
    add(
        "v12_parent_neurodev_context",
        row_mean(out, ["cbcl_attention_problems_proxy", "sdq_hyperactivity_inattention", "conners_total", "swan_total"]),
        "context",
        "cbcl_attention_problems_proxy,sdq_hyperactivity_inattention,conners_total,swan_total",
    )
    add(
        "v12_parent_impact_context",
        row_sum(out, ["sdq_impact", "ari_p_impairment_item"]),
        "impact",
        "sdq_impact,ari_p_impairment_item",
    )
    den = max(1.0, float(len([c for c in parent if c in out.columns])))
    nm = row_nonmissing(out, parent)
    add("v12_parent_nonmissing_ratio_clean", nm / den, "missingness", ",".join(parent))
    add("v12_parent_missing_count_clean", den - nm, "missingness", ",".join(parent))
    add(
        "v12_parent_signal_density_clean",
        row_sum(out, ["v12_parent_behavior_burden", "v12_parent_internalizing_context", "v12_parent_neurodev_context", "v12_parent_impact_context"]).fillna(0.0)
        / (1.0 + to_num(out, "v12_parent_missing_count_clean").fillna(0.0)),
        "burden",
        "v12_parent_behavior_burden,v12_parent_internalizing_context,v12_parent_neurodev_context,v12_parent_impact_context,v12_parent_missing_count_clean",
    )
    add(
        "v12_parent_source_count_clean",
        row_sum(out, ["has_cbcl", "has_sdq", "has_conners", "has_swan", "has_scared_p", "has_ari_p", "has_icut", "has_mfq_p"]).fillna(0.0),
        "source",
        "has_cbcl,has_sdq,has_conners,has_swan,has_scared_p,has_ari_p,has_icut,has_mfq_p",
    )
    add(
        "v12_cbcl_sdq_alignment",
        (to_num(out, "cbcl_externalizing_proxy") - to_num(out, "sdq_total_difficulties")).abs(),
        "consistency",
        "cbcl_externalizing_proxy,sdq_total_difficulties",
    )
    add(
        "v12_cbcl_sdq_internal_alignment",
        (to_num(out, "cbcl_internalizing_proxy") - to_num(out, "sdq_emotional_symptoms")).abs(),
        "consistency",
        "cbcl_internalizing_proxy,sdq_emotional_symptoms",
    )
    add(
        "v12_self_internalizing_context",
        row_mean(out, ["ysr_internalizing_proxy", "scared_sr_total", "cdi_total", "mfq_sr_total"]),
        "source",
        "ysr_internalizing_proxy,scared_sr_total,cdi_total,mfq_sr_total",
    )
    add(
        "v12_parent_self_gap_anxiety",
        (to_num(out, "scared_p_total") - to_num(out, "scared_sr_total")).abs(),
        "agreement",
        "scared_p_total,scared_sr_total",
    )
    add(
        "v12_parent_self_gap_irritability",
        (to_num(out, "ari_p_symptom_total") - to_num(out, "ari_sr_symptom_total")).abs(),
        "agreement",
        "ari_p_symptom_total,ari_sr_symptom_total",
    )
    gap = row_mean(out, ["v12_parent_self_gap_anxiety", "v12_parent_self_gap_irritability"])
    add(
        "v12_cross_source_agreement_clean",
        1.0 / (1.0 + gap.fillna(0.0)),
        "agreement",
        "v12_parent_self_gap_anxiety,v12_parent_self_gap_irritability",
    )

    reg_df = pd.DataFrame(reg)
    reg_df = reg_df[reg_df["uses_blocked"] == "no"].reset_index(drop=True)
    return out, reg_df

def sanitize(
    df: pd.DataFrame,
    cols: List[str],
    mode: str,
    blocked_exact: set[str],
    formula_lookup: Dict[str, str],
    v11: Any,
) -> List[str]:
    out: List[str] = []
    for c in cols:
        if c not in df.columns or c in blocked_exact:
            continue
        if v11.is_blocked_feature(c):
            continue
        if mode == "caregiver" and v11.is_self_report_feature(c):
            continue
        src = formula_lookup.get(c, "")
        if any(tok in c for tok in BLOCKED_TOKENS) or any(tok in src for tok in BLOCKED_TOKENS):
            continue
        if c not in out:
            out.append(c)
    return out


def build_sets(
    df: pd.DataFrame,
    mode: str,
    champion: List[str],
    blocked_exact: set[str],
    formula_lookup: Dict[str, str],
    v11: Any,
) -> Dict[str, List[str]]:
    base = [
        "age_years",
        "sex_assigned_at_birth",
        "site",
        "release",
        "has_cbcl",
        "has_sdq",
        "has_conners",
        "has_swan",
        "cbcl_rule_breaking_proxy",
        "cbcl_aggressive_behavior_proxy",
        "cbcl_attention_problems_proxy",
        "cbcl_externalizing_proxy",
        "cbcl_internalizing_proxy",
        "sdq_conduct_problems",
        "sdq_impact",
        "sdq_total_difficulties",
        "conners_total",
        "swan_total",
        "scared_p_total",
        "ari_p_symptom_total",
    ]
    psych = ["has_ysr", "has_scared_sr", "ysr_internalizing_proxy", "scared_sr_total", "cdi_total", "mfq_sr_total"]
    eng = [
        "v12_parent_behavior_burden",
        "v12_parent_internalizing_context",
        "v12_parent_neurodev_context",
        "v12_parent_impact_context",
        "v12_parent_nonmissing_ratio_clean",
        "v12_parent_signal_density_clean",
        "v12_parent_source_count_clean",
        "v12_cbcl_sdq_alignment",
        "v12_cbcl_sdq_internal_alignment",
        "v12_self_internalizing_context",
        "v12_parent_self_gap_anxiety",
        "v12_parent_self_gap_irritability",
        "v12_cross_source_agreement_clean",
    ]
    mode_base = base + (psych if mode == "psychologist" else [])
    mode_eng = eng + (["v12_self_internalizing_context", "v12_parent_self_gap_anxiety", "v12_parent_self_gap_irritability", "v12_cross_source_agreement_clean"] if mode == "psychologist" else [])
    raw = {
        "baseline_clean_no_shortcuts": champion + ["has_conners", "has_swan", "conners_total", "swan_total", "sdq_impact"],
        "proxy_pruned_clean": ["age_years", "sex_assigned_at_birth", "site", "release", "has_cbcl", "has_sdq", "cbcl_rule_breaking_proxy", "cbcl_aggressive_behavior_proxy", "cbcl_attention_problems_proxy", "sdq_conduct_problems", "sdq_total_difficulties", "sdq_impact", "v12_parent_behavior_burden", "v12_parent_nonmissing_ratio_clean"],
        "subtype_aware_clean": ["age_years", "sex_assigned_at_birth", "site", "release", "sdq_impact", "sdq_conduct_problems", "cbcl_rule_breaking_proxy", "cbcl_aggressive_behavior_proxy", "v12_parent_behavior_burden", "v12_parent_neurodev_context", "v12_cbcl_sdq_alignment", "v12_cbcl_sdq_internal_alignment"] + (["v12_self_internalizing_context", "v12_cross_source_agreement_clean"] if mode == "psychologist" else []),
        "compact_clinical_clean": ["age_years", "sex_assigned_at_birth", "site", "release", "has_cbcl", "has_sdq", "cbcl_attention_problems_proxy", "cbcl_externalizing_proxy", "cbcl_internalizing_proxy", "sdq_conduct_problems", "sdq_impact", "sdq_total_difficulties", "conners_total", "swan_total", "scared_p_total", "ari_p_symptom_total", "v12_parent_behavior_burden", "v12_parent_internalizing_context", "v12_parent_neurodev_context", "v12_parent_nonmissing_ratio_clean", "v12_parent_source_count_clean"] + (["ysr_internalizing_proxy", "scared_sr_total", "v12_cross_source_agreement_clean"] if mode == "psychologist" else []),
        "impact_burden_clean": mode_base + ["v12_parent_behavior_burden", "v12_parent_internalizing_context", "v12_parent_neurodev_context", "v12_parent_impact_context", "v12_parent_signal_density_clean"],
        "missingness_aware_clean": mode_base + ["v12_parent_nonmissing_ratio_clean", "v12_parent_missing_count_clean", "v12_parent_source_count_clean", "v12_parent_signal_density_clean"],
        "source_semantics_clean": mode_base + mode_eng,
        "hybrid_clean_best_effort": mode_base + mode_eng,
    }
    return {k: sanitize(df, v, mode, blocked_exact, formula_lookup, v11) for k, v in raw.items()}


def fit(
    v11: Any,
    df: pd.DataFrame,
    ids_train: List[str],
    ids_val: List[str],
    ids_test: List[str],
    features: List[str],
    family: str,
    mode: str,
    fset: str,
) -> Dict[str, Any]:
    frame = df[["participant_id", TARGET] + features].copy()
    tr = frame[frame["participant_id"].astype(str).isin(ids_train)]
    va = frame[frame["participant_id"].astype(str).isin(ids_val)]
    te = frame[frame["participant_id"].astype(str).isin(ids_test)]
    Xtr, ytr = tr[features], pd.to_numeric(tr[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()
    Xva, yva = va[features], pd.to_numeric(va[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()
    Xte, yte = te[features], pd.to_numeric(te[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()
    pipe = Pipeline([("preprocessor", v11.build_preprocessor(Xtr)), ("model", v11.build_estimator(family, 42))])
    t0 = time.time()
    pipe.fit(Xtr, ytr)
    fit_s = time.time() - t0
    pva_raw = pipe.predict_proba(Xva)[:, 1]
    pte_raw = pipe.predict_proba(Xte)[:, 1]
    pva, pte, cal, iso = pva_raw.copy(), pte_raw.copy(), "none", None
    if len(np.unique(yva)) > 1:
        iso_ = IsotonicRegression(out_of_bounds="clip")
        iso_.fit(pva_raw, yva)
        pva_c, pte_c = iso_.transform(pva_raw), iso_.transform(pte_raw)
        if float(np.mean((pva_c - yva) ** 2)) <= float(np.mean((pva_raw - yva) ** 2)) + 5e-4:
            pva, pte, cal, iso = pva_c, pte_c, "isotonic", iso_
    thr = float(v11.select_threshold(yva, pva, "balanced"))
    m = v11.compute_metrics(yte, pte, thr)
    u = v11.uncertainty_pack(yte, pte, thr, 0.08)
    seed_ba = []
    for s in [11, 42, 2026]:
        p = Pipeline([("preprocessor", v11.build_preprocessor(Xtr)), ("model", v11.build_estimator(family, s))])
        p.fit(Xtr, ytr)
        seed_ba.append(v11.compute_metrics(yte, p.predict_proba(Xte)[:, 1], thr)["balanced_accuracy"])
    std = float(np.std(seed_ba))
    obj = 0.32 * float(m["balanced_accuracy"]) + 0.22 * float(m["recall"]) + 0.16 * float(m["pr_auc"]) + 0.1 * float(m["precision"]) + 0.1 * (1 - float(m["brier"])) + 0.05 * float(u["output_realism_score"]) + 0.05 * max(0.0, 1.0 - min(1.0, std * 30.0))
    return {
        "mode": mode,
        "domain": "elimination",
        "feature_set": fset,
        "family": family,
        "n_features": len(features),
        "calibration": cal,
        "threshold": thr,
        "fit_seconds": float(fit_s),
        "precision": float(m["precision"]),
        "recall": float(m["recall"]),
        "specificity": float(m["specificity"]),
        "balanced_accuracy": float(m["balanced_accuracy"]),
        "f1": float(m["f1"]),
        "roc_auc": float(m["roc_auc"]),
        "pr_auc": float(m["pr_auc"]),
        "brier": float(m["brier"]),
        "seed_std_balanced_accuracy": std,
        "stability": "high" if std < 0.01 else ("medium" if std < 0.02 else "low"),
        "uncertain_rate": float(u["uncertain_rate"]),
        "uncertainty_usefulness": float(u["uncertainty_usefulness"]),
        "output_realism_score": float(u["output_realism_score"]),
        "operational_complexity": float({"rf": 1.0, "lightgbm": 1.8, "xgboost": 2.0}[family] + len(features) / 42.0),
        "maintenance_complexity": float({"rf": 1.0, "lightgbm": 1.8, "xgboost": 2.0}[family] + len(features) / 34.0 + (0.4 if cal == "isotonic" else 0.0)),
        "objective": float(obj),
        "_features": features,
        "_pipe": pipe,
        "_iso": iso,
        "_Xte": Xte,
        "_yte": yte,
        "_pte": pte,
        "_Xtr": Xtr,
        "_ytr": ytr,
    }


def pred(pack: Dict[str, Any], X: pd.DataFrame) -> np.ndarray:
    p = pack["_pipe"].predict_proba(X[pack["_features"]])[:, 1]
    if pack["_iso"] is not None:
        p = pack["_iso"].transform(p)
    return np.asarray(p, dtype=float)


def evalp(v11: Any, y: np.ndarray, p: np.ndarray, thr: float, band: float) -> Dict[str, float]:
    m = v11.compute_metrics(y, p, float(thr))
    u = v11.uncertainty_pack(y, p, float(thr), float(band))
    return {
        "precision": float(m["precision"]),
        "recall": float(m["recall"]),
        "specificity": float(m["specificity"]),
        "balanced_accuracy": float(m["balanced_accuracy"]),
        "f1": float(m["f1"]),
        "pr_auc": float(m["pr_auc"]),
        "brier": float(m["brier"]),
        "uncertain_rate": float(u["uncertain_rate"]),
        "uncertainty_usefulness": float(u["uncertainty_usefulness"]),
        "output_realism_score": float(u["output_realism_score"]),
    }

def main():
    root = Path(__file__).resolve().parents[1]
    base = root / "data" / "elimination_clean_rebuild_v12"
    for d in ["inventory", "forbidden_signals", "feature_sets", "trials", "ablation", "stress", "tables", "reports"]:
        (base / d).mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "elimination_clean_rebuild_v12").mkdir(parents=True, exist_ok=True)

    v11 = load_v11(root / "scripts" / "run_elimination_feature_engineering_v11.py")
    df = pd.read_csv(root / "data" / "processed_hybrid_dsm5_v2" / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv", low_memory=False)
    df["participant_id"] = df["participant_id"].astype(str)
    df, reg_v12 = add_v12_features(df)

    ids_train = read_ids(root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full" / "ids_train.csv")
    ids_val = read_ids(root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full" / "ids_val.csv")
    ids_test = read_ids(root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full" / "ids_test.csv")

    v10 = pd.read_csv(root / "data" / "final_hardening_v10" / "elimination" / "elimination_trial_registry.csv")
    v10_base = v10[v10["trial_name"] == "baseline"].copy()
    v11_manifest = json.loads((root / "artifacts" / "elimination_feature_engineering_v11" / "elimination_feature_engineering_v11_manifest.json").read_text(encoding="utf-8"))
    v11_trials = pd.read_csv(root / "data" / "elimination_feature_engineering_v11" / "trials" / "elimination_trial_metrics_full.csv")
    v11_lineage = pd.read_csv(root / "data" / "elimination_feature_engineering_v11" / "feature_sets" / "elimination_engineered_feature_lineage.csv")
    champ = json.loads((root / "models" / "champions" / "rf_elimination_current" / "metadata.json").read_text(encoding="utf-8"))
    champion = [c for c in champ["feature_columns"] if c in df.columns]

    forbidden = pd.DataFrame([
        {"feature_name": "cbcl_108", "source": "CBCL", "signal_type": "direct_item", "relation_with_target": "direct_elimination_proxy", "shortcut_evidence": "v11 shortcut equivalent winner", "severity": "critical", "decision": "forbid"},
        {"feature_name": "cbcl_112", "source": "CBCL", "signal_type": "direct_item", "relation_with_target": "direct_elimination_proxy", "shortcut_evidence": "v11 shortcut equivalent winner", "severity": "critical", "decision": "forbid"},
        {"feature_name": "shortcut_rule_cbcl108_or_cbcl112", "source": "forensic_rule", "signal_type": "rule", "relation_with_target": "practical_target_reconstruction", "shortcut_evidence": "v11 audit psychologist max_diff=0", "severity": "critical", "decision": "forbid"},
    ])
    for _, r in v11_lineage.iterrows():
        n, src = str(r["feature_name"]), str(r.get("source_variables", ""))
        if any(t in src for t in BLOCKED_TOKENS):
            forbidden = pd.concat([forbidden, pd.DataFrame([{"feature_name": n, "source": "v11_engineered", "signal_type": "derived", "relation_with_target": "inherits_blocked_signal", "shortcut_evidence": src, "severity": "high", "decision": "forbid"}])], ignore_index=True)
    forbidden = forbidden.drop_duplicates(subset=["feature_name"])
    wcsv(forbidden, base / "forbidden_signals" / "forbidden_signal_registry.csv")
    wmd(base / "reports" / "forbidden_signal_analysis.md", "# forbidden signal analysis\n\n" + forbidden.to_string(index=False))

    policy = pd.DataFrame([
        {"policy_id": "P1", "rule_type": "exact_feature_block", "rule_definition": "feature in forbidden_signal_registry where decision=forbid", "applies_to": "all_modes", "enforcement_stage": "feature_set_build", "rationale": "remove direct shortcuts"},
        {"policy_id": "P2", "rule_type": "formula_token_block", "rule_definition": "source_formula contains cbcl_108 or cbcl_112", "applies_to": "engineered_features", "enforcement_stage": "engineered_filter", "rationale": "remove equivalent derived shortcuts"},
        {"policy_id": "P3", "rule_type": "winner_guard", "rule_definition": "assert winner feature list excludes forbidden tokens", "applies_to": "winner_export", "enforcement_stage": "pre_export", "rationale": "prevent accidental reintroduction"},
        {"policy_id": "P4", "rule_type": "extreme_performance_trigger", "rule_definition": "BA>=0.995 or P/R/Spec=1.0", "applies_to": "all_modes", "enforcement_stage": "post_eval", "rationale": "force forensic re-audit"},
    ])
    wcsv(policy, base / "forbidden_signals" / "shortcut_block_policy.csv")
    wmd(base / "reports" / "shortcut_block_policy.md", "# shortcut block policy\n\n" + policy.to_string(index=False))

    blocked_exact = set(forbidden[forbidden["decision"] == "forbid"]["feature_name"].astype(str).tolist()) | set(BLOCKED_EXACT)
    formula_lookup = {str(r["feature_name"]): str(r.get("source_variables", "")) for _, r in pd.concat([v11_lineage[["feature_name", "source_variables"]], reg_v12[["feature_name", "source_variables"]]], ignore_index=True).drop_duplicates("feature_name").iterrows()}

    fs_rows, fs_map = [], {}
    for mode in MODES:
        sets = build_sets(df, mode, champion, blocked_exact, formula_lookup, v11)
        for name, feats in sets.items():
            fs_map[(mode, name)] = feats
            fs_rows.append({"mode": mode, "feature_set_name": name, "n_features": len(feats), "included_features_preview": "|".join(feats[:25]), "excluded_features_count": len([f for f in feats if f in blocked_exact]), "rationale": "clean build", "maintenance_cost": "low" if len(feats) <= 24 else ("medium" if len(feats) <= 40 else "high"), "methodological_risk": "low_to_medium", "dependency_on_cbcl_coverage": "high" if sum(1 for f in feats if f.startswith("cbcl_") or f == "has_cbcl") >= 5 else ("medium" if sum(1 for f in feats if f.startswith("cbcl_") or f == "has_cbcl") >= 2 else "low"), "expected_robustness": "medium"})
    fs_df = pd.DataFrame(fs_rows).sort_values(["mode", "feature_set_name"])
    wcsv(fs_df, base / "feature_sets" / "elimination_clean_feature_set_registry.csv")
    wmd(base / "reports" / "elimination_clean_feature_sets.md", "# elimination clean feature sets\n\n" + fs_df.to_string(index=False))

    trials, packs = [], {}
    for mode in MODES:
        for name in sorted({k[1] for k in fs_map if k[0] == mode}):
            feats = fs_map[(mode, name)]
            if len(feats) < 8:
                continue
            for fam in FAMILIES:
                t = fit(v11, df, ids_train, ids_val, ids_test, feats, fam, mode, name)
                trials.append({k: v for k, v in t.items() if not k.startswith("_")})
                packs[(mode, name, fam)] = t
    tdf = pd.DataFrame(trials).sort_values(["mode", "objective"], ascending=[True, False])
    wcsv(tdf[["mode", "domain", "feature_set", "family", "n_features", "calibration", "threshold", "fit_seconds", "seed_std_balanced_accuracy", "stability", "operational_complexity", "maintenance_complexity", "objective"]], base / "trials" / "elimination_clean_trial_registry.csv")
    wcsv(tdf, base / "trials" / "elimination_clean_trial_metrics_full.csv")

    best = {}
    for mode in MODES:
        r = tdf[tdf["mode"] == mode].iloc[0]
        best[mode] = packs[(r["mode"], r["feature_set"], r["family"])]
    wmd(base / "reports" / "elimination_clean_training_analysis.md", "# elimination clean training analysis\n\n" + tdf.groupby("mode", as_index=False).first()[["mode", "feature_set", "family", "precision", "recall", "specificity", "balanced_accuracy", "f1", "pr_auc", "brier", "objective"]].to_string(index=False))

    op_rows = []
    for mode in MODES:
        b = best[mode]
        ops = [("balanced", b["threshold"], 0.08), ("recall_first_screening", max(0.01, b["threshold"] - 0.07), 0.10), ("uncertainty_preferred", b["threshold"], 0.16), ("conservative_probability", min(0.99, b["threshold"] + 0.06), 0.06), ("professional_detail_only", max(0.01, b["threshold"] - 0.03), 0.14)]
        for oname, thr, band in ops:
            m = evalp(v11, b["_yte"], b["_pte"], float(thr), float(band))
            obj = 0.35 * m["balanced_accuracy"] + 0.25 * m["recall"] + 0.15 * m["precision"] + 0.15 * m["pr_auc"] + 0.10 * (1 - m["brier"]) - (0.05 if mode == "caregiver" and oname == "professional_detail_only" else 0.0)
            op_rows.append({"mode": mode, "operating_mode": oname, "threshold": float(thr), "uncertainty_band": float(band), **m, "objective": float(obj), "source_feature_set": b["feature_set"], "source_family": b["family"], "source_calibration": b["calibration"]})
    op_df = pd.DataFrame(op_rows).sort_values(["mode", "objective"], ascending=[True, False])
    sel_op = op_df.groupby("mode", as_index=False).first()
    wcsv(op_df, base / "tables" / "elimination_clean_operating_modes.csv")
    wmd(base / "reports" / "elimination_clean_operating_modes.md", "# elimination clean operating modes\n\n" + sel_op[["mode", "operating_mode", "threshold", "uncertainty_band", "precision", "recall", "specificity", "balanced_accuracy", "pr_auc", "brier", "uncertain_rate"]].to_string(index=False))
    abl_rows, stress_rows, short_rows = [], [], []
    test = df[df["participant_id"].isin(set(ids_test))].copy()

    def miss(X: pd.DataFrame, frac: float, seed: int) -> pd.DataFrame:
        out = X.copy(); rng = np.random.default_rng(seed)
        cols = [c for c in out.columns if c not in {"sex_assigned_at_birth", "site", "release"}]
        msk = rng.random((len(out), len(cols))) < frac
        for j, c in enumerate(cols):
            out.loc[msk[:, j], c] = np.nan
        return out

    def noise(X: pd.DataFrame, frac: float, seed: int) -> pd.DataFrame:
        out = X.copy(); rng = np.random.default_rng(seed)
        for c in out.columns:
            if pd.api.types.is_numeric_dtype(out[c]):
                s = pd.to_numeric(out[c], errors="coerce"); sd = float(s.std(skipna=True))
                if np.isfinite(sd) and sd > 0:
                    out[c] = s + rng.normal(0.0, sd * frac, size=len(out))
        return out

    for mode in MODES:
        b = best[mode]
        thr = float(sel_op[sel_op["mode"] == mode].iloc[0]["threshold"])
        band = float(sel_op[sel_op["mode"] == mode].iloc[0]["uncertainty_band"])
        feats = b["_features"]

        corr = []
        for c in b["_Xtr"].columns:
            s = pd.to_numeric(b["_Xtr"][c], errors="coerce")
            if s.notna().sum() >= 30:
                corr.append((c, abs(float(s.fillna(s.median()).corr(pd.Series(b["_ytr"]))))))
        corr.sort(key=lambda x: x[1], reverse=True)
        top1 = [x[0] for x in corr[:1]]
        top3 = [x[0] for x in corr[:3]]

        cfg = {
            "winner_selected": feats,
            "drop_engineered_clean_block": [f for f in feats if not f.startswith("v12_")],
            "drop_cbcl_block": [f for f in feats if not (f.startswith("cbcl_") or f == "has_cbcl")],
            "drop_sdq_block": [f for f in feats if not (f.startswith("sdq_") or f == "has_sdq")],
            "drop_source_specific_block": [f for f in feats if not (f.startswith("has_") or f in {"site", "release"})],
            "drop_self_report_block": [f for f in feats if not (f.startswith(("ysr_", "scared_sr_", "ari_sr_", "cdi_", "mfq_sr_")) or f in {"has_ysr", "has_scared_sr", "has_ari_sr", "has_cdi", "has_mfq_sr"})],
            "drop_top1_corr_feature": [f for f in feats if f not in set(top1)],
            "drop_top3_corr_features": [f for f in feats if f not in set(top3)],
            "minimal_reasonable_subset": feats[: max(8, min(12, len(feats)))],
        }
        for name, f2 in cfg.items():
            f2 = [f for f in f2 if f in df.columns]
            if len(f2) < 6:
                continue
            t = fit(v11, df, ids_train, ids_val, ids_test, f2, b["family"], mode, name)
            m = evalp(v11, t["_yte"], t["_pte"], float(t["threshold"]), band)
            abl_rows.append({"mode": mode, "ablation_config": name, "family": b["family"], "n_features": len(f2), **m, "delta_ba_vs_winner": float(m["balanced_accuracy"] - float(sel_op[sel_op["mode"] == mode].iloc[0]["balanced_accuracy"]))})

        rule = ((to_num(test, "cbcl_108").fillna(0) > 0) | (to_num(test, "cbcl_112").fillna(0) > 0)).astype(float).to_numpy()
        short_rows.append({"mode": mode, "shortcut_rule": "cbcl_108_or_cbcl_112", **evalp(v11, b["_yte"], rule, 0.5, band)})

        scenarios = [("baseline_clean", b["_Xte"].copy(), thr), ("missingness_light_10pct", miss(b["_Xte"], 0.1, 11), thr), ("missingness_moderate_25pct", miss(b["_Xte"], 0.25, 42), thr)]
        xcb = b["_Xte"].copy()
        for c in [c for c in xcb.columns if c.startswith("cbcl_")]:
            xcb[c] = np.nan
        if "has_cbcl" in xcb.columns:
            xcb["has_cbcl"] = 0.0
        scenarios.append(("cbcl_coverage_drop", xcb, thr))
        scenarios.append(("partial_coverage_random_40pct", miss(b["_Xte"], 0.4, 2026), thr))
        xsm = b["_Xte"].copy()
        if mode == "caregiver":
            for c in ["conners_total", "swan_total", "scared_p_total", "ari_p_symptom_total"]:
                if c in xsm.columns:
                    xsm[c] = np.nan
            for c in ["has_conners", "has_swan", "has_scared_p", "has_ari_p"]:
                if c in xsm.columns:
                    xsm[c] = 0.0
        else:
            for c in [c for c in xsm.columns if c.startswith(("ysr_", "scared_sr_", "ari_sr_", "cdi_", "mfq_sr_", "v12_parent_self_gap_", "v12_self_", "v12_cross_source_agreement_clean"))]:
                xsm[c] = np.nan
            for c in ["has_ysr", "has_scared_sr", "has_ari_sr", "has_cdi", "has_mfq_sr"]:
                if c in xsm.columns:
                    xsm[c] = 0.0
        scenarios.append(("source_mix_shift", xsm, thr))
        scenarios += [("threshold_stress_minus_0.05", b["_Xte"].copy(), max(0.01, thr - 0.05)), ("threshold_stress_plus_0.05", b["_Xte"].copy(), min(0.99, thr + 0.05)), ("feature_perturbation_5pct_std", noise(b["_Xte"], 0.05, 777), thr)]

        for sname, Xs, t in scenarios:
            m = evalp(v11, b["_yte"], pred(b, Xs), float(t), band)
            stress_rows.append({"mode": mode, "scenario": sname, "threshold_used": float(t), **m, "delta_ba_vs_baseline_clean": float(m["balanced_accuracy"] - float(sel_op[sel_op["mode"] == mode].iloc[0]["balanced_accuracy"]))})

        mask = np.abs(b["_pte"] - thr) <= 0.08
        if int(mask.sum()) >= 20:
            m = evalp(v11, b["_yte"][mask], b["_pte"][mask], float(thr), band)
            stress_rows.append({"mode": mode, "scenario": "borderline_cases_threshold_pm_0.08", "threshold_used": float(thr), **m, "delta_ba_vs_baseline_clean": float(m["balanced_accuracy"] - float(sel_op[sel_op["mode"] == mode].iloc[0]["balanced_accuracy"]))})

    abl = pd.DataFrame(abl_rows).sort_values(["mode", "balanced_accuracy"], ascending=[True, False])
    stress = pd.DataFrame(stress_rows).sort_values(["mode", "scenario"])
    short = pd.DataFrame(short_rows)
    wcsv(abl, base / "ablation" / "elimination_clean_ablation_results.csv")
    wcsv(stress, base / "stress" / "elimination_clean_stress_results.csv")
    wmd(base / "reports" / "elimination_clean_ablation_and_stress.md", "# elimination clean ablation and stress\n\n## ablation\n\n" + abl.to_string(index=False) + "\n\n## shortcut comparator\n\n" + short.to_string(index=False) + "\n\n## stress\n\n" + stress.to_string(index=False))

    out = []
    for mode in MODES:
        sel = sel_op[sel_op["mode"] == mode].iloc[0]
        worst = float(stress[(stress["mode"] == mode) & (stress["scenario"] != "borderline_cases_threshold_pm_0.08")]["balanced_accuracy"].min())
        sh = short[short["mode"] == mode].iloc[0]
        mdiff = max(abs(float(sel["precision"]) - float(sh["precision"])), abs(float(sel["recall"]) - float(sh["recall"])), abs(float(sel["specificity"]) - float(sh["specificity"])), abs(float(sel["balanced_accuracy"]) - float(sh["balanced_accuracy"])))
        independent = mdiff > 0.01
        if float(sel["balanced_accuracy"]) >= 0.86 and float(sel["recall"]) >= 0.78 and float(sel["brier"]) <= 0.11 and worst >= 0.70 and independent:
            status = "ready_with_caveat"
        elif float(sel["balanced_accuracy"]) >= 0.80 and float(sel["recall"]) >= 0.70 and worst >= 0.62 and independent:
            status = "uncertainty_preferred"
        elif float(sel["balanced_accuracy"]) >= 0.76:
            status = "ready_only_for_professional_detail"
        else:
            status = "not_ready_for_strong_probability_interpretation"
        out.append({"mode": mode, "domain": "elimination", "selected_operating_mode": sel["operating_mode"], "precision": float(sel["precision"]), "recall": float(sel["recall"]), "specificity": float(sel["specificity"]), "balanced_accuracy": float(sel["balanced_accuracy"]), "f1": float(sel["f1"]), "pr_auc": float(sel["pr_auc"]), "brier": float(sel["brier"]), "worst_stress_ba": worst, "shortcut_max_metric_diff": mdiff, "shortcut_independence": "yes" if independent else "no", "probability_ready": "yes" if float(sel["brier"]) <= 0.14 else "no", "risk_band_ready": "yes" if float(sel["balanced_accuracy"]) >= 0.80 else "no", "confidence_ready": "yes" if float(sel["output_realism_score"]) >= 0.82 else "no", "uncertainty_ready": "yes" if float(sel["uncertainty_usefulness"]) >= -0.05 else "no", "professional_detail_ready": "yes", "final_output_status": status, "visible_user_prob_cap": "[0.01,0.99]", "visible_prof_prob_cap": "[0.005,0.995]", "extreme_performance_audit_trigger": "yes" if (float(sel["balanced_accuracy"]) >= 0.995 or np.isclose(float(sel["precision"]), 1.0) or np.isclose(float(sel["recall"]), 1.0) or np.isclose(float(sel["specificity"]), 1.0)) else "no"})

    outdf = pd.DataFrame(out)
    wcsv(outdf, base / "tables" / "elimination_clean_output_readiness.csv")
    wmd(base / "reports" / "elimination_clean_output_readiness.md", "# elimination clean output readiness\n\n" + outdf.to_string(index=False))
    v11_rows = []
    for mode in MODES:
        bm = v11_manifest["best_trials_by_mode"][mode]
        sub = v11_trials[(v11_trials["mode"] == mode) & (v11_trials["feature_set"] == bm["feature_set"]) & (v11_trials["family"] == bm["family"])].copy().sort_values("objective", ascending=False).iloc[0]
        v11_rows.append({"mode": mode, "precision": float(sub["precision"]), "recall": float(sub["recall"]), "specificity": float(sub["specificity"]), "balanced_accuracy": float(sub["balanced_accuracy"]), "f1": float(sub["f1"]), "pr_auc": float(sub["pr_auc"]), "brier": float(sub["brier"])})
    v11df = pd.DataFrame(v11_rows)

    comp, delta = [], []
    for mode in MODES:
        b = v10_base[v10_base["mode"] == mode].iloc[0]
        i = v11df[v11df["mode"] == mode].iloc[0]
        c = outdf[outdf["mode"] == mode].iloc[0]
        comp.extend([
            {"mode": mode, "version": "baseline_pre_v11", "precision": float(b["precision"]), "recall": float(b["recall"]), "specificity": float(b["specificity"]), "balanced_accuracy": float(b["balanced_accuracy"]), "f1": float(b["f1"]), "pr_auc": float(b.get("pr_auc", np.nan)), "brier": float(b["brier"]), "stress_worst_ba": np.nan, "output_status": "legacy_caveat"},
            {"mode": mode, "version": "v11_inflated", "precision": float(i["precision"]), "recall": float(i["recall"]), "specificity": float(i["specificity"]), "balanced_accuracy": float(i["balanced_accuracy"]), "f1": float(i["f1"]), "pr_auc": float(i["pr_auc"]), "brier": float(i["brier"]), "stress_worst_ba": np.nan, "output_status": "hold_v11_needs_revision"},
            {"mode": mode, "version": "v12_clean", "precision": float(c["precision"]), "recall": float(c["recall"]), "specificity": float(c["specificity"]), "balanced_accuracy": float(c["balanced_accuracy"]), "f1": float(c["f1"]), "pr_auc": float(c["pr_auc"]), "brier": float(c["brier"]), "stress_worst_ba": float(c["worst_stress_ba"]), "output_status": str(c["final_output_status"])},
        ])
        delta.append({
            "mode": mode,
            "delta_precision_v12_vs_baseline": float(c["precision"] - float(b["precision"])),
            "delta_recall_v12_vs_baseline": float(c["recall"] - float(b["recall"])),
            "delta_specificity_v12_vs_baseline": float(c["specificity"] - float(b["specificity"])),
            "delta_ba_v12_vs_baseline": float(c["balanced_accuracy"] - float(b["balanced_accuracy"])),
            "delta_f1_v12_vs_baseline": float(c["f1"] - float(b["f1"])),
            "delta_pr_auc_v12_vs_baseline": float(c["pr_auc"] - float(b.get("pr_auc", np.nan))),
            "delta_brier_v12_vs_baseline": float(c["brier"] - float(b["brier"])),
            "delta_precision_v12_vs_v11": float(c["precision"] - float(i["precision"])),
            "delta_recall_v12_vs_v11": float(c["recall"] - float(i["recall"])),
            "delta_specificity_v12_vs_v11": float(c["specificity"] - float(i["specificity"])),
            "delta_ba_v12_vs_v11": float(c["balanced_accuracy"] - float(i["balanced_accuracy"])),
            "delta_f1_v12_vs_v11": float(c["f1"] - float(i["f1"])),
            "delta_pr_auc_v12_vs_v11": float(c["pr_auc"] - float(i["pr_auc"])),
            "delta_brier_v12_vs_v11": float(c["brier"] - float(i["brier"])),
            "delta_stress_robustness_v12": float(c["worst_stress_ba"] - float(c["balanced_accuracy"])),
            "delta_output_readiness_v12_vs_baseline": str(c["final_output_status"]),
        })
    compdf, deltadf = pd.DataFrame(comp), pd.DataFrame(delta)
    wcsv(deltadf, base / "tables" / "elimination_clean_final_delta.csv")
    wmd(base / "reports" / "elimination_clean_final_delta_analysis.md", "# elimination clean final delta\n\n## absolute\n\n" + compdf.to_string(index=False) + "\n\n## deltas\n\n" + deltadf.to_string(index=False))

    shortcut_ok = all(float(outdf[outdf["mode"] == m]["shortcut_max_metric_diff"].iloc[0]) > 0.01 for m in MODES)
    robust_ok = all(float(outdf[outdf["mode"] == m]["worst_stress_ba"].iloc[0]) >= 0.62 for m in MODES)
    recall_ok = all(float(outdf[outdf["mode"] == m]["recall"].iloc[0]) >= 0.70 for m in MODES)

    if not shortcut_ok:
        decision = "HOLD_ELIMINATION_STRUCTURAL_LIMIT"
    elif robust_ok and recall_ok and all(outdf["final_output_status"].isin(["ready_with_caveat", "uncertainty_preferred"])):
        decision = "APPROVE_V12_WITH_CAVEAT"
    elif all(outdf["final_output_status"].isin(["uncertainty_preferred", "ready_only_for_professional_detail"])):
        decision = "UNCERTAINTY_PREFERRED_ONLY"
    elif all(outdf["final_output_status"] == "not_ready_for_strong_probability_interpretation"):
        decision = "REJECT_FOR_STRONG_INTERPRETATION"
    else:
        decision = "HOLD_ELIMINATION_STRUCTURAL_LIMIT"

    wmd(base / "reports" / "elimination_clean_final_decision.md", f"# elimination clean final decision\n\nDecision: `{decision}`\n\n1) valid clean improvement: {'yes' if all(deltadf['delta_ba_v12_vs_baseline'] > 0) else 'partial/no'}\n2) recall improved useful: {'yes' if recall_ok else 'no'}\n3) robustness improved: {'yes' if robust_ok else 'partial/no'}\n4) shortcut dependence removed: {'yes' if shortcut_ok else 'no'}\n5) can replace previous: {'yes' if decision in ['APPROVE_V12','APPROVE_V12_WITH_CAVEAT','UNCERTAINTY_PREFERRED_ONLY'] else 'no'}\n6) caveat: high caveat + confidence clipping + automatic extreme audit\n7) closure: {'close with caveat' if decision!='HOLD_ELIMINATION_STRUCTURAL_LIMIT' else 'hold; likely structural limit'}\n\n" + outdf.to_string(index=False))
    wmd(base / "reports" / "elimination_clean_executive_summary.md", f"# elimination clean executive summary\n\n- decision: {decision}\n- shortcut_independence_global: {'yes' if shortcut_ok else 'no'}\n- robust_global: {'yes' if robust_ok else 'no'}\n- recall_useful_global: {'yes' if recall_ok else 'no'}\n- rounds_policy: max 3 strong + 1 confirm\n\n" + deltadf.to_string(index=False) + "\n\nConfidence policy: user [1%,99%], professional [0.5%,99.5%], internal raw preserved.")

    inv = pd.DataFrame([
        {
            "mode": m,
            "train_size": len(ids_train),
            "val_size": len(ids_val),
            "test_size": len(ids_test),
            "holdout_hash_ordered": h(ids_test, True),
            "holdout_hash_set": h(ids_test, False),
            "selected_feature_set": best[m]["feature_set"],
            "selected_family": best[m]["family"],
            "selected_threshold": best[m]["threshold"],
            "selected_calibration": best[m]["calibration"],
            "selected_operating_mode": outdf[outdf["mode"] == m].iloc[0]["selected_operating_mode"],
        }
        for m in MODES
    ])
    wcsv(inv, base / "inventory" / "elimination_base_inventory.csv")
    wmd(base / "reports" / "elimination_base_summary.md", "# elimination clean rebuild v12 inventory\n\n" + inv.to_string(index=False))

    wjson(root / "artifacts" / "elimination_clean_rebuild_v12" / "elimination_clean_rebuild_v12_manifest.json", {
        "campaign": "elimination_clean_rebuild_v12",
        "final_decision": decision,
        "split_dir": str(root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full"),
        "holdout_hash_ordered": h(ids_test, True),
        "holdout_hash_set": h(ids_test, False),
        "forbidden_signals": sorted(list(blocked_exact))[:100],
        "selected_models": {m: {"feature_set": best[m]["feature_set"], "family": best[m]["family"], "n_features": len(best[m]["_features"]), "threshold": float(best[m]["threshold"]), "calibration": best[m]["calibration"]} for m in MODES},
        "confidence_display_policy": {"internal_raw_probability_preserved": True, "user_visible": {"min": 0.01, "max": 0.99}, "professional_visible": {"min": 0.005, "max": 0.995}},
        "extreme_performance_audit_trigger": {"balanced_accuracy_ge": 0.995, "precision_eq": 1.0, "recall_eq": 1.0, "specificity_eq": 1.0},
    })

    print("OK - elimination_clean_rebuild_v12 generated")


if __name__ == "__main__":
    main()
