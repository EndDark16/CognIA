# Hybrid Operational Classification Policy v1

## Objetivo
Eliminar ambigÃ¼edad en `final_class` y separar explÃ­citamente:

1. clase operativa principal
2. flags de riesgo metodolÃ³gico

Esta politica aplica sobre la linea operativa vigente declarada por el loader v2. A 2026-04-27, esa linea es `hybrid_active_modes_freeze_v11` / `hybrid_operational_freeze_v11`; `freeze_v2` a `freeze_v10` quedan como historicos auditables.

## Capa 1: clase operativa principal
Valores permitidos:

- `ROBUST_PRIMARY`
- `PRIMARY_WITH_CAVEAT`
- `HOLD_FOR_LIMITATION`
- `REJECT_AS_PRIMARY`

`SUSPECT_EASY_DATASET_NEEDS_CAUTION` queda deprecada como clase principal. Si aparece en histÃ³rico, se transforma a riesgo (`easy_dataset_flag`) y/o bloqueador.

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

## Reglas de decisiÃ³n
### Gate robusto (`ROBUST_PRIMARY`)
Se exige simultÃ¡neamente:

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
Modelo Ãºtil con caveat explÃ­cito y sin bloqueador duro, cuando:

- no alcanza gate robusto, o
- presenta anomalÃ­a secundaria no resuelta, o
- presenta fragilidad de modo/calibraciÃ³n sin riesgo metodolÃ³gico fuerte.

### `HOLD_FOR_LIMITATION`
Cuando falla gate mÃ­nimo operativo o requiere demasiada interpretaciÃ³n defensiva:

- mÃ©tricas mÃ­nimas no satisfechas, o
- `overfit_risk_flag=yes`, o
- `generalization_risk_flag=yes`, o
- limitaciÃ³n estructural persistente en modo frÃ¡gil.

### `REJECT_AS_PRIMARY`
Bloqueador metodolÃ³gico fuerte:

- `easy_dataset_flag=yes`, o
- `shortcut_risk_flag=yes`.

## Reglas duras de enforcement
- `easy_dataset_flag=yes` nunca puede coexistir con `ROBUST_PRIMARY`.
- `shortcut_risk_flag=yes` nunca puede coexistir con `ROBUST_PRIMARY`.
- `secondary_metric_anomaly_flag=yes` solo puede coexistir con `ROBUST_PRIMARY` si `secondary_anomaly_resolution=documented_strong`.
- si no hay evidencia documental fuerte de resoluciÃ³n de anomalÃ­a secundaria, marcar `secondary_anomaly_resolution=por_confirmar`.
- NingÃºn champion activo puede permanecer si `recall`, `specificity`, `roc_auc` o `pr_auc` queda `> 0.98`.
- La comunicaciÃ³n de confianza debe quedar alineada: `ACTIVE_MODERATE_CONFIDENCE` usa `confidence_band=moderate`; `ACTIVE_LIMITED_USE` usa `confidence_band=limited`; `ACTIVE_HIGH_CONFIDENCE` requiere `confidence_band=high` y sin caveat metodolÃ³gico fuerte.

## PolÃ­tica de anomalÃ­a secundaria
Se marca `secondary_metric_anomaly_flag=yes` cuando existe al menos una de estas seÃ±ales:

- `roc_auc > 0.98`
- `pr_auc > 0.98`
- `specificity > 0.98`
- combinaciÃ³n casi perfecta de mÃ©tricas secundarias + `brier` muy bajo

No se usa solo umbral bruto: la evaluaciÃ³n agrega combinaciones `secondary_peak + brier` y consistencia con `balanced_accuracy`.

## ImplementaciÃ³n
- EjecuciÃ³n de normalizaciÃ³n: `scripts/run_hybrid_classification_normalization_v1.py`
- ValidaciÃ³n/enforcement: `scripts/validate_hybrid_classification_policy_v1.py`
- MÃ³dulo reusable de polÃ­tica: `api/services/hybrid_classification_policy_v1.py`

## Compatibilidad y trazabilidad
- No sobrescribe tablas histÃ³ricas (`freeze_v1` a `freeze_v6`).
- Produce tablas derivadas versionadas en `data/hybrid_classification_normalization_v2/` para la lÃ­nea activa reciente.
- Mantiene el framing metodolÃ³gico: screening/apoyo profesional, no diagnÃ³stico automÃ¡tico.

## Actualizacion 2026-04-26 - v10 (historico)
La linea v10 queda preservada como historica en `hybrid_active_modes_freeze_v10` / `hybrid_operational_freeze_v10` tras la promocion v11. La pasada `hybrid_final_model_structural_compliance_v1` mantiene el gate duro `recall|specificity|roc_auc|pr_auc <= 0.98`, aplica anti-clonado en Elimination, reconstruye `feature_list_pipe` para champions heredados retenidos, sincroniza flags de cuestionario sin modificar textos auditados y deja Supabase/Postgres con 30 activaciones activas verificadas.


## Actualizacion 2026-04-27 - v11 RF-only
La linea vigente queda en `hybrid_active_modes_freeze_v11` / `hybrid_operational_freeze_v11`. La campana `hybrid_rf_max_real_metrics_v1` reentreno 30/30 slots con RandomForestClassifier exclusivamente, mantuvo los mismos `feature_list_pipe` de v10, no modifico cuestionario ni outputs funcionales y dejo `recall|specificity|roc_auc|pr_auc <= 0.98` en todos los champions activos. La clasificacion final queda `ACTIVE_MODERATE_CONFIDENCE=15` y `ACTIVE_LIMITED_USE=15`, sin `ACTIVE_HIGH_CONFIDENCE` por caveats/fragilidad persistentes.
