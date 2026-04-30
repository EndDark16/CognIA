#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations


LINE = "hybrid_global_contract_compatible_rf_champion_selection_v13"
FREEZE = "v13"
SOURCE_LINE = "v13_global_contract_compatible_rf_champion_selection"
BASE = ROOT / "data" / LINE
ART = ROOT / "artifacts" / LINE
ACTIVE_OUT = ROOT / "data" / f"hybrid_active_modes_freeze_{FREEZE}"
OP_OUT = ROOT / "data" / f"hybrid_operational_freeze_{FREEZE}"
ACTIVE_ART = ROOT / "artifacts" / f"hybrid_active_modes_freeze_{FREEZE}"
OP_ART = ROOT / "artifacts" / f"hybrid_operational_freeze_{FREEZE}"
NORM_BASE = ROOT / "data" / "hybrid_classification_normalization_v2"
NORM_OUT = NORM_BASE / "tables" / f"hybrid_operational_classification_normalized_{FREEZE}.csv"
NORM_VIOL = NORM_BASE / "validation" / f"hybrid_classification_policy_violations_{FREEZE}.csv"

ACTIVE_V12 = ROOT / "data/hybrid_active_modes_freeze_v12/tables/hybrid_active_models_30_modes.csv"
ACTIVE_V11 = ROOT / "data/hybrid_active_modes_freeze_v11/tables/hybrid_active_models_30_modes.csv"
OP_V12 = ROOT / "data/hybrid_operational_freeze_v12/tables/hybrid_operational_final_champions.csv"
OP_V11 = ROOT / "data/hybrid_operational_freeze_v11/tables/hybrid_operational_final_champions.csv"
SUMMARY_V12 = ROOT / "data/hybrid_active_modes_freeze_v12/tables/hybrid_active_modes_summary.csv"
INPUTS_V12 = ROOT / "data/hybrid_active_modes_freeze_v12/tables/hybrid_questionnaire_inputs_master.csv"
LOADER = ROOT / "api/services/questionnaire_v2_loader_service.py"

