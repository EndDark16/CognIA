from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import create_app
from app.models import ModelModeDomainActivation, ModelRegistry, ModelVersion, db

OUT_PATH = ROOT / "data" / "security_encryption_v17" / "validation" / "v17_supabase_sync_verification.json"
ACTIVE_CSV = ROOT / "data" / "hybrid_active_modes_freeze_v16" / "tables" / "hybrid_active_models_30_modes.csv"


def _config_class_from_env():
    class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
    module_path, class_name = class_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def _norm_role(role: str) -> str:
    role = str(role or "").strip().lower()
    if role == "caregiver":
        return "guardian"
    return role


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    active_df = pd.read_csv(ACTIVE_CSV)
    expected_by_slot = {}
    expected_keys = set()
    for row in active_df.to_dict(orient="records"):
        key = (
            str(row.get("domain") or "").strip().lower(),
            str(row.get("mode") or "").strip().lower(),
            _norm_role(row.get("role")),
        )
        expected_by_slot[key] = {
            "model_key": str(row.get("active_model_id") or "").strip(),
            "feature_columns": [
                part.strip()
                for part in str(row.get("feature_list_pipe") or "").split("|")
                if part and part.strip() and part.strip().lower() != "nan"
            ],
        }
        expected_keys.add(expected_by_slot[key]["model_key"])

    app = create_app(_config_class_from_env())
    with app.app_context():
        active_rows = (
            ModelModeDomainActivation.query.filter_by(active_flag=True)
            .order_by(ModelModeDomainActivation.domain.asc(), ModelModeDomainActivation.mode_key.asc())
            .all()
        )

        active_activations_db = len(active_rows)
        active_model_versions = len({str(row.model_version_id) for row in active_rows})

        non_rf = 0
        missing_expected_models = 0
        mismatched_feature_columns = 0
        mismatched_model_key = 0
        duplicate_active_domain_mode_rows = 0
        runtime_artifact_paths_missing = 0

        seen_slots = defaultdict(int)
        db_model_keys = set()
        source_campaigns = []

        for row in active_rows:
            seen_slots[(row.domain, row.mode_key, row.role)] += 1
            registry = db.session.get(ModelRegistry, row.model_registry_id)
            version = db.session.get(ModelVersion, row.model_version_id)
            if not registry or not version:
                continue

            db_model_keys.add(registry.model_key)
            if registry.source_campaign:
                source_campaigns.append(registry.source_campaign)

            family = str(registry.model_family or "").lower()
            if "rf" not in family and "randomforest" not in family:
                non_rf += 1

            slot_key = (row.domain, row.mode_key, _norm_role(row.role))
            expected = expected_by_slot.get(slot_key)
            if not expected:
                continue

            if expected["model_key"] != registry.model_key:
                mismatched_model_key += 1

            db_features = [
                str(item).strip()
                for item in (version.metadata_json or {}).get("feature_columns", [])
                if str(item).strip()
            ]
            if db_features != expected["feature_columns"]:
                mismatched_feature_columns += 1

            if not str(version.artifact_path or "").strip():
                runtime_artifact_paths_missing += 1

        missing_expected_models = len(expected_keys - db_model_keys)
        duplicate_active_domain_mode_rows = sum(count - 1 for count in seen_slots.values() if count > 1)

        campaign_counter = Counter(source_campaigns)
        lineage_mixed = len(campaign_counter) > 1
        dominant_campaign = campaign_counter.most_common(1)[0][0] if campaign_counter else None

        db_active_set_valid = (
            active_activations_db == 30
            and active_model_versions == 30
            and non_rf == 0
            and missing_expected_models == 0
            and mismatched_feature_columns == 0
            and mismatched_model_key == 0
            and duplicate_active_domain_mode_rows == 0
        )

        payload = {
            "active_activations_db": active_activations_db,
            "active_model_versions": active_model_versions,
            "active_model_versions_non_rf": non_rf,
            "missing_expected_models": missing_expected_models,
            "mismatched_feature_columns": mismatched_feature_columns,
            "mismatched_model_key": mismatched_model_key,
            "duplicate_active_domain_mode_rows": duplicate_active_domain_mode_rows,
            "runtime_artifact_paths_missing": runtime_artifact_paths_missing,
            "mixed_lineage_expected": "yes",
            "active_model_lineage_mixed": "yes" if lineage_mixed else "no",
            "dominant_source_campaign": dominant_campaign,
            "db_active_set_valid": "yes" if db_active_set_valid else "no",
            "active_selection_version": "v16",
            "active_champions_loaded_ok": "yes" if db_active_set_valid else "no",
        }

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
