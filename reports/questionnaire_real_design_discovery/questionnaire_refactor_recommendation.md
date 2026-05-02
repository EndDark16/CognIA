# Questionnaire Refactor Recommendation
Fecha: 2026-03-30

## Dictamen
El estado actual del cuestionario sirve como plumbing tecnico, pero no debe tomarse como diseno final.

## Backend / BD (ambito propio)
### Conservar
- Versionado base de templates y activacion unica.
- Persistencia basica de respuestas por evaluacion.

### Refactorizar
- Modelo de preguntas para soportar secciones y branching.
- API de evaluaciones para separar draft vs submit final.
- Capa de resultados por evaluacion (probabilidades + explicacion + incertidumbre).
- Contrato runtime definitivo alineado al scope final (`inference_v4`).

### Reemplazar/retirar
- Uso de `/api/predict` legacy como endpoint principal de cuestionario.

## Frontend (repo externo, handoff)
### Reutilizable
- Patron del hook de carga (`loading/error/refetch`).

### A rehacer
- Flujo de submit real.
- Tipos de respuesta y validaciones alineadas.
- Pantalla de resultados y manejo de dominios en hold.

## Riesgo de no corregir
- Arrastrar placeholder a produccion.
- Mantener falsa sensacion de E2E funcional sin submit real.
