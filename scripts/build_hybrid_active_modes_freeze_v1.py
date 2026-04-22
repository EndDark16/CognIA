import hashlib
import json
from pathlib import Path

import pandas as pd

B = Path("data/hybrid_active_modes_freeze_v1")
A = Path("artifacts/hybrid_active_modes_freeze_v1")
for d in ["tables", "reports"]:
    (B / d).mkdir(parents=True, exist_ok=True)
A.mkdir(parents=True, exist_ok=True)

OP = Path("data/hybrid_operational_freeze_v1")
V2 = Path("data/hybrid_no_external_scores_rebuild_v2")
V3 = Path("data/hybrid_no_external_scores_boosted_v3")
RB = Path("data/hybrid_dsm5_rebuild_v1")
FF = Path("data/hybrid_final_freeze_v1")


def yn(v, default="no"):
    s = str(v).strip().lower()
    if s in {"yes", "si", "true", "1"}:
        return "yes"
    if s in {"no", "false", "0"}:
        return "no"
    return default


def role(mode):
    return "caregiver" if str(mode).startswith("caregiver") else "psychologist"


def cfgid(cfg):
    if pd.isna(cfg) or str(cfg).strip() == "":
        return "cfg_unknown"
    return "cfg_" + hashlib.md5(str(cfg).encode("utf-8")).hexdigest()[:10]


def conf_score(r):
    def n(x, lo, hi):
        x = float(x)
        if x <= lo:
            return 0.0
        if x >= hi:
            return 1.0
        return (x - lo) / (hi - lo)

    s = 0.0
    s += 18 * n(r["precision"], 0.5, 0.95)
    s += 14 * n(r["recall"], 0.5, 0.95)
    s += 22 * n(r["balanced_accuracy"], 0.5, 0.98)
    s += 22 * n(r["pr_auc"], 0.5, 0.98)
    s += 10 * n(0.12 - float(r["brier"]), 0, 0.12)
    s += {"muy_bueno": 10, "bueno": 7, "aceptable": 4, "malo": 0}.get(str(r["quality_label"]).lower(), 0)
    s += {"ROBUST_PRIMARY": 8, "PRIMARY_WITH_CAVEAT": 2, "HOLD_FOR_LIMITATION": -8, "SUSPECT_EASY_DATASET_NEEDS_CAUTION": -4}.get(
        str(r["src_class"]), 0
    )
    if r["overfit_flag"] == "yes":
        s -= 12
    if r["generalization_flag"] == "no":
        s -= 10
    if r["dataset_ease_flag"] == "yes":
        s -= 8
    return round(max(0, min(100, s)), 1)


def conf_band(x):
    if x >= 85:
        return "high"
    if x >= 70:
        return "moderate"
    if x >= 55:
        return "low"
    return "limited"


def op_class(r):
    if r["src_class"] == "HOLD_FOR_LIMITATION" or r["confidence_band"] == "limited":
        return "ACTIVE_LIMITED_USE"
    if r["dataset_ease_flag"] == "yes" and r["confidence_band"] == "high":
        return "ACTIVE_MODERATE_CONFIDENCE"
    if r["confidence_band"] == "high":
        return "ACTIVE_HIGH_CONFIDENCE"
    if r["confidence_band"] == "moderate":
        return "ACTIVE_MODERATE_CONFIDENCE"
    return "ACTIVE_LOW_CONFIDENCE"


op = pd.read_csv(OP / "tables/hybrid_operational_final_champions.csv")
v2 = pd.read_csv(V2 / "tables/hybrid_no_external_scores_final_models.csv")
v3 = pd.read_csv(V3 / "tables/hybrid_no_external_scores_boosted_final_ranked_models.csv")
over = pd.read_csv(OP / "validation/hybrid_operational_overfit_audit.csv")
gen = pd.read_csv(OP / "validation/hybrid_operational_generalization_audit.csv")
v3_inv = pd.read_csv(V3 / "inventory/hybrid_no_external_scores_boosted_inventory.csv")
v3_seed = int(v3_inv["seed_base"].iloc[0]) if "seed_base" in v3_inv.columns else 20270413

v2i = {(r.domain, r.mode): r for r in v2.itertuples(index=False)}
v3i = {(r.domain, r.mode): r for r in v3.itertuples(index=False)}
ovi = {(r.domain, r.mode): r for r in over.itertuples(index=False)}
gni = {(r.domain, r.mode): r for r in gen.itertuples(index=False)}

