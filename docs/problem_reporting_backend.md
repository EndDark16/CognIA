# Problem Reporting Backend

## Scope
This module adds operational support for frontend "Reportar un problema" flows in a backend-safe way:

- End-user report creation (authenticated users).
- Admin-only listing, filtering, detail, and state management.
- Optional screenshot attachment persisted with local storage strategy.
- Audit trail for report lifecycle events.

This is **support/screening platform telemetry**, not clinical diagnosis logic.

## Data Model
Implemented tables:

- `problem_reports`
- `problem_report_attachments`
- `problem_report_audit_events`

Migration:

- `migrations/versions/20260415_01_add_problem_reports.py`

### `problem_reports` core fields
- `id` (UUID)
- `report_code` (human-readable code, unique)
- `reporter_user_id`, `reporter_role`
- `issue_type`, `description`
- `source_module`, `source_path`
- `related_questionnaire_session_id`, `related_questionnaire_history_id`
- `status` (`open`, `triaged`, `in_progress`, `resolved`, `rejected`)
- `admin_notes`, `resolved_at`
- `attachment_count`, `metadata_json`
- `created_at`, `updated_at`

### Attachment strategy
By default attachments are stored in:

- `artifacts/problem_reports/uploads`

Configurable via:

- `PROBLEM_REPORT_UPLOAD_DIR`
- `PROBLEM_REPORT_MAX_ATTACHMENT_BYTES`
- `PROBLEM_REPORT_ALLOWED_MIME_TYPES`

Current allowed MIME defaults:

- `image/png`
- `image/jpeg`
- `image/webp`

## API Endpoints

### User endpoints
- `POST /api/problem-reports`
  - Auth: JWT required
  - Purpose: create new problem report
  - Payload (JSON or multipart form fields):
    - `issue_type` (required)
    - `description` (required)
    - `attachment` (optional, multipart)
    - `source_module` (optional)
    - `source_path` (optional)
    - `related_questionnaire_session_id` (optional)
    - `related_questionnaire_history_id` (optional)
    - `metadata` (optional)
- `GET /api/problem-reports/mine`
  - Auth: JWT required
  - Purpose: list own reports with pagination

### Admin endpoints
- `GET /api/admin/problem-reports`
  - Auth: `ADMIN`
  - Supports filters: `status`, `issue_type`, `reporter_role`, `q`, `from_date`, `to_date`
  - Supports pagination and sort (`created_at`, `updated_at`, `resolved_at`, `status`, `issue_type`)
- `GET /api/admin/problem-reports/{id}`
  - Auth: `ADMIN`
  - Purpose: report detail
- `PATCH /api/admin/problem-reports/{id}`
  - Auth: `ADMIN`
  - Purpose: update `status` and/or `admin_notes`

## Validation and Permissions

- Create report:
  - Any authenticated active user can create.
  - `issue_type` is constrained to controlled values.
  - `description` has length constraints.
- Admin operations:
  - Only users with `ADMIN` role in JWT claims can list/detail/update.
- Non-admin users cannot access admin problem-report endpoints.

## Audit and Traceability

- `problem_report_audit_events` records lifecycle events such as:
  - creation
  - attachment upload
  - admin updates
- Global audit log also records:
  - `PROBLEM_REPORT_CREATED`
  - `PROBLEM_REPORT_UPDATED`

## Testing

Implemented tests in:

- `tests/test_problem_reports.py`

Coverage includes:

- valid report creation
- invalid payload validation
- attachment upload
- unauthorized access behavior
- admin listing with pagination
- non-admin access denied to admin list/update
- admin filtering and status updates
