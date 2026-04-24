from __future__ import annotations

import json
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

ROOT = Path(__file__).resolve().parents[1]

DATASET_PATH = (
    ROOT
    / "data"
    / "processed_hybrid_dsm5_v2"
    / "final"
    / "model_ready"
    / "strict_no_leakage_hybrid"
    / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv"
)
ROLE_SPLIT_PATH = ROOT / "reports" / "questionnaire_final_design" / "questionnaire_role_split_final.csv"
MASTER_HUMANIZED_PATH = ROOT / "reports" / "questionnaire_final_design" / "questionnaire_master_final_humanized.csv"
NON_ELIM_FEATURES_PATH = ROOT / "artifacts" / "tmp_selected_features_v4_non_elim.csv"
FINAL_INPUT_REGISTRY_PATH = ROOT / "data" / "questionnaire_final_modeling_v3" / "inventory" / "final_input_contract_registry.csv"
FINAL_RUNTIME_VALIDATION_PATH = ROOT / "data" / "questionnaire_final_ceiling_v4" / "tables" / "final_model_runtime_validation_results.csv"
FINAL_MODEL_INVENTORY_PATH = ROOT / "data" / "final_ceiling_check_v15" / "inventory" / "final_model_inventory.csv"

OUT_BASE = ROOT / "data" / "questionnaire_scenario_eval_v1"
OUT_TABLES = OUT_BASE / "tables"
OUT_REPORTS = OUT_BASE / "reports"
OUT_ARTIFACTS = ROOT / "artifacts" / "questionnaire_scenario_eval_v1"

DOMAINS = ["adhd", "conduct", "anxiety", "depression", "elimination"]
TARGETS = {d: f"target_domain_{d}" for d in DOMAINS}

HAS_EXCLUDE = {
    "has_cbcl",
    "has_sdq",
    "has_swan",
    "has_conners",
    "has_scared_p",
    "has_scared_sr",
    "has_ysr",
    "has_ari_p",
    "has_ari_sr",
    "has_icut",
}

HAS_PREFIX_MAP = {
    "has_cbcl": ["cbcl_"],
    "has_sdq": ["sdq_"],
    "has_swan": ["swan_"],
    "has_conners": ["conners_"],
    "has_scared_p": ["scared_p_"],
    "has_scared_sr": ["scared_sr_"],
    "has_ysr": ["ysr_"],
    "has_ari_p": ["ari_p_"],
    "has_ari_sr": ["ari_sr_"],
    "has_icut": ["icut_"],
}

SYSTEM_FILLED_FEATURES = {"site", "release"}


def ensure_dirs() -> None:
    for p in [OUT_BASE, OUT_TABLES, OUT_REPORTS, OUT_ARTIFACTS]:
        p.mkdir(parents=True, exist_ok=True)


def load_role_split_inputs() -> dict[str, set[str]]:
    role = pd.read_csv(ROLE_SPLIT_PATH)
    base = role[["recommended_bucket", "input_key_primary", "system_filled_hidden"]].drop_duplicates()
    base["input_key_primary"] = base["input_key_primary"].astype(str).str.strip()

    both_inputs = set(base.loc[base["recommended_bucket"] == "both", "input_key_primary"].tolist())
    psych_inputs = set(base.loc[base["recommended_bucket"] == "psychologist", "input_key_primary"].tolist())
    hidden_inputs = set(base.loc[base["recommended_bucket"] == "hidden_system", "input_key_primary"].tolist())

    _ = pd.read_csv(MASTER_HUMANIZED_PATH)

    return {
        "both": both_inputs,
        "psychologist": psych_inputs,
        "hidden_system": hidden_inputs,
    }


def _expected_n_features() -> dict[tuple[str, str], int]:
    frv = pd.read_csv(FINAL_RUNTIME_VALIDATION_PATH)
    out: dict[tuple[str, str], int] = {}
    for _, row in frv.iterrows():
        if str(row.get("check", "")).strip() != "input_contract_non_empty":
            continue
        det = str(row.get("details", ""))
        if "n_features=" not in det:
            continue
        n = int(det.split("n_features=")[1].strip())
        out[(str(row["mode"]).strip(), str(row["domain"]).strip())] = n
    return out


