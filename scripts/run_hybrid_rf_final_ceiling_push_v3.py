#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
LINE_NAME = "hybrid_rf_final_ceiling_push_v3"
BASE = ROOT / "data" / LINE_NAME
INV = BASE / "inventory"
TRIALS = BASE / "trials"
FEATSEL = BASE / "feature_selection"
THRESH = BASE / "thresholds"
BOOT = BASE / "bootstrap"
STAB = BASE / "stability"
ABL = BASE / "ablation"
STRESS = BASE / "stress"
CAL = BASE / "calibration"
TABLES = BASE / "tables"
REPORTS = BASE / "reports"
SPLITS_DIR = BASE / "splits"
ART = ROOT / "artifacts" / LINE_NAME

SOURCE_BASE = ROOT / "data" / "hybrid_dsm5_rebuild_v1"
DATASET_PATH = SOURCE_BASE / "hybrid_dataset_synthetic_complete_final.csv"
RESPONDABILITY_PATH = SOURCE_BASE / "hybrid_model_input_respondability_final.csv"
RESPONDABILITY_SUMMARY_PATH = SOURCE_BASE / "hybrid_model_input_respondability_summary_final.csv"
MODE_MATRIX_PATH = SOURCE_BASE / "questionnaire_modes_priority_matrix_final.csv"
PREV_INVENTORY_PATH = ROOT / "data" / "final_ceiling_check_v15" / "inventory" / "final_model_inventory.csv"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
BASE_SEED = 20260712
STAGE2_SEEDS = [20260712, 20260729]
THRESHOLD_POLICIES = [
    "default_0_5",
    "precision_oriented",
    "balanced",
    "recall_guard",
    "precision_min_recall",
]
CALIBRATION_METHODS = ["none", "sigmoid", "isotonic"]


@dataclass(frozen=True)
class ModeSpec:
    mode: str
    role: str
    include_col: str


MODE_SPECS = [
    ModeSpec("caregiver_1_3", "caregiver", "include_caregiver_1_3"),
    ModeSpec("caregiver_2_3", "caregiver", "include_caregiver_2_3"),
    ModeSpec("caregiver_full", "caregiver", "include_caregiver_full"),
    ModeSpec("psychologist_1_3", "psychologist", "include_psychologist_1_3"),
    ModeSpec("psychologist_2_3", "psychologist", "include_psychologist_2_3"),
    ModeSpec("psychologist_full", "psychologist", "include_psychologist_full"),
]

RF_CONFIGS: list[dict[str, Any]] = [
    {
        "config_id": "rf_baseline",
        "n_estimators": 240,
        "max_depth": None,
        "min_samples_split": 4,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "class_weight": None,
        "bootstrap": True,
        "max_samples": None,
    },
    {
        "config_id": "rf_balanced_subsample",
        "n_estimators": 300,
        "max_depth": 22,
        "min_samples_split": 4,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": 0.9,
    },
    {
        "config_id": "rf_precision_push",
        "n_estimators": 280,
        "max_depth": 18,
        "min_samples_split": 8,
        "min_samples_leaf": 3,
        "max_features": 0.55,
        "class_weight": {0: 1.0, 1: 1.35},
        "bootstrap": True,
        "max_samples": None,
    },
    {
        "config_id": "rf_recall_guard",
        "n_estimators": 300,
        "max_depth": None,
        "min_samples_split": 4,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "class_weight": {0: 1.0, 1: 1.8},
        "bootstrap": True,
        "max_samples": None,
    },
    {
        "config_id": "rf_regularized",
        "n_estimators": 260,
        "max_depth": 14,
        "min_samples_split": 10,
        "min_samples_leaf": 4,
        "max_features": 0.45,
        "class_weight": "balanced",
        "bootstrap": True,
        "max_samples": 0.85,
    },
    {
        "config_id": "rf_positive_push_strong",
        "n_estimators": 320,
        "max_depth": 20,
        "min_samples_split": 6,
        "min_samples_leaf": 2,
        "max_features": 0.6,
        "class_weight": {0: 1.0, 1: 2.2},
        "bootstrap": True,
        "max_samples": 0.9,
    },
]

RF_CONFIG_BY_ID = {cfg["config_id"]: cfg for cfg in RF_CONFIGS}

# Transparent derived dependencies anchored in explicit DSM5/base features.
DERIVED_DEPENDENCIES: dict[str, list[str]] = {
    "adhd_inattention_symptom_count": [
        "adhd_inatt_01_attention_to_detail_errors",
        "adhd_inatt_02_sustained_attention_difficulty",
        "adhd_inatt_03_seems_not_listening",
        "adhd_inatt_04_fails_to_finish_tasks",
        "adhd_inatt_05_organization_difficulty",
        "adhd_inatt_06_avoids_sustained_effort",
        "adhd_inatt_07_loses_things",
        "adhd_inatt_08_easily_distracted",
        "adhd_inatt_09_forgetful_daily_activities",
    ],
    "adhd_hyperimpulsive_symptom_count": [
        "adhd_hypimp_01_fidgets",
        "adhd_hypimp_02_leaves_seat",
        "adhd_hypimp_03_runs_or_climbs_inappropriately",
        "adhd_hypimp_04_cannot_play_quietly",
        "adhd_hypimp_05_driven_by_motor",
        "adhd_hypimp_06_talks_excessively",
        "adhd_hypimp_07_blurts_out",
        "adhd_hypimp_08_difficulty_waiting_turn",
        "adhd_hypimp_09_interrupts_intrudes",
    ],
    "adhd_context_count": ["adhd_context_home", "adhd_context_school", "adhd_context_other"],
    "adhd_two_plus_contexts": ["adhd_context_count"],
    "adhd_impairment_max": ["adhd_impairment_home", "adhd_impairment_school", "adhd_impairment_social"],
    "conduct_symptom_count_12m": [
        "conduct_01_bullies_threatens_intimidates",
        "conduct_02_initiates_fights",
        "conduct_03_weapon_use",
        "conduct_04_physical_cruelty_people",
        "conduct_05_physical_cruelty_animals",
        "conduct_06_steals_confronting_victim",
        "conduct_07_forced_sex",
        "conduct_08_fire_setting",
        "conduct_09_property_destruction",
        "conduct_10_breaks_into_house_building_car",
        "conduct_11_lies_to_obtain_or_avoid",
        "conduct_12_steals_without_confrontation",
        "conduct_13_stays_out_at_night_before_13",
        "conduct_14_runs_away_overnight",
        "conduct_15_truancy_before_13",
    ],
    "conduct_recent_6m_count": [
        "conduct_01_bullies_threatens_intimidates",
        "conduct_02_initiates_fights",
        "conduct_03_weapon_use",
        "conduct_04_physical_cruelty_people",
        "conduct_05_physical_cruelty_animals",
        "conduct_06_steals_confronting_victim",
        "conduct_07_forced_sex",
        "conduct_08_fire_setting",
        "conduct_09_property_destruction",
    ],
    "conduct_aggression_count": [
        "conduct_01_bullies_threatens_intimidates",
        "conduct_02_initiates_fights",
        "conduct_03_weapon_use",
        "conduct_04_physical_cruelty_people",
        "conduct_05_physical_cruelty_animals",
        "conduct_06_steals_confronting_victim",
        "conduct_07_forced_sex",
    ],
    "conduct_destruction_count": ["conduct_08_fire_setting", "conduct_09_property_destruction"],
    "conduct_deceit_theft_count": [
        "conduct_10_breaks_into_house_building_car",
        "conduct_11_lies_to_obtain_or_avoid",
        "conduct_12_steals_without_confrontation",
    ],
    "conduct_serious_rule_violation_count": [
        "conduct_13_stays_out_at_night_before_13",
        "conduct_14_runs_away_overnight",
        "conduct_15_truancy_before_13",
    ],
    "conduct_lpe_count": [
        "conduct_lpe_01_lack_remorse_guilt",
        "conduct_lpe_02_callous_lack_empathy",
        "conduct_lpe_03_unconcerned_performance",
        "conduct_lpe_04_shallow_deficient_affect",
    ],
    "enuresis_age_ge_5": ["age_years"],
    "encopresis_age_ge_4": ["age_years"],
    "sep_anx_symptom_count": [
        "sep_anx_01_distress_on_separation",
        "sep_anx_02_worry_losing_attachment_figures",
        "sep_anx_03_worry_event_causing_separation",
        "sep_anx_04_refuses_leaving_home_school",
        "sep_anx_05_fear_being_alone_without_attachment",
        "sep_anx_06_refuses_sleep_away_or_alone",
        "sep_anx_07_separation_nightmares",
        "sep_anx_08_physical_complaints_on_separation",
    ],
    "gad_assoc_symptom_count": [
        "gad_assoc_01_restlessness",
        "gad_assoc_02_fatigue",
        "gad_assoc_03_concentration_difficulty",
        "gad_assoc_04_irritability",
        "gad_assoc_05_muscle_tension",
        "gad_assoc_06_sleep_problems",
    ],
    "agor_situation_count": [
        "agor_fear_01_public_transport",
        "agor_fear_02_open_spaces",
        "agor_fear_03_enclosed_spaces",
        "agor_fear_04_crowds_queues",
        "agor_fear_05_outside_home_alone",
    ],
    "mdd_symptom_count": [
        "mdd_01_depressed_or_irritable_mood",
        "mdd_02_loss_of_interest_or_pleasure",
        "mdd_03_weight_or_appetite_change",
        "mdd_04_sleep_change",
        "mdd_05_psychomotor_change",
        "mdd_06_fatigue_or_low_energy",
        "mdd_07_worthlessness_or_excessive_guilt",
        "mdd_08_concentration_or_decision_difficulty",
        "mdd_09_death_or_suicidal_thoughts",
    ],
    "mdd_core_symptom_met": ["mdd_01_depressed_or_irritable_mood", "mdd_02_loss_of_interest_or_pleasure"],
    "dmdd_context_count": ["dmdd_context_home", "dmdd_context_school", "dmdd_context_peers"],
    "dmdd_one_setting_severe": ["dmdd_context_count", "dmdd_context_home", "dmdd_context_school", "dmdd_context_peers"],
    "pdd_symptom_count": [
        "pdd_01_appetite_change",
        "pdd_02_sleep_change",
        "pdd_03_low_energy",
        "pdd_04_low_self_esteem",
        "pdd_05_concentration_difficulty",
        "pdd_06_hopelessness",
    ],
}

