#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def safe_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_predict_domains_py() -> str:
    return """#!/usr/bin/env python
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
"""


def build_predict_internal_units_py() -> str:
    return """#!/usr/bin/env python
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
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Export inference layer artifacts for hybrid v2.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    out = root / "artifacts" / "inference_v2"
    out.mkdir(parents=True, exist_ok=True)

    safe_text(build_predict_domains_py(), out / "predict_domains.py")
    safe_text(build_predict_internal_units_py(), out / "predict_internal_units.py")

    output_schema = {
        "type": "object",
        "properties": {
            "probabilities_by_domain": {"type": "object"},
            "probabilities_by_internal_unit": {"type": "object"},
            "confidence_level": {"type": "string"},
            "coverage_summary": {"type": "object"},
            "direct_proxy_absent_summary": {"type": "object"},
            "key_positive_contributors": {"type": "array"},
            "key_negative_contributors": {"type": "array"},
            "missing_critical_inputs": {"type": "array"},
            "abstention_flag": {"type": "boolean"},
            "threshold_used": {"type": "object"},
            "model_version": {"type": "string"},
            "recommendation_text": {"type": "string"},
            "disclaimers": {"type": "array"},
        },
    }
    safe_json(output_schema, out / "inference_output_schema.json")

    safe_text(
        "# Explanation Contract\n\n"
        "- Output is probabilistic and experimental.\n"
        "- It is not a definitive diagnosis.\n"
        "- Include contributors, missing critical inputs, and abstention flag.\n",
        out / "explanation_contract.md",
    )

    sample_output = {
        "probabilities_by_domain": {"adhd": 0.71, "conduct": 0.38, "elimination": 0.52, "anxiety": 0.44, "depression": 0.29},
        "probabilities_by_internal_unit": {"adhd": 0.69},
        "confidence_level": "medium",
        "coverage_summary": {"observed_features_ratio": 0.82},
        "direct_proxy_absent_summary": {"direct": 41, "proxy": 18, "absent": 9},
        "key_positive_contributors": ["q_qi_0012", "q_qi_0048"],
        "key_negative_contributors": ["q_qi_0113"],
        "missing_critical_inputs": ["q_qi_0009"],
        "abstention_flag": False,
        "threshold_used": {"adhd": 0.58},
        "model_version": "hybrid_dsm5_v2",
        "recommendation_text": "Use as early-warning support and clinical triage aid.",
        "disclaimers": ["Experimental simulated environment", "Not a clinical diagnosis"],
    }
    safe_json(sample_output, out / "sample_inference_outputs.json")

    # keep schema references for app/backend.
    mode_csv = root / "reports" / "operating_modes" / "operating_modes_comparison.csv"
    mode_rows = pd.read_csv(mode_csv).head(10).to_dict(orient="records") if mode_csv.exists() else []
    safe_json({"modes_snapshot": mode_rows}, out / "operating_modes_snapshot.json")


if __name__ == "__main__":
    main()

