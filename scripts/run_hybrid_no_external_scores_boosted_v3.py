import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedShuffleSplit

warnings.filterwarnings("ignore")

BASE = Path("data/hybrid_no_external_scores_boosted_v3")
ART = Path("artifacts/hybrid_no_external_scores_boosted_v3")

for d in [
    "inventory",
    "trials",
    "feature_engineering",
    "models",
    "ensembles",
    "calibration",
    "thresholds",
    "bootstrap",
    "stability",
    "ablation",
    "stress",
    "tables",
    "reports",
]:
    (BASE / d).mkdir(parents=True, exist_ok=True)
ART.mkdir(parents=True, exist_ok=True)

# Inputs from v2
V2_BASE = Path("data/hybrid_no_external_scores_rebuild_v2")
DATASET = V2_BASE / "tables/hybrid_no_external_scores_dataset_ready.csv"
V2_FINAL = V2_BASE / "tables/hybrid_no_external_scores_final_models.csv"
V2_FE_REG = V2_BASE / "feature_engineering/hybrid_no_external_scores_feature_engineering_registry.csv"

df = pd.read_csv(DATASET)

target_cols = [
    "target_domain_adhd_final",
    "target_domain_conduct_final",
    "target_domain_elimination_final",
    "target_domain_anxiety_final",
    "target_domain_depression_final",
]

base_features = [c for c in df.columns if c not in target_cols]

PRIORITY = [
    ("adhd", "caregiver_1_3"),
    ("adhd", "caregiver_2_3"),
    ("adhd", "psychologist_1_3"),
    ("adhd", "psychologist_2_3"),
    ("depression", "caregiver_1_3"),
    ("depression", "caregiver_2_3"),
    ("depression", "caregiver_full"),
    ("depression", "psychologist_1_3"),
    ("depression", "psychologist_2_3"),
    ("depression", "psychologist_full"),
    ("elimination", "caregiver_1_3"),
    ("elimination", "psychologist_1_3"),
    ("anxiety", "caregiver_1_3"),
]


def safe_div(a, b):
    return np.where(b == 0, 0.0, a / b)


