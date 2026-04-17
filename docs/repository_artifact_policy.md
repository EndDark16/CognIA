# Repository Artifact Policy

## Objective
Keep CognIA reproducible and auditable without polluting Git history with heavy/runtime-derived files.

This policy defines:

1. What **must** be versioned.
2. What **must not** be versioned.
3. How to preserve traceability for non-versioned artifacts.

## Versioned (required)

- Source code:
  - `api/`, `app/`, `core/`, `config/`, `scripts/`
- Infrastructure/config templates:
  - `alembic.ini`, `docker-compose.yml`, `Dockerfile`, `.env.example`
- Migrations:
  - `migrations/versions/`
- Tests:
  - `tests/`
- Product/API docs:
  - `README.md`, `docs/`
  - OpenAPI activo en `docs/openapi.yaml` (snapshots historicos en `docs/archive/openapi/`)
- Governance and handoff:
  - `AGENTS.md`, `docs/HANDOFF.md`
- Traceability source-of-truth artifacts that are compact and non-secret:
  - closure decisions
  - inventories
  - manifests required to audit final selections

## Versioned (allowed with caveat)

- Curated compact CSV/MD reports used as source of truth for closure decisions.
- Small static assets required by runtime (`static/`, `templates/`).
- Minimal runtime model pointers/contracts.

If an artifact is large, regenerated, or duplicative, prefer external storage + manifest.

## Not versioned

- Secrets and local env:
  - `.env`, `.env.*` (except `.env.example`)
  - API keys, tokens, credentials
- Runtime uploads and generated user files:
  - problem report attachments
  - runtime generated PDF exports
- Build/cache/temp:
  - `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`
  - `tmp/`, `temp/`, `*.tmp`, `*.log`
- Local virtual environments:
  - `venv/`, `.venv/`, `env/`
- Editor/OS noise:
  - `.vscode/`, `.idea/`, `.DS_Store`, `Thumbs.db`
  - `.codex/` (contexto local de agentes/herramientas)
- Heavy model/data binaries unless explicitly approved:
  - `*.pkl`, `*.joblib`, `*.onnx`, `*.npy`, `*.npz`
  - generated intermediate datasets/exports

## Traceability for non-versioned artifacts

When an artifact is excluded from Git, keep a manifest containing:

- logical artifact name
- campaign/version
- generation timestamp
- script/command used
- checksum (if available)
- storage locator/path

Recommended location:

- `artifacts/<campaign>/...manifest.json`
- `reports/<campaign>/..._summary.md`

## Regeneration ownership

- Engineering owner regenerates technical artifacts with scripts in `scripts/`.
- Data/model owner regenerates model/data outputs from registered campaign scripts.
- Docs owner updates narrative and source-of-truth references in `docs/` and `README.md`.

## Enforcement

- `.gitignore` is the first enforcement layer.
- PR review checks:
  - no secrets
  - no accidental heavy uploads
  - no runtime-generated user files
  - manifests/docs updated when moving artifacts out of Git
