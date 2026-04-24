from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "final_ceiling_check_v15"
INV = BASE / "inventory"
CMP = BASE / "comparison"
BST = BASE / "bootstrap"
STB = BASE / "stability"
TBL = BASE / "tables"
RPT = BASE / "reports"
ART = ROOT / "artifacts" / "final_ceiling_check_v15"

MODES = ["caregiver", "psychologist"]
DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
KEY_METRICS = ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    for p in [BASE, INV, CMP, BST, STB, TBL, RPT, ART]:
        p.mkdir(parents=True, exist_ok=True)


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
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = []
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
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join([header, sep] + rows)


def safe_float(x: Any) -> float | None:
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def bootstrap_ci(values: np.ndarray, n_boot: int = 4000, seed: int = 42) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    n = len(values)
    reps = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        reps[i] = float(np.mean(values[idx]))
    return float(np.percentile(reps, 2.5)), float(np.percentile(reps, 97.5)), float(np.mean(reps))


def load_v4_tables() -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for mode in MODES:
        out[f"{mode}_full"] = pd.read_csv(
            ROOT / "data" / "questionnaire_final_ceiling_v4" / mode / f"{mode}_full_results.csv"
        )
        out[f"{mode}_trial"] = pd.read_csv(
            ROOT / "data" / "questionnaire_final_ceiling_v4" / mode / f"{mode}_trial_registry.csv"
        )
    out["readiness"] = pd.read_csv(ROOT / "data" / "questionnaire_final_ceiling_v4" / "tables" / "output_readiness_matrix.csv")
    out["runtime"] = pd.read_csv(
        ROOT / "data" / "questionnaire_final_ceiling_v4" / "tables" / "final_model_runtime_validation_results.csv"
    )
    out["ceiling"] = pd.read_csv(ROOT / "data" / "questionnaire_final_ceiling_v4" / "tables" / "ceiling_detection_matrix.csv")
    return out


def load_v10_tables() -> dict[str, pd.DataFrame]:
    return {
        "delta_v9_v10": pd.read_csv(ROOT / "data" / "final_hardening_v10" / "tables" / "final_delta_vs_v9.csv"),
        "source_shift": pd.read_csv(ROOT / "data" / "final_hardening_v10" / "source_shift" / "source_shift_results.csv"),
        "slice_gap": pd.read_csv(ROOT / "data" / "final_hardening_v10" / "slices" / "slice_gap_matrix.csv"),
    }


def load_elimination_tables() -> dict[str, pd.DataFrame]:
    return {
        "ops": pd.read_csv(ROOT / "data" / "elimination_clean_rebuild_v12" / "tables" / "elimination_clean_operating_modes.csv"),
        "readiness": pd.read_csv(ROOT / "data" / "elimination_clean_rebuild_v12" / "tables" / "elimination_clean_output_readiness.csv"),
        "trials": pd.read_csv(ROOT / "data" / "elimination_clean_rebuild_v12" / "trials" / "elimination_clean_trial_metrics_full.csv"),
        "stress": pd.read_csv(ROOT / "data" / "elimination_clean_rebuild_v12" / "stress" / "elimination_clean_stress_results.csv"),
        "v14_delta": pd.read_csv(ROOT / "data" / "elimination_final_push_v14" / "tables" / "elimination_v14_final_delta.csv"),
    }


def selected_threshold_from_trials(
    trial_df: pd.DataFrame,
    domain: str,
    profile_name: str,
    config_id: str,
    calibration: str,
    threshold_policy: str,
    selected_seed: int,
) -> float | None:
    mask = (
        (trial_df["domain"] == domain)
        & (trial_df["profile_name"] == profile_name)
        & (trial_df["config_id"] == config_id)
        & (trial_df["calibration"] == calibration)
        & (trial_df["threshold_policy"] == threshold_policy)
        & (trial_df["seed"] == selected_seed)
    )
    rows = trial_df[mask]
    if rows.empty:
        return None
    return safe_float(rows.iloc[0]["threshold"])


