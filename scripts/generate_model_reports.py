from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

import pandas as pd

from ml_rf_common import safe_csv, safe_json, select_best_binary_per_disorder


def _build_training_log(root: Path, binary: pd.DataFrame, multilabel: pd.DataFrame) -> str:
    split_bin = root / "reports" / "training" / "split_decisions_binary.csv"
    split_multi = root / "reports" / "training" / "split_decisions_multilabel.csv"
    split_bin_df = pd.read_csv(split_bin) if split_bin.exists() else pd.DataFrame()
    split_multi_df = pd.read_csv(split_multi) if split_multi.exists() else pd.DataFrame()

    reg_bin = int((split_bin_df["action"] == "regenerated").sum()) if not split_bin_df.empty else 0
    reg_multi = int((split_multi_df["action"] == "regenerated").sum()) if not split_multi_df.empty else 0

    lines = [
        "# Training Log",
        "",
        "Pipeline ejecutado en entorno simulado, usando datasets ya preparados (strict_no_leakage como baseline).",
        "",
        f"- Modelos binarios entrenados: {len(binary)}",
        f"- Modelos multilabel entrenados: {len(multilabel)}",
        f"- Splits binarios regenerados: {reg_bin}",
        f"- Splits multilabel regenerados: {reg_multi}",
        "",
        "## Notas",
        "- No se rehizo limpieza/preparación de datos.",
        "- Se aplicaron guardas anti-leakage antes de cada entrenamiento.",
        "- research_extended se trató como comparación secundaria.",
    ]
    return "\n".join(lines) + "\n"


def _build_model_registry(binary: pd.DataFrame, multilabel: pd.DataFrame, best_binary: pd.DataFrame, best_multilabel_id: str) -> pd.DataFrame:
    rows = []
    best_binary_ids = set(best_binary["model_id"].tolist())
    for r in binary.itertuples(index=False):
        rows.append(
            {
                "model_id": r.model_id,
                "task": "binary",
                "disorder": r.disorder,
                "dataset_name": r.dataset_name,
                "variant": r.variant,
                "version": r.version,
                "is_primary_recommended": int(r.model_id in best_binary_ids),
                "threshold": r.threshold_value,
                "threshold_method": r.threshold_method,
                "balanced_accuracy_test": r.balanced_accuracy_test,
                "recall_test": r.recall_test,
                "specificity_test": r.specificity_test,
                "f1_test": r.f1_test,
                "roc_auc_test": r.roc_auc_test,
                "pr_auc_test": r.pr_auc_test,
                "artifact_pipeline_path": r.artifact_pipeline_path,
                "artifact_metadata_path": r.artifact_metadata_path,
                "artifact_calibrated_path": r.artifact_calibrated_path,
            }
        )
    for r in multilabel.itertuples(index=False):
        rows.append(
            {
                "model_id": r.model_id,
                "task": "multilabel",
                "disorder": "multilabel",
                "dataset_name": r.dataset_name,
                "variant": "master",
                "version": r.version,
                "is_primary_recommended": int(r.model_id == best_multilabel_id),
                "threshold": 0.5,
                "threshold_method": "fixed_0_5",
                "balanced_accuracy_test": None,
                "recall_test": None,
                "specificity_test": None,
                "f1_test": r.micro_f1_test,
                "roc_auc_test": None,
                "pr_auc_test": None,
                "artifact_pipeline_path": r.artifact_pipeline_path,
                "artifact_metadata_path": r.artifact_metadata_path,
                "artifact_calibrated_path": "",
            }
        )
    return pd.DataFrame(rows)


def _build_recommendations_md(
    best_binary: pd.DataFrame,
    best_multilabel: pd.Series,
    strict_vs_research: pd.DataFrame,
) -> str:
    lines = [
        "# Final Model Recommendations",
        "",
        "Este reporte resume recomendaciones para producción experimental (no diagnóstico clínico definitivo).",
        "",
        "## Recomendación por trastorno (baseline strict_no_leakage)",
    ]
    for r in best_binary.sort_values("disorder").itertuples(index=False):
        lines.append(
            (
                f"- **{r.disorder}**: `{r.dataset_name}` ({r.version}) | "
                f"balanced_accuracy={r.balanced_accuracy_test:.4f}, recall={r.recall_test:.4f}, "
                f"specificity={r.specificity_test:.4f}, f1={r.f1_test:.4f}, "
                f"threshold={r.threshold_value:.4f} ({r.threshold_method})"
            )
        )

    lines += [
        "",
        "## Mejor modelo multietiqueta",
        (
            f"- `{best_multilabel['dataset_name']}` ({best_multilabel['version']}) | "
            f"micro_f1={best_multilabel['micro_f1_test']:.4f}, macro_f1={best_multilabel['macro_f1_test']:.4f}, "
            f"subset_accuracy={best_multilabel['subset_accuracy_test']:.4f}, hamming_loss={best_multilabel['hamming_loss_test']:.4f}"
        ),
        "",
        "## Strict vs Research (resumen)",
    ]
    deltas = strict_vs_research.dropna(subset=["delta_balanced_accuracy_research_minus_strict"], how="all")
    for r in deltas.sort_values(["disorder", "variant"]).itertuples(index=False):
        if r.disorder == "multilabel":
            continue
        lines.append(
            f"- {r.disorder}/{r.variant}: Δbalanced_accuracy(research-strict)={r.delta_balanced_accuracy_research_minus_strict:.4f}"
        )

    lines += [
        "",
        "## Estado exploratorio",
        "- Elimination se mantiene exploratorio por menor cobertura específica y mayor sensibilidad a ruido de features.",
        "",
        "## Advertencias",
        "- Los resultados son experimentales en entorno simulado.",
        "- Deben interpretarse como alerta temprana, no diagnóstico definitivo.",
        "- En clases minoritarias, priorizar sensibilidad con control de especificidad según contexto operativo.",
    ]
    return "\n".join(lines) + "\n"


