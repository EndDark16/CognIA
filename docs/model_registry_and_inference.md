# Model Registry and Inference (v9)

## Fuente de verdad
- `data/hybrid_active_modes_freeze_v9/tables/hybrid_active_models_30_modes.csv`
- `data/hybrid_active_modes_freeze_v9/tables/hybrid_active_modes_summary.csv`
- `data/hybrid_active_modes_freeze_v9/tables/hybrid_questionnaire_inputs_master.csv`
- `data/hybrid_operational_freeze_v9/tables/hybrid_operational_final_champions.csv`

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
- Nota de continuidad (2026-04-22, campana final agresiva):
  - Se ejecuto `hybrid_final_aggressive_rescue_v6`.
  - Se versionaron `data/hybrid_operational_freeze_v6/` y `data/hybrid_active_modes_freeze_v6/`.
  - `replaced_pairs=2` (promociones focales en `conduct/caregiver_full` y `conduct/psychologist_full`).
  - Se ejecutaron pasadas A/B/C con weighting y variantes DSM-5 trazables sobre 18 slots priorizados.
  - Se recalculo `confidence_pct/confidence_band/final_operational_class` para los 30 slots bajo politica normalizada.
  - Se genero normalizacion v2 en `data/hybrid_classification_normalization_v2/` con `policy_violations=0`.
  - La fuente operativa efectiva pasa a `*_freeze_v6`.
- Nota de continuidad (2026-04-24, cierre guardia dura):
  - Se aplico `hybrid_v6_quick_champion_guard_hotfix_v1` sobre `v6`.
  - Se versionaron `data/hybrid_operational_freeze_v6_hotfix_v1/` y `data/hybrid_active_modes_freeze_v6_hotfix_v1/`.
  - Resultado de auditoria guardia: `remaining_guard_violations=0` en las metricas vigiladas (`recall`, `specificity`, `roc_auc`, `pr_auc`).
  - La fuente operativa efectiva pasa a `*_freeze_v6_hotfix_v1`; `*_freeze_v6` queda historico para trazabilidad.
- Nota de continuidad (2026-04-24, coherencia de confianza):
  - Se normalizo la comunicacion de `confidence_band/confidence_pct` en `hybrid_active_modes_freeze_v6_hotfix_v1`.
  - Resultado: `ACTIVE_HIGH_CONFIDENCE/high=1`, `ACTIVE_MODERATE_CONFIDENCE/moderate=14`, `ACTIVE_LIMITED_USE/limited=15`.
  - No se cambiaron champions, metricas de modelo, inputs funcionales ni outputs funcionales.

- Nota de continuidad (2026-04-26, structural mode rescue v1):
  - Se ejecuto `hybrid_structural_mode_rescue_v1` sobre la linea activa real `v6_hotfix_v1`.
  - Se versionaron `data/hybrid_operational_freeze_v8/` y `data/hybrid_active_modes_freeze_v8/`.
  - Se reemplazaron los 14 champions 1_3/2_3 prohibidos por modelos estructurales reentrenados; `accepted_existing_fallbacks=0`.
  - Se aplicaron 3 rescates extra por degeneracion estructural de una sola variable: `anxiety/psychologist_full`, `elimination/caregiver_full` y `elimination/psychologist_full`.
  - Elimination queda en subsets estructurales `structural_ranked` para sus 6 modos (42/84/126 features en caregiver y 50/101/151 en psychologist). Resultado de cierre: `blacklisted_active_final=0`, `structural_extra_rescue_final=0`, `single_feature_active_final=0`, `guardrail_violations_final=0`, `policy_violations_final=0`.
  - La fuente operativa efectiva pasa a `*_freeze_v8`; `*_freeze_v6_hotfix_v1` queda historico para trazabilidad. Summary final activa: `ACTIVE_HIGH_CONFIDENCE/high=1`, `ACTIVE_MODERATE_CONFIDENCE/moderate=9`, `ACTIVE_LIMITED_USE/limited=20`.

- Nota de continuidad (2026-04-26, elimination structural audit rescue v1 + OpenAPI fix):
  - Se ejecuto `hybrid_elimination_structural_audit_rescue_v1` sobre la linea activa `v8`.
  - Se versionaron `data/hybrid_operational_freeze_v9/` y `data/hybrid_active_modes_freeze_v9/`.
  - Se demovieron los 6 champions Elimination de v8 por comportamiento clonado: `old_prediction_pairs_identical=15/15`.
  - Se reentrenaron los 6 slots Elimination con universos directos enuresis/encopresis, sin `eng_elimination_intensity`, y con gate `recall|specificity|roc_auc|pr_auc <= 0.98`.
  - Resultado: `remaining_guardrail_violations=0`, `policy_violations=0`, `new_prediction_pairs_identical=0/15`.
  - Se corrigio `docs/openapi.yaml` eliminando un bloque duplicado dentro de `paths`; el spec conserva `openapi: 3.0.3` y vuelve a parsear sin duplicate mapping keys.
  - La fuente operativa efectiva pasa a `*_freeze_v9`; `*_freeze_v8` queda historico para trazabilidad.

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
