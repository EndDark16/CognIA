#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd


def _risk_band(p: float) -> str:
    if p < 0.33:
        return "low"
    if p < 0.66:
        return "moderate"
    return "high"


def predict_domains(features: Dict[str, Any], models_root: str = "artifacts/hybrid_dsm5_v2/models") -> Dict[str, Any]:
    root = Path(models_root)
    outputs: Dict[str, Any] = {"probabilities_by_domain": {}, "details": {}}
    row = pd.DataFrame([features])
    for model_dir in sorted(root.glob("domain_*_strict_full")):
        payload = joblib.load(model_dir / "model.joblib")
        model = payload["model"]
        cols = payload["feature_columns"]
        x = row.reindex(columns=cols, fill_value=np.nan)
        p = float(model.predict_proba(x)[:, 1][0])
        domain = model_dir.name.split("_")[1]
        outputs["probabilities_by_domain"][domain] = p
        outputs["details"][domain] = {"risk_band": _risk_band(p)}
    return outputs


if __name__ == "__main__":
    sample = {"age_years": 9, "sex_assigned_at_birth": "F"}
    print(json.dumps(predict_domains(sample), indent=2))