def load_final_mode_domain_features() -> dict[tuple[str, str], list[str]]:
    non = pd.read_csv(NON_ELIM_FEATURES_PATH)
    feat_map: dict[tuple[str, str], list[str]] = {}

    for _, row in non.iterrows():
        mode = str(row["mode"]).strip()
        domain = str(row["domain"]).strip()
        feats = [x.strip() for x in str(row["features"]).split("|") if x.strip()]
        feat_map[(mode, domain)] = feats

    expected = _expected_n_features()
    fir = pd.read_csv(FINAL_INPUT_REGISTRY_PATH)

    care_elim = fir[(fir["mode"] == "caregiver") & (fir["domain"] == "elimination")]
    care_pick = care_elim[(care_elim["route"] == "A") & (care_elim["variant"] == "direct_basic")]["feature"].drop_duplicates().astype(str).tolist()
    if not care_pick:
        target_n = expected.get(("caregiver", "elimination"), 16)
        grp = care_elim.groupby(["route", "variant"])["feature"].nunique().reset_index(name="n")
        if not grp.empty:
            cand = grp.loc[grp["n"] == target_n]
            if cand.empty:
                cand = grp.sort_values("n").head(1)
            r, v = cand.iloc[0]["route"], cand.iloc[0]["variant"]
            care_pick = care_elim[(care_elim["route"] == r) & (care_elim["variant"] == v)]["feature"].drop_duplicates().astype(str).tolist()

    psy_elim = fir[(fir["mode"] == "psychologist") & (fir["domain"] == "elimination")]
    psy_pick = psy_elim[(psy_elim["route"] == "P") & (psy_elim["variant"] == "professional_full_coverage")]["feature"].drop_duplicates().astype(str).tolist()
    if not psy_pick:
        target_n = expected.get(("psychologist", "elimination"), 17)
        grp = psy_elim.groupby(["route", "variant"])["feature"].nunique().reset_index(name="n")
        if not grp.empty:
            cand = grp.loc[grp["n"] == target_n]
            if cand.empty:
                cand = grp.sort_values("n").head(1)
            r, v = cand.iloc[0]["route"], cand.iloc[0]["variant"]
            psy_pick = psy_elim[(psy_elim["route"] == r) & (psy_elim["variant"] == v)]["feature"].drop_duplicates().astype(str).tolist()

    feat_map[("caregiver", "elimination")] = care_pick
    feat_map[("psychologist", "elimination")] = psy_pick

    return feat_map


def load_thresholds() -> dict[tuple[str, str], float]:
    inv = pd.read_csv(FINAL_MODEL_INVENTORY_PATH)
    out: dict[tuple[str, str], float] = {}
    for _, row in inv.iterrows():
        mode = str(row["mode"]).strip()
        domain = str(row["domain"]).strip()
        out[(mode, domain)] = float(row["threshold_final"])
    return out


def normalize_sex(x: Any) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "Unknown"
    raw = str(x).strip().lower()
    if raw in {"m", "male", "masculino", "1"}:
        return "Male"
    if raw in {"f", "female", "femenino", "0"}:
        return "Female"
    return "Unknown"


def normalize_site(x: Any) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "CBIC"
    raw = str(x).strip()
    if raw in {"CBIC", "CUNY", "RUBIC", "Staten Island"}:
        return raw
    return "CBIC"


def default_for_feature(feature: str) -> Any:
    if feature == "age_years":
        return 9.0
    if feature == "sex_assigned_at_birth":
        return "Unknown"
    if feature == "site":
        return "CBIC"
    if feature == "release":
        return 11.0
    if feature.startswith("has_"):
        return 0.0
    return 0.0