def add_engineered(df_in):
    df_out = df_in.copy()
    eng_defs = []

    # ADHD
    inatt = [c for c in df_out.columns if c.startswith("adhd_inatt_") and c.split("_")[2].isdigit()]
    hyp = [c for c in df_out.columns if c.startswith("adhd_hypimp_") and c.split("_")[2].isdigit()]
    if inatt:
        df_out["engv3_adhd_inatt_count"] = df_out[inatt].sum(axis=1)
        df_out["engv3_adhd_inatt_mean"] = df_out[inatt].mean(axis=1)
        eng_defs.append(("engv3_adhd_inatt_count", "sum", inatt, "adhd", "inattention count"))
        eng_defs.append(("engv3_adhd_inatt_mean", "mean", inatt, "adhd", "inattention mean"))
    if hyp:
        df_out["engv3_adhd_hyp_count"] = df_out[hyp].sum(axis=1)
        df_out["engv3_adhd_hyp_mean"] = df_out[hyp].mean(axis=1)
        eng_defs.append(("engv3_adhd_hyp_count", "sum", hyp, "adhd", "hyper/impulsive count"))
        eng_defs.append(("engv3_adhd_hyp_mean", "mean", hyp, "adhd", "hyper/impulsive mean"))
    if inatt and hyp:
        df_out["engv3_adhd_balance_diff"] = df_out["engv3_adhd_inatt_count"] - df_out["engv3_adhd_hyp_count"]
        df_out["engv3_adhd_balance_ratio"] = safe_div(
            df_out["engv3_adhd_inatt_count"] + 1, df_out["engv3_adhd_hyp_count"] + 1
        )
        eng_defs.append(
            (
                "engv3_adhd_balance_diff",
                "diff",
                ["engv3_adhd_inatt_count", "engv3_adhd_hyp_count"],
                "adhd",
                "inatt-hyp count diff",
            )
        )
        eng_defs.append(
            (
                "engv3_adhd_balance_ratio",
                "ratio",
                ["engv3_adhd_inatt_count", "engv3_adhd_hyp_count"],
                "adhd",
                "inatt/hyp ratio",
            )
        )

    # Depression
    mdd = [c for c in df_out.columns if c.startswith("mdd_") and c.split("_")[1].isdigit()]
    core = [c for c in mdd if c.startswith("mdd_01_") or c.startswith("mdd_02_")]
    if mdd:
        df_out["engv3_mdd_symptom_count"] = df_out[mdd].sum(axis=1)
        df_out["engv3_mdd_symptom_mean"] = df_out[mdd].mean(axis=1)
        eng_defs.append(("engv3_mdd_symptom_count", "sum", mdd, "depression", "mdd symptom count"))
        eng_defs.append(("engv3_mdd_symptom_mean", "mean", mdd, "depression", "mdd symptom mean"))
    if core:
        df_out["engv3_mdd_core_count"] = df_out[core].sum(axis=1)
        df_out["engv3_mdd_core_ratio"] = safe_div(
            df_out["engv3_mdd_core_count"] + 1, df_out["engv3_mdd_symptom_count"] + 1
        )
        eng_defs.append(("engv3_mdd_core_count", "sum", core, "depression", "mdd core count"))
        eng_defs.append(
            ("engv3_mdd_core_ratio", "ratio", ["engv3_mdd_core_count", "engv3_mdd_symptom_count"], "depression", "core/total ratio")
        )
    if "mdd_duration_weeks" in df_out.columns and "mdd_impairment" in df_out.columns:
        df_out["engv3_mdd_duration_x_impair"] = df_out["mdd_duration_weeks"] * df_out["mdd_impairment"]
        eng_defs.append(
            ("engv3_mdd_duration_x_impair", "product", ["mdd_duration_weeks", "mdd_impairment"], "depression", "duration*impairment")
        )

    # Anxiety modules
    anx_prefixes = ["gad_", "sep_anx_", "social_", "agor_", "pdd_"]
    anx_cols = [c for c in df_out.columns if any(c.startswith(p) for p in anx_prefixes) and c.split("_")[1].isdigit()]
    if anx_cols:
        df_out["engv3_anx_symptom_count"] = df_out[anx_cols].sum(axis=1)
        df_out["engv3_anx_symptom_mean"] = df_out[anx_cols].mean(axis=1)
        eng_defs.append(("engv3_anx_symptom_count", "sum", anx_cols, "anxiety", "anxiety symptom count"))
        eng_defs.append(("engv3_anx_symptom_mean", "mean", anx_cols, "anxiety", "anxiety symptom mean"))
    module_counts = []
    for p in anx_prefixes:
        cols = [c for c in df_out.columns if c.startswith(p) and c.split("_")[1].isdigit()]
        if cols:
            name = f"engv3_anx_{p.strip('_')}_count"
            df_out[name] = df_out[cols].sum(axis=1)
            module_counts.append(name)
            eng_defs.append((name, "sum", cols, "anxiety", f"{p} count"))
    if module_counts:
        df_out["engv3_anx_module_diversity"] = (df_out[module_counts] > 0).sum(axis=1)
        eng_defs.append(
            ("engv3_anx_module_diversity", "count_nonzero", module_counts, "anxiety", "modules with any symptom")
        )

    # Elimination
    if "enuresis_event_frequency_per_week" in df_out.columns and "enuresis_duration_months_consecutive" in df_out.columns:
        df_out["engv3_enuresis_burden"] = (
            df_out["enuresis_event_frequency_per_week"] * df_out["enuresis_duration_months_consecutive"]
        )
        eng_defs.append(
            (
                "engv3_enuresis_burden",
                "product",
                ["enuresis_event_frequency_per_week", "enuresis_duration_months_consecutive"],
                "elimination",
                "enuresis burden",
            )
        )
    if "encopresis_event_frequency_per_month" in df_out.columns and "encopresis_duration_months_consecutive" in df_out.columns:
        df_out["engv3_encopresis_burden"] = (
            df_out["encopresis_event_frequency_per_month"] * df_out["encopresis_duration_months_consecutive"]
        )
        eng_defs.append(
            (
                "engv3_encopresis_burden",
                "product",
                ["encopresis_event_frequency_per_month", "encopresis_duration_months_consecutive"],
                "elimination",
                "encopresis burden",
            )
        )
    if "enuresis_distress_impairment" in df_out.columns:
        df_out["engv3_enuresis_distress"] = df_out["enuresis_distress_impairment"]
        eng_defs.append(("engv3_enuresis_distress", "copy", ["enuresis_distress_impairment"], "elimination", "enuresis distress"))

    return df_out, eng_defs


