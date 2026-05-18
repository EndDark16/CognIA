# Admin Reports Contract (QV2)

## Endpoints
- `POST /api/v2/reports/jobs`
- `GET /api/v2/reports/jobs/{report_job_id}`
- `GET /api/v2/reports/jobs/{report_job_id}/download`

## Auth and Permissions
- JWT bearer required.
- Admin role required (`roles` claim contains `ADMIN`).
- Non-admin users receive `403 admin_required`.

## Supported `report_type`
- `executive_summary`
- `adoption_history`
- `user_growth`
- `questionnaire_volume`
- `funnel`
- `retention`
- `productivity`
- `questionnaire_quality`
- `data_quality`
- `api_health`
- `model_monitoring`
- `drift`
- `equity`
- `human_review`

Backward-compatible aliases:
- `executive_monthly` -> `executive_summary`
- `operational_productivity` -> `productivity`
- `security_compliance` -> `api_health`
- `traceability_audit` -> `model_monitoring`

## Request body (`POST /reports/jobs`)
```json
{
  "report_type": "executive_summary",
  "months": 6,
  "date_from": "2026-01-01",
  "date_to": "2026-05-31",
  "granularity": "month",
  "format": "pdf",
  "filters": {
    "role": "guardian",
    "mode": "complete",
    "status": "processed",
    "domain": "anxiety",
    "include_sections": [
      "Crecimiento de usuarios",
      "Volumen de cuestionarios"
    ]
  }
}
```

Notes:
- `months` remains supported.
- `format` currently accepts only `pdf`.
- Unsupported filter keys are ignored and returned in `warnings`.
- Invalid date range (`date_from > date_to`) returns `400`.

## Metadata/Preview response (`GET /reports/jobs/{id}`)
```json
{
  "report_job_id": "uuid",
  "report_type": "executive_summary",
  "status": "completed",
  "file_name": "report_executive_summary_....pdf",
  "download_url": "/api/v2/reports/jobs/{id}/download",
  "filters": {
    "status": "processed"
  },
  "period": {
    "months": 6,
    "date_from": "2026-01-01",
    "date_to": "2026-05-31"
  },
  "summary": {
    "title": "Reporte executive_summary",
    "headline_metrics": [
      {"label": "Usuarios nuevos", "value": 42},
      {"label": "Cuestionarios completados", "value": 87}
    ],
    "sections": [
      {
        "title": "Crecimiento de usuarios",
        "description": "Evolucion temporal de altas de usuarios en el periodo.",
        "chart_type": "line",
        "available": true
      }
    ]
  },
  "warnings": [],
  "created_at": "2026-05-18T00:00:00+00:00",
  "completed_at": "2026-05-18T00:00:05+00:00"
}
```

## Download (`GET /reports/jobs/{id}/download`)
- Returns the generated PDF.
- Uses secure path resolution under runtime reports directory.
- `404 report_file_not_found|report_file_missing` when file is absent or outside allowed path.
