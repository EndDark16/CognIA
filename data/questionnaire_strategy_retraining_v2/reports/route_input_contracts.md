# Route input contracts

## Ruta A (baseline control)
- Contrato congelado: `questionnaire_basic_candidate_v1` (49 inputs).
- Sin capa fuerte de derivacion. Faltantes estructurales visibles.

## Ruta B (basic + capa intermedia)
- Contrato base: mismo cuestionario de Ruta A.
- Capa intermedia congelada: proxies/derivaciones + imputacion controlada train-only.

## Ruta C (remodelado cuidador-compatible)
- Contrato cuidador+system congelado: 224 inputs (sin self-report).
- Excluye dependencias estructurales de ysr_*, scared_sr_*, ari_sr_*.

## Legacy runtime esperado por dominio
- `adhd`: 35 inputs legacy
- `conduct`: 23 inputs legacy
- `elimination`: 17 inputs legacy
- `anxiety`: 260 inputs legacy
- `depression`: 18 inputs legacy
