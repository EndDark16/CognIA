# Model Registry and Inference (v2)

## Fuente de verdad
- `data/hybrid_active_modes_freeze_v1/tables/hybrid_active_models_30_modes.csv`
- `data/hybrid_active_modes_freeze_v1/tables/hybrid_active_modes_summary.csv`
- `data/hybrid_active_modes_freeze_v1/tables/hybrid_questionnaire_inputs_master.csv`
- `data/hybrid_operational_freeze_v1/tables/hybrid_operational_final_champions.csv`

## Registro en DB
- `model_registry`: identidad por `active_model_id`.
- `model_versions`: versionado, calibration/threshold/seed/n_features, artifacts.
- `model_mode_domain_activation`: activación final por `domain + mode_key + role`.
- `model_metrics_snapshot`: snapshot de métricas operativas.
- `model_artifact_registry`: localizadores de artefactos.
- `model_confidence_registry`: `% confianza`, banda y clase operativa.
- `model_operational_caveats`: caveats por activación.

## Resolución de modelos en runtime
1. Resolver `mode_key` desde `(role, mode)`.
2. Buscar activación activa exacta (`domain, mode_key, role`).
3. Cargar `ModelVersion` y artefacto:
   - `artifact_path` si existe.
   - fallback a champion por dominio `models/champions/rf_<domain>_current/*`.
4. Construir vector por `feature_columns` (metadata) con defaults trazables.
5. Ejecutar `predict_proba` cuando está disponible.
6. Si artefacto no está disponible: fallback heurístico defensivo y marcado `por_confirmar` en metadata.

## Estado de caveat
- La integración respeta 30 activaciones de producto.
- Para algunos IDs históricos, la ruta exacta de artefacto queda `por_confirmar` y se usa fallback controlado a champion por dominio.
- Claim permitido: screening/apoyo profesional en entorno simulado, no diagnóstico automático.