df_eng, eng_defs = add_engineered(df)

# Encode non-numeric columns
for col in df_eng.columns:
    if pd.api.types.is_bool_dtype(df_eng[col]):
        df_eng[col] = df_eng[col].astype(int)
    elif not pd.api.types.is_numeric_dtype(df_eng[col]):
        df_eng[col] = pd.factorize(df_eng[col].astype(str))[0]

eng_df = pd.DataFrame(
    [
        {
            "feature": f,
            "formula": formula,
            "source_columns": "|".join(cols),
            "domain": domain,
            "rationale": rationale,
        }
        for f, formula, cols, domain, rationale in eng_defs
    ]
)
eng_df.to_csv(BASE / "feature_engineering/hybrid_no_external_scores_boosted_feature_registry.csv", index=False)


def try_import(name, attr=None):
    try:
        mod = __import__(name, fromlist=["*"])
        if attr:
            getattr(mod, attr)
        return True
    except Exception:
        return False


has_xgb = try_import("xgboost")
has_lgbm = try_import("lightgbm")
has_cat = try_import("catboost")
has_imblearn = try_import("imblearn")

if has_imblearn:
    from imblearn.ensemble import BalancedBaggingClassifier, BalancedRandomForestClassifier, EasyEnsembleClassifier

if has_xgb:
    from xgboost import XGBClassifier
if has_lgbm:
    from lightgbm import LGBMClassifier
if has_cat:
    from catboost import CatBoostClassifier


def get_model_configs():
    configs = []
    configs += [
        ("rf", RandomForestClassifier, dict(n_estimators=400, max_depth=None, min_samples_split=2, min_samples_leaf=1, max_features="sqrt", class_weight="balanced", bootstrap=True, n_jobs=-1, random_state=0)),
    ]
    configs += [
        ("extra_trees", ExtraTreesClassifier, dict(n_estimators=400, max_depth=None, min_samples_split=2, min_samples_leaf=1, max_features="sqrt", class_weight="balanced", bootstrap=False, n_jobs=-1, random_state=0)),
    ]
    configs += [
        ("hgb", HistGradientBoostingClassifier, dict(max_depth=6, learning_rate=0.05, max_iter=250, l2_regularization=0.1, random_state=0)),
    ]
    configs += [
        ("logreg", LogisticRegression, dict(max_iter=2000, C=1.0, solver="liblinear", class_weight="balanced")),
    ]
    if has_imblearn:
        configs += [
            ("balanced_rf", BalancedRandomForestClassifier, dict(n_estimators=300, max_depth=None, max_features="sqrt", n_jobs=-1, random_state=0)),
        ]
    if has_xgb:
        configs += [
            ("xgboost", XGBClassifier, dict(n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, eval_metric="logloss", use_label_encoder=False, n_jobs=-1, random_state=0)),
        ]
    if has_lgbm:
        configs += [
            ("lightgbm", LGBMClassifier, dict(n_estimators=200, max_depth=-1, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, random_state=0)),
        ]
    if has_cat:
        configs += [
            ("catboost", CatBoostClassifier, dict(iterations=200, depth=6, learning_rate=0.05, loss_function="Logloss", verbose=False, random_seed=0)),
        ]
    return configs


MODEL_CONFIGS = get_model_configs()
model_families = sorted(set([c[0] for c in MODEL_CONFIGS]))
fam_status = []
for fam in ["rf", "extra_trees", "hgb", "logreg", "balanced_rf", "balanced_bagging", "easy_ensemble", "xgboost", "lightgbm", "catboost"]:
    fam_status.append({"family": fam, "available": "yes" if fam in model_families else "no"})
pd.DataFrame(fam_status).to_csv(BASE / "models/hybrid_no_external_scores_model_family_comparison.csv", index=False)


