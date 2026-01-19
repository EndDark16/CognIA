# Contributing

Thanks for contributing to CognIA. This project uses a simple branch flow and
lightweight PR process.

## Branch flow
- `main`: production-ready releases only.
- `development`: integration branch.
- `dev.enddark`: active development branch for day-to-day work.

## How to work
1) Sync your local branches:
   - `git checkout dev.enddark`
   - `git pull origin dev.enddark`
2) Create a feature branch from `dev.enddark`:
   - `git checkout -b feat/<short-name>`
3) Make your changes, then run tests:
   - `pytest`
4) Commit with a clear message (example):
   - `feat: add health and metrics endpoints`
5) Push and open a PR to `dev.enddark`.
6) After review, merge `dev.enddark` into `development`.
7) Merge `development` into `main` only for final releases.

## PR checklist
- Tests pass locally (`pytest`).
- No secrets committed (`.env`, keys, credentials).
- README updated if behavior or setup changed.

## Notes
- Keep commits small and focused.
- Prefer one topic per PR.
