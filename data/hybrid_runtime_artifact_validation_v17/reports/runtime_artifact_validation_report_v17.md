# Runtime Artifact Validation v17

- total_active_slots: 30
- runtime_artifact_available: 0/30
- joblib_load_ok: 0/30
- predict_proba_smoke_ok: 0/30
- feature_columns_match: 30/30
- por_confirmar_active_models: 0
- generic_domain_fallback_unverified: 0
- artifact_duplicate_hash_count: 0
- runtime_artifact_validation_status: fail

## Notes
- Validation is based on active DB rows (`model_mode_domain_activation.active_flag=true`).
- `predict_proba` smoke uses a single dummy row aligned to each model feature contract.
- No heuristic fallback was used inside this validator.