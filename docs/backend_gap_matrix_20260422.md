# Backend Gap Matrix (2026-04-22)

## Objetivo
Documento de verificacion backend para los puntos 9-25 solicitados en revision.

Regla metodologica que no cambia:
- CognIA en este repositorio aplica a entorno simulado de screening/apoyo profesional.
- No se permite claim de diagnostico clinico automatico.

## Resumen ejecutivo
- Implementado y verificable en codigo: puntos `9`, `10`, `22` (normalizacion parcial con alias), y parte de `12`, `15`, `18`, `24`.
- Parcial o no confirmado end-to-end: `12`, `13`, `14`, `15`, `18`, `20`, `21`, `23`.
- Fuera de alcance backend puro o dependiente de frontend/operacion externa: `11`, `16`, `17`, `19`, `24` (consumo frontend), `25` (claim de producto/compliance).

## Matriz 9-25 (estado backend)

### 9) Cargador exacto del modelo + serializacion
- Estado: `implementado y verificable`.
- Evidencia backend:
  - `api/services/questionnaire_v2_service.py` usa `joblib.load` para artefactos runtime.
  - `api/services/questionnaire_runtime_service.py` usa `joblib.load` para champions runtime v1.
  - `api/services/questionnaire_v2_loader_service.py` resuelve `artifact_path` y `fallback_artifact_path`.
- Documentacion reforzada: `docs/model_registry_and_inference.md`.

### 10) Traduccion respuesta -> feature de inferencia
- Estado: `implementado y verificable`.
- Evidencia backend:
  - Catalogo y `feature_key` versionados en entidades v2.
  - Guardado de respuestas por sesion y armado de `feature_map` en `api/services/questionnaire_v2_service.py`.
  - Repeat mapping e internal features soportadas por loader/servicio v2.
- Alcance: trazabilidad tecnica backend confirmada; validacion UX completa corresponde al cliente.

### 11) Cumplimiento clinico/interoperabilidad sanitaria/adopcion asistencial real
- Estado: `por confirmar` (no demostrable desde este repo).
- Nota: backend/documentacion sostienen entorno simulado para screening/apoyo, no practica clinica automatizada.

### 12) Consentimiento formal en interfaz final
- Estado: `parcial`.
- Evidencia backend:
  - Runtime v1 mantiene disclosures versionados y `consent_accepted_at`.
  - Endpoints/admin de disclosures presentes en runtime v1.
- Gap: cierre contractual uniforme en UX final v2/front por confirmar.

### 13) Cifrado de datos en reposo
- Estado: `por confirmar`.
- Evidencia parcial:
  - cifrado/uso seguro para secreto MFA.
- Gap: no hay prueba backend en repo de cifrado at-rest general de DB/storage.

### 14) Gestion formal de secretos
- Estado: `parcial`.
- Evidencia:
  - configuracion por variables de entorno en `.env.example`/settings.
- Gap: no se verifica secret manager formal (Vault/KMS equivalente) en esta revision.

### 15) Retencion/borrado/recuperacion end-to-end
- Estado: `parcial`.
- Evidencia backend:
  - campos runtime v1 `retention_until`, `deleted_at`, `deleted_by_user`.
  - rutas de borrado y estados asociados en runtime v1.
- Gap: politica completa y verificacion extremo a extremo de recuperacion: `por confirmar`.

### 16) Proteccion del frontend frente a manipulacion del cliente
- Estado: `frontend/integracion (por confirmar desde backend)`.
- Evidencia backend:
  - validaciones de schemas, permisos, rate limits y hardening.
- Gap: robustez del cliente en frontend no verificable en este repo.

### 17) SSO/federacion/directorios externos
- Estado: `no implementado/por confirmar`.
- Evidencia actual: auth local JWT + MFA + roles.

### 18) Monitoreo productivo integral/tracing/SIEM
- Estado: `parcial`.
- Evidencia backend:
  - `/healthz`, `/readyz`, `/metrics`, logs y snapshots de monitoreo de modelo en datos.
- Gap: no se observa tracing distribuido ni SIEM integral verificado.

### 19) Tests E2E frontend
- Estado: `fuera de alcance backend`.
- Evidencia: en repo hay pruebas API/backend, no E2E de cliente.

### 20) Cobertura porcentual global de pruebas
- Estado: `por confirmar`.
- Evidencia: existe `pytest` amplio, pero sin reporte de cobertura global versionado en esta revision.

### 21) Despliegue productivo definitivo/plataforma unica
- Estado: `parcial`.
- Evidencia:
  - hay `Dockerfile`, `docker-compose.yml`, politicas y hotfixes de arranque documentados.
  - evidencia operativa externa recibida en sesion (`readme_deployment_summary.txt`) incorporada en `docs/deployment_playbook_ingest_20260422.md`.
- Gap: validacion de despliegue productivo definitivo unico en operacion real: `por confirmar`.

### 22) Normalizacion guardian vs caregiver
- Estado: `parcialmente implementado (backend)`.
- Evidencia:
  - contrato publico v2/runtime usa `guardian`.
  - compatibilidad legacy preservada con alias `caregiver -> guardian` en loader/servicios.
- Gap: persisten referencias historicas `caregiver_*` en `mode_key` y artefactos, por trazabilidad.

### 23) Correspondencia exacta artefactos historicos cuestionario <-> UX actual
- Estado: `parcial`.
- Evidencia backend:
  - source pointers/versionado y mappings disponibles.
- Gap: correspondencia exacta con UX final del cliente depende de frontend; `por confirmar`.

### 24) Garantia de exposicion frontend de todos los flujos runtime backend
- Estado: `backend documentado; integracion frontend por confirmar`.
- Hallazgo tecnico:
  - existen flujos paralelos v1 (legacy) y v2 (operacional actual).
  - hay endpoints v1 que se superponen funcionalmente con admin/v2.
- Accion documental en esta sesion:
  - se marca deprecacion y reemplazo recomendado en OpenAPI para endpoints legacy solapados.

### 25) Claim de diagnostico clinico automatico
- Estado: `rechazado explicitamente`.
- Evidencia:
  - README y OpenAPI sostienen screening/apoyo profesional en entorno simulado.
  - no debe publicarse claim de diagnostico automatico.

## Mapa operativo de endpoints superpuestos (punto 24)
- `POST /api/v1/questionnaires/{template_id}/activate`
  - Estado: legacy activo por compatibilidad.
  - Uso recomendado: `POST /api/admin/questionnaires/{template_id}/publish`.
- `POST /api/v1/questionnaires/active/clone`
  - Estado: legacy activo por compatibilidad.
  - Uso recomendado: `POST /api/admin/questionnaires/{template_id}/clone`.
- Flujo nuevo de producto:
  - usar `api/v2/questionnaires/*` para sesiones, respuestas, submit, historial, PDF, share.

## Pipeline de entrenamiento visible en codigo (aclaracion)
- El repositorio si contiene scripts de entrenamiento/auditoria/versionado (campanas `scripts/run_hybrid_*`, `scripts/run_*ceiling*`, `scripts/run_*retrain*`).
- La fuente operativa del runtime no es "reentrenar en linea", sino los freezes versionados + registro de modelos + inferencia.
- Esto es consistente con separar entrenamiento offline y consumo runtime trazable.
