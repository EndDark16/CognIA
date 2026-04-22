# Frontend handoff - API contract (backend listo)

## Autenticaci?n
- Todos los endpoints requieren JWT.
- Endpoints `/admin/*` requieren rol `ADMIN`.
- Endpoints `/professional/*` requieren rol profesional (`PSYCHOLOGIST` o `user_type=psychologist`).

## Contrato base de resultado
- Resultado por dominio incluye al menos:
  - `domain`, `risk_band`, `confidence_level`, `evidence_level`
  - `uncertainty_flag`, `abstention_flag`
  - `recommendation_text`, `explanation_short`
  - `model_status`, `caveats`
- En audiencia profesional agrega:
  - `probability`, `threshold_used`, `model_name`, `model_version`, `contributors`

## Estados UI requeridos
- `draft`, `submitted`, `processing`, `completed`, `failed`, `deleted_by_user`.