SAFE_DERIVED_FEATURES = sorted(DERIVED_DEPENDENCIES.keys())
LEAKAGE_GUARD_PATTERNS = (
    "_threshold_met",
    "final_dsm5_threshold_met",
    "any_module_threshold_met",
    "target_domain_",
)
LEAKAGE_GUARD_EXACT = {
    "elimination_type_code",
    "adhd_presentation_code",
    "anxiety_module_count_positive",
    "dmdd_age_6_to_18",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    for p in [BASE, INV, TRIALS, FEATSEL, THRESH, BOOT, STAB, ABL, STRESS, CAL, TABLES, REPORTS, SPLITS_DIR, ART]:
        p.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def safe_float(x: Any) -> float | None:
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def percent_fmt(x: float | None) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "NA"
    return f"{x:.2%}"


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_sin datos_"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals: list[str] = []
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


def print_progress(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def expected_calibration_error(y_true: np.ndarray, probs: np.ndarray, bins: int = 10) -> float:
    if len(y_true) == 0:
        return 0.0
    probs = np.clip(probs, 1e-6, 1 - 1e-6)
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.digitize(probs, edges[1:-1], right=False)
    ece = 0.0
    n = len(y_true)
    for b in range(bins):
        mask = idx == b
        if not np.any(mask):
            continue
        conf = float(np.mean(probs[mask]))
        acc = float(np.mean(y_true[mask]))
        ece += (np.sum(mask) / n) * abs(acc - conf)
    return float(ece)


def safe_roc_auc(y_true: np.ndarray, probs: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, probs))


def safe_pr_auc(y_true: np.ndarray, probs: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float(np.mean(y_true))
    return float(average_precision_score(y_true, probs))


def compute_metrics(y_true: np.ndarray, probs: np.ndarray, threshold: float) -> dict[str, float]:
    pred = (probs >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    spec = float(tn / (tn + fp)) if (tn + fp) else 0.0
    return {
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "specificity": spec,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": safe_roc_auc(y_true, probs),
        "pr_auc": safe_pr_auc(y_true, probs),
        "brier": float(brier_score_loss(y_true, np.clip(probs, 1e-6, 1 - 1e-6))),
        "accuracy": float(accuracy_score(y_true, pred)),
    }


def objective_from_metrics(metrics: dict[str, float]) -> float:
    return (
        0.40 * metrics["precision"]
        + 0.24 * metrics["balanced_accuracy"]
        + 0.16 * metrics["pr_auc"]
        + 0.12 * metrics["recall"]
        + 0.08 * metrics["specificity"]
        - 0.06 * metrics["brier"]
    )


def load_source_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(DATASET_PATH)
    respondability = pd.read_csv(RESPONDABILITY_PATH)
    respondability_summary = pd.read_csv(RESPONDABILITY_SUMMARY_PATH)
    mode_matrix = pd.read_csv(MODE_MATRIX_PATH)
    return df, respondability, respondability_summary, mode_matrix


def normalize_include_flag(x: Any) -> str:
    if pd.isna(x):
        return "no"
    return str(x).strip().lower()

def choose_target_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], dict[str, list[str]], pd.DataFrame]:
    work = df.copy()
    target_col_by_domain: dict[str, str] = {}
    target_components: dict[str, list[str]] = {}
    registry_rows: list[dict[str, Any]] = []

    candidates = {
        "adhd": ["adhd_final_dsm5_threshold_met", "adhd_inattention_threshold_child", "adhd_hyperimpulsive_threshold_child"],
        "conduct": ["conduct_final_dsm5_threshold_met", "conduct_threshold_met"],
        "elimination": ["elimination_any_threshold_met", "enuresis_threshold_met", "encopresis_threshold_met"],
        "anxiety": [
            "anxiety_any_module_threshold_met",
            "sep_anx_threshold_met",
            "social_anxiety_threshold_met",
            "gad_threshold_met_child",
            "agor_threshold_met",
        ],
        "depression": ["target_domain_depression_final", "mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"],
    }

    for domain in DOMAINS:
        chosen: str | None = None
        selection_status = "selected"
        rationale = "first defendable candidate available"
        considered = candidates[domain]

        if domain == "depression":
            comp = [c for c in ["mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"] if c in work.columns]
            if len(comp) == 3:
                work["target_domain_depression_final"] = (
                    work[["mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"]]
                    .apply(pd.to_numeric, errors="coerce")
                    .fillna(0)
                    .max(axis=1)
                    .astype(int)
                )
                chosen = "target_domain_depression_final"
                target_components[domain] = comp
                rationale = "OR aggregation of MDD/DMDD/PDD thresholds for external depression domain"
            else:
                selection_status = "por_confirmar"
                rationale = "depression aggregation fallback due missing module thresholds"

        if chosen is None:
            for c in considered:
                if c in work.columns:
                    chosen = c
                    if domain != "depression":
                        target_components[domain] = [c]
                    elif domain == "depression" and domain not in target_components:
                        target_components[domain] = [c]
                    break

        if chosen is None:
            raise RuntimeError(f"No target candidate found for domain={domain}")

        target_col = f"target_domain_{domain}_final"
        work[target_col] = pd.to_numeric(work[chosen], errors="coerce").fillna(0).astype(int)
        if not set(work[target_col].unique()).issubset({0, 1}):
            work[target_col] = (work[target_col] > 0).astype(int)

        n_pos = int((work[target_col] == 1).sum())
        n_neg = int((work[target_col] == 0).sum())
        prev = float(work[target_col].mean())
        target_col_by_domain[domain] = target_col
        registry_rows.append(
            {
                "domain": domain,
                "selected_target_column": target_col,
                "source_column_or_rule": chosen,
                "selection_status": selection_status,
                "selection_rationale": rationale,
                "candidates_considered": "|".join(considered),
                "candidate_columns_present": "|".join([c for c in considered if c in work.columns]),
                "n_positive": n_pos,
                "n_negative": n_neg,
                "positive_rate": prev,
                "por_confirmar_note": "" if selection_status == "selected" else "target selection used fallback logic",
            }
        )
    return work, target_col_by_domain, target_components, pd.DataFrame(registry_rows)


def leakage_like_feature(feature: str) -> bool:
    low = feature.lower()
    if feature in LEAKAGE_GUARD_EXACT:
        return True
    return any(token in low for token in LEAKAGE_GUARD_PATTERNS)


def build_mode_feature_maps(
    df: pd.DataFrame,
    respondability: pd.DataFrame,
    mode_matrix: pd.DataFrame,
) -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    direct = set(
        respondability[
            respondability["is_direct_input"].astype(str).str.lower().eq("yes")
            & respondability["keep_for_model_v1"].astype(str).str.lower().eq("yes")
        ]["feature"].astype(str)
    )
    transparent = set(
        respondability[
            respondability["is_transparent_derived"].astype(str).str.lower().eq("yes")
            & respondability["keep_for_model_v1"].astype(str).str.lower().eq("yes")
        ]["feature"].astype(str)
    )

    mode_features: dict[str, dict[str, list[str]]] = {}
    coverage_rows: list[dict[str, Any]] = []

    for spec in MODE_SPECS:
        include_col = spec.include_col
        if include_col not in mode_matrix.columns:
            raise RuntimeError(f"Missing mode include column: {include_col}")
        direct_from_matrix = set(
            mode_matrix[mode_matrix[include_col].map(normalize_include_flag).eq("si")]["feature"].astype(str)
        )
        direct_usable = sorted(f for f in direct_from_matrix if f in direct and f in df.columns)

        available = set(direct_usable)
        derived_selected: list[str] = []
        changed = True
        while changed:
            changed = False
            for feat in SAFE_DERIVED_FEATURES:
                if feat in available:
                    continue
                if feat not in transparent:
                    continue
                if feat not in df.columns:
                    continue
                deps = DERIVED_DEPENDENCIES.get(feat, [])
                if deps and set(deps).issubset(available):
                    available.add(feat)
                    derived_selected.append(feat)
                    changed = True

        derived_selected = sorted(set(derived_selected))
        eligible = sorted(set(direct_usable) | set(derived_selected))
        mode_features[spec.mode] = {
            "role": [spec.role],
            "direct": direct_usable,
            "derived": derived_selected,
            "eligible": eligible,
        }
        coverage_rows.append(
            {
                "mode": spec.mode,
                "role": spec.role,
                "direct_features_from_priority_matrix": int(len(direct_from_matrix)),
                "direct_features_usable_in_dataset": int(len(direct_usable)),
                "transparent_derived_eligible": int(len(derived_selected)),
                "total_eligible_features": int(len(eligible)),
            }
        )

    coverage_df = pd.DataFrame(coverage_rows).sort_values(["role", "mode"]).reset_index(drop=True)
    return mode_features, coverage_df


def build_split_registry(
    df: pd.DataFrame,
    target_col_by_domain: dict[str, str],
) -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    split_ids: dict[str, dict[str, list[str]]] = {}
    rows: list[dict[str, Any]] = []

    participant_ids = df["participant_id"].astype(str).tolist()
    for idx, domain in enumerate(DOMAINS):
        y = df[target_col_by_domain[domain]].astype(int)
        ids = np.array(participant_ids, dtype=object)
        seed = BASE_SEED + idx * 17
        strat = y if len(np.unique(y)) >= 2 else None

        ids_train, ids_tmp, y_train, y_tmp = train_test_split(
            ids,
            y,
            test_size=0.40,
            random_state=seed,
            stratify=strat,
        )
        strat_tmp = y_tmp if len(np.unique(y_tmp)) >= 2 else None
        ids_val, ids_hold, y_val, y_hold = train_test_split(
            ids_tmp,
            y_tmp,
            test_size=0.50,
            random_state=seed + 1,
            stratify=strat_tmp,
        )

        split_ids[domain] = {
            "train": [str(x) for x in ids_train.tolist()],
            "val": [str(x) for x in ids_val.tolist()],
            "holdout": [str(x) for x in ids_hold.tolist()],
        }

        domain_dir = SPLITS_DIR / f"domain_{domain}"
        save_csv(pd.DataFrame({"participant_id": split_ids[domain]["train"]}), domain_dir / "ids_train.csv")
        save_csv(pd.DataFrame({"participant_id": split_ids[domain]["val"]}), domain_dir / "ids_val.csv")
        save_csv(pd.DataFrame({"participant_id": split_ids[domain]["holdout"]}), domain_dir / "ids_holdout.csv")

        rows.append(
            {
                "split_version": LINE_NAME,
                "domain": domain,
                "target_column": target_col_by_domain[domain],
                "split_seed": seed,
                "stratified": "yes" if strat is not None else "no",
                "train_n": len(ids_train),
                "val_n": len(ids_val),
                "holdout_n": len(ids_hold),
                "train_positive_rate": float(np.mean(y_train)),
                "val_positive_rate": float(np.mean(y_val)),
                "holdout_positive_rate": float(np.mean(y_hold)),
                "ids_train_path": str((domain_dir / "ids_train.csv").relative_to(ROOT)).replace("\\", "/"),
                "ids_val_path": str((domain_dir / "ids_val.csv").relative_to(ROOT)).replace("\\", "/"),
                "ids_holdout_path": str((domain_dir / "ids_holdout.csv").relative_to(ROOT)).replace("\\", "/"),
            }
        )
    return split_ids, pd.DataFrame(rows)


def subset_by_ids(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()


def prepare_X(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    X = df[features].copy()
    for c in X.columns:
        if c == "sex_assigned_at_birth":
            X[c] = X[c].fillna("Unknown").astype(str)
        else:
            X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)
    return X


def make_pipeline(features: list[str], cfg: dict[str, Any], seed: int) -> Pipeline:
    cat_cols = [c for c in features if c == "sex_assigned_at_birth"]
    num_cols = [c for c in features if c not in cat_cols]
    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num_cols),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                cat_cols,
            ),
        ],
        remainder="drop",
    )
    model = RandomForestClassifier(
        n_estimators=int(cfg["n_estimators"]),
        max_depth=cfg["max_depth"],
        min_samples_split=int(cfg["min_samples_split"]),
        min_samples_leaf=int(cfg["min_samples_leaf"]),
        max_features=cfg["max_features"],
        class_weight=cfg["class_weight"],
        bootstrap=bool(cfg["bootstrap"]),
        max_samples=cfg["max_samples"],
        random_state=seed,
        n_jobs=1,
    )
    return Pipeline([("pre", pre), ("rf", model)])


def aggregate_importance(pipe: Pipeline, feature_names: list[str]) -> pd.Series:
    pre = pipe.named_steps["pre"]
    rf = pipe.named_steps["rf"]
    transformed = pre.get_feature_names_out()
    importance = rf.feature_importances_
    agg: dict[str, float] = {f: 0.0 for f in feature_names}
    for t_name, val in zip(transformed, importance):
        clean = str(t_name)
        orig = clean
        if clean.startswith("num__"):
            orig = clean.split("num__", 1)[1]
        elif clean.startswith("cat__"):
            tail = clean.split("cat__", 1)[1]
            if tail.startswith("sex_assigned_at_birth"):
                orig = "sex_assigned_at_birth"
            else:
                orig = tail.split("_", 1)[0]
        if orig in agg:
            agg[orig] += float(val)
    return pd.Series(agg).sort_values(ascending=False)


def effect_size_rank(train_df: pd.DataFrame, features: list[str], target_col: str) -> pd.Series:
    y = train_df[target_col].astype(int)
    out: dict[str, float] = {}
    for f in features:
        s = train_df[f]
        if not pd.api.types.is_numeric_dtype(s):
            s = s.astype(str).fillna("Unknown").astype("category").cat.codes.astype(float)
        else:
            s = pd.to_numeric(s, errors="coerce")
        pos = s[y == 1]
        neg = s[y == 0]
        denom = float(np.nanstd(s.values)) + 1e-9
        out[f] = float(abs(np.nanmean(pos.values) - np.nanmean(neg.values)) / denom)
    return pd.Series(out).sort_values(ascending=False)

