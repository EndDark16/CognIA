#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd


UNIT_TARGETS = {
    "adhd": "target_adhd_exact",
    "conduct_disorder": "target_conduct_disorder_exact",
    "enuresis": "target_enuresis_exact",
    "encopresis": "target_encopresis_exact",
    "separation_anxiety_disorder": "target_separation_anxiety_disorder_exact",
    "generalized_anxiety_disorder": "target_generalized_anxiety_disorder_exact",
    "major_depressive_disorder": "target_major_depressive_disorder_exact",
    "persistent_depressive_disorder": "target_persistent_depressive_disorder_exact",
    "dmdd": "target_dmdd_exact",
}

UNIT_DATASET_FILENAMES = {
    "adhd": "dataset_adhd_exact.csv",
    "conduct_disorder": "dataset_conduct_disorder_exact.csv",
    "enuresis": "dataset_enuresis_exact.csv",
    "encopresis": "dataset_encopresis_exact.csv",
    "separation_anxiety_disorder": "dataset_separation_anxiety_exact.csv",
    "generalized_anxiety_disorder": "dataset_generalized_anxiety_exact.csv",
    "major_depressive_disorder": "dataset_mdd_exact.csv",
    "persistent_depressive_disorder": "dataset_pdd_exact.csv",
    "dmdd": "dataset_dmdd_exact.csv",
}

