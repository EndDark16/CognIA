# Questionnaire Runtime v1 - Arquitectura final

## Alcance funcional
- Sistema real de cuestionario multipaso versionado para 5 dominios: `adhd`, `conduct`, `elimination`, `anxiety`, `depression`.
- Flujo operacional: `draft -> submitted -> processing -> completed|failed -> deleted_by_user`.
- Persistencia completa de respuestas, resultados por dominio, metadata de modelo y trazabilidad.
- Acceso profesional por `reference_id + PIN` (PIN hash, nunca en texto plano).

## Actores
- **Cuidador/usuario**: crea borrador, guarda avance, envia, consulta historial/resultados, exporta, borra (soft delete).
- **Psicologo/profesional**: accede por referencia+PIN, revisa respuestas/resultados detallados, etiqueta estado, libera acceso.
- **Admin**: versiona cuestionario, disclosures/consentimiento, publica versiones.

## Componentes backend implementados
- Modelos DB nuevos `qr_*` en `app/models.py`.
- Servicio central `api/services/questionnaire_runtime_service.py`.
- API nueva `api/routes/questionnaire_runtime.py`.
- Registro de rutas en `api/app.py`.
- Configuracion runtime en `config/settings.py`.
- Migracion: `migrations/versions/20260330_01_add_questionnaire_runtime_v1.py`.

## Alineacion de dominio Elimination
- Elimination se incluye en flujo de producto y resultados.
- Se adjunta `model_status = experimental_line_more_useful_not_product_ready` y caveat explicito por dominio.
- No se oculta en API; se controla con metadata de madurez y advertencias.

## Versionado
- `QRQuestionnaireTemplate` + `QRQuestionnaireVersion`.
- Versiones publicadas son inmutables en uso (nuevas iteraciones van en nuevas versiones).
- Consentimiento y disclaimers versionados por `QRDisclosureVersion` y vinculados por evaluacion.

## Insumos de diseno usados
- `reports/questionnaire_real_design_discovery/*`
- `reports/final_closure/*`
- `reports/final_closure_audit_v1/*`
- `artifacts/specs/*`
- `artifacts/inference_v4/*`
- Runtime de modelos en `models/champions/rf_*_current`
