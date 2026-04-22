#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LINE = "hybrid_final_freeze_v1"
BASE = ROOT / "data" / LINE
TABLES = BASE / "tables"
REPORTS = BASE / "reports"
ART = ROOT / "artifacts" / LINE

V1 = ROOT / "data" / "hybrid_rf_ceiling_push_v1"
V2 = ROOT / "data" / "hybrid_rf_consolidation_v2"
V3 = ROOT / "data" / "hybrid_rf_final_ceiling_push_v3"
V4 = ROOT / "data" / "hybrid_rf_targeted_fix_v4"
H = ROOT / "data" / "hybrid_dsm5_rebuild_v1"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
MODES = ["caregiver_1_3", "caregiver_2_3", "caregiver_full", "psychologist_1_3", "psychologist_2_3", "psychologist_full"]

REQ_INPUT_COLS = [
    "feature", "feature_label_human", "feature_description", "layer", "domain", "domains_final", "module", "criterion_ref", "source_label",
    "instrument_or_source", "feature_type", "feature_role", "dataset_class", "questionnaire_class", "respondability_group", "respondent_expected",
    "administered_by", "caregiver_answerable_yes_no", "psychologist_answerable_yes_no", "must_be_self_report_yes_no", "is_direct_input",
    "is_transparent_derived", "show_in_questionnaire_yes_no", "derivable_if_not_shown_yes_no", "include_caregiver_1_3", "include_caregiver_2_3",
    "include_caregiver_full", "include_psychologist_1_3", "include_psychologist_2_3", "include_psychologist_full", "caregiver_rank", "psychologist_rank",
    "caregiver_priority_bucket", "psychologist_priority_bucket", "selection_rationale", "questionnaire_section_suggested", "questionnaire_subsection_suggested",
    "needs_human_question_text", "notes",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    for p in [BASE, TABLES, REPORTS, ART]:
        p.mkdir(parents=True, exist_ok=True)


def yesno(x: Any) -> str:
    s = str(x).strip().lower() if not pd.isna(x) else ""
    if s in {"si", "sí", "yes", "y", "true", "1"}:
        return "si"
    if s in {"no", "n", "false", "0"}:
        return "no"
    return "por_confirmar"


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_sin datos_"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in df.columns:
            v = row[c]
            if pd.isna(v):
                vals.append("")
            elif isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v).replace("|", "\\|"))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def clean_text_label(feature: str) -> str:
    return re.sub(r"\s+", " ", str(feature).replace("_", " ")).strip().capitalize()


