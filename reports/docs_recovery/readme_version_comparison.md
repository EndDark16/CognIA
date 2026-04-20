# README Version Comparison
Fecha: 2026-03-30

## Versiones comparadas
- Version simplificada (problematica): `f50b009:README.md`
- Version base recuperada: `042c940:README.md`
- Version final fusionada: `README.md` (working tree actual)

## Diferencia estructural principal
- `f50b009` redujo el README a enfoque de cierre ejecutivo.
- `042c940` mantenia cobertura tecnica-operativa completa.
- La version fusionada actual recupera estructura tecnica amplia y agrega explicitamente el estado final de cierre.

## Contenido valioso perdido en la version simplificada (recuperado)
- Arquitectura detallada por capas backend.
- Flujo de peticion de inferencia paso a paso.
- Tecnologias y dependencias clave.
- Seguridad/Auth (JWT, CSRF, MFA, RBAC, COLPSIC).
- Migraciones Alembic y notas operativas de esquema.
- Detalle de endpoints API (predict, questionnaires/evaluations, auth/admin).
- Seccion de despliegue Docker y observabilidad.
- Guia de ejecucion local/produccion.
- Contexto academico y limitaciones eticas completas.

## Contenido nuevo integrado en la fusion final
- Estado final validado por dominio con metricas oficiales de cierre.
- Separacion explicita tesis vs producto.
- Scope vigente de inferencia (`artifacts/inference_v4/`).
- Aclaracion de runtime minimo actual y su relacion con gobernanza de scope.
- Referencias directas a `reports/final_closure/` y `data/final_closure_audit_v1/`.
- Actualizacion de seccion de pruebas con la cobertura de modelos/inferencia agregada.

## Ajustes de precision documental aplicados
- Se elimino referencia desactualizada a `MONGO_URI` en configuracion.
- Se actualizo descripcion de inferencia para reflejar:
  - resolucion de modelos por dominio (`models/<domain>_model.pkl`),
  - runtime minimo vigente,
  - trazabilidad de decisiones en reportes de cierre/deploy.

## Resultado
README restaurado y actualizado con criterio conservador:
- **base historico-tecnica preservada**,
- **cierre final y alcance vigente integrados**,
- sin amputar contexto tecnico util.
