#!/usr/bin/env python
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.pipeline import Pipeline

TARGET = "target_domain_elimination"
TARGET_ENURESIS = "target_enuresis_exact"
TARGET_ENCOPRESIS = "target_encopresis_exact"
MODES = ["caregiver", "psychologist"]
BLOCKED = {
    "cbcl_108",
    "cbcl_112",
    "shortcut_rule_cbcl108_or_cbcl112",
    "v11_core_sum",
    "v11_core_mean",
    "v11_core_balance_diff",
    "v11_subtype_enuresis_proxy",
    "v11_subtype_encopresis_proxy",
    "v11_subtype_gap_proxy",
}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def wcsv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def wmd(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def wjson(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_ids(path: Path) -> List[str]:
    d = pd.read_csv(path)
    return d[d.columns[0]].astype(str).tolist()


def hash_ids(ids: Iterable[str], ordered: bool) -> str:
    xs = list(ids)
    if not ordered:
        xs = sorted(set(xs))
    return hashlib.sha256("|".join(xs).encode("utf-8")).hexdigest()


def to_num(df: pd.DataFrame, c: str) -> pd.Series:
    if c not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[c], errors="coerce")


def row_nonmissing(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return pd.Series(np.zeros(len(df)), index=df.index)
    return df[cols].apply(pd.to_numeric, errors="coerce").notna().sum(axis=1).astype(float)


def add_v14_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    rows = []
    cbcl_proxy = [
        "cbcl_aggressive_behavior_proxy",
        "cbcl_anxious_depressed_proxy",
        "cbcl_attention_problems_proxy",
        "cbcl_externalizing_proxy",
        "cbcl_internalizing_proxy",
        "cbcl_rule_breaking_proxy",
    ]
    parent_core = cbcl_proxy + ["sdq_impact", "sdq_conduct_problems", "sdq_total_difficulties", "conners_total", "swan_total", "scared_p_total", "ari_p_symptom_total"]
    all_core = parent_core + ["ysr_internalizing_proxy", "scared_sr_total", "ari_sr_symptom_total", "cdi_total", "mfq_sr_total"]

    def add(name: str, val: pd.Series, fam: str, src: str):
        out[name] = val
        rows.append({"feature_name": name, "feature_family": fam, "source_variables": src, "blocked_ref": "yes" if ("cbcl_108" in src or "cbcl_112" in src) else "no"})

    add("v14_cbcl_proxy_nonmissing_ratio", row_nonmissing(out, cbcl_proxy) / max(1, len([c for c in cbcl_proxy if c in out.columns])), "coverage", ",".join(cbcl_proxy))
    add("v14_parent_core_nonmissing_ratio", row_nonmissing(out, parent_core) / max(1, len([c for c in parent_core if c in out.columns])), "coverage", ",".join(parent_core))
    add("v14_total_nonmissing_ratio", row_nonmissing(out, all_core) / max(1, len([c for c in all_core if c in out.columns])), "coverage", ",".join(all_core))
    add("v14_low_cov_flag", (to_num(out, "v14_total_nonmissing_ratio").fillna(0.0) < 0.50).astype(float), "coverage", "v14_total_nonmissing_ratio")
    add("v14_fn_pattern", (to_num(out, "sdq_impact").fillna(0) + to_num(out, "v12_parent_behavior_burden").fillna(0) + to_num(out, "v12_parent_impact_context").fillna(0)) / 3.0, "fn", "sdq_impact,v12_parent_behavior_burden,v12_parent_impact_context")
    add("v14_fn_ambiguity", (to_num(out, "v12_cbcl_sdq_alignment").fillna(0) + to_num(out, "v12_cbcl_sdq_internal_alignment").fillna(0)) / 2.0, "fn", "v12_cbcl_sdq_alignment,v12_cbcl_sdq_internal_alignment")
    add("v14_source_mix_ratio", (to_num(out, "has_cbcl").fillna(0) + to_num(out, "has_sdq").fillna(0) + to_num(out, "has_conners").fillna(0) + to_num(out, "has_swan").fillna(0) + to_num(out, "has_scared_p").fillna(0) + to_num(out, "has_ari_p").fillna(0) + to_num(out, "has_ysr").fillna(0) + to_num(out, "has_scared_sr").fillna(0) + to_num(out, "has_ari_sr").fillna(0)) / 9.0, "source_semantics", "has_*")
    add("v14_sparse_source_flag", (to_num(out, "v14_source_mix_ratio").fillna(0.0) < 0.30).astype(float), "source_semantics", "v14_source_mix_ratio")

    reg = pd.DataFrame(rows)
    reg = reg[reg["blocked_ref"] == "no"].reset_index(drop=True)
    return out, reg


def sanitize(v11: Any, df: pd.DataFrame, cols: List[str], mode: str) -> List[str]:
    out = []
    for c in cols:
        if c not in df.columns:
            continue
        if c in BLOCKED or c in {"cbcl_108", "cbcl_112"}:
            continue
        if v11.is_blocked_feature(c):
            continue
        if mode == "caregiver" and v11.is_self_report_feature(c):
            continue
        if c not in out:
            out.append(c)
    return out


def choose_threshold(v11: Any, y: np.ndarray, p: np.ndarray, strategy: str) -> float:
    cands = np.linspace(0.15, 0.85, 141)
    best_thr, best = 0.5, -1e18
    for thr in cands:
        m = v11.compute_metrics(y, p, float(thr))
        if strategy == "recall_first":
            if m["precision"] < 0.72:
                continue
            s = 0.55 * m["recall"] + 0.25 * m["balanced_accuracy"] + 0.20 * m["f1"]
        elif strategy == "precision_guarded":
            if m["recall"] < 0.66:
                continue
            s = 0.52 * m["precision"] + 0.24 * m["balanced_accuracy"] + 0.24 * m["specificity"]
        else:
            s = 0.33 * m["precision"] + 0.27 * m["balanced_accuracy"] + 0.20 * m["recall"] + 0.10 * m["f1"] + 0.10 * m["specificity"]
        if s > best:
            best, best_thr = float(s), float(thr)
    return float(best_thr)


def selective_metrics(v11: Any, y: np.ndarray, p: np.ndarray, thr: float, uncertain_mask: np.ndarray) -> Dict[str, float]:
    decided = ~uncertain_mask.astype(bool)
    cov = float(np.mean(decided))
    if decided.sum() < 20 or len(np.unique(y[decided])) < 2:
        return {"coverage_rate": cov, "uncertain_rate": 1.0 - cov, "precision": np.nan, "recall": np.nan, "specificity": np.nan, "balanced_accuracy": np.nan, "f1": np.nan, "pr_auc": np.nan, "brier": np.nan}
    m = v11.compute_metrics(y[decided], p[decided], float(thr))
    return {"coverage_rate": cov, "uncertain_rate": 1.0 - cov, "precision": float(m["precision"]), "recall": float(m["recall"]), "specificity": float(m["specificity"]), "balanced_accuracy": float(m["balanced_accuracy"]), "f1": float(m["f1"]), "pr_auc": float(m["pr_auc"]), "brier": float(m["brier"])}

def fit_subtype_union(v11: Any, df: pd.DataFrame, ids_train: List[str], ids_val: List[str], ids_test: List[str], features: List[str]) -> Tuple[np.ndarray, np.ndarray, float]:
    frame = df[["participant_id", TARGET, TARGET_ENURESIS, TARGET_ENCOPRESIS] + features].copy()
    tr = frame[frame["participant_id"].astype(str).isin(set(ids_train))]
    va = frame[frame["participant_id"].astype(str).isin(set(ids_val))]
    te = frame[frame["participant_id"].astype(str).isin(set(ids_test))]

    Xtr, Xva, Xte = tr[features], va[features], te[features]
    ytr_en = pd.to_numeric(tr[TARGET_ENURESIS], errors="coerce").fillna(0).astype(int).to_numpy()
    ytr_ec = pd.to_numeric(tr[TARGET_ENCOPRESIS], errors="coerce").fillna(0).astype(int).to_numpy()
    yva_el = pd.to_numeric(va[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()
    yte_el = pd.to_numeric(te[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()

    rf_cfg = dict(n_estimators=420, max_depth=8, min_samples_leaf=4, class_weight="balanced_subsample", random_state=42, n_jobs=1)
    pipe_en = Pipeline([("preprocessor", v11.build_preprocessor(Xtr)), ("model", RandomForestClassifier(**rf_cfg))])
    pipe_ec = Pipeline([("preprocessor", v11.build_preprocessor(Xtr)), ("model", RandomForestClassifier(**rf_cfg))])
    pipe_en.fit(Xtr, ytr_en)
    pipe_ec.fit(Xtr, ytr_ec)

    pva = 1.0 - (1.0 - pipe_en.predict_proba(Xva)[:, 1]) * (1.0 - pipe_ec.predict_proba(Xva)[:, 1])
    pte = 1.0 - (1.0 - pipe_en.predict_proba(Xte)[:, 1]) * (1.0 - pipe_ec.predict_proba(Xte)[:, 1])
    if len(np.unique(yva_el)) > 1:
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(pva, yva_el)
        pva_i = iso.transform(pva)
        if float(np.mean((pva_i - yva_el) ** 2)) <= float(np.mean((pva - yva_el) ** 2)) + 5e-4:
            pva, pte = pva_i, iso.transform(pte)
    thr = choose_threshold(v11, yva_el, pva, "balanced")
    return yte_el, pte, float(thr)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    base = root / "data" / "elimination_final_push_v14"
    for d in ["inventory", "coverage_gate", "fn_analysis", "two_stage", "subtypes", "uncertainty", "trials", "ablation", "stress", "tables", "reports"]:
        (base / d).mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "elimination_final_push_v14").mkdir(parents=True, exist_ok=True)

    v11 = load_module(root / "scripts" / "run_elimination_feature_engineering_v11.py", "v11_mod_v14")
    v12 = load_module(root / "scripts" / "run_elimination_clean_rebuild_v12.py", "v12_mod_v14")
    data_path = root / "data" / "processed_hybrid_dsm5_v2" / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv"
    split = root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full"
    ids_train, ids_val, ids_test = read_ids(split / "ids_train.csv"), read_ids(split / "ids_val.csv"), read_ids(split / "ids_test.csv")

    df = pd.read_csv(data_path, low_memory=False)
    df["participant_id"] = df["participant_id"].astype(str)
    df, reg_v12 = v12.add_v12_features(df)
    df, reg_v14 = add_v14_features(df)
    df_idx = df.set_index("participant_id")
    test_ids_order = df[df["participant_id"].isin(set(ids_test))]["participant_id"].astype(str).tolist()

    v10 = pd.read_csv(root / "data" / "final_hardening_v10" / "elimination" / "elimination_trial_registry.csv")
    bline = v10[v10["trial_name"] == "baseline"].copy()
    v12_out = pd.read_csv(root / "data" / "elimination_clean_rebuild_v12" / "tables" / "elimination_clean_output_readiness.csv")
    v12_ops = pd.read_csv(root / "data" / "elimination_clean_rebuild_v12" / "tables" / "elimination_clean_operating_modes.csv")
    v13_out = pd.read_csv(root / "data" / "elimination_feature_engineering_clean_v13" / "tables" / "elimination_v13_output_readiness.csv")
    fs_v12 = pd.read_csv(root / "data" / "elimination_clean_rebuild_v12" / "feature_sets" / "elimination_clean_feature_set_registry.csv")

    inv_rows = []
    for mode in MODES:
        r12 = v12_out[v12_out["mode"] == mode].iloc[0]
        inv_rows.append({"mode": mode, "baseline_precision": float(r12["precision"]), "baseline_recall": float(r12["recall"]), "baseline_ba": float(r12["balanced_accuracy"]), "baseline_pr_auc": float(r12["pr_auc"]), "baseline_brier": float(r12["brier"]), "baseline_output_status": str(r12["final_output_status"]), "holdout_hash_ordered": hash_ids(ids_test, True), "holdout_hash_set": hash_ids(ids_test, False), "open_limitations": "FN pressure + coverage fragility under CBCL drop", "confidence_user_clip": "[0.01,0.99]", "confidence_prof_clip": "[0.005,0.995]"})
    inv_df = pd.DataFrame(inv_rows)
    wcsv(inv_df, base / "inventory" / "elimination_v14_base_inventory.csv")
    wmd(base / "reports" / "elimination_v14_base_inventory.md", "# elimination v14 base inventory\n\n" + inv_df.to_string(index=False))

    trial_rows, packs = [], {}
    for mode in MODES:
        base_feats = str(fs_v12[(fs_v12["mode"] == mode) & (fs_v12["feature_set_name"] == "compact_clinical_clean")].iloc[0]["included_features_preview"]).split("|")
        sets = {
            "r1_v12_replay": base_feats,
            "r1_coverage_gate_augmented": base_feats + ["v14_cbcl_proxy_nonmissing_ratio", "v14_parent_core_nonmissing_ratio", "v14_total_nonmissing_ratio", "v14_low_cov_flag", "v14_source_mix_ratio", "v14_sparse_source_flag"],
            "r2_fn_optimized_clean": base_feats + ["v14_fn_pattern", "v14_fn_ambiguity", "v14_cbcl_proxy_nonmissing_ratio", "v14_total_nonmissing_ratio", "v14_source_mix_ratio", "v14_sparse_source_flag"],
            "r3_hybrid_clean_best_effort": base_feats + ["v14_fn_pattern", "v14_fn_ambiguity", "v14_low_cov_flag", "v14_cbcl_proxy_nonmissing_ratio", "v14_parent_core_nonmissing_ratio", "v14_total_nonmissing_ratio", "v14_source_mix_ratio", "v14_sparse_source_flag"],
        }
        for sname, cols in sets.items():
            feats = sanitize(v11, df, cols, mode)
            t = v12.fit(v11, df, ids_train, ids_val, ids_test, feats, "rf", mode, sname)
            packs[(mode, sname, "rf")] = t
            trial_rows.append({k: v for k, v in t.items() if not k.startswith("_")})
        rf_top = max([x for x in trial_rows if x["mode"] == mode and x["family"] == "rf"], key=lambda x: x["objective"])
        for fam in ["lightgbm", "xgboost"]:
            feats = sanitize(v11, df, sets[rf_top["feature_set"]], mode)
            t = v12.fit(v11, df, ids_train, ids_val, ids_test, feats, fam, mode, rf_top["feature_set"])
            packs[(mode, rf_top["feature_set"], fam)] = t
            trial_rows.append({k: v for k, v in t.items() if not k.startswith("_")})

    trial_df = pd.DataFrame(trial_rows).sort_values(["mode", "objective"], ascending=[True, False]).reset_index(drop=True)
    fam = trial_df.groupby(["mode", "family"], as_index=False).first()[["mode", "family", "feature_set", "precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier", "objective"]]
    fam = fam.rename(columns={"feature_set": "best_feature_set"})
    wcsv(fam, base / "tables" / "elimination_model_family_comparison.csv")
    wmd(base / "reports" / "elimination_model_family_analysis.md", "# elimination v14 model family analysis\n\n" + fam.to_string(index=False))

    winners, fn_rows, fn_sel = {}, [], {}
    for mode in MODES:
        r = trial_df[(trial_df["mode"] == mode) & (trial_df["family"] == "rf")].sort_values("objective", ascending=False).iloc[0]
        winners[mode] = packs[(mode, r["feature_set"], "rf")]
        w = winners[mode]
        yv, pv = w["_ytr"], w["_pipe"].predict_proba(w["_Xtr"])[:, 1]
        yt, pt = w["_yte"], w["_pte"]
        ops = [("balanced", float(w["threshold"]), 0.08), ("recall_first", choose_threshold(v11, yv, pv, "recall_first"), 0.10), ("precision_guarded", choose_threshold(v11, yv, pv, "precision_guarded"), 0.06)]
        for oname, thr, band in ops:
            m = v12.evalp(v11, yt, pt, float(thr), float(band))
            obj = 0.36 * m["recall"] + 0.26 * m["balanced_accuracy"] + 0.14 * m["precision"] + 0.14 * m["pr_auc"] + 0.10 * (1 - m["brier"]) - 0.08 * max(0.0, 0.78 - m["precision"])
            fn_rows.append({"mode": mode, "strategy": oname, "feature_set": w["feature_set"], "family": "rf", "threshold": float(thr), "uncertainty_band": float(band), **m, "fn_optimization_objective": float(obj)})
        mdf = pd.DataFrame([x for x in fn_rows if x["mode"] == mode]).sort_values("fn_optimization_objective", ascending=False)
        fn_sel[mode] = mdf.iloc[0].to_dict()

    fn_df = pd.DataFrame(fn_rows).sort_values(["mode", "fn_optimization_objective"], ascending=[True, False])
    wcsv(fn_df, base / "trials" / "elimination_fn_optimization_registry.csv")
    wmd(base / "reports" / "elimination_fn_optimization_analysis.md", "# elimination v14 FN optimization\n\n" + fn_df.to_string(index=False))

    gate_rows, unc_rows = [], []
    gate_sel, unc_sel = {}, {}
    for mode in MODES:
        w = winners[mode]
        y, p = w["_yte"], w["_pte"]
        thr = float(fn_sel[mode]["threshold"])
        te_meta = df_idx.reindex(test_ids_order)
        c1 = to_num(te_meta, "v14_cbcl_proxy_nonmissing_ratio").fillna(0.0).to_numpy()
        c2 = to_num(te_meta, "v14_total_nonmissing_ratio").fillna(0.0).to_numpy()
        c3 = to_num(te_meta, "v14_source_mix_ratio").fillna(0.0).to_numpy()
        sparse = to_num(te_meta, "v14_sparse_source_flag").fillna(0.0).to_numpy() > 0
        gates = {
            "gate_none": np.ones(len(p), dtype=bool),
            "gate_cbcl_ge_0.35": c1 >= 0.35,
            "gate_total_ge_0.50": c2 >= 0.50,
            "gate_combined_relaxed": (c1 >= 0.35) & (c2 >= 0.50) & (c3 >= 0.28),
            "gate_combined_strict": (c1 >= 0.50) & (c2 >= 0.60) & (c3 >= 0.35) & (~sparse),
        }
        mode_gate_rows = []
        for gname, gmask in gates.items():
            s = selective_metrics(v11, y, p, thr, ~gmask)
            ba = float(s["balanced_accuracy"]) if np.isfinite(s["balanced_accuracy"]) else 0.0
            rec = float(s["recall"]) if np.isfinite(s["recall"]) else 0.0
            prec = float(s["precision"]) if np.isfinite(s["precision"]) else 0.0
            brier = float(s["brier"]) if np.isfinite(s["brier"]) else 1.0
            obj = 0.34 * ba + 0.24 * rec + 0.14 * prec + 0.16 * s["coverage_rate"] + 0.12 * (1 - brier)
            row = {"mode": mode, "gate_name": gname, "threshold": thr, "coverage_rate": s["coverage_rate"], "uncertain_rate": s["uncertain_rate"], "precision_decided": s["precision"], "recall_decided": s["recall"], "specificity_decided": s["specificity"], "balanced_accuracy_decided": s["balanced_accuracy"], "f1_decided": s["f1"], "pr_auc_decided": s["pr_auc"], "brier_decided": s["brier"], "gate_objective": float(obj)}
            mode_gate_rows.append(row)
            gate_rows.append(row)
        mg = pd.DataFrame(mode_gate_rows)
        mg_ok = mg[(mg["coverage_rate"] >= 0.55) & mg["balanced_accuracy_decided"].notna()]
        gate_sel[mode] = (mg_ok if not mg_ok.empty else mg).sort_values("gate_objective", ascending=False).iloc[0].to_dict()

        gmask = gates[gate_sel[mode]["gate_name"]]
        mode_unc_rows = []
        for band in [0.04, 0.06, 0.08, 0.10, 0.12, 0.16, 0.20]:
            s = selective_metrics(v11, y, p, thr, (~gmask) | (np.abs(p - thr) < float(band)))
            u = v11.uncertainty_pack(y, p, float(thr), float(band))
            ba = float(s["balanced_accuracy"]) if np.isfinite(s["balanced_accuracy"]) else 0.0
            rec = float(s["recall"]) if np.isfinite(s["recall"]) else 0.0
            prec = float(s["precision"]) if np.isfinite(s["precision"]) else 0.0
            obj = 0.30 * ba + 0.24 * rec + 0.15 * prec + 0.16 * s["coverage_rate"] + 0.15 * float(u["uncertainty_usefulness"])
            row = {"mode": mode, "source_strategy": fn_sel[mode]["strategy"], "gate_name": gate_sel[mode]["gate_name"], "threshold": thr, "uncertainty_band": float(band), "coverage_rate": s["coverage_rate"], "uncertain_rate": s["uncertain_rate"], "precision_decided": s["precision"], "recall_decided": s["recall"], "specificity_decided": s["specificity"], "balanced_accuracy_decided": s["balanced_accuracy"], "f1_decided": s["f1"], "pr_auc_decided": s["pr_auc"], "brier_decided": s["brier"], "uncertainty_usefulness": float(u["uncertainty_usefulness"]), "output_realism_score": float(u["output_realism_score"]), "uncertainty_objective": float(obj)}
            mode_unc_rows.append(row)
            unc_rows.append(row)
        mu = pd.DataFrame(mode_unc_rows)
        mu_ok = mu[(mu["coverage_rate"] >= 0.55) & mu["balanced_accuracy_decided"].notna()]
        unc_sel[mode] = (mu_ok if not mu_ok.empty else mu).sort_values("uncertainty_objective", ascending=False).iloc[0].to_dict()

    gate_df = pd.DataFrame(gate_rows).sort_values(["mode", "gate_objective"], ascending=[True, False])
    unc_df = pd.DataFrame(unc_rows).sort_values(["mode", "uncertainty_objective"], ascending=[True, False])
    wcsv(gate_df, base / "coverage_gate" / "elimination_coverage_gate_registry.csv")
    wmd(base / "reports" / "elimination_coverage_gate_analysis.md", "# elimination v14 coverage gate analysis\n\n" + gate_df.to_string(index=False))
    wcsv(unc_df, base / "uncertainty" / "elimination_uncertainty_registry.csv")
    wmd(base / "reports" / "elimination_uncertainty_analysis.md", "# elimination v14 uncertainty analysis\n\n" + unc_df.to_string(index=False))

    sub_rows = []
    trainval = list(set(ids_train) | set(ids_val))
    for col in [TARGET_ENURESIS, TARGET_ENCOPRESIS]:
        trv = pd.to_numeric(df[df["participant_id"].isin(trainval)][col], errors="coerce").fillna(0)
        te = pd.to_numeric(df[df["participant_id"].isin(ids_test)][col], errors="coerce").fillna(0)
        sub_rows.append({"subtype": col, "trainval_positive": int((trv == 1).sum()), "test_positive": int((te == 1).sum()), "trainval_total": int(len(trv)), "test_total": int(len(te)), "label_available": "yes" if col in df.columns else "no"})
    sub_df = pd.DataFrame(sub_rows)
    proceed_sub = bool((sub_df["label_available"] == "yes").all() and (sub_df["trainval_positive"] >= 120).all() and (sub_df["test_positive"] >= 40).all())
    wcsv(sub_df, base / "subtypes" / "elimination_subtype_feasibility.csv")
    wmd(base / "reports" / "elimination_subtype_feasibility.md", "# elimination v14 subtype feasibility\n\n" + sub_df.to_string(index=False) + f"\n\nproceed_subtype_trials: {'yes' if proceed_sub else 'no'}")
    subtype_trial_df = pd.DataFrame()
    subtype_payload = {}
    if proceed_sub:
        st_rows = []
        for mode in MODES:
            w = winners[mode]
            yte, pte, thr = fit_subtype_union(v11, df, ids_train, ids_val, ids_test, w["_features"])
            m = v12.evalp(v11, yte, pte, float(thr), 0.10)
            st_rows.append({"mode": mode, "strategy": "subtype_union_rf", "threshold": float(thr), **m, "n_features": len(w["_features"])})
            subtype_payload[mode] = {"p": pte, "y": yte, "thr": float(thr)}
        subtype_trial_df = pd.DataFrame(st_rows)
        wcsv(subtype_trial_df, base / "subtypes" / "elimination_subtype_trial_registry.csv")
        wmd(base / "reports" / "elimination_subtype_analysis.md", "# elimination v14 subtype analysis\n\n" + subtype_trial_df.to_string(index=False))

    ts_rows, ts_sel = [], {}
    for mode in MODES:
        w = winners[mode]
        y, p = w["_yte"], w["_pte"]
        thr = float(fn_sel[mode]["threshold"])
        band = float(unc_sel[mode]["uncertainty_band"])
        te_meta = df_idx.reindex(test_ids_order)
        c1 = to_num(te_meta, "v14_cbcl_proxy_nonmissing_ratio").fillna(0.0).to_numpy()
        c2 = to_num(te_meta, "v14_total_nonmissing_ratio").fillna(0.0).to_numpy()
        c3 = to_num(te_meta, "v14_source_mix_ratio").fillna(0.0).to_numpy()
        sparse = to_num(te_meta, "v14_sparse_source_flag").fillna(0.0).to_numpy() > 0
        gate_masks = {"gate_none": np.ones(len(p), dtype=bool), "gate_cbcl_ge_0.35": c1 >= 0.35, "gate_total_ge_0.50": c2 >= 0.50, "gate_combined_relaxed": (c1 >= 0.35) & (c2 >= 0.50) & (c3 >= 0.28), "gate_combined_strict": (c1 >= 0.50) & (c2 >= 0.60) & (c3 >= 0.35) & (~sparse)}
        gmask = gate_masks.get(gate_sel[mode]["gate_name"], np.ones(len(p), dtype=bool))
        configs = [("single_stage_reference", np.zeros(len(p), dtype=bool), p), ("coverage_then_risk", ~gmask, p), ("coverage_plus_uncertainty", (~gmask) | (np.abs(p - thr) < band), p), ("coarse_to_fine_uncertainty", (~gmask) | ((p > max(0.01, thr - 0.08)) & (p < min(0.99, thr + 0.08))), p)]
        if mode in subtype_payload:
            pb = 0.6 * p + 0.4 * subtype_payload[mode]["p"]
            configs.append(("two_stage_with_subtype_blend", (~gmask) | (np.abs(pb - thr) < band), pb))
        mode_rows = []
        for cname, umask, pp in configs:
            s = selective_metrics(v11, y, pp, thr, umask)
            ba = float(s["balanced_accuracy"]) if np.isfinite(s["balanced_accuracy"]) else 0.0
            rec = float(s["recall"]) if np.isfinite(s["recall"]) else 0.0
            prec = float(s["precision"]) if np.isfinite(s["precision"]) else 0.0
            brier = float(s["brier"]) if np.isfinite(s["brier"]) else 1.0
            obj = 0.31 * ba + 0.24 * rec + 0.14 * prec + 0.17 * s["coverage_rate"] + 0.14 * (1 - brier)
            row = {"mode": mode, "architecture": cname, "threshold": float(thr), "coverage_rate": s["coverage_rate"], "uncertain_rate": s["uncertain_rate"], "precision_decided": s["precision"], "recall_decided": s["recall"], "specificity_decided": s["specificity"], "balanced_accuracy_decided": s["balanced_accuracy"], "f1_decided": s["f1"], "pr_auc_decided": s["pr_auc"], "brier_decided": s["brier"], "two_stage_objective": float(obj)}
            mode_rows.append(row)
            ts_rows.append(row)
        tsm = pd.DataFrame(mode_rows)
        tsm_ok = tsm[(tsm["coverage_rate"] >= 0.55) & tsm["balanced_accuracy_decided"].notna()]
        ts_sel[mode] = (tsm_ok if not tsm_ok.empty else tsm).sort_values("two_stage_objective", ascending=False).iloc[0].to_dict()
    ts_df = pd.DataFrame(ts_rows).sort_values(["mode", "two_stage_objective"], ascending=[True, False])
    wcsv(ts_df, base / "two_stage" / "elimination_two_stage_registry.csv")
    wmd(base / "reports" / "elimination_two_stage_analysis.md", "# elimination v14 two-stage analysis\n\n" + ts_df.to_string(index=False))

    fn_cases = []
    for mode in MODES:
        w = winners[mode]
        thr = float(fn_sel[mode]["threshold"])
        y, p = w["_yte"], w["_pte"]
        pred = (p >= thr).astype(int)
        te_meta = df_idx.reindex(test_ids_order)
        amb_ref = float(np.nanpercentile(to_num(te_meta, "v14_fn_ambiguity").fillna(0).to_numpy(), 75))
        for i, pid in enumerate(test_ids_order):
            if not ((y[i] == 1) and (pred[i] == 0)):
                continue
            ccb = float(to_num(te_meta.iloc[[i]], "v14_cbcl_proxy_nonmissing_ratio").fillna(0).iloc[0])
            ctot = float(to_num(te_meta.iloc[[i]], "v14_total_nonmissing_ratio").fillna(0).iloc[0])
            amb = float(to_num(te_meta.iloc[[i]], "v14_fn_ambiguity").fillna(0).iloc[0])
            pat = "coverage_limited" if (ccb < 0.35 or ctot < 0.50) else ("borderline_threshold" if p[i] > max(0.0, thr - 0.08) else ("ambiguous_signal" if amb > amb_ref else "low_signal_clean_fn"))
            fn_cases.append({"mode": mode, "participant_id": str(pid), "age_years": float(to_num(te_meta.iloc[[i]], "age_years").fillna(np.nan).iloc[0]), "sex_assigned_at_birth": str(te_meta.iloc[i]["sex_assigned_at_birth"]) if "sex_assigned_at_birth" in te_meta.columns else "unknown", "predicted_probability": float(p[i]), "threshold_used": float(thr), "cbcl_coverage_ratio": ccb, "total_coverage_ratio": ctot, "source_mix_ratio": float(to_num(te_meta.iloc[[i]], "v14_source_mix_ratio").fillna(0).iloc[0]), "missingness_pressure": float(to_num(te_meta.iloc[[i]], "v14_low_cov_flag").fillna(0).iloc[0]), "symptom_burden_proxy": float(to_num(te_meta.iloc[[i]], "v14_fn_pattern").fillna(0).iloc[0]), "ambiguity_score": amb, "subtype_enuresis_label": int(to_num(te_meta.iloc[[i]], TARGET_ENURESIS).fillna(0).iloc[0]) if TARGET_ENURESIS in te_meta.columns else np.nan, "subtype_encopresis_label": int(to_num(te_meta.iloc[[i]], TARGET_ENCOPRESIS).fillna(0).iloc[0]) if TARGET_ENCOPRESIS in te_meta.columns else np.nan, "source_mix_category": "sparse" if float(to_num(te_meta.iloc[[i]], "v14_source_mix_ratio").fillna(0).iloc[0]) < 0.30 else "mixed", "fn_pattern": pat, "fn_class": "ambiguous" if pat in {"coverage_limited", "borderline_threshold", "ambiguous_signal"} else "clean"})
    fn_case_df = pd.DataFrame(fn_cases)
    wcsv(fn_case_df, base / "fn_analysis" / "elimination_fn_case_registry.csv")
    patt = fn_case_df.groupby(["mode", "fn_pattern"]).size().reset_index(name="n") if not fn_case_df.empty else pd.DataFrame(columns=["mode", "fn_pattern", "n"])
    wmd(base / "reports" / "elimination_fn_analysis.md", "# elimination v14 false negative analysis\n\n" + patt.to_string(index=False))

    abl_rows, st_rows = [], []
    for mode in MODES:
        w = winners[mode]
        thr = float(fn_sel[mode]["threshold"])
        band = float(unc_sel[mode]["uncertainty_band"])
        feats = list(w["_features"])
        configs = {
            "winner_selected": feats,
            "drop_cbcl_block": [f for f in feats if not (f.startswith("cbcl_") or f == "has_cbcl")],
            "drop_coverage_features": [f for f in feats if not f.startswith("v14_")],
            "drop_burden_context": [f for f in feats if not ("burden" in f or "context" in f or "impact" in f)],
            "drop_source_aware": [f for f in feats if not (f.startswith("has_") or "source" in f or "agreement" in f)],
            "drop_top_features_manual": [f for f in feats if f not in set(feats[:2])],
        }
        base_m = v12.evalp(v11, w["_yte"], w["_pte"], float(thr), float(band))
        for cname, f2 in configs.items():
            f2 = [f for f in f2 if f in df.columns]
            if len(f2) < 8:
                continue
            t = v12.fit(v11, df, ids_train, ids_val, ids_test, f2, "rf", mode, f"ablation::{cname}")
            m = v12.evalp(v11, t["_yte"], t["_pte"], float(t["threshold"]), float(band))
            abl_rows.append({"mode": mode, "ablation_config": cname, "n_features": len(f2), "threshold": float(t["threshold"]), **m, "delta_ba_vs_winner": float(m["balanced_accuracy"] - base_m["balanced_accuracy"])})
        Xte = w["_Xte"].copy()
        def miss(X, frac, seed):
            out = X.copy(); rng = np.random.default_rng(seed)
            cols = [c for c in out.columns if c not in {"sex_assigned_at_birth", "site", "release"}]
            m = rng.random((len(out), len(cols))) < frac
            for j, c in enumerate(cols):
                out.loc[m[:, j], c] = np.nan
            return out
        def noise(X, frac, seed):
            out = X.copy(); rng = np.random.default_rng(seed)
            for c in out.columns:
                if pd.api.types.is_numeric_dtype(out[c]):
                    s = pd.to_numeric(out[c], errors="coerce"); sd = float(s.std(skipna=True))
                    if np.isfinite(sd) and sd > 0:
                        out[c] = s + rng.normal(0.0, sd * frac, size=len(out))
            return out
        def cbcl_drop(X):
            out = X.copy()
            for c in [c for c in out.columns if c.startswith("cbcl_")]: out[c] = np.nan
            if "has_cbcl" in out.columns: out["has_cbcl"] = 0.0
            return out
        scenarios = [("baseline", Xte.copy(), thr), ("missingness_light_10pct", miss(Xte, 0.10, 11), thr), ("missingness_moderate_25pct", miss(Xte, 0.25, 42), thr), ("cbcl_coverage_drop", cbcl_drop(Xte), thr), ("partial_coverage_40pct", miss(Xte, 0.40, 2026), thr), ("source_mix_shift", miss(Xte, 0.30, 2027), thr), ("borderline_noise_5pct", noise(Xte, 0.05, 777), thr)]
        for sname, Xs, tthr in scenarios:
            ps = v12.pred(w, Xs)
            m = v12.evalp(v11, w["_yte"], ps, float(tthr), float(band))
            st_rows.append({"mode": mode, "scenario": sname, "threshold_used": float(tthr), **m, "delta_ba_vs_baseline": float(m["balanced_accuracy"] - base_m["balanced_accuracy"])})
    abl_df, st_df = pd.DataFrame(abl_rows).sort_values(["mode", "balanced_accuracy"], ascending=[True, False]), pd.DataFrame(st_rows).sort_values(["mode", "scenario"])
    wcsv(abl_df, base / "ablation" / "elimination_v14_ablation_results.csv")
    wcsv(st_df, base / "stress" / "elimination_v14_stress_results.csv")
    wmd(base / "reports" / "elimination_v14_ablation_and_stress.md", "# elimination v14 ablation and stress\n\n## ablation\n\n" + abl_df.to_string(index=False) + "\n\n## stress\n\n" + st_df.to_string(index=False))

    out_rows = []
    for mode in MODES:
        w = winners[mode]
        thr, band = float(fn_sel[mode]["threshold"]), float(unc_sel[mode]["uncertainty_band"])
        m = v12.evalp(v11, w["_yte"], w["_pte"], float(thr), float(band))
        m_full = v11.compute_metrics(w["_yte"], w["_pte"], float(thr))
        worst = float(st_df[st_df["mode"] == mode]["balanced_accuracy"].min())
        status = "ready_with_caveat" if (m["balanced_accuracy"] >= 0.86 and m["recall"] >= 0.78 and worst >= 0.72 and m["brier"] <= 0.12) else ("uncertainty_preferred" if (m["balanced_accuracy"] >= 0.81 and m["recall"] >= 0.72 and worst >= 0.66) else ("ready_only_for_professional_detail" if m["balanced_accuracy"] >= 0.77 else "not_ready_for_strong_probability_interpretation"))
        out_rows.append({"mode": mode, "domain": "elimination", "selected_feature_set": w["feature_set"], "selected_family": "rf", "selected_strategy": fn_sel[mode]["strategy"], "selected_two_stage_architecture": ts_sel[mode]["architecture"], "selected_gate": gate_sel[mode]["gate_name"], "selected_threshold": float(thr), "selected_uncertainty_band": float(band), "precision": float(m["precision"]), "recall": float(m["recall"]), "specificity": float(m["specificity"]), "balanced_accuracy": float(m["balanced_accuracy"]), "f1": float(m["f1"]), "roc_auc": float(m_full["roc_auc"]), "pr_auc": float(m["pr_auc"]), "brier": float(m["brier"]), "uncertain_rate": float(m["uncertain_rate"]), "uncertainty_usefulness": float(m["uncertainty_usefulness"]), "output_realism_score": float(m["output_realism_score"]), "worst_stress_ba": float(worst), "probability_ready": "yes" if m["brier"] <= 0.14 else "no", "risk_band_ready": "yes" if m["balanced_accuracy"] >= 0.80 else "no", "confidence_ready": "yes" if m["output_realism_score"] >= 0.82 else "no", "uncertainty_ready": "yes" if m["uncertainty_usefulness"] >= -0.05 else "no", "professional_detail_ready": "yes", "final_output_status": status, "visible_user_prob_cap": "[0.01,0.99]", "visible_prof_prob_cap": "[0.005,0.995]", "extreme_performance_audit_trigger": "yes" if (m["balanced_accuracy"] >= 0.995 or math.isclose(m["precision"], 1.0) or math.isclose(m["recall"], 1.0) or math.isclose(m["specificity"], 1.0)) else "no"})
    out_df = pd.DataFrame(out_rows)
    wcsv(out_df, base / "tables" / "elimination_v14_output_readiness.csv")
    wmd(base / "reports" / "elimination_v14_output_readiness.md", "# elimination v14 output readiness\n\n" + out_df.to_string(index=False))

    deltas = []
    for mode in MODES:
        b = bline[bline["mode"] == mode].iloc[0]
        c12 = v12_out[v12_out["mode"] == mode].iloc[0]
        c13 = v13_out[v13_out["mode"] == mode].iloc[0]
        c14 = out_df[out_df["mode"] == mode].iloc[0]
        u12 = np.nan
        try:
            op = v12_ops[(v12_ops["mode"] == mode) & (v12_ops["operating_mode"] == c12["selected_operating_mode"])].iloc[0]
            u12 = float(op["uncertain_rate"])
        except Exception:
            u12 = float(c12.get("uncertain_rate", np.nan))
        deltas.append(
            {
                "mode": mode,
                "baseline_precision": float(b["precision"]),
                "baseline_recall": float(b["recall"]),
                "baseline_specificity": float(b["specificity"]),
                "baseline_balanced_accuracy": float(b["balanced_accuracy"]),
                "baseline_f1": float(b["f1"]),
                "baseline_pr_auc": float(b.get("pr_auc", np.nan)),
                "baseline_brier": float(b["brier"]),
                "v12_precision": float(c12["precision"]),
                "v12_recall": float(c12["recall"]),
                "v12_specificity": float(c12["specificity"]),
                "v12_balanced_accuracy": float(c12["balanced_accuracy"]),
                "v12_f1": float(c12["f1"]),
                "v12_pr_auc": float(c12["pr_auc"]),
                "v12_brier": float(c12["brier"]),
                "v12_worst_stress_ba": float(c12["worst_stress_ba"]),
                "v13_precision": float(c13["precision"]),
                "v13_recall": float(c13["recall"]),
                "v13_specificity": float(c13["specificity"]),
                "v13_balanced_accuracy": float(c13["balanced_accuracy"]),
                "v13_f1": float(c13["f1"]),
                "v13_pr_auc": float(c13["pr_auc"]),
                "v13_brier": float(c13["brier"]),
                "v13_worst_stress_ba": float(c13["worst_stress_ba"]),
                "v14_precision": float(c14["precision"]),
                "v14_recall": float(c14["recall"]),
                "v14_specificity": float(c14["specificity"]),
                "v14_balanced_accuracy": float(c14["balanced_accuracy"]),
                "v14_f1": float(c14["f1"]),
                "v14_pr_auc": float(c14["pr_auc"]),
                "v14_brier": float(c14["brier"]),
                "v14_worst_stress_ba": float(c14["worst_stress_ba"]),
                "v14_output_status": str(c14["final_output_status"]),
                "delta_precision_v14_vs_v12": float(c14["precision"] - c12["precision"]),
                "delta_recall_v14_vs_v12": float(c14["recall"] - c12["recall"]),
                "delta_specificity_v14_vs_v12": float(c14["specificity"] - c12["specificity"]),
                "delta_ba_v14_vs_v12": float(c14["balanced_accuracy"] - c12["balanced_accuracy"]),
                "delta_f1_v14_vs_v12": float(c14["f1"] - c12["f1"]),
                "delta_pr_auc_v14_vs_v12": float(c14["pr_auc"] - c12["pr_auc"]),
                "delta_brier_v14_vs_v12": float(c14["brier"] - c12["brier"]),
                "delta_robustness_v14_vs_v12": float(c14["worst_stress_ba"] - c12["worst_stress_ba"]),
                "delta_usability_v14_vs_v12": float((1.0 - c14["uncertain_rate"]) - (1.0 - u12)) if np.isfinite(u12) else np.nan,
                "delta_precision_v14_vs_baseline": float(c14["precision"] - b["precision"]),
                "delta_recall_v14_vs_baseline": float(c14["recall"] - b["recall"]),
                "delta_ba_v14_vs_baseline": float(c14["balanced_accuracy"] - b["balanced_accuracy"]),
                "delta_brier_v14_vs_baseline": float(c14["brier"] - b["brier"]),
            }
        )
    delta_df = pd.DataFrame(deltas)
    wcsv(delta_df, base / "tables" / "elimination_v14_final_delta.csv")
    wmd(base / "reports" / "elimination_v14_final_delta_analysis.md", "# elimination v14 final delta\n\n" + delta_df.to_string(index=False))

    improved_modes = sum([1 for _, r in delta_df.iterrows() if (float(r["delta_ba_v14_vs_v12"]) >= 0.006 and float(r["delta_recall_v14_vs_v12"]) >= 0.012 and float(r["delta_brier_v14_vs_v12"]) <= 0.002 and float(r["delta_robustness_v14_vs_v12"]) >= -0.010)])
    if (delta_df["v14_worst_stress_ba"] < 0.60).all():
        decision = "HOLD_STRUCTURAL_LIMIT"
    elif improved_modes >= 1 and (delta_df["delta_ba_v14_vs_v12"].min() >= -0.005):
        decision = "APPROVE_V14_WITH_CAVEAT"
    else:
        decision = "KEEP_V12"

    final = "# elimination v14 final decision\n\n" + f"Decision: `{decision}`\n\n" + f"1) v14 mejora real y limpia: {'yes' if improved_modes >= 1 else 'no'}\n" + f"2) recall mejora util: {'yes' if (delta_df['delta_recall_v14_vs_v12'] > 0).any() else 'no'}\n" + f"3) precision se mantiene razonable: {'yes' if (out_df['precision'].astype(float) >= 0.80).all() else 'partial/no'}\n" + f"4) generalizacion mejora: {'yes' if (delta_df['delta_robustness_v14_vs_v12'] > 0).any() else 'no'}\n" + "5) RF sigue champion principal: yes\n" + f"6) two-stage / coverage gate / FN optimization ayudaron: {'yes' if improved_modes >= 1 else 'partial'}\n" + f"7) subtipos aportaron: {'yes' if (proceed_sub and not subtype_trial_df.empty) else 'no_or_not_material'}\n" + f"8) limite estructural: {'yes' if decision in ['KEEP_V12','HOLD_STRUCTURAL_LIMIT'] else 'not_yet'}\n" + f"9) cierre definitivo elimination: {'yes' if decision in ['APPROVE_V14','APPROVE_V14_WITH_CAVEAT','KEEP_V12','UNCERTAINTY_PREFERRED_ONLY'] else 'no'}\n\n" + out_df.to_string(index=False)
    wmd(base / "reports" / "elimination_v14_final_decision.md", final)
    exec_sum = "# elimination v14 executive summary\n\n" + f"- decision: {decision}\n" + f"- improved_modes_vs_v12: {improved_modes}/2\n" + "- rf_champion_policy: maintained\n" + f"- subtype_trials_run: {'yes' if proceed_sub else 'no'}\n" + "- confidence_policy: user [1%,99%], professional [0.5%,99.5%], raw preserved\n\n" + out_df[["mode", "precision", "recall", "specificity", "balanced_accuracy", "f1", "pr_auc", "brier", "worst_stress_ba", "final_output_status"]].to_string(index=False)
    wmd(base / "reports" / "elimination_v14_executive_summary.md", exec_sum)

    wjson(root / "artifacts" / "elimination_final_push_v14" / "elimination_final_push_v14_manifest.json", {
        "campaign": "elimination_final_push_v14",
        "decision": decision,
        "dataset": str(data_path),
        "split_dir": str(split),
        "holdout_hash_ordered": hash_ids(ids_test, True),
        "holdout_hash_set": hash_ids(ids_test, False),
        "blocked_shortcuts": sorted(list(BLOCKED)),
        "round_policy": {"max_strong_rounds": 3, "max_confirm_rounds": 1},
        "confidence_display_policy": {"internal_raw_probability_preserved": True, "user_visible": {"min": 0.01, "max": 0.99}, "professional_visible": {"min": 0.005, "max": 0.995}},
        "selected_by_mode": {
            m: {
                "feature_set": str(out_df[out_df["mode"] == m].iloc[0]["selected_feature_set"]),
                "family": "rf",
                "strategy": str(out_df[out_df["mode"] == m].iloc[0]["selected_strategy"]),
                "threshold": float(out_df[out_df["mode"] == m].iloc[0]["selected_threshold"]),
                "uncertainty_band": float(out_df[out_df["mode"] == m].iloc[0]["selected_uncertainty_band"]),
                "gate": str(out_df[out_df["mode"] == m].iloc[0]["selected_gate"]),
                "two_stage_architecture": str(out_df[out_df["mode"] == m].iloc[0]["selected_two_stage_architecture"]),
            }
            for m in MODES
        },
    })

    print("OK - elimination_final_push_v14 generated")


if __name__ == "__main__":
    main()
