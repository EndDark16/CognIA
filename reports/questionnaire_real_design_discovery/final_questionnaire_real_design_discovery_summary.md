# Final Questionnaire Real Design Discovery Summary
Fecha: 2026-03-30

## 1) Que existe hoy del cuestionario placeholder
- Backend con templates/preguntas y persistencia de evaluaciones.
- Frontend que carga template activa y responde localmente.
- Sin submit real conectado desde UI.

## 2) Que parte sirve
- Versionado base de templates.
- Validacion server-side por tipo.
- Persistencia por pregunta.
- Trazabilidad por template de evaluacion.

## 3) Que parte no sirve como final
- Flujo frontend local sin envio.
- Tipos frontend simplificados desalineados.
- Endpoint `/api/predict` legacy adhd-only.
- Sin endpoint final de resultados por evaluacion.

## 4) Estado API actual
- APIs de template y guardado existen, pero incompletas para cuestionario real (faltan draft/section validation/result/explanation/uncertainty).

## 5) Estado BD y migraciones
- BD: base aceptable para cuestionario plano.
- Faltan capacidades estructurales (secciones/branching/progreso/auditoria de respuestas).
- Migraciones actuales no cubren esas capacidades aun.

## 6) Que conservar / quitar / corregir
- Conservar: plumbing de templates y persistencia base.
- Corregir: contrato runtime, flujo draft/submit, salida de resultados, modelo de pregunta.
- Quitar/reemplazar: dependencia funcional de `/api/predict` legacy.

## 7) Dependencias por responsabilidad
- Backend/BD/deploy (ambito propio): contrato final, modelo de datos, endpoints y runtime.
- Frontend (repo externo): submit wiring, validaciones tipadas, pantalla de resultados y manejo de scope.

## 8) Informacion que falta del usuario
- Queda listada en `questionnaire_information_requests.md` (38 decisiones concretas).

## 9) Siguiente paso logico
- Cerrar respuestas del archivo de preguntas.
- Luego pasar a diseno de arquitectura funcional + BD + API en bloque unico.

## Evidencia principal usada
- Backend: `api/routes/questionnaires.py`, `api/routes/evaluations.py`, `api/schemas/*`, `api/services/evaluation_service.py`, `app/models.py`, `docs/openapi.yaml`.
- Artefactos: `artifacts/specs/*`, `data/questionnaire_dsm5_v1/*`, `artifacts/inference_v4/*`.
- Cierre final: `reports/final_closure/*`.
- Frontend referencia externa (read-only): `JeiTy29/cognIA-frontend`.
