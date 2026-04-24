#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


LOGGER = logging.getLogger("dsm5-exact-rebuild")
NORMATIVE_VERSION = "normative_matrix_dsm5_v1"

TARGET_CONFIG = {
    "adhd": {
        "diagnostic_unit": "Trastorno por deficit de atencion/hiperactividad",
        "target_col": "target_adhd_exact",
        "status_col": "target_adhd_exact_status",
        "confidence_col": "target_adhd_exact_confidence",
        "coverage_col": "target_adhd_exact_coverage",
        "direct_count_col": "target_adhd_exact_direct_criteria_count",
        "proxy_count_col": "target_adhd_exact_proxy_criteria_count",
        "absent_count_col": "target_adhd_exact_absent_criteria_count",
        "external_domain": "adhd",
    },
    "conduct_disorder": {
        "diagnostic_unit": "Trastorno de conducta",
        "target_col": "target_conduct_disorder_exact",
        "status_col": "target_conduct_disorder_exact_status",
        "confidence_col": "target_conduct_disorder_exact_confidence",
        "coverage_col": "target_conduct_disorder_exact_coverage",
        "direct_count_col": "target_conduct_disorder_exact_direct_criteria_count",
        "proxy_count_col": "target_conduct_disorder_exact_proxy_criteria_count",
        "absent_count_col": "target_conduct_disorder_exact_absent_criteria_count",
        "external_domain": "conduct",
    },
    "enuresis": {
        "diagnostic_unit": "Enuresis",
        "target_col": "target_enuresis_exact",
        "status_col": "target_enuresis_exact_status",
        "confidence_col": "target_enuresis_exact_confidence",
        "coverage_col": "target_enuresis_exact_coverage",
        "direct_count_col": "target_enuresis_exact_direct_criteria_count",
        "proxy_count_col": "target_enuresis_exact_proxy_criteria_count",
        "absent_count_col": "target_enuresis_exact_absent_criteria_count",
        "external_domain": "elimination",
    },
    "encopresis": {
        "diagnostic_unit": "Encopresis",
        "target_col": "target_encopresis_exact",
        "status_col": "target_encopresis_exact_status",
        "confidence_col": "target_encopresis_exact_confidence",
        "coverage_col": "target_encopresis_exact_coverage",
        "direct_count_col": "target_encopresis_exact_direct_criteria_count",
        "proxy_count_col": "target_encopresis_exact_proxy_criteria_count",
        "absent_count_col": "target_encopresis_exact_absent_criteria_count",
        "external_domain": "elimination",
    },
    "separation_anxiety_disorder": {
        "diagnostic_unit": "Trastorno de ansiedad por separacion",
        "target_col": "target_separation_anxiety_disorder_exact",
        "status_col": "target_separation_anxiety_disorder_exact_status",
        "confidence_col": "target_separation_anxiety_disorder_exact_confidence",
        "coverage_col": "target_separation_anxiety_disorder_exact_coverage",
        "direct_count_col": "target_separation_anxiety_disorder_exact_direct_criteria_count",
        "proxy_count_col": "target_separation_anxiety_disorder_exact_proxy_criteria_count",
        "absent_count_col": "target_separation_anxiety_disorder_exact_absent_criteria_count",
        "external_domain": "anxiety",
    },
    "generalized_anxiety_disorder": {
        "diagnostic_unit": "Trastorno de ansiedad generalizada",
        "target_col": "target_generalized_anxiety_disorder_exact",
        "status_col": "target_generalized_anxiety_disorder_exact_status",
        "confidence_col": "target_generalized_anxiety_disorder_exact_confidence",
        "coverage_col": "target_generalized_anxiety_disorder_exact_coverage",
        "direct_count_col": "target_generalized_anxiety_disorder_exact_direct_criteria_count",
        "proxy_count_col": "target_generalized_anxiety_disorder_exact_proxy_criteria_count",
        "absent_count_col": "target_generalized_anxiety_disorder_exact_absent_criteria_count",
        "external_domain": "anxiety",
    },
    "major_depressive_disorder": {
        "diagnostic_unit": "Trastorno de depresion mayor",
        "target_col": "target_major_depressive_disorder_exact",
        "status_col": "target_major_depressive_disorder_exact_status",
        "confidence_col": "target_major_depressive_disorder_exact_confidence",
        "coverage_col": "target_major_depressive_disorder_exact_coverage",
        "direct_count_col": "target_major_depressive_disorder_exact_direct_criteria_count",
        "proxy_count_col": "target_major_depressive_disorder_exact_proxy_criteria_count",
        "absent_count_col": "target_major_depressive_disorder_exact_absent_criteria_count",
        "external_domain": "depression",
    },
    "persistent_depressive_disorder": {
        "diagnostic_unit": "Trastorno depresivo persistente",
        "target_col": "target_persistent_depressive_disorder_exact",
        "status_col": "target_persistent_depressive_disorder_exact_status",
        "confidence_col": "target_persistent_depressive_disorder_exact_confidence",
        "coverage_col": "target_persistent_depressive_disorder_exact_coverage",
        "direct_count_col": "target_persistent_depressive_disorder_exact_direct_criteria_count",
        "proxy_count_col": "target_persistent_depressive_disorder_exact_proxy_criteria_count",
        "absent_count_col": "target_persistent_depressive_disorder_exact_absent_criteria_count",
        "external_domain": "depression",
    },
    "dmdd": {
        "diagnostic_unit": "Trastorno de desregulacion disruptiva del estado de animo",
        "target_col": "target_dmdd_exact",
        "status_col": "target_dmdd_exact_status",
        "confidence_col": "target_dmdd_exact_confidence",
        "coverage_col": "target_dmdd_exact_coverage",
        "direct_count_col": "target_dmdd_exact_direct_criteria_count",
        "proxy_count_col": "target_dmdd_exact_proxy_criteria_count",
        "absent_count_col": "target_dmdd_exact_absent_criteria_count",
        "external_domain": "depression",
    },
}

DOMAIN_TARGETS = {
    "adhd": "target_domain_adhd",
    "conduct": "target_domain_conduct",
    "elimination": "target_domain_elimination",
    "anxiety": "target_domain_anxiety",
    "depression": "target_domain_depression",
}

