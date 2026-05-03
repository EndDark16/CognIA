# Sonar Metric Evolution

- project_key: EndDark16_CognIA
- analyses_considered: 21
- quality_gate_initial_known: NONE
- quality_gate_final: OK
- quality_gate_status_changes_detected: 4
- source: /api/project_analyses/search, /api/qualitygates/project_status, /api/measures/search_history

## Cambios relevantes
- Cobertura final reportada: 59.3.
- Duplicacion final reportada: 1.4.
- Bugs/Vulnerabilities/Code Smells finales: 0/0/0.

## Interpretacion tecnica
- La evolucion se reconstruye con el historial retenido por Sonar para este proyecto.
- Las metricas `new_*` pueden aparecer sin valor historico en API; se documentan como `not_available_from_api_history`.

## Limites de evidencia
- El historial depende de la retencion disponible en SonarCloud para el proyecto.
- No se infiere causalidad commit-a-commit sin un mapeo explicito adicional.