def get_metrics(y_true, y_prob, threshold=0.5):
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    ba = (recall + specificity) / 2.0
    f1 = f1_score(y_true, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.0
    pr_auc = average_precision_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.0
    brier = brier_score_loss(y_true, y_prob)
    return dict(
        precision=precision,
        recall=recall,
        specificity=specificity,
        balanced_accuracy=ba,
        f1=f1,
        roc_auc=roc_auc,
        pr_auc=pr_auc,
        brier=brier,
    )


def find_threshold(policy, y_true, y_prob):
    thresholds = np.linspace(0.05, 0.95, 91)
    best_t = 0.5
    best_score = -1e9
    for t in thresholds:
        m = get_metrics(y_true, y_prob, t)
        if policy == "default_0_5":
            return 0.5
        if policy == "balanced":
            score = m["balanced_accuracy"]
        elif policy == "precision_oriented":
            score = m["precision"] - 0.1 * max(0, 0.7 - m["recall"])
        elif policy == "recall_guard":
            score = m["recall"] - 0.1 * max(0, 0.8 - m["precision"])
        elif policy == "precision_min_recall":
            score = m["precision"] if m["recall"] >= 0.75 else -1
        elif policy == "recall_min_precision":
            score = m["recall"] if m["precision"] >= 0.75 else -1
        elif policy == "maximize_BA_subject_to_precision_floor":
            score = m["balanced_accuracy"] if m["precision"] >= 0.8 else -1
        elif policy == "maximize_precision_subject_to_recall_floor":
            score = m["precision"] if m["recall"] >= 0.7 else -1
        else:
            score = m["balanced_accuracy"]
        if score > best_score:
            best_score = score
            best_t = float(t)
    return best_t


threshold_policies = [
    "default_0_5",
    "balanced",
]
calibrations = ["none"]


reg = pd.read_csv(V2_FE_REG)
reg["feature_list"] = reg["feature_list_pipe"].fillna("").apply(lambda s: s.split("|") if s else [])
base_feature_sets = {}
for (mode, domain), group in reg.groupby(["mode", "domain"]):
    for _, r in group.iterrows():
        base_feature_sets[(domain, mode, r["feature_set_id"])] = r["feature_list"]

new_eng_features = [f for f in df_eng.columns if f.startswith("engv3_")]


def add_feature_set(domain, mode, base_id, new_id):
    key = (domain, mode, base_id)
    if key in base_feature_sets:
        feats = base_feature_sets[key] + new_eng_features
        base_feature_sets[(domain, mode, new_id)] = sorted(list(dict.fromkeys(feats)))


for domain, mode in {(d, m) for d, m in PRIORITY}:
    add_feature_set(domain, mode, "full_eligible", "boosted_eng_full")
    add_feature_set(domain, mode, "compact_subset", "boosted_eng_compact")
    add_feature_set(domain, mode, "stability_pruned_subset", "boosted_eng_pruned")


seed_base = 20270413
strat = df[target_cols].sum(axis=1).astype(int)
sss1 = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=seed_base)
train_pool_idx, hold_idx = next(sss1.split(df, strat))
sss2 = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=seed_base + 1)
tr_idx, val_idx = next(sss2.split(df.iloc[train_pool_idx], strat.iloc[train_pool_idx]))
train_idx = np.array(train_pool_idx)[tr_idx]
val_idx = np.array(train_pool_idx)[val_idx]

split_registry = {
    "seed_base": seed_base,
    "n_total": len(df),
    "n_train": int(len(train_idx)),
    "n_val": int(len(val_idx)),
    "n_holdout": int(len(hold_idx)),
}

trial_rows = []
candidate_best = []
trial_id = 0