rows = []
for r in op.itertuples(index=False):
    k = (r.domain, r.mode)
    src = r.source_campaign
    if src == "rebuild_v2" and k in v2i:
        m = v2i[k]
        model_family, config_id, seed, n_features = "rf", m.config_id, int(m.seed), int(m.n_features)
        calib, tpol, thr = m.calibration, m.threshold_policy, float(m.threshold)
        source_line = "hybrid_no_external_scores_rebuild_v2"
        notes = str(m.notes) if hasattr(m, "notes") else ""
    else:
        m = v3i[k]
        model_family, config_id, seed, n_features = str(m.model_family), cfgid(m.config), v3_seed, int(m.n_features)
        calib, tpol, thr = m.calibration, m.threshold_policy, float(m.threshold)
        source_line = "hybrid_no_external_scores_boosted_v3"
        notes = "boosted_v3_override"
    of = "yes" if (k in ovi and str(ovi[k].overfit_flag).lower() == "yes") else "no"
    gf = "no" if (of == "yes" or (k in gni and "not" in str(gni[k].note).lower())) else "yes"
    de = "yes" if str(r.final_class) == "SUSPECT_EASY_DATASET_NEEDS_CAUTION" else "no"
    rows.append(
        {
            "domain": r.domain,
            "mode": r.mode,
            "role": role(r.mode),
            "active_model_required": "yes",
            "active_model_id": f"{r.domain}__{r.mode}__{src}__{model_family}__{r.feature_set_id}",
            "source_line": source_line,
            "source_campaign": src,
            "model_family": model_family,
            "feature_set_id": r.feature_set_id,
            "config_id": config_id,
            "calibration": calib,
            "threshold_policy": tpol,
            "threshold": thr,
            "seed": seed,
            "n_features": n_features,
            "precision": float(r.precision),
            "recall": float(r.recall),
            "specificity": float(r.specificity),
            "balanced_accuracy": float(r.balanced_accuracy),
            "f1": float(r.f1),
            "roc_auc": float(r.roc_auc),
            "pr_auc": float(r.pr_auc),
            "brier": float(r.brier),
            "src_class": str(r.final_class),
            "overfit_flag": of,
            "generalization_flag": gf,
            "dataset_ease_flag": de,
            "quality_label": str(r.quality_label),
            "notes": notes,
        }
    )

active = pd.DataFrame(rows).sort_values(["domain", "mode"]).drop_duplicates(["domain", "mode"])
active["confidence_pct"] = active.apply(conf_score, axis=1)
active["confidence_band"] = active["confidence_pct"].apply(conf_band)
active["final_operational_class"] = active.apply(op_class, axis=1)

caveats, rec = [], []
for r in active.itertuples(index=False):
    c = []
    if r.final_operational_class == "ACTIVE_LIMITED_USE":
        c.append("limited reliability; escalate to richer mode")
    if r.overfit_flag == "yes":
        c.append("overfit risk")
    if r.dataset_ease_flag == "yes":
        c.append("possible easy-dataset inflation")
    if r.precision < 0.80:
        c.append("low precision")
    if r.recall < 0.70:
        c.append("low recall")
    if "1_3" in r.mode and r.final_operational_class in {"ACTIVE_LOW_CONFIDENCE", "ACTIVE_LIMITED_USE"}:
        c.append("short mode fragile")
    if r.source_campaign == "boosted_v3":
        c.append("boosted override; monitor robustness")
    caveats.append("; ".join(c) if c else "none")
    rec.append("yes" if r.final_operational_class in {"ACTIVE_HIGH_CONFIDENCE", "ACTIVE_MODERATE_CONFIDENCE"} else "no")
active["operational_caveat"] = caveats
active["recommended_for_default_use"] = rec

active = active[
    [
        "domain",
        "mode",
        "role",
        "active_model_required",
        "active_model_id",
        "source_line",
        "source_campaign",
        "model_family",
        "feature_set_id",
        "config_id",
        "calibration",
        "threshold_policy",
        "threshold",
        "seed",
        "n_features",
        "precision",
        "recall",
        "specificity",
        "balanced_accuracy",
        "f1",
        "roc_auc",
        "pr_auc",
        "brier",
        "final_operational_class",
        "overfit_flag",
        "generalization_flag",
        "dataset_ease_flag",
        "confidence_pct",
        "confidence_band",
        "operational_caveat",
        "recommended_for_default_use",
        "notes",
    ]
]
active.to_csv(B / "tables/hybrid_active_models_30_modes.csv", index=False)
active.groupby(["final_operational_class", "confidence_band"], as_index=False).size().to_csv(
    B / "tables/hybrid_active_modes_summary.csv", index=False
)