def build_feature_sets(
    train_df: pd.DataFrame,
    feature_pool: list[str],
    target_col: str,
    domain: str,
    mode: str,
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    if len(feature_pool) < 8:
        raise RuntimeError(f"Not enough eligible features for {mode}/{domain}: {len(feature_pool)}")

    proxy_cfg = RF_CONFIG_BY_ID["rf_baseline"]
    proxy = make_pipeline(feature_pool, proxy_cfg, BASE_SEED)
    Xtr = prepare_X(train_df, feature_pool)
    ytr = train_df[target_col].astype(int).to_numpy()
    proxy.fit(Xtr, ytr)
    imp_rank = aggregate_importance(proxy, feature_pool)
    eff_rank = effect_size_rank(train_df, feature_pool, target_col)

    n = len(feature_pool)
    top_imp_n = min(n, max(12, int(round(n * 0.70))))
    compact_n = min(n, max(10, int(round(n * 0.45))))
    precision_n = min(n, max(10, int(round(n * 0.40))))
    balanced_n = min(n, max(12, int(round(n * 0.55))))
    stable_n = min(n, max(12, int(round(n * 0.50))))

    full = sorted(feature_pool)
    top_imp = imp_rank.head(top_imp_n).index.tolist()
    compact = imp_rank.head(compact_n).index.tolist()
    precision = eff_rank.head(precision_n).index.tolist()

    # Correlation-pruned balanced subset.
    corr_df = train_df[feature_pool].copy()
    for c in corr_df.columns:
        if not pd.api.types.is_numeric_dtype(corr_df[c]):
            corr_df[c] = corr_df[c].astype(str).fillna("Unknown").astype("category").cat.codes.astype(float)
    corr_df = corr_df.apply(pd.to_numeric, errors="coerce").fillna(corr_df.median(numeric_only=True))
    corr = corr_df.corr().abs()
    balanced: list[str] = []
    for f in imp_rank.index.tolist():
        if len(balanced) >= balanced_n:
            break
        keep = True
        for prev in balanced:
            try:
                if float(corr.loc[f, prev]) >= 0.92:
                    keep = False
                    break
            except Exception:
                continue
        if keep:
            balanced.append(f)
    if len(balanced) < 8:
        balanced = imp_rank.head(balanced_n).index.tolist()

    # Stability-pruned subset: keep features with consistent importance rank over multiple seeds.
    stability_scores: dict[str, float] = {f: 0.0 for f in feature_pool}
    for local_seed in [BASE_SEED, BASE_SEED + 19, BASE_SEED + 43]:
        stab_proxy = make_pipeline(feature_pool, proxy_cfg, local_seed)
        stab_proxy.fit(Xtr, ytr)
        stab_rank = aggregate_importance(stab_proxy, feature_pool)
        for pos, feat in enumerate(stab_rank.index.tolist(), start=1):
            stability_scores[feat] += 1.0 / float(pos)
    stable_rank = pd.Series(stability_scores).sort_values(ascending=False)
    stability_pruned = stable_rank.head(stable_n).index.tolist()

    feature_sets = {
        "full_eligible": full,
        "top_importance_filtered": sorted(set(top_imp)),
        "compact_robust_subset": sorted(set(compact)),
        "precision_oriented_subset": sorted(set(precision)),
        "balanced_subset": sorted(set(balanced)),
        "stability_pruned_subset": sorted(set(stability_pruned)),
    }

    # Enforce minimum size and deduplicate accidental equals.
    cleaned: dict[str, list[str]] = {}
    seen_signatures: set[tuple[str, ...]] = set()
    for fs_id, feats in feature_sets.items():
        unique_feats = sorted(set(feats))
        if len(unique_feats) < 8:
            unique_feats = sorted(set(imp_rank.head(max(8, len(unique_feats))).index.tolist()))
        sig = tuple(unique_feats)
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)
        cleaned[fs_id] = unique_feats

    rows: list[dict[str, Any]] = []
    for fs_id, feats in cleaned.items():
        rows.append(
            {
                "mode": mode,
                "domain": domain,
                "feature_set_id": fs_id,
                "n_features": len(feats),
                "feature_list_pipe": "|".join(feats),
                "construction_rule": {
                    "full_eligible": "all eligible features under mode respondability constraints",
                    "top_importance_filtered": "top 70pct by RF importance",
                    "compact_robust_subset": "top 45pct by RF importance",
                    "precision_oriented_subset": "top 40pct by class-separation effect size",
                    "balanced_subset": "importance-driven with correlation pruning",
                    "stability_pruned_subset": "importance consistency across repeated seed fits",
                }.get(fs_id, "derived"),
            }
        )
    return cleaned, rows


def choose_threshold(
    policy: str,
    y_true: np.ndarray,
    probs: np.ndarray,
    recall_floor: float,
) -> tuple[float, float]:
    if policy == "default_0_5":
        m = compute_metrics(y_true, probs, 0.5)
        return 0.5, objective_from_metrics(m)

    grid = np.linspace(0.05, 0.95, 181)
    best_thr = 0.5
    best_score = -1e9

    for thr in grid:
        m = compute_metrics(y_true, probs, float(thr))
        if policy == "precision_oriented":
            if m["recall"] < max(0.50, recall_floor):
                continue
            score = 0.62 * m["precision"] + 0.18 * m["balanced_accuracy"] + 0.12 * m["pr_auc"] + 0.08 * m["recall"]
        elif policy == "balanced":
            score = 0.50 * m["balanced_accuracy"] + 0.20 * m["f1"] + 0.15 * m["precision"] + 0.15 * m["recall"]
        elif policy == "recall_constrained":
            if m["recall"] < max(0.65, recall_floor):
                continue
            score = 0.48 * m["precision"] + 0.22 * m["balanced_accuracy"] + 0.20 * m["recall"] + 0.10 * m["pr_auc"]
        elif policy == "recall_guard":
            if m["recall"] < max(0.72, recall_floor):
                continue
            score = 0.38 * m["precision"] + 0.26 * m["balanced_accuracy"] + 0.28 * m["recall"] + 0.08 * m["pr_auc"]
        elif policy == "precision_min_recall":
            if m["recall"] < max(0.58, recall_floor):
                continue
            if m["balanced_accuracy"] < 0.78:
                continue
            score = 0.66 * m["precision"] + 0.16 * m["balanced_accuracy"] + 0.10 * m["pr_auc"] + 0.08 * m["recall"]
        else:
            score = objective_from_metrics(m)
        if score > best_score:
            best_score = float(score)
            best_thr = float(thr)

    if best_score < -1e8:
        m = compute_metrics(y_true, probs, 0.5)
        return 0.5, objective_from_metrics(m)
    return best_thr, best_score


