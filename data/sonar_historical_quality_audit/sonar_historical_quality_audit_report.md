# Sonar Historical Quality Audit Report

## Objetivo
Generar trazabilidad historica completa de calidad Sonar para backend CognIA, incluyendo evolucion de metricas, Quality Gate, issues e hotspots.

## Fuentes de datos
- `data/sonar_main_audit/*` (evidencia final ya versionada).
- Sonar API publica del proyecto (`/api/project_analyses/search`, `/api/measures/*`, `/api/issues/search`, `/api/hotspots/*`, `/api/qualitygates/project_status`).

## Metodologia de extraccion
- Se consumio historial retenido por Sonar para el `project_key` vigente.
- Se normalizaron series por fecha de analisis y se materializaron CSV/JSON/MD reproducibles.
- Donde la API no entrega valores historicos puntuales, se registra `not_available` sin inferencia.

## Estado final
- quality_gate_final: OK
- latest_revision_analyzed: bdafd5d077b5bee365da087589b5dccff15a8b84
- latest_project_version: 2026.05.03-main-e2cd499
- open_issues_total_actual: 0
- open_hotspots_total_actual: 0

## Comparacion pre/post
- estado_inicial_conocido (analisis mas antiguo retenido): 2026-04-22T02:07:27+0000 / revision=0ce74a455293f81cddcfb4a4f5f2185f22f9f0d0.
- estado_final (analisis mas reciente retenido): 2026-05-03T22:05:40+0000 / revision=bdafd5d077b5bee365da087589b5dccff15a8b84.
- Ver detalle en `sonar_pre_post_comparison.csv`.

## Issues encontrados
- historicos_resueltos_total: 486
- abiertos_actuales_total: 0
- abiertos_por_tipo: {}
- resueltos_por_tipo: {'CODE_SMELL': 468, 'VULNERABILITY': 16, 'BUG': 2}
- resueltos_por_resolution: {'FIXED': 486}

## Issues resueltos/cerrados
- Detalle granular exportado en `sonar_resolved_issues_detail.csv`.

## Issues abiertos
- Detalle actual exportado en `sonar_current_open_issues.csv`.

## Quality Gate
- Evolucion y detalle por analisis en `sonar_quality_gate_history.json` y `sonar_metric_evolution.md`.

## Cobertura, duplicacion y ratings
- coverage_final: 59.3
- duplicated_lines_density_final: 1.4
- reliability_rating_final: 1.0
- security_rating_final: 1.0
- maintainability_rating_final(sqale_rating): 1.0
- technical_debt_final(sqale_index): 0

## Seguridad
- Hotspots en `sonar_security_hotspots_summary.csv` con estado de revision.

## Limitaciones de datos
- Las metricas `new_*` no siempre exponen valor historico en `search_history`; se marca `not_available_from_api_history`.
- El historial esta acotado por la retencion disponible en Sonar.
- No se afirma trazabilidad clinica; evidencia aplicada solo a calidad de codigo/inferencia operacional.

## Conclusion
- Evidencia historica consolidada y reproducible generada para auditoria Sonar del backend CognIA.
- Claim operativo: apto para soporte de calidad de software en entorno simulado; no implica diagnostico automatico.

## Datos sugeridos para documentos de pruebas
- metricas_para_graficas: cobertura, duplicacion, bugs, vulnerabilities, code_smells, ratings, estado Quality Gate por analisis.
- tablas_recomendadas: `sonar_metric_evolution.csv`, `sonar_pre_post_comparison.csv`, `sonar_issues_by_type_and_severity.csv`.
- datos_finales: quality_gate=OK, coverage=59.3, duplicated_lines_density=1.4, open_issues=0.
- datos_historicos_disponibles: 21 analisis con timeline de metricas core y Quality Gate.
- datos_no_disponibles: valores historicos completos para algunas metricas `new_*` en API.