def _write_inference_scripts(root: Path) -> None:
    inference_dir = root / "artifacts" / "inference"
    inference_dir.mkdir(parents=True, exist_ok=True)

    predict_binary_code = dedent(
        """
        from __future__ import annotations
        import json
        from pathlib import Path
        from typing import Dict, Any

        import joblib
        import numpy as np
        import pandas as pd


        ROOT = Path(__file__).resolve().parents[2]
        REGISTRY_PATH = ROOT / "reports" / "training" / "model_registry.csv"


        def _load_registry() -> pd.DataFrame:
            return pd.read_csv(REGISTRY_PATH)


        def _risk_band(prob: float) -> str:
            if prob < 0.33:
                return "low"
            if prob < 0.66:
                return "moderate"
            return "high"


        def _evidence_quality(missing_ratio: float) -> str:
            if missing_ratio >= 0.4:
                return "weak"
            if missing_ratio >= 0.2:
                return "medium"
            return "strong"


        def predict_binary(disorder: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            reg = _load_registry()
            row = reg[(reg["task"] == "binary") & (reg["disorder"] == disorder) & (reg["is_primary_recommended"] == 1)]
            if row.empty:
                raise ValueError(f"No recommended binary model found for disorder={disorder}")
            r = row.iloc[0]
            model_path = ROOT / r["artifact_pipeline_path"]
            metadata = json.loads((ROOT / r["artifact_metadata_path"]).read_text(encoding="utf-8"))
            calibr_path = str(r.get("artifact_calibrated_path", "")).strip()

            predictor = joblib.load(ROOT / calibr_path) if calibr_path else joblib.load(model_path)
            X = pd.DataFrame([payload])
            for c in metadata["feature_columns"]:
                if c not in X.columns:
                    X[c] = np.nan
            X = X[metadata["feature_columns"]]

            prob = float(predictor.predict_proba(X)[:, 1][0])
            threshold = float(r["threshold"])
            label = int(prob >= threshold)

            missing = [c for c in metadata["feature_columns"] if c not in payload or pd.isna(payload.get(c))]
            missing_ratio = (len(missing) / max(len(metadata["feature_columns"]), 1))
            quality = _evidence_quality(missing_ratio)

            # Approx local contributors from encoded feature deltas.
            pipe = joblib.load(model_path)
            encoded = pipe.named_steps["preprocessor"].transform(X)
            encoded = np.asarray(encoded[0]).ravel()
            med = np.asarray(metadata.get("encoded_feature_medians", []), dtype=float)
            imp = np.asarray(metadata.get("encoded_feature_importances", []), dtype=float)
            feat = metadata.get("encoded_feature_names", [])
            top_pos, top_neg = [], []
            if len(med) == len(imp) == len(encoded) == len(feat) and len(feat) > 0:
                contrib = (encoded - med) * imp
                pos_idx = np.argsort(contrib)[::-1][:10]
                neg_idx = np.argsort(contrib)[:10]
                top_pos = [{"feature": feat[i], "score": float(contrib[i])} for i in pos_idx]
                top_neg = [{"feature": feat[i], "score": float(contrib[i])} for i in neg_idx]

            return {
                "disorder": disorder,
                "probability_score": prob,
                "predicted_label": label,
                "threshold_used": threshold,
                "risk_band": _risk_band(prob),
                "evidence_quality": quality,
                "missing_critical_features": missing[:20],
                "top_contributors": {"positive": top_pos, "negative": top_neg},
                "note": "Experimental early-warning output. Not a definitive diagnosis.",
            }


        if __name__ == "__main__":
            sample = {"age_years": 8, "sex_assigned_at_birth": "M"}
            print(predict_binary("adhd", sample))
        """
    ).strip() + "\n"

    predict_multilabel_code = dedent(
        """
        from __future__ import annotations
        import json
        from pathlib import Path
        from typing import Dict, Any

        import joblib
        import numpy as np
        import pandas as pd

        TARGETS = ["target_conduct", "target_adhd", "target_elimination", "target_anxiety", "target_depression"]
        ROOT = Path(__file__).resolve().parents[2]
        REGISTRY_PATH = ROOT / "reports" / "training" / "model_registry.csv"


        def _risk_band(prob: float) -> str:
            if prob < 0.33:
                return "low"
            if prob < 0.66:
                return "moderate"
            return "high"


        def predict_multilabel(payload: Dict[str, Any]) -> Dict[str, Any]:
            reg = pd.read_csv(REGISTRY_PATH)
            row = reg[(reg["task"] == "multilabel") & (reg["is_primary_recommended"] == 1)]
            if row.empty:
                raise ValueError("No recommended multilabel model found.")
            r = row.iloc[0]
            model_path = ROOT / r["artifact_pipeline_path"]
            metadata = json.loads((ROOT / r["artifact_metadata_path"]).read_text(encoding="utf-8"))
            model = joblib.load(model_path)

            X = pd.DataFrame([payload])
            for c in metadata["feature_columns"]:
                if c not in X.columns:
                    X[c] = np.nan
            X = X[metadata["feature_columns"]]

            probs_list = model.predict_proba(X)
            probs = [float(arr[:, 1][0] if arr.shape[1] > 1 else arr[:, 0][0]) for arr in probs_list]
            labels = [int(p >= 0.5) for p in probs]
            positive_count = int(sum(labels))

            results = {}
            for target, p, yhat in zip(TARGETS, probs, labels):
                results[target] = {"probability_score": p, "predicted_label": yhat, "risk_band": _risk_band(p)}

            missing = [c for c in metadata["feature_columns"] if c not in payload or pd.isna(payload.get(c))]
            missing_ratio = len(missing) / max(len(metadata["feature_columns"]), 1)
            evidence = "strong" if missing_ratio < 0.2 else ("medium" if missing_ratio < 0.4 else "weak")

            return {
                "per_disorder": results,
                "suspected_comorbidity": positive_count >= 2,
                "predicted_positive_count": positive_count,
                "evidence_quality": evidence,
                "missing_critical_features": missing[:20],
                "summary": "Experimental early-warning profile; not a definitive diagnosis.",
            }


        if __name__ == "__main__":
            sample = {"age_years": 8, "sex_assigned_at_birth": "M"}
            print(predict_multilabel(sample))
        """
    ).strip() + "\n"

    (inference_dir / "predict_binary.py").write_text(predict_binary_code, encoding="utf-8")
    (inference_dir / "predict_multilabel.py").write_text(predict_multilabel_code, encoding="utf-8")