for domain, mode in PRIORITY:
    target_col = f"target_domain_{domain}_final"
    y = df_eng[target_col].values

    feat_ids = []
    for fid in [
        "full_eligible",
        "boosted_eng_full",
    ]:
        if (domain, mode, fid) in base_feature_sets:
            feat_ids.append(fid)

    if not feat_ids:
        continue

    X_all = df_eng
    X_train = X_all.iloc[train_idx]
    y_train = y[train_idx]
    X_val = X_all.iloc[val_idx]
    y_val = y[val_idx]
    X_hold = X_all.iloc[hold_idx]
    y_hold = y[hold_idx]

    best_val_score = -1e9
    best_row = None

    for feat_id in feat_ids:
        features = [f for f in base_feature_sets[(domain, mode, feat_id)] if f in X_all.columns]
        if len(features) < 5:
            continue
        Xtr = X_train[features]
        Xva = X_val[features]
        Xho = X_hold[features]

        heavy_subset = {
            ("adhd", "caregiver_1_3"),
            ("adhd", "psychologist_1_3"),
            ("depression", "caregiver_full"),
            ("elimination", "caregiver_1_3"),
            ("anxiety", "caregiver_1_3"),
        }
        for fam, cls, params in MODEL_CONFIGS:
            if fam in ["xgboost", "lightgbm", "catboost"] and (domain, mode) not in heavy_subset:
                continue
            if fam in ["xgboost", "lightgbm", "catboost"] and feat_id != "full_eligible":
                continue
            if "random_state" in params:
                params = dict(params)
                params["random_state"] = seed_base
            model = cls(**params)

            sample_weight = None
            if fam in ["hgb", "xgboost", "lightgbm", "catboost"]:
                pos = (y_train == 1).sum()
                neg = (y_train == 0).sum()
                if pos > 0:
                    w_pos = neg / pos
                    sample_weight = np.where(y_train == 1, w_pos, 1.0)

            # Train base model once for non-calibrated path
            model.fit(Xtr, y_train, sample_weight=sample_weight)

            if hasattr(model, "predict_proba"):
                base_val_prob = model.predict_proba(Xva)[:, 1]
            else:
                base_val_prob = model.decision_function(Xva)
                base_val_prob = (base_val_prob - base_val_prob.min()) / (base_val_prob.max() - base_val_prob.min() + 1e-9)

            for cal in calibrations:
                if cal == "none":
                    cal_model = model
                    cal_val_prob = base_val_prob
                else:
                    # Refit inside calibrator using train only
                    cal_model = CalibratedClassifierCV(cls(**params), method=cal, cv=3)
                    cal_model.fit(Xtr, y_train)
                    cal_val_prob = cal_model.predict_proba(Xva)[:, 1]

                policies = threshold_policies
                if fam in ["xgboost", "lightgbm", "catboost"]:
                    policies = ["default_0_5"]
                for policy in policies:
                    threshold = find_threshold(policy, y_val, cal_val_prob)
                    val_metrics = get_metrics(y_val, cal_val_prob, threshold)
                    val_score = val_metrics["balanced_accuracy"]

                    if hasattr(cal_model, "predict_proba"):
                        hold_prob = cal_model.predict_proba(Xho)[:, 1]
                        train_prob = cal_model.predict_proba(Xtr)[:, 1]
                    else:
                        hold_prob = cal_model.decision_function(Xho)
                        hold_prob = (hold_prob - hold_prob.min()) / (hold_prob.max() - hold_prob.min() + 1e-9)
                        train_prob = cal_model.decision_function(Xtr)
                        train_prob = (train_prob - train_prob.min()) / (train_prob.max() - train_prob.min() + 1e-9)

                    hold_metrics = get_metrics(y_hold, hold_prob, threshold)
                    train_metrics = get_metrics(y_train, train_prob, threshold)

                    trial_id += 1
                    trial_rows.append(
                        {
                            "trial_id": trial_id,
                            "domain": domain,
                            "mode": mode,
                            "feature_set_id": feat_id,
                            "model_family": fam,
                            "config": json.dumps(params, sort_keys=True),
                            "calibration": cal,
                            "threshold_policy": policy,
                            "threshold": threshold,
                            "n_features": len(features),
                            "val_balanced_accuracy": val_metrics["balanced_accuracy"],
                            "val_pr_auc": val_metrics["pr_auc"],
                            "val_precision": val_metrics["precision"],
                            "val_recall": val_metrics["recall"],
                            "holdout_precision": hold_metrics["precision"],
                            "holdout_recall": hold_metrics["recall"],
                            "holdout_specificity": hold_metrics["specificity"],
                            "holdout_balanced_accuracy": hold_metrics["balanced_accuracy"],
                            "holdout_f1": hold_metrics["f1"],
                            "holdout_roc_auc": hold_metrics["roc_auc"],
                            "holdout_pr_auc": hold_metrics["pr_auc"],
                            "holdout_brier": hold_metrics["brier"],
                            "train_balanced_accuracy": train_metrics["balanced_accuracy"],
                            "overfit_gap_train_val_ba": train_metrics["balanced_accuracy"] - val_metrics["balanced_accuracy"],
                        }
                    )

                    if val_score > best_val_score:
                        best_val_score = val_score
                        best_row = trial_rows[-1].copy()
                        best_row["features"] = features
                        best_row["hold_prob"] = hold_prob

    if best_row is None:
        continue

    # Calibration retry (sigmoid) on best config only
    try:
        best_features = best_row["features"]
        Xtr = X_train[best_features]
        Xva = X_val[best_features]
        Xho = X_hold[best_features]
        params = json.loads(best_row["config"])
        fam = best_row["model_family"]
        cls = None
        for f_name, f_cls, _ in MODEL_CONFIGS:
            if f_name == fam:
                cls = f_cls
                break
        if cls is not None:
            cal_model = CalibratedClassifierCV(cls(**params), method="sigmoid", cv=3)
            cal_model.fit(Xtr, y_train)
            cal_val_prob = cal_model.predict_proba(Xva)[:, 1]
            for policy in threshold_policies:
                threshold = find_threshold(policy, y_val, cal_val_prob)
                val_metrics = get_metrics(y_val, cal_val_prob, threshold)
                val_score = val_metrics["balanced_accuracy"]
                hold_prob = cal_model.predict_proba(Xho)[:, 1]
                hold_metrics = get_metrics(y_hold, hold_prob, threshold)
                train_prob = cal_model.predict_proba(Xtr)[:, 1]
                train_metrics = get_metrics(y_train, train_prob, threshold)
                trial_id += 1
                trial_rows.append(
                    {
                        "trial_id": trial_id,
                        "domain": domain,
                        "mode": mode,
                        "feature_set_id": best_row["feature_set_id"],
                        "model_family": fam,
                        "config": json.dumps(params, sort_keys=True),
                        "calibration": "sigmoid",
                        "threshold_policy": policy,
                        "threshold": threshold,
                        "n_features": len(best_features),
                        "val_balanced_accuracy": val_metrics["balanced_accuracy"],
                        "val_pr_auc": val_metrics["pr_auc"],
                        "val_precision": val_metrics["precision"],
                        "val_recall": val_metrics["recall"],
                        "holdout_precision": hold_metrics["precision"],
                        "holdout_recall": hold_metrics["recall"],
                        "holdout_specificity": hold_metrics["specificity"],
                        "holdout_balanced_accuracy": hold_metrics["balanced_accuracy"],
                        "holdout_f1": hold_metrics["f1"],
                        "holdout_roc_auc": hold_metrics["roc_auc"],
                        "holdout_pr_auc": hold_metrics["pr_auc"],
                        "holdout_brier": hold_metrics["brier"],
                        "train_balanced_accuracy": train_metrics["balanced_accuracy"],
                        "overfit_gap_train_val_ba": train_metrics["balanced_accuracy"] - val_metrics["balanced_accuracy"],
                    }
                )
                if val_score > best_val_score:
                    best_val_score = val_score
                    best_row = trial_rows[-1].copy()
                    best_row["features"] = best_features
                    best_row["hold_prob"] = hold_prob
    except Exception:
        pass

    hold_prob = best_row["hold_prob"]
    band = 0.1
    decided = (hold_prob <= 0.5 - band) | (hold_prob >= 0.5 + band)
    coverage = decided.mean()
    if decided.sum() > 0:
        decided_metrics = get_metrics(y_hold[decided], hold_prob[decided], best_row["threshold"])
    else:
        decided_metrics = {k: 0.0 for k in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]}

    candidate_best.append(
        {
            "domain": domain,
            "mode": mode,
            "feature_set_id": best_row["feature_set_id"],
            "model_family": best_row["model_family"],
            "config": best_row["config"],
            "calibration": best_row["calibration"],
            "threshold_policy": best_row["threshold_policy"],
            "threshold": best_row["threshold"],
            "n_features": best_row["n_features"],
            "precision": best_row["holdout_precision"],
            "recall": best_row["holdout_recall"],
            "specificity": best_row["holdout_specificity"],
            "balanced_accuracy": best_row["holdout_balanced_accuracy"],
            "f1": best_row["holdout_f1"],
            "roc_auc": best_row["holdout_roc_auc"],
            "pr_auc": best_row["holdout_pr_auc"],
            "brier": best_row["holdout_brier"],
            "overfit_gap_train_val_ba": best_row["overfit_gap_train_val_ba"],
            "abstain_band": band,
            "abstain_coverage": coverage,
            "abstain_precision": decided_metrics["precision"],
            "abstain_recall": decided_metrics["recall"],
            "abstain_balanced_accuracy": decided_metrics["balanced_accuracy"],
            "abstain_pr_auc": decided_metrics["pr_auc"],
        }
    )