def coerce_value(feature: str, value: Any) -> Any:
    if feature == "sex_assigned_at_birth":
        return normalize_sex(value)
    if feature == "site":
        return normalize_site(value)
    if feature.startswith("has_"):
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return 0.0
        raw = str(value).strip().lower()
        if raw in {"1", "true", "si", "yes"}:
            return 1.0
        if raw in {"0", "false", "no"}:
            return 0.0
        try:
            return 1.0 if float(raw) >= 0.5 else 0.0
        except Exception:
            return 0.0
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default_for_feature(feature)
    try:
        return float(value)
    except Exception:
        return default_for_feature(feature)


def safe_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> dict[str, float]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
    out = {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "specificity": specificity,
        "ba": float(balanced_accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float("nan"),
        "pr_auc": float("nan"),
        "brier": float(brier_score_loss(y_true, y_prob)),
    }
    try:
        out["roc_auc"] = float(roc_auc_score(y_true, y_prob))
    except Exception:
        pass
    try:
        out["pr_auc"] = float(average_precision_score(y_true, y_prob))
    except Exception:
        pass
    return out


def load_model(domain: str):
    base = ROOT / "models" / "champions" / f"rf_{domain}_current"
    meta = json.loads((base / "metadata.json").read_text(encoding="utf-8"))
    model_path = base / "calibrated.joblib"
    if not model_path.exists():
        model_path = base / "pipeline.joblib"
    model = joblib.load(model_path)
    model = force_single_thread(model)
    model_cols = list(meta.get("feature_columns", []))
    return model, model_cols


def force_single_thread(model: Any) -> Any:
    # Avoid sandbox/thread-pool permission issues from nested joblib in loaded RF estimators.
    try:
        if hasattr(model, "n_jobs"):
            model.n_jobs = 1
    except Exception:
        pass

    try:
        if hasattr(model, "steps"):
            for _, step in model.steps:
                if hasattr(step, "n_jobs"):
                    step.n_jobs = 1
    except Exception:
        pass

    try:
        if hasattr(model, "calibrated_classifiers_"):
            for cc in model.calibrated_classifiers_:
                est = getattr(cc, "estimator", None)
                if est is not None:
                    force_single_thread(est)
    except Exception:
        pass

    try:
        if hasattr(model, "base_estimator"):
            force_single_thread(model.base_estimator)
    except Exception:
        pass

    return model


def load_dataset() -> pd.DataFrame:
    return pd.read_csv(DATASET_PATH)


def load_test_subset(df: pd.DataFrame, domain: str) -> pd.DataFrame:
    ids_path = ROOT / "data" / "processed_hybrid_dsm5_v2" / "splits" / f"domain_{domain}_strict_full" / "ids_test.csv"
    ids = pd.read_csv(ids_path)
    id_col = "participant_id" if "participant_id" in ids.columns else ids.columns[0]
    idset = set(ids[id_col].astype(str).tolist())
    return df[df["participant_id"].astype(str).isin(idset)].copy()


def has_derive_possible(feature: str, visible_inputs: set[str]) -> bool:
    prefixes = HAS_PREFIX_MAP.get(feature, [])
    if not prefixes:
        return False
    for v in visible_inputs:
        if any(str(v).startswith(p) for p in prefixes):
            return True
    return False


def derive_has_value(feature: str, row: pd.Series, visible_inputs: set[str]) -> tuple[float, bool]:
    prefixes = HAS_PREFIX_MAP.get(feature, [])
    if not prefixes:
        return 0.0, False
    candidate_cols = [c for c in visible_inputs if any(str(c).startswith(p) for p in prefixes)]
    if not candidate_cols:
        return 0.0, False
    for c in candidate_cols:
        if c in row.index and pd.notna(row[c]):
            return 1.0, True
    return 0.0, True


def scenario_configs(role_inputs: dict[str, set[str]]) -> dict[str, dict[str, Any]]:
    both = role_inputs["both"]
    psych = role_inputs["psychologist"]
    hidden = role_inputs["hidden_system"]

    caregiver_visible = set(both)
    psych_with_has_visible = set(both | psych)
    psych_no_has_visible = set((both | psych) - HAS_EXCLUDE)

    return {
        "caregiver": {
            "mode_ref": "caregiver",
            "visible_inputs": caregiver_visible,
            "hidden_inputs": hidden,
            "exclude_has": False,
        },
        "psychologist_no_has": {
            "mode_ref": "psychologist",
            "visible_inputs": psych_no_has_visible,
            "hidden_inputs": hidden,
            "exclude_has": True,
        },
        "psychologist_with_has": {
            "mode_ref": "psychologist",
            "visible_inputs": psych_with_has_visible,
            "hidden_inputs": hidden,
            "exclude_has": False,
        },
    }


def feature_status(feature: str, cfg: dict[str, Any]) -> str:
    visible = cfg["visible_inputs"]
    hidden = cfg["hidden_inputs"]
    exclude_has = cfg["exclude_has"]

    if feature in visible:
        return "direct"
    if feature in hidden or feature in SYSTEM_FILLED_FEATURES:
        return "derived"
    if exclude_has and feature in HAS_EXCLUDE:
        return "derived" if has_derive_possible(feature, visible) else "missing_default"
    return "missing_default"


def build_X_for_scenario(
    df_test: pd.DataFrame,
    model_cols: list[str],
    required_features: set[str],
    cfg: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, float]]:
    visible = cfg["visible_inputs"]
    hidden = cfg["hidden_inputs"]
    exclude_has = cfg["exclude_has"]

    X = pd.DataFrame(index=df_test.index)

    direct_slots = 0
    derived_slots = 0
    missing_slots = 0

    for col in model_cols:
        vals = []
        if col not in required_features:
            default_val = default_for_feature(col)
            vals = [default_val] * len(df_test)
            X[col] = vals
            continue

        if col in visible:
            for _, row in df_test.iterrows():
                raw = row[col] if col in row.index else np.nan
                if pd.notna(raw):
                    vals.append(coerce_value(col, raw))
                    direct_slots += 1
                else:
                    vals.append(default_for_feature(col))
                    missing_slots += 1
        elif col in hidden or col in SYSTEM_FILLED_FEATURES:
            for _, row in df_test.iterrows():
                raw = row[col] if col in row.index else np.nan
                if pd.notna(raw):
                    vals.append(coerce_value(col, raw))
                else:
                    vals.append(default_for_feature(col))
                derived_slots += 1
        elif exclude_has and col in HAS_EXCLUDE:
            for _, row in df_test.iterrows():
                val, used_derivation = derive_has_value(col, row, visible)
                vals.append(val)
                if used_derivation:
                    derived_slots += 1
                else:
                    missing_slots += 1
        else:
            default_val = default_for_feature(col)
            vals = [default_val] * len(df_test)
            missing_slots += len(df_test)

        X[col] = vals

    total_slots = max(len(df_test) * max(len(required_features), 1), 1)
    trace = {
        "direct_ratio": float(direct_slots / total_slots),
        "derived_ratio": float(derived_slots / total_slots),
        "missing_default_ratio": float(missing_slots / total_slots),
    }
    return X, trace


