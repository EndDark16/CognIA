
#!/usr/bin/env python
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
NA_TOKENS = ["", " ", "NA", "N/A", "null", "None", "nan", "NaN", "NULL", "-", "--"]
ID_CANDIDATES = ["participant_id", "subject_id", "src_subject_id", "participant", "id"]
TARGETS = ["target_conduct", "target_adhd", "target_elimination", "target_anxiety", "target_depression"]
LABEL_ORDER = ["target_conduct", "target_adhd", "target_elimination", "target_anxiety", "target_depression"]
DIAG_PRIORITY = ["diagnosis_clinician_consensus", "diagnosis_ksads_d", "diagnosis_ksads_p", "diagnosis_ksads_t"]
ADULT_ONLY = {"asr", "bdi", "caars", "stai"}

DATASET_SPECS = [
    {"name": "dataset_adhd_minimal", "target": "target_adhd", "inst": ["swan", "conners", "cbcl", "sdq"], "mode": "minimal"},
    {"name": "dataset_adhd_clinical", "target": "target_adhd", "inst": ["swan", "conners", "cbcl", "sdq", "ysr"], "mode": "clinical"},
    {"name": "dataset_adhd_items", "target": "target_adhd", "inst": ["swan", "conners", "cbcl", "sdq", "ysr"], "mode": "items"},
    {"name": "dataset_conduct_minimal", "target": "target_conduct", "inst": ["icut", "ari_p", "ari_sr", "cbcl", "sdq"], "mode": "minimal"},
    {"name": "dataset_conduct_clinical", "target": "target_conduct", "inst": ["icut", "ari_p", "ari_sr", "cbcl", "sdq", "ysr"], "mode": "clinical"},
    {"name": "dataset_conduct_items", "target": "target_conduct", "inst": ["icut", "ari_p", "ari_sr", "cbcl", "sdq", "ysr"], "mode": "items"},
    {"name": "dataset_elimination_core", "target": "target_elimination", "inst": ["cbcl", "sdq"], "mode": "core", "exploratory": 1},
    {"name": "dataset_elimination_items", "target": "target_elimination", "inst": ["cbcl", "sdq"], "mode": "items", "exploratory": 1},
    {"name": "dataset_anxiety_parent", "target": "target_anxiety", "inst": ["scared_p", "cbcl", "sdq"], "mode": "clinical"},
    {"name": "dataset_anxiety_combined", "target": "target_anxiety", "inst": ["scared_p", "scared_sr", "cbcl", "sdq"], "mode": "clinical"},
    {"name": "dataset_anxiety_items", "target": "target_anxiety", "inst": ["scared_p", "scared_sr", "cbcl", "sdq"], "mode": "items"},
    {"name": "dataset_depression_parent", "target": "target_depression", "inst": ["mfq_p", "cbcl", "sdq"], "mode": "clinical"},
    {"name": "dataset_depression_combined", "target": "target_depression", "inst": ["mfq_p", "mfq_sr", "cdi", "cbcl", "sdq"], "mode": "clinical"},
    {"name": "dataset_depression_items", "target": "target_depression", "inst": ["mfq_p", "mfq_sr", "cdi", "cbcl", "sdq"], "mode": "items"},
]

PATTERNS = {
    "target_conduct": [r"disruptive", r"conduct", r"impulse[\s\-]*control", r"oppositional", r"odd\b"],
    "target_adhd": [r"adhd", r"attention", r"hyperactiv", r"deficit"],
    "target_elimination": [r"elimination", r"enuresis", r"encopresis"],
    "target_anxiety": [r"anxiety", r"phobia", r"panic", r"separation anxiety", r"social anxiety"],
    "target_depression": [r"depress", r"major depression", r"depressive", r"mood"],
}


def snake(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(name).strip())
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return re.sub(r"_+", "_", s).strip("_").lower()


def safe_csv(df: pd.DataFrame, p: Path) -> None:
    if p.exists():
        logging.warning("Overwriting %s", p)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)