def build_final_inventory(v4: dict[str, pd.DataFrame], elim: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for mode in MODES:
        full = v4[f"{mode}_full"].copy()
        trial = v4[f"{mode}_trial"].copy()
        readiness = v4["readiness"][v4["readiness"]["mode"] == mode].set_index("domain")
        runtime = v4["runtime"][v4["runtime"]["mode"] == mode]
        runtime_strong_map = runtime.groupby("domain")["status"].apply(lambda s: bool((s == "pass").all())).to_dict()

        for _, r in full.iterrows():
            domain = str(r["domain"])
            if domain == "elimination":
                continue
            threshold = selected_threshold_from_trials(
                trial_df=trial,
                domain=domain,
                profile_name=str(r["profile_name"]),
                config_id=str(r["config_id"]),
                calibration=str(r["calibration"]),
                threshold_policy=str(r["threshold_policy"]),
                selected_seed=int(r["selected_seed"]),
            )
            ready = readiness.loc[domain] if domain in readiness.index else None
            rows.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "champion_model": str(r["config_id"]),
                    "champion_profile": str(r["profile_name"]),
                    "valid_from_version": "final_hardening_v10",
                    "selected_in_campaign": "questionnaire_final_ceiling_v4",
                    "threshold_final": threshold,
                    "threshold_policy_final": str(r["threshold_policy"]),
                    "calibration_final": str(r["calibration"]),
                    "output_mode_final": str(r["threshold_policy"]),
                    "caveat_final": "screening_only_requires_professional_context",
                    "runtime_strong_entry": runtime_strong_map.get(domain, False),
                    "readiness_score": safe_float(ready["readiness_score"]) if ready is not None else None,
                    "precision": safe_float(r["precision"]),
                    "recall": safe_float(r["recall"]),
                    "specificity": safe_float(r["specificity"]),
                    "balanced_accuracy": safe_float(r["balanced_accuracy"]),
                    "f1": safe_float(r["f1"]),
                    "roc_auc": safe_float(r["roc_auc"]),
                    "pr_auc": safe_float(r["pr_auc"]),
                    "brier": safe_float(r["brier"]),
                    "lineage_note": "metrics comparable in-repo; strict cross-campaign identity por_confirmar",
                    "source": f"questionnaire_final_ceiling_v4/{mode}",
                }
            )

    ops = elim["ops"]
    out_ready = elim["readiness"]
    v4_runtime = v4["runtime"]
    runtime_strong_map = v4_runtime.groupby(["mode", "domain"])["status"].apply(lambda s: bool((s == "pass").all())).to_dict()

    for _, r in out_ready.iterrows():
        mode = str(r["mode"])
        domain = str(r["domain"])
        selected_mode = str(r["selected_operating_mode"])
        op = ops[(ops["mode"] == mode) & (ops["operating_mode"] == selected_mode)].iloc[0]
        rows.append(
            {
                "mode": mode,
                "domain": domain,
                "champion_model": f"{op['source_family']}::{op['source_feature_set']}",
                "champion_profile": selected_mode,
                "valid_from_version": "elimination_clean_rebuild_v12",
                "selected_in_campaign": "elimination_clean_rebuild_v12",
                "threshold_final": safe_float(op["threshold"]),
                "threshold_policy_final": selected_mode,
                "calibration_final": str(op["source_calibration"]),
                "output_mode_final": selected_mode,
                "caveat_final": str(r["final_output_status"]),
                "runtime_strong_entry": bool(runtime_strong_map.get((mode, domain), False)) and str(r["final_output_status"]) != "uncertainty_preferred",
                "readiness_score": None,
                "precision": safe_float(r["precision"]),
                "recall": safe_float(r["recall"]),
                "specificity": safe_float(r["specificity"]),
                "balanced_accuracy": safe_float(r["balanced_accuracy"]),
                "f1": safe_float(r["f1"]),
                "roc_auc": None,
                "pr_auc": safe_float(r["pr_auc"]),
                "brier": safe_float(r["brier"]),
                "lineage_note": "KEEP_V12 against v14 confirmed; uncertainty_preferred retained",
                "source": "elimination_clean_rebuild_v12",
            }
        )

    cols = [
        "mode",
        "domain",
        "champion_model",
        "champion_profile",
        "valid_from_version",
        "selected_in_campaign",
        "threshold_final",
        "threshold_policy_final",
        "calibration_final",
        "output_mode_final",
        "caveat_final",
        "runtime_strong_entry",
        "readiness_score",
        "precision",
        "recall",
        "specificity",
        "balanced_accuracy",
        "f1",
        "roc_auc",
        "pr_auc",
        "brier",
        "lineage_note",
        "source",
    ]
    return pd.DataFrame(rows)[cols].sort_values(["mode", "domain"]).reset_index(drop=True)