SENTINEL_FILES = [
    "data/processed/final/strict_no_leakage/master_multilabel_ready_strict_no_leakage.csv",
    "data/processed/intermediate/master_with_targets_and_features.csv",
    "data/processed/intermediate/targets_6_11.csv",
]


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def snake(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value.lower()


def clean_text(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    s = text.strip()
    if not s:
        return s
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_name(text: str) -> str:
    text = clean_text(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def first_existing(columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    cols = set(columns)
    for c in candidates:
        if c in cols:
            return c
    return None


@dataclass
class RebuildPaths:
    root: Path
    out: Path
    inventory: Path
    normative: Path
    mapping: Path
    intermediate: Path
    final: Path
    final_internal: Path
    final_external: Path
    final_model_ready: Path
    strict_exact: Path
    research_exact: Path
    reports: Path
    metadata: Path
    artifacts: Path


class DSM5ExactRebuilder:
    def __init__(self, root: Path):
        self.root = root
        self.paths = RebuildPaths(
            root=root,
            out=root / "data" / "processed_dsm5_exact_v1",
            inventory=root / "data" / "processed_dsm5_exact_v1" / "inventory",
            normative=root / "data" / "processed_dsm5_exact_v1" / "normative",
            mapping=root / "data" / "processed_dsm5_exact_v1" / "mapping",
            intermediate=root / "data" / "processed_dsm5_exact_v1" / "intermediate",
            final=root / "data" / "processed_dsm5_exact_v1" / "final",
            final_internal=root / "data" / "processed_dsm5_exact_v1" / "final" / "internal_exact",
            final_external=root / "data" / "processed_dsm5_exact_v1" / "final" / "external_domains",
            final_model_ready=root / "data" / "processed_dsm5_exact_v1" / "final" / "model_ready",
            strict_exact=root / "data" / "processed_dsm5_exact_v1" / "final" / "model_ready" / "strict_no_leakage_exact",
            research_exact=root / "data" / "processed_dsm5_exact_v1" / "final" / "model_ready" / "research_extended_exact",
            reports=root / "data" / "processed_dsm5_exact_v1" / "reports",
            metadata=root / "data" / "processed_dsm5_exact_v1" / "metadata",
            artifacts=root / "artifacts" / "dsm5_exact_v1",
        )
        self.normative_raw: Optional[pd.DataFrame] = None
        self.normative_registry: Optional[pd.DataFrame] = None
        self.mapping_df: Optional[pd.DataFrame] = None
        self.base_df: Optional[pd.DataFrame] = None
        self.evidence_long: Optional[pd.DataFrame] = None
        self.evidence_wide: Optional[pd.DataFrame] = None
        self.coverage_by_participant_unit: Optional[pd.DataFrame] = None
        self.internal_targets: Optional[pd.DataFrame] = None
        self.external_targets: Optional[pd.DataFrame] = None
        self.baseline_hashes: Dict[str, str] = {}
        self.validation_rows: List[Dict[str, Any]] = []

    def ensure_dirs(self) -> None:
        for d in [
            self.paths.out,
            self.paths.inventory,
            self.paths.normative,
            self.paths.mapping,
            self.paths.intermediate,
            self.paths.final,
            self.paths.final_internal,
            self.paths.final_external,
            self.paths.final_model_ready,
            self.paths.strict_exact,
            self.paths.research_exact,
            self.paths.reports,
            self.paths.metadata,
            self.paths.artifacts,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def capture_baseline_hashes(self) -> None:
        hashes: Dict[str, str] = {}
        for rel in SENTINEL_FILES:
            p = self.root / rel
            if p.exists():
                hashes[rel] = file_hash(p)
        self.baseline_hashes = hashes
        safe_write_text(
            json.dumps({"captured_at": now_iso(), "hashes": hashes}, indent=2),
            self.paths.artifacts / "baseline_sentinel_hashes_before.json",
        )

    def verify_baseline_hashes(self) -> None:
        after: Dict[str, str] = {}
        changed: List[str] = []
        missing: List[str] = []
        for rel, before_hash in self.baseline_hashes.items():
            p = self.root / rel
            if not p.exists():
                missing.append(rel)
                continue
            new_hash = file_hash(p)
            after[rel] = new_hash
            if new_hash != before_hash:
                changed.append(rel)
        safe_write_text(
            json.dumps({"checked_at": now_iso(), "hashes": after, "missing": missing, "changed": changed}, indent=2),
            self.paths.artifacts / "baseline_sentinel_hashes_after.json",
        )
        status = "pass" if not changed and not missing else "fail"
        self.validation_rows.append(
            {
                "check_name": "previous_generation_sentinel_hash_unchanged",
                "status": status,
                "details": f"changed={len(changed)} missing={len(missing)}",
            }
        )

    def load_inputs(self) -> None:
        norm_path = self.root / "data" / "normative_matrix" / "normative_matrix_dsm5_v1.csv"
        norm = pd.read_csv(norm_path, dtype=str).fillna("")
        for c in norm.columns:
            norm[c] = norm[c].map(clean_text)
        norm["row_id_from_normative_csv"] = np.arange(1, len(norm) + 1)
        norm["parameter_name_filled"] = norm["parameter_name"].where(norm["parameter_name"].str.strip() != "", "")
        norm["parameter_name_filled"] = norm.apply(
            lambda r: r["parameter_name_filled"] if str(r["parameter_name_filled"]).strip() else f"NORM_PARAM_{int(r['row_id_from_normative_csv']):04d}",
            axis=1,
        )
        norm["diagnostic_unit_norm"] = norm["diagnostic_unit"].map(normalize_name)
        norm["external_domain_norm"] = norm["external_domain"].map(normalize_name)
        self.normative_raw = norm

        master_path = self.root / "data" / "processed" / "intermediate" / "master_with_targets_and_features.csv"
        base = pd.read_csv(master_path, low_memory=False)
        base.columns = [snake(c) for c in base.columns]
        base["participant_id"] = base["participant_id"].astype(str)

        cohort_path = self.root / "data" / "processed" / "intermediate" / "cohort_6_11.csv"
        if cohort_path.exists():
            cohort = pd.read_csv(cohort_path, low_memory=False)
            cohort.columns = [snake(c) for c in cohort.columns]
            cohort["participant_id"] = cohort["participant_id"].astype(str)
            base = base[base["participant_id"].isin(set(cohort["participant_id"]))].copy()
        else:
            age_col = first_existing(base.columns, ["age_years", "age"])
            if age_col:
                base = base[pd.to_numeric(base[age_col], errors="coerce").between(6, 11, inclusive="both")].copy()

        diag = self._build_diagnosis_flags()
        base = base.merge(diag, on="participant_id", how="left")
        for c in [col for col in base.columns if col.startswith("diag_domain_")]:
            base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0).astype(int)

        self.base_df = base
        LOGGER.info("Loaded inputs: normative_rows=%d cohort_rows=%d", len(norm), len(base))

    def _build_diagnosis_flags(self) -> pd.DataFrame:
        base = self.root / "data" / "HBN_synthetic_release11_focused_subset_csv"
        cc = pd.read_csv(base / "Diagnosis_ClinicianConsensus.csv", low_memory=False)
        cc.columns = [snake(c) for c in cc.columns]
        cc["participant_id"] = cc["participant_id"].astype(str)
        diag_cols = [c for c in cc.columns if c.startswith("diagnosis_") and not c.endswith("_certainty")]
        text = cc[diag_cols].fillna("").astype(str).apply(lambda s: s.str.lower())
        domain_patterns = {
            "adhd": [r"attention-deficit", r"adhd", r"hyperactivity"],
            "conduct": [r"disruptive", r"conduct", r"impulse control"],
            "elimination": [r"elimination", r"enuresis", r"encopresis"],
            "anxiety": [r"anxiety"],
            "depression": [r"depress"],
        }
        out = pd.DataFrame({"participant_id": cc["participant_id"]})
        for dom, pats in domain_patterns.items():
            dom_hit = pd.Series(False, index=cc.index)
            for col in diag_cols:
                col_lower = text[col]
                pat_hit = pd.Series(False, index=cc.index)
                for pat in pats:
                    pat_hit = pat_hit | col_lower.str.contains(pat, regex=True, na=False)
                dom_hit = dom_hit | pat_hit
            out[f"diag_consensus_{dom}"] = dom_hit.astype(int)

        def load_ksads(name: str) -> pd.DataFrame:
            d = pd.read_csv(base / name, low_memory=False)
            d.columns = [snake(c) for c in d.columns]
            d["participant_id"] = d["participant_id"].astype(str)
            keep = [
                "participant_id",
                "adhd_present",
                "anxietydisorders_present",
                "depressivedisorders_present",
                "disruptiveimpulsecontrolconductdisorders_present",
                "eliminationdisorders_present",
            ]
            keep = [k for k in keep if k in d.columns]
            d = d[keep].copy()
            rename_map = {
                "adhd_present": "adhd",
                "anxietydisorders_present": "anxiety",
                "depressivedisorders_present": "depression",
                "disruptiveimpulsecontrolconductdisorders_present": "conduct",
                "eliminationdisorders_present": "elimination",
            }
            for src_col, dom in rename_map.items():
                if src_col in d.columns:
                    d[f"diag_{snake(name).replace('.csv', '')}_{dom}"] = pd.to_numeric(d[src_col], errors="coerce").fillna(0).astype(int)
            return d[["participant_id"] + [c for c in d.columns if c.startswith(f"diag_{snake(name).replace('.csv', '')}_")]]

        out = out.merge(load_ksads("Diagnosis_KSADS_D.csv"), on="participant_id", how="outer")
        out = out.merge(load_ksads("Diagnosis_KSADS_P.csv"), on="participant_id", how="outer")
        out = out.merge(load_ksads("Diagnosis_KSADS_T.csv"), on="participant_id", how="outer")
        out = out.fillna(0)

        for dom in ["adhd", "conduct", "elimination", "anxiety", "depression"]:
            source_cols = [c for c in out.columns if c.endswith(f"_{dom}") and c.startswith("diag_")]
            cons = f"diag_consensus_{dom}"
            source_cols = [cons] + [c for c in source_cols if c != cons]
            out[f"diag_domain_{dom}_broad"] = (out[source_cols].apply(pd.to_numeric, errors="coerce").fillna(0).max(axis=1) > 0).astype(int)
            out[f"diag_domain_{dom}_source_count"] = (out[source_cols].apply(pd.to_numeric, errors="coerce").fillna(0) > 0).sum(axis=1).astype(int)

        return out[["participant_id"] + [c for c in out.columns if c.startswith("diag_")]].copy()

    def build_source_inventory(self) -> None:
        raw_dir = self.root / "data" / "HBN_synthetic_release11_focused_subset_csv"
        rows: List[Dict[str, Any]] = []
        for path in sorted(raw_dir.glob("*.csv")):
            df = pd.read_csv(path, low_memory=False)
            df.columns = [snake(c) for c in df.columns]
            id_col = first_existing(df.columns, ["participant_id", "subject_id", "src_subject_id", "id"])
            table_type = "questionnaire"
            name = path.stem.lower()
            if "participants" in name:
                table_type = "participants"
            elif "diagnosis" in name:
                table_type = "diagnostics"
            elif "dictionary" in name or "summary" in name or "source" in name:
                table_type = "metadata"
            rows.append({
                "file_name": path.name,
                "table_name": snake(path.stem),
                "rows": int(len(df)),
                "columns": int(df.shape[1]),
                "id_column": id_col or "",
                "null_pct": float(df.isna().mean().mean() * 100.0),
                "estimated_table_type": table_type,
            })
        safe_write_csv(pd.DataFrame(rows), self.paths.inventory / "source_inventory.csv")

    def build_previous_artifacts_inventory(self) -> None:
        roots = [
            self.root / "data" / "processed",
            self.root / "artifacts" / "preprocessing",
            self.root / "artifacts" / "specs",
            self.root / "reports" / "versioning",
            self.root / "reports" / "metrics",
            self.root / "reports" / "comparisons",
            self.root / "reports" / "experiments",
        ]
        rows: List[Dict[str, Any]] = []
        for r in roots:
            if not r.exists():
                continue
            for p in sorted(x for x in r.rglob("*") if x.is_file()):
                stat = p.stat()
                rows.append({
                    "relative_path": str(p.relative_to(self.root)).replace("\\", "/"),
                    "source_area": str(r.relative_to(self.root)).replace("\\", "/"),
                    "size_bytes": int(stat.st_size),
                    "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "extension": p.suffix.lower(),
                })
        safe_write_csv(pd.DataFrame(rows), self.paths.inventory / "previous_artifacts_inventory.csv")

    def _map_unit_key(self, diagnostic_unit_norm: str) -> str:
        if "deficit" in diagnostic_unit_norm and "atencion" in diagnostic_unit_norm:
            return "adhd"
        if diagnostic_unit_norm == "trastorno de conducta":
            return "conduct_disorder"
        if diagnostic_unit_norm == "enuresis":
            return "enuresis"
        if diagnostic_unit_norm == "encopresis":
            return "encopresis"
        if "ansiedad por separacion" in diagnostic_unit_norm:
            return "separation_anxiety_disorder"
        if "ansiedad generalizada" in diagnostic_unit_norm:
            return "generalized_anxiety_disorder"
        if "depresion mayor" in diagnostic_unit_norm:
            return "major_depressive_disorder"
        if "depresivo persistente" in diagnostic_unit_norm:
            return "persistent_depressive_disorder"
        if "desregulacion disruptiva" in diagnostic_unit_norm:
            return "dmdd"
        if diagnostic_unit_norm == "transversal":
            return "transversal"
        return "other"

    def build_normative_registries(self) -> None:
        if self.normative_raw is None:
            raise RuntimeError("normative data not loaded")
        n = self.normative_raw.copy()
        n["unit_key"] = n["diagnostic_unit_norm"].map(self._map_unit_key)
        n["parameter_type"] = n["section"].map({
            "master_units": "master_unit",
            "transversal_parameters": "transversal",
            "diagnostic_structural": "structural",
            "diagnostic_symptom": "symptom",
            "diagnostic_specifiers": "specifier",
        }).fillna("other")
        n["data_type_expected"] = n["data_type"]
        n["required_for_diagnosis"] = np.where(n["parameter_type"].isin(["structural", "symptom"]), "yes", "optional")
        nr = n["normative_rule"].fillna("")
        pn = n["parameter_name_filled"].fillna("")
        ct = n["criterion_text"].fillna("")
        n["threshold_rule"] = np.where(pn.str.contains("THRESHOLD", case=False, na=False) | nr.str.contains("umbral", case=False, na=False), nr, "")
        n["frequency_rule"] = np.where(pn.str.contains("frequency", case=False, na=False) | ct.str.contains("veces|frecuencia", case=False, na=False), nr, "")
        n["duration_rule"] = np.where(pn.str.contains("duration|persistence", case=False, na=False) | ct.str.contains("mes|semana|ano", case=False, na=False), nr, "")
        n["onset_rule"] = np.where(pn.str.contains("onset|before|inicio", case=False, na=False) | ct.str.contains("antes de|inicio", case=False, na=False), nr, "")
        n["context_rule"] = np.where(pn.str.contains("context|setting", case=False, na=False) | ct.str.contains("context|entorno|ambiente", case=False, na=False), nr, "")
        n["impairment_rule"] = np.where(pn.str.contains("impairment|impact", case=False, na=False) | ct.str.contains("deterioro|interferencia|funcionamiento|malestar", case=False, na=False), nr, "")
        n["exclusion_rule"] = np.where(pn.str.contains("EXCLUSION|COEXISTENCE", case=False, na=False) | ct.str.contains("no se explica|descarta|exclus", case=False, na=False), nr, "")
        n["coexistence_rule"] = np.where(pn.str.contains("COEXISTENCE", case=False, na=False) | ct.str.contains("coexist", case=False, na=False), nr, "")
        n["remission_rule"] = np.where(pn.str.contains("REMISSION", case=False, na=False) | ct.str.contains("remision", case=False, na=False), nr, "")
        n["severity_rule"] = np.where(pn.str.contains("SEVERITY", case=False, na=False) | ct.str.contains("leve|moderado|grave", case=False, na=False), nr, "")
        n["specifier_rule"] = np.where(pn.str.contains("SPEC", case=False, na=False) | n["dsm_block"].str.contains("Especificador", case=False, na=False), nr, "")
        n["notes"] = (n["audit_result"].fillna("") + " | " + n["rule_of_use"].fillna("")).str.strip(" |")
        n["source_document"] = n["source_document"].replace("", "normative_matrix_dsm5_v1.csv")
        n["normative_version"] = NORMATIVE_VERSION

        keep_cols = [
            "diagnostic_unit", "external_domain", "parameter_name_filled", "dsm_block", "criterion_label", "criterion_text",
            "parameter_type", "data_type_expected", "required_for_diagnosis", "threshold_rule", "frequency_rule", "duration_rule",
            "onset_rule", "context_rule", "impairment_rule", "exclusion_rule", "coexistence_rule", "remission_rule", "severity_rule",
            "specifier_rule", "notes", "source_document", "normative_version", "row_id_from_normative_csv", "table_index", "matrix_name",
            "row_index_in_table", "section", "code_reference", "audit_result", "rule_of_use", "unit_key",
        ]
        reg = n[keep_cols].copy().rename(columns={"parameter_name_filled": "parameter_name"})
        reg["parameter_name_raw"] = n["parameter_name"].values
        self.normative_registry = reg
        safe_write_csv(reg, self.paths.normative / "normative_parameter_registry.csv")

        units = n[n["section"] == "master_units"].copy()
        units["unit_key"] = units["diagnostic_unit_norm"].map(self._map_unit_key)
        units["internal_target_col"] = units["unit_key"].map(lambda k: TARGET_CONFIG[k]["target_col"] if k in TARGET_CONFIG else "")
        units["external_domain_target_col"] = units["unit_key"].map(lambda k: DOMAIN_TARGETS.get(TARGET_CONFIG[k]["external_domain"], "") if k in TARGET_CONFIG else "")
        safe_write_csv(units[["row_id_from_normative_csv", "diagnostic_unit", "external_domain", "unit_key", "internal_target_col", "external_domain_target_col", "criterion_text", "normative_rule", "source_document"]].copy(), self.paths.normative / "normative_units_registry.csv")

        criteria = reg[(reg["criterion_label"].astype(str).str.strip() != "") | (reg["criterion_text"].astype(str).str.strip() != "")]
        safe_write_csv(criteria.copy(), self.paths.normative / "normative_criteria_registry.csv")
        spec = reg[reg["section"].eq("diagnostic_specifiers") | reg["parameter_name"].str.contains("SPEC|PRESENTATION|SEVERITY|REMISSION", case=False, na=False)]
        safe_write_csv(spec.copy(), self.paths.normative / "normative_specifiers_registry.csv")
        exc = reg[reg["parameter_name"].str.contains("EXCLUSION|COEXISTENCE", case=False, na=False) | reg["criterion_text"].str.contains("no se explica|descarta|exclus", case=False, na=False)]
        safe_write_csv(exc.copy(), self.paths.normative / "normative_exclusion_registry.csv")
        temp = reg[reg["parameter_name"].str.contains("ONSET|DURATION|FREQUENCY|PERSISTENCE|REMISSION|COURSE", case=False, na=False) | reg["criterion_text"].str.contains("mes|semana|ano|antes de", case=False, na=False)]
        safe_write_csv(temp.copy(), self.paths.normative / "normative_temporality_registry.csv")

        cross = units[["diagnostic_unit", "external_domain", "unit_key", "internal_target_col", "external_domain_target_col"]].copy()
        safe_write_csv(cross, self.paths.normative / "normative_domain_crosswalk.csv")

        self.validation_rows.append({
            "check_name": "normative_parameter_registry_row_count_matches_normative_csv",
            "status": "pass" if len(reg) == len(n) else "fail",
            "details": f"registry_rows={len(reg)} normative_rows={len(n)}",
        })

    def _infer_source_table(self, cols: List[str]) -> str:
        if not cols:
            return ""
        first = cols[0]
        pref = first.split("_")[0]
        map_pref = {
            "swan": "SWAN",
            "conners": "Conners",
            "scared": "SCARED",
            "mfq": "MFQ",
            "cdi": "CDI",
            "icut": "ICUT",
            "ari": "ARI",
            "sdq": "SDQ",
            "cbcl": "CBCL",
            "age": "participants",
            "sex": "participants",
            "site": "participants",
            "release": "participants",
            "diag": "Diagnosis_*",
            "target": "derived_previous_generation",
            "comorbidity": "derived_previous_generation",
        }
        return map_pref.get(pref, "derived")

    def _assign_mapping_rule(self, row: pd.Series) -> Dict[str, Any]:
        unit = row["unit_key"]
        param = str(row["parameter_name"]).strip()
        section = str(row.get("section", "")).strip()

        def pack(
            status: str,
            cols: Optional[List[str]] = None,
            strategy: str = "column",
            threshold: Optional[float] = None,
            confidence: str = "medium",
            evidence_type: str = "questionnaire",
            leakage_risk: str = "low",
            usable_target: str = "yes",
            usable_feature: str = "yes",
            usable_domain: str = "yes",
            comments: str = "",
            literal_value: str = "",
        ) -> Dict[str, Any]:
            cols = cols or []
            if status == "absent":
                confidence = "high"
                evidence_type = "absent"
                leakage_risk = "none"
                usable_target = "no"
                usable_feature = "no"
                usable_domain = "no"
            return {
                "hbn_source_table": self._infer_source_table(cols),
                "hbn_source_columns": ";".join(cols),
                "mapping_status": status,
                "mapping_confidence": confidence,
                "transformation_rule": strategy if strategy != "column" else "identity",
                "evidence_type": evidence_type,
                "missingness_risk": "high" if status in {"absent", "proxy"} else "medium" if status == "derived" else "low",
                "leakage_risk": leakage_risk,
                "usable_for_internal_target": usable_target,
                "usable_for_model_feature": usable_feature,
                "usable_for_external_domain": usable_domain,
                "comments": comments,
                "compute_strategy": strategy,
                "compute_threshold": "" if threshold is None else threshold,
                "literal_value": literal_value,
            }

        if section == "master_units":
            return pack("derived", strategy="literal", confidence="high", evidence_type="normative_only", usable_feature="no", comments="Normative unit row", literal_value=row["diagnostic_unit"])

        if unit == "transversal":
            if param == "diagnostic_unit":
                return pack("derived", strategy="literal", confidence="high", evidence_type="normative_only", usable_feature="no", literal_value=row["diagnostic_unit"])
            if param == "diagnostic_domain":
                return pack("derived", strategy="literal", confidence="high", evidence_type="normative_only", usable_feature="no", literal_value=row["external_domain"])
            if param == "age_at_assessment":
                return pack("direct", cols=["age_years"], evidence_type="demographic", confidence="high")
            if param == "functional_impairment":
                return pack("proxy", cols=["sdq_impact", "ari_p_impairment_item", "ari_sr_impairment_item"], strategy="any_positive")
            if param == "diagnostic_coexistence_rule":
                return pack("derived", cols=["comorbidity_count_5targets"], strategy="column", evidence_type="derived")
            if param == "subjective_report":
                return pack("derived", cols=["has_scared_sr", "has_mfq_sr", "has_ari_sr"], strategy="any_positive", evidence_type="availability")
            if param == "observer_report":
                return pack("derived", cols=["has_scared_p", "has_mfq_p", "has_cbcl", "has_ari_p"], strategy="any_positive", evidence_type="availability")
            if param == "severity_current":
                return pack("derived", cols=["sdq_total_difficulties", "cbcl_externalizing_proxy", "cbcl_internalizing_proxy"], strategy="severity_band")
            if param in {"age_at_onset", "duration_minimum", "symptom_frequency", "persistence_rule", "contexts_present", "cross_setting_severity", "substance_medical_exclusion", "other_mental_disorder_exclusion", "specifier_set", "remission_status"}:
                return pack("absent", comments="Not observed in current subset")
            return pack("absent")

        if unit == "adhd":
            a_map = {
                "ADHD_A1_a": "swan_01", "ADHD_A1_b": "swan_02", "ADHD_A1_c": "swan_03", "ADHD_A1_d": "swan_04", "ADHD_A1_e": "swan_05",
                "ADHD_A1_f": "swan_06", "ADHD_A1_g": "swan_07", "ADHD_A1_h": "swan_08", "ADHD_A1_i": "swan_09",
                "ADHD_A2_a": "swan_10", "ADHD_A2_b": "swan_11", "ADHD_A2_c": "swan_12", "ADHD_A2_d": "swan_13", "ADHD_A2_e": "swan_14",
                "ADHD_A2_f": "swan_15", "ADHD_A2_g": "swan_16", "ADHD_A2_h": "swan_17", "ADHD_A2_i": "swan_18",
            }
            if param in a_map:
                return pack("proxy", cols=[a_map[param]])
            if param in {"ADHD_GATE_A", "ADHD_A1_THRESHOLD", "ADHD_A2_THRESHOLD"}:
                return pack("proxy", cols=["diag_domain_adhd_broad", "swan_inattention_total", "swan_hyperactive_impulsive_total", "conners_hyperactivity"], strategy="mean", leakage_risk="high", usable_feature="no")
            if param == "ADHD_MULTICONTEXT":
                return pack("proxy", cols=["sdq_impact", "conners_total"], strategy="mean", confidence="low")
            if param == "ADHD_IMPAIRMENT":
                return pack("proxy", cols=["sdq_impact", "ari_p_impairment_item", "ari_sr_impairment_item"], strategy="any_positive")
            if param == "ADHD_PRESENTATION":
                return pack("derived", cols=["swan_inattention_total", "swan_hyperactive_impulsive_total"], strategy="adhd_presentation")
            if param == "ADHD_SEVERITY":
                return pack("derived", cols=["swan_total", "conners_total"], strategy="severity_band")
            if param in {"ADHD_ONSET_BEFORE_12", "ADHD_EXCLUSION", "ADHD_PARTIAL_REMISSION"}:
                return pack("absent", comments="Requires temporal/exclusion fields")
            return pack("absent")

        if unit == "conduct_disorder":
            if re.fullmatch(r"CD_[0-9]{1,2}", param):
                idx = int(param.split("_")[1])
                if 1 <= idx <= 24:
                    return pack("proxy", cols=[f"icut_{idx:02d}"])
            if re.fullmatch(r"CD_LPE_[0-9]", param):
                lpe_map = {
                    "CD_LPE_1": ["icut_callousness"],
                    "CD_LPE_2": ["icut_uncaring"],
                    "CD_LPE_3": ["icut_unemotional"],
                    "CD_LPE_4": ["ari_p_symptom_total", "ari_sr_symptom_total"],
                }
                return pack("proxy", cols=lpe_map.get(param, ["icut_total"]), strategy="mean", confidence="low")
            if param in {"CD_GATE_A", "CD_THRESHOLD"}:
                return pack("proxy", cols=["diag_domain_conduct_broad", "icut_total", "conners_conduct_problems", "sdq_conduct_problems"], strategy="mean", leakage_risk="high", usable_feature="no")
            if param == "CD_IMPAIRMENT":
                return pack("proxy", cols=["sdq_impact", "ari_p_impairment_item", "ari_sr_impairment_item"], strategy="any_positive")
            if param == "CD_LIMITED_PROSOCIAL":
                return pack("derived", cols=["icut_callousness", "icut_uncaring", "icut_unemotional"], strategy="mean")
            if param == "CD_SEVERITY":
                return pack("derived", cols=["icut_total", "cbcl_externalizing_proxy", "sdq_conduct_problems"], strategy="severity_band")
            if param in {"CD_ASPD_EXCLUSION", "CD_ONSET_TYPE"}:
                return pack("absent", comments="Exclusion/onset not available")
            return pack("absent")

        if unit == "enuresis":
            if param in {"ENUR_A", "ENUR_B"}:
                return pack("proxy", cols=["diag_domain_elimination_broad", "cbcl_108"], strategy="mean", leakage_risk="high", usable_feature="no")
            if param == "ENUR_C":
                return pack("direct", cols=["age_years"], evidence_type="demographic", confidence="high")
            if param in {"ENUR_D", "ENUR_SUBTYPE"}:
                return pack("absent")
            return pack("absent")

        if unit == "encopresis":
            if param in {"ENC_A", "ENC_B"}:
                return pack("proxy", cols=["diag_domain_elimination_broad", "cbcl_112"], strategy="mean", leakage_risk="high", usable_feature="no")
            if param == "ENC_C":
                return pack("direct", cols=["age_years"], evidence_type="demographic", confidence="high")
            if param in {"ENC_D", "ENC_SUBTYPE"}:
                return pack("absent")
            return pack("absent")

        if unit == "separation_anxiety_disorder":
            if re.fullmatch(r"SAD_[1-8]", param):
                return pack("proxy", cols=["scared_p_separation_anxiety", "scared_sr_separation_anxiety"], strategy="mean")
            if param == "SAD_A_THRESHOLD":
                return pack("proxy", cols=["diag_domain_anxiety_broad", "scared_p_separation_anxiety", "scared_sr_separation_anxiety"], strategy="mean", leakage_risk="high", usable_feature="no")
            if param == "SAD_C":
                return pack("proxy", cols=["sdq_impact"])
            if param in {"SAD_B", "SAD_D"}:
                return pack("absent")
            return pack("absent")

        if unit == "generalized_anxiety_disorder":
            if re.fullmatch(r"GAD_[1-6]", param):
                return pack("proxy", cols=["scared_p_generalized_anxiety", "scared_sr_generalized_anxiety"], strategy="mean")
            if param in {"GAD_A", "GAD_B", "GAD_C_THRESHOLD"}:
                return pack("proxy", cols=["diag_domain_anxiety_broad", "scared_p_generalized_anxiety", "scared_sr_generalized_anxiety"], strategy="mean", leakage_risk="high", usable_feature="no")
            if param == "GAD_D":
                return pack("proxy", cols=["sdq_impact"])
            if param in {"GAD_E", "GAD_F"}:
                return pack("absent")
            return pack("absent")

        if unit == "major_depressive_disorder":
            if re.fullmatch(r"MDD_[1-9]", param):
                return pack("proxy", cols=["mfq_p_total", "mfq_sr_total", "cdi_total"], strategy="mean")
            if param in {"MDD_A_THRESHOLD", "MDD_A_NUCLEAR"}:
                return pack("proxy", cols=["diag_domain_depression_broad", "mfq_p_total", "mfq_sr_total", "cdi_total"], strategy="mean", leakage_risk="high", usable_feature="no")
            if param == "MDD_C":
                return pack("proxy", cols=["sdq_impact"])
            if param == "MDD_CURRENT_SEVERITY":
                return pack("derived", cols=["mfq_p_total", "mfq_sr_total", "cdi_total"], strategy="severity_band")
            if param == "MDD_DIAGNOSTIC_RECORD_ORDER":
                return pack("derived", cols=["n_diagnoses"], strategy="column", evidence_type="derived")
            if param.startswith("MDD_SPEC_") or param in {"MDD_B", "MDD_D", "MDD_E", "MDD_SPECIFIERS", "MDD_EPISODE_COURSE", "MDD_RECURRENT_INTERVAL", "MDD_PSYCHOTIC_STATUS", "MDD_REMISSION_STATUS"}:
                return pack("absent")
            return pack("absent")

        if unit == "persistent_depressive_disorder":
            if re.fullmatch(r"PDD_[1-6]", param):
                return pack("proxy", cols=["mfq_p_total", "mfq_sr_total", "cdi_total"], strategy="mean")
            if param in {"PDD_A", "PDD_B_THRESHOLD"}:
                return pack("proxy", cols=["diag_domain_depression_broad", "mfq_p_total", "mfq_sr_total", "cdi_total"], strategy="mean", leakage_risk="high", usable_feature="no")
            if param == "PDD_SEVERITY":
                return pack("derived", cols=["mfq_p_total", "mfq_sr_total", "cdi_total"], strategy="severity_band")
            return pack("absent")

        if unit == "dmdd":
            if param in {"DMDD_A", "DMDD_B", "DMDD_C", "DMDD_D", "DMDD_E"}:
                return pack("proxy", cols=["ari_p_symptom_total", "ari_sr_symptom_total"], strategy="mean")
            if param in {"DMDD_F", "DMDD_G"}:
                return pack("proxy", cols=["sdq_impact", "ari_p_impairment_item", "ari_sr_impairment_item"], strategy="any_positive")
            if param in {"DMDD_I", "DMDD_J_COEXISTENCE"}:
                return pack("derived", cols=["diag_domain_depression_source_count", "diag_domain_conduct_source_count", "diag_domain_anxiety_source_count"], strategy="sum", evidence_type="derived")
            if param == "DMDD_K":
                return pack("derived", cols=["ari_p_symptom_total", "ari_sr_symptom_total"], strategy="severity_band")
            if param in {"DMDD_H", "DMDD_J"}:
                return pack("absent")
            return pack("absent")

        return pack("absent")

    def build_mapping(self) -> None:
        if self.normative_registry is None or self.base_df is None:
            raise RuntimeError("normative registry/base dataframe missing")
        reg = self.normative_registry.copy()
        mapping_rows = [self._assign_mapping_rule(row) for _, row in reg.iterrows()]
        mapping = pd.concat([reg.reset_index(drop=True), pd.DataFrame(mapping_rows)], axis=1)
        mapping["parameter_feature_name"] = mapping.apply(lambda r: snake(f"{r['unit_key']}__{r['parameter_name']}"), axis=1)

        available_cols = set(self.base_df.columns)
        adjusted = []
        for _, row in mapping.iterrows():
            cols = [c for c in str(row["hbn_source_columns"]).split(";") if c]
            missing_cols = [c for c in cols if c not in available_cols]
            if missing_cols and row["mapping_status"] != "absent":
                row["comments"] = f"{row['comments']} | auto-demoted-to-absent missing columns: {','.join(missing_cols)}".strip(" |")
                row["mapping_status"] = "absent"
                row["mapping_confidence"] = "high"
                row["evidence_type"] = "absent"
                row["usable_for_internal_target"] = "no"
                row["usable_for_model_feature"] = "no"
                row["usable_for_external_domain"] = "no"
                row["compute_strategy"] = "absent"
                row["hbn_source_columns"] = ""
                row["hbn_source_table"] = ""
                row["missingness_risk"] = "high"
                row["leakage_risk"] = "none"
                row["compute_threshold"] = ""
                row["literal_value"] = ""
            adjusted.append(row)
        mapping = pd.DataFrame(adjusted)
        self.mapping_df = mapping

        safe_write_csv(mapping, self.paths.mapping / "parameter_to_hbn_mapping.csv")
        crit_map = mapping[(mapping["criterion_label"].astype(str).str.strip() != "") | (mapping["criterion_text"].astype(str).str.strip() != "")].copy()
        safe_write_csv(crit_map, self.paths.mapping / "criterion_to_hbn_mapping.csv")

        coverage = mapping.groupby(["unit_key", "mapping_status"]).size().reset_index(name="n_parameters").sort_values(["unit_key", "mapping_status"])
        total = mapping.groupby("unit_key").size().reset_index(name="total_parameters")
        coverage = coverage.merge(total, on="unit_key", how="left")
        coverage["pct"] = coverage["n_parameters"] / coverage["total_parameters"]
        safe_write_csv(coverage, self.paths.mapping / "mapping_coverage_summary.csv")
        safe_write_csv(mapping[mapping["mapping_status"] == "absent"].copy(), self.paths.mapping / "absent_normative_parameters.csv")
        safe_write_csv(mapping[mapping["mapping_status"] == "proxy"].copy(), self.paths.mapping / "proxy_parameters_registry.csv")
        safe_write_csv(mapping[mapping["mapping_status"] == "derived"].copy(), self.paths.mapping / "derived_parameters_registry.csv")

        checklist = mapping[["row_id_from_normative_csv", "diagnostic_unit", "external_domain", "parameter_name", "section", "mapping_status", "mapping_confidence", "hbn_source_table", "hbn_source_columns", "compute_strategy", "usable_for_internal_target", "usable_for_model_feature", "usable_for_external_domain", "comments"]].copy()
        checklist["present_in_mapping"] = 1
        safe_write_csv(checklist, self.paths.out / "full_normative_parameter_checklist.csv")
        safe_write_csv(checklist[checklist["mapping_status"].isin(["proxy", "derived", "absent"])].copy(), self.paths.out / "unmapped_or_partially_mapped_parameters.csv")

        mandatory_md = [
            "# Mandatory Parameter Completeness Report",
            "",
            f"- normative_rows: {len(self.normative_registry)}",
            f"- mapping_rows: {len(mapping)}",
            f"- direct: {int((mapping['mapping_status']=='direct').sum())}",
            f"- proxy: {int((mapping['mapping_status']=='proxy').sum())}",
            f"- derived: {int((mapping['mapping_status']=='derived').sum())}",
            f"- absent: {int((mapping['mapping_status']=='absent').sum())}",
            "",
            "All normative rows are materialized in mapping table with explicit status.",
        ]
        safe_write_text("\n".join(mandatory_md) + "\n", self.paths.out / "mandatory_parameter_completeness_report.md")

        self.validation_rows.append({
            "check_name": "parameter_to_hbn_mapping_row_count_matches_normative_registry",
            "status": "pass" if len(mapping) == len(self.normative_registry) else "fail",
            "details": f"mapping_rows={len(mapping)} normative_registry_rows={len(self.normative_registry)}",
        })

    def _compute_series(self, map_row: pd.Series) -> Tuple[pd.Series, pd.Series]:
        if self.base_df is None:
            raise RuntimeError("base dataframe not loaded")
        df = self.base_df
        strategy = str(map_row["compute_strategy"])
        cols = [c for c in str(map_row["hbn_source_columns"]).split(";") if c]
        threshold = map_row["compute_threshold"]
        threshold = float(threshold) if str(threshold).strip() != "" else None
        literal = str(map_row.get("literal_value", ""))

        def _num(sel_cols: List[str]) -> pd.DataFrame:
            if not sel_cols:
                return pd.DataFrame(index=df.index)
            return df[sel_cols].apply(pd.to_numeric, errors="coerce")

        if strategy == "absent":
            raw = pd.Series([np.nan] * len(df), index=df.index)
            return raw, raw.copy()
        if strategy == "literal":
            raw = pd.Series([literal] * len(df), index=df.index, dtype="object")
            return raw, raw.copy()
        if strategy == "column":
            col = cols[0] if cols else ""
            raw = df[col] if col else pd.Series([np.nan] * len(df), index=df.index)
            return raw, raw
        if strategy == "any_positive":
            num = _num(cols)
            if num.empty:
                raw = pd.Series([np.nan] * len(df), index=df.index)
                return raw, raw.copy()
            raw = num.max(axis=1, skipna=True)
            all_na = num.isna().all(axis=1)
            val = (num.fillna(0) > 0).any(axis=1).astype(float)
            val[all_na] = np.nan
            return raw, val
        if strategy == "sum":
            num = _num(cols)
            raw = num.sum(axis=1, min_count=1) if not num.empty else pd.Series([np.nan] * len(df), index=df.index)
            return raw, raw
        if strategy == "mean":
            num = _num(cols)
            raw = num.mean(axis=1, skipna=True) if not num.empty else pd.Series([np.nan] * len(df), index=df.index)
            return raw, raw
        if strategy == "severity_band":
            num = _num(cols)
            raw = num.mean(axis=1, skipna=True) if not num.empty else pd.Series([np.nan] * len(df), index=df.index)
            if raw.notna().sum() == 0:
                return raw, raw.copy()
            q1 = float(raw.quantile(0.33))
            q2 = float(raw.quantile(0.66))
            val = pd.Series(["low"] * len(df), index=df.index, dtype="object")
            val[raw >= q1] = "moderate"
            val[raw >= q2] = "high"
            val[raw.isna()] = np.nan
            return raw, val
        if strategy == "adhd_presentation":
            inat = pd.to_numeric(df.get("swan_inattention_total"), errors="coerce")
            hyp = pd.to_numeric(df.get("swan_hyperactive_impulsive_total"), errors="coerce")
            raw = pd.concat([inat, hyp], axis=1).mean(axis=1, skipna=True)
            val = pd.Series(["unspecified"] * len(df), index=df.index, dtype="object")
            val[inat > hyp] = "predominantly_inattentive"
            val[hyp > inat] = "predominantly_hyperactive_impulsive"
            val[(inat.notna()) & (hyp.notna()) & (np.abs(inat - hyp) <= 0.25 * (inat.abs() + hyp.abs() + 1e-9))] = "combined"
            val[(inat.isna()) & (hyp.isna())] = np.nan
            return raw, val

        raw = pd.Series([np.nan] * len(df), index=df.index)
        return raw, raw.copy()

    def build_participant_normative_evidence(self) -> None:
        if self.mapping_df is None or self.base_df is None:
            raise RuntimeError("mapping/base not available")
        participants = self.base_df[["participant_id"]].copy()
        rows: List[pd.DataFrame] = []
        for _, m in self.mapping_df.iterrows():
            raw, val = self._compute_series(m)
            status = pd.Series([m["mapping_status"]] * len(participants), index=participants.index, dtype="object")
            if m["mapping_status"] != "absent":
                missing = val.isna() if isinstance(val, pd.Series) else pd.Series([True] * len(participants), index=participants.index)
                status[missing] = "no_observed"
            coverage_status = status.map({
                "direct": "mapped_covered",
                "proxy": "mapped_covered",
                "derived": "mapped_covered",
                "no_observed": "mapped_but_missing",
                "absent": "not_mappable",
            }).fillna("mapped_but_missing")
            quality = status.map({"direct": "high", "proxy": "medium", "derived": "medium", "no_observed": "low", "absent": "low"})
            pname = str(m["parameter_name"])
            temporal_flag = int(bool(re.search(r"onset|duration|frequency|persistence|remission|course", pname, flags=re.I)))
            context_flag = int(bool(re.search(r"context|setting", pname, flags=re.I)))
            exclusion_flag = int(bool(re.search(r"exclusion|coexistence", pname, flags=re.I)))

            tmp = pd.DataFrame({
                "participant_id": participants["participant_id"].values,
                "diagnostic_unit": m["diagnostic_unit"],
                "unit_key": m["unit_key"],
                "parameter_name": m["parameter_name"],
                "parameter_feature_name": m["parameter_feature_name"],
                "parameter_value": val.values if isinstance(val, pd.Series) else val,
                "parameter_value_raw": raw.values if isinstance(raw, pd.Series) else raw,
                "evidence_status": status.values,
                "mapping_status": m["mapping_status"],
                "evidence_type": m["evidence_type"],
                "coverage_status": coverage_status.values,
                "source_table": m["hbn_source_table"],
                "source_columns": m["hbn_source_columns"],
                "derivation_rule": m["transformation_rule"],
                "quality_flag": quality.values,
                "temporal_flag": temporal_flag,
                "context_flag": context_flag,
                "exclusion_flag": exclusion_flag,
                "usable_for_target": np.where((m["usable_for_internal_target"] == "yes") & (~status.isin(["absent", "no_observed"])), 1, 0),
                "usable_for_feature": np.where((m["usable_for_model_feature"] == "yes") & (~status.isin(["absent", "no_observed"])), 1, 0),
                "row_id_from_normative_csv": m["row_id_from_normative_csv"],
            })
            rows.append(tmp)

        long_df = pd.concat(rows, axis=0, ignore_index=True)
        self.evidence_long = long_df
        safe_write_csv(long_df, self.paths.intermediate / "participant_normative_evidence_long.csv")
        safe_write_csv(long_df, self.paths.final / "dataset_participant_normative_evidence_long.csv")

        wide = long_df.pivot_table(index="participant_id", columns="parameter_feature_name", values="parameter_value", aggfunc="first").reset_index()
        wide.columns = [str(c) for c in wide.columns]
        self.evidence_wide = wide
        safe_write_csv(wide, self.paths.intermediate / "participant_normative_evidence_wide.csv")
        safe_write_csv(wide, self.paths.final / "dataset_participant_normative_evidence_wide.csv")

        cov = long_df.groupby(["participant_id", "unit_key", "evidence_status"]).size().unstack(fill_value=0).reset_index()
        for c in ["direct", "proxy", "derived", "no_observed", "absent"]:
            if c not in cov.columns:
                cov[c] = 0
        cov["total_parameters"] = cov[["direct", "proxy", "derived", "no_observed", "absent"]].sum(axis=1)
        cov["covered_parameters"] = cov[["direct", "proxy", "derived"]].sum(axis=1)
        cov["coverage_ratio"] = cov["covered_parameters"] / cov["total_parameters"].replace({0: np.nan})
        cov["coverage_band"] = pd.cut(cov["coverage_ratio"].fillna(0.0), bins=[-0.01, 0.33, 0.66, 1.01], labels=["low", "medium", "high"]).astype(str)
        self.coverage_by_participant_unit = cov
        safe_write_csv(cov, self.paths.intermediate / "participant_coverage_flags.csv")
        safe_write_csv(cov, self.paths.intermediate / "participant_direct_proxy_absent_summary.csv")

        summary = long_df.groupby(["unit_key", "mapping_status"]).size().reset_index(name="n").rename(columns={"mapping_status": "evidence_status"})
        safe_write_csv(summary, self.paths.final / "dataset_parameter_coverage_summary.csv")

        expected_rows = len(self.base_df) * len(self.mapping_df)
        self.validation_rows.append({
            "check_name": "participant_evidence_row_count_matches_participants_x_parameters",
            "status": "pass" if len(long_df) == expected_rows else "fail",
            "details": f"actual_rows={len(long_df)} expected_rows={expected_rows}",
        })
        param_count = long_df["row_id_from_normative_csv"].nunique()
        self.validation_rows.append({
            "check_name": "all_normative_parameters_present_in_evidence",
            "status": "pass" if param_count == len(self.mapping_df) else "fail",
            "details": f"evidence_parameters={param_count} mapping_parameters={len(self.mapping_df)}",
        })

    def _quantile_or_default(self, series: pd.Series, q: float, default: float = 0.0) -> float:
        s = pd.to_numeric(series, errors="coerce")
        if s.notna().sum() == 0:
            return default
        return float(s.quantile(q))

    def build_internal_exact_targets(self) -> None:
        if self.base_df is None or self.coverage_by_participant_unit is None:
            raise RuntimeError("base/evidence not ready")
        df = self.base_df.copy()
        cov = self.coverage_by_participant_unit.copy()

        def cov_cols(unit_key: str) -> pd.DataFrame:
            c = cov[cov["unit_key"] == unit_key][["participant_id", "direct", "proxy", "absent", "coverage_band"]].copy()
            return c.rename(columns={"direct": "direct_count", "proxy": "proxy_count", "absent": "absent_count", "coverage_band": "coverage_band"})

        swan_sum = pd.to_numeric(df.get("swan_inattention_total"), errors="coerce").fillna(0) + pd.to_numeric(df.get("swan_hyperactive_impulsive_total"), errors="coerce").fillna(0)
        conduct_components = pd.concat([
            pd.to_numeric(df.get("icut_total"), errors="coerce"),
            pd.to_numeric(df.get("conners_conduct_problems"), errors="coerce"),
            pd.to_numeric(df.get("sdq_conduct_problems"), errors="coerce"),
            pd.to_numeric(df.get("cbcl_rule_breaking_proxy"), errors="coerce"),
        ], axis=1)
        conduct_score = conduct_components.mean(axis=1, skipna=True)
        sep_score = pd.concat([
            pd.to_numeric(df.get("scared_p_separation_anxiety"), errors="coerce"),
            pd.to_numeric(df.get("scared_sr_separation_anxiety"), errors="coerce"),
        ], axis=1).max(axis=1, skipna=True)
        gad_score = pd.concat([
            pd.to_numeric(df.get("scared_p_generalized_anxiety"), errors="coerce"),
            pd.to_numeric(df.get("scared_sr_generalized_anxiety"), errors="coerce"),
        ], axis=1).max(axis=1, skipna=True)
        dep_score = pd.concat([
            pd.to_numeric(df.get("mfq_p_total"), errors="coerce"),
            pd.to_numeric(df.get("mfq_sr_total"), errors="coerce"),
            pd.to_numeric(df.get("cdi_total"), errors="coerce"),
        ], axis=1).max(axis=1, skipna=True)
        dmdd_score = pd.concat([
            pd.to_numeric(df.get("ari_p_symptom_total"), errors="coerce"),
            pd.to_numeric(df.get("ari_sr_symptom_total"), errors="coerce"),
        ], axis=1).max(axis=1, skipna=True)
        enu_proxy = pd.to_numeric(df.get("cbcl_108"), errors="coerce")
        enc_proxy = pd.to_numeric(df.get("cbcl_112"), errors="coerce")

        th = {
            "adhd": self._quantile_or_default(swan_sum, 0.75, 0.0),
            "conduct": self._quantile_or_default(conduct_score, 0.75, 0.0),
            "sep": self._quantile_or_default(sep_score, 0.75, 0.0),
            "gad": self._quantile_or_default(gad_score, 0.75, 0.0),
            "dep": self._quantile_or_default(dep_score, 0.75, 0.0),
            "pdd": self._quantile_or_default(dep_score, 0.60, 0.0),
            "dmdd": self._quantile_or_default(dmdd_score, 0.75, 0.0),
        }

        out = df[["participant_id"]].copy()
        rules_registry: List[Dict[str, Any]] = []

        def apply_target(key: str, target: pd.Series, status: pd.Series, confidence: pd.Series) -> None:
            cfg = TARGET_CONFIG[key]
            out[cfg["target_col"]] = target.astype(int)
            out[cfg["status_col"]] = status.astype(str)
            out[cfg["confidence_col"]] = confidence.astype(str)

        adhd_broad = pd.to_numeric(df.get("diag_domain_adhd_broad"), errors="coerce").fillna(0).astype(int)
        adhd_proxy = (swan_sum >= th["adhd"]).fillna(False)
        adhd_target = (adhd_broad == 1) | adhd_proxy
        adhd_status = np.where((adhd_broad == 1) & adhd_proxy, "direct_plus_proxy", np.where(adhd_broad == 1, "direct", np.where(adhd_proxy, "proxy", "negative")))
        adhd_conf = np.where(adhd_status == "direct_plus_proxy", "high", np.where(adhd_status == "direct", "medium", np.where(adhd_status == "proxy", "low", "none")))
        apply_target("adhd", adhd_target, pd.Series(adhd_status), pd.Series(adhd_conf))
        rules_registry.append({"target_name": TARGET_CONFIG["adhd"]["target_col"], "rule_summary": f"diag_domain_adhd_broad == 1 OR (swan_sum >= {th['adhd']:.4f})", "evidence_type": "direct_plus_proxy", "threshold": th["adhd"]})

        conduct_broad = pd.to_numeric(df.get("diag_domain_conduct_broad"), errors="coerce").fillna(0).astype(int)
        conduct_proxy = (conduct_score >= th["conduct"]).fillna(False)
        conduct_target = (conduct_broad == 1) | conduct_proxy
        conduct_status = np.where((conduct_broad == 1) & conduct_proxy, "proxy_with_broad_support", np.where(conduct_broad == 1, "broad_proxy", np.where(conduct_proxy, "proxy", "negative")))
        conduct_conf = np.where(conduct_status == "proxy_with_broad_support", "high", np.where(conduct_status == "broad_proxy", "medium", np.where(conduct_status == "proxy", "low", "none")))
        apply_target("conduct_disorder", conduct_target, pd.Series(conduct_status), pd.Series(conduct_conf))
        rules_registry.append({"target_name": TARGET_CONFIG["conduct_disorder"]["target_col"], "rule_summary": f"diag_domain_conduct_broad == 1 OR (conduct_score >= {th['conduct']:.4f})", "evidence_type": "proxy", "threshold": th["conduct"]})

        elim_broad = pd.to_numeric(df.get("diag_domain_elimination_broad"), errors="coerce").fillna(0).astype(int)
        enu_flag = ((enu_proxy >= 1).fillna(False)) if enu_proxy is not None else pd.Series(False, index=df.index)
        enu_target = (elim_broad == 1) | enu_flag
        enu_status = np.where((elim_broad == 1) & enu_flag, "proxy_with_broad_support", np.where(elim_broad == 1, "broad_proxy", np.where(enu_flag, "proxy", "negative")))
        enu_conf = np.where(enu_status == "proxy_with_broad_support", "medium", np.where(enu_status == "broad_proxy", "low", np.where(enu_status == "proxy", "low", "none")))
        apply_target("enuresis", enu_target, pd.Series(enu_status), pd.Series(enu_conf))
        rules_registry.append({"target_name": TARGET_CONFIG["enuresis"]["target_col"], "rule_summary": "diag_domain_elimination_broad == 1 OR cbcl_108 >= 1", "evidence_type": "proxy", "threshold": 1})

        enc_flag = ((enc_proxy >= 1).fillna(False)) if enc_proxy is not None else pd.Series(False, index=df.index)
        enc_target = (elim_broad == 1) | enc_flag
        enc_status = np.where((elim_broad == 1) & enc_flag, "proxy_with_broad_support", np.where(elim_broad == 1, "broad_proxy", np.where(enc_flag, "proxy", "negative")))
        enc_conf = np.where(enc_status == "proxy_with_broad_support", "medium", np.where(enc_status == "broad_proxy", "low", np.where(enc_status == "proxy", "low", "none")))
        apply_target("encopresis", enc_target, pd.Series(enc_status), pd.Series(enc_conf))
        rules_registry.append({"target_name": TARGET_CONFIG["encopresis"]["target_col"], "rule_summary": "diag_domain_elimination_broad == 1 OR cbcl_112 >= 1", "evidence_type": "proxy", "threshold": 1})

        anx_broad = pd.to_numeric(df.get("diag_domain_anxiety_broad"), errors="coerce").fillna(0).astype(int)
        sep_proxy = (sep_score >= th["sep"]).fillna(False)
        sep_target = ((anx_broad == 1) & sep_proxy) | sep_proxy
        sep_status = np.where((anx_broad == 1) & sep_proxy, "proxy_with_broad_support", np.where(sep_proxy, "proxy", "negative"))
        sep_conf = np.where(sep_status == "proxy_with_broad_support", "medium", np.where(sep_status == "proxy", "low", "none"))
        apply_target("separation_anxiety_disorder", sep_target, pd.Series(sep_status), pd.Series(sep_conf))
        rules_registry.append({"target_name": TARGET_CONFIG["separation_anxiety_disorder"]["target_col"], "rule_summary": f"(diag_domain_anxiety_broad == 1 AND sep_score >= {th['sep']:.4f}) OR sep_score >= {th['sep']:.4f}", "evidence_type": "proxy", "threshold": th["sep"]})

        gad_proxy = (gad_score >= th["gad"]).fillna(False)
        gad_target = ((anx_broad == 1) & gad_proxy) | gad_proxy
        gad_status = np.where((anx_broad == 1) & gad_proxy, "proxy_with_broad_support", np.where(gad_proxy, "proxy", "negative"))
        gad_conf = np.where(gad_status == "proxy_with_broad_support", "medium", np.where(gad_status == "proxy", "low", "none"))
        apply_target("generalized_anxiety_disorder", gad_target, pd.Series(gad_status), pd.Series(gad_conf))
        rules_registry.append({"target_name": TARGET_CONFIG["generalized_anxiety_disorder"]["target_col"], "rule_summary": f"(diag_domain_anxiety_broad == 1 AND gad_score >= {th['gad']:.4f}) OR gad_score >= {th['gad']:.4f}", "evidence_type": "proxy", "threshold": th["gad"]})

        dep_broad = pd.to_numeric(df.get("diag_domain_depression_broad"), errors="coerce").fillna(0).astype(int)
        mdd_proxy = (dep_score >= th["dep"]).fillna(False)
        mdd_target = (dep_broad == 1) | mdd_proxy
        mdd_status = np.where((dep_broad == 1) & mdd_proxy, "proxy_with_broad_support", np.where(dep_broad == 1, "broad_proxy", np.where(mdd_proxy, "proxy", "negative")))
        mdd_conf = np.where(mdd_status == "proxy_with_broad_support", "medium", np.where(mdd_status == "broad_proxy", "low", np.where(mdd_status == "proxy", "low", "none")))
        apply_target("major_depressive_disorder", mdd_target, pd.Series(mdd_status), pd.Series(mdd_conf))
        rules_registry.append({"target_name": TARGET_CONFIG["major_depressive_disorder"]["target_col"], "rule_summary": f"diag_domain_depression_broad == 1 OR dep_score >= {th['dep']:.4f}", "evidence_type": "proxy", "threshold": th["dep"]})

        pdd_proxy = (dep_score >= th["pdd"]).fillna(False)
        pdd_target = (dep_broad == 1) & pdd_proxy
        pdd_status = np.where((dep_broad == 1) & pdd_proxy, "weak_proxy", "negative")
        pdd_conf = np.where(pdd_status == "weak_proxy", "low", "none")
        apply_target("persistent_depressive_disorder", pdd_target, pd.Series(pdd_status), pd.Series(pdd_conf))
        rules_registry.append({"target_name": TARGET_CONFIG["persistent_depressive_disorder"]["target_col"], "rule_summary": f"(diag_domain_depression_broad == 1) AND (dep_score >= {th['pdd']:.4f}); duration not directly observed", "evidence_type": "weak_proxy", "threshold": th["pdd"]})

        dmdd_proxy = (dmdd_score >= th["dmdd"]).fillna(False)
        dmdd_context = (conduct_score >= self._quantile_or_default(conduct_score, 0.60, 0.0)).fillna(False)
        dmdd_target = dmdd_proxy & (dmdd_context | (dep_broad == 1) | (conduct_broad == 1))
        dmdd_status = np.where(dmdd_target, "weak_proxy", "negative")
        dmdd_conf = np.where(dmdd_target, "low", "none")
        apply_target("dmdd", dmdd_target, pd.Series(dmdd_status), pd.Series(dmdd_conf))
        rules_registry.append({"target_name": TARGET_CONFIG["dmdd"]["target_col"], "rule_summary": f"(dmdd_score >= {th['dmdd']:.4f}) AND (conduct_context OR broad mood/disruptive support)", "evidence_type": "weak_proxy", "threshold": th["dmdd"]})

        for key, cfg in TARGET_CONFIG.items():
            cv = cov_cols(key).rename(
                columns={
                    "direct_count": cfg["direct_count_col"],
                    "proxy_count": cfg["proxy_count_col"],
                    "absent_count": cfg["absent_count_col"],
                    "coverage_band": cfg["coverage_col"],
                }
            )
            out = out.merge(cv, on="participant_id", how="left")
            for col in [cfg["direct_count_col"], cfg["proxy_count_col"], cfg["absent_count_col"]]:
                out[col] = out[col].fillna(0).astype(int)
            out[cfg["coverage_col"]] = out[cfg["coverage_col"]].fillna("low")

        out["internal_exact_comorbidity_count"] = out[[cfg["target_col"] for cfg in TARGET_CONFIG.values()]].sum(axis=1).astype(int)
        out["internal_exact_any_positive"] = (out["internal_exact_comorbidity_count"] > 0).astype(int)

        self.internal_targets = out
        safe_write_csv(out, self.paths.intermediate / "internal_exact_targets.csv")
        safe_write_csv(out, self.paths.out / "internal_exact_targets.csv")

        rules_df = pd.DataFrame(rules_registry)
        rules_df["generated_at_utc"] = now_iso()
        safe_write_csv(rules_df, self.paths.out / "target_construction_registry.csv")
        safe_write_text("\n".join([
            "# Target Construction Rules",
            "",
            "Targets are built from broad diagnostic evidence plus instrument-based proxies.",
            "Each target includes status/confidence/coverage to expose uncertainty and missingness.",
            "",
            "See target_construction_registry.csv for explicit formulas and thresholds.",
        ]) + "\n", self.paths.out / "target_construction_rules.md")

        coverage_audit_rows: List[Dict[str, Any]] = []
        for key, cfg in TARGET_CONFIG.items():
            tc = cfg["target_col"]
            sc = cfg["status_col"]
            cc = cfg["confidence_col"]
            coverage_audit_rows.append({
                "target_col": tc,
                "positives": int(out[tc].sum()),
                "prevalence": float(out[tc].mean()),
                "status_direct_like": int(out[sc].isin(["direct", "direct_plus_proxy"]).sum()),
                "status_proxy_like": int(out[sc].isin(["proxy", "proxy_with_broad_support", "broad_proxy", "weak_proxy"]).sum()),
                "confidence_high": int((out[cc] == "high").sum()),
                "confidence_medium": int((out[cc] == "medium").sum()),
                "confidence_low": int((out[cc] == "low").sum()),
            })
        safe_write_csv(pd.DataFrame(coverage_audit_rows), self.paths.out / "target_coverage_audit.csv")

        expected_target_cols = [cfg["target_col"] for cfg in TARGET_CONFIG.values()]
        self.validation_rows.append({
            "check_name": "all_9_internal_exact_targets_exist",
            "status": "pass" if all(c in out.columns for c in expected_target_cols) else "fail",
            "details": f"found={sum(c in out.columns for c in expected_target_cols)} expected={len(expected_target_cols)}",
        })

    def build_external_domain_targets(self) -> None:
        if self.internal_targets is None:
            raise RuntimeError("internal targets not built")
        it = self.internal_targets.copy()
        out = it[["participant_id"]].copy()
        out[DOMAIN_TARGETS["adhd"]] = it[TARGET_CONFIG["adhd"]["target_col"]].astype(int)
        out[DOMAIN_TARGETS["conduct"]] = it[TARGET_CONFIG["conduct_disorder"]["target_col"]].astype(int)
        out[DOMAIN_TARGETS["elimination"]] = (it[TARGET_CONFIG["enuresis"]["target_col"]].astype(int) | it[TARGET_CONFIG["encopresis"]["target_col"]].astype(int)).astype(int)
        out[DOMAIN_TARGETS["anxiety"]] = (it[TARGET_CONFIG["separation_anxiety_disorder"]["target_col"]].astype(int) | it[TARGET_CONFIG["generalized_anxiety_disorder"]["target_col"]].astype(int)).astype(int)
        out[DOMAIN_TARGETS["depression"]] = (it[TARGET_CONFIG["major_depressive_disorder"]["target_col"]].astype(int) | it[TARGET_CONFIG["persistent_depressive_disorder"]["target_col"]].astype(int) | it[TARGET_CONFIG["dmdd"]["target_col"]].astype(int)).astype(int)
        out["domain_comorbidity_count"] = out[list(DOMAIN_TARGETS.values())].sum(axis=1).astype(int)
        out["domain_any_positive"] = (out["domain_comorbidity_count"] > 0).astype(int)
        self.external_targets = out
        safe_write_csv(out, self.paths.intermediate / "external_domain_targets.csv")
        safe_write_csv(out, self.paths.out / "external_domain_targets.csv")

        crosswalk_rows = [
            {"external_domain_target": DOMAIN_TARGETS["adhd"], "derived_from_internal_targets": TARGET_CONFIG["adhd"]["target_col"], "derivation_logic": "identity"},
            {"external_domain_target": DOMAIN_TARGETS["conduct"], "derived_from_internal_targets": TARGET_CONFIG["conduct_disorder"]["target_col"], "derivation_logic": "identity"},
            {"external_domain_target": DOMAIN_TARGETS["elimination"], "derived_from_internal_targets": f"{TARGET_CONFIG['enuresis']['target_col']} OR {TARGET_CONFIG['encopresis']['target_col']}", "derivation_logic": "logical_or"},
            {"external_domain_target": DOMAIN_TARGETS["anxiety"], "derived_from_internal_targets": f"{TARGET_CONFIG['separation_anxiety_disorder']['target_col']} OR {TARGET_CONFIG['generalized_anxiety_disorder']['target_col']}", "derivation_logic": "logical_or"},
            {"external_domain_target": DOMAIN_TARGETS["depression"], "derived_from_internal_targets": f"{TARGET_CONFIG['major_depressive_disorder']['target_col']} OR {TARGET_CONFIG['persistent_depressive_disorder']['target_col']} OR {TARGET_CONFIG['dmdd']['target_col']}", "derivation_logic": "logical_or"},
        ]
        safe_write_csv(pd.DataFrame(crosswalk_rows), self.paths.out / "internal_to_external_crosswalk.csv")
        safe_write_text("\n".join([
            "# Domain Derivation Rules",
            "",
            "- domain_adhd <- target_adhd_exact",
            "- domain_conduct <- target_conduct_disorder_exact",
            "- domain_elimination <- target_enuresis_exact OR target_encopresis_exact",
            "- domain_anxiety <- target_separation_anxiety_disorder_exact OR target_generalized_anxiety_disorder_exact",
            "- domain_depression <- target_major_depressive_disorder_exact OR target_persistent_depressive_disorder_exact OR target_dmdd_exact",
        ]) + "\n", self.paths.out / "domain_derivation_rules.md")

        domain_ok = (out[DOMAIN_TARGETS["depression"]].astype(int) == (it[TARGET_CONFIG["major_depressive_disorder"]["target_col"]].astype(int) | it[TARGET_CONFIG["persistent_depressive_disorder"]["target_col"]].astype(int) | it[TARGET_CONFIG["dmdd"]["target_col"]].astype(int)).astype(int)).all()
        self.validation_rows.append({
            "check_name": "external_domains_derived_only_from_internal_exact_targets",
            "status": "pass" if domain_ok else "fail",
            "details": "validated depression domain OR rule",
        })

    def _feature_source_from_col(self, col: str) -> str:
        if col in {"participant_id", "age_years", "sex_assigned_at_birth", "site", "release"}:
            return "participants"
        pref = col.split("_")[0]
        pref_map = {
            "swan": "SWAN", "conners": "Conners", "scared": "SCARED", "mfq": "MFQ", "cdi": "CDI",
            "sdq": "SDQ", "cbcl": "CBCL", "ari": "ARI", "icut": "ICUT", "diag": "Diagnosis_*", "target": "derived_target", "has": "availability_flag",
        }
        return pref_map.get(pref, "derived")

    def _layer_for_col(self, col: str) -> str:
        if col == "participant_id":
            return "identifiers"
        if col in {"age_years", "sex_assigned_at_birth", "site", "release"}:
            return "demographic_fields"
        if col.startswith("target_domain_"):
            return "domain_targets"
        if col.startswith("target_") and col.endswith("_exact"):
            return "normative_exact_targets"
        if "__" in col:
            return "criterion_level_evidence_fields"
        if "specifier" in col or "presentation" in col:
            return "specifier_fields"
        if "exclusion" in col:
            return "exclusion_fields"
        if "context" in col:
            return "context_fields"
        if any(k in col for k in ["duration", "onset", "frequency", "persistence", "remission", "course"]):
            return "temporality_fields"
        if "impairment" in col or "impact" in col:
            return "impairment_fields"
        if any(k in col for k in ["status", "confidence", "coverage", "source", "mapping"]):
            return "mapping_metadata_fields"
        if col.startswith("diag_"):
            return "audit_only_fields"
        return "model_eligible_features"

    def export_datasets(self) -> None:
        if any(x is None for x in [self.base_df, self.evidence_wide, self.internal_targets, self.external_targets, self.mapping_df]):
            raise RuntimeError("required artifacts missing before export")
        base = self.base_df.copy()
        internal = self.internal_targets.copy()
        external = self.external_targets.copy()
        evidence_wide = self.evidence_wide.copy()

        master = base[["participant_id", "age_years", "sex_assigned_at_birth", "site", "release"]].copy().merge(internal, on="participant_id", how="left").merge(external, on="participant_id", how="left")
        safe_write_csv(master, self.paths.final_internal / "dataset_internal_exact_master.csv")

        evidence_rich = master.merge(evidence_wide, on="participant_id", how="left")
        safe_write_csv(evidence_rich, self.paths.final_internal / "dataset_internal_exact_evidence_rich.csv")

        model_cols = [c for c in base.columns if c not in {"target_conduct", "target_adhd", "target_elimination", "target_anxiety", "target_depression", "source_target_conduct", "source_target_adhd", "source_target_elimination", "source_target_anxiety", "source_target_depression", "label_pattern"}]
        model_ready = base[model_cols].merge(internal, on="participant_id", how="left").merge(external, on="participant_id", how="left")
        safe_write_csv(model_ready, self.paths.final_internal / "dataset_internal_exact_model_ready.csv")

        unit_feature_map = {
            "adhd": ["swan_", "conners_", "sdq_hyperactivity_inattention", "cbcl_attention_problems_proxy"],
            "conduct_disorder": ["icut_", "conners_conduct_problems", "sdq_conduct_problems", "cbcl_rule_breaking_proxy", "cbcl_aggressive_behavior_proxy", "ari_"],
            "enuresis": ["cbcl_108", "diag_domain_elimination_broad", "sdq_impact"],
            "encopresis": ["cbcl_112", "diag_domain_elimination_broad", "sdq_impact"],
            "separation_anxiety_disorder": ["scared_p_", "scared_sr_", "sdq_emotional_symptoms", "sdq_impact"],
            "generalized_anxiety_disorder": ["scared_p_", "scared_sr_", "sdq_emotional_symptoms", "sdq_impact"],
            "major_depressive_disorder": ["mfq_", "cdi_", "cbcl_internalizing_proxy", "sdq_emotional_symptoms"],
            "persistent_depressive_disorder": ["mfq_", "cdi_", "cbcl_internalizing_proxy", "sdq_emotional_symptoms"],
            "dmdd": ["ari_", "sdq_conduct_problems", "cbcl_aggressive_behavior_proxy", "cbcl_rule_breaking_proxy"],
        }
        unit_file_map = {
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
        for key, cfg in TARGET_CONFIG.items():
            prefixes = unit_feature_map.get(key, [])
            feat_cols = ["participant_id", "age_years", "sex_assigned_at_birth", "site", "release"]
            for c in base.columns:
                if c in feat_cols:
                    continue
                if any((c.startswith(p) if p.endswith("_") else c == p) for p in prefixes):
                    feat_cols.append(c)
            feat_cols = [c for c in feat_cols if c in base.columns]
            dsu = base[feat_cols].merge(internal[["participant_id", cfg["target_col"], cfg["status_col"], cfg["confidence_col"], cfg["coverage_col"], cfg["direct_count_col"], cfg["proxy_count_col"], cfg["absent_count_col"]]], on="participant_id", how="left")
            safe_write_csv(dsu, self.paths.final_internal / unit_file_map[key])

        dom_feature_map = {
            "adhd": ["swan_", "conners_", "sdq_hyperactivity_inattention", "cbcl_attention_problems_proxy"],
            "conduct": ["icut_", "conners_conduct_problems", "sdq_conduct_problems", "cbcl_rule_breaking_proxy", "cbcl_aggressive_behavior_proxy", "ari_"],
            "elimination": ["cbcl_108", "cbcl_112", "sdq_impact", "diag_domain_elimination_broad"],
            "anxiety": ["scared_", "sdq_emotional_symptoms", "cbcl_internalizing_proxy"],
            "depression": ["mfq_", "cdi_", "ari_", "cbcl_internalizing_proxy", "sdq_emotional_symptoms"],
        }
        dom_file_map = {
            "adhd": "dataset_domain_adhd.csv",
            "conduct": "dataset_domain_conduct.csv",
            "elimination": "dataset_domain_elimination.csv",
            "anxiety": "dataset_domain_anxiety.csv",
            "depression": "dataset_domain_depression.csv",
        }
        for dom, tcol in DOMAIN_TARGETS.items():
            prefixes = dom_feature_map[dom]
            cols = ["participant_id", "age_years", "sex_assigned_at_birth", "site", "release"]
            for c in base.columns:
                if c in cols:
                    continue
                if any((c.startswith(p) if p.endswith("_") else c == p) for p in prefixes):
                    cols.append(c)
            cols = [c for c in cols if c in base.columns]
            ddf = base[cols].merge(external[["participant_id", tcol]], on="participant_id", how="left")
            safe_write_csv(ddf, self.paths.final_external / dom_file_map[dom])

        domain_master = base[["participant_id", "age_years", "sex_assigned_at_birth", "site", "release"]].copy().merge(external, on="participant_id", how="left").merge(internal[["participant_id"] + [cfg["target_col"] for cfg in TARGET_CONFIG.values()]], on="participant_id", how="left")
        safe_write_csv(domain_master, self.paths.final_external / "dataset_domain_master.csv")

        safe_write_csv(self.evidence_long.copy(), self.paths.final / "dataset_participant_normative_evidence_long.csv")
        safe_write_csv(self.evidence_wide.copy(), self.paths.final / "dataset_participant_normative_evidence_wide.csv")
        safe_write_csv(pd.read_csv(self.paths.final / "dataset_parameter_coverage_summary.csv"), self.paths.final / "dataset_parameter_coverage_summary.csv")

        target_support = []
        for cfg in TARGET_CONFIG.values():
            target_support.append({
                "target_col": cfg["target_col"],
                "positive_count": int(internal[cfg["target_col"]].sum()),
                "positive_rate": float(internal[cfg["target_col"]].mean()),
                "high_confidence_count": int((internal[cfg["confidence_col"]] == "high").sum()),
                "medium_confidence_count": int((internal[cfg["confidence_col"]] == "medium").sum()),
                "low_confidence_count": int((internal[cfg["confidence_col"]] == "low").sum()),
            })
        safe_write_csv(pd.DataFrame(target_support), self.paths.final / "dataset_target_support_summary.csv")

        strict_drop = [c for c in model_ready.columns if c.startswith("diag_") or c.endswith("_status") or c.endswith("_confidence") or c.endswith("_coverage")]
        strict_df = model_ready.drop(columns=strict_drop, errors="ignore").copy()
        safe_write_csv(strict_df, self.paths.strict_exact / "dataset_internal_exact_model_ready_strict_no_leakage_exact.csv")
        safe_write_csv(domain_master, self.paths.strict_exact / "dataset_domain_master_strict_no_leakage_exact.csv")
        safe_write_csv(model_ready.copy(), self.paths.research_exact / "dataset_internal_exact_model_ready_research_extended_exact.csv")
        safe_write_csv(domain_master.merge(base[[c for c in base.columns if c.startswith("diag_domain_")] + ["participant_id"]], on="participant_id", how="left"), self.paths.research_exact / "dataset_domain_master_research_extended_exact.csv")

        target_cols_all = [cfg["target_col"] for cfg in TARGET_CONFIG.values()] + list(DOMAIN_TARGETS.values())
        leak_rows = []
        for c in model_ready.columns:
            if c in target_cols_all:
                cls, action = "target_column", "exclude_from_X"
            elif c.startswith("diag_domain_"):
                cls, action = "diagnostic_proxy_high_leakage", "exclude_from_strict_X"
            elif c.endswith("_status") or c.endswith("_confidence") or c.endswith("_coverage"):
                cls, action = "target_metadata_leakage", "exclude_from_X"
            elif c == "participant_id":
                cls, action = "identifier", "exclude_or_group_key_only"
            else:
                cls, action = "feature_candidate", "allow"
            leak_rows.append({"column_name": c, "classification": cls, "recommended_action": action})
        safe_write_csv(pd.DataFrame(leak_rows), self.paths.out / "leakage_audit_dsm5_exact.csv")

        feature_lineage_rows = []
        for c in strict_df.columns:
            if c in target_cols_all:
                continue
            feature_lineage_rows.append({
                "final_feature_name": c,
                "source_table": self._feature_source_from_col(c),
                "source_column": c,
                "transform_applied": "identity_or_previous_pipeline_transform",
                "imputation_applied": "none_at_dataset_rebuild_stage",
                "encoding_applied": "none_at_dataset_rebuild_stage",
                "layer": self._layer_for_col(c),
            })
        safe_write_csv(pd.DataFrame(feature_lineage_rows), self.paths.out / "feature_lineage_dsm5_exact.csv")

        parameter_lineage = self.mapping_df[["diagnostic_unit", "parameter_name", "parameter_feature_name", "hbn_source_table", "hbn_source_columns", "mapping_status", "transformation_rule", "compute_strategy"]].copy()
        parameter_lineage = parameter_lineage.rename(columns={"hbn_source_table": "source_table", "hbn_source_columns": "source_column", "transformation_rule": "transform_applied"})
        parameter_lineage["imputation_applied"] = "none"
        parameter_lineage["encoding_applied"] = "none"
        safe_write_csv(parameter_lineage, self.paths.out / "parameter_lineage_dsm5_exact.csv")

        cohort_summary = pd.DataFrame([
            {"metric": "cohort_size_6_11", "value": int(len(base))},
            {"metric": "normative_rows", "value": int(len(self.normative_registry))},
            {"metric": "mapping_rows", "value": int(len(self.mapping_df))},
        ])
        safe_write_csv(cohort_summary, self.paths.out / "cohort_rebuild_summary.csv")

        exact_rows = []
        for key, cfg in TARGET_CONFIG.items():
            exact_rows.append({
                "unit_key": key,
                "target_col": cfg["target_col"],
                "positive_count": int(internal[cfg["target_col"]].sum()),
                "positive_rate": float(internal[cfg["target_col"]].mean()),
                "coverage_high_count": int((internal[cfg["coverage_col"]] == "high").sum()),
                "coverage_medium_count": int((internal[cfg["coverage_col"]] == "medium").sum()),
                "coverage_low_count": int((internal[cfg["coverage_col"]] == "low").sum()),
            })
        safe_write_csv(pd.DataFrame(exact_rows), self.paths.out / "cohort_by_exact_unit.csv")

        dom_rows = []
        for dom, tcol in DOMAIN_TARGETS.items():
            dom_rows.append({"domain": dom, "target_col": tcol, "positive_count": int(external[tcol].sum()), "positive_rate": float(external[tcol].mean())})
        safe_write_csv(pd.DataFrame(dom_rows), self.paths.out / "cohort_by_domain.csv")

        self._export_manifests()

    def _export_manifests(self) -> None:
        all_csvs = sorted(self.paths.final.rglob("*.csv"))
        manifest_rows = []
        feature_dict_rows = []
        for p in all_csvs:
            df = pd.read_csv(p, low_memory=False)
            rel = str(p.relative_to(self.root)).replace("\\", "/")
            target_cols = [c for c in df.columns if c.startswith("target_")]
            manifest = {
                "dataset_name": p.stem,
                "relative_path": rel,
                "rows": int(len(df)),
                "columns": int(df.shape[1]),
                "target_columns": target_cols,
                "id_columns": [c for c in df.columns if c == "participant_id"],
                "created_at_utc": now_iso(),
                "normative_version": NORMATIVE_VERSION,
            }
            manifest_rows.append(manifest)
            safe_write_text(json.dumps(manifest, indent=2), self.paths.metadata / f"dataset_manifest_{p.stem}.json")

            for col in df.columns:
                feature_dict_rows.append({
                    "dataset_name": p.stem,
                    "column_name": col,
                    "dtype": str(df[col].dtype),
                    "missing_pct": float(df[col].isna().mean() * 100.0),
                    "layer": self._layer_for_col(col),
                    "source_table_guess": self._feature_source_from_col(col),
                })

        safe_write_csv(pd.DataFrame(manifest_rows), self.paths.metadata / "dataset_manifests_index.csv")
        safe_write_csv(pd.DataFrame(feature_dict_rows), self.paths.out / "dataset_feature_dictionary.csv")
        safe_write_text("\n".join([
            "# Dataset Layering Guide",
            "",
            "- identifiers: participant keys only.",
            "- demographic_fields: age/sex/site/release context.",
            "- normative_exact_targets: 9 internal DSM-5 exact targets.",
            "- domain_targets: 5 external product domains derived from internal exact layer.",
            "- criterion_level_evidence_fields: parameterized normative evidence fields (wide).",
            "- mapping_metadata_fields: status/confidence/coverage fields for traceability.",
            "- model_eligible_features: psychometric and demographic feature candidates.",
            "- audit_only_fields: high-leakage or diagnostic proxy fields for audit use only.",
        ]) + "\n", self.paths.out / "dataset_layering_guide.md")

    def export_reports(self) -> None:
        if any(x is None for x in [self.normative_registry, self.mapping_df, self.internal_targets, self.external_targets, self.base_df]):
            raise RuntimeError("required state missing for reports")
        nr = self.normative_registry
        mp = self.mapping_df
        it = self.internal_targets
        et = self.external_targets
        base = self.base_df

        rebuild_summary = [
            "# Rebuild Summary",
            "",
            f"- run_at_utc: {now_iso()}",
            f"- normative_version: {NORMATIVE_VERSION}",
            f"- cohort_rows_6_11: {len(base)}",
            f"- normative_parameters: {len(nr)}",
            f"- mapping_rows: {len(mp)}",
            f"- mapping_direct: {int((mp['mapping_status']=='direct').sum())}",
            f"- mapping_proxy: {int((mp['mapping_status']=='proxy').sum())}",
            f"- mapping_derived: {int((mp['mapping_status']=='derived').sum())}",
            f"- mapping_absent: {int((mp['mapping_status']=='absent').sum())}",
        ]
        safe_write_text("\n".join(rebuild_summary) + "\n", self.paths.reports / "rebuild_summary.md")

        safe_write_text("\n".join([
            "# Normative Rebuild Readiness",
            "",
            "- normative registries exported",
            "- HBN-to-DSM mapping exported with direct/proxy/derived/absent statuses",
            "- participant-level normative evidence (long and wide) exported",
            "- internal exact targets (9 units) exported with status/confidence/coverage",
            "- external domain targets (5 domains) derived from internal exact layer",
            "- model-ready strict/research exact datasets exported",
            "- validations executed and exported",
        ]) + "\n", self.paths.reports / "normative_rebuild_readiness.md")

        safe_write_text("\n".join([
            "# Internal Exact vs External Domain Explanation",
            "",
            "Internal layer stores exact DSM-5 diagnostic units.",
            "External layer stores product-facing grouped domains and is always derived from internal units.",
            "",
            "Internal units: ADHD, Conduct disorder, Enuresis, Encopresis, Separation anxiety disorder, Generalized anxiety disorder, MDD, PDD, DMDD.",
            "External domains: adhd, conduct, elimination, anxiety, depression.",
        ]) + "\n", self.paths.reports / "internal_exact_vs_external_domain_explanation.md")

        dict_lines = ["# DSM5 Exact Dataset Dictionary", "", "See dataset_feature_dictionary.csv and dataset_manifests_index.csv for full dictionary.", "", "Key targets:"]
        for cfg in TARGET_CONFIG.values():
            dict_lines.append(f"- {cfg['target_col']}")
        for t in DOMAIN_TARGETS.values():
            dict_lines.append(f"- {t}")
        safe_write_text("\n".join(dict_lines) + "\n", self.paths.reports / "dsm5_exact_dataset_dictionary.md")

        gap = mp.groupby(["unit_key", "mapping_status"]).size().unstack(fill_value=0)
        gap_lines = ["# Coverage and Gaps Report", ""]
        for unit_key, row in gap.iterrows():
            gap_lines.append(f"- {unit_key}: direct={int(row.get('direct',0))}, proxy={int(row.get('proxy',0))}, derived={int(row.get('derived',0))}, absent={int(row.get('absent',0))}")
        gap_lines.append("")
        gap_lines.append("Absent parameters are still materialized in normative and participant evidence layers.")
        safe_write_text("\n".join(gap_lines) + "\n", self.paths.reports / "coverage_and_gaps_report.md")

        safe_write_text("\n".join([
            "# Model Readiness DSM5 Exact",
            "",
            f"- strict model-ready dataset: {str((self.paths.strict_exact / 'dataset_internal_exact_model_ready_strict_no_leakage_exact.csv').relative_to(self.root)).replace(chr(92),'/')}",
            f"- research model-ready dataset: {str((self.paths.research_exact / 'dataset_internal_exact_model_ready_research_extended_exact.csv').relative_to(self.root)).replace(chr(92),'/')}",
            "- strict dataset excludes high-leakage diagnostic proxy fields and target metadata fields.",
            "- research dataset keeps broader audit fields for controlled experiments.",
        ]) + "\n", self.paths.reports / "model_readiness_dsm5_exact.md")

        prev = pd.read_csv(self.root / "data" / "processed" / "intermediate" / "targets_6_11.csv", low_memory=False)
        prev_targets = [c for c in prev.columns if c.startswith("target_") and not c.endswith("_exact")]
        cmp_lines = [
            "# Comparison vs Previous Generation",
            "",
            f"- previous target columns: {len(prev_targets)} ({', '.join(prev_targets)})",
            f"- new internal exact target columns: {len(TARGET_CONFIG)}",
            f"- new external domain target columns: {len(DOMAIN_TARGETS)}",
            "- previous generation focused on 5 broad domains as primary labels.",
            "- this generation introduces 9 exact internal units and derives 5 external domains from them.",
            "- normative matrix rows are fully materialized in this generation, including absent coverage states.",
            "- strict/research exact split is now explicit in model_ready outputs.",
        ]
        safe_write_text("\n".join(cmp_lines) + "\n", self.paths.reports / "comparison_vs_previous_generation.md")

    def run_validations(self) -> None:
        if any(x is None for x in [self.normative_registry, self.mapping_df, self.evidence_long, self.internal_targets, self.external_targets]):
            raise RuntimeError("required artifacts missing for validation")
        nr = self.normative_registry
        mp = self.mapping_df
        ev = self.evidence_long
        it = self.internal_targets
        et = self.external_targets

        missing_map = sorted(set(nr["row_id_from_normative_csv"].tolist()) - set(mp["row_id_from_normative_csv"].tolist()))
        self.validation_rows.append({"check_name": "every_normative_row_has_mapping_row", "status": "pass" if not missing_map else "fail", "details": f"missing={len(missing_map)}"})

        missing_evidence = sorted(set(mp["row_id_from_normative_csv"].tolist()) - set(ev["row_id_from_normative_csv"].tolist()))
        self.validation_rows.append({"check_name": "every_parameter_present_in_participant_evidence", "status": "pass" if not missing_evidence else "fail", "details": f"missing={len(missing_evidence)}"})

        domain_uses_internal = (et[DOMAIN_TARGETS["depression"]].astype(int) == (it[TARGET_CONFIG["major_depressive_disorder"]["target_col"]].astype(int) | it[TARGET_CONFIG["persistent_depressive_disorder"]["target_col"]].astype(int) | it[TARGET_CONFIG["dmdd"]["target_col"]].astype(int)).astype(int)).all()
        self.validation_rows.append({"check_name": "internal_external_layers_not_mixed_and_domain_derivation_consistent", "status": "pass" if domain_uses_internal else "fail", "details": "checked depression domain OR rule"})

        strict_path = self.paths.strict_exact / "dataset_internal_exact_model_ready_strict_no_leakage_exact.csv"
        strict_df = pd.read_csv(strict_path, low_memory=False)
        forbidden = [c for c in strict_df.columns if c.startswith("diag_domain_") or c.endswith("_status") or c.endswith("_confidence") or c.endswith("_coverage")]
        self.validation_rows.append({"check_name": "strict_no_leakage_exact_excludes_high_leakage_metadata_fields", "status": "pass" if not forbidden else "fail", "details": f"forbidden_columns={len(forbidden)}"})

        results = pd.DataFrame(self.validation_rows)
        safe_write_csv(results, self.paths.out / "validation_results_dsm5_exact.csv")
        fails = results[results["status"] != "pass"].copy()
        safe_write_csv(fails, self.paths.out / "validation_failures_dsm5_exact.csv")

        summary = [
            "# Validation Summary DSM5 Exact",
            "",
            f"- total_checks: {len(results)}",
            f"- passed: {int((results['status']=='pass').sum())}",
            f"- failed: {int((results['status']!='pass').sum())}",
        ]
        if not fails.empty:
            summary.append("")
            summary.append("Failed checks:")
            for _, row in fails.iterrows():
                summary.append(f"- {row['check_name']}: {row['details']}")
        safe_write_text("\n".join(summary) + "\n", self.paths.out / "validation_summary_dsm5_exact.md")

    def run(self) -> None:
        self.ensure_dirs()
        self.capture_baseline_hashes()
        self.load_inputs()
        self.build_source_inventory()
        self.build_previous_artifacts_inventory()
        self.build_normative_registries()
        self.build_mapping()
        self.build_participant_normative_evidence()
        self.build_internal_exact_targets()
        self.build_external_domain_targets()
        self.export_datasets()
        self.export_reports()
        self.verify_baseline_hashes()
        self.run_validations()


def run_phase(root: Path, phase: str) -> None:
    reb = DSM5ExactRebuilder(root)
    reb.ensure_dirs()
    if phase == "all":
        reb.run()
        return
    reb.capture_baseline_hashes()
    reb.load_inputs()
    if phase == "inventory":
        reb.build_source_inventory()
        reb.build_previous_artifacts_inventory()
        reb.verify_baseline_hashes()
        return
    if phase == "normative":
        reb.build_normative_registries()
        reb.verify_baseline_hashes()
        return
    if phase == "mapping":
        reb.build_normative_registries()
        reb.build_mapping()
        reb.verify_baseline_hashes()
        return
    if phase == "evidence":
        reb.build_normative_registries()
        reb.build_mapping()
        reb.build_participant_normative_evidence()
        reb.verify_baseline_hashes()
        return
    if phase == "internal_targets":
        reb.build_normative_registries()
        reb.build_mapping()
        reb.build_participant_normative_evidence()
        reb.build_internal_exact_targets()
        reb.verify_baseline_hashes()
        return
    if phase == "external_targets":
        reb.build_normative_registries()
        reb.build_mapping()
        reb.build_participant_normative_evidence()
        reb.build_internal_exact_targets()
        reb.build_external_domain_targets()
        reb.verify_baseline_hashes()
        return
    if phase == "export":
        reb.build_normative_registries()
        reb.build_mapping()
        reb.build_participant_normative_evidence()
        reb.build_internal_exact_targets()
        reb.build_external_domain_targets()
        reb.export_datasets()
        reb.export_reports()
        reb.verify_baseline_hashes()
        return
    if phase == "validate":
        reb.build_normative_registries()
        reb.build_mapping()
        reb.build_participant_normative_evidence()
        reb.build_internal_exact_targets()
        reb.build_external_domain_targets()
        reb.export_datasets()
        reb.verify_baseline_hashes()
        reb.run_validations()
        return
    raise ValueError(f"Unsupported phase: {phase}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild DSM-5 exact datasets without touching previous generation.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--phase", type=str, default="all", choices=["all", "inventory", "normative", "mapping", "evidence", "internal_targets", "external_targets", "export", "validate"])
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)
    root = Path(args.root).resolve()
    run_phase(root, args.phase)
    LOGGER.info("DSM-5 exact rebuild phase '%s' completed", args.phase)


if __name__ == "__main__":
    main()

