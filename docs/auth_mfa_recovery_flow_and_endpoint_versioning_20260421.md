# Auth + MFA Recovery Flow and Endpoint Versioning (2026-04-21)

## Objetivo
Documentar, endpoint por endpoint, el estado contractual vigente (`ACTIVE`, `ACTIVE_BUT_LEGACY`, `DEPRECATED`) y dejar explícito el flujo completo de recovery codes MFA.

## 1) Endpoint Map (Auth/MFA)
| Área | Endpoint | Método | Estado contractual | Reemplazo / Nota |
| --- | --- | --- | --- | --- |
| Auth | `/api/auth/register` | `POST` | `ACTIVE` | Registro operativo vigente |
| Auth | `/api/auth/login` | `POST` | `ACTIVE` | Acepta `identifier` (username/email), también `username` o `email` por compatibilidad |
| Auth | `/api/auth/login/mfa` | `POST` | `ACTIVE` | Segundo factor con TOTP o `recovery_code` |
| Auth | `/api/auth/refresh` | `POST` | `ACTIVE` | Rotación de refresh cookie + CSRF |
| Auth | `/api/auth/logout` | `POST` | `ACTIVE` | Revocación de refresh |
| Auth | `/api/auth/me` | `GET` | `ACTIVE` | Perfil autenticado |
| Auth | `/api/auth/password/change` | `POST` | `ACTIVE` | Cambio autenticado |
| Auth | `/api/auth/password/forgot` | `POST` | `ACTIVE` | Inicio reset por email |
| Auth | `/api/auth/password/reset` | `POST` | `ACTIVE` | Aplicar token reset |
| Auth | `/api/auth/password/reset/verify` | `GET` | `ACTIVE` | Verificar token reset |
| MFA | `/api/mfa/setup` | `POST` | `ACTIVE` | Inicializa secreto TOTP |
| MFA | `/api/mfa/confirm` | `POST` | `ACTIVE` | Activa MFA y emite recovery codes |
| MFA | `/api/mfa/disable` | `POST` | `ACTIVE` | Desactiva MFA con password + TOTP/recovery |
| MFA | `/api/mfa/recovery-codes/status` | `GET` | `ACTIVE` | Nuevo: estado operativo de recovery codes |
| MFA | `/api/mfa/recovery-codes/regenerate` | `POST` | `ACTIVE` | Nuevo: rotación completa de recovery codes |

## 2) Legacy vs Updated (contexto operativo)
| Endpoint legacy | Método | Estado | Endpoint actualizado |
| --- | --- | --- | --- |
| `/api/v1/questionnaires/{template_id}/activate` | `POST` | Retirado (2026-04-15) | `/api/admin/questionnaires/{template_id}/publish` |
| `/api/v1/questionnaires/active/clone` | `POST` | Retirado (2026-04-15) | `/api/admin/questionnaires/{template_id}/clone` |
| `/api/predict` | `POST` | `DEPRECATED` | Flujo recomendado: `questionnaire_runtime` v1 y `questionnaire_v2` |

## 3) Flujo completo de Recovery Code (vigente)
1. Usuario completa `POST /api/mfa/setup`.
2. Usuario confirma con `POST /api/mfa/confirm` (`code` TOTP).
3. Backend devuelve `recovery_codes` (solo una vez en texto plano).
4. En login con MFA:
   - `POST /api/auth/login` -> `mfa_required + challenge_id`.
   - `POST /api/auth/login/mfa` con `code` o `recovery_code`.
5. Monitoreo de disponibilidad:
   - `GET /api/mfa/recovery-codes/status`.
6. Rotación segura cuando baja inventario o por política:
   - `POST /api/mfa/recovery-codes/regenerate` con `password` + (`code` o `recovery_code`).
7. Al desactivar MFA:
   - `POST /api/mfa/disable` con `password` + (`code` o `recovery_code`), invalida recovery codes previos.

## 4) Criterios operativos de seguridad
- Recovery codes son de un solo uso.
- Recovery code consumido no puede reutilizarse.
- Regeneración invalida todos los códigos anteriores.
- El flujo exige verificación fuerte (password + segundo factor).
- Claim de plataforma se mantiene: screening/apoyo profesional; no diagnóstico automático.