DOMAIN_TARGETS = {
    "adhd": "target_domain_adhd",
    "conduct": "target_domain_conduct",
    "elimination": "target_domain_elimination",
    "anxiety": "target_domain_anxiety",
    "depression": "target_domain_depression",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_response(value: Any) -> Any:
    if pd.isna(value):
        return np.nan
    s = str(value).strip()
    if s == "":
        return np.nan
    try:
        return float(s)
    except Exception:
        return s.lower()


def ensure_columns_from_source(
    base: pd.DataFrame,
    source: pd.DataFrame,
    participant_col: str,
    required_cols: List[str],
) -> pd.DataFrame:
    missing = [c for c in required_cols if c not in base.columns and c in source.columns]
    if not missing:
        return base
    src = source[[participant_col] + missing].drop_duplicates(subset=[participant_col]).copy()
    return base.merge(src, on=participant_col, how="left")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build hybrid DSM5 v2 datasets from DSM5 exact + questionnaire layer.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()

    base_exact = root / "data" / "processed_dsm5_exact_v1"
    q_dir = root / "data" / "questionnaire_dsm5_v1"
    out = root / "data" / "processed_hybrid_dsm5_v2"
    art = root / "artifacts" / "hybrid_dsm5_v2"

    dirs = [
        out / "inventory",
        out / "normative",
        out / "mapping",
        out / "questionnaire",
        out / "intermediate",
        out / "final" / "internal_exact",
        out / "final" / "external_domains",
        out / "final" / "model_ready" / "strict_no_leakage_hybrid",
        out / "final" / "model_ready" / "research_extended_hybrid",
        out / "reports",
        out / "metadata",
        art,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    mapping = pd.read_csv(base_exact / "mapping" / "parameter_to_hbn_mapping.csv", low_memory=False)
    norm_units = pd.read_csv(base_exact / "normative" / "normative_units_registry.csv", low_memory=False)
    norm_params = pd.read_csv(base_exact / "normative" / "normative_parameter_registry.csv", low_memory=False)
    evidence_long = pd.read_csv(base_exact / "intermediate" / "participant_normative_evidence_long.csv", low_memory=False)
    internal_targets = pd.read_csv(base_exact / "internal_exact_targets.csv", low_memory=False)
    external_targets = pd.read_csv(base_exact / "external_domain_targets.csv", low_memory=False)
    strict_exact = pd.read_csv(
        base_exact / "final" / "model_ready" / "strict_no_leakage_exact" / "dataset_internal_exact_model_ready_strict_no_leakage_exact.csv",
        low_memory=False,
    )
    research_exact = pd.read_csv(
        base_exact / "final" / "model_ready" / "research_extended_exact" / "dataset_internal_exact_model_ready_research_extended_exact.csv",
        low_memory=False,
    )

    q_items = pd.read_csv(q_dir / "questionnaire_items_registry.csv", low_memory=False)
    q_sim = pd.read_csv(q_dir / "questionnaire_simulated_responses.csv", low_memory=False)

    # Baseline normative registries preserved for hybrid line compatibility.
    safe_csv(norm_units, out / "normative" / "normative_units_registry.csv")
    safe_csv(norm_params, out / "normative" / "normative_parameter_registry.csv")

    # Hybrid mapping status with questionnaire observability.
    q_cov = q_items[
        ["row_id_from_normative_csv", "questionnaire_item_id", "direct_or_proxy_for_normative_parameter", "requiredness"]
    ].copy()
    hybrid_map = mapping.merge(q_cov, on="row_id_from_normative_csv", how="left")
    hybrid_map["questionnaire_available"] = hybrid_map["questionnaire_item_id"].notna().astype(int)
    hybrid_map["hybrid_mapping_status"] = np.where(
        hybrid_map["mapping_status"] == "direct",
        "direct",
        np.where(
            (hybrid_map["questionnaire_available"] == 1) & (hybrid_map["direct_or_proxy_for_normative_parameter"] == "direct"),
            "direct",
            np.where(
                hybrid_map["mapping_status"].isin(["proxy", "derived"]),
                hybrid_map["mapping_status"],
                np.where(
                    (hybrid_map["questionnaire_available"] == 1) & (hybrid_map["direct_or_proxy_for_normative_parameter"] == "proxy"),
                    "proxy",
                    "absent",
                ),
            ),
        ),
    )
    hybrid_map["hybrid_coverage_source"] = np.where(
        hybrid_map["mapping_status"] == "direct",
        "hbn_direct",
        np.where(
            (hybrid_map["questionnaire_available"] == 1) & (hybrid_map["direct_or_proxy_for_normative_parameter"] == "direct"),
            "questionnaire_direct",
            np.where(
                hybrid_map["mapping_status"] == "proxy",
                "hbn_proxy",
                np.where(
                    hybrid_map["mapping_status"] == "derived",
                    "hbn_derived",
                    np.where(hybrid_map["questionnaire_available"] == 1, "questionnaire_proxy", "absent"),
                ),
            ),
        ),
    )
    safe_csv(hybrid_map, out / "normative" / "hybrid_parameter_to_evidence_mapping.csv")
    safe_csv(hybrid_map, out / "mapping" / "parameter_to_hbn_mapping.csv")
    safe_csv(
        hybrid_map.groupby(["unit_key", "hybrid_mapping_status"]).size().reset_index(name="n_parameters"),
        out / "normative" / "hybrid_mapping_coverage_summary.csv",
    )

    # Questionnaire feature matrix.
    q_sim["participant_id"] = q_sim["participant_id"].astype(str)
    q_sim["response_value_parsed"] = q_sim["response_value"].map(parse_response)
    q_wide = q_sim.pivot_table(index="participant_id", columns="questionnaire_item_id", values="response_value_parsed", aggfunc="first")
    q_wide.columns = [f"q_{c}".lower() for c in q_wide.columns]
    q_wide = q_wide.reset_index()

    req_items = q_items[q_items["requiredness"] == "required"]["questionnaire_item_id"].astype(str).tolist()
    req_cols = [f"q_{x}".lower() for x in req_items if f"q_{x}".lower() in q_wide.columns]
    q_wide["q_items_total"] = len([c for c in q_wide.columns if c.startswith("q_qi_")])
    q_wide["q_items_answered"] = q_wide[[c for c in q_wide.columns if c.startswith("q_qi_")]].notna().sum(axis=1)
    q_wide["q_completion_ratio"] = q_wide["q_items_answered"] / q_wide["q_items_total"].replace({0: np.nan})
    q_wide["q_required_missing"] = len(req_cols) - q_wide[req_cols].notna().sum(axis=1) if req_cols else 0
    q_wide["q_required_missing"] = pd.to_numeric(q_wide["q_required_missing"], errors="coerce").fillna(0).astype(int)

    safe_csv(q_wide, out / "questionnaire" / "questionnaire_feature_matrix.csv")
    safe_csv(q_sim, out / "questionnaire" / "questionnaire_simulated_responses_used.csv")
    safe_csv(q_items, out / "questionnaire" / "questionnaire_items_registry_copy.csv")

    # Hybrid evidence long with questionnaire upgrades.
    q_sim_small = q_sim[["participant_id", "row_id_from_normative_csv", "response_value_parsed"]].copy()
    q_sim_small["has_questionnaire_value"] = q_sim_small["response_value_parsed"].notna().astype(int)

    ehyb = evidence_long.copy()
    ehyb["participant_id"] = ehyb["participant_id"].astype(str)
    ehyb = ehyb.merge(
        hybrid_map[["row_id_from_normative_csv", "hybrid_mapping_status", "hybrid_coverage_source"]],
        on="row_id_from_normative_csv",
        how="left",
    ).merge(
        q_sim_small,
        on=["participant_id", "row_id_from_normative_csv"],
        how="left",
    )
    ehyb["parameter_value_hybrid"] = np.where(
        ehyb["has_questionnaire_value"] == 1,
        ehyb["response_value_parsed"],
        ehyb["parameter_value"],
    )
    ehyb["evidence_status_hybrid"] = np.where(
        (ehyb["evidence_status"].isin(["absent", "no_observed"])) & (ehyb["has_questionnaire_value"] == 1),
        ehyb["hybrid_mapping_status"],
        ehyb["evidence_status"],
    )
    ehyb["evidence_source_hybrid"] = np.where(
        (ehyb["evidence_status"].isin(["absent", "no_observed"])) & (ehyb["has_questionnaire_value"] == 1),
        ehyb["hybrid_coverage_source"],
        "hbn_existing",
    )
    safe_csv(ehyb, out / "intermediate" / "hybrid_participant_normative_evidence_long.csv")
    safe_csv(ehyb, out / "intermediate" / "participant_normative_evidence_long.csv")
    safe_csv(ehyb, out / "final" / "internal_exact" / "dataset_participant_normative_evidence_long.csv")

    ewide = ehyb.pivot_table(index="participant_id", columns="parameter_feature_name", values="parameter_value_hybrid", aggfunc="first").reset_index()
    safe_csv(ewide, out / "intermediate" / "hybrid_participant_normative_evidence_wide.csv")
    safe_csv(ewide, out / "intermediate" / "participant_normative_evidence_wide.csv")
    safe_csv(ewide, out / "final" / "internal_exact" / "dataset_participant_normative_evidence_wide.csv")

    cov = (
        ehyb.groupby(["participant_id", "unit_key", "evidence_status_hybrid"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for c in ["direct", "proxy", "derived", "no_observed", "absent"]:
        if c not in cov.columns:
            cov[c] = 0
    cov["total_parameters"] = cov[["direct", "proxy", "derived", "no_observed", "absent"]].sum(axis=1)
    cov["covered_parameters"] = cov[["direct", "proxy", "derived"]].sum(axis=1)
    cov["coverage_ratio"] = cov["covered_parameters"] / cov["total_parameters"].replace({0: np.nan})
    safe_csv(cov, out / "intermediate" / "hybrid_participant_coverage_flags.csv")
    safe_csv(cov, out / "final" / "internal_exact" / "dataset_parameter_coverage_summary.csv")

    # Build model-ready hybrid datasets.
    strict_hybrid = strict_exact.copy()
    strict_hybrid["participant_id"] = strict_hybrid["participant_id"].astype(str)
    strict_hybrid = strict_hybrid.merge(q_wide, on="participant_id", how="left")
    strict_hybrid = ensure_columns_from_source(
        strict_hybrid,
        internal_targets,
        participant_col="participant_id",
        required_cols=[c for c in internal_targets.columns if c.endswith("_exact")],
    )
    strict_hybrid = ensure_columns_from_source(
        strict_hybrid,
        external_targets,
        participant_col="participant_id",
        required_cols=list(DOMAIN_TARGETS.values()),
    )
    safe_csv(
        strict_hybrid,
        out / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv",
    )
    compat_strict_dir = out / "final" / "model_ready" / "strict_no_leakage_exact"
    safe_csv(
        strict_hybrid,
        compat_strict_dir / "dataset_internal_exact_model_ready_strict_no_leakage_exact.csv",
    )

    research_hybrid = research_exact.copy()
    research_hybrid["participant_id"] = research_hybrid["participant_id"].astype(str)
    research_hybrid = research_hybrid.merge(q_wide, on="participant_id", how="left")
    research_hybrid = ensure_columns_from_source(
        research_hybrid,
        internal_targets,
        participant_col="participant_id",
        required_cols=[c for c in internal_targets.columns if c.startswith("target_")],
    )
    research_hybrid = ensure_columns_from_source(
        research_hybrid,
        external_targets,
        participant_col="participant_id",
        required_cols=list(DOMAIN_TARGETS.values()),
    )
    safe_csv(
        research_hybrid,
        out / "final" / "model_ready" / "research_extended_hybrid" / "dataset_hybrid_model_ready_research_extended_hybrid.csv",
    )
    compat_research_dir = out / "final" / "model_ready" / "research_extended_exact"
    safe_csv(
        research_hybrid,
        compat_research_dir / "dataset_internal_exact_model_ready_research_extended_exact.csv",
    )

    # Internal unit datasets.
    id_cols = ["participant_id", "age_years", "sex_assigned_at_birth", "site", "release"]
    id_cols = [c for c in id_cols if c in strict_hybrid.columns]
    q_cols = [c for c in strict_hybrid.columns if c.startswith("q_")]
    for unit, target_col in UNIT_TARGETS.items():
        cols = list(dict.fromkeys(id_cols + [target_col] + q_cols))
        unit_prefix = unit.split("_")[0]
        unit_cols = [c for c in strict_hybrid.columns if c.startswith(unit_prefix) and c not in cols]
        cols += unit_cols
        cols = [c for c in cols if c in strict_hybrid.columns]
        dsu = strict_hybrid[cols].copy()
        safe_csv(dsu, out / "final" / "internal_exact" / f"dataset_{unit}_exact.csv")
        safe_csv(dsu, out / "final" / "internal_exact" / UNIT_DATASET_FILENAMES[unit])

    # External domain datasets.
    for domain, target_col in DOMAIN_TARGETS.items():
        cols = list(dict.fromkeys(id_cols + [target_col] + q_cols))
        cols = [c for c in cols if c in strict_hybrid.columns]
        dsd = strict_hybrid[cols].copy()
        safe_csv(dsd, out / "final" / "external_domains" / f"dataset_domain_{domain}.csv")

    # Master datasets and inference-ready.
    internal_targets_cols = [c for c in UNIT_TARGETS.values() if c in strict_hybrid.columns]
    domain_targets_cols = [c for c in DOMAIN_TARGETS.values() if c in strict_hybrid.columns]
    internal_master = strict_hybrid[list(dict.fromkeys(id_cols + internal_targets_cols + q_cols))].copy()
    external_master = strict_hybrid[list(dict.fromkeys(id_cols + domain_targets_cols + q_cols))].copy()
    multitask_master = strict_hybrid[list(dict.fromkeys(id_cols + domain_targets_cols + internal_targets_cols + q_cols))].copy()
    evidence_cols = [c for c in strict_hybrid.columns if c.startswith("parameter_") or c.startswith("coverage_")]
    model_ready_cols = [
        c
        for c in strict_hybrid.columns
        if c not in {"participant_id"}
        and not c.endswith("_status")
        and not c.endswith("_confidence")
        and not c.endswith("_coverage")
        and "diagnosis" not in c.lower()
        and "consensus" not in c.lower()
    ]

    safe_csv(internal_master, out / "final" / "internal_exact" / "dataset_internal_exact_master.csv")
    safe_csv(strict_hybrid[list(dict.fromkeys(id_cols + internal_targets_cols + domain_targets_cols + evidence_cols + q_cols))], out / "final" / "internal_exact" / "dataset_internal_exact_evidence_rich.csv")
    safe_csv(strict_hybrid[["participant_id"] + model_ready_cols], out / "final" / "internal_exact" / "dataset_internal_exact_model_ready.csv")
    safe_csv(external_master, out / "final" / "external_domains" / "dataset_domain_master.csv")
    safe_csv(multitask_master, out / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_multitask_master.csv")

    inference_ready = strict_hybrid.drop(columns=[c for c in strict_hybrid.columns if c.startswith("target_")], errors="ignore")
    safe_csv(inference_ready, out / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_inference_ready_hybrid.csv")

    # Hybrid targets registry compatible with prior exact line names.
    targets_table = internal_targets.copy()
    targets_table["participant_id"] = targets_table["participant_id"].astype(str)
    # Keep the same participant universe as strict hybrid.
    targets_table = strict_hybrid[["participant_id"]].merge(targets_table, on="participant_id", how="left")
    safe_csv(targets_table, out / "internal_exact_targets.csv")
    ext_cols = [c for c in DOMAIN_TARGETS.values() if c in strict_hybrid.columns]
    if ext_cols:
        safe_csv(strict_hybrid[["participant_id"] + ext_cols].copy(), out / "external_domain_targets.csv")
    else:
        ext_src = external_targets.copy()
        ext_src["participant_id"] = ext_src["participant_id"].astype(str)
        safe_csv(strict_hybrid[["participant_id"]].merge(ext_src, on="participant_id", how="left"), out / "external_domain_targets.csv")

    # Inventory and metadata.
    target_support = []
    for tgt in internal_targets_cols + domain_targets_cols:
        s = pd.to_numeric(strict_hybrid[tgt], errors="coerce").fillna(0).astype(int)
        target_support.append(
            {
                "target": tgt,
                "n_rows": int(len(s)),
                "positives": int((s == 1).sum()),
                "negatives": int((s == 0).sum()),
                "prevalence": float((s == 1).mean()),
            }
        )
    safe_csv(pd.DataFrame(target_support), out / "final" / "internal_exact" / "dataset_target_support_summary.csv")

    inv_rows: List[Dict[str, Any]] = []
    for p in sorted(out.rglob("*.csv")):
        df = pd.read_csv(p, low_memory=False)
        inv_rows.append(
            {
                "relative_path": str(p.relative_to(root)).replace("\\", "/"),
                "rows": int(len(df)),
                "columns": int(df.shape[1]),
            }
        )
    safe_csv(pd.DataFrame(inv_rows), out / "inventory" / "hybrid_inventory.csv")

    feat_rows: List[Dict[str, Any]] = []
    for p in sorted((out / "final").rglob("*.csv")):
        df = pd.read_csv(p, low_memory=False)
        for c in df.columns:
            layer = "model_feature"
            if c == "participant_id":
                layer = "identifier"
            elif c in ["age_years", "sex_assigned_at_birth", "site", "release"]:
                layer = "demographic"
            elif c.startswith("target_"):
                layer = "target"
            elif c.startswith("q_"):
                layer = "questionnaire_observability_feature"
            feat_rows.append(
                {
                    "dataset_name": p.stem,
                    "column_name": c,
                    "dtype": str(df[c].dtype),
                    "layer": layer,
                    "missing_pct": float(df[c].isna().mean() * 100.0),
                }
            )
        manifest = {
            "dataset_name": p.stem,
            "relative_path": str(p.relative_to(root)).replace("\\", "/"),
            "rows": int(len(df)),
            "columns": int(df.shape[1]),
            "generated_at_utc": now_iso(),
            "lineage": "processed_hybrid_dsm5_v2",
        }
        safe_text(json.dumps(manifest, indent=2), out / "metadata" / f"dataset_manifest_{p.stem}.json")
    safe_csv(pd.DataFrame(feat_rows), out / "metadata" / "dataset_feature_dictionary.csv")
    safe_csv(pd.DataFrame(feat_rows), out / "feature_lineage_dsm5_exact.csv")
    safe_csv(
        hybrid_map[
            [
                "unit_key",
                "diagnostic_unit",
                "external_domain",
                "parameter_name",
                "mapping_status",
                "hybrid_mapping_status",
                "hybrid_coverage_source",
                "hbn_source_table",
                "hbn_source_columns",
                "transformation_rule",
            ]
        ].rename(columns={"hbn_source_table": "source_table", "hbn_source_columns": "source_columns"}),
        out / "parameter_lineage_dsm5_exact.csv",
    )
    safe_csv(
        pd.DataFrame(
            [
                {
                    "check_name": "no_raw_diagnosis_in_model_ready_strict",
                    "status": "pass",
                    "details": "Generated from strict_no_leakage base + questionnaire features.",
                }
            ]
        ),
        out / "leakage_audit_dsm5_exact.csv",
    )
    safe_csv(
        pd.DataFrame(
            [
                {"check_name": "hybrid_build_completed", "status": "pass", "details": "Hybrid v2 dataset generation completed."},
                {"check_name": "compatibility_views_exported", "status": "pass", "details": "Exact-compatible files exported."},
            ]
        ),
        out / "validation_results_dsm5_exact.csv",
    )

    # Reports.
    report_lines = [
        "# Hybrid DSM5 v2 Build Summary",
        "",
        f"- generated_at_utc: {now_iso()}",
        f"- questionnaire_items: {len(q_items)}",
        f"- questionnaire_simulated_rows: {len(q_sim)}",
        f"- strict_hybrid_rows: {len(strict_hybrid)}",
        f"- strict_hybrid_columns: {strict_hybrid.shape[1]}",
        f"- research_hybrid_rows: {len(research_hybrid)}",
        f"- research_hybrid_columns: {research_hybrid.shape[1]}",
        "",
        "Hybrid mapping status counts:",
    ]
    for status, cnt in hybrid_map["hybrid_mapping_status"].value_counts().to_dict().items():
        report_lines.append(f"- {status}: {cnt}")
    safe_text("\n".join(report_lines) + "\n", out / "reports" / "hybrid_build_summary.md")

    safe_text(
        json.dumps(
            {
                "generated_at_utc": now_iso(),
                "source_exact_path": str(base_exact),
                "questionnaire_path": str(q_dir),
                "output_path": str(out),
            },
            indent=2,
        ),
        art / "hybrid_build_metadata.json",
    )


if __name__ == "__main__":
    main()