trials_df = pd.DataFrame(trial_rows)
trials_df.to_csv(BASE / "trials/hybrid_no_external_scores_boosted_trial_registry.csv", index=False)
trials_df.to_csv(BASE / "trials/hybrid_no_external_scores_boosted_trial_metrics_full.csv", index=False)

best_df = pd.DataFrame(candidate_best)

v2 = pd.read_csv(V2_FINAL)
v2 = v2[["domain", "mode", "precision", "recall", "balanced_accuracy", "pr_auc", "brier"]]
comp = best_df.merge(v2, on=["domain", "mode"], how="left", suffixes=("", "_v2"))
for m in ["precision", "recall", "balanced_accuracy", "pr_auc", "brier"]:
    comp[f"delta_{m}"] = comp[m] - comp[f"{m}_v2"]
comp.to_csv(BASE / "tables/hybrid_no_external_scores_boosted_vs_v2_comparison.csv", index=False)


def quality(row):
    if row["precision"] >= 0.88 and row["recall"] >= 0.80 and row["balanced_accuracy"] >= 0.90 and row["pr_auc"] >= 0.90 and row["brier"] <= 0.05:
        return "muy_bueno"
    if row["precision"] >= 0.84 and row["recall"] >= 0.75 and row["balanced_accuracy"] >= 0.88 and row["pr_auc"] >= 0.88 and row["brier"] <= 0.06:
        return "bueno"
    if row["precision"] >= 0.80 and row["recall"] >= 0.70 and row["balanced_accuracy"] >= 0.85 and row["pr_auc"] >= 0.85 and row["brier"] <= 0.08:
        return "aceptable"
    return "malo"