def quality_label(row: pd.Series) -> str:
    p, r, ba, pr, b = row["precision"], row["recall"], row["balanced_accuracy"], row["pr_auc"], row["brier"]
    frag = str(row.get("generalization_status", "")).lower() in {"weak", "fragile"} or yesno(row.get("overfit_warning", "no")) == "si"
    if p >= 0.88 and r >= 0.80 and ba >= 0.90 and pr >= 0.90 and b <= 0.05 and not frag:
        return "muy_bueno"
    if p >= 0.84 and r >= 0.75 and ba >= 0.88 and pr >= 0.88 and b <= 0.06 and not frag:
        return "bueno"
    if p >= 0.80 and r >= 0.70 and ba >= 0.85 and pr >= 0.85 and b <= 0.08:
        return "aceptable"
    return "malo"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def build_frozen_champions() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    v3m = pd.read_csv(V3 / "tables" / "hybrid_rf_mode_domain_final_metrics.csv")
    v3w = pd.read_csv(V3 / "tables" / "hybrid_rf_mode_domain_winners.csv")
    v3d = pd.read_csv(V3 / "tables" / "hybrid_rf_final_promotion_decisions.csv")
    v4d = pd.read_csv(V4 / "tables" / "hybrid_rf_targeted_decisions.csv")

    base = v3m.merge(
        v3w[["domain", "mode", "ceiling_status", "overfit_warning"]],
        on=["domain", "mode"],
        how="left",
    ).merge(v3d[["domain", "mode", "promotion_decision"]], on=["domain", "mode"], how="left")
    # Normalize duplicated columns from merges.
    if "overfit_warning" not in base.columns:
        for c in ["overfit_warning_y", "overfit_warning_x"]:
            if c in base.columns:
                base["overfit_warning"] = base[c]
                break
    if "ceiling_status" not in base.columns:
        for c in ["ceiling_status_y", "ceiling_status_x"]:
            if c in base.columns:
                base["ceiling_status"] = base[c]
                break
    base["source_campaign"] = "hybrid_rf_final_ceiling_push_v3"

    v4 = v4d[[
        "domain", "mode", "role", "winner_feature_set_id", "winner_config_id", "winner_calibration",
        "winner_threshold_policy", "winner_threshold", "winner_seed", "n_features", "holdout_precision",
        "holdout_recall", "holdout_specificity", "holdout_balanced_accuracy", "holdout_f1", "holdout_roc_auc",
        "holdout_pr_auc", "holdout_brier", "overfit_gap_train_val_ba", "generalization_gap_val_holdout_ba",
        "promotion_decision", "material_improvement_vs_v3"
    ]].copy()
    v4["source_campaign"] = "hybrid_rf_targeted_fix_v4"
    v4["ceiling_status"] = np.where(
        v4["promotion_decision"].eq("CEILING_CONFIRMED_NO_MATERIAL_GAIN"),
        "ceiling_confirmed",
        np.where(v4["material_improvement_vs_v3"].eq("yes"), "marginal_room_left", "near_ceiling"),
    )
    v4["overfit_warning"] = np.where(
        (v4["overfit_gap_train_val_ba"] > 0.07) | (v4["generalization_gap_val_holdout_ba"] > 0.06),
        "yes",
        "no",
    )

    keyset = set(zip(v4["domain"], v4["mode"]))
    rows: list[dict[str, Any]] = []
    for _, r in base.iterrows():
        k = (r["domain"], r["mode"])
        if k in keyset:
            x = v4[(v4["domain"] == k[0]) & (v4["mode"] == k[1])].iloc[0]
            rows.append({
                "domain": x["domain"], "mode": x["mode"], "role": x["role"], "source_campaign": x["source_campaign"],
                "feature_set_id": x["winner_feature_set_id"], "config_id": x["winner_config_id"], "calibration": x["winner_calibration"],
                "threshold_policy": x["winner_threshold_policy"], "threshold": float(x["winner_threshold"]), "seed": int(x["winner_seed"]),
                "n_features": int(x["n_features"]), "precision": float(x["holdout_precision"]), "recall": float(x["holdout_recall"]),
                "specificity": float(x["holdout_specificity"]), "balanced_accuracy": float(x["holdout_balanced_accuracy"]),
                "f1": float(x["holdout_f1"]), "roc_auc": float(x["holdout_roc_auc"]), "pr_auc": float(x["holdout_pr_auc"]),
                "brier": float(x["holdout_brier"]), "overfit_warning": yesno(x["overfit_warning"]),
                "overfit_gap_train_val_ba": float(x["overfit_gap_train_val_ba"]),
                "generalization_gap_val_holdout_ba": float(x["generalization_gap_val_holdout_ba"]),
                "promotion_decision": x["promotion_decision"], "ceiling_status_raw": x["ceiling_status"],
                "material_gain_flag": x.get("material_improvement_vs_v3", "por_confirmar"),
            })
        else:
            rows.append({
                "domain": r["domain"], "mode": r["mode"], "role": r["role"], "source_campaign": r["source_campaign"],
                "feature_set_id": r["winner_feature_set_id"], "config_id": r["winner_config_id"], "calibration": r["winner_calibration"],
                "threshold_policy": r["winner_threshold_policy"], "threshold": float(r["winner_threshold"]), "seed": int(r["winner_seed"]),
                "n_features": int(r["n_features"]), "precision": float(r["holdout_precision"]), "recall": float(r["holdout_recall"]),
                "specificity": float(r["holdout_specificity"]), "balanced_accuracy": float(r["holdout_balanced_accuracy"]),
                "f1": float(r["holdout_f1"]), "roc_auc": float(r["holdout_roc_auc"]), "pr_auc": float(r["holdout_pr_auc"]),
                "brier": float(r["holdout_brier"]), "overfit_warning": yesno(r["overfit_warning"]),
                "overfit_gap_train_val_ba": float(r["overfit_gap_train_val_ba"]),
                "generalization_gap_val_holdout_ba": float(r["generalization_gap_val_holdout_ba"]),
                "promotion_decision": r["promotion_decision"], "ceiling_status_raw": r.get("ceiling_status", "not_demonstrated"),
                "material_gain_flag": r.get("material_improvement_vs_baseline", "por_confirmar"),
            })

    out = pd.DataFrame(rows)
    out["generalization_status"] = np.where(
        (out["generalization_gap_val_holdout_ba"] <= 0.03) & (out["overfit_warning"].eq("no")),
        "strong",
        np.where(out["generalization_gap_val_holdout_ba"] <= 0.06, "acceptable", "weak"),
    )

    decision_map = {
        "PROMOTE_NOW": "FROZEN_PRIMARY",
        "PROMOTE_WITH_CAVEAT": "FROZEN_WITH_CAVEAT",
        "HOLD_FOR_TARGETED_FIX": "HOLD_FOR_LIMITATION",
        "HOLD_FOR_FINAL_LIMITATION": "HOLD_FOR_LIMITATION",
        "REJECT_AS_PRIMARY": "REJECT_AS_PRIMARY",
        "CEILING_CONFIRMED_NO_MATERIAL_GAIN": "CEILING_CONFIRMED_BEST_PRACTICAL_POINT",
    }
    out["final_status"] = out["promotion_decision"].map(decision_map).fillna("HOLD_FOR_LIMITATION")
    out["quality_label"] = out.apply(quality_label, axis=1)

    def ceiling_final(r: pd.Series) -> str:
        c = str(r["ceiling_status_raw"]).strip().lower()
        fs = str(r["final_status"])
        if fs == "CEILING_CONFIRMED_BEST_PRACTICAL_POINT" or c in {"ceiling_reached", "ceiling_confirmed"}:
            return "ceiling_confirmed"
        if c == "near_ceiling":
            return "near_ceiling"
        if c == "marginal_room_left":
            return "marginal_room_left"
        if str(r.get("material_gain_flag", "")).lower() == "yes":
            return "marginal_room_left"
        if fs in {"FROZEN_PRIMARY", "FROZEN_WITH_CAVEAT"}:
            return "near_ceiling"
        return "not_demonstrated"

    out["ceiling_status_final"] = out.apply(ceiling_final, axis=1)

    def keep_improving(r: pd.Series) -> str:
        if r["ceiling_status_final"] == "ceiling_confirmed":
            return "no_practical_ceiling_confirmed"
        if r["final_status"] in {"HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"}:
            return "only_if_new_signal"
        if r["ceiling_status_final"] == "marginal_room_left" and r["generalization_status"] != "weak" and r["quality_label"] in {"aceptable", "bueno"}:
            return "yes"
        return "no"

    out["should_keep_improving"] = out.apply(keep_improving, axis=1)
    out["frozen_model_id"] = out.apply(
        lambda r: hashlib.sha1(
            f"{r['source_campaign']}|{r['domain']}|{r['mode']}|{r['feature_set_id']}|{r['config_id']}|{r['calibration']}|{r['threshold_policy']}|{r['seed']}".encode("utf-8")
        ).hexdigest()[:16],
        axis=1,
    )
    out["notes"] = np.where(
        out["source_campaign"].eq("hybrid_rf_targeted_fix_v4"),
        "v4 targeted override on fragile pair",
        "carried from v3 full campaign",
    )
    out = out.sort_values(["domain", "mode"]).reset_index(drop=True)

    lim = out[["domain", "mode", "role", "final_status", "quality_label", "ceiling_status_final", "should_keep_improving", "generalization_status", "overfit_warning"]].copy()
    lim["mode_type"] = np.where(lim["mode"].str.contains("1_3"), "short_1_3", np.where(lim["mode"].str.contains("2_3"), "short_2_3", "full"))
    lim["limitation_type"] = np.where(
        lim["final_status"].eq("REJECT_AS_PRIMARY"),
        "operational_rejection",
        np.where(
            lim["final_status"].eq("HOLD_FOR_LIMITATION"),
            "performance_or_stability_limitation",
            np.where(lim["ceiling_status_final"].eq("ceiling_confirmed"), "practical_ceiling_confirmed", "none_or_minor"),
        ),
    )
    lim["limitation_statement"] = np.where(
        lim["limitation_type"].eq("none_or_minor"),
        "no major unresolved limitation",
        np.where(lim["ceiling_status_final"].eq("ceiling_confirmed"), "best practical point reached with no material gain", "material fragility or signal limits remain"),
    )

    caveats = {
        "missing_hybrid_input_audit_classification_final.csv": "por_confirmar",
        "missing_hybrid_dataset_final_registry_v1.csv": "por_confirmar",
    }
    return out, lim, caveats

