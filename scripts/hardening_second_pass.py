
#!/usr/bin/env python
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

RANDOM_STATE = 42
TARGETS = ["target_conduct", "target_adhd", "target_elimination", "target_anxiety", "target_depression"]
ADULT_ONLY = {"asr", "bdi", "caars", "stai"}
PREDERIVED_EXCLUDE = {
    "n_diagnoses",
    "has_any_target_disorder",
    "comorbidity_count_5targets",
    "label_pattern",
}


def safe_csv(df: pd.DataFrame, path: Path) -> None:
    if path.exists():
        logging.warning("Overwriting %s", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_text(content: str, path: Path) -> None:
    if path.exists():
        logging.warning("Overwriting %s", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def source_from_feature(col: str, feature_catalog: pd.DataFrame) -> str:
    row = feature_catalog.loc[feature_catalog["feature_name"] == col]
    if not row.empty:
        return str(row.iloc[0]["source_table"])
    for token in ["swan", "conners", "caars", "cbcl", "sdq", "scared_p", "scared_sr", "mfq_p", "mfq_sr", "cdi", "bdi", "ysr", "asr", "icut", "ari_p", "ari_sr", "stai"]:
        if col.startswith(token + "_") or col.startswith("has_" + token) or col.startswith(token + "__"):
            return token
    if col in {"age_years", "sex_assigned_at_birth", "site", "release"}:
        return "participants"
    return "derived"


def modality_from_source(source: str, feature: str) -> str:
    if feature in {"age_years", "sex_assigned_at_birth", "site", "release"}:
        return "dato_demografico"
    if feature.startswith("has_"):
        return "disponibilidad_instrumental"
    if source.endswith("_sr") or source in {"ysr", "conners", "mfq_sr", "scared_sr", "ari_sr"}:
        return "autoreporte"
    if source.endswith("_p") or source in {"swan", "cbcl", "sdq", "icut", "mfq_p", "scared_p", "ari_p"}:
        return "reporte_cuidador"
    if any(k in feature for k in ["total", "proxy", "subscale", "score", "symptom", "impact", "cut"]):
        return "score_derivado"
    return "score_derivado"


def disorder_from_source(source: str, feature: str) -> str:
    src = source.lower()
    f = feature.lower()
    if src in {"swan", "conners", "caars"} or "adhd" in f or "attention" in f or "hyper" in f:
        return "adhd"
    if src in {"icut", "ari_p", "ari_sr"} or "conduct" in f or "aggressive" in f or "rule_break" in f:
        return "conduct"
    if src in {"scared_p", "scared_sr", "stai"} or "anxiety" in f or "panic" in f or "phobia" in f:
        return "anxiety"
    if src in {"mfq_p", "mfq_sr", "cdi", "bdi"} or "depress" in f or "mood" in f:
        return "depression"
    if "elimination" in f or "enuresis" in f or "encopresis" in f:
        return "elimination"
    if src in {"cbcl", "sdq", "ysr"}:
        return "transdiagnostic"
    return "general"


class HardeningPass:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.base = root / "data" / "HBN_synthetic_release11_focused_subset_csv"
        self.proc = root / "data" / "processed"
        self.final_dir = self.proc / "final"
        self.strict_dir = self.final_dir / "strict_no_leakage"
        self.research_dir = self.final_dir / "research_extended"
        self.splits_dir = self.proc / "splits"
        self.prep_dir = root / "artifacts" / "preprocessing"
        self.specs_dir = root / "artifacts" / "specs"
        self.manifests_dir = self.proc / "metadata" / "model_manifests"
        self.feature_catalog = pd.read_csv(self.proc / "feature_catalog.csv")
        self.action_logs: List[str] = []

    def run(self) -> None:
        self.action_logs.append(f"run_started,{datetime.now(timezone.utc).isoformat()}")
        self._ensure_dirs()
        self.action_logs.append("step_done,ensure_dirs")
        age_report = self._age_applicability_report()
        self.action_logs.append(f"step_done,age_applicability_report,rows={len(age_report)}")
        leakage_matrix = self._build_leakage_matrix(age_report)
        self.action_logs.append(f"step_done,leakage_risk_matrix,rows={len(leakage_matrix)}")
        self._harden_strict_datasets(leakage_matrix, age_report)
        self.action_logs.append("step_done,harden_strict_datasets")
        self._build_master_inference_ready(leakage_matrix, age_report)
        self.action_logs.append("step_done,build_master_inference_ready")
        self._build_questionnaire_contracts(leakage_matrix, age_report)
        self.action_logs.append("step_done,build_questionnaire_contracts")
        self._regenerate_strict_splits_and_preprocessing()
        self.action_logs.append("step_done,regenerate_strict_splits_and_preprocessing")
        self._build_model_manifests(leakage_matrix)
        self.action_logs.append("step_done,build_model_manifests")
        self._build_feature_lineage(leakage_matrix, age_report)
        self.action_logs.append("step_done,build_feature_lineage")
        self._split_quality_report()
        self.action_logs.append("step_done,split_quality_report")
        self._write_specs_and_readiness()
        self.action_logs.append("step_done,write_specs_and_readiness")
        self.action_logs.append(f"run_completed,{datetime.now(timezone.utc).isoformat()}")
        self._write_action_log()
        self._print_summary()

    def _ensure_dirs(self) -> None:
        for d in [self.specs_dir, self.manifests_dir, self.proc / "reports", self.proc / "metadata"]:
            d.mkdir(parents=True, exist_ok=True)

    def _age_applicability_report(self) -> pd.DataFrame:
        cohort = pd.read_csv(self.proc / "intermediate" / "cohort_6_11.csv")
        cohort_ids = set(cohort["participant_id"].astype(str))
        rows = []
        for p in sorted(self.base.glob("*.csv")):
            name = p.stem.lower()
            if name in {"participants", "sources", "summary_tables", "data_dictionary_public_schema", "synthetic_diagnostic_counts"} or name.startswith("diagnosis"):
                continue
            df = pd.read_csv(p)
            cols = {c.lower(): c for c in df.columns}
            age_col = cols.get("age_years")
            id_col = cols.get("participant_id")
            overall_min = overall_max = np.nan
            cohort_rows = 0
            cohort_cov = 0.0
            if age_col:
                age = pd.to_numeric(df[age_col], errors="coerce")
                if age.notna().any():
                    overall_min = float(age.min())
                    overall_max = float(age.max())
            if id_col:
                ids = df[id_col].astype(str)
                in_cohort = ids.isin(cohort_ids)
                cohort_rows = int(in_cohort.sum())
                cohort_cov = float(cohort_rows / max(len(cohort), 1))
            source = name
            applies = bool(cohort_rows > 0)
            reason = "has_rows_in_6_11"
            if source in ADULT_ONLY:
                applies = False
                reason = "adult_only_instrument"
            elif cohort_rows == 0:
                applies = False
                reason = "no_records_for_6_11"
            elif pd.notna(overall_min) and pd.notna(overall_max):
                if overall_min > 11 or overall_max < 6:
                    applies = False
                    reason = "age_range_outside_6_11"
            rows.append(
                {
                    "instrument": source,
                    "file_name": p.name,
                    "overall_age_min": overall_min,
                    "overall_age_max": overall_max,
                    "cohort_rows_6_11": cohort_rows,
                    "cohort_coverage_pct": round(cohort_cov * 100.0, 4),
                    "applies_to_6_11": int(applies),
                    "applicability_reason": reason,
                }
            )
        report = pd.DataFrame(rows).sort_values("instrument")
        safe_csv(report, self.proc / "reports" / "age_applicability_report.csv")
        return report

    def _build_leakage_matrix(self, age_report: pd.DataFrame) -> pd.DataFrame:
        master = pd.read_csv(self.research_dir / "master_multilabel_ready_research_extended.csv")
        age_ok = {r.instrument: bool(r.applies_to_6_11) for r in age_report.itertuples(index=False)}
        rows = []
        feature_cols = [c for c in master.columns if c not in ["participant_id", *TARGETS, *PREDERIVED_EXCLUDE] and not c.startswith("source_target_")]

        for c in feature_cols:
            s = master[c]
            src = source_from_feature(c, self.feature_catalog)
            miss = float(s.isna().mean())
            risk = "none"
            reason = ""
            action = "keep"

            low = c.lower()
            if src in ADULT_ONLY or not age_ok.get(src, True):
                risk = "exclude"
                reason = "age_non_applicable"
                action = "exclude"
            elif low.startswith("diag_") or "diagnosis" in low or low.endswith("_present"):
                risk = "exclude"
                reason = "diagnostic_or_postdiagnostic_feature"
                action = "exclude"
            elif low in PREDERIVED_EXCLUDE:
                risk = "exclude"
                reason = "target_derived_feature"
                action = "exclude"
            elif miss >= 0.98:
                risk = "high"
                reason = "near_empty"
                action = "exclude"
            elif "cut" in low or "possible_" in low:
                risk = "medium"
                reason = "screening_threshold_proxy"
                action = "review"
            elif c.startswith("has_"):
                risk = "low"
                reason = "instrument_availability_indicator"
                action = "keep"

            max_corr = 0.0
            if action != "exclude":
                num = pd.to_numeric(s, errors="coerce")
                if num.notna().sum() > 10:
                    for t in TARGETS:
                        corr = abs(float(num.corr(master[t]))) if master[t].nunique() > 1 else 0.0
                        max_corr = max(max_corr, 0.0 if np.isnan(corr) else corr)
                    if max_corr >= 0.999:
                        risk = "exclude"
                        reason = "exact_or_near_exact_target_equivalent"
                        action = "exclude"
                    elif max_corr >= 0.95 and risk not in {"exclude"}:
                        risk = "high"
                        reason = "very_high_target_association"
                        action = "exclude"
                    elif max_corr >= 0.8 and risk in {"none", "low"}:
                        risk = "medium"
                        reason = "strong_target_association"
                        action = "review"

            rows.append(
                {
                    "feature_name": c,
                    "source_table": src,
                    "missing_pct": round(miss * 100.0, 4),
                    "max_abs_corr_target": round(max_corr, 6),
                    "risk_level": risk,
                    "recommended_action": action,
                    "reason": reason or "no_signal_of_leakage",
                }
            )

        leak = pd.DataFrame(rows).sort_values(["risk_level", "source_table", "feature_name"])
        order = {"none": 0, "low": 1, "medium": 2, "high": 3, "exclude": 4}
        leak = leak.assign(_ord=leak["risk_level"].map(order)).sort_values(["_ord", "source_table", "feature_name"]).drop(columns="_ord")
        safe_csv(leak, self.proc / "reports" / "leakage_risk_matrix.csv")
        return leak

    def _strict_backup(self, path: Path) -> None:
        backup_dir = self.proc / "intermediate" / "backups_strict_v1"
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / path.name
        if not target.exists():
            shutil.copy2(path, target)
            self.action_logs.append(f"backup_created,{path.relative_to(self.root)},{target.relative_to(self.root)}")

    def _harden_strict_datasets(self, leakage: pd.DataFrame, age_report: pd.DataFrame) -> None:
        exclude_features = set(leakage.loc[leakage["recommended_action"] == "exclude", "feature_name"])
        age_ok = {r.instrument: bool(r.applies_to_6_11) for r in age_report.itertuples(index=False)}

        for p in sorted(self.strict_dir.glob("*.csv")):
            df = pd.read_csv(p)
            cols_before = list(df.columns)
            keep = []
            dropped = []
            for c in cols_before:
                if c in TARGETS or c in {"participant_id", "primary_target", "dataset_name", "is_exploratory"}:
                    keep.append(c)
                    continue
                if c in PREDERIVED_EXCLUDE or c.startswith("source_target_"):
                    dropped.append((c, "target_derived"))
                    continue
                src = source_from_feature(c, self.feature_catalog)
                if src in ADULT_ONLY or not age_ok.get(src, True):
                    dropped.append((c, "age_non_applicable"))
                    continue
                if c in exclude_features:
                    dropped.append((c, "leakage_exclude"))
                    continue
                keep.append(c)

            if set(keep) != set(cols_before):
                self._strict_backup(p)
                hardened = df[keep].copy()
                safe_csv(hardened, p)
                for c, r in dropped:
                    self.action_logs.append(f"strict_drop,{p.name},{c},{r}")

    def _build_master_inference_ready(self, leakage: pd.DataFrame, age_report: pd.DataFrame) -> None:
        strict = pd.read_csv(self.strict_dir / "master_multilabel_ready_strict_no_leakage.csv")
        research = pd.read_csv(self.research_dir / "master_multilabel_ready_research_extended.csv")
        leak_ex = set(leakage.loc[leakage["recommended_action"] == "exclude", "feature_name"])
        age_ok = {r.instrument: bool(r.applies_to_6_11) for r in age_report.itertuples(index=False)}

        def prediag_cols(df: pd.DataFrame, strict_mode: bool) -> List[str]:
            keep = []
            for c in df.columns:
                if c in {"participant_id", *TARGETS}:
                    keep.append(c)
                    continue
                if c in PREDERIVED_EXCLUDE or c.startswith("source_target_") or c.startswith("diag_") or "diagnosis" in c.lower():
                    continue
                src = source_from_feature(c, self.feature_catalog)
                if strict_mode:
                    if src in ADULT_ONLY or not age_ok.get(src, True):
                        continue
                    if c in leak_ex:
                        continue
                keep.append(c)
            return keep

        strict_keep = prediag_cols(strict, strict_mode=True)
        research_keep = prediag_cols(research, strict_mode=False)

        strict_inf = strict[strict_keep].copy()
        research_inf = research[research_keep].copy()

        safe_csv(strict_inf, self.final_dir / "master_inference_ready_strict.csv")
        safe_csv(research_inf, self.final_dir / "master_inference_ready_research.csv")

        safe_csv(strict_inf, self.strict_dir / "master_inference_ready_strict.csv")
        safe_csv(research_inf, self.research_dir / "master_inference_ready_research.csv")

        meta = {
            "strict_feature_count": int(len([c for c in strict_inf.columns if c not in ["participant_id", *TARGETS]])),
            "research_feature_count": int(len([c for c in research_inf.columns if c not in ["participant_id", *TARGETS]])),
            "prediagnostic_definition": "Features available before final diagnostic adjudication.",
            "targets": TARGETS,
        }
        safe_text(json.dumps(meta, indent=2), self.proc / "metadata" / "master_inference_ready_metadata.json")

    def _build_questionnaire_contracts(self, leakage: pd.DataFrame, age_report: pd.DataFrame) -> None:
        strict_inf = pd.read_csv(self.final_dir / "master_inference_ready_strict.csv")
        age_ok = {r.instrument: bool(r.applies_to_6_11) for r in age_report.itertuples(index=False)}

        feature_cols = [c for c in strict_inf.columns if c not in ["participant_id", *TARGETS]]
        rows = []
        schema_props = {}
        template_row = {}

        for c in feature_cols:
            src = source_from_feature(c, self.feature_catalog)
            ser = strict_inf[c]
            dtype = "categorical"
            opts = ""
            rng = ""
            if pd.api.types.is_numeric_dtype(ser):
                uniq = set(pd.to_numeric(ser, errors="coerce").dropna().unique().tolist())
                if uniq.issubset({0, 1}):
                    dtype = "binary"
                    opts = "0|1"
                else:
                    dtype = "numeric"
                    if ser.notna().any():
                        rng = f"{float(pd.to_numeric(ser, errors='coerce').min()):.4f}|{float(pd.to_numeric(ser, errors='coerce').max()):.4f}"
            else:
                vals = ser.dropna().astype(str).unique().tolist()
                if len(vals) <= 12:
                    opts = "|".join(sorted(vals))

            modality = modality_from_source(src, c)
            disorder = disorder_from_source(src, c)
            applies = int(age_ok.get(src, True))
            required = "required" if c in {"age_years"} else "optional"

            rows.append(
                {
                    "pregunta_encuesta": c,
                    "dataset_origen": "master_inference_ready_strict",
                    "columna_origen": c,
                    "feature_final": c,
                    "tipo_respuesta": dtype,
                    "opciones_permitidas": opts,
                    "rango_esperado": rng,
                    "trastorno_relacionado": disorder,
                    "aplica_a_edad": "6-11" if applies else "not_6_11",
                    "requerida_opcional": required,
                    "modalidad": modality,
                }
            )

            schema_props[c] = {
                "type": "number" if dtype in {"binary", "numeric"} else "string",
                "description": f"{src}::{c}",
                "x-modality": modality,
                "x-disorder-domain": disorder,
                "x-age-applicability": "6-11" if applies else "not_6_11",
            }
            template_row[c] = ""

        contract = pd.DataFrame(rows).sort_values(["trastorno_relacionado", "pregunta_encuesta"])
        safe_csv(contract, self.specs_dir / "questionnaire_feature_contract.csv")
        safe_csv(contract, self.proc / "reports" / "questionnaire_feature_contract.csv")

        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "CognIA Questionnaire Input Schema",
            "type": "object",
            "properties": schema_props,
            "required": ["age_years"],
            "additionalProperties": False,
        }
        safe_text(json.dumps(schema, indent=2, ensure_ascii=False), self.specs_dir / "questionnaire_schema.json")

        safe_csv(pd.DataFrame([template_row]), self.specs_dir / "inference_input_template.csv")

    def _regenerate_strict_splits_and_preprocessing(self) -> None:
        for p in sorted(self.strict_dir.glob("*.csv")):
            ds_name = p.stem.replace("_strict_no_leakage", "")
            df = pd.read_csv(p)
            if "participant_id" not in df.columns:
                continue
            ids = df["participant_id"].astype(str)
            if "primary_target" in df.columns and df["primary_target"].notna().any():
                target = str(df["primary_target"].dropna().iloc[0])
            elif "adhd" in ds_name:
                target = "target_adhd"
            elif "conduct" in ds_name:
                target = "target_conduct"
            elif "elimination" in ds_name:
                target = "target_elimination"
            elif "anxiety" in ds_name:
                target = "target_anxiety"
            elif "depression" in ds_name:
                target = "target_depression"
            else:
                target = "target_adhd"

            y = df[TARGETS].copy() if ds_name == "master_multilabel_ready" else df[[target]].copy()
            nonf = {"participant_id", "primary_target", "dataset_name", "is_exploratory", "label_pattern", *TARGETS, *PREDERIVED_EXCLUDE, *(f"source_{c}" for c in TARGETS)}
            X = df[[c for c in df.columns if c not in nonf]].copy()

            strat = None
            if ds_name == "master_multilabel_ready" and "label_pattern" in df.columns:
                vc = df["label_pattern"].value_counts()
                if len(vc) > 1 and vc.min() >= 2:
                    strat = df["label_pattern"]
            elif target in y.columns:
                vc = y[target].value_counts()
                if len(vc) > 1 and vc.min() >= 2:
                    strat = y[target]

            X_tv, X_te, y_tv, y_te, i_tv, i_te = train_test_split(X, y, ids, test_size=0.15, random_state=RANDOM_STATE, stratify=strat)
            strat2 = strat.loc[X_tv.index] if strat is not None else None
            if strat2 is not None and strat2.value_counts().min() < 2:
                strat2 = None
            X_tr, X_va, y_tr, y_va, i_tr, i_va = train_test_split(X_tv, y_tv, i_tv, test_size=0.1764706, random_state=RANDOM_STATE, stratify=strat2)

            sdir = self.splits_dir / ds_name / "strict_no_leakage"
            sdir.mkdir(parents=True, exist_ok=True)
            for n, d in {
                "X_train": X_tr, "X_val": X_va, "X_test": X_te,
                "y_train": y_tr, "y_val": y_va, "y_test": y_te,
                "ids_train": pd.DataFrame({"participant_id": i_tr}),
                "ids_val": pd.DataFrame({"participant_id": i_va}),
                "ids_test": pd.DataFrame({"participant_id": i_te}),
            }.items():
                safe_csv(d.reset_index(drop=True), sdir / f"{n}.csv")

            ncols = [c for c in X_tr.columns if pd.api.types.is_numeric_dtype(X_tr[c])]
            ccols = [c for c in X_tr.columns if c not in ncols]
            prep = ColumnTransformer([
                ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), ncols),
                ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=True))]), ccols),
            ], remainder="drop")
            prep.fit(X_tr)

            adir = self.prep_dir / ds_name / "strict_no_leakage"
            adir.mkdir(parents=True, exist_ok=True)
            safe_csv(X, adir / "X_cleaned.csv")
            safe_csv(y, adir / "y.csv")
            safe_csv(X, adir / "X_raw.csv")
            sparse.save_npz(adir / "X_train_encoded.npz", sparse.csr_matrix(prep.transform(X_tr)))
            sparse.save_npz(adir / "X_val_encoded.npz", sparse.csr_matrix(prep.transform(X_va)))
            sparse.save_npz(adir / "X_test_encoded.npz", sparse.csr_matrix(prep.transform(X_te)))
            sparse.save_npz(adir / "X_encoded.npz", sparse.csr_matrix(prep.transform(X)))
            safe_csv(pd.DataFrame({"encoded_feature": prep.get_feature_names_out()}), adir / "encoded_feature_names.csv")
            joblib.dump(prep, adir / "preprocessor.joblib")

            meta = {
                "dataset_name": ds_name,
                "version": "strict_no_leakage",
                "primary_target": target,
                "split_sizes": {"train": len(X_tr), "val": len(X_va), "test": len(X_te)},
                "random_state": RANDOM_STATE,
                "numeric_features": ncols,
                "categorical_features": ccols,
            }
            safe_text(json.dumps(meta, indent=2), adir / "metadata.json")

    def _build_model_manifests(self, leakage: pd.DataFrame) -> None:
        leak_map = leakage.set_index("feature_name")["recommended_action"].to_dict()
        all_files = list(self.strict_dir.glob("*.csv")) + list(self.research_dir.glob("*.csv"))
        for p in sorted(all_files):
            ver = "strict_no_leakage" if "strict_no_leakage" in p.name or p.parent.name == "strict_no_leakage" else "research_extended"
            ds = p.stem.replace("_strict_no_leakage", "").replace("_research_extended", "")
            df = pd.read_csv(p)
            if "participant_id" not in df.columns:
                continue
            if "primary_target" in df.columns and df["primary_target"].notna().any():
                target = str(df["primary_target"].dropna().iloc[0])
            elif "adhd" in ds:
                target = "target_adhd"
            elif "conduct" in ds:
                target = "target_conduct"
            elif "elimination" in ds:
                target = "target_elimination"
            elif "anxiety" in ds:
                target = "target_anxiety"
            elif "depression" in ds:
                target = "target_depression"
            else:
                target = "multilabel"

            nonf = {"participant_id", "primary_target", "dataset_name", "is_exploratory", "label_pattern", *TARGETS, *PREDERIVED_EXCLUDE, *(f"source_{c}" for c in TARGETS)}
            feats = [c for c in df.columns if c not in nonf]
            X = df[feats].copy()
            n_features = len(feats)
            numeric = [c for c in feats if pd.api.types.is_numeric_dtype(X[c])]
            categorical = [c for c in feats if c not in numeric]
            binary = [c for c in numeric if set(pd.to_numeric(X[c], errors="coerce").dropna().unique()).issubset({0, 1})]
            null_before = float(X.isna().mean().mean() * 100.0) if n_features else 0.0
            X_imp = X.copy()
            all_missing_numeric = []
            all_missing_categorical = []
            # Column-wise imputation avoids shape mismatches when an imputer drops fully-missing columns.
            for c in numeric:
                col = pd.to_numeric(X[c], errors="coerce")
                if col.notna().any():
                    X_imp[c] = col.fillna(float(col.median()))
                else:
                    all_missing_numeric.append(c)
                    X_imp[c] = col.fillna(0.0)
            for c in categorical:
                col = X[c]
                if col.notna().any():
                    mode = col.mode(dropna=True)
                    fill_value = mode.iloc[0] if not mode.empty else "__missing__"
                    X_imp[c] = col.fillna(fill_value)
                else:
                    all_missing_categorical.append(c)
                    X_imp[c] = col.fillna("__missing__")
            null_after = float(X_imp.isna().mean().mean() * 100.0) if n_features else 0.0
            excluded = [c for c in feats if leak_map.get(c) == "exclude"]
            imputed = [c for c in feats if X[c].isna().any()]
            encoded = categorical

            class_balance = {}
            if target == "multilabel":
                for t in TARGETS:
                    if t in df.columns:
                        pos = int(df[t].sum())
                        class_balance[t] = {"positive": pos, "negative": int(len(df) - pos), "rate": float(pos / len(df))}
                cw = "per-label balanced"
            else:
                if target in df.columns:
                    pos = int(df[target].sum())
                    rate = float(pos / len(df)) if len(df) else 0.0
                    class_balance[target] = {"positive": pos, "negative": int(len(df) - pos), "rate": rate}
                    cw = "balanced" if rate < 0.4 or rate > 0.6 else "none_or_balanced_subsample"
                else:
                    cw = "unknown"

            manifest = {
                "dataset": ds,
                "version": ver,
                "target": target,
                "n_rows": int(len(df)),
                "n_features": int(n_features),
                "n_numeric": int(len(numeric)),
                "n_categorical": int(len(categorical)),
                "n_binary": int(len(binary)),
                "null_pct_before_imputation": round(null_before, 4),
                "null_pct_after_imputation": round(null_after, 4),
                "columns_excluded": excluded,
                "columns_imputed": imputed,
                "columns_encoded": encoded,
                "class_balance": class_balance,
                "recommended_class_weight": cw,
                "recommended_threshold_tuning": ["youden_j", "f1_opt", "sensitivity_priority"],
                "methodological_warnings": [
                    "Check subgroup fairness by age/sex.",
                    "Validate calibration before clinical interpretation.",
                    "For low-prevalence targets prioritize sensitivity/specificity tradeoff.",
                ],
                "all_missing_numeric_fallback_zero": all_missing_numeric,
                "all_missing_categorical_fallback_missing_token": all_missing_categorical,
            }
            safe_text(json.dumps(manifest, indent=2), self.manifests_dir / f"{ds}__{ver}.json")

    def _build_feature_lineage(self, leakage: pd.DataFrame, age_report: pd.DataFrame) -> None:
        age_ok = {r.instrument: bool(r.applies_to_6_11) for r in age_report.itertuples(index=False)}
        leak_action = leakage.set_index("feature_name")["recommended_action"].to_dict()
        rows = []
        for ver_dir in [self.strict_dir, self.research_dir]:
            version = ver_dir.name
            for p in sorted(ver_dir.glob("*.csv")):
                ds = p.stem.replace("_strict_no_leakage", "").replace("_research_extended", "")
                df = pd.read_csv(p, nrows=5)
                for c in df.columns:
                    if c in {"participant_id", *TARGETS, "primary_target", "dataset_name", "is_exploratory"}:
                        continue
                    src = source_from_feature(c, self.feature_catalog)
                    modality = modality_from_source(src, c)
                    transform = "direct_pass_through"
                    if c.startswith("has_"):
                        transform = "availability_indicator"
                    elif "item_sum" in c or any(k in c for k in ["total", "proxy", "subscale", "score", "symptom", "impact", "cut"]):
                        transform = "instrument_derived_score"
                    imputation = "median_or_mode_if_missing"
                    encoding = "onehot_if_categorical"
                    rows.append(
                        {
                            "dataset_name": ds,
                            "version": version,
                            "source_table": src,
                            "source_column": c,
                            "transform_applied": transform,
                            "imputation_applied": imputation,
                            "encoding_applied": encoding,
                            "final_feature_name": c,
                            "modality": modality,
                            "age_applicability": "6-11" if age_ok.get(src, True) else "not_6_11",
                            "leakage_action": leak_action.get(c, "keep"),
                        }
                    )
        lineage = pd.DataFrame(rows).drop_duplicates().sort_values(["dataset_name", "version", "final_feature_name"])
        safe_csv(lineage, self.proc / "metadata" / "feature_lineage.csv")

    def _split_quality_report(self) -> None:
        rows = []
        for ds_dir in sorted(self.splits_dir.glob("*")):
            if not ds_dir.is_dir():
                continue
            ds = ds_dir.name
            for ver_dir in sorted(ds_dir.glob("*")):
                if not ver_dir.is_dir():
                    continue
                ver = ver_dir.name
                req = ["ids_train.csv", "ids_val.csv", "ids_test.csv", "y_train.csv", "y_val.csv", "y_test.csv"]
                if not all((ver_dir / r).exists() for r in req):
                    continue
                i_tr = set(pd.read_csv(ver_dir / "ids_train.csv")["participant_id"].astype(str))
                i_va = set(pd.read_csv(ver_dir / "ids_val.csv")["participant_id"].astype(str))
                i_te = set(pd.read_csv(ver_dir / "ids_test.csv")["participant_id"].astype(str))
                y_tr = pd.read_csv(ver_dir / "y_train.csv")
                y_va = pd.read_csv(ver_dir / "y_val.csv")
                y_te = pd.read_csv(ver_dir / "y_test.csv")

                if ds == "master_multilabel_ready":
                    drift = {}
                    for t in [c for c in TARGETS if c in y_tr.columns]:
                        rtr = float(y_tr[t].mean()) if len(y_tr) else 0.0
                        rte = float(y_te[t].mean()) if len(y_te) else 0.0
                        drift[t] = round(abs(rtr - rte), 6)
                    drift_metric = float(max(drift.values())) if drift else 0.0
                    drift_detail = json.dumps(drift)
                else:
                    tc = y_tr.columns[0]
                    rtr = float(y_tr[tc].mean()) if len(y_tr) else 0.0
                    rte = float(y_te[tc].mean()) if len(y_te) else 0.0
                    drift_metric = round(abs(rtr - rte), 6)
                    drift_detail = json.dumps({tc: drift_metric})

                rows.append(
                    {
                        "dataset_name": ds,
                        "version": ver,
                        "n_train": len(i_tr),
                        "n_val": len(i_va),
                        "n_test": len(i_te),
                        "overlap_train_val": len(i_tr & i_va),
                        "overlap_train_test": len(i_tr & i_te),
                        "overlap_val_test": len(i_va & i_te),
                        "participant_overlap_flag": int(bool((i_tr & i_va) or (i_tr & i_te) or (i_va & i_te))),
                        "target_distribution_drift_abs": drift_metric,
                        "target_distribution_drift_detail": drift_detail,
                        "split_reproducible_random_state": RANDOM_STATE,
                        "oversampling_pre_split": "not_applied",
                    }
                )
        safe_csv(pd.DataFrame(rows).sort_values(["dataset_name", "version"]), self.proc / "reports" / "split_quality_report.csv")

    def _write_specs_and_readiness(self) -> None:
        strat_md = """# Training Strategy Recommendations

## A) Binary strategy (one model per disorder)
- conduct: use `dataset_conduct_clinical_strict_no_leakage.csv`
- adhd: use `dataset_adhd_clinical_strict_no_leakage.csv`
- elimination: use `dataset_elimination_core_strict_no_leakage.csv` (exploratory)
- anxiety: use `dataset_anxiety_combined_strict_no_leakage.csv`
- depression: use `dataset_depression_combined_strict_no_leakage.csv`

Recommended estimator: `RandomForestClassifier(class_weight='balanced_subsample', random_state=42)` with threshold tuning per disorder.

## B) Multilabel strategy
- Use `master_multilabel_ready_strict_no_leakage.csv`
- Recommended wrapper: `MultiOutputClassifier(RandomForestClassifier(...))`
- Preserve label pattern distribution in splits when feasible.

## Priority for immediate training
1. ADHD
2. Anxiety
3. Depression
4. Conduct
5. Elimination (exploratory)
"""
        safe_text(strat_md, self.specs_dir / "training_strategy_recommendations.md")

        threshold_md = """# Threshold Selection Protocol

For each disorder model evaluate thresholds in [0.05, 0.95] step 0.01.

1) Youden J optimization
- J = sensitivity + specificity - 1
- choose threshold maximizing J when balanced operating point is desired.

2) F1 optimization
- choose threshold maximizing F1 when precision-recall tradeoff is priority.

3) Sensitivity-prioritized
- choose lowest threshold meeting target sensitivity (e.g. >=0.85), then maximize specificity.

Always report calibration status and final selected threshold rationale per disorder.
"""
        safe_text(threshold_md, self.specs_dir / "threshold_selection_protocol.md")

        rf_md = """# Random Forest Evaluation Specification

Required metrics per binary model:
- accuracy
- balanced_accuracy
- precision
- recall / sensitivity
- specificity
- f1
- roc_auc
- pr_auc
- confusion_matrix
- normalized_confusion_matrix
- calibration_curve
- brier_score
- feature_importance_gini
- permutation_importance
- top_positive_contributors (approx local explanation)

Subgroup metrics:
- by age
- by sex (if available)
- by comorbidity_count_5targets

Multilabel metrics:
- macro/micro/weighted precision-recall-f1
- subset accuracy
- hamming loss
- per-label confusion matrices
- comorbidity-aware slices by label_pattern

Clinical output contract:
- risk score 0..1 per disorder
- category: low/moderate/high
- suspected comorbidity flag
- evidence quality: weak/medium/strong
- critical missingness flags reducing confidence
"""
        safe_text(rf_md, self.proc / "random_forest_evaluation_spec.md")
        safe_text(rf_md, self.proc / "reports" / "random_forest_evaluation_spec.md")
        safe_text(rf_md, self.specs_dir / "random_forest_evaluation_spec.md")

        readiness_md = """# Model Readiness Report (Second Pass Hardening)

## Hardened status
- Strict datasets hardened for age applicability and leakage exclusion matrix.
- Split integrity checked (no participant overlap expected).
- Inference-ready masters produced: strict and research variants.
- Questionnaire contracts and schema generated.

## Clinical prioritization to train first
1. ADHD (highest coverage + rich feature set)
2. Anxiety (strong parent/self scales)
3. Depression (good coverage but lower prevalence)
4. Conduct (moderate prevalence and mixed sources)
5. Elimination (exploratory, sparse direct signals)

## Main methodological risks
- Class imbalance (especially depression/elimination/conduct).
- Potential proxy leakage if research_extended is used without strict controls.
- Confidence depends on missing critical inputs from questionnaire.

## Immediate next step
- Train binary RF per disorder with strict datasets + threshold protocol.
- Train multilabel baseline on strict master for comorbidity profiling.
"""
        safe_text(readiness_md, self.proc / "model_readiness_report.md")
        safe_text(readiness_md, self.proc / "reports" / "model_readiness_report.md")

    def _write_action_log(self) -> None:
        lines = ["hardening_action"] + self.action_logs
        safe_text("\n".join(lines) + "\n", self.proc / "reports" / "hardening_actions.log")

    def _print_summary(self) -> None:
        strict_files = sorted(self.strict_dir.glob("*.csv"))
        print("\n=== SECOND PASS HARDENING SUMMARY ===")
        print(f"Strict datasets hardened: {len(strict_files)}")
        print(f"Age applicability report: {(self.proc / 'reports' / 'age_applicability_report.csv').relative_to(self.root)}")
        print(f"Leakage risk matrix: {(self.proc / 'reports' / 'leakage_risk_matrix.csv').relative_to(self.root)}")
        print(f"Master inference strict: {(self.final_dir / 'master_inference_ready_strict.csv').relative_to(self.root)}")
        print(f"Master inference research: {(self.final_dir / 'master_inference_ready_research.csv').relative_to(self.root)}")
        print(f"Split quality report: {(self.proc / 'reports' / 'split_quality_report.csv').relative_to(self.root)}")
        print(f"Feature lineage: {(self.proc / 'metadata' / 'feature_lineage.csv').relative_to(self.root)}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    root = Path(__file__).resolve().parents[1]
    HardeningPass(root).run()


if __name__ == "__main__":
    main()

