# Redundancy and Cleanup Recommendations

## Hallazgos principales
- archivos >=5MB detectados: 118
- archivos pesados con duplicacion exacta detectada: 110

## Recomendaciones concretas
- Mantener un solo repositorio de binarios de modelos fuera de git (storage externo con manifiesto y checksum).
- Evitar duplicar el mismo `calibrated.joblib` en `models/` y `artifacts/`.
- Excluir tablas long gigantes (`participant_normative_evidence_long.csv`) del repo y conservar solo versiones compactas para auditoria.
- Mantener en git solo artefactos de inferencia vigentes (`artifacts/inference_v4/`) y metadatos livianos.
- Introducir release bundles externos por iteracion (`v1`, `v2`, `v3`) para datasets/modelos pesados.