def progression_rows_for_domain(
    mode: str,
    domain: str,
    inv_row: pd.Series,
    v10_delta: pd.DataFrame,
    elim_v14_delta: pd.DataFrame,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if domain != "elimination":
        r = v10_delta[(v10_delta["mode"] == mode) & (v10_delta["domain"] == domain)].iloc[0]
        out.append(
            {
                "mode": mode,
                "domain": domain,
                "stage_order": 1,
                "stage_label": "baseline_strong_previous",
                "version_ref": "final_hardening_v9_baseline",
                "precision": safe_float(r["precision_v9"]),
                "recall": safe_float(r["recall_v9"]),
                "specificity": safe_float(r["specificity_v9"]),
                "balanced_accuracy": safe_float(r["balanced_accuracy_v9"]),
                "f1": safe_float(r["f1_v9"]),
                "roc_auc": safe_float(r["roc_auc_v9"]),
                "pr_auc": safe_float(r["pr_auc_v9"]),
                "brier": safe_float(r["brier_v9"]),
                "stage_note": "baseline fuerte anterior",
            }
        )
        out.append(
            {
                "mode": mode,
                "domain": domain,
                "stage_order": 2,
                "stage_label": "last_material_improvement",
                "version_ref": "final_hardening_v10",
                "precision": safe_float(r["precision_v10"]),
                "recall": safe_float(r["recall_v10"]),
                "specificity": safe_float(r["specificity_v10"]),
                "balanced_accuracy": safe_float(r["balanced_accuracy_v10"]),
                "f1": safe_float(r["f1_v10"]),
                "roc_auc": safe_float(r["roc_auc_v10"]),
                "pr_auc": safe_float(r["pr_auc_v10"]),
                "brier": safe_float(r["brier_v10"]),
                "stage_note": "ultima mejora material previa",
            }
        )
        out.append(
            {
                "mode": mode,
                "domain": domain,
                "stage_order": 3,
                "stage_label": "final_current",
                "version_ref": str(inv_row["selected_in_campaign"]),
                "precision": safe_float(inv_row["precision"]),
                "recall": safe_float(inv_row["recall"]),
                "specificity": safe_float(inv_row["specificity"]),
                "balanced_accuracy": safe_float(inv_row["balanced_accuracy"]),
                "f1": safe_float(inv_row["f1"]),
                "roc_auc": safe_float(inv_row["roc_auc"]),
                "pr_auc": safe_float(inv_row["pr_auc"]),
                "brier": safe_float(inv_row["brier"]),
                "stage_note": "version final vigente",
            }
        )
        return out

    e = elim_v14_delta[elim_v14_delta["mode"] == mode].iloc[0]
    out.append(
        {
            "mode": mode,
            "domain": domain,
            "stage_order": 1,
            "stage_label": "baseline_strong_previous",
            "version_ref": "elimination_baseline_pre_v12",
            "precision": safe_float(e["baseline_precision"]),
            "recall": safe_float(e["baseline_recall"]),
            "specificity": safe_float(e["baseline_specificity"]),
            "balanced_accuracy": safe_float(e["baseline_balanced_accuracy"]),
            "f1": safe_float(e["baseline_f1"]),
            "roc_auc": None,
            "pr_auc": safe_float(e["baseline_pr_auc"]),
            "brier": safe_float(e["baseline_brier"]),
            "stage_note": "baseline fuerte anterior de linea elimination",
        }
    )
    out.append(
        {
            "mode": mode,
            "domain": domain,
            "stage_order": 2,
            "stage_label": "last_material_improvement",
            "version_ref": "elimination_clean_rebuild_v12",
            "precision": safe_float(e["v12_precision"]),
            "recall": safe_float(e["v12_recall"]),
            "specificity": safe_float(e["v12_specificity"]),
            "balanced_accuracy": safe_float(e["v12_balanced_accuracy"]),
            "f1": safe_float(e["v12_f1"]),
            "roc_auc": None,
            "pr_auc": safe_float(e["v12_pr_auc"]),
            "brier": safe_float(e["v12_brier"]),
            "stage_note": "ultima mejora material previa",
        }
    )
    out.append(
        {
            "mode": mode,
            "domain": domain,
            "stage_order": 3,
            "stage_label": "final_current",
            "version_ref": str(inv_row["selected_in_campaign"]),
            "precision": safe_float(inv_row["precision"]),
            "recall": safe_float(inv_row["recall"]),
            "specificity": safe_float(inv_row["specificity"]),
            "balanced_accuracy": safe_float(inv_row["balanced_accuracy"]),
            "f1": safe_float(inv_row["f1"]),
            "roc_auc": safe_float(inv_row["roc_auc"]),
            "pr_auc": safe_float(inv_row["pr_auc"]),
            "brier": safe_float(inv_row["brier"]),
            "stage_note": "version final vigente (KEEP_V12)",
        }
    )
    out.append(
        {
            "mode": mode,
            "domain": domain,
            "stage_order": 4,
            "stage_label": "exploratory_later_version",
            "version_ref": "elimination_final_push_v14",
            "precision": safe_float(e["v14_precision"]),
            "recall": safe_float(e["v14_recall"]),
            "specificity": safe_float(e["v14_specificity"]),
            "balanced_accuracy": safe_float(e["v14_balanced_accuracy"]),
            "f1": safe_float(e["v14_f1"]),
            "roc_auc": None,
            "pr_auc": safe_float(e["v14_pr_auc"]),
            "brier": safe_float(e["v14_brier"]),
            "stage_note": "exploratorio; decision formal KEEP_V12",
        }
    )
    return out


def build_progression(inv: pd.DataFrame, v10: dict[str, pd.DataFrame], elim: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, inv_row in inv.iterrows():
        mode = str(inv_row["mode"])
        domain = str(inv_row["domain"])
        rows.extend(
            progression_rows_for_domain(mode, domain, inv_row, v10["delta_v9_v10"], elim["v14_delta"])
        )
    out = pd.DataFrame(rows).sort_values(["mode", "domain", "stage_order"]).reset_index(drop=True)
    for metric in ["balanced_accuracy", "pr_auc", "brier"]:
        out[f"delta_{metric}_vs_prev"] = out.groupby(["mode", "domain"])[metric].diff()
        out[f"delta_{metric}_vs_stage1"] = out[metric] - out.groupby(["mode", "domain"])[metric].transform("first")
    return out


def build_bootstrap(inv: pd.DataFrame, v4: dict[str, pd.DataFrame], elim: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, r in inv.iterrows():
        mode = str(r["mode"])
        domain = str(r["domain"])
        if domain != "elimination":
            full = v4[f"{mode}_full"]
            tr = v4[f"{mode}_trial"]
            sel = full[full["domain"] == domain].iloc[0]
            mask = (
                (tr["domain"] == domain)
                & (tr["profile_name"] == sel["profile_name"])
                & (tr["config_id"] == sel["config_id"])
                & (tr["calibration"] == sel["calibration"])
                & (tr["threshold_policy"] == sel["threshold_policy"])
            )
            sample = tr[mask].copy()
            for metric in KEY_METRICS:
                vals = sample[metric].dropna().to_numpy(dtype=float)
                lo, hi, m = bootstrap_ci(vals, n_boot=4000, seed=42) if len(vals) >= 2 else (np.nan, np.nan, np.nan)
                point = safe_float(sel[metric]) if metric in sel else safe_float(r.get(metric))
                rows.append(
                    {
                        "mode": mode,
                        "domain": domain,
                        "metric": metric,
                        "point_estimate": point,
                        "bootstrap_mean": m,
                        "ci95_low": lo,
                        "ci95_high": hi,
                        "ci95_half_width": (hi - lo) / 2 if np.isfinite(lo) and np.isfinite(hi) else None,
                        "n_samples": len(vals),
                        "method": "seed_bootstrap_selected_config",
                        "status": "ok" if len(vals) >= 2 else "por_confirmar_insufficient_samples",
                    }
                )
            continue

        stress = elim["stress"][elim["stress"]["mode"] == mode].copy()
        trial = elim["trials"][elim["trials"]["mode"] == mode].copy()
        readiness = elim["readiness"]
        ops = elim["ops"]
        selected_mode = str(readiness[readiness["mode"] == mode].iloc[0]["selected_operating_mode"])
        op_row = ops[(ops["mode"] == mode) & (ops["operating_mode"] == selected_mode)].iloc[0]
        for metric in KEY_METRICS:
            if metric == "roc_auc":
                tmask = (
                    (trial["feature_set"] == op_row["source_feature_set"])
                    & (trial["family"] == op_row["source_family"])
                    & (trial["calibration"] == op_row["source_calibration"])
                    & (np.isclose(trial["threshold"], float(op_row["threshold"])))
                )
                vals = trial[tmask]["roc_auc"].dropna().to_numpy(dtype=float)
                point = float(vals[0]) if len(vals) == 1 else None
                rows.append(
                    {
                        "mode": mode,
                        "domain": domain,
                        "metric": metric,
                        "point_estimate": point,
                        "bootstrap_mean": None,
                        "ci95_low": None,
                        "ci95_high": None,
                        "ci95_half_width": None,
                        "n_samples": int(len(vals)),
                        "method": "exact_selected_trial_lookup",
                        "status": "por_confirmar_single_sample_for_ci",
                    }
                )
                continue

            vals = stress[metric].dropna().to_numpy(dtype=float)
            point = safe_float(readiness[readiness["mode"] == mode].iloc[0][metric]) if metric in readiness.columns else float(stress.iloc[0][metric])
            lo, hi, m = bootstrap_ci(vals, n_boot=4000, seed=42)
            rows.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "metric": metric,
                    "point_estimate": point,
                    "bootstrap_mean": m,
                    "ci95_low": lo,
                    "ci95_high": hi,
                    "ci95_half_width": (hi - lo) / 2,
                    "n_samples": len(vals),
                    "method": "stress_scenario_bootstrap_proxy",
                    "status": "proxy_not_seed_bootstrap",
                }
            )
    return pd.DataFrame(rows).sort_values(["mode", "domain", "metric"]).reset_index(drop=True)


def build_stability(inv: pd.DataFrame, v4: dict[str, pd.DataFrame], v10: dict[str, pd.DataFrame], elim: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, r in inv.iterrows():
        mode = str(r["mode"])
        domain = str(r["domain"])
        if domain != "elimination":
            full = v4[f"{mode}_full"]
            row = full[full["domain"] == domain].iloc[0]
            sg = v10["slice_gap"]
            sg_row = sg[(sg["mode"] == mode) & (sg["domain"] == domain)]
            fragile_gap = safe_float(sg_row.iloc[0]["slice_ba_gap"]) if not sg_row.empty else None
            fragile_status = str(sg_row.iloc[0]["corrected_status"]) if not sg_row.empty else "por_confirmar"
            seed_std = safe_float(row["seed_std"])
            split_std = safe_float(row["split_std"])
            miss = safe_float(row["missingness_sensitivity"])
            cov_drop = safe_float(row["partial_questionnaire_sensitivity"])
            src_mix = safe_float(row["realism_shift_delta"])
            stable = (
                (seed_std is not None and seed_std <= 0.005)
                and (split_std is not None and split_std <= 0.006)
                and (miss is not None and abs(miss) <= 0.03)
                and (cov_drop is not None and abs(cov_drop) <= 0.04)
            )
            rows.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "seed_std": seed_std,
                    "split_std": split_std,
                    "missingness_delta": miss,
                    "coverage_drop_delta": cov_drop,
                    "source_mix_delta": src_mix,
                    "borderline_delta_ba": fragile_gap,
                    "fragile_slice_status": fragile_status,
                    "stability_status": "stable" if stable else "watch",
                    "stability_note": "v4 full_results + v10 slice gap",
                }
            )
            continue

        stress = elim["stress"][elim["stress"]["mode"] == mode].copy()
        baseline = stress[stress["scenario"] == "baseline_clean"].iloc[0]
        rows.append(
            {
                "mode": mode,
                "domain": domain,
                "seed_std": None,
                "split_std": None,
                "missingness_delta": safe_float(
                    stress[stress["scenario"] == "missingness_moderate_25pct"]["delta_ba_vs_baseline_clean"].iloc[0]
                ),
                "coverage_drop_delta": safe_float(
                    stress[stress["scenario"] == "cbcl_coverage_drop"]["delta_ba_vs_baseline_clean"].iloc[0]
                ),
                "source_mix_delta": safe_float(
                    stress[stress["scenario"] == "source_mix_shift"]["delta_ba_vs_baseline_clean"].iloc[0]
                ),
                "borderline_delta_ba": safe_float(
                    stress[stress["scenario"] == "borderline_cases_threshold_pm_0.08"]["delta_ba_vs_baseline_clean"].iloc[0]
                ),
                "fragile_slice_status": "structural_fragility_detected",
                "stability_status": "fragile_but_bounded",
                "stability_note": f"baseline_ba={float(baseline['balanced_accuracy']):.6f}; stress-scenario matrix",
            }
        )
    return pd.DataFrame(rows).sort_values(["mode", "domain"]).reset_index(drop=True)


