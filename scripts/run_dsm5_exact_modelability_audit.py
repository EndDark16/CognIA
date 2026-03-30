#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


LOGGER = logging.getLogger("dsm5-exact-modelability-audit")


UNIT_CONFIG: Dict[str, Dict[str, str]] = {
    "adhd": {
        "diagnostic_unit": "Trastorno por deficit de atencion/hiperactividad",
        "target_col": "target_adhd_exact",
        "status_col": "target_adhd_exact_status",
        "confidence_col": "target_adhd_exact_confidence",
        "coverage_col": "target_adhd_exact_coverage",
        "direct_count_col": "target_adhd_exact_direct_criteria_count",
        "proxy_count_col": "target_adhd_exact_proxy_criteria_count",
        "absent_count_col": "target_adhd_exact_absent_criteria_count",
        "dataset_file": "dataset_adhd_exact.csv",
        "domain": "adhd",
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
        "dataset_file": "dataset_conduct_disorder_exact.csv",
        "domain": "conduct",
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
        "dataset_file": "dataset_enuresis_exact.csv",
        "domain": "elimination",
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
        "dataset_file": "dataset_encopresis_exact.csv",
        "domain": "elimination",
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
        "dataset_file": "dataset_separation_anxiety_exact.csv",
        "domain": "anxiety",
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
        "dataset_file": "dataset_generalized_anxiety_exact.csv",
        "domain": "anxiety",
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
        "dataset_file": "dataset_mdd_exact.csv",
        "domain": "depression",
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
        "dataset_file": "dataset_pdd_exact.csv",
        "domain": "depression",
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
        "dataset_file": "dataset_dmdd_exact.csv",
        "domain": "depression",
    },
}


DOMAIN_TO_UNITS = {
    "adhd": ["adhd"],
    "conduct": ["conduct_disorder"],
    "elimination": ["enuresis", "encopresis"],
    "anxiety": ["separation_anxiety_disorder", "generalized_anxiety_disorder"],
    "depression": ["major_depressive_disorder", "persistent_depressive_disorder", "dmdd"],
}


def sentinel_files_for_base(base_subdir: str, strict_dir_name: str) -> List[str]:
    base = base_subdir.strip("/\\")
    return [
        f"{base}/normative/normative_parameter_registry.csv",
        f"{base}/mapping/parameter_to_hbn_mapping.csv",
        f"{base}/intermediate/participant_normative_evidence_long.csv",
        f"{base}/internal_exact_targets.csv",
        f"{base}/final/model_ready/{strict_dir_name}/dataset_internal_exact_model_ready_strict_no_leakage_exact.csv",
    ]


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


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


def clamp(x: float, low: float = 0.0, high: float = 100.0) -> float:
    return float(max(low, min(high, x)))


@dataclass
class AuditPaths:
    root: Path
    base: Path
    audit: Path
    reports: Path
    tables: Path
    diagnostics: Path
    artifacts: Path