def safe_txt(text: str, p: Path) -> None:
    if p.exists():
        logging.warning("Overwriting %s", p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def pick_id(df: pd.DataFrame) -> Tuple[Optional[str], List[Tuple[str, float, float]]]:
    cands = [c for c in df.columns if c in ID_CANDIDATES or re.search(r"(participant|subject|\bid\b)", c)]
    if not cands:
        return None, []
    scored = []
    for c in cands:
        nn = df[c].notna().mean()
        uq = df[c].nunique(dropna=True) / max(df[c].notna().sum(), 1)
        scored.append((c, nn, uq))
    pr = {k: i for i, k in enumerate(ID_CANDIDATES)}
    scored = sorted(scored, key=lambda x: (pr.get(x[0], 99), -x[1], -x[2]))
    return scored[0][0], scored


def pick_age(df: pd.DataFrame) -> Tuple[Optional[str], List[Tuple[str, float, float]]]:
    cands = [c for c in df.columns if "age" in c]
    scored = []
    for c in cands:
        num = pd.to_numeric(df[c], errors="coerce")
        nn = num.notna().mean()
        vr = num.dropna().between(0, 120).mean() if num.notna().any() else 0.0
        scored.append((c, nn, vr))
    if not scored:
        return None, []
    scored = sorted(scored, key=lambda x: (-x[1], -x[2], x[0]))
    return scored[0][0], scored


def numify(df: pd.DataFrame, th: float = 0.9) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_numeric_dtype(out[c]) or out[c].dropna().empty:
            continue
        num = pd.to_numeric(out[c], errors="coerce")
        if num.notna().mean() >= th:
            out[c] = num
    return out


class PipelineBuilder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.base = root / "data" / "HBN_synthetic_release11_focused_subset_csv"
        self.proc = root / "data" / "processed"
        self.art = root / "artifacts" / "preprocessing"
        self.specs = root / "artifacts" / "specs"
        self.csvs: List[Path] = []
        self.tables: Dict[str, pd.DataFrame] = {}
        self.map: Dict[str, Dict[str, List[str]]] = {}
        self.leak: List[Dict[str, str]] = []
        self.cohort: Optional[pd.DataFrame] = None
        self.targets: Optional[pd.DataFrame] = None
        self.master: Optional[pd.DataFrame] = None

    def run(self) -> None:
        self._mkdirs()
        self._discover()
        self._inventory()
        self._load_tables()
        self._cohort()
        self._targets()
        self._features()
        outputs = self._final_datasets()
        self._preprocess(outputs)
        self._reports(outputs)
        self._summary(outputs)

    def _mkdirs(self) -> None:
        dirs = [
            self.proc,
            self.proc / "inventory",
            self.proc / "intermediate",
            self.proc / "final",
            self.proc / "final" / "strict_no_leakage",
            self.proc / "final" / "research_extended",
            self.proc / "splits",
            self.proc / "metadata",
            self.proc / "reports",
            self.art,
            self.specs,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _discover(self) -> None:
        self.csvs = sorted(self.base.glob("*.csv"))
        if not self.csvs:
            raise RuntimeError(f"No CSV files in {self.base}")
        logging.info("Found %d CSV files", len(self.csvs))

    def _inventory(self) -> None:
        rows = []
        for p in self.csvs:
            df = pd.read_csv(p, low_memory=False).replace(NA_TOKENS, np.nan)
            df = df.rename(columns={c: snake(c) for c in df.columns})
            id_col, id_scores = pick_id(df)
            age_col, age_scores = pick_age(df)
            name = snake(p.stem)
            t = "metadata"
            if "participants" in name:
                t = "participants"
            elif "diagnosis" in name:
                t = "diagnostics"
            elif name not in {"summary_tables", "sources", "data_dictionary_public_schema", "synthetic_diagnostic_counts"}:
                t = "questionnaire"
            rows.append({
                "file_name": p.name,
                "table_name": name,
                "rows": len(df),
                "columns": df.shape[1],
                "key_columns": ";".join([c for c in [id_col, age_col] if c]),
                "id_column_selected": id_col,
                "id_candidates_scored": json.dumps(id_scores),
                "age_column_selected": age_col,
                "age_candidates_scored": json.dumps(age_scores),
                "null_pct": round(float(df.isna().mean().mean() * 100.0), 4),
                "estimated_table_type": t,
            })
        inv = pd.DataFrame(rows).sort_values("file_name")
        safe_csv(inv, self.proc / "inventory" / "inventory_all_csvs.csv")
        safe_csv(inv, self.proc / "inventory_all_csvs.csv")

    def _load_tables(self) -> None:
        for p in self.csvs:
            name = snake(p.stem)
            df = pd.read_csv(p, low_memory=False).replace(NA_TOKENS, np.nan)
            df = df.rename(columns={c: snake(c) for c in df.columns})
            df = numify(df)
            df = df.drop_duplicates()
            id_col, _ = pick_id(df)
            if id_col and id_col != "participant_id" and "participant_id" not in df.columns:
                df = df.rename(columns={id_col: "participant_id"})
            if "participant_id" in df.columns and df["participant_id"].duplicated(keep=False).any():
                num_cols = [c for c in df.columns if c != "participant_id" and pd.api.types.is_numeric_dtype(df[c])]
                oth_cols = [c for c in df.columns if c not in ["participant_id", *num_cols]]
                n = df.groupby("participant_id", dropna=False)[num_cols].mean() if num_cols else pd.DataFrame()

                def first_valid(s: pd.Series):
                    nnull = s.dropna()
                    return nnull.iloc[0] if not nnull.empty else np.nan

                o = df.groupby("participant_id", dropna=False)[oth_cols].agg(first_valid) if oth_cols else pd.DataFrame()
                if not n.empty and not o.empty:
                    df = n.join(o, how="outer").reset_index()
                elif not n.empty:
                    df = n.reset_index()
                elif not o.empty:
                    df = o.reset_index()
            self.tables[name] = df
            logging.info("Loaded %s rows=%d cols=%d", name, len(df), df.shape[1])

    def _cohort(self) -> None:
        pt = self.tables.get("participants")
        if pt is None or "participant_id" not in pt.columns:
            raise RuntimeError("participants table with participant_id is required")
        age_col = "age_years" if "age_years" in pt.columns else pick_age(pt)[0]
        if not age_col:
            raise RuntimeError("No age column found")
        pt = pt.copy()
        pt[age_col] = pd.to_numeric(pt[age_col], errors="coerce")
        elig = pt[age_col].between(6, 11, inclusive="both")
        cohort = pt.loc[elig, [c for c in ["participant_id", age_col, "sex_assigned_at_birth", "site", "release"] if c in pt.columns]].copy()
        cohort = cohort.rename(columns={age_col: "age_years"})
        self.cohort = cohort
        summary = pd.DataFrame([
            {"metric": "total_original", "value": int(len(pt))},
            {"metric": "total_eligible_6_11", "value": int(len(cohort))},
            {"metric": "excluded_missing_age", "value": int(pt[age_col].isna().sum())},
            {"metric": "excluded_outside_6_11", "value": int((~pt[age_col].between(6, 11, inclusive="both") & pt[age_col].notna()).sum())},
            {"metric": "age_column_selected", "value": "age_years"},
        ])
        safe_csv(summary, self.proc / "inventory" / "cohort_summary.csv")
        safe_csv(summary, self.proc / "cohort_summary.csv")
        safe_csv(cohort, self.proc / "intermediate" / "cohort_6_11.csv")

    def _targets(self) -> None:
        if self.cohort is None:
            raise RuntimeError("cohort required")
        ids = self.cohort["participant_id"].astype(str)
        t = pd.DataFrame({"participant_id": ids})
        for c in TARGETS:
            t[c] = 0
        src_hit = pd.DataFrame({"participant_id": ids})
        for c in TARGETS:
            src_hit[f"source_{c}"] = pd.Series([None] * len(ids), dtype="object")
        map_rows, unmapped = [], {}
        diag_support = pd.DataFrame({"participant_id": ids})

        for src in DIAG_PRIORITY:
            df = self.tables.get(src)
            if df is None or "participant_id" not in df.columns:
                continue
            df = df.copy()
            df["participant_id"] = df["participant_id"].astype(str)
            df = df[df["participant_id"].isin(set(ids))]
            st = pd.DataFrame({"participant_id": df["participant_id"]})
            for c in TARGETS:
                st[c] = 0
            if src == "diagnosis_clinician_consensus":
                dcols = [c for c in df.columns if re.match(r"diagnosis_\d+$", c)]
                for _, r in df.iterrows():
                    pid = r["participant_id"]
                    texts = [str(r[c]).strip() for c in dcols if pd.notna(r[c])]
                    texts = [d for d in texts if d and d.lower() != "no diagnosis given"]
                    for txt in texts:
                        hit = False
                        for tc, pats in PATTERNS.items():
                            if any(re.search(p, txt, flags=re.I) for p in pats):
                                st.loc[st["participant_id"] == pid, tc] = 1
                                hit = True
                        if not hit:
                            unmapped[txt] = unmapped.get(txt, 0) + 1
                if "n_diagnoses" in df.columns:
                    diag_support = diag_support.merge(df[["participant_id", "n_diagnoses"]].rename(columns={"n_diagnoses": "diag_clinician_n_diagnoses"}), on="participant_id", how="left")
            else:
                km = {
                    "adhd_present": "target_adhd",
                    "anxietydisorders_present": "target_anxiety",
                    "depressivedisorders_present": "target_depression",
                    "disruptiveimpulsecontrolconductdisorders_present": "target_conduct",
                    "eliminationdisorders_present": "target_elimination",
                }
                for sc, tc in km.items():
                    if sc in df.columns:
                        st[tc] = pd.to_numeric(df[sc], errors="coerce").fillna(0).clip(0, 1).astype(int)
                        diag_support = diag_support.merge(df[["participant_id", sc]].rename(columns={sc: f"diag_{src}_{sc}"}), on="participant_id", how="left")
                for ac in ["interview_complete", "respondent"]:
                    if ac in df.columns:
                        diag_support = diag_support.merge(df[["participant_id", ac]].rename(columns={ac: f"diag_{src}_{ac}"}), on="participant_id", how="left")
            m = t.merge(st, on="participant_id", suffixes=("", "_src"), how="left")
            for tc in TARGETS:
                sc = f"{tc}_src"
                m[sc] = m[sc].fillna(0).astype(int)
                m[tc] = m[[tc, sc]].max(axis=1)
                mask = m[sc].eq(1) & src_hit[f"source_{tc}"].isna()
                src_hit.loc[mask, f"source_{tc}"] = src
                map_rows.append({"source": src, "target": tc, "positive_count": int(m[sc].sum())})
            t = m.drop(columns=[c for c in m.columns if c.endswith("_src")])

        t = t.merge(src_hit, on="participant_id", how="left")
        t[TARGETS] = t[TARGETS].fillna(0).astype(int)
        if "diag_clinician_n_diagnoses" in diag_support.columns:
            diag_support["diag_clinician_n_diagnoses"] = pd.to_numeric(diag_support["diag_clinician_n_diagnoses"], errors="coerce")
            t["n_diagnoses"] = diag_support["diag_clinician_n_diagnoses"].fillna(t[TARGETS].sum(axis=1))
        else:
            t["n_diagnoses"] = t[TARGETS].sum(axis=1)
        t["has_any_target_disorder"] = (t[TARGETS].sum(axis=1) > 0).astype(int)
        t["comorbidity_count_5targets"] = t[TARGETS].sum(axis=1).astype(int)
        t["label_pattern"] = t[LABEL_ORDER].astype(str).agg("".join, axis=1)
        self.targets = t
        self.diag_support = diag_support

        rep = pd.DataFrame(map_rows)
        if unmapped:
            rep = pd.concat([rep, pd.DataFrame([{"source": "diagnosis_clinician_consensus", "target": "unmapped_diagnosis_text", "positive_count": int(v), "value": k} for k, v in sorted(unmapped.items(), key=lambda x: (-x[1], x[0]))])], ignore_index=True)
        safe_csv(rep, self.proc / "reports" / "diagnosis_mapping_report.csv")
        safe_csv(t, self.proc / "intermediate" / "targets_6_11.csv")

    def _features(self) -> None:
        if self.cohort is None or self.targets is None:
            raise RuntimeError("cohort and targets required")
        master = self.cohort.copy()
        for name, df in sorted(self.tables.items()):
            if name in {"participants", "data_dictionary_public_schema", "summary_tables", "sources", "synthetic_diagnostic_counts"} or name.startswith("diagnosis"):
                continue
            if "participant_id" not in df.columns:
                continue
            d = df.copy()
            d["participant_id"] = d["participant_id"].astype(str)
            d = d[d["participant_id"].isin(set(master["participant_id"].astype(str)))]
            age_cols = [c for c in d.columns if "age" in c]
            fcols = [c for c in d.columns if c not in ["participant_id", *age_cols]]
            if not fcols:
                continue
            d = d[["participant_id", *fcols]].copy()
            d = numify(d)
            items = [c for c in fcols if re.match(rf"^{re.escape(name)}_\d+$", c)]
            clinical = [c for c in fcols if c not in items]
            if items and not clinical:
                s = f"{name}_item_sum"
                d[s] = d[items].sum(axis=1, min_count=1)
                clinical.append(s)
                fcols.append(s)
            has = f"has_{name}"
            d[has] = d[fcols].notna().any(axis=1).astype(int)
            cols = ["participant_id", has, *fcols]
            coll = [c for c in cols if c != "participant_id" and c in master.columns]
            if coll:
                ren = {c: f"{name}__{c}" for c in coll}
                d = d.rename(columns=ren)
                has = ren.get(has, has)
                items = [ren.get(c, c) for c in items]
                clinical = [ren.get(c, c) for c in clinical]
                fcols = [ren.get(c, c) for c in fcols]
            master = master.merge(d[["participant_id", has, *fcols]], on="participant_id", how="left")
            self.map[name] = {"items": sorted(items), "clinical": sorted(clinical), "all": sorted(fcols), "availability": [has]}
        master = master.merge(self.targets, on="participant_id", how="left")
        if hasattr(self, "diag_support"):
            ds = self.diag_support.copy()
            ds["participant_id"] = ds["participant_id"].astype(str)
            master = master.merge(ds, on="participant_id", how="left")
        self.master = master
        safe_csv(master, self.proc / "intermediate" / "master_with_targets_and_features.csv")
        self._feature_catalog(master)
        self._missingness(master)

    def _feature_catalog(self, master: pd.DataFrame) -> None:
        src = {}
        for t, m in self.map.items():
            for group in m.values():
                for c in group:
                    src[c] = t
        rows = []
        for c in master.columns:
            role = "feature"
            if c in TARGETS:
                role = "target"
            elif c == "participant_id":
                role = "identifier"
            elif c in {"age_years", "sex_assigned_at_birth", "site", "release"}:
                role = "demographic"
            elif c.startswith("has_"):
                role = "availability_flag"
            elif re.search(r"_\d+$", c):
                role = "item"
            elif any(k in c for k in ["total", "proxy", "subscale", "cut", "score", "symptom", "impact"]):
                role = "clinical_summary"
            elif "diag_" in c or "diagnosis" in c:
                role = "diagnostic_support"
            s = master[c]
            rows.append({
                "feature_name": c,
                "source_table": src.get(c, "participants" if role == "demographic" else "derived"),
                "feature_role": role,
                "dtype": str(s.dtype),
                "missing_pct": round(float(s.isna().mean() * 100.0), 4),
                "is_constant": int(s.nunique(dropna=True) <= 1),
                "is_near_empty": int(s.isna().mean() >= 0.95),
            })
        safe_csv(pd.DataFrame(rows).sort_values(["feature_role", "feature_name"]), self.proc / "reports" / "feature_catalog.csv")

    def _missingness(self, master: pd.DataFrame) -> None:
        rows = [{"dataset": "master", "column": c, "missing_pct": round(float(master[c].isna().mean() * 100.0), 4), "is_near_empty": int(master[c].isna().mean() >= 0.95)} for c in master.columns]
        safe_csv(pd.DataFrame(rows).sort_values("missing_pct", ascending=False), self.proc / "reports" / "missingness_report.csv")

    def _select_cols(self, spec: Dict[str, object], pool: List[str]) -> List[str]:
        mode = str(spec.get("mode"))
        cols = [c for c in ["age_years", "sex_assigned_at_birth", "site", "release"] if c in pool]
        for ins in spec.get("inst", []):
            m = self.map.get(ins, {})
            cols.extend(m.get("availability", []))
            if mode == "items":
                cols.extend(m.get("items", [])); cols.extend(m.get("clinical", []))
            elif mode in {"clinical", "combined"}:
                cols.extend(m.get("clinical", []))
            elif mode in {"minimal", "core"}:
                cl = m.get("clinical", [])
                sl = [c for c in cl if any(k in c for k in ["total", "proxy", "subscale", "attention", "hyper", "conduct", "anxiety", "depress", "impact", "symptom"])]
                cols.extend(sl if sl else cl)
            else:
                cols.extend(m.get("all", []))
        return [c for c in dict.fromkeys(cols) if c in pool]

    def _strict_keep(self, df: pd.DataFrame, cols: List[str], target: str) -> List[str]:
        keep = []
        y = df[target] if target in df.columns else None
        for c in cols:
            low = c.lower()
            reason = None
            if low.startswith("diag_"):
                reason = "diagnostic_support_prefix"
            elif "diagnosis" in low:
                reason = "diagnosis_string_or_field"
            elif low.endswith("_present"):
                reason = "diagnosis_presence_flag"
            elif low in {"n_diagnoses", "has_any_target_disorder", "comorbidity_count_5targets", "label_pattern"}:
                reason = "target_derived_summary"
            elif low.startswith("source_target_"):
                reason = "target_source_field"
            if reason is None and y is not None:
                s = pd.to_numeric(df[c], errors="coerce") if df[c].notna().any() else pd.Series(dtype=float)
                if not s.empty and s.notna().all() and set(s.dropna().unique()).issubset({0, 1}) and s.equals(y):
                    reason = "exact_equivalent_to_primary_target"
            if reason:
                self.leak.append({"feature": c, "reason": reason, "primary_target": target})
            else:
                keep.append(c)
        return keep

    def _final_datasets(self) -> Dict[str, Dict[str, Path]]:
        if self.master is None:
            raise RuntimeError("master required")
        m = self.master.copy(); m["participant_id"] = m["participant_id"].astype(str)
        pool = [c for c in m.columns if c not in ["participant_id", *TARGETS, "label_pattern", "n_diagnoses", "has_any_target_disorder", "comorbidity_count_5targets"] and not c.startswith("source_target_")]
        out: Dict[str, Dict[str, Path]] = {}

        skeep = self._strict_keep(m, pool, "target_adhd")
        strict = m[["participant_id", *skeep, *TARGETS, "n_diagnoses", "has_any_target_disorder", "comorbidity_count_5targets", "label_pattern"]].copy()
        research = m[["participant_id", *pool, *TARGETS, "n_diagnoses", "has_any_target_disorder", "comorbidity_count_5targets", "label_pattern"]].copy()
        sp = self.proc / "final" / "strict_no_leakage" / "master_multilabel_ready_strict_no_leakage.csv"
        rp = self.proc / "final" / "research_extended" / "master_multilabel_ready_research_extended.csv"
        safe_csv(strict, sp); safe_csv(research, rp); safe_csv(strict, self.proc / "final" / "master_multilabel_ready.csv")
        out["master_multilabel_ready"] = {"strict_no_leakage": sp, "research_extended": rp}

        for spec in DATASET_SPECS:
            name, target = spec["name"], spec["target"]
            sel = self._select_cols(spec, pool)
            base = m[["participant_id", *sel, *TARGETS, "n_diagnoses", "has_any_target_disorder", "comorbidity_count_5targets", "label_pattern"]].copy()
            base["primary_target"] = target; base["dataset_name"] = name; base["is_exploratory"] = int(spec.get("exploratory", 0))
            sk = self._strict_keep(base, sel, target)
            strict = base[["participant_id", *sk, *TARGETS, "n_diagnoses", "has_any_target_disorder", "comorbidity_count_5targets", "label_pattern", "primary_target", "dataset_name", "is_exploratory"]].copy()
            research = base[["participant_id", *sel, *TARGETS, "n_diagnoses", "has_any_target_disorder", "comorbidity_count_5targets", "label_pattern", "primary_target", "dataset_name", "is_exploratory"]].copy()
            sp = self.proc / "final" / "strict_no_leakage" / f"{name}_strict_no_leakage.csv"
            rp = self.proc / "final" / "research_extended" / f"{name}_research_extended.csv"
            safe_csv(strict, sp); safe_csv(research, rp)
            out[name] = {"strict_no_leakage": sp, "research_extended": rp}

        leak_df = pd.DataFrame(self.leak)
        if leak_df.empty:
            leak_df = pd.DataFrame(columns=["feature", "reason", "primary_target"])
        else:
            leak_df = leak_df.drop_duplicates().sort_values(["primary_target", "feature"])
        safe_csv(leak_df, self.proc / "reports" / "leakage_exclusion_report.csv")
        return out

    def _xy(self, df: pd.DataFrame, target: str, ds_name: str):
        y = df[TARGETS].copy() if ds_name == "master_multilabel_ready" else df[[target]].copy()
        nonf = {"participant_id", "primary_target", "dataset_name", "is_exploratory", "label_pattern", "n_diagnoses", "has_any_target_disorder", "comorbidity_count_5targets", *TARGETS, *(f"source_{c}" for c in TARGETS)}
        X_raw = df[[c for c in df.columns if c not in nonf]].copy()
        X_clean = numify(X_raw).dropna(axis=1, how="all")
        return X_raw, X_clean, y

    def _split(self, X: pd.DataFrame, y: pd.DataFrame, ids: pd.Series, ds_name: str, target: str, label_pattern: Optional[pd.Series]):
        strat = None
        if ds_name == "master_multilabel_ready" and label_pattern is not None:
            vc = label_pattern.value_counts()
            if not vc.empty and len(vc) > 1 and vc.min() >= 2:
                strat = label_pattern
        elif target in y.columns:
            vc = y[target].value_counts()
            if not vc.empty and len(vc) > 1 and vc.min() >= 2:
                strat = y[target]
        X_tv, X_te, y_tv, y_te, i_tv, i_te = train_test_split(X, y, ids, test_size=0.15, random_state=RANDOM_STATE, stratify=strat)
        strat2 = None
        if strat is not None:
            strat2 = strat.loc[X_tv.index]
            if strat2.value_counts().min() < 2:
                strat2 = None
        X_tr, X_va, y_tr, y_va, i_tr, i_va = train_test_split(X_tv, y_tv, i_tv, test_size=0.1764706, random_state=RANDOM_STATE, stratify=strat2)
        return {
            "X_train": X_tr, "X_val": X_va, "X_test": X_te,
            "y_train": y_tr, "y_val": y_va, "y_test": y_te,
            "ids_train": pd.DataFrame({"participant_id": i_tr}),
            "ids_val": pd.DataFrame({"participant_id": i_va}),
            "ids_test": pd.DataFrame({"participant_id": i_te}),
        }

    def _preprocess(self, outputs: Dict[str, Dict[str, Path]]) -> None:
        bal = []
        for ds, versions in outputs.items():
            for ver, p in versions.items():
                df = pd.read_csv(p); df["participant_id"] = df["participant_id"].astype(str)
                target = "target_adhd"
                if "primary_target" in df.columns and df["primary_target"].notna().any():
                    target = str(df["primary_target"].dropna().iloc[0])
                elif "conduct" in ds: target = "target_conduct"
                elif "elimination" in ds: target = "target_elimination"
                elif "anxiety" in ds: target = "target_anxiety"
                elif "depression" in ds: target = "target_depression"
                X_raw, X_clean, y = self._xy(df, target, ds)
                ad = self.art / ds / ver; ad.mkdir(parents=True, exist_ok=True)
                safe_csv(X_raw, ad / "X_raw.csv"); safe_csv(X_clean, ad / "X_cleaned.csv"); safe_csv(y, ad / "y.csv")
                lp = df["label_pattern"] if "label_pattern" in df.columns else None
                s = self._split(X_clean, y, df["participant_id"], ds, target, lp)
                sd = self.proc / "splits" / ds / ver; sd.mkdir(parents=True, exist_ok=True)
                for n, d in s.items():
                    safe_csv(d.reset_index(drop=True), sd / f"{n}.csv")
                ncols = [c for c in s["X_train"].columns if pd.api.types.is_numeric_dtype(s["X_train"][c])]
                ccols = [c for c in s["X_train"].columns if c not in ncols]
                prep = ColumnTransformer([
                    ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), ncols),
                    ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=True))]), ccols),
                ], remainder="drop")
                prep.fit(s["X_train"])
                Xt = prep.transform(s["X_train"]); Xv = prep.transform(s["X_val"]); Xe = prep.transform(s["X_test"]); Xall = prep.transform(X_clean)
                sparse.save_npz(ad / "X_train_encoded.npz", sparse.csr_matrix(Xt))
                sparse.save_npz(ad / "X_val_encoded.npz", sparse.csr_matrix(Xv))
                sparse.save_npz(ad / "X_test_encoded.npz", sparse.csr_matrix(Xe))
                sparse.save_npz(ad / "X_encoded.npz", sparse.csr_matrix(Xall))
                safe_csv(pd.DataFrame({"encoded_feature": prep.get_feature_names_out()}), ad / "encoded_feature_names.csv")
                joblib.dump(prep, ad / "preprocessor.joblib")
                meta = {
                    "dataset_name": ds, "version": ver, "primary_target": target, "random_state": RANDOM_STATE,
                    "n_rows": int(len(df)), "n_features_raw": int(X_raw.shape[1]), "n_features_cleaned": int(X_clean.shape[1]), "n_features_encoded": int(Xall.shape[1]),
                    "numeric_features": ncols, "categorical_features": ccols,
                    "split_sizes": {"train": int(len(s["X_train"])), "val": int(len(s["X_val"])), "test": int(len(s["X_test"]))},
                    "imputation": {"numeric": "median", "categorical": "most_frequent"}, "encoding": "onehot_handle_unknown_ignore",
                }
                safe_txt(json.dumps(meta, indent=2), ad / "metadata.json")
                if ds == "master_multilabel_ready":
                    for tc in TARGETS:
                        pos, tot = int(y[tc].sum()), int(len(y))
                        bal.append({"dataset_name": ds, "version": ver, "target": tc, "n_total": tot, "n_positive": pos, "n_negative": tot - pos, "positive_rate": round(pos / tot if tot else 0.0, 6)})
                else:
                    pos, tot = int(y[target].sum()), int(len(y))
                    bal.append({"dataset_name": ds, "version": ver, "target": target, "n_total": tot, "n_positive": pos, "n_negative": tot - pos, "positive_rate": round(pos / tot if tot else 0.0, 6)})
        safe_csv(pd.DataFrame(bal).sort_values(["dataset_name", "version", "target"]), self.proc / "reports" / "class_balance_report.csv")

    def _reports(self, outputs: Dict[str, Dict[str, Path]]) -> None:
        if self.targets is None:
            raise RuntimeError("targets required")
        com = self.targets.groupby("comorbidity_count_5targets", dropna=False).size().reset_index(name="participant_count").sort_values("comorbidity_count_5targets")
        safe_csv(com, self.proc / "reports" / "comorbidity_report.csv")
        fc = pd.read_csv(self.proc / "reports" / "feature_catalog.csv")
        qf = fc[fc["feature_role"].isin(["item", "clinical_summary", "availability_flag", "demographic"])].copy()

        def domain(src: str) -> str:
            if src in {"swan", "conners"}: return "adhd"
            if src in {"icut", "ari_p", "ari_sr"}: return "conduct"
            if src in {"scared_p", "scared_sr", "stai"}: return "anxiety"
            if src in {"mfq_p", "mfq_sr", "cdi", "bdi"}: return "depression"
            if src in {"cbcl", "sdq", "ysr"}: return "transdiagnostic"
            return "general"

        qm = pd.DataFrame({
            "questionnaire_item_id": "",
            "feature_name": qf["feature_name"],
            "source_table": qf["source_table"],
            "disorder_domain": qf["source_table"].map(domain),
            "expected_dtype": qf["dtype"],
            "mapping_rule": "direct_or_documented_transform",
            "notes": "",
        })
        safe_csv(qm, self.proc / "reports" / "questionnaire_feature_mapping_template.csv")

        prep_md = """# Preprocessing Decisions\n\n- ID selected by priority+uniqueness; final anchor is participant_id.\n- Cohort filtered to age_years 6..11 from participants table.\n- Missing tokens normalized: \"\", \" \", NA/N-A/null/None/nan and variants.\n- snake_case normalization applied to all columns.\n- Numeric-like conversion applied when >=90% parsable.\n- strict_no_leakage removes diagnosis support and target-derived proxies.\n- Dataset splits: 70/15/15 with random_state=42; stratification when feasible.\n"""
        safe_txt(prep_md, self.proc / "reports" / "preprocessing_decisions.md")

        rf_md = """# Random Forest Evaluation Specification\n\nBinary metrics: accuracy, balanced_accuracy, precision, recall/sensitivity, specificity, f1, roc_auc, pr_auc, confusion_matrix, class report, feature importance, permutation importance, calibration.\n\nMultilabel metrics: subset accuracy, hamming loss, macro/micro/weighted precision-recall-f1, per-label confusion, roc_auc/pr_auc macro-micro when applicable, comorbidity slices by label_pattern and comorbidity_count_5targets.\n\nDeployment profile output: per-disorder risk, key contributors, clinical flags, confidence indicators, comorbidity flags.\n"""
        safe_txt(rf_md, self.specs / "random_forest_evaluation_spec.md")
        safe_txt(rf_md, self.proc / "reports" / "random_forest_evaluation_spec.md")

        dd = ["# Dataset Dictionary", "", "## Final datasets"]
        for ds, versions in sorted(outputs.items()):
            for ver, p in versions.items():
                d = pd.read_csv(p)
                dd.append(f"- {ds} ({ver}): rows={len(d)}, columns={d.shape[1]}, path={p.relative_to(self.root)}")
        dd += ["", "## Core targets", *[f"- {t}: binary target label" for t in TARGETS]]
        safe_txt("\n".join(dd) + "\n", self.proc / "reports" / "dataset_dictionary.md")

        mr = """# Model Readiness Report\n\n- Cohort restricted to 6-11 years.\n- Strict and research dataset versions generated.\n- sklearn-ready preprocessing artifacts generated per dataset/version.\n\nRisks:\n- Target imbalance present in several disorders (see class_balance_report.csv).\n- Elimination datasets are exploratory due limited direct instruments in 6-11.\n- Adult-only instruments (ASR/BDI/CAARS/STAI) excluded from 6-11 features.\n"""
        safe_txt(mr, self.proc / "reports" / "model_readiness_report.md")

        copies = {
            "diagnosis_mapping_report.csv": "reports/diagnosis_mapping_report.csv",
            "feature_catalog.csv": "reports/feature_catalog.csv",
            "leakage_exclusion_report.csv": "reports/leakage_exclusion_report.csv",
            "missingness_report.csv": "reports/missingness_report.csv",
            "class_balance_report.csv": "reports/class_balance_report.csv",
            "comorbidity_report.csv": "reports/comorbidity_report.csv",
            "preprocessing_decisions.md": "reports/preprocessing_decisions.md",
            "dataset_dictionary.md": "reports/dataset_dictionary.md",
            "model_readiness_report.md": "reports/model_readiness_report.md",
            "questionnaire_feature_mapping_template.csv": "reports/questionnaire_feature_mapping_template.csv",
            "random_forest_evaluation_spec.md": "reports/random_forest_evaluation_spec.md",
        }
        for dst, src in copies.items():
            sp = self.proc / src
            dp = self.proc / dst
            if sp.suffix == ".csv": safe_csv(pd.read_csv(sp), dp)
            else: safe_txt(sp.read_text(encoding="utf-8"), dp)

    def _summary(self, outputs: Dict[str, Dict[str, Path]]) -> None:
        print("\n=== PIPELINE SUMMARY ===")
        print(f"Input folder: {self.base}")
        print(f"CSV files discovered: {len(self.csvs)}")
        if self.cohort is not None: print(f"Cohort (age 6-11): {len(self.cohort)} participants")
        print("\nDatasets ready for training:")
        for ds, versions in sorted(outputs.items()):
            for ver, p in versions.items():
                d = pd.read_csv(p)
                print(f"- {ds} [{ver}] -> rows={len(d)}, cols={d.shape[1]}, targets={','.join([c for c in TARGETS if c in d.columns])}, path={p.relative_to(self.root)}")
        print("\nKey reports:")
        print(f"- Inventory: {(self.proc / 'inventory_all_csvs.csv').relative_to(self.root)}")
        print(f"- Cohort summary: {(self.proc / 'cohort_summary.csv').relative_to(self.root)}")
        print(f"- Feature catalog: {(self.proc / 'feature_catalog.csv').relative_to(self.root)}")
        print(f"- Model readiness: {(self.proc / 'model_readiness_report.md').relative_to(self.root)}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    root = Path(__file__).resolve().parents[1]
    PipelineBuilder(root).run()


if __name__ == "__main__":
    main()