best_df["quality_label"] = best_df.apply(quality, axis=1)
ranked = best_df.sort_values(["balanced_accuracy", "pr_auc", "precision"], ascending=False)
ranked.to_csv(BASE / "tables/hybrid_no_external_scores_boosted_final_ranked_models.csv", index=False)

champs = best_df.sort_values(["balanced_accuracy", "pr_auc", "precision"], ascending=False).groupby("domain").head(1)
champs.to_csv(BASE / "tables/hybrid_no_external_scores_boosted_final_champions.csv", index=False)

ens_rows = []
for (domain, mode), grp in trials_df.groupby(["domain", "mode"]):
    top2 = grp.sort_values("val_balanced_accuracy", ascending=False).head(2)
    if len(top2) < 2:
        continue
    ens_rows.append(
        {
            "domain": domain,
            "mode": mode,
            "ensemble_type": "avg_top2_val",
            "members": "|".join(top2["trial_id"].astype(str).tolist()),
            "note": "ensemble placeholder; use best single model",
        }
    )
pd.DataFrame(ens_rows).to_csv(BASE / "ensembles/hybrid_no_external_scores_ensemble_results.csv", index=False)

trials_df[["domain", "mode", "model_family", "calibration", "val_balanced_accuracy", "val_pr_auc"]].to_csv(
    BASE / "calibration/hybrid_no_external_scores_boosted_calibration.csv", index=False
)
trials_df[["domain", "mode", "threshold_policy", "threshold", "val_balanced_accuracy", "val_pr_auc"]].to_csv(
    BASE / "thresholds/hybrid_no_external_scores_boosted_thresholds.csv", index=False
)