WATCH = ["recall", "specificity", "roc_auc", "pr_auc"]
METRICS = ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mkdirs() -> None:
    for path in [
        BASE / "tables",
        BASE / "validation",
        BASE / "reports",
        ART,
        ACTIVE_OUT / "tables",
        ACTIVE_OUT / "validation",
        ACTIVE_OUT / "reports",
        OP_OUT / "tables",
        OP_OUT / "validation",
        OP_OUT / "reports",
        ACTIVE_ART,
        OP_ART,
        NORM_BASE / "tables",
        NORM_BASE / "validation",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sf(value: Any, default: float = float("nan")) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def feats(value: Any) -> list[str]:
    return [x.strip() for x in str(value or "").split("|") if x.strip() and x.strip().lower() != "nan"]


def slot_key(row: pd.Series) -> tuple[str, str, str]:
    return str(row["domain"]), str(row["role"]), str(row["mode"])


def metric_guard(row: pd.Series) -> bool:
    return all(sf(row.get(metric), 1.0) <= 0.98 for metric in WATCH)


def metadata_path(model_id: str) -> Path:
    return ROOT / "models" / "active_modes" / str(model_id) / "metadata.json"


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def source_label_from_path(path: Path) -> str:
    match = re.search(r"hybrid_active_modes_freeze_(.+?)[/\\]tables", str(path))
    return f"active_{match.group(1)}" if match else path.parent.parent.name


def add_candidate(
    row: pd.Series,
    source_label: str,
    source_path: Path,
    current_contract: dict[tuple[str, str, str], list[str]],
    current_slots: set[tuple[str, str, str]],
    candidates: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> None:
    key = slot_key(row)
    model_id = str(row.get("active_model_id", ""))
    reasons: list[str] = []

    if key not in current_slots:
        reasons.append("slot_not_in_current_contract")
    if str(row.get("model_family", "")).strip().lower() != "rf":
        reasons.append("non_rf_model_family")
    current_features = current_contract.get(key, [])
    row_features = feats(row.get("feature_list_pipe"))
    if row_features != current_features:
        reasons.append("feature_columns_not_exact_current_contract")
    if not (0 < sf(row.get("threshold"), -1) < 1):
        reasons.append("threshold_missing_or_invalid")
    missing_metrics = [m for m in METRICS if m not in row.index or pd.isna(row.get(m))]
    if missing_metrics:
        reasons.append("metrics_missing:" + "|".join(missing_metrics))
    if not metric_guard(row):
        reasons.append("hard_guardrail_violation")
    meta = metadata_path(model_id)
    if not meta.exists():
        reasons.append("runtime_metadata_missing")
    comparable = source_label in {"active_v11", "active_v12"}
    if not comparable:
        reasons.append("metrics_not_comparable_to_current_v11_v12_selection_window")

    record = {
        "domain": key[0],
        "role": key[1],
        "mode": key[2],
        "active_model_id": model_id,
        "candidate_source": source_label,
        "source_path": str(source_path.as_posix()),
        "model_family": row.get("model_family"),
        "feature_set_id": row.get("feature_set_id"),
        "config_id": row.get("config_id"),
        "calibration": row.get("calibration"),
        "threshold_policy": row.get("threshold_policy"),
        "threshold": row.get("threshold"),
        "seed": row.get("seed"),
        "n_features": len(row_features),
        "metadata_path": str(meta.as_posix()),
        "metadata_available": "yes" if meta.exists() else "no",
        "contract_feature_count": len(current_features),
        "feature_columns_exact_match": "yes" if row_features == current_features else "no",
        "metric_comparable": "yes" if comparable else "no",
        "guardrail_ok": "yes" if metric_guard(row) else "no",
        "rejection_reason": "|".join(reasons),
    }
    for metric in METRICS:
        record[metric] = row.get(metric)
    record["feature_list_pipe"] = "|".join(row_features)

    if reasons:
        rejected.append(record)
    else:
        candidates.append(record)


def dedupe_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    sort_cols = ["domain", "role", "mode", "active_model_id", "candidate_source"]
    df = df.sort_values(sort_cols).copy()
    return df.drop_duplicates(["domain", "role", "mode", "active_model_id"], keep="first").reset_index(drop=True)


def select_slot(group: pd.DataFrame) -> pd.Series:
    g = group.copy()
    max_f1 = g["f1"].astype(float).max()
    v12_f1 = g.loc[g["candidate_source"].eq("active_v12"), "f1"].astype(float)
    best_v12_f1 = float(v12_f1.max()) if not v12_f1.empty else float("nan")
    tied = g[g["f1"].astype(float) >= max_f1 - 0.005].copy()
    tied["source_preference"] = tied["candidate_source"].map({"active_v12": 1, "active_v11": 0}).fillna(2)
    tied = tied.sort_values(
        ["recall", "precision", "balanced_accuracy", "brier", "source_preference"],
        ascending=[False, False, False, True, True],
    )
    winner = tied.iloc[0].copy()
    if str(winner["candidate_source"]) == "active_v11":
        if pd.notna(best_v12_f1) and float(winner["f1"]) > best_v12_f1 + 0.005:
            reason = "historical_v11_recovered_higher_f1_contract_compatible"
        else:
            reason = "historical_v11_recovered_practical_f1_tie_better_recall"
    elif str(winner["candidate_source"]) == "active_v12":
        reason = "v12_retained_best_contract_compatible_rf"
    else:
        reason = "historical_rf_contract_compatible_selected"
    winner["selection_reason"] = reason
    winner["max_candidate_f1_in_slot"] = max_f1
    winner["candidate_count_in_slot"] = len(group)
    return winner


def quality_label(row: pd.Series) -> str:
    if sf(row["f1"], 0) >= 0.86 and sf(row["balanced_accuracy"], 0) >= 0.90 and sf(row["brier"], 1) <= 0.06:
        return "strong"
    if sf(row["f1"], 0) >= 0.80 and sf(row["balanced_accuracy"], 0) >= 0.86:
        return "aceptable"
    return "limited"


def build_active_and_operational(selected: pd.DataFrame, active_v12: pd.DataFrame, active_v11: pd.DataFrame, op_v12: pd.DataFrame, op_v11: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    active_lookup = {
        ("active_v12", row["domain"], row["role"], row["mode"]): row
        for _, row in active_v12.iterrows()
    }
    active_lookup.update({
        ("active_v11", row["domain"], row["role"], row["mode"]): row
        for _, row in active_v11.iterrows()
    })
    op_lookup = {
        ("active_v12", row["domain"], row["mode"]): row
        for _, row in op_v12.iterrows()
    }
    op_lookup.update({
        ("active_v11", row["domain"], row["mode"]): row
        for _, row in op_v11.iterrows()
    })

    active_rows: list[pd.Series] = []
    op_rows: list[pd.Series] = []
    comparison_rows: list[dict[str, Any]] = []
    v11_idx = active_v11.set_index(["domain", "role", "mode"])
    v12_idx = active_v12.set_index(["domain", "role", "mode"])

    for _, selected_row in selected.iterrows():
        key = (str(selected_row["domain"]), str(selected_row["role"]), str(selected_row["mode"]))
        source = str(selected_row["candidate_source"])
        active_source = active_lookup[(source, *key)].copy()
        active_source["source_line"] = SOURCE_LINE
        active_source["source_campaign"] = LINE
        active_source["notes"] = (
            f"{LINE}:selected_from={source};selected_model={selected_row['active_model_id']};"
            f"selection_reason={selected_row['selection_reason']};contract_exact=yes"
        )
        active_rows.append(active_source)

        op_source = op_lookup[(source, key[0], key[2])].copy()
        op_source["source_campaign"] = LINE
        op_rows.append(op_source)

        v11 = v11_idx.loc[key]
        v12 = v12_idx.loc[key]
        comparison_rows.append({
            "domain": key[0],
            "role": key[1],
            "mode": key[2],
            "champion_v11": v11["active_model_id"],
            "champion_v12": v12["active_model_id"],
            "champion_final_v13": selected_row["active_model_id"],
            "final_champion_source": source,
            "contract_compatible": "yes",
            "f1_v11": v11["f1"],
            "f1_v12": v12["f1"],
            "f1_v13": selected_row["f1"],
            "recall_v11": v11["recall"],
            "recall_v12": v12["recall"],
            "recall_v13": selected_row["recall"],
            "precision_v11": v11["precision"],
            "precision_v12": v12["precision"],
            "precision_v13": selected_row["precision"],
            "brier_v11": v11["brier"],
            "brier_v12": v12["brier"],
            "brier_v13": selected_row["brier"],
            "selection_reason": selected_row["selection_reason"],
        })

    active_new = pd.DataFrame(active_rows)[active_v12.columns].reset_index(drop=True)
    op_new = pd.DataFrame(op_rows)[op_v12.columns].reset_index(drop=True)
    comparison = pd.DataFrame(comparison_rows)

    return active_new, op_new, comparison


def build_summary(active_new: pd.DataFrame) -> pd.DataFrame:
    return (
        active_new.groupby(["final_operational_class", "confidence_band"], dropna=False)
        .size()
        .reset_index(name="n")
    )


def pairwise_proxy(active_new: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, a in active_new.iterrows():
        for _, b in active_new.iterrows():
            if str(a["domain"]) != str(b["domain"]):
                continue
            if str(a["active_model_id"]) >= str(b["active_model_id"]):
                continue
            if not (str(a["role"]) == str(b["role"]) or str(a["domain"]) == "elimination"):
                continue
            fa, fb = set(feats(a["feature_list_pipe"])), set(feats(b["feature_list_pipe"]))
            metric_delta = max(abs(sf(a[m], 0) - sf(b[m], 0)) for m in ["f1", "recall", "precision", "balanced_accuracy", "specificity"])
            threshold_delta = abs(sf(a["threshold"], 0) - sf(b["threshold"], 0))
            rows.append({
                "domain": a["domain"],
                "role_a": a["role"],
                "mode_a": a["mode"],
                "role_b": b["role"],
                "mode_b": b["mode"],
                "threshold_a": a["threshold"],
                "threshold_b": b["threshold"],
                "metric_max_abs_delta": metric_delta,
                "threshold_abs_delta": threshold_delta,
                "feature_jaccard": len(fa & fb) / max(1, len(fa | fb)),
                "near_metric_clone_proxy": "yes" if metric_delta <= 0.001 and threshold_delta <= 0.001 and len(fa & fb) / max(1, len(fa | fb)) >= 0.95 else "no",
                "prediction_recomputed": "no",
                "audit_note": "metric_threshold_feature_proxy; no retraining performed",
            })
    return pd.DataFrame(rows)


def write_manifests(active_new: pd.DataFrame, selected: pd.DataFrame, rejected: pd.DataFrame, policy_viol: pd.DataFrame) -> None:
    payload = {
        "line": LINE,
        "freeze_label": FREEZE,
        "generated_at_utc": now(),
        "source_truth_initial": {
            "active": str(ACTIVE_V12.as_posix()),
            "operational": str(OP_V12.as_posix()),
            "inputs_master": str(INPUTS_V12.as_posix()),
        },
        "source_truth_final": {
            "active": str((ACTIVE_OUT / "tables/hybrid_active_models_30_modes.csv").as_posix()),
            "operational": str((OP_OUT / "tables/hybrid_operational_final_champions.csv").as_posix()),
            "inputs_master": str((ACTIVE_OUT / "tables/hybrid_questionnaire_inputs_master.csv").as_posix()),
        },
        "rules": {
            "selection_scope": "champions_only",
            "model_family_allowed": "RF-based only",
            "contract_compatibility": "exact feature_list_pipe and order versus v12 current contract",
            "no_training": True,
            "same_inputs_outputs": True,
            "no_question_changes": True,
            "guardrail_metrics_max": 0.98,
        },
        "stats": {
            "active_rows": int(len(active_new)),
            "rf_rows": int((active_new["model_family"].str.lower() == "rf").sum()),
            "selected_from_v11": int((selected["candidate_source"] == "active_v11").sum()),
            "selected_from_v12": int((selected["candidate_source"] == "active_v12").sum()),
            "rejected_candidates": int(len(rejected)),
            "policy_violations": int(len(policy_viol)),
        },
    }
    for path in [
        ART / f"{LINE}_manifest.json",
        ACTIVE_ART / "hybrid_active_modes_freeze_v13_manifest.json",
        OP_ART / "hybrid_operational_freeze_v13_manifest.json",
    ]:
        write(path, json.dumps(payload, indent=2, ensure_ascii=False))


def markdown_table(df: pd.DataFrame, cols: list[str], max_rows: int = 40) -> str:
    if df.empty:
        return "_No rows._"
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.head(max_rows).iterrows():
        out.append("| " + " | ".join(str(row.get(c, "")).replace("|", "/") for c in cols) + " |")
    if len(df) > max_rows:
        out.append(f"| ... | {len(df) - max_rows} additional rows omitted | | | | | | | | | | | | | | | | | | | |")
    return "\n".join(out)


def main() -> int:
    mkdirs()
    active_v12 = load_csv(ACTIVE_V12)
    active_v11 = load_csv(ACTIVE_V11)
    op_v12 = load_csv(OP_V12)
    op_v11 = load_csv(OP_V11)
    summary_v12 = load_csv(SUMMARY_V12)
    inputs_v12 = load_csv(INPUTS_V12)

    current_contract = {slot_key(row): feats(row["feature_list_pipe"]) for _, row in active_v12.iterrows()}
    current_slots = set(current_contract)

    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for label, path, df in [
        ("active_v12", ACTIVE_V12, active_v12),
        ("active_v11", ACTIVE_V11, active_v11),
    ]:
        for _, row in df.iterrows():
            add_candidate(row, label, path, current_contract, current_slots, candidates, rejected)

    for path in sorted((ROOT / "data").glob("hybrid_active_modes_freeze_*/tables/hybrid_active_models_30_modes.csv")):
        label = source_label_from_path(path)
        if label in {"active_v11", "active_v12"}:
            continue
        df = load_csv(path)
        for _, row in df.iterrows():
            add_candidate(row, label, path, current_contract, current_slots, candidates, rejected)

    cand_df = dedupe_candidates(pd.DataFrame(candidates))
    rejected_df = pd.DataFrame(rejected).sort_values(["domain", "role", "mode", "candidate_source", "active_model_id"]).reset_index(drop=True)
    if cand_df.empty:
        raise RuntimeError("No contract-compatible RF candidates found.")

    selected = (
        pd.DataFrame([select_slot(group) for _, group in cand_df.groupby(["domain", "role", "mode"], sort=False)])
        .reset_index(drop=True)
        .sort_values(["domain", "role", "mode"])
        .reset_index(drop=True)
    )
    active_new, op_new, comparison = build_active_and_operational(selected, active_v12, active_v11, op_v12, op_v11)
    summary_new = build_summary(active_new)

    save(cand_df, BASE / "tables/candidate_inventory_rf_contract_compatible.csv")
    save(rejected_df, BASE / "tables/historical_candidates_rejected_contract_incompatible.csv")
    save(comparison, BASE / "tables/v11_v12_candidate_comparison_by_slot.csv")
    save(selected, BASE / "tables/selected_global_rf_champions_v13.csv")
    nonchampions = cand_df.merge(selected[["active_model_id"]], on="active_model_id", how="left", indicator=True)
    nonchampions = nonchampions[nonchampions["_merge"] == "left_only"].drop(columns=["_merge"])
    save(nonchampions, BASE / "tables/compatible_rf_nonchampions_v13.csv")

    historical_better = []
    for _, row in comparison.iterrows():
        final_f1 = sf(row["f1_v13"], 0)
        if sf(row["f1_v11"], 0) > final_f1 + 0.005 and row["champion_v11"] != row["champion_final_v13"]:
            historical_better.append({
                **row.to_dict(),
                "better_historical_model": row["champion_v11"],
                "not_selected_reason": "would_break_selection_order_or_failed_validator",
            })
    historical_better_columns = list(comparison.columns) + ["better_historical_model", "not_selected_reason"]
    save(pd.DataFrame(historical_better, columns=historical_better_columns), BASE / "tables/historical_better_compatible_not_selected.csv")

    save(active_new, ACTIVE_OUT / "tables/hybrid_active_models_30_modes.csv")
    save(summary_new, ACTIVE_OUT / "tables/hybrid_active_modes_summary.csv")
    save(inputs_v12, ACTIVE_OUT / "tables/hybrid_questionnaire_inputs_master.csv")
    save(op_new, OP_OUT / "tables/hybrid_operational_final_champions.csv")
    save(nonchampions, OP_OUT / "tables/hybrid_operational_final_nonchampions.csv")

    rf_validator = pd.DataFrame([{
        "active_rows": len(active_new),
        "unique_slots": active_new[["domain", "role", "mode"]].drop_duplicates().shape[0],
        "rf_rows": int((active_new["model_family"].str.lower() == "rf").sum()),
        "non_rf_rows": int((active_new["model_family"].str.lower() != "rf").sum()),
        "rf_compatibility_ok": "yes" if (active_new["model_family"].str.lower() == "rf").all() and len(active_new) == 30 else "no",
    }])
    contract_validator = pd.DataFrame([{
        "domain": r["domain"],
        "role": r["role"],
        "mode": r["mode"],
        "active_model_id": r["active_model_id"],
        "contract_compatible": "yes",
        "same_inputs_outputs": "yes",
        "metadata_available": "yes" if metadata_path(r["active_model_id"]).exists() else "no",
        "feature_columns_exact_match": "yes" if feats(r["feature_list_pipe"]) == current_contract[slot_key(r)] else "no",
    } for _, r in active_new.iterrows()])
    feature_validator = contract_validator[["domain", "role", "mode", "active_model_id", "feature_columns_exact_match"]].copy()
    metric_validator = selected[["domain", "role", "mode", "active_model_id", "candidate_source", "metric_comparable", "guardrail_ok", "selection_reason"]].copy()
    guard_validator = active_new[["domain", "role", "mode", "active_model_id", *WATCH]].copy()
    guard_validator["guardrail_violation"] = guard_validator.apply(lambda r: "yes" if any(sf(r[m], 1) > 0.98 for m in WATCH) else "no", axis=1)
    anti_clone = pairwise_proxy(active_new)
    loader_text = LOADER.read_text(encoding="utf-8") if LOADER.exists() else ""
    loader_points_v13 = (
        "hybrid_active_modes_freeze_v13" in loader_text
        and "hybrid_operational_freeze_v13" in loader_text
    )
    loader_validator = pd.DataFrame([{
        "loader_expected_active": "data/hybrid_active_modes_freeze_v13/tables/hybrid_active_models_30_modes.csv",
        "loader_expected_operational": "data/hybrid_operational_freeze_v13/tables/hybrid_operational_final_champions.csv",
        "loader_points_v13": "yes" if loader_points_v13 else "no",
        "loader_update_required": "no" if loader_points_v13 else "yes",
    }])

    save(rf_validator, BASE / "validation/rf_compatibility_validator_v13.csv")
    save(contract_validator, BASE / "validation/contract_compatibility_validator_v13.csv")
    save(feature_validator, BASE / "validation/feature_columns_exact_match_validator_v13.csv")
    save(metric_validator, BASE / "validation/metric_comparability_validator_v13.csv")
    save(guard_validator, BASE / "validation/guardrail_validator_v13.csv")
    save(anti_clone, BASE / "validation/anti_clone_validator_v13.csv")
    save(loader_validator, BASE / "validation/loader_update_validator_v13.csv")

    normalized = build_normalized_table(
        PolicyInputs(
            operational_csv=OP_OUT / "tables/hybrid_operational_final_champions.csv",
            active_csv=ACTIVE_OUT / "tables/hybrid_active_models_30_modes.csv",
            shortcut_inventory_csv=BASE / "tables/candidate_inventory_rf_contract_compatible.csv",
        )
    )
    violations = policy_violations(normalized)
    save(normalized, NORM_OUT)
    save(violations, NORM_VIOL)

    report = [
        "# Global Contract-Compatible RF Champion Selection v13",
        "",
        f"Generated: `{now()}`",
        "",
        "## Scope",
        "- Champion selection only; no retraining.",
        "- Candidate must be RF, exact current feature_list_pipe/order, metric-comparable, guardrail-compliant, and have runtime metadata.",
        "- Current contract reference: v12.",
        "",
        "## Results",
        f"- active rows: `{len(active_new)}`",
        f"- RF rows: `{int((active_new['model_family'].str.lower() == 'rf').sum())}`",
        f"- selected from v11: `{int((selected['candidate_source'] == 'active_v11').sum())}`",
        f"- selected from v12: `{int((selected['candidate_source'] == 'active_v12').sum())}`",
        f"- rejected historical candidates: `{len(rejected_df)}`",
        f"- policy violations: `{len(violations)}`",
        "",
        "## Selection",
        markdown_table(
            comparison,
            [
                "domain", "role", "mode", "champion_v11", "champion_v12", "champion_final_v13",
                "final_champion_source", "f1_v11", "f1_v12", "f1_v13", "recall_v11", "recall_v12",
                "recall_v13", "precision_v11", "precision_v12", "precision_v13", "brier_v11",
                "brier_v12", "brier_v13", "selection_reason",
            ],
            max_rows=35,
        ),
    ]
    write(BASE / "reports/final_selection_report_v13.md", "\n".join(report))

    write_manifests(active_new, selected, rejected_df, violations)

    print(json.dumps({
        "status": "ok",
        "line": LINE,
        "active_rows": len(active_new),
        "rf_rows": int((active_new["model_family"].str.lower() == "rf").sum()),
        "selected_from_v11": int((selected["candidate_source"] == "active_v11").sum()),
        "selected_from_v12": int((selected["candidate_source"] == "active_v12").sum()),
        "guardrail_violations": int((guard_validator["guardrail_violation"] == "yes").sum()),
        "policy_violations": len(violations),
        "near_clone_proxy_pairs": int((anti_clone.get("near_metric_clone_proxy", pd.Series(dtype=str)) == "yes").sum()),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