def _write_inference_schemas(root: Path) -> None:
    inference_dir = root / "artifacts" / "inference"
    inference_dir.mkdir(parents=True, exist_ok=True)
    questionnaire_schema_path = root / "artifacts" / "specs" / "questionnaire_schema.json"
    if questionnaire_schema_path.exists():
        schema = json.loads(questionnaire_schema_path.read_text(encoding="utf-8"))
    else:
        schema = {"type": "object", "properties": {}, "required": []}
    safe_json(schema, inference_dir / "model_input_schema.json")

    output_schema = {
        "binary_output": {
            "type": "object",
            "required": [
                "disorder",
                "probability_score",
                "predicted_label",
                "threshold_used",
                "risk_band",
                "evidence_quality",
                "missing_critical_features",
                "top_contributors",
            ],
        },
        "multilabel_output": {
            "type": "object",
            "required": [
                "per_disorder",
                "suspected_comorbidity",
                "predicted_positive_count",
                "evidence_quality",
                "missing_critical_features",
            ],
        },
    }
    safe_json(output_schema, inference_dir / "output_schema.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate registry, recommendation report, and inference helpers.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()

    metrics_dir = root / "reports" / "metrics"
    compare_dir = root / "reports" / "comparisons"
    training_dir = root / "reports" / "training"
    training_dir.mkdir(parents=True, exist_ok=True)

    binary = pd.read_csv(metrics_dir / "binary_model_results_detailed.csv")
    multilabel = pd.read_csv(metrics_dir / "multilabel_model_results_detailed.csv")
    strict_vs_research = pd.read_csv(compare_dir / "strict_vs_research.csv")

    strict_binary = binary[binary["version"] == "strict_no_leakage"].copy()
    best_binary = select_best_binary_per_disorder(strict_binary)
    best_multilabel = multilabel[multilabel["version"] == "strict_no_leakage"].sort_values(
        ["micro_f1_test", "subset_accuracy_test"], ascending=[False, False]
    ).iloc[0]

    registry = _build_model_registry(binary, multilabel, best_binary, best_multilabel["model_id"])
    safe_csv(registry, training_dir / "model_registry.csv")

    training_log = _build_training_log(root, binary, multilabel)
    (training_dir / "training_log.md").write_text(training_log, encoding="utf-8")

    recommendation_md = _build_recommendations_md(best_binary, best_multilabel, strict_vs_research)
    (compare_dir / "final_model_recommendations.md").write_text(recommendation_md, encoding="utf-8")

    _write_inference_scripts(root)
    _write_inference_schemas(root)


if __name__ == "__main__":
    main()