def parse_pipe_features(x: Any) -> list[str]:
    if pd.isna(x):
        return []
    out: list[str] = []
    for t in re.split(r"[|;,]", str(x)):
        t = t.strip()
        if t:
            out.append(t)
    return out


def infer_domain_from_feature(f: str) -> str:
    x = str(f).lower()
    if x.startswith("adhd_"):
        return "ADHD"
    if x.startswith("conduct_"):
        return "Conduct"
    if x.startswith("enuresis_") or x.startswith("encopresis_") or x.startswith("elimination_"):
        return "Elimination"
    if x.startswith("sep_anx_") or x.startswith("social_anxiety_") or x.startswith("gad_") or x.startswith("agor_") or x.startswith("anxiety_"):
        return "Anxiety"
    if x.startswith("mdd_") or x.startswith("dmdd_") or x.startswith("pdd_"):
        return "Depression"
    return "cross_domain"


def build_inputs_master() -> tuple[pd.DataFrame, dict[str, int], dict[str, str]]:
    dataset = pd.read_csv(H / "hybrid_dataset_synthetic_complete_final.csv", nrows=1)
    features = [c for c in dataset.columns if c != "participant_id"]
    master = pd.DataFrame({"feature": features})

    respond = pd.read_csv(H / "hybrid_model_input_respondability_final.csv")
    modes = pd.read_csv(H / "questionnaire_modes_priority_matrix_final.csv")
    dsm = pd.read_csv(H / "dsm5_quant_feature_template_final.csv").rename(columns={"feature_name": "feature"})

    qhuman = pd.read_csv(ROOT / "reports" / "questionnaire_final_design" / "questionnaire_master_final_humanized.csv")
    qroles = pd.read_csv(ROOT / "reports" / "questionnaire_final_design" / "questionnaire_role_split_final.csv")
    contract = pd.read_csv(ROOT / "artifacts" / "specs" / "questionnaire_feature_contract.csv")
    final_contract = pd.read_csv(ROOT / "data" / "questionnaire_final_modeling_v3" / "inventory" / "final_input_contract_registry.csv")

    # Expand questionnaire sources by feature
    qrows = []
    for _, r in qhuman.iterrows():
        feats = parse_pipe_features(r.get("input_key_primary")) + parse_pipe_features(r.get("input_keys_secondary"))
        for f in feats:
            qrows.append({
                "feature": f,
                "q_domains": r.get("domains"),
                "q_section": r.get("section_name"),
                "q_subsection": r.get("question_group_id"),
                "q_concept": r.get("concept_name"),
                "q_source_type": r.get("source_type"),
                "q_resp": r.get("respondent_expected"),
                "q_admin": r.get("administered_by"),
            })
    qf = pd.DataFrame(qrows)
    if not qf.empty:
        qf = qf.groupby("feature", as_index=False).agg({
            "q_domains": lambda s: "|".join(sorted({str(x) for x in s if not pd.isna(x)})),
            "q_section": lambda s: "|".join(sorted({str(x) for x in s if not pd.isna(x)})),
            "q_subsection": lambda s: "|".join(sorted({str(x) for x in s if not pd.isna(x)})),
            "q_concept": "first",
            "q_source_type": "first",
            "q_resp": "first",
            "q_admin": "first",
        })

    master = master.merge(respond, on="feature", how="left")
    master = master.merge(modes, on=["feature", "layer", "feature_type", "respondability_group", "caregiver_answerable_yes_no", "psychologist_answerable_yes_no"], how="left")
    master = master.merge(dsm[["feature", "domain", "module", "criterion_ref", "feature_role", "notes"]], on="feature", how="left", suffixes=("", "_dsm"))
    if not qf.empty:
        master = master.merge(qf, on="feature", how="left")

    map_contract = contract.rename(columns={"feature_final": "feature", "dataset_origen": "instrument_or_source_contract", "pregunta_encuesta": "feature_label_contract", "trastorno_relacionado": "contract_domain"})
    master = master.merge(map_contract[["feature", "instrument_or_source_contract", "feature_label_contract", "contract_domain"]], on="feature", how="left")

    fc = final_contract.groupby("feature", as_index=False).agg({
        "domain": lambda s: "|".join(sorted({str(x) for x in s if not pd.isna(x)})),
        "mode": lambda s: "|".join(sorted({str(x) for x in s if not pd.isna(x)})),
        "route": "first",
        "mapping_layer": "first",
    }).rename(columns={"domain": "final_contract_domains", "mode": "final_contract_modes"})
    master = master.merge(fc, on="feature", how="left")
    # Build required columns
    out = pd.DataFrame()
    out["feature"] = master["feature"]
    out["feature_label_human"] = master["q_concept"].fillna(master["feature_label_contract"]).fillna(master["feature"].map(clean_text_label))
    out["feature_description"] = (
        master["module_label"].fillna(master["module"]).fillna("general")
        .astype(str)
        .radd("Input for ")
        + " - "
        + master["feature"].map(clean_text_label)
    )
    inferred_layer = pd.Series(
        np.where(
            master["module"].notna(),
            "dsm5",
            np.where(
                master["feature"].str.contains(r"^(?:adhd_|conduct_|enuresis_|encopresis_|sep_anx_|social_anxiety_|gad_|agor_|mdd_|dmdd_|pdd_)", regex=True),
                "dsm5",
                "clean_base",
            ),
        ),
        index=master.index,
    )
    out["layer"] = master["layer"].combine_first(inferred_layer)
    out["domain"] = master["domain_label"].fillna(master["domain"]).fillna(master["contract_domain"]).fillna(master["feature"].map(infer_domain_from_feature))
    out["domains_final"] = master["final_contract_domains"].fillna(master["q_domains"]).fillna(out["domain"])
    out["module"] = master["module_label"].fillna(master["module"]).fillna("por_confirmar")
    out["criterion_ref"] = master["criterion_ref"].fillna("na")
    out["source_label"] = master["source_label"].fillna(master["q_source_type"]).fillna(out["layer"])
    out["instrument_or_source"] = master["instrument_or_source_contract"].fillna(master["source_label"]).fillna(master["q_source_type"]).fillna("por_confirmar")
    out["feature_type"] = master["feature_type"].fillna("derived_or_unspecified")
    out["feature_role"] = master["feature_role"].fillna(master["feature_role_dsm"]).fillna("unspecified")

    targets = {"adhd_final_dsm5_threshold_met", "conduct_final_dsm5_threshold_met", "elimination_any_threshold_met", "anxiety_any_module_threshold_met", "target_domain_depression_final"}
    out["dataset_class"] = np.where(out["feature"].isin(targets), "target_or_label", np.where(master["keep_for_model_v1"].astype(str).str.lower().eq("yes"), "model_input", "dataset_auxiliary"))

    out["questionnaire_class"] = master["questionnaire_class"].fillna("por_confirmar")
    out["respondability_group"] = master["respondability_group"].fillna("por_confirmar")
    out["respondent_expected"] = master["respondent_expected"].fillna(master["q_resp"]).fillna("caregiver_or_psychologist")
    out["administered_by"] = master["administered_by"].fillna(master["q_admin"]).fillna("caregiver_or_psychologist")
    out["caregiver_answerable_yes_no"] = master["caregiver_answerable_yes_no"].map(yesno)
    out["psychologist_answerable_yes_no"] = master["psychologist_answerable_yes_no"].map(yesno)
    out["must_be_self_report_yes_no"] = master["must_be_self_report_yes_no"].map(yesno)
    out["is_direct_input"] = master["is_direct_input"].map(yesno)
    out["is_transparent_derived"] = master["is_transparent_derived"].map(yesno)

    shown = (out["is_direct_input"].eq("si") | master["q_section"].notna())
    out["show_in_questionnaire_yes_no"] = np.where(shown, "si", "no")
    out["derivable_if_not_shown_yes_no"] = np.where((out["show_in_questionnaire_yes_no"].eq("no")) & (out["is_transparent_derived"].eq("si")), "si", "no")

    for c in ["include_caregiver_1_3", "include_caregiver_2_3", "include_caregiver_full", "include_psychologist_1_3", "include_psychologist_2_3", "include_psychologist_full"]:
        out[c] = master[c].map(yesno) if c in master.columns else "por_confirmar"

    out["caregiver_rank"] = master["caregiver_rank"].fillna(np.nan)
    out["psychologist_rank"] = master["psychologist_rank"].fillna(np.nan)
    out["caregiver_priority_bucket"] = master["caregiver_priority_bucket"].fillna("por_confirmar")
    out["psychologist_priority_bucket"] = master["psychologist_priority_bucket"].fillna("por_confirmar")
    out["selection_rationale"] = master["selection_rationale"].fillna("derived from available contracts and priority matrix")
    out["questionnaire_section_suggested"] = master["q_section"].fillna("por_confirmar")
    out["questionnaire_subsection_suggested"] = master["q_subsection"].fillna("por_confirmar")
    out["needs_human_question_text"] = np.where(out["show_in_questionnaire_yes_no"].eq("si"), "si", "no")

    out["notes"] = np.where(master["final_contract_modes"].notna(), "present_in_final_input_contract_registry", "")
    out.loc[out["feature"].isin(set(contract["feature_final"].astype(str))), "notes"] = out["notes"].astype(str) + "|present_in_questionnaire_feature_contract"

    out = out.drop_duplicates(subset=["feature"]).reset_index(drop=True)
    for c in REQ_INPUT_COLS:
        if c not in out.columns:
            out[c] = "por_confirmar"
    out = out[REQ_INPUT_COLS].sort_values("feature").reset_index(drop=True)

    stats = {
        "total_inputs": int(len(out)),
        "direct_inputs": int((out["is_direct_input"] == "si").sum()),
        "transparent_derived_inputs": int((out["is_transparent_derived"] == "si").sum()),
        "shown_inputs": int((out["show_in_questionnaire_yes_no"] == "si").sum()),
    }
    caveats = {
        "missing_hybrid_input_audit_classification_final.csv": "por_confirmar",
        "missing_hybrid_dataset_final_registry_v1.csv": "por_confirmar",
    }
    return out, stats, caveats