# Inputs master
retained = pd.read_csv(V2 / "inventory/no_external_scores_retained_features.csv")
prev = pd.read_csv(FF / "tables/frozen_hybrid_champions_inputs_master.csv")
resp = pd.read_csv(RB / "hybrid_model_input_respondability_final.csv")
modes = pd.read_csv(RB / "questionnaire_modes_priority_matrix_final.csv")
dsm = pd.read_csv(RB / "dsm5_quant_feature_template_final.csv").rename(columns={"feature_name": "feature"})
qmaster = pd.read_csv("questionnaire_master_final_corrected.csv")
v2fs = pd.read_csv(V2 / "feature_engineering/hybrid_no_external_scores_feature_engineering_registry.csv")
v3eng = pd.read_csv(V3 / "feature_engineering/hybrid_no_external_scores_boosted_feature_registry.csv")

def flist(x):
    if pd.isna(x) or str(x).strip() == "":
        return []
    return [i for i in str(x).split("|") if i]

fidx = {(r.domain, r.mode, r.feature_set_id): flist(r.feature_list_pipe) for r in v2fs.itertuples(index=False)}
engv3 = set(v3eng["feature"].astype(str))
mode_map = {m: set() for m in ["caregiver_1_3", "caregiver_2_3", "caregiver_full", "psychologist_1_3", "psychologist_2_3", "psychologist_full"]}
dom_map = {d: set() for d in ["adhd", "conduct", "elimination", "anxiety", "depression"]}
for r in active.itertuples(index=False):
    feats = fidx.get((r.domain, r.mode, r.feature_set_id), [])
    if str(r.feature_set_id).startswith("boosted_eng_"):
        feats = sorted(set(feats).union(engv3))
    for f in feats:
        mode_map[r.mode].add(f)
        dom_map[r.domain].add(f)

allf = sorted(set(retained["feature"].astype(str)).union({f for f in set().union(*mode_map.values()) if f.startswith("eng_") or f.startswith("engv3_")}))
im = pd.DataFrame({"feature": allf})
im = im.merge(prev, on="feature", how="left")
im = im.merge(
    resp[
        [
            "feature",
            "layer",
            "feature_type",
            "questionnaire_class",
            "caregiver_answerable_yes_no",
            "psychologist_answerable_yes_no",
            "must_be_self_report_yes_no",
            "respondent_expected",
            "administered_by",
            "respondability_group",
            "is_direct_input",
            "is_transparent_derived",
        ]
    ],
    on="feature",
    how="left",
    suffixes=("", "_resp"),
)
im = im.merge(
    modes[
        [
            "feature",
            "layer",
            "domain_label",
            "module_label",
            "source_label",
            "feature_type",
            "feature_role",
            "caregiver_rank",
            "caregiver_priority_bucket",
            "psychologist_rank",
            "psychologist_priority_bucket",
            "include_caregiver_1_3",
            "include_caregiver_2_3",
            "include_caregiver_full",
            "include_psychologist_1_3",
            "include_psychologist_2_3",
            "include_psychologist_full",
            "selection_rationale",
        ]
    ],
    on="feature",
    how="left",
    suffixes=("", "_m"),
)
im = im.merge(dsm[["feature", "domain", "module", "criterion_ref", "notes"]], on="feature", how="left", suffixes=("", "_dsm"))
qp = (
    qmaster.groupby("input_key_primary", as_index=False)
    .agg(caregiver_prompt=("caregiver_prompt", "first"), psychologist_prompt=("psychologist_prompt", "first"), section_name=("section_name", "first"))
    .rename(columns={"input_key_primary": "feature"})
)
im = im.merge(qp, on="feature", how="left")
engmap = {r.feature: (r.source_columns, f"{r.formula}: {r.rationale}") for r in v3eng.itertuples(index=False)}

