# Input coverage summary

- Filas auditadas (input x dominio): **353**
- Inputs caregiver-answerable: **294**
- Inputs self-report-only: **59**
- Inputs marcados como derivables/proxy: **58**
- Preguntas incluidas en questionnaire_basic_candidate_v1: **49**

## Cobertura por dominio
- `adhd`: caregiver=25/35 | self-report=10/35
- `anxiety`: caregiver=212/260 | self-report=48/260
- `conduct`: caregiver=22/23 | self-report=1/23
- `depression`: caregiver=18/18 | self-report=0/18
- `elimination`: caregiver=17/17 | self-report=0/17

## Observaciones
- `anxiety` y `adhd` mantienen mayor dependencia de familias con componente self-report (SCARED-SR / YSR).
- `elimination` depende casi por completo de señales caregiver (CBCL/SDQ) y sistema.
- Los metadatos `site` y `release` pueden llenarse por sistema sin intervención del cuidador.
