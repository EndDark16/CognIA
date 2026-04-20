# Markdown Fix Log
Fecha: 2026-03-30

## Cambios aplicados

| Archivo | Tipo de problema | Cambio realizado | Motivo |
| --- | --- | --- | --- |
| `README.md` | Perdida de contexto tecnico por simplificacion excesiva | Se restauro base completa desde `042c940` y se fusiono con estado final vigente (dominios, scope tesis/producto, inference_v4, cierre final, testing reciente). | Recuperar trazabilidad tecnica sin perder informacion de cierre. |
| `README.md` | Referencia de configuracion desactualizada | Se reemplazo referencia a `MONGO_URI` por variables reales de DB/JWT/CORS/MFA/rate limits. | Evitar inconsistencia con `config/settings.py`. |
| `README.md` | Ambiguedad entre scope metodologico y runtime expuesto | Se agrego nota explicita en secciones de evaluaciones/motor de IA y cierre documental. | Evitar interpretaciones erroneas sobre despliegue actual. |
| `reports/final_closure/inference_scope_final.md` | Ambiguedad scope vs implementacion runtime | Se agrego seccion de nota de implementacion backend. | Coherencia documental con deploy/runtime actual. |
| `reports/final_closure/product_scope_final.md` | Ambiguedad de alcance productivo vs endpoint actual | Se agrego nota de runtime backend. | Clarificar que alcance metodologico y exposicion API no son sinonimos en esta iteracion. |
| `reports/final_closure/final_project_closure_report.md` | Falta de nota operacional sobre runtime | Se agrego nota puntual en decision de inferencia. | Consolidar consistencia entre reportes de cierre y deploy. |
| `data/README.md` | Archivo vacio | Se documento rol del directorio `data/`, regla de lectura y carpetas clave. | Mejorar orientacion y trazabilidad. |
| `artifacts/inference_v4/promotion_scope.md` | Documento minimalista y ambiguo | Se normalizo estructura (estado, dominios, referencias y nota de vigencia). | Mejorar claridad operacional. |
| `artifacts/inference_v5/elimination_scope_rationale.md` | Potencial contradiccion con cierre final | Se marco explicitamente como registro historico no vigente. | Evitar que se interprete como scope activo. |

## Cambios no aplicados (intencional)
- No se reescribieron reportes historicos de fases (`data/*_v*/reports/`) para no alterar evidencia versionada.
- No se consolidaron aun los roadmaps duplicados de `reports/audit/roadmaps/`; se deja recomendacion editorial futura.