def main() -> None:
    ensure_dirs()

    frozen, limitations, caveats_model = build_frozen_champions()
    inputs_master, input_stats, caveats_input = build_inputs_master()

    frozen["notes"] = frozen["notes"].astype(str)
    for k, v in {**caveats_model, **caveats_input}.items():
        frozen["notes"] = frozen["notes"] + f"|{k}:{v}"

    cols = [
        "domain", "mode", "role", "final_status", "frozen_model_id", "source_campaign", "feature_set_id", "config_id", "calibration",
        "threshold_policy", "threshold", "seed", "n_features", "precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier",
        "overfit_warning", "generalization_status", "quality_label", "ceiling_status_final", "should_keep_improving", "notes",
    ]
    frozen_master = frozen[cols].copy()
    save_csv(frozen_master, TABLES / "frozen_hybrid_champions_master.csv")
    save_csv(inputs_master, TABLES / "frozen_hybrid_champions_inputs_master.csv")
    save_csv(limitations, TABLES / "frozen_hybrid_domain_limitations.csv")

    quality_counts = frozen_master["quality_label"].value_counts().to_dict()
    ceiling_counts = frozen_master["ceiling_status_final"].value_counts().to_dict()
    keep_counts = frozen_master["should_keep_improving"].value_counts().to_dict()

    md1 = [
        "# Frozen Hybrid Final Status v1",
        "",
        "## Champions (30 pares)",
        md_table(frozen_master[["domain", "mode", "final_status", "precision", "recall", "balanced_accuracy", "pr_auc", "brier", "quality_label", "ceiling_status_final", "should_keep_improving"]]),
        "",
        "## Conteos",
        f"- quality: {quality_counts}",
        f"- ceiling: {ceiling_counts}",
        f"- should_keep_improving: {keep_counts}",
        "",
        "## Caveats de fuentes",
        "- `hybrid_input_audit_classification_final.csv`: por_confirmar (no encontrado en repo).",
        "- `hybrid_dataset_final_registry_v1.csv`: por_confirmar (no encontrado en repo).",
    ]
    write_md(REPORTS / "frozen_hybrid_final_status.md", "\n".join(md1))

    md2 = [
        "# Frozen Hybrid Questionnaire Coverage v1",
        "",
        "## Input coverage summary",
        f"- total_inputs: {input_stats['total_inputs']}",
        f"- direct_inputs: {input_stats['direct_inputs']}",
        f"- transparent_derived_inputs: {input_stats['transparent_derived_inputs']}",
        f"- shown_inputs: {input_stats['shown_inputs']}",
        "",
        "## Sample",
        md_table(inputs_master.head(30)[["feature", "layer", "domains_final", "is_direct_input", "is_transparent_derived", "show_in_questionnaire_yes_no", "include_caregiver_1_3", "include_psychologist_full"]]),
    ]
    write_md(REPORTS / "frozen_hybrid_questionnaire_coverage.md", "\n".join(md2))

    generated_files = []
    for p in sorted(BASE.rglob("*")):
        if p.is_file():
            generated_files.append({
                "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                "sha256": file_sha256(p),
                "bytes": p.stat().st_size,
            })

    manifest = {
        "line": LINE,
        "generated_at_utc": now_iso(),
        "champion_pairs": int(len(frozen_master)),
        "quality_counts": quality_counts,
        "ceiling_counts": ceiling_counts,
        "should_keep_improving_counts": keep_counts,
        "input_coverage_stats": input_stats,
        "source_campaigns": [
            "hybrid_rf_ceiling_push_v1",
            "hybrid_rf_consolidation_v2",
            "hybrid_rf_final_ceiling_push_v3",
            "hybrid_rf_targeted_fix_v4",
        ],
        "source_dataset": "data/hybrid_dsm5_rebuild_v1",
        "caveats": {**caveats_model, **caveats_input},
        "generated_files": generated_files,
    }
    (ART / "hybrid_final_freeze_v1_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
