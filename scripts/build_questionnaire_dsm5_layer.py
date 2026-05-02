#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def infer_response_type(row: pd.Series) -> str:
    data_type = str(row.get("data_type_expected", "")).lower()
    pname = str(row.get("parameter_name", "")).lower()
    criterion = str(row.get("criterion_text", "")).lower()
    if "boolean" in data_type or any(k in pname for k in ["flag", "present", "exclusion", "impairment"]):
        return "boolean"
    if any(k in pname for k in ["frequency", "count", "duration", "months", "weeks"]):
        return "integer"
    if any(k in pname for k in ["severity", "level", "specifier", "remission"]):
        return "categorical"
    if any(k in criterion for k in ["nunca", "a veces", "frecuente", "siempre"]):
        return "ordinal_0_4"
    if any(k in data_type for k in ["int", "float", "numeric", "number"]):
        return "numeric"
    return "categorical"


def infer_allowed_values(response_type: str) -> str:
    if response_type == "boolean":
        return "0,1"
    if response_type == "integer":
        return "0..999"
    if response_type == "numeric":
        return "0.0..999.0"
    if response_type == "ordinal_0_4":
        return "0,1,2,3,4"
    return "none,low,moderate,high,unknown"


def build_question_text(row: pd.Series) -> str:
    criterion = str(row.get("criterion_text", "")).strip()
    pname = str(row.get("parameter_name", "")).strip()
    dunit = str(row.get("diagnostic_unit", "")).strip()
    if criterion:
        return criterion
    if pname:
        return f"Para {dunit}, indique el valor observado para {pname}."
    return f"Registrar observacion clinica para {dunit}."


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DSM5 questionnaire observability layer.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()

    norm_csv = root / "data" / "normative_matrix" / "normative_matrix_dsm5_v1.csv"
    norm_params = root / "data" / "processed_dsm5_exact_v1" / "normative" / "normative_parameter_registry.csv"
    mapping_csv = root / "data" / "processed_dsm5_exact_v1" / "mapping" / "parameter_to_hbn_mapping.csv"
    evidence_long_csv = root / "data" / "processed_dsm5_exact_v1" / "intermediate" / "participant_normative_evidence_long.csv"
    cohort_csv = root / "data" / "processed_dsm5_exact_v1" / "final" / "model_ready" / "strict_no_leakage_exact" / "dataset_internal_exact_model_ready_strict_no_leakage_exact.csv"

    out_dir = root / "data" / "questionnaire_dsm5_v1"
    art_dir = root / "artifacts" / "questionnaire_dsm5_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    art_dir.mkdir(parents=True, exist_ok=True)

    norm_raw = pd.read_csv(norm_csv, low_memory=False)
    params = pd.read_csv(norm_params, low_memory=False)
    mapping = pd.read_csv(mapping_csv, low_memory=False)
    evidence = pd.read_csv(evidence_long_csv, low_memory=False)
    cohort = pd.read_csv(cohort_csv, low_memory=False)
    participant_ids = cohort["participant_id"].astype(str).unique().tolist()

    # Ensure one row per normative parameter.
    params = params.sort_values("row_id_from_normative_csv").reset_index(drop=True).copy()
    params["questionnaire_item_id"] = [f"QI_{i:04d}" for i in range(1, len(params) + 1)]
    params["response_type"] = params.apply(infer_response_type, axis=1)
    params["allowed_values"] = params["response_type"].map(infer_allowed_values)
    params["question_text"] = params.apply(build_question_text, axis=1)
    params["requiredness"] = np.where(params["required_for_diagnosis"].astype(str).str.lower() == "yes", "required", "optional")
    params["temporal_reference"] = params["duration_rule"].fillna("")
    params["context_reference"] = params["context_rule"].fillna("")
    params["impairment_reference"] = params["impairment_rule"].fillna("")
    params["exclusion_reference"] = params["exclusion_rule"].fillna("")
    params["severity_reference"] = params["severity_rule"].fillna("")

    map_cols = mapping[["row_id_from_normative_csv", "mapping_status", "evidence_type"]].copy()
    params = params.merge(map_cols, on="row_id_from_normative_csv", how="left")
    params["direct_or_proxy_for_normative_parameter"] = np.where(
        params["mapping_status"].isin(["direct"]),
        "direct",
        np.where(params["mapping_status"].isin(["proxy", "derived"]), "proxy", "direct"),
    )
    params["notes"] = (
        "mapping_status="
        + params["mapping_status"].fillna("unknown").astype(str)
        + "; evidence_type="
        + params["evidence_type"].fillna("unknown").astype(str)
    )

    items = params[
        [
            "questionnaire_item_id",
            "diagnostic_unit",
            "external_domain",
            "parameter_name",
            "dsm_block",
            "question_text",
            "response_type",
            "allowed_values",
            "temporal_reference",
            "context_reference",
            "impairment_reference",
            "exclusion_reference",
            "severity_reference",
            "requiredness",
            "direct_or_proxy_for_normative_parameter",
            "notes",
            "row_id_from_normative_csv",
            "unit_key",
        ]
    ].copy()
    safe_csv(items, out_dir / "questionnaire_items_registry.csv")

    sections = (
        items.groupby(["diagnostic_unit", "external_domain", "dsm_block"], dropna=False)
        .agg(section_item_count=("questionnaire_item_id", "count"))
        .reset_index()
    )
    sections["questionnaire_section_id"] = [f"QS_{i:03d}" for i in range(1, len(sections) + 1)]
    safe_csv(sections, out_dir / "questionnaire_sections_registry.csv")

    response_schema = (
        items.groupby("response_type")
        .agg(allowed_values=("allowed_values", "first"), item_count=("questionnaire_item_id", "count"))
        .reset_index()
    )
    response_schema["schema_notes"] = "Derived from normative matrix and mapping rules."
    safe_csv(response_schema, out_dir / "questionnaire_response_schema.csv")

    q_to_norm = items[
        [
            "questionnaire_item_id",
            "row_id_from_normative_csv",
            "diagnostic_unit",
            "external_domain",
            "parameter_name",
            "dsm_block",
            "direct_or_proxy_for_normative_parameter",
        ]
    ].copy()
    safe_csv(q_to_norm, out_dir / "questionnaire_to_normative_mapping.csv")

    q_to_unit = items[["questionnaire_item_id", "diagnostic_unit", "unit_key"]].drop_duplicates().copy()
    safe_csv(q_to_unit, out_dir / "questionnaire_to_internal_unit_mapping.csv")

    q_to_domain = items[["questionnaire_item_id", "external_domain"]].drop_duplicates().copy()
    safe_csv(q_to_domain, out_dir / "questionnaire_to_domain_mapping.csv")

    scoring_logic = [
        "# Questionnaire Scoring Logic (DSM5 v1)",
        "",
        "- Source of truth: normative_matrix_dsm5_v1.csv",
        "- Each questionnaire item maps 1:1 to a normative parameter row.",
        "- direct_or_proxy_for_normative_parameter is derived from previous mapping status.",
        "- Hybrid fusion rule (next phase): questionnaire response can upgrade absent/no_observed normative evidence.",
        "- No diagnostic claim is emitted from questionnaire alone in this environment.",
        "",
        f"- Generated at UTC: {now_iso()}",
        f"- Normative rows in matrix: {len(norm_raw)}",
        f"- Questionnaire items generated: {len(items)}",
    ]
    safe_text("\n".join(scoring_logic) + "\n", out_dir / "questionnaire_scoring_logic.md")

    # Input/output templates and contract.
    template = pd.DataFrame(
        {
            "participant_id": "",
            "questionnaire_item_id": items["questionnaire_item_id"],
            "response_value": "",
            "response_timestamp_utc": "",
            "source": "manual_or_api",
        }
    )
    safe_csv(template, out_dir / "questionnaire_input_template.csv")

    input_schema = {
        "type": "object",
        "required": ["participant_id", "responses"],
        "properties": {
            "participant_id": {"type": "string"},
            "responses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["questionnaire_item_id", "response_value"],
                    "properties": {
                        "questionnaire_item_id": {"type": "string"},
                        "response_value": {},
                        "response_timestamp_utc": {"type": "string"},
                    },
                },
            },
        },
    }
    safe_text(json.dumps(input_schema, indent=2), art_dir / "questionnaire_input_schema.json")

    output_schema = {
        "type": "object",
        "required": ["participant_id", "questionnaire_completion", "normative_evidence_updates"],
        "properties": {
            "participant_id": {"type": "string"},
            "questionnaire_completion": {"type": "number"},
            "normative_evidence_updates": {"type": "array"},
            "coverage_summary": {"type": "object"},
            "warnings": {"type": "array"},
        },
    }
    safe_text(json.dumps(output_schema, indent=2), art_dir / "questionnaire_output_schema.json")

    contract_lines = [
        "# Questionnaire API Contract (simulated)",
        "",
        "POST /api/questionnaire/submit",
        "- payload follows questionnaire_input_schema.json",
        "- response follows questionnaire_output_schema.json",
        "",
        "Expected backend behavior:",
        "1. Validate questionnaire_item_id against questionnaire_items_registry.csv",
        "2. Validate response value against response_type + allowed_values",
        "3. Map response to normative parameter using questionnaire_to_normative_mapping.csv",
        "4. Return coverage deltas and warnings when critical criteria remain missing",
    ]
    safe_text("\n".join(contract_lines) + "\n", art_dir / "questionnaire_api_contract.md")

    # Simulated/derived responses from existing participant evidence.
    ev = evidence[["participant_id", "row_id_from_normative_csv", "parameter_value", "evidence_status"]].copy()
    ev["participant_id"] = ev["participant_id"].astype(str)
    ev = ev[ev["participant_id"].isin(participant_ids)].copy()
    sim = ev.merge(
        q_to_norm[["questionnaire_item_id", "row_id_from_normative_csv"]],
        on="row_id_from_normative_csv",
        how="left",
    )
    sim["response_value"] = np.where(
        sim["evidence_status"].isin(["absent", "no_observed"]),
        "",
        sim["parameter_value"].astype(str),
    )
    sim["response_origin"] = np.where(
        sim["evidence_status"].isin(["direct", "proxy", "derived"]),
        "derived_from_existing_evidence",
        "simulated_missing",
    )
    sim = sim[
        [
            "participant_id",
            "questionnaire_item_id",
            "row_id_from_normative_csv",
            "response_value",
            "response_origin",
            "evidence_status",
        ]
    ].copy()
    safe_csv(sim, out_dir / "questionnaire_simulated_responses.csv")

    summary = [
        "# Questionnaire DSM5 Layer Build Summary",
        "",
        f"- items: {len(items)}",
        f"- sections: {len(sections)}",
        f"- response schemas: {len(response_schema)}",
        f"- simulated response rows: {len(sim)}",
        f"- participants covered in template base: {len(participant_ids)}",
    ]
    safe_text("\n".join(summary) + "\n", out_dir / "questionnaire_build_summary.md")


if __name__ == "__main__":
    main()

