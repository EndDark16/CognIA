#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd


def predict_internal_units(features: Dict[str, Any], models_root: str = "artifacts/hybrid_dsm5_v2/models") -> Dict[str, Any]:
    root = Path(models_root)
    outputs: Dict[str, Any] = {"probabilities_by_internal_unit": {}}
    row = pd.DataFrame([features])
    for model_dir in sorted(root.glob("internal_*_strict_compact")):
        payload = joblib.load(model_dir / "model.joblib")
        model = payload["model"]
        cols = payload["feature_columns"]
        x = row.reindex(columns=cols, fill_value=np.nan)
        p = float(model.predict_proba(x)[:, 1][0])
        unit = model_dir.name.replace("internal_", "").replace("_strict_compact", "")
        outputs["probabilities_by_internal_unit"][unit] = p
    return outputs


if __name__ == "__main__":
    sample = {"age_years": 9, "sex_assigned_at_birth": "F"}
    print(json.dumps(predict_internal_units(sample), indent=2))