def main() -> None:
    ensure_dirs()

    role_inputs = load_role_split_inputs()
    cfgs = scenario_configs(role_inputs)
    feature_map = load_final_mode_domain_features()
    thresholds = load_thresholds()
    df = load_dataset()

    scenario_rows: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []

    for scenario, cfg in cfgs.items():
        mode_ref = cfg["mode_ref"]
        for domain in DOMAINS:
            model, model_cols = load_model(domain)
            required = set(feature_map[(mode_ref, domain)])
            test_df = load_test_subset(df, domain)
            target_col = TARGETS[domain]
            y = test_df[target_col].astype(int).to_numpy()

            X, trace = build_X_for_scenario(test_df, model_cols, required, cfg)
            prob = model.predict_proba(X[model_cols])[:, 1]

            threshold = thresholds.get((mode_ref, domain), 0.5)
            m = safe_metrics(y, prob, threshold)

            note = (
                f"threshold={threshold:.3f}; mode_ref={mode_ref}; "
                f"direct_ratio={trace['direct_ratio']:.4f}; "
                f"derived_ratio={trace['derived_ratio']:.4f}; "
                f"missing_default_ratio={trace['missing_default_ratio']:.4f}"
            )

            row = {
                "scenario": scenario,
                "domain": domain,
                "precision": m["precision"],
                "recall": m["recall"],
                "specificity": m["specificity"],
                "ba": m["ba"],
                "f1": m["f1"],
                "roc_auc": m["roc_auc"],
                "pr_auc": m["pr_auc"],
                "brier": m["brier"],
                "notes": note,
            }
            scenario_rows.append(row)
            metrics_rows.append({k: row[k] for k in ["scenario", "domain", "precision", "recall", "specificity", "ba", "f1", "roc_auc", "pr_auc", "brier"]})

    scenario_results = pd.DataFrame(scenario_rows).sort_values(["scenario", "domain"])
    scenario_metrics = pd.DataFrame(metrics_rows).sort_values(["scenario", "domain"])

    scenario_results_path = OUT_BASE / "scenario_results.csv"
    scenario_metrics_path = OUT_BASE / "scenario_metrics_by_domain.csv"
    scenario_results.to_csv(scenario_results_path, index=False)
    scenario_metrics.to_csv(scenario_metrics_path, index=False)

    coverage_rows = []
    for scenario, cfg in cfgs.items():
        mode_ref = cfg["mode_ref"]
        req_union = set()
        for d in DOMAINS:
            req_union.update(feature_map[(mode_ref, d)])

        status_map = {f: feature_status(f, cfg) for f in sorted(req_union)}
        direct = sum(1 for s in status_map.values() if s == "direct")
        derived = sum(1 for s in status_map.values() if s == "derived")
        missing = sum(1 for s in status_map.values() if s == "missing_default")
        has_avail = sum(1 for f, s in status_map.items() if f.startswith("has_") and s in {"direct", "derived"})

        coverage_rows.append(
            {
                "scenario": scenario,
                "total_inputs_required": len(req_union),
                "direct_inputs_filled": direct,
                "derived_inputs_filled": derived,
                "missing_or_default_inputs": missing,
                "has_flags_available": has_avail,
                "notes": f"mode_ref={mode_ref}; role_split_source=questionnaire_role_split_final.csv",
            }
        )

    coverage_df = pd.DataFrame(coverage_rows).sort_values("scenario")
    coverage_path = OUT_BASE / "scenario_coverage_summary.csv"
    coverage_df.to_csv(coverage_path, index=False)

    global_scores = scenario_metrics.groupby("scenario", as_index=False)["ba"].mean().rename(columns={"ba": "ba_mean"})
    best_scenario = global_scores.sort_values("ba_mean", ascending=False).iloc[0]["scenario"]

    best_by_domain = scenario_metrics[scenario_metrics["scenario"] == best_scenario].set_index("domain")
    delta_rows = []
    for _, r in scenario_metrics.iterrows():
        b = best_by_domain.loc[r["domain"]]
        delta_rows.append(
            {
                "scenario": r["scenario"],
                "domain": r["domain"],
                "d_precision": float(r["precision"] - b["precision"]),
                "d_recall": float(r["recall"] - b["recall"]),
                "d_specificity": float(r["specificity"] - b["specificity"]),
                "d_ba": float(r["ba"] - b["ba"]),
                "d_f1": float(r["f1"] - b["f1"]),
                "d_roc_auc": float(r["roc_auc"] - b["roc_auc"]),
                "d_pr_auc": float(r["pr_auc"] - b["pr_auc"]),
                "d_brier": float(r["brier"] - b["brier"]),
            }
        )

    delta_df = pd.DataFrame(delta_rows).sort_values(["scenario", "domain"])
    delta_path = OUT_TABLES / "scenario_delta_vs_best.csv"
    delta_df.to_csv(delta_path, index=False)

    caregiver_mean = scenario_metrics[scenario_metrics["scenario"] == "caregiver"]["ba"].mean()
    psy_no_has_mean = scenario_metrics[scenario_metrics["scenario"] == "psychologist_no_has"]["ba"].mean()
    psy_with_has_mean = scenario_metrics[scenario_metrics["scenario"] == "psychologist_with_has"]["ba"].mean()

    delta_caregiver_vs_with = caregiver_mean - psy_with_has_mean
    delta_no_has_vs_with = psy_no_has_mean - psy_with_has_mean

    has_effect = "material" if abs(delta_no_has_vs_with) >= 0.01 else "no_material"

    worst_no_has = (
        delta_df[delta_df["scenario"] == "psychologist_no_has"]
        .sort_values("d_ba")
        .iloc[0]["domain"]
    )

    report_lines = [
        "# scenario_decision_report",
        "",
        "## Resumen ejecutivo",
        f"- Mejor escenario global (BA media): {best_scenario}.",
        f"- BA media caregiver: {caregiver_mean:.4f}",
        f"- BA media psychologist_no_has: {psy_no_has_mean:.4f}",
        f"- BA media psychologist_with_has: {psy_with_has_mean:.4f}",
        "",
        "## Comparacion solicitada",
        f"- Perdida caregiver vs psychologist_with_has (BA): {delta_caregiver_vs_with:.4f}",
        f"- Perdida psychologist_no_has vs psychologist_with_has (BA): {delta_no_has_vs_with:.4f}",
        f"- Aporte de has_*: {has_effect}",
        f"- Dominio mas afectado al quitar has_* (d_ba minimo): {worst_no_has}",
        "",
        "## Lectura por escenario",
        "- caregiver: flujo mas simple, menor cobertura de inputs y mayor dependencia de defaults.",
        "- psychologist_no_has: mantiene casi todo el flujo psicologo, removiendo solo has_* y derivandolos cuando hay evidencia.",
        "- psychologist_with_has: referencia de flujo psicologo completo.",
        "",
        "## Recomendacion practica",
        "- Producto: mantener psychologist_with_has como referencia clinica completa.",
        "- Si se busca simplificar, psychologist_no_has es viable cuando la perdida no sea material en BA/PR-AUC.",
        "- caregiver sigue usable para screening rapido, con caveat explicito por menor cobertura.",
        "",
        "## Caveats",
        "- Evaluacion sin reentrenar, con thresholds finales v15 y holdout strict_full.",
        "- El alcance usa lineas finales vigentes: no-elimination final_hardening_v10 y elimination_clean_rebuild_v12.",
    ]

    report_path = OUT_REPORTS / "scenario_decision_report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest = {
        "line": "questionnaire_scenario_eval_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "non_elimination_valid_from": "final_hardening_v10",
            "elimination_valid_from": "elimination_clean_rebuild_v12",
            "no_retraining": True,
            "split": "strict_full_test",
        },
        "scenarios": ["caregiver", "psychologist_no_has", "psychologist_with_has"],
        "best_scenario_global": best_scenario,
        "has_flags_material_effect": has_effect,
        "files": [
            str(scenario_results_path.relative_to(ROOT)),
            str(scenario_metrics_path.relative_to(ROOT)),
            str(coverage_path.relative_to(ROOT)),
            str(delta_path.relative_to(ROOT)),
            str(report_path.relative_to(ROOT)),
        ],
    }

    manifest_path = OUT_ARTIFACTS / "scenario_eval_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("BEST_SCENARIO", best_scenario)
    print("BA_CAREGIVER", round(float(caregiver_mean), 6))
    print("BA_PSY_NO_HAS", round(float(psy_no_has_mean), 6))
    print("BA_PSY_WITH_HAS", round(float(psy_with_has_mean), 6))
    print("HAS_EFFECT", has_effect)


if __name__ == "__main__":
    main()