pd.DataFrame([{"note": "bootstrap not computed in v3 minimal run"}]).to_csv(
    BASE / "bootstrap/hybrid_no_external_scores_boosted_bootstrap.csv", index=False
)
pd.DataFrame([{"note": "seed stability not re-fit in v3 minimal run"}]).to_csv(
    BASE / "stability/hybrid_no_external_scores_boosted_seed_stability.csv", index=False
)
pd.DataFrame([{"note": "ablation not computed in v3 minimal run"}]).to_csv(
    BASE / "ablation/hybrid_no_external_scores_boosted_ablation.csv", index=False
)
pd.DataFrame([{"note": "stress tests not computed in v3 minimal run"}]).to_csv(
    BASE / "stress/hybrid_no_external_scores_boosted_stress.csv", index=False
)

inv = pd.DataFrame(
    [
        {
            "run_id": "hybrid_no_external_scores_boosted_v3",
            "dataset": str(DATASET),
            "n_rows": len(df),
            "n_features_base": len(base_features),
            "n_features_engineered_v3": len(new_eng_features),
            "priority_pairs": len(PRIORITY),
            "seed_base": seed_base,
        }
    ]
)
inv.to_csv(BASE / "inventory/hybrid_no_external_scores_boosted_inventory.csv", index=False)
(BASE / "inventory/hybrid_no_external_scores_boosted_inventory.md").write_text(inv.to_markdown(index=False), encoding="utf-8")

fe_results_df = pd.DataFrame(
    [
        {
            "n_engineered_features": len(new_eng_features),
            "note": "engineered features applied globally to priority candidates",
        }
    ]
)
fe_results_df.to_csv(BASE / "feature_engineering/hybrid_no_external_scores_boosted_feature_results.csv", index=False)

summary = "# Hybrid No External Scores Boosted v3 - Summary\n\n"
summary += f"- Priority pairs evaluated: {len(PRIORITY)}\n"
summary += f"- Model families available: {', '.join(model_families)}\n"
summary += f"- Engineered features added: {len(new_eng_features)}\n"
summary += f"- Trials: {len(trials_df)}\n\n"
if not best_df.empty:
    summary += "Best candidates (holdout):\n\n"
    summary += best_df[
        ["domain", "mode", "model_family", "feature_set_id", "precision", "recall", "balanced_accuracy", "pr_auc", "brier", "quality_label"]
    ].to_markdown(index=False)
(BASE / "reports/hybrid_no_external_scores_boosted_summary.md").write_text(summary, encoding="utf-8")

decision = "# Hybrid No External Scores Boosted v3 - Modeling Decision\n\n"
decision += "Champions per domain (priority set):\n\n"
if not champs.empty:
    decision += champs[
        ["domain", "mode", "model_family", "feature_set_id", "precision", "recall", "balanced_accuracy", "pr_auc", "brier", "quality_label"]
    ].to_markdown(index=False)
(BASE / "reports/hybrid_no_external_scores_boosted_modeling_decision.md").write_text(decision, encoding="utf-8")

fe_report = "# Hybrid No External Scores Boosted v3 - Feature Engineering\n\n"
fe_report += eng_df.to_markdown(index=False)
(BASE / "reports/hybrid_no_external_scores_boosted_feature_engineering_report.md").write_text(fe_report, encoding="utf-8")

ceiling = "# Hybrid No External Scores Boosted v3 - Ceiling Decision\n\n"
ceiling += "Use v2 comparison deltas to assess room for improvement.\n"
(BASE / "reports/hybrid_no_external_scores_boosted_ceiling_decision.md").write_text(ceiling, encoding="utf-8")

manifest = {
    "run_id": "hybrid_no_external_scores_boosted_v3",
    "n_trials": int(len(trials_df)),
    "n_candidates": int(len(best_df)),
    "artifacts": {
        "inventory": str(BASE / "inventory/hybrid_no_external_scores_boosted_inventory.csv"),
        "trials": str(BASE / "trials/hybrid_no_external_scores_boosted_trial_metrics_full.csv"),
        "final_ranked": str(BASE / "tables/hybrid_no_external_scores_boosted_final_ranked_models.csv"),
        "final_champions": str(BASE / "tables/hybrid_no_external_scores_boosted_final_champions.csv"),
        "comparison_vs_v2": str(BASE / "tables/hybrid_no_external_scores_boosted_vs_v2_comparison.csv"),
    },
}
(ART / "hybrid_no_external_scores_boosted_v3_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print("done")
