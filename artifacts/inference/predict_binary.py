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
