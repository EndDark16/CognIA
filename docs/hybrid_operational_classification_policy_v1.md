# Hybrid Operational Classification Policy v1

## Objetivo
Eliminar ambigüedad en `final_class` y separar explícitamente:

1. clase operativa principal
2. flags de riesgo metodológico

Esta política aplica sobre la línea operativa vigente declarada por el loader v2. A 2026-04-24, esa línea es `hybrid_active_modes_freeze_v6_hotfix_v1` / `hybrid_operational_freeze_v6_hotfix_v1`; `freeze_v2` y `freeze_v3` quedan como históricos auditables.

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
