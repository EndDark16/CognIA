# Questionnaire Migration Impact Assessment
Fecha: 2026-03-30

## Diagnostico
La BD actual soporta cuestionario plano versionado y persistencia basica, pero no cubre bien un cuestionario real con secciones, branching, guardado parcial y auditoria fina de respuestas.

## Extension vs rediseno (sin ejecutar migraciones)

### Opcion A - Extender modelo actual (recomendada)
- Mantener: `questionnaire_template`, `question`, `evaluation`, `evaluation_response`.
- Extender con:
  - `questionnaire_section`
  - `question_branching_rule`
  - `evaluation_draft_state` (o tabla equivalente)
  - `evaluation_response_audit`
  - metadatos de contrato/version por evaluacion
- Ventaja: menor ruptura y mayor reutilizacion de plumbing ya probado.

### Opcion B - Reemplazo total paralelo
- Crear esquema nuevo desde cero para runtime de cuestionario.
- Ventaja: modelo limpio.
- Riesgo: costo alto, migracion compleja y mayor chance de romper trazabilidad.

## Recomendacion para siguiente bloque
- No ejecutar migraciones en esta fase (discovery-only).
- Preparar plan Alembic incremental en este orden:
  1. secciones + metadata estructural,
  2. draft/progreso,
  3. branching,
  4. auditoria de cambios,
  5. endpoints asociados.

## Evidencia
- `app/models.py`
- `migrations/versions/20260124_03_add_evaluation_questionnaire_template.py`
- `migrations/versions/20260124_04_add_question_response_constraints.py`
- `migrations/versions/20260124_05_add_question_disorder_relation.py`
- `docs/vistas/Plataforma/Cuestionario.md` (frontend: "guardado parcial" como esperado futuro)