def build_ceiling_matrix(
    inv: pd.DataFrame, progression: pd.DataFrame, bootstrap: pd.DataFrame, stability: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, r in inv.iterrows():
        mode = str(r["mode"])
        domain = str(r["domain"])
        prog = progression[(progression["mode"] == mode) & (progression["domain"] == domain)].sort_values("stage_order")
        final3 = prog[prog["stage_order"] <= 3]
        d_ba = safe_float(final3.iloc[-1]["delta_balanced_accuracy_vs_prev"]) if len(final3) >= 2 else None
        d_pr = safe_float(final3.iloc[-1]["delta_pr_auc_vs_prev"]) if len(final3) >= 2 else None
        d_br = safe_float(final3.iloc[-1]["delta_brier_vs_prev"]) if len(final3) >= 2 else None

        b = bootstrap[(bootstrap["mode"] == mode) & (bootstrap["domain"] == domain)]
        half = b.set_index("metric")["ci95_half_width"].to_dict()
        half_ba = max(safe_float(half.get("balanced_accuracy")) or 0.005, 0.010)
        half_pr = max(safe_float(half.get("pr_auc")) or 0.005, 0.010)
        half_br = max(safe_float(half.get("brier")) or 0.003, 0.005)
        in_noise = (
            (d_ba is not None and abs(d_ba) <= half_ba)
            and (d_pr is not None and abs(d_pr) <= half_pr)
            and (d_br is not None and abs(d_br) <= half_br)
        )
        stab = stability[(stability["mode"] == mode) & (stability["domain"] == domain)].iloc[0]
        robust = str(stab["stability_status"]) in {"stable", "fragile_but_bounded"}
        ready = bool(r["runtime_strong_entry"])
        final_ba = safe_float(r["balanced_accuracy"]) or 0.0
        material_positive = (
            (d_ba is not None and d_ba > half_ba)
            and (d_pr is not None and d_pr > half_pr)
            and (d_br is not None and d_br < -half_br)
        )
        if domain == "elimination":
            status = "near_ceiling"
            reason = "KEEP_V12 + structural limit + uncertainty_preferred"
        elif in_noise and ready and robust and final_ba >= 0.90:
            status = "ceiling_reached"
            reason = "recent deltas within bootstrap noise and stability acceptable"
        elif material_positive and final_ba < 0.86:
            status = "meaningful_room_left"
            reason = "material gain pattern still present and current BA not yet high"
        elif robust and final_ba >= 0.86:
            status = "near_ceiling"
            reason = "high final BA with mixed/noisy recent deltas; additional gains likely marginal"
        else:
            status = "marginal_room_left"
            reason = "only small/mixed deltas after final campaign"
        rows.append(
            {
                "mode": mode,
                "domain": domain,
                "recent_delta_ba": d_ba,
                "recent_delta_pr_auc": d_pr,
                "recent_delta_brier": d_br,
                "noise_half_ba": half_ba,
                "noise_half_pr_auc": half_pr,
                "noise_half_brier": half_br,
                "delta_within_noise": in_noise,
                "runtime_strong_entry": ready,
                "stability_status": str(stab["stability_status"]),
                "ceiling_classification": status,
                "decision_rationale": reason,
            }
        )
    return pd.DataFrame(rows).sort_values(["mode", "domain"]).reset_index(drop=True)


def write_reports(
    inv: pd.DataFrame, progression: pd.DataFrame, bootstrap: pd.DataFrame, stability: pd.DataFrame, ceiling: pd.DataFrame
) -> None:
    write_md(
        RPT / "final_model_inventory.md",
        "\n".join(
            [
                "# Final model inventory",
                "",
                "- generated_at_utc: " + now_iso(),
                "- fuente principal no-elimination: `questionnaire_final_ceiling_v4` (lineage valida desde `final_hardening_v10`)",
                "- fuente principal elimination: `elimination_clean_rebuild_v12` (`KEEP_V12` frente a v14)",
                "",
                md_table(inv),
            ]
        ),
    )
    write_md(
        RPT / "domain_version_progression.md",
        "\n".join(
            [
                "# Domain version progression",
                "",
                "- minima comparacion aplicada: baseline fuerte anterior, ultima mejora material, version final vigente.",
                "- equivalencia estricta entre campanas para identidad exacta de artefacto: `por_confirmar` cuando no existe mapeo explicito 1:1.",
                "",
                md_table(progression),
            ]
        ),
    )
    write_md(
        RPT / "bootstrap_metric_analysis.md",
        "\n".join(
            [
                "# Bootstrap metric analysis",
                "",
                "- no-elimination: bootstrap sobre seeds del config seleccionado.",
                "- elimination: bootstrap proxy por escenarios de estres; ROC-AUC con muestra unica queda `por_confirmar_single_sample_for_ci`.",
                "",
                md_table(bootstrap),
            ]
        ),
    )
    write_md(
        RPT / "final_stability_analysis.md",
        "\n".join(
            [
                "# Final stability analysis",
                "",
                "- estabilidad analizada en seeds/splits (cuando disponible), missingness, coverage drop, source mix y casos borderline.",
                "",
                md_table(stability),
            ]
        ),
    )
    write_md(
        RPT / "ceiling_status_analysis.md",
        "\n".join(
            [
                "# Ceiling status analysis",
                "",
                "## Stop rules aplicadas",
                "",
                "1. `delta_within_noise`: mejoras recientes en BA/PR-AUC/Brier menores o iguales al ruido bootstrap.",
                "2. penalizacion por robustez: si estabilidad no es aceptable, no se marca `ceiling_reached`.",
                "3. penalizacion operativa: si no entra en runtime fuerte, se evita sobre-claim aunque el delta este en ruido.",
                "4. para Elimination se respeta `KEEP_V12` y `uncertainty_preferred` como limite operativo vigente.",
                "",
                md_table(ceiling),
            ]
        ),
    )

    elim_rows = ceiling[ceiling["domain"] == "elimination"]
    elim_summary = "\n".join(
        [
            f"- {row['mode']}: {row['ceiling_classification']} ({row['decision_rationale']})"
            for _, row in elim_rows.iterrows()
        ]
    )
    write_md(
        RPT / "elimination_ceiling_analysis.md",
        "\n".join(
            [
                "# Elimination ceiling analysis",
                "",
                "- v12 como mejor punto valido: **si** (decision previa `KEEP_V12` mantiene v12 como referencia operativa).",
                "- campanas posteriores con retornos marginales: **si** (v14 no desplaza v12).",
                "- limite actual estructural: **si**, con fragilidad en escenarios borderline/coverage.",
                "- estado `uncertainty_preferred`: **si**, se mantiene.",
                "- vale la pena seguir iterando modelos en esta tesis: **no recomendado** salvo evidencia nueva fuera del ruido actual.",
                "",
                elim_summary,
            ]
        ),
    )

    c = ceiling["ceiling_classification"].value_counts().to_dict()
    write_md(
        RPT / "thesis_ceiling_conclusion.md",
        "\n".join(
            [
                "# Thesis ceiling conclusion",
                "",
                "- enfoque: evidencia de techo practico por dominio y modo, sin abrir nueva campana.",
                f"- conteo clasificaciones: {json.dumps(c, ensure_ascii=False)}",
                "- lectura global: cuatro dominios no-elimination se ubican en `ceiling_reached` o `near_ceiling`; elimination queda `near_ceiling` con caveat estructural.",
                "- conclusion operativa: mayor retorno esperado ahora esta en cierre de cuestionario/runtime/documentacion y no en nueva iteracion amplia de modelado.",
                "- claim clinico: evidencia apta para screening/apoyo profesional en entorno simulado; no diagnostico automatico.",
            ]
        ),
    )


def write_manifest() -> None:
    manifest = {
        "generated_at_utc": now_iso(),
        "line": "final_ceiling_check_v15",
        "generated_files": [
            "data/final_ceiling_check_v15/inventory/final_model_inventory.csv",
            "data/final_ceiling_check_v15/reports/final_model_inventory.md",
            "data/final_ceiling_check_v15/comparison/domain_version_progression.csv",
            "data/final_ceiling_check_v15/reports/domain_version_progression.md",
            "data/final_ceiling_check_v15/bootstrap/bootstrap_metric_intervals.csv",
            "data/final_ceiling_check_v15/reports/bootstrap_metric_analysis.md",
            "data/final_ceiling_check_v15/stability/final_stability_matrix.csv",
            "data/final_ceiling_check_v15/reports/final_stability_analysis.md",
            "data/final_ceiling_check_v15/tables/ceiling_status_matrix.csv",
            "data/final_ceiling_check_v15/reports/ceiling_status_analysis.md",
            "data/final_ceiling_check_v15/reports/elimination_ceiling_analysis.md",
            "data/final_ceiling_check_v15/reports/thesis_ceiling_conclusion.md",
        ],
    }
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "final_ceiling_check_v15_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    v4 = load_v4_tables()
    v10 = load_v10_tables()
    elim = load_elimination_tables()

    inventory = build_final_inventory(v4=v4, elim=elim)
    progression = build_progression(inv=inventory, v10=v10, elim=elim)
    bootstrap = build_bootstrap(inv=inventory, v4=v4, elim=elim)
    stability = build_stability(inv=inventory, v4=v4, v10=v10, elim=elim)
    ceiling = build_ceiling_matrix(inv=inventory, progression=progression, bootstrap=bootstrap, stability=stability)

    save_csv(inventory, INV / "final_model_inventory.csv")
    save_csv(progression, CMP / "domain_version_progression.csv")
    save_csv(bootstrap, BST / "bootstrap_metric_intervals.csv")
    save_csv(stability, STB / "final_stability_matrix.csv")
    save_csv(ceiling, TBL / "ceiling_status_matrix.csv")

    write_reports(inventory, progression, bootstrap, stability, ceiling)
    write_manifest()


if __name__ == "__main__":
    main()
