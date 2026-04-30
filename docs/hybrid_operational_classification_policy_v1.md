# Hybrid Operational Classification Policy v1

## Objetivo
Eliminar ambigüedad en `final_class` y separar explícitamente:

1. clase operativa principal
2. flags de riesgo metodológico

Esta politica aplica sobre la linea operativa vigente declarada por el loader v2. A 2026-04-29, esa linea es `hybrid_active_modes_freeze_v13` / `hybrid_operational_freeze_v13`; `freeze_v2` a `freeze_v12` quedan como historicos auditables.

## Capa 1: clase operativa principal
Valores permitidos:

- `ROBUST_PRIMARY`
- `PRIMARY_WITH_CAVEAT`
- `HOLD_FOR_LIMITATION`
- `REJECT_AS_PRIMARY`

`SUSPECT_EASY_DATASET_NEEDS_CAUTION` queda deprecada como clase principal. Si aparece en histórico, se transforma a riesgo (`easy_dataset_flag`) y/o bloqueador.

## Capa 2: flags de riesgo
Campos normalizados:

- `generalization_risk_flag`
- `overfit_risk_flag`
- `easy_dataset_flag`
- `secondary_metric_anomaly_flag`
- `mode_fragility_flag`
- `shortcut_risk_flag`
- `calibration_concern_flag`
- `classification_rationale` (texto trazable)

## Reglas de decisión
### Gate robusto (`ROBUST_PRIMARY`)
Se exige simultáneamente:

- `balanced_accuracy >= 0.90`
- `f1 >= 0.85`
- `precision >= 0.82`
- `recall >= 0.80`
- `brier <= 0.06`
- sin `overfit_risk_flag=yes`
- sin `generalization_risk_flag=yes`
- sin `easy_dataset_flag=yes`
- sin `shortcut_risk_flag=yes`
- sin `secondary_metric_anomaly_flag=yes` no resuelta

### `PRIMARY_WITH_CAVEAT`
Modelo útil con caveat explícito y sin bloqueador duro, cuando:

- no alcanza gate robusto, o
- presenta anomalía secundaria no resuelta, o
- presenta fragilidad de modo/calibración sin riesgo metodológico fuerte.

### `HOLD_FOR_LIMITATION`
Cuando falla gate mínimo operativo o requiere demasiada interpretación defensiva:

- métricas mínimas no satisfechas, o
- `overfit_risk_flag=yes`, o
- `generalization_risk_flag=yes`, o
- limitación estructural persistente en modo frágil.

### `REJECT_AS_PRIMARY`
Bloqueador metodológico fuerte:

- `easy_dataset_flag=yes`, o
- `shortcut_risk_flag=yes`.

## Reglas duras de enforcement
- `easy_dataset_flag=yes` nunca puede coexistir con `ROBUST_PRIMARY`.
- `shortcut_risk_flag=yes` nunca puede coexistir con `ROBUST_PRIMARY`.
- `secondary_metric_anomaly_flag=yes` solo puede coexistir con `ROBUST_PRIMARY` si `secondary_anomaly_resolution=documented_strong`.
- si no hay evidencia documental fuerte de resolución de anomalía secundaria, marcar `secondary_anomaly_resolution=por_confirmar`.
- Ningún champion activo puede permanecer si `recall`, `specificity`, `roc_auc` o `pr_auc` queda `> 0.98`.
- La comunicación de confianza debe quedar alineada: `ACTIVE_MODERATE_CONFIDENCE` usa `confidence_band=moderate`; `ACTIVE_LIMITED_USE` usa `confidence_band=limited`; `ACTIVE_HIGH_CONFIDENCE` requiere `confidence_band=high` y sin caveat metodológico fuerte.

## Política de anomalía secundaria
Se marca `secondary_metric_anomaly_flag=yes` cuando existe al menos una de estas señales:

- `roc_auc > 0.98`
- `pr_auc > 0.98`
- `specificity > 0.98`
- combinación casi perfecta de métricas secundarias + `brier` muy bajo