rows = []
for r in im.itertuples(index=False):
    d = r._asdict()
    f = d["feature"]
    is_eng = f.startswith("eng_") or f.startswith("engv3_")
    is_dir = yn(d.get("is_direct_input"), "no")
    is_der = yn(d.get("is_transparent_derived"), "no")
    if is_eng:
        is_dir, is_der = "no", "yes"
    layer = d.get("layer") if pd.notna(d.get("layer")) else ("dsm5" if is_eng else "clean_base")
    show_q = yn(d.get("show_in_questionnaire_yes_no"), "yes" if is_dir == "yes" else "no")
    deriv = yn(d.get("derivable_if_not_shown_yes_no"), "yes" if is_der == "yes" else "no")
    doms = [x for x in ["adhd", "conduct", "elimination", "anxiety", "depression"] if f in dom_map[x]]
    dom_primary = doms[0] if doms else (str(d.get("domain")) if pd.notna(d.get("domain")) else "")
    dom_final = "|".join(doms) if doms else (str(d.get("domains_final")) if pd.notna(d.get("domains_final")) else "")
    inc = {}
    for m in mode_map:
        c = f"include_{m}"
        inc[c] = "yes" if (f in mode_map[m] or yn(d.get(c)) == "yes") else "no"
    req_exact = "yes" if (is_dir == "yes" and str(layer) == "dsm5") else "no"
    admin = str(d.get("administered_by")) if pd.notna(d.get("administered_by")) else "both"
    resp_exp = str(d.get("respondent_expected")) if pd.notna(d.get("respondent_expected")) else "both"
    req_clin = "yes" if ("psychologist" in admin.lower() and "caregiver" not in admin.lower()) else "no"
    req_self = "yes" if (yn(d.get("must_be_self_report_yes_no")) == "yes" or "child" in resp_exp.lower()) else "no"
    req_internal = "yes" if (is_der == "yes" or show_q == "no" or is_eng) else "no"
    if f in engmap:
        dfrom, fsum = engmap[f]
    elif is_eng:
        dfrom, fsum = "por_confirmar", "internal composite from valid questionnaire inputs (por_confirmar exact formula)"
    elif is_der == "yes":
        dfrom, fsum = "transparent from related direct items", "internal transparent aggregation"
    else:
        dfrom, fsum = "", ""
    label = str(d.get("feature_label_human")) if pd.notna(d.get("feature_label_human")) else (str(d.get("caregiver_prompt")) if pd.notna(d.get("caregiver_prompt")) else f.replace("_", " ").capitalize())
    desc = str(d.get("feature_description")) if pd.notna(d.get("feature_description")) else (str(d.get("notes_dsm")) if pd.notna(d.get("notes_dsm")) else f"Input {label} used by active hybrid models.")
    rows.append(
        {
            "feature": f,
            "feature_label_human": label,
            "feature_description": desc,
            "layer": layer,
            "domain": dom_primary,
            "domains_final": dom_final,
            "module": str(d.get("module")) if pd.notna(d.get("module")) else (str(d.get("module_label")) if pd.notna(d.get("module_label")) else ""),
            "criterion_ref": str(d.get("criterion_ref")) if pd.notna(d.get("criterion_ref")) else "",
            "source_label": str(d.get("source_label")) if pd.notna(d.get("source_label")) else ("engineered_internal" if is_eng else "por_confirmar"),
            "instrument_or_source": str(d.get("instrument_or_source")) if pd.notna(d.get("instrument_or_source")) else (str(d.get("source_label")) if pd.notna(d.get("source_label")) else "por_confirmar"),
            "feature_type": str(d.get("feature_type")) if pd.notna(d.get("feature_type")) else ("engineered_internal" if is_eng else "por_confirmar"),
            "feature_role": str(d.get("feature_role")) if pd.notna(d.get("feature_role")) else ("internal_composite" if is_eng else "por_confirmar"),
            "dataset_class": str(d.get("dataset_class")) if pd.notna(d.get("dataset_class")) else "model_input",
            "questionnaire_class": str(d.get("questionnaire_class")) if pd.notna(d.get("questionnaire_class")) else ("derived_internal" if is_der == "yes" else "direct_both"),
            "respondability_group": str(d.get("respondability_group")) if pd.notna(d.get("respondability_group")) else "both",
            "respondent_expected": resp_exp,
            "administered_by": admin,
            "caregiver_answerable_yes_no": yn(d.get("caregiver_answerable_yes_no"), "yes"),
            "psychologist_answerable_yes_no": yn(d.get("psychologist_answerable_yes_no"), "yes"),
            "must_be_self_report_yes_no": yn(d.get("must_be_self_report_yes_no"), "no"),
            "is_direct_input": is_dir,
            "is_transparent_derived": is_der,
            "show_in_questionnaire_yes_no": show_q,
            "derivable_if_not_shown_yes_no": deriv,
            "requires_exact_item_wording": req_exact,
            "requires_clinician_administration": req_clin,
            "requires_child_self_report": req_self,
            "requires_internal_scoring": req_internal,
            "questionnaire_section_suggested": str(d.get("questionnaire_section_suggested")) if pd.notna(d.get("questionnaire_section_suggested")) else (str(d.get("section_name")) if pd.notna(d.get("section_name")) else dom_primary),
            "questionnaire_subsection_suggested": str(d.get("questionnaire_subsection_suggested")) if pd.notna(d.get("questionnaire_subsection_suggested")) else (str(d.get("module_label")) if pd.notna(d.get("module_label")) else ""),
            "question_text_needed_yes_no": "yes" if show_q == "yes" else "no",
            "input_needed_for_adhd": "yes" if f in dom_map["adhd"] else "no",
            "input_needed_for_conduct": "yes" if f in dom_map["conduct"] else "no",
            "input_needed_for_elimination": "yes" if f in dom_map["elimination"] else "no",
            "input_needed_for_anxiety": "yes" if f in dom_map["anxiety"] else "no",
            "input_needed_for_depression": "yes" if f in dom_map["depression"] else "no",
            "include_caregiver_1_3": inc["include_caregiver_1_3"],
            "include_caregiver_2_3": inc["include_caregiver_2_3"],
            "include_caregiver_full": inc["include_caregiver_full"],
            "include_psychologist_1_3": inc["include_psychologist_1_3"],
            "include_psychologist_2_3": inc["include_psychologist_2_3"],
            "include_psychologist_full": inc["include_psychologist_full"],
            "caregiver_rank": d.get("caregiver_rank") if pd.notna(d.get("caregiver_rank")) else "",
            "psychologist_rank": d.get("psychologist_rank") if pd.notna(d.get("psychologist_rank")) else "",
            "caregiver_priority_bucket": d.get("caregiver_priority_bucket") if pd.notna(d.get("caregiver_priority_bucket")) else "",
            "psychologist_priority_bucket": d.get("psychologist_priority_bucket") if pd.notna(d.get("psychologist_priority_bucket")) else "",
            "derived_from_features": dfrom,
            "internal_scoring_formula_summary": fsum,
            "selection_rationale": d.get("selection_rationale") if pd.notna(d.get("selection_rationale")) else "active model input coverage",
            "notes": d.get("notes") if pd.notna(d.get("notes")) else "",
        }
    )

