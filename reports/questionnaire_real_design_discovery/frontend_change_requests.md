# Frontend Change Requests (Handoff)
Fecha: 2026-03-30
Repositorio auditado (read-only): `https://github.com/JeiTy29/cognIA-frontend`

## Requerimientos para el equipo frontend
1. Conectar submit real del cuestionario (draft + submit final cuando exista contrato).
2. Alinear `ResponseType` y validaciones cliente con contrato backend definitivo.
3. Implementar flujo multipaso por secciones (cuando backend exponga metadata de seccion/branching).
4. Implementar pantalla de resultados que consuma salida por dominio y respete scope productivo final.
5. Manejar errores remotos por item/seccion y estados de borrador.

## Bloqueadores detectados
- `Cuestionario.tsx` finaliza localmente (sin POST de respuestas).
- Documentacion frontend confirma explicitamente que no hay envio al backend.
- Tipos frontend simplificados no corresponden a tipos backend.

## Clasificacion de hallazgos (externo)
- reusable_frontend_pattern: hook de carga y manejo base de estado.
- frontend_dependency: cliente GET active y mock dev.
- frontend_change_request: tipos, payloads y validaciones.
- frontend_blocker: ausencia de submit/result wiring.
