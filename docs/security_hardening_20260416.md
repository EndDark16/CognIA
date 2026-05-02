# Security Hardening Audit (2026-04-16)

## Scope
Backend API hardening pass covering:
- auth/JWT/CSRF/cookies,
- admin and role-protected surfaces,
- questionnaire runtime/v2 flows,
- shared links, uploads and file downloads,
- runtime-vs-spec exposure consistency.

## Findings (relevant)

1. Blueprint criticality risk:
- `questionnaire_runtime` and `questionnaire_v2` were imported with silent `try/except` fallback in app startup.
- Risk: critical routes could disappear in runtime without explicit failure.

2. Information disclosure in error payloads:
- Several v2/problem-report endpoints returned `details.reason=str(exc)` on unhandled failures.
- Risk: leaking internal exception strings and infrastructure details.

3. Shared-link abuse surface:
- Public shared access endpoint lacked explicit throttling and strict path-parameter validation in route layer.
- Risk: brute-force amplification and noisy invalid requests.

4. File download trust boundary:
- PDF download route accepted persisted absolute path without boundary check.
- Risk: path abuse if persisted path becomes tampered.

5. Upload MIME spoofing:
- Problem report attachment validation relied on declared MIME + extension only.
- Risk: content-type spoofing with non-image payload.

## Applied remediations

1. Optional blueprint policy (fail-fast configurable):
- `api/app.py` now loads optional blueprints via controlled loader with:
  - `OPTIONAL_BLUEPRINTS_STRICT` (default `true`)
  - `OPTIONAL_BLUEPRINTS_REQUIRED` (default `questionnaire_runtime,questionnaire_v2`)
- Required blueprint import failures now raise explicit runtime errors in strict mode.

2. Error payload hardening:
- Removed direct `str(exc)` leakage from:
  - `api/routes/questionnaire_v2.py`
  - `api/routes/problem_reports.py`
- Added server-side structured logging; responses now keep stable error codes.

3. Shared access hardening:
- Added payload validation for shared path params using `SharedAccessSchema`.
- Added route rate-limit for public share access:
  - `QV2_SHARED_ACCESS_RATE_LIMIT` (default `30 per minute`).

4. Download path guard:
- Added `resolve_download_path()` in `api/services/questionnaire_v2_service.py`.
- PDF download now enforces artifact path inside `artifacts/runtime_reports`.

5. Upload binary signature validation:
- Added signature checks in `api/services/problem_report_service.py` for:
  - PNG, JPEG, WEBP
- Rejects mismatched payloads with `attachment_content_mismatch`.

6. DTO/schema normalization:
- Added `api/schemas/questionnaire_runtime_schema.py`.
- Runtime v1 routes now validate payloads via schemas for:
  - draft create/save/submit,
  - section validation,
  - professional access/tag,
  - runtime admin template/version/disclosure/section/question flows.
- Admin clone endpoint now validated with `QuestionnaireCloneRequestSchema`.

## Added verification

- `tests/api/test_app_blueprint_policy.py`
  - strict mode fails fast on required optional blueprint import failure.
  - non-strict mode allows startup when optional module is absent.
- `tests/api/test_questionnaire_v2_api.py`
  - internal errors do not expose details.
  - shared path params are validated.
  - PDF download rejects paths outside runtime artifact root.
- `tests/test_problem_reports.py`
  - attachment content signature mismatch is rejected.
- `tests/api/test_questionnaire_runtime_api.py`
  - runtime draft payload validation coverage.

## Residual caveats

- This hardening pass preserves claim boundaries: output remains screening/support in simulated environment, not automated diagnosis.
- Some historical runtime/report payloads are intentionally flexible (`additionalProperties`) in OpenAPI for backward compatibility and traceability.
