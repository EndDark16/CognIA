# CognIA API Full Reference

## Purpose
Operational API reference for backend consumers and maintainers.

- Canonical machine-readable contract: `docs/openapi.yaml`
- This document: maintainers' overview of modules, auth, pagination and error patterns.

## Base conventions

- Base path: `/api` (plus versioned groups such as `/api/v1/*`, `/api/v2/*`).
- Auth: JWT Bearer for protected endpoints.
- Error shape:
  - `{"msg": "<human_message>", "error": "<stable_code>", "details": {...optional...}}`
- Pagination convention:
  - query params: `page`, `page_size`
  - response: `pagination = {page, page_size, total, pages}`

## Endpoint groups

## 1) Auth and MFA
- `/api/auth/register`
- `/api/auth/login`
- `/api/auth/login/mfa`
- `/api/auth/refresh`
- `/api/auth/logout`
- `/api/auth/me`
- `/api/auth/password/change`
- `/api/auth/password/forgot`
- `/api/auth/password/reset`
- `/api/auth/password/reset/verify`
- `/api/mfa/setup`
- `/api/mfa/confirm`
- `/api/mfa/disable`

## 2) Admin
- `/api/admin/users` (list, patch)
- `/api/admin/users/{user_id}` (patch)
- `/api/admin/users/{user_id}/password-reset`
- `/api/admin/users/{user_id}/mfa/reset`
- `/api/admin/audit-logs`
- `/api/admin/questionnaires` (list, publish/archive/clone)
- `/api/admin/questionnaires/{template_id}/publish|archive|clone`
- `/api/admin/psychologists/{user_id}/approve|reject`
- `/api/admin/evaluations` (+ status update)
- `/api/admin/roles`
- `/api/admin/users/{user_id}/roles`
- `/api/admin/email/unsubscribes`
- `/api/admin/email/health`
- `/api/admin/metrics`

## 3) Questionnaires v1 (legacy template management)
- `/api/v1/questionnaires/active`
- `/api/v1/questionnaires`
- `/api/v1/questionnaires/{template_id}/questions`

Legacy v1 endpoints removed in 2026-04-15:
- `POST /api/v1/questionnaires/{template_id}/activate`
- `POST /api/v1/questionnaires/active/clone`

Operational replacements:
- `POST /api/admin/questionnaires/{template_id}/publish`
- `POST /api/admin/questionnaires/{template_id}/clone`

## 4) Evaluations v1
- `/api/v1/evaluations` (create/list/get/update/delete)
- plus access-key/professional actions where applicable in existing routes

## 5) Questionnaire runtime v1
- `/api/v1/questionnaire-runtime/questionnaire/active`
- `/api/v1/questionnaire-runtime/evaluations/*`
- `/api/v1/questionnaire-runtime/professional/*`
- `/api/v1/questionnaire-runtime/notifications/*`
- `/api/v1/questionnaire-runtime/admin/*`

## 6) Questionnaire operational v2
- `/api/v2/questionnaires/active`
- `/api/v2/questionnaires/sessions/*`
- `/api/v2/questionnaires/history/*`
- `/api/v2/questionnaires/shared/{questionnaire_id}/{share_code}`
- `/api/v2/questionnaires/history/{id}/pdf/*`
- `/api/v2/dashboard/*`
- `/api/v2/reports/jobs`

## 7) Problem reports
- `POST /api/problem-reports`
- `GET /api/problem-reports/mine`
- `GET /api/admin/problem-reports`
- `GET /api/admin/problem-reports/{id}`
- `PATCH /api/admin/problem-reports/{id}`

Details and payloads:
- `docs/problem_reporting_backend.md`

## 8) Predict / health / docs / metrics
- `/api/predict`
- `/healthz`
- `/readyz`
- `/metrics`
- `/docs`
- `/openapi.yaml`

## Permissions matrix (high-level)

- Anonymous:
  - health/readiness/docs/openapi
- Authenticated users:
  - profile/auth lifecycle
  - own questionnaire flows
  - create/list own problem reports
- Psychologist:
  - psychologist workflow endpoints
- Admin:
  - admin governance endpoints
  - global problem-report management

## Error code examples

- `validation_error`
- `invalid_user`
- `forbidden`
- `rate_limited`
- `db_error`
- `problem_report_create_failed`
- `problem_report_update_failed`

## Documentation maintenance workflow

When adding or changing endpoints:

1. Update route code.
2. Update schema/validation.
3. Update `docs/openapi.yaml`.
4. Update this file and domain-specific docs.
5. Add/adjust tests for request + response + permissions.

Runtime/spec guardrail:
- `pytest tests/contracts/test_openapi_runtime_alignment.py -q`