class DSM5ExactModelabilityAuditor:
    def __init__(
        self,
        root: Path,
        base_subdir: str = "data/processed_dsm5_exact_v1",
        artifact_subdir: str = "artifacts/dsm5_exact_v1/modelability_audit",
        strict_dir_name: str = "strict_no_leakage_exact",
        audit_label: str = "dsm5_exact",
    ):
        base = root / Path(base_subdir)
        self.paths = AuditPaths(
            root=root,
            base=base,
            audit=base / "modelability_audit",
            reports=base / "modelability_audit" / "reports",
            tables=base / "modelability_audit" / "tables",
            diagnostics=base / "modelability_audit" / "diagnostics",
            artifacts=root / Path(artifact_subdir),
        )
        self.base_subdir = base_subdir
        self.strict_dir_name = strict_dir_name
        self.audit_label = audit_label
        self.sentinel_files = sentinel_files_for_base(base_subdir, strict_dir_name)
        self.sentinel_before: Dict[str, str] = {}

        self.normative_raw: Optional[pd.DataFrame] = None
        self.normative_units: Optional[pd.DataFrame] = None
        self.normative_params: Optional[pd.DataFrame] = None
        self.mapping: Optional[pd.DataFrame] = None
        self.evidence_long: Optional[pd.DataFrame] = None
        self.internal_targets: Optional[pd.DataFrame] = None
        self.strict_model_ready: Optional[pd.DataFrame] = None
        self.validation_results: Optional[pd.DataFrame] = None
        self.feature_lineage: Optional[pd.DataFrame] = None
        self.parameter_lineage: Optional[pd.DataFrame] = None
        self.leakage_audit: Optional[pd.DataFrame] = None

        self.unit_cov_matrix: Optional[pd.DataFrame] = None
        self.unit_type_cov: Optional[pd.DataFrame] = None
        self.core_criteria_audit: Optional[pd.DataFrame] = None
        self.cohort_support_by_unit: Optional[pd.DataFrame] = None
        self.target_strength: Optional[pd.DataFrame] = None
        self.feature_modelability: Optional[pd.DataFrame] = None
        self.methodological_risk: Optional[pd.DataFrame] = None
        self.modelability_index: Optional[pd.DataFrame] = None
        self.final_decisions: Optional[pd.DataFrame] = None
        self.next_actions: Optional[pd.DataFrame] = None

    def ensure_dirs(self) -> None:
        for d in [self.paths.audit, self.paths.reports, self.paths.tables, self.paths.diagnostics, self.paths.artifacts]:
            d.mkdir(parents=True, exist_ok=True)

    def capture_sentinels_before(self) -> None:
        hashes: Dict[str, str] = {}
        for rel in self.sentinel_files:
            p = self.paths.root / rel
            if p.exists():
                hashes[rel] = file_hash(p)
        self.sentinel_before = hashes
        safe_write_text(json.dumps({"captured_at": now_iso(), "hashes": hashes}, indent=2), self.paths.artifacts / "sentinel_before.json")

    def verify_sentinels_unchanged(self) -> None:
        changed: List[str] = []
        missing: List[str] = []
        after: Dict[str, str] = {}
        for rel, before_hash in self.sentinel_before.items():
            p = self.paths.root / rel
            if not p.exists():
                missing.append(rel)
                continue
            h = file_hash(p)
            after[rel] = h
            if h != before_hash:
                changed.append(rel)
        safe_write_text(
            json.dumps({"checked_at": now_iso(), "hashes": after, "changed": changed, "missing": missing}, indent=2),
            self.paths.artifacts / "sentinel_after.json",
        )
        status = "pass" if not changed and not missing else "fail"
        safe_write_csv(
            pd.DataFrame(
                [
                    {
                        "check_name": f"{self.audit_label}_source_files_unchanged_during_modelability_audit",
                        "status": status,
                        "changed_count": len(changed),
                        "missing_count": len(missing),
                        "changed_files": ";".join(changed),
                        "missing_files": ";".join(missing),
                    }
                ]
            ),
            self.paths.artifacts / "sentinel_integrity_check.csv",
        )

    def load_inputs(self) -> None:
        base = self.paths.base
        self.normative_raw = pd.read_csv(self.paths.root / "data" / "normative_matrix" / "normative_matrix_dsm5_v1.csv", low_memory=False)
        self.normative_units = pd.read_csv(base / "normative" / "normative_units_registry.csv", low_memory=False)
        self.normative_params = pd.read_csv(base / "normative" / "normative_parameter_registry.csv", low_memory=False)
        self.mapping = pd.read_csv(base / "mapping" / "parameter_to_hbn_mapping.csv", low_memory=False)
        self.evidence_long = pd.read_csv(base / "intermediate" / "participant_normative_evidence_long.csv", low_memory=False)
        self.internal_targets = pd.read_csv(base / "internal_exact_targets.csv", low_memory=False)
        self.strict_model_ready = pd.read_csv(
            base / "final" / "model_ready" / self.strict_dir_name / "dataset_internal_exact_model_ready_strict_no_leakage_exact.csv",
            low_memory=False,
        )
        self.validation_results = pd.read_csv(base / "validation_results_dsm5_exact.csv", low_memory=False)
        self.feature_lineage = pd.read_csv(base / "feature_lineage_dsm5_exact.csv", low_memory=False)
        self.parameter_lineage = pd.read_csv(base / "parameter_lineage_dsm5_exact.csv", low_memory=False)
        self.leakage_audit = pd.read_csv(base / "leakage_audit_dsm5_exact.csv", low_memory=False)
        LOGGER.info("Loaded DSM5 exact inputs for modelability audit")

    def build_input_inventory(self) -> None:
        rows: List[Dict[str, Any]] = []
        scan_roots = [
            self.paths.root / "data" / "normative_matrix",
            self.paths.base / "normative",
            self.paths.base / "mapping",
            self.paths.base / "intermediate",
            self.paths.base / "final" / "internal_exact",
            self.paths.base / "final" / "external_domains",
            self.paths.base / "final" / "model_ready" / "strict_no_leakage_exact",
            self.paths.base / "reports",
            self.paths.base,
        ]
        for r in scan_roots:
            if not r.exists():
                continue
            for p in sorted(x for x in r.rglob("*") if x.is_file()):
                stat = p.stat()
                rows.append(
                    {
                        "relative_path": str(p.relative_to(self.paths.root)).replace("\\", "/"),
                        "source_area": str(r.relative_to(self.paths.root)).replace("\\", "/"),
                        "extension": p.suffix.lower(),
                        "size_bytes": int(stat.st_size),
                        "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    }
                )
        inv = pd.DataFrame(rows)
        safe_write_csv(inv, self.paths.tables / "modelability_input_inventory.csv")

        summary = [
            "# Modelability Input Summary",
            "",
            f"- generated_at_utc: {now_iso()}",
            f"- inventory_files: {len(inv)}",
            f"- normative_rows_raw: {len(self.normative_raw)}",
            f"- normative_parameters: {len(self.normative_params)}",
            f"- mapping_rows: {len(self.mapping)}",
            f"- participant_evidence_rows: {len(self.evidence_long)}",
            f"- internal_target_rows: {len(self.internal_targets)}",
            f"- strict_model_ready_rows: {len(self.strict_model_ready)}",
            "",
            "This audit uses existing DSM5 exact outputs as immutable source artifacts.",
        ]
        safe_write_text("\n".join(summary) + "\n", self.paths.reports / "modelability_input_summary.md")

    def _parameter_type_bucket(self, row: pd.Series) -> str:
        def has_text(value: Any) -> bool:
            if pd.isna(value):
                return False
            s = str(value).strip().lower()
            return s not in {"", "nan", "none", "null"}

        ptype = str(row.get("parameter_type", "")).lower()
        section = str(row.get("section", "")).lower()
        pname = str(row.get("parameter_name", "")).lower()
        dsm_block = str(row.get("dsm_block", "")).lower()

        if section == "master_units" or ptype == "master_unit":
            return "coding_registration"
        if has_text(row.get("specifier_rule", "")) or ptype == "specifier" or "especificador" in dsm_block:
            return "specifiers"
        if has_text(row.get("severity_rule", "")):
            return "severity"
        if has_text(row.get("remission_rule", "")):
            return "remission"
        if has_text(row.get("exclusion_rule", "")) or has_text(row.get("coexistence_rule", "")):
            return "exclusions"
        if has_text(row.get("impairment_rule", "")):
            return "impairment"
        if has_text(row.get("context_rule", "")) or "context" in pname or "setting" in pname:
            return "context"
        if has_text(row.get("onset_rule", "")) or "onset" in pname or "before" in pname:
            return "onset"
        if has_text(row.get("duration_rule", "")) or has_text(row.get("frequency_rule", "")) or any(x in pname for x in ["duration", "frequency", "persistence", "course"]):
            return "temporality"
        if str(row.get("required_for_diagnosis", "")).lower() == "yes" and ptype in {"symptom", "structural"}:
            return "criteria_nucleares"
        if ptype in {"symptom", "structural"}:
            return "criterios_adicionales"
        return "coding_registration"

    def audit_unit_coverage(self) -> None:
        mp = self.mapping.copy()
        mp = mp[mp["unit_key"].isin(UNIT_CONFIG.keys())].copy()
        mp["parameter_bucket"] = mp.apply(self._parameter_type_bucket, axis=1)

        cov_rows: List[Dict[str, Any]] = []
        for unit, cfg in UNIT_CONFIG.items():
            sub = mp[mp["unit_key"] == unit]
            total = int(len(sub))
            c_direct = int((sub["mapping_status"] == "direct").sum())
            c_proxy = int((sub["mapping_status"] == "proxy").sum())
            c_derived = int((sub["mapping_status"] == "derived").sum())
            c_absent = int((sub["mapping_status"] == "absent").sum())
            cov_rows.append(
                {
                    "unit_key": unit,
                    "diagnostic_unit": cfg["diagnostic_unit"],
                    "total_normative_parameters": total,
                    "total_direct_parameters": c_direct,
                    "total_proxy_parameters": c_proxy,
                    "total_derived_parameters": c_derived,
                    "total_absent_parameters": c_absent,
                    "direct_ratio": float(c_direct / total) if total else 0.0,
                    "proxy_ratio": float(c_proxy / total) if total else 0.0,
                    "derived_ratio": float(c_derived / total) if total else 0.0,
                    "absent_ratio": float(c_absent / total) if total else 0.0,
                }
            )
        unit_cov = pd.DataFrame(cov_rows)
        self.unit_cov_matrix = unit_cov
        safe_write_csv(unit_cov, self.paths.tables / "unit_parameter_coverage_matrix.csv")

        type_rows: List[Dict[str, Any]] = []
        for (unit, bucket), grp in mp.groupby(["unit_key", "parameter_bucket"]):
            total = int(len(grp))
            direct = int((grp["mapping_status"] == "direct").sum())
            proxy = int((grp["mapping_status"] == "proxy").sum())
            derived = int((grp["mapping_status"] == "derived").sum())
            absent = int((grp["mapping_status"] == "absent").sum())
            type_rows.append(
                {
                    "unit_key": unit,
                    "diagnostic_unit": UNIT_CONFIG[unit]["diagnostic_unit"],
                    "parameter_bucket": bucket,
                    "total_parameters": total,
                    "direct_parameters": direct,
                    "proxy_parameters": proxy,
                    "derived_parameters": derived,
                    "absent_parameters": absent,
                    "direct_ratio": float(direct / total) if total else 0.0,
                    "proxy_ratio": float(proxy / total) if total else 0.0,
                    "derived_ratio": float(derived / total) if total else 0.0,
                    "absent_ratio": float(absent / total) if total else 0.0,
                }
            )
        type_cov = pd.DataFrame(type_rows).sort_values(["unit_key", "parameter_bucket"])
        self.unit_type_cov = type_cov
        safe_write_csv(type_cov, self.paths.tables / "unit_parameter_type_coverage_matrix.csv")

        summary_lines = ["# Unit Coverage Summary", ""]
        for _, row in unit_cov.sort_values("unit_key").iterrows():
            summary_lines.append(
                f"- {row['unit_key']}: total={int(row['total_normative_parameters'])}, direct={int(row['total_direct_parameters'])}, proxy={int(row['total_proxy_parameters'])}, derived={int(row['total_derived_parameters'])}, absent={int(row['total_absent_parameters'])}"
            )
        safe_write_text("\n".join(summary_lines) + "\n", self.paths.reports / "unit_coverage_summary.md")

    def _component_status(self, grp: pd.DataFrame) -> str:
        if grp.empty:
            return "absent"
        direct = int((grp["mapping_status"] == "direct").sum())
        proxy = int((grp["mapping_status"] == "proxy").sum())
        derived = int((grp["mapping_status"] == "derived").sum())
        absent = int((grp["mapping_status"] == "absent").sum())
        if direct > 0 and absent == 0:
            return "directly_covered"
        if proxy > 0 and direct == 0 and absent == 0:
            return "proxy_covered"
        if (direct + proxy + derived) > 0 and absent > 0:
            return "partially_covered"
        if (proxy + derived) > 0 and absent == 0:
            return "partially_covered"
        return "absent"

    def audit_core_criteria_sufficiency(self) -> None:
        if self.unit_type_cov is None:
            self.audit_unit_coverage()
        mp = self.mapping.copy()
        mp = mp[mp["unit_key"].isin(UNIT_CONFIG.keys())].copy()
        mp["parameter_bucket"] = mp.apply(self._parameter_type_bucket, axis=1)

        def pick_component(df: pd.DataFrame, component: str) -> pd.DataFrame:
            if component == "sintomas_nucleares":
                return df[df["parameter_bucket"] == "criteria_nucleares"]
            if component == "duration_frequency":
                return df[df["parameter_bucket"] == "temporality"]
            if component == "onset":
                return df[df["parameter_bucket"] == "onset"]
            if component == "context":
                return df[df["parameter_bucket"] == "context"]
            if component == "impairment":
                return df[df["parameter_bucket"] == "impairment"]
            if component == "exclusions":
                return df[df["parameter_bucket"] == "exclusions"]
            return df.iloc[0:0]

        components = ["sintomas_nucleares", "duration_frequency", "onset", "context", "impairment", "exclusions"]
        rows: List[Dict[str, Any]] = []
        for unit, cfg in UNIT_CONFIG.items():
            usub = mp[mp["unit_key"] == unit]
            for comp in components:
                csub = pick_component(usub, comp)
                total = int(len(csub))
                status = self._component_status(csub)
                rows.append(
                    {
                        "unit_key": unit,
                        "diagnostic_unit": cfg["diagnostic_unit"],
                        "component": comp,
                        "component_total_parameters": total,
                        "direct_parameters": int((csub["mapping_status"] == "direct").sum()) if total else 0,
                        "proxy_parameters": int((csub["mapping_status"] == "proxy").sum()) if total else 0,
                        "derived_parameters": int((csub["mapping_status"] == "derived").sum()) if total else 0,
                        "absent_parameters": int((csub["mapping_status"] == "absent").sum()) if total else 0,
                        "coverage_status": status,
                    }
                )
        core = pd.DataFrame(rows)
        self.core_criteria_audit = core
        safe_write_csv(core, self.paths.tables / "core_criteria_coverage_audit.csv")

        gaps = core[core["coverage_status"].isin(["partially_covered", "absent"])].copy()
        safe_write_csv(gaps, self.paths.diagnostics / "core_criteria_gaps_by_unit.csv")
        safe_write_csv(gaps, self.paths.tables / "core_criteria_gaps_by_unit.csv")

        decision_lines = ["# Core Criteria Sufficiency Decision", ""]
        for unit in UNIT_CONFIG:
            us = core[core["unit_key"] == unit]
            cstats = us.set_index("component")["coverage_status"].to_dict()
            good_core = cstats.get("sintomas_nucleares") in {"directly_covered", "proxy_covered"}
            good_imp = cstats.get("impairment") in {"directly_covered", "proxy_covered", "partially_covered"}
            good_excl = cstats.get("exclusions") in {"directly_covered", "proxy_covered", "partially_covered"}
            temporal_ok = cstats.get("duration_frequency") in {"directly_covered", "proxy_covered", "partially_covered"}
            if good_core and good_imp and good_excl and temporal_ok:
                suf = "sufficient_for_controlled_training"
            elif good_core and (good_imp or good_excl):
                suf = "partially_sufficient_experimental"
            else:
                suf = "insufficient_core_support"
            decision_lines.append(f"- {unit}: {suf}")
        safe_write_text("\n".join(decision_lines) + "\n", self.paths.reports / "core_criteria_sufficiency_decision.md")

    def _support_class(self, row: pd.Series) -> str:
        total = float(row["core_total_parameters"])
        if total <= 0:
            return "predominantly_absent"
        covered_ratio = float(row["core_covered_ratio"])
        absent_ratio = float(row["core_absent_ratio"])
        direct = int(row["core_direct"])
        proxy = int(row["core_proxy"])
        no_obs_ratio = float(row["core_no_observed_ratio"])
        if absent_ratio >= 0.5 or covered_ratio < 0.2:
            return "predominantly_absent"
        if covered_ratio >= 0.7 and no_obs_ratio <= 0.2:
            return "sufficient_core_coverage"
        if direct == 0 and proxy > 0 and covered_ratio >= 0.4:
            return "evidence_only_proxy"
        if covered_ratio >= 0.4:
            return "partial_core_coverage"
        return "minimal_insufficient"

    def audit_cohort_support(self) -> None:
        if self.core_criteria_audit is None:
            self.audit_core_criteria_sufficiency()
        ev = self.evidence_long.copy()
        mp = self.mapping[["row_id_from_normative_csv"]].copy()
        mp["row_id_from_normative_csv"] = pd.to_numeric(mp["row_id_from_normative_csv"], errors="coerce")
        mp["parameter_bucket"] = self.mapping.apply(self._parameter_type_bucket, axis=1).values
        ev["row_id_from_normative_csv"] = pd.to_numeric(ev["row_id_from_normative_csv"], errors="coerce")
        ev = ev.merge(mp, on=["row_id_from_normative_csv"], how="left")
        ev = ev[ev["unit_key"].isin(UNIT_CONFIG.keys())].copy()
        ev_core = ev[ev["parameter_bucket"].isin(["criteria_nucleares", "temporality", "onset", "context", "impairment", "exclusions"])].copy()

        pivot = (
            ev_core.groupby(["participant_id", "unit_key", "evidence_status"])
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        for c in ["direct", "proxy", "derived", "no_observed", "absent"]:
            if c not in pivot.columns:
                pivot[c] = 0
        pivot["core_total_parameters"] = pivot[["direct", "proxy", "derived", "no_observed", "absent"]].sum(axis=1)
        pivot["core_covered"] = pivot[["direct", "proxy", "derived"]].sum(axis=1)
        pivot["core_covered_ratio"] = pivot["core_covered"] / pivot["core_total_parameters"].replace({0: np.nan})
        pivot["core_absent_ratio"] = pivot["absent"] / pivot["core_total_parameters"].replace({0: np.nan})
        pivot["core_no_observed_ratio"] = pivot["no_observed"] / pivot["core_total_parameters"].replace({0: np.nan})
        pivot = pivot.rename(columns={"direct": "core_direct", "proxy": "core_proxy", "derived": "core_derived", "no_observed": "core_no_observed", "absent": "core_absent"})
        pivot["core_covered_ratio"] = pivot["core_covered_ratio"].fillna(0.0)
        pivot["core_absent_ratio"] = pivot["core_absent_ratio"].fillna(1.0)
        pivot["core_no_observed_ratio"] = pivot["core_no_observed_ratio"].fillna(0.0)
        pivot["support_quality"] = pivot.apply(self._support_class, axis=1)

        dist = (
            pivot.groupby(["unit_key", "support_quality"])
            .size()
            .reset_index(name="participants")
            .sort_values(["unit_key", "support_quality"])
        )
        safe_write_csv(dist, self.paths.diagnostics / "participant_support_quality_distribution.csv")
        safe_write_csv(dist, self.paths.tables / "participant_support_quality_distribution.csv")

        support_rows: List[Dict[str, Any]] = []
        usable_rows: List[Dict[str, Any]] = []
        pn_rows: List[Dict[str, Any]] = []

        target_df = self.internal_targets.copy()
        for unit, cfg in UNIT_CONFIG.items():
            us = pivot[pivot["unit_key"] == unit].copy()
            total = int(len(us))
            counts = us["support_quality"].value_counts().to_dict()
            sufficient = int(counts.get("sufficient_core_coverage", 0))
            partial = int(counts.get("partial_core_coverage", 0))
            minimal = int(counts.get("minimal_insufficient", 0))
            proxy_only = int(counts.get("evidence_only_proxy", 0))
            absent = int(counts.get("predominantly_absent", 0))
            support_rows.append(
                {
                    "unit_key": unit,
                    "diagnostic_unit": cfg["diagnostic_unit"],
                    "participants_total": total,
                    "coverage_sufficient_core": sufficient,
                    "coverage_partial_core": partial,
                    "coverage_minimal_insufficient": minimal,
                    "coverage_evidence_only_proxy": proxy_only,
                    "coverage_predominantly_absent": absent,
                    "ratio_sufficient_core": float(sufficient / total) if total else 0.0,
                    "ratio_partial_core": float(partial / total) if total else 0.0,
                    "ratio_proxy_only": float(proxy_only / total) if total else 0.0,
                    "ratio_predominantly_absent": float(absent / total) if total else 0.0,
                    "avg_core_covered_ratio": float(us["core_covered_ratio"].mean()) if total else 0.0,
                    "avg_core_absent_ratio": float(us["core_absent_ratio"].mean()) if total else 1.0,
                }
            )

            unit_target = target_df[["participant_id", cfg["target_col"], cfg["status_col"]]].copy()
            unit_support = us.merge(unit_target, on="participant_id", how="left")
            unit_support[cfg["target_col"]] = pd.to_numeric(unit_support[cfg["target_col"]], errors="coerce").fillna(0).astype(int)
            positive = int(unit_support[cfg["target_col"]].sum())
            negative = int((unit_support[cfg["target_col"]] == 0).sum())
            usable_mask = unit_support["support_quality"].isin(["sufficient_core_coverage", "partial_core_coverage"])
            unusable_mask = unit_support["support_quality"].isin(["minimal_insufficient", "predominantly_absent"])
            ambiguous_mask = unit_support["support_quality"].isin(["evidence_only_proxy", "partial_core_coverage"]) & unit_support[cfg["status_col"]].isin(["proxy", "broad_proxy", "weak_proxy", "proxy_with_broad_support"])
            pn_rows.append(
                {
                    "unit_key": unit,
                    "diagnostic_unit": cfg["diagnostic_unit"],
                    "positives_exact": positive,
                    "negatives_usable_pool": negative,
                    "positives_with_usable_support": int((unit_support[cfg["target_col"]] == 1).where(usable_mask, False).sum()),
                    "negatives_with_usable_support": int((unit_support[cfg["target_col"]] == 0).where(usable_mask, False).sum()),
                    "cases_ambiguous": int(ambiguous_mask.sum()),
                    "cases_unusable": int(unusable_mask.sum()),
                }
            )
            usable_rows.append(
                {
                    "unit_key": unit,
                    "diagnostic_unit": cfg["diagnostic_unit"],
                    "participants_usable": int(usable_mask.sum()),
                    "participants_ambiguous": int(ambiguous_mask.sum()),
                    "participants_unusable": int(unusable_mask.sum()),
                    "participants_proxy_only": int((unit_support["support_quality"] == "evidence_only_proxy").sum()),
                }
            )

        cohort_support = pd.DataFrame(support_rows).sort_values("unit_key")
        self.cohort_support_by_unit = cohort_support
        safe_write_csv(cohort_support, self.paths.tables / "cohort_support_by_unit.csv")
        safe_write_csv(pd.DataFrame(usable_rows).sort_values("unit_key"), self.paths.diagnostics / "usable_participants_by_unit.csv")
        safe_write_csv(pd.DataFrame(pn_rows).sort_values("unit_key"), self.paths.diagnostics / "positive_negative_support_by_unit.csv")
        safe_write_csv(pd.DataFrame(usable_rows).sort_values("unit_key"), self.paths.tables / "usable_participants_by_unit.csv")
        safe_write_csv(pd.DataFrame(pn_rows).sort_values("unit_key"), self.paths.tables / "positive_negative_support_by_unit.csv")

    def _classify_target_strength(self, positive_count: int, direct_support_ratio: float, proxy_dependence_ratio: float, low_coverage_ratio: float, avg_absent_criteria: float) -> str:
        if positive_count < 30:
            return "pseudo_target_risk"
        if direct_support_ratio >= 0.40 and proxy_dependence_ratio <= 0.75 and low_coverage_ratio <= 0.30 and avg_absent_criteria <= 4.0:
            return "strong_target"
        if direct_support_ratio >= 0.25 and proxy_dependence_ratio <= 0.90 and low_coverage_ratio <= 0.50:
            return "acceptable_target"
        if direct_support_ratio >= 0.10 and proxy_dependence_ratio <= 0.98:
            return "weak_target"
        return "pseudo_target_risk"

    def audit_target_strength(self) -> None:
        t = self.internal_targets.copy()
        rows: List[Dict[str, Any]] = []
        for unit, cfg in UNIT_CONFIG.items():
            tc = cfg["target_col"]
            sc = cfg["status_col"]
            cc = cfg["confidence_col"]
            covc = cfg["coverage_col"]
            dc = cfg["direct_count_col"]
            pc = cfg["proxy_count_col"]
            ac = cfg["absent_count_col"]

            sub = t[[tc, sc, cc, covc, dc, pc, ac]].copy()
            sub[tc] = pd.to_numeric(sub[tc], errors="coerce").fillna(0).astype(int)
            pos = sub[sub[tc] == 1].copy()
            pcount = int(len(pos))
            if pcount == 0:
                rows.append(
                    {
                        "unit_key": unit,
                        "diagnostic_unit": cfg["diagnostic_unit"],
                        "positive_count": 0,
                        "positive_rate": 0.0,
                        "direct_support_ratio": 0.0,
                        "proxy_dependence_ratio": 1.0,
                        "low_coverage_ratio": 1.0,
                        "avg_direct_criteria_count_positive": 0.0,
                        "avg_proxy_criteria_count_positive": 0.0,
                        "avg_absent_criteria_count_positive": 0.0,
                        "target_strength_class": "pseudo_target_risk",
                    }
                )
                continue

            direct_like = pos[sc].isin(["direct", "direct_plus_proxy", "proxy_with_broad_support"]).mean()
            proxy_like = pos[sc].isin(["proxy", "broad_proxy", "weak_proxy", "proxy_with_broad_support"]).mean()
            low_cov = (pos[covc] == "low").mean()
            avg_direct = float(pd.to_numeric(pos[dc], errors="coerce").fillna(0).mean())
            avg_proxy = float(pd.to_numeric(pos[pc], errors="coerce").fillna(0).mean())
            avg_abs = float(pd.to_numeric(pos[ac], errors="coerce").fillna(0).mean())
            cls = self._classify_target_strength(
                positive_count=pcount,
                direct_support_ratio=float(direct_like),
                proxy_dependence_ratio=float(proxy_like),
                low_coverage_ratio=float(low_cov),
                avg_absent_criteria=float(avg_abs),
            )
            rows.append(
                {
                    "unit_key": unit,
                    "diagnostic_unit": cfg["diagnostic_unit"],
                    "positive_count": pcount,
                    "positive_rate": float(sub[tc].mean()),
                    "direct_support_ratio": float(direct_like),
                    "proxy_dependence_ratio": float(proxy_like),
                    "low_coverage_ratio": float(low_cov),
                    "confidence_high_ratio_positive": float((pos[cc] == "high").mean()),
                    "confidence_medium_ratio_positive": float((pos[cc] == "medium").mean()),
                    "confidence_low_ratio_positive": float((pos[cc] == "low").mean()),
                    "avg_direct_criteria_count_positive": avg_direct,
                    "avg_proxy_criteria_count_positive": avg_proxy,
                    "avg_absent_criteria_count_positive": avg_abs,
                    "target_strength_class": cls,
                }
            )
        out = pd.DataFrame(rows).sort_values("unit_key")
        self.target_strength = out
        safe_write_csv(out, self.paths.tables / "target_strength_audit.csv")

        lines = ["# Target Build Quality Report", ""]
        for _, r in out.iterrows():
            lines.append(
                f"- {r['unit_key']}: {r['target_strength_class']} (positive_count={int(r['positive_count'])}, direct_support_ratio={r['direct_support_ratio']:.3f}, proxy_dependence_ratio={r['proxy_dependence_ratio']:.3f})"
            )
        safe_write_text("\n".join(lines) + "\n", self.paths.reports / "target_build_quality_report.md")

    def _is_specific_feature(self, unit: str, feature: str) -> bool:
        patterns = {
            "adhd": [r"^swan_", r"^conners_", r"sdq_hyperactivity_inattention", r"cbcl_attention_problems_proxy"],
            "conduct_disorder": [r"^icut_", r"conners_conduct_problems", r"sdq_conduct_problems", r"cbcl_rule_breaking_proxy", r"cbcl_aggressive_behavior_proxy", r"^ari_"],
            "enuresis": [r"^cbcl_108$"],
            "encopresis": [r"^cbcl_112$"],
            "separation_anxiety_disorder": [r"^scared_p_", r"^scared_sr_", r"separation"],
            "generalized_anxiety_disorder": [r"^scared_p_", r"^scared_sr_", r"generalized"],
            "major_depressive_disorder": [r"^mfq_", r"^cdi_"],
            "persistent_depressive_disorder": [r"^mfq_", r"^cdi_"],
            "dmdd": [r"^ari_"],
        }
        for pat in patterns.get(unit, []):
            if re.search(pat, feature):
                return True
        return False

    def _is_transdiagnostic_feature(self, feature: str) -> bool:
        return bool(re.search(r"^(sdq_|cbcl_|ari_|has_)", feature))

    def audit_feature_modelability(self) -> None:
        rows: List[Dict[str, Any]] = []
        spec_rows: List[Dict[str, Any]] = []
        base_dir = self.paths.base / "final" / "internal_exact"

        metadata_exact_suffixes = ("_status", "_confidence", "_coverage", "_criteria_count")
        id_cols = {"participant_id", "age_years", "sex_assigned_at_birth", "site", "release"}

        for unit, cfg in UNIT_CONFIG.items():
            p = base_dir / cfg["dataset_file"]
            df = pd.read_csv(p, low_memory=False)
            feature_cols = [
                c
                for c in df.columns
                if c not in id_cols
                and not c.startswith("target_")
                and not any(c.endswith(s) for s in metadata_exact_suffixes)
            ]
            if cfg["target_col"] in feature_cols:
                feature_cols.remove(cfg["target_col"])
            n_total = len(feature_cols)
            if n_total == 0:
                rows.append(
                    {
                        "unit_key": unit,
                        "diagnostic_unit": cfg["diagnostic_unit"],
                        "eligible_feature_count_strict": 0,
                        "features_with_sufficient_coverage": 0,
                        "clinical_specific_feature_count": 0,
                        "clinical_specific_with_sufficient_coverage": 0,
                        "transdiagnostic_feature_count": 0,
                        "clinical_specificity_ratio": 0.0,
                        "sufficient_coverage_ratio": 0.0,
                        "feature_signal_class": "sparse_specific_signal",
                    }
                )
                continue

            missing = df[feature_cols].isna().mean()
            sufficient = missing[missing <= 0.40]
            specific = [c for c in feature_cols if self._is_specific_feature(unit, c)]
            specific_sufficient = [c for c in specific if missing.get(c, 1.0) <= 0.40]
            transdiag = [c for c in feature_cols if self._is_transdiagnostic_feature(c)]

            if len(specific_sufficient) >= 8:
                signal = "high_specific_signal"
            elif len(specific_sufficient) >= 4:
                signal = "moderate_specific_signal"
            elif len(specific_sufficient) >= 2:
                signal = "low_specific_signal"
            else:
                signal = "sparse_specific_signal"

            rows.append(
                {
                    "unit_key": unit,
                    "diagnostic_unit": cfg["diagnostic_unit"],
                    "eligible_feature_count_strict": int(n_total),
                    "features_with_sufficient_coverage": int(len(sufficient)),
                    "clinical_specific_feature_count": int(len(specific)),
                    "clinical_specific_with_sufficient_coverage": int(len(specific_sufficient)),
                    "transdiagnostic_feature_count": int(len(transdiag)),
                    "clinical_specificity_ratio": float(len(specific) / n_total) if n_total else 0.0,
                    "sufficient_coverage_ratio": float(len(sufficient) / n_total) if n_total else 0.0,
                    "feature_signal_class": signal,
                }
            )
            for c in feature_cols:
                spec_rows.append(
                    {
                        "unit_key": unit,
                        "feature_name": c,
                        "is_clinically_specific": int(c in specific),
                        "is_transdiagnostic": int(c in transdiag),
                        "missing_ratio": float(missing.get(c, 1.0)),
                        "sufficient_coverage": int(c in sufficient.index),
                    }
                )

        feat = pd.DataFrame(rows).sort_values("unit_key")
        self.feature_modelability = feat
        safe_write_csv(feat, self.paths.tables / "feature_modelability_by_unit.csv")
        safe_write_csv(pd.DataFrame(spec_rows).sort_values(["unit_key", "feature_name"]), self.paths.diagnostics / "clinical_specificity_by_unit.csv")
        safe_write_csv(pd.DataFrame(spec_rows).sort_values(["unit_key", "feature_name"]), self.paths.tables / "clinical_specificity_by_unit.csv")

        lines = ["# Feature Signal Risk Report", ""]
        for _, r in feat.iterrows():
            lines.append(
                f"- {r['unit_key']}: signal={r['feature_signal_class']}, specific={int(r['clinical_specific_feature_count'])}, specific_sufficient={int(r['clinical_specific_with_sufficient_coverage'])}, transdiagnostic={int(r['transdiagnostic_feature_count'])}"
            )
        safe_write_text("\n".join(lines) + "\n", self.paths.reports / "feature_signal_risk_report.md")

    def _risk_level_from_score(self, x: float) -> str:
        if x >= 3.0:
            return "critical"
        if x >= 2.2:
            return "high"
        if x >= 1.2:
            return "moderate"
        return "low"

    def _risk_to_penalty(self, level: str) -> float:
        return {"low": 5.0, "moderate": 12.0, "high": 22.0, "critical": 35.0}.get(level, 22.0)

    def audit_methodological_risk(self) -> None:
        if self.unit_cov_matrix is None:
            self.audit_unit_coverage()
        if self.core_criteria_audit is None:
            self.audit_core_criteria_sufficiency()
        if self.cohort_support_by_unit is None:
            self.audit_cohort_support()
        if self.target_strength is None:
            self.audit_target_strength()
        if self.feature_modelability is None:
            self.audit_feature_modelability()

        cov = self.unit_cov_matrix.set_index("unit_key")
        core = self.core_criteria_audit.copy()
        cohort = self.cohort_support_by_unit.set_index("unit_key")
        tstr = self.target_strength.set_index("unit_key")
        feat = self.feature_modelability.set_index("unit_key")

        rows: List[Dict[str, Any]] = []
        for unit, cfg in UNIT_CONFIG.items():
            uc = cov.loc[unit]
            us_core = core[core["unit_key"] == unit]
            component_statuses = us_core.set_index("component")["coverage_status"].to_dict()
            absent_components = sum(v == "absent" for v in component_statuses.values())
            partial_components = sum(v == "partially_covered" for v in component_statuses.values())

            proxy_ratio = float(uc["proxy_ratio"])
            absent_ratio = float(uc["absent_ratio"])
            direct_ratio = float(uc["direct_ratio"])

            proxy_dependence = float(tstr.loc[unit, "proxy_dependence_ratio"])
            target_strength_class = str(tstr.loc[unit, "target_strength_class"])
            positives = int(tstr.loc[unit, "positive_count"])
            low_cov_pos = float(tstr.loc[unit, "low_coverage_ratio"])

            participants_total = int(cohort.loc[unit, "participants_total"])
            sufficient_ratio = float(cohort.loc[unit, "ratio_sufficient_core"])
            partial_ratio = float(cohort.loc[unit, "ratio_partial_core"])
            proxy_only_ratio = float(cohort.loc[unit, "ratio_proxy_only"])

            specific_ratio = float(feat.loc[unit, "clinical_specificity_ratio"])
            signal_class = str(feat.loc[unit, "feature_signal_class"])

            score_proxy = 3.2 if (proxy_ratio > 0.8 and proxy_dependence > 0.9) else 2.4 if proxy_ratio > 0.7 else 1.5 if proxy_ratio > 0.5 else 0.8
            score_absent = 3.2 if absent_components >= 3 else 2.6 if absent_components >= 2 else 1.8 if partial_components >= 3 else 1.0
            score_sample = 3.2 if positives < 80 else 2.4 if positives < 150 else 1.2
            score_target = 3.2 if target_strength_class == "pseudo_target_risk" else 2.2 if target_strength_class == "weak_target" else 1.2 if target_strength_class == "acceptable_target" else 0.8
            score_precision = 3.0 if (direct_ratio < 0.05 and absent_ratio > 0.4) else 2.2 if direct_ratio < 0.1 else 1.2
            score_train_without_support = 3.0 if (sufficient_ratio < 0.2 and partial_ratio < 0.25) else 2.2 if sufficient_ratio < 0.3 else 1.2
            score_overclaim = 3.0 if (direct_ratio < 0.05 and proxy_only_ratio > 0.4) else 2.0 if direct_ratio < 0.1 else 1.0

            global_score = float(
                np.mean(
                    [
                        score_proxy,
                        score_absent,
                        score_sample,
                        score_target,
                        score_precision,
                        score_train_without_support,
                        score_overclaim,
                    ]
                )
            )
            global_level = self._risk_level_from_score(global_score)

            rows.append(
                {
                    "unit_key": unit,
                    "diagnostic_unit": cfg["diagnostic_unit"],
                    "risk_of_overclaiming_dsm_exactness": self._risk_level_from_score(score_overclaim),
                    "risk_of_proxy_overdependence": self._risk_level_from_score(score_proxy),
                    "risk_of_absent_core_criteria": self._risk_level_from_score(score_absent),
                    "risk_of_low_sample_support": self._risk_level_from_score(score_sample),
                    "risk_of_target_instability": self._risk_level_from_score(score_target),
                    "risk_of_false_clinical_precision": self._risk_level_from_score(score_precision),
                    "risk_of_training_without_sufficient_normative_support": self._risk_level_from_score(score_train_without_support),
                    "methodological_risk_global": global_level,
                    "methodological_risk_score": round(global_score, 4),
                    "proxy_ratio": proxy_ratio,
                    "absent_ratio": absent_ratio,
                    "direct_ratio": direct_ratio,
                    "participants_total": participants_total,
                    "positive_count": positives,
                    "feature_signal_class": signal_class,
                    "clinical_specificity_ratio": specific_ratio,
                    "low_coverage_ratio_positive": low_cov_pos,
                }
            )

        out = pd.DataFrame(rows).sort_values("unit_key")
        self.methodological_risk = out
        safe_write_csv(out, self.paths.tables / "methodological_risk_by_unit.csv")

        lines = ["# Overclaiming Risk Report", ""]
        for _, r in out.iterrows():
            lines.append(
                f"- {r['unit_key']}: global_risk={r['methodological_risk_global']} (overclaiming={r['risk_of_overclaiming_dsm_exactness']}, absent_core={r['risk_of_absent_core_criteria']}, proxy_overdependence={r['risk_of_proxy_overdependence']})"
            )
        safe_write_text("\n".join(lines) + "\n", self.paths.reports / "overclaiming_risk_report.md")

    def build_modelability_index(self) -> None:
        if self.unit_cov_matrix is None:
            self.audit_unit_coverage()
        if self.core_criteria_audit is None:
            self.audit_core_criteria_sufficiency()
        if self.cohort_support_by_unit is None:
            self.audit_cohort_support()
        if self.target_strength is None:
            self.audit_target_strength()
        if self.feature_modelability is None:
            self.audit_feature_modelability()
        if self.methodological_risk is None:
            self.audit_methodological_risk()

        cov = self.unit_cov_matrix.set_index("unit_key")
        core = self.core_criteria_audit.copy()
        cohort = self.cohort_support_by_unit.set_index("unit_key")
        tstr = self.target_strength.set_index("unit_key")
        feat = self.feature_modelability.set_index("unit_key")
        risk = self.methodological_risk.set_index("unit_key")

        status_score = {"directly_covered": 1.0, "proxy_covered": 0.8, "partially_covered": 0.5, "absent": 0.0}
        target_score = {"strong_target": 90.0, "acceptable_target": 70.0, "weak_target": 45.0, "pseudo_target_risk": 20.0}
        feature_signal_score = {
            "high_specific_signal": 85.0,
            "moderate_specific_signal": 68.0,
            "low_specific_signal": 48.0,
            "sparse_specific_signal": 28.0,
        }

        rows: List[Dict[str, Any]] = []
        for unit, cfg in UNIT_CONFIG.items():
            us_core = core[core["unit_key"] == unit]
            comp_score = float(us_core["coverage_status"].map(status_score).mean()) * 100.0 if not us_core.empty else 0.0
            c = cohort.loc[unit]
            participant_score = (
                float(c["ratio_sufficient_core"]) * 100.0
                + float(c["ratio_partial_core"]) * 60.0
                + float(c["ratio_proxy_only"]) * 40.0
                - float(c["ratio_predominantly_absent"]) * 50.0
            )
            participant_score = clamp(participant_score)
            target_strength_score = target_score.get(str(tstr.loc[unit, "target_strength_class"]), 20.0)
            feature_score = feature_signal_score.get(str(feat.loc[unit, "feature_signal_class"]), 28.0)

            absent_penalty = float(cov.loc[unit, "absent_ratio"]) * 30.0
            risk_penalty = self._risk_to_penalty(str(risk.loc[unit, "methodological_risk_global"]))
            final = (
                0.30 * comp_score
                + 0.25 * participant_score
                + 0.25 * target_strength_score
                + 0.20 * feature_score
                - absent_penalty
                - risk_penalty
            )
            final = clamp(final)

            global_risk = str(risk.loc[unit, "methodological_risk_global"])
            t_class = str(tstr.loc[unit, "target_strength_class"])
            if final >= 75 and global_risk in {"low", "moderate"} and t_class in {"strong_target", "acceptable_target"}:
                decision = "trainable_high_rigor"
            elif final >= 60 and global_risk in {"low", "moderate", "high"} and t_class != "pseudo_target_risk":
                decision = "trainable_moderate_rigor"
            elif final >= 45:
                decision = "experimental_only"
            else:
                decision = "not_recommended_yet"

            rows.append(
                {
                    "unit_key": unit,
                    "diagnostic_unit": cfg["diagnostic_unit"],
                    "core_criteria_coverage_score": round(comp_score, 4),
                    "participant_support_score": round(participant_score, 4),
                    "target_strength_score": round(target_strength_score, 4),
                    "feature_specificity_score": round(feature_score, 4),
                    "absent_penalty": round(absent_penalty, 4),
                    "methodological_risk_penalty": round(risk_penalty, 4),
                    "final_modelability_score": round(final, 4),
                    "decision_class": decision,
                }
            )
        idx = pd.DataFrame(rows).sort_values("unit_key")
        self.modelability_index = idx
        safe_write_csv(idx, self.paths.tables / "modelability_index_by_unit.csv")

        safe_write_text(
            "\n".join(
                [
                    "# Modelability Scoring Method",
                    "",
                    "final_modelability_score =",
                    "0.30*core_criteria_coverage_score +",
                    "0.25*participant_support_score +",
                    "0.25*target_strength_score +",
                    "0.20*feature_specificity_score -",
                    "absent_penalty - methodological_risk_penalty",
                    "",
                    "Penalties:",
                    "- absent_penalty = absent_ratio * 30",
                    "- methodological_risk_penalty in {5,12,22,35} for {low,moderate,high,critical}",
                    "",
                    "Decision mapping:",
                    "- >=75 and controlled risk -> trainable_high_rigor",
                    "- >=60 and non-critical risk -> trainable_moderate_rigor",
                    "- >=45 -> experimental_only",
                    "- else -> not_recommended_yet",
                ]
            )
            + "\n",
            self.paths.reports / "modelability_scoring_method.md",
        )

    def _primary_bottleneck(self, row: pd.Series) -> str:
        candidates = [
            ("absent_core_criteria", row["risk_of_absent_core_criteria"]),
            ("proxy_overdependence", row["risk_of_proxy_overdependence"]),
            ("low_sample_support", row["risk_of_low_sample_support"]),
            ("target_instability", row["risk_of_target_instability"]),
            ("false_clinical_precision", row["risk_of_false_clinical_precision"]),
            ("overclaiming_exactness", row["risk_of_overclaiming_dsm_exactness"]),
        ]
        rank = {"low": 1, "moderate": 2, "high": 3, "critical": 4}
        candidates.sort(key=lambda x: rank.get(str(x[1]), 0), reverse=True)
        return candidates[0][0]

    def export_decisions_and_workflow(self) -> None:
        if self.modelability_index is None:
            self.build_modelability_index()
        if self.methodological_risk is None:
            self.audit_methodological_risk()

        idx = self.modelability_index.copy()
        risk = self.methodological_risk.copy()
        merged = idx.merge(risk, on=["unit_key", "diagnostic_unit"], how="left")
        merged["primary_bottleneck"] = merged.apply(self._primary_bottleneck, axis=1)

        decisions = merged[
            [
                "unit_key",
                "diagnostic_unit",
                "decision_class",
                "final_modelability_score",
                "primary_bottleneck",
                "core_criteria_coverage_score",
                "participant_support_score",
                "target_strength_score",
                "feature_specificity_score",
                "methodological_risk_global",
            ]
        ].copy()
        self.final_decisions = decisions.sort_values("unit_key")
        safe_write_csv(self.final_decisions, self.paths.tables / "final_modelability_decisions.csv")

        lines = ["# Final Modelability Decisions", ""]
        for _, r in self.final_decisions.iterrows():
            lines.append(
                f"- {r['unit_key']}: {r['decision_class']} (score={r['final_modelability_score']:.2f}, bottleneck={r['primary_bottleneck']}, risk={r['methodological_risk_global']})"
            )
        safe_write_text("\n".join(lines) + "\n", self.paths.reports / "final_modelability_decisions.md")

        action_rows: List[Dict[str, Any]] = []
        for _, r in self.final_decisions.iterrows():
            decision = str(r["decision_class"])
            bottleneck = str(r["primary_bottleneck"])
            if decision == "trainable_high_rigor":
                action = "train_now_with_strict_pipeline"
            elif decision == "trainable_moderate_rigor":
                action = "train_but_label_experimental"
            elif decision == "experimental_only":
                if bottleneck in {"target_instability", "proxy_overdependence"}:
                    action = "require_target_redefinition"
                elif bottleneck in {"absent_core_criteria", "false_clinical_precision"}:
                    action = "require_more_observable_criteria"
                else:
                    action = "require_feature_redesign"
            else:
                action = "do_not_train_yet"
            action_rows.append(
                {
                    "unit_key": r["unit_key"],
                    "diagnostic_unit": r["diagnostic_unit"],
                    "decision_class": decision,
                    "primary_bottleneck": bottleneck,
                    "next_action": action,
                }
            )
        actions = pd.DataFrame(action_rows).sort_values("unit_key")
        self.next_actions = actions
        safe_write_csv(actions, self.paths.tables / "next_action_by_unit.csv")

        rec_lines = ["# Training Readiness Recommendations", ""]
        for _, r in actions.iterrows():
            rec_lines.append(f"- {r['unit_key']}: {r['next_action']} ({r['decision_class']}, bottleneck={r['primary_bottleneck']})")
        safe_write_text("\n".join(rec_lines) + "\n", self.paths.reports / "training_readiness_recommendations.md")

        grouping_rows: List[Dict[str, Any]] = []
        for _, r in decisions.iterrows():
            d = str(r["decision_class"])
            if d == "trainable_high_rigor":
                g = "grupo_entrenable_ahora"
            elif d in {"trainable_moderate_rigor", "experimental_only"}:
                g = "grupo_entrenable_experimentalmente"
            else:
                g = "grupo_no_entrenable_aun"
            grouping_rows.append(
                {
                    "unit_key": r["unit_key"],
                    "diagnostic_unit": r["diagnostic_unit"],
                    "decision_class": d,
                    "workflow_group": g,
                }
            )
        grouping = pd.DataFrame(grouping_rows).sort_values("unit_key")
        safe_write_csv(grouping, self.paths.tables / "unit_grouping_for_workflow.csv")

        domain_rows: List[Dict[str, Any]] = []
        for domain, units in DOMAIN_TO_UNITS.items():
            sub = grouping[grouping["unit_key"].isin(units)].copy()
            if all(x == "trainable_high_rigor" for x in sub["decision_class"]):
                readiness = "ready_for_strict_training"
                next_step = "train_now_with_strict_pipeline"
            elif all(x in {"trainable_high_rigor", "trainable_moderate_rigor"} for x in sub["decision_class"]):
                readiness = "ready_with_moderate_controls"
                next_step = "train_but_label_experimental"
            elif any(x in {"trainable_moderate_rigor", "experimental_only"} for x in sub["decision_class"]) and not any(x == "not_recommended_yet" for x in sub["decision_class"]):
                readiness = "experimental_readiness"
                next_step = "train_but_label_experimental"
            elif any(x == "not_recommended_yet" for x in sub["decision_class"]):
                readiness = "not_ready_due_internal_unit_gaps"
                next_step = "require_feature_redesign"
            else:
                readiness = "experimental_readiness"
                next_step = "train_but_label_experimental"
            domain_rows.append(
                {
                    "external_domain": domain,
                    "internal_units": ",".join(units),
                    "unit_decisions": ",".join(sorted(sub["decision_class"].tolist())),
                    "domain_readiness": readiness,
                    "recommended_next_step": next_step,
                }
            )
        domain_df = pd.DataFrame(domain_rows).sort_values("external_domain")
        safe_write_csv(domain_df, self.paths.tables / "domain_readiness_from_internal_units.csv")

        impact_lines = ["# Workflow Impact Summary", ""]
        for _, r in domain_df.iterrows():
            impact_lines.append(
                f"- {r['external_domain']}: {r['domain_readiness']} (units={r['internal_units']}, decisions={r['unit_decisions']})"
            )
        safe_write_text("\n".join(impact_lines) + "\n", self.paths.reports / "workflow_impact_summary.md")

    def export_previous_vs_current_comparison(self) -> None:
        prev_path = self.paths.root / "data" / "processed" / "intermediate" / "targets_6_11.csv"
        prev = pd.read_csv(prev_path, low_memory=False)
        prev_targets = {
            "adhd": "target_adhd",
            "conduct": "target_conduct",
            "elimination": "target_elimination",
            "anxiety": "target_anxiety",
            "depression": "target_depression",
        }
        if self.final_decisions is None:
            self.export_decisions_and_workflow()

        decisions = self.final_decisions.copy().set_index("unit_key")
        rows: List[Dict[str, Any]] = []
        for domain, prev_col in prev_targets.items():
            units = DOMAIN_TO_UNITS[domain]
            dclasses = [str(decisions.loc[u, "decision_class"]) for u in units if u in decisions.index]
            if any(x == "not_recommended_yet" for x in dclasses):
                readiness = "reduced_practical_trainability"
            elif all(x in {"trainable_high_rigor", "trainable_moderate_rigor"} for x in dclasses):
                readiness = "improved_rigor_with_maintained_trainability"
            else:
                readiness = "higher_rigor_but_experimental_constraints"
            rows.append(
                {
                    "external_domain": domain,
                    "previous_broad_target_column": prev_col,
                    "previous_broad_target_prevalence": float(pd.to_numeric(prev[prev_col], errors="coerce").fillna(0).mean()) if prev_col in prev.columns else np.nan,
                    "internal_exact_units": ",".join(units),
                    "internal_exact_unit_decisions": ",".join(dclasses),
                    "what_improved_in_rigor": "Exact DSM-5 unit separation and explicit normative coverage traceability",
                    "what_worsened_in_practical_coverage": "Higher dependence on proxy/absent criteria in some units",
                    "conceptual_precision_gain": "high",
                    "simplicity_loss_vs_broad_targets": "moderate",
                    "cost_benefit_assessment": readiness,
                }
            )
        comp = pd.DataFrame(rows).sort_values("external_domain")
        safe_write_csv(comp, self.paths.diagnostics / "previous_vs_dsm5_exact_modelability_comparison.csv")
        safe_write_csv(comp, self.paths.tables / "previous_vs_dsm5_exact_modelability_comparison.csv")

        lines = [
            "# Rigor vs Coverage Tradeoff Report",
            "",
            "DSM5 exact reconstruction improves conceptual and traceability rigor,",
            "but practical trainability now varies by internal unit due to uneven observable criteria coverage.",
            "",
            "Domain-level tradeoff summary:",
        ]
        for _, r in comp.iterrows():
            lines.append(f"- {r['external_domain']}: {r['cost_benefit_assessment']}")
        safe_write_text("\n".join(lines) + "\n", self.paths.reports / "rigor_vs_coverage_tradeoff_report.md")

    def export_summary_report(self) -> None:
        if self.final_decisions is None:
            self.export_decisions_and_workflow()
        dec = self.final_decisions.copy()
        counts = dec["decision_class"].value_counts().to_dict()
        lines = [
            "# Modelability Audit Summary",
            "",
            f"- generated_at_utc: {now_iso()}",
            f"- units_audited: {len(dec)}",
            f"- trainable_high_rigor: {int(counts.get('trainable_high_rigor', 0))}",
            f"- trainable_moderate_rigor: {int(counts.get('trainable_moderate_rigor', 0))}",
            f"- experimental_only: {int(counts.get('experimental_only', 0))}",
            f"- not_recommended_yet: {int(counts.get('not_recommended_yet', 0))}",
            "",
            "Per-unit decision:",
        ]
        for _, r in dec.sort_values("unit_key").iterrows():
            lines.append(
                f"- {r['unit_key']}: {r['decision_class']} (score={r['final_modelability_score']:.2f}, bottleneck={r['primary_bottleneck']})"
            )
        safe_write_text("\n".join(lines) + "\n", self.paths.reports / "modelability_audit_summary.md")

    def run(self) -> None:
        self.ensure_dirs()
        self.capture_sentinels_before()
        self.load_inputs()
        self.build_input_inventory()
        self.audit_unit_coverage()
        self.audit_core_criteria_sufficiency()
        self.audit_cohort_support()
        self.audit_target_strength()
        self.audit_feature_modelability()
        self.audit_methodological_risk()
        self.build_modelability_index()
        self.export_decisions_and_workflow()
        self.export_previous_vs_current_comparison()
        self.export_summary_report()
        self.verify_sentinels_unchanged()


def run_phase(
    root: Path,
    phase: str,
    base_subdir: str = "data/processed_dsm5_exact_v1",
    artifact_subdir: str = "artifacts/dsm5_exact_v1/modelability_audit",
    strict_dir_name: str = "strict_no_leakage_exact",
    audit_label: str = "dsm5_exact",
) -> None:
    audit = DSM5ExactModelabilityAuditor(
        root,
        base_subdir=base_subdir,
        artifact_subdir=artifact_subdir,
        strict_dir_name=strict_dir_name,
        audit_label=audit_label,
    )
    audit.ensure_dirs()
    if phase == "all":
        audit.run()
        return

    audit.capture_sentinels_before()
    audit.load_inputs()
    if phase == "coverage":
        audit.build_input_inventory()
        audit.audit_unit_coverage()
    elif phase == "core":
        audit.audit_unit_coverage()
        audit.audit_core_criteria_sufficiency()
    elif phase == "target":
        audit.audit_target_strength()
    elif phase == "feature":
        audit.audit_feature_modelability()
    elif phase == "risk":
        audit.audit_unit_coverage()
        audit.audit_core_criteria_sufficiency()
        audit.audit_cohort_support()
        audit.audit_target_strength()
        audit.audit_feature_modelability()
        audit.audit_methodological_risk()
    elif phase == "index":
        audit.audit_unit_coverage()
        audit.audit_core_criteria_sufficiency()
        audit.audit_cohort_support()
        audit.audit_target_strength()
        audit.audit_feature_modelability()
        audit.audit_methodological_risk()
        audit.build_modelability_index()
    elif phase == "export":
        audit.audit_unit_coverage()
        audit.audit_core_criteria_sufficiency()
        audit.audit_cohort_support()
        audit.audit_target_strength()
        audit.audit_feature_modelability()
        audit.audit_methodological_risk()
        audit.build_modelability_index()
        audit.export_decisions_and_workflow()
        audit.export_previous_vs_current_comparison()
        audit.export_summary_report()
    else:
        raise ValueError(f"Unsupported phase: {phase}")

    audit.verify_sentinels_unchanged()


def main() -> None:
    parser = argparse.ArgumentParser(description="DSM5 exact modelability audit by internal diagnostic unit.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument(
        "--phase",
        type=str,
        default="all",
        choices=["all", "coverage", "core", "target", "feature", "risk", "index", "export"],
    )
    parser.add_argument("--base-subdir", type=str, default="data/processed_dsm5_exact_v1")
    parser.add_argument("--artifact-subdir", type=str, default="artifacts/dsm5_exact_v1/modelability_audit")
    parser.add_argument("--strict-dir-name", type=str, default="strict_no_leakage_exact")
    parser.add_argument("--audit-label", type=str, default="dsm5_exact")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)
    run_phase(
        Path(args.root).resolve(),
        args.phase,
        base_subdir=args.base_subdir,
        artifact_subdir=args.artifact_subdir,
        strict_dir_name=args.strict_dir_name,
        audit_label=args.audit_label,
    )
    LOGGER.info("DSM5 exact modelability audit phase '%s' completed", args.phase)


if __name__ == "__main__":
    main()
