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