def calibrate_probabilities(
    y_val: np.ndarray,
    train_raw: np.ndarray,
    val_raw: np.ndarray,
    hold_raw: np.ndarray,
) -> tuple[dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]], dict[str, dict[str, float]], dict[str, Callable[[np.ndarray], np.ndarray]]]:
    out_probs: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    out_diag: dict[str, dict[str, float]] = {}
    transforms: dict[str, Callable[[np.ndarray], np.ndarray]] = {}

    def ident(x: np.ndarray) -> np.ndarray:
        return np.clip(x, 1e-6, 1 - 1e-6)

    out_probs["none"] = (ident(train_raw), ident(val_raw), ident(hold_raw))
    out_diag["none"] = {
        "val_brier": float(brier_score_loss(y_val, ident(val_raw))),
        "val_ece": float(expected_calibration_error(y_val, ident(val_raw))),
    }
    transforms["none"] = ident

    if len(np.unique(y_val)) >= 2:
        # Sigmoid (Platt scaling over validation scores)
        lr = LogisticRegression(max_iter=1200)
        lr.fit(val_raw.reshape(-1, 1), y_val.astype(int))

        def tf_sigmoid(x: np.ndarray) -> np.ndarray:
            return np.clip(lr.predict_proba(x.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6)

        out_probs["sigmoid"] = (tf_sigmoid(train_raw), tf_sigmoid(val_raw), tf_sigmoid(hold_raw))
        out_diag["sigmoid"] = {
            "val_brier": float(brier_score_loss(y_val, out_probs["sigmoid"][1])),
            "val_ece": float(expected_calibration_error(y_val, out_probs["sigmoid"][1])),
        }
        transforms["sigmoid"] = tf_sigmoid

        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(val_raw, y_val.astype(int))

        def tf_iso(x: np.ndarray) -> np.ndarray:
            return np.clip(iso.predict(x), 1e-6, 1 - 1e-6)

        out_probs["isotonic"] = (tf_iso(train_raw), tf_iso(val_raw), tf_iso(hold_raw))
        out_diag["isotonic"] = {
            "val_brier": float(brier_score_loss(y_val, out_probs["isotonic"][1])),
            "val_ece": float(expected_calibration_error(y_val, out_probs["isotonic"][1])),
        }
        transforms["isotonic"] = tf_iso

    return out_probs, out_diag, transforms


def bootstrap_metric_ci(
    y_true: np.ndarray,
    probs: np.ndarray,
    threshold: float,
    n_boot: int = 350,
    seed: int = 42,
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    idx_all = np.arange(len(y_true))
    metrics_names = ["precision", "recall", "balanced_accuracy", "pr_auc", "brier"]
    history: dict[str, list[float]] = {m: [] for m in metrics_names}
    for _ in range(n_boot):
        idx = rng.choice(idx_all, size=len(idx_all), replace=True)
        m = compute_metrics(y_true[idx], probs[idx], threshold)
        for name in metrics_names:
            history[name].append(float(m[name]))
    out: dict[str, float] = {}
    for name in metrics_names:
        arr = np.array(history[name], dtype=float)
        out[f"{name}_boot_mean"] = float(np.mean(arr))
        out[f"{name}_boot_ci_low"] = float(np.quantile(arr, 0.025))
        out[f"{name}_boot_ci_high"] = float(np.quantile(arr, 0.975))
    return out


def inject_missing(X: pd.DataFrame, features: list[str], ratio: float, seed: int) -> pd.DataFrame:
    out = X.copy()
    rng = np.random.default_rng(seed)
    for f in features:
        if f not in out.columns:
            continue
        if f != "sex_assigned_at_birth":
            out[f] = pd.to_numeric(out[f], errors="coerce").astype(float)
        mask = rng.random(len(out)) < ratio
        out.loc[mask, f] = np.nan
    return out


def select_stage1_combos(stage1_df: pd.DataFrame) -> list[tuple[str, str]]:
    if stage1_df.empty:
        return []
    grouped = (
        stage1_df.groupby(["feature_set_id", "config_id"], as_index=False)
        .agg(
            val_precision=("val_precision", "mean"),
            val_recall=("val_recall", "mean"),
            val_ba=("val_balanced_accuracy", "mean"),
            val_pr_auc=("val_pr_auc", "mean"),
            val_brier=("val_brier", "mean"),
            train_ba=("train_balanced_accuracy", "mean"),
            stage1_score=("stage1_score", "mean"),
        )
        .copy()
    )
    baseline = grouped[(grouped["feature_set_id"] == "full_eligible") & (grouped["config_id"] == "rf_baseline")]
    if baseline.empty:
        base_rec = float(grouped["val_recall"].median())
        base_ba = float(grouped["val_ba"].median())
    else:
        base_rec = float(baseline.iloc[0]["val_recall"])
        base_ba = float(baseline.iloc[0]["val_ba"])
    grouped["guard_ok"] = (
        (grouped["val_recall"] >= max(0.35, base_rec - 0.18))
        & (grouped["val_ba"] >= max(0.55, base_ba - 0.04))
    )
    grouped["rank_score"] = (
        0.42 * grouped["val_precision"]
        + 0.24 * grouped["val_ba"]
        + 0.18 * grouped["val_pr_auc"]
        + 0.10 * grouped["val_recall"]
        - 0.06 * grouped["val_brier"]
    )
    chosen = grouped[grouped["guard_ok"]].sort_values("rank_score", ascending=False).head(1)
    if len(chosen) < 1:
        fallback = grouped.sort_values("rank_score", ascending=False)
        chosen = pd.concat([chosen, fallback]).drop_duplicates(subset=["feature_set_id", "config_id"]).head(1)

    baseline_combo = ("full_eligible", "rf_baseline")
    combos = [(str(r["feature_set_id"]), str(r["config_id"])) for _, r in chosen.iterrows()]
    if baseline_combo not in combos:
        combos.append(baseline_combo)
    combos = list(dict.fromkeys(combos))
    return combos[:2]


def parse_role_from_mode(mode: str) -> str:
    return "caregiver" if mode.startswith("caregiver") else "psychologist"


def is_dsm5_feature(feature: str) -> bool:
    f = str(feature).lower()
    if f in {"age_years", "sex_assigned_at_birth"}:
        return False
    if f.startswith(("swan_", "sdq_", "icut_", "ari_", "scared_", "mfq_")):
        return False
    prefixes = (
        "adhd_",
        "conduct_",
        "enuresis_",
        "encopresis_",
        "elimination_",
        "sep_anx_",
        "social_anx_",
        "gad_",
        "agor_",
        "anxiety_",
        "mdd_",
        "dmdd_",
        "pdd_",
    )
    if f.startswith(prefixes):
        return True
    return any(tok in f for tok in ["symptom", "threshold", "criterion", "impairment", "onset", "duration"])


def short_mode_chain(mode: str) -> list[str]:
    if mode.endswith("full"):
        if mode.startswith("caregiver"):
            return ["caregiver_2_3", "caregiver_1_3"]
        return ["psychologist_2_3", "psychologist_1_3"]
    if mode.endswith("2_3"):
        if mode.startswith("caregiver"):
            return ["caregiver_1_3"]
        return ["psychologist_1_3"]
    return []

def run_campaign() -> None:
    ensure_dirs()
    print_progress("Loading source tables")
    df_raw, respondability, respondability_summary, mode_matrix = load_source_tables()

    print_progress("Detecting domain targets")
    df, target_col_by_domain, target_components, target_registry = choose_target_columns(df_raw)
    save_csv(target_registry, TABLES / "domain_target_registry.csv")

    print_progress("Building mode feature coverage and respondability maps")
    mode_feature_map, coverage_df = build_mode_feature_maps(df, respondability, mode_matrix)
    save_csv(coverage_df, TABLES / "mode_feature_coverage_matrix.csv")

    print_progress("Creating reproducible split registry with holdout untouched")
    split_ids, split_registry = build_split_registry(df, target_col_by_domain)
    save_csv(split_registry, TABLES / "split_registry.csv")

    all_target_related = set(target_registry["source_column_or_rule"].astype(str).tolist())
    all_target_related.update(target_registry["selected_target_column"].astype(str).tolist())
    all_target_related.update(["mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"])

    feature_set_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    winner_rows: list[dict[str, Any]] = []
    final_metric_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    operating_rows: list[dict[str, Any]] = []

    trial_id = 0

    for mode_spec in MODE_SPECS:
        mode = mode_spec.mode
        print_progress(f"Campaign loop for mode={mode}")
        mode_eligible = mode_feature_map[mode]["eligible"]
        for domain in DOMAINS:
            print_progress(f"  -> training domain={domain} under mode={mode}")
            target_col = target_col_by_domain[domain]
            split = split_ids[domain]
            train_df = subset_by_ids(df, split["train"])
            val_df = subset_by_ids(df, split["val"])
            hold_df = subset_by_ids(df, split["holdout"])

            forbidden = set(all_target_related)
            forbidden.update(target_components.get(domain, []))
            forbidden.update([target_col, "participant_id"])
            feature_pool = [
                f
                for f in mode_eligible
                if f in df.columns and f not in forbidden and not leakage_like_feature(f)
            ]
            if len(feature_pool) < 8:
                # Conservative fallback: keep eligible non-target fields even if flagged.
                feature_pool = [f for f in mode_eligible if f in df.columns and f not in forbidden]
            feature_pool = sorted(set(feature_pool))

            feature_sets, fs_rows = build_feature_sets(train_df, feature_pool, target_col, domain, mode)
            feature_set_rows.extend(fs_rows)

            y_train = train_df[target_col].astype(int).to_numpy()
            y_val = val_df[target_col].astype(int).to_numpy()
            y_hold = hold_df[target_col].astype(int).to_numpy()

            # Stage 1: coarse search on seed BASE_SEED, no calibration, threshold 0.5
            stage1_rows_local: list[dict[str, Any]] = []
            for fs_id, fs_features in feature_sets.items():
                X_train = prepare_X(train_df, fs_features)
                X_val = prepare_X(val_df, fs_features)
                for cfg in RF_CONFIGS:
                    model = make_pipeline(fs_features, cfg, BASE_SEED)
                    model.fit(X_train, y_train)
                    train_raw = np.clip(model.predict_proba(X_train)[:, 1], 1e-6, 1 - 1e-6)
                    val_raw = np.clip(model.predict_proba(X_val)[:, 1], 1e-6, 1 - 1e-6)
                    m_train = compute_metrics(y_train, train_raw, 0.5)
                    m_val = compute_metrics(y_val, val_raw, 0.5)
                    stage1_score = objective_from_metrics(m_val) - 0.10 * max(
                        0.0, m_train["balanced_accuracy"] - m_val["balanced_accuracy"]
                    )
                    trial_id += 1
                    row = {
                        "trial_id": trial_id,
                        "stage": "stage1_coarse",
                        "mode": mode,
                        "role": mode_spec.role,
                        "domain": domain,
                        "feature_set_id": fs_id,
                        "config_id": cfg["config_id"],
                        "seed": BASE_SEED,
                        "calibration": "none",
                        "threshold_policy": "default_0_5",
                        "threshold": 0.5,
                        "n_features": len(fs_features),
                        "feature_list_pipe": "|".join(fs_features),
                        "stage1_score": stage1_score,
                        "selected_for_stage2": "no",
                    }
                    for k, v in m_train.items():
                        row[f"train_{k}"] = v
                    for k, v in m_val.items():
                        row[f"val_{k}"] = v
                    row["val_objective"] = stage1_score
                    row["overfit_gap_ba"] = m_train["balanced_accuracy"] - m_val["balanced_accuracy"]
                    stage1_rows_local.append(row)
                    trial_rows.append(row)

            stage1_df = pd.DataFrame(stage1_rows_local)
            selected_combos = select_stage1_combos(stage1_df)
            for combo in selected_combos:
                mask = (stage1_df["feature_set_id"] == combo[0]) & (stage1_df["config_id"] == combo[1])
                stage1_df.loc[mask, "selected_for_stage2"] = "yes"
            # sync selection flags back into global rows
            selected_map = set(selected_combos)
            for row in trial_rows:
                if (
                    row["mode"] == mode
                    and row["domain"] == domain
                    and row["stage"] == "stage1_coarse"
                    and (row["feature_set_id"], row["config_id"]) in selected_map
                ):
                    row["selected_for_stage2"] = "yes"

            baseline_stage1 = stage1_df[
                (stage1_df["feature_set_id"] == "full_eligible") & (stage1_df["config_id"] == "rf_baseline")
            ]
            if baseline_stage1.empty:
                baseline_recall_floor = float(stage1_df["val_recall"].median())
                baseline_precision = float(stage1_df["val_precision"].median())
                baseline_ba = float(stage1_df["val_balanced_accuracy"].median())
            else:
                baseline_recall_floor = float(baseline_stage1["val_recall"].iloc[0])
                baseline_precision = float(baseline_stage1["val_precision"].iloc[0])
                baseline_ba = float(baseline_stage1["val_balanced_accuracy"].iloc[0])

            # Stage 2: selected configs x seeds x calibration x threshold policy
            stage2_rows_local: list[dict[str, Any]] = []
            for fs_id, cfg_id in selected_combos:
                fs_features = feature_sets[fs_id]
                cfg = RF_CONFIG_BY_ID[cfg_id]
                X_train = prepare_X(train_df, fs_features)
                X_val = prepare_X(val_df, fs_features)
                X_hold = prepare_X(hold_df, fs_features)

                for seed in STAGE2_SEEDS:
                    model = make_pipeline(fs_features, cfg, seed)
                    model.fit(X_train, y_train)
                    train_raw = np.clip(model.predict_proba(X_train)[:, 1], 1e-6, 1 - 1e-6)
                    val_raw = np.clip(model.predict_proba(X_val)[:, 1], 1e-6, 1 - 1e-6)
                    hold_raw = np.clip(model.predict_proba(X_hold)[:, 1], 1e-6, 1 - 1e-6)
                    calibrated, cal_diag, _ = calibrate_probabilities(y_val, train_raw, val_raw, hold_raw)

                    for cal_method in CALIBRATION_METHODS:
                        if cal_method not in calibrated:
                            continue
                        train_prob, val_prob, hold_prob = calibrated[cal_method]
                        cal_brier = cal_diag[cal_method]["val_brier"]
                        cal_ece = cal_diag[cal_method]["val_ece"]
                        calibration_rows.append(
                            {
                                "mode": mode,
                                "domain": domain,
                                "feature_set_id": fs_id,
                                "config_id": cfg_id,
                                "seed": seed,
                                "calibration_method": cal_method,
                                "val_brier": cal_brier,
                                "val_ece": cal_ece,
                                "stage": "stage2",
                            }
                        )
                        for policy in THRESHOLD_POLICIES:
                            thr, thr_score = choose_threshold(
                                policy=policy,
                                y_true=y_val,
                                probs=val_prob,
                                recall_floor=max(0.40, baseline_recall_floor - 0.10),
                            )
                            m_train = compute_metrics(y_train, train_prob, thr)
                            m_val = compute_metrics(y_val, val_prob, thr)
                            val_objective = objective_from_metrics(m_val) - 0.08 * max(
                                0.0, m_train["balanced_accuracy"] - m_val["balanced_accuracy"]
                            )
                            trial_id += 1
                            row = {
                                "trial_id": trial_id,
                                "stage": "stage2_search",
                                "mode": mode,
                                "role": mode_spec.role,
                                "domain": domain,
                                "feature_set_id": fs_id,
                                "config_id": cfg_id,
                                "seed": seed,
                                "calibration": cal_method,
                                "threshold_policy": policy,
                                "threshold": thr,
                                "threshold_policy_score": thr_score,
                                "n_features": len(fs_features),
                                "feature_list_pipe": "|".join(fs_features),
                                "stage1_score": np.nan,
                                "selected_for_stage2": "yes",
                                "calibration_val_brier": cal_brier,
                                "calibration_val_ece": cal_ece,
                            }
                            for k, v in m_train.items():
                                row[f"train_{k}"] = v
                            for k, v in m_val.items():
                                row[f"val_{k}"] = v
                            row["val_objective"] = val_objective
                            row["overfit_gap_ba"] = m_train["balanced_accuracy"] - m_val["balanced_accuracy"]
                            stage2_rows_local.append(row)
                            trial_rows.append(row)

            stage2_df = pd.DataFrame(stage2_rows_local)
            if stage2_df.empty:
                raise RuntimeError(f"Stage2 search failed with no rows for {mode}/{domain}")

            grouped = (
                stage2_df.groupby(["feature_set_id", "config_id", "calibration", "threshold_policy"], as_index=False)
                .agg(
                    val_precision_mean=("val_precision", "mean"),
                    val_precision_std=("val_precision", "std"),
                    val_recall_mean=("val_recall", "mean"),
                    val_recall_std=("val_recall", "std"),
                    val_ba_mean=("val_balanced_accuracy", "mean"),
                    val_ba_std=("val_balanced_accuracy", "std"),
                    val_pr_auc_mean=("val_pr_auc", "mean"),
                    val_brier_mean=("val_brier", "mean"),
                    train_ba_mean=("train_balanced_accuracy", "mean"),
                    val_objective_mean=("val_objective", "mean"),
                    val_objective_std=("val_objective", "std"),
                    n_features=("n_features", "max"),
                )
                .fillna(0.0)
            )
            grouped["guard_ok"] = (
                (grouped["val_precision_mean"] >= max(0.40, baseline_precision - 0.08))
                & (grouped["val_recall_mean"] >= max(0.35, baseline_recall_floor - 0.12))
                & (grouped["val_ba_mean"] >= max(0.55, baseline_ba - 0.03))
            )
            grouped["selection_score"] = (
                0.42 * grouped["val_precision_mean"]
                + 0.24 * grouped["val_ba_mean"]
                + 0.16 * grouped["val_pr_auc_mean"]
                + 0.12 * grouped["val_recall_mean"]
                - 0.06 * grouped["val_brier_mean"]
                - 0.06 * grouped["val_ba_std"]
                - 0.05 * grouped["val_objective_std"]
            )

            valid_grouped = grouped[grouped["guard_ok"]].copy()
            if valid_grouped.empty:
                valid_grouped = grouped.copy()
            winner_group = valid_grouped.sort_values(
                ["selection_score", "val_ba_mean", "val_precision_mean", "n_features"],
                ascending=[False, False, False, True],
            ).iloc[0]

            winner_key = (
                str(winner_group["feature_set_id"]),
                str(winner_group["config_id"]),
                str(winner_group["calibration"]),
                str(winner_group["threshold_policy"]),
            )
            winner_seed_rows = stage2_df[
                (stage2_df["feature_set_id"] == winner_key[0])
                & (stage2_df["config_id"] == winner_key[1])
                & (stage2_df["calibration"] == winner_key[2])
                & (stage2_df["threshold_policy"] == winner_key[3])
            ].copy()
            winner_seed_row = winner_seed_rows.sort_values("val_objective", ascending=False).iloc[0]
            selected_seed = int(winner_seed_row["seed"])

            # Final evaluation with holdout intact.
            winner_features = feature_sets[winner_key[0]]
            winner_cfg = RF_CONFIG_BY_ID[winner_key[1]]
            X_train_w = prepare_X(train_df, winner_features)
            X_val_w = prepare_X(val_df, winner_features)
            X_hold_w = prepare_X(hold_df, winner_features)
            winner_model = make_pipeline(winner_features, winner_cfg, selected_seed)
            winner_model.fit(X_train_w, y_train)
            train_raw_w = np.clip(winner_model.predict_proba(X_train_w)[:, 1], 1e-6, 1 - 1e-6)
            val_raw_w = np.clip(winner_model.predict_proba(X_val_w)[:, 1], 1e-6, 1 - 1e-6)
            hold_raw_w = np.clip(winner_model.predict_proba(X_hold_w)[:, 1], 1e-6, 1 - 1e-6)

            cal_probs, cal_diags, cal_transforms = calibrate_probabilities(y_val, train_raw_w, val_raw_w, hold_raw_w)
            selected_calibration = winner_key[2]
            if selected_calibration not in cal_probs:
                selected_calibration = "none"
            train_prob_w, val_prob_w, hold_prob_w = cal_probs[selected_calibration]
            selected_threshold, _ = choose_threshold(
                policy=winner_key[3],
                y_true=y_val,
                probs=val_prob_w,
                recall_floor=max(0.40, baseline_recall_floor - 0.10),
            )

            m_train_w = compute_metrics(y_train, train_prob_w, selected_threshold)
            m_val_w = compute_metrics(y_val, val_prob_w, selected_threshold)
            m_hold_w = compute_metrics(y_hold, hold_prob_w, selected_threshold)

            # Baseline holdout for delta table.
            baseline_features = feature_sets.get("full_eligible", winner_features)
            baseline_cfg = RF_CONFIG_BY_ID["rf_baseline"]
            X_train_b = prepare_X(train_df, baseline_features)
            X_val_b = prepare_X(val_df, baseline_features)
            X_hold_b = prepare_X(hold_df, baseline_features)
            baseline_model = make_pipeline(baseline_features, baseline_cfg, BASE_SEED)
            baseline_model.fit(X_train_b, y_train)
            val_raw_b = np.clip(baseline_model.predict_proba(X_val_b)[:, 1], 1e-6, 1 - 1e-6)
            hold_raw_b = np.clip(baseline_model.predict_proba(X_hold_b)[:, 1], 1e-6, 1 - 1e-6)
            m_hold_b = compute_metrics(y_hold, hold_raw_b, 0.5)

            # Calibration comparison for winner model.
            for cal_method, (tr_p, va_p, ho_p) in cal_probs.items():
                thr_def = 0.5
                m_val_cal = compute_metrics(y_val, va_p, thr_def)
                m_hold_cal = compute_metrics(y_hold, ho_p, thr_def)
                calibration_rows.append(
                    {
                        "mode": mode,
                        "domain": domain,
                        "feature_set_id": winner_key[0],
                        "config_id": winner_key[1],
                        "seed": selected_seed,
                        "calibration_method": cal_method,
                        "val_brier": cal_diags[cal_method]["val_brier"],
                        "val_ece": cal_diags[cal_method]["val_ece"],
                        "val_precision_at_0_5": m_val_cal["precision"],
                        "val_recall_at_0_5": m_val_cal["recall"],
                        "val_balanced_accuracy_at_0_5": m_val_cal["balanced_accuracy"],
                        "holdout_precision_at_0_5": m_hold_cal["precision"],
                        "holdout_recall_at_0_5": m_hold_cal["recall"],
                        "holdout_balanced_accuracy_at_0_5": m_hold_cal["balanced_accuracy"],
                        "stage": "winner_eval",
                    }
                )

            # Operating points for winner.
            for policy in THRESHOLD_POLICIES:
                thr, score = choose_threshold(
                    policy=policy,
                    y_true=y_val,
                    probs=val_prob_w,
                    recall_floor=max(0.40, baseline_recall_floor - 0.10),
                )
                m_val_op = compute_metrics(y_val, val_prob_w, thr)
                m_hold_op = compute_metrics(y_hold, hold_prob_w, thr)
                operating_rows.append(
                    {
                        "mode": mode,
                        "role": mode_spec.role,
                        "domain": domain,
                        "winner_feature_set_id": winner_key[0],
                        "winner_config_id": winner_key[1],
                        "winner_seed": selected_seed,
                        "calibration": selected_calibration,
                        "threshold_policy": policy,
                        "threshold": thr,
                        "policy_score": score,
                        "is_selected_policy": "yes" if policy == winner_key[3] else "no",
                        "val_precision": m_val_op["precision"],
                        "val_recall": m_val_op["recall"],
                        "val_balanced_accuracy": m_val_op["balanced_accuracy"],
                        "val_pr_auc": m_val_op["pr_auc"],
                        "val_brier": m_val_op["brier"],
                        "holdout_precision": m_hold_op["precision"],
                        "holdout_recall": m_hold_op["recall"],
                        "holdout_balanced_accuracy": m_hold_op["balanced_accuracy"],
                        "holdout_pr_auc": m_hold_op["pr_auc"],
                        "holdout_brier": m_hold_op["brier"],
                    }
                )

            # Feature importance and ablation.
            importance = aggregate_importance(winner_model, winner_features)
            top_features = importance.head(8).index.tolist()
            winner_transform = cal_transforms[selected_calibration]

            for k in [1, 3, 5]:
                impacted = top_features[:k]
                X_hold_ab = X_hold_w.copy()
                X_hold_ab.loc[:, impacted] = np.nan
                hold_raw_ab = np.clip(winner_model.predict_proba(X_hold_ab)[:, 1], 1e-6, 1 - 1e-6)
                hold_prob_ab = winner_transform(hold_raw_ab)
                m_ab = compute_metrics(y_hold, hold_prob_ab, selected_threshold)
                ablation_rows.append(
                    {
                        "mode": mode,
                        "domain": domain,
                        "winner_feature_set_id": winner_key[0],
                        "winner_config_id": winner_key[1],
                        "winner_seed": selected_seed,
                        "ablation_case": f"drop_top_{k}",
                        "impacted_features": "|".join(impacted),
                        "precision": m_ab["precision"],
                        "recall": m_ab["recall"],
                        "balanced_accuracy": m_ab["balanced_accuracy"],
                        "pr_auc": m_ab["pr_auc"],
                        "brier": m_ab["brier"],
                        "delta_balanced_accuracy_vs_winner": m_ab["balanced_accuracy"] - m_hold_w["balanced_accuracy"],
                        "delta_precision_vs_winner": m_ab["precision"] - m_hold_w["precision"],
                        "delta_recall_vs_winner": m_ab["recall"] - m_hold_w["recall"],
                    }
                )

            # Stress tests: missingness, threshold sensitivity, mode truncation.
            for ratio in [0.10, 0.20, 0.30]:
                X_hold_st = inject_missing(X_hold_w, winner_features, ratio, BASE_SEED + int(ratio * 1000))
                hold_raw_st = np.clip(winner_model.predict_proba(X_hold_st)[:, 1], 1e-6, 1 - 1e-6)
                hold_prob_st = winner_transform(hold_raw_st)
                m_st = compute_metrics(y_hold, hold_prob_st, selected_threshold)
                stress_rows.append(
                    {
                        "mode": mode,
                        "domain": domain,
                        "stress_type": "missingness",
                        "scenario": f"missingness_{ratio:.2f}",
                        "precision": m_st["precision"],
                        "recall": m_st["recall"],
                        "balanced_accuracy": m_st["balanced_accuracy"],
                        "pr_auc": m_st["pr_auc"],
                        "brier": m_st["brier"],
                        "delta_balanced_accuracy_vs_winner": m_st["balanced_accuracy"] - m_hold_w["balanced_accuracy"],
                        "delta_precision_vs_winner": m_st["precision"] - m_hold_w["precision"],
                        "delta_recall_vs_winner": m_st["recall"] - m_hold_w["recall"],
                    }
                )

            for delta_thr in [-0.10, -0.05, 0.05, 0.10]:
                thr = float(np.clip(selected_threshold + delta_thr, 0.05, 0.95))
                m_thr = compute_metrics(y_hold, hold_prob_w, thr)
                stress_rows.append(
                    {
                        "mode": mode,
                        "domain": domain,
                        "stress_type": "threshold_sensitivity",
                        "scenario": f"threshold_shift_{delta_thr:+.2f}",
                        "precision": m_thr["precision"],
                        "recall": m_thr["recall"],
                        "balanced_accuracy": m_thr["balanced_accuracy"],
                        "pr_auc": m_thr["pr_auc"],
                        "brier": m_thr["brier"],
                        "delta_balanced_accuracy_vs_winner": m_thr["balanced_accuracy"] - m_hold_w["balanced_accuracy"],
                        "delta_precision_vs_winner": m_thr["precision"] - m_hold_w["precision"],
                        "delta_recall_vs_winner": m_thr["recall"] - m_hold_w["recall"],
                    }
                )

            for short_mode in short_mode_chain(mode):
                allowed = set(mode_feature_map[short_mode]["eligible"])
                restricted_feats = [f for f in winner_features if f not in allowed]
                if not restricted_feats:
                    continue
                X_hold_cut = X_hold_w.copy()
                X_hold_cut.loc[:, restricted_feats] = np.nan
                hold_raw_cut = np.clip(winner_model.predict_proba(X_hold_cut)[:, 1], 1e-6, 1 - 1e-6)
                hold_prob_cut = winner_transform(hold_raw_cut)
                m_cut = compute_metrics(y_hold, hold_prob_cut, selected_threshold)
                stress_rows.append(
                    {
                        "mode": mode,
                        "domain": domain,
                        "stress_type": "mode_shortening",
                        "scenario": f"truncate_to_{short_mode}",
                        "precision": m_cut["precision"],
                        "recall": m_cut["recall"],
                        "balanced_accuracy": m_cut["balanced_accuracy"],
                        "pr_auc": m_cut["pr_auc"],
                        "brier": m_cut["brier"],
                        "delta_balanced_accuracy_vs_winner": m_cut["balanced_accuracy"] - m_hold_w["balanced_accuracy"],
                        "delta_precision_vs_winner": m_cut["precision"] - m_hold_w["precision"],
                        "delta_recall_vs_winner": m_cut["recall"] - m_hold_w["recall"],
                    }
                )

            # Stability matrix row.
            boot = bootstrap_metric_ci(y_hold, hold_prob_w, selected_threshold, n_boot=250, seed=selected_seed)
            seed_std_ba = float(winner_seed_rows["val_balanced_accuracy"].std()) if len(winner_seed_rows) > 1 else 0.0
            seed_std_precision = float(winner_seed_rows["val_precision"].std()) if len(winner_seed_rows) > 1 else 0.0
            seed_std_recall = float(winner_seed_rows["val_recall"].std()) if len(winner_seed_rows) > 1 else 0.0
            stability_rows.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "winner_feature_set_id": winner_key[0],
                    "winner_config_id": winner_key[1],
                    "winner_seed": selected_seed,
                    "seed_std_val_balanced_accuracy": seed_std_ba,
                    "seed_std_val_precision": seed_std_precision,
                    "seed_std_val_recall": seed_std_recall,
                    **boot,
                }
            )

            # Ceiling status per mode/domain.
            top_sorted = valid_grouped.sort_values("selection_score", ascending=False).reset_index(drop=True)
            top_score = float(top_sorted.iloc[0]["selection_score"])
            second_score = float(top_sorted.iloc[1]["selection_score"]) if len(top_sorted) > 1 else top_score
            delta_top = top_score - second_score
            delta_ba_hold = float(m_hold_w["balanced_accuracy"] - m_hold_b["balanced_accuracy"])
            delta_pr_hold = float(m_hold_w["pr_auc"] - m_hold_b["pr_auc"])
            delta_prec_hold = float(m_hold_w["precision"] - m_hold_b["precision"])
            delta_rec_hold = float(m_hold_w["recall"] - m_hold_b["recall"])
            material_improvement = (
                (delta_ba_hold >= 0.01)
                or (delta_pr_hold >= 0.01)
                or (delta_prec_hold >= 0.01 and delta_rec_hold > -0.03)
            )
            if not material_improvement and delta_top < 0.003:
                ceiling_status = "ceiling_reached"
            elif not material_improvement:
                ceiling_status = "near_ceiling"
            elif material_improvement and delta_top < 0.005:
                ceiling_status = "marginal_room_left"
            else:
                ceiling_status = "meaningful_room_left"

            overfit_flag = (
                (m_train_w["balanced_accuracy"] - m_val_w["balanced_accuracy"] > 0.06)
                or (m_val_w["balanced_accuracy"] - m_hold_w["balanced_accuracy"] > 0.05)
                or (m_train_w["precision"] - m_val_w["precision"] > 0.10)
            )

            winner_rows.append(
                {
                    "mode": mode,
                    "role": mode_spec.role,
                    "domain": domain,
                    "winner_feature_set_id": winner_key[0],
                    "winner_config_id": winner_key[1],
                    "winner_calibration": selected_calibration,
                    "winner_threshold_policy": winner_key[3],
                    "winner_threshold": selected_threshold,
                    "winner_seed": selected_seed,
                    "n_features": len(winner_features),
                    "top_features": "|".join(top_features[:6]),
                    "selection_score": float(winner_group["selection_score"]),
                    "ceiling_status": ceiling_status,
                    "material_improvement_vs_baseline": "yes" if material_improvement else "no",
                    "overfit_warning": "yes" if overfit_flag else "no",
                }
            )

            final_metric_rows.append(
                {
                    "mode": mode,
                    "role": mode_spec.role,
                    "domain": domain,
                    "winner_feature_set_id": winner_key[0],
                    "winner_config_id": winner_key[1],
                    "winner_calibration": selected_calibration,
                    "winner_threshold_policy": winner_key[3],
                    "winner_threshold": selected_threshold,
                    "winner_seed": selected_seed,
                    "n_features": len(winner_features),
                    "train_precision": m_train_w["precision"],
                    "train_recall": m_train_w["recall"],
                    "train_specificity": m_train_w["specificity"],
                    "train_balanced_accuracy": m_train_w["balanced_accuracy"],
                    "train_f1": m_train_w["f1"],
                    "train_roc_auc": m_train_w["roc_auc"],
                    "train_pr_auc": m_train_w["pr_auc"],
                    "train_brier": m_train_w["brier"],
                    "val_precision": m_val_w["precision"],
                    "val_recall": m_val_w["recall"],
                    "val_specificity": m_val_w["specificity"],
                    "val_balanced_accuracy": m_val_w["balanced_accuracy"],
                    "val_f1": m_val_w["f1"],
                    "val_roc_auc": m_val_w["roc_auc"],
                    "val_pr_auc": m_val_w["pr_auc"],
                    "val_brier": m_val_w["brier"],
                    "holdout_precision": m_hold_w["precision"],
                    "holdout_recall": m_hold_w["recall"],
                    "holdout_specificity": m_hold_w["specificity"],
                    "holdout_balanced_accuracy": m_hold_w["balanced_accuracy"],
                    "holdout_f1": m_hold_w["f1"],
                    "holdout_roc_auc": m_hold_w["roc_auc"],
                    "holdout_pr_auc": m_hold_w["pr_auc"],
                    "holdout_brier": m_hold_w["brier"],
                    "overfit_gap_train_val_ba": m_train_w["balanced_accuracy"] - m_val_w["balanced_accuracy"],
                    "generalization_gap_val_holdout_ba": m_val_w["balanced_accuracy"] - m_hold_w["balanced_accuracy"],
                    "overfit_warning": "yes" if overfit_flag else "no",
                    "ceiling_status": ceiling_status,
                }
            )

            delta_rows.append(
                {
                    "mode": mode,
                    "role": mode_spec.role,
                    "domain": domain,
                    "baseline_config": "rf_baseline",
                    "baseline_feature_set_id": "full_eligible",
                    "baseline_seed": BASE_SEED,
                    "winner_config_id": winner_key[1],
                    "winner_feature_set_id": winner_key[0],
                    "winner_calibration": selected_calibration,
                    "winner_threshold_policy": winner_key[3],
                    "delta_precision": m_hold_w["precision"] - m_hold_b["precision"],
                    "delta_recall": m_hold_w["recall"] - m_hold_b["recall"],
                    "delta_balanced_accuracy": m_hold_w["balanced_accuracy"] - m_hold_b["balanced_accuracy"],
                    "delta_pr_auc": m_hold_w["pr_auc"] - m_hold_b["pr_auc"],
                    "delta_brier": m_hold_w["brier"] - m_hold_b["brier"],
                    "material_improvement": "yes"
                    if (
                        (m_hold_w["balanced_accuracy"] - m_hold_b["balanced_accuracy"] >= 0.01)
                        or (m_hold_w["pr_auc"] - m_hold_b["pr_auc"] >= 0.01)
                        or (
                            (m_hold_w["precision"] - m_hold_b["precision"] >= 0.01)
                            and (m_hold_w["recall"] - m_hold_b["recall"] > -0.03)
                        )
                    )
                    else "no",
                }
            )

            # Mark selected winner in trial registry rows.
            for row in trial_rows:
                if (
                    row["mode"] == mode
                    and row["domain"] == domain
                    and row["stage"] == "stage2_search"
                    and row["feature_set_id"] == winner_key[0]
                    and row["config_id"] == winner_key[1]
                    and row["calibration"] == selected_calibration
                    and row["threshold_policy"] == winner_key[3]
                    and int(row["seed"]) == selected_seed
                ):
                    row["is_winner_trial"] = "yes"
                else:
                    row.setdefault("is_winner_trial", "no")

    # Persist core campaign tables.
    trial_df = pd.DataFrame(trial_rows)
    if "is_winner_trial" not in trial_df.columns:
        trial_df["is_winner_trial"] = "no"
    trial_registry = trial_df[
        [
            "trial_id",
            "stage",
            "mode",
            "role",
            "domain",
            "feature_set_id",
            "config_id",
            "seed",
            "calibration",
            "threshold_policy",
            "threshold",
            "n_features",
            "selected_for_stage2",
            "is_winner_trial",
            "val_objective",
            "overfit_gap_ba",
        ]
    ].copy()

    trial_metrics_full = trial_df[
        [
            "trial_id",
            "stage",
            "mode",
            "role",
            "domain",
            "feature_set_id",
            "config_id",
            "seed",
            "calibration",
            "threshold_policy",
            "threshold",
            "n_features",
            "train_precision",
            "train_recall",
            "train_specificity",
            "train_balanced_accuracy",
            "train_f1",
            "train_roc_auc",
            "train_pr_auc",
            "train_brier",
            "val_precision",
            "val_recall",
            "val_specificity",
            "val_balanced_accuracy",
            "val_f1",
            "val_roc_auc",
            "val_pr_auc",
            "val_brier",
            "val_objective",
            "overfit_gap_ba",
            "selected_for_stage2",
            "is_winner_trial",
        ]
    ].copy()

    feature_set_df = pd.DataFrame(feature_set_rows).drop_duplicates(
        subset=["mode", "domain", "feature_set_id"]
    ).sort_values(["mode", "domain", "feature_set_id"])
    winners_df = pd.DataFrame(winner_rows).sort_values(["mode", "domain"]).reset_index(drop=True)
    final_metrics_df = pd.DataFrame(final_metric_rows).sort_values(["mode", "domain"]).reset_index(drop=True)
    delta_df = pd.DataFrame(delta_rows).sort_values(["mode", "domain"]).reset_index(drop=True)
    cal_df = pd.DataFrame(calibration_rows).sort_values(["mode", "domain", "stage"]).reset_index(drop=True)
    op_df = pd.DataFrame(operating_rows).sort_values(["mode", "domain", "threshold_policy"]).reset_index(drop=True)
    ablation_df = pd.DataFrame(ablation_rows).sort_values(["mode", "domain", "ablation_case"]).reset_index(drop=True)
    stress_df = pd.DataFrame(stress_rows).sort_values(["mode", "domain", "stress_type", "scenario"]).reset_index(drop=True)
    stability_df = pd.DataFrame(stability_rows).sort_values(["mode", "domain"]).reset_index(drop=True)

    save_csv(trial_registry, TRIALS / "hybrid_rf_final_trial_registry.csv")
    save_csv(trial_metrics_full, TRIALS / "hybrid_rf_final_trial_metrics_full.csv")
    save_csv(feature_set_df, TRIALS / "hybrid_rf_final_trial_feature_sets.csv")
    save_csv(winners_df, TABLES / "hybrid_rf_mode_domain_winners.csv")
    save_csv(final_metrics_df, TABLES / "hybrid_rf_mode_domain_final_metrics.csv")
    save_csv(delta_df, TABLES / "hybrid_rf_mode_domain_delta_vs_baseline.csv")
    save_csv(cal_df, CAL / "hybrid_rf_calibration_results.csv")
    save_csv(op_df, TABLES / "hybrid_rf_operating_points.csv")
    save_csv(op_df, THRESH / "hybrid_rf_threshold_results.csv")
    save_csv(ablation_df, ABL / "hybrid_rf_ablation_results.csv")
    save_csv(stress_df, STRESS / "hybrid_rf_stress_results.csv")
    save_csv(stability_df, TABLES / "hybrid_rf_stability_matrix.csv")
    save_csv(stability_df, STAB / "hybrid_rf_seed_stability.csv")
    boot_cols = [
        "mode",
        "domain",
        "winner_feature_set_id",
        "winner_config_id",
        "winner_seed",
        "precision_boot_mean",
        "precision_boot_ci_low",
        "precision_boot_ci_high",
        "recall_boot_mean",
        "recall_boot_ci_low",
        "recall_boot_ci_high",
        "balanced_accuracy_boot_mean",
        "balanced_accuracy_boot_ci_low",
        "balanced_accuracy_boot_ci_high",
        "pr_auc_boot_mean",
        "pr_auc_boot_ci_low",
        "pr_auc_boot_ci_high",
        "brier_boot_mean",
        "brier_boot_ci_low",
        "brier_boot_ci_high",
    ]
    save_csv(stability_df[boot_cols].copy(), BOOT / "hybrid_rf_bootstrap_intervals.csv")

    # Inventory artifacts.
    inventory_rows = [
        {"item": "campaign_line", "value": LINE_NAME},
        {"item": "dataset_path", "value": str(DATASET_PATH.relative_to(ROOT)).replace("\\", "/")},
        {"item": "n_rows_dataset", "value": int(len(df_raw))},
        {"item": "n_columns_dataset", "value": int(df_raw.shape[1])},
        {"item": "n_domains", "value": len(DOMAINS)},
        {"item": "n_modes", "value": len(MODE_SPECS)},
        {"item": "n_mode_domain_pairs", "value": len(MODE_SPECS) * len(DOMAINS)},
        {"item": "rf_configs_explored", "value": len(RF_CONFIGS)},
        {"item": "threshold_policies_explored", "value": len(THRESHOLD_POLICIES)},
        {"item": "calibrations_explored", "value": "|".join(CALIBRATION_METHODS)},
        {"item": "stage2_seeds", "value": "|".join([str(s) for s in STAGE2_SEEDS])},
        {"item": "trial_count_total", "value": int(len(trial_registry))},
        {"item": "winner_count", "value": int(len(winners_df))},
        {"item": "generated_at_utc", "value": now_iso()},
    ]
    inventory_df = pd.DataFrame(inventory_rows)
    save_csv(inventory_df, INV / "hybrid_rf_final_ceiling_inventory.csv")

    inventory_md = [
        "# Hybrid RF Final Ceiling Push v3 - Modeling Inventory",
        "",
        "## Inventory Table",
        md_table(inventory_df),
        "",
        "## Notes",
        "- Main model family: RandomForestClassifier.",
        "- Holdout split remained untouched during search; used only for winner validation/audit.",
        "- Targets were detected from current hybrid dataset columns and documented in domain_target_registry.",
    ]
    write_md(INV / "hybrid_rf_final_ceiling_inventory.md", "\n".join(inventory_md))

    # Comparative summary vs prior final line (full modes only).
    prev_improvement = "por_confirmar"
    prev_delta_table = pd.DataFrame()
    if PREV_INVENTORY_PATH.exists():
        prev = pd.read_csv(PREV_INVENTORY_PATH)
        full_now = final_metrics_df[final_metrics_df["mode"].isin(["caregiver_full", "psychologist_full"])].copy()
        full_now["mode_ref"] = full_now["mode"].str.replace("_full", "", regex=False)
        comp = full_now.merge(
            prev[["mode", "domain", "precision", "recall", "balanced_accuracy", "pr_auc", "brier"]],
            left_on=["mode_ref", "domain"],
            right_on=["mode", "domain"],
            how="left",
            suffixes=("_new", "_prev"),
        )
        if not comp.empty:
            comp["delta_precision"] = comp["holdout_precision"] - comp["precision"]
            comp["delta_recall"] = comp["holdout_recall"] - comp["recall"]
            comp["delta_balanced_accuracy"] = comp["holdout_balanced_accuracy"] - comp["balanced_accuracy"]
            comp["delta_pr_auc"] = comp["holdout_pr_auc"] - comp["pr_auc"]
            comp["delta_brier"] = comp["holdout_brier"] - comp["brier"]
            comp["material_gain"] = (
                (comp["delta_balanced_accuracy"] >= 0.01)
                | (comp["delta_pr_auc"] >= 0.01)
                | ((comp["delta_precision"] >= 0.01) & (comp["delta_recall"] > -0.03))
            )
            prev_improvement = "yes" if bool(comp["material_gain"].sum() >= max(1, int(len(comp) * 0.4))) else "no"
            prev_delta_table = comp[
                [
                    "mode_ref",
                    "domain",
                    "delta_precision",
                    "delta_recall",
                    "delta_balanced_accuracy",
                    "delta_pr_auc",
                    "delta_brier",
                    "material_gain",
                ]
            ].rename(columns={"mode_ref": "mode"})
            save_csv(prev_delta_table, TABLES / "hybrid_rf_vs_previous_fullmode_delta.csv")

    # Feature strategy summary.
    fs_summary = (
        feature_set_df.groupby("feature_set_id", as_index=False)
        .agg(
            avg_n_features=("n_features", "mean"),
            min_n_features=("n_features", "min"),
            max_n_features=("n_features", "max"),
            mode_domain_coverage=("mode", "count"),
        )
        .sort_values("avg_n_features")
        .reset_index(drop=True)
    )
    winner_fs = winners_df["winner_feature_set_id"].value_counts().rename_axis("feature_set_id").reset_index(name="winner_count")
    fs_summary = fs_summary.merge(winner_fs, on="feature_set_id", how="left").fillna({"winner_count": 0})
    fs_summary["winner_count"] = fs_summary["winner_count"].astype(int)
    save_csv(fs_summary, FEATSEL / "hybrid_rf_feature_selection_summary.csv")

    # DSM5 vs clean-base analysis over final winners.
    dsm_rows: list[dict[str, Any]] = []
    for _, wrow in winners_df.iterrows():
        mode = str(wrow["mode"])
        domain = str(wrow["domain"])
        target_col = target_col_by_domain[domain]
        fs_id = str(wrow["winner_feature_set_id"])
        cfg_id = str(wrow["winner_config_id"])
        seed = int(wrow["winner_seed"])
        cal_method = str(wrow["winner_calibration"])
        policy = str(wrow["winner_threshold_policy"])
        split = split_ids[domain]
        train_df = subset_by_ids(df, split["train"])
        val_df = subset_by_ids(df, split["val"])
        hold_df = subset_by_ids(df, split["holdout"])
        all_features = [f for f in feature_set_df[(feature_set_df["mode"] == mode) & (feature_set_df["domain"] == domain) & (feature_set_df["feature_set_id"] == fs_id)].iloc[0]["feature_list_pipe"].split("|") if f]
        dsm_feats = [f for f in all_features if is_dsm5_feature(f)]
        clean_feats = [f for f in all_features if not is_dsm5_feature(f)]
        variants = [
            ("clean_base_only", clean_feats),
            ("dsm5_only", dsm_feats),
            ("hybrid_full", all_features),
        ]
        for variant, feats in variants:
            if len(feats) < 5:
                dsm_rows.append(
                    {
                        "mode": mode,
                        "domain": domain,
                        "variant": variant,
                        "n_features": len(feats),
                        "status": "insufficient_features",
                    }
                )
                continue
            cfg = RF_CONFIG_BY_ID[cfg_id]
            X_train = prepare_X(train_df, feats)
            X_val = prepare_X(val_df, feats)
            X_hold = prepare_X(hold_df, feats)
            y_train = train_df[target_col].astype(int).to_numpy()
            y_val = val_df[target_col].astype(int).to_numpy()
            y_hold = hold_df[target_col].astype(int).to_numpy()
            model = make_pipeline(feats, cfg, seed)
            model.fit(X_train, y_train)
            train_raw = np.clip(model.predict_proba(X_train)[:, 1], 1e-6, 1 - 1e-6)
            val_raw = np.clip(model.predict_proba(X_val)[:, 1], 1e-6, 1 - 1e-6)
            hold_raw = np.clip(model.predict_proba(X_hold)[:, 1], 1e-6, 1 - 1e-6)
            calibrated, _, _ = calibrate_probabilities(y_val, train_raw, val_raw, hold_raw)
            train_prob, val_prob, hold_prob = calibrated[cal_method] if cal_method in calibrated else calibrated["none"]
            thr, _ = choose_threshold(policy, y_val, val_prob, recall_floor=0.55)
            m = compute_metrics(y_hold, hold_prob, thr)
            dsm_rows.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "variant": variant,
                    "n_features": len(feats),
                    "status": "ok",
                    "precision": m["precision"],
                    "recall": m["recall"],
                    "balanced_accuracy": m["balanced_accuracy"],
                    "pr_auc": m["pr_auc"],
                    "brier": m["brier"],
                }
            )
    dsm_df = pd.DataFrame(dsm_rows)
    if not dsm_df.empty:
        summary_rows: list[dict[str, Any]] = []
        for (mode, domain), grp in dsm_df.groupby(["mode", "domain"]):
            clean = grp[(grp["variant"] == "clean_base_only") & (grp["status"] == "ok")]
            hybrid = grp[(grp["variant"] == "hybrid_full") & (grp["status"] == "ok")]
            dsmv = grp[(grp["variant"] == "dsm5_only") & (grp["status"] == "ok")]
            if clean.empty or hybrid.empty:
                continue
            c = clean.iloc[0]
            h = hybrid.iloc[0]
            d_ok = not dsmv.empty
            d = dsmv.iloc[0] if d_ok else None
            summary_rows.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "hybrid_minus_clean_precision": float(h["precision"] - c["precision"]),
                    "hybrid_minus_clean_recall": float(h["recall"] - c["recall"]),
                    "hybrid_minus_clean_balanced_accuracy": float(h["balanced_accuracy"] - c["balanced_accuracy"]),
                    "hybrid_minus_clean_pr_auc": float(h["pr_auc"] - c["pr_auc"]),
                    "hybrid_minus_clean_brier": float(h["brier"] - c["brier"]),
                    "dsm5_only_balanced_accuracy": float(d["balanced_accuracy"]) if d_ok else np.nan,
                    "dsm5_material_gain": "yes"
                    if (
                        (float(h["balanced_accuracy"] - c["balanced_accuracy"]) >= 0.01)
                        or (float(h["pr_auc"] - c["pr_auc"]) >= 0.01)
                        or (
                            float(h["precision"] - c["precision"]) >= 0.01
                            and float(h["recall"] - c["recall"]) > -0.03
                        )
                    )
                    else "no",
                }
            )
        dsm_summary = pd.DataFrame(summary_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
        save_csv(dsm_summary, TABLES / "hybrid_rf_dsm5_vs_cleanbase_analysis.csv")
    else:
        save_csv(pd.DataFrame(), TABLES / "hybrid_rf_dsm5_vs_cleanbase_analysis.csv")

    # Derived analyses for reports.
    role_mode_summary = (
        final_metrics_df.groupby("mode", as_index=False)
        .agg(
            mean_holdout_precision=("holdout_precision", "mean"),
            mean_holdout_recall=("holdout_recall", "mean"),
            mean_holdout_balanced_accuracy=("holdout_balanced_accuracy", "mean"),
            mean_holdout_pr_auc=("holdout_pr_auc", "mean"),
            mean_holdout_brier=("holdout_brier", "mean"),
        )
        .sort_values("mean_holdout_balanced_accuracy", ascending=False)
    )
    best_mode_caregiver = role_mode_summary[role_mode_summary["mode"].str.startswith("caregiver")].head(1)
    best_mode_psych = role_mode_summary[role_mode_summary["mode"].str.startswith("psychologist")].head(1)

    best_by_domain = (
        final_metrics_df.sort_values(
            ["domain", "holdout_balanced_accuracy", "holdout_precision", "holdout_pr_auc"],
            ascending=[True, False, False, False],
        )
        .groupby("domain", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )

    mode_compare_rows: list[dict[str, Any]] = []
    for role in ["caregiver", "psychologist"]:
        m13 = final_metrics_df[final_metrics_df["mode"] == f"{role}_1_3"].set_index("domain")
        m23 = final_metrics_df[final_metrics_df["mode"] == f"{role}_2_3"].set_index("domain")
        mf = final_metrics_df[final_metrics_df["mode"] == f"{role}_full"].set_index("domain")
        for domain in DOMAINS:
            if domain not in m13.index or domain not in m23.index or domain not in mf.index:
                continue
            mode_compare_rows.append(
                {
                    "role": role,
                    "domain": domain,
                    "ba_loss_1_3_to_2_3": float(m13.loc[domain, "holdout_balanced_accuracy"] - m23.loc[domain, "holdout_balanced_accuracy"]),
                    "ba_loss_2_3_to_full": float(m23.loc[domain, "holdout_balanced_accuracy"] - mf.loc[domain, "holdout_balanced_accuracy"]),
                    "precision_loss_1_3_to_2_3": float(m13.loc[domain, "holdout_precision"] - m23.loc[domain, "holdout_precision"]),
                    "precision_loss_2_3_to_full": float(m23.loc[domain, "holdout_precision"] - mf.loc[domain, "holdout_precision"]),
                }
            )
    mode_compare_df = pd.DataFrame(mode_compare_rows)
    if not mode_compare_df.empty:
        save_csv(mode_compare_df, TABLES / "hybrid_rf_mode_step_losses.csv")

    overfit_df = final_metrics_df.copy()
    overfit_df["overfit_train_val"] = overfit_df["overfit_gap_train_val_ba"] > 0.06
    overfit_df["overfit_val_holdout"] = overfit_df["generalization_gap_val_holdout_ba"] > 0.05
    overfit_df["overfit_any"] = overfit_df["overfit_train_val"] | overfit_df["overfit_val_holdout"]
    overfit_yes = bool(overfit_df["overfit_any"].any())

    generalization_df = final_metrics_df.copy()
    generalization_df["generalization_ok"] = (
        (generalization_df["holdout_balanced_accuracy"] >= 0.75)
        & (generalization_df["holdout_precision"] >= 0.75)
        & (generalization_df["holdout_recall"] >= 0.55)
    )
    generalization_yes = bool(generalization_df["generalization_ok"].mean() >= 0.80)

    ceiling_counts = winners_df["ceiling_status"].value_counts().to_dict()

    # Final ranking and promotion decisions.
    ranked_df = final_metrics_df.copy()
    ranked_df["ranking_score"] = (
        0.40 * ranked_df["holdout_precision"]
        + 0.24 * ranked_df["holdout_balanced_accuracy"]
        + 0.18 * ranked_df["holdout_pr_auc"]
        + 0.10 * ranked_df["holdout_recall"]
        - 0.08 * ranked_df["holdout_brier"]
    )
    ranked_df["stability_penalty"] = (
        0.60 * ranked_df["overfit_gap_train_val_ba"].clip(lower=0)
        + 0.60 * ranked_df["generalization_gap_val_holdout_ba"].clip(lower=0)
    )
    ranked_df["ranking_score_adj"] = ranked_df["ranking_score"] - ranked_df["stability_penalty"]
    ranked_df = ranked_df.sort_values(["ranking_score_adj", "holdout_balanced_accuracy"], ascending=False).reset_index(drop=True)
    save_csv(ranked_df, TABLES / "hybrid_rf_final_ranked_models.csv")

    decisions = ranked_df.copy()
    conditions_now = (
        (decisions["holdout_precision"] >= 0.88)
        & (decisions["holdout_balanced_accuracy"] >= 0.88)
        & (decisions["holdout_pr_auc"] >= 0.86)
        & (decisions["holdout_recall"] >= 0.65)
        & (decisions["holdout_brier"] <= 0.04)
        & (decisions["overfit_gap_train_val_ba"] <= 0.05)
        & (decisions["generalization_gap_val_holdout_ba"] <= 0.05)
    )
    conditions_caveat = (
        (decisions["holdout_precision"] >= 0.80)
        & (decisions["holdout_balanced_accuracy"] >= 0.82)
        & (decisions["holdout_pr_auc"] >= 0.78)
        & (decisions["holdout_recall"] >= 0.55)
    )
    decisions["promotion_decision"] = np.where(
        conditions_now,
        "PROMOTE_NOW",
        np.where(
            conditions_caveat,
            "PROMOTE_WITH_CAVEAT",
            np.where(
                (decisions["holdout_balanced_accuracy"] >= 0.75) & (decisions["holdout_precision"] >= 0.72),
                "HOLD_FOR_TARGETED_FIX",
                "REJECT_AS_PRIMARY",
            ),
        ),
    )
    decisions["decision_reason"] = np.where(
        decisions["promotion_decision"] == "PROMOTE_NOW",
        "strong_metrics_and_stability",
        np.where(
            decisions["promotion_decision"] == "PROMOTE_WITH_CAVEAT",
            "good_metrics_with_caveats",
            np.where(
                decisions["promotion_decision"] == "HOLD_FOR_TARGETED_FIX",
                "partially_good_but_fragile_or_unbalanced",
                "insufficient_quality_for_primary",
            ),
        ),
    )
    save_csv(decisions, TABLES / "hybrid_rf_final_promotion_decisions.csv")

    # Champions by domain with practical preference for 2/3 if full is not materially better.
    champions_rows: list[dict[str, Any]] = []
    for domain in DOMAINS:
        ddf = decisions[decisions["domain"] == domain].copy()
        if ddf.empty:
            continue
        ddf["decision_rank"] = ddf["promotion_decision"].map(
            {"PROMOTE_NOW": 4, "PROMOTE_WITH_CAVEAT": 3, "HOLD_FOR_TARGETED_FIX": 2, "REJECT_AS_PRIMARY": 1}
        )
        ddf = ddf.sort_values(
            ["decision_rank", "ranking_score_adj", "holdout_balanced_accuracy", "holdout_precision"],
            ascending=False,
        ).reset_index(drop=True)
        best = ddf.iloc[0].copy()
        if best["mode"].endswith("full"):
            mode_23 = best["mode"].replace("_full", "_2_3")
            alt = ddf[ddf["mode"] == mode_23]
            if not alt.empty:
                a = alt.iloc[0]
                delta_ba = float(best["holdout_balanced_accuracy"] - a["holdout_balanced_accuracy"])
                delta_pr = float(best["holdout_pr_auc"] - a["holdout_pr_auc"])
                delta_prec = float(best["holdout_precision"] - a["holdout_precision"])
                if (delta_ba < 0.01) and (delta_pr < 0.01) and (delta_prec < 0.015):
                    best = a.copy()
        champions_rows.append(
            {
                "domain": domain,
                "champion_mode": best["mode"],
                "champion_config_id": best["winner_config_id"],
                "champion_feature_set_id": best["winner_feature_set_id"],
                "champion_calibration": best["winner_calibration"],
                "champion_threshold_policy": best["winner_threshold_policy"],
                "champion_decision": best["promotion_decision"],
                "precision": best["holdout_precision"],
                "recall": best["holdout_recall"],
                "balanced_accuracy": best["holdout_balanced_accuracy"],
                "pr_auc": best["holdout_pr_auc"],
                "brier": best["holdout_brier"],
            }
        )
    champions_df = pd.DataFrame(champions_rows).sort_values("domain").reset_index(drop=True)
    save_csv(champions_df, TABLES / "hybrid_rf_final_champions.csv")

    # Reports.
    report_domain_mode = [
        "# Hybrid RF Domain/Mode Analysis",
        "",
        "## Winner table",
        md_table(
            final_metrics_df[
                [
                    "mode",
                    "domain",
                    "holdout_precision",
                    "holdout_recall",
                    "holdout_balanced_accuracy",
                    "holdout_pr_auc",
                    "holdout_brier",
                    "ceiling_status",
                ]
            ]
        ),
        "",
        "## Answers to requested questions",
        f"1. Mejor modelo por dominio y modo: ver [tables/hybrid_rf_mode_domain_winners.csv](../tables/hybrid_rf_mode_domain_winners.csv).",
        f"2. Mejor modo global cuidador: {best_mode_caregiver.iloc[0]['mode'] if not best_mode_caregiver.empty else 'por_confirmar'}.",
        f"3. Mejor modo global psicologo: {best_mode_psych.iloc[0]['mode'] if not best_mode_psych.empty else 'por_confirmar'}.",
        "4. Perdida 1/3->2/3 y 2/3->full: ver [tables/hybrid_rf_mode_step_losses.csv](../tables/hybrid_rf_mode_step_losses.csv).",
        "5. Dominios mas afectados en modos cortos: revisar mayores caidas de BA/precision en `hybrid_rf_mode_step_losses.csv`.",
        "6. Subidas de precision sin romper recall: ver `hybrid_rf_mode_domain_delta_vs_baseline.csv` (material_improvement=yes).",
        "7. Donde aparece sobreentrenamiento: ver `hybrid_rf_overfitting_audit.md` y columna `overfit_warning`.",
        "8. Donde calibracion mejora: ver `calibration/hybrid_rf_calibration_results.csv` por delta de brier/ece.",
        "9. Donde llegamos al techo: ver `ceiling_status` en winners.",
        "10. Combinaciones a descartar: trials con `overfit_gap_ba` alto y sin mejora material.",
        "11. Defendibilidad de modos cortos: defendibles cuando BA>=0.75, precision>=0.75 y recall>=0.55.",
        f"12. Dataset hibrido mejora frente a anterior: {prev_improvement}.",
        "13. Subset mas robusto: revisar winners por frecuencia de `winner_feature_set_id` y estabilidad bootstrap.",
        "14. Aporte DSM-5 explicito: comparado via subsets compactos vs full; mantener si mejora material y no degrada robustez.",
        f"15. Generalizacion suficiente para cierre: {'yes' if generalization_yes else 'no'}.",
    ]
    write_md(REPORTS / "hybrid_rf_domain_mode_analysis.md", "\n".join(report_domain_mode))

    report_overfit = [
        "# Hybrid RF Overfitting Audit",
        "",
        "## Summary",
        f"- evidencia_de_sobreentrenamiento: {'yes' if overfit_yes else 'no'}",
        f"- pares_con_bandera: {int(overfit_df['overfit_any'].sum())}/{len(overfit_df)}",
        "",
        "## Detailed table",
        md_table(
            overfit_df[
                [
                    "mode",
                    "domain",
                    "overfit_gap_train_val_ba",
                    "generalization_gap_val_holdout_ba",
                    "overfit_train_val",
                    "overfit_val_holdout",
                    "overfit_any",
                ]
            ]
        ),
        "",
        "## Criteria",
        "- train->val BA gap > 0.06",
        "- val->holdout BA gap > 0.05",
    ]
    write_md(REPORTS / "hybrid_rf_overfitting_audit_v3.md", "\n".join(report_overfit))

    report_generalization = [
        "# Hybrid RF Generalization Audit",
        "",
        "## Summary",
        f"- evidencia_de_buena_generalizacion: {'yes' if generalization_yes else 'no'}",
        f"- pares_ok: {int(generalization_df['generalization_ok'].sum())}/{len(generalization_df)}",
        "",
        "## Holdout performance matrix",
        md_table(
            final_metrics_df[
                [
                    "mode",
                    "domain",
                    "holdout_precision",
                    "holdout_recall",
                    "holdout_balanced_accuracy",
                    "holdout_pr_auc",
                    "holdout_brier",
                ]
            ]
        ),
        "",
        "## Stability matrix",
        md_table(
            stability_df[
                [
                    "mode",
                    "domain",
                    "seed_std_val_balanced_accuracy",
                    "precision_boot_ci_low",
                    "precision_boot_ci_high",
                    "balanced_accuracy_boot_ci_low",
                    "balanced_accuracy_boot_ci_high",
                ]
            ]
        ),
    ]
    write_md(REPORTS / "hybrid_rf_generalization_audit_v3.md", "\n".join(report_generalization))

    report_ceiling = [
        "# Hybrid RF Ceiling Decision",
        "",
        "## Decision matrix",
        md_table(
            winners_df[
                [
                    "mode",
                    "domain",
                    "ceiling_status",
                    "material_improvement_vs_baseline",
                    "selection_score",
                ]
            ]
        ),
        "",
        "## Count by status",
        md_table(pd.DataFrame([{"status": k, "count": v} for k, v in sorted(ceiling_counts.items())])),
        "",
        "## Closure rule result",
        (
            "- Campaign closure condition met: yes (no broad evidence of meaningful_room_left).\n"
            if int(ceiling_counts.get("meaningful_room_left", 0)) == 0
            else "- Campaign closure condition met: no (there are mode/domain pairs with meaningful_room_left).\n"
        ),
    ]
    write_md(REPORTS / "hybrid_rf_final_ceiling_decision_v3.md", "\n".join(report_ceiling))

    report_exec = [
        "# Hybrid RF Executive Summary",
        "",
        f"- line: `{LINE_NAME}`",
        f"- mode_domain_pairs_trained: {len(final_metrics_df)}",
        f"- evidence_overfitting: {'yes' if overfit_yes else 'no'}",
        f"- evidence_good_generalization: {'yes' if generalization_yes else 'no'}",
        f"- hybrid_dataset_material_improvement_vs_previous: {prev_improvement}",
        f"- ceiling_status_counts: {json.dumps(ceiling_counts, ensure_ascii=True)}",
        "",
        "## Best by domain (holdout BA)",
        md_table(
            best_by_domain[
                ["domain", "mode", "holdout_precision", "holdout_recall", "holdout_balanced_accuracy", "holdout_pr_auc"]
            ]
        ),
        "",
        "## Best mode by role",
        md_table(
            pd.concat([best_mode_caregiver, best_mode_psych], ignore_index=True)[
                [
                    "mode",
                    "mean_holdout_precision",
                    "mean_holdout_recall",
                    "mean_holdout_balanced_accuracy",
                    "mean_holdout_pr_auc",
                ]
            ]
            if (not best_mode_caregiver.empty or not best_mode_psych.empty)
            else pd.DataFrame(columns=["mode", "mean_holdout_precision", "mean_holdout_recall", "mean_holdout_balanced_accuracy", "mean_holdout_pr_auc"])
        ),
    ]
    write_md(REPORTS / "hybrid_rf_executive_summary_v3.md", "\n".join(report_exec))

    report_feature_strategy = [
        "# Hybrid RF Feature Strategy Report",
        "",
        "## Feature set summary",
        md_table(fs_summary),
        "",
        "## Winners by feature set",
        md_table(winners_df[["mode", "domain", "winner_feature_set_id", "n_features", "selection_score"]]),
        "",
        "## DSM5 vs clean-base",
        md_table(pd.read_csv(TABLES / "hybrid_rf_dsm5_vs_cleanbase_analysis.csv")),
    ]
    write_md(REPORTS / "hybrid_rf_feature_strategy_report.md", "\n".join(report_feature_strategy))

    # Artifact manifest.
    generated_files = sorted([p for p in BASE.rglob("*") if p.is_file()])
    manifest_entries: list[dict[str, Any]] = []
    for p in generated_files:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        data = p.read_bytes()
        manifest_entries.append(
            {
                "path": rel,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest = {
        "campaign": LINE_NAME,
        "generated_at_utc": now_iso(),
        "script": str((ROOT / "scripts" / "run_hybrid_rf_final_ceiling_push_v3.py").relative_to(ROOT)).replace("\\", "/"),
        "dataset_source": str(DATASET_PATH.relative_to(ROOT)).replace("\\", "/"),
        "mode_count": len(MODE_SPECS),
        "domain_count": len(DOMAINS),
        "mode_domain_pairs": len(MODE_SPECS) * len(DOMAINS),
        "trial_count": int(len(trial_registry)),
        "winner_count": int(len(winners_df)),
        "evidence_overfitting": "yes" if overfit_yes else "no",
        "evidence_good_generalization": "yes" if generalization_yes else "no",
        "hybrid_dataset_material_improvement_vs_previous": prev_improvement,
        "ceiling_status_counts": ceiling_counts,
        "generated_files": manifest_entries,
    }
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "hybrid_rf_final_ceiling_push_v3_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print_progress("Campaign completed successfully")


if __name__ == "__main__":
    run_campaign()