No se usa solo umbral bruto: la evaluación agrega combinaciones `secondary_peak + brier` y consistencia con `balanced_accuracy`.

## Implementación
- Ejecución de normalización: `scripts/run_hybrid_classification_normalization_v1.py`
- Validación/enforcement: `scripts/validate_hybrid_classification_policy_v1.py`
- Módulo reusable de política: `api/services/hybrid_classification_policy_v1.py`

## Compatibilidad y trazabilidad
- No sobrescribe tablas históricas (`freeze_v1` a `freeze_v6`).
- Produce tablas derivadas versionadas en `data/hybrid_classification_normalization_v2/` para la línea activa reciente.
- Mantiene el framing metodológico: screening/apoyo profesional, no diagnóstico automático.

## Actualizacion 2026-04-26 - v10 (historico)
La linea v10 queda preservada como historica en `hybrid_active_modes_freeze_v10` / `hybrid_operational_freeze_v10` tras la promocion v11. La pasada `hybrid_final_model_structural_compliance_v1` mantiene el gate duro `recall|specificity|roc_auc|pr_auc <= 0.98`, aplica anti-clonado en Elimination, reconstruye `feature_list_pipe` para champions heredados retenidos, sincroniza flags de cuestionario sin modificar textos auditados y deja Supabase/Postgres con 30 activaciones activas verificadas.


## Actualizacion 2026-04-27 - v11 RF-only
La linea vigente queda en `hybrid_active_modes_freeze_v11` / `hybrid_operational_freeze_v11`. La campana `hybrid_rf_max_real_metrics_v1` reentreno 30/30 slots con RandomForestClassifier exclusivamente, mantuvo los mismos `feature_list_pipe` de v10, no modifico cuestionario ni outputs funcionales y dejo `recall|specificity|roc_auc|pr_auc <= 0.98` en todos los champions activos. La clasificacion final queda `ACTIVE_MODERATE_CONFIDENCE=15` y `ACTIVE_LIMITED_USE=15`, sin `ACTIVE_HIGH_CONFIDENCE` por caveats/fragilidad persistentes.

## Actualizacion 2026-04-27 - v12 RF-based final
La linea vigente queda en `hybrid_active_modes_freeze_v12` / `hybrid_operational_freeze_v12`. La campana `hybrid_final_rf_plus_maximize_metrics_v1` evaluo 30/30 slots con RandomForestClassifier como estimador base obligatorio, mantuvo los mismos `feature_list_pipe` de v11, no modifico cuestionario ni outputs funcionales y dejo `recall|specificity|roc_auc|pr_auc <= 0.98` en todos los champions activos. La clasificacion final queda `ACTIVE_HIGH_CONFIDENCE=2`, `ACTIVE_MODERATE_CONFIDENCE=13` y `ACTIVE_LIMITED_USE=15`; la sincronizacion Supabase/Postgres queda validada en `data/hybrid_final_rf_plus_maximize_metrics_v1/supabase_sync/supabase_sync_verification_v12.json`.

## Actualizacion 2026-04-29 - v13 seleccion global RF contract-compatible
La linea vigente queda en `hybrid_active_modes_freeze_v13` / `hybrid_operational_freeze_v13`. La pasada `hybrid_global_contract_compatible_rf_champion_selection_v13` no reentreno modelos: filtro candidatos RF historicos por contrato exacto de inputs/outputs, metadata activable, threshold valido, metricas comparables y gate duro `recall|specificity|roc_auc|pr_auc <= 0.98`. Resultado final: 30/30 champions RF-based, 17 recuperados desde v11 y 13 retenidos desde v12, sin cambios de cuestionario ni outputs funcionales. La clasificacion final queda `ACTIVE_HIGH_CONFIDENCE=2`, `ACTIVE_MODERATE_CONFIDENCE=14` y `ACTIVE_LIMITED_USE=14`; la sincronizacion Supabase/Postgres queda validada en `data/hybrid_global_contract_compatible_rf_champion_selection_v13/supabase_sync/supabase_sync_verification_v13.json`.
