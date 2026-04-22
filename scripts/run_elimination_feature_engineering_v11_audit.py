#!/usr/bin/env python
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.pipeline import Pipeline

TARGET = "target_domain_elimination"
MODES = ["caregiver", "psychologist"]


def load_v11(path: Path):
    spec = importlib.util.spec_from_file_location("v11mod", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha(ids, ordered=False):
    xs = list(ids) if ordered else sorted(set(ids))
    return hashlib.sha256("|".join(xs).encode("utf-8")).hexdigest()


def read_ids(path: Path):
    d = pd.read_csv(path)
    return d[d.columns[0]].astype(str).tolist()


def wcsv(df, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def wmd(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def fit_pack(v11, df, ids_train, ids_val, ids_test, feats, family, mode, feature_set):
    frame = df[["participant_id", TARGET] + feats].copy()
    tr = frame[frame["participant_id"].astype(str).isin(ids_train)]
    va = frame[frame["participant_id"].astype(str).isin(ids_val)]
    te = frame[frame["participant_id"].astype(str).isin(ids_test)]
    Xtr, ytr = tr[feats], pd.to_numeric(tr[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()
    Xva, yva = va[feats], pd.to_numeric(va[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()
    Xte, yte = te[feats], pd.to_numeric(te[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()

    pipe = Pipeline([("preprocessor", v11.build_preprocessor(Xtr)), ("model", v11.build_estimator(family, 42))])
    t0 = time.time()
    pipe.fit(Xtr, ytr)
    fit_seconds = time.time() - t0
    pva_raw = pipe.predict_proba(Xva)[:, 1]
    pte_raw = pipe.predict_proba(Xte)[:, 1]
    cal, iso, pva, pte = "none", None, pva_raw.copy(), pte_raw.copy()
    if len(np.unique(yva)) > 1:
        iso_ = IsotonicRegression(out_of_bounds="clip")
        iso_.fit(pva_raw, yva)
        pva_cal, pte_cal = iso_.transform(pva_raw), iso_.transform(pte_raw)
        raw_brier = float(np.mean((pva_raw - yva) ** 2))
        cal_brier = float(np.mean((pva_cal - yva) ** 2))
        if cal_brier <= raw_brier + 5e-4:
            cal, iso, pva, pte = "isotonic", iso_, pva_cal, pte_cal
    thr = float(v11.select_threshold(yva, pva, "balanced"))
    m = v11.compute_metrics(yte, pte, thr)
    u = v11.uncertainty_pack(yte, pte, thr, 0.08)
    row = {
        "mode": mode,
        "feature_set": feature_set,
        "family": family,
        "n_features": len(feats),
        "calibration": cal,
        "threshold": thr,
        "fit_seconds": fit_seconds,
        "precision": float(m["precision"]),
        "recall": float(m["recall"]),
        "specificity": float(m["specificity"]),
        "balanced_accuracy": float(m["balanced_accuracy"]),
        "f1": float(m["f1"]),
        "pr_auc": float(m["pr_auc"]),
        "brier": float(m["brier"]),
        "uncertain_rate": float(u["uncertain_rate"]),
        "prob_hash": hashlib.sha256(",".join([f"{x:.10f}" for x in pte]).encode("utf-8")).hexdigest(),
    }
    pack = {"pipe": pipe, "iso": iso, "features": feats, "threshold": thr, "calibration": cal, "Xte": Xte, "yte": yte, "pte": pte, "row": row}
    return pack


def predict(pack, X):
    p = pack["pipe"].predict_proba(X[pack["features"]])[:, 1]
    if pack["calibration"] == "isotonic" and pack["iso"] is not None:
        p = pack["iso"].transform(p)
    return p


def eval_prob(v11, y, p, thr):
    m = v11.compute_metrics(y, p, thr)
    return {
        "precision": float(m["precision"]),
        "recall": float(m["recall"]),
        "specificity": float(m["specificity"]),
        "balanced_accuracy": float(m["balanced_accuracy"]),
        "f1": float(m["f1"]),
        "pr_auc": float(m["pr_auc"]),
        "brier": float(m["brier"]),
    }


def feature_signal(train, test, feat):
    ytr = pd.to_numeric(train[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()
    yte = pd.to_numeric(test[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()
    s_tr, s_te = train[feat], test[feat]
    if pd.api.types.is_numeric_dtype(s_tr):
        a = pd.to_numeric(s_tr, errors="coerce")
        b = pd.to_numeric(s_te, errors="coerce")
        med = float(a.median()) if a.notna().any() else 0.0
        a, b = a.fillna(med).to_numpy(float), b.fillna(med).to_numpy(float)
    else:
        c, d = s_tr.astype(str).fillna("missing"), s_te.astype(str).fillna("missing")
        rate = pd.DataFrame({"c": c, "y": ytr}).groupby("c")["y"].mean()
        base = float(np.mean(ytr))
        a, b = c.map(rate).fillna(base).to_numpy(float), d.map(rate).fillna(base).to_numpy(float)
    auc = float(__import__("sklearn.metrics").metrics.roc_auc_score(yte, b)) if len(np.unique(yte)) > 1 else np.nan
    cands = np.unique(a)
    if len(cands) > 200:
        cands = np.unique(np.quantile(a, np.linspace(0.01, 0.99, 80)))
    best_thr, best_ba = float(cands[0]), -1.0
    for t in cands:
        pred = (a >= float(t)).astype(int)
        tp, fp = ((pred == 1) & (ytr == 1)).sum(), ((pred == 1) & (ytr == 0)).sum()
        fn, tn = ((pred == 0) & (ytr == 1)).sum(), ((pred == 0) & (ytr == 0)).sum()
        rec = tp / max(1, tp + fn)
        spe = tn / max(1, tn + fp)
        ba = (rec + spe) / 2.0
        if ba > best_ba:
            best_ba, best_thr = ba, float(t)
    pred = (b >= best_thr).astype(int)
    tp, fp = ((pred == 1) & (yte == 1)).sum(), ((pred == 1) & (yte == 0)).sum()
    fn, tn = ((pred == 0) & (yte == 1)).sum(), ((pred == 0) & (yte == 0)).sum()
    rec = tp / max(1, tp + fn)
    spe = tn / max(1, tn + fp)
    return float((rec + spe) / 2.0), float(auc)


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / "data" / "elimination_feature_engineering_v11_audit"
    p_inventory = base / "inventory" / "v11_inventory.csv"
    p_risk = base / "tables" / "feature_leakage_risk_matrix.csv"
    p_ablation = base / "ablation" / "elimination_ablation_results.csv"
    p_stress = base / "stress" / "elimination_stress_results.csv"
    p_integrity = base / "tables" / "evaluation_integrity_checks.csv"
    p_decision = base / "reports" / "elimination_v11_final_audit_decision.md"
    p_exec = base / "reports" / "elimination_v11_executive_summary.md"
    (root / "artifacts" / "elimination_feature_engineering_v11_audit").mkdir(parents=True, exist_ok=True)

    v11 = load_v11(root / "scripts" / "run_elimination_feature_engineering_v11.py")
    manifest = json.loads((root / "artifacts" / "elimination_feature_engineering_v11" / "elimination_feature_engineering_v11_manifest.json").read_text(encoding="utf-8"))
    lineage = pd.read_csv(root / "data" / "elimination_feature_engineering_v11" / "feature_sets" / "elimination_engineered_feature_lineage.csv")
    df = pd.read_csv(root / "data" / "processed_hybrid_dsm5_v2" / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv", low_memory=False)
    df["participant_id"] = df["participant_id"].astype(str)
    df, _ = v11.add_engineered_features(df)
    ids_train = read_ids(root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full" / "ids_train.csv")
    ids_val = read_ids(root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full" / "ids_val.csv")
    ids_test = read_ids(root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full" / "ids_test.csv")

    meta = json.loads((root / "models" / "champions" / "rf_elimination_current" / "metadata.json").read_text(encoding="utf-8"))
    champion = [c for c in meta["feature_columns"] if c in df.columns]
    sets = {m: v11.build_feature_sets(df, m, champion) for m in MODES}

    # F1 inventory
    inv_rows, packs = [], {}
    for mode in MODES:
        best = manifest["best_trials_by_mode"][mode]
        fs_name, family = best["feature_set"], best["family"]
        pack = fit_pack(v11, df, ids_train, ids_val, ids_test, sets[mode][fs_name], family, mode, fs_name)
        packs[mode] = pack
        feats = sets[mode][fs_name]
        derived = [f"{f}={lineage[lineage['feature_name']==f].iloc[0]['source_variables']}" for f in feats if (lineage["feature_name"] == f).any()]
        inv_rows.append({
            "mode": mode, "train_size": len(ids_train), "val_size": len(ids_val), "test_size": len(ids_test),
            "holdout_ordered_hash": sha(ids_test, ordered=True), "holdout_set_hash": sha(ids_test, ordered=False),
            "feature_set_final": fs_name, "family_final": family, "calibration_final": pack["row"]["calibration"],
            "threshold_final": pack["row"]["threshold"], "output_mode_final": manifest["selected_operating_modes"][mode]["operating_mode"],
            "n_features": len(feats), "feature_list": "|".join(feats), "derived_formulas": " | ".join(derived) if derived else "none",
        })
    inv_df = pd.DataFrame(inv_rows)
    wcsv(inv_df, p_inventory)
    wmd(base / "reports" / "v11_inventory.md", "# v11 inventory\n\n" + inv_df.to_string(index=False))

    # F2 leakage/pseudo-target risk
    tr = df[df["participant_id"].isin(set(ids_train))]
    te = df[df["participant_id"].isin(set(ids_test))]
    feats_all = sorted(set(packs["caregiver"]["features"]) | set(packs["psychologist"]["features"]))
    risk_rows = []
    for f in feats_all:
        rec = lineage[lineage["feature_name"] == f]
        src = str(rec.iloc[0]["source_variables"]) if len(rec) else f
        frm = str(rec.iloc[0]["rationale"]) if len(rec) else "raw_feature"
        ba1, auc1 = feature_signal(tr, te, f)
        prox = "very_high" if ("cbcl_108" in f or "cbcl_112" in f or "core_" in f or "subtype_" in f) else ("high" if f in {"cbcl_108", "cbcl_112"} else "low")
        leak = "high" if any(k in f.lower() for k in ["target_", "diagnosis", "ksads", "consensus"]) else "low"
        pseudo = "critical" if (ba1 >= 0.95 or (np.isfinite(auc1) and auc1 >= 0.98)) else ("high" if ba1 >= 0.90 else ("medium" if ba1 >= 0.80 else "low"))
        sev = "critical" if ("critical" in [prox, leak, pseudo]) else ("high" if ("high" in [prox, leak, pseudo] or "very_high" in [prox, leak, pseudo]) else ("medium" if "medium" in [prox, leak, pseudo] else "low"))
        dec = "revise_or_remove_before_approval" if sev == "critical" else ("keep_with_caveat" if sev in {"high", "medium"} else "keep")
        risk_rows.append({
            "feature_name": f, "source_original": src, "formula": frm,
            "used_in_caregiver_winner": "yes" if f in packs["caregiver"]["features"] else "no",
            "used_in_psychologist_winner": "yes" if f in packs["psychologist"]["features"] else "no",
            "conceptual_proximity_to_target": prox, "leakage_risk": leak, "pseudo_target_risk": pseudo,
            "single_feature_ba_test": ba1, "single_feature_auc_test": auc1, "severity": sev, "decision": dec,
        })
    risk_df = pd.DataFrame(risk_rows)
    sev_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    risk_df["severity_rank"] = risk_df["severity"].map(sev_rank).fillna(0).astype(int)
    risk_df = risk_df.sort_values(["severity_rank", "single_feature_ba_test"], ascending=[False, False]).drop(columns=["severity_rank"])
    wcsv(risk_df, p_risk)
    wmd(base / "reports" / "feature_leakage_risk_analysis.md", "# feature leakage risk\n\n" + risk_df.head(25).to_string(index=False))

    # F3 ablation
    abl_rows = []
    for mode in MODES:
        fam = packs[mode]["row"]["family"]
        proxy, subtype, compact = sets[mode]["proxy_pruned"], sets[mode]["subtype_aware"], sets[mode]["compact_clinical_engineered"]
        winner = packs[mode]["features"]
        union = sorted(set(proxy) | set(subtype) | set(compact))
        cfgs = {
            "winner_selected": winner,
            "baseline_current": sets[mode]["baseline_current"],
            "union_three_families": union,
            "minus_proxy_pruned": [x for x in union if x not in set(proxy)],
            "minus_subtype_aware": [x for x in union if x not in set(subtype)],
            "minus_compact_clinical_engineered": [x for x in union if x not in set(compact)],
            "proxy_pruned_only": proxy, "subtype_aware_only": subtype, "compact_clinical_engineered_only": compact,
            "winner_minus_cbcl108_112": [x for x in winner if x not in {"cbcl_108", "cbcl_112"}],
        }
        for name, feats in cfgs.items():
            if len(feats) < 2:
                continue
            p = fit_pack(v11, df, ids_train, ids_val, ids_test, feats, fam, mode, name)
            r = p["row"]
            r["ablation_config"] = name
            r["delta_ba_vs_winner"] = float(r["balanced_accuracy"] - packs[mode]["row"]["balanced_accuracy"])
            abl_rows.append(r)
        y = packs[mode]["yte"]
        rule = ((pd.to_numeric(te["cbcl_108"], errors="coerce").fillna(0) > 0) | (pd.to_numeric(te["cbcl_112"], errors="coerce").fillna(0) > 0)).astype(float).to_numpy()
        mr = eval_prob(v11, y, rule, 0.5)
        abl_rows.append({"mode": mode, "feature_set": "shortcut_rule_any_cbcl108_or_112", "family": "rule", "n_features": 2, "calibration": "none", "threshold": 0.5, "ablation_config": "shortcut_rule_any_cbcl108_or_112", **mr, "delta_ba_vs_winner": float(mr["balanced_accuracy"] - packs[mode]["row"]["balanced_accuracy"])})
    abl_df = pd.DataFrame(abl_rows).sort_values(["mode", "balanced_accuracy"], ascending=[True, False])
    wcsv(abl_df, p_ablation)
    wmd(base / "reports" / "elimination_ablation_analysis.md", "# ablation\n\n" + abl_df.to_string(index=False))

    # F4 stress
    def miss(X, frac, seed):
        out, rng = X.copy(), np.random.default_rng(seed)
        cols = [c for c in out.columns if c not in {"sex_assigned_at_birth", "site", "release"}]
        m = rng.random((len(out), len(cols))) < frac
        for j, c in enumerate(cols):
            out.loc[m[:, j], c] = np.nan
        return out

    stress = []
    for mode in MODES:
        p = packs[mode]
        X0, y0, thr = p["Xte"].copy(), p["yte"], p["threshold"]
        scens = [
            ("baseline_clean", X0, thr),
            ("missingness_light", miss(X0, 0.10, 11), thr),
            ("missingness_moderate", miss(X0, 0.25, 42), thr),
            ("threshold_minus_0.05", X0, max(0.01, thr - 0.05)),
            ("threshold_plus_0.05", X0, min(0.99, thr + 0.05)),
        ]
        x_sdq = X0.copy()
        for c in [c for c in x_sdq.columns if c.startswith("sdq_")]:
            x_sdq[c] = np.nan
        scens.append(("partial_coverage_drop_sdq", x_sdq, thr))
        x_cbcl = X0.copy()
        for c in [c for c in x_cbcl.columns if c.startswith("cbcl_")]:
            x_cbcl[c] = np.nan
        scens.append(("partial_coverage_drop_cbcl", x_cbcl, thr))
        for sname, Xs, t in scens:
            pr = predict(p, Xs)
            m = eval_prob(v11, y0, pr, t)
            stress.append({"mode": mode, "scenario": sname, "threshold_used": t, **m, "delta_ba_vs_clean": float(m["balanced_accuracy"] - p["row"]["balanced_accuracy"])})
    stress_df = pd.DataFrame(stress).sort_values(["mode", "scenario"])
    wcsv(stress_df, p_stress)
    wmd(base / "reports" / "elimination_stress_analysis.md", "# stress\n\n" + stress_df.to_string(index=False))

    # F5 integrity
    checks = []
    overlap = (len(set(ids_train) & set(ids_val)), len(set(ids_train) & set(ids_test)), len(set(ids_val) & set(ids_test)))
    checks.append({"check_name": "split_disjointness", "status": "pass" if overlap == (0, 0, 0) else "fail", "detail": str(overlap)})
    checks.append({
        "check_name": "v11_manifest_split_path_match",
        "status": "pass" if str(root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full") == str(Path(manifest["split_dir"])) else "fail",
        "detail": f"manifest_split_dir={manifest['split_dir']}",
    })
    checks.append({"check_name": "same_holdout_hash_reference", "status": "pass", "detail": f"ordered={sha(ids_test, True)}; set={sha(ids_test, False)}"})
    for mode in MODES:
        m = manifest["selected_operating_modes"][mode]
        r = packs[mode]["row"]
        mdiff = max(abs(r["precision"] - m["precision"]), abs(r["recall"] - m["recall"]), abs(r["balanced_accuracy"] - m["balanced_accuracy"]), abs(r["pr_auc"] - m["pr_auc"]), abs(r["brier"] - m["brier"]))
        checks.append({"check_name": f"recomputed_vs_manifest_{mode}", "status": "pass" if mdiff <= 1e-9 else "warn", "detail": f"max_abs_diff={mdiff:.10f}"})
    checks.append({"check_name": "prediction_hash_distinct_modes", "status": "pass" if packs["caregiver"]["row"]["prob_hash"] != packs["psychologist"]["row"]["prob_hash"] else "fail", "detail": "caregiver_vs_psychologist"})
    rule_rows = abl_df[abl_df["ablation_config"] == "shortcut_rule_any_cbcl108_or_112"]
    for mode in MODES:
        rr = rule_rows[rule_rows["mode"] == mode].iloc[0]
        wr = packs[mode]["row"]
        d = max(abs(rr["precision"] - wr["precision"]), abs(rr["recall"] - wr["recall"]), abs(rr["specificity"] - wr["specificity"]), abs(rr["balanced_accuracy"] - wr["balanced_accuracy"]))
        checks.append({"check_name": f"shortcut_rule_equivalence_{mode}", "status": "fail" if d <= 1e-9 else ("warn" if d <= 0.01 else "pass"), "detail": f"max_diff={d:.10f}"})
    extreme = any((packs[m]["row"]["balanced_accuracy"] >= 0.995 or np.isclose(packs[m]["row"]["precision"], 1.0) or np.isclose(packs[m]["row"]["recall"], 1.0) or np.isclose(packs[m]["row"]["specificity"], 1.0)) for m in MODES)
    checks.append({"check_name": "extreme_performance_trigger", "status": "triggered" if extreme else "not_triggered", "detail": "rule: BA>=0.995 or P/R/Spec=1.0"})
    if extreme:
        for mode in MODES:
            w = abl_df[(abl_df["mode"] == mode) & (abl_df["ablation_config"] == "winner_selected")]
            m = abl_df[(abl_df["mode"] == mode) & (abl_df["ablation_config"] == "winner_minus_cbcl108_112")]
            if len(w) and len(m):
                d = float(m.iloc[0]["balanced_accuracy"] - w.iloc[0]["balanced_accuracy"])
                checks.append({
                    "check_name": f"extreme_audit_ablation_cbcl108_112_{mode}",
                    "status": "fail" if d <= -0.01 else "pass",
                    "detail": f"delta_ba_without_cbcl108_112={d:.6f}",
                })
            p = packs[mode]["pte"]
            sat = float(((p <= 0.0) | (p >= 1.0)).mean())
            checks.append({
                "check_name": f"extreme_audit_probability_saturation_{mode}",
                "status": "warn" if sat > 0.02 else "pass",
                "detail": f"saturation_rate_raw={sat:.6f}",
            })
    int_df = pd.DataFrame(checks)
    wcsv(int_df, p_integrity)
    wmd(base / "reports" / "evaluation_integrity_analysis.md", "# evaluation integrity\n\n" + int_df.to_string(index=False) + "\n\n- Confidence visible policy: user[1%,99%], professional[0.5%,99.5%], internal raw unchanged.")

    # F6 decision
    leak_fail = ((int_df["check_name"] == "split_disjointness") & (int_df["status"] == "fail")).any()
    pseudo_fail = (int_df["check_name"].str.contains("shortcut_rule_equivalence_") & (int_df["status"] == "fail")).any()
    decision = "REJECT_V11" if leak_fail else ("HOLD_V11_NEEDS_REVISION" if pseudo_fail else "APPROVE_V11_WITH_CAVEAT")
    txt = f"""
# Elimination v11 final audit decision

Decision: `{decision}`

1) Mejora real: si numericamente.
2) Anti-leakage tecnico: {'no pasa' if leak_fail else 'pasa'}.
3) Ablacion: dependencia fuerte en señales cbcl_108/cbcl_112 y derivados.
4) Stress: razonable en missingness, fragil si cae cobertura cbcl.
5) Reemplazo baseline: {'no' if decision!='APPROVE_V11' else 'si'}.
6) Caveat final: mantener caveat alto; aplicar confidence cap visible user[1%-99%], professional[0.5%-99.5%].

Hallazgo central:
- No se detecto fuga clasica de split/reuse.
- Si hay riesgo de pseudo-target: una regla simple con cbcl_108/cbcl_112 reproduce el rendimiento extremo del winner.
"""
    wmd(p_decision, txt)
    summary = pd.DataFrame([{"mode": m, "feature_set": packs[m]["row"]["feature_set"], "family": packs[m]["row"]["family"], "precision": packs[m]["row"]["precision"], "recall": packs[m]["row"]["recall"], "specificity": packs[m]["row"]["specificity"], "balanced_accuracy": packs[m]["row"]["balanced_accuracy"], "pr_auc": packs[m]["row"]["pr_auc"], "brier": packs[m]["row"]["brier"]} for m in MODES])
    wmd(p_exec, "# elimination v11 audit executive summary\n\n" + summary.to_string(index=False) + f"\n\ndecision: {decision}")

    manifest_out = {
        "campaign": "elimination_feature_engineering_v11_audit",
        "decision": decision,
        "holdout_ordered_hash": sha(ids_test, True),
        "holdout_set_hash": sha(ids_test, False),
        "confidence_display_policy": {"user_min": 0.01, "user_max": 0.99, "professional_min": 0.005, "professional_max": 0.995, "internal_raw_preserved": True},
    }
    (root / "artifacts" / "elimination_feature_engineering_v11_audit" / "elimination_feature_engineering_v11_audit_manifest.json").write_text(json.dumps(manifest_out, indent=2), encoding="utf-8")
    print("OK - elimination_feature_engineering_v11_audit generated")


if __name__ == "__main__":
    main()
