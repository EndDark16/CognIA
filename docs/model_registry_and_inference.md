# Model Registry and Inference (v5)

## Fuente de verdad
- `data/hybrid_active_modes_freeze_v5/tables/hybrid_active_models_30_modes.csv`
- `data/hybrid_active_modes_freeze_v5/tables/hybrid_active_modes_summary.csv`
- `data/hybrid_active_modes_freeze_v5/tables/hybrid_questionnaire_inputs_master.csv`
- `data/hybrid_operational_freeze_v5/tables/hybrid_operational_final_champions.csv`

Nota de continuidad (2026-04-22):
- Se ejecuto la linea `hybrid_secondary_honest_retrain_v1` y se versionaron:
  - `data/hybrid_operational_freeze_v3/`
  - `data/hybrid_active_modes_freeze_v3/`
- Resultado de esa pasada: `replaced_pairs=0` (no hubo promociones).
- En la campana `hybrid_final_honest_improvement_v1` se promovieron 9 reemplazos honestos (foco `full/2_3` en `anxiety`, `depression`, `elimination`).
- Cambio estructural mas relevante:
  - `depression/psychologist_2_3` pasa de `HOLD_FOR_LIMITATION` a `PRIMARY_WITH_CAVEAT`.
- En los reemplazos de `anxiety` y `elimination` se mantiene caveat por anomalia secundaria (>0.98), por lo que no se reclasifican como robustez limpia.
- Nota de continuidad (2026-04-22, campana final decisiva):
  - Se ejecuto `hybrid_final_decisive_rescue_v5`.
  - Se versionaron `data/hybrid_operational_freeze_v5/` y `data/hybrid_active_modes_freeze_v5/`.
  - `replaced_pairs=1` (promocion focal en `depression/caregiver_2_3`).
  - Se recalculo `confidence_pct/confidence_band/final_operational_class` para los 30 slots bajo politica normalizada.
  - Se genero normalizacion v2 en `data/hybrid_classification_normalization_v2/` con `policy_violations=0`.
  - La fuente operativa efectiva pasa a `*_freeze_v5`.

## Registro en DB
- `model_registry`: identidad por `active_model_id`.
- `model_versions`: versionado, calibration/threshold/seed/n_features, artifacts.
- `model_mode_domain_activation`: activacion final por `domain + mode_key + role`.
- `model_metrics_snapshot`: snapshot de metricas operativas.
- `model_artifact_registry`: localizadores de artefactos.
- `model_confidence_registry`: `% confianza`, banda y clase operativa.
- `model_operational_caveats`: caveats por activacion.

## Resolucion de modelos en runtime
1. Resolver `mode_key` desde `(role, mode)`.
2. Buscar activacion activa exacta (`domain, mode_key, role`).
3. Cargar `ModelVersion` y artefacto:
   - `artifact_path` si existe.
   - fallback a champion por dominio `models/champions/rf_<domain>_current/*`.
   - deserializacion explicita con `joblib.load(...)` en runtime (`questionnaire_v2_service` y `questionnaire_runtime_service`).
4. Construir vector por `feature_columns` (metadata) con defaults trazables.
5. Ejecutar `predict_proba` cuando esta disponible.
6. Si artefacto no esta disponible: fallback heuristico defensivo y marcado `por_confirmar` en metadata.

Nota de rol operativo (2026-04-21):
- El contrato publico de API/runtime usa `guardian` (antes `caregiver`).
- Internamente se mantiene compatibilidad de `mode_key` historico (`caregiver_1_3`, `caregiver_2_3`, `caregiver_full`) para no romper trazabilidad ni artefactos.
- El loader/runtime normaliza alias legacy `caregiver -> guardian`.

## Estado de caveat
- La integracion respeta 30 activaciones de producto.
- Para algunos IDs historicos, la ruta exacta de artefacto queda `por_confirmar` y se usa fallback controlado a champion por dominio.
- Claim permitido: screening/apoyo profesional en entorno simulado, no diagnostico automatico.

Referencia historica preservada:
- `data/hybrid_active_modes_freeze_v1/*`
- `data/hybrid_operational_freeze_v1/*`
