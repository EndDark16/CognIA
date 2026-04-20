# Current Questionnaire System Flow
Fecha: 2026-03-30

## Flujo reconstruido hoy
1. Frontend (externo) solicita plantilla activa (`GET /api/v1/questionnaires/active`).
2. Backend responde template + preguntas (lista plana).
3. Frontend valida y guarda respuestas en estado local.
4. La UI finaliza localmente (modal de exito) sin submit backend.
5. Backend si tiene `POST /api/v1/evaluations`, pero hoy no se invoca desde UI.
6. No existe tramo integrado `submit -> inferencia -> resultado` dentro del flujo de cuestionario visible.

## Donde se corta
- Corte principal: frontend no llama `POST /api/v1/evaluations`.
- Corte secundario: no existe endpoint final user-facing para resultado por evaluacion (probabilidad + explicacion + incertidumbre).

## Que se puede reutilizar
- API de templates (create/add/activate/clone + admin lifecycle).
- Validacion server-side por `response_type`.
- Persistencia de evaluacion y respuestas por pregunta.

## Que no debe asumirse como final
- UI actual y su finalizacion local.
- Contrato de tipos frontend actual.
- `/api/predict` legacy como endpoint principal.

## Impacto separado
- Backend/BD: contrato definitivo, endpoints de draft/submit/resultado, y conexion real con inferencia.
- Frontend (handoff): wiring de submit, manejo de errores remotos, estado de draft y render de resultados.