inputs = pd.DataFrame(rows).sort_values("feature").drop_duplicates("feature")
inputs.to_csv(B / "tables/hybrid_questionnaire_inputs_master.csv", index=False)

# Reports + manifest
r1 = [
    "# Hybrid Active Modes Freeze v1 - Summary",
    "",
    f"- Active models defined: {len(active)}",
    f"- ACTIVE_HIGH_CONFIDENCE: {(active['final_operational_class'] == 'ACTIVE_HIGH_CONFIDENCE').sum()}",
    f"- ACTIVE_MODERATE_CONFIDENCE: {(active['final_operational_class'] == 'ACTIVE_MODERATE_CONFIDENCE').sum()}",
    f"- ACTIVE_LOW_CONFIDENCE: {(active['final_operational_class'] == 'ACTIVE_LOW_CONFIDENCE').sum()}",
    f"- ACTIVE_LIMITED_USE: {(active['final_operational_class'] == 'ACTIVE_LIMITED_USE').sum()}",
]
(B / "reports/hybrid_active_modes_freeze_summary.md").write_text("\n".join(r1), encoding="utf-8")
r2 = [
    "# Hybrid Questionnaire Inputs Master - Summary",
    "",
    f"- Total inputs: {len(inputs)}",
    f"- Direct inputs: {(inputs['is_direct_input'] == 'yes').sum()}",
    f"- Transparent derived inputs: {(inputs['is_transparent_derived'] == 'yes').sum()}",
    f"- Inputs requiring internal scoring: {(inputs['requires_internal_scoring'] == 'yes').sum()}",
]
(B / "reports/hybrid_questionnaire_inputs_summary.md").write_text("\n".join(r2), encoding="utf-8")
manifest = {
    "run_id": "hybrid_active_modes_freeze_v1",
    "active_models": int(len(active)),
    "inputs_exported": int(len(inputs)),
    "artifacts": {
        "active_models": str(B / "tables/hybrid_active_models_30_modes.csv"),
        "inputs_master": str(B / "tables/hybrid_questionnaire_inputs_master.csv"),
        "summary": str(B / "tables/hybrid_active_modes_summary.csv"),
    },
}
(A / "hybrid_active_modes_freeze_v1_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("done")
