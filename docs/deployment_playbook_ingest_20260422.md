# Deployment Playbook Ingest (2026-04-22)

## Source used
- External file received in this session:
  - `C:\Users\andre\Downloads\readme_deployment_summary.txt`
- Scope of source:
  - Ubuntu + Docker Compose deployment,
  - Nginx gateway,
  - Cloudflare Tunnel + Access,
  - self-hosted GitHub Actions runners,
  - backup and hardening checklist.

## Methodological status
- This document captures operational deployment guidance.
- It does not change the methodological claim of the project:
  - simulated environment,
  - screening/professional support,
  - no automatic clinical diagnosis.

## Target architecture from the provided source
- Ubuntu host
- Docker + Docker Compose
- PostgreSQL container
- Flask backend container
- Frontend static container (React/Vite + Nginx)
- Gateway Nginx container
- Cloudflare Tunnel for public exposure
- Cloudflare Access for `/docs` and `/openapi.yaml`
- Self-hosted runners for auto-deploy

## What is currently versioned in this backend repo
- Present:
  - `Dockerfile`
  - `docker-compose.yml`
- Not present in this backend repo at the time of this ingest:
  - `.deploy/` backend deployment folder from the external guide
  - `deploy_wsgi.py`
  - `gateway/default.conf`
  - workflow files described in the external guide:
    - `.github/workflows/deploy-backend.yml`
    - `.github/workflows/deploy-frontend.yml`

## Backend operational conclusions
- There is enough backend-side evidence to document a concrete deployment line (Docker/Docker Compose + Flask + Postgres + reverse proxy pattern).
- Full end-to-end production confirmation remains `por confirmar` until:
  - deployment files described in the external playbook are versioned in the corresponding repositories,
  - environment execution evidence (live compose/services and release trace) is published as auditable artifact.

## Frontend/integration clarifications (out of backend-only scope)
- Frontend build/container and frontend runner workflow are external to this backend repository.
- They are kept here as integration notes only and must be validated in the frontend repository and infra runtime.

## Recommended next backend documentation state
- Keep point 21 as `parcial` (not `cerrado`), now with explicit external deployment evidence reference.
- Keep integration caveat for frontend/infra as `por confirmar` when not versioned in this repo.
