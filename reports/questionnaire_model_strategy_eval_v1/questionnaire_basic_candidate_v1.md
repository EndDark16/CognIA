# questionnaire_basic_candidate_v1

- Objetivo: cuestionario cuidador-friendly de carga moderada para evaluar acople con modelos existentes.
- Total preguntas/features seleccionadas: **49**
- Exclusión explícita: features self-report (`ysr_*`, `scared_sr_*`, `ari_sr_*`) como preguntas directas.

## Distribución por dominio
- `adhd`: 19 items
- `conduct`: 8 items
- `anxiety`: 19 items
- `depression`: 3 items

## Reglas
- Incluye contexto base (`age_years`, `sex_assigned_at_birth`) y metadatos de sistema (`site`, `release`).
- Prioriza escalas parentales y proxies caregiver.
- Mantiene estructura compatible con secciones multipaso por dominio.
