# Reporting and Dashboards (v2)

## Dashboards en tiempo real (API)
- Adopción histórica (`/dashboard/adoption-history`)
- Volumen de cuestionarios
- Crecimiento de usuarios
- Funnel de uso
- Retención/cohortes (vista consolidada)
- Productividad operativa
- Calidad de cuestionario y de datos
- Salud de API
- Monitoreo de modelos, drift y equity (vista operativa consolidada)
- Revisión humana y resumen ejecutivo

## Dataset combinado obligatorio
`adoption_history` incluye:
1. volumen y crecimiento
2. conversión creación -> procesado
3. retención/cohortes (proxy operativo)
4. capacidad operativa (procesados por usuario)

## Report jobs
- Endpoint: `POST /api/v2/reports/jobs`
- Tipos soportados:
  - `executive_monthly`
  - `adoption_history`
  - `model_monitoring`
  - `operational_productivity`
  - `security_compliance`
  - `traceability_audit`

## Persistencia
- `report_jobs`: estado de generación.
- `generated_reports`: archivo generado.
- `dashboard_aggregates`: snapshots consolidados.
- `service_health_snapshots` / `model_monitoring_snapshots`: soporte de observabilidad.

## Exportable a PDF
Los reportes se exportan en PDF para descarga operativa y auditoría.